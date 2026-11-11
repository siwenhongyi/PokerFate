"""G5 recommendations must be observational and share the real decision node."""

from copy import deepcopy
import json
import queue
import threading
from types import SimpleNamespace

import pytest

from pokerfate.api import BotDecision, PlayerInfo, PokerFateAPI
from pokerfate.core.game_state import Action, ActionType, GameState, Player, Street
from pokerfate.decision.g5_engine import G5EngineOptions, G5JsonDecisionEngine
from pokerfate.decision.g5_shadow import G5ShadowObserver
from pokerfate.logger import _JsonlWriter
from scripts.g5_json_worker import G5Worker


class FakeEngine:
    def __init__(self, options):
        self.histories = []
        self.states = []
        self.starts = []
        self.last_result = {"checkCallEV": 1.0}
        self.closed = False

    def preflight(self):
        return {}

    def start_hand(self, **kwargs):
        self.starts.append(deepcopy(kwargs))
        self.histories.append([])

    def deal_hole_cards(self, **kwargs):
        self.histories[-1].append(("hole", kwargs))

    def deal_board(self, **kwargs):
        self.histories[-1].append(("board", kwargs))

    def notify_action(self, **kwargs):
        self.histories[-1].append(("action", kwargs))

    def decide(self, gs, **kwargs):
        self.states.append(deepcopy(gs))
        return Action(ActionType.FOLD)

    def shutdown(self):
        self.closed = True


def state():
    return GameState(players=[Player(0, "hero", 99), Player(1, "villain", 98)],
                     pot=3, current_bet=2, street=Street.PREFLOP)


def start(observer, hand=1, seeds=None):
    observer.start_hand(players=state().players, dealer_id=0, hand_number=hand,
                        hero_player_id=0, big_blind=2, small_blind=1,
                        seed_payload=seeds or [])
    observer.hole_cards(["As", "Kd"])


def submit(observer, gs=None):
    return observer.submit(gs or state(), my_current_bet=1,
                           decision=BotDecision("call"), source="pokerfate")


def confirm(observer, action="call"):
    observer.action(player_id=0, action=action, amount_added=1,
                    total_bet_after=2, street="preflop")


def test_fold_recommendation_never_enters_next_real_history():
    rows = queue.Queue()
    engine = FakeEngine(None)
    observer = G5ShadowObserver(G5EngineOptions("unused"), rows.put, engine_factory=lambda _: engine)
    try:
        start(observer)
        first_id = submit(observer)
        first = rows.get(timeout=3)
        assert first["action"] == "fold"
        confirm(observer)
        execution = rows.get(timeout=3)
        assert execution["decision_id"] == first_id
        assert execution["executed_action"]["action"] == "call"
        observer.action(player_id=1, action="raise", amount_added=4,
                        total_bet_after=6, street="preflop")
        second_id = submit(observer)
        second = rows.get(timeout=3)
        assert second["status"] == "ok"
        assert second_id != first_id
        assert [p["action"] for kind, p in engine.histories[-1] if kind == "action"] == ["call", "raise"]
        assert all(s["fresh_game"] for s in engine.starts)
    finally:
        observer.close()
    assert engine.closed
    assert not observer._thread.is_alive()


def test_async_snapshot_freezes_history_state_seeds_and_original_hand():
    entered, release = threading.Event(), threading.Event()
    rows = queue.Queue()

    class BlockedEngine(FakeEngine):
        def preflight(self):
            entered.set()
            assert release.wait(3)

    engine = BlockedEngine(None)
    observer = G5ShadowObserver(G5EngineOptions("unused"), rows.put, engine_factory=lambda _: engine)
    try:
        seeds = [{"name": "uid:1", "vpip_positive": 3}]
        start(observer, hand=7, seeds=seeds)
        gs = state()
        submit(observer, gs)
        assert entered.wait(3)  # submit returned while G5 is blocked
        seeds[0]["vpip_positive"] = 999
        gs.players[0].stack = 0
        observer.board(["2s", "3s", "4s"], "flop")
        start(observer, hand=8)
        release.set()
        row = rows.get(timeout=3)
        assert row["hand"] == 7
        assert engine.starts[0]["seed_payload"][0]["vpip_positive"] == 3
        assert engine.states[0].players[0].stack == 99
        assert [kind for kind, _ in engine.histories[0]] == ["hole"]
    finally:
        release.set()
        observer.close()


