from __future__ import annotations

from dataclasses import dataclass

import pygame

from game.constants import GROUND_Y, LANE_MAX_Y, LANE_MIN_Y, SHADOW_COLOR
from game.systems.animation import AnimationPlayer
from game.systems.assets import load_character_sheet


COMBAT_ATTACK_STATES = {
    "basic_attack",
    "heavy_attack",
    "sprint_punch",
    "throw",
    "throw_heavy",
    "sp_move_attack",
    "sp_vert_attack",
}


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
    jump_pressed: bool = False
    jump_just_pressed: bool = False
    left_just_pressed: bool = False
    right_just_pressed: bool = False
    knock_just_pressed: bool = False
    lift_just_pressed: bool = False
    die_just_pressed: bool = False
    revive_just_pressed: bool = False
    break_block_just_pressed: bool = False
    drink_just_pressed: bool = False
    fire_knock_just_pressed: bool = False
    ice_knock_just_pressed: bool = False
    hurt_just_pressed: bool = False


@dataclass
class FighterSnapshot:
    x: float
    lane_y: float
    z: float
    facing: int
    state: str
    block_broken: bool
    controls_enabled: bool
    health: int
    mana: int
    defense_cooldown: float


class Fighter:
    def __init__(self, config: FighterConfig, start_pos: tuple[float, float], x_bounds: tuple[float, float] = (60.0, 900.0)) -> None:
        self.name = config.name
        self.definition = config.definition
        self.x, self.lane_y = start_pos
        self.min_x, self.max_x = x_bounds
        self.lane_y = max(LANE_MIN_Y, min(LANE_MAX_Y, self.lane_y))
        self.z = 0.0
        self.velocity_z = 0.0
        self.facing = 1
        self.state = "idle"
        self.attack_timer = 0.0
        self.state_timer = 0.0
        self.knock_hold_timer = 0.0
        self.freeze_timer = 0.0
        self.freeze_cooldown = 0.0
        self.is_defending = False
        self.revive_flash_timer = 0.0
        self.revive_flash_interval = 0.10
        self.revive_flash_count = 0
        self.controls_enabled = True
        self.block_strength = 1
        self.block_hold_timer = 0.0
        self.defense_cooldown = 0.0
        self.block_broken = False
        self.dodge_invulnerable = False
        self.push_velocity_x = 0.0
        self.grapple_target: Fighter | None = None
        self.grapple_hit_timer = 0.0
        self.current_jump_animation = "jump_normal"
        self.jump_stage = 0
        self.jump_horizontal_velocity = 0.0
        self.jump_attack_active = False
        self.movement = self.definition["movement"]
        self.combat = self.definition["combat"]
        self.stats = self.definition.get("stats", {})
        self.shadow_size = self.definition["shadow_size"]
        self.max_health = int(self.stats.get("max_health", 20))
        self.health = self.max_health
        self.max_mana = int(self.stats.get("max_mana", 100))
        self.mana = self.max_mana
        self.touch_damage = int(self.stats.get("touch_damage", 1))
        hitbox_width, hitbox_height = self.stats.get("hitbox", (92, 160))
        self.hitbox_size = (int(hitbox_width), int(hitbox_height))
        self.damage_cooldown = 0.0
        self.has_applied_attack_damage = False
        self.attack_started = False
        self.attack_projectile_fired = False
        self.last_step_state = False
        self.step_cycle_timer = 0.0
        self.just_landed = False
        self.just_jumped = False
        self.just_knocked_down = False
        self.special_attack_lock: str | None = None
        self.special_move_buffer = 0.0
        self.special_vert_buffer = 0.0
        self.special_move_projectile_timer = 0.0
        self.animations = load_character_sheet(self.definition)
        self.animation_player = AnimationPlayer(self.animations, "idle")
        self.basic_attack_cycle = [name for name in self.definition.get("basic_attack_cycle", ["attack_punch", "attack_kick"]) if name in self.animations]
        if not self.basic_attack_cycle:
            self.basic_attack_cycle = ["attack_punch"]
        self.basic_attack_index = 0
        self.special_move_projectile_index = 0
        self.attack_animation = self.basic_attack_cycle[0]

    def _has_animation(self, name: str) -> bool:
        return name in self.animations

    def _next_basic_attack_animation(self) -> str:
        animation = self.basic_attack_cycle[self.basic_attack_index]
        self.basic_attack_index = (self.basic_attack_index + 1) % len(self.basic_attack_cycle)
        return animation

    def next_special_move_projectile_index(self) -> int:
        index = self.special_move_projectile_index
        self.special_move_projectile_index = (self.special_move_projectile_index + 1) % 3
        return index + 1

    def _start_attack_state(self, state: str, push_velocity_x: float = 0.0) -> None:
        self.state = state
        self.attack_timer = self.combat["attack_duration"]
        self.has_applied_attack_damage = False
        self.attack_started = True
        self.attack_projectile_fired = False
        self.push_velocity_x = push_velocity_x

    def draw_pos(self, camera_x: float = 0.0) -> tuple[int, int]:
        frame = self.animation_player.current_frame
        frame_rect = frame.get_rect()
        return int(self.x - camera_x - (frame_rect.width / 2)), int(GROUND_Y + self.lane_y - self.z - frame_rect.height)

    @property
    def snapshot(self) -> FighterSnapshot:
        return FighterSnapshot(
            x=self.x,
            lane_y=self.lane_y,
            z=self.z,
            facing=self.facing,
            state=self.state,
            block_broken=self.block_broken,
            controls_enabled=self.controls_enabled,
            health=self.health,
            mana=self.mana,
            defense_cooldown=self.defense_cooldown,
        )

    @property
    def is_dead(self) -> bool:
        return self.state in {"die", "dead"}

    @property
    def is_invulnerable(self) -> bool:
        return self.state in {"knocked", "knocked_fire", "knocked_freeze", "get_up", "grappled"} or self.dodge_invulnerable

    def hitbox_rect(self, camera_x: float = 0.0) -> pygame.Rect:
        width, height = self.hitbox_size
        draw_x, draw_y = self.draw_pos(camera_x)
        frame = self.animation_player.current_frame
        x = draw_x + max(0, (frame.get_width() - width) // 2)
        y = draw_y + max(0, frame.get_height() - height)
        return pygame.Rect(x, y, width, height)

    def world_hitbox_rect(self) -> pygame.Rect:
        width, height = self.hitbox_size
        x = int(self.x - (width / 2))
        y = int(GROUND_Y + self.lane_y - self.z - height)
        return pygame.Rect(x, y, width, height)

    def _start_knockdown(self) -> None:
        self.state = "knocked"
        self.state_timer = 0.48
        self.knock_hold_timer = 0.7
        self.freeze_timer = 0.0
        self.freeze_cooldown = 0.0
        self.attack_timer = 0.0
        self.block_hold_timer = 0.0
        self.push_velocity_x = -self.facing * 160.0
        self.jump_stage = 0
        self.jump_horizontal_velocity = 0.0
        self.jump_attack_active = False
        self.grapple_target = None
        self.just_knocked_down = True

    def _start_fire_knockdown(self) -> None:
        self.state = "knocked_fire"
        self.state_timer = 0.52
        self.knock_hold_timer = 0.7
        self.freeze_timer = 0.0
        self.freeze_cooldown = 0.0
        self.attack_timer = 0.0
        self.block_hold_timer = 0.0
        self.push_velocity_x = -self.facing * 180.0
        self.jump_stage = 0
        self.jump_horizontal_velocity = 0.0
        self.jump_attack_active = False
        self.grapple_target = None
        self.just_knocked_down = True

    def _start_ice_knockdown(self) -> None:
        self.state = "knocked_freeze"
        self.state_timer = 5.0
        self.knock_hold_timer = 0.9
        self.freeze_timer = 5.0
        self.freeze_cooldown = 0.0
        self.attack_timer = 0.0
        self.block_hold_timer = 0.0
        self.push_velocity_x = -self.facing * 150.0
        self.jump_stage = 0
        self.jump_horizontal_velocity = 0.0
        self.jump_attack_active = False
        self.grapple_target = None
        self.just_knocked_down = True

    def _start_death(self) -> None:
        self.state = "die"
        self.state_timer = 0.55
        self.controls_enabled = False
        self.attack_timer = 0.0
        self.has_applied_attack_damage = False
        self.block_hold_timer = 0.0
        self.push_velocity_x = self.facing * 120.0
        self.jump_stage = 0
        self.jump_horizontal_velocity = 0.0
        self.jump_attack_active = False
        self.grapple_target = None

    def _start_revive(self) -> None:
        self.state = "get_up"
        self.state_timer = 0.36
        self.controls_enabled = True
        self.block_broken = False
        self.block_strength = 1
        self.freeze_timer = 0.0
        self.freeze_cooldown = 0.0
        self.defense_cooldown = 0.0
        self.revive_flash_count = 10
        self.revive_flash_timer = self.revive_flash_interval
        self.push_velocity_x = 0.0
        self.jump_stage = 0
        self.jump_horizontal_velocity = 0.0
        self.jump_attack_active = False
        self.grapple_target = None

    def _start_block_break(self) -> None:
        self.state = "block_break"
        self.state_timer = 0.22
        self.block_broken = True
        self.block_strength = 0
        self.block_hold_timer = 0.0

    def _start_hurt(self) -> None:
        self.state = "hurt"
        self.state_timer = 0.28
        self.freeze_timer = 0.0
        self.freeze_cooldown = 0.0
        self.attack_timer = 0.0
        self.has_applied_attack_damage = False
        self.jump_attack_active = False

    def _apply_grapple_hit(self) -> None:
        self.state = "grapple_hit"
        self.state_timer = 0.22

    def receive_damage(self, amount: int) -> None:
        if amount <= 0 or self.is_dead or self.damage_cooldown > 0 or self.is_invulnerable:
            return

        self.health = max(0, self.health - amount)
        self.damage_cooldown = 0.18
        if self.health == 0:
            self._start_death()
            return

        self._start_hurt()

    def _start_jump(self) -> None:
        self.state = "jump"
        self.current_jump_animation = "jump_normal"
        self.jump_stage = 1
        self.jump_horizontal_velocity = 0.0
        self.jump_attack_active = False
        self.velocity_z = self.movement["jump_velocity"]
        self.z = 1

    def _start_second_jump(self) -> None:
        self.state = "jump"
        self.current_jump_animation = "jump_second"
        self.jump_stage = 2
        self.jump_horizontal_velocity = self.facing * self.movement["run_speed"] * 1.8
        self.jump_attack_active = False
        self.velocity_z = self.movement["jump_velocity"]
        if self.z <= 0:
            self.z = 1

    def _start_jump_attack(self) -> None:
        self.state = "jump"
        self.current_jump_animation = "jump_attack" if "jump_attack" in self.animations else ("jump_second" if self.jump_stage == 2 else "jump_normal")
        self.jump_attack_active = True
        self.attack_timer = self.combat["attack_duration"]
        self.has_applied_attack_damage = False
        self.attack_started = True
        self.attack_projectile_fired = False

    def try_start_grapple(self, target: Fighter | None, attack_pressed: bool) -> bool:
        if target is None:
            return False
        if not attack_pressed:
            return False
        if not target.block_broken:
            return False
        if target.state in {"die", "dead", "knocked", "knocked_fire", "knocked_freeze", "get_up"}:
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
        jump_pressed = controlled and inputs.jump_pressed
        jump_just_pressed = controlled and inputs.jump_just_pressed
        drink_just_pressed = controlled and inputs.drink_just_pressed
        fire_knock_just_pressed = controlled and inputs.fire_knock_just_pressed
        ice_knock_just_pressed = controlled and inputs.ice_knock_just_pressed
        hurt_just_pressed = controlled and inputs.hurt_just_pressed
        was_airborne = self.z > 0 or self.velocity_z != 0
        self.just_landed = False
        self.just_jumped = False
        self.just_knocked_down = False

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
        move_special_chord = attack_pressed and block_pressed and move_x != 0
        vert_special_chord = attack_pressed and jump_pressed and inputs.up
        if controlled and self.controls_enabled and block_pressed and move_x != 0:
            self.special_move_buffer = 0.20
        if controlled and self.controls_enabled and jump_pressed and inputs.up:
            self.special_vert_buffer = 0.20
        move_special_ready = self.special_move_buffer > 0.0 or (block_pressed and move_x != 0)
        vert_special_ready = self.special_vert_buffer > 0.0 or (jump_pressed and inputs.up)
        if self.special_attack_lock == "move" and not move_special_chord:
            self.special_attack_lock = None
        if self.special_attack_lock == "vert" and not vert_special_chord:
            self.special_attack_lock = None

        if self.state_timer > 0:
            self.state_timer = max(0.0, self.state_timer - dt)
        if self.knock_hold_timer > 0:
            self.knock_hold_timer = max(0.0, self.knock_hold_timer - dt)
        if self.freeze_timer > 0:
            self.freeze_timer = max(0.0, self.freeze_timer - dt)
        if self.freeze_cooldown > 0:
            self.freeze_cooldown = max(0.0, self.freeze_cooldown - dt)
        if self.attack_timer > 0:
            self.attack_timer = max(0.0, self.attack_timer - dt)
        if self.damage_cooldown > 0:
            self.damage_cooldown = max(0.0, self.damage_cooldown - dt)
        if self.block_hold_timer > 0:
            self.block_hold_timer = max(0.0, self.block_hold_timer - dt)
        if self.defense_cooldown > 0:
            self.defense_cooldown = max(0.0, self.defense_cooldown - dt)
        if self.grapple_hit_timer > 0:
            self.grapple_hit_timer = max(0.0, self.grapple_hit_timer - dt)
        if self.special_move_buffer > 0:
            self.special_move_buffer = max(0.0, self.special_move_buffer - dt)
        if self.special_vert_buffer > 0:
            self.special_vert_buffer = max(0.0, self.special_vert_buffer - dt)
        if self.revive_flash_count > 0:
            self.revive_flash_timer = max(0.0, self.revive_flash_timer - dt)
            if self.revive_flash_timer == 0:
                self.revive_flash_count -= 1
                if self.revive_flash_count > 0:
                    self.revive_flash_timer = self.revive_flash_interval

        if self.state == "knocked_freeze" and self.freeze_timer <= 0:
            self.state = "knocked"
            self.state_timer = 0.48
            self.freeze_cooldown = 0.25
            self.animation_player.frame_index = 0

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

        if self.state == "sp_move_attack" and self.special_attack_lock == "move":
            if attack_pressed:
                self.special_move_projectile_timer = max(0.0, self.special_move_projectile_timer - dt)
                if self.special_move_projectile_timer == 0.0 and self.attack_projectile_fired:
                    self.attack_projectile_fired = False
            else:
                self.special_move_projectile_timer = 0.0
        else:
            self.special_move_projectile_timer = 0.0

        if self.state == "sp_move_attack" and self.attack_timer == 0 and self.animation_player.finished and move_special_ready and self.special_attack_lock == "move":
            self.attack_timer = 0.01
        if self.state == "sp_vert_attack" and self.attack_timer == 0 and self.animation_player.finished and vert_special_ready and self.special_attack_lock == "vert":
            self.attack_timer = 0.01
        if self.attack_timer == 0 and self.state in COMBAT_ATTACK_STATES and self.animation_player.finished:
            if self.state == "sp_move_attack" and move_special_ready and self.special_attack_lock == "move":
                pass
            elif self.state == "sp_vert_attack" and vert_special_ready and self.special_attack_lock == "vert":
                pass
            else:
                self.state = "idle"
                self.has_applied_attack_damage = False
                self.attack_started = False
                self.attack_projectile_fired = False
        if self.attack_timer == 0 and self.current_jump_animation == "jump_attack":
            self.current_jump_animation = "jump_second" if self.jump_stage == 2 else "jump_normal"
            self.jump_attack_active = False
            self.has_applied_attack_damage = False
            self.attack_started = False
            self.attack_projectile_fired = False
        if self.state == "knocked" and self.state_timer == 0 and self.knock_hold_timer == 0:
            self.state = "get_up"
            self.state_timer = 0.36
        if self.state == "knocked_fire" and self.state_timer == 0 and self.knock_hold_timer == 0:
            self.state = "get_up"
            self.state_timer = 0.36
        if self.state_timer == 0 and self.state in {"get_up", "lift_heavy", "block_break", "block_dodge", "grapple_hit"}:
            self.state = "idle"
            self.block_strength = 1
            self.dodge_invulnerable = False
        if self.state == "hurt" and self.state_timer == 0:
            self.state = "idle"
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
                if self.state == "jump":
                    self.state = "idle"
                    self.jump_stage = 0
                    self.jump_horizontal_velocity = 0.0
                    self.jump_attack_active = False
                    self.current_jump_animation = "jump_normal"
                    self.just_landed = True

        if revive_just_pressed and self.state in {"die", "dead"}:
            self._start_revive()
        elif die_just_pressed and self.state not in {"die", "dead"}:
            self._start_death()
        elif knock_just_pressed and self.z == 0 and self.state not in {"die", "dead"}:
            self._start_knockdown()
        elif fire_knock_just_pressed and self.z == 0 and self.state not in {"die", "dead"}:
            self._start_fire_knockdown()
        elif ice_knock_just_pressed and self.z == 0 and self.state not in {"die", "dead"}:
            self._start_ice_knockdown()
        elif hurt_just_pressed and self.z == 0 and self.state not in {"die", "dead"}:
            self._start_hurt()
        elif drink_just_pressed and self.z == 0 and self.state not in (COMBAT_ATTACK_STATES | {"grapple", "grappled", "jump"} | {"die", "dead"}):
            self.state = "drink"
            self.state_timer = 0.55
        elif break_block_just_pressed and self.state == "block":
            self._start_block_break()
        elif self.state not in (COMBAT_ATTACK_STATES | {"knocked", "knocked_fire", "knocked_freeze", "lift_heavy", "get_up", "die", "dead", "block_break", "block_dodge", "grapple", "grappled", "grapple_hit", "jump", "drink", "hurt"}) and self.z == 0 and self.velocity_z == 0:
            special_attack_started = False
            can_move_special = "sp_move_attack" in self.animations
            can_vert_special = "sp_vert_attack" in self.animations
            if attack_just_pressed and self.z == 0 and move_special_ready and self.special_attack_lock is None and can_move_special:
                self.state = "sp_move_attack"
                self._start_attack_state("sp_move_attack")
                special_attack_started = True
                self.special_attack_lock = "move"
                self.special_move_projectile_timer = 0.0
            elif attack_just_pressed and self.z == 0 and vert_special_ready and self.special_attack_lock is None and can_vert_special:
                self.state = "sp_vert_attack"
                self._start_attack_state("sp_vert_attack")
                special_attack_started = True
                self.special_attack_lock = "vert"
            if not special_attack_started:
                self.is_defending = controlled and self.controls_enabled and block_pressed and self.z == 0
                self.dodge_invulnerable = False

                if self.is_defending and block_just_pressed and (move_x or move_y):
                    self.state = "block_dodge"
                    self.state_timer = 0.22
                    self.dodge_invulnerable = True
                    self.block_hold_timer = 0.0
                    self.defense_cooldown = 0.5
                    if move_x != 0:
                        self.push_velocity_x = move_x * 320.0
                elif self.is_defending and self.defense_cooldown == 0.0:
                    if self.state != "block":
                        self.block_hold_timer = 1.0
                        self.block_strength = 1
                        self.defense_cooldown = 0.5
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
                    self.state_timer = 0.48
                elif attack_pressed and self.block_broken and self.z == 0 and self.try_start_grapple(target, attack_pressed):
                    pass
                elif self.state == "lift_heavy" and attack_just_pressed:
                    self.state = "throw_heavy"
                    self._start_attack_state("throw_heavy")
                elif attack_just_pressed and self.z == 0 and (move_x or move_y) and running:
                    self.state = "sprint_punch"
                    self._start_attack_state("sprint_punch", push_velocity_x=self.facing * 160.0)
                elif attack_just_pressed and self.z == 0 and (move_x or move_y):
                    self.state = "heavy_attack"
                    self._start_attack_state("heavy_attack")
                elif attack_just_pressed and self.z == 0:
                    self.state = "basic_attack"
                    self.attack_animation = self._next_basic_attack_animation()
                    self._start_attack_state("basic_attack")
                elif jump_just_pressed and self.z == 0:
                    self._start_jump()
                    self.just_jumped = True
                elif move_x or move_y:
                    self.state = "run" if running else "walk"
                elif self.z == 0:
                    self.state = "idle"
        elif self.state == "jump" and attack_just_pressed and self.attack_timer == 0:
            self._start_jump_attack()

        if jump_just_pressed and was_airborne and self.state == "jump" and self.jump_stage == 1:
            self._start_second_jump()
            self.just_jumped = True

        if (self.z > 0 or self.velocity_z != 0) and self.state != "jump":
            self.state = "jump"

        if self.state in {"walk", "run"}:
            speed = self.movement["run_speed"] if self.state == "run" else self.movement["walk_speed"]
            if self.state == "run":
                speed *= 1.25
            self.x += move_x * speed * dt
            self.lane_y += move_y * self.movement["lane_speed"] * dt
        elif self.state == "jump":
            air_horizontal_speed = self.movement["walk_speed"] * (1.6 if self.jump_stage == 2 else 1.2)
            if move_x != 0:
                self.jump_horizontal_velocity = move_x * air_horizontal_speed
            else:
                self.jump_horizontal_velocity *= max(0.0, 1.0 - (4.5 * dt))

            self.x += self.jump_horizontal_velocity * dt
            self.lane_y += move_y * self.movement["lane_speed"] * dt

        self.x = max(self.min_x, min(self.max_x, self.x))
        self.lane_y = max(LANE_MIN_Y, min(LANE_MAX_Y, self.lane_y))

        is_moving_on_ground = self.z == 0 and self.state in {"walk", "run"}
        if is_moving_on_ground:
            self.step_cycle_timer = max(0.0, self.step_cycle_timer - dt)
        else:
            self.step_cycle_timer = 0.0
            self.last_step_state = False

        if self.state == "basic_attack":
            animation_name = self.attack_animation
        elif self.state == "heavy_attack":
            animation_name = "heavy_attack"
        elif self.state == "sp_move_attack":
            animation_name = "sp_move_attack" if "sp_move_attack" in self.animations else ("heavy_attack" if "heavy_attack" in self.animations else "idle")
        elif self.state == "sp_vert_attack":
            animation_name = "sp_vert_attack" if "sp_vert_attack" in self.animations else ("jump_attack" if "jump_attack" in self.animations else ("jump_normal" if "jump_normal" in self.animations else "idle"))
        elif self.state == "grapple":
            animation_name = "grapple"
        elif self.state == "grappled":
            animation_name = "grappled"
        elif self.state == "grapple_hit":
            animation_name = "grapple_hit"
        elif self.state == "knocked":
            animation_name = "knocked"
        elif self.state == "knocked_fire":
            animation_name = "knocked_fire"
        elif self.state == "knocked_freeze":
            animation_name = "knocked_freeze"
        elif self.state == "drink":
            animation_name = "drink"
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
        elif self.state == "throw":
            animation_name = "throw"
        elif self.state == "throw_heavy":
            animation_name = "throw_heavy"
        elif self.state == "run":
            animation_name = "run"
        elif self.state == "walk":
            animation_name = "walk"
        elif self.state == "sprint_punch":
            animation_name = "sprint_punch"
        elif self.state == "hurt":
            animation_name = "hurt"
        elif self.state == "jump":
            animation_name = self.current_jump_animation if self.current_jump_animation in self.animations else "jump_normal"
        else:
            animation_name = "idle"
        if self.animation_player.current_name != animation_name:
            self.animation_player.play(animation_name)
        if self.state == "knocked_freeze":
            if self.freeze_timer > 0.0:
                self.animation_player.frame_index = 1
            else:
                self.animation_player.frame_index = 0
        self.animation_player.update(dt, facing=self.facing)
        if self.state in COMBAT_ATTACK_STATES and self.attack_timer == 0 and self.animation_player.finished:
            self.state = "idle"
            self.has_applied_attack_damage = False
            self.attack_started = False
            self.attack_projectile_fired = False
        if animation_name == "block" and self.block_strength == 0:
            self.animation_player.frame_index = min(1, len(self.animation_player.animations["block"]["surfaces"]) - 1)
            frame = self.animation_player.animations["block"]["surfaces"][self.animation_player.frame_index]
            self.animation_player.current_frame = frame if self.facing == 1 else pygame.transform.flip(frame, True, False)

    def draw(self, surface: pygame.Surface, camera_x: float = 0.0) -> None:
        shadow = pygame.Surface(self.shadow_size, pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, SHADOW_COLOR, shadow.get_rect())
        shadow_rect = shadow.get_rect(center=(int(self.x - camera_x), int(GROUND_Y + self.lane_y - 6)))
        surface.blit(shadow, shadow_rect)
        frame = self.animation_player.current_frame.copy()
        if self.revive_flash_count > 0 and self.revive_flash_count % 2 == 0:
            frame.set_alpha(100)
        surface.blit(frame, self.draw_pos(camera_x))
