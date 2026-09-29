from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, replace
from pathlib import Path

import pygame

from game.constants import (
    GROUND_Y,
    HEAVY_BOX_ITEM_ID,
    HEAVY_ITEM_ANCHOR_KEYS,
    HEAVY_ITEM_FALLBACK_ANCHOR,
    HEAVY_ITEM_IDS,
    LANE_MAX_Y,
    LANE_MIN_Y,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    TEXT_COLOR,
)
from game.data.characters import CHARACTERS
from game.entities.fighter import COMBAT_ATTACK_STATES, Fighter, FighterConfig, FighterInput, FighterSnapshot
from game.systems.audio import AudioBank
from game.systems.item_anchors import HandAnchor, load_hand_anchors
from game.systems.stage import CityStage


THROWN_ITEM_MAX_DISTANCE = 330.0
THROWABLE_DISTANCE_MULTIPLIER = 2.0
HEAVY_ITEM_DISTANCE_MULTIPLIER = THROWABLE_DISTANCE_MULTIPLIER / 2
STAGE_CARD_DURATION = 2.4
CAMERA_FOLLOW_SPEED = 10.0
STAGE_ROMAN_NUMERALS = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X")
STAGE_ENCOUNTERS = (
    (("bandit", 1),),
    (("bandit", 1), ("hunter", 1)),
    (("jack", 1), ("bandit", 2), ("hunter", 1)),
    (("knight", 2), ("monk", 1)),
    (("bat", 1),),
    (("bandit", 3), ("armored_bandit", 1)),
    (("mark", 3), ("sorcerer", 1)),
    (("sorcerer", 1), ("monk", 1), ("mark", 1), ("hunter", 2)),
    (("axle", 3), ("jack", 2)),
    (("luis_liberated", 1), ("henry", 1)),
)


def _is_throwable_item(item_id: str) -> bool:
    return item_id.partition("/")[0] == "throwables"


def _load_folder_frames(folder: Path) -> list[pygame.Surface]:
    frames: list[pygame.Surface] = []
    if not folder.exists():
        return frames

    def frame_sort_key(path: Path) -> tuple[str, int, str]:
        match = re.search(r"(\d+)$", path.stem)
        if match is None:
            return path.stem.casefold(), -1, path.suffix.casefold()
        return path.stem[:match.start()].casefold(), int(match.group(1)), path.suffix.casefold()

    frame_paths = (
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in {".png", ".bmp"}
    )
    for path in sorted(frame_paths, key=frame_sort_key):
        frame = pygame.image.load(str(path)).convert()
        frame.set_colorkey((0, 0, 0))
        frames.append(frame)
    return frames


def _scale_frames(frames: list[pygame.Surface], scale: float) -> list[pygame.Surface]:
    return [
        pygame.transform.scale(
            frame,
            (round(frame.get_width() * scale), round(frame.get_height() * scale)),
        )
        for frame in frames
    ]


def _trim_item_frames(frames: list[pygame.Surface]) -> list[pygame.Surface]:
    trimmed: list[pygame.Surface] = []
    for frame in frames:
        bounds = pygame.mask.from_surface(frame).get_bounding_rects()
        if not bounds:
            trimmed.append(frame)
            continue
        left = min(rect.left for rect in bounds)
        top = min(rect.top for rect in bounds)
        right = max(rect.right for rect in bounds)
        bottom = max(rect.bottom for rect in bounds)
        content = pygame.Rect(left, top, right - left, bottom - top)
        cropped = pygame.Surface(content.size).convert()
        cropped.fill((0, 0, 0))
        cropped.blit(frame, (0, 0), content)
        cropped.set_colorkey((0, 0, 0))
        trimmed.append(cropped)
    return trimmed


def _load_item_sprite_animations(root: Path) -> dict[str, dict[str, list[pygame.Surface]]]:
    item_sprites: dict[str, dict[str, list[pygame.Surface]]] = {}
    if not root.is_dir():
        return item_sprites

    for category_folder in sorted(root.iterdir()):
        if not category_folder.is_dir() or category_folder.name.startswith("_"):
            continue
        for item_folder in sorted(category_folder.iterdir()):
            if not item_folder.is_dir() or item_folder.name.startswith("_"):
                continue

            animations: dict[str, list[pygame.Surface]] = {}
            for action_folder in sorted(item_folder.iterdir()):
                if not action_folder.is_dir() or action_folder.name.startswith("_"):
                    continue

                frame_folder = action_folder
                if action_folder.name == "holding" and (action_folder / "idle").is_dir():
                    frame_folder = action_folder / "idle"
                frames = _load_folder_frames(frame_folder)
                if not frames and frame_folder != action_folder:
                    frames = _load_folder_frames(action_folder)
                if frames:
                    animations[action_folder.name] = _trim_item_frames(_scale_frames(frames, 1.2))
                    continue

                for variant_folder in sorted(path for path in action_folder.rglob("*") if path.is_dir()):
                    relative_parts = variant_folder.relative_to(item_folder).parts
                    if any(part.startswith("_") for part in relative_parts):
                        continue
                    frames = _load_folder_frames(variant_folder)
                    if frames:
                        action = variant_folder.relative_to(item_folder).as_posix()
                        animations[action] = _trim_item_frames(_scale_frames(frames, 1.2))

            if animations:
                item_sprites[item_folder.relative_to(root).as_posix()] = animations
    return item_sprites


class ConsumableItem:
    BREAK_AFTER_THROW_LANDINGS = 2
    BASEBALL_ITEM_ID = "throwables/baseball"
    BASEBALL_BOUNCE_SPEED = -280.0
    BASEBALL_GRAVITY = 900.0

    def _initialize_landings(
        self,
        land_frame_sets: list[tuple[str, list[pygame.Surface]]],
        landing_count: int = 0,
    ) -> None:
        self.land_frame_sets = land_frame_sets
        self.landing_count = landing_count
        self.landing_elapsed = 0.0
        self.landing_animation_finished = False
        self.break_after_landing = False
        self.bounce_velocity = 0.0

    def _begin_landing(self, counts_toward_breakage: bool) -> str:
        facing = getattr(self, "facing", 0)
        side = "right" if facing > 0 else "left"
        matching_sets = [
            frames for name, frames in self.land_frame_sets if name.casefold().endswith(side)
        ] if facing else []
        self.frames = random.choice(matching_sets or [frames for _, frames in self.land_frame_sets])
        if counts_toward_breakage:
            self.landing_count += 1
        self.break_after_landing = (
            counts_toward_breakage and self.landing_count >= self.BREAK_AFTER_THROW_LANDINGS
        )
        self.phase = "landed"
        self.frame_index = 0
        self.frame_timer = 0.0
        self.landing_elapsed = 0.0
        self.landing_animation_finished = False
        self.y = self.floor_y - self.frames[0].get_height() / 2
        if self.item_id == self.BASEBALL_ITEM_ID:
            self.phase = "bouncing"
            self.bounce_velocity = self.BASEBALL_BOUNCE_SPEED
        return "landed"

    def _update_bounce(self, dt: float) -> None:
        self.frame_timer += dt
        while self.frame_timer >= 0.08 and self.frame_index < len(self.frames) - 1:
            self.frame_timer -= 0.08
            self.frame_index += 1
        frame = self.frames[self.frame_index]
        self.bounce_velocity += self.BASEBALL_GRAVITY * dt
        self.y += self.bounce_velocity * dt
        if self.y + frame.get_height() / 2 >= self.floor_y:
            self.y = self.floor_y - frame.get_height() / 2
            self.phase = "landed"
            self.frame_index = 0
            self.frame_timer = 0.0
            self.bounce_velocity = 0.0

    def _update_landing(self, dt: float) -> str | None:
        if self.landing_animation_finished:
            return None
        self.landing_elapsed += dt
        self.frame_timer += dt
        while self.frame_timer >= 0.08 and self.frame_index < len(self.frames) - 1:
            self.frame_timer -= 0.08
            self.frame_index += 1
        if self.landing_elapsed < len(self.frames) * 0.08:
            return None
        if self.break_after_landing:
            self.phase = "breaking"
            return "break"
        self.landing_animation_finished = True
        return None

    def world_rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        center_y = self.y if self.phase in {"falling", "thrown", "bouncing"} else self.floor_y - frame.get_height() / 2
        return frame.get_rect(center=(round(self.x), round(center_y)))


class SpawnedConsumable(ConsumableItem):
    def __init__(
        self,
        item_id: str,
        x: float,
        lane_y: float,
        spawn_frames: list[pygame.Surface],
        land_frame_sets: list[tuple[str, list[pygame.Surface]]],
    ) -> None:
        self.item_id = item_id
        self.x = x
        self.lane_y = lane_y
        self.floor_y = GROUND_Y + lane_y
        self.spawn_frames = spawn_frames
        self.land_frame_sets = land_frame_sets
        self.frames = spawn_frames
        self.phase = "falling"
        self.frame_index = 0
        self.frame_timer = 0.0
        self.fall_speed = 0.0
        self.facing = 0
        self.y = -spawn_frames[0].get_height() / 2
        self._initialize_landings(land_frame_sets)

    @property
    def pickupable(self) -> bool:
        return self.phase == "landed"

    def update(self, dt: float) -> str | None:
        if self.phase == "landed":
            return self._update_landing(dt)
        if self.phase == "bouncing":
            self._update_bounce(dt)
            return None

        self.frame_timer += dt
        if self.phase == "falling":
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % len(self.frames)
            self.fall_speed += 900.0 * dt
            self.y += self.fall_speed * dt
            if self.y + self.frames[self.frame_index].get_height() / 2 >= self.floor_y:
                return self._begin_landing(counts_toward_breakage=False)
        return None

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        center_y = self.y if self.phase in {"falling", "bouncing"} else self.floor_y - frame.get_height() / 2
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(center_y - frame.get_height() / 2)))


class ThrownItem(ConsumableItem):
    def __init__(
        self,
        owner: Fighter,
        item_id: str,
        start_x: float,
        end_x: float,
        lane_y: float,
        start_height: float,
        horizontal_speed: float,
        facing: int,
        throw_frames: list[pygame.Surface],
        land_frame_sets: list[tuple[str, list[pygame.Surface]]],
        landing_count: int = 0,
    ) -> None:
        self.owner = owner
        self.item_id = item_id
        self.x = start_x
        self.start_x = start_x
        self.end_x = end_x
        self.lane_y = lane_y
        self.floor_y = GROUND_Y + lane_y
        self.start_height = max(0.0, start_height)
        self.facing = 1 if facing >= 0 else -1
        self.frames = throw_frames
        self.phase = "thrown"
        self.frame_index = 0
        self.frame_timer = 0.0
        self.fall_speed = 0.0
        self.elapsed = 0.0
        self.flight_duration = max(0.08, abs(end_x - start_x) / horizontal_speed)
        self.y = self.floor_y - throw_frames[0].get_height() / 2 - self.start_height
        self._initialize_landings(land_frame_sets, landing_count)

    @property
    def pickupable(self) -> bool:
        return self.phase == "landed" and not self.break_after_landing

    def update(self, dt: float) -> str | None:
        if self.phase == "landed":
            return self._update_landing(dt)
        if self.phase == "bouncing":
            self._update_bounce(dt)
            return None
        self.frame_timer += dt
        if self.phase == "falling":
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % len(self.frames)
            frame = self.frames[self.frame_index]
            self.fall_speed += 900.0 * dt
            self.y += self.fall_speed * dt
            if self.y + frame.get_height() / 2 >= self.floor_y:
                self.y = self.floor_y - frame.get_height() / 2
                return self._begin_landing(counts_toward_breakage=True)
            return None
        if self.phase == "thrown":
            self.elapsed = min(self.flight_duration, self.elapsed + dt)
            progress = self.elapsed / self.flight_duration
            self.frame_index = min(int(progress * len(self.frames)), len(self.frames) - 1)
            frame = self.frames[self.frame_index]
            arc_height = 48.0
            height = self.start_height * (1.0 - progress) + arc_height * 4.0 * progress * (1.0 - progress)
            self.x = self.start_x + (self.end_x - self.start_x) * progress
            self.y = self.floor_y - frame.get_height() / 2 - height
            if progress >= 1.0:
                return self._begin_landing(counts_toward_breakage=True)
        return None

    def drop_at_hit(self) -> None:
        self.phase = "falling"
        self.frame_timer = 0.0
        self.fall_speed = 0.0

    def world_rect(self) -> pygame.Rect:
        return self.frames[self.frame_index].get_rect(center=(round(self.x), round(self.y)))

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        center_y = (
            self.y
            if self.phase in {"thrown", "falling", "bouncing"}
            else self.floor_y - frame.get_height() / 2
        )
        surface.blit(
            frame,
            (int(self.x - camera_x - frame.get_width() / 2), int(center_y - frame.get_height() / 2)),
        )


class ConsumableBreakEffect:
    FRAME_DURATION = 0.08

    def __init__(
        self,
        x: float,
        lane_y: float,
        dust_frames: list[pygame.Surface],
        large_frames: list[pygame.Surface],
        small_frames: list[pygame.Surface],
    ) -> None:
        self.x = x
        self.floor_y = GROUND_Y + lane_y
        self.dust_frames = dust_frames
        self.large_frames = large_frames
        self.small_frames = small_frames
        self.elapsed = 0.0
        self.duration = max(len(dust_frames), len(large_frames), len(small_frames)) * self.FRAME_DURATION

    def update(self, dt: float) -> bool:
        self.elapsed += dt
        return self.elapsed >= self.duration

    def _current_frame(self, frames: list[pygame.Surface]) -> pygame.Surface:
        index = min(int(self.elapsed / self.FRAME_DURATION), len(frames) - 1)
        return frames[index]

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        x = int(self.x - camera_x)
        dust = self._current_frame(self.dust_frames)
        large = self._current_frame(self.large_frames)
        small = self._current_frame(self.small_frames)
        surface.blit(dust, dust.get_rect(midbottom=(x, int(self.floor_y))))
        surface.blit(large, large.get_rect(midbottom=(x, int(self.floor_y))))

        side_offset = (large.get_width() + small.get_width()) // 2 + 2
        left_small = pygame.transform.flip(small, True, False)
        surface.blit(left_small, left_small.get_rect(midbottom=(x - side_offset, int(self.floor_y))))
        surface.blit(small, small.get_rect(midbottom=(x + side_offset, int(self.floor_y))))


class ItemBreakEffect:
    FRAME_DURATION = 0.08

    def __init__(self, x: float, lane_y: float, frames: list[pygame.Surface]) -> None:
        self.x = x
        self.floor_y = GROUND_Y + lane_y
        self.frames = frames
        self.elapsed = 0.0

    def update(self, dt: float) -> bool:
        self.elapsed += dt
        return self.elapsed >= len(self.frames) * self.FRAME_DURATION

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame_index = min(int(self.elapsed / self.FRAME_DURATION), len(self.frames) - 1)
        frame = self.frames[frame_index]
        surface.blit(
            frame,
            frame.get_rect(midbottom=(int(self.x - camera_x), int(self.floor_y))),
        )


class MetalFragmentEffect(ItemBreakEffect):
    INITIAL_UPWARD_SPEED = 420.0
    GRAVITY = 1400.0

    def __init__(self, x: float, lane_y: float, frames: list[pygame.Surface]) -> None:
        super().__init__(x, lane_y, frames)
        self.flight_duration = (2.0 * self.INITIAL_UPWARD_SPEED) / self.GRAVITY
        self.duration = max(len(frames) * self.FRAME_DURATION, self.flight_duration)

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame_index = min(int(self.elapsed / self.FRAME_DURATION), len(self.frames) - 1)
        frame = self.frames[frame_index]
        flight_time = min(self.elapsed, self.flight_duration)
        vertical_offset = max(
            0.0,
            self.INITIAL_UPWARD_SPEED * flight_time - 0.5 * self.GRAVITY * flight_time**2,
        )
        surface.blit(
            frame,
            frame.get_rect(
                midbottom=(int(self.x - camera_x), int(self.floor_y - vertical_offset))
            ),
        )


@dataclass
class HeavyBoxFragment:
    frames: list[pygame.Surface]
    x: float
    bottom_y: float
    velocity_x: float
    velocity_y: float
    elapsed: float = 0.0
    landed: bool = False


class HeavyBoxBreakEffect:
    FRAME_DURATION = 0.08
    GRAVITY = 1300.0

    def __init__(
        self,
        x: float,
        lane_y: float,
        large_frames: list[pygame.Surface],
        left_frames: list[pygame.Surface],
        right_frames: list[pygame.Surface],
        tiny_frames: list[pygame.Surface],
    ) -> None:
        floor_y = GROUND_Y + lane_y
        self.floor_y = floor_y
        self.fragments = [
            HeavyBoxFragment(large_frames, x, floor_y, 0.0, -480.0),
            HeavyBoxFragment(left_frames, x - 10.0, floor_y, -220.0, -380.0),
            HeavyBoxFragment(right_frames, x + 10.0, floor_y, 220.0, -380.0),
            HeavyBoxFragment(tiny_frames, x, floor_y, 0.0, 0.0, landed=True),
        ]

    def update(self, dt: float) -> bool:
        for fragment in self.fragments:
            fragment.elapsed += dt
            if fragment.landed:
                continue

            fragment.x += fragment.velocity_x * dt
            fragment.bottom_y += fragment.velocity_y * dt
            fragment.velocity_y += self.GRAVITY * dt
            if fragment.bottom_y >= self.floor_y:
                fragment.bottom_y = self.floor_y
                fragment.velocity_x = 0.0
                fragment.velocity_y = 0.0
                fragment.landed = True

        return all(
            fragment.landed and fragment.elapsed >= len(fragment.frames) * self.FRAME_DURATION
            for fragment in self.fragments
        )

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        for fragment in self.fragments:
            frame_index = min(
                int(fragment.elapsed / self.FRAME_DURATION),
                len(fragment.frames) - 1,
            )
            frame = fragment.frames[frame_index]
            surface.blit(
                frame,
                frame.get_rect(midbottom=(int(fragment.x - camera_x), int(fragment.bottom_y))),
            )


class ItemSpriteAnimation:
    def __init__(self, frames: list[pygame.Surface], loop: bool = False) -> None:
        self.frames = frames
        self.loop = loop
        self.frame_index = 0
        self.frame_timer = 0.0

    def update(self, dt: float) -> bool:
        self.frame_timer += dt
        while self.frame_timer >= 0.08:
            self.frame_timer -= 0.08
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                if self.loop:
                    self.frame_index = 0
                else:
                    return True
        return False

    @property
    def current_frame(self) -> pygame.Surface:
        return self.frames[self.frame_index]


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

        if self.attack_cooldown == 0.0 and same_lane and abs_dx < 185.0 and self_snapshot.state not in {"basic_attack", "heavy_attack", "sprint_punch", "spawn", "throw_heavy", "lift_heavy"}:
            result.attack_just_pressed = True
            self.attack_cooldown = 0.85

        return result


@dataclass
class RudolfClone:
    fighter: Fighter
    brain: BanditBrain
    lifetime: float = 8.0


class RudolfSmokeEffect:
    FRAME_DURATION = 0.08

    def __init__(self, x: float, lane_y: float, frames: list[pygame.Surface]) -> None:
        self.x = x
        self.floor_y = GROUND_Y + lane_y
        self.frames = frames
        self.elapsed = 0.0

    def update(self, dt: float) -> bool:
        self.elapsed += dt
        return self.elapsed >= len(self.frames) * self.FRAME_DURATION

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame_index = min(int(self.elapsed / self.FRAME_DURATION), len(self.frames) - 1)
        frame = self.frames[frame_index]
        surface.blit(
            frame,
            frame.get_rect(midbottom=(int(self.x - camera_x), int(self.floor_y))),
        )


