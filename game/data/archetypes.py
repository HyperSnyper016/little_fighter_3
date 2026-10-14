from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Archetype:
    key: str
    label: str
    stats: Mapping[str, object]
    movement: Mapping[str, float]


ARCHETYPES = {
    "balanced": Archetype(
        "balanced",
        "Balanced",
        {"max_health": 10, "max_mana": 100, "touch_damage": 1, "hitbox": (92, 160)},
        {
            "walk_speed": 220.0,
            "run_speed": 380.0,
            "lane_speed": 150.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
    ),
    "grunt": Archetype(
        "grunt",
        "Grunt",
        {"max_health": 10, "max_mana": 20, "touch_damage": 1, "hitbox": (92, 160)},
        {
            "walk_speed": 220.0,
            "run_speed": 380.0,
            "lane_speed": 150.0,
            "jump_velocity": -700.0,
            "gravity": 1800.0,
        },
    ),
    "brawler": Archetype(
        "brawler",
        "Brawler",
        {"max_health": 11, "max_mana": 80, "touch_damage": 1, "hitbox": (92, 160)},
        {
            "walk_speed": 210.0,
            "run_speed": 360.0,
            "lane_speed": 145.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
    ),
    "ranger": Archetype(
        "ranger",
        "Ranger",
        {"max_health": 9, "max_mana": 110, "touch_damage": 1, "hitbox": (92, 160)},
        {
            "walk_speed": 230.0,
            "run_speed": 390.0,
            "lane_speed": 155.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
    ),
    "mystic": Archetype(
        "mystic",
        "Mystic",
        {"max_health": 9, "max_mana": 120, "touch_damage": 1, "hitbox": (92, 160)},
        {
            "walk_speed": 210.0,
            "run_speed": 360.0,
            "lane_speed": 145.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
    ),
    "heavyweight": Archetype(
        "heavyweight",
        "Heavyweight",
        {"max_health": 12, "max_mana": 70, "touch_damage": 1, "hitbox": (96, 164)},
        {
            "walk_speed": 190.0,
            "run_speed": 320.0,
            "lane_speed": 130.0,
            "jump_velocity": -480.0,
            "gravity": 1300.0,
        },
    ),
    "agile": Archetype(
        "agile",
        "Agile",
        {"max_health": 9, "max_mana": 100, "touch_damage": 1, "hitbox": (88, 154)},
        {
            "walk_speed": 240.0,
            "run_speed": 430.0,
            "lane_speed": 165.0,
            "jump_velocity": -560.0,
            "gravity": 1180.0,
        },
    ),
    "boss": Archetype(
        "boss",
        "Boss",
        {"max_health": 15, "max_mana": 120, "touch_damage": 1, "hitbox": (100, 170)},
        {
            "walk_speed": 210.0,
            "run_speed": 360.0,
            "lane_speed": 140.0,
            "jump_velocity": -500.0,
            "gravity": 1250.0,
        },
    ),
    "training": Archetype(
        "training",
        "Training",
        {"max_health": 10, "max_mana": 20, "touch_damage": 1, "hitbox": (92, 160)},
        {
            "walk_speed": 180.0,
            "run_speed": 300.0,
            "lane_speed": 130.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
    ),
    "dummy": Archetype(
        "dummy",
        "Dummy",
        {"max_health": 9999, "max_mana": 20, "touch_damage": 0, "hitbox": (92, 160)},
        {
            "walk_speed": 0.0,
            "run_speed": 0.0,
            "lane_speed": 0.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
    ),
}


CHARACTER_ARCHETYPES = {
    "bandit": "grunt",
    "armored_bandit": "heavyweight",
    "axle": "brawler",
    "bat": "agile",
    "dark_bat": "agile",
    "davis": "brawler",
    "deep": "brawler",
    "denis": "agile",
    "firen": "mystic",
    "firzen": "mystic",
    "freeze": "mystic",
    "henry": "ranger",
    "hunter": "ranger",
    "jack": "balanced",
    "jan": "mystic",
    "john": "mystic",
    "julian": "boss",
    "knight": "heavyweight",
    "luis": "heavyweight",
    "luis_liberated": "heavyweight",
    "mark": "brawler",
    "monk": "brawler",
    "rudolf": "ranger",
    "sorcerer": "mystic",
    "template": "training",
    "woody": "agile",
    "dummy": "dummy",
}


def resolve_character_profile(
    character_key: str,
    definition: Mapping[str, Any],
) -> tuple[Archetype, dict[str, object], dict[str, float]]:
    archetype = ARCHETYPES[CHARACTER_ARCHETYPES.get(character_key, "balanced")]
    stats = {**archetype.stats, **definition.get("stats", {})}
    # Health and mana are archetype baselines; exceptional values belong in stat_overrides.
    stat_overrides = definition.get("stat_overrides", {})
    stats["max_health"] = stat_overrides.get("max_health", archetype.stats["max_health"])
    stats["max_mana"] = stat_overrides.get("max_mana", archetype.stats["max_mana"])
    stats.update(stat_overrides)
    movement = {**archetype.movement, **definition.get("movement", {})}
    return archetype, stats, movement
