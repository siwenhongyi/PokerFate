"""足球竞猜, bet on for the tasks that count bets: scripted server replies, no real requests."""
from __future__ import annotations

import asyncio
import re

import pytest

from pf_intercept.headless.lobby.doers import football as fb
from pf_intercept.headless.lobby.core import base as lb
from pf_intercept.headless.lobby.routine import fund as fd
from pf_intercept.headless.lobby.core import needs as nd
from pf_intercept.headless.lobby.core import service as sv
from pf_intercept.headless.lobby.routine import tasks as tk
from tests.test_dispatch import TPL, ScriptedHTTP, journal, lua_table

NOW = 1795400000
STATUS, LIST, HISTORY, BET = "/activity/betStatus", "/activity/betList", "/activity/betHistory", "/activity/bet"


class Wallet:
    def __init__(self, chips):
        self.chips = chips

    def bankroll_dashboard(self):
        return {} if self.chips is None else {"wallet_chips": self.chips}


def setup(tmp_path, replies, *, wallet=5_000_000):
    http = ScriptedHTTP(replies)
    ready = asyncio.Event()
    ready.set()

    async def credit(chips, uncertain):
        raise AssertionError("a bet is no reward")

    svc = sv.RewardService(uid=42, authorization="session-secret", http_base="https://game.example",
                           chnl=3, version="1.7.0", on_credit=credit, ready=ready, post=http,
                           journal_path=tmp_path / "rewards.jsonl")
    clock = [NOW]
    svc.now = lambda: clock[0]
    worker = fb.Football(svc, Wallet(wallet))
    svc.attach(worker)
    return worker, svc, http, clock


def pass_lists(done, steps=(1, 2, 3, 5, 7)):
    """The battle pass's weekly football chain as its list shows it: the steps done, the current one."""
    rows = [{"id": 900 + i, "task_id": 1010901 + i, "task_type": 322, "value": [step],
             "status": 3 if step <= done else 1, "current_value": min(done, step)} for i, step in enumerate(steps)]
    current = next((row for row in rows if row["status"] == 1), None)
    return [row for row in rows if row["status"] == 3] + ([current] if current else [])


def match(bet_id, kickoff, pools=(500, 300, 200), status=0, lock=0):
    return {"bet_id": bet_id, "status": status, "lock": lock, "game_start_time": kickoff, "bet_type": 1,
            "bet_area": [{"type": kind, "name": name, "amount": amount}
                         for kind, name, amount in zip((1, 2, 3), ("Home", "Away", "Draw"), pools)]}


def listing(*matches):
    return (LIST, {"code": 0, "list": list(matches)})


def history(*bets):
    return (HISTORY, {"code": 0, "list": [
        {"bet_id": bet_id, "status": status, "is_settled": int(status == 1), "game_start_time": NOW - 9000,
         "bet_area": [{"type": 1, "amount": stake, "reward": reward}, {"type": 2, "amount": 0, "reward": 0}]}
        for bet_id, status, stake, reward in bets]})


OPEN = (STATUS, {"code": 0, "open": 0, "live": 0, "bet_ids": []})


def test_the_stakes_and_the_rules_are_the_clients():
    tiers = tuple((int(r["balance"]), int(r["chips1"])) for r in lua_table("predictor_bet"))
    assert tiers == fb.tiers()
    for r in lua_table("predictor_bet"):         # the smallest chip says which amounts can be made
        assert all(int(r[f"chips{i}"]) % int(r["chips1"]) == 0 for i in range(1, 5))
    weekly = [r for r in lua_table("battle_pass_tasks_week") if r["task_type"] == "322"]
    assert weekly and all(re.fullmatch(r"\{\d+\}", r["value"]) for r in weekly)
    assert nd.Needs.task_key(322) == fb.KEY
    model = (TPL.parent / "app" / "model" / "activity" / "SoccerGuessingModel.lua").read_text(encoding="utf-8")
    assert 'Net:post("activity/bet", params,' in model and "l.bet_area = k" in model and "l.amount = v" in model
    main = (TPL.parent / "app" / "views" / "SoccerGuessing" / "SoccerMain.lua").read_text(encoding="utf-8")
    assert "Normal = 0," in main and "Team1 = 1," in main and "Draw = 3," in main
    assert "self._betStatus = data.open" in model
    lobby = (TPL.parent / "app" / "views" / "Lobby" / "LobbyLayer.lua").read_text(encoding="utf-8")
    assert "if SoccerGuessingModel:getBetStatus() == 0 or PlayerModel:isEventWhite() then\n        self.SoccerButton:SetActive(true)" in lobby


@pytest.mark.parametrize("value, shown", [(0, True), (0.0, True), (1, False), (2, False), (False, False),
                                          (True, False), ("0", False), (None, False)])
def test_is_open(value, shown):
    assert fb.is_open({"open": value}) is shown


