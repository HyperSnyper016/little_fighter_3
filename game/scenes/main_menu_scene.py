from __future__ import annotations

import random
from pathlib import Path

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR
from game.systems.audio import AudioBank


class MainMenuScene:
    def __init__(self) -> None:
        self.title_font = pygame.font.Font(None, 72)
        self.option_font = pygame.font.Font(None, 40)
        self.credit_font = pygame.font.Font(None, 24)
        self.start_requested = False
        self._confirm_pressed = False
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

    def update(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        confirm_pressed = keys[pygame.K_j]
        self.start_requested = confirm_pressed and not self._confirm_pressed
        if self.start_requested:
            self.audio.play("menu_accept")
        self._confirm_pressed = confirm_pressed
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
            y = int(row * tile_h + row_offset) - tile_h
            for col in range(-1, cols):
                source_col = col_base + col
                seed = self.grid_seed ^ (source_row * 374761393) ^ (source_col * 668265263)
                tile = self.background_tiles[abs(seed) % len(self.background_tiles)]
                x = int(col * tile_w + col_offset) - tile_w
                surface.blit(tile, (x, y))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 14, 120))
        surface.blit(overlay, (0, 0))

    def _draw_title(self, surface: pygame.Surface) -> None:
        option = self.option_font.render("Test Game", True, TEXT_COLOR)
        prompt = self.credit_font.render("Press Attack Key", True, TEXT_COLOR)
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

        for text, pos in (
            (option, option.get_rect(center=(SCREEN_WIDTH // 2, 260))),
            (prompt, prompt.get_rect(center=(SCREEN_WIDTH // 2, 305))),
        ):
            shadow = text.copy()
            shadow.fill((0, 0, 0, 120), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(shadow, (pos.x + 3, pos.y + 3))
            surface.blit(text, pos)

        credit_rect = credit.get_rect(bottomright=(SCREEN_WIDTH - 20, SCREEN_HEIGHT - 16))
        surface.blit(credit, credit_rect)

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        self._draw_title(surface)
