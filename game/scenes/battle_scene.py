from __future__ import annotations

import pygame

from game.constants import GROUND_COLOR, GROUND_Y, LANE_COLOR, LANE_MAX_Y, LANE_MIN_Y, SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR
from game.data.characters import CHARACTERS
from game.entities.fighter import Fighter, FighterConfig, FighterInput


class BattleScene:
    def __init__(self, character_name: str = "bandit", include_idle_enemy: bool = True) -> None:
        self.font = pygame.font.Font(None, 32)
        self.fighter = Fighter(FighterConfig(character_name, CHARACTERS[character_name]), (SCREEN_WIDTH / 2, 0))
        self.enemy = Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), ((SCREEN_WIDTH / 2) + 180, 0)) if include_idle_enemy else None
        if self.enemy is not None:
            self.enemy.facing = -1
            self.enemy.controls_enabled = False

    def update(self, dt: float, inputs: FighterInput) -> None:
        self.fighter.update(dt, inputs, target=self.enemy, controlled=True)
        if self.enemy is not None:
            self.enemy.update(dt, FighterInput(), target=self.fighter, controlled=False)
            if self.enemy.state not in {"die", "dead", "grappled", "grappled_hit", "knocked", "get_up"}:
                self.enemy.state = "idle"

    def draw(self, surface: pygame.Surface) -> None:
        ground_top = GROUND_Y + LANE_MIN_Y - 20
        ground_height = SCREEN_HEIGHT - ground_top
        pygame.draw.rect(surface, GROUND_COLOR, (0, ground_top, SCREEN_WIDTH, ground_height))

        lane_top = GROUND_Y + LANE_MIN_Y + 40
        lane_bottom = GROUND_Y + LANE_MAX_Y
        pygame.draw.line(surface, LANE_COLOR, (0, lane_top), (SCREEN_WIDTH, lane_top), 2)
        pygame.draw.line(surface, LANE_COLOR, (0, lane_bottom), (SCREEN_WIDTH, lane_bottom), 2)

        self.fighter.draw(surface)
        if self.enemy is not None:
            self.enemy.draw(surface)
        label = self.font.render(self.fighter.definition["display_name"], True, TEXT_COLOR)
        surface.blit(label, (20, 52))
