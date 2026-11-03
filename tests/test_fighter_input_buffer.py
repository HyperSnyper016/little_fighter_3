import unittest

import pygame

from game.data.characters import CHARACTERS
from game.entities.fighter import Fighter, FighterConfig, FighterInput


class FighterInputBufferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.display.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def _fighter_recovering_from_attack(self) -> Fighter:
        fighter = Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (120.0, 40.0))
        fighter._start_attack_state("basic_attack")
        fighter.animation_player.play(fighter.attack_animation)
        fighter.attack_timer = 0.10
        return fighter

    def _finish_attack_recovery(self, fighter: Fighter) -> None:
        fighter.attack_timer = 0.0
        fighter.animation_player.finished = True
        fighter.update(0.01, FighterInput())

    def test_attack_pressed_during_recovery_starts_once_when_legal(self) -> None:
        fighter = self._fighter_recovering_from_attack()

        fighter.update(0.01, FighterInput(attack_just_pressed=True))
        self.assertEqual(fighter.state, "basic_attack")
        self.assertGreater(fighter.attack_input_buffer_timer, 0.0)

        self._finish_attack_recovery(fighter)

        self.assertEqual(fighter.state, "basic_attack")
        self.assertAlmostEqual(
            fighter.attack_timer,
            fighter.basic_attack_timing.total_duration,
        )
        self.assertEqual(fighter.attack_input_buffer_timer, 0.0)

        fighter.state = "idle"
        fighter.attack_timer = 0.0
        fighter.animation_player.finished = True
        fighter.update(0.01, FighterInput())
        self.assertEqual(fighter.state, "idle")

    def test_jump_pressed_during_recovery_starts_when_legal(self) -> None:
        fighter = self._fighter_recovering_from_attack()

        fighter.update(0.01, FighterInput(jump_just_pressed=True))
        self.assertEqual(fighter.state, "basic_attack")
        self.assertGreater(fighter.jump_input_buffer_timer, 0.0)

        self._finish_attack_recovery(fighter)

        self.assertEqual(fighter.state, "jump_throw")
        self.assertEqual(fighter.jump_stage, 1)
        self.assertEqual(fighter.jump_input_buffer_timer, 0.0)

    def test_attack_input_expires_if_recovery_last_too_long(self) -> None:
        fighter = self._fighter_recovering_from_attack()

        fighter.update(0.01, FighterInput(attack_just_pressed=True))
        fighter.update(0.13, FighterInput())
        self.assertEqual(fighter.attack_input_buffer_timer, 0.0)

        fighter.state = "idle"
        fighter.attack_timer = 0.0
        fighter.animation_player.finished = True
        fighter.update(0.01, FighterInput())
        self.assertEqual(fighter.state, "idle")


if __name__ == "__main__":
    unittest.main()
