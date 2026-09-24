from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _character_path(*parts: str) -> Path:
    return PROJECT_ROOT / "assets" / "sprites" / "characters" / Path(*parts)


def _shared_character_path(*parts: str) -> Path:
    return PROJECT_ROOT / "assets" / "sprites" / "shared_sprites" / Path(*parts)


def _natural_sort_key(path: Path) -> list[str | int]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def _animation_files(*parts: str) -> list[Path]:
    folder = _character_path(*parts)
    if not folder.exists():
        return []
    return sorted((path for path in folder.iterdir() if path.is_file()), key=_natural_sort_key)


def _prefixed_animation_files(prefix: str, *parts: str) -> list[Path]:
    folder = _character_path(*parts)
    if not folder.exists():
        return []
    return sorted((path for path in folder.iterdir() if path.is_file() and path.name.startswith(prefix)), key=_natural_sort_key)


def _shared_animation_files(*parts: str) -> list[Path]:
    folder = _shared_character_path(*parts)
    if not folder.exists():
        return []
    return sorted((path for path in folder.iterdir() if path.is_file()), key=_natural_sort_key)


CHARACTERS = {
    "bandit": {
        "display_name": "Bandit",
        "scale": 2,
        "shadow_size": (56, 18),
        "stats": {
            "max_health": 20,
            "max_mana": 20,
            "touch_damage": 1,
            "hitbox": (92, 160),
        },
        "animations": {
            "idle": {
                "files": _animation_files("bandit", "idle"),
                "frame_duration": 0.12,
                "loop": True,
            },
            "walk": {
                "files": _animation_files("bandit", "movement", "walking"),
                "frame_duration": 0.09,
                "loop": True,
            },
            "run": {
                "files": _animation_files("bandit", "movement", "sprinting"),
                "frame_duration": 0.07,
                "loop": True,
            },
            "lift_heavy": {
                "files": _animation_files("bandit", "hold_item", "heavy_carry", "walk"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "fall": {
                "files": _animation_files("bandit", "fall", "knocked_down", "basic"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "knocked_fire": {
                "files": _animation_files("bandit", "fall", "knocked_down", "fire"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "knocked_freeze": {
                "files": _animation_files("bandit", "fall", "knocked_down", "ice", "freeze"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "knocked_freeze_break": {
                "files": _animation_files("bandit", "fall", "knocked_down", "ice", "freeze_break"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "drink": {
                "files": _animation_files("bandit", "hold_item", "drink"),
                "frame_duration": 0.08,
                "loop": True,
            },
            "sprint_punch": {
                "files": _animation_files("bandit", "movement", "sprint_basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": _animation_files("bandit", "hold_item", "throw_item", "ground_throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "hurt": {
                "files": _animation_files("bandit", "hurt", "basic_hurt"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "get_up": {
                "files": _animation_files("bandit", "fall", "get_up"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "jump_normal": {
                "files": _animation_files("bandit", "movement", "jump_actions", "basic_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": _animation_files("bandit", "movement", "jump_actions", "second_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_attack": {
                "files": _animation_files("bandit", "actions", "jump_attack"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": _animation_files("bandit", "actions", "defend_actions", "defend"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": _animation_files("bandit", "actions", "defend_actions", "defend_break"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": _prefixed_animation_files("dodge_1_", "bandit", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.06,
                "loop": False,
            },
            "block_dodge_alt": {
                "files": _prefixed_animation_files("dodge_2_", "bandit", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.06,
                "loop": False,
            },
            "attack_punch": {
                "files": _prefixed_animation_files("attack_1_", "bandit", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_kick": {
                "files": [
                    *_prefixed_animation_files("attack_2_", "bandit", "actions", "basic_attack"),
                    *_prefixed_animation_files("attack_3_", "bandit", "actions", "basic_attack"),
                ],
                "frame_duration": 0.07,
                "loop": False,
            },
            "heavy_attack": {
                "files": _animation_files("bandit", "actions", "sp_move_attack_1"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "grapple": {
                "files": _animation_files("bandit", "actions", "grapple_actions", "grappling"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": _animation_files("bandit", "actions", "grapple_actions", "grappled"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": _animation_files("bandit", "actions", "grapple_actions", "grappled", "hit_grappled"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": _animation_files("bandit", "hurt", "died"),
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
    "armored_bandit": {
        "display_name": "Armored Bandit",
        "scale": 2,
        "shadow_size": (56, 18),
        "stats": {
            "max_health": 20,
            "max_mana": 20,
            "touch_damage": 1,
            "hitbox": (92, 160),
        },
        "animations": {
            "idle": {
                "files": _animation_files("armored_bandit", "idle"),
                "frame_duration": 0.12,
                "loop": True,
            },
            "walk": {
                "files": _animation_files("armored_bandit", "movement", "walking"),
                "frame_duration": 0.09,
                "loop": True,
            },
            "run": {
                "files": _animation_files("armored_bandit", "movement", "sprinting"),
                "frame_duration": 0.07,
                "loop": True,
            },
            "lift_heavy": {
                "files": _animation_files("armored_bandit", "hold_item", "heavy_carry", "walk"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "fall": {
                "files": _animation_files("armored_bandit", "fall", "knocked_down", "basic"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "knocked_fire": {
                "files": _animation_files("armored_bandit", "fall", "knocked_down", "fire"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "knocked_freeze": {
                "files": _animation_files("armored_bandit", "fall", "knocked_down", "ice", "freeze"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "knocked_freeze_break": {
                "files": _animation_files("armored_bandit", "fall", "knocked_down", "ice", "freeze_break"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "drink": {
                "files": _animation_files("armored_bandit", "hold_item", "drink"),
                "frame_duration": 0.08,
                "loop": True,
            },
            "sprint_punch": {
                "files": _animation_files("armored_bandit", "movement", "sprint_basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": _animation_files("armored_bandit", "hold_item", "throw_item", "ground_throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "hurt": {
                "files": _animation_files("armored_bandit", "hurt", "basic_hurt"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "get_up": {
                "files": _animation_files("armored_bandit", "fall", "get_up"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "jump_normal": {
                "files": _animation_files("armored_bandit", "movement", "jump_actions", "basic_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": _animation_files("armored_bandit", "movement", "jump_actions", "second_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_attack": {
                "files": _animation_files("armored_bandit", "actions", "jump_attack"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": _animation_files("armored_bandit", "actions", "defend_actions", "defend"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": _animation_files("armored_bandit", "actions", "defend_actions", "defend_break"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": _prefixed_animation_files("dodge_1_", "armored_bandit", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.06,
                "loop": False,
            },
            "block_dodge_alt": {
                "files": _prefixed_animation_files("dodge_2_", "armored_bandit", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.06,
                "loop": False,
            },
            "attack_punch": {
                "files": _prefixed_animation_files("attack_1_", "armored_bandit", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_kick": {
                "files": [
                    *_prefixed_animation_files("attack_2_", "armored_bandit", "actions", "basic_attack"),
                    *_prefixed_animation_files("attack_3_", "armored_bandit", "actions", "basic_attack"),
                ],
                "frame_duration": 0.07,
                "loop": False,
            },
            "heavy_attack": {
                "files": _animation_files("armored_bandit", "actions", "sp_move_attack_1"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "grapple": {
                "files": _animation_files("armored_bandit", "actions", "grapple_actions", "grappling"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": _animation_files("armored_bandit", "actions", "grapple_actions", "grappled"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": _animation_files("armored_bandit", "actions", "grapple_actions", "grappled", "hit_grappled"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": _animation_files("armored_bandit", "hurt", "died"),
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
    "dark_bat": {
        "display_name": "Dark Bat",
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
                "files": _animation_files("dark_bat", "idle"),
                "frame_duration": 0.12,
                "loop": True,
            },
            "walk": {
                "files": _animation_files("dark_bat", "movement", "walking"),
                "frame_duration": 0.09,
                "loop": True,
            },
            "run": {
                "files": _animation_files("dark_bat", "movement", "sprinting"),
                "frame_duration": 0.07,
                "loop": True,
            },
            "lift_heavy": {
                "files": _animation_files("dark_bat", "hold_item", "heavy_carry", "walk"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "fall": {
                "files": _animation_files("dark_bat", "fall", "knocked_down", "basic"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "knocked_fire": {
                "files": _animation_files("dark_bat", "fall", "knocked_down", "fire"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "knocked_freeze": {
                "files": _animation_files("dark_bat", "fall", "knocked_down", "ice", "freeze"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "knocked_freeze_break": {
                "files": _animation_files("dark_bat", "fall", "knocked_down", "ice", "freeze_break"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "get_up": {
                "files": _animation_files("dark_bat", "fall", "get_up"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_normal": {
                "files": _animation_files("dark_bat", "movement", "jump_actions", "basic_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": _animation_files("dark_bat", "movement", "jump_actions", "second_jump"),
                "frame_duration": 0.10,
                "loop": True,
            },
            "jump_attack": {
                "files": _animation_files("dark_bat", "actions", "jump_attack"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "drink": {
                "files": _animation_files("dark_bat", "hold_item", "drink"),
                "frame_duration": 0.08,
                "loop": True,
            },
            "hurt": {
                "files": _animation_files("dark_bat", "hurt", "basic_hurt"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": _animation_files("dark_bat", "actions", "defend_actions", "defend"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": _animation_files("dark_bat", "actions", "defend_actions", "defend_break"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": _prefixed_animation_files("dodge_1_", "dark_bat", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.06,
                "loop": False,
            },
            "attack_1": {
                "files": _prefixed_animation_files("attack_1_", "dark_bat", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_2": {
                "files": _prefixed_animation_files("attack_2_", "dark_bat", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_3": {
                "files": _prefixed_animation_files("attack_3_", "dark_bat", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_4": {
                "files": _prefixed_animation_files("attack_4_", "dark_bat", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "heavy_attack": {
                "files": _animation_files("dark_bat", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_1": {
                "files": _animation_files("dark_bat", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_2": {
                "files": _animation_files("dark_bat", "actions", "sp_move_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_1": {
                "files": _animation_files("dark_bat", "actions", "sp_vert_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_2": {
                "files": _animation_files("dark_bat", "actions", "sp_vert_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sprint_punch": {
                "files": _animation_files("dark_bat", "movement", "sprint_basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": _animation_files("dark_bat", "hold_item", "throw_item", "ground_throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "throw_heavy": {
                "files": _animation_files("dark_bat", "hold_item", "heavy_carry", "throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "grapple": {
                "files": _animation_files("dark_bat", "actions", "grapple_actions", "grappling"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": _animation_files("dark_bat", "actions", "grapple_actions", "grappled"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": _animation_files("dark_bat", "actions", "grapple_actions", "grappled", "hit_grappled"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": _animation_files("dark_bat", "hurt", "died"),
                "frame_duration": 0.12,
                "loop": False,
            },
        },
        "movement": {
            "walk_speed": 220.0,
            "run_speed": 380.0,
            "lane_speed": 150.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
        "combat": {
            "attack_duration": 0.30,
            "special_projectile_interval": 0.5,
        },
        "basic_attack_cycle": ["attack_1", "attack_2", "attack_3", "attack_4"],
    },
    "hunter": {
        "display_name": "Hunter",
        "scale": 2,
        "shadow_size": (56, 18),
        "stats": {
            "max_health": 20,
            "max_mana": 20,
            "touch_damage": 1,
            "hitbox": (92, 160),
        },
        "animations": {
            "idle": {
                "files": _animation_files("hunter", "idle"),
                "frame_duration": 0.12,
                "loop": True,
            },
            "walk": {
                "files": _animation_files("hunter", "movement", "walking"),
                "frame_duration": 0.09,
                "loop": True,
            },
            "run": {
                "files": _animation_files("hunter", "movement", "sprinting"),
                "frame_duration": 0.07,
                "loop": True,
            },
            "lift_heavy": {
                "files": _animation_files("hunter", "hold_item", "heavy_carry", "walk"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "fall": {
                "files": _animation_files("hunter", "fall", "knocked_down", "basic"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "knocked_fire": {
                "files": _animation_files("hunter", "fall", "knocked_down", "fire"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "knocked_freeze": {
                "files": _animation_files("hunter", "fall", "knocked_down", "ice", "freeze"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "drink": {
                "files": _animation_files("hunter", "hold_item", "drink"),
                "frame_duration": 0.08,
                "loop": True,
            },
            "sprint_punch": {
                "files": _animation_files("hunter", "movement", "sprint_basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": _animation_files("hunter", "hold_item", "throw_item", "ground_throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "hurt": {
                "files": _animation_files("hunter", "hurt", "basic_hurt"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "get_up": {
                "files": _animation_files("hunter", "fall", "get_up"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "jump_normal": {
                "files": _animation_files("hunter", "movement", "jump_actions", "basic_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": _animation_files("hunter", "movement", "jump_actions", "second_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_attack": {
                "files": _animation_files("hunter", "actions", "jump_attack"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": _animation_files("hunter", "actions", "defend_actions", "defend"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": _animation_files("hunter", "actions", "defend_actions", "defend_break"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": _prefixed_animation_files("dodge_1_", "hunter", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.06,
                "loop": False,
            },
            "block_dodge_alt": {
                "files": _prefixed_animation_files("dodge_2_", "hunter", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.06,
                "loop": False,
            },
            "attack_punch": {
                "files": _animation_files("hunter", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_kick": {
                "files": _prefixed_animation_files("attack_2_", "hunter", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "heavy_attack": {
                "files": _animation_files("hunter", "actions", "sp_move_attack_1"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "grapple": {
                "files": _animation_files("hunter", "actions", "grapple_actions", "grappling"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": _animation_files("hunter", "actions", "grapple_actions", "grappled"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": _animation_files("hunter", "actions", "grapple_actions", "grappling", "hit_grappled_target"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": _animation_files("hunter", "hurt", "died"),
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
        "basic_attack_cycle": ["attack_punch"],
    },
    "template": {
        "display_name": "Template",
        "scale": 2,
        "shadow_size": (56, 18),
        "stats": {
            "max_health": 20,
            "max_mana": 20,
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
                "files": _animation_files("template", "movement", "walking"),
                "frame_duration": 0.12,
                "loop": True,
            },
            "run": {
                "files": _animation_files("template", "movement", "sprinting"),
                "frame_duration": 0.10,
                "loop": True,
            },
            "lift_heavy": {
                "files": _animation_files("template", "hold_item", "heavy_carry", "walk"),
                "frame_duration": 0.11,
                "loop": False,
            },
            "fall": {
                "files": _animation_files("template", "fall", "knocked_down", "basic"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "get_up": {
                "files": _animation_files("template", "fall", "get_up"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_normal": {
                "files": _animation_files("template", "movement", "jump_actions", "basic_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": _animation_files("template", "movement", "jump_actions", "second_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_attack": {
                "files": _animation_files("template", "hold_item", "weapon_carry", "jump_attack"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "drink": {
                "files": _animation_files("template", "hold_item", "drink"),
                "frame_duration": 0.08,
                "loop": True,
            },
            "hurt": {
                "files": _animation_files("template", "hurt", "basic_hurt"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": _animation_files("template", "actions", "defend_actions", "defend"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": _animation_files("template", "actions", "defend_actions", "defend_break"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": _prefixed_animation_files("dodge_1_", "template", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block_dodge_alt": {
                "files": _prefixed_animation_files("dodge_2_", "template", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block_dodge_alt_2": {
                "files": _prefixed_animation_files("dodge_3_", "template", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "attack_1": {
                "files": _prefixed_animation_files("attack_1_", "template", "actions", "basic_attack"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "attack_2": {
                "files": _prefixed_animation_files("attack_2_", "template", "actions", "basic_attack"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "attack_3": {
                "files": _prefixed_animation_files("attack_3_", "template", "actions", "basic_attack"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "heavy_attack": {
                "files": _animation_files("template", "actions", "sp_move_attack_1"),
                "frame_duration": 0.09,
                "loop": False,
            },
            "sp_move_attack_1": {
                "files": _animation_files("template", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_1": {
                "files": _animation_files("template", "actions", "sp_vert_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sprint_punch": {
                "files": _animation_files("template", "movement", "sprint_basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": _animation_files("template", "hold_item", "throw_item", "ground_throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "throw_heavy": {
                "files": _animation_files("template", "hold_item", "heavy_carry", "throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "grapple": {
                "files": _animation_files("template", "actions", "grapple_actions", "grappling"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": _animation_files("template", "actions", "grapple_actions", "grappled"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": _animation_files("template", "actions", "grapple_actions", "grappled", "hit_grappled"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": _animation_files("template", "hurt", "died"),
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
    "deep": {
        "display_name": "Deep",
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
                "files": _animation_files("deep", "idle"),
                "frame_duration": 0.18,
                "loop": True,
            },
            "walk": {
                "files": _animation_files("deep", "movement", "walking"),
                "frame_duration": 0.12,
                "loop": True,
            },
            "run": {
                "files": _animation_files("deep", "movement", "sprinting"),
                "frame_duration": 0.10,
                "loop": True,
            },
            "lift_heavy": {
                "files": _animation_files("deep", "hold_item", "heavy_carry", "walk"),
                "frame_duration": 0.11,
                "loop": False,
            },
            "fall": {
                "files": _animation_files("deep", "fall", "knocked_down", "basic"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "knocked_fire": {
                "files": _animation_files("deep", "fall", "knocked_down", "fire"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "knocked_freeze": {
                "files": _animation_files("deep", "fall", "knocked_down", "ice", "freeze"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "knocked_freeze_break": {
                "files": _animation_files("deep", "fall", "knocked_down", "ice", "freeze_break"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "get_up": {
                "files": _animation_files("deep", "fall", "get_up"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_normal": {
                "files": _animation_files("deep", "movement", "jump_actions", "basic_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": _animation_files("deep", "movement", "jump_actions", "second_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_attack": {
                "files": _animation_files("deep", "actions", "jump_attack"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "drink": {
                "files": _animation_files("deep", "hold_item", "drink"),
                "frame_duration": 0.08,
                "loop": True,
            },
            "hurt": {
                "files": _animation_files("deep", "hurt", "basic_hurt"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": _animation_files("deep", "actions", "defend_actions", "defend"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": _animation_files("deep", "actions", "defend_actions", "defend_break"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": _prefixed_animation_files("dodge_1_", "deep", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block_dodge_alt": {
                "files": _prefixed_animation_files("dodge_2_", "deep", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block_dodge_alt_2": {
                "files": _prefixed_animation_files("dodge_3_", "deep", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "attack_1": {
                "files": _prefixed_animation_files("attack_1_", "deep", "actions", "basic_attack"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "attack_2": {
                "files": _prefixed_animation_files("attack_2_", "deep", "actions", "basic_attack"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "heavy_attack": {
                "files": _animation_files("deep", "actions", "sp_move_attack_1"),
                "frame_duration": 0.09,
                "loop": False,
            },
            "sp_move_attack_1": {
                "files": _prefixed_animation_files("sp_move_attack_1_", "deep", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_1_follow": {
                "files": _prefixed_animation_files("sp_move_attack_2_", "deep", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_2": {
                "files": _prefixed_animation_files("sp_move_attack_1_", "deep", "actions", "sp_move_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_2_follow": {
                "files": _prefixed_animation_files("sp_move_attack_2_", "deep", "actions", "sp_move_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_1": {
                "files": _animation_files("deep", "actions", "sp_vert_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_2": {
                "files": _animation_files("deep", "actions", "sp_vert_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sprint_punch": {
                "files": _animation_files("deep", "movement", "sprint_basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": _animation_files("deep", "hold_item", "throw_item", "ground_throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "throw_heavy": {
                "files": _animation_files("deep", "hold_item", "heavy_carry", "throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "grapple": {
                "files": _animation_files("deep", "actions", "grapple_actions", "grappling"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": _animation_files("deep", "actions", "grapple_actions", "grappled"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": _animation_files("deep", "actions", "grapple_actions", "grappled", "hit_grappled"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": _animation_files("deep", "hurt", "died"),
                "frame_duration": 0.12,
                "loop": False,
            },
        },
        "movement": {
            "walk_speed": 200.0,
            "run_speed": 420.0,
            "lane_speed": 130.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
        "combat": {
            "attack_duration": 0.30,
            "special_projectile_interval": 0.5,
        },
        "basic_attack_cycle": ["attack_1", "attack_2"],
    },
    "firen": {
        "display_name": "Firen",
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
                "files": _animation_files("firen", "idle"),
                "frame_duration": 0.12,
                "loop": True,
            },
            "walk": {
                "files": _animation_files("firen", "movement", "walking"),
                "frame_duration": 0.09,
                "loop": True,
            },
            "run": {
                "files": _animation_files("firen", "movement", "sprinting"),
                "frame_duration": 0.07,
                "loop": True,
            },
            "lift_heavy": {
                "files": _animation_files("firen", "hold_item", "heavy_carry", "walk"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "fall": {
                "files": _animation_files("firen", "fall", "knocked_down", "basic"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "knocked_fire": {
                "files": _animation_files("firen", "fall", "knocked_down", "fire"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "knocked_freeze": {
                "files": _animation_files("firen", "fall", "knocked_down", "ice", "freeze"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "knocked_freeze_break": {
                "files": _animation_files("firen", "fall", "knocked_down", "ice", "freeze_break"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "get_up": {
                "files": _animation_files("firen", "fall", "get_up"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_normal": {
                "files": _animation_files("firen", "movement", "jump_actions", "basic_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": _animation_files("firen", "movement", "jump_actions", "second_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_attack": {
                "files": _animation_files("firen", "actions", "jump_attack"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "drink": {
                "files": _animation_files("firen", "hold_item", "drink"),
                "frame_duration": 0.08,
                "loop": True,
            },
            "hurt": {
                "files": _animation_files("firen", "hurt", "basic_hurt"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": _animation_files("firen", "actions", "defend_actions", "defend"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": _animation_files("firen", "actions", "defend_actions", "defend_break"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": _animation_files("firen", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.06,
                "loop": False,
            },
            "attack_1": {
                "files": _prefixed_animation_files("1_", "firen", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_2": {
                "files": _prefixed_animation_files("2_", "firen", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_3": {
                "files": _prefixed_animation_files("3_", "firen", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_4": {
                "files": _prefixed_animation_files("4_", "firen", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "heavy_attack": {
                "files": _animation_files("firen", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_1": {
                "files": _prefixed_animation_files("1_", "firen", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_1_follow": {
                "files": _prefixed_animation_files("2_", "firen", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_1_follow_2": {
                "files": _prefixed_animation_files("3_", "firen", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_2": {
                "files": _prefixed_animation_files("1_", "firen", "actions", "sp_move_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_2_follow": {
                "files": _prefixed_animation_files("2_", "firen", "actions", "sp_move_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_1": {
                "files": _animation_files("firen", "actions", "sp_vert_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_2": {
                "files": _animation_files("firen", "actions", "sp_vert_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sprint_punch": {
                "files": _animation_files("firen", "movement", "sprint_basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": _animation_files("firen", "hold_item", "throw_item", "ground_throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "throw_heavy": {
                "files": _animation_files("firen", "hold_item", "heavy_carry", "throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "grapple": {
                "files": _animation_files("firen", "actions", "grapple_actions", "grappling"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": _animation_files("firen", "actions", "grapple_actions", "grappled"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": _animation_files("firen", "actions", "grapple_actions", "grappled", "hit_grappled"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": _animation_files("firen", "hurt", "died"),
                "frame_duration": 0.12,
                "loop": False,
            },
        },
        "movement": {
            "walk_speed": 200.0,
            "run_speed": 420.0,
            "lane_speed": 130.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
        "combat": {
            "attack_duration": 0.30,
        },
        "basic_attack_cycle": ["attack_1", "attack_2", "attack_3", "attack_4"],
    },
    "henry": {
        "display_name": "Henry",
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
                "files": _animation_files("henry", "idle"),
                "frame_duration": 0.12,
                "loop": True,
            },
            "walk": {
                "files": _animation_files("henry", "movement", "walking"),
                "frame_duration": 0.09,
                "loop": True,
            },
            "run": {
                "files": _animation_files("henry", "movement", "sprinting"),
                "frame_duration": 0.07,
                "loop": True,
            },
            "lift_heavy": {
                "files": _animation_files("henry", "hold_item", "heavy_carry", "walk"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "fall": {
                "files": _animation_files("henry", "fall", "knocked_down", "basic"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "knocked_fire": {
                "files": _animation_files("henry", "fall", "knocked_down", "fire"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "knocked_freeze": {
                "files": _animation_files("henry", "fall", "knocked_down", "ice", "freeze"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "knocked_freeze_break": {
                "files": _animation_files("henry", "fall", "knocked_down", "ice", "freeze_break"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "get_up": {
                "files": _animation_files("henry", "fall", "get_up"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_normal": {
                "files": _animation_files("henry", "movement", "jump_actions", "basic_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": _animation_files("henry", "movement", "jump_actions", "second_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_attack": {
                "files": _animation_files("henry", "actions", "jump_attack"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "drink": {
                "files": _animation_files("henry", "hold_item", "drink"),
                "frame_duration": 0.08,
                "loop": True,
            },
            "hurt": {
                "files": _animation_files("henry", "hurt", "basic_hurt"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": _animation_files("henry", "actions", "defend_actions", "defend"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": _animation_files("henry", "actions", "defend_actions", "defend_break"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": _prefixed_animation_files("1_", "henry", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.06,
                "loop": False,
            },
            "block_dodge_alt": {
                "files": _prefixed_animation_files("2_", "henry", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.06,
                "loop": False,
            },
            "attack_1": {
                "files": _animation_files("henry", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "heavy_attack": {
                "files": _animation_files("henry", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_1": {
                "files": _animation_files("henry", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_2": {
                "files": _animation_files("henry", "actions", "sp_move_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_1": {
                "files": _animation_files("henry", "actions", "sp_vert_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_2": {
                "files": _animation_files("henry", "actions", "sp_vert_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sprint_punch": {
                "files": _animation_files("henry", "movement", "sprint_basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": _animation_files("henry", "hold_item", "throw_item", "ground_throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "throw_heavy": {
                "files": _animation_files("henry", "hold_item", "heavy_carry", "throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "grapple": {
                "files": _animation_files("henry", "actions", "grapple_actions", "grappling"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": _animation_files("henry", "actions", "grapple_actions", "grappled"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": _animation_files("henry", "actions", "grapple_actions", "grappled", "hit_grappled"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": _animation_files("henry", "hurt", "died"),
                "frame_duration": 0.12,
                "loop": False,
            },
        },
        "movement": {
            "walk_speed": 220.0,
            "run_speed": 380.0,
            "lane_speed": 150.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
        "combat": {
            "attack_duration": 0.30,
        },
        "basic_attack_cycle": ["attack_1"],
    },
    "bat": {
        "display_name": "Bat",
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
                "files": _animation_files("bat", "idle"),
                "frame_duration": 0.12,
                "loop": True,
            },
            "walk": {
                "files": _animation_files("bat", "movement", "walking"),
                "frame_duration": 0.09,
                "loop": True,
            },
            "run": {
                "files": _animation_files("bat", "movement", "sprinting"),
                "frame_duration": 0.07,
                "loop": True,
            },
            "lift_heavy": {
                "files": _animation_files("bat", "hold_item", "heavy_carry", "walk"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "fall": {
                "files": _animation_files("bat", "fall", "knocked_down", "basic"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "knocked_fire": {
                "files": _animation_files("bat", "fall", "knocked_down", "fire"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "knocked_freeze": {
                "files": _animation_files("bat", "fall", "knocked_down", "ice", "freeze"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "knocked_freeze_break": {
                "files": _animation_files("bat", "fall", "knocked_down", "ice", "freeze_break"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "get_up": {
                "files": _animation_files("bat", "fall", "get_up"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_normal": {
                "files": _animation_files("bat", "movement", "jump_actions", "basic_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": _animation_files("bat", "movement", "jump_actions", "second_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_attack": {
                "files": _animation_files("bat", "actions", "jump_attack"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "drink": {
                "files": _animation_files("bat", "hold_item", "drink"),
                "frame_duration": 0.08,
                "loop": True,
            },
            "hurt": {
                "files": _animation_files("bat", "hurt", "basic_hurt"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": _animation_files("bat", "actions", "defend_actions", "defend"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": _animation_files("bat", "actions", "defend_actions", "defend_break"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": _prefixed_animation_files("dodge_1_", "bat", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.06,
                "loop": False,
            },
            "attack_1": {
                "files": _prefixed_animation_files("attack_1_", "bat", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_2": {
                "files": _prefixed_animation_files("attack_2_", "bat", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "heavy_attack": {
                "files": _animation_files("bat", "actions", "sp_move_attack_1"),
                "frame_duration": 0.09,
                "loop": False,
            },
            "sp_move_attack_1": {
                "files": _animation_files("bat", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_2": {
                "files": _animation_files("bat", "actions", "sp_move_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_1": {
                "files": _animation_files("bat", "actions", "sp_vert_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_2": {
                "files": _animation_files("bat", "actions", "sp_vert_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sprint_punch": {
                "files": _animation_files("bat", "movement", "sprint_basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": _animation_files("bat", "hold_item", "throw_item", "ground_throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "throw_heavy": {
                "files": _animation_files("bat", "hold_item", "heavy_carry", "throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "grapple": {
                "files": _animation_files("bat", "actions", "grapple_actions", "grappling"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": _animation_files("bat", "actions", "grapple_actions", "grappled"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": _animation_files("bat", "actions", "grapple_actions", "grappled", "hit_grappled"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": _animation_files("bat", "hurt", "died"),
                "frame_duration": 0.12,
                "loop": False,
            },
        },
        "movement": {
            "walk_speed": 220.0,
            "run_speed": 380.0,
            "lane_speed": 150.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
        "combat": {
            "attack_duration": 0.30,
            "special_projectile_interval": 0.5,
        },
        "basic_attack_cycle": ["attack_1", "attack_2"],
    },
    "davis": {
        "display_name": "Davis",
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
                "files": _animation_files("davis", "idle"),
                "frame_duration": 0.12,
                "loop": True,
            },
            "walk": {
                "files": _animation_files("davis", "movement", "walking"),
                "frame_duration": 0.09,
                "loop": True,
            },
            "run": {
                "files": _animation_files("davis", "movement", "sprinting"),
                "frame_duration": 0.07,
                "loop": True,
            },
            "lift_heavy": {
                "files": _animation_files("davis", "hold_item", "heavy_carry", "walk"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "fall": {
                "files": _animation_files("davis", "fall", "knocked_down", "basic"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "knocked_fire": {
                "files": _animation_files("davis", "fall", "knocked_down", "fire"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "knocked_freeze": {
                "files": _animation_files("davis", "fall", "knocked_down", "ice", "freeze"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "knocked_freeze_break": {
                "files": _animation_files("davis", "fall", "knocked_down", "ice", "freeze_break"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "get_up": {
                "files": _animation_files("davis", "fall", "get_up"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_normal": {
                "files": _animation_files("davis", "movement", "jump_actions", "basic_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": _animation_files("davis", "movement", "jump_actions", "second_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_attack": {
                "files": _animation_files("davis", "actions", "jump_attack"),
                "frame_duration": 0.08,
                "loop": False,
                "trim_small_components": 20,
            },
            "drink": {
                "files": _animation_files("davis", "hold_item", "drink"),
                "frame_duration": 0.08,
                "loop": True,
            },
            "hurt": {
                "files": _animation_files("davis", "hurt", "basic_hurt"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": _animation_files("davis", "actions", "defend_actions", "defend"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": _animation_files("davis", "actions", "defend_actions", "defend_break"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": _prefixed_animation_files("dodge_1_", "davis", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.06,
                "loop": False,
            },
            "attack_1": {
                "files": _prefixed_animation_files("attack_1_", "davis", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_2": {
                "files": _prefixed_animation_files("attack_2_", "davis", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_3": {
                "files": _prefixed_animation_files("attack_3_", "davis", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "heavy_attack": {
                "files": _prefixed_animation_files("sp_1_", "davis", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_1": {
                "files": _prefixed_animation_files("sp_1_", "davis", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_1_follow": {
                "files": _prefixed_animation_files("sp_2_", "davis", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_2": {
                "files": _animation_files("davis", "actions", "sp_move_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_1": {
                "files": _animation_files("davis", "actions", "sp_vert_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_2": {
                "files": _animation_files("davis", "actions", "sp_vert_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sprint_punch": {
                "files": _animation_files("davis", "movement", "sprint_basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": _animation_files("davis", "hold_item", "throw_item", "ground_throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "throw_heavy": {
                "files": _animation_files("davis", "hold_item", "heavy_carry", "throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "grapple": {
                "files": _animation_files("davis", "actions", "grapple_actions", "grappling"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": _animation_files("davis", "actions", "grapple_actions", "grappled"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": _animation_files("davis", "actions", "grapple_actions", "grappled", "hit_grappled"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": _animation_files("davis", "hurt", "died"),
                "frame_duration": 0.12,
                "loop": False,
            },
        },
        "movement": {
            "walk_speed": 220.0,
            "run_speed": 380.0,
            "lane_speed": 150.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
        "combat": {
            "attack_duration": 0.32,
        },
        "basic_attack_cycle": ["attack_1", "attack_2", "attack_3"],
    },
    "denis": {
        "display_name": "Denis",
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
                "files": _animation_files("denis", "idle"),
                "frame_duration": 0.12,
                "loop": True,
            },
            "walk": {
                "files": _animation_files("denis", "movement", "walking"),
                "frame_duration": 0.09,
                "loop": True,
            },
            "run": {
                "files": _animation_files("denis", "movement", "sprinting"),
                "frame_duration": 0.07,
                "loop": True,
            },
            "lift_heavy": {
                "files": _animation_files("denis", "hold_item", "heavy_carry", "walk"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "fall": {
                "files": _animation_files("denis", "fall", "knocked_down", "basic"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "knocked_fire": {
                "files": _animation_files("denis", "fall", "knocked_down", "fire"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "knocked_freeze": {
                "files": _animation_files("denis", "fall", "knocked_down", "ice", "freeze"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "knocked_freeze_break": {
                "files": _animation_files("denis", "fall", "knocked_down", "ice", "freeze_break"),
                "frame_duration": 0.16,
                "loop": False,
            },
            "get_up": {
                "files": _animation_files("denis", "fall", "get_up"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_normal": {
                "files": _animation_files("denis", "movement", "jump_actions", "basic_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": _animation_files("denis", "movement", "jump_actions", "second_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_attack": {
                "files": _animation_files("denis", "actions", "jump_attack"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "drink": {
                "files": _animation_files("denis", "hold_item", "drink"),
                "frame_duration": 0.08,
                "loop": True,
            },
            "hurt": {
                "files": _animation_files("denis", "hurt", "basic_hurt"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "block": {
                "files": _animation_files("denis", "actions", "defend_actions", "defend"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": _animation_files("denis", "actions", "defend_actions", "defend_break"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": _animation_files("denis", "actions", "defend_actions", "dodge"),
                "frame_duration": 0.06,
                "loop": False,
            },
            "attack_1": {
                "files": _prefixed_animation_files("1_", "denis", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_2": {
                "files": _prefixed_animation_files("2_", "denis", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "attack_3": {
                "files": _prefixed_animation_files("3_", "denis", "actions", "basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "heavy_attack": {
                "files": _animation_files("denis", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_1": {
                "files": _animation_files("denis", "actions", "sp_move_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_move_attack_2": {
                "files": _animation_files("denis", "actions", "sp_move_attack_2"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_1": {
                "files": _animation_files("denis", "actions", "sp_vert_attack_1"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "sp_vert_attack_2": {
                "files": _animation_files("denis", "actions", "sp_vert_attack_2"),
                "frame_duration": 0.05,
                "loop": False,
            },
            "sprint_punch": {
                "files": _animation_files("denis", "movement", "sprint_basic_attack"),
                "frame_duration": 0.07,
                "loop": False,
            },
            "throw": {
                "files": _animation_files("denis", "hold_item", "throw_item", "ground_throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "throw_heavy": {
                "files": _animation_files("denis", "hold_item", "heavy_carry", "throw"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "grapple": {
                "files": _animation_files("denis", "actions", "grapple_actions", "grappling"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": _animation_files("denis", "actions", "grapple_actions", "grappled"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "grapple_hit": {
                "files": _animation_files("denis", "actions", "grapple_actions", "grappled", "hit_grappled"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": _animation_files("denis", "hurt", "died"),
                "frame_duration": 0.12,
                "loop": False,
            },
        },
        "movement": {
            "walk_speed": 220.0,
            "run_speed": 380.0,
            "lane_speed": 150.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
        "combat": {
            "attack_duration": 0.30,
        },
        "basic_attack_cycle": ["attack_1", "attack_2", "attack_3"],
    },
    "dummy": {
        "display_name": "Dummy",
        "scale": 2,
        "shadow_size": (56, 18),
        "stats": {
            "max_health": 9999,
            "max_mana": 20,
            "touch_damage": 0,
            "hitbox": (92, 160),
        },
        "animations": {
            "idle": {
                "files": _animation_files("_blank_char", "idle"),
                "frame_duration": 0.18,
                "loop": True,
            },
            "walk": {
                "files": _animation_files("_blank_char", "movement", "walking"),
                "frame_duration": 0.12,
                "loop": True,
            },
            "run": {
                "files": _animation_files("_blank_char", "movement", "sprinting"),
                "frame_duration": 0.10,
                "loop": True,
            },
            "fall": {
                "files": _animation_files("_blank_char", "fall", "knocked_down", "basic"),
                "frame_duration": 0.10,
                "loop": False,
            },
            "get_up": {
                "files": _animation_files("_blank_char", "fall", "get_up"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "hurt": {
                "files": _animation_files("_blank_char", "hurt", "basic_hurt"),
                "frame_duration": 0.08,
                "loop": False,
            },
            "jump_normal": {
                "files": _animation_files("_blank_char", "movement", "jump_actions", "basic_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_second": {
                "files": _animation_files("_blank_char", "movement", "jump_actions", "second_jump"),
                "frame_duration": 0.12,
                "loop": False,
            },
        },
        "movement": {
            "walk_speed": 0.0,
            "run_speed": 0.0,
            "lane_speed": 0.0,
            "jump_velocity": -520.0,
            "gravity": 1200.0,
        },
        "combat": {
            "attack_duration": 0.18,
        },
        "basic_attack_cycle": ["idle"],
    },
}
