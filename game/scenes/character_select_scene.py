from __future__ import annotations

from pathlib import Path

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR


class CharacterSelectScene:
    def __init__(self, sprites_root: Path, confirm_already_pressed: bool = False) -> None:
        self.title_font = pygame.font.Font(None, 54)
        self.name_font = pygame.font.Font(None, 36)
        self.prompt_font = pygame.font.Font(None, 24)
        self.sprites_root = sprites_root
        self.characters = self._discover_characters()
        self.selected_index = 0
        self.selection_confirmed = False
        self.selected_character = self.characters[0]["key"] if self.characters else None
        self.include_idle_enemy = True
        self._up_pressed = False
        self._down_pressed = False
        self._toggle_pressed = False
        self._confirm_pressed = confirm_already_pressed

    def _discover_characters(self) -> list[dict]:
        characters: list[dict] = []
        if not self.sprites_root.exists():
            return characters

        for directory in sorted(path for path in self.sprites_root.iterdir() if path.is_dir()):
            # skip placeholder folders (e.g. _example_asset)
            if directory.name.startswith("_"):
                continue
            profile_path = self._resolve_profile_path(directory)
            if profile_path is None:
                continue

            profile = pygame.image.load(str(profile_path)).convert()
            profile.set_colorkey((0, 0, 0))
            width, height = profile.get_size()
            scaled = pygame.transform.scale(profile, (width * 2, height * 2))
            characters.append(
                {
                    "key": directory.name,
                    "display_name": directory.name.replace("_", " ").title(),
                    "profile": scaled,
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

        fallback_frames = sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in {".bmp", ".png"})
        if fallback_frames:
            return fallback_frames[0]

        return None

    def update(self, dt: float) -> None:
        _ = dt
        keys = pygame.key.get_pressed()

        up_pressed = keys[pygame.K_UP]
        down_pressed = keys[pygame.K_DOWN]
        toggle_pressed = keys[pygame.K_e]
        confirm_pressed = keys[pygame.K_RETURN] or keys[pygame.K_SPACE]

        if self.characters:
            if up_pressed and not self._up_pressed:
                self.selected_index = (self.selected_index - 1) % len(self.characters)
            if down_pressed and not self._down_pressed:
                self.selected_index = (self.selected_index + 1) % len(self.characters)

            self.selected_character = self.characters[self.selected_index]["key"]

            if toggle_pressed and not self._toggle_pressed:
                self.include_idle_enemy = not self.include_idle_enemy

            if confirm_pressed and not self._confirm_pressed:
                self.selection_confirmed = True

        self._up_pressed = up_pressed
        self._down_pressed = down_pressed
        self._toggle_pressed = toggle_pressed
        self._confirm_pressed = confirm_pressed

    def draw(self, surface: pygame.Surface) -> None:
        title = self.title_font.render("Choose Your Fighter", True, TEXT_COLOR)
        prompt = self.prompt_font.render("Up/Down to select, Enter or Space to start", True, TEXT_COLOR)

        surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 70)))
        surface.blit(prompt, prompt.get_rect(center=(SCREEN_WIDTH // 2, 110)))

        if not self.characters:
            empty = self.name_font.render("No playable characters found in assets\\sprites\\characters", True, TEXT_COLOR)
            surface.blit(empty, empty.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
            return

        selected = self.characters[self.selected_index]
        profile = selected["profile"]
        profile_rect = profile.get_rect(center=(SCREEN_WIDTH // 2, 245))
        surface.blit(profile, profile_rect)

        name = self.name_font.render(selected["display_name"], True, TEXT_COLOR)
        surface.blit(name, name.get_rect(center=(SCREEN_WIDTH // 2, 360)))
        enemy_text = "Idle Enemy: ON" if self.include_idle_enemy else "Idle Enemy: OFF"
        enemy_prompt = self.prompt_font.render(f"E to toggle idle enemy ({enemy_text})", True, TEXT_COLOR)
        surface.blit(enemy_prompt, enemy_prompt.get_rect(center=(SCREEN_WIDTH // 2, 395)))

        for index, character in enumerate(self.characters):
            prefix = ">" if index == self.selected_index else " "
            option = self.prompt_font.render(f"{prefix} {character['display_name']}", True, TEXT_COLOR)
            surface.blit(option, (80, 180 + (index * 28)))