def test_queue_full_and_worker_errors_are_counted_without_blocking():
    entered, release = threading.Event(), threading.Event()
    rows = queue.Queue()

    class FailedEngine(FakeEngine):
        def decide(self, *args, **kwargs):
            entered.set()
            assert release.wait(3)
            raise RuntimeError("test worker timeout")

    observer = G5ShadowObserver(G5EngineOptions("unused"), rows.put,
                                engine_factory=FailedEngine, queue_size=1)
    try:
        start(observer)
        submit(observer)
        assert entered.wait(3)
        confirm(observer)
        submit(observer)
        confirm(observer)
        overflow_id = submit(observer)
        before = [rows.get(timeout=3) for _ in range(3)]
        assert before[-1]["decision_id"] == overflow_id
        assert before[-1]["reason"] == "queue_full"
        release.set()
        assert rows.get(timeout=3)["status"] == "error"
        assert rows.get(timeout=3)["status"] == "error"
    finally:
        release.set()
        observer.close()


def test_unconfirmed_hero_action_invalidates_following_snapshot():
    rows = []
    observer = G5ShadowObserver(G5EngineOptions("unused"), rows.append, engine_factory=FakeEngine)
    try:
        start(observer)
        submit(observer)
        second = submit(observer)
        row = next(r for r in rows if r["decision_id"] == second)
        assert row["reason"] == "missing_hero_action_confirmation"
    finally:
        observer.close()


@pytest.mark.parametrize("outcome", ["ok", "error", "skipped"])
def test_local_shadow_decision_can_be_written_as_json(tmp_path, outcome):
    rows = queue.Queue()
    path = tmp_path / "shadow.jsonl"
    writer = _JsonlWriter(str(path))

    def emit(row):
        writer.write(row)
        rows.put(row)

    class ResultEngine(FakeEngine):
        def decide(self, *args, **kwargs):
            if outcome == "error":
                raise RuntimeError("test worker error")
            return super().decide(*args, **kwargs)

    observer = G5ShadowObserver(G5EngineOptions("unused"), emit, engine_factory=ResultEngine)
    shadow = {"status": "ok", "decision": BotDecision("raise", 9),
              "elapsed_ms": 1.5, "diagnostics": {"equity": 0.6}}
    try:
        start(observer)
        if outcome == "skipped":
            observer.invalidate("test invalidation")
        observer.submit(state(), my_current_bet=1, decision=BotDecision("call"),
                        source="flop_book", local_shadow=shadow)
        assert rows.get(timeout=3)["status"] == outcome
    finally:
        observer.close()
        writer.close()

    row = json.loads(path.read_text().splitlines()[0])
    assert row["local_shadow"]["decision"] == {"action": "raise", "amount": 9}
    assert row["local_shadow"]["diagnostics"] == {"equity": 0.6}
    assert row["main_decision"]["action"] == "call"
    assert isinstance(shadow["decision"], BotDecision)
    assert observer._queue.unfinished_tasks == 0


