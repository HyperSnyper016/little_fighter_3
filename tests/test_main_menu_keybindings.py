import unittest
from unittest.mock import patch

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from game.scenes.main_menu_scene import MainMenuScene
from game.systems.keybindings import KEY_BINDINGS


class MainMenuKeybindingTests(unittest.TestCase):
    def test_conflict_warning_renders_for_selected_binding(self) -> None:
        pygame.font.init()
        scene = MainMenuScene.__new__(MainMenuScene)
        scene.keybinding_selected_index = 0
        scene.keybinding_notice = ""
        scene.keybinding_scroll = 0
        scene.keybinding_capture = None
        scene.history_hint_font = pygame.font.Font(None, 20)
        scene.history_button_font = pygame.font.Font(None, 24)
        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

        with patch.object(
            KEY_BINDINGS,
            "conflicting_actions",
            side_effect=lambda action: ("move_down",) if action == "move_up" else (),
        ):
            scene._draw_keybindings(surface)


if __name__ == "__main__":
    unittest.main()
