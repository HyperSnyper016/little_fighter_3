from __future__ import annotations

import math
import random
from pathlib import Path

import pygame

from game.constants import GROUND_Y, SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR
from game.data.characters import CHARACTERS
from game.entities.fighter import COMBAT_ATTACK_STATES, Fighter, FighterConfig, FighterInput, FighterSnapshot
from game.systems.audio import AudioBank
from game.systems.stage import ForestStage


def _load_folder_frames(folder: Path) -> list[pygame.Surface]:
    frames: list[pygame.Surface] = []
    if not folder.exists():
        return frames
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".png", ".bmp"}:
            continue
        frame = pygame.image.load(str(path)).convert()
        frame.set_colorkey((0, 0, 0))
        frames.append(frame)
    return frames


class BanditBrain:
    def __init__(self) -> None:
        self.throw_prep = False
        self.block_hold = False
        self.jump_cooldown = 0.0
        self.throw_cooldown = 0.0
        self.attack_cooldown = 0.0
        self.behavior_timer = 0.0
        self.behavior_mode = "advance"
        self.turn_lock = 0.0
        self.roam_target_x = 0.0
        self.roam_target_lane = 0.0
        self.last_mode_was_close = False

    def update(self, dt: float) -> None:
        self.jump_cooldown = max(0.0, self.jump_cooldown - dt)
        self.throw_cooldown = max(0.0, self.throw_cooldown - dt)
        self.attack_cooldown = max(0.0, self.attack_cooldown - dt)
        self.behavior_timer = max(0.0, self.behavior_timer - dt)
        self.turn_lock = max(0.0, self.turn_lock - dt)

    def _pick_behavior(self, self_snapshot: FighterSnapshot, target_snapshot: FighterSnapshot, dx: float, dy: float, same_lane: bool, target_attacking: bool) -> None:
        if self.behavior_timer > 0.0:
            return

        abs_dx = abs(dx)
        facing_to_target = 1 if dx >= 0 else -1
        if target_attacking and same_lane and abs_dx < 150.0:
            self.behavior_mode = random.choice(("defend", "dodge", "retreat"))
        elif abs_dx > 360.0:
            self.behavior_mode = random.choice(("advance", "advance", "jump", "flank"))
        elif abs_dx > 180.0:
            self.behavior_mode = random.choice(("advance", "pressure", "jump", "flank"))
        else:
            self.behavior_mode = random.choice(("pressure", "retreat", "dodge", "defend", "jump"))

        if self.behavior_mode == "advance":
            self.roam_target_x = target_snapshot.x - (facing_to_target * 150.0)
            self.roam_target_lane = target_snapshot.lane_y
            self.behavior_timer = random.uniform(0.7, 1.2)
        elif self.behavior_mode == "pressure":
            self.roam_target_x = target_snapshot.x - (facing_to_target * 80.0)
            self.roam_target_lane = target_snapshot.lane_y + random.uniform(-18.0, 18.0)
            self.behavior_timer = random.uniform(0.55, 1.0)
        elif self.behavior_mode == "flank":
            self.roam_target_x = target_snapshot.x + (facing_to_target * random.uniform(220.0, 520.0))
            self.roam_target_lane = target_snapshot.lane_y + random.uniform(-40.0, 40.0)
            self.behavior_timer = random.uniform(0.8, 1.4)
        elif self.behavior_mode == "retreat":
            self.roam_target_x = self_snapshot.x - (facing_to_target * random.uniform(260.0, 620.0))
            self.roam_target_lane = self_snapshot.lane_y + random.uniform(-60.0, 60.0)
            self.behavior_timer = random.uniform(0.65, 1.15)
        elif self.behavior_mode == "dodge":
            self.roam_target_x = self_snapshot.x + (-facing_to_target * random.uniform(200.0, 420.0))
            self.roam_target_lane = self_snapshot.lane_y + random.uniform(-70.0, 70.0)
            self.behavior_timer = random.uniform(0.45, 0.85)
        else:
            self.roam_target_x = self_snapshot.x + random.uniform(-420.0, 420.0)
            self.roam_target_lane = self_snapshot.lane_y + random.uniform(-88.0, 88.0)
            self.behavior_timer = random.uniform(0.6, 1.1)
        self.last_mode_was_close = abs_dx < 180.0

    def build_input(self, self_snapshot: FighterSnapshot, target_snapshot: FighterSnapshot) -> FighterInput:
        result = FighterInput()
        dx = target_snapshot.x - self_snapshot.x
        dy = target_snapshot.lane_y - self_snapshot.lane_y
        abs_dx = abs(dx)
        same_lane = abs(dy) <= 28.0
        facing_right = dx >= 0
        target_attacking = target_snapshot.state in COMBAT_ATTACK_STATES or target_snapshot.state == "jump_throw"
        facing_to_target = 1 if facing_right else -1

        if self.throw_prep and self_snapshot.state == "lift_heavy":
            result.attack_pressed = True
            result.attack_just_pressed = True
            self.throw_prep = False
            self.throw_cooldown = 2.0
            self.attack_cooldown = 0.9
            return result

        if self_snapshot.state == "lift_heavy":
            result.attack_pressed = True
            result.attack_just_pressed = True
            return result

        if target_attacking and same_lane and abs_dx < 95.0 and random.random() < 0.18:
            result.block_pressed = True
            result.block_just_pressed = not self.block_hold
            self.block_hold = True
            return result
        self.block_hold = False

        if same_lane and abs_dx < 80.0 and self.throw_cooldown == 0.0 and not self.throw_prep and self_snapshot.state not in {"block", "block_break", "throw_heavy"}:
            result.lift_just_pressed = True
            self.throw_prep = True
            return result

        self._pick_behavior(self_snapshot, target_snapshot, dx, dy, same_lane, target_attacking)

        if abs_dx > 260.0 and self.jump_cooldown == 0.0 and self_snapshot.z == 0 and target_snapshot.z == 0 and self.behavior_mode == "jump":
            result.jump_just_pressed = True
            self.jump_cooldown = 1.8
            return result

        desired_x = self.roam_target_x
        desired_lane = self.roam_target_lane
        if self.behavior_mode == "advance":
            desired_x = target_snapshot.x - (facing_to_target * 150.0)
        elif self.behavior_mode == "pressure":
            desired_x = target_snapshot.x - (facing_to_target * 80.0)
        elif self.behavior_mode == "flank":
            desired_x = self.roam_target_x
        elif self.behavior_mode == "retreat":
            desired_x = self.roam_target_x
        elif self.behavior_mode == "dodge":
            desired_x = self.roam_target_x
        elif self.behavior_mode == "defend":
            desired_x = self_snapshot.x

        if self.turn_lock == 0.0 and abs(desired_x - self_snapshot.x) > 64.0:
            if desired_x > self_snapshot.x:
                result.right = True
                if self_snapshot.facing != 1:
                    self.turn_lock = 0.28
            else:
                result.left = True
                if self_snapshot.facing != -1:
                    self.turn_lock = 0.28
        elif abs(desired_x - self_snapshot.x) <= 64.0 and self.behavior_mode in {"retreat", "dodge"}:
            if facing_right:
                result.left = True
            else:
                result.right = True

        lane_delta = desired_lane - self_snapshot.lane_y
        if abs(lane_delta) > 18.0:
            if lane_delta > 0:
                result.down = True
            else:
                result.up = True

        if self.behavior_mode in {"pressure", "flank"} and abs_dx < 260.0:
            result.run = True
        elif abs_dx > 340.0:
            result.run = True

        if self.behavior_mode == "dodge" and self_snapshot.z == 0 and self.jump_cooldown == 0.0:
            result.jump_just_pressed = True
            self.jump_cooldown = 1.2
            return result

        if target_attacking and same_lane and abs_dx < 115.0 and random.random() < 0.4:
            result.block_pressed = True
            result.block_just_pressed = not self.block_hold
            self.block_hold = True
            return result
        self.block_hold = False

        if self.behavior_mode == "jump" and self_snapshot.z == 0 and self.jump_cooldown == 0.0 and abs_dx > 120.0:
            result.jump_just_pressed = True
            self.jump_cooldown = 1.6
            return result

        if self.attack_cooldown == 0.0 and same_lane and abs_dx < 185.0 and self_snapshot.state not in {"basic_attack", "heavy_attack", "sprint_punch", "throw", "throw_heavy", "lift_heavy"}:
            result.attack_just_pressed = True
            self.attack_cooldown = 0.85

        return result


class ArrowProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int, style: str = "basic") -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.origin_y = float(y)
        self.origin_x = float(x)
        self.facing = 1 if facing >= 0 else -1
        self.style = style
        self.speed_x = 1040.0
        self.ascend_speed = 620.0
        self.straight_speed = 70.0
        self.fall_speed = 160.0
        self.gravity = 520.0
        self.max_distance = 3920.0
        self.damage = 1
        self.frame_timer = 0.0
        self.frame_index = 0
        self.phase = "fly"
        self.can_damage = True
        self.finished = False
        self.just_broke = False
        self.break_velocity_y = 0.0
        self.break_bounced = False
        arrows_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "arrow"
        fly_frames = _load_folder_frames(arrows_root / "arrow_fly")
        enchanted_frames = _load_folder_frames(arrows_root / "arrow_enchanted") if style == "enchanted" else []
        self.enchanted_launch_frames = enchanted_frames[:1]
        self.enchanted_loop_frames = enchanted_frames[1:] if len(enchanted_frames) > 1 else enchanted_frames
        self.enchanted_launch_done = False
        self.fly_frames = fly_frames or [pygame.Surface((12, 12), pygame.SRCALPHA)]
        self.break_frames = _load_folder_frames(arrows_root / "arrow_break")
        self.frames = self.fly_frames if self.fly_frames else [pygame.Surface((12, 12), pygame.SRCALPHA)]
        self.ground_y = GROUND_Y + owner.lane_y - 18.0

    def _start_break(self) -> None:
        if self.phase == "break":
            return
        self.phase = "break"
        self.just_broke = True
        self.can_damage = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.frames = self.break_frames or self.frames
        self.break_velocity_y = -180.0
        self.break_bounced = False

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        if self.phase == "fly":
            self.x += self.facing * self.speed_x * dt
            if self.style == "enchanted":
                if not self.enchanted_launch_done:
                    self.frames = self.enchanted_launch_frames or self.enchanted_loop_frames or self.frames
                    self.frame_timer += dt
                    while self.frame_timer >= 0.08:
                        self.frame_timer -= 0.08
                        self.enchanted_launch_done = True
                        self.frames = self.enchanted_loop_frames or self.enchanted_launch_frames or self.frames
                        self.frame_index = 0
                        break
                else:
                    self.frames = self.enchanted_loop_frames or self.enchanted_launch_frames or self.frames
                    self.frame_timer += dt
                    while self.frame_timer >= 0.08:
                        self.frame_timer -= 0.08
                        self.frame_index = (self.frame_index + 1) % max(1, len(self.frames))
            else:
                self.frames = self.fly_frames
                if self.frame_index <= 0:
                    self.y -= self.ascend_speed * dt
                elif self.frame_index == 1:
                    self.y -= self.straight_speed * dt
                else:
                    self.y += self.fall_speed * dt
                    self.fall_speed += self.gravity * dt
                self.frame_timer += dt
                while self.frame_timer >= 0.08:
                    self.frame_timer -= 0.08
                    if self.frame_index < len(self.frames) - 1:
                        self.frame_index += 1
                if self.y >= self.ground_y:
                    self.y = self.ground_y
                    self._start_break()
            if self.style != "enchanted" and abs(self.x - self.origin_x) >= self.max_distance:
                self._start_break()
        else:
            self.y += self.break_velocity_y * dt
            self.break_velocity_y += 560.0 * dt
            if self.y >= self.ground_y:
                self.y = self.ground_y
                if not self.break_bounced:
                    self.break_bounced = True
                    self.break_velocity_y = -self.break_velocity_y * 0.45
                elif self.frame_index >= len(self.frames) - 1:
                    self.finished = True
            self.frame_timer += dt
            while self.frame_timer >= 0.05:
                self.frame_timer -= 0.05
                self.frame_index += 1
                if self.frame_index >= len(self.break_frames):
                    self.frame_index = len(self.break_frames) - 1 if self.break_frames else 0
                    if self.break_bounced:
                        self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class LaserProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.origin_x = float(x)
        self.origin_y = float(y)
        self.beam_y = owner.world_hitbox_rect().centery
        self.x = float(x)
        self.y = self.beam_y
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = 1320.0
        self.damage = 1
        self.can_damage = True
        self.finished = False
        self.phase = "fly"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.hit_timer = 0.0
        self.impact_x = self.x
        self.impact_y = self.y
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "laser"
        self.point_frames = self._load_frames(root / "lazer_point")[:1]
        self.hit_frames = self._load_frames(root / "lazer_hit")
        self.frames = [self.point_frames[0]] if self.point_frames else [pygame.Surface((12, 12), pygame.SRCALPHA)]

    def _load_frames(self, folder: Path) -> list[pygame.Surface]:
        frames: list[pygame.Surface] = []
        if not folder.exists():
            return frames
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".png", ".bmp"}:
                continue
            frame = pygame.image.load(str(path)).convert()
            frame.set_colorkey((0, 0, 0))
            frames.append(frame)
        return frames

    def _load_first_frame(self, folder: Path) -> pygame.Surface | None:
        frames = self._load_frames(folder)
        if frames:
            return frames[0]
        return None

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.hit_timer = 0.0
        self.frame_timer = 0.0
        self.frame_index = 0
        self.impact_x = self.x
        self.impact_y = self.beam_y
        self.frames = self.hit_frames or self.frames

    def rect(self) -> pygame.Rect:
        if self.phase == "fly":
            frame = self.frames[self.frame_index]
            return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.beam_y - (frame.get_height() / 2)), frame.get_width(), frame.get_height())

        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.impact_x - frame.get_width() / 2), int(self.impact_y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        if self.phase == "fly":
            self.x += self.facing * self.speed_x * dt
            self.frame_timer += dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % max(1, len(self.frames))
        else:
            self.hit_timer += dt
            self.frame_timer += dt
            while self.frame_timer >= 0.05:
                self.frame_timer -= 0.05
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.frame_index = len(self.frames) - 1 if self.frames else 0
                    self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        if self.phase == "fly":
            frame = self.frames[self.frame_index]
            if self.facing < 0:
                frame = pygame.transform.flip(frame, True, False)
            surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.beam_y - frame.get_height() / 2)))
            return

        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.impact_x - camera_x - frame.get_width() / 2), int(self.impact_y - frame.get_height() / 2)))