def test_close_serializes_queued_local_shadow_snapshot(tmp_path):
    entered, release = threading.Event(), threading.Event()
    path = tmp_path / "shadow.jsonl"
    writer = _JsonlWriter(str(path))

    class BlockedEngine(FakeEngine):
        def decide(self, *args, **kwargs):
            entered.set()
            assert release.wait(3)
            return super().decide(*args, **kwargs)

        def shutdown(self):
            release.set()
            super().shutdown()

    observer = G5ShadowObserver(G5EngineOptions("unused"), writer.write, engine_factory=BlockedEngine)
    shadow = {"status": "ok", "decision": BotDecision("raise", 9),
              "diagnostics": {"equity": 0.6}}
    try:
        start(observer)
        submit(observer)
        assert entered.wait(3)
        confirm(observer)
        queued_id = observer.submit(state(), my_current_bet=1, decision=BotDecision("call"),
                                    source="flop_book", local_shadow=shadow)
        shadow["decision"].amount = 99
        shadow["diagnostics"]["equity"] = 0.9
        observer.close()
    finally:
        release.set()
        observer.close()
        writer.close()

    rows = [json.loads(line) for line in path.read_text().splitlines()]
    queued = next(row for row in rows if row["decision_id"] == queued_id)
    assert queued["status"] == "skipped" and queued["reason"] == "closed"
    assert queued["local_shadow"]["decision"] == {"action": "raise", "amount": 9}
    assert queued["local_shadow"]["diagnostics"] == {"equity": 0.6}
    assert not observer._thread.is_alive()
    assert observer._queue.unfinished_tasks == 0


@pytest.mark.parametrize("source", ["pokerfate", "flop_book", "realtime_cfr"])
def test_api_schedules_shadow_for_each_main_source(monkeypatch, tmp_path, source):
    path = tmp_path / "pokerfate.jsonl"
    api = PokerFateAPI(my_player_id=0, decision_engine="cfr", g5_observer_enabled=True,
                      g5_shadow_server_actions=True, log_file=str(path), enable_showdown_calibration=False)
    jobs = []
    monkeypatch.setattr(api._g5_observer, "submit", lambda gs, **kw: jobs.append(deepcopy((gs, kw))) or "node-1")
    monkeypatch.setattr(api, "_local_shadow_decide", lambda *a, **kw: {"status": "ok", "action": "check"})
    monkeypatch.setattr(api._bot, "decide", lambda *a, **kw: Action(ActionType.CHECK))
    monkeypatch.setattr(api._flop_book_engine, "decide", lambda ctx: Action(ActionType.CHECK))
    monkeypatch.setattr(api._realtime_cfr_engine, "decide", lambda ctx: Action(ActionType.CHECK))
    api.new_hand([PlayerInfo(0, "hero", 200, "BTN"), PlayerInfo(1, "villain", 200, "BB")], 0)
    api.deal_hole_cards(["As", "Kd"])
    street = {"pokerfate": "preflop", "flop_book": "flop", "realtime_cfr": "turn"}[source]
    if street != "preflop":
        api.deal_board(["2c", "3h", "4s"], "flop", pot=20)
    if street == "turn":
        api.deal_board(["9d"], "turn", pot=20)
    result = api.request_action(street, pot=20, current_bet=0, to_call=0, my_stack=200)
    assert result.action == "check"
    assert jobs[0][1]["source"] == source
    assert jobs[0][0].players[0].stack == 200
    assert not any(kind == "action" for kind, _ in api._g5_observer._events)
    api.record_g5_actual_action(player_id=0, action="check", amount_added=0, total_bet_after=0, street=street)
    assert api._g5_observer._events[-1][1]["action"] == "check"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert next(r for r in rows if r["event"] == "decision")["decision_id"] == "node-1"
    resolved = next(r for r in rows if r["event"] == "session_config")["resolved"]
    assert resolved["PF_G5_SHADOW_ENABLED"] is True
    assert resolved["G5_SHADOW_ACTION_HISTORY"] == "server_confirmed"
    api.close_g5_shadow()
    api._log.close()


def test_bridge_observes_confirmed_hero_call_instead_of_intended_raise():
    from pf_intercept.bot.bridge import BotBridge
    rows = []
    bridge = BotBridge(max_auto_rebuy=0)
    bridge._my_seat = 0
    bridge._stage = 1
    bridge._street_bets = {0: 8, 1: 10}
    bridge._api = SimpleNamespace(record_g5_actual_action=lambda **kw: rows.append(kw),
                                  disable_external_decision_current_hand=lambda reason: None)
    bridge._on_action_brc({"seatid": 0, "action_type": 17, "chips": 1, "hand_chips": 0})
    assert rows[0]["action"] == "call"
    assert rows[0]["amount_added"] == 1
    assert rows[0]["total_bet_after"] == 9


