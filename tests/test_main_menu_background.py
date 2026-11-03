from pathlib import Path
import unittest

from game.scenes.main_menu_scene import MainMenuScene


class MainMenuBackgroundTests(unittest.TestCase):
    def test_armored_bandit_profile_is_used_instead_of_signature(self) -> None:
        character_directory = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "sprites"
            / "characters"
            / "armored_bandit"
        )
        scene = MainMenuScene.__new__(MainMenuScene)

        self.assertEqual(
            scene._resolve_background_path(character_directory),
            character_directory / "armored_bandit.jpg",
        )


if __name__ == "__main__":
    unittest.main()
