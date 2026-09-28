from __future__ import annotations

import random
from pathlib import Path

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR
from game.systems.audio import AudioBank


class MainMenuScene:
    MAIN_OPTIONS = ("Play", "Settings", "Quit")

    def __init__(self) -> None:
        self.title_font = pygame.font.Font(None, 72)
        self.option_font = pygame.font.Font(None, 40)
        self.credit_font = pygame.font.Font(None, 24)
        self.start_requested = False
        self.quit_requested = False
        self.settings_open = False
        self.selected_index = 0
        self._up_pressed = False
        self._down_pressed = False
        self._left_pressed = False
        self._right_pressed = False
        self._confirm_pressed = False
        self._escape_pressed = False
        self.sprites_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "characters"
        self.tile_size = (176, 132)
        self.scroll_x = 0.0
        self.scroll_y = 0.0
        self.scroll_speed_x = 11.0
        self.scroll_speed_y = 18.0
        self.grid_seed = random.randrange(1, 1_000_000_000)
        self.background_tiles = self._load_background_tiles()
        self.title_logo = self._load_title_logo()
        sounds_root = Path(__file__).resolve().parents[2] / "assets" / "sounds"
        self.audio = AudioBank(sounds_root)
        self.audio.play("menu_start")

    def _resolve_background_path(self, directory: Path) -> Path | None:
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

        fallback_images = sorted(
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() in {".bmp", ".png"}
        )
        if fallback_images:
            return fallback_images[0]

        return None

    def _load_background_tiles(self) -> list[pygame.Surface]:
        if not self.sprites_root.exists():
            return []

        tiles: list[pygame.Surface] = []
        for directory in sorted(path for path in self.sprites_root.iterdir() if path.is_dir()):
            background_path = self._resolve_background_path(directory)
            if background_path is None:
                continue

            image = pygame.image.load(str(background_path)).convert()
            image.set_colorkey((0, 0, 0))
            tiles.append(pygame.transform.smoothscale(image, self.tile_size))
        return tiles

    def _load_title_logo(self) -> pygame.Surface | None:
        logo_path = Path(__file__).resolve().parents[2] / "assets" / "LF3_logo.jpg"
        if not logo_path.exists():
            return None

        logo = pygame.image.load(str(logo_path)).convert()
        logo.set_colorkey((0, 0, 0))
        width, height = logo.get_size()
        target_width = 980
        target_height = max(1, int(height * (target_width / width)))
        scaled = pygame.transform.smoothscale(logo, (target_width, target_height))
        scaled.set_colorkey((0, 0, 0))
        return scaled

    def _menu_options(self) -> tuple[str, ...]:
        if self.settings_open:
            sound_state = "Off" if AudioBank.muted else "On"
            return (f"Sound: {sound_state}", "Volume", "Back")
        return self.MAIN_OPTIONS

    def _option_rects(self) -> list[pygame.Rect]:
        options = self._menu_options()
        return [
            pygame.Rect(0, 0, 300, 54).move(
                SCREEN_WIDTH // 2 - 150,
                310 + index * 68,
            )
            for index in range(len(options))
        ]

    def _activate_selected(self) -> None:
        self.audio.play("menu_accept")
        if self.settings_open:
            if self.selected_index == 0:
                AudioBank.set_muted(not AudioBank.muted)
            elif self.selected_index == 1:
                AudioBank.set_master_volume(AudioBank.master_volume + 0.1)
            else:
                self.settings_open = False
                self.selected_index = 0
            return

        if self.selected_index == 0:
            self.start_requested = True
        elif self.selected_index == 1:
            self.settings_open = True
            self.selected_index = 0
        else:
            self.quit_requested = True

    def update(
        self,
        dt: float,
        mouse_pos: tuple[int, int] | None = None,
        mouse_click: tuple[int, int] | None = None,
    ) -> None:
        keys = pygame.key.get_pressed()
        up_pressed = keys[pygame.K_UP]
        down_pressed = keys[pygame.K_DOWN]
        left_pressed = keys[pygame.K_LEFT]
        right_pressed = keys[pygame.K_RIGHT]
        confirm_pressed = keys[pygame.K_j] or keys[pygame.K_RETURN] or keys[pygame.K_SPACE]
        escape_pressed = keys[pygame.K_ESCAPE]
        options = self._menu_options()
        rects = self._option_rects()

        if mouse_pos is not None:
            for index, rect in enumerate(rects):
                if rect.collidepoint(mouse_pos):
                    self.selected_index = index
                    break
        if up_pressed and not self._up_pressed:
            self.selected_index = (self.selected_index - 1) % len(options)
        elif down_pressed and not self._down_pressed:
            self.selected_index = (self.selected_index + 1) % len(options)
        if self.settings_open and self.selected_index == 1:
            if left_pressed and not self._left_pressed:
                AudioBank.set_master_volume(AudioBank.master_volume - 0.1)
            elif right_pressed and not self._right_pressed:
                AudioBank.set_master_volume(AudioBank.master_volume + 0.1)

        self.start_requested = False
        self.quit_requested = False
        if mouse_click is not None:
            for index, rect in enumerate(rects):
                if rect.collidepoint(mouse_click):
                    self.selected_index = index
                    if self.settings_open and index == 1:
                        bar_rect = pygame.Rect(rect.x + 100, rect.y + 17, 130, 20)
                        if bar_rect.collidepoint(mouse_click):
                            volume = (mouse_click[0] - bar_rect.left) / bar_rect.width
                            AudioBank.set_master_volume(volume)
                    else:
                        self._activate_selected()
                    break
        elif confirm_pressed and not self._confirm_pressed:
            self._activate_selected()
        elif self.settings_open and escape_pressed and not self._escape_pressed:
            self.settings_open = False
            self.selected_index = 0

        self._up_pressed = up_pressed
        self._down_pressed = down_pressed
        self._left_pressed = left_pressed
        self._right_pressed = right_pressed
        self._confirm_pressed = confirm_pressed
        self._escape_pressed = escape_pressed
        self.scroll_x += self.scroll_speed_x * dt
        self.scroll_y += self.scroll_speed_y * dt

    def _draw_background(self, surface: pygame.Surface) -> None:
        if not self.background_tiles:
            surface.fill((14, 14, 18))
            return

        tile_w, tile_h = self.tile_size
        cols = (SCREEN_WIDTH // tile_w) + 3
        rows = (SCREEN_HEIGHT // tile_h) + 3
        col_base = int(self.scroll_x // tile_w)
        row_base = int(self.scroll_y // tile_h)
        col_offset = self.scroll_x % tile_w
        row_offset = self.scroll_y % tile_h

        for row in range(-1, rows):
            source_row = row_base + row
            y = int(source_row * tile_h - self.scroll_y)
            for col in range(-1, cols):
                source_col = col_base + col
                seed = self.grid_seed ^ (source_row * 374761393) ^ (source_col * 668265263)
                tile = self.background_tiles[abs(seed) % len(self.background_tiles)]
                x = int(source_col * tile_w - self.scroll_x)
                surface.blit(tile, (x, y))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 14, 120))
        surface.blit(overlay, (0, 0))

    def _draw_title(self, surface: pygame.Surface) -> None:
        credit = self.credit_font.render("Official game by Josh Olsson", True, TEXT_COLOR)

        if self.title_logo is not None:
            logo_rect = self.title_logo.get_rect(center=(SCREEN_WIDTH // 2, 140))
            shadow = self.title_logo.copy()
            shadow.fill((0, 0, 0, 120), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(shadow, (logo_rect.x + 3, logo_rect.y + 3))
            surface.blit(self.title_logo, logo_rect)
        else:
            title = self.title_font.render("Little Fighter 3", True, TEXT_COLOR)
            title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 140))
            shadow = title.copy()
            shadow.fill((0, 0, 0, 120), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(shadow, (title_rect.x + 3, title_rect.y + 3))
            surface.blit(title, title_rect)

        heading_text = "Settings" if self.settings_open else "Main Menu"
        heading = self.option_font.render(heading_text, True, TEXT_COLOR)
        surface.blit(heading, heading.get_rect(center=(SCREEN_WIDTH // 2, 260)))
        for index, (label, rect) in enumerate(zip(self._menu_options(), self._option_rects())):
            color = (80, 110, 165) if index == self.selected_index else (35, 38, 48)
            pygame.draw.rect(surface, color, rect, border_radius=8)
            pygame.draw.rect(surface, (210, 210, 220), rect, 2, border_radius=8)
            if self.settings_open and index == 1:
                label_text = self.option_font.render(label, True, TEXT_COLOR)
                surface.blit(label_text, label_text.get_rect(midleft=(rect.x + 14, rect.centery)))
                bar_rect = pygame.Rect(rect.x + 100, rect.y + 17, 130, 20)
                pygame.draw.rect(surface, (20, 22, 28), bar_rect, border_radius=6)
                fill_rect = bar_rect.copy()
                fill_rect.width = round(bar_rect.width * AudioBank.master_volume)
                if fill_rect.width:
                    pygame.draw.rect(surface, (100, 190, 120), fill_rect, border_radius=6)
                volume_text = self.credit_font.render(f"{round(AudioBank.master_volume * 100)}%", True, TEXT_COLOR)
                surface.blit(volume_text, volume_text.get_rect(midright=(rect.right - 12, rect.centery)))
                continue
            text = self.option_font.render(label, True, TEXT_COLOR)
            surface.blit(text, text.get_rect(center=rect.center))

        credit_rect = credit.get_rect(bottomright=(SCREEN_WIDTH - 20, SCREEN_HEIGHT - 16))
        surface.blit(credit, credit_rect)

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        self._draw_title(surface)