class BatSummonProjectile:
    def __init__(self, owner: Fighter, target: Fighter | None, x: float, y: float, facing: int, summon_index: int) -> None:
        self.owner = owner
        self.target = target
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.summon_index = summon_index
        self.speed_x = 980.0
        self.speed_y = 28.0
        self.damage = 1
        self.can_damage = True
        self.finished = False
        self.phase = "fly"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.life_timer = 0.0
        self.wobble_phase = random.uniform(0.0, math.tau)
        self.roam_phase = random.uniform(0.0, math.tau)
        self.targeting_factor = 0.5
        self.swing_width = 360.0
        self.impact_x = self.x
        self.impact_y = self.y
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "summons" / "bats"
        self.fly_frames = self._load_frames(root / "bats_flying")
        self.hit_frames = self._load_frames(root / "bats_hit")
        self.frames = self.fly_frames or [pygame.Surface((18, 12), pygame.SRCALPHA)]

    def _load_frames(self, folder: Path) -> list[pygame.Surface]:
        frames: list[pygame.Surface] = []
        if not folder.exists():
            return frames
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".png", ".bmp"}:
                continue
            frame = pygame.image.load(str(path)).convert()
            frame.set_colorkey((0, 0, 0))
            frames.append(frame)
        return frames

    def _start_burst(self) -> None:
        if self.phase == "hit":
            return
        self.phase = "hit"
        self.can_damage = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.impact_x = self.x
        self.impact_y = self.y
        self.frames = self.hit_frames or self.frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        if self.phase == "fly":
            return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())
        return pygame.Rect(int(self.impact_x - frame.get_width() / 2), int(self.impact_y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        self.life_timer += dt
        if self.phase == "fly":
            if self.life_timer >= 4.0:
                self._start_burst()
                return

            if self.target is not None and not self.target.is_dead:
                target_rect = self.target.world_hitbox_rect()
                target_x = target_rect.centerx
                target_y = target_rect.centery - 28
                dx = target_x - self.x
                dy = target_y - self.y
                distance = max(1.0, math.hypot(dx, dy))
                self.facing = 1 if dx >= 0 else -1
                homing_strength = (0.02 + min(0.03, distance / 6500.0)) * self.targeting_factor
                swing_phase = self.life_timer * 2.4 + self.wobble_phase
                vertical_ratio = min(1.0, abs(dy) / 90.0)
                swing_width = self.swing_width + (self.swing_width * 1.1 * vertical_ratio)
                swing_bias = math.copysign(self.swing_width * (0.75 + (0.35 * vertical_ratio)), dy if dy != 0 else self.facing)
                swing_x = (math.sin(swing_phase) * swing_width) + swing_bias
                swing_y = math.cos(swing_phase) * self.speed_y * (0.10 + (0.10 * vertical_ratio))
                self.x += (self.facing * self.speed_x * 0.18 + swing_x) * dt
                self.y += (((dy / distance) * self.speed_y * homing_strength) + swing_y) * dt
            else:
                roam_phase = self.life_timer * 2.0 + self.roam_phase
                swing_x = (math.sin(roam_phase) * self.swing_width * 1.35) + (self.facing * self.swing_width * 0.7)
                self.x += (self.facing * self.speed_x * 0.22 + swing_x) * dt
                self.y += math.sin(roam_phase * 0.85) * self.speed_y * 0.18 * dt
            self.frame_timer += dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % max(1, len(self.frames))
            if self.life_timer >= 12.0:
                self.finished = True
        else:
            self.frame_timer += dt
            while self.frame_timer >= 0.06:
                self.frame_timer -= 0.06
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.frame_index = len(self.frames) - 1 if self.frames else 0
                    self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        if self.phase == "fly":
            surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))
            return
        surface.blit(frame, (int(self.impact_x - camera_x - frame.get_width() / 2), int(self.impact_y - frame.get_height() / 2)))


class BallProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int, ball_index: int, frame_scheme: str = "three_stage") -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = 110.0
        self.max_speed_x = 560.0
        self.acceleration_x = 62.0
        self.damage = 1
        self.phase = "fly"
        self.can_damage = True
        self.finished = False
        self.just_burst = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.use_fast_frames = False
        self.fly_time = 0.0
        self.frame_scheme = frame_scheme
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "blue_ball" / f"ball_{ball_index}"
        self.slow_frames = self._load_frames(root / "davis_ball_slow")
        self.fast_frames = self._load_frames(root / "davis_ball_fast")
        self.burst_frames = self._load_frames(root.parent / "ball_burst")
        self.frames = self.slow_frames or self.fast_frames or [pygame.Surface((16, 16), pygame.SRCALPHA)]

    def _load_frames(self, folder: Path) -> list[pygame.Surface]:
        frames: list[pygame.Surface] = []
        if not folder.exists():
            return frames
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".png", ".bmp"}:
                continue
            frame = pygame.image.load(str(path)).convert()
            frame.set_colorkey((0, 0, 0))
            frames.append(frame)
        return frames

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.just_burst = True
        self.frame_timer = 0.0
        self.frame_index = 0
        self.frames = self.burst_frames or self.frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        if self.phase == "fly":
            self.fly_time += dt
            speed_gain = self.acceleration_x * dt * (1.0 + (self.fly_time * 2.5))
            self.speed_x = min(self.max_speed_x, self.speed_x + speed_gain)
            self.use_fast_frames = self.speed_x >= 180.0 and bool(self.fast_frames)
            self.frames = self.fast_frames if self.use_fast_frames else (self.slow_frames or self.fast_frames or self.frames)
            self.x += self.facing * self.speed_x * dt
        else:
            self.frame_timer += dt
            while self.frame_timer >= 0.05:
                self.frame_timer -= 0.05
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.frame_index = len(self.frames) - 1 if self.frames else 0
                    self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class DavisBallProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = 240.0
        self.max_speed_x = 980.0
        self.acceleration_x = 180.0
        self.damage = 1
        self.phase = "fly"
        self.can_damage = True
        self.finished = False
        self.just_burst = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.fly_time = 0.0
        self.frame_mode = "slow"
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "davis_ball"
        self.slow_frames = self._load_frames(root / "davis_ball_slow")
        self.medium_frames = self._load_frames(root / "davis_ball_medium")
        self.fast_frames = self._load_frames(root / "davis_ball_fast")
        self.burst_frames = self._load_frames(root / "davis_ball_burst")
        self.frames = self.slow_frames or self.medium_frames or self.fast_frames or [pygame.Surface((16, 16), pygame.SRCALPHA)]

    def _load_frames(self, folder: Path) -> list[pygame.Surface]:
        frames: list[pygame.Surface] = []
        if not folder.exists():
            return frames
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".png", ".bmp"}:
                continue
            frame = pygame.image.load(str(path)).convert()
            frame.set_colorkey((0, 0, 0))
            frames.append(frame)
        return frames

    def _frames_for_mode(self, mode: str) -> list[pygame.Surface]:
        if mode == "slow":
            return self.slow_frames or self.medium_frames or self.fast_frames
        if mode == "medium":
            return self.medium_frames or self.fast_frames or self.slow_frames
        return self.fast_frames or self.medium_frames or self.slow_frames

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.just_burst = True
        self.frame_timer = 0.0
        self.frame_index = 0
        self.frames = self.burst_frames or self.frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        if self.phase == "fly":
            self.fly_time += dt
            speed_gain = self.acceleration_x * dt * (1.0 + (self.fly_time * 2.2))
            self.speed_x = min(self.max_speed_x, self.speed_x + speed_gain)
            if self.frame_scheme == "two_stage":
                mode = "slow" if self.speed_x < 480.0 else "fast"
            elif self.speed_x < 380.0:
                mode = "slow"
            elif self.speed_x < 700.0:
                mode = "medium"
            else:
                mode = "fast"
            if mode != self.frame_mode:
                self.frame_mode = mode
                self.frame_index = 0
                self.frame_timer = 0.0
            self.frames = self._frames_for_mode(mode) or self.frames
            self.frame_timer += dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % max(1, len(self.frames))
            self.x += self.facing * self.speed_x * dt
        else:
            self.frame_timer += dt
            while self.frame_timer >= 0.05:
                self.frame_timer -= 0.05
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.frame_index = len(self.frames) - 1 if self.frames else 0
                    self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class DenisOrbProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.damage = 1
        self.can_damage = True
        self.finished = False
        self.phase = "fly"
        self.just_burst = False
        self.stage_timer = 0.0
        self.frame_timer = 0.0
        self.frame_index = 0
        self.stage_index = 0
        self.speed_by_stage = [420.0, 620.0, 860.0, 1120.0]
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "denis_orb"
        self.stage_frames = [
            self._load_frames(root / "1"),
            self._load_frames(root / "2"),
            self._load_frames(root / "3"),
            self._load_frames(root / "4"),
        ]
        self.burst_frames = self._load_frames(root / "burst")
        self.frames = self.stage_frames[0] or [pygame.Surface((16, 16), pygame.SRCALPHA)]

    def _load_frames(self, folder: Path) -> list[pygame.Surface]:
        frames: list[pygame.Surface] = []
        if not folder.exists():
            return frames
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".png", ".bmp"}:
                continue
            frame = pygame.image.load(str(path)).convert()
            frame.set_colorkey((0, 0, 0))
            frames.append(frame)
        return frames

    def _stage_frames(self, stage_index: int) -> list[pygame.Surface]:
        if stage_index < 0:
            stage_index = 0
        if stage_index >= len(self.stage_frames):
            stage_index = len(self.stage_frames) - 1
        return self.stage_frames[stage_index] or self.frames

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.just_burst = True
        self.frame_timer = 0.0
        self.frame_index = 0
        self.frames = self.burst_frames or self.frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        if self.phase == "fly":
            self.stage_timer += dt
            self.stage_index = min(3, int(self.stage_timer))
            self.speed_x = self.speed_by_stage[self.stage_index]
            self.frames = self._stage_frames(self.stage_index)
            self.frame_timer += dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % max(1, len(self.frames))
            self.x += self.facing * self.speed_x * dt
        else:
            self.frame_timer += dt
            while self.frame_timer >= 0.05:
                self.frame_timer -= 0.05
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.frame_index = len(self.frames) - 1 if self.frames else 0
                    self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class DenisFollowOrbProjectile:
    def __init__(self, owner: Fighter, target: Fighter | None, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.target = target
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.damage = 1
        self.can_damage = False
        self.finished = False
        self.phase = "create"
        self.just_burst = False
        self.create_timer = 0.0
        self.stage_timer = 0.0
        self.frame_timer = 0.0
        self.frame_index = 0
        self.stage_index = 0
        self.speed_x = 0.0
        self.speed_y = 88.0
        self.speed_by_stage = [360.0, 520.0, 720.0, 940.0]
        self.targeting_factor = 0.7
        self.swing_width = 170.0
        self.wide_swing = False
        self.wobble_phase = random.uniform(0.0, math.tau)
        self.roam_phase = random.uniform(0.0, math.tau)
        self.impact_x = self.x
        self.impact_y = self.y
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "denis_follow_orb"
        self.create_frames = self._load_frames(root / "create")
        self.stage_frames = [
            self._load_frames(root / "slow"),
            self._load_frames(root / "medium"),
            self._load_frames(root / "fast"),
            self._load_frames(root / "fast"),
        ]
        self.burst_frames = self._load_frames(root / "burst")
        self.frames = self.create_frames or self.stage_frames[0] or [pygame.Surface((16, 16), pygame.SRCALPHA)]

    def _load_frames(self, folder: Path) -> list[pygame.Surface]:
        frames: list[pygame.Surface] = []
        if not folder.exists():
            return frames
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".png", ".bmp"}:
                continue
            frame = pygame.image.load(str(path)).convert()
            frame.set_colorkey((0, 0, 0))
            frames.append(frame)
        return frames

    def _frames_for_stage(self, stage_index: int) -> list[pygame.Surface]:
        stage_index = max(0, min(stage_index, len(self.stage_frames) - 1))
        return self.stage_frames[stage_index] or self.frames

    def _launch(self) -> None:
        if self.phase == "fly":
            return
        self.phase = "fly"
        self.can_damage = True
        self.stage_timer = 0.0
        self.frame_timer = 0.0
        self.frame_index = 0
        self.stage_index = 0
        self.frames = self._frames_for_stage(0) or self.frames

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.just_burst = True
        self.frame_timer = 0.0
        self.frame_index = 0
        self.impact_x = self.x
        self.impact_y = self.y
        self.frames = self.burst_frames or self.frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        if self.phase == "create":
            return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())
        if self.phase == "fly":
            return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())
        return pygame.Rect(int(self.impact_x - frame.get_width() / 2), int(self.impact_y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        if self.phase == "create":
            self.create_timer += dt
            self.frame_timer += dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % max(1, len(self.frames))
            if self.owner.is_dead:
                self.finished = True
                return
            if self.owner.state == "sp_vert_attack_2" and self.owner.animation_player.current_name == "sp_vert_attack_2" and self.owner.animation_player.frame_index >= 5:
                self._launch()
            elif self.create_timer >= 2.0:
                self.finished = True
            return

        if self.phase == "fly":
            self.stage_timer += dt
            self.stage_index = min(3, int(self.stage_timer))
            self.speed_x = self.speed_by_stage[self.stage_index]
            self.frames = self._frames_for_stage(self.stage_index)
            self.frame_timer += dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % max(1, len(self.frames))

            if self.target is not None and not self.target.is_dead:
                target_rect = self.target.world_hitbox_rect()
                target_x = target_rect.centerx
                target_y = target_rect.centery - 24
                dx = target_x - self.x
                dy = target_y - self.y
                distance = max(1.0, math.hypot(dx, dy))
                self.wide_swing = self.wide_swing or (self.stage_timer >= 0.75 and distance >= 520.0)
                self.facing = 1 if dx >= 0 else -1
                homing_strength = (0.022 + min(0.04, distance / 5600.0)) * self.targeting_factor
                swing_phase = self.stage_timer * 2.1 + self.wobble_phase
                vertical_ratio = min(1.0, abs(dy) / 64.0)
                swing_width = self.swing_width + (self.swing_width * (1.15 if self.wide_swing else 0.85) * vertical_ratio)
                swing_bias = math.copysign(self.swing_width * ((0.55 if not self.wide_swing else 0.92) + 0.5 * vertical_ratio), dy if dy != 0 else self.facing)
                swing_x = (math.sin(swing_phase) * swing_width) + swing_bias
                swing_y = math.cos(swing_phase * (1.18 if self.wide_swing else 1.08)) * self.speed_y * (0.26 + (0.24 * vertical_ratio))
                swing_y += math.sin(swing_phase * 0.5) * self.speed_y * (0.18 if self.wide_swing else 0.10)
                self.x += (self.facing * self.speed_x * 0.18 + swing_x) * dt
                self.y += (((dy / distance) * self.speed_y * homing_strength * (2.4 if self.wide_swing else 1.8)) + swing_y) * dt
            else:
                roam_phase = self.stage_timer * 1.9 + self.roam_phase
                self.wide_swing = True
                swing_x = (math.sin(roam_phase) * self.swing_width * 1.65) + (self.facing * self.swing_width * 0.82)
                self.x += (self.facing * self.speed_x * 0.22 + swing_x) * dt
                self.y += math.sin(roam_phase * 1.25) * self.speed_y * 0.58 * dt
                self.y += math.cos(roam_phase * 0.63) * self.speed_y * 0.18 * dt

            if self.stage_timer >= 12.0:
                self.finished = True
            return

        self.frame_timer += dt
        while self.frame_timer >= 0.05:
            self.frame_timer -= 0.05
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                self.frame_index = len(self.frames) - 1 if self.frames else 0
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        if self.phase == "fly":
            surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))
            return
        if self.phase == "create":
            surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))
            return
        surface.blit(frame, (int(self.impact_x - camera_x - frame.get_width() / 2), int(self.impact_y - frame.get_height() / 2)))


class BladeSwipeProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = 720.0
        self.damage = 1
        self.can_damage = True
        self.finished = False
        self.frame_timer = 0.0
        self.frame_index = 0
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "blade_swipe"
        self.frames = self._load_frames(root) or [pygame.Surface((64, 48), pygame.SRCALPHA)]

    def _load_frames(self, folder: Path) -> list[pygame.Surface]:
        frames: list[pygame.Surface] = []
        if not folder.exists():
            return frames
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".png", ".bmp"}:
                continue
            frame = pygame.image.load(str(path)).convert()
            frame.set_colorkey((0, 0, 0))
            frame = pygame.transform.scale(frame, (int(frame.get_width() * 2.0), int(frame.get_height() * 2.0)))
            frames.append(frame)
        return frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        while self.frame_timer >= 0.05:
            self.frame_timer -= 0.05
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                self.frame_index = len(self.frames) - 1 if self.frames else 0
                self.finished = True
                break
        self.x += self.facing * self.speed_x * dt

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class FireballProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.origin_x = float(x)
        self.facing = 1 if facing >= 0 else -1
        self.damage = 1
        self.can_damage = True
        self.finished = False
        self.just_burst = False
        self.phase = "fly"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.speed_x = 700.0
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "fireball"
        self.travel_frames = _load_folder_frames(root / "fireball_travel")
        self.hit_frames = _load_folder_frames(root / "fireball_hit")
        self.frames = self.travel_frames or [pygame.Surface((24, 24), pygame.SRCALPHA)]

    def _start_hit(self) -> None:
        if self.phase == "hit":
            return
        self.phase = "hit"
        self.can_damage = False
        self.just_burst = True
        self.frame_timer = 0.0
        self.frame_index = 0
        self.frames = self.hit_frames or self.frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        if self.phase == "fly":
            self.x += self.facing * self.speed_x * dt
            self.frame_timer += dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % max(1, len(self.frames))
        else:
            self.frame_timer += dt
            while self.frame_timer >= 0.05:
                self.frame_timer -= 0.05
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.frame_index = len(self.frames) - 1 if self.frames else 0
                    self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class FireBreathProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.origin_x = float(x)
        self.facing = 1 if facing >= 0 else -1
        self.damage = 1
        self.can_damage = True
        self.finished = False
        self.just_impact = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.speed_x = 120.0
        self.max_distance = 120.0
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "fire_breath"
        self.frames = _load_folder_frames(root) or [pygame.Surface((28, 18), pygame.SRCALPHA)]

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        self.x += self.facing * self.speed_x * dt
        if abs(self.x - self.origin_x) >= self.max_distance:
            self.finished = True
        self.frame_timer += dt
        while self.frame_timer >= 0.08:
            self.frame_timer -= 0.08
            self.frame_index = (self.frame_index + 1) % max(1, len(self.frames))

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class WindProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.can_damage = True
        self.finished = False
        self.phase = "play"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.impact_x = self.x
        self.impact_y = self.y
        self.hit_targets: set[int] = set()
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "wind"
        self.frames = _load_folder_frames(root) or [pygame.Surface((40, 24), pygame.SRCALPHA)]
        self.scale = 2.0

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        width = int(frame.get_width() * self.scale)
        height = int(frame.get_height() * self.scale)
        return pygame.Rect(int(self.x - width / 2), int(self.y - height / 2), width, height)

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        while self.frame_timer >= 0.07:
            self.frame_timer -= 0.07
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                self.frame_index = len(self.frames) - 1 if self.frames else 0
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        width = int(frame.get_width() * self.scale)
        height = int(frame.get_height() * self.scale)
        scaled = pygame.transform.scale(frame, (width, height))
        surface.blit(scaled, (int(self.x - camera_x - width / 2), int(self.y - height / 2)))


class FireTrailEffect:
    def __init__(self, owner: Fighter, x: float, y: float) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.damage = 1
        self.can_damage = True
        self.finished = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.hit_targets: set[int] = set()
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "fire_trail"
        self.frames = _load_folder_frames(root) or [pygame.Surface((48, 24), pygame.SRCALPHA)]
        self.scale = 1.75

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        width = int(frame.get_width() * self.scale)
        height = int(frame.get_height() * self.scale)
        return pygame.Rect(int(self.x - width / 2), int(self.y - height / 2), width, height)

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        while self.frame_timer >= 0.05:
            self.frame_timer -= 0.05
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                self.frame_index = len(self.frames) - 1 if self.frames else 0
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        width = int(frame.get_width() * self.scale)
        height = int(frame.get_height() * self.scale)
        scaled = pygame.transform.scale(frame, (width, height))
        surface.blit(scaled, (int(self.x - camera_x - width / 2), int(self.y - height / 2)))


class FireExplosionEffect:
    def __init__(self, owner: Fighter, x: float, y: float) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.damage = 1
        self.can_damage = True
        self.finished = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.hit_targets: set[int] = set()
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "explode"
        self.frames = _load_folder_frames(root) or [pygame.Surface((72, 72), pygame.SRCALPHA)]
        self.scale = 2.5

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        width = int(frame.get_width() * self.scale)
        height = int(frame.get_height() * self.scale)
        return pygame.Rect(int(self.x - width / 2), int(self.y - height / 2), width, height)

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        while self.frame_timer >= 0.05:
            self.frame_timer -= 0.05
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                self.frame_index = len(self.frames) - 1 if self.frames else 0
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        width = int(frame.get_width() * self.scale)
        height = int(frame.get_height() * self.scale)
        scaled = pygame.transform.scale(frame, (width, height))
        surface.blit(scaled, (int(self.x - camera_x - width / 2), int(self.y - height / 2)))


