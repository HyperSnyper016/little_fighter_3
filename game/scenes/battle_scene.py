from __future__ import annotations

from pathlib import Path

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR
from game.data.characters import CHARACTERS
from game.entities.fighter import Fighter, FighterConfig, FighterInput, FighterSnapshot
from game.systems.audio import AudioBank
from game.systems.stage import ForestStage


class EnemyBrain:
    def build_input(self, fighter: FighterSnapshot, target: FighterSnapshot) -> FighterInput:
        input_state = FighterInput()
        lane_delta = target.lane_y - fighter.lane_y
        horizontal_delta = target.x - fighter.x
        distance = abs(horizontal_delta)

        if not fighter.controls_enabled:
            return input_state

        if target.state in {"knocked", "knocked_fire", "knocked_freeze"} and distance < 72 and fighter.z == 0:
            input_state.lift_just_pressed = True
            return input_state

        if fighter.state in {"knocked", "knocked_fire", "knocked_freeze", "get_up", "hurt", "die", "dead"}:
            return input_state

        if lane_delta < -12:
            input_state.up = True
        elif lane_delta > 12:
            input_state.down = True

        if horizontal_delta < -26:
            input_state.left = True
        elif horizontal_delta > 26:
            input_state.right = True

        if distance > 280:
            input_state.run = True
        elif distance < 56 and fighter.block_broken:
            input_state.attack_pressed = True
            input_state.attack_just_pressed = True
            return input_state

        if target.state in {"attack", "move_attack", "sprint_punch", "jump"} and fighter.defense_cooldown == 0.0 and distance < 96 and abs(lane_delta) < 30:
            input_state.block_pressed = True
            if distance < 72:
                if horizontal_delta < 0:
                    input_state.right = True
                else:
                    input_state.left = True
            return input_state

        if fighter.block_broken and distance < 56 and abs(lane_delta) < 18:
            input_state.attack_pressed = True
            input_state.attack_just_pressed = True
        elif fighter.z == 0 and target.z == 0 and 96 <= distance <= 132 and abs(lane_delta) < 18:
            if input_state.run and distance < 120:
                input_state.attack_pressed = True
                input_state.attack_just_pressed = True
            elif distance < 108:
                input_state.attack_pressed = True
                input_state.attack_just_pressed = True

        if fighter.z == 0 and target.z == 0 and 210 <= distance <= 320 and abs(lane_delta) < 18:
            input_state.jump_just_pressed = True

        input_state.horizontal_move_active = input_state.left or input_state.right
        return input_state


