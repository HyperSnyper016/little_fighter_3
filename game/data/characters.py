from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


CHARACTERS = {
    "bandit": {
        "display_name": "Bandit",
        "scale": 2,
        "shadow_size": (56, 18),
        "animations": {
            "idle": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "idle" / "bandit_idle_1.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "idle" / "bandit_idle_2.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "idle" / "bandit_idle_3.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "idle" / "bandit_idle_4.bmp",
                ],
                "frame_duration": 0.18,
                "loop": True,
            },
            "walk": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "walk" / "bandit_walk_5.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "walk" / "bandit_walk_6.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "walk" / "bandit_walk_7.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "walk" / "bandit_walk_8.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "walk" / "bandit_walk_9.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "walk" / "bandit_walk_10.bmp",
                ],
                "frame_duration": 0.12,
                "loop": True,
            },
            "run": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "run" / "bandit_0_21.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "run" / "bandit_0_22.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "run" / "bandit_0_23.bmp",
                ],
                "frame_duration": 0.10,
                "loop": True,
            },
            "lift_heavy": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "lift_heavy" / "bandit_0_24.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "lift_heavy" / "bandit_0_25.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "lift_heavy" / "bandit_0_26.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "lift_heavy" / "bandit_0_27.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "lift_heavy" / "bandit_0_28.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "lift_heavy" / "bandit_0_29.bmp",
                ],
                "frame_duration": 0.11,
                "loop": False,
            },
            "knocked": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "knocked" / "bandit_0_31.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "knocked" / "bandit_0_32.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "knocked" / "bandit_0_33.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "knocked" / "bandit_0_34.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "knocked" / "bandit_0_35.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "knocked" / "bandit_0_36.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "knocked" / "bandit_0_37.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "get_up": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "get_up" / "bandit_0_37.bmp",
                ],
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_vertical": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "jump" / "virtically" / "bandit_0_62.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "jump" / "virtically" / "bandit_0_63.bmp",
                ],
                "frame_duration": 0.12,
                "loop": False,
            },
            "jump_forward": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "jump" / "forward" / "bandit_0_62.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "jump" / "forward" / "bandit_0_64.bmp",
                ],
                "frame_duration": 0.12,
                "loop": False,
            },
            "block": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "block" / "bandit_0_57.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "block" / "bandit_0_58.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_break": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "block_break" / "bandit_0_47.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "block_break" / "bandit_0_48.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "block_break" / "bandit_0_49.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "block_dodge": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "block_dodge" / "bandit_0_50.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "block_dodge" / "bandit_0_59.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "block_dodge" / "bandit_0_60.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "block_dodge" / "bandit_0_61.bmp",
                ],
                "frame_duration": 0.08,
                "loop": False,
            },
            "attack_punch": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "attack" / "bandit_punch_1.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "attack" / "bandit_punch_2.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "attack" / "bandit_punch_3.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "attack_kick": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "attack" / "bandit_kick_1.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "attack" / "bandit_kick_2.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "attack" / "bandit_kick_3.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "move_attack": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "move_attack" / "bandit_0_38.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "move_attack" / "bandit_0_39.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "move_attack" / "bandit_0_40.bmp",
                ],
                "frame_duration": 0.09,
                "loop": False,
            },
            "grapple": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "grapple" / "bandit_0_51.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "grapple" / "bandit_0_52.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "grapple" / "bandit_0_53.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "grappled": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "grapple" / "grappled" / "bandit_0_54.bmp",
                ],
                "frame_duration": 0.12,
                "loop": False,
            },
            "grappled_hit": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "grapple" / "grappled_hit" / "bandit_0_55.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "grapple" / "grappled_hit" / "bandit_0_56.bmp",
                ],
                "frame_duration": 0.10,
                "loop": False,
            },
            "die": {
                "files": [
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "die" / "bandit_0_41.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "die" / "bandit_0_42.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "die" / "bandit_0_43.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "die" / "bandit_0_44.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "die" / "bandit_0_45.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "die" / "bandit_0_46.bmp",
                    PROJECT_ROOT / "assets" / "sprites" / "bandit" / "die" / "bandit_0_47.bmp",
                ],
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
        },
    }
}
