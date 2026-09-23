from __future__ import annotations

import sys
from pathlib import Path

import pygame

from game.constants import BG_COLOR, FPS, SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR, VERSION
from game.entities.fighter import FighterInput
from game.scenes.battle_scene import BattleScene
from game.scenes.character_select_scene import CharacterSelectScene
from game.scenes.main_menu_scene import MainMenuScene
from game.systems.audio import AudioBank


class Game:
    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(f"little_fighter_3 {VERSION}")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 28)
        self.scene = MainMenuScene()
        self.sprites_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "characters"
        self.input_state = FighterInput()
        self.left_tap_time = 0.0
        self.right_tap_time = 0.0
        self.sprint_direction = 0
        self.double_tap_window = 0.24

    def run(self) -> None:
        while True:
            dt = self.clock.tick(FPS) / 1000.0
            pressed_actions = set()
            left_pressed = False
            right_pressed = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    pressed_actions.add(event.key)
                    if event.key == pygame.K_F9:
                        AudioBank.toggle_mute()
                    if event.key == pygame.K_LEFT:
                        if self.left_tap_time <= self.double_tap_window:
                            self.sprint_direction = -1
                        self.left_tap_time = 0.0
                    elif event.key == pygame.K_RIGHT:
                        if self.right_tap_time <= self.double_tap_window:
                            self.sprint_direction = 1
                        self.right_tap_time = 0.0
                if event.type == pygame.KEYUP:
                    if event.key == pygame.K_LEFT and self.sprint_direction == -1:
                        self.sprint_direction = 0
                    elif event.key == pygame.K_RIGHT and self.sprint_direction == 1:
                        self.sprint_direction = 0

            keys = pygame.key.get_pressed()
            left_pressed = keys[pygame.K_LEFT]
            right_pressed = keys[pygame.K_RIGHT]
            self.left_tap_time += dt
            self.right_tap_time += dt
            self.input_state = FighterInput(
                left=left_pressed,
                right=right_pressed,
                up=keys[pygame.K_UP],
                down=keys[pygame.K_DOWN],
                run=keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT] or (self.sprint_direction == -1 and left_pressed) or (self.sprint_direction == 1 and right_pressed),
                horizontal_move_active=left_pressed or right_pressed,
                attack_pressed=keys[pygame.K_j],
                attack_just_pressed=pygame.K_j in pressed_actions,
                block_pressed=keys[pygame.K_l],
                block_just_pressed=pygame.K_l in pressed_actions,
                jump_pressed=keys[pygame.K_k],
                jump_just_pressed=pygame.K_k in pressed_actions,
                left_just_pressed=pygame.K_LEFT in pressed_actions,
                right_just_pressed=pygame.K_RIGHT in pressed_actions,
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
                if pygame.K_ESCAPE in pressed_actions:
                    if self.scene.paused:
                        self.scene.paused = False
                    else:
                        self.scene.paused = True
                if self.scene.paused and pygame.K_m in pressed_actions:
                    self.scene = MainMenuScene()
                if pygame.K_F10 in pressed_actions:
                    for fighter in (self.scene.enemy,):
                        if fighter is not None and not fighter.is_dead:
                            fighter.health = 0
                            fighter._start_death()

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
                self.scene = BattleScene(self.scene.selected_character)
            self.screen.fill(BG_COLOR)
            self.scene.draw(self.screen)
            if isinstance(self.scene, BattleScene):
                mute_state = "Muted" if AudioBank.muted else "Sound on"
                hint = self.font.render(f"Arrows move, Shift runs, J attack, K jump_throw, L defend_actions, V knockdown, B lift, G break, N die, M revive, Q drink, F fire knock, I ice knock, H hurt, F9 {mute_state}, F10 kill enemy", True, TEXT_COLOR)
                self.screen.blit(hint, (20, 18))
            pygame.display.flip()
