from __future__ import annotations

import json

import pytest

from scripts.hero_name import HeroNames, load_hero_names
from scripts.replay_and_compare import _hero_id


def test_load_hero_names_from_json(tmp_path):
    path = tmp_path / "hero_names.json"
    path.write_text(
        json.dumps(
            {
                "current": "Royal Police",
                "aliases": ["Royal Police", "斯文红衣"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    names = load_hero_names(path)

    assert names == HeroNames(
        current="Royal Police",
        aliases=("Royal Police", "斯文红衣"),
    )
    assert names.all_names == ("Royal Police", "斯文红衣")
    assert names.matches("Royal Police")
    assert names.matches("斯文红衣")


def test_plain_text_hero_name_is_invalid(tmp_path):
    path = tmp_path / "hero_names.json"
    path.write_text("Royal Police\n斯文红衣\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="invalid hero name json"):
        load_hero_names(path)


def test_replay_hero_id_matches_any_configured_name():
    players = [
        {"id": 1, "name": "其他人"},
        {"id": 2, "name": "斯文红衣"},
    ]
    names = HeroNames(current="Royal Police", aliases=("Royal Police", "斯文红衣"))

    assert _hero_id(players, names) == 2