@pytest.mark.parametrize("wallet, chip", [(0, 1000), (9_999_999, 1000), (10_000_000, 10_000),
                                          (115_700_159, 100_000), (10 ** 10, 1_000_000)])
def test_smallest_chip(wallet, chip):
    assert fb.smallest_chip(wallet) == chip


@pytest.mark.parametrize("stake, wallet, made", [
    (100_000, 5_000_000, True), (100_000, 115_700_159, True), (300_000, 115_700_159, True),
    (1000, 115_700_159, False), (10_000, 115_700_159, False), (150_000, 115_700_159, False),
    (100_000, 99_999, False), (100_000, 2_000_000_000, False)])
def test_can_make(stake, wallet, made):
    assert fb.can_make(stake, wallet) is made


def test_the_board_holds_counts_that_are_not_a_game():
    rows = pass_lists(2) + [{"task_type": 301, "status": 1, "value": [4], "current_value": 1},
                            {"task_type": 103, "status": 1, "value": [30030101, 300000], "current_value": 5}]
    assert nd.Needs.gaps(rows) == {fb.KEY: 1, "task_type:301": 3}
    # Chips bet are not on the board at all: no gap, and no count.
    assert nd.Needs.counted(rows) == {fb.KEY: 2, "task_type:301": 1}


def test_a_bet_on_the_soonest_match_not_bet_on_on_the_favourite_at_the_smallest_stake(tmp_path):
    async def run():
        worker, svc, http, _ = setup(tmp_path, [
            OPEN,
            listing(match("m-late", NOW + 90000, (100, 900, 0)),
                    match("m-soon", NOW + 3600, (200, 300, 500)),            # the draw has most of the pool
                    match("m-mine", NOW + 1800),                              # bet on already
                    match("m-kick", NOW + 60),                                # about to start
                    match("m-lock", NOW + 900, lock=1),
                    match("m-done", NOW + 900, status=1)),
            history(("m-mine", 0, 1000, 0), ("m-old", 1, 1000, 1500), ("m-void", 2, 1000, 0)),
            (BET, {"code": 0}),
        ])
        svc.needs.want("battlepass", pass_lists(0))
        svc.due["battlepass"] = NOW + 300
        await worker.check()
        assert not http.replies
        assert http.calls[-1] == (BET, {"bet_id": "m-soon", "areas": [{"bet_area": 3, "amount": fb.STAKE}]})
        attempt, = journal(tmp_path, "football_attempt")
        assert (attempt["bet_id"], attempt["area"], attempt["stake"], attempt["pools"]) == (
            "m-soon", 3, fb.STAKE, {"1": 200, "2": 300, "3": 500})
        assert attempt["payload"] == http.calls[-1][1]
        listed, = journal(tmp_path, "football_matches")
        assert listed["rows"] == [
            match("m-late", NOW + 90000, (100, 900, 0)), match("m-soon", NOW + 3600, (200, 300, 500)),
            match("m-mine", NOW + 1800), match("m-kick", NOW + 60), match("m-lock", NOW + 900, lock=1),
            match("m-done", NOW + 900, status=1)]
        assert journal(tmp_path, "football_bet")[0]["stake"] == fb.STAKE == 100_000
        state, = journal(tmp_path, "football_state")
        assert (state["open"], state["matches"], state["to_bet"]) == (True, 6, 2)
        past, = journal(tmp_path, "football_history")
        assert (past["bets"], past["settled"], past["cancelled"], past["staked"], past["paid"]) == (3, 1, 1, 3000, 1500)
        # The pass is asked to read its list again; nothing else happens until it has.
        assert svc.due["battlepass"] == NOW + fb.COMEBACK_SEC
        await worker.check()
        assert not http.replies
    asyncio.run(run())


def test_one_bet_at_a_time_each_confirmed_by_the_lists_before_the_next(tmp_path):
    async def run():
        worker, svc, http, _ = setup(tmp_path, [
            OPEN, listing(match("a", NOW + 3600), match("b", NOW + 7200)), history(), (BET, {"code": 0}),
        ])
        svc.needs.want("battlepass", pass_lists(1))           # step 2: lacks 1
        await worker.check()
        # The pass reads its list: the step was done and collected; the next step lacks 1 again.
        svc.needs.want("battlepass", pass_lists(2))
        http.replies.extend([OPEN, listing(match("a", NOW + 3600), match("b", NOW + 7200)),
                             history(("a", 0, 1000, 0)), (BET, {"code": 0})])
        await worker.check()
        assert not http.replies and [p["bet_id"] for e, p in http.calls if e == BET] == ["a", "b"]
        assert not journal(tmp_path, "football_blocked")
    asyncio.run(run())


