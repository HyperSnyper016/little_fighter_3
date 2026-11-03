from __future__ import annotations

import math


XP_REQUIREMENT_MULTIPLIER = 0.75


class StageProgression:
    """XP and level-up state for a single Stage or Test Mode run."""

    def __init__(self, xp_total: int = 0) -> None:
        self.xp_total = max(0, int(xp_total))
        self.level = 1
        self.level_up_events: list[int] = []
        self.pending_levels: list[int] = []
        while self.xp_total >= self.threshold_for_level(self.level + 1):
            self.level += 1

    @staticmethod
    def threshold_for_level(level: int) -> int:
        """Return 75% of the original cumulative XP requirement for ``level``."""
        if level < 1:
            raise ValueError("Level must be at least 1.")
        levels_gained = level - 1
        original_threshold = (
            100 * levels_gained + 25 * levels_gained * (levels_gained - 1)
        )
        return math.ceil(original_threshold * XP_REQUIREMENT_MULTIPLIER)

    @property
    def xp_into_level(self) -> int:
        return self.xp_total - self.threshold_for_level(self.level)

    @property
    def xp_for_next_level(self) -> int:
        return self.threshold_for_level(self.level + 1) - self.threshold_for_level(self.level)

    def add_xp(self, amount: int) -> list[int]:
        if amount <= 0:
            return []
        self.xp_total += int(amount)
        earned_levels = []
        while self.xp_total >= self.threshold_for_level(self.level + 1):
            self.level += 1
            earned_levels.append(self.level)
            self.level_up_events.append(self.level)
            self.pending_levels.append(self.level)
        return earned_levels

    def consume_pending_level(self) -> int | None:
        if not self.pending_levels:
            return None
        return self.pending_levels.pop(0)
