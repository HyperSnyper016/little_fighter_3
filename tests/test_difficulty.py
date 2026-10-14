import unittest

from game.data.difficulty import (
    DEFAULT_DIFFICULTY,
    DIFFICULTY_PROFILES,
    get_difficulty_profile,
)
from game.scenes.battle_scene import BanditBrain
from game.scenes.main_menu_scene import MainMenuScene


class DifficultyProfileTests(unittest.TestCase):
    def test_difficulty_profiles_scale_enemy_health_and_ai(self) -> None:
        self.assertEqual(DEFAULT_DIFFICULTY, "Medium")
        self.assertEqual(tuple(DIFFICULTY_PROFILES), ("Easy", "Medium", "Hard"))
        self.assertEqual(
            [
                get_difficulty_profile(name).scale_enemy_health(5)
                for name in DIFFICULTY_PROFILES
            ],
            [4, 5, 6],
        )
        self.assertGreater(
            get_difficulty_profile("Easy").enemy_attack_cooldown_multiplier,
            get_difficulty_profile("Medium").enemy_attack_cooldown_multiplier,
        )
        self.assertLess(
            get_difficulty_profile("Hard").enemy_attack_cooldown_multiplier,
            get_difficulty_profile("Medium").enemy_attack_cooldown_multiplier,
        )
        self.assertLess(
            get_difficulty_profile("Easy").enemy_block_chance_multiplier,
            get_difficulty_profile("Medium").enemy_block_chance_multiplier,
        )
        self.assertGreater(
            get_difficulty_profile("Hard").enemy_block_chance_multiplier,
            get_difficulty_profile("Medium").enemy_block_chance_multiplier,
        )

    def test_invalid_difficulty_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            get_difficulty_profile("Impossible")

    def test_menu_cycles_difficulty_in_both_directions(self) -> None:
        menu = MainMenuScene.__new__(MainMenuScene)
        menu.difficulty = "Medium"

        menu._cycle_difficulty(-1)
        self.assertEqual(menu.difficulty, "Easy")
        menu._cycle_difficulty(1)
        self.assertEqual(menu.difficulty, "Medium")
        menu._cycle_difficulty(1)
        self.assertEqual(menu.difficulty, "Hard")

    def test_enemy_brain_uses_selected_difficulty_profile(self) -> None:
        profile = get_difficulty_profile("Easy")
        brain = BanditBrain(profile)

        self.assertIs(brain.difficulty, profile)


if __name__ == "__main__":
    unittest.main()
