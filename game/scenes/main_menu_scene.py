from __future__ import annotations

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR


class MainMenuScene:
    def __init__(self) -> None:
        self.title_font = pygame.font.Font(None, 72)
        self.option_font = pygame.font.Font(None, 40)
        self.credit_font = pygame.font.Font(None, 24)
        self.start_requested = False
        self._confirm_pressed = False

    def update(self, dt: float) -> None:
        _ = dt
        keys = pygame.key.get_pressed()
        confirm_pressed = keys[pygame.K_RETURN] or keys[pygame.K_SPACE]
        self.start_requested = confirm_pressed and not self._confirm_pressed
        self._confirm_pressed = confirm_pressed

    def draw(self, surface: pygame.Surface) -> None:
        title = self.title_font.render("Little Fighter 3", True, TEXT_COLOR)
        option = self.option_font.render("Test Game", True, TEXT_COLOR)
        prompt = self.credit_font.render("Press Enter or Space", True, TEXT_COLOR)
        credit = self.credit_font.render("Official game by Josh Olsson", True, TEXT_COLOR)

        title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 140))
        option_rect = option.get_rect(center=(SCREEN_WIDTH // 2, 260))
        prompt_rect = prompt.get_rect(center=(SCREEN_WIDTH // 2, 305))
        credit_rect = credit.get_rect(bottomright=(SCREEN_WIDTH - 20, SCREEN_HEIGHT - 16))

        surface.blit(title, title_rect)
        surface.blit(option, option_rect)
        surface.blit(prompt, prompt_rect)
        surface.blit(credit, credit_rect)
