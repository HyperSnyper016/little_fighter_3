from __future__ import annotations

import sys
from pathlib import Path

import pygame

from game.constants import BG_COLOR, FPS, SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR, VERSION
from game.entities.fighter import FighterInput
from game.scenes.battle_scene import BattleScene
from game.scenes.character_select_scene import CharacterSelectScene
from game.scenes.main_menu_scene import MainMenuScene
from game.scenes.map_select_scene import MapSelectScene
from game.systems.audio import AudioBank
from game.systems.keybindings import KEY_BINDINGS


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
            pressed_key_events: list[int] = []
            mouse_click = None
            mouse_wheel_y = 0
            left_pressed = False
            right_pressed = False
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_click = event.pos
                if event.type == pygame.MOUSEWHEEL:
                    mouse_wheel_y += event.y
                if event.type == pygame.KEYDOWN:
                    pressed_actions.add(event.key)
                    pressed_key_events.append(event.key)
                    if KEY_BINDINGS.matches("mute", event.key):
                        AudioBank.toggle_mute()
                    if KEY_BINDINGS.matches("move_left", event.key):
                        if self.left_tap_time <= self.double_tap_window:
                            self.sprint_direction = -1
                        self.left_tap_time = 0.0
                    elif KEY_BINDINGS.matches("move_right", event.key):
                        if self.right_tap_time <= self.double_tap_window:
                            self.sprint_direction = 1
                        self.right_tap_time = 0.0
                if event.type == pygame.KEYUP:
                    if KEY_BINDINGS.matches("move_left", event.key) and self.sprint_direction == -1:
                        self.sprint_direction = 0
                    elif KEY_BINDINGS.matches("move_right", event.key) and self.sprint_direction == 1:
                        self.sprint_direction = 0

            keys = pygame.key.get_pressed()
            left_pressed = KEY_BINDINGS.is_pressed("move_left", keys)
            right_pressed = KEY_BINDINGS.is_pressed("move_right", keys)
            self.left_tap_time += dt
            self.right_tap_time += dt
            test_mode = isinstance(self.scene, BattleScene) and self.scene.test_mode
            self.input_state = FighterInput(
                left=left_pressed,
                right=right_pressed,
                up=KEY_BINDINGS.is_pressed("move_up", keys),
                up_just_pressed=KEY_BINDINGS.was_pressed("move_up", pressed_actions),
                down=KEY_BINDINGS.is_pressed("move_down", keys),
                run=KEY_BINDINGS.is_pressed("sprint", keys) or (self.sprint_direction == -1 and left_pressed) or (self.sprint_direction == 1 and right_pressed),
                horizontal_move_active=left_pressed or right_pressed,
                attack_pressed=KEY_BINDINGS.is_pressed("attack", keys),
                attack_just_pressed=KEY_BINDINGS.was_pressed("attack", pressed_actions),
                block_pressed=KEY_BINDINGS.is_pressed("defend", keys),
                block_just_pressed=KEY_BINDINGS.was_pressed("defend", pressed_actions),
                jump_pressed=KEY_BINDINGS.is_pressed("jump", keys),
                jump_just_pressed=KEY_BINDINGS.was_pressed("jump", pressed_actions),
                left_just_pressed=KEY_BINDINGS.was_pressed("move_left", pressed_actions),
                right_just_pressed=KEY_BINDINGS.was_pressed("move_right", pressed_actions),
                knock_just_pressed=test_mode and KEY_BINDINGS.was_pressed("knock_down", pressed_actions),
                lift_just_pressed=test_mode and KEY_BINDINGS.was_pressed("lift", pressed_actions),
                die_just_pressed=test_mode and KEY_BINDINGS.was_pressed("die", pressed_actions),
                revive_just_pressed=test_mode and KEY_BINDINGS.was_pressed("revive", pressed_actions),
                break_block_just_pressed=test_mode and KEY_BINDINGS.was_pressed("break_block", pressed_actions),
                drink_just_pressed=test_mode and KEY_BINDINGS.was_pressed("drink", pressed_actions),
                fire_knock_just_pressed=test_mode and KEY_BINDINGS.was_pressed("fire_knockdown", pressed_actions),
                ice_knock_just_pressed=test_mode and KEY_BINDINGS.was_pressed("ice_knockdown", pressed_actions),
                hurt_just_pressed=test_mode and KEY_BINDINGS.was_pressed("hurt", pressed_actions),
                spawn_random_item_just_pressed=test_mode and KEY_BINDINGS.was_pressed("spawn_item", pressed_actions),
                spawn_heavy_item_just_pressed=test_mode and KEY_BINDINGS.was_pressed("spawn_heavy_box", pressed_actions),
            )

            if isinstance(self.scene, BattleScene):
                if KEY_BINDINGS.was_pressed("back_pause", pressed_actions):
                    if self.scene.paused:
                        self.scene.paused = False
                    else:
                        self.scene.paused = True
                if self.scene.paused and KEY_BINDINGS.was_pressed("return_to_menu", pressed_actions):
                    self.scene = MainMenuScene()
                elif self.scene.test_mode and KEY_BINDINGS.was_pressed("defeat_enemy", pressed_actions):
                    for fighter in (self.scene.enemy,):
                        if fighter is not None and not fighter.is_dead:
                            fighter.health = 0
                            fighter._start_death()

            if isinstance(self.scene, BattleScene):
                self.scene.update(dt, self.input_state)
            elif isinstance(self.scene, MainMenuScene):
                self.scene.update(
                    dt,
                    pygame.mouse.get_pos(),
                    mouse_click,
                    mouse_wheel_y,
                    pygame.mouse.get_pressed()[0],
                    pressed_key_events,
                )
            elif isinstance(self.scene, CharacterSelectScene):
                self.scene.update(dt, pygame.mouse.get_pos(), mouse_click, mouse_wheel_y)
            elif isinstance(self.scene, MapSelectScene):
                self.scene.update(dt, pygame.mouse.get_pos(), mouse_click)
            else:
                self.scene.update(dt)
            if isinstance(self.scene, MainMenuScene) and self.scene.quit_requested:
                pygame.quit()
                sys.exit()
            if isinstance(self.scene, MainMenuScene) and self.scene.start_requested:
                self.scene = CharacterSelectScene(
                    self.sprites_root,
                    confirm_already_pressed=KEY_BINDINGS.is_pressed("menu_confirm", keys),
                    stage_mode=self.scene.stage_mode_requested,
                    test_mode=self.scene.test_mode_requested,
                )
            elif isinstance(self.scene, CharacterSelectScene) and self.scene.selection_confirmed and self.scene.selected_character:
                if self.scene.stage_mode:
                    self.scene = BattleScene(
                        self.scene.selected_character,
                        stage_mode=True,
                    )
                elif self.scene.test_mode:
                    self.scene = MapSelectScene(
                        self.scene.selected_character,
                        test_mode=True,
                        confirm_already_pressed=KEY_BINDINGS.is_pressed("menu_confirm", keys),
                    )
                elif self.scene.opponent_selection:
                    if self.scene.player_character is None:
                        raise RuntimeError("Opponent selection is missing the chosen player character.")
                    self.scene = BattleScene(
                        self.scene.player_character,
                        enemy_names=tuple(sorted(self.scene.selected_opponents)),
                        map_name=self.scene.map_name,
                    )
                else:
                    self.scene = MapSelectScene(
                        self.scene.selected_character,
                        confirm_already_pressed=(
                            KEY_BINDINGS.is_pressed("menu_confirm", keys)
                        ),
                    )
            elif isinstance(self.scene, MapSelectScene):
                if self.scene.back_requested:
                    self.scene = CharacterSelectScene(
                        self.sprites_root,
                        test_mode=self.scene.test_mode,
                        initial_character=self.scene.player_character,
                    )
                elif self.scene.selection_confirmed:
                    if self.scene.test_mode:
                        self.scene = BattleScene(
                            self.scene.player_character,
                            test_mode=True,
                            map_name=self.scene.selected_map,
                        )
                    else:
                        self.scene = CharacterSelectScene(
                            self.sprites_root,
                            opponent_selection=True,
                            player_character=self.scene.player_character,
                            confirm_already_pressed=KEY_BINDINGS.is_pressed("menu_confirm", keys),
                            map_name=self.scene.selected_map,
                        )
            elif isinstance(self.scene, BattleScene) and self.scene.return_to_menu_requested:
                self.scene = MainMenuScene()
            self.screen.fill(BG_COLOR)
            self.scene.draw(self.screen)
            if isinstance(self.scene, BattleScene):
                mute_state = "Muted" if AudioBank.muted else "Sound on"
                if self.scene.test_mode:
                    hint_text = (
                        "TEST: "
                        f"{KEY_BINDINGS.label('knock_down')} knockdown, "
                        f"{KEY_BINDINGS.label('lift')} lift, "
                        f"{KEY_BINDINGS.label('break_block')} break, "
                        f"{KEY_BINDINGS.label('die')} die, "
                        f"{KEY_BINDINGS.label('revive')} revive, "
                        f"{KEY_BINDINGS.label('drink')} drink, "
                        f"{KEY_BINDINGS.label('fire_knockdown')}/{KEY_BINDINGS.label('ice_knockdown')} fire/ice, "
                        f"{KEY_BINDINGS.label('hurt')} hurt, "
                        f"{KEY_BINDINGS.label('spawn_item')}/{KEY_BINDINGS.label('spawn_heavy_box')} spawn, "
                        f"{KEY_BINDINGS.label('defeat_enemy')} defeat enemy"
                    )
                else:
                    hint_text = (
                        f"{KEY_BINDINGS.label('move_up')}/{KEY_BINDINGS.label('move_down')}/"
                        f"{KEY_BINDINGS.label('move_left')}/{KEY_BINDINGS.label('move_right')} move, "
                        f"{KEY_BINDINGS.label('sprint')} sprint, "
                        f"{KEY_BINDINGS.label('attack')} attack/pick up/drink, "
                        f"{KEY_BINDINGS.label('jump')} jump, "
                        f"{KEY_BINDINGS.label('defend')} defend"
                    )
                hint = self.font.render(
                    f"{hint_text} | {KEY_BINDINGS.label('mute')} {mute_state}",
                    True,
                    TEXT_COLOR,
                )
                self.screen.blit(hint, (20, 18))
            pygame.display.flip()
