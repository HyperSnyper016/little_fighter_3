from __future__ import annotations

import sys
from pathlib import Path

import pygame

from game.constants import BG_COLOR, FPS, SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR
from game.entities.fighter import FighterInput
from game.scenes.battle_scene import BattleScene
from game.scenes.character_select_scene import CharacterSelectScene
from game.scenes.main_menu_scene import MainMenuScene


class Game:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("little_fighter_3")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 28)
        self.scene = MainMenuScene()
        self.sprites_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "characters"
        self.input_state = FighterInput()

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            pressed_actions = set()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    pressed_actions.add(event.key)

            keys = pygame.key.get_pressed()
            self.input_state = FighterInput(
                left=keys[pygame.K_LEFT],
                right=keys[pygame.K_RIGHT],
                up=keys[pygame.K_UP],
                down=keys[pygame.K_DOWN],
                run=keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT],
                horizontal_move_active=keys[pygame.K_LEFT] or keys[pygame.K_RIGHT],
                attack_pressed=keys[pygame.K_x],
                attack_just_pressed=pygame.K_x in pressed_actions,
                block_pressed=keys[pygame.K_c],
                block_just_pressed=pygame.K_c in pressed_actions,
                jump_just_pressed=pygame.K_z in pressed_actions,
                knock_just_pressed=pygame.K_v in pressed_actions,
                lift_just_pressed=pygame.K_b in pressed_actions,
                die_just_pressed=pygame.K_n in pressed_actions,
                revive_just_pressed=pygame.K_m in pressed_actions,
                break_block_just_pressed=pygame.K_g in pressed_actions,
                drink_just_pressed=pygame.K_q in pressed_actions,
                fire_knock_just_pressed=pygame.K_f in pressed_actions,
                ice_knock_just_pressed=pygame.K_i in pressed_actions,
                hurt_just_pressed=pygame.K_h in pressed_actions,
            )

            if isinstance(self.scene, BattleScene):
                self.scene.update(dt, self.input_state)
            else:
                self.scene.update(dt)
            if isinstance(self.scene, MainMenuScene) and self.scene.start_requested:
                self.scene = CharacterSelectScene(
                    self.sprites_root,
                    confirm_already_pressed=keys[pygame.K_RETURN] or keys[pygame.K_SPACE],
                )
            elif isinstance(self.scene, CharacterSelectScene) and self.scene.selection_confirmed and self.scene.selected_character:
                self.scene = BattleScene(self.scene.selected_character, include_idle_enemy=self.scene.include_idle_enemy)
            self.screen.fill(BG_COLOR)
            self.scene.draw(self.screen)
            if isinstance(self.scene, BattleScene):
                hint = self.font.render("Arrows move, Shift runs, Z jump, X attack, C block, Move+C dodge, V knockdown, B lift, G break, N die, M revive, Q drink, F fire knock, I ice knock, H hurt", True, TEXT_COLOR)
                self.screen.blit(hint, (20, 18))
            pygame.display.flip()
