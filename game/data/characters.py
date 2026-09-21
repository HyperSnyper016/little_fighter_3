from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _character_path(*parts: str) -> Path:
    return PROJECT_ROOT / "assets" / "sprites" / "characters" / Path(*parts)


def _natural_sort_key(path: Path) -> list[str | int]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def _animation_files(*parts: str) -> list[Path]:
    folder = _character_path(*parts)
    return sorted((path for path in folder.iterdir() if path.is_file()), key=_natural_sort_key)


def _prefixed_animation_files(prefix: str, *parts: str) -> list[Path]:
    folder = _character_path(*parts)
    return sorted((path for path in folder.iterdir() if path.is_file() and path.name.startswith(prefix)), key=_natural_sort_key)


CHARACTERS = {
    "bandit": {
        "display_name": "Bandit",
        "scale": 2,
        "shadow_size": (56, 18),
        "stats": {
            "max_health": 20,
            "max_mana": 100,
            "touch_damage": 1,
            "hitbox": (92, 160),
        },
        "animations": {
            "idle": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "idle" / "bandit_idle_1.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "idle" / "bandit_idle_2.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "idle" / "bandit_idle_3.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "idle" / "bandit_idle_4.bmp",
                ],
                "frame_duration": 0.12,
                "loop": True,
            },
            "walk": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "walk" / "bandit_walk_5.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "walk" / "bandit_walk_6.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "walk" / "bandit_walk_7.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "walk" / "bandit_walk_8.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "walk" / "bandit_walk_9.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "walk" / "bandit_walk_10.bmp",
                ],
                "frame_duration": 0.09,
                "loop": True,
            },
            "run": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "run" / "bandit_0_21.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "run" / "bandit_0_22.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "run" / "bandit_0_23.bmp",
                ],
                "frame_duration": 0.07,
                "loop": True,
            },
            "lift_heavy": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "lift_heavy" / "bandit_0_24.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "lift_heavy" / "bandit_0_25.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "lift_heavy" / "bandit_0_26.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "lift_heavy" / "bandit_0_27.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "lift_heavy" / "bandit_0_28.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "lift_heavy" / "bandit_0_29.bmp",
                ],
                "frame_duration": 0.08,
                "loop": False,
            },
            "knocked": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "bandit_0_31.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "bandit_0_32.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "bandit_0_33.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "bandit_0_34.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "bandit_0_35.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "bandit_0_36.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "bandit_0_37.bmp",
                ],
                "frame_duration": 0.08,
                "loop": False,
            },
            "knocked_fire": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "knocked_fire" / "bandit_1_31.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "knocked_fire" / "bandit_1_32.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "knocked_fire" / "bandit_1_41.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "knocked_fire" / "bandit_1_42.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "knocked_fire" / "bandit_1_43.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "knocked_fire" / "bandit_1_44.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "knocked_fire" / "bandit_1_45.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "knocked_fire" / "bandit_1_46.bmp",
                ],
                "frame_duration": 0.07,
                "loop": False,
            },
            "knocked_freeze": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "knocked_freeze" / "bandit_1_36.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "knocked" / "knocked_freeze" / "bandit_1_46.bmp",
                ],
                "frame_duration": 0.16,
                "loop": False,
            },
            "drink": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "drink" / "bandit_1_63.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "drink" / "bandit_1_64.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "drink" / "bandit_1_65.bmp",
                ],
                "frame_duration": 0.08,
                "loop": False,
            },
            "sprint_punch": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "sprint_punch" / "bandit_1_35.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "sprint_punch" / "bandit_1_37.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "sprint_punch" / "bandit_1_38.bmp",
                ],
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "throw" / "bandit_1_25.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "throw" / "bandit_1_26.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "throw" / "bandit_1_27.bmp",
                ],
                "frame_duration": 0.08,
                "loop": False,
            },
            "hurt": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "hurt" / "bandit_1_51.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "hurt" / "bandit_1_54.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "hurt" / "bandit_1_62.bmp",
                ],
                "frame_duration": 0.08,
                "loop": False,
            },
            "get_up": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "get_up" / "bandit_0_37.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "jump_normal": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "jump" / "normal" / "bandit_0_62.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "jump" / "normal" / "bandit_0_63.bmp",
                ],
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "jump" / "second" / "bandit_0_62.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "jump" / "second" / "bandit_0_64.bmp",
                ],
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_attack": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "jump_attack" / "bandit_1_21.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "jump_attack" / "bandit_1_22.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "jump_attack" / "bandit_1_23.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "jump_attack" / "bandit_1_24.bmp",
                ],
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "block" / "bandit_0_57.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "block" / "bandit_0_58.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "block_break" / "bandit_0_47.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "block_break" / "bandit_0_48.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "block_break" / "bandit_0_49.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "block_dodge" / "bandit_0_50.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "block_dodge" / "bandit_0_59.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "block_dodge" / "bandit_0_60.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "block_dodge" / "bandit_0_61.bmp",
                ],
                "frame_duration": 0.06,
                "loop": False,
            },
            "attack_punch": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "basic_attack" / "bandit_punch_1.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "basic_attack" / "bandit_punch_2.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "basic_attack" / "bandit_punch_3.bmp",
                ],
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_kick": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "basic_attack" / "bandit_kick_1.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "basic_attack" / "bandit_kick_2.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "basic_attack" / "bandit_kick_3.bmp",
                ],
                "frame_duration": 0.07,
                "loop": False,
            },
            "heavy_attack": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "heavy_attack" / "bandit_0_38.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "heavy_attack" / "bandit_0_39.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "heavy_attack" / "bandit_0_40.bmp",
                ],
                "frame_duration": 0.07,
                "loop": False,
            },
            "grapple": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "grapple" / "bandit_0_51.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "grapple" / "bandit_0_52.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "grapple" / "bandit_0_53.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "grapple" / "grappled" / "bandit_0_54.bmp",
                ],
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "grapple" / "grapple_hit" / "bandit_0_55.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "grapple" / "grapple_hit" / "bandit_0_56.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "die" / "bandit_0_41.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "die" / "bandit_0_42.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "die" / "bandit_0_43.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "die" / "bandit_0_44.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "die" / "bandit_0_45.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "die" / "bandit_0_46.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "bandit" / "die" / "bandit_0_47.bmp",
                ],
                "frame_duration": 0.12,
                "loop": False,
            },
        },
        "movement": {
            "walk_speed": 220.0,
            "run_speed": 380.0,
            "lane_speed": 150.0,
            "jump_velocity": -700.0,
            "gravity": 1800.0,
        },
        "combat": {
            "attack_duration": 0.18,
        },
        "basic_attack_cycle": ["attack_punch", "attack_kick"],
    },
    "hunter": {
        "display_name": "Hunter",
        "scale": 2,
        "shadow_size": (56, 18),
        "stats": {
            "max_health": 20,
            "max_mana": 100,
            "touch_damage": 1,
            "hitbox": (92, 160),
        },
        "animations": {
            "idle": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "idle" / "hunter_0_1.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "idle" / "hunter_0_2.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "idle" / "hunter_0_3.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "idle" / "hunter_0_4.bmp",
                ],
                "frame_duration": 0.12,
                "loop": True,
            },
            "walk": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "walk" / "hunter_0_5.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "walk" / "hunter_0_6.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "walk" / "hunter_0_7.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "walk" / "hunter_0_8.bmp",
                ],
                "frame_duration": 0.09,
                "loop": True,
            },
            "run": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "run" / "hunter_0_21.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "run" / "hunter_0_22.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "run" / "hunter_0_23.bmp",
                ],
                "frame_duration": 0.07,
                "loop": True,
            },
            "lift_heavy": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "lift_heavy" / "hunter_0_24.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "lift_heavy" / "hunter_0_25.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "lift_heavy" / "hunter_0_26.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "lift_heavy" / "hunter_0_27.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "lift_heavy" / "hunter_0_28.bmp",
                ],
                "frame_duration": 0.08,
                "loop": False,
            },
            "knocked": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "knocked" / "hunter_0_31.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "knocked" / "hunter_0_32.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "knocked" / "hunter_0_33.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "knocked" / "hunter_0_34.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "knocked" / "hunter_0_35.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "knocked" / "hunter_0_36.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "knocked" / "hunter_0_37.bmp",
                ],
                "frame_duration": 0.08,
                "loop": False,
            },
            "knocked_fire": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "knocked" / "knocked_fire" / "hunter_1_18.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "knocked" / "knocked_fire" / "hunter_1_19.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "knocked" / "knocked_fire" / "hunter_1_35.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "knocked" / "knocked_fire" / "hunter_1_36.bmp",
                ],
                "frame_duration": 0.07,
                "loop": False,
            },
            "knocked_freeze": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "knocked" / "knocked_freeze" / "hunter_1_9.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "knocked" / "knocked_freeze" / "hunter_1_10.bmp",
                ],
                "frame_duration": 0.16,
                "loop": False,
            },
            "drink": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "drink" / "hunter_1_63.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "drink" / "hunter_1_64.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "drink" / "hunter_1_65.bmp",
                ],
                "frame_duration": 0.08,
                "loop": False,
            },
            "sprint_punch": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "sprint_punch" / "hunter_1_11.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "sprint_punch" / "hunter_1_12.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "sprint_punch" / "hunter_1_13.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "sprint_punch" / "hunter_1_14.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "sprint_punch" / "hunter_1_16.bmp",
                ],
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "throw" / "hunter_0_29.bmp",
                ],
                "frame_duration": 0.08,
                "loop": False,
            },
            "hurt": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "hurt" / "hunter_1_51.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "hurt" / "hunter_1_52.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "hurt" / "hunter_1_53.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "hurt" / "hunter_1_54.bmp",
                ],
                "frame_duration": 0.08,
                "loop": False,
            },
            "get_up": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "get_up" / "hunter_0_37.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "jump_normal": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "jump" / "normal" / "hunter_0_62.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "jump" / "normal" / "hunter_0_63.bmp",
                ],
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "jump" / "second" / "hunter_0_62.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "jump" / "second" / "hunter_0_64.bmp",
                ],
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_attack": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "jump_attack" / "hunter_1_37.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "jump_attack" / "hunter_1_38.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "jump_attack" / "hunter_1_39.bmp",
                ],
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "block" / "hunter_0_57.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "block" / "hunter_0_58.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "block_break" / "hunter_0_47.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "block_break" / "hunter_0_49.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "block_dodge" / "hunter_0_17.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "block_dodge" / "hunter_0_18.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "block_dodge" / "hunter_0_19.bmp",
                ],
                "frame_duration": 0.06,
                "loop": False,
            },
            "attack_punch": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "basic_attack" / "hunter_0_11.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "basic_attack" / "hunter_0_12.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "basic_attack" / "hunter_0_13.bmp",
                ],
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_kick": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "basic_attack" / "hunter_0_14.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "basic_attack" / "hunter_0_15.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "basic_attack" / "hunter_0_16.bmp",
                ],
                "frame_duration": 0.07,
                "loop": False,
            },
            "heavy_attack": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "heavy_attack" / "hunter_0_38.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "heavy_attack" / "hunter_0_40.bmp",
                ],
                "frame_duration": 0.07,
                "loop": False,
            },
            "grapple": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "grapple" / "grapple_hit" / "hunter_0_51.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "grapple" / "grapple_hit" / "hunter_0_52.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "grapple" / "grapple_hit" / "hunter_0_53.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "grapple" / "grappled" / "hunter_0_54.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "grapple" / "grappled" / "hunter_0_55.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "grapple" / "grappled" / "hunter_0_56.bmp",
                ],
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "grapple" / "grapple_hit" / "hunter_0_51.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "grapple" / "grapple_hit" / "hunter_0_52.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "grapple" / "grapple_hit" / "hunter_0_53.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "die" / "hunter_0_41.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "die" / "hunter_0_42.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "die" / "hunter_0_43.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "die" / "hunter_0_44.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "die" / "hunter_0_45.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "die" / "hunter_0_46.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "characters" / "hunter" / "die" / "hunter_0_47.png",
                ],
                "frame_duration": 0.12,
                "loop": False,
            },
        },
        "movement": {
            "walk_speed": 220.0,
            "run_speed": 380.0,
            "lane_speed": 150.0,
            "jump_velocity": -700.0,
            "gravity": 1800.0,
        },
        "combat": {
            "attack_duration": 0.18,
        },
        "basic_attack_cycle": ["attack_punch", "attack_kick"],
    },
    "template": {
        "display_name": "Template",
        "scale": 2,
        "shadow_size": (56, 18),
        "stats": {
            "max_health": 20,
            "max_mana": 100,
            "touch_damage": 1,
            "hitbox": (92, 160),
        },
        "animations": {
            "idle": {
                "files": _animation_files("template", "idle"),
                "frame_duration": 0.18,
                "loop": True,
            },
            "walk": {
                "files": _animation_files("template", "walk"),
                "frame_duration": 0.12,
                "loop": True,
            },
            "run": {
                "files": _animation_files("template", "run"),
                "frame_duration": 0.10,
                "loop": True,
            },
            "lift_heavy": {
                "files": _animation_files("template", "lift_heavy"),
                "frame_duration": 0.11,
                "loop": False,
            },
            "knocked": {
                "files": _animation_files("template", "knocked"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "get_up": {
                "files": _animation_files("template", "get_up"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_normal": {
                "files": _animation_files("template", "jump", "normal"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": _animation_files("template", "jump", "second"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_attack": {
                "files": _animation_files("template", "jump_attack"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "drink": {
                "files": _animation_files("template", "drink"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "hurt": {
                "files": _animation_files("template", "hurt"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": _animation_files("template", "block"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": _animation_files("template", "block_break"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": _animation_files("template", "block_dodge"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "attack_1": {
                "files": _prefixed_animation_files("attack_1_", "template", "basic_attack"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "attack_2": {
                "files": _prefixed_animation_files("attack_2_", "template", "basic_attack"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "attack_3": {
                "files": _prefixed_animation_files("attack_3_", "template", "basic_attack"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "heavy_attack": {
                "files": _animation_files("template", "heavy_attack"),
                "frame_duration": 0.09,
                "loop": False,
            },
            "sp_move_attack": {
                "files": _animation_files("template", "sp_move_attack"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack": {
                "files": _animation_files("template", "sp_vert_attack"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sprint_punch": {
                "files": _animation_files("template", "sprint_punch"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": _animation_files("template", "throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "throw_heavy": {
                "files": _animation_files("template", "throw_heavy"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "grapple": {
                "files": _animation_files("template", "grapple"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": _animation_files("template", "grapple", "grappled"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": _animation_files("template", "grapple", "grapple_hit"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": _animation_files("template", "die"),
                "frame_duration": 0.12,
                "loop": False,
            },
        },
        "movement": {
            "walk_speed": 180.0,
            "run_speed": 300.0,
            "lane_speed": 130.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
        "combat": {
            "attack_duration": 0.30,
            "special_projectile_interval": 0.5,
        },
        "basic_attack_cycle": ["attack_1", "attack_2", "attack_3"],
    },
}
