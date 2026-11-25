from __future__ import annotations

import re
from datetime import datetime

from pokerfate.logger import PokerLogger, archive_runtime_logs_on_startup


def test_archive_runtime_logs_on_startup_uses_daily_archive_folder(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    for name in ("pokerfate_console.log", "pokerfate.log"):
        (logs_dir / name).write_text(f"{name} old\n", encoding="utf-8")

    archive_runtime_logs_on_startup(logs_dir)

    date_key = datetime.now().strftime("%Y-%m-%d")
    for name in ("pokerfate_console", "pokerfate"):
        assert (logs_dir / f"{name}.log").read_text(encoding="utf-8") == ""
        archived = logs_dir / "archive" / f"{date_key}.{name}.bak.log"
        assert archived.read_text(encoding="utf-8") == f"{name}.log old\n"


def test_console_mirror_timestamp_includes_date(tmp_path):
    log_file = tmp_path / "pokerfate.log"
    logger = PokerLogger(log_file=str(log_file), console=False)
    try:
        logger.note("hello")
    finally:
        logger.close()

    line = (tmp_path / "pokerfate_console.log").read_text(encoding="utf-8").strip()
    assert re.match(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] hello$", line)


def test_decision_listener_receives_the_record_and_cannot_break_a_decision():
    logger = PokerLogger(log_file=None, console=False)
    seen = []
    logger.decision_listener = seen.append
    logger.decision(action="call", amount=0, street="turn", equity=0.412, pot=900, to_call=300, reasoning="because",
                    spr=2.5, equity_mode="range_v2", elapsed_ms=48.2, extra={"decision_source": "realtime_cfr"})
    assert {k: seen[0][k] for k in ("event", "street", "action", "equity", "pot", "to_call", "spr", "equity_mode",
                                    "elapsed_ms", "decision_source", "reasoning")} == {
        "event": "decision", "street": "turn", "action": "call", "equity": 0.412, "pot": 900, "to_call": 300, "spr": 2.5,
        "equity_mode": "range_v2", "elapsed_ms": 48.2, "decision_source": "realtime_cfr", "reasoning": "because"}

    def broken(_record):
        raise RuntimeError("page gone")
    logger.decision_listener = broken
    logger.decision(action="fold", amount=0, street="river", equity=0.1, pot=900, to_call=300)
