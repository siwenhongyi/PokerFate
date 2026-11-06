#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_DIR = ROOT / "pokerfate" / "logs"
DEFAULT_OUT_DIR = DEFAULT_LOG_DIR / "extracted"

BB_PATH_RE = re.compile(r"(?:opponents_bb|g5_stats_bb)_(\d+k)\.json", re.IGNORECASE)
CONSOLE_HAND_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s+第\s+(\d+)\s+手")
UTC = timezone.utc
CONSOLE_TZ = timezone(timedelta(hours=8))


@dataclass
class SourceStats:
    structured: str
    console: str | None = None
    structured_lines: int = 0
    console_lines: int = 0
    console_blocks: int = 0
    json_errors: int = 0
    hands: set[int] = field(default_factory=set)
    hand_times: dict[int, list[datetime]] = field(default_factory=dict)

    def to_json(self) -> dict:
        ordered_hands = sorted(self.hands)
        return {
            "structured": self.structured,
            "console": self.console,
            "structured_lines": self.structured_lines,
            "console_lines": self.console_lines,
            "console_blocks": self.console_blocks,
            "json_errors": self.json_errors,
            "hand_count": len(ordered_hands),
            "hand_min": ordered_hands[0] if ordered_hands else None,
            "hand_max": ordered_hands[-1] if ordered_hands else None,
            "hands": ordered_hands,
        }


def iter_structured_files(log_dir: Path) -> Iterable[Path]:
    archive = log_dir / "archive"
    if archive.exists():
        yield from sorted(archive.glob("*.pokerfate.bak.log"))
    current = log_dir / "pokerfate.log"
    if current.exists():
        yield current


def matching_console_path(structured_path: Path, log_dir: Path) -> Path:
    if structured_path.name == "pokerfate.log":
        return log_dir / "pokerfate_console.log"
    return structured_path.with_name(
        structured_path.name.replace(".pokerfate.bak.log", ".pokerfate_console.bak.log")
    )


def detect_bb_key(obj: dict) -> str | None:
    for key in ("path", "model_file"):
        value = obj.get(key)
        if isinstance(value, str):
            match = BB_PATH_RE.search(value)
            if match:
                return match.group(1).lower()
    return None


def parse_utc_to_console_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(CONSOLE_TZ).replace(tzinfo=None)


def parse_console_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def extract_structured(
    log_dir: Path,
    structured_out: Path,
    target_bb: str,
) -> list[SourceStats]:
    stats_by_source: list[SourceStats] = []
    target_bb = target_bb.lower()

    structured_out.write_text("", encoding="utf-8")
    for src in iter_structured_files(log_dir):
        stats = SourceStats(structured=str(src))
        stats.console = str(matching_console_path(src, log_dir))
        stats_by_source.append(stats)

        current_bb: str | None = None
        prefix_buffer: list[str] = []
        temp_out = structured_out.with_name(f".{structured_out.name}.{src.stem}.tmp")

        with temp_out.open("w", encoding="utf-8") as out:
            with src.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        stats.json_errors += 1
                        if current_bb == target_bb:
                            out.write(line)
                            stats.structured_lines += 1
                        elif current_bb is None:
                            prefix_buffer.append(line)
                        continue

                    detected_bb = detect_bb_key(obj)
                    if detected_bb:
                        current_bb = detected_bb

                    if current_bb is None:
                        prefix_buffer.append(line)
                        continue

                    if current_bb == target_bb:
                        if prefix_buffer:
                            for buffered_line in prefix_buffer:
                                out.write(buffered_line)
                                stats.structured_lines += 1
                            prefix_buffer.clear()
                        out.write(line)
                        stats.structured_lines += 1

                        hand = obj.get("hand")
                        if isinstance(hand, int):
                            stats.hands.add(hand)
                            local_ts = parse_utc_to_console_time(obj.get("ts"))
                            if local_ts is not None:
                                stats.hand_times.setdefault(hand, []).append(local_ts)
                    else:
                        prefix_buffer.clear()

        if stats.hands:
            with structured_out.open("a", encoding="utf-8") as final_out:
                with temp_out.open("r", encoding="utf-8", errors="replace") as temp_in:
                    shutil.copyfileobj(temp_in, final_out)
        else:
            stats.structured_lines = 0
        temp_out.unlink(missing_ok=True)

    return stats_by_source


def should_write_console_block(hand: int | None, header_time: datetime | None, stats: SourceStats) -> bool:
    if hand is None or hand not in stats.hands:
        return False
    known_times = stats.hand_times.get(hand) or []
    if header_time is None or not known_times:
        return True
    return any(abs(header_time - known_time) <= timedelta(minutes=30) for known_time in known_times)


def extract_console(console_out: Path, stats_by_source: list[SourceStats]) -> None:
    with console_out.open("w", encoding="utf-8") as out:
        for stats in stats_by_source:
            if not stats.hands or not stats.console:
                continue
            console_path = Path(stats.console)
            if not console_path.exists():
                continue

            current_hand: int | None = None
            current_time: datetime | None = None
            block: list[str] = []

            def flush_block() -> None:
                nonlocal block
                if should_write_console_block(current_hand, current_time, stats):
                    for item in block:
                        out.write(item)
                    stats.console_lines += len(block)
                    stats.console_blocks += 1
                block = []

            with console_path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    match = CONSOLE_HAND_RE.match(line)
                    if match:
                        flush_block()
                        current_time = parse_console_time(match.group(1))
                        current_hand = int(match.group(2))
                    block.append(line)
                flush_block()


def write_manifest(
    manifest_out: Path,
    structured_out: Path,
    console_out: Path,
    target_bb: str,
    stats_by_source: list[SourceStats],
) -> None:
    used_sources = [stats for stats in stats_by_source if stats.structured_lines or stats.console_blocks]
    payload = {
        "generated_at": datetime.now(CONSOLE_TZ).isoformat(),
        "target_bb": target_bb,
        "structured_out": str(structured_out),
        "console_out": str(console_out),
        "source_count": len(used_sources),
        "totals": {
            "structured_lines": sum(stats.structured_lines for stats in used_sources),
            "console_lines": sum(stats.console_lines for stats in used_sources),
            "console_blocks": sum(stats.console_blocks for stats in used_sources),
            "hand_count": sum(len(stats.hands) for stats in used_sources),
            "json_errors": sum(stats.json_errors for stats in used_sources),
        },
        "sources": [stats.to_json() for stats in used_sources],
    }
    manifest_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract 50k PokerFate logs into standalone files.")
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--target-bb", default="50k")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    structured_out = args.out_dir / f"{args.target_bb}.pokerfate.log"
    console_out = args.out_dir / f"{args.target_bb}.pokerfate_console.log"
    manifest_out = args.out_dir / f"{args.target_bb}.manifest.json"

    stats_by_source = extract_structured(args.log_dir, structured_out, args.target_bb)
    extract_console(console_out, stats_by_source)
    write_manifest(manifest_out, structured_out, console_out, args.target_bb, stats_by_source)

    used_sources = [stats for stats in stats_by_source if stats.structured_lines or stats.console_blocks]
    print(f"target_bb={args.target_bb}")
    print(f"structured_out={structured_out}")
    print(f"console_out={console_out}")
    print(f"manifest_out={manifest_out}")
    print(f"sources={len(used_sources)}")
    print(f"hands={sum(len(stats.hands) for stats in used_sources)}")
    print(f"console_blocks={sum(stats.console_blocks for stats in used_sources)}")
    print(f"structured_lines={sum(stats.structured_lines for stats in used_sources)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
