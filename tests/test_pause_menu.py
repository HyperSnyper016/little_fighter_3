import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from game.data.stage_progression import StageProgression
from game.scenes.battle_scene import (
    PAUSE_CARD_HOVER_SIZE,
    PAUSE_CARD_SIZE,
    BattleScene,
    _pause_card_surface,
)


class PauseMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.font.init()

    def make_scene(self, card_ranks: dict[str, int]) -> BattleScene:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_card_ranks = card_ranks
        scene.stage_progression = StageProgression(140)
        scene.small_font = pygame.font.Font(None, 24)
        scene.pause_font = pygame.font.Font(None, 54)
        scene.stage_subtitle_font = pygame.font.Font(None, 30)
        scene.fighter = SimpleNamespace(
            definition={"display_name": "Bandit"},
            health=18,
            max_health=22,
            mana=14,
            max_mana=20,
            movement={"walk_speed": 220.0, "run_speed": 380.0},
        )
        return scene

    def test_pause_fan_includes_owned_cards_and_hover_pulls_card_forward(self) -> None:
        ranks = {"heavy_hands": 1, "iron_skin": 1, "quick_step": 1}
        scene = self.make_scene(ranks)
        plain_scene = self.make_scene(ranks)
        plain = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        hovered = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        plain.fill((1, 2, 3))
        hovered.fill((1, 2, 3))
        normal_card = _pause_card_surface("vitality", 2, *PAUSE_CARD_SIZE)
        foreground_card = _pause_card_surface(
            "vitality",
            2,
            *PAUSE_CARD_HOVER_SIZE,
        )

        scene._update_pause_card_hover(0.016, (495, 700))
        self.assertEqual(scene._pause_card_hover_progress["iron_skin"], 0.0)
        scene._update_pause_card_hover(0.055, (495, 700))
        self.assertGreater(scene._pause_card_hover_progress["iron_skin"], 0.0)
        self.assertLess(scene._pause_card_hover_progress["iron_skin"], 1.0)
        self.assertIsNone(plain_scene._draw_pause_card_fan(plain, (-10, -10)))
        self.assertEqual(scene._draw_pause_card_fan(hovered, (495, 700)), "iron_skin")
        scene._update_pause_card_hover(0.18, (495, 700))
        self.assertEqual(scene._pause_card_hover_progress["iron_skin"], 1.0)
        self.assertGreater(foreground_card.get_width(), normal_card.get_width() * 1.4)
        self.assertNotEqual(
            pygame.image.tobytes(plain, "RGB"),
            pygame.image.tobytes(hovered, "RGB"),
        )

    def test_pause_menu_renders_stats_and_empty_card_collection(self) -> None:
        scene = self.make_scene({})
        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surface.fill((30, 40, 50))

        with patch("pygame.mouse.get_pos", return_value=(-10, -10)):
            scene._draw_pause_menu(surface)

        self.assertNotEqual(surface.get_at((100, 160))[:3], (30, 40, 50))
        self.assertNotEqual(surface.get_at((1_050, 160))[:3], (30, 40, 50))
        self.assertNotEqual(surface.get_at((SCREEN_WIDTH // 2, SCREEN_HEIGHT - 74))[:3], (30, 40, 50))


if __name__ == "__main__":
    unittest.main()
