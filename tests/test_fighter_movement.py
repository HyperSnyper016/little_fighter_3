import math
import unittest

import pygame

from game.data.characters import CHARACTERS
from game.entities.fighter import Fighter, FighterConfig, FighterInput


class FighterMovementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.display.init()
        pygame.font.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def _fighter(self, name: str = "bandit") -> Fighter:
        return Fighter(FighterConfig(name, CHARACTERS[name]), (120.0, 180.0))

    def test_diagonal_walk_is_normalized_without_erasing_archetype_speeds(self) -> None:
        measured_speeds = {}
        for name in ("bandit", "template"):
            with self.subTest(name=name):
                fighter = self._fighter(name)
                start_x, start_lane = fighter.x, fighter.lane_y

                fighter.update(0.1, FighterInput(right=True, up=True))

                horizontal_velocity = (fighter.x - start_x) / 0.1
                lane_velocity = (fighter.lane_y - start_lane) / 0.1
                measured_speeds[name] = math.hypot(horizontal_velocity, lane_velocity)
                self.assertGreater(horizontal_velocity, 0.0)
                self.assertLess(lane_velocity, 0.0)
                self.assertAlmostEqual(
                    measured_speeds[name],
                    fighter.movement["walk_speed"],
                )

        self.assertLess(measured_speeds["template"], measured_speeds["bandit"])

    def test_diagonal_run_is_capped_at_run_speed(self) -> None:
        fighter = self._fighter()
        start_x, start_lane = fighter.x, fighter.lane_y

        fighter.update(
            0.1,
            FighterInput(right=True, up=True, run=True),
        )

        horizontal_velocity = (fighter.x - start_x) / 0.1
        lane_velocity = (fighter.lane_y - start_lane) / 0.1
        self.assertAlmostEqual(
            math.hypot(horizontal_velocity, lane_velocity),
            fighter.movement["run_speed"] * 1.25,
        )

    def test_air_diagonal_movement_is_normalized(self) -> None:
        fighter = self._fighter()
        fighter._start_jump()
        start_x, start_lane = fighter.x, fighter.lane_y

        fighter.update(0.1, FighterInput(right=True, up=True))

        horizontal_velocity = (fighter.x - start_x) / 0.1
        lane_velocity = (fighter.lane_y - start_lane) / 0.1
        self.assertAlmostEqual(
            math.hypot(horizontal_velocity, lane_velocity),
            fighter.movement["walk_speed"],
        )

    def test_ground_movement_starts_and_stops_immediately(self) -> None:
        fighter = self._fighter()
        start_x = fighter.x

        fighter.update(0.1, FighterInput(right=True))
        moved_x = fighter.x
        self.assertAlmostEqual(moved_x - start_x, fighter.movement["walk_speed"] * 0.1)

        fighter.update(0.1, FighterInput())
        self.assertEqual(fighter.state, "idle")
        self.assertEqual(fighter.x, moved_x)

        fighter.update(0.1, FighterInput(left=True))
        self.assertAlmostEqual(
            fighter.x,
            moved_x - fighter.movement["walk_speed"] * 0.1,
        )


if __name__ == "__main__":
    unittest.main()
