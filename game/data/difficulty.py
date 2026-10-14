from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DifficultyProfile:
    name: str
    enemy_health_multiplier: float
    enemy_attack_cooldown_multiplier: float
    enemy_block_chance_multiplier: float

    def scale_enemy_health(self, health: int) -> int:
        return max(1, round(health * self.enemy_health_multiplier))


DIFFICULTY_PROFILES = {
    "Easy": DifficultyProfile("Easy", 0.75, 1.5, 0.35),
    "Medium": DifficultyProfile("Medium", 1.0, 1.0, 1.0),
    "Hard": DifficultyProfile("Hard", 1.25, 0.75, 1.3),
}
DEFAULT_DIFFICULTY = "Medium"


def get_difficulty_profile(name: str) -> DifficultyProfile:
    try:
        return DIFFICULTY_PROFILES[name]
    except KeyError:
        raise ValueError(f"Unknown difficulty: {name}") from None