def test_fresh_replay_recreates_game_and_never_loads_mutable_model(monkeypatch):
    calls = []
    engine = G5JsonDecisionEngine(G5EngineOptions("unused", model_file="must-not-read.json"))
    monkeypatch.setattr(engine, "_rpc", lambda method, params: calls.append((method, params)) or {})
    monkeypatch.setattr(engine, "_seed_current_players", lambda: pytest.fail("read future model"))
    for _ in range(2):
        engine.start_hand(players=state().players, dealer_id=0, hand_number=1, hero_player_id=0,
                          big_blind=2, small_blind=1, fresh_game=True, seed_payload=[])
    assert [m for m, _ in calls] == ["create_game", "start_hand", "create_game", "start_hand"]


def test_worker_rejects_mismatched_state_before_calculating():
    worker = G5Worker()
    worker.api = SimpleNamespace(
        getPlayerToActInd=lambda _: 0, getAmountToCall=lambda _: 5,
        getStakesSize=lambda *args: 1, getPotSize=lambda _: 20,
        calculateHeroAction=lambda _: pytest.fail("mismatched state evaluated"),
    )
    with pytest.raises(ValueError, match="replay state mismatch"):
        worker.decide({"hero_index": 0, "current_bet": 2, "my_current_bet_this_street": 1,
                       "hero_stack": 99, "pot": 20, "validate_replay_state": True})


def test_shadow_default_on_outside_tests_and_explicit_off(monkeypatch):
    # Explicit persistence paths keep this default-resolution test isolated.
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    monkeypatch.delenv("PF_G5_SHADOW_ENABLED")
    for override, expected in [(None, True), (False, False)]:
        api = PokerFateAPI(decision_engine="local", g5_observer_enabled=override,
                          autosave_path=None, log_file=None, g5_model_path=None,
                          enable_showdown_calibration=False)
        assert api._g5_observer_enabled is expected
        api.close_g5_shadow()


def test_snapshot_failure_never_changes_main_action(monkeypatch):
    api = PokerFateAPI(decision_engine="local", g5_observer_enabled=True,
                      enable_showdown_calibration=False)
    api.new_hand([PlayerInfo(0, "hero", 200), PlayerInfo(1, "villain", 200)], 0)
    api.deal_hole_cards(["As", "Kd"])
    def fail(*args, **kwargs):
        raise RuntimeError("snapshot failure")
    rows = []
    monkeypatch.setattr(api._g5_observer, "submit", fail)
    monkeypatch.setattr(api._log, "raw", rows.append)
    monkeypatch.setattr(api._bot, "decide", lambda *a, **kw: Action(ActionType.CALL))
    decision = api.request_action("preflop", pot=3, current_bet=2, to_call=1,
                                  my_stack=199, my_current_bet_this_street=1)
    assert decision.action == "call"
    assert api._get_my_player().stack == 198
    assert any(r.get("reason") == "snapshot_failed: snapshot failure" for r in rows)
    api.close_g5_shadow()


def test_preflop_reconnect_disables_shadow_until_next_hand():
    from pf_intercept.bot.bridge import BotBridge
    reasons = []
    bridge = BotBridge(max_auto_rebuy=0)
    bridge._api = SimpleNamespace(invalidate_g5_shadow=reasons.append)
    bridge._sync_hand_snapshot_from_enter_room({"is_playing": True, "stage": 1})
    assert reasons == ["reconnected_without_full_history"]


def test_shutdown_prevents_lazy_worker_respawn():
    engine = G5JsonDecisionEngine(G5EngineOptions("must-not-execute"))
    engine.shutdown()
    from pokerfate.decision.g5_engine import DecisionEngineError
    with pytest.raises(DecisionEngineError, match="observer closed"):
        engine.preflight()
