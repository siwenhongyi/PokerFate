from __future__ import annotations

import re
from datetime import datetime

from pokerfate.logger import PokerLogger, archive_runtime_logs_on_startup


def test_archive_runtime_logs_on_startup_uses_daily_archive_folder(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    for name in ("pokerfate_console.log", "pokerfate.log", "g5.log"):
        (logs_dir / name).write_text(f"{name} old\n", encoding="utf-8")

    archive_runtime_logs_on_startup(logs_dir)

    date_key = datetime.now().strftime("%Y-%m-%d")
    for name in ("pokerfate_console", "pokerfate", "g5"):
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
