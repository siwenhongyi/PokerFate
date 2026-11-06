from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class PendingHeartbeat:
    seq: int
    sent_at: float


@dataclass
class HeartbeatTrace:
    session_id: int
    req_count: int = 0
    rsp_count: int = 0
    _seq: int = 0
    last_req_at: float | None = None
    last_rsp_at: float | None = None
    last_rtt_ms: float | None = None
    max_rtt_ms: float | None = None
    pending_reqs: list[PendingHeartbeat] = field(default_factory=list)

    def note_req(self) -> tuple[int, int]:
        now = time.monotonic()
        self.req_count += 1
        self._seq += 1
        self.last_req_at = now
        self.pending_reqs.append(PendingHeartbeat(seq=self._seq, sent_at=now))
        return self._seq, len(self.pending_reqs)

    def note_rsp(self) -> tuple[float | None, int]:
        now = time.monotonic()
        self.rsp_count += 1
        self.last_rsp_at = now
        rtt_ms = None
        if self.pending_reqs:
            pending = self.pending_reqs.pop(0)
            rtt_ms = (now - pending.sent_at) * 1000.0
            self.last_rtt_ms = rtt_ms
            self.max_rtt_ms = (
                rtt_ms if self.max_rtt_ms is None else max(self.max_rtt_ms, rtt_ms)
            )
        return rtt_ms, len(self.pending_reqs)

    def summary(self) -> str:
        now = time.monotonic()

        def age(value: float | None) -> str:
            if value is None:
                return "-"
            return f"{now - value:.1f}s"

        def ms(value: float | None) -> str:
            if value is None:
                return "-"
            return f"{value:.0f}ms"

        return (
            f"hb_req={self.req_count} hb_rsp={self.rsp_count} "
            f"pending={len(self.pending_reqs)} "
            f"last_req_age={age(self.last_req_at)} last_rsp_age={age(self.last_rsp_at)} "
            f"last_rtt={ms(self.last_rtt_ms)} max_rtt={ms(self.max_rtt_ms)}"
        )
