from __future__ import annotations

from pathlib import Path

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR
from game.systems.stage import STAGE_CONFIGS
from game.systems.keybindings import KEY_BINDINGS


class MapSelectScene:
    PREVIEW_SIZE = (640, 360)
    CARD_SIZE = (700, 500)
    CARD_TOP = 210
    CARD_GAP = 60
    CONFIRM_BUTTON = pygame.Rect(1010, 830, 300, 72)
    BACK_BUTTON = pygame.Rect(610, 830, 300, 72)

    def __init__(
        self,
        player_character: str,
        *,
        test_mode: bool = False,
        confirm_already_pressed: bool = False,
    ) -> None:
        self.player_character = player_character
        self.test_mode = test_mode
        self.map_names = tuple(STAGE_CONFIGS)
        self.preview_size = self.PREVIEW_SIZE if len(self.map_names) <= 2 else (520, 293)
        self.selected_index = 0
        self.selected_map = self.map_names[self.selected_index]
        self.selection_confirmed = False
        self.back_requested = False
        self.title_font = pygame.font.Font(None, 64)
        self.map_font = pygame.font.Font(None, 44)
        self.prompt_font = pygame.font.Font(None, 26)
        self.button_font = pygame.font.Font(None, 34)
        self._left_pressed = False
        self._right_pressed = False
        self._confirm_pressed = confirm_already_pressed
        self._escape_pressed = False
        self.previews = self._load_previews()

    def _load_previews(self) -> dict[str, pygame.Surface]:
        maps_root = Path(__file__).resolve().parents[2] / "assets" / "maps"
        previews = {}
        for map_name, (directory, stage_type) in STAGE_CONFIGS.items():
            stage = stage_type(maps_root / directory)
            full_size = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            stage.draw(full_size, stage.world_width / 2)
            previews[map_name] = pygame.transform.smoothscale(full_size, self.preview_size)
        return previews

    def _card_rect(self, index: int) -> pygame.Rect:
        card_size = self.CARD_SIZE if len(self.map_names) <= 2 else (560, 440)
        card_gap = self.CARD_GAP if len(self.map_names) <= 2 else 30
        total_width = len(self.map_names) * card_size[0] + (len(self.map_names) - 1) * card_gap
        left = (SCREEN_WIDTH - total_width) // 2
        return pygame.Rect(
            left + index * (card_size[0] + card_gap),
            self.CARD_TOP,
            *card_size,
        )

    def _select_map(self, index: int) -> None:
        self.selected_index = index % len(self.map_names)
        self.selected_map = self.map_names[self.selected_index]

    def update(
        self,
        dt: float,
        mouse_pos: tuple[int, int] | None = None,
        mouse_click: tuple[int, int] | None = None,
    ) -> None:
        keys = pygame.key.get_pressed()
        left_pressed = KEY_BINDINGS.is_pressed("move_left", keys)
        right_pressed = KEY_BINDINGS.is_pressed("move_right", keys)
        confirm_pressed = KEY_BINDINGS.is_pressed("menu_confirm", keys)
        escape_pressed = KEY_BINDINGS.is_pressed("back_pause", keys)

        if left_pressed and not self._left_pressed:
            self._select_map(self.selected_index - 1)
        elif right_pressed and not self._right_pressed:
            self._select_map(self.selected_index + 1)

        if mouse_pos is not None:
            for index in range(len(self.map_names)):
                if self._card_rect(index).collidepoint(mouse_pos):
                    self._select_map(index)
                    break

        if mouse_click is not None:
            if self.CONFIRM_BUTTON.collidepoint(mouse_click):
                self.selection_confirmed = True
            elif self.BACK_BUTTON.collidepoint(mouse_click):
                self.back_requested = True
            else:
                for index in range(len(self.map_names)):
                    if self._card_rect(index).collidepoint(mouse_click):
                        self._select_map(index)
                        break
        elif confirm_pressed and not self._confirm_pressed:
            self.selection_confirmed = True
        elif escape_pressed and not self._escape_pressed:
            self.back_requested = True

        self._left_pressed = left_pressed
        self._right_pressed = right_pressed
        self._confirm_pressed = confirm_pressed
        self._escape_pressed = escape_pressed

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((18, 23, 32))
        title = self.title_font.render("CHOOSE A MAP", True, TEXT_COLOR)
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 80)))
        mode_text = "TEST MODE" if self.test_mode else "PLAY MODE"
        subtitle = self.prompt_font.render(
            f"{mode_text} - choose the arena for {self.player_character.replace('_', ' ').title()}",
            True,
            (174, 188, 204),
        )
        surface.blit(subtitle, subtitle.get_rect(center=(SCREEN_WIDTH // 2, 135)))

        for index, map_name in enumerate(self.map_names):
            card = self._card_rect(index)
            selected = index == self.selected_index
            pygame.draw.rect(surface, (35, 45, 59), card, border_radius=12)
            pygame.draw.rect(
                surface,
                (255, 190, 92) if selected else (69, 84, 102),
                card,
                width=4 if selected else 2,
                border_radius=12,
            )
            preview = self.previews[map_name]
            preview_rect = preview.get_rect(midtop=(card.centerx, card.top + 24))
            surface.blit(preview, preview_rect)
            label = self.map_font.render(map_name, True, TEXT_COLOR)
            surface.blit(label, label.get_rect(center=(card.centerx, card.bottom - 80)))

        pygame.draw.rect(surface, (58, 119, 150), self.BACK_BUTTON, border_radius=10)
        pygame.draw.rect(surface, (126, 197, 224), self.BACK_BUTTON, width=2, border_radius=10)
        back = self.button_font.render("BACK", True, (255, 255, 255))
        surface.blit(back, back.get_rect(center=self.BACK_BUTTON.center))
        pygame.draw.rect(surface, (58, 119, 150), self.CONFIRM_BUTTON, border_radius=10)
        pygame.draw.rect(surface, (126, 197, 224), self.CONFIRM_BUTTON, width=2, border_radius=10)
        confirm = self.button_font.render("CONTINUE", True, (255, 255, 255))
        surface.blit(confirm, confirm.get_rect(center=self.CONFIRM_BUTTON.center))

        controls = self.prompt_font.render(
            f"{KEY_BINDINGS.label('move_left')}/{KEY_BINDINGS.label('move_right')}: choose map   "
            f"{KEY_BINDINGS.label('menu_confirm')}: continue   {KEY_BINDINGS.label('back_pause')}: back",
            True,
            (174, 188, 204),
        )
        surface.blit(controls, controls.get_rect(center=(SCREEN_WIDTH // 2, self.CONFIRM_BUTTON.bottom + 44)))