def test_a_bet_the_lists_do_not_count_is_not_repeated(tmp_path):
    async def run():
        worker, svc, http, clock = setup(tmp_path, [
            OPEN, listing(match("a", NOW + 3600), match("b", NOW + 7200)), history(), (BET, {"code": 0}),
        ])
        svc.needs.want("battlepass", pass_lists(1))
        await worker.check()
        svc.needs.want("battlepass", pass_lists(1))           # read again: no further than before
        await worker.check()
        blocked, = journal(tmp_path, "football_blocked")
        assert blocked["action"] == "bet" and blocked["code"].startswith("not counted")
        await worker.check()
        assert not http.replies and len([1 for e, _ in http.calls if e == BET]) == 1
        clock[0] += lb.BLOCK_SEC + 1
        svc.needs.want("battlepass", pass_lists(1))
        http.replies.extend([OPEN, listing(match("b", NOW + 99999)), history(("a", 0, 1000, 0)), (BET, {"code": 0})])
        await worker.check()
        assert not http.replies
    asyncio.run(run())


def test_nothing_is_asked_when_no_list_lacks_a_bet(tmp_path):
    async def run():
        worker, svc, http, _ = setup(tmp_path, [])
        await worker.check()                                  # nobody lacks a bet
        svc.needs.want("battlepass", pass_lists(7))           # all done
        await worker.check()
        svc.needs.want("battlepass", pass_lists(3))
        worker.session.chips = None                           # lacking, but no wallet reading yet
        await worker.check()
        worker.session.chips = 99_999                         # lacking, and the wallet is below the stake
        await worker.check()
        await worker.check()
        assert http.calls == []
        skipped, = journal(tmp_path, "football_skipped")      # said once
        assert skipped["stake"] == fb.STAKE
    asyncio.run(run())


@pytest.mark.parametrize("wallet, sent", [(5_000_000, True), (115_700_159, True), (2_000_000_000, False)])
def test_the_stake_is_sent_only_when_the_client_can_make_it_from_the_wallets_chips(tmp_path, wallet, sent):
    async def run():
        replies = [OPEN, listing(match("a", NOW + 3600)), history(), (BET, {"code": 0})]
        worker, svc, http, _ = setup(tmp_path, replies if sent else [], wallet=wallet)
        svc.needs.want("battlepass", pass_lists(0))
        await worker.check()
        assert not http.replies
        if sent:
            assert http.calls[-1] == (BET, {"bet_id": "a", "areas": [{"bet_area": 1, "amount": fb.STAKE}]})
            attempt, = journal(tmp_path, "football_attempt")
            assert (attempt["stake"], attempt["client_chip"]) == (fb.STAKE, fb.smallest_chip(wallet))
        else:
            assert http.calls == []
            skipped, = journal(tmp_path, "football_skipped")
            assert (skipped["stake"], skipped["client_chip"]) == (fb.STAKE, 1_000_000)
    asyncio.run(run())


def test_a_closed_predictor_or_no_open_match_is_looked_at_again_later(tmp_path):
    async def run():
        worker, svc, http, clock = setup(tmp_path, [(STATUS, {"code": 0, "open": 1})])
        svc.needs.want("battlepass", pass_lists(0))
        await worker.check()
        await worker.check()
        state = journal(tmp_path, "football_state")[0]
        assert not http.replies and (state["open"], state["raw_open"]) == (False, 1)
        clock[0] += fb.QUIET_SEC + 1
        svc.needs.want("battlepass", pass_lists(0))
        http.replies.extend([OPEN, listing(match("x", NOW + 100, lock=1)), history()])
        await worker.check()
        await worker.check()
        assert not http.replies and journal(tmp_path, "football_state")[-1]["to_bet"] == 0
    asyncio.run(run())


def test_a_refused_bet_waits_and_an_unanswered_one_is_never_placed_twice(tmp_path):
    async def run():
        worker, svc, http, clock = setup(tmp_path, [
            OPEN, listing(match("a", NOW + 3600)), history(), (BET, {"code": -802})])
        svc.needs.want("battlepass", pass_lists(0))
        await worker.check()
        await worker.check()
        assert not http.replies
        refused, = journal(tmp_path, "football_blocked")
        assert (refused["code"], refused["reply"]) == (-802, {"code": -802})
        clock[0] += lb.BLOCK_SEC + 1
        svc.needs.want("battlepass", pass_lists(0))
        http.replies.extend([OPEN, listing(match("a", NOW + 99999)), history(), (BET, None)])
        with pytest.raises(lb.RewardAPIError):
            await worker.check()
        assert journal(tmp_path, "football_uncertain")[0]["bet_id"] == "a"
        # The next pass: the history shows the bet went through, and the match is not bet on again.
        http.replies.extend([OPEN, listing(match("a", NOW + 99999)), history(("a", 0, 1000, 0))])
        await worker.check()
        assert not http.replies
    asyncio.run(run())
