from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_COLOR_RECORD_FILE = DATA_DIR / "entertainment_color_records.json"


class JsonRecordStore:
    def __init__(self, path: Path = DEFAULT_COLOR_RECORD_FILE) -> None:
        self.path = path
        self._lock = threading.Lock()

    def load(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._load_unlocked()

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        records = self.load()
        return records[-limit:][::-1]

    def summary(self) -> dict[str, int]:
        records = self.load()
        total_bet = 0
        total_return = 0
        net_profit = 0
        played = 0
        for record in records:
            summary = record.get("summary") or {}
            total_bet += int(summary.get("total_bet") or 0)
            total_return += int(summary.get("total_return") or 0)
            net_profit += int(summary.get("net_profit") or 0)
            played += int(summary.get("played") or 0)
        return {
            "records": len(records),
            "played": played,
            "total_bet": total_bet,
            "total_return": total_return,
            "net_profit": net_profit,
        }

    def append(self, record: dict[str, Any]) -> None:
        with self._lock:
            records = self._load_unlocked()
            records.append(record)
            self._write_unlocked(records)

    def _load_unlocked(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except Exception:
            return []

        if isinstance(payload, dict):
            runs = payload.get("runs", [])
        else:
            runs = payload
        if not isinstance(runs, list):
            return []
        return [item for item in runs if isinstance(item, dict)]

    def _write_unlocked(self, records: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"runs": records}
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)
