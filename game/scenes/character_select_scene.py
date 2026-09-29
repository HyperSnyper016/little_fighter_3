from __future__ import annotations

import math
from pathlib import Path

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR
from game.data.characters import CHARACTERS

GRID_COLUMNS = 6
VISIBLE_ROWS = 5
GRID_X = 50
GRID_Y = 176
CARD_WIDTH = 164
CARD_HEIGHT = 150
CARD_GAP_X = 12
CARD_GAP_Y = 12
THUMBNAIL_SIZE = (108, 108)
PROFILE_SIZE = (240, 240)
DETAIL_PANEL = pygame.Rect(1140, 156, 720, 822)
CONFIRM_BUTTON = pygame.Rect(1330, 840, 340, 76)
DOUBLE_CLICK_INTERVAL = 0.35


class CharacterSelectScene:
    def __init__(
        self,
        sprites_root: Path,
        confirm_already_pressed: bool = False,
        stage_mode: bool = False,
        test_mode: bool = False,
        opponent_selection: bool = False,
        player_character: str | None = None,
        toggle_already_pressed: bool = False,
    ) -> None:
        self.title_font = pygame.font.Font(None, 58)
        self.name_font = pygame.font.Font(None, 48)
        self.card_name_font = pygame.font.Font(None, 23)
        self.prompt_font = pygame.font.Font(None, 26)
        self.panel_heading_font = pygame.font.Font(None, 30)
        self.button_font = pygame.font.Font(None, 32)
        self.sprites_root = sprites_root
        self.stage_mode = stage_mode
        self.test_mode = test_mode
        self.opponent_selection = opponent_selection
        self.player_character = player_character
        self.characters = self._discover_characters()
        self.selected_index = 0
        self.scroll_row = 0
        self.selection_confirmed = False
        self.selected_character = self.characters[0]["key"] if self.characters else None
        self.selected_opponents: set[str] = set()
        self._up_pressed = False
        self._down_pressed = False
        self._left_pressed = False
        self._right_pressed = False
        self._confirm_pressed = confirm_already_pressed
        self._toggle_pressed = toggle_already_pressed
        self._elapsed_time = 0.0
        self._last_clicked_character: str | None = None
        self._last_click_time = 0.0

    def _discover_characters(self) -> list[dict]:
        characters: list[dict] = []
        if not self.sprites_root.exists():
            return characters

        for directory in sorted(path for path in self.sprites_root.iterdir() if path.is_dir()):
            character_key = directory.name.lower()
            if directory.name.startswith("_") or character_key not in CHARACTERS:
                continue
            profile_path = self._resolve_profile_path(directory)
            if profile_path is None:
                continue

            profile = pygame.image.load(str(profile_path)).convert()
            profile.set_colorkey((0, 0, 0))
            profile = pygame.transform.smoothscale(profile, PROFILE_SIZE)
            characters.append(
                {
                    "key": character_key,
                    "display_name": CHARACTERS[character_key]["display_name"],
                    "profile": profile,
                    "thumbnail": pygame.transform.smoothscale(profile, THUMBNAIL_SIZE),
                }
            )
        return characters

    def _resolve_profile_path(self, directory: Path) -> Path | None:
        preferred_names = (
            f"{directory.name}.bmp",
            f"{directory.name}.png",
            f"{directory.name}_profile.bmp",
            f"{directory.name}_profile.png",
            f"{directory.name.capitalize()}.bmp",
            f"{directory.name.capitalize()}.png",
        )

        for filename in preferred_names:
            candidate = directory / filename
            if candidate.exists():
                return candidate

        fallback_profiles = sorted(
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() in {".bmp", ".png"}
            and "profile" in path.stem.lower()
        )
        if fallback_profiles:
            return fallback_profiles[0]

        fallback_frames = sorted(
            path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in {".bmp", ".png"}
        )
        if fallback_frames:
            return fallback_frames[0]

        nested_frames = sorted(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in {".bmp", ".png"}
        )
        if nested_frames:
            return nested_frames[0]

        return None

    def _card_rect(self, index: int) -> pygame.Rect:
        row = index // GRID_COLUMNS - self.scroll_row
        column = index % GRID_COLUMNS
        return pygame.Rect(
            GRID_X + column * (CARD_WIDTH + CARD_GAP_X),
            GRID_Y + row * (CARD_HEIGHT + CARD_GAP_Y),
            CARD_WIDTH,
            CARD_HEIGHT,
        )

    def _ensure_selected_visible(self) -> None:
        if not self.characters:
            return
        selected_row = self.selected_index // GRID_COLUMNS
        max_scroll_row = max(0, math.ceil(len(self.characters) / GRID_COLUMNS) - VISIBLE_ROWS)
        self.scroll_row = max(0, min(selected_row - VISIBLE_ROWS + 1, max_scroll_row))

    def _move_vertical(self, direction: int) -> None:
        row_count = math.ceil(len(self.characters) / GRID_COLUMNS)
        row = self.selected_index // GRID_COLUMNS
        column = self.selected_index % GRID_COLUMNS
        row = (row + direction) % row_count
        row_start = row * GRID_COLUMNS
        self.selected_index = min(row_start + column, len(self.characters) - 1)

    def update(
        self,
        dt: float,
        mouse_pos: tuple[int, int] | None = None,
        mouse_click: tuple[int, int] | None = None,
    ) -> None:
        self._elapsed_time += dt
        keys = pygame.key.get_pressed()
        up_pressed = keys[pygame.K_UP]
        down_pressed = keys[pygame.K_DOWN]
        left_pressed = keys[pygame.K_LEFT]
        right_pressed = keys[pygame.K_RIGHT]
        confirm_pressed = keys[pygame.K_j] or keys[pygame.K_RETURN] or keys[pygame.K_KP_ENTER]
        toggle_pressed = keys[pygame.K_SPACE]

        if self.characters:
            visible_start = self.scroll_row * GRID_COLUMNS
            visible_end = min(len(self.characters), visible_start + GRID_COLUMNS * VISIBLE_ROWS)
            if mouse_pos is not None:
                for index in range(visible_start, visible_end):
                    if self._card_rect(index).collidepoint(mouse_pos):
                        self.selected_index = index
                        break

            if up_pressed and not self._up_pressed:
                self._move_vertical(-1)
            elif down_pressed and not self._down_pressed:
                self._move_vertical(1)
            elif left_pressed and not self._left_pressed:
                self.selected_index = (self.selected_index - 1) % len(self.characters)
            elif right_pressed and not self._right_pressed:
                self.selected_index = (self.selected_index + 1) % len(self.characters)

            self._ensure_selected_visible()
            self.selected_character = self.characters[self.selected_index]["key"]

            if mouse_click is not None:
                if self.opponent_selection and CONFIRM_BUTTON.collidepoint(mouse_click):
                    self.selection_confirmed = bool(self.selected_opponents)
                elif CONFIRM_BUTTON.collidepoint(mouse_click):
                    self.selection_confirmed = True
                else:
                    for index in range(visible_start, visible_end):
                        if self._card_rect(index).collidepoint(mouse_click):
                            self.selected_index = index
                            self.selected_character = self.characters[index]["key"]
                            if self.opponent_selection:
                                self._toggle_opponent(self.selected_character)
                            elif (
                                self._last_clicked_character == self.selected_character
                                and self._elapsed_time - self._last_click_time <= DOUBLE_CLICK_INTERVAL
                            ):
                                self.selection_confirmed = True
                            else:
                                self._last_clicked_character = self.selected_character
                                self._last_click_time = self._elapsed_time
                            break

            if confirm_pressed and not self._confirm_pressed:
                if self.opponent_selection:
                    self.selection_confirmed = bool(self.selected_opponents)
                else:
                    self.selection_confirmed = True
            if self.opponent_selection and toggle_pressed and not self._toggle_pressed:
                self._toggle_opponent(self.selected_character)

        self._up_pressed = up_pressed
        self._down_pressed = down_pressed
        self._left_pressed = left_pressed
        self._right_pressed = right_pressed
        self._confirm_pressed = confirm_pressed
        self._toggle_pressed = toggle_pressed

    def _toggle_opponent(self, character: str | None) -> None:
        if character is None:
            return
        if character in self.selected_opponents:
            self.selected_opponents.remove(character)
        else:
            self.selected_opponents.add(character)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((18, 23, 32))
        if self.opponent_selection:
            title_text = "CHOOSE YOUR OPPONENTS"
            prompt_text = "Select one or more opponents, then start the battle"
        else:
            if self.stage_mode:
                title_text = "STAGE MODE - CHOOSE YOUR FIGHTER"
            elif self.test_mode:
                title_text = "TEST MODE - CHOOSE YOUR FIGHTER"
            else:
                title_text = "CHOOSE YOUR FIGHTER"
            prompt_text = "Select a portrait, then confirm or double-click to start"
        title = self.title_font.render(title_text, True, TEXT_COLOR)
        prompt = self.prompt_font.render(prompt_text, True, (174, 188, 204))
        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 64)))
        surface.blit(prompt, prompt.get_rect(center=(SCREEN_WIDTH // 2, 112)))

        if not self.characters:
            empty = self.prompt_font.render(
                "No playable characters found in assets\\sprites\\characters",
                True,
                TEXT_COLOR,
            )
            surface.blit(empty, empty.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
            return

        visible_start = self.scroll_row * GRID_COLUMNS
        visible_end = min(len(self.characters), visible_start + GRID_COLUMNS * VISIBLE_ROWS)
        for index in range(visible_start, visible_end):
            character = self.characters[index]
            card = self._card_rect(index)
            selected = index == self.selected_index
            chosen_opponent = character["key"] in self.selected_opponents
            card_color = (47, 75, 66) if chosen_opponent else (47, 59, 75) if selected else (29, 37, 49)
            outline_color = (111, 211, 150) if chosen_opponent else (255, 190, 92) if selected else (69, 84, 102)
            pygame.draw.rect(surface, card_color, card, border_radius=10)
            pygame.draw.rect(
                surface,
                outline_color,
                card,
                width=3 if selected or chosen_opponent else 1,
                border_radius=10,
            )
            thumbnail = character["thumbnail"]
            surface.blit(thumbnail, thumbnail.get_rect(midtop=(card.centerx, card.top + 5)))
            label = self.card_name_font.render(character["display_name"], True, TEXT_COLOR)
            surface.blit(label, label.get_rect(center=(card.centerx, card.bottom - 16)))

        pygame.draw.rect(surface, (27, 35, 47), DETAIL_PANEL, border_radius=16)
        pygame.draw.rect(surface, (70, 88, 109), DETAIL_PANEL, width=2, border_radius=16)
        heading_text = "CHOOSE OPPONENTS" if self.opponent_selection else "SELECTED FIGHTER"
        heading = self.panel_heading_font.render(heading_text, True, (174, 188, 204))
        surface.blit(heading, heading.get_rect(center=(DETAIL_PANEL.centerx, DETAIL_PANEL.top + 48)))

        selected = self.characters[self.selected_index]
        profile = selected["profile"]
        surface.blit(profile, profile.get_rect(center=(DETAIL_PANEL.centerx, DETAIL_PANEL.top + 250)))
        name = self.name_font.render(selected["display_name"], True, TEXT_COLOR)
        surface.blit(name, name.get_rect(center=(DETAIL_PANEL.centerx, DETAIL_PANEL.top + 420)))

        pygame.draw.rect(surface, (58, 119, 150), CONFIRM_BUTTON, border_radius=12)
        pygame.draw.rect(surface, (126, 197, 224), CONFIRM_BUTTON, width=2, border_radius=12)
        if self.opponent_selection:
            button_text = "START BATTLE"
        elif self.test_mode:
            button_text = "START TEST"
        else:
            button_text = "CONFIRM / START"
        confirm = self.button_font.render(button_text, True, (255, 255, 255))
        surface.blit(confirm, confirm.get_rect(center=CONFIRM_BUTTON.center))
        if self.opponent_selection:
            controls_text = f"{len(self.selected_opponents)} selected  |  Space/click: toggle  |  Enter/J: start"
        else:
            controls_text = "Arrows to choose  |  Enter or J to start"
        controls = self.prompt_font.render(controls_text, True, (174, 188, 204))
        surface.blit(controls, controls.get_rect(center=(DETAIL_PANEL.centerx, CONFIRM_BUTTON.bottom + 36)))
