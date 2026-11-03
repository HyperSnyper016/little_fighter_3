from __future__ import annotations

from game.data.campaign import ENDLESS_ENEMY_THREAT


XP_PER_THREAT = 10
DEFAULT_ENEMY_XP = 15


def enemy_xp_reward(character_name: str) -> int:
    """Return an enemy's Stage Mode XP reward based on its campaign threat."""
    threat = ENDLESS_ENEMY_THREAT.get(character_name, DEFAULT_ENEMY_XP / XP_PER_THREAT)
    return max(1, round(threat * XP_PER_THREAT))
