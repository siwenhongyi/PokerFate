"""Observational G5 evaluation: immutable real-history snapshots, no execution.

The main thread owns the journal. A bounded background queue replays each
snapshot into a fresh game in a persistent worker. G5 recommendations are never
applied, and neither cards nor model updates after the request can leak in.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
import queue
import threading
import time
from uuid import uuid4

from pokerfate.decision.g5_engine import G5JsonDecisionEngine


class G5ShadowObserver:
    def __init__(self, options, emit, *, engine_factory=G5JsonDecisionEngine, queue_size=32):
        self.options = options
        self._emit = emit
        self._factory = engine_factory
        self._queue = queue.Queue(maxsize=queue_size)
        self._stop = threading.Event()
        self._thread = None
        self._engine = None
        self._preflight_done = False
        self._lifecycle_lock = threading.Lock()
        self._session_id = uuid4().hex
        self._index = 0
        self._start = None
        self._events = []
        self._reason = "hand_not_started"
        self._pending = None
        self._seed_hash = ""

    def start_hand(self, **kwargs):
        self._start = deepcopy(kwargs)
        self._events = []
        self._reason = ""
        self._pending = None
        self._seed_hash = hashlib.sha256(json.dumps(kwargs.get("seed_payload", []), sort_keys=True).encode()).hexdigest()

    def invalidate(self, reason):
        self._reason = reason

    def hole_cards(self, cards):
        self._events.append(("hole_cards", {"cards": list(cards)}))

    def board(self, cards, street):
        self._events.append(("board", {"cards": list(cards), "street": street}))

    def action(self, **kwargs):
        self._events.append(("action", dict(kwargs)))
        if self._start and kwargs["player_id"] == self._start["hero_player_id"]:
            if self._pending:
                self._emit({
                    "event": "g5_shadow_execution", **self._pending,
                    "executed_action": dict(kwargs),
                })
                self._pending = None

    def submit(self, gs, *, my_current_bet, decision, source, local_shadow=None):
        shadow_snapshot = deepcopy(local_shadow)
        if isinstance(shadow_snapshot, dict):
            shadow_decision = shadow_snapshot.get("decision")
            if is_dataclass(shadow_decision):
                # BotDecision is a runtime object; every result/skip/close path
                # must receive a JSON-ready snapshot before it enters the queue.
                shadow_snapshot["decision"] = asdict(shadow_decision)
        self._index += 1
        decision_id = f"{self._session_id}:{self._index}"
        hand = self._start["hand_number"] if self._start else 0
        meta = {
            "event": "g5_shadow_decision", "mode": "real_history_v1",
            "decision_id": decision_id, "hand": hand, "street": str(gs.street).lower(),
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "main_decision": {"action": decision.action, "amount": decision.amount, "source": source},
            "local_shadow": shadow_snapshot,
            "context": {
                "pot": gs.pot, "current_bet": gs.current_bet,
                "my_current_bet": my_current_bet,
                "board": [str(c) for c in gs.board],
                "players": [{"player_id": p.player_id, "stack": p.stack,
                             "current_bet": p.current_bet, "folded": p.is_folded,
                             "hole_cards": [str(c) for c in p.hole_cards]}
                            for p in gs.players],
            },
            "history_length": len(self._events),
            "history_hash": hashlib.sha256(json.dumps(self._events, sort_keys=True).encode()).hexdigest(),
            "model_seed_hash": self._seed_hash,
        }
        if self._pending:
            self.invalidate("missing_hero_action_confirmation")
        self._pending = {"decision_id": decision_id, "hand": hand, "street": meta["street"]}
        if self._reason or self._stop.is_set():
            self._emit({**meta, "status": "skipped", "reason": self._reason or "closed"})
            return decision_id
        job = (deepcopy(self._start), deepcopy(self._events), deepcopy(gs), my_current_bet, meta)
        try:
            self._queue.put_nowait(job)
        except queue.Full:
            self._emit({**meta, "status": "skipped", "reason": "queue_full"})
            return decision_id
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="g5-real-history-shadow", daemon=True)
            self._thread.start()
        return decision_id

    def _run(self):
        try:
            while not self._stop.is_set():
                try:
                    job = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                start, events, gs, my_bet, meta = job
                t0 = time.perf_counter()
                try:
                    with self._lifecycle_lock:
                        if self._stop.is_set():
                            raise RuntimeError("shadow_closed")
                        if self._engine is None:
                            self._engine = self._factory(self.options)
                            # First runtime load can take longer than one decision RPC.
                    if not self._preflight_done:
                        self._engine.preflight()
                        self._preflight_done = True
                    self._engine.start_hand(**start, fresh_game=True)
                    for kind, payload in events:
                        if self._stop.is_set():
                            raise RuntimeError("shadow_closed")
                        if kind == "hole_cards":
                            self._engine.deal_hole_cards(**payload)
                        elif kind == "board":
                            self._engine.deal_board(**payload)
                        else:
                            self._engine.notify_action(**payload)
                    action = self._engine.decide(gs, hero_player_id=start["hero_player_id"],
                                                 my_current_bet_this_street=my_bet)
                    result = {"status": "ok", "action": str(action.action_type),
                              "amount": action.amount, "result": self._engine.last_result}
                except Exception as exc:
                    result = {"status": "error", "reason": str(exc)}
                self._emit({**meta, **result, "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1)})
                self._queue.task_done()
        finally:
            if self._engine is not None:
                self._engine.shutdown()

    def close(self):
        self._stop.set()
        with self._lifecycle_lock:
            if self._engine is not None:
                self._engine.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        while True:
            try:
                *_, meta = self._queue.get_nowait()
            except queue.Empty:
                break
            self._emit({**meta, "status": "skipped", "reason": "closed"})
            self._queue.task_done()
