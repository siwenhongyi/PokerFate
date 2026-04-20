"""Local hero-name configuration for replay scripts."""
from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HERO_NAME_FILE = REPO_ROOT / "data" / "hero_name.txt"


def load_hero_name(path: Path = HERO_NAME_FILE) -> str:
    try:
        name = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing hero name file: {path}") from exc

    if not name:
        raise RuntimeError(f"empty hero name file: {path}")
    return name
