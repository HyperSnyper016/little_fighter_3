import unittest
from pathlib import Path

import pygame

from game.systems.assets import _key_near_black_background


class NearBlackBackgroundTests(unittest.TestCase):
    def test_keys_edge_connected_near_black_without_erasing_dark_art(self) -> None:
        surface = pygame.Surface((5, 5))
        surface.fill((0, 0, 0))
        surface.set_at((0, 2), (20, 20, 20))
        surface.set_at((1, 2), (35, 34, 34))
        for y in range(1, 4):
            for x in range(2, 5):
                surface.set_at((x, y), (52, 28, 4))
        surface.set_at((3, 2), (20, 20, 20))

        _key_near_black_background(surface, 40)

        self.assertEqual(surface.get_at((0, 2))[:3], (0, 0, 0))
        self.assertEqual(surface.get_at((1, 2))[:3], (0, 0, 0))
        self.assertEqual(surface.get_at((2, 2))[:3], (52, 28, 4))
        self.assertEqual(surface.get_at((3, 2))[:3], (20, 20, 20))

    def test_blue_sparkle_frames_have_clean_colorkey_backgrounds(self) -> None:
        asset_root = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "sprites"
            / "particals"
            / "blue_sparkles"
        )
        for image_path in sorted(asset_root.glob("*.png")):
            with self.subTest(image=image_path.name):
                image = pygame.image.load(str(image_path))
                for y in range(image.get_height()):
                    for x in range(image.get_width()):
                        red, green, blue = image.get_at((x, y))[:3]
                        if (red, green, blue) != (0, 0, 0):
                            self.assertGreater(max(red, green, blue), 40)


if __name__ == "__main__":
    unittest.main()
