import unittest

import pygame

from game.data.characters import CHARACTERS
from game.entities.fighter import Fighter, FighterConfig
from game.scenes.battle_scene import BattleScene


class DepthLaneTargetingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.display.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    @staticmethod
    def _fighter(x: float, lane_y: float) -> Fighter:
        return Fighter(
            FighterConfig("bandit", CHARACTERS["bandit"]),
            (x, lane_y),
        )

    def _active_attacker(self) -> Fighter:
        attacker = self._fighter(120.0, 40.0)
        attacker.attack_animation = attacker._next_basic_attack_animation()
        attacker._start_attack_state("basic_attack")
        attacker.animation_player.play(attacker.attack_animation)
        attacker.attack_elapsed = attacker.basic_attack_timing.startup_duration
        return attacker

    def _select(self, attacker: Fighter, targets: list[Fighter]) -> Fighter | None:
        timing = attacker.basic_attack_timing
        self.assertIsNotNone(timing)
        return BattleScene._select_melee_target(
            attacker,
            targets,
            BattleScene._melee_attack_rect(attacker),
            timing.lane_tolerance,
        )

    def test_attack_reaches_targets_within_the_lane_tolerance_only(self) -> None:
        attacker = self._active_attacker()
        tolerance = attacker.basic_attack_timing.lane_tolerance
        aligned_target = self._fighter(attacker.x + 24.0, attacker.lane_y + tolerance)
        outside_target = self._fighter(
            attacker.x + 24.0,
            attacker.lane_y + tolerance + 0.1,
        )

        self.assertIs(self._select(attacker, [aligned_target]), aligned_target)
        self.assertIsNone(self._select(attacker, [outside_target]))

    def test_basic_attack_facing_excludes_targets_behind_the_attacker(self) -> None:
        attacker = self._active_attacker()
        behind_target = self._fighter(attacker.x - 15.0, attacker.lane_y)

        self.assertIsNone(self._select(attacker, [behind_target]))

        attacker.facing = -1
        self.assertIs(self._select(attacker, [behind_target]), behind_target)

    def test_crowded_fight_selects_the_closest_valid_opponent_not_list_order(self) -> None:
        attacker = self._active_attacker()
        farther_target = self._fighter(attacker.x + 65.0, attacker.lane_y)
        closer_target = self._fighter(attacker.x + 30.0, attacker.lane_y)

        self.assertIs(
            self._select(attacker, [farther_target, closer_target]),
            closer_target,
        )

    def test_forward_target_is_preferred_over_a_rear_overlap(self) -> None:
        attacker = self._active_attacker()
        rear_target = self._fighter(attacker.x - 5.0, attacker.lane_y)
        forward_target = self._fighter(attacker.x + 28.0, attacker.lane_y)

        self.assertIs(
            self._select(attacker, [rear_target, forward_target]),
            forward_target,
        )


if __name__ == "__main__":
    unittest.main()
