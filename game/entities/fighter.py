from __future__ import annotations

from dataclasses import dataclass

import pygame

from game.constants import GROUND_Y, LANE_MAX_Y, LANE_MIN_Y, SHADOW_COLOR
from game.systems.animation import AnimationPlayer
from game.systems.assets import load_character_sheet


@dataclass
class FighterConfig:
    name: str
    definition: dict


@dataclass
class FighterInput:
    left: bool = False
    right: bool = False
    up: bool = False
    down: bool = False
    run: bool = False
    horizontal_move_active: bool = False
    attack_pressed: bool = False
    attack_just_pressed: bool = False
    block_pressed: bool = False
    block_just_pressed: bool = False
    jump_just_pressed: bool = False
    knock_just_pressed: bool = False
    lift_just_pressed: bool = False
    die_just_pressed: bool = False
    revive_just_pressed: bool = False
    break_block_just_pressed: bool = False


class Fighter:
    def __init__(self, config: FighterConfig, start_pos: tuple[float, float]) -> None:
        self.name = config.name
        self.definition = config.definition
        self.x, self.lane_y = start_pos
        self.lane_y = max(LANE_MIN_Y, min(LANE_MAX_Y, self.lane_y))
        self.z = 0.0
        self.velocity_z = 0.0
        self.facing = 1
        self.state = "idle"
        self.attack_timer = 0.0
        self.state_timer = 0.0
        self.knock_hold_timer = 0.0
        self.is_defending = False
        self.attack_animation = "attack_punch"
        self.next_attack_animation = "attack_punch"
        self.revive_flash_timer = 0.0
        self.revive_flash_interval = 0.10
        self.revive_flash_count = 0
        self.controls_enabled = True
        self.block_strength = 1
        self.block_hold_timer = 0.0
        self.block_broken = False
        self.dodge_invulnerable = False
        self.push_velocity_x = 0.0
        self.grapple_target: Fighter | None = None
        self.grapple_hit_timer = 0.0
        self.current_jump_animation = "jump_vertical"
        self.jump_locked_forward = False
        self.movement = self.definition["movement"]
        self.combat = self.definition["combat"]
        self.shadow_size = self.definition["shadow_size"]
        animations = load_character_sheet(self.definition)
        self.animation_player = AnimationPlayer(animations, "idle")

    @property
    def draw_pos(self) -> tuple[int, int]:
        frame = self.animation_player.current_frame
        frame_rect = frame.get_rect()
        return int(self.x - frame_rect.width / 2), int(GROUND_Y + self.lane_y - self.z - frame_rect.height)

    def _start_knockdown(self) -> None:
        self.state = "knocked"
        self.state_timer = 0.70
        self.knock_hold_timer = 1.0
        self.attack_timer = 0.0
        self.block_hold_timer = 0.0
        self.push_velocity_x = -self.facing * 140.0
        self.jump_locked_forward = False
        self.grapple_target = None

    def _start_death(self) -> None:
        self.state = "die"
        self.state_timer = 0.84
        self.controls_enabled = False
        self.attack_timer = 0.0
        self.block_hold_timer = 0.0
        self.push_velocity_x = self.facing * 120.0
        self.jump_locked_forward = False
        self.grapple_target = None

    def _start_revive(self) -> None:
        self.state = "get_up"
        self.state_timer = 0.45
        self.controls_enabled = True
        self.block_broken = False
        self.block_strength = 1
        self.revive_flash_count = 10
        self.revive_flash_timer = self.revive_flash_interval
        self.push_velocity_x = 0.0
        self.jump_locked_forward = False
        self.grapple_target = None

    def _start_block_break(self) -> None:
        self.state = "block_break"
        self.state_timer = 0.36
        self.block_broken = True
        self.block_strength = 0
        self.block_hold_timer = 0.0

    def _apply_grapple_hit(self) -> None:
        self.state = "grappled_hit"
        self.state_timer = 0.22

    def _start_jump(self, use_forward_jump: bool) -> None:
        self.state = "jump_forward" if use_forward_jump else "jump_vertical"
        self.current_jump_animation = "jump_forward" if use_forward_jump else "jump_vertical"
        self.jump_locked_forward = use_forward_jump
        self.velocity_z = self.movement["jump_velocity"]
        self.z = 1

    def try_start_grapple(self, target: Fighter | None, attack_pressed: bool) -> bool:
        if target is None:
            return False
        if not attack_pressed:
            return False
        if not target.block_broken:
            return False
        if target.state in {"die", "dead", "knocked", "get_up"}:
            return False

        self.state = "grapple"
        self.attack_timer = 2.0
        self.grapple_target = target
        target.state = "grappled"
        target.state_timer = 2.0
        target.controls_enabled = False
        return True

    def update(self, dt: float, inputs: FighterInput, target: Fighter | None = None, controlled: bool = True) -> None:
        attack_pressed = controlled and inputs.attack_pressed
        block_pressed = controlled and inputs.block_pressed
        attack_just_pressed = controlled and inputs.attack_just_pressed
        block_just_pressed = controlled and inputs.block_just_pressed
        knock_just_pressed = controlled and inputs.knock_just_pressed
        lift_just_pressed = controlled and inputs.lift_just_pressed
        die_just_pressed = controlled and inputs.die_just_pressed
        revive_just_pressed = controlled and inputs.revive_just_pressed
        break_block_just_pressed = controlled and inputs.break_block_just_pressed
        jump_just_pressed = controlled and inputs.jump_just_pressed

        move_x = 0
        move_y = 0
        if controlled and self.controls_enabled and inputs.left:
            move_x -= 1
            self.facing = -1
        if controlled and self.controls_enabled and inputs.right:
            move_x += 1
            self.facing = 1
        if controlled and self.controls_enabled and inputs.up:
            move_y -= 1
        if controlled and self.controls_enabled and inputs.down:
            move_y += 1

        running = controlled and self.controls_enabled and inputs.run

        if self.state_timer > 0:
            self.state_timer = max(0.0, self.state_timer - dt)
        if self.knock_hold_timer > 0:
            self.knock_hold_timer = max(0.0, self.knock_hold_timer - dt)
        if self.attack_timer > 0:
            self.attack_timer = max(0.0, self.attack_timer - dt)
        if self.block_hold_timer > 0:
            self.block_hold_timer = max(0.0, self.block_hold_timer - dt)
        if self.grapple_hit_timer > 0:
            self.grapple_hit_timer = max(0.0, self.grapple_hit_timer - dt)
        if self.revive_flash_count > 0:
            self.revive_flash_timer = max(0.0, self.revive_flash_timer - dt)
            if self.revive_flash_timer == 0:
                self.revive_flash_count -= 1
                if self.revive_flash_count > 0:
                    self.revive_flash_timer = self.revive_flash_interval

        if self.push_velocity_x != 0:
            self.x += self.push_velocity_x * dt
            decay = 420.0 * dt
            if abs(self.push_velocity_x) <= decay:
                self.push_velocity_x = 0.0
            else:
                self.push_velocity_x -= decay if self.push_velocity_x > 0 else -decay

        if self.grapple_target is not None:
            if block_just_pressed or self.attack_timer == 0:
                self.grapple_target._start_knockdown()
                self.grapple_target.controls_enabled = True
                self.grapple_target = None
                self.state = "idle"
                self.attack_timer = 0.0
            elif attack_just_pressed:
                self.grapple_target._apply_grapple_hit()
                self.grapple_target.state_timer = 0.22
                self.grapple_hit_timer = 0.22

        if self.attack_timer == 0 and self.state in {"attack", "move_attack"}:
            self.state = "idle"
        if self.state == "knocked" and self.state_timer == 0 and self.knock_hold_timer == 0:
            self.state = "get_up"
            self.state_timer = 0.45
        if self.state_timer == 0 and self.state in {"get_up", "lift_heavy", "block_break", "block_dodge", "grappled_hit"}:
            self.state = "idle"
            self.block_strength = 1
            self.dodge_invulnerable = False
        if self.state_timer == 0 and self.state == "die":
            self.state = "dead"
        if self.state_timer == 0 and self.state == "grappled":
            self.state = "idle"
            self.controls_enabled = True

        if self.z > 0 or self.velocity_z != 0:
            self.velocity_z += self.movement["gravity"] * dt
            self.z -= self.velocity_z * dt
            if self.z <= 0:
                self.z = 0
                self.velocity_z = 0
                if self.state in {"jump_vertical", "jump_forward"}:
                    self.state = "idle"
                    self.jump_locked_forward = False

        if revive_just_pressed and self.state in {"die", "dead"}:
            self._start_revive()
        elif die_just_pressed and self.state not in {"die", "dead"}:
            self._start_death()
        elif knock_just_pressed and self.z == 0 and self.state not in {"die", "dead"}:
            self._start_knockdown()
        elif break_block_just_pressed and self.state == "block":
            self._start_block_break()
        elif self.state not in {"attack", "move_attack", "knocked", "lift_heavy", "get_up", "die", "dead", "block_break", "block_dodge", "grapple", "grappled", "grappled_hit"} and self.z == 0 and self.velocity_z == 0:
            self.is_defending = controlled and self.controls_enabled and block_pressed and self.z == 0
            self.dodge_invulnerable = False

            if self.is_defending and (move_x or move_y):
                self.state = "block_dodge"
                self.state_timer = 0.32
                self.dodge_invulnerable = True
                self.block_hold_timer = 0.0
                if move_x != 0:
                    self.push_velocity_x = move_x * 320.0
            elif self.is_defending:
                if self.state != "block":
                    self.block_hold_timer = 1.0
                    self.block_strength = 1
                self.state = "block"
                if attack_just_pressed and self.block_strength > 0:
                    self.block_strength = 0
                if self.block_strength == 0 and break_block_just_pressed:
                    self._start_block_break()
            elif self.state == "block":
                self.state = "idle"
                self.block_hold_timer = 0.0
                self.block_strength = 1
            elif lift_just_pressed and self.z == 0:
                self.state = "lift_heavy"
                self.state_timer = 0.66
            elif attack_pressed and self.block_broken and self.z == 0 and self.try_start_grapple(target, attack_pressed):
                pass
            elif attack_just_pressed and self.z == 0 and (move_x or move_y):
                self.state = "move_attack"
                self.attack_timer = self.combat["attack_duration"]
            elif attack_just_pressed and self.z == 0:
                self.state = "attack"
                self.attack_animation = self.next_attack_animation
                self.next_attack_animation = "attack_kick" if self.next_attack_animation == "attack_punch" else "attack_punch"
                self.attack_timer = self.combat["attack_duration"]
            elif jump_just_pressed and self.z == 0:
                self._start_jump(use_forward_jump=inputs.horizontal_move_active)
            elif move_x or move_y:
                self.state = "run" if running else "walk"
            elif self.z == 0:
                self.state = "idle"

        if jump_just_pressed and self.z > 0 and self.state in {"jump_vertical", "jump_forward"}:
            self.current_jump_animation = "jump_forward" if self.jump_locked_forward else "jump_vertical"

        if (self.z > 0 or self.velocity_z != 0) and self.state not in {"jump_vertical", "jump_forward"}:
            self.state = "jump_forward" if self.jump_locked_forward else "jump_vertical"

        if self.state in {"walk", "run"}:
            speed = self.movement["run_speed"] if self.state == "run" else self.movement["walk_speed"]
            self.x += move_x * speed * dt
            self.lane_y += move_y * self.movement["lane_speed"] * dt
        elif self.state in {"jump_vertical", "jump_forward"}:
            horizontal_speed = 0.0
            jump_lane_move = move_y
            if self.jump_locked_forward:
                horizontal_speed = self.movement["walk_speed"]
                jump_lane_move = 0
            self.x += self.facing * horizontal_speed * dt
            self.lane_y += jump_lane_move * self.movement["lane_speed"] * dt

        self.x = max(60, min(900, self.x))
        self.lane_y = max(LANE_MIN_Y, min(LANE_MAX_Y, self.lane_y))

        if self.state == "attack":
            animation_name = self.attack_animation
        elif self.state == "move_attack":
            animation_name = "move_attack"
        elif self.state == "grapple":
            animation_name = "grapple"
        elif self.state == "grappled":
            animation_name = "grappled"
        elif self.state == "grappled_hit":
            animation_name = "grappled_hit"
        elif self.state == "knocked":
            animation_name = "knocked"
        elif self.state == "get_up":
            animation_name = "get_up"
        elif self.state == "lift_heavy":
            animation_name = "lift_heavy"
        elif self.state == "block":
            animation_name = "block"
        elif self.state == "block_break":
            animation_name = "block_break"
        elif self.state == "block_dodge":
            animation_name = "block_dodge"
        elif self.state in {"die", "dead"}:
            animation_name = "die"
        elif self.state == "run":
            animation_name = "run"
        elif self.state == "walk":
            animation_name = "walk"
        elif self.state in {"jump_vertical", "jump_forward"}:
            animation_name = self.current_jump_animation
        else:
            animation_name = "idle"

        self.animation_player.play(animation_name)
        self.animation_player.update(dt, facing=self.facing)
        if animation_name == "block" and self.block_strength == 0:
            self.animation_player.frame_index = min(1, len(self.animation_player.animations["block"]["surfaces"]) - 1)
            frame = self.animation_player.animations["block"]["surfaces"][self.animation_player.frame_index]
            self.animation_player.current_frame = frame if self.facing == 1 else pygame.transform.flip(frame, True, False)

    def draw(self, surface: pygame.Surface) -> None:
        shadow = pygame.Surface(self.shadow_size, pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, SHADOW_COLOR, shadow.get_rect())
        shadow_rect = shadow.get_rect(center=(int(self.x), int(GROUND_Y + self.lane_y - 6)))
        surface.blit(shadow, shadow_rect)
        frame = self.animation_player.current_frame.copy()
        if self.revive_flash_count > 0 and self.revive_flash_count % 2 == 0:
            frame.set_alpha(100)
        surface.blit(frame, self.draw_pos)