class BattleScene:
    def __init__(self, character_name: str = "bandit") -> None:
        self.font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 24)
        self.pause_font = pygame.font.Font(None, 54)
        self.projectiles: list[object] = []
        self.paused = False
        stage_root = Path(__file__).resolve().parents[2] / "assets" / "maps" / "Forrest"
        sounds_root = Path(__file__).resolve().parents[2] / "assets" / "sounds"
        self.stage = ForestStage(stage_root)
        self.audio = AudioBank(sounds_root)
        x_bounds = (self.stage.play_min_x, self.stage.play_max_x)
        start_x = SCREEN_WIDTH / 2
        self.fighter = Fighter(FighterConfig(character_name, CHARACTERS[character_name]), (start_x, 0), x_bounds=x_bounds)
        self.enemy = Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (start_x + 220.0, 0), x_bounds=x_bounds)
        self.enemy.max_health = 8
        self.enemy.health = 8
        self.enemy.controls_enabled = True
        self.enemy_brain = BanditBrain()
        self.victory_played = False
        self.victory_played = False

    def _draw_speech_bubble(self, surface: pygame.Surface, fighter: Fighter, camera_x: float) -> None:
        if not fighter.speech_text:
            return
        text = self.small_font.render(fighter.speech_text, True, (24, 24, 24))
        bubble_width = max(text.get_width() + 24, 156)
        bubble_height = text.get_height() + 20
        bubble = pygame.Surface((bubble_width, bubble_height + 14), pygame.SRCALPHA)
        bubble_rect = bubble.get_rect()
        white = (255, 255, 255)
        outline = (32, 32, 32)
        pygame.draw.ellipse(bubble, white, bubble_rect.inflate(-6, -14))
        pygame.draw.ellipse(bubble, outline, bubble_rect.inflate(-6, -14), 2)
        tail = [
            (bubble_rect.centerx - 10, bubble_rect.bottom - 12),
            (bubble_rect.centerx + 8, bubble_rect.bottom - 12),
            (bubble_rect.centerx - 2, bubble_rect.bottom + 2),
        ]
        pygame.draw.polygon(bubble, white, tail)
        pygame.draw.polygon(bubble, outline, tail, 2)
        bubble.blit(text, text.get_rect(center=(bubble_rect.centerx, bubble_rect.centery - 2)))
        bubble_pos = bubble.get_rect(midbottom=(fighter.world_hitbox_rect().centerx - int(camera_x), fighter.world_hitbox_rect().top - 10))
        surface.blit(bubble, bubble_pos)

    def _handle_combat(self) -> None:
        for attacker, defender in ((self.fighter, self.enemy), (self.enemy, self.fighter)):
            if attacker.is_dead or defender.is_dead:
                continue
            if attacker.state not in (COMBAT_ATTACK_STATES | {"jump_throw"}):
                continue
            if attacker.name == "hunter" and attacker.state == "basic_attack":
                continue
            if attacker.name == "henry" and attacker.state in {"basic_attack", "sp_move_attack_1"}:
                continue
            if attacker.name == "bat" and attacker.state in {"sp_move_attack_2", "sp_vert_attack_2"}:
                continue
            if attacker.name == "davis" and attacker.state == "sp_move_attack_1":
                continue
            if attacker.name == "denis" and attacker.state == "sp_move_attack_1":
                continue
            if attacker.name == "denis" and attacker.state == "sp_vert_attack_2":
                continue
            if attacker.name == "firen" and attacker.state in {"sp_move_attack_1", "sp_move_attack_2", "sp_vert_attack_1", "sp_vert_attack_2"}:
                continue
            if attacker.state == "jump_throw" and not attacker.jump_attack_active:
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
            attack_range = 72
            if attacker.name == "dark_bat" and attacker.state == "sp_move_attack_1":
                attack_range = 132
            if attacker.name == "dark_bat" and attacker.state == "jump_throw" and attacker.jump_attack_active:
                attack_range = 96
            if not attacker.world_hitbox_rect().inflate(attack_range, 0).colliderect(defender.world_hitbox_rect()):
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
            if not defender.is_dead:
                if attacker.state == "jump_throw" and attacker.jump_attack_active:
                    defender._start_knockdown()
                elif attacker.state == "sp_vert_attack_1":
                    if attacker.name in {"deep", "template"}:
                        defender._start_launch_knockdown()
                    elif attacker.name == "davis":
                        defender._start_knockdown()
                    else:
                        defender._start_knockdown()
            if attacker.name == "dark_bat" and attacker.state in {"sp_move_attack_1", "jump_throw"}:
                self.audio.play("sword_cut")
            elif attacker.name in {"deep", "armored_bandit"} and attacker.state in {"sp_vert_attack_1", "sp_vert_attack_2", "sp_move_attack_2"}:
                self.audio.play("sword_cut")
            elif attacker.name in {"deep", "armored_bandit"}:
                self.audio.play("sword_cut")
            else:
                self.audio.play("hit_success")

    def _handle_audio(self, dt: float) -> None:
        fighters = [self.fighter, self.enemy]

        for fighter in fighters:
            if fighter.hunter_draw_arrow_sfx_pending:
                self.audio.play("draw_arrow")
                fighter.hunter_draw_arrow_sfx_pending = False
            if fighter.hunter_shoot_arrow_sfx_pending:
                self.audio.play("shoot_arrow")
                fighter.hunter_shoot_arrow_sfx_pending = False
            if fighter.deep_sword_swing_sfx_pending:
                self.audio.play("sword_swing")
                fighter.deep_sword_swing_sfx_pending = False
            if fighter.armored_bandit_sword_swing_sfx_pending:
                self.audio.play("sword_swing")
                fighter.armored_bandit_sword_swing_sfx_pending = False
            if fighter.dark_bat_sword_swing_sfx_pending:
                self.audio.play("sword_swing")
                fighter.dark_bat_sword_swing_sfx_pending = False
            if fighter.dark_bat_shadow_step_sfx_pending:
                self.audio.play("shadow_step")
                fighter.dark_bat_shadow_step_sfx_pending = False
            if fighter.template_uppercut_shear_sfx_pending:
                self.audio.play("uppercut_shear")
                fighter.template_uppercut_shear_sfx_pending = False
            if fighter.davis_uppercut_shear_sfx_pending:
                self.audio.play("davis_uppercut")
                self.audio.play("uppercut_shear")
                fighter.davis_uppercut_shear_sfx_pending = False
            if fighter.denis_follow_orb_create_sfx_pending:
                self.audio.play("denis_orb_follow_create")
                fighter.denis_follow_orb_create_sfx_pending = False
            while fighter.denis_sp_vert_attack_1_sound_pending:
                self.audio.play(fighter.denis_sp_vert_attack_1_sound_pending.pop(0))
            while fighter.denis_sp_move_attack_2_sound_pending:
                self.audio.play(fighter.denis_sp_move_attack_2_sound_pending.pop(0))
            if fighter.bat_shadow_step_sfx_pending:
                self.audio.play("shadow_step")
                fighter.bat_shadow_step_sfx_pending = False
            if fighter.bat_lazer_sfx_pending:
                self.audio.play("lazer")
                fighter.bat_lazer_sfx_pending = False
            if fighter.bat_summon_bats_sfx_pending:
                self.audio.play("summon_bats")
                fighter.bat_summon_bats_sfx_pending = False
            if fighter.henry_wind_sfx_pending:
                self.audio.play("henry_wind")
                fighter.henry_wind_sfx_pending = False
            if fighter.ice_break_sfx_pending:
                self.audio.play("ice_break")
                fighter.ice_break_sfx_pending = False
            if fighter.fire_knock_sfx_pending:
                self.audio.play("fire_knock")
                self.audio.play("knockdown")
                fighter.fire_knock_sfx_pending = False
            if fighter.just_knocked_down:
                if fighter.state != "knocked_fire":
                    self.audio.play("knockdown")
            if fighter.just_jumped:
                self.audio.play("jump_throw")
            if fighter.just_landed:
                self.audio.play("jump_land")

            if fighter.z == 0 and fighter.state in {"walk", "run"}:
                if fighter.step_cycle_timer == 0.0:
                    self.audio.play_footstep()
                    fighter.step_cycle_timer = 0.22 if fighter.state == "walk" else 0.16
            else:
                fighter.step_cycle_timer = 0.0

        if self.enemy.is_dead and not self.victory_played:
            self.audio.play("win")
            self.victory_played = True

    def _spawn_hunter_projectile(self, fighter: Fighter) -> None:
        if fighter.name not in {"hunter", "henry"}:
            return
        if fighter.state not in {"basic_attack", "jump_throw"} and not (fighter.name == "henry" and fighter.state == "sp_move_attack_1"):
            return
        if not fighter.attack_started or fighter.attack_projectile_fired:
            return

        fighter.attack_projectile_fired = True
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 58.0
        style = fighter.hunter_projectile_style
        self.projectiles.append(ArrowProjectile(fighter, origin_x, origin_y, fighter.facing, style))
        if style == "enchanted":
            self.audio.play("arrow_enchanted_shot")
        else:
            fighter.hunter_shoot_arrow_sfx_pending = True

    def _spawn_template_projectile(self, fighter: Fighter) -> None:
        if fighter.name != "template":
            return
        if not fighter.state.startswith("sp_move_attack"):
            return
        if not fighter.attack_started or fighter.attack_projectile_fired:
            return

        fighter.attack_projectile_fired = True
        ball_index = fighter.next_special_move_projectile_index()
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 56.0
        self.projectiles.append(BallProjectile(fighter, origin_x, origin_y, fighter.facing, ball_index))
        self.audio.play("orb")
        fighter.special_move_projectile_timer = fighter.combat.get("special_projectile_interval", 0.2)

    def _spawn_denis_projectile(self, fighter: Fighter) -> None:
        if fighter.name != "denis" or fighter.state != "sp_move_attack_1":
            return

        current_name = fighter.animation_player.current_name
        if current_name not in {"sp_move_attack_1", "sp_move_attack_1_follow"}:
            return

        trigger_frames = {2, 7, 13, 16, 17}
        current_frame = fighter.animation_player.frame_index
        if current_frame not in trigger_frames:
            return

        if current_frame in fighter.denis_sp_move_attack_1_spawned_frames:
            return

        fighter.denis_sp_move_attack_1_spawned_frames.add(current_frame)
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 56.0
        self.projectiles.append(DenisOrbProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.audio.play("denis_ball")

    def _spawn_denis_follow_orb(self, fighter: Fighter) -> None:
        if fighter.name != "denis" or fighter.state != "sp_vert_attack_2":
            return
        if not fighter.denis_follow_orb_pending or fighter.attack_projectile_fired:
            return

        fighter.denis_follow_orb_pending = False
        fighter.attack_projectile_fired = True
        target = self.enemy if fighter is self.fighter else self.fighter
        if target is not None and target.is_dead:
            target = None
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.55)
        origin_y = fighter.world_hitbox_rect().bottom - 54.0
        self.projectiles.append(DenisFollowOrbProjectile(fighter, target, origin_x, origin_y, fighter.facing))

    def _spawn_davis_projectile(self, fighter: Fighter) -> None:
        if fighter.name != "davis" or fighter.davis_ball_projectiles_pending <= 0:
            return

        fighter.davis_ball_projectiles_pending -= 1
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 56.0
        self.projectiles.append(DavisBallProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.audio.play("orb")

    def _spawn_bat_laser(self, fighter: Fighter) -> None:
        if fighter.name not in {"bat", "dark_bat"} or fighter.state != "sp_move_attack_2" or fighter.attack_projectile_fired:
            return

        fighter.attack_projectile_fired = True
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = fighter.world_hitbox_rect().top + 12.0
        self.projectiles.append(LaserProjectile(fighter, origin_x, origin_y, fighter.facing))

    def _spawn_bat_summons(self, fighter: Fighter) -> None:
        if fighter.name == "bat":
            allowed_state = "sp_vert_attack_2"
        elif fighter.name == "dark_bat":
            allowed_state = "sp_vert_attack_1"
        else:
            return

        if fighter.state != allowed_state or fighter.attack_projectile_fired:
            return

        fighter.attack_projectile_fired = True
        if fighter is self.fighter:
            target = self.enemy if self.enemy is not None and not self.enemy.is_dead else None
        else:
            target = self.fighter if self.fighter is not None and not self.fighter.is_dead else None
        base_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.12)
        base_y = fighter.world_hitbox_rect().top + 28.0
        summon_count = 6 if fighter.name == "dark_bat" else 3
        for index in range(summon_count):
            offset_x = fighter.facing * (index - ((summon_count - 1) / 2.0)) * 28.0
            offset_y = (index - ((summon_count - 1) / 2.0)) * 16.0
            self.projectiles.append(BatSummonProjectile(fighter, target, base_x + offset_x, base_y + offset_y, fighter.facing, index))

    def _spawn_deep_projectile(self, fighter: Fighter) -> None:
        if fighter.name != "deep" or fighter.pending_projectile != "blade_swipe" or fighter.attack_projectile_fired:
            return
        fighter.attack_projectile_fired = True
        fighter.pending_projectile = None
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.55)
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 64.0
        self.projectiles.append(BladeSwipeProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.audio.play("blade_swipe_sound")

    def _spawn_firen_fireball(self, fighter: Fighter) -> None:
        if fighter.name != "firen":
            return
        while fighter.firen_fireball_projectiles_pending > 0:
            fighter.firen_fireball_projectiles_pending -= 1
            origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
            origin_y = GROUND_Y + fighter.lane_y - fighter.z - 54.0
            self.projectiles.append(FireballProjectile(fighter, origin_x, origin_y, fighter.facing))
            self.audio.play_fireball()

    def _spawn_firen_fire_breath(self, fighter: Fighter) -> None:
        if fighter.name != "firen":
            return
        while fighter.firen_fire_breath_projectiles_pending > 0:
            fighter.firen_fire_breath_projectiles_pending -= 1
            origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.40)
            origin_y = fighter.world_hitbox_rect().top + 54.0
            self.projectiles.append(FireBreathProjectile(fighter, origin_x, origin_y, fighter.facing))
            self.audio.play_fire_breath()

    def _spawn_henry_wind(self, fighter: Fighter) -> None:
        if fighter.name != "henry" or fighter.state != "sp_move_attack_2":
            return
        while fighter.henry_wind_projectiles_pending > 0:
            fighter.henry_wind_projectiles_pending -= 1
            fighter.attack_projectile_fired = True
            hitbox = fighter.world_hitbox_rect()
            offset_x = fighter.facing * (fighter.hitbox_size[0] * 0.48)
            origin_x = hitbox.centerx + offset_x
            origin_y = hitbox.bottom - 22.0
            self.projectiles.append(WindProjectile(fighter, origin_x, origin_y, fighter.facing))

    def _spawn_firen_fire_trail(self, fighter: Fighter) -> None:
        if fighter.name != "firen":
            return
        while fighter.firen_fire_trail_projectiles_pending > 0:
            fighter.firen_fire_trail_projectiles_pending -= 1
            hitbox = fighter.world_hitbox_rect()
            origin_x = float(hitbox.centerx)
            origin_y = float(hitbox.bottom - 12)
            self.projectiles.append(FireTrailEffect(fighter, origin_x, origin_y))

    def _spawn_firen_explosion(self, fighter: Fighter) -> None:
        if fighter.name != "firen":
            return
        while fighter.firen_fire_explosion_pending > 0:
            fighter.firen_fire_explosion_pending -= 1
            hitbox = fighter.world_hitbox_rect()
            origin_x = float(hitbox.centerx)
            origin_y = float(hitbox.centery)
            self.projectiles.append(FireExplosionEffect(fighter, origin_x, origin_y))

    def _update_projectiles(self, dt: float) -> None:
        focus_x = self.fighter.x
        player_margin = SCREEN_WIDTH * 0.3
        min_focus = self.fighter.x - player_margin
        max_focus = self.fighter.x + player_margin
        enemy_focus = (self.fighter.x + self.enemy.x) / 2
        focus_x = max(min_focus, min(max_focus, enemy_focus))
        camera_x = self.stage.camera_x(focus_x)
        visible_left = camera_x
        visible_right = camera_x + SCREEN_WIDTH
        for projectile in list(self.projectiles):
            projectile.update(dt)
            if getattr(projectile, "just_broke", False):
                self.audio.play("broken_arrow")
                projectile.just_broke = False
            if getattr(projectile, "just_burst", False):
                if isinstance(projectile, FireballProjectile):
                    self.audio.play_fireball()
                else:
                    self.audio.play("orb_burst")
                projectile.just_burst = False
            if getattr(projectile, "just_impact", False):
                projectile.just_impact = False
            if projectile.finished:
                self.projectiles.remove(projectile)
                continue
            if isinstance(projectile, (BallProjectile, DavisBallProjectile, DenisOrbProjectile, DenisFollowOrbProjectile)) and projectile.phase == "fly":
                if projectile.x <= visible_left or projectile.x >= visible_right:
                    projectile.x = max(visible_left, min(visible_right, projectile.x))
                    projectile._start_burst()
            if isinstance(projectile, LaserProjectile) and projectile.phase == "fly":
                if projectile.x <= visible_left or projectile.x >= visible_right:
                    projectile.x = max(visible_left, min(visible_right, projectile.x))
                    projectile._start_burst()
            if isinstance(projectile, FireballProjectile) and projectile.phase == "fly":
                if projectile.x <= visible_left or projectile.x >= visible_right:
                    projectile.x = max(visible_left, min(visible_right, projectile.x))
                    projectile._start_hit()
                    projectile.just_burst = False
                    self.audio.play_fireball()
            if isinstance(projectile, ArrowProjectile) and projectile.phase == "fly":
                if projectile.x <= visible_left or projectile.x >= visible_right:
                    projectile.x = max(visible_left, min(visible_right, projectile.x))
                    projectile._start_break()
            if isinstance(projectile, FireBreathProjectile):
                if projectile.x <= visible_left or projectile.x >= visible_right:
                    projectile.finished = True
                    projectile.just_impact = True
            if isinstance(projectile, WindProjectile):
                pass
            if projectile.x < self.stage.play_min_x - 400 or projectile.x > self.stage.play_max_x + 400:
                self.projectiles.remove(projectile)
                continue

            for target in (self.fighter, self.enemy):
                if target is None or target is projectile.owner or target.is_dead:
                    continue
                if not projectile.can_damage:
                    continue
                knocked_and_vulnerable = target.state in {"fall", "knocked_fire"} and not target.animation_player.finished
                if isinstance(projectile, (FireTrailEffect, FireExplosionEffect)):
                    if id(target) in projectile.hit_targets:
                        continue
                    if not projectile.rect().colliderect(target.world_hitbox_rect()):
                        continue
                    projectile.hit_targets.add(id(target))
                    if knocked_and_vulnerable:
                        target.receive_damage(projectile.damage, ignore_invulnerability=True)
                    else:
                        target.receive_damage(projectile.damage)
                    if not target.is_dead:
                        target._start_fire_knockdown()
                    self.audio.play_fire_breath()
                    continue
                if isinstance(projectile, FireBreathProjectile):
                    if abs(target.lane_y - projectile.owner.lane_y) > 10:
                        continue
                    if projectile.facing > 0 and target.world_hitbox_rect().centerx < projectile.x:
                        continue
                    if projectile.facing < 0 and target.world_hitbox_rect().centerx > projectile.x:
                        continue
                    if abs(target.world_hitbox_rect().centery - projectile.y) > 24:
                        continue
                    if not projectile.rect().colliderect(target.world_hitbox_rect()):
                        continue
                    target.receive_damage(projectile.damage, ignore_invulnerability=True)
                    self.audio.play_fireball()
                    if not target.is_dead:
                        target._start_fire_knockdown()
                    projectile.finished = True
                    projectile.just_impact = True
                    continue
                if isinstance(projectile, WindProjectile):
                    if abs(target.lane_y - projectile.owner.lane_y) > 10:
                        continue
                    target_rect = target.world_hitbox_rect()
                    if id(target) in projectile.hit_targets:
                        continue
                    if projectile.facing > 0 and target_rect.centerx < projectile.x:
                        continue
                    if projectile.facing < 0 and target_rect.centerx > projectile.x:
                        continue
                    if not projectile.rect().colliderect(target_rect):
                        continue
                    projectile.hit_targets.add(id(target))
                    target._start_knockdown()
                    continue
                if abs(projectile.y - target.world_hitbox_rect().centery) > 42:
                    continue
                target_center_x = target.world_hitbox_rect().centerx
                if projectile.facing > 0 and target_center_x < projectile.x:
                    continue
                if projectile.facing < 0 and target_center_x > projectile.x:
                    continue
                if not projectile.rect().colliderect(target.world_hitbox_rect()):
                    continue

                if target.state == "block" and target.block_strength > 0:
                    target.block_strength = 0
                    target.block_hold_timer = 0.0
                    self.audio.play("hit_guard")
                elif target.state == "block" and target.block_strength == 0:
                    target._start_block_break()
                    self.audio.play("hit_guard")
                else:
                    if knocked_and_vulnerable:
                        target.receive_damage(projectile.damage, ignore_invulnerability=True)
                    else:
                        target.receive_damage(projectile.damage)
                    if isinstance(projectile, ArrowProjectile):
                        self.audio.play("arrow_hit")
                    elif isinstance(projectile, FireballProjectile):
                        self.audio.play_fireball()
                        if not target.is_dead:
                            target._start_fire_knockdown()
                    elif projectile.owner.name == "deep":
                        self.audio.play("sword_cut")
                    else:
                        self.audio.play("hit_success")

                if isinstance(projectile, FireballProjectile):
                    projectile._start_hit()
                    projectile.just_burst = False
                elif hasattr(projectile, "_start_burst"):
                    projectile._start_burst()
                else:
                    self.projectiles.remove(projectile)
                return

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
        if self.paused:
            return
        self.fighter.update(dt, inputs, target=self.enemy, controlled=True)
        self.enemy_brain.update(dt)
        enemy_input = self.enemy_brain.build_input(self.enemy.snapshot, self.fighter.snapshot)
        self.enemy.update(dt, enemy_input, target=self.fighter, controlled=True)

        for fighter in (self.fighter, self.enemy):
            self._spawn_hunter_projectile(fighter)
            self._spawn_template_projectile(fighter)
            self._spawn_denis_projectile(fighter)
            self._spawn_denis_follow_orb(fighter)
            self._spawn_davis_projectile(fighter)
            self._spawn_bat_laser(fighter)
            self._spawn_bat_summons(fighter)
            self._spawn_deep_projectile(fighter)
            self._spawn_firen_fireball(fighter)
            self._spawn_firen_fire_breath(fighter)
            self._spawn_henry_wind(fighter)
            self._spawn_firen_fire_trail(fighter)
            self._spawn_firen_explosion(fighter)

        self._update_projectiles(dt)
        self._handle_combat()
        self._handle_audio(dt)

    def draw(self, surface: pygame.Surface) -> None:
        focus_x = self.fighter.x
        player_margin = SCREEN_WIDTH * 0.3
        min_focus = self.fighter.x - player_margin
        max_focus = self.fighter.x + player_margin
        enemy_focus = (self.fighter.x + self.enemy.x) / 2
        focus_x = max(min_focus, min(max_focus, enemy_focus))

        camera_x = self.stage.camera_x(focus_x)
        self.stage.draw(surface, focus_x)

        for projectile in self.projectiles:
            projectile.draw(surface, camera_x)

        fighters = [self.fighter, self.enemy]
        fighters.sort(key=lambda fighter: fighter.lane_y)
        for fighter in fighters:
            fighter.draw(surface, camera_x)
            self._draw_speech_bubble(surface, fighter, camera_x)

        self._draw_marker(surface, self.fighter, camera_x, "P1")
        self._draw_hud(surface)
        if self.paused:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            surface.blit(overlay, (0, 0))
            paused = self.pause_font.render("Paused", True, TEXT_COLOR)
            resume = self.small_font.render("Esc: Resume", True, TEXT_COLOR)
            menu = self.small_font.render("M: Main Menu", True, TEXT_COLOR)
            surface.blit(paused, paused.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40)))
            surface.blit(resume, resume.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 10)))
            surface.blit(menu, menu.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 40)))