class BattleScene:
    def __init__(self, character_name: str = "bandit", include_idle_enemy: bool = True) -> None:
        self.font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 24)
        stage_root = Path(__file__).resolve().parents[2] / "assets" / "maps" / "Forrest"
        sounds_root = Path(__file__).resolve().parents[2] / "assets" / "sounds"
        self.stage = ForestStage(stage_root)
        self.audio = AudioBank(sounds_root)
        x_bounds = (self.stage.play_min_x, self.stage.play_max_x)
        start_x = SCREEN_WIDTH / 2
        self.fighter = Fighter(FighterConfig(character_name, CHARACTERS[character_name]), (start_x, 0), x_bounds=x_bounds)
        self.enemy = Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (start_x + 180, 0), x_bounds=x_bounds) if include_idle_enemy else None
        if self.enemy is not None:
            self.enemy.max_health = 10
            self.enemy.health = 10
        self.enemy_brain = EnemyBrain()
        if self.enemy is not None:
            self.enemy.facing = -1

    def _handle_combat(self) -> None:
        if self.enemy is None:
            return

        for attacker, defender in ((self.fighter, self.enemy), (self.enemy, self.fighter)):
            if attacker.is_dead or defender.is_dead:
                continue
            if attacker.state not in {"attack", "move_attack", "sprint_punch", "jump"}:
                continue
            if attacker.state == "jump" and not attacker.jump_attack_active:
                continue
            if attacker.has_applied_attack_damage:
                continue
            if not attacker.attack_started:
                continue
            if attacker.attack_timer <= 0:
                attacker.has_applied_attack_damage = True
                attacker.attack_started = False
                continue
            if abs(attacker.lane_y - defender.lane_y) > 36:
                attacker.has_applied_attack_damage = True
                attacker.attack_started = False
                self.audio.play_hit_miss()
                continue
            if not attacker.world_hitbox_rect().inflate(40, 0).colliderect(defender.world_hitbox_rect()):
                attacker.has_applied_attack_damage = True
                attacker.attack_started = False
                self.audio.play_hit_miss()
                continue

            attacker.has_applied_attack_damage = True
            attacker.attack_started = False
            if defender.state == "block" and defender.block_strength > 0:
                defender.block_strength = 0
                defender.block_hold_timer = 0.0
                self.audio.play("hit_guard")
                continue
            if defender.state == "block" and defender.block_strength == 0:
                defender._start_block_break()
                self.audio.play("hit_guard")
                continue

            defender.receive_damage(attacker.touch_damage)
            if attacker.state == "jump" and attacker.jump_attack_active and not defender.is_dead:
                defender._start_knockdown()
            self.audio.play("hit_success")

    def _handle_audio(self, dt: float) -> None:
        fighters = [self.fighter]
        if self.enemy is not None:
            fighters.append(self.enemy)

        for fighter in fighters:
            if fighter.just_knocked_down:
                self.audio.play("knockdown")
            if fighter.just_jumped:
                self.audio.play("jump")
            if fighter.just_landed:
                self.audio.play("jump_land")

            if fighter.z == 0 and fighter.state in {"walk", "run"}:
                if fighter.step_cycle_timer == 0.0:
                    self.audio.play_footstep()
                    fighter.step_cycle_timer = 0.22 if fighter.state == "walk" else 0.16
            else:
                fighter.step_cycle_timer = 0.0

    def _draw_hud_bar(self, surface: pygame.Surface, x: int, y: int, width: int, height: int, value: int, maximum: int, color: tuple[int, int, int], label: str) -> None:
        pygame.draw.rect(surface, (28, 28, 32), (x, y, width, height), border_radius=6)
        pygame.draw.rect(surface, (215, 215, 220), (x, y, width, height), 2, border_radius=6)
        fill_width = 0 if maximum <= 0 else int((max(0, value) / maximum) * (width - 4))
        if fill_width > 0:
            pygame.draw.rect(surface, color, (x + 2, y + 2, fill_width, height - 4), border_radius=4)
        text = self.small_font.render(f"{label} {value}/{maximum}", True, TEXT_COLOR)
        surface.blit(text, (x + 10, y + 6))

    def _draw_hud(self, surface: pygame.Surface) -> None:
        panel_width = 420
        self._draw_hud_bar(surface, 20, 18, panel_width, 28, self.fighter.health, self.fighter.max_health, (194, 58, 58), f"{self.fighter.definition['display_name']} HP")
        self._draw_hud_bar(surface, 20, 52, panel_width, 24, self.fighter.mana, self.fighter.max_mana, (72, 122, 235), "MP")
        if self.enemy is not None:
            x = SCREEN_WIDTH - panel_width - 20
            self._draw_hud_bar(surface, x, 18, panel_width, 28, self.enemy.health, self.enemy.max_health, (194, 58, 58), f"{self.enemy.definition['display_name']} HP")
            self._draw_hud_bar(surface, x, 52, panel_width, 24, self.enemy.mana, self.enemy.max_mana, (72, 122, 235), "MP")

    def _draw_marker(self, surface: pygame.Surface, fighter: Fighter, camera_x: float, text: str) -> None:
        marker = self.small_font.render(text, True, (255, 240, 120))
        rect = marker.get_rect(midtop=(fighter.world_hitbox_rect().centerx - int(camera_x), fighter.world_hitbox_rect().bottom + 6))
        if rect.bottom < SCREEN_HEIGHT:
            surface.blit(marker, rect)

    def update(self, dt: float, inputs: FighterInput) -> None:
        self.fighter.update(dt, inputs, target=self.enemy, controlled=True)
        if self.enemy is not None:
            enemy_input = self.enemy_brain.build_input(self.enemy.snapshot, self.fighter.snapshot)
            self.enemy.update(dt, enemy_input, target=self.fighter, controlled=True)
        self._handle_combat()
        self._handle_audio(dt)

    def draw(self, surface: pygame.Surface) -> None:
        focus_x = self.fighter.x
        if self.enemy is not None:
            player_margin = SCREEN_WIDTH * 0.3
            min_focus = self.fighter.x - player_margin
            max_focus = self.fighter.x + player_margin
            enemy_focus = (self.fighter.x + self.enemy.x) / 2
            focus_x = max(min_focus, min(max_focus, enemy_focus))

        camera_x = self.stage.camera_x(focus_x)
        self.stage.draw(surface, focus_x)

        fighters = [self.fighter]
        if self.enemy is not None:
            fighters.append(self.enemy)
        fighters.sort(key=lambda fighter: fighter.lane_y)
        for fighter in fighters:
            fighter.draw(surface, camera_x)

        self._draw_marker(surface, self.fighter, camera_x, "P1")
        self._draw_hud(surface)
