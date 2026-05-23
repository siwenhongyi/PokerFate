"""Hero-name JSON configuration for replay scripts."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HERO_NAMES_FILE = REPO_ROOT / "data" / "hero_names.json"


@dataclass(frozen=True)
class HeroNames:
    current: str
    aliases: tuple[str, ...]

    @property
    def all_names(self) -> tuple[str, ...]:
        return _dedupe((self.current, *self.aliases))

    def matches(self, name: str) -> bool:
        target = str(name).strip()
        return bool(target) and target in set(self.all_names)


def _dedupe(names) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in names:
        name = str(raw).strip()
        if not name:
            continue
        if name not in seen:
            seen.add(name)
            result.append(name)
    return tuple(result)


def load_hero_names(path: Path = HERO_NAMES_FILE) -> HeroNames:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise RuntimeError(f"missing hero name file: {path}") from exc

    if not raw:
        raise RuntimeError(f"empty hero name file: {path}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid hero name json: {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"hero name config must be a json object: {path}")

    current_raw = data.get("current")
    if not isinstance(current_raw, str):
        raise RuntimeError(f"hero name config missing current: {path}")
    current = current_raw.strip()
    if not current:
        raise RuntimeError(f"hero name config missing current: {path}")

    aliases_raw = data.get("aliases") or []
    if not isinstance(aliases_raw, list):
        raise RuntimeError(f"hero name aliases must be a list: {path}")
    if not all(isinstance(name, str) for name in aliases_raw):
        raise RuntimeError(f"hero name aliases must contain strings only: {path}")

    aliases = _dedupe(name.strip() for name in aliases_raw)
    return HeroNames(current=current, aliases=aliases)