class ArrowProjectile:
    HENRY_SPEED_X = 585.0
    HENRY_RANGE_FACTOR = 0.5625

    def __init__(
        self,
        owner: Fighter,
        x: float,
        y: float,
        facing: int,
        style: str = "basic",
        vertical_speed: float = 0.0,
        target_lane_y: float | None = None,
    ) -> None:
        self.owner = owner
        self.origin_lane_y = float(owner.lane_y)
        self.lane_y = self.origin_lane_y
        self.target_lane_y = float(owner.lane_y if target_lane_y is None else target_lane_y)
        self.lane_change_distance = 220.0
        self.x = float(x)
        self.y = float(y)
        self.origin_y = float(y)
        self.origin_x = float(x)
        self.facing = 1 if facing >= 0 else -1
        self.style = style
        self.vertical_speed = vertical_speed
        self.speed_x = 1040.0
        self.ascend_speed = 620.0
        self.straight_speed = 70.0
        self.fall_speed = 160.0
        self.gravity = 520.0
        self.max_distance = 3920.0
        self.damage = 1
        self.frame_timer = 0.0
        self.frame_index = 0
        self.flight_elapsed = 0.0
        self.motion_frame_timer = 0.0
        self.motion_frame_index = 0
        self.phase = "fly"
        self.can_damage = True
        self.finished = False
        self.just_broke = False
        self.just_ground_hit = False
        self.break_velocity_y = 0.0
        self.break_bounced = False
        arrows_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "arrow"
        if style == "rudolf":
            self.fly_frames = _load_folder_frames(arrows_root.parent / "rudolf_shuriken")
        else:
            self.fly_frames = [
                pygame.transform.flip(frame, False, True)
                for frame in _load_folder_frames(arrows_root / "arrow_fly")
            ]
        enchanted_frames = _load_folder_frames(arrows_root / "arrow_enchanted") if style == "enchanted" else []
        self.enchanted_launch_frames = enchanted_frames[:1]
        self.enchanted_loop_frames = enchanted_frames[1:] if len(enchanted_frames) > 1 else enchanted_frames
        self.enchanted_launch_done = False
        self.fly_frames = self.fly_frames or [pygame.Surface((12, 12), pygame.SRCALPHA)]
        self.henry_jump_frames = self.fly_frames[5:6]
        self.break_frames = _load_folder_frames(arrows_root / "arrow_break")
        self.frames = self.henry_jump_frames if style == "henry_jump" else self.fly_frames
        if not self.frames:
            self.frames = [pygame.Surface((12, 12), pygame.SRCALPHA)]
        self.ground_y = GROUND_Y + self.lane_y - 18.0
        if style in {"henry_basic", "henry_vertical"}:
            self.speed_x = self.HENRY_SPEED_X
            self.max_distance *= self.HENRY_RANGE_FACTOR
        if style == "henry_basic":
            self.vertical_speed = -300.0
            self.gravity = 700.0
        if style == "henry_jump":
            self.max_distance /= 2
            self.fall_speed = self.speed_x
            self.gravity = 0.0
        if style == "henry_vertical":
            self.gravity = 720.0
        self.flight_duration = self._estimate_flight_duration()

    def _estimate_flight_duration(self) -> float:
        max_distance_duration = self.max_distance / self.speed_x
        if self.style == "henry_jump":
            ground_duration = max(0.0, (self.ground_y - self.y) / self.fall_speed)
        elif self.style in {"henry_basic", "henry_vertical"}:
            distance_to_ground = self.ground_y - self.y
            discriminant = self.vertical_speed**2 + 2.0 * self.gravity * distance_to_ground
            ground_duration = (
                max(0.0, (-self.vertical_speed + math.sqrt(max(0.0, discriminant))) / self.gravity)
                if self.gravity > 0.0
                else max(0.0, distance_to_ground / self.vertical_speed)
            )
        else:
            ascent_duration = 0.16
            fall_distance = max(
                0.0,
                self.ground_y - self.y + self.ascend_speed * 0.08 + self.straight_speed * 0.08,
            )
            fall_duration = (
                max(
                    0.0,
                    (
                        -self.fall_speed
                        + math.sqrt(self.fall_speed**2 + 2.0 * self.gravity * fall_distance)
                    )
                    / self.gravity,
                )
                if self.gravity > 0.0
                else 0.0
            )
            ground_duration = ascent_duration + fall_duration
        return min(ground_duration, max_distance_duration)

    def _start_break(self, ground_hit: bool = False) -> None:
        if self.phase == "break":
            return
        if self.style == "rudolf" and ground_hit:
            self.phase = "break"
            self.finished = True
            self.can_damage = False
            self.just_ground_hit = True
            return
        self.phase = "break"
        self.just_broke = True
        self.just_ground_hit = ground_hit
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
            if self.style != "enchanted":
                self.flight_elapsed += dt
                if self.flight_duration > 0.0 and self.style != "rudolf":
                    progress = min(self.flight_elapsed / self.flight_duration, 1.0)
                    self.frame_index = min(int(progress * len(self.frames)), len(self.frames) - 1)
            if self.style in {"henry_basic", "henry_vertical"}:
                self.x += self.facing * self.speed_x * dt
                self.y += self.vertical_speed * dt
                self.vertical_speed += self.gravity * dt
                if self.y >= self.ground_y:
                    self.y = self.ground_y
                    self._start_break(ground_hit=True)
            elif self.style == "henry_jump":
                self.frames = self.henry_jump_frames or self.fly_frames
                self.x += self.facing * self.speed_x * dt
                self.y += self.fall_speed * dt
                if self.y >= self.ground_y:
                    self.y = self.ground_y
                    self._start_break(ground_hit=True)
            else:
                self.x += self.facing * self.speed_x * dt
            if self.style == "rudolf":
                lane_progress = min(abs(self.x - self.origin_x) / self.lane_change_distance, 1.0)
                next_lane_y = self.origin_lane_y + (self.target_lane_y - self.origin_lane_y) * lane_progress
                lane_delta = next_lane_y - self.lane_y
                self.lane_y = next_lane_y
                self.y += lane_delta
                self.ground_y += lane_delta
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
            elif self.style not in {"henry_jump", "henry_vertical", "henry_basic"}:
                self.frames = self.fly_frames
                if self.motion_frame_index <= 0:
                    self.y -= self.ascend_speed * dt
                elif self.motion_frame_index == 1:
                    self.y -= self.straight_speed * dt
                else:
                    self.y += self.fall_speed * dt
                    self.fall_speed += self.gravity * dt
                self.motion_frame_timer += dt
                while self.motion_frame_timer >= 0.08:
                    self.motion_frame_timer -= 0.08
                    if self.motion_frame_index < 2:
                        self.motion_frame_index += 1
                if self.style == "rudolf":
                    self.frame_timer += dt
                    while self.frame_timer >= 0.08:
                        self.frame_timer -= 0.08
                        self.frame_index = (self.frame_index + 1) % len(self.fly_frames)
                if self.y >= self.ground_y:
                    self.y = self.ground_y
                    self._start_break(ground_hit=True)
            if self.style != "enchanted" and abs(self.x - self.origin_x) >= self.max_distance:
                if self.style == "henry_jump":
                    self.x = self.origin_x + (self.facing * self.max_distance)
                    self.y = self.ground_y
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
        if self.style in {"henry_basic", "henry_vertical"} and self.phase == "fly":
            angle = -math.degrees(math.atan2(self.vertical_speed, self.facing * self.speed_x))
            frame = pygame.transform.rotate(frame, angle)
        elif self.style == "henry_jump" and self.phase == "fly":
            if self.facing < 0:
                frame = pygame.transform.flip(frame, True, False)
            frame = pygame.transform.rotate(frame, -45.0 * self.facing)
        elif self.facing < 0:
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


class JackBlastProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = 720.0
        self.damage = 1
        self.phase = "fly"
        self.can_damage = True
        self.finished = False
        self.frame_timer = 0.0
        self.frame_index = 0
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "jack_blast"
        self.fly_frames = _load_folder_frames(root / "fly")
        self.burst_frames = _load_folder_frames(root / "burst")
        self.frames = self.fly_frames or [pygame.Surface((16, 16), pygame.SRCALPHA)]

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.frames = self.burst_frames or self.frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        if self.phase == "fly":
            self.x += self.facing * self.speed_x * dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % len(self.frames)
            return

        while self.frame_timer >= 0.05:
            self.frame_timer -= 0.05
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                self.frame_index = len(self.frames) - 1
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class AxleShotProjectile:
    MAX_DISTANCE = 280.0

    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.origin_x = self.x
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = 720.0
        self.distance_travelled = 0.0
        self.damage = 1
        self.phase = "create"
        self.can_damage = False
        self.finished = False
        self.just_axle_shot_hit = False
        self.frame_timer = 0.0
        self.frame_index = 0
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "axle_shot"
        self.create_frames = _load_folder_frames(root / "create")
        self.fly_frames = _load_folder_frames(root / "fly")
        self.burst_frames = _load_folder_frames(root / "burst")
        fallback = [pygame.Surface((16, 16), pygame.SRCALPHA)]
        self.create_frames = self.create_frames or fallback
        self.fly_frames = self.fly_frames or fallback
        self.burst_frames = self.burst_frames or fallback
        self.frames = self.create_frames

    def _launch(self) -> None:
        self.phase = "fly"
        self.can_damage = True
        self.frames = self.fly_frames
        self.frame_index = 0
        self.frame_timer = 0.0

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.frames = self.burst_frames
        self.frame_index = 0
        self.frame_timer = 0.0
        self.just_axle_shot_hit = True

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        if self.phase == "create":
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self._launch()
                    return
        elif self.phase == "fly":
            distance = self.speed_x * dt
            self.distance_travelled += distance
            self.x += self.facing * distance
            if self.distance_travelled >= self.MAX_DISTANCE:
                self.x = self.origin_x + self.facing * self.MAX_DISTANCE
                self._start_burst()
                return
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % len(self.frames)
        else:
            while self.frame_timer >= 0.05:
                self.frame_timer -= 0.05
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.frame_index = len(self.frames) - 1
                    self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class JohnBlastCreateEffect:
    def __init__(self, x: float, y: float, facing: int) -> None:
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.frame_timer = 0.0
        self.frame_index = 0
        self.finished = False
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "john_blast"
        self.frames = _load_folder_frames(root / "create") or [pygame.Surface((16, 16), pygame.SRCALPHA)]

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        while self.frame_timer >= 0.08:
            self.frame_timer -= 0.08
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class JulianSkullProjectile:
    def __init__(self, owner: Fighter, target: Fighter | None, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.target = target
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = float(owner.movement["walk_speed"])
        self.speed_y = self.speed_x * 0.55
        self.damage = 1
        self.phase = "slow"
        self.can_damage = False
        self.finished = False
        self.life_timer = 0.0
        self.frame_timer = 0.0
        self.frame_index = 0
        self.just_burst_sound = False
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "julian_skull"
        self.slow_frames = _load_folder_frames(root / "slow")
        self.fast_frames = _load_folder_frames(root / "fast")
        self.burst_frames = _load_folder_frames(root / "burst")
        fallback = [pygame.Surface((24, 24), pygame.SRCALPHA)]
        self.slow_frames = self.slow_frames or fallback
        self.fast_frames = self.fast_frames or fallback
        self.burst_frames = self.burst_frames or fallback
        self.frames = self.slow_frames

    def _launch(self) -> None:
        self.phase = "fly"
        self.can_damage = True
        self.frames = self.fast_frames
        self.frame_index = 0
        self.frame_timer = 0.0

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.frames = self.burst_frames
        self.frame_index = 0
        self.frame_timer = 0.0

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        self.life_timer += dt
        self.frame_timer += dt
        if self.phase != "burst" and self.life_timer >= 8.0:
            self._start_burst()
            self.just_burst_sound = True
            return
        if self.phase == "slow":
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self._launch()
                    return
        elif self.phase == "fly":
            if self.target is not None and not self.target.is_dead:
                target_rect = self.target.world_hitbox_rect()
                target_is_ahead = (target_rect.centerx - self.x) * self.facing > 0
                target_is_in_lane = abs(self.target.lane_y - self.owner.lane_y) <= 36
                if target_is_ahead and target_is_in_lane:
                    vertical_offset = (target_rect.centery - self.y) * 0.55
                    vertical_step = max(-self.speed_y * dt, min(self.speed_y * dt, vertical_offset))
                    self.y += vertical_step
            self.x += self.facing * self.speed_x * dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % len(self.frames)
        else:
            while self.frame_timer >= 0.05:
                self.frame_timer -= 0.05
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.frame_index = len(self.frames) - 1
                    self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class JulianBallProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = float(owner.movement["walk_speed"])
        self.damage = 1
        self.phase = "fly"
        self.can_damage = True
        self.finished = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.hit_count = 0
        self.hit_targets: set[int] = set()
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "julian_ball"
        self.fly_frames = _load_folder_frames(root / "fly")
        self.burst_frames = _load_folder_frames(root / "burst")
        fallback = [pygame.Surface((24, 24), pygame.SRCALPHA)]
        self.fly_frames = self.fly_frames or fallback
        self.burst_frames = self.burst_frames or fallback
        self.frames = self.fly_frames

    def register_hit(self, target: object) -> bool:
        target_id = id(target)
        if target_id in self.hit_targets:
            return False
        self.hit_targets.add(target_id)
        self.hit_count += 1
        return True

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.frames = self.burst_frames
        self.frame_index = 0
        self.frame_timer = 0.0

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        if self.phase == "fly":
            self.x += self.facing * self.speed_x * dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % len(self.frames)
        else:
            while self.frame_timer >= 0.05:
                self.frame_timer -= 0.05
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.frame_index = len(self.frames) - 1
                    self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class JulianExplosionEffect:
    def __init__(self, owner: Fighter, x: float, y: float, radius: float, launch: bool) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.lane_y = owner.lane_y
        self.radius = radius
        self.launch = launch
        self.damage = 1
        self.finished = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.hit_targets: set[int] = set()
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "julian_explode"
        self.frames = _load_folder_frames(root) or [pygame.Surface((72, 72), pygame.SRCALPHA)]
        self.scale = 2.5

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        while self.frame_timer >= 0.05:
            self.frame_timer -= 0.05
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                self.frame_index = len(self.frames) - 1
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        width = int(frame.get_width() * self.scale)
        height = int(frame.get_height() * self.scale)
        scaled = pygame.transform.scale(frame, (width, height))
        surface.blit(scaled, (int(self.x - camera_x - width / 2), int(self.y - height)))


class JohnBlastProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = 720.0
        self.damage = 1
        self.phase = "fly"
        self.can_damage = True
        self.finished = False
        self.frame_timer = 0.0
        self.frame_index = 0
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "john_blast"
        self.fly_frames = _load_folder_frames(root / "fly")
        self.burst_frames = _load_folder_frames(root / "burst")
        self.frames = self.fly_frames or [pygame.Surface((16, 16), pygame.SRCALPHA)]

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.frames = self.burst_frames or self.frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        if self.phase == "fly":
            self.x += self.facing * self.speed_x * dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % len(self.frames)
            return

        while self.frame_timer >= 0.05:
            self.frame_timer -= 0.05
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                self.frame_index = len(self.frames) - 1
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class JohnBarrierEffect:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.phase = "create"
        self.life_timer = 0.0
        self.frame_timer = 0.0
        self.frame_index = 0
        self.reflect_count = 0
        self.burst_after_reflect = False
        self.finished = False
        self.just_barrier_sound = False
        self.just_reflect_sound = False
        self.just_burst_sound = False
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "john_magical_barrier"
        self.create_frames = _load_folder_frames(root / "create")
        self.barrier_frames = _load_folder_frames(root / "barrier")
        self.reflect_frames = _load_folder_frames(root / "barrier_reflect")
        self.burst_frames = _load_folder_frames(root / "burst")
        fallback = pygame.Surface((32, 64), pygame.SRCALPHA)
        self.create_frames = self.create_frames or [fallback.copy()]
        self.barrier_frames = self.barrier_frames or [fallback.copy()]
        self.reflect_frames = self.reflect_frames or [fallback.copy()]
        self.burst_frames = self.burst_frames or [fallback.copy()]
        for frames in (self.create_frames, self.barrier_frames, self.reflect_frames, self.burst_frames):
            frames[:] = [
                pygame.transform.scale(
                    frame,
                    (max(1, round(frame.get_width() * 1.25)), max(1, round(frame.get_height() * 1.25))),
                )
                for frame in frames
            ]
        self.frames = self.create_frames

    @property
    def can_reflect(self) -> bool:
        return self.phase == "barrier"

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def _enter_barrier(self) -> None:
        self.phase = "barrier"
        self.frames = self.barrier_frames
        self.frame_index = 0
        self.frame_timer = 0.0
        self.just_barrier_sound = True

    def _start_reflect(self) -> None:
        self.phase = "reflect"
        self.frames = self.reflect_frames
        self.frame_index = 0
        self.frame_timer = 0.0
        self.just_reflect_sound = True
        self.burst_after_reflect = self.reflect_count >= 3

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.frames = self.burst_frames
        self.frame_index = 0
        self.frame_timer = 0.0
        self.just_burst_sound = True

    def _advance_once(self, dt: float) -> bool:
        self.frame_timer += dt
        while self.frame_timer >= 0.08:
            self.frame_timer -= 0.08
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                self.frame_index = len(self.frames) - 1
                return True
        return False

    def update(self, dt: float) -> None:
        self.life_timer += dt
        if self.phase != "burst" and self.life_timer >= 8.0:
            self._start_burst()
            return

        if self.phase == "create":
            if self._advance_once(dt):
                self._enter_barrier()
        elif self.phase == "barrier":
            self.frame_timer += dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % len(self.frames)
                if self.frame_index == 0:
                    self.just_barrier_sound = True
        elif self.phase == "reflect":
            if self._advance_once(dt):
                if self.burst_after_reflect:
                    self._start_burst()
                else:
                    self._enter_barrier()
        elif self.phase == "burst" and self._advance_once(dt):
            self.finished = True

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


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
        self.just_died = False
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
        self.just_died = True
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


class HealingBirdProjectile:
    def __init__(self, owner: Fighter, target: Fighter, x: float, y: float, facing: int, spread_index: int) -> None:
        self.owner = owner
        self.target = target
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = 980.0
        self.speed_y = 28.0
        self.can_damage = False
        self.finished = False
        self.phase = "create"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.life_timer = 0.0
        self.wobble_phase = random.uniform(0.0, math.tau)
        self.spread_timer = 0.25
        self.spread_velocity_x = (spread_index - 1) * 320.0 * self.facing
        self.spread_velocity_y = -320.0 if spread_index == 1 else -240.0
        self.targeting_factor = 0.5
        self.swing_width = 360.0
        self.impact_x = self.x
        self.impact_y = self.y
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "summons" / "healing_birds"
        self.create_frames = _load_folder_frames(root / "create")
        self.fly_frames = _load_folder_frames(root / "fly")
        self.heal_frames = _load_folder_frames(root / "heal_target")
        self.burst_frames = _load_folder_frames(root / "burst")
        self.frames = self.create_frames or self.fly_frames or [pygame.Surface((18, 12), pygame.SRCALPHA)]

    def _start_heal(self) -> None:
        if self.phase != "fly":
            return
        self.phase = "heal"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.impact_x = self.x
        self.impact_y = self.y
        self.frames = self.heal_frames or self.frames

    def _start_burst(self) -> None:
        if self.phase in {"heal", "burst"}:
            return
        self.phase = "burst"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.impact_x = self.x
        self.impact_y = self.y
        self.frames = self.burst_frames or self.frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        if self.phase in {"heal", "burst"}:
            return pygame.Rect(int(self.impact_x - frame.get_width() / 2), int(self.impact_y - frame.get_height() / 2), frame.get_width(), frame.get_height())
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        self.life_timer += dt
        if self.life_timer >= 4.0 and self.phase in {"create", "fly"}:
            self._start_burst()
            return

        if self.phase == "create":
            self.frame_timer += dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.phase = "fly"
                    self.frames = self.fly_frames or self.frames
                    self.frame_index = 0
                    self.frame_timer = 0.0
                    return
            return

        if self.phase == "fly":
            animation_dt = dt
            if self.spread_timer > 0.0:
                spread_dt = min(dt, self.spread_timer)
                self.x += self.spread_velocity_x * spread_dt
                self.y += self.spread_velocity_y * spread_dt
                self.spread_timer -= spread_dt
                dt -= spread_dt

            if dt > 0.0 and not self.target.is_dead:
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
            self.frame_timer += animation_dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % max(1, len(self.frames))
            return

        self.frame_timer += dt
        while self.frame_timer >= 0.06:
            self.frame_timer -= 0.06
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                self.frame_index = len(self.frames) - 1
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        x, y = (self.impact_x, self.impact_y) if self.phase in {"heal", "burst"} else (self.x, self.y)
        surface.blit(frame, (int(x - camera_x - frame.get_width() / 2), int(y - frame.get_height() / 2)))


class JanFollowOrbProjectile:
    def __init__(self, owner: Fighter, target: Fighter | None, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.target = target
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = 980.0
        self.speed_y = 28.0
        self.damage = 1
        self.can_damage = False
        self.finished = False
        self.phase = "create"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.flight_timer = 0.0
        self.wobble_phase = random.uniform(0.0, math.tau)
        self.roam_phase = random.uniform(0.0, math.tau)
        self.targeting_factor = 0.5
        self.swing_width = 360.0
        self.impact_x = self.x
        self.impact_y = self.y
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "jan_follow_orb"
        self.create_frames = _load_folder_frames(root / "create")
        self.fly_frames = _load_folder_frames(root / "fly")
        self.burst_frames = _load_folder_frames(root / "burst")
        self.frames = self.create_frames or self.fly_frames or [pygame.Surface((18, 18), pygame.SRCALPHA)]

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.impact_x = self.x
        self.impact_y = self.y
        self.frames = self.burst_frames or self.frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        x, y = (self.impact_x, self.impact_y) if self.phase == "burst" else (self.x, self.y)
        return pygame.Rect(int(x - frame.get_width() / 2), int(y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        if self.phase == "create":
            self.frame_timer += dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.phase = "fly"
                    self.can_damage = True
                    self.frames = self.fly_frames or self.frames
                    self.frame_index = 0
                    self.frame_timer = 0.0
                    return
            return

        if self.phase == "fly":
            self.flight_timer += dt
            if self.flight_timer >= 5.0:
                self._start_burst()
                return

            if self.target is not None and not self.target.is_dead:
                target_rect = self.target.world_hitbox_rect()
                dx = target_rect.centerx - self.x
                dy = target_rect.centery - 28 - self.y
                distance = max(1.0, math.hypot(dx, dy))
                self.facing = 1 if dx >= 0 else -1
                homing_strength = (0.02 + min(0.03, distance / 6500.0)) * self.targeting_factor
                swing_phase = self.flight_timer * 2.4 + self.wobble_phase
                vertical_ratio = min(1.0, abs(dy) / 90.0)
                swing_width = self.swing_width + (self.swing_width * 1.1 * vertical_ratio)
                swing_bias = math.copysign(self.swing_width * (0.75 + (0.35 * vertical_ratio)), dy if dy != 0 else self.facing)
                swing_x = (math.sin(swing_phase) * swing_width) + swing_bias
                swing_y = math.cos(swing_phase) * self.speed_y * (0.10 + (0.10 * vertical_ratio))
                self.x += (self.facing * self.speed_x * 0.18 + swing_x) * dt
                self.y += (((dy / distance) * self.speed_y * homing_strength) + swing_y) * dt
            else:
                roam_phase = self.flight_timer * 2.0 + self.roam_phase
                swing_x = (math.sin(roam_phase) * self.swing_width * 1.35) + (self.facing * self.swing_width * 0.7)
                self.x += (self.facing * self.speed_x * 0.22 + swing_x) * dt
                self.y += math.sin(roam_phase * 0.85) * self.speed_y * 0.18 * dt

            self.frame_timer += dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % max(1, len(self.frames))
            return

        self.frame_timer += dt
        while self.frame_timer >= 0.06:
            self.frame_timer -= 0.06
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                self.frame_index = len(self.frames) - 1
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        x, y = (self.impact_x, self.impact_y) if self.phase == "burst" else (self.x, self.y)
        surface.blit(frame, (int(x - camera_x - frame.get_width() / 2), int(y - frame.get_height() / 2)))


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
        self.slow_frames = self._load_frames(root / "slow")
        self.fast_frames = self._load_frames(root / "fast")
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


class FreezeBallProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = 560.0
        self.damage = 1
        self.phase = "fly"
        self.can_damage = True
        self.finished = False
        self.just_burst = False
        self.frame_timer = 0.0
        self.frame_index = 0
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "freeze_ball"
        self.fly_frames = _load_folder_frames(root / "freeze_ball_projectile")
        self.burst_frames = _load_folder_frames(root / "freeze_ball_burst")
        self.frames = self.fly_frames or [pygame.Surface((16, 16), pygame.SRCALPHA)]

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(
            int(self.x - frame.get_width() / 2),
            int(self.y - frame.get_height() / 2),
            frame.get_width(),
            frame.get_height(),
        )

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.just_burst = True
        self.frame_timer = 0.0
        self.frame_index = 0
        self.frames = self.burst_frames or self.fly_frames

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        if self.phase == "fly":
            self.x += self.facing * self.speed_x * dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % len(self.frames)
        else:
            while self.frame_timer >= 0.06:
                self.frame_timer -= 0.06
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class FreezeColumnEffect:
    def __init__(
        self,
        x: float,
        y: float,
        column_number: int | str,
        facing: int = 1,
        lane_y: float = 0.0,
        owner: Fighter | None = None,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.lane_y = float(lane_y)
        self.owner = owner
        self.scale = 1.8
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "freeze_colum"
        self.frames = _load_folder_frames(root / f"freeze_colum_{column_number}")
        self.frame_index = 0
        self.frame_timer = 0.0
        self.lifetime = 10.0
        self.finished = False
        self.just_expired = False

    def rect(self) -> pygame.Rect:
        if not self.frames:
            return pygame.Rect(int(self.x), int(self.y), 0, 0)
        frame = self.frames[self.frame_index]
        width = int(frame.get_width() * self.scale)
        height = int(frame.get_height() * self.scale)
        return pygame.Rect(int(self.x - width / 2), int(self.y - height), width, height)

    def break_apart(self) -> None:
        if self.finished:
            return
        self.finished = True
        self.just_expired = True

    def update(self, dt: float) -> None:
        self.lifetime = max(0.0, self.lifetime - dt)
        if self.lifetime == 0.0:
            self.finished = True
            self.just_expired = True
            return
        if self.frames:
            self.frame_timer += dt
            while self.frame_timer >= 0.10 and self.frame_index < len(self.frames) - 1:
                self.frame_timer -= 0.10
                self.frame_index += 1

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        if not self.frames or self.finished:
            return
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        width = int(frame.get_width() * self.scale)
        height = int(frame.get_height() * self.scale)
        frame = pygame.transform.scale(frame, (width, height))
        surface.blit(frame, (int(self.x - camera_x - width / 2), int(self.y - height)))


class FreezeTornadoProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = float(owner.movement["run_speed"]) * 1.25
        self.scale = 1.25
        self.hitbox_scale = 1.5
        self.frames = _load_folder_frames(
            Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "freeze_tornado"
        ) or [pygame.Surface((16, 16), pygame.SRCALPHA)]
        self.frame_index = 0
        self.frame_timer = 0.0
        self.hit_targets: set[int] = set()
        self.can_damage = True
        self.finished = False

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        width = int(frame.get_width() * self.scale * self.hitbox_scale)
        height = int(frame.get_height() * self.scale * self.hitbox_scale)
        return pygame.Rect(
            int(self.x - width / 2),
            int(self.y - height / 2),
            width,
            height,
        )

    def update(self, dt: float) -> None:
        self.x += self.facing * self.speed_x * dt
        self.frame_timer += dt
        while self.frame_timer >= 0.08 and not self.finished:
            self.frame_timer -= 0.08
            if self.frame_index < len(self.frames) - 1:
                self.frame_index += 1
            else:
                self.finished = True

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        width = int(frame.get_width() * self.scale)
        height = int(frame.get_height() * self.scale)
        scaled = pygame.transform.scale(frame, (width, height))
        surface.blit(scaled, (int(self.x - camera_x - width / 2), int(self.y - height / 2)))


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
            if self.speed_x < 380.0:
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


class JohnFollowDiskProjectile:
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
        self.create_timer = 0.0
        self.flight_timer = 0.0
        self.frame_timer = 0.0
        self.frame_index = 0
        self.speed = 520.0
        self.hit_radius = 42
        self.wobble_phase = random.uniform(0.0, math.tau)
        self.impact_x = self.x
        self.impact_y = self.y
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "john_follow_disk"
        self.create_frames = _load_folder_frames(root / "create")
        self.fly_frames = _load_folder_frames(root / "fly")
        self.burst_frames = _load_folder_frames(root / "burst")
        fallback = [pygame.Surface((20, 20), pygame.SRCALPHA)]
        self.create_frames = self.create_frames or fallback
        self.fly_frames = self.fly_frames or fallback
        self.burst_frames = self.burst_frames or fallback
        self.frames = self.create_frames

    def _launch(self) -> None:
        self.phase = "fly"
        self.can_damage = True
        self.frames = self.fly_frames
        self.frame_index = 0
        self.frame_timer = 0.0
        self.flight_timer = 0.0

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.frames = self.burst_frames
        self.frame_index = 0
        self.frame_timer = 0.0
        self.impact_x = self.x
        self.impact_y = self.y

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        x, y = (self.impact_x, self.impact_y) if self.phase == "burst" else (self.x, self.y)
        return pygame.Rect(int(x - frame.get_width() / 2), int(y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def hit_rect(self) -> pygame.Rect:
        return self.rect().inflate(self.hit_radius * 2, self.hit_radius * 2)

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        if self.phase == "create":
            self.create_timer += dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self._launch()
                    return
        elif self.phase == "fly":
            self.flight_timer += dt
            if self.flight_timer >= 5.0:
                self._start_burst()
                return
            if self.target is not None and not self.target.is_dead:
                target_rect = self.target.world_hitbox_rect()
                dx = target_rect.centerx - self.x
                dy = target_rect.centery - self.y
                distance = max(1.0, math.hypot(dx, dy))
                self.facing = 1 if dx >= 0 else -1
                wobble = math.sin(self.flight_timer * 3.0 + self.wobble_phase) * 46.0
                self.x += (dx / distance * self.speed + wobble) * dt
                self.y += dy / distance * self.speed * dt
            else:
                self.x += self.facing * self.speed * dt
                self.y += math.sin(self.flight_timer * 3.0 + self.wobble_phase) * 34.0 * dt
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index = (self.frame_index + 1) % len(self.frames)
        else:
            while self.frame_timer >= 0.05:
                self.frame_timer -= 0.05
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.frame_index = len(self.frames) - 1
                    self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        x, y = (self.impact_x, self.impact_y) if self.phase == "burst" else (self.x, self.y)
        surface.blit(frame, (int(x - camera_x - frame.get_width() / 2), int(y - frame.get_height() / 2)))


class JohnHealOrbProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.phase = "create"
        self.life_timer = 0.0
        self.frame_timer = 0.0
        self.frame_index = 0
        self.finished = False
        self.just_heal_sound = False
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "john_heal_orb"
        self.create_frames = _load_folder_frames(root / "create")
        self.idle_frames = _load_folder_frames(root / "idle")
        self.burst_frames = _load_folder_frames(root / "burst")
        fallback = [pygame.Surface((24, 24), pygame.SRCALPHA)]
        self.create_frames = self.create_frames or fallback
        self.idle_frames = self.idle_frames or fallback
        self.burst_frames = self.burst_frames or fallback
        self.frames = self.create_frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def contact_rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - 20), int(self.y - 20), 40, 40)

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.frames = self.burst_frames
        self.frame_index = 0
        self.frame_timer = 0.0
        self.just_heal_sound = True

    def update(self, dt: float) -> None:
        self.life_timer += dt
        self.frame_timer += dt
        if self.phase != "burst" and self.life_timer >= 6.0:
            self._start_burst()
            return

        if self.phase == "create":
            while self.frame_timer >= 0.08:
                self.frame_timer -= 0.08
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.phase = "idle"
                    self.frames = self.idle_frames
                    self.frame_index = 0
                    self.frame_timer = 0.0
                    break
        elif self.phase == "idle":
            while self.frame_timer >= 0.10:
                self.frame_timer -= 0.10
                self.frame_index = (self.frame_index + 1) % len(self.frames)
        elif self.phase == "burst":
            while self.frame_timer >= 0.05:
                self.frame_timer -= 0.05
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.frame_index = len(self.frames) - 1
                    self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class JohnHealOrbParticleEffect:
    def __init__(self, x: float, y: float) -> None:
        self.x = float(x)
        self.y = float(y)
        self.frame_timer = 0.0
        self.frame_index = 0
        self.finished = False
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "john_heal_orb"
        self.frames = _load_folder_frames(root / "particals") or [pygame.Surface((24, 24), pygame.SRCALPHA)]

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        while self.frame_timer >= 0.08:
            self.frame_timer -= 0.08
            self.frame_index += 1
            if self.frame_index >= len(self.frames):
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


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


class FirzenCharBlastProjectile:
    FRAME_DURATION = 0.08
    BODY_SEGMENT_COUNT = 4
    SPRITE_SCALE = 1.794

    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.origin_x = float(x) + self.facing * owner.hitbox_size[0] / 2
        self.damage = 1
        self.can_damage = True
        self.finished = False
        self.phase = "fly"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.travel_distance = 0.0
        self.speed_x = 650.0
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "firzen_char_blast"
        self.front_frames = _scale_frames(_load_folder_frames(root / "front"), self.SPRITE_SCALE)
        self.body_frames = _scale_frames(_load_folder_frames(root / "body"), self.SPRITE_SCALE)
        self.burst_frames = _scale_frames(_load_folder_frames(root / "burst"), self.SPRITE_SCALE)
        if not self.front_frames or not self.body_frames or not self.burst_frames:
            raise FileNotFoundError(f"Firzen character blast sprites are missing from {root}")
        self.x = float(x) + self.facing * (
            owner.hitbox_size[0] / 2 + self.front_frames[0].get_width() / 2
        )
        self.frames = self.front_frames

    def _start_burst(self, impact_x: float | None = None) -> None:
        if self.phase == "burst":
            return
        if impact_x is not None:
            self.x = impact_x
        self.phase = "burst"
        self.can_damage = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.frames = self.burst_frames

    def segment_rects(self) -> list[pygame.Rect]:
        if self.phase == "burst":
            frame = self.burst_frames[self.frame_index]
            return [pygame.Rect(
                int(self.x - frame.get_width() / 2),
                int(self.y - frame.get_height() / 2),
                frame.get_width(),
                frame.get_height(),
            )]
        front = self.front_frames[self.frame_index % len(self.front_frames)]
        spacing = front.get_width() * 0.58
        body_count = min(self.BODY_SEGMENT_COUNT, int(self.travel_distance / spacing))
        frames = [
            (front, self.x),
            *(
                (
                    self.body_frames[(self.frame_index + index) % len(self.body_frames)],
                    self.x - self.facing * spacing * index,
                )
                for index in range(1, body_count + 1)
            ),
        ]
        return [
            pygame.Rect(
                int(segment_x - frame.get_width() / 2),
                int(self.y - frame.get_height() / 2),
                frame.get_width(),
                frame.get_height(),
            )
            for frame, segment_x in frames
        ]

    def rect(self) -> pygame.Rect:
        return self.segment_rects()[0].unionall(self.segment_rects()[1:])

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        while self.frame_timer >= self.FRAME_DURATION:
            self.frame_timer -= self.FRAME_DURATION
            if self.phase == "fly":
                self.frame_index = (self.frame_index + 1) % max(len(self.front_frames), len(self.body_frames))
            else:
                self.frame_index += 1
                if self.frame_index >= len(self.burst_frames):
                    self.frame_index = len(self.burst_frames) - 1
                    self.finished = True
                    break
        if self.phase == "fly":
            self.x += self.facing * self.speed_x * dt
            self.travel_distance += self.speed_x * dt

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        if self.phase == "burst":
            frame = self.burst_frames[self.frame_index]
            if self.facing < 0:
                frame = pygame.transform.flip(frame, True, False)
            surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))
            return
        for index, rect in enumerate(self.segment_rects()):
            frames = self.front_frames if index == 0 else self.body_frames
            frame = frames[self.frame_index % len(frames)]
            if self.facing < 0:
                frame = pygame.transform.flip(frame, True, False)
            surface.blit(frame, (int(rect.x - camera_x), rect.y))


class FirzenFireProjectile:
    FRAME_DURATION = 0.07

    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.origin_x = float(x) + self.facing * owner.hitbox_size[0] / 2
        self.damage = 1
        self.can_damage = True
        self.finished = False
        self.phase = "fly"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.speed_x = 700.0
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "firzen_fire"
        self.fly_frames = _load_folder_frames(root / "fly")
        self.burst_frames = _load_folder_frames(root / "burst")
        if not self.fly_frames or not self.burst_frames:
            raise FileNotFoundError(f"Firzen fire sprites are missing from {root}")
        self.x = float(x) + self.facing * (
            owner.hitbox_size[0] / 2 + self.fly_frames[0].get_width() / 2
        )
        self.frames = self.fly_frames

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.frames = self.burst_frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(
            int(self.x - frame.get_width() / 2),
            int(self.y - frame.get_height() / 2),
            frame.get_width(),
            frame.get_height(),
        )

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        if self.phase == "fly":
            self.x += self.facing * self.speed_x * dt
            while self.frame_timer >= self.FRAME_DURATION:
                self.frame_timer -= self.FRAME_DURATION
                self.frame_index = (self.frame_index + 1) % len(self.fly_frames)
            return
        while self.frame_timer >= self.FRAME_DURATION:
            self.frame_timer -= self.FRAME_DURATION
            self.frame_index += 1
            if self.frame_index >= len(self.burst_frames):
                self.frame_index = len(self.burst_frames) - 1
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class FirzenFireIceOrb:
    FRAME_DURATION = 0.08

    def __init__(self, owner: Fighter, x: float, y: float) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.speed_y = -650.0
        self.phase = "create"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.finished = False
        self.just_split = False
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "firzen_fire_ice_orb"
        self.create_frames = _load_folder_frames(root / "create")
        self.burst_frames = _load_folder_frames(root / "burst")
        if not self.create_frames or not self.burst_frames:
            raise FileNotFoundError(f"Firzen fire/ice orb sprites are missing from {root}")
        self.frames = self.create_frames

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        if self.phase == "create":
            self.y += self.speed_y * dt
            while self.frame_timer >= self.FRAME_DURATION:
                self.frame_timer -= self.FRAME_DURATION
                self.frame_index += 1
                if self.frame_index >= len(self.create_frames):
                    self.phase = "burst"
                    self.frames = self.burst_frames
                    self.frame_index = 0
                    self.frame_timer = 0.0
                    self.just_split = True
                    break
            return
        while self.frame_timer >= self.FRAME_DURATION:
            self.frame_timer -= self.FRAME_DURATION
            self.frame_index += 1
            if self.frame_index >= len(self.burst_frames):
                self.frame_index = len(self.burst_frames) - 1
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class FirzenTargetOrbProjectile:
    FRAME_DURATION = 0.08
    FLIGHT_DURATION = 0.35

    def __init__(
        self,
        owner: Fighter,
        orb_kind: str,
        x: float,
        y: float,
        target_x: float,
        target_lane_y: float,
        target_y: float,
    ) -> None:
        if orb_kind not in {"ice", "fire"}:
            raise ValueError(f"Unknown Firzen orb kind: {orb_kind}")
        self.owner = owner
        self.orb_kind = orb_kind
        self.x = float(x)
        self.y = float(y)
        self.start_x = self.x
        self.start_y = self.y
        self.target_x = float(target_x)
        self.target_lane_y = float(target_lane_y)
        self.target_y = float(target_y)
        self.facing = 1 if self.target_x >= self.start_x else -1
        self.elapsed = 0.0
        self.phase = "fly"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.finished = False
        self.just_hit_ground = False
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "firzen_fire_ice_orb" / f"{orb_kind}_orb"
        self.fly_frames = _load_folder_frames(root / "fly")
        self.burst_frames = _load_folder_frames(root / "burst")
        if not self.fly_frames or not self.burst_frames:
            raise FileNotFoundError(f"Firzen {orb_kind} orb sprites are missing from {root}")
        self.frames = self.fly_frames

    def _start_burst(self) -> None:
        self.phase = "burst"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.frames = self.burst_frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(
            int(self.x - frame.get_width() / 2),
            int(self.y - frame.get_height() / 2),
            frame.get_width(),
            frame.get_height(),
        )

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        if self.phase == "fly":
            self.elapsed = min(self.FLIGHT_DURATION, self.elapsed + dt)
            progress = self.elapsed / self.FLIGHT_DURATION
            self.x = self.start_x + (self.target_x - self.start_x) * progress
            self.y = self.start_y + (self.target_y - self.start_y) * progress * progress
            while self.frame_timer >= self.FRAME_DURATION:
                self.frame_timer -= self.FRAME_DURATION
                self.frame_index = (self.frame_index + 1) % len(self.fly_frames)
            if self.elapsed >= self.FLIGHT_DURATION:
                self.x = self.target_x
                self.y = self.target_y
                self._start_burst()
                self.just_hit_ground = True
            return
        while self.frame_timer >= self.FRAME_DURATION:
            self.frame_timer -= self.FRAME_DURATION
            self.frame_index += 1
            if self.frame_index >= len(self.burst_frames):
                self.frame_index = len(self.burst_frames) - 1
                self.finished = True
                break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class WoodyShotProjectile:
    FRAME_DURATION = 0.08

    def __init__(self, owner: Fighter, x: float, y: float, facing: int, shot_set: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.damage = 1
        self.can_damage = True
        self.finished = False
        self.phase = "fly"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.speed_x = owner.movement["run_speed"] * 1.25
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "woody_shot"
        self.fly_frames = _load_folder_frames(root / str(shot_set))
        self.burst_frames = _load_folder_frames(root / "burst")
        if not self.fly_frames or not self.burst_frames:
            raise FileNotFoundError(f"Woody shot sprites are missing from {root}")
        self.frames = self.fly_frames

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.frames = self.burst_frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(
            int(self.x - frame.get_width() / 2),
            int(self.y - frame.get_height() / 2),
            frame.get_width(),
            frame.get_height(),
        )

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        if self.phase == "fly":
            self.x += self.facing * self.speed_x * dt
            while self.frame_timer >= self.FRAME_DURATION:
                self.frame_timer -= self.FRAME_DURATION
                self.frame_index += 1
                if self.frame_index >= len(self.fly_frames):
                    self._start_burst()
                    break
        else:
            while self.frame_timer >= self.FRAME_DURATION:
                self.frame_timer -= self.FRAME_DURATION
                self.frame_index += 1
                if self.frame_index >= len(self.burst_frames):
                    self.frame_index = len(self.burst_frames) - 1
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
        if self.facing > 0:
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
    def __init__(
        self,
        character_name: str = "bandit",
        *,
        stage_mode: bool = False,
        test_mode: bool = False,
        enemy_names: tuple[str, ...] | None = None,
    ) -> None:
        if not stage_mode and not test_mode and enemy_names is not None and not enemy_names:
            raise ValueError("Play mode requires at least one opponent.")
        self.font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 24)
        self.pause_font = pygame.font.Font(None, 54)
        self.stage_title_font = pygame.font.Font(None, 82)
        self.stage_subtitle_font = pygame.font.Font(None, 32)
        self.projectiles: list[object] = []
        self.consumable_items: list[SpawnedConsumable | ThrownItem] = []
        self.paused = False
        self.stage_mode = stage_mode
        self.test_mode = test_mode
        self.stage_index = 0
        self.stage_card_timer = STAGE_CARD_DURATION if stage_mode else 0.0
        self.stage_mode_complete = False
        self.stage_mode_failed = False
        self.return_to_menu_requested = False
        stage_root = Path(__file__).resolve().parents[2] / "assets" / "maps" / "The City"
        sounds_root = Path(__file__).resolve().parents[2] / "assets" / "sounds"
        self.stage = CityStage(stage_root)
        item_sprites_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "item_sprites"
        self.item_sprite_animations = _load_item_sprite_animations(item_sprites_root)
        self.item_hand_anchors = load_hand_anchors(item_sprites_root / "hand_anchors.json")
        milk_root = item_sprites_root / "consumables" / "milk"
        milk_animations = self.item_sprite_animations.get("consumables/milk", {})
        self.milk_throw_frames = milk_animations.get("throw", [])
        self.milk_break_frames = {
            effect: milk_animations.get(f"broken/{effect}", [])
            for effect in ("dust", "large", "small")
        }
        if (
            not milk_animations.get("spawn")
            or not self._land_frame_sets_for_item("consumables/milk")
            or not milk_animations.get("holding")
            or not milk_animations.get("drink")
            or not self.milk_throw_frames
            or any(not frames for frames in self.milk_break_frames.values())
        ):
            raise FileNotFoundError(f"Milk sprites are missing from {milk_root}")
        heavy_box_animations = self.item_sprite_animations.get(HEAVY_BOX_ITEM_ID, {})
        self.heavy_box_break_frames = {
            name: heavy_box_animations.get(f"broken/{name}", [])
            for name in ("large_chunk", "small_chunk_1", "small_chunk_2", "tiny_chunk")
        }
        if any(not frames for frames in self.heavy_box_break_frames.values()):
            raise FileNotFoundError(f"Heavy-box break sprites are missing from {item_sprites_root / 'throwables' / 'heavy_box' / 'broken'}")
        self.spawnable_items = sorted(
            item_id
            for item_id, animations in self.item_sprite_animations.items()
            if animations.get("spawn")
            and animations.get("holding")
            and animations.get("throw")
            and self._land_frame_sets_for_item(item_id)
        )
        self.active_item_overlays: dict[Fighter, tuple[str, ItemSpriteAnimation, str | None]] = {}
        self.held_item_animations: dict[Fighter, tuple[str, ItemSpriteAnimation]] = {}
        self.consumable_break_effects: list[
            ConsumableBreakEffect | HeavyBoxBreakEffect | ItemBreakEffect | MetalFragmentEffect
        ] = []
        fragment_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "particals"
        self.rudolf_metal_fragments = [
            _scale_frames(_load_folder_frames(fragment_root / name), 2.0)
            for name in ("metal_fragment_1", "metal_fragment_2")
        ]
        if any(not frames for frames in self.rudolf_metal_fragments):
            raise FileNotFoundError(f"Rudolf shuriken fragments are missing from {fragment_root}")
        rudolf_smoke_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "rudolf_smoke" / "red_smoke"
        self.rudolf_red_smoke_frames = _scale_frames(_load_folder_frames(rudolf_smoke_root), 2.0)
        if not self.rudolf_red_smoke_frames:
            raise FileNotFoundError(f"Rudolf red smoke sprites are missing from {rudolf_smoke_root}")
        self.rudolf_metal_fragment_index = 0
        self.rudolf_clones: list[RudolfClone] = []
        self.rudolf_clone_smoke_effects: list[RudolfSmokeEffect] = []
        self.consumable_spawn_timer = 18.0
        self.audio = AudioBank(sounds_root)
        x_bounds = (self.stage.play_min_x, self.stage.play_max_x)
        start_x = SCREEN_WIDTH / 2
        self.fighter = Fighter(FighterConfig(character_name, CHARACTERS[character_name]), (start_x, 0), x_bounds=x_bounds)
        self.enemy_names = enemy_names
        self.enemies: list[Fighter] = []
        self.enemy_brains: dict[Fighter, BanditBrain] = {}
        self._spawn_encounter(x_bounds, start_x)
        self.camera_focus_x = self._desired_camera_focus_x()
        self.victory_played = False

    def _spawn_encounter(self, x_bounds: tuple[float, float], start_x: float) -> None:
        if self.stage_mode:
            encounter = STAGE_ENCOUNTERS[self.stage_index]
            character_names = [name for name, count in encounter for _ in range(count)]
        elif self.test_mode:
            character_names = []
        else:
            character_names = list(self.enemy_names if self.enemy_names is not None else ("bandit",))
        self.enemies = []
        self.enemy_brains = {}

        for index, character_name in enumerate(character_names):
            x_offset = 220.0 + (index % 3) * 115.0 + (index // 3) * 90.0
            x = min(x_bounds[1], max(x_bounds[0], start_x + x_offset))
            lane_y = 0.0 if len(character_names) == 1 else float(36 + (index % 3) * 90)
            enemy = Fighter(
                FighterConfig(character_name, CHARACTERS[character_name]),
                (x, lane_y),
                x_bounds=x_bounds,
            )
            if not self.stage_mode:
                enemy.max_health = 8
                enemy.health = 8
            enemy.controls_enabled = True
            self.enemies.append(enemy)
            self.enemy_brains[enemy] = BanditBrain()

    @property
    def enemy(self) -> Fighter | None:
        return next(
            (enemy for enemy in self.enemies if not enemy.is_dead),
            self.enemies[0] if self.enemies else None,
        )

    def _target_for(self, fighter: Fighter) -> Fighter | None:
        return self.enemy if fighter is self.fighter else self.fighter

    def _fighters(self) -> list[Fighter]:
        return [self.fighter, *self.enemies, *(clone.fighter for clone in self.rudolf_clones)]

    def _opponents_of(self, fighter: Fighter) -> list[Fighter]:
        if fighter in self.enemies:
            return [self.fighter, *(clone.fighter for clone in self.rudolf_clones)]
        return [enemy for enemy in self.enemies if not enemy.is_dead]

    def _advance_stage_mode(self) -> None:
        if self.stage_index + 1 >= len(STAGE_ENCOUNTERS):
            self.stage_mode_complete = True
            return

        self.stage_index += 1
        x_bounds = (self.stage.play_min_x, self.stage.play_max_x)
        self._spawn_encounter(x_bounds, self.fighter.x)
        self.stage_card_timer = STAGE_CARD_DURATION
        self.victory_played = False

    def _spawn_rudolf_clones(self, fighter: Fighter) -> None:
        if not fighter.rudolf_clones_pending:
            return
        fighter.rudolf_clones_pending = False
        clone_config = FighterConfig("rudolf", CHARACTERS["rudolf"])
        for horizontal_offset, lane_offset in ((-72.0, -18.0), (72.0, 18.0)):
            clone_x = max(
                self.stage.play_min_x,
                min(self.stage.play_max_x, fighter.x + horizontal_offset),
            )
            clone = Fighter(
                clone_config,
                (
                    clone_x,
                    fighter.lane_y + lane_offset,
                ),
                x_bounds=(self.stage.play_min_x, self.stage.play_max_x),
            )
            clone.facing = fighter.facing
            clone.is_rudolf_clone = True
            clone.max_health = 1
            clone.health = 1
            self.rudolf_clones.append(RudolfClone(clone, BanditBrain()))

    def _remove_rudolf_clone(self, clone: RudolfClone) -> None:
        self.rudolf_clones.remove(clone)
        self.rudolf_clone_smoke_effects.append(
            RudolfSmokeEffect(clone.fighter.x, clone.fighter.lane_y, self.rudolf_red_smoke_frames)
        )

    def _remove_finished_rudolf_clones(self) -> None:
        for clone in tuple(self.rudolf_clones):
            if clone.fighter.is_dead or clone.lifetime <= 0.0:
                self._remove_rudolf_clone(clone)

    def _camera_focus_x(self) -> float:
        return self.camera_focus_x

    def _desired_camera_focus_x(self) -> float:
        enemy = self.enemy
        if enemy is None:
            return self.fighter.x
        player_margin = SCREEN_WIDTH * 0.3
        min_focus = self.fighter.x - player_margin
        max_focus = self.fighter.x + player_margin
        enemy_focus = (self.fighter.x + enemy.x) / 2
        return max(min_focus, min(max_focus, enemy_focus))

    def _update_camera_focus(self, dt: float) -> None:
        target_focus_x = self._desired_camera_focus_x()
        blend = 1.0 - math.exp(-CAMERA_FOLLOW_SPEED * dt)
        self.camera_focus_x += (target_focus_x - self.camera_focus_x) * blend

    def _spawn_consumable(self, item_id: str) -> None:
        camera_x = self.stage.camera_x(self._camera_focus_x())
        min_x = max(self.stage.play_min_x, camera_x + 40.0)
        max_x = min(self.stage.play_max_x, camera_x + SCREEN_WIDTH - 40.0)
        animations = self.item_sprite_animations[item_id]
        self.consumable_items.append(
            SpawnedConsumable(
                item_id,
                random.uniform(min_x, max_x),
                random.uniform(LANE_MIN_Y, LANE_MAX_Y),
                animations["spawn"],
                self._land_frame_sets_for_item(item_id),
            )
        )

    def _heavy_box_obstacles(self) -> list[SpawnedConsumable | ThrownItem]:
        return [
            item
            for item in self.consumable_items
            if item.item_id in HEAVY_ITEM_IDS and item.phase == "landed"
        ]

    def _break_heavy_box(self, item: SpawnedConsumable | ThrownItem) -> bool:
        if item.item_id not in HEAVY_ITEM_IDS or item not in self.consumable_items:
            return False
        self.consumable_items.remove(item)
        self.audio.play("heavy_box_break")
        self.consumable_break_effects.append(
            HeavyBoxBreakEffect(
                item.x,
                item.lane_y,
                self.heavy_box_break_frames["large_chunk"],
                self.heavy_box_break_frames["small_chunk_1"],
                self.heavy_box_break_frames["small_chunk_2"],
                self.heavy_box_break_frames["tiny_chunk"],
            )
        )
        return True

    def _break_heavy_box_from_rect(self, attack_rect: pygame.Rect, lane_y: float | None = None) -> bool:
        for item in self._heavy_box_obstacles():
            if lane_y is not None and abs(lane_y - item.lane_y) > 36.0:
                continue
            if attack_rect.colliderect(item.world_rect()):
                return self._break_heavy_box(item)
        return False

    def _resolve_heavy_box_obstruction(self, previous_x_by_fighter: dict[int, float]) -> None:
        for item in self._heavy_box_obstacles():
            obstacle_rect = item.world_rect()
            for fighter in self._fighters():
                if fighter.is_dead or abs(fighter.lane_y - item.lane_y) > 36.0:
                    continue
                fighter_rect = fighter.world_hitbox_rect()
                if not fighter_rect.colliderect(obstacle_rect):
                    continue

                previous_x = previous_x_by_fighter.get(id(fighter), fighter.x)
                half_width = fighter.hitbox_size[0] / 2
                crossed_from_left = previous_x + half_width <= obstacle_rect.left and fighter_rect.right > obstacle_rect.left
                crossed_from_right = previous_x - half_width >= obstacle_rect.right and fighter_rect.left < obstacle_rect.right
                move_left = crossed_from_left or (
                    not crossed_from_right
                    and (previous_x < item.x or (previous_x == item.x and fighter.facing > 0))
                )
                if move_left:
                    fighter.x = max(fighter.min_x, obstacle_rect.left - half_width)
                    if fighter.push_velocity_x > 0.0:
                        fighter.push_velocity_x = 0.0
                else:
                    fighter.x = min(fighter.max_x, obstacle_rect.right + half_width)
                    if fighter.push_velocity_x < 0.0:
                        fighter.push_velocity_x = 0.0

    def _damage_heavy_boxes_with_melee(self) -> None:
        for attacker in self._fighters():
            if (
                attacker.is_dead
                or attacker.state not in (COMBAT_ATTACK_STATES | {"jump_throw"})
                or not attacker.attack_started
                or attacker.has_applied_attack_damage
                or (attacker.state == "jump_throw" and not attacker.jump_attack_active)
            ):
                continue
            luis_contact_attack = attacker.name == "luis" and attacker.state in {"sp_move_attack_1", "sp_vert_attack_1"}
            mark_plow_attack = attacker.name == "mark" and attacker.state == "sp_move_attack_1"
            if attacker.attack_timer <= 0.0 and not (
                (luis_contact_attack or mark_plow_attack) and not attacker.animation_player.finished
            ):
                continue

            attack_range = 72
            if attacker.name == "dark_bat" and attacker.state == "sp_move_attack_1":
                attack_range = 132
            elif attacker.name == "dark_bat" and attacker.state == "jump_throw":
                attack_range = 96
            attack_rect = attacker.world_hitbox_rect().inflate(attack_range, 0)
            for item in self._heavy_box_obstacles():
                if (
                    abs(attacker.lane_y - item.lane_y) <= 36.0
                    and attack_rect.colliderect(item.world_rect())
                    and self._break_heavy_box(item)
                ):
                    attacker.has_applied_attack_damage = True
                    attacker.attack_started = False
                    break

    def _damage_heavy_box_with_projectile(self, projectile: object) -> None:
        if isinstance(projectile, FreezeColumnEffect):
            if not projectile.finished:
                self._break_heavy_box_from_rect(projectile.rect(), projectile.lane_y)
            return
        if isinstance(projectile, JulianExplosionEffect):
            if projectile.finished:
                return
            for item in self._heavy_box_obstacles():
                dx = item.world_rect().centerx - projectile.x
                dy = item.lane_y - projectile.lane_y
                if dx * dx + dy * dy <= projectile.radius * projectile.radius:
                    self._break_heavy_box(item)
                    break
            return
        if not getattr(projectile, "can_damage", False):
            return

        rect_method = getattr(projectile, "rect", None)
        if not callable(rect_method):
            return
        owner = getattr(projectile, "owner", None)
        lane_y = getattr(projectile, "lane_y", getattr(owner, "lane_y", None))
        self._break_heavy_box_from_rect(rect_method(), lane_y)

    def _try_pick_up_consumable(self, fighter: Fighter, inputs: FighterInput) -> bool:
        if (
            not inputs.attack_just_pressed
            or fighter.held_item is not None
            or not fighter.controls_enabled
            or fighter.state != "idle"
            or fighter.z != 0
            or any((inputs.left, inputs.right, inputs.up, inputs.down))
        ):
            return False
        for item in self.consumable_items:
            pickup_range = 56.0
            if item.item_id in HEAVY_ITEM_IDS:
                pickup_range = max(pickup_range, item.world_rect().width / 2 + fighter.hitbox_size[0] / 2)
            if item.pickupable and abs(fighter.x - item.x) <= pickup_range and abs(fighter.lane_y - item.lane_y) <= 24.0:
                self.consumable_items.remove(item)
                fighter.state = "get_up"
                fighter.state_timer = 0.36
                fighter.held_item = item.item_id
                fighter.held_item_landings = item.landing_count
                return True
        return False

    def _item_to_drink(self, fighter: Fighter, inputs: FighterInput) -> str | None:
        if (
            fighter.held_item is None
            or not (inputs.attack_just_pressed or inputs.drink_just_pressed)
            or fighter.z != 0
            or fighter.state in (COMBAT_ATTACK_STATES | {"grapple", "grappled", "jump_throw", "die", "dead"})
        ):
            return None
        if _is_throwable_item(fighter.held_item) or "drink" not in self.item_sprite_animations.get(fighter.held_item, {}):
            return None
        return fighter.held_item

    def start_item_overlay(
        self,
        fighter: Fighter,
        item_id: str,
        action: str,
        active_state: str | None = None,
    ) -> bool:
        frames = self.item_sprite_animations.get(item_id, {}).get(action)
        if not frames:
            return False
        should_loop = action == "drink" and active_state is not None
        self.active_item_overlays[fighter] = (action, ItemSpriteAnimation(frames, loop=should_loop), active_state)
        return True

    def _land_frame_sets_for_item(self, item_id: str) -> list[tuple[str, list[pygame.Surface]]]:
        animations = self.item_sprite_animations.get(item_id, {})
        return [
            (action, animations[action])
            for action in sorted(animations)
            if action == "land" or action.startswith("land/")
        ]

    def _handle_held_item_throw_input(self, fighter: Fighter, inputs: FighterInput) -> bool:
        chord_pressed = (
            inputs.attack_just_pressed and inputs.block_pressed
        ) or (
            inputs.attack_pressed and inputs.block_just_pressed
        )
        if (
            not chord_pressed
            or fighter.held_item is None
            or fighter.item_throw_animation is not None
            or not fighter.controls_enabled
            or fighter.state
            in (
                COMBAT_ATTACK_STATES
                | {
                    "fall",
                    "get_up",
                    "henry_float",
                    "knocked_fire",
                    "knocked_freeze",
                    "die",
                    "dead",
                    "block_break",
                    "block_dodge",
                    "grapple",
                    "grappled",
                    "grapple_hit",
                    "hurt",
                    "lift_heavy",
                }
            )
        ):
            return False

        item_id = fighter.held_item
        item_animations = self.item_sprite_animations.get(item_id, {})
        if not item_animations.get("throw") or not self._land_frame_sets_for_item(item_id):
            fighter._show_speech("Cannot throw item!")
            return True

        airborne = fighter.z > 0 or fighter.velocity_z != 0
        animation_name = (
            "jump_throw"
            if airborne
            else ("throw_heavy" if item_id in HEAVY_ITEM_IDS else "spawn")
        )
        if inputs.left != inputs.right:
            fighter.facing = -1 if inputs.left else 1
        if not fighter.start_item_throw(animation_name, airborne):
            fighter._show_speech("Cannot throw item!")
        return True

    @staticmethod
    def _suppress_item_throw_inputs(inputs: FighterInput) -> FighterInput:
        return replace(
            inputs,
            left=False,
            right=False,
            up=False,
            down=False,
            run=False,
            horizontal_move_active=False,
            attack_pressed=False,
            attack_just_pressed=False,
            block_pressed=False,
            block_just_pressed=False,
            jump_just_pressed=False,
            drink_just_pressed=False,
        )

    def _finish_held_item_throw(self, fighter: Fighter) -> None:
        animation_name = fighter.item_throw_animation
        if animation_name is None:
            return
        if fighter.state not in {"item_throw", "jump_throw", "get_up"}:
            fighter.item_throw_animation = None
            return
        if not fighter.animation_player.finished:
            return

        item_id = fighter.held_item
        if item_id is not None:
            item_animations = self.item_sprite_animations[item_id]
            throw_frames = item_animations["throw"]
            land_frame_sets = self._land_frame_sets_for_item(item_id)
            if not land_frame_sets:
                raise ValueError(f"No land animation frames found for thrown item {item_id}")

            facing = fighter.facing
            start_x = fighter.x + facing * 32.0
            if item_id in HEAVY_ITEM_IDS:
                distance_multiplier = HEAVY_ITEM_DISTANCE_MULTIPLIER
            elif _is_throwable_item(item_id):
                distance_multiplier = THROWABLE_DISTANCE_MULTIPLIER
            else:
                distance_multiplier = 1.0
            end_x = fighter.x + facing * THROWN_ITEM_MAX_DISTANCE * distance_multiplier
            start_x = max(self.stage.play_min_x, min(self.stage.play_max_x, start_x))
            end_x = max(self.stage.play_min_x, min(self.stage.play_max_x, end_x))
            self.consumable_items.append(
                ThrownItem(
                    fighter,
                    item_id,
                    start_x,
                    end_x,
                    fighter.lane_y,
                    fighter.z + 48.0,
                    fighter.movement["run_speed"] * 1.25,
                    facing,
                    throw_frames,
                    land_frame_sets,
                    fighter.held_item_landings,
                )
            )
            fighter.held_item = None
            fighter.held_item_landings = 0

        fighter.item_throw_animation = None
        if fighter.state == "item_throw":
            fighter.state = "idle"

    def _resolve_thrown_item_hits(self) -> None:
        for item in tuple(self.consumable_items):
            if not isinstance(item, ThrownItem) or item.phase != "thrown":
                continue
            heavy_box = next(
                (
                    obstacle
                    for obstacle in self._heavy_box_obstacles()
                    if abs(obstacle.lane_y - item.lane_y) <= 28.0
                    and item.world_rect().colliderect(obstacle.world_rect())
                ),
                None,
            )
            if heavy_box is not None:
                self._break_heavy_box(heavy_box)
                item.drop_at_hit()
                continue
            target = next(
                (
                    target
                    for target in self._opponents_of(item.owner)
                    if not target.is_dead
                    and abs(target.lane_y - item.lane_y) <= 28.0
                    and item.world_rect().colliderect(target.world_hitbox_rect())
                ),
                None,
            )
            if target is None:
                continue

            item.drop_at_hit()
            if target.state == "block" and target.block_strength > 0:
                target.block_strength = 0
                target.block_hold_timer = 0.0
                self.audio.play("hit_guard")
            elif target.state == "block":
                target._start_block_break()
                self.audio.play("hit_guard")
            else:
                previous_health = target.health
                target.receive_damage(1)
                if target.health < previous_health:
                    self.audio.play("hit_success")

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

    def _character_hand_anchor(self, fighter: Fighter, fallback_to_idle: bool = True) -> HandAnchor | None:
        character_anchors = self.item_hand_anchors.get(fighter.name)
        if character_anchors is None:
            return None

        animation_name = fighter.animation_player.current_name
        is_heavy_item = fighter.held_item in HEAVY_ITEM_IDS
        anchor_animation_name = (
            HEAVY_ITEM_ANCHOR_KEYS.get(animation_name, HEAVY_ITEM_ANCHOR_KEYS["idle"])
            if is_heavy_item
            else animation_name
        )
        frame_index = fighter.animation_player.frame_index
        animation_anchors = character_anchors.get(anchor_animation_name, [])
        if frame_index < len(animation_anchors) and animation_anchors[frame_index] is not None:
            return animation_anchors[frame_index]

        if not fallback_to_idle:
            return None
        idle_key = HEAVY_ITEM_ANCHOR_KEYS["idle"] if is_heavy_item else "idle"
        idle_anchors = character_anchors.get(idle_key, [])
        return next((anchor for anchor in idle_anchors if anchor is not None), None)

    def _draw_item_sprite(
        self,
        surface: pygame.Surface,
        fighter: Fighter,
        frame: pygame.Surface,
        camera_x: float,
        fallback_anchor: HandAnchor,
        fallback_to_idle: bool = True,
    ) -> None:
        anchor = self._character_hand_anchor(fighter, fallback_to_idle)
        if anchor is None:
            anchor = fallback_anchor
        horizontal_anchor, vertical_anchor = anchor
        if fighter.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
            horizontal_anchor = 1 - horizontal_anchor
        fighter_frame = fighter.animation_player.current_frame
        draw_x, draw_y = fighter.draw_pos(camera_x)
        hand_x = draw_x + fighter_frame.get_width() * horizontal_anchor
        hand_y = draw_y + fighter_frame.get_height() * vertical_anchor
        surface.blit(frame, frame.get_rect(center=(int(hand_x), int(hand_y))))

    def _draw_held_item(self, surface: pygame.Surface, fighter: Fighter, camera_x: float) -> None:
        if fighter.held_item is None:
            return
        frames = self.item_sprite_animations.get(fighter.held_item, {}).get("holding")
        if not frames:
            return
        held_animation = self.held_item_animations.get(fighter)
        if held_animation is None or held_animation[0] != fighter.held_item:
            animation = ItemSpriteAnimation(frames, loop=True)
            self.held_item_animations[fighter] = (fighter.held_item, animation)
        else:
            _, animation = held_animation
        self._draw_item_sprite(
            surface,
            fighter,
            animation.current_frame,
            camera_x,
            fallback_anchor=(
                HEAVY_ITEM_FALLBACK_ANCHOR
                if fighter.held_item in HEAVY_ITEM_IDS
                else (0.30, 0.62)
            ),
        )

    def _draw_item_overlay(self, surface: pygame.Surface, fighter: Fighter, camera_x: float) -> None:
        active_overlay = self.active_item_overlays.get(fighter)
        if active_overlay is None:
            return
        action, animation, _ = active_overlay
        is_drink_overlay = action == "drink"
        fallback_anchor = (0.68, 0.22) if is_drink_overlay else (0.68, 0.54)
        item_frame = animation.current_frame
        character_drink = fighter.animation_player.animations.get("drink")
        if (
            is_drink_overlay
            and fighter.animation_player.current_name == "drink"
            and character_drink is not None
            and len(animation.frames) == len(character_drink["surfaces"])
        ):
            item_frame = animation.frames[fighter.animation_player.frame_index]
        self._draw_item_sprite(
            surface,
            fighter,
            item_frame,
            camera_x,
            fallback_anchor,
            fallback_to_idle=not is_drink_overlay,
        )

    def _resolve_freeze_column_obstruction(self, previous_x_by_fighter: dict[int, float]) -> None:
        columns = [projectile for projectile in self.projectiles if isinstance(projectile, FreezeColumnEffect) and not projectile.finished]
        for fighter in self._fighters():
            if fighter.is_dead or fighter.z > 0:
                continue
            previous_x = previous_x_by_fighter.get(id(fighter), fighter.x)
            half_width = fighter.hitbox_size[0] / 2
            for column in columns:
                if column.owner is fighter:
                    continue
                if abs(fighter.lane_y - column.lane_y) > 36:
                    continue
                column_rect = column.rect()
                fighter_rect = fighter.world_hitbox_rect()
                if fighter_rect.top >= column_rect.bottom or fighter_rect.bottom <= column_rect.top:
                    continue

                crossed_from_left = previous_x + half_width <= column_rect.left and fighter_rect.right > column_rect.left
                crossed_from_right = previous_x - half_width >= column_rect.right and fighter_rect.left < column_rect.right
                if not column_rect.colliderect(fighter_rect) and not crossed_from_left and not crossed_from_right:
                    continue
                move_left = crossed_from_left or (
                    not crossed_from_right
                    and (previous_x < column.x or (previous_x == column.x and fighter.facing > 0))
                )
                if move_left:
                    fighter.x = max(fighter.min_x, column_rect.left - half_width)
                    if fighter.push_velocity_x > 0:
                        fighter.push_velocity_x = 0.0
                else:
                    fighter.x = min(fighter.max_x, column_rect.right + half_width)
                    if fighter.push_velocity_x < 0:
                        fighter.push_velocity_x = 0.0

    def _break_freeze_columns_with_melee(self) -> None:
        columns = [projectile for projectile in self.projectiles if isinstance(projectile, FreezeColumnEffect)]
        for attacker in self._fighters():
            if (
                attacker.is_dead
                or attacker.state not in (COMBAT_ATTACK_STATES | {"jump_throw"})
                or not attacker.attack_started
                or attacker.has_applied_attack_damage
                or attacker.attack_timer <= 0
                or (attacker.state == "jump_throw" and not attacker.jump_attack_active)
                or (attacker.name == "freeze" and attacker.state == "sp_move_attack_2")
            ):
                continue
            attack_range = 132 if attacker.name == "dark_bat" and attacker.state == "sp_move_attack_1" else 72
            attack_rect = attacker.world_hitbox_rect().inflate(attack_range, 0)
            for column in columns:
                if column.finished:
                    continue
                if abs(attacker.lane_y - column.lane_y) <= 36 and attack_rect.colliderect(column.rect()):
                    column.break_apart()

    def _handle_combat(self) -> None:
        self._damage_heavy_boxes_with_melee()
        self._break_freeze_columns_with_melee()
        for attacker in self._fighters():
            defenders = self._opponents_of(attacker)
            if attacker.is_dead or all(defender.is_dead or defender.state == "henry_float" for defender in defenders):
                continue
            if (
                attacker.name == "mark"
                and attacker.state == "sp_move_attack_1"
                and len(attacker.mark_sp_move_attack_1_targets_hit) >= 2
            ):
                continue
            if attacker.name == "luis_liberated" and attacker.state == "sp_vert_attack_1":
                self._handle_luis_liberated_dash_hits(attacker, defender)
                continue
            if attacker.state not in (COMBAT_ATTACK_STATES | {"jump_throw"}):
                continue
            if (
                attacker.state == "basic_attack"
                and (
                    attacker.name == "hunter"
                    or (attacker.name == "rudolf" and not attacker.is_rudolf_clone)
                )
            ):
                continue
            if attacker.name == "henry" and attacker.state in {"basic_attack", "sp_move_attack_1", "sp_vert_attack_1", "sp_vert_attack_2"}:
                continue
            if attacker.name == "bat" and attacker.state in {"sp_move_attack_2", "sp_vert_attack_2"}:
                continue
            if attacker.name == "davis" and attacker.state == "sp_move_attack_1":
                continue
            if attacker.name in {"denis", "jack", "axle"} and attacker.state == "sp_move_attack_1":
                continue
            if attacker.name == "denis" and attacker.state == "sp_vert_attack_2":
                continue
            if attacker.name == "jan" and attacker.state in {"sp_vert_attack_1", "sp_vert_attack_2"}:
                continue
            if attacker.name == "monk" and attacker.state == "sp_move_attack_1":
                continue
            if attacker.name == "john" and attacker.state in {"sp_move_attack_1", "sp_move_attack_2", "sp_vert_attack_1", "sp_vert_attack_2"}:
                continue
            if attacker.name == "sorcerer" and attacker.state in {"sp_move_attack_1", "sp_move_attack_2", "sp_vert_attack_2"}:
                continue
            if attacker.name == "woody" and attacker.state in {"sp_move_attack_1", "sp_move_attack_2", "sp_vert_attack_1", "sp_vert_attack_2"}:
                continue
            if attacker.name == "luis" and attacker.state == "sp_move_attack_2":
                continue
            if attacker.name == "julian" and attacker.state in {"sp_move_attack_1", "sp_move_attack_2", "sp_vert_attack_1", "sp_vert_attack_2"}:
                continue
            if attacker.name == "firen" and attacker.state in {"sp_move_attack_1", "sp_move_attack_2", "sp_vert_attack_1", "sp_vert_attack_2"}:
                continue
            if attacker.name == "freeze" and attacker.state in {"sp_move_attack_1", "sp_move_attack_2", "sp_vert_attack_1"}:
                continue
            if attacker.state == "jump_throw" and not attacker.jump_attack_active:
                continue
            if attacker.has_applied_attack_damage:
                continue
            if not attacker.attack_started:
                continue
            luis_contact_attack = attacker.name == "luis" and attacker.state in {"sp_move_attack_1", "sp_vert_attack_1"}
            mark_plow_attack = attacker.name == "mark" and attacker.state == "sp_move_attack_1"
            if attacker.attack_timer <= 0 and not (
                (luis_contact_attack or mark_plow_attack) and not attacker.animation_player.finished
            ):
                attacker.has_applied_attack_damage = True
                attacker.attack_started = False
                continue
            attack_range = 72
            if attacker.name == "dark_bat" and attacker.state == "sp_move_attack_1":
                attack_range = 132
            if attacker.name == "dark_bat" and attacker.state == "jump_throw" and attacker.jump_attack_active:
                attack_range = 96
            attack_rect = attacker.world_hitbox_rect().inflate(attack_range, 0)
            defender = next(
                (
                    target
                    for target in defenders
                    if not target.is_dead
                    and target.state != "henry_float"
                    and abs(attacker.lane_y - target.lane_y) <= 36
                    and attack_rect.colliderect(target.world_hitbox_rect())
                ),
                None,
            )
            if defender is None:
                if luis_contact_attack or mark_plow_attack:
                    continue
                attacker.has_applied_attack_damage = True
                attacker.attack_started = False
                if attacker.name == "freeze" and attacker.state == "basic_attack":
                    self.audio.play_freeze_basic_miss()
                else:
                    self.audio.play_hit_miss()
                continue
            if mark_plow_attack and id(defender) in attacker.mark_sp_move_attack_1_targets_hit:
                attacker.has_applied_attack_damage = True
                attacker.attack_started = False
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

            previous_health = defender.health
            defender.receive_damage(attacker.touch_damage)
            if mark_plow_attack:
                if defender.health < previous_health:
                    attacker.mark_sp_move_attack_1_targets_hit.add(id(defender))
            if not defender.is_dead:
                if attacker.state == "jump_throw" and attacker.jump_attack_active:
                    defender._start_knockdown()
                elif attacker.state == "sp_vert_attack_1":
                    if attacker.name in {"deep", "template", "jack", "axle"}:
                        defender._start_launch_knockdown()
                    elif attacker.name == "davis":
                        defender._start_knockdown()
                    else:
                        defender._start_knockdown()
                elif attacker.name == "jack" and attacker.state == "sp_move_attack_2":
                    defender._start_knockdown()
                elif attacker.name == "axle" and attacker.state == "sp_move_attack_2":
                    defender._start_knockdown()
                elif attacker.name == "luis" and attacker.state == "sp_move_attack_1":
                    defender._start_knockdown()
                elif mark_plow_attack:
                    defender._start_knockdown()
            if attacker.name in {"knight", "luis_liberated"}:
                self.audio.play("sword_cut")
            elif attacker.name == "dark_bat" and attacker.state in {"sp_move_attack_1", "jump_throw"}:
                self.audio.play("sword_cut")
            elif attacker.name in {"deep", "armored_bandit"} and attacker.state in {"sp_vert_attack_1", "sp_vert_attack_2", "sp_move_attack_2"}:
                self.audio.play("sword_cut")
            elif attacker.name in {"deep", "armored_bandit"}:
                self.audio.play("sword_cut")
            elif attacker.name == "freeze" and attacker.state == "basic_attack":
                self.audio.play("hit_success")
            else:
                self.audio.play("hit_success")
            if mark_plow_attack and len(attacker.mark_sp_move_attack_1_targets_hit) >= 2:
                attacker.state = "idle"
                attacker.attack_timer = 0.0
                attacker.has_applied_attack_damage = False
                attacker.attack_started = False
                attacker.attack_projectile_fired = False
                attacker.special_move_followup_state = None
                attacker.animation_player.play("idle")

    def _handle_luis_liberated_dash_hits(self, attacker: Fighter, defender: Fighter) -> None:
        while attacker.luis_liberated_swing_hits_pending:
            attacker.luis_liberated_swing_hits_pending.pop(0)
            if self._break_heavy_box_from_rect(attacker.world_hitbox_rect().inflate(72, 0), attacker.lane_y):
                continue
            if abs(attacker.lane_y - defender.lane_y) > 36:
                continue
            if not attacker.world_hitbox_rect().inflate(72, 0).colliderect(defender.world_hitbox_rect()):
                continue
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
            self.audio.play("sword_cut")

    def _handle_woody_punches(self) -> None:
        for fighter in self._fighters():
            while fighter.woody_punches_pending:
                animation_name, frame_index = fighter.woody_punches_pending.pop(0)
                punch_frames = (1, 5, 9) if animation_name == "sp_move_attack_2" else (2, 5, 7)
                if fighter.name != "woody" or frame_index not in punch_frames:
                    continue
                attack_rect = fighter.world_hitbox_rect().inflate(84, 0)
                if self._break_heavy_box_from_rect(attack_rect, fighter.lane_y):
                    continue
                target = next(
                    (
                        opponent
                        for opponent in self._opponents_of(fighter)
                        if not opponent.is_dead
                        and abs(opponent.lane_y - fighter.lane_y) <= 36
                        and attack_rect.colliderect(opponent.world_hitbox_rect())
                    ),
                    None,
                )
                if target is None:
                    self.audio.play_hit_miss()
                    continue
                if target.state == "block" and target.block_strength > 0:
                    target.block_strength = 0
                    target.block_hold_timer = 0.0
                    self.audio.play("hit_guard")
                    continue
                if target.state == "block":
                    target._start_block_break()
                    self.audio.play("hit_guard")
                    continue
                target.receive_damage(fighter.touch_damage)
                self.audio.play("hit_success")

    def _handle_woody_dash_hits(self, previous_x_by_fighter: dict[int, float]) -> None:
        for fighter in self._fighters():
            if fighter.name != "woody" or not fighter.woody_vert_dash_active:
                continue
            current_rect = fighter.world_hitbox_rect()
            previous_x = previous_x_by_fighter.get(id(fighter), fighter.x)
            previous_rect = current_rect.move(round(previous_x - fighter.x), 0)
            swept_rect = current_rect.union(previous_rect)
            self._break_heavy_box_from_rect(swept_rect, fighter.lane_y)
            for target in self._opponents_of(fighter):
                if (
                    target.is_dead
                    or id(target) in fighter.woody_vert_dash_hit_targets
                    or abs(target.lane_y - fighter.lane_y) > 36
                    or not swept_rect.colliderect(target.world_hitbox_rect())
                ):
                    continue
                fighter.woody_vert_dash_hit_targets.add(id(target))
                if target.state == "block" and target.block_strength > 0:
                    target.block_strength = 0
                    target.block_hold_timer = 0.0
                    self.audio.play("hit_guard")
                    continue
                if target.state == "block":
                    target._start_block_break()
                    self.audio.play("hit_guard")
                    continue
                target.receive_damage(fighter.touch_damage)
                if not target.is_dead:
                    target._start_knockdown()
                    target.push_velocity_x = fighter.facing * fighter.movement["run_speed"]
                self.audio.play("hit_success")

    def _handle_audio(self, dt: float) -> None:
        self.audio.update_sequences()
        fighters = self._fighters()

        for fighter in fighters:
            while fighter.rudolf_sounds_pending:
                self.audio.play(fighter.rudolf_sounds_pending.pop(0))
            while fighter.luis_sounds_pending:
                self.audio.play(fighter.luis_sounds_pending.pop(0))
            if fighter.woody_yell_sfx_pending:
                self.audio.play("woody_yell")
                fighter.woody_yell_sfx_pending = False
            if fighter.woody_shadowstep_sfx_pending:
                self.audio.play("woody_shadowstep")
                fighter.woody_shadowstep_sfx_pending = False
            if fighter.sorcerer_healed_target_sfx_pending:
                self.audio.play("healed_target")
                fighter.sorcerer_healed_target_sfx_pending = False
            if fighter.knight_sword_swing_sfx_pending:
                self.audio.play("sword_swing")
                fighter.knight_sword_swing_sfx_pending = False
            if fighter.knight_armor_hit_sfx_pending is not None:
                self.audio.play(fighter.knight_armor_hit_sfx_pending)
                fighter.knight_armor_hit_sfx_pending = None
            if fighter.hunter_draw_arrow_sfx_pending:
                self.audio.play("draw_arrow")
                fighter.hunter_draw_arrow_sfx_pending = False
            if fighter.jack_yell_sfx_pending:
                self.audio.play("jack_yell")
                fighter.jack_yell_sfx_pending = False
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
            if fighter.axle_uppercut_shear_sfx_pending:
                self.audio.play("uppercut_shear")
                fighter.axle_uppercut_shear_sfx_pending = False
            if fighter.axle_dash_attack_sfx_pending:
                self.audio.play("axle_dash_attack")
                fighter.axle_dash_attack_sfx_pending = False
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
            if fighter.freeze_break_sfx_pending:
                self.audio.play("freeze_break")
                fighter.freeze_break_sfx_pending = False
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

        if self.enemies and all(enemy.is_dead for enemy in self.enemies) and not self.victory_played:
            self.audio.play("win")
            self.victory_played = True

    def _spawn_hunter_projectile(self, fighter: Fighter) -> None:
        if fighter.name not in {"hunter", "henry", "rudolf"}:
            return
        if fighter.name == "rudolf" and fighter.state != "basic_attack":
            return
        if fighter.state not in {"basic_attack", "jump_throw"} and not (fighter.name == "henry" and fighter.state == "sp_move_attack_1"):
            return
        if not fighter.attack_started or fighter.attack_projectile_fired:
            return

        fighter.attack_projectile_fired = True
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 58.0
        style = fighter.hunter_projectile_style
        if fighter.name in {"henry", "hunter"} and fighter.state == "basic_attack":
            style = "henry_basic"
        elif fighter.name == "rudolf":
            style = "rudolf"
        self.projectiles.append(ArrowProjectile(fighter, origin_x, origin_y, fighter.facing, style))
        if style == "enchanted":
            self.audio.play("arrow_enchanted_shot")
        elif fighter.name != "rudolf":
            fighter.hunter_shoot_arrow_sfx_pending = True

    def _spawn_rudolf_shurikens(self, fighter: Fighter) -> None:
        if fighter.name != "rudolf" or fighter.state != "sp_move_attack_1":
            return
        while fighter.rudolf_shuriken_lanes_pending:
            target_lane_y = fighter.rudolf_shuriken_lanes_pending.pop(0)
            origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
            origin_y = GROUND_Y + fighter.lane_y - fighter.z - 58.0
            self.projectiles.append(
                ArrowProjectile(
                    fighter,
                    origin_x,
                    origin_y,
                    fighter.facing,
                    "rudolf",
                    target_lane_y=target_lane_y,
                )
            )

    def _spawn_jack_blast(self, fighter: Fighter) -> None:
        if fighter.name != "jack" or fighter.state != "sp_move_attack_1" or not fighter.jack_blast_pending:
            return
        fighter.jack_blast_pending = False
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 56.0
        self.projectiles.append(JackBlastProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.audio.play("jack_blast")

    def _spawn_axle_shot(self, fighter: Fighter) -> None:
        if fighter.name != "axle" or fighter.state != "sp_move_attack_1" or not fighter.axle_shot_pending:
            return
        fighter.axle_shot_pending = False
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.48)
        origin_y = fighter.world_hitbox_rect().centery
        self.projectiles.append(AxleShotProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.audio.play("axle_shot")

    def _spawn_julian_skull(self, fighter: Fighter) -> None:
        if fighter.name != "julian" or fighter.state != "sp_move_attack_1" or not fighter.julian_skull_pending:
            return
        fighter.julian_skull_pending = False
        target = self._target_for(fighter)
        if target is not None and target.is_dead:
            target = None
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.48)
        origin_y = fighter.world_hitbox_rect().centery
        self.projectiles.append(JulianSkullProjectile(fighter, target, origin_x, origin_y, fighter.facing))
        self.audio.play("julian_skull_shot")

    def _spawn_julian_ball(self, fighter: Fighter) -> None:
        if fighter.name != "julian" or fighter.state != "sp_move_attack_2" or not fighter.julian_ball_pending:
            return
        fighter.julian_ball_pending = False
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.48)
        origin_y = fighter.world_hitbox_rect().centery
        self.projectiles.append(JulianBallProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.audio.play("julian_ball_create")

    def _spawn_julian_explosions(self, fighter: Fighter) -> None:
        if fighter.name != "julian":
            return
        hitbox = fighter.world_hitbox_rect()
        if fighter.state == "sp_vert_attack_1" and fighter.julian_sp_vert_attack_1_pending:
            fighter.julian_sp_vert_attack_1_pending = False
            self.projectiles.append(
                JulianExplosionEffect(fighter, hitbox.centerx, hitbox.bottom, radius=160.0, launch=True)
            )
        if fighter.state == "sp_vert_attack_2" and fighter.julian_sp_vert_attack_2_pending:
            fighter.julian_sp_vert_attack_2_pending = False
            self.projectiles.append(
                JulianExplosionEffect(fighter, hitbox.centerx, hitbox.bottom, radius=280.0, launch=False)
            )

    def _spawn_john_blast(self, fighter: Fighter) -> None:
        if fighter.name != "john" or fighter.state != "sp_move_attack_1" or not fighter.john_blast_pending:
            return
        fighter.john_blast_pending = False
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.48)
        origin_y = fighter.world_hitbox_rect().centery
        self.projectiles.append(JohnBlastCreateEffect(origin_x, origin_y, fighter.facing))
        self.projectiles.append(JohnBlastProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.audio.play("john_blast_create")

    def _spawn_john_barrier(self, fighter: Fighter) -> None:
        if fighter.name != "john" or fighter.state != "sp_move_attack_2" or not fighter.john_barrier_pending:
            return
        fighter.john_barrier_pending = False
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.68)
        origin_y = fighter.world_hitbox_rect().centery
        self.projectiles.append(JohnBarrierEffect(fighter, origin_x, origin_y, fighter.facing))
        self.audio.play("john_barrier_create")

    def _spawn_john_follow_disk(self, fighter: Fighter) -> None:
        if fighter.name != "john" or fighter.state != "sp_vert_attack_1" or not fighter.john_follow_disk_pending:
            return
        fighter.john_follow_disk_pending = False
        target = self._target_for(fighter)
        if target is not None and target.is_dead:
            target = None
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.52)
        origin_y = fighter.world_hitbox_rect().bottom - 54.0
        self.projectiles.append(JohnFollowDiskProjectile(fighter, target, origin_x, origin_y, fighter.facing))

    def _spawn_john_heal_orb(self, fighter: Fighter) -> None:
        if fighter.name != "john" or fighter.state != "sp_vert_attack_2" or not fighter.john_heal_orb_pending:
            return
        fighter.john_heal_orb_pending = False
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.72)
        origin_y = fighter.world_hitbox_rect().centery
        self.projectiles.append(JohnHealOrbProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.projectiles.append(JohnHealOrbParticleEffect(origin_x, origin_y))
        self.audio.play("john_heal_orb")

    def _spawn_sorcerer_heal_orb(self, fighter: Fighter) -> None:
        if fighter.name != "sorcerer" or fighter.state != "sp_vert_attack_2" or not fighter.sorcerer_heal_orb_pending:
            return
        fighter.sorcerer_heal_orb_pending = False
        fighter.health = min(fighter.max_health, fighter.health + 5)
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.72)
        origin_y = fighter.world_hitbox_rect().centery
        self.projectiles.append(JohnHealOrbProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.projectiles.append(JohnHealOrbParticleEffect(origin_x, origin_y))
        self.audio.play("john_heal_orb")

    def _spawn_freeze_ball(self, fighter: Fighter) -> None:
        if fighter.name != "freeze" or fighter.state != "sp_move_attack_1":
            return
        if not fighter.freeze_ball_pending or fighter.freeze_ball_spawned:
            return
        fighter.freeze_ball_pending = False
        fighter.attack_projectile_fired = True
        fighter.freeze_ball_spawned = True
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 56.0
        self.projectiles.append(FreezeBallProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.audio.play("freeze_ball")

    def _spawn_sorcerer_freeze_ball(self, fighter: Fighter) -> None:
        if fighter.name != "sorcerer" or fighter.state != "sp_move_attack_2" or not fighter.sorcerer_freeze_ball_pending:
            return
        fighter.sorcerer_freeze_ball_pending = False
        fighter.attack_projectile_fired = True
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 56.0
        self.projectiles.append(FreezeBallProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.audio.play("freeze_ball")

    def _spawn_freeze_columns(self, fighter: Fighter) -> None:
        if fighter.name != "freeze" or not fighter.freeze_columns_pending:
            return
        fighter.freeze_columns_pending = False
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "freeze_colum"
        first_frames = _load_folder_frames(root / "freeze_colum_1")
        column_width = first_frames[0].get_width() if first_frames else fighter.hitbox_size[0]
        column_direction = fighter.facing
        spacing = column_width * 0.65
        first_x = fighter.x + column_direction * (fighter.hitbox_size[0] / 2 + column_width * 1.8 / 2)
        ground_y = GROUND_Y + fighter.lane_y
        for column_number in (1, 2, 3):
            x = first_x + column_direction * spacing * (column_number - 1)
            self.projectiles.append(FreezeColumnEffect(x, ground_y, column_number, fighter.facing, fighter.lane_y))
            self.audio.play("freeze_colum")

    def _spawn_freeze_tornado(self, fighter: Fighter) -> None:
        if fighter.name != "freeze" or not fighter.freeze_tornado_pending:
            return
        fighter.freeze_tornado_pending = False
        hitbox = fighter.world_hitbox_rect()
        origin_x = hitbox.centerx + fighter.facing * (fighter.hitbox_size[0] * 0.48)
        origin_y = hitbox.bottom - 48.0
        self.projectiles.append(FreezeTornadoProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.audio.play("freeze_tornado")

    def _spawn_henry_vertical_volley(self, fighter: Fighter) -> None:
        if fighter.name != "henry" or fighter.state != "sp_vert_attack_1":
            return
        if not fighter.attack_started or fighter.attack_projectile_fired:
            return

        fighter.attack_projectile_fired = True
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 58.0
        for angle in (-40.0, -34.0, -28.0, -22.0, -16.0):
            vertical_speed = math.tan(math.radians(angle)) * ArrowProjectile.HENRY_SPEED_X
            self.projectiles.append(
                ArrowProjectile(fighter, origin_x, origin_y, fighter.facing, "henry_vertical", vertical_speed)
            )
        fighter.hunter_shoot_arrow_sfx_pending = True

    def _apply_henry_flute_attack(self, fighter: Fighter) -> None:
        if fighter.name != "henry" or not fighter.henry_sp_vert_attack_2_pending:
            return

        fighter.henry_sp_vert_attack_2_pending = False
        self.audio.play_sequence(("flute_1", "flute_2", "flute_3"))
        for target in self._opponents_of(fighter):
            if target is fighter or target.is_dead:
                continue
            if abs(target.x - fighter.x) > 240.0 or abs(target.lane_y - fighter.lane_y) > 52.0:
                continue
            target._start_henry_float()

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
        target = self._target_for(fighter)
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

    def _spawn_jan_healing_birds(self, fighter: Fighter) -> None:
        if fighter.name != "jan" or fighter.state != "sp_vert_attack_1" or not fighter.jan_healing_birds_pending:
            return
        fighter.jan_healing_birds_pending = False
        self.audio.play("bird_summon")
        target = fighter
        base_x = fighter.x
        base_y = fighter.world_hitbox_rect().centery - 28.0
        for index in range(3):
            self.projectiles.append(
                HealingBirdProjectile(fighter, target, base_x, base_y, fighter.facing, index)
            )

    def _spawn_jan_follow_orb(self, fighter: Fighter) -> None:
        if fighter.name != "jan" or fighter.state != "sp_vert_attack_2" or not fighter.jan_follow_orb_pending:
            return
        fighter.jan_follow_orb_pending = False
        fighter.attack_projectile_fired = True
        target = self._target_for(fighter)
        if target is not None and target.is_dead:
            target = None
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = fighter.world_hitbox_rect().centery - 28.0
        self.projectiles.append(JanFollowOrbProjectile(fighter, target, origin_x, origin_y, fighter.facing))
        self.audio.play("bird_summon")

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

    def _spawn_sorcerer_fireball(self, fighter: Fighter) -> None:
        if fighter.name != "sorcerer" or fighter.state != "sp_move_attack_1" or not fighter.sorcerer_fireball_pending:
            return
        fighter.sorcerer_fireball_pending = False
        fighter.attack_projectile_fired = True
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 54.0
        self.projectiles.append(FireballProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.audio.play_fireball()

    def _spawn_firzen_char_blast(self, fighter: Fighter) -> None:
        if fighter.name != "firzen" or fighter.state != "sp_move_attack_1" or not fighter.firzen_char_blast_pending:
            return
        fighter.firzen_char_blast_pending = False
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 74.0
        self.projectiles.append(FirzenCharBlastProjectile(fighter, fighter.x, origin_y, fighter.facing))

    def _spawn_firzen_fire_shots(self, fighter: Fighter, dt: float) -> None:
        if fighter.name != "firzen" or fighter.firzen_fire_shots_pending <= 0:
            return
        fighter.firzen_fire_shot_timer = max(0.0, fighter.firzen_fire_shot_timer - dt)
        if fighter.firzen_fire_shot_timer > 0.0:
            return
        origin_y = fighter.world_hitbox_rect().centery
        self.projectiles.append(FirzenFireProjectile(fighter, fighter.x, origin_y, fighter.facing))
        fighter.firzen_fire_shots_pending -= 1
        fighter.firzen_fire_shot_timer = 0.14 if fighter.firzen_fire_shots_pending else 0.0

    def _spawn_firzen_fire_ice_orb(self, fighter: Fighter) -> None:
        if fighter.name != "firzen" or fighter.state != "sp_vert_attack_1" or not fighter.firzen_fire_ice_orb_pending:
            return
        fighter.firzen_fire_ice_orb_pending = False
        fighter.attack_projectile_fired = True
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 56.0
        self.projectiles.append(FirzenFireIceOrb(fighter, fighter.x, origin_y))

    def _spawn_firzen_ground_orbs(self, orb: FirzenFireIceOrb) -> None:
        owner = orb.owner
        for orb_kind in ("ice", "fire"):
            target_x = max(
                self.stage.play_min_x,
                min(self.stage.play_max_x, owner.x + random.uniform(-360.0, 360.0)),
            )
            target_lane_y = random.uniform(LANE_MIN_Y, LANE_MAX_Y)
            target_y = GROUND_Y + target_lane_y - 22.0
            self.projectiles.append(
                FirzenTargetOrbProjectile(
                    owner,
                    orb_kind,
                    orb.x,
                    orb.y,
                    target_x,
                    target_lane_y,
                    target_y,
                )
            )

    def _spawn_firzen_vert_attack_2(self, fighter: Fighter) -> None:
        if fighter.name != "firzen":
            return
        if fighter.firzen_vert_attack_2_columns_pending:
            fighter.firzen_vert_attack_2_columns_pending = False
            frozen_targets: set[int] = set()
            for offset_x in (-96.0, 96.0):
                for offset_lane in (-24.0, 24.0):
                    column_x = max(
                        self.stage.play_min_x,
                        min(self.stage.play_max_x, fighter.x + offset_x),
                    )
                    column_lane = max(
                        LANE_MIN_Y,
                        min(LANE_MAX_Y, fighter.lane_y + offset_lane),
                    )
                    column = FreezeColumnEffect(
                        column_x,
                        GROUND_Y + column_lane,
                        random.choice((1, 2, 3)),
                        random.choice((-1, 1)),
                        column_lane,
                        fighter,
                    )
                    self.projectiles.append(column)
                    for target in self._opponents_of(fighter):
                        if (
                            target is None
                            or target.is_dead
                            or id(target) in frozen_targets
                            or abs(target.lane_y - column.lane_y) > 36
                            or not column.rect().colliderect(target.world_hitbox_rect())
                        ):
                            continue
                        target._start_ice_knockdown()
                        frozen_targets.add(id(target))
                        self.audio.play("freeze")
        if fighter.firzen_vert_attack_2_orbs_pending:
            origin_y = GROUND_Y + fighter.lane_y - fighter.z - 56.0
            for offset_x in (-60.0, 0.0, 60.0):
                if fighter.firzen_vert_attack_2_orbs_pending <= 0:
                    break
                orb_x = max(
                    self.stage.play_min_x,
                    min(self.stage.play_max_x, fighter.x + offset_x),
                )
                self.projectiles.append(FirzenFireIceOrb(fighter, orb_x, origin_y))
                fighter.firzen_vert_attack_2_orbs_pending -= 1

    def _spawn_woody_shots(self, fighter: Fighter) -> None:
        while fighter.woody_shots_pending:
            shot_set = fighter.woody_shots_pending.pop(0)
            origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
            origin_y = fighter.world_hitbox_rect().centery
            self.projectiles.append(
                WoodyShotProjectile(fighter, origin_x, origin_y, fighter.facing, shot_set)
            )
            self.audio.play("woody_shot")

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
            origin_y = hitbox.bottom - 42.0
            wind = WindProjectile(fighter, origin_x, origin_y, fighter.facing)
            self.projectiles.append(wind)
            targets = self._opponents_of(fighter)
            for target in targets:
                if target.is_dead or abs(target.lane_y - fighter.lane_y) > 10:
                    continue
                target._start_knockdown()
                wind.hit_targets.add(id(target))
                target_hitbox = target.world_hitbox_rect()
                target_x = target_hitbox.centerx + fighter.facing * (target.hitbox_size[0] * 0.48)
                target_y = target_hitbox.bottom - 42.0
                target_wind = WindProjectile(fighter, target_x, target_y, fighter.facing)
                target_wind.hit_targets.add(id(target))
                self.projectiles.append(target_wind)

    def _spawn_luis_wind(self, fighter: Fighter) -> None:
        if fighter.name != "luis" or fighter.state != "sp_move_attack_2" or not fighter.luis_wind_pending:
            return
        fighter.luis_wind_pending = False
        self.audio.play("luis_wind")

        hitbox = fighter.world_hitbox_rect()
        wind_y = hitbox.bottom - 42.0
        wind_offset = hitbox.width * 0.55 + 24.0
        winds = [
            WindProjectile(fighter, hitbox.centerx + facing * wind_offset, wind_y, facing)
            for facing in (-1, 1)
        ]
        self.projectiles.extend(winds)

        target = self.enemy if fighter is self.fighter else self.fighter
        if target is None or target.is_dead or abs(target.lane_y - fighter.lane_y) > 36:
            return

        for wind in winds:
            wind.hit_targets.add(id(target))
        if target.state == "block" and target.block_strength > 0:
            target.block_strength = 0
            target.block_hold_timer = 0.0
            self.audio.play("hit_guard")
        elif target.state == "block":
            target._start_block_break()
            self.audio.play("hit_guard")
        else:
            target.receive_damage(fighter.touch_damage)
            if not target.is_dead:
                target._start_knockdown()

        facing_toward_luis = 1 if fighter.x > target.x else -1
        if fighter.x == target.x:
            facing_toward_luis = -fighter.facing
        target_hitbox = target.world_hitbox_rect()
        target_wind_x = target_hitbox.centerx + facing_toward_luis * target.hitbox_size[0] * 0.48
        target_wind_y = target_hitbox.bottom - 42.0
        target_wind = WindProjectile(fighter, target_wind_x, target_wind_y, facing_toward_luis)
        target_wind.hit_targets.add(id(target))
        self.projectiles.append(target_wind)

    def _spawn_luis_liberated_wind(self, fighter: Fighter) -> None:
        if (
            fighter.name != "luis_liberated"
            or fighter.state != "sp_move_attack_2"
            or not fighter.luis_liberated_wind_pending
        ):
            return
        fighter.luis_liberated_wind_pending = False

        hitbox = fighter.world_hitbox_rect()
        wind = WindProjectile(
            fighter,
            hitbox.centerx + fighter.facing * (hitbox.width * 0.55 + 24.0),
            hitbox.bottom - 42.0,
            fighter.facing,
        )
        self.projectiles.append(wind)

        target = self.enemy if fighter is self.fighter else self.fighter
        if target is None or target.is_dead or abs(target.lane_y - fighter.lane_y) > 36:
            return

        wind.hit_targets.add(id(target))
        target._start_knockdown()
        facing_toward_luis = 1 if fighter.x > target.x else -1
        if fighter.x == target.x:
            facing_toward_luis = -fighter.facing
        target_hitbox = target.world_hitbox_rect()
        target_wind = WindProjectile(
            fighter,
            target_hitbox.centerx + facing_toward_luis * target.hitbox_size[0] * 0.48,
            target_hitbox.bottom - 42.0,
            facing_toward_luis,
        )
        target_wind.hit_targets.add(id(target))
        self.projectiles.append(target_wind)

    def _spawn_monk_wind(self, fighter: Fighter) -> None:
        if fighter.name != "monk" or fighter.state != "sp_move_attack_1" or not fighter.monk_wind_pending:
            return
        fighter.monk_wind_pending = False
        hitbox = fighter.world_hitbox_rect()
        wind = WindProjectile(
            fighter,
            hitbox.centerx + fighter.facing * (hitbox.width * 0.55 + 24.0),
            hitbox.bottom - 42.0,
            fighter.facing,
        )
        self.projectiles.append(wind)
        self.audio.play("monk_wind")

        target = self.enemy if fighter is self.fighter else self.fighter
        if (
            target is None
            or target.is_dead
            or abs(target.lane_y - fighter.lane_y) > 36
            or not wind.rect().colliderect(target.world_hitbox_rect())
        ):
            return

        wind.hit_targets.add(id(target))
        target.receive_damage(fighter.touch_damage)
        if not target.is_dead:
            target._start_knockdown()
        self.audio.play("wind_hit")

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

    def _reflect_projectile(self, projectile, barrier: JohnBarrierEffect) -> bool:
        phase = getattr(projectile, "phase", None)
        if (
            not getattr(projectile, "can_damage", False)
            or phase not in (None, "fly", "play")
            or (phase is None and not hasattr(projectile, "speed_x"))
            or not all(hasattr(projectile, attribute) for attribute in ("owner", "x", "y", "facing"))
        ):
            return False

        projectile.owner = barrier.owner
        projectile.facing = barrier.facing
        projectile.x = barrier.x + barrier.facing * (barrier.rect().width / 2 + projectile.rect().width / 2 + 2)
        if hasattr(projectile, "origin_x"):
            projectile.origin_x = projectile.x
        if hasattr(projectile, "distance_travelled"):
            projectile.distance_travelled = 0.0
        if hasattr(projectile, "target"):
            target = self._target_for(barrier.owner)
            projectile.target = target if target is not None and not target.is_dead else None
        if hasattr(projectile, "hit_targets"):
            projectile.hit_targets.clear()
        return True

    def _update_projectiles(self, dt: float) -> None:
        focus_x = self.fighter.x
        player_margin = SCREEN_WIDTH * 0.3
        min_focus = self.fighter.x - player_margin
        max_focus = self.fighter.x + player_margin
        enemy = self.enemy
        enemy_focus = (self.fighter.x + enemy.x) / 2 if enemy is not None else self.fighter.x
        focus_x = max(min_focus, min(max_focus, enemy_focus))
        camera_x = self.stage.camera_x(focus_x)
        visible_left = camera_x
        visible_right = camera_x + SCREEN_WIDTH
        for projectile in list(self.projectiles):
            projectile.update(dt)
            self._damage_heavy_box_with_projectile(projectile)
            if isinstance(projectile, FirzenFireIceOrb) and projectile.just_split:
                projectile.just_split = False
                self._spawn_firzen_ground_orbs(projectile)
            if isinstance(projectile, FirzenTargetOrbProjectile) and projectile.just_hit_ground:
                projectile.just_hit_ground = False
                ground_y = GROUND_Y + projectile.target_lane_y
                if projectile.orb_kind == "ice":
                    self.projectiles.append(
                        FreezeColumnEffect(
                            projectile.target_x,
                            ground_y,
                            "4_spike",
                            projectile.owner.facing,
                            projectile.target_lane_y,
                            projectile.owner,
                        )
                    )
                else:
                    self.projectiles.append(
                        FireTrailEffect(projectile.owner, projectile.target_x, ground_y - 22.0)
                    )
            if isinstance(projectile, AxleShotProjectile) and projectile.just_axle_shot_hit:
                self.audio.play("axle_shot_hit")
                projectile.just_axle_shot_hit = False
            if isinstance(projectile, JulianSkullProjectile) and projectile.just_burst_sound:
                self.audio.play("summon_bats_died")
                projectile.just_burst_sound = False
            if getattr(projectile, "just_ground_hit", False):
                if isinstance(projectile, ArrowProjectile) and projectile.style == "rudolf":
                    self.audio.play("rudolf_shuriken")
                    frames = self.rudolf_metal_fragments[self.rudolf_metal_fragment_index]
                    self.consumable_break_effects.append(
                        MetalFragmentEffect(projectile.x, projectile.lane_y, frames)
                    )
                    self.rudolf_metal_fragment_index = 1 - self.rudolf_metal_fragment_index
                projectile.just_ground_hit = False
            if isinstance(projectile, JohnBarrierEffect):
                if projectile.just_barrier_sound:
                    self.audio.play("john_barrier")
                    projectile.just_barrier_sound = False
                if projectile.just_reflect_sound:
                    self.audio.play("john_barrier_reflect")
                    projectile.just_reflect_sound = False
                if projectile.just_burst_sound:
                    self.audio.play("john_barrier_burst")
                    projectile.just_burst_sound = False
                if projectile.finished:
                    self.projectiles.remove(projectile)
                continue
            if isinstance(projectile, (JohnBlastCreateEffect, JohnHealOrbProjectile, JohnHealOrbParticleEffect)):
                if isinstance(projectile, JohnHealOrbProjectile) and projectile.just_heal_sound:
                    self.audio.play("john_heal_orb_heal")
                    projectile.just_heal_sound = False
                if isinstance(projectile, JohnHealOrbProjectile) and projectile.phase == "idle":
                    allies = (
                        [self.fighter, *(clone.fighter for clone in self.rudolf_clones)]
                        if projectile.owner is self.fighter
                        else self.enemies
                    )
                    for target in allies:
                        if target is None or target.is_dead or not projectile.contact_rect().colliderect(target.world_hitbox_rect()):
                            continue
                        target.health = min(target.max_health, target.health + 5)
                        projectile._start_burst()
                        projectile.just_heal_sound = False
                        self.audio.play("john_heal_orb_heal")
                        break
                if projectile.finished:
                    self.projectiles.remove(projectile)
                continue
            if getattr(projectile, "just_expired", False):
                self.audio.play("freeze_break")
                projectile.just_expired = False
            if getattr(projectile, "just_broke", False):
                if not (isinstance(projectile, ArrowProjectile) and projectile.style == "rudolf"):
                    self.audio.play("broken_arrow")
                projectile.just_broke = False
            if getattr(projectile, "just_burst", False):
                if isinstance(projectile, FireballProjectile):
                    self.audio.play_fireball()
                elif not isinstance(projectile, FreezeBallProjectile):
                    self.audio.play("orb_burst")
                projectile.just_burst = False
            if getattr(projectile, "just_impact", False):
                projectile.just_impact = False
            if getattr(projectile, "just_died", False):
                self.audio.play("bat_die")
                projectile.just_died = False
            if projectile.finished:
                self.projectiles.remove(projectile)
                continue
            if isinstance(projectile, (FirzenFireIceOrb, FirzenTargetOrbProjectile)):
                continue
            if isinstance(projectile, FirzenFireProjectile) and projectile.phase == "fly":
                if projectile.x <= visible_left or projectile.x >= visible_right:
                    self.projectiles.remove(projectile)
                    continue
            if isinstance(projectile, JulianBallProjectile) and projectile.phase == "fly":
                if projectile.x <= visible_left or projectile.x >= visible_right:
                    projectile.x = max(visible_left, min(visible_right, projectile.x))
                    projectile._start_burst()
                    self.audio.play("julian_ball_explode")
                    continue
            if isinstance(projectile, (BallProjectile, DavisBallProjectile, DenisOrbProjectile, DenisFollowOrbProjectile, FreezeBallProjectile, JackBlastProjectile, JohnBlastProjectile)) and projectile.phase == "fly":
                if projectile.x <= visible_left or projectile.x >= visible_right:
                    projectile.x = max(visible_left, min(visible_right, projectile.x))
                    if isinstance(projectile, JohnBlastProjectile):
                        projectile._start_burst()
                        self.audio.play("john_blast_hit")
                    else:
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
            if isinstance(projectile, FirzenCharBlastProjectile) and projectile.phase == "fly":
                if projectile.x <= visible_left or projectile.x >= visible_right:
                    projectile.x = max(visible_left, min(visible_right, projectile.x))
                    projectile._start_burst()
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
            if isinstance(projectile, FreezeTornadoProjectile):
                if projectile.x <= visible_left or projectile.x >= visible_right:
                    projectile.finished = True
            outside_stage = projectile.x < self.stage.play_min_x - 400 or projectile.x > self.stage.play_max_x + 400
            if outside_stage and not isinstance(projectile, (BatSummonProjectile, JanFollowOrbProjectile, JohnFollowDiskProjectile, JulianSkullProjectile)):
                self.projectiles.remove(projectile)
                continue
            if getattr(projectile, "can_damage", False):
                owner = getattr(projectile, "owner", None)
                if owner is not None:
                    projectile_rect = projectile.rect()
                    reflected = False
                    if (
                        getattr(projectile, "phase", None) in {"fly", "play"}
                        or (getattr(projectile, "phase", None) is None and hasattr(projectile, "speed_x"))
                    ):
                        for barrier in self.projectiles:
                            if (
                                isinstance(barrier, JohnBarrierEffect)
                                and barrier.can_reflect
                                and projectile_rect.colliderect(barrier.rect())
                                and self._reflect_projectile(projectile, barrier)
                            ):
                                barrier.reflect_count += 1
                                barrier._start_reflect()
                                barrier.just_reflect_sound = False
                                self.audio.play("john_barrier_reflect")
                                reflected = True
                                break
                    if reflected:
                        continue
                    for column in self.projectiles:
                        if not isinstance(column, FreezeColumnEffect) or column.finished:
                            continue
                        if abs(owner.lane_y - column.lane_y) > 36:
                            continue
                        if projectile_rect.colliderect(column.rect()):
                            if isinstance(projectile, JulianBallProjectile) and projectile.register_hit(column):
                                if projectile.hit_count >= 2:
                                    projectile._start_burst()
                                    self.audio.play("julian_ball_explode")
                                    column.break_apart()
                                    break
                            column.break_apart()
            if isinstance(projectile, FreezeColumnEffect):
                continue
            if isinstance(projectile, HealingBirdProjectile):
                target = projectile.target
                if (
                    projectile.phase == "fly"
                    and projectile.spread_timer <= 0.0
                    and not target.is_dead
                    and projectile.rect().colliderect(target.world_hitbox_rect())
                ):
                    target.health = min(target.max_health, target.health + 2)
                    projectile._start_heal()
                    self.audio.play("healed_target")
                continue
            if isinstance(projectile, JanFollowOrbProjectile):
                target = projectile.target
                if (
                    projectile.phase == "fly"
                    and target is not None
                    and not target.is_dead
                    and abs(target.lane_y - projectile.owner.lane_y) <= 36
                    and abs(projectile.y - target.world_hitbox_rect().centery) <= 42
                    and projectile.rect().colliderect(target.world_hitbox_rect())
                ):
                    if target.state == "block" and target.block_strength > 0:
                        target.block_strength = 0
                        target.block_hold_timer = 0.0
                        self.audio.play("hit_guard")
                    elif target.state == "block":
                        target._start_block_break()
                        self.audio.play("hit_guard")
                    else:
                        target.receive_damage(projectile.damage)
                    projectile._start_burst()
                    self.audio.play("jan_burst")
                continue
            if isinstance(projectile, JohnFollowDiskProjectile):
                target = projectile.target
                if (
                    projectile.phase == "fly"
                    and target is not None
                    and not target.is_dead
                    and projectile.hit_rect().colliderect(target.world_hitbox_rect())
                ):
                    if target.state == "block" and target.block_strength > 0:
                        target.block_strength = 0
                        target.block_hold_timer = 0.0
                        self.audio.play("hit_guard")
                    elif target.state == "block":
                        target._start_block_break()
                        self.audio.play("hit_guard")
                    else:
                        target.receive_damage(projectile.damage)
                        if not target.is_dead:
                            target._start_knockdown()
                        self.audio.play("arrow_hit")
                    projectile._start_burst()
                continue
            if isinstance(projectile, JulianBallProjectile):
                if projectile.phase == "fly" and projectile.can_damage:
                    for target in self._opponents_of(projectile.owner):
                        if (
                            target is None
                            or target is projectile.owner
                            or target.is_dead
                            or id(target) in projectile.hit_targets
                            or abs(target.lane_y - projectile.owner.lane_y) > 36
                            or abs(projectile.y - target.world_hitbox_rect().centery) > 42
                            or (projectile.facing > 0 and target.world_hitbox_rect().centerx < projectile.x)
                            or (projectile.facing < 0 and target.world_hitbox_rect().centerx > projectile.x)
                            or not projectile.rect().colliderect(target.world_hitbox_rect())
                        ):
                            continue
                        projectile.register_hit(target)
                        if target.state == "block" and target.block_strength > 0:
                            target.block_strength = 0
                            target.block_hold_timer = 0.0
                            self.audio.play("hit_guard")
                        elif target.state == "block":
                            target._start_block_break()
                            self.audio.play("hit_guard")
                        else:
                            target.receive_damage(projectile.damage)
                            if not target.is_dead:
                                target._start_knockdown()
                        self.audio.play("julian_ball_hit")
                        if projectile.hit_count >= 2:
                            projectile._start_burst()
                            self.audio.play("julian_ball_explode")
                        break
                continue
            if isinstance(projectile, JulianExplosionEffect):
                for target in self._opponents_of(projectile.owner):
                    if target is None or target is projectile.owner or target.is_dead or id(target) in projectile.hit_targets:
                        continue
                    dx = target.world_hitbox_rect().centerx - projectile.x
                    dy = target.lane_y - projectile.lane_y
                    if dx * dx + dy * dy > projectile.radius * projectile.radius:
                        continue
                    projectile.hit_targets.add(id(target))
                    if target.state == "block" and target.block_strength > 0:
                        target.block_strength = 0
                        target.block_hold_timer = 0.0
                        self.audio.play("hit_guard")
                    elif target.state == "block":
                        target._start_block_break()
                        self.audio.play("hit_guard")
                    else:
                        target.receive_damage(projectile.damage)
                        if not target.is_dead:
                            if projectile.launch:
                                target._start_launch_knockdown()
                            else:
                                target._start_knockdown()
                continue

            for target in self._opponents_of(projectile.owner):
                if target is None or target is projectile.owner or target.is_dead:
                    continue
                if not projectile.can_damage:
                    continue
                knocked_and_vulnerable = target.state in {"fall", "knocked_fire"} and not target.animation_player.finished
                if isinstance(projectile, FreezeBallProjectile):
                    if abs(target.lane_y - projectile.owner.lane_y) > 36:
                        continue
                    if abs(projectile.y - target.world_hitbox_rect().centery) > 42:
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
                        target.receive_damage(projectile.damage)
                        if not target.is_dead:
                            target._start_ice_knockdown()
                            self.audio.play("freeze")
                    projectile._start_burst()
                    continue
                if isinstance(projectile, WoodyShotProjectile):
                    if abs(target.lane_y - projectile.owner.lane_y) > 36:
                        continue
                    if abs(projectile.y - target.world_hitbox_rect().centery) > 42:
                        continue
                    if not projectile.rect().colliderect(target.world_hitbox_rect()):
                        continue
                    if target.state == "block" and target.block_strength > 0:
                        target.block_strength = 0
                        target.block_hold_timer = 0.0
                        self.audio.play("hit_guard")
                    elif target.state == "block":
                        target._start_block_break()
                        self.audio.play("hit_guard")
                    else:
                        target.receive_damage(projectile.damage)
                        self.audio.play("hit_success")
                    projectile._start_burst()
                    break
                if isinstance(projectile, FirzenFireProjectile):
                    if abs(target.lane_y - projectile.owner.lane_y) > 36:
                        continue
                    target_rect = target.world_hitbox_rect()
                    if (
                        abs(projectile.y - target_rect.centery) > 42
                        or (projectile.facing > 0 and target_rect.centerx < projectile.origin_x)
                        or (projectile.facing < 0 and target_rect.centerx > projectile.origin_x)
                        or not projectile.rect().colliderect(target_rect)
                    ):
                        continue
                    if target.state == "block" and target.block_strength > 0:
                        target.block_strength = 0
                        target.block_hold_timer = 0.0
                        self.audio.play("hit_guard")
                    elif target.state == "block":
                        target._start_block_break()
                        self.audio.play("hit_guard")
                    else:
                        target.receive_damage(projectile.damage)
                        if not target.is_dead:
                            target._start_fire_knockdown()
                        self.audio.play_fireball()
                    projectile._start_burst()
                    break
                if isinstance(projectile, FirzenCharBlastProjectile):
                    if abs(target.lane_y - projectile.owner.lane_y) > 36:
                        continue
                    if abs(projectile.y - target.world_hitbox_rect().centery) > 42:
                        continue
                    if (
                        (projectile.facing > 0 and target.world_hitbox_rect().centerx < projectile.origin_x)
                        or (projectile.facing < 0 and target.world_hitbox_rect().centerx > projectile.origin_x)
                        or not any(rect.colliderect(target.world_hitbox_rect()) for rect in projectile.segment_rects())
                    ):
                        continue
                    if target.state == "block" and target.block_strength > 0:
                        target.block_strength = 0
                        target.block_hold_timer = 0.0
                        self.audio.play("hit_guard")
                    elif target.state == "block":
                        target._start_block_break()
                        self.audio.play("hit_guard")
                    else:
                        target.receive_damage(projectile.damage)
                        self.audio.play("hit_success")
                    segment = next(
                        rect
                        for rect in projectile.segment_rects()
                        if rect.colliderect(target.world_hitbox_rect())
                    )
                    projectile._start_burst(segment.centerx)
                    break
                if isinstance(projectile, FreezeTornadoProjectile):
                    if abs(target.lane_y - projectile.owner.lane_y) > 10 or id(target) in projectile.hit_targets:
                        continue
                    if not projectile.rect().colliderect(target.world_hitbox_rect()):
                        continue
                    projectile.hit_targets.add(id(target))
                    target._start_ice_launch_knockdown()
                    self.audio.play("freeze")
                    continue
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
                if isinstance(projectile, JulianSkullProjectile) and abs(target.lane_y - projectile.owner.lane_y) > 36:
                    continue
                if isinstance(projectile, ArrowProjectile) and projectile.style == "rudolf":
                    if abs(target.lane_y - projectile.lane_y) > 36:
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

                if isinstance(projectile, JohnBlastProjectile) and projectile.phase == "fly":
                    projectile._start_burst()
                    self.audio.play("john_blast_hit")

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
                    elif isinstance(projectile, AxleShotProjectile):
                        if not target.is_dead:
                            target._start_knockdown()
                        self.audio.play("hit_success")
                    elif isinstance(projectile, FireballProjectile):
                        self.audio.play_fireball()
                        if not target.is_dead:
                            target._start_fire_knockdown()
                    elif projectile.owner.name == "deep":
                        self.audio.play("sword_cut")
                    elif not isinstance(projectile, (BatSummonProjectile, JulianSkullProjectile)):
                        self.audio.play("hit_success")

                if isinstance(projectile, FireballProjectile):
                    projectile._start_hit()
                    projectile.just_burst = False
                elif isinstance(projectile, AxleShotProjectile):
                    projectile._start_burst()
                    projectile.just_axle_shot_hit = False
                    self.audio.play("axle_shot_hit")
                elif isinstance(projectile, JohnBlastProjectile):
                    projectile._start_burst()
                elif isinstance(projectile, JulianSkullProjectile):
                    projectile._start_burst()
                    self.audio.play("summon_bats_died")
                elif hasattr(projectile, "_start_burst"):
                    projectile._start_burst()
                    if isinstance(projectile, BatSummonProjectile):
                        self.audio.play("bat_die")
                        projectile.just_died = False
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
        x = SCREEN_WIDTH - panel_width - 20
        if self.test_mode:
            label = self.small_font.render("TEST MODE - NO ENEMIES", True, TEXT_COLOR)
            surface.blit(label, label.get_rect(topright=(SCREEN_WIDTH - 20, 24)))
        elif self.stage_mode:
            for index, enemy in enumerate(enemy for enemy in self.enemies if not enemy.is_dead):
                self._draw_hud_bar(
                    surface,
                    x,
                    18 + index * 31,
                    panel_width,
                    27,
                    enemy.health,
                    enemy.max_health,
                    (194, 58, 58),
                    f"{enemy.definition['display_name']} HP",
                )
        elif len(self.enemies) > 1:
            for index, enemy in enumerate(enemy for enemy in self.enemies if not enemy.is_dead):
                self._draw_hud_bar(
                    surface,
                    x,
                    18 + index * 31,
                    panel_width,
                    27,
                    enemy.health,
                    enemy.max_health,
                    (194, 58, 58),
                    f"{enemy.definition['display_name']} HP",
                )
        elif self.enemies:
            enemy = self.enemy
            if enemy is not None:
                self._draw_hud_bar(surface, x, 18, panel_width, 28, enemy.health, enemy.max_health, (194, 58, 58), f"{enemy.definition['display_name']} HP")
                self._draw_hud_bar(surface, x, 52, panel_width, 24, enemy.mana, enemy.max_mana, (72, 122, 235), "MP")

    def _draw_stage_mode_card(self, surface: pygame.Surface) -> None:
        if not self.stage_mode:
            return

        show_title = self.stage_card_timer > 0.0
        if not (show_title or self.stage_mode_complete or self.stage_mode_failed):
            return

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 20, 175))
        surface.blit(overlay, (0, 0))
        card = pygame.Rect(460, 350, 1000, 330)
        pygame.draw.rect(surface, (24, 32, 44), card, border_radius=18)
        pygame.draw.rect(surface, (220, 169, 91), card, width=3, border_radius=18)

        if self.stage_mode_complete:
            heading_text = "CAMPAIGN COMPLETE"
            subtitle_text = "All ten stages cleared - press J to return to the menu"
        elif self.stage_mode_failed:
            heading_text = "STAGE FAILED"
            subtitle_text = "Press J to return to the menu"
        else:
            heading_text = f"STAGE {STAGE_ROMAN_NUMERALS[self.stage_index]}"
            subtitle_text = "Prepare for battle"

        heading = self.stage_title_font.render(heading_text, True, TEXT_COLOR)
        subtitle = self.stage_subtitle_font.render(subtitle_text, True, (195, 205, 218))
        surface.blit(heading, heading.get_rect(center=(card.centerx, card.centery - 42)))
        surface.blit(subtitle, subtitle.get_rect(center=(card.centerx, card.centery + 42)))

    def _draw_marker(self, surface: pygame.Surface, fighter: Fighter, camera_x: float, text: str) -> None:
        marker = self.small_font.render(text, True, (255, 240, 120))
        rect = marker.get_rect(midtop=(fighter.world_hitbox_rect().centerx - int(camera_x), fighter.world_hitbox_rect().bottom + 6))
        if rect.bottom < SCREEN_HEIGHT:
            surface.blit(marker, rect)

    def update(self, dt: float, inputs: FighterInput) -> None:
        if self.paused:
            return
        if self.stage_mode and (self.stage_mode_complete or self.stage_mode_failed):
            if inputs.attack_just_pressed:
                self.return_to_menu_requested = True
            return
        if self.stage_mode and self.stage_card_timer > 0.0:
            self.stage_card_timer = max(0.0, self.stage_card_timer - dt)
            return

        self.consumable_spawn_timer -= dt
        while self.consumable_spawn_timer <= 0.0:
            self._spawn_consumable(random.choice(self.spawnable_items))
            self.consumable_spawn_timer += 18.0
        if inputs.spawn_random_item_just_pressed:
            self._spawn_consumable(random.choice(self.spawnable_items))
        if inputs.spawn_heavy_item_just_pressed:
            self._spawn_consumable(HEAVY_BOX_ITEM_ID)
        fighter_throw_was_active = self.fighter.item_throw_animation is not None
        fighter_throw_handled = self._handle_held_item_throw_input(self.fighter, inputs)
        if fighter_throw_was_active or fighter_throw_handled:
            fighter_inputs = self._suppress_item_throw_inputs(inputs)
            fighter_item = None
        else:
            fighter_item = self._item_to_drink(self.fighter, inputs)
            if fighter_item is not None:
                fighter_inputs = replace(inputs, attack_pressed=False, attack_just_pressed=False, drink_just_pressed=True)
            elif self._try_pick_up_consumable(self.fighter, inputs):
                fighter_inputs = replace(inputs, attack_pressed=False, attack_just_pressed=False)
            else:
                fighter_inputs = inputs
        if self.fighter.held_item is not None and _is_throwable_item(self.fighter.held_item):
            fighter_inputs = replace(fighter_inputs, drink_just_pressed=False)
        previous_x_by_fighter = {
            id(fighter): fighter.x for fighter in self._fighters()
        }
        fighters_before_enemy_updates = [self.fighter, *self.enemies]
        was_drinking = {fighter: fighter.state == "drink" for fighter in fighters_before_enemy_updates}
        items_to_drink: dict[Fighter, str | None] = {self.fighter: fighter_item}
        self.fighter.update(dt, fighter_inputs, target=self.enemy, controlled=True)
        self._spawn_rudolf_clones(self.fighter)
        for enemy in tuple(self.enemies):
            if enemy.is_dead:
                enemy.update(dt, FighterInput(), target=self.fighter, controlled=True)
                items_to_drink[enemy] = None
                continue

            brain = self.enemy_brains[enemy]
            brain.update(dt)
            enemy_input = brain.build_input(enemy.snapshot, self.fighter.snapshot)
            enemy_throw_was_active = enemy.item_throw_animation is not None
            enemy_throw_handled = self._handle_held_item_throw_input(enemy, enemy_input)
            if enemy_throw_was_active or enemy_throw_handled:
                enemy_input = self._suppress_item_throw_inputs(enemy_input)
                enemy_item = None
            else:
                enemy_item = self._item_to_drink(enemy, enemy_input)
                if enemy_item is not None:
                    enemy_input.attack_pressed = False
                    enemy_input.attack_just_pressed = False
                    enemy_input.drink_just_pressed = True
                elif self._try_pick_up_consumable(enemy, enemy_input):
                    enemy_input.attack_just_pressed = False
            if enemy.held_item is not None and _is_throwable_item(enemy.held_item):
                enemy_input.drink_just_pressed = False
            enemy.update(dt, enemy_input, target=self.fighter, controlled=True)
            items_to_drink[enemy] = enemy_item

        for clone in tuple(self.rudolf_clones):
            clone.lifetime -= dt
            if clone.lifetime <= 0.0:
                self._remove_rudolf_clone(clone)
                continue
            clone.brain.update(dt)
            clone_target = self.enemy
            clone_input = (
                clone.brain.build_input(clone.fighter.snapshot, clone_target.snapshot)
                if clone_target is not None and not clone_target.is_dead
                else FighterInput()
            )
            clone.fighter.update(dt, clone_input, target=clone_target, controlled=True)
        for fighter in self._fighters():
            if fighter.luis_transform_pending:
                fighter.transform_to(FighterConfig("luis_liberated", CHARACTERS["luis_liberated"]))
        self._finish_held_item_throw(self.fighter)
        for enemy in self.enemies:
            self._finish_held_item_throw(enemy)
        for fighter, previously_drinking in was_drinking.items():
            item_id = items_to_drink.get(fighter)
            if fighter.state == "drink" and not previously_drinking:
                self.audio.play("drink_drink")
                if item_id is not None:
                    if item_id == "consumables/milk":
                        fighter.health = min(fighter.max_health, fighter.health + 10)
                    self.start_item_overlay(fighter, item_id, "drink", active_state="drink")

        for fighter in self._fighters():
            self._apply_henry_flute_attack(fighter)
            self._spawn_freeze_ball(fighter)
            self._spawn_sorcerer_freeze_ball(fighter)
            self._spawn_freeze_columns(fighter)
            self._spawn_freeze_tornado(fighter)
            self._spawn_hunter_projectile(fighter)
            self._spawn_rudolf_shurikens(fighter)
            self._spawn_jack_blast(fighter)
            self._spawn_axle_shot(fighter)
            self._spawn_julian_skull(fighter)
            self._spawn_julian_ball(fighter)
            self._spawn_julian_explosions(fighter)
            self._spawn_john_blast(fighter)
            self._spawn_john_barrier(fighter)
            self._spawn_john_follow_disk(fighter)
            self._spawn_john_heal_orb(fighter)
            self._spawn_sorcerer_heal_orb(fighter)
            self._spawn_henry_vertical_volley(fighter)
            self._spawn_template_projectile(fighter)
            self._spawn_denis_projectile(fighter)
            self._spawn_denis_follow_orb(fighter)
            self._spawn_davis_projectile(fighter)
            self._spawn_bat_laser(fighter)
            self._spawn_bat_summons(fighter)
            self._spawn_jan_healing_birds(fighter)
            self._spawn_jan_follow_orb(fighter)
            self._spawn_deep_projectile(fighter)
            self._spawn_firen_fireball(fighter)
            self._spawn_sorcerer_fireball(fighter)
            self._spawn_firzen_char_blast(fighter)
            self._spawn_firzen_fire_shots(fighter, dt)
            self._spawn_firzen_fire_ice_orb(fighter)
            self._spawn_firzen_vert_attack_2(fighter)
            self._spawn_woody_shots(fighter)
            self._spawn_firen_fire_breath(fighter)
            self._spawn_henry_wind(fighter)
            self._spawn_luis_wind(fighter)
            self._spawn_luis_liberated_wind(fighter)
            self._spawn_monk_wind(fighter)
            self._spawn_firen_fire_trail(fighter)
            self._spawn_firen_explosion(fighter)

        self._resolve_heavy_box_obstruction(previous_x_by_fighter)
        self._resolve_freeze_column_obstruction(previous_x_by_fighter)
        for effect in tuple(self.consumable_break_effects):
            if effect.update(dt):
                self.consumable_break_effects.remove(effect)
        for effect in tuple(self.rudolf_clone_smoke_effects):
            if effect.update(dt):
                self.rudolf_clone_smoke_effects.remove(effect)
        for item in tuple(self.consumable_items):
            item_event = item.update(dt)
            if item_event == "landed":
                if item.item_id in HEAVY_ITEM_IDS:
                    self.audio.play_heavy_box_land()
                else:
                    sound = (
                        "armor_piece_land"
                        if item.item_id in {"throwables/armor_piece_1", "throwables/armor_piece_2"}
                        else "drink_land"
                    )
                    self.audio.play(sound)
            elif item_event == "break":
                if item.item_id in HEAVY_ITEM_IDS:
                    self._break_heavy_box(item)
                else:
                    self.consumable_items.remove(item)
                    self.audio.play(
                        "baseball_break"
                        if item.item_id == ConsumableItem.BASEBALL_ITEM_ID
                        else "drink_break"
                    )
                if item.item_id == "consumables/milk":
                    self.consumable_break_effects.append(
                        ConsumableBreakEffect(
                            item.x,
                            item.lane_y,
                            self.milk_break_frames["dust"],
                            self.milk_break_frames["large"],
                            self.milk_break_frames["small"],
                        )
                    )
                elif item.item_id not in HEAVY_ITEM_IDS:
                    broken_frames = self.item_sprite_animations.get(item.item_id, {}).get("broken")
                    if broken_frames:
                        self.consumable_break_effects.append(
                            ItemBreakEffect(item.x, item.lane_y, broken_frames)
                        )
        self._resolve_thrown_item_hits()
        for fighter, (_, animation, active_state) in tuple(self.active_item_overlays.items()):
            if (active_state is not None and fighter.state != active_state) or animation.update(dt):
                del self.active_item_overlays[fighter]
        for fighter, (item_id, animation) in tuple(self.held_item_animations.items()):
            if fighter.held_item != item_id:
                del self.held_item_animations[fighter]
            else:
                animation.update(dt)
        self._update_camera_focus(dt)
        self._update_projectiles(dt)
        self._remove_finished_rudolf_clones()
        self._handle_woody_punches()
        self._handle_woody_dash_hits(previous_x_by_fighter)
        self._handle_combat()
        self._remove_finished_rudolf_clones()
        self._handle_audio(dt)
        if self.stage_mode:
            if self.fighter.state == "dead":
                self.stage_mode_failed = True
            elif self.fighter.state != "die" and self.enemies and all(
                enemy.state == "dead" for enemy in self.enemies
            ):
                self._advance_stage_mode()

    def draw(self, surface: pygame.Surface) -> None:
        focus_x = self._camera_focus_x()
        camera_x = self.stage.camera_x(focus_x)
        self.stage.draw(surface, focus_x)

        for projectile in self.projectiles:
            projectile.draw(surface, camera_x)
        for item in sorted(self.consumable_items, key=lambda consumable: consumable.lane_y):
            item.draw(surface, camera_x)
        for effect in self.consumable_break_effects:
            effect.draw(surface, camera_x)
        for effect in self.rudolf_clone_smoke_effects:
            effect.draw(surface, camera_x)
        fighters = self._fighters()
        fighters.sort(key=lambda fighter: fighter.lane_y)
        for fighter in fighters:
            fighter.draw(surface, camera_x)
            self._draw_held_item(surface, fighter, camera_x)
            self._draw_item_overlay(surface, fighter, camera_x)
            self._draw_speech_bubble(surface, fighter, camera_x)

        self._draw_marker(surface, self.fighter, camera_x, "P1")
        self._draw_hud(surface)
        self._draw_stage_mode_card(surface)
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
