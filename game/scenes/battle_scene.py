from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, replace
from functools import lru_cache
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
from game.data.campaign import (
    ENDLESS_SUPPLY_BREAK_INTERVAL,
    get_endless_encounter,
)
from game.data.difficulty import DEFAULT_DIFFICULTY, DifficultyProfile, get_difficulty_profile
from game.data.stage_progression import StageProgression
from game.data.xp_rewards import enemy_xp_reward
from game.entities.fighter import (
    COMBAT_ATTACK_STATES,
    HENRY_FLOAT_DURATION,
    HENRY_FLOAT_HEIGHT,
    Fighter,
    FighterConfig,
    FighterInput,
    FighterSnapshot,
)
from game.entities.xp_orb import XPOrb
from game.systems.audio import AudioBank
from game.systems.keybindings import KEY_BINDINGS
from game.systems.stage_cards import (
    CARDS_BY_KEY,
    CARDS_BY_TITLE,
    STAGE_CARD_CATALOG,
    StageCard,
    card_rank_title,
    stage_card_effects,
)
from game.systems.stage_level_up_slot import SAMPLE_CARD_LABELS, StageLevelUpSlot
from game.systems.item_anchors import (
    DEFAULT_WEAPON_ANCHOR_REFERENCE,
    HandAnchor,
    load_hand_anchors,
    load_weapon_anchor_reference,
    load_weapon_hand_anchors,
    load_weapon_reference_sprites,
)
from game.systems.stage import STAGE_CONFIGS


THROWN_ITEM_MAX_DISTANCE = 330.0
THROWABLE_DISTANCE_MULTIPLIER = 2.0
HEAVY_ITEM_DISTANCE_MULTIPLIER = THROWABLE_DISTANCE_MULTIPLIER / 2
DARK_BAT_SP_MOVE_ATTACK_REACH = 270
BUZZ_BALL_ITEM_ID = "throwables/buzz_ball"
BIGGIE_BALL_ITEM_ID = "throwables/biggie_ball"
BIGGIE_BALL_BLAST_RADIUS = 110.0
# Normalized chest point measured from frame 8 of Reece's moving special animation.
REECE_SP_MOVE_ATTACK_1_CHEST_ANCHOR = (0.5, 0.53)
STAGE_CARD_DURATION = 2.4
STAGE_WAVE_GRACE_DURATION = 4.0
STAGE_MILESTONE_XP_PER_STAGE = 10
STAGE_SLOT_CANVAS_SIZE = (1_040, 598)
STAGE_SLOT_SCALE = min(
    SCREEN_WIDTH * 0.9 / STAGE_SLOT_CANVAS_SIZE[0],
    SCREEN_HEIGHT * 0.9 / STAGE_SLOT_CANVAS_SIZE[1],
)
STAGE_SLOT_DISPLAY_SIZE = tuple(
    round(dimension * STAGE_SLOT_SCALE) for dimension in STAGE_SLOT_CANVAS_SIZE
)
STAGE_CARD_SIZE = (
    round(208 * STAGE_SLOT_SCALE),
    round(279 * STAGE_SLOT_SCALE),
)
PAUSE_CARD_SIZE = (220, 295)
PAUSE_CARD_HOVER_SIZE = (370, 496)
PAUSE_CARD_HOVER_DELAY = 0.055
PAUSE_CARD_HOVER_IN_DURATION = 0.18
PAUSE_CARD_HOVER_OUT_DURATION = 0.14
STAGE_CARD_WINDOWS = (
    pygame.Rect(138, 184, 210, 281),
    pygame.Rect(416, 184, 216, 281),
    pygame.Rect(694, 184, 221, 281),
)


@lru_cache(maxsize=12)
def _load_stage_card_image(card_key: str) -> pygame.Surface:
    card = CARDS_BY_KEY[card_key]
    image_path = (
        Path(__file__).resolve().parents[2]
        / "assets"
        / "sprites"
        / "ui"
        / "stage_mode"
        / "cards"
        / card.image
    )
    if not image_path.is_file():
        raise FileNotFoundError(f"Required Stage Mode card artwork is missing: {image_path}")
    image = pygame.image.load(str(image_path))
    if image.get_size() != (896, 1200):
        raise ValueError(
            f"Stage Mode card artwork must be 896x1200 pixels: {image_path}"
        )
    return pygame.transform.smoothscale(image, STAGE_CARD_SIZE)


@lru_cache(maxsize=24)
def _load_stage_card_glow_layer(
    card_key: str,
    width: int,
    height: int,
) -> pygame.Surface:
    glow = _load_stage_card_glow_mask(card_key)
    if glow.get_size() == (width, height):
        return glow
    return pygame.transform.smoothscale(glow, (width, height))


@lru_cache(maxsize=3)
def _load_stage_card_glow_mask(card_key: str) -> pygame.Surface:
    card = CARDS_BY_KEY[card_key]
    glow = pygame.Surface(STAGE_CARD_SIZE, pygame.SRCALPHA)
    if not card.image.startswith("curse_cards/"):
        return glow

    image = _load_stage_card_image(card_key)
    glow_mask = pygame.Surface(STAGE_CARD_SIZE, pygame.SRCALPHA)
    for y in range(STAGE_CARD_SIZE[1]):
        for x in range(STAGE_CARD_SIZE[0]):
            red, green, blue, alpha = image.get_at((x, y))
            if alpha and red >= 135 and red > green * 1.25 and red > blue * 1.15:
                glow_mask.set_at((x, y), (255, 74, 20, 200))
    blur_size = (
        max(1, STAGE_CARD_SIZE[0] // 6),
        max(1, STAGE_CARD_SIZE[1] // 6),
    )
    soft_glow = pygame.transform.smoothscale(
        pygame.transform.smoothscale(glow_mask, blur_size),
        STAGE_CARD_SIZE,
    )
    soft_glow.set_alpha(120)
    glow.blit(soft_glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    glow_mask.set_alpha(80)
    glow.blit(glow_mask, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    return glow


def _stage_card_glow_alpha() -> int:
    pulse = (math.sin(pygame.time.get_ticks() * math.tau / 2_600.0) + 1.0) / 2.0
    return round(48 + pulse * 34)


def _apply_stage_card_glow(
    surface: pygame.Surface,
    card_key: str,
    glow_size: tuple[int, int] | None = None,
    rotation: float = 0.0,
    destination: tuple[int, int] = (0, 0),
) -> None:
    card = CARDS_BY_KEY[card_key]
    if not card.image.startswith("curse_cards/"):
        return
    width, height = glow_size or surface.get_size()
    glow = _load_stage_card_glow_layer(
        card_key,
        width,
        height,
    )
    if rotation:
        glow = pygame.transform.rotate(glow, rotation)
    glow.set_alpha(_stage_card_glow_alpha())
    surface.blit(glow, destination, special_flags=pygame.BLEND_RGBA_ADD)


def _scale_stage_slot_rect(rect: pygame.Rect) -> pygame.Rect:
    return pygame.Rect(
        round(rect.x * STAGE_SLOT_SCALE),
        round(rect.y * STAGE_SLOT_SCALE),
        round(rect.width * STAGE_SLOT_SCALE),
        round(rect.height * STAGE_SLOT_SCALE),
    )


@lru_cache(maxsize=6)
def _stage_card_font(size: int) -> pygame.font.Font:
    return pygame.font.Font(None, size)


def _wrap_stage_card_text(
    text: str,
    font: pygame.font.Font,
    max_width: int,
) -> list[tuple[str, int, int]]:
    lines = []
    start = 0
    while start < len(text):
        end = start
        last_space = -1
        while end < len(text):
            if text[end].isspace():
                last_space = end
            if font.size(text[start:end + 1])[0] > max_width:
                break
            end += 1
        if end == len(text):
            lines.append((text[start:end], start, end))
            break
        if last_space >= start:
            line_end = last_space
            next_start = last_space + 1
        else:
            line_end = max(start + 1, end)
            next_start = line_end
        lines.append((text[start:line_end], start, line_end))
        start = next_start
    return lines


@lru_cache(maxsize=36)
def _pause_card_surface(
    card_key: str,
    rank: int,
    width: int,
    height: int,
) -> pygame.Surface:
    card = CARDS_BY_KEY[card_key]
    surface = pygame.transform.smoothscale(
        _load_stage_card_image(card_key),
        (width, height),
    )
    title_font = _stage_card_font(max(11, width // 15))
    detail_font = _stage_card_font(max(10, width // 18))
    title = card_rank_title(card, rank)
    title_lines = _wrap_stage_card_text(title, title_font, width - 28)
    title_y = max(8, round(height * 0.065))
    for line, _, _ in title_lines[:2]:
        label = title_font.render(line, True, (255, 232, 173))
        surface.blit(label, label.get_rect(midtop=(width // 2, title_y)))
        title_y += title_font.get_linesize()

    description_lines = _wrap_stage_card_text(
        card.description,
        detail_font,
        width - 34,
    )
    description_y = round(height * 0.735)
    for line, _, _ in description_lines[:3]:
        detail = detail_font.render(line, True, (245, 237, 220))
        surface.blit(detail, detail.get_rect(midtop=(width // 2, description_y)))
        description_y += detail_font.get_linesize()
    perk = detail_font.render(card.perk, True, (255, 217, 126))
    surface.blit(
        perk,
        perk.get_rect(midtop=(width // 2, height - detail_font.get_linesize() - 11)),
    )
    return surface


STAGE_CORPSE_DURATION = 15.0
STAGE_ENEMY_SPAWN_MARGIN = SCREEN_WIDTH * 0.3 + 200.0
STAGE_MAX_ACTIVE_ENEMIES = 4
STAGE_CURSE_SKULL_INITIAL_DELAY = 12.0
STAGE_MAX_XP_ORBS = 128
STAGE_TITLE_BANNER_TOP = 96
STAGE_TITLE_BANNER_WIDTH = 1_080
STAGE_TITLE_BANNER_HEIGHT = 106
CAMERA_FOLLOW_SPEED = 10.0
QUICK_PLAY_OPPONENT_HEALTH = 5
WEAPON_ANCHOR_POSES = {
    "idle": "weapon_idle",
    "weapon_idle": "weapon_idle",
    "jump_normal": "weapon_jump_normal",
    "jump_second": "weapon_jump_second",
    "spawn": "weapon_ground_throw",
    "jump_throw": "weapon_jump_throw",
    "attack_1": "weapon_basic_attack",
    "attack_2": "weapon_basic_attack",
    "attack_3": "weapon_basic_attack",
    "attack_punch": "weapon_basic_attack",
    "attack_kick": "weapon_basic_attack",
    "basic_attack": "weapon_basic_attack",
    "weapon_basic_attack": "weapon_basic_attack",
    "jump_attack": "weapon_jump_attack",
    "weapon_jump_attack": "weapon_jump_attack",
    "sprint_punch": "weapon_sprint_basic_attack",
    "sprint_basic_attack": "weapon_sprint_basic_attack",
    "sprint_attack": "weapon_sprint_basic_attack",
    "weapon_sprint_basic_attack": "weapon_sprint_basic_attack",
    "sprint_jump_basic_attack": "weapon_sprint_jump_basic_attack",
    "sprint_jump_attack": "weapon_sprint_jump_basic_attack",
    "weapon_sprint_jump_basic_attack": "weapon_sprint_jump_basic_attack",
    "get_up": "weapon_get_up",
}


def _is_throwable_item(item_id: str) -> bool:
    return item_id.partition("/")[0] == "throwables"


def _load_folder_frames(folder: Path, *, prefix: str | None = None) -> list[pygame.Surface]:
    frames: list[pygame.Surface] = []
    if not folder.exists():
        return frames

    frame_paths = (
        path
        for path in folder.iterdir()
        if path.is_file()
        and path.suffix.lower() in {".png", ".bmp"}
        and (prefix is None or path.stem.startswith(prefix))
    )
    for path in sorted(frame_paths, key=_sprite_frame_sort_key):
        frame = pygame.image.load(str(path)).convert()
        frame.set_colorkey((0, 0, 0))
        frames.append(frame)
    return frames


def _sprite_frame_sort_key(path: Path) -> tuple[str, int, str]:
    match = re.search(r"(\d+)$", path.stem)
    if match is None:
        return path.stem.casefold(), -1, path.suffix.casefold()
    return path.stem[:match.start()].casefold(), int(match.group(1)), path.suffix.casefold()


def _load_named_weapon_frames(root: Path, action_path: tuple[str, ...]) -> dict[str, dict[str, pygame.Surface]]:
    weapon_frames: dict[str, dict[str, pygame.Surface]] = {}
    weapons_root = root / "weapons"
    if not weapons_root.is_dir():
        return weapon_frames

    for weapon_folder in sorted(weapons_root.iterdir()):
        if not weapon_folder.is_dir() or weapon_folder.name.startswith("_"):
            continue
        frame_folder = weapon_folder.joinpath(*action_path)
        if not frame_folder.is_dir():
            continue

        frames: dict[str, pygame.Surface] = {}
        for path in sorted(
            (
                path
                for path in frame_folder.iterdir()
                if path.is_file() and path.suffix.lower() in {".png", ".bmp"}
            ),
            key=_sprite_frame_sort_key,
        ):
            frame_name = path.stem.casefold()
            if frame_name in frames:
                raise ValueError(f"Duplicate weapon frame name in {frame_folder}: {path.stem}")
            frame = pygame.image.load(str(path)).convert()
            frame.set_colorkey((0, 0, 0))
            frames[frame_name] = pygame.transform.scale(
                frame,
                (round(frame.get_width() * 1.2), round(frame.get_height() * 1.2)),
            )
        if frames:
            weapon_frames[f"weapons/{weapon_folder.name}"] = frames
    return weapon_frames


def _load_weapon_swing_frames(root: Path) -> dict[str, dict[str, pygame.Surface]]:
    return _load_named_weapon_frames(root, ("holding", "swing"))


def _load_weapon_throw_frames(root: Path) -> dict[str, dict[str, pygame.Surface]]:
    return _load_named_weapon_frames(root, ("throw",))


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
                    scaled_frames = _scale_frames(frames, 1.2)
                    animations[action_folder.name] = (
                        scaled_frames
                        if category_folder.name == "weapons" and action_folder.name == "holding"
                        else _trim_item_frames(scaled_frames)
                    )
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


def _is_spawnable_item(item_id: str, animations: dict, has_land_frames: bool) -> bool:
    return (
        item_id not in {BUZZ_BALL_ITEM_ID, BIGGIE_BALL_ITEM_ID}
        and bool(animations.get("spawn"))
        and bool(animations.get("holding"))
        and bool(animations.get("throw"))
        and has_land_frames
    )


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
        self.henry_float_timer = 0.0
        self.henry_float_elapsed = 0.0
        self.henry_float_offset = 0.0

    def start_henry_float(self) -> None:
        self.henry_float_timer = HENRY_FLOAT_DURATION
        self.henry_float_elapsed = 0.0
        self.henry_float_offset = 0.0

    def _update_henry_float(self, dt: float) -> None:
        if self.henry_float_timer <= 0.0:
            return

        self.henry_float_elapsed = min(HENRY_FLOAT_DURATION, self.henry_float_elapsed + dt)
        self.henry_float_timer = max(0.0, self.henry_float_timer - dt)
        easing_duration = min(0.18, HENRY_FLOAT_DURATION / 2)
        if self.henry_float_elapsed < easing_duration:
            self.henry_float_offset = HENRY_FLOAT_HEIGHT * self.henry_float_elapsed / easing_duration
        elif self.henry_float_timer < easing_duration:
            self.henry_float_offset = HENRY_FLOAT_HEIGHT * self.henry_float_timer / easing_duration
        else:
            self.henry_float_offset = HENRY_FLOAT_HEIGHT
        if self.henry_float_timer == 0.0:
            self.henry_float_offset = 0.0

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
        center_y = (
            self.y if self.phase in {"falling", "thrown", "bouncing"} else self.floor_y - frame.get_height() / 2
        ) - self.henry_float_offset
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
        self._update_henry_float(dt)
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
        center_y = (
            self.y if self.phase in {"falling", "bouncing"} else self.floor_y - frame.get_height() / 2
        ) - self.henry_float_offset
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
        self._update_henry_float(dt)
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
        return self.frames[self.frame_index].get_rect(center=(round(self.x), round(self.y - self.henry_float_offset)))

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        center_y = (
            self.y
            if self.phase in {"thrown", "falling", "bouncing"}
            else self.floor_y - frame.get_height() / 2
        ) - self.henry_float_offset
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


class IceFragmentEffect:
    FRAME_DURATION = 0.08
    GRAVITY = 900.0
    DURATION = 0.9

    def __init__(
        self,
        frames: list[pygame.Surface],
        x: float,
        y: float,
        velocity_x: float,
        velocity_y: float,
    ) -> None:
        self.frames = frames
        self.x = float(x)
        self.y = float(y)
        self.velocity_x = velocity_x
        self.velocity_y = velocity_y
        self.elapsed = 0.0
        self.finished = False

    def update(self, dt: float) -> bool:
        self.elapsed += dt
        self.x += self.velocity_x * dt
        self.y += self.velocity_y * dt
        self.velocity_y += self.GRAVITY * dt
        self.finished = self.elapsed >= self.DURATION
        return self.finished

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame_index = min(int(self.elapsed / self.FRAME_DURATION), len(self.frames) - 1)
        frame = self.frames[frame_index]
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class BuzzBallProjectile:
    FLIGHT_DISTANCE = 360.0
    SPEED_X = 480.0
    ARC_HEIGHT = 78.0

    def __init__(
        self,
        owner: Fighter,
        x: float,
        lane_y: float,
        facing: int,
        frames: list[pygame.Surface],
        origin_y: float | None = None,
    ) -> None:
        self.owner = owner
        self.x = float(x)
        self.lane_y = float(lane_y)
        self.ground_y = GROUND_Y + lane_y
        self.facing = 1 if facing >= 0 else -1
        self.frames = frames
        self.frame_index = 0
        self.elapsed = 0.0
        self.flight_duration = self.FLIGHT_DISTANCE / self.SPEED_X
        self.start_x = self.x
        ground_center_y = self.ground_y - self.frames[0].get_height() / 2
        self.y = ground_center_y if origin_y is None else float(origin_y)
        self.launch_height_offset = ground_center_y - self.y
        self.phase = "fly"
        self.damage = 1
        self.finished = False
        self.just_ground_hit = False

    def update(self, dt: float) -> None:
        if self.finished:
            return
        self.elapsed = min(self.flight_duration, self.elapsed + dt)
        progress = self.elapsed / self.flight_duration
        self.x = self.start_x + self.facing * self.FLIGHT_DISTANCE * progress
        self.frame_index = min(int(progress * len(self.frames)), len(self.frames) - 1)
        self.y = (
            self.ground_y
            - self.frames[self.frame_index].get_height() / 2
            - self.launch_height_offset * (1.0 - progress)
            - self.ARC_HEIGHT * math.sin(math.pi * progress)
        )
        if progress >= 1.0:
            self.finished = True
            self.just_ground_hit = True

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return frame.get_rect(center=(round(self.x), round(self.y)))

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, frame.get_rect(center=(round(self.x - camera_x), round(self.y))))


class BiggieBallProjectile:
    GRAVITY = 1400.0
    DAMAGE = 2

    def __init__(
        self,
        owner: Fighter,
        x: float,
        lane_y: float,
        frames: list[pygame.Surface],
    ) -> None:
        self.owner = owner
        self.x = float(x)
        self.lane_y = float(lane_y)
        self.ground_y = GROUND_Y + self.lane_y
        self.frames = frames
        self.frame_index = 0
        self.frame_timer = 0.0
        self.y = -self.frames[0].get_height() / 2
        self.velocity_y = 0.0
        self.just_ground_hit = False
        self.finished = False

    def update(self, dt: float) -> None:
        if self.finished:
            return
        self.frame_timer += dt
        while self.frame_timer >= 0.08:
            self.frame_timer -= 0.08
            self.frame_index = (self.frame_index + 1) % len(self.frames)
        self.velocity_y += self.GRAVITY * dt
        self.y += self.velocity_y * dt
        floor_center_y = self.ground_y - self.frames[self.frame_index].get_height() / 2
        if self.y >= floor_center_y:
            self.y = floor_center_y
            self.finished = True
            self.just_ground_hit = True

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        surface.blit(frame, frame.get_rect(center=(round(self.x - camera_x), round(self.y))))


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
    def __init__(self, difficulty: DifficultyProfile | None = None) -> None:
        self.difficulty = difficulty or get_difficulty_profile(DEFAULT_DIFFICULTY)
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
            self.throw_cooldown = 2.0 * self.difficulty.enemy_attack_cooldown_multiplier
            self.attack_cooldown = 0.9 * self.difficulty.enemy_attack_cooldown_multiplier
            return result

        if self_snapshot.state == "lift_heavy":
            result.attack_pressed = True
            result.attack_just_pressed = True
            return result

        if (
            target_attacking
            and same_lane
            and abs_dx < 95.0
            and random.random() < 0.18 * self.difficulty.enemy_block_chance_multiplier
        ):
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

        if (
            target_attacking
            and same_lane
            and abs_dx < 115.0
            and random.random() < 0.4 * self.difficulty.enemy_block_chance_multiplier
        ):
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
            self.attack_cooldown = 0.85 * self.difficulty.enemy_attack_cooldown_multiplier

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


class AshleySpriteEffect:
    def __init__(
        self,
        asset_folder: str,
        x: float,
        y: float,
        *,
        facing: int = 1,
        scale: float = 1.0,
        ground_anchored: bool = False,
        frame_prefix: str | None = None,
        foreground: bool = False,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.scale = scale
        self.ground_anchored = ground_anchored
        self.frame_prefix = frame_prefix
        self.foreground = foreground
        self.frame_timer = 0.0
        self.frame_index = 0
        self.finished = False
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / asset_folder
        self.frames = _load_folder_frames(root, prefix=frame_prefix) or [
            pygame.Surface((24, 24), pygame.SRCALPHA)
        ]

    def update(self, dt: float) -> None:
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
        width = max(1, round(frame.get_width() * self.scale))
        height = max(1, round(frame.get_height() * self.scale))
        if self.scale != 1.0:
            frame = pygame.transform.scale(frame, (width, height))
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        y = self.y - height if self.ground_anchored else self.y - height / 2
        surface.blit(frame, (int(self.x - camera_x - width / 2), int(y)))


class AshleyBlastProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.origin_x = float(x)
        self.facing = 1 if facing >= 0 else -1
        self.lane_y = float(owner.lane_y)
        self.speed_x = 720.0
        self.damage = 1
        self.phase = "fly"
        self.can_damage = True
        self.finished = False
        self.just_burst = False
        self.frame_timer = 0.0
        self.frame_index = 0
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "ashley_blast"
        self.fly_frames = _load_folder_frames(root / "fly")
        self.burst_frames = _load_folder_frames(root / "burst")
        fallback = [pygame.Surface((24, 24), pygame.SRCALPHA)]
        self.fly_frames = self.fly_frames or fallback
        self.burst_frames = self.burst_frames or fallback
        self.frames = self.fly_frames

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
        self.frames = self.burst_frames
        self.frame_index = 0
        self.frame_timer = 0.0
        self.just_burst = True

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


class AshleyMissileProjectile:
    def __init__(
        self,
        owner: Fighter,
        target: Fighter | None,
        x: float,
        y: float,
        facing: int,
        target_lane_y: float,
        missile_index: int,
        ground_target_x: float | None = None,
    ) -> None:
        self.owner = owner
        self.target = target
        self.x = float(x)
        self.y = float(y)
        self.origin_x = float(x)
        self.launch_x = float(x)
        self.start_y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.lane_y = float(target_lane_y)
        self.target_lane_y = float(target_lane_y)
        self.speed_x = 360.0
        self.arc_height = 80.0
        self.missile_index = missile_index
        self.damage = 1
        self.phase = "fly"
        self.can_damage = True
        self.finished = False
        self.just_ground_hit = False
        self.flight_timer = 0.0
        if ground_target_x is None and target is None:
            ground_target_x = self.x + self.facing * 360.0
        self.ground_target_x = ground_target_x
        destination_x = (
            target.world_hitbox_rect().centerx if target is not None else self.ground_target_x
        )
        self.flight_duration = max(0.45, abs(destination_x - self.launch_x) / self.speed_x)
        self.frame_timer = 0.0
        self.frame_index = 0
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "ashley_missile"
        self.fly_frames = _load_folder_frames(root / "fly")
        self.burst_frames = _load_folder_frames(root / "burst")
        fallback = [pygame.Surface((24, 24), pygame.SRCALPHA)]
        self.fly_frames = self.fly_frames or fallback
        self.burst_frames = self.burst_frames or fallback
        self.frames = self.fly_frames

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
        self.frames = self.burst_frames
        self.frame_index = 0
        self.frame_timer = 0.0

    def _begin_ground_fall(self) -> None:
        self.target = None
        self.launch_x = self.x
        self.start_y = self.y
        self.ground_target_x = self.x + self.facing * 220.0
        self.flight_timer = 0.0
        self.flight_duration = max(0.45, 220.0 / self.speed_x)
        self.arc_height = 0.0

    def update(self, dt: float) -> None:
        self.frame_timer += dt
        if self.phase == "fly":
            self.flight_timer += dt
            if self.target is not None and not self.target.is_dead:
                target_rect = self.target.world_hitbox_rect()
                target_x = target_rect.centerx
                target_y = target_rect.centery
                self.target_lane_y = float(self.target.lane_y)
                self.lane_y = self.target_lane_y
                if (target_x - self.x) * self.facing < 0.0:
                    self._begin_ground_fall()
            else:
                if self.target is not None:
                    self._begin_ground_fall()
            if self.target is None:
                target_x = self.ground_target_x
                target_y = GROUND_Y + self.target_lane_y - 18.0
            progress = min(1.0, self.flight_timer / self.flight_duration)
            arc = math.sin(math.pi * progress)
            self.x = self.launch_x + (target_x - self.launch_x) * progress
            self.x += math.sin(self.flight_timer * 4.0 + self.missile_index) * 10.0 * arc
            self.y = self.start_y + (target_y - self.start_y) * progress**2 - self.arc_height * arc
            if self.target is None and progress >= 1.0:
                self.x = self.ground_target_x
                self.y = GROUND_Y + self.target_lane_y - 18.0
                self.just_ground_hit = True
                self._start_burst()
                return
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


class JulianSkullProjectile:
    def __init__(self, owner: Fighter, target: Fighter | None, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.target = target
        self.lane_y = float(owner.lane_y)
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = float(owner.movement["run_speed"]) * 2.0
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
                target_is_in_lane = abs(self.target.lane_y - self.lane_y) <= 36
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
    def __init__(
        self,
        owner: Fighter,
        x: float,
        y: float,
        facing: int,
        asset_folder: str = "john_magical_barrier",
    ) -> None:
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
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / asset_folder
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


class AshleyMagicalBarrierEffect:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.base_y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.lane_y = float(owner.lane_y)
        self.phase = "create"
        self.life_timer = 0.0
        self.frame_timer = 0.0
        self.frame_index = 0
        self.reflect_frame_timer = 0.0
        self.reflect_frame_index = 0
        self.reflect_active = False
        self.speed_x = 125.0
        self.movement_enabled = False
        self.health = 2
        self.enemy_hits = 0
        self.reflect_count = 0
        self.hit_targets: set[int] = set()
        self.burst_after_reflect = False
        self.finished = False
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "ashley_magical_barrier"
        self.create_frames = _load_folder_frames(root / "create")
        self.barrier_frames = _load_folder_frames(root / "barrier")
        self.reflect_frames = _load_folder_frames(root / "barrier_reflect")
        self.burst_frames = _load_folder_frames(root / "burst")
        fallback = [pygame.Surface((48, 48), pygame.SRCALPHA)]
        self.create_frames = self.create_frames or fallback
        self.barrier_frames = self.barrier_frames or fallback
        self.reflect_frames = self.reflect_frames or fallback
        self.burst_frames = self.burst_frames or fallback
        self.frames = self.create_frames

    @property
    def can_reflect(self) -> bool:
        return self.phase == "barrier" and not self.burst_after_reflect

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(
            int(self.x - frame.get_width() / 2),
            int(self.y - frame.get_height() / 2),
            frame.get_width(),
            frame.get_height(),
        )

    def start_moving(self) -> None:
        self.movement_enabled = True

    def _enter_barrier(self) -> None:
        self.phase = "barrier"
        self.frames = self.barrier_frames
        self.frame_index = 0
        self.frame_timer = 0.0

    def _start_reflect(self, burst_after: bool = False) -> None:
        if self.phase != "barrier":
            return
        self.reflect_active = True
        self.reflect_frame_index = 0
        self.reflect_frame_timer = 0.0
        self.burst_after_reflect = burst_after

    def take_damage(self) -> None:
        if not self.can_reflect:
            return
        self.health -= 1
        self.reflect_count += 1
        self._start_reflect(self.health <= 0)

    def hit_enemy(self, target: Fighter) -> bool:
        if not self.can_reflect or id(target) in self.hit_targets:
            return False
        self.hit_targets.add(id(target))
        self.enemy_hits += 1
        self._start_reflect(self.enemy_hits >= 2)
        return True

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.reflect_active = False
        self.frames = self.burst_frames
        self.frame_index = 0
        self.frame_timer = 0.0

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
        if self.phase == "create":
            if self._advance_once(dt):
                self._enter_barrier()
        elif self.phase == "barrier":
            if self.movement_enabled:
                self.x += self.facing * self.speed_x * dt
                self.y = self.base_y + math.sin(self.life_timer * 3.0) * 5.0
            self.frame_timer += dt
            while self.frame_timer >= 0.12:
                self.frame_timer -= 0.12
                self.frame_index = (self.frame_index + 1) % len(self.frames)
            if self.reflect_active:
                self.reflect_frame_timer += dt
                while self.reflect_frame_timer >= 0.08:
                    self.reflect_frame_timer -= 0.08
                    self.reflect_frame_index += 1
                    if self.reflect_frame_index >= len(self.reflect_frames):
                        self.reflect_active = False
                        if self.burst_after_reflect:
                            self._start_burst()
                        else:
                            self.burst_after_reflect = False
                        break
        elif self.phase == "burst" and self._advance_once(dt):
            self.finished = True

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))

    def draw_reflect_overlay(self, surface: pygame.Surface, camera_x: float) -> None:
        if not self.reflect_active:
            return
        frame = self.reflect_frames[self.reflect_frame_index]
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
        blocks_movement: bool = True,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.lane_y = float(lane_y)
        self.owner = owner
        self.blocks_movement = blocks_movement
        self.break_cause: str | None = None
        self.break_direction = self.facing
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

    def break_apart(self, outward_direction: int | None = None) -> None:
        if self.finished:
            return
        self.finished = True
        self.just_expired = True
        self.break_cause = "damage"
        direction = self.facing if outward_direction is None else outward_direction
        self.break_direction = 1 if direction >= 0 else -1

    def update(self, dt: float) -> None:
        if self.finished:
            return
        self.lifetime = max(0.0, self.lifetime - dt)
        if self.lifetime == 0.0:
            self.finished = True
            self.just_expired = True
            self.break_cause = "timeout"
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


class AshleyManaOrbProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.lane_y = float(owner.lane_y)
        self.phase = "create"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.finished = False
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "ashley_mana_orb"
        self.create_frames = _load_folder_frames(root / "create")
        self.idle_frames = _load_folder_frames(root / "idle")
        fallback = [pygame.Surface((24, 24), pygame.SRCALPHA)]
        self.create_frames = self.create_frames or fallback
        self.idle_frames = self.idle_frames or fallback
        self.frames = self.create_frames

    def contact_rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - 20), int(self.y - 20), 40, 40)

    def update(self, dt: float) -> None:
        self.frame_timer += dt
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
        else:
            while self.frame_timer >= 0.10:
                self.frame_timer -= 0.10
                self.frame_index = (self.frame_index + 1) % len(self.frames)

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
        self.damage = 1
        self.elapsed = 0.0
        self.phase = "fly"
        self.frame_timer = 0.0
        self.frame_index = 0
        self.finished = False
        self.just_hit_ground = False
        self.hit_targets: set[int] = set()
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
    FLIGHT_RANGE_MULTIPLIER = 2.0

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
        self.distance_travelled = 0.0
        self.speed_x = owner.movement["run_speed"] * 1.25
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "woody_shot"
        self.fly_frames = _load_folder_frames(root / str(shot_set))
        self.burst_frames = _load_folder_frames(root / "burst")
        if not self.fly_frames or not self.burst_frames:
            raise FileNotFoundError(f"Woody shot sprites are missing from {root}")
        self.max_distance = (
            self.speed_x * self.FRAME_DURATION * len(self.fly_frames) * self.FLIGHT_RANGE_MULTIPLIER
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
            distance = min(self.max_distance, self.distance_travelled + self.speed_x * dt)
            self.x += self.facing * (distance - self.distance_travelled)
            self.distance_travelled = distance
            if self.distance_travelled >= self.max_distance:
                self._start_burst()
                return
            while self.frame_timer >= self.FRAME_DURATION:
                self.frame_timer -= self.FRAME_DURATION
                self.frame_index = (self.frame_index + 1) % len(self.fly_frames)
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
    def __init__(self, owner: Fighter, x: float, y: float, facing: int, lane_y: float | None = None) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.lane_y = float(owner.lane_y if lane_y is None else lane_y)
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


class WhiskeyFireTrailEffect(FireTrailEffect):
    def __init__(self, owner: Fighter, x: float, y: float) -> None:
        super().__init__(owner, x, y)
        self.hits_all_fighters = True


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
        map_name: str = "City",
        difficulty: str = DEFAULT_DIFFICULTY,
    ) -> None:
        if not stage_mode and not test_mode and enemy_names is not None and not enemy_names:
            raise ValueError("Play mode requires at least one opponent.")
        self.font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 24)
        self.pause_font = pygame.font.Font(None, 54)
        self.stage_title_font = pygame.font.Font(None, 76)
        self.stage_name_font = pygame.font.Font(None, 42)
        self.stage_act_font = pygame.font.Font(None, 28)
        self.stage_subtitle_font = pygame.font.Font(None, 26)
        self.stage_banner_heading_font = pygame.font.Font(None, 38)
        self.stage_banner_subtitle_font = pygame.font.Font(None, 24)
        self.stage_choice_font = pygame.font.Font(None, 30)
        self.projectiles: list[object] = []
        self.consumable_items: list[SpawnedConsumable | ThrownItem] = []
        self.paused = False
        self._pause_hover_candidate_key: str | None = None
        self._pause_hover_dwell = 0.0
        self._pause_card_hover_progress: dict[str, float] = {}
        self.stage_mode = stage_mode
        self.test_mode = test_mode
        self.difficulty = get_difficulty_profile(difficulty)
        self.stage_index = 0
        self.stage_wave_index = 0
        self.stage_wave_clear_timer: float | None = None
        self.stage_wave_enemies: list[Fighter] = []
        self.stage_wave_enemy_total = 0
        self._stage_enemy_spawn_queue: list[str] = []
        self._stage_corpse_timers: dict[Fighter, float] = {}
        self.stage_xp_orbs: list[XPOrb] = []
        self.stage_xp_total = 0
        self.stage_progression: StageProgression | None = None
        self.stage_card_ranks: dict[str, int] = {}
        self._stage_damage_remainder = 0.0
        self._stage_damage_reduction_remainder = 0.0
        self._stage_xp_remainder = 0.0
        self._stage_julian_skull_timer = 0.0
        self._stage_base_movement: dict[str, float] | None = None
        self._reset_stage_progression()
        self.stage_level_up_slot = StageLevelUpSlot()
        self.campaign_score = 0
        self.stage_intermission = False
        self.stage_intermission_choice = 0
        self.stage_card_mode = "stage"
        self.stage_card_timer = STAGE_CARD_DURATION if stage_mode else 0.0
        self.stage_milestone_reward_xp = 0
        self.stage_milestone_reward_stage = 0
        self.stage_milestone_reward_timer = 0.0
        self.stage_mode_failed = False
        self.return_to_menu_requested = False
        stage_config = STAGE_CONFIGS.get(map_name)
        if stage_config is None:
            raise ValueError(f"Unknown map: {map_name}")
        stage_directory, stage_type = stage_config
        stage_root = Path(__file__).resolve().parents[2] / "assets" / "maps" / stage_directory
        sounds_root = Path(__file__).resolve().parents[2] / "assets" / "sounds"
        self.stage = stage_type(stage_root)
        item_sprites_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "item_sprites"
        self.item_sprite_animations = _load_item_sprite_animations(item_sprites_root)
        self.weapon_swing_frames = _load_weapon_swing_frames(item_sprites_root)
        self.weapon_throw_frames = _load_weapon_throw_frames(item_sprites_root)
        self.item_hand_anchors = load_hand_anchors(item_sprites_root / "hand_anchors.json")
        self.weapon_hand_anchors = load_weapon_hand_anchors(item_sprites_root / "hand_anchors.json")
        self.weapon_anchor_reference = load_weapon_anchor_reference(item_sprites_root / "hand_anchors.json")
        self.weapon_reference_sprites = load_weapon_reference_sprites(item_sprites_root / "hand_anchors.json")
        if not self.weapon_anchor_reference:
            self.weapon_anchor_reference = DEFAULT_WEAPON_ANCHOR_REFERENCE
        milk_root = item_sprites_root / "consumables" / "milk"
        milk_animations = self.item_sprite_animations.get("consumables/milk", {})
        self.milk_throw_frames = milk_animations.get("throw", [])
        self.milk_break_frames = {
            "dust": milk_animations.get("broken/dust", []),
            "large_1": milk_animations.get("broken/large", []),
            "small": milk_animations.get("broken/small", []),
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
        whiskey_root = item_sprites_root / "consumables" / "whiskey"
        whiskey_animations = self.item_sprite_animations.get("consumables/whiskey", {})
        self.whiskey_break_frames = {
            name: whiskey_animations.get(f"broken/{name}", [])
            for name in ("dust", "large", "small_1", "small_2")
        }
        if (
            not whiskey_animations.get("spawn")
            or not self._land_frame_sets_for_item("consumables/whiskey")
            or not whiskey_animations.get("holding")
            or not whiskey_animations.get("drink")
            or not whiskey_animations.get("throw")
            or any(not frames for frames in self.whiskey_break_frames.values())
        ):
            raise FileNotFoundError(f"Whiskey sprites are missing from {whiskey_root}")
        particles_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "particals"
        self.drunk_bubbles_frames = _scale_frames(_load_folder_frames(particles_root / "drunk_bubbles"), 1.2)
        self.sleep_frames = _scale_frames(_load_folder_frames(particles_root / "sleep"), 1.2)
        if not self.drunk_bubbles_frames or not self.sleep_frames:
            raise FileNotFoundError(f"Whiskey status sprites are missing from {particles_root}")
        heavy_box_animations = self.item_sprite_animations.get(HEAVY_BOX_ITEM_ID, {})
        self.heavy_box_break_frames = {
            name: heavy_box_animations.get(f"broken/{name}", [])
            for name in ("large_chunk", "small_chunk_1", "small_chunk_2", "tiny_chunk")
        }
        if any(not frames for frames in self.heavy_box_break_frames.values()):
            raise FileNotFoundError(f"Heavy-box break sprites are missing from {item_sprites_root / 'throwables' / 'heavy_box' / 'broken'}")
        buzz_ball_animations = self.item_sprite_animations.get(BUZZ_BALL_ITEM_ID, {})
        self.buzz_ball_throw_frames = buzz_ball_animations.get("throw", [])
        self.buzz_ball_break_frames = {
            name: buzz_ball_animations.get(f"broken/{name}", [])
            for name in ("large", "small_1", "small_2")
        }
        if not self.buzz_ball_throw_frames or any(not frames for frames in self.buzz_ball_break_frames.values()):
            raise FileNotFoundError(f"Buzz Ball sprites are missing from {item_sprites_root / 'throwables' / 'buzz_ball'}")
        biggie_ball_animations = self.item_sprite_animations.get(BIGGIE_BALL_ITEM_ID, {})
        self.biggie_ball_drop_frames = biggie_ball_animations.get("spawn", [])
        self.biggie_ball_break_frames = {
            name: biggie_ball_animations.get(f"broken/{name}", [])
            for name in ("large", "small_1", "small_2")
        }
        if not self.biggie_ball_drop_frames or any(not frames for frames in self.biggie_ball_break_frames.values()):
            raise FileNotFoundError(f"Biggie Ball sprites are missing from {item_sprites_root / 'throwables' / 'biggie_ball'}")
        self.spawnable_items = sorted(
            item_id
            for item_id, animations in self.item_sprite_animations.items()
            if _is_spawnable_item(
                item_id,
                animations,
                bool(self._land_frame_sets_for_item(item_id)),
            )
        )
        self.active_item_overlays: dict[Fighter, tuple[str, ItemSpriteAnimation, str | None]] = {}
        self.whiskey_status_effects: dict[Fighter, dict] = {}
        self.held_item_animations: dict[Fighter, tuple[str, ItemSpriteAnimation]] = {}
        self.consumable_break_effects: list[
            ConsumableBreakEffect | HeavyBoxBreakEffect | ItemBreakEffect | MetalFragmentEffect | IceFragmentEffect
        ] = []
        fragment_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "particals"
        ice_fragment_root = fragment_root / "ice_fragment"
        self.ice_fragment_frames = {
            name: _scale_frames(_load_folder_frames(ice_fragment_root / name), 2.0)
            for name in ("large_1", "large_2", "medium_1", "small_1")
        }
        if any(not frames for frames in self.ice_fragment_frames.values()):
            raise FileNotFoundError(f"Ice fragment sprites are missing from {ice_fragment_root}")
        self.ice_fragment_large_toggle = 0
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
        if self.stage_mode or self.test_mode:
            self._apply_stage_card_modifiers()
        self.enemy_names = enemy_names
        self.enemies: list[Fighter] = []
        self.enemy_brains: dict[Fighter, BanditBrain] = {}
        self._spawn_encounter(x_bounds, start_x)
        self.camera_focus_x = self._desired_camera_focus_x()
        self.victory_played = False

    def _spawn_encounter(self, x_bounds: tuple[float, float], start_x: float) -> None:
        if self.stage_mode:
            wave = self._endless_encounter(self.stage_index + 1).waves[self.stage_wave_index]
            self.stage_wave_enemies = []
            self._stage_enemy_spawn_queue = [
                name for name, count in wave.enemies for _ in range(count)
            ]
            self.stage_wave_enemy_total = len(self._stage_enemy_spawn_queue)
            self._dispatch_stage_enemy_spawns(x_bounds)
            return
        elif self.test_mode:
            character_names = []
        else:
            character_names = list(self.enemy_names if self.enemy_names is not None else ("bandit",))
        if not self.stage_mode:
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
            enemy.max_health = QUICK_PLAY_OPPONENT_HEALTH
            enemy.max_health = self.difficulty.scale_enemy_health(enemy.max_health)
            enemy.health = enemy.max_health
            enemy.controls_enabled = True
            self.enemies.append(enemy)
            self.enemy_brains[enemy] = BanditBrain(self.difficulty)

    def _endless_encounter(self, stage_number: int):
        difficulty = getattr(self, "difficulty", None)
        return get_endless_encounter(
            stage_number,
            getattr(difficulty, "name", "Medium"),
        )

    def _dispatch_stage_enemy_spawns(
        self,
        x_bounds: tuple[float, float] | None = None,
    ) -> None:
        spawn_queue = getattr(self, "_stage_enemy_spawn_queue", [])
        if not self.stage_mode or not spawn_queue:
            return
        active_count = sum(not enemy.is_dead for enemy in self.stage_wave_enemies)
        active_enemy_cap = STAGE_MAX_ACTIVE_ENEMIES + int(
            stage_card_effects(
                getattr(self, "stage_card_ranks", {})
            )["active_enemy_bonus"]
        )
        slots = min(
            active_enemy_cap - active_count,
            len(spawn_queue),
        )
        if slots <= 0:
            return
        if x_bounds is None:
            x_bounds = (self.stage.play_min_x, self.stage.play_max_x)
        focus_x = (
            self._camera_focus_x()
            if hasattr(self, "camera_focus_x")
            else self.fighter.x
        )
        positions, spawn_facing = self._stage_wave_spawn_positions(
            slots,
            x_bounds,
            focus_x,
        )
        enemy_health_bonus = int(
            stage_card_effects(
                getattr(self, "stage_card_ranks", {})
            )["enemy_health_bonus"]
        )
        for character_name, (x, lane_y) in zip(
            spawn_queue[:slots],
            positions,
        ):
            enemy = Fighter(
                FighterConfig(character_name, CHARACTERS[character_name]),
                (x, lane_y),
                x_bounds=x_bounds,
            )
            enemy.facing = spawn_facing
            normal_max_health = self.difficulty.scale_enemy_health(enemy.max_health)
            enemy.max_health = max(1, round(normal_max_health / 2) + enemy_health_bonus)
            enemy.health = enemy.max_health
            enemy.controls_enabled = True
            self.enemies.append(enemy)
            self.stage_wave_enemies.append(enemy)
            self.enemy_brains[enemy] = BanditBrain(self.difficulty)
        del spawn_queue[:slots]

    def _stage_wave_spawn_positions(
        self,
        enemy_count: int,
        x_bounds: tuple[float, float],
        focus_x: float,
    ) -> tuple[list[tuple[float, float]], int]:
        camera_x = self.stage.camera_x(focus_x)
        view_left = camera_x
        view_right = camera_x + SCREEN_WIDTH
        spawn_margin = STAGE_ENEMY_SPAWN_MARGIN
        can_spawn_left = view_left - spawn_margin >= x_bounds[0]
        can_spawn_right = view_right + spawn_margin <= x_bounds[1]

        if can_spawn_right and (
            not can_spawn_left or self.fighter.x <= (view_left + view_right) / 2
        ):
            side = 1
        elif can_spawn_left:
            side = -1
        else:
            side = 1 if x_bounds[1] - view_right >= view_left - x_bounds[0] else -1

        positions = []
        lane_count = 3
        lane_step = (LANE_MAX_Y - LANE_MIN_Y) / (lane_count - 1)
        for index in range(enemy_count):
            offset = spawn_margin + (index // lane_count) * 54.0
            if side > 0:
                x = min(x_bounds[1], view_right + offset)
            else:
                x = max(x_bounds[0], view_left - offset)
            lane_y = LANE_MIN_Y + (index % lane_count) * lane_step
            positions.append((x, lane_y))
        return positions, -side

    def _age_stage_enemy_corpses(self, dt: float) -> None:
        for enemy, remaining in tuple(self._stage_corpse_timers.items()):
            remaining -= dt
            if remaining > 0.0:
                self._stage_corpse_timers[enemy] = remaining
                continue
            self._stage_corpse_timers.pop(enemy, None)
            if enemy in self.enemies:
                self.enemies.remove(enemy)
            self.enemy_brains.pop(enemy, None)

    def _register_stage_enemy_corpses(self) -> None:
        if not self.stage_mode:
            return
        for enemy in self.enemies:
            if enemy.is_dead and enemy not in self._stage_corpse_timers:
                self._stage_corpse_timers[enemy] = STAGE_CORPSE_DURATION
                self._add_stage_xp_orb(
                    getattr(enemy, "x", 0.0),
                    getattr(enemy, "lane_y", 0.0),
                    enemy_xp_reward(getattr(enemy, "name", "")),
                )

    def _add_stage_xp_orb(self, x: float, lane_y: float, xp_value: int) -> None:
        orbs = getattr(self, "stage_xp_orbs", None)
        if orbs is None:
            self.stage_xp_orbs = []
            orbs = self.stage_xp_orbs
        if len(orbs) >= STAGE_MAX_XP_ORBS:
            nearest = min(
                orbs,
                key=lambda orb: (orb.x - x) ** 2 + (orb.lane_y - lane_y) ** 2,
            )
            nearest.xp_value += xp_value
            return
        orbs.append(XPOrb(x, lane_y, xp_value))

    def _spawn_test_xp_orb(self) -> None:
        if not getattr(self, "test_mode", False) or self.stage_mode:
            return
        camera_x = self.stage.camera_x(self._camera_focus_x())
        left = max(self.stage.play_min_x, camera_x + 48.0)
        right = min(self.stage.play_max_x, camera_x + SCREEN_WIDTH - 48.0)
        if right < left:
            left = right = min(
                self.stage.play_max_x,
                max(self.stage.play_min_x, self.fighter.x),
            )
        self._add_stage_xp_orb(
            random.uniform(left, right),
            random.uniform(LANE_MIN_Y, LANE_MAX_Y),
            random.choice((5, 10, 15, 20, 25)),
        )

    def _update_stage_xp_orbs(self, dt: float) -> None:
        if not (self.stage_mode or getattr(self, "test_mode", False)):
            return
        orbs = getattr(self, "stage_xp_orbs", [])
        remaining_orbs = []
        effects = stage_card_effects(getattr(self, "stage_card_ranks", {}))
        for orb in orbs:
            if orb.overlaps(self.fighter, effects["xp_range_multiplier"]):
                self._award_stage_xp(orb.xp_value)
            else:
                orb.update(dt)
                remaining_orbs.append(orb)
        self.stage_xp_orbs = remaining_orbs

    def _reset_stage_progression(self) -> None:
        self.stage_progression = (
            StageProgression()
            if self.stage_mode or getattr(self, "test_mode", False)
            else None
        )
        self.stage_xp_total = 0
        self.stage_card_ranks = {}
        self._stage_damage_remainder = 0.0
        self._stage_damage_reduction_remainder = 0.0
        self._stage_xp_remainder = 0.0
        self._stage_julian_skull_timer = 0.0
        if (self.stage_mode or getattr(self, "test_mode", False)) and hasattr(self, "fighter"):
            self._apply_stage_card_modifiers()

    def _award_stage_xp(self, amount: int) -> None:
        if not (self.stage_mode or getattr(self, "test_mode", False)):
            return
        effects = stage_card_effects(getattr(self, "stage_card_ranks", {}))
        scaled_amount = amount * effects["xp_gain_multiplier"] + getattr(
            self, "_stage_xp_remainder", 0.0
        )
        amount = int(scaled_amount)
        self._stage_xp_remainder = scaled_amount - amount
        if amount <= 0:
            return
        progression = getattr(self, "stage_progression", None)
        if progression is None:
            progression = StageProgression(getattr(self, "stage_xp_total", 0))
            self.stage_progression = progression
        progression.add_xp(amount)
        self.stage_xp_total = progression.xp_total

    def _apply_stage_card_modifiers(self) -> None:
        if not (
            getattr(self, "stage_mode", False)
            or getattr(self, "test_mode", False)
        ):
            return
        fighter = getattr(self, "fighter", None)
        if fighter is None:
            return
        ranks = getattr(self, "stage_card_ranks", {})
        effects = stage_card_effects(ranks)
        base_movement = getattr(self, "_stage_base_movement", None)
        if base_movement is None:
            base_movement = dict(fighter.movement)
            self._stage_base_movement = base_movement
        fighter.movement.update(
            {
                name: speed * effects["movement_multiplier"]
                for name, speed in base_movement.items()
                if name in {"walk_speed", "run_speed", "lane_speed"}
            }
        )
        base_max_health = int(fighter.stats.get("max_health", fighter.max_health))
        fighter.max_health = base_max_health + int(effects["max_health_bonus"])
        fighter.health = min(fighter.health, fighter.max_health)

    def _apply_stage_card(self, title: str) -> bool:
        if not (
            getattr(self, "stage_mode", False)
            or getattr(self, "test_mode", False)
        ):
            return False
        card = CARDS_BY_TITLE.get(title)
        if card is None:
            return False
        ranks = getattr(self, "stage_card_ranks", {})
        rank = ranks.get(card.key, 0)
        ranks[card.key] = rank + 1
        self.stage_card_ranks = ranks
        if self.stage_mode and card.effect == "enemy_health":
            health_bonus = int(card.amount_per_rank)
            for enemy in getattr(self, "stage_wave_enemies", []):
                if not enemy.is_dead:
                    enemy.max_health += health_bonus
                    enemy.health += health_bonus
        if self.stage_mode and card.effect == "julian_skull" and rank == 0:
            self._stage_julian_skull_timer = STAGE_CURSE_SKULL_INITIAL_DELAY
        self._apply_stage_card_modifiers()
        if self.stage_mode and card.effect == "active_enemy":
            self._dispatch_stage_enemy_spawns()
        return True

    def _update_stage_curse_attacks(self, dt: float) -> None:
        if not self.stage_mode:
            return
        interval = stage_card_effects(
            getattr(self, "stage_card_ranks", {})
        )["julian_skull_interval"]
        if interval <= 0.0 or self.fighter.is_dead:
            return
        active_enemies = [
            enemy
            for enemy in getattr(self, "stage_wave_enemies", [])
            if not enemy.is_dead
        ]
        if not active_enemies:
            return
        self._stage_julian_skull_timer = max(
            0.0,
            getattr(
                self,
                "_stage_julian_skull_timer",
                STAGE_CURSE_SKULL_INITIAL_DELAY,
            )
            - max(0.0, dt),
        )
        if self._stage_julian_skull_timer > 0.0:
            return

        camera_x = self.stage.camera_x(self.fighter.x)
        player_screen_x = self.fighter.x - camera_x
        if player_screen_x < SCREEN_WIDTH / 2:
            origin_x = camera_x + SCREEN_WIDTH - 120.0
            facing = -1
        else:
            origin_x = camera_x + 120.0
            facing = 1
        origin_y = GROUND_Y + self.fighter.lane_y - 56.0
        projectile = JulianSkullProjectile(
            active_enemies[0],
            self.fighter,
            origin_x,
            origin_y,
            facing,
        )
        projectile.lane_y = float(self.fighter.lane_y)
        self.projectiles.append(projectile)
        self._stage_julian_skull_timer = interval

    def _transform_luis_if_pending(self, fighter: Fighter) -> None:
        if not fighter.luis_transform_pending:
            return
        fighter.transform_to(FighterConfig("luis_liberated", CHARACTERS["luis_liberated"]))
        if fighter is self.fighter and (
            self.stage_mode or getattr(self, "test_mode", False)
        ):
            self._stage_base_movement = None
            self._apply_stage_card_modifiers()

    def consume_stage_level_up(self) -> int | None:
        """Consume one queued level-up after its temporary offer screen is confirmed."""
        if not (self.stage_mode or getattr(self, "test_mode", False)):
            return None
        progression = getattr(self, "stage_progression", None)
        return progression.consume_pending_level() if progression is not None else None

    def _ensure_stage_level_up_slot(self) -> None:
        if (
            not (self.stage_mode or getattr(self, "test_mode", False))
            or (
                self.stage_mode
                and (
                    getattr(self, "stage_mode_failed", False)
                    or getattr(self, "stage_intermission", False)
                )
            )
        ):
            return
        slot = getattr(self, "stage_level_up_slot", None)
        if slot is None:
            slot = StageLevelUpSlot()
            self.stage_level_up_slot = slot
        progression = getattr(self, "stage_progression", None)
        if not slot.active and progression is not None and progression.pending_levels:
            while progression.pending_levels and not slot.active:
                if not slot.start(
                    progression.pending_levels[0],
                    getattr(self, "stage_card_ranks", {}),
                ):
                    progression.consume_pending_level()

    def _update_stage_level_up_slot(self, dt: float, inputs: FighterInput) -> None:
        self._ensure_stage_level_up_slot()
        slot = self.stage_level_up_slot
        if not slot.active:
            return
        slot.update(dt)
        if not slot.ready:
            return
        if inputs.left_just_pressed:
            slot.move_selection(-1)
        elif inputs.right_just_pressed:
            slot.move_selection(1)
        if inputs.attack_just_pressed:
            selected = slot.confirm()
            if selected is not None:
                self._apply_stage_card(selected)
            self.consume_stage_level_up()
            self._ensure_stage_level_up_slot()

    def _update_test_level_up_slot(self, dt: float, inputs: FighterInput) -> bool:
        if not self.test_mode or self.stage_mode:
            return False
        slot = self.stage_level_up_slot
        if not slot.active and inputs.test_level_up_just_pressed:
            slot.start(1, visual_only=True)
        if not slot.active:
            return False

        slot.update(dt)
        if slot.ready:
            if inputs.left_just_pressed:
                slot.move_selection(-1)
            elif inputs.right_just_pressed:
                slot.move_selection(1)
            if inputs.attack_just_pressed:
                slot.confirm()
        return True

    def _get_stage_level_up_slot_frame(self) -> pygame.Surface:
        frame = getattr(self, "_stage_level_up_slot_frame", None)
        if frame is None:
            frame_path = (
                Path(__file__).resolve().parents[2]
                / "assets"
                / "sprites"
                / "ui"
                / "stage_mode"
                / "card_slot"
                / "1.png"
            )
            if not frame_path.is_file():
                raise FileNotFoundError(
                    f"Required Stage Mode card-slot sprite is missing: {frame_path}"
                )
            frame = pygame.image.load(str(frame_path))
            if frame.get_size() != STAGE_SLOT_CANVAS_SIZE:
                raise ValueError(
                    "Stage Mode card-slot sprite must be 1040x598 pixels: "
                    f"{frame_path}"
                )
            frame = pygame.transform.smoothscale(frame, STAGE_SLOT_DISPLAY_SIZE)
            self._stage_level_up_slot_frame = frame
        return frame

    def _draw_stage_level_up_slot(self, surface: pygame.Surface) -> None:
        slot = self.stage_level_up_slot
        if (
            not (self.stage_mode or getattr(self, "test_mode", False))
            or not slot.active
            or self.paused
            or self.stage_mode_failed
            or self.stage_intermission
        ):
            return

        shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        shade.fill((4, 8, 16, 205))
        surface.blit(shade, (0, 0))
        panel = pygame.Rect((0, 0), STAGE_SLOT_DISPLAY_SIZE)
        panel.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        surface.blit(self._get_stage_level_up_slot_frame(), panel.topleft)
        title_font = _stage_card_font(round(46 * STAGE_SLOT_SCALE))
        subtitle_font = _stage_card_font(round(21 * STAGE_SLOT_SCALE))
        title = title_font.render("LEVEL UP!", True, (255, 223, 143))
        surface.blit(
            title,
            title.get_rect(
                center=(
                    panel.centerx,
                    panel.y + round(128 * STAGE_SLOT_SCALE),
                )
            ),
        )
        subtitle = subtitle_font.render(
            f"Level {slot.level_id}  •  Spin for three offers",
            True,
            (220, 227, 237),
        )
        surface.blit(
            subtitle,
            subtitle.get_rect(
                center=(
                    panel.centerx,
                    panel.y + round(181 * STAGE_SLOT_SCALE),
                )
            ),
        )

        reel_centers = tuple(
            round(center * STAGE_SLOT_SCALE) for center in (242, 520, 797)
        )
        card_font = _stage_card_font(round(18 * STAGE_SLOT_SCALE))
        detail_font = _stage_card_font(round(14 * STAGE_SLOT_SCALE))
        perk_font = _stage_card_font(round(15 * STAGE_SLOT_SCALE))
        for index, title in enumerate(slot.reel_labels):
            window = _scale_stage_slot_rect(STAGE_CARD_WINDOWS[index]).move(
                panel.topleft
            )
            center_x = panel.x + reel_centers[index]
            selected = slot.ready and slot.selected_index == index
            old_clip = surface.get_clip()
            surface.set_clip(window)
            if slot.stopped[index]:
                card = CARDS_BY_TITLE[slot.offers[index]]
                image = _load_stage_card_image(card.key)
                card_rect = image.get_rect(center=window.center)
                surface.blit(image, card_rect)
                _apply_stage_card_glow(
                    surface,
                    card.key,
                    image.get_size(),
                    destination=card_rect.topleft,
                )

                title_text = card_rank_title(card, slot.offer_ranks[index])
                revealed_title = slot.revealed_text(index, 0)
                title_x = card_rect.centerx - card_font.size(title_text)[0] // 2
                title_y = (
                    card_rect.y
                    + round(34 * STAGE_SLOT_SCALE)
                    - card_font.get_height() // 2
                )
                for position, character in enumerate(title_text):
                    if character.isspace() or (
                        position < len(revealed_title)
                        and revealed_title[position] != " "
                    ):
                        glyph = card_font.render(character, True, (255, 235, 180))
                        surface.blit(
                            glyph,
                            (
                                title_x + card_font.size(title_text[:position])[0],
                                title_y,
                            ),
                        )

                description = card.description
                revealed_description = slot.revealed_text(index, 1)
                description_lines = _wrap_stage_card_text(
                    description,
                    detail_font,
                    STAGE_CARD_SIZE[0] - round(24 * STAGE_SLOT_SCALE),
                )
                footer_y = card_rect.y + round(202 * STAGE_SLOT_SCALE)
                for line, start, end in description_lines[:2]:
                    revealed_line = revealed_description[start:end]
                    line_x = card_rect.centerx - detail_font.size(line)[0] // 2
                    for position, character in enumerate(line):
                        if character.isspace() or (
                            position < len(revealed_line)
                            and revealed_line[position] != " "
                        ):
                            glyph = detail_font.render(character, True, (247, 239, 220))
                            surface.blit(
                                glyph,
                                (
                                    line_x + detail_font.size(line[:position])[0],
                                    footer_y,
                                ),
                            )
                    footer_y += round(15 * STAGE_SLOT_SCALE)

                perk = card.perk
                revealed_perk = slot.revealed_text(index, 2)
                perk_x = card_rect.centerx - perk_font.size(perk)[0] // 2
                perk_y = card_rect.y + STAGE_CARD_SIZE[1] - round(
                    45 * STAGE_SLOT_SCALE
                )
                for position, character in enumerate(perk):
                    if character.isspace() or (
                        position < len(revealed_perk)
                        and revealed_perk[position] != " "
                    ):
                        glyph = perk_font.render(character, True, (255, 217, 126))
                        surface.blit(
                            glyph,
                            (
                                perk_x + perk_font.size(perk[:position])[0],
                                perk_y,
                            ),
                        )
            else:
                position = slot.reel_scroll_positions[index]
                first_card = int(position)
                offset = position - first_card
                sequence = slot.reel_card_sequences[index]
                for stack_offset in range(3):
                    sequence_index = min(first_card + stack_offset, len(sequence) - 1)
                    stack_card = CARDS_BY_TITLE[sequence[sequence_index]]
                    image = _load_stage_card_image(stack_card.key)
                    card_rect = image.get_rect(
                        center=(
                            window.centerx,
                            round(
                                window.centery
                                + (stack_offset - offset) * image.get_height()
                            ),
                        )
                    )
                    surface.blit(image, card_rect)
                    _apply_stage_card_glow(
                        surface,
                        stack_card.key,
                        image.get_size(),
                        destination=card_rect.topleft,
                    )
            surface.set_clip(old_clip)

            if selected:
                outline = round(4 * STAGE_SLOT_SCALE)
                selection = pygame.Rect(
                    window.x - outline,
                    window.y - outline,
                    window.width + outline * 2,
                    window.height + outline * 2,
                )
                pygame.draw.rect(
                    surface,
                    (255, 215, 117),
                    selection,
                    width=outline,
                    border_radius=round(8 * STAGE_SLOT_SCALE),
                )

        if slot.ready:
            controls = (
                f"{KEY_BINDINGS.label('move_left')} / {KEY_BINDINGS.label('move_right')}  Select"
                f"      {KEY_BINDINGS.label('attack')}  Choose"
            )
        else:
            controls = "Reels are spinning..."
        control_font = _stage_card_font(round(20 * STAGE_SLOT_SCALE))
        control_label = control_font.render(controls, True, (236, 240, 247))
        surface.blit(
            control_label,
            control_label.get_rect(
                center=(
                    panel.centerx,
                    panel.y + round(516 * STAGE_SLOT_SCALE),
                )
            ),
        )
        if slot.ready:
            pygame.draw.line(
                surface,
                (255, 215, 117),
                (
                    panel.x + round(102 * STAGE_SLOT_SCALE),
                    panel.y + round(476 * STAGE_SLOT_SCALE),
                ),
                (
                    panel.right - round(102 * STAGE_SLOT_SCALE),
                    panel.y + round(476 * STAGE_SLOT_SCALE),
                ),
                max(1, round(2 * STAGE_SLOT_SCALE)),
            )

    def _stage_progress_display(self) -> tuple[int, int, int] | None:
        progression = getattr(self, "stage_progression", None)
        if not (self.stage_mode or getattr(self, "test_mode", False)) or progression is None:
            return None
        return (
            progression.level,
            progression.xp_into_level,
            progression.xp_for_next_level,
        )

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
        self.campaign_score += 100 * getattr(
            self,
            "stage_wave_enemy_total",
            len(self.stage_wave_enemies),
        )
        self.stage_wave_clear_timer = None
        encounter = self._endless_encounter(self.stage_index + 1)
        if self.stage_wave_index + 1 < len(encounter.waves):
            self.stage_wave_index += 1
            x_bounds = (self.stage.play_min_x, self.stage.play_max_x)
            self._spawn_encounter(x_bounds, self.fighter.x)
            self.stage_card_mode = "wave"
            self.stage_card_timer = STAGE_CARD_DURATION
            self.victory_played = False
            return

        if (self.stage_index + 1) % ENDLESS_SUPPLY_BREAK_INTERVAL == 0:
            self.stage_intermission = True
            self.stage_intermission_choice = 0
            return

        self._start_next_campaign_stage()

    def _start_next_campaign_stage(self) -> None:
        completed_stage = self.stage_index + 1
        if completed_stage % 5 == 0:
            previous_xp = getattr(self, "stage_xp_total", 0)
            self._award_stage_xp(
                completed_stage * STAGE_MILESTONE_XP_PER_STAGE
            )
            self.stage_milestone_reward_xp = (
                self.stage_xp_total - previous_xp
            )
            self.stage_milestone_reward_stage = completed_stage
            self.stage_milestone_reward_timer = STAGE_CARD_DURATION
        self.stage_index += 1
        self.stage_wave_index = 0
        x_bounds = (self.stage.play_min_x, self.stage.play_max_x)
        self._spawn_encounter(x_bounds, self.fighter.x)
        self.stage_card_mode = "stage"
        self.stage_card_timer = STAGE_CARD_DURATION
        self.victory_played = False

    def _confirm_recovery_choice(self) -> None:
        if self.stage_intermission_choice == 0:
            recovery = min(
                max(0, self.fighter.max_health - self.fighter.health),
                max(1, self.fighter.max_health // 4),
            )
            self.fighter.health += recovery
        else:
            recovery = min(
                max(0, self.fighter.max_mana - self.fighter.mana),
                max(1, self.fighter.max_mana // 4),
            )
            self.fighter.mana += recovery
        self.stage_intermission = False
        self._start_next_campaign_stage()

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

    def _deal_damage(
        self,
        attacker: Fighter,
        target: Fighter,
        amount: int,
        ignore_invulnerability: bool = False,
        apply_whiskey_multiplier: bool = True,
    ) -> None:
        target_can_receive_damage = (
            amount > 0
            and not getattr(target, "is_dead", False)
            and (
                ignore_invulnerability
                or (
                    getattr(target, "damage_cooldown", 0.0) <= 0.0
                    and not getattr(target, "is_invulnerable", False)
                )
            )
        )
        if (
            getattr(self, "stage_mode", False)
            or getattr(self, "test_mode", False)
        ):
            effects = stage_card_effects(getattr(self, "stage_card_ranks", {}))
            if attacker is getattr(self, "fighter", None) and target_can_receive_damage:
                scaled = amount * effects["damage_multiplier"] + getattr(
                    self, "_stage_damage_remainder", 0.0
                )
                amount = int(scaled)
                self._stage_damage_remainder = scaled - amount
                if amount <= 0:
                    return
        effect = self.whiskey_status_effects.get(attacker) if apply_whiskey_multiplier else None
        multiplier = 2 if effect is not None and not effect["sleeping"] else 1
        amount *= multiplier
        if (
            (
                getattr(self, "stage_mode", False)
                or getattr(self, "test_mode", False)
            )
            and target is getattr(self, "fighter", None)
            and target_can_receive_damage
        ):
            effects = stage_card_effects(getattr(self, "stage_card_ranks", {}))
            blocked = amount * effects["damage_reduction"] + getattr(
                self, "_stage_damage_reduction_remainder", 0.0
            )
            reduced = int(blocked)
            self._stage_damage_reduction_remainder = blocked - reduced
            amount = max(0, amount - reduced)
        target.receive_damage(amount, ignore_invulnerability=ignore_invulnerability)

    def _break_whiskey_item(self, item: ConsumableItem, spawn_fire: bool) -> bool:
        if item.item_id != "consumables/whiskey" or item not in self.consumable_items:
            return False
        self.consumable_items.remove(item)
        self.audio.play("drink_break")
        frames = self.whiskey_break_frames
        self.consumable_break_effects.append(
            ConsumableBreakEffect(
                item.x,
                item.lane_y,
                frames["dust"],
                frames["large"],
                frames["small_1"],
            )
        )
        fragment_y = GROUND_Y + item.lane_y - 10.0
        self.consumable_break_effects.extend(
            (
                IceFragmentEffect(frames["small_1"], item.x, fragment_y, -250.0, -210.0),
                IceFragmentEffect(frames["small_2"], item.x, fragment_y, 250.0, -210.0),
            )
        )
        if spawn_fire:
            self.projectiles.append(
                WhiskeyFireTrailEffect(
                    self.fighter,
                    item.x,
                    GROUND_Y + item.lane_y - 22.0,
                )
            )
        return True

    def _break_buzz_ball(self, projectile: BuzzBallProjectile) -> None:
        self.audio.play("drink_break")
        fragment_y = projectile.ground_y - 24.0
        self.consumable_break_effects.extend(
            (
                IceFragmentEffect(
                    self.buzz_ball_break_frames["large"],
                    projectile.x,
                    fragment_y,
                    -260.0,
                    -300.0,
                ),
                IceFragmentEffect(
                    self.buzz_ball_break_frames["small_1"],
                    projectile.x,
                    fragment_y,
                    320.0,
                    -250.0,
                ),
                IceFragmentEffect(
                    self.buzz_ball_break_frames["small_2"],
                    projectile.x,
                    fragment_y,
                    -380.0,
                    -180.0,
                ),
            )
        )

    def _break_biggie_ball(self, projectile: BiggieBallProjectile) -> None:
        self.audio.play("drink_break")
        fragment_y = projectile.ground_y - 24.0
        self.consumable_break_effects.extend(
        (
            IceFragmentEffect(
                self.biggie_ball_break_frames["large"],
                projectile.x,
                fragment_y,
                -260.0,
                -300.0,
            ),
            IceFragmentEffect(
                self.biggie_ball_break_frames["small_1"],
                projectile.x,
                fragment_y,
                320.0,
                -250.0,
            ),
            IceFragmentEffect(
                self.biggie_ball_break_frames["small_2"],
                projectile.x,
                fragment_y,
                -380.0,
                -180.0,
            ),
        )
        )

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

    @staticmethod
    def _melee_attack_rect(attacker: Fighter, attack_range: int = 72) -> pygame.Rect:
        attack_rect = attacker.world_hitbox_rect()
        if attacker.name == "dark_bat" and attacker.state == "sp_move_attack_1":
            attack_rect.width += DARK_BAT_SP_MOVE_ATTACK_REACH
            if attacker.facing < 0:
                attack_rect.x -= DARK_BAT_SP_MOVE_ATTACK_REACH
            return attack_rect
        return attack_rect.inflate(attack_range, 0)

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

            attack_range = 96 if attacker.name == "dark_bat" and attacker.state == "jump_throw" else 72
            attack_rect = self._melee_attack_rect(attacker, attack_range)
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
            pickup_range = self._item_pickup_range(fighter, item)
            if item.pickupable and abs(fighter.x - item.x) <= pickup_range and abs(fighter.lane_y - item.lane_y) <= 24.0:
                self.consumable_items.remove(item)
                fighter.state = "get_up"
                fighter.state_timer = 0.36
                fighter.held_item = item.item_id
                fighter.held_item_landings = item.landing_count
                return True
        return False

    @staticmethod
    def _item_pickup_range(fighter: Fighter, item: SpawnedConsumable | ThrownItem) -> float:
        pickup_range = 56.0
        if item.item_id in HEAVY_ITEM_IDS:
            pickup_range = max(pickup_range, item.world_rect().width / 2 + fighter.hitbox_size[0] / 2)
        return pickup_range

    def _npc_item_input(
        self,
        fighter: Fighter,
        target: Fighter | None,
        inputs: FighterInput,
    ) -> FighterInput:
        if not fighter.controls_enabled or fighter.state not in {"idle", "walk", "run"} or fighter.z != 0:
            return inputs

        if fighter.held_item is not None:
            item_animations = self.item_sprite_animations.get(fighter.held_item, {})
            if "drink" in item_animations and fighter.health < fighter.max_health:
                return FighterInput(drink_just_pressed=True)
            if (
                target is not None
                and _is_throwable_item(fighter.held_item)
                and abs(fighter.x - target.x) <= 360.0
                and abs(fighter.lane_y - target.lane_y) <= 48.0
            ):
                return FighterInput(
                    attack_pressed=True,
                    attack_just_pressed=True,
                    block_pressed=True,
                    block_just_pressed=True,
                )
            return inputs

        nearby_items = [
            item
            for item in self.consumable_items
            if item.pickupable
            and abs(fighter.x - item.x) <= 300.0
            and abs(fighter.lane_y - item.lane_y) <= 112.0
        ]
        if not nearby_items:
            return inputs

        item = min(
            nearby_items,
            key=lambda candidate: (fighter.x - candidate.x) ** 2 + (fighter.lane_y - candidate.lane_y) ** 2,
        )
        dx = item.x - fighter.x
        dy = item.lane_y - fighter.lane_y
        if abs(dx) <= self._item_pickup_range(fighter, item) and abs(dy) <= 24.0:
            return FighterInput(attack_just_pressed=True) if fighter.state == "idle" else FighterInput()

        return FighterInput(
            left=dx < -8.0,
            right=dx > 8.0,
            up=dy < -12.0,
            down=dy > 12.0,
            run=True,
        )

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

    def _start_whiskey_effect(self, fighter: Fighter) -> None:
        self.whiskey_status_effects[fighter] = {
            "remaining": 3.0,
            "sleeping": False,
            "just_started": True,
            "bubbles": ItemSpriteAnimation(self.drunk_bubbles_frames, loop=True),
            "sleep": ItemSpriteAnimation(self.sleep_frames, loop=True),
        }

    def _update_whiskey_effects(self, dt: float) -> None:
        for fighter, effect in tuple(self.whiskey_status_effects.items()):
            if effect["just_started"]:
                effect["just_started"] = False
                continue
            if effect["sleeping"]:
                if fighter.state == "idle" or fighter.is_dead:
                    fighter.whiskey_sleep_hold = False
                    del self.whiskey_status_effects[fighter]
                    continue
                effect["sleep"].update(dt)
                if fighter.knock_hold_timer == 0.0:
                    fighter.whiskey_sleep_hold = False
                    if fighter.state != "fall":
                        del self.whiskey_status_effects[fighter]
                continue

            effect["bubbles"].update(dt)
            effect["remaining"] = max(0.0, effect["remaining"] - dt)
            if effect["remaining"] == 0.0:
                effect["sleeping"] = True
                effect["bubbles"].frame_index = len(effect["bubbles"].frames) - 1
                effect["bubbles"].frame_timer = 0.0
                if not fighter.is_dead:
                    fighter._start_knockdown()
                    fighter.knock_hold_timer *= 2.0
                    fighter.whiskey_sleep_hold = True

    def _draw_whiskey_status(self, surface: pygame.Surface, fighter: Fighter, camera_x: float) -> None:
        effect = self.whiskey_status_effects.get(fighter)
        if effect is None:
            return
        animation = effect["sleep"] if effect["sleeping"] else effect["bubbles"]
        frame = animation.current_frame
        _, draw_y = fighter.draw_pos(camera_x)
        sprite = fighter.animation_player.current_frame
        surface.blit(
            frame,
            frame.get_rect(
                center=(
                    int(fighter.x - camera_x),
                    int(draw_y + sprite.get_height() * 0.28),
                )
            ),
        )

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

            if item.item_id == "consumables/whiskey":
                self._break_whiskey_item(item, spawn_fire=False)
                previous_health = target.health
                self._deal_damage(item.owner, target, 1)
                if not target.is_dead:
                    target._start_fire_knockdown()
                if target.health < previous_health:
                    self.audio.play("hit_success")
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
                self._deal_damage(item.owner, target, 1)
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

    @staticmethod
    def _weapon_anchor_pose(fighter: Fighter) -> str | None:
        if fighter.item_throw_animation is not None:
            return (
                "weapon_jump_throw"
                if fighter.item_throw_animation == "jump_throw"
                else "weapon_ground_throw"
            )
        animation_name = fighter.animation_player.current_name
        if animation_name.startswith("weapon_basic_attack_"):
            return "weapon_basic_attack"
        return WEAPON_ANCHOR_POSES.get(animation_name)

    def _character_hand_anchor(self, fighter: Fighter, fallback_to_idle: bool = True) -> HandAnchor | None:
        animation_name = fighter.animation_player.current_name
        if fighter.held_item and fighter.held_item.startswith("weapons/"):
            weapon_name = fighter.held_item.partition("/")[2]
            anchor_animation_name = self._weapon_anchor_pose(fighter)
            source_names = dict.fromkeys((weapon_name, self.weapon_anchor_reference))
            frame_index = fighter.animation_player.frame_index
            for source_name in source_names:
                weapon_anchors = self.weapon_hand_anchors.get(source_name, {}).get(fighter.name, {})
                if anchor_animation_name is not None:
                    pose_anchors = weapon_anchors.get(anchor_animation_name, [])
                    if frame_index < len(pose_anchors) and pose_anchors[frame_index] is not None:
                        return pose_anchors[frame_index]
                if fallback_to_idle:
                    idle_anchors = weapon_anchors.get("weapon_idle", [])
                    if anchor_animation_name != "weapon_idle" and frame_index < len(idle_anchors):
                        if idle_anchors[frame_index] is not None:
                            return idle_anchors[frame_index]
                    fallback_anchor = next((point for point in idle_anchors if point is not None), None)
                    if fallback_anchor is not None:
                        return fallback_anchor
            if not fallback_to_idle:
                return None

        character_anchors = self.item_hand_anchors.get(fighter.name)
        if character_anchors is None:
            return None

        is_heavy_item = fighter.held_item in HEAVY_ITEM_IDS
        anchor_animation_name = (
            HEAVY_ITEM_ANCHOR_KEYS.get(animation_name) if is_heavy_item else animation_name
        )
        frame_index = fighter.animation_player.frame_index
        if anchor_animation_name is not None:
            animation_anchors = character_anchors.get(anchor_animation_name, [])
            if frame_index < len(animation_anchors) and animation_anchors[frame_index] is not None:
                return animation_anchors[frame_index]

        if not fallback_to_idle:
            return None
        idle_anchors = character_anchors.get("idle", [])
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

    def _draw_dark_bat_weapon_phase(
        self,
        surface: pygame.Surface,
        fighter: Fighter,
        camera_x: float,
    ) -> None:
        if fighter.name != "dark_bat" or fighter.state != "basic_attack":
            return
        weapon_overlay = fighter.dark_bat_weapon_overlay
        if weapon_overlay is None:
            raise RuntimeError("Dark Bat weapon overlay is not loaded.")

        fade_duration = 0.06
        elapsed = max(0.0, fighter.combat["attack_duration"] - fighter.attack_timer)
        fade_ratio = min(1.0, elapsed / fade_duration, fighter.attack_timer / fade_duration)
        if fade_ratio <= 0.0:
            return

        frame = weapon_overlay if fighter.facing > 0 else pygame.transform.flip(weapon_overlay, True, False)
        frame = frame.copy()
        frame.set_alpha(round(255 * fade_ratio))
        draw_x, draw_y = fighter.draw_pos(camera_x)
        surface.blit(frame, (draw_x, draw_y))

    def _draw_held_item(self, surface: pygame.Surface, fighter: Fighter, camera_x: float) -> None:
        if fighter.held_item is None:
            return
        frame = self._weapon_pose_frame(fighter)
        if frame is None:
            frames = self.item_sprite_animations.get(fighter.held_item, {}).get("holding")
            if not frames:
                return
            held_animation = self.held_item_animations.get(fighter)
            if held_animation is None or held_animation[0] != fighter.held_item:
                animation = ItemSpriteAnimation(frames, loop=True)
                self.held_item_animations[fighter] = (fighter.held_item, animation)
            else:
                _, animation = held_animation
            frame = animation.current_frame
        self._draw_item_sprite(
            surface,
            fighter,
            frame,
            camera_x,
            fallback_anchor=(
                HEAVY_ITEM_FALLBACK_ANCHOR
                if fighter.held_item in HEAVY_ITEM_IDS
                else (0.30, 0.62)
            ),
        )

    def _weapon_pose_frame(self, fighter: Fighter) -> pygame.Surface | None:
        if not fighter.held_item or not fighter.held_item.startswith("weapons/"):
            return None
        pose = self._weapon_anchor_pose(fighter)
        if pose is None or pose == "weapon_idle":
            return None
        references = self.weapon_reference_sprites.get(self.weapon_anchor_reference, {})
        character_references = references.get(fighter.name, {})
        pose_references = character_references.get(pose, [])
        frame_index = fighter.animation_player.frame_index
        if frame_index >= len(pose_references):
            return None
        reference_sprite = pose_references[frame_index]
        if reference_sprite is None:
            return None
        frame_name = Path(reference_sprite).stem.casefold()
        weapon_frames = (
            self.weapon_throw_frames
            if pose in {"weapon_ground_throw", "weapon_jump_throw"}
            else self.weapon_swing_frames
        )
        return weapon_frames.get(fighter.held_item, {}).get(frame_name)

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
        columns = [
            projectile
            for projectile in self.projectiles
            if isinstance(projectile, FreezeColumnEffect)
            and not projectile.finished
            and projectile.blocks_movement
        ]
        for fighter in self._fighters():
            if fighter.is_dead:
                continue
            previous_x = previous_x_by_fighter.get(id(fighter), fighter.x)
            half_width = fighter.hitbox_size[0] / 2
            for column in columns:
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

    def _spawn_ice_fragment(
        self,
        name: str,
        x: float,
        y: float,
        velocity_x: float,
        velocity_y: float,
    ) -> None:
        self.consumable_break_effects.append(
            IceFragmentEffect(
                self.ice_fragment_frames[name],
                x,
                y,
                velocity_x,
                velocity_y,
            )
        )

    def _spawn_freeze_column_fragments(self, column: FreezeColumnEffect) -> None:
        column_rect = column.rect()
        x = float(column_rect.centerx)
        y = float(column_rect.centery)
        if column.break_cause == "damage":
            direction = column.break_direction
            fragments = (
                ("large_1", direction * 300.0, -230.0),
                ("large_2", direction * 400.0, -180.0),
                ("medium_1", direction * 140.0, -420.0),
                ("small_1", direction * 260.0, -160.0),
                ("small_1", direction * 360.0, -270.0),
            )
        else:
            fragments = (
                ("large_1", -300.0, -220.0),
                ("large_2", 300.0, -220.0),
                ("medium_1", 0.0, -420.0),
                ("small_1", -260.0, -160.0),
                ("small_1", 260.0, -160.0),
            )
        for name, velocity_x, velocity_y in fragments:
            self._spawn_ice_fragment(name, x, y, velocity_x, velocity_y)

    def _spawn_character_freeze_break_fragments(self, fighter: Fighter) -> None:
        if not fighter.ice_break_fragments_pending:
            return
        fighter.ice_break_fragments_pending = False
        large_name = ("large_1", "large_2")[self.ice_fragment_large_toggle]
        self.ice_fragment_large_toggle = 1 - self.ice_fragment_large_toggle
        fighter_rect = fighter.world_hitbox_rect()
        x = float(fighter_rect.centerx)
        y = float(fighter_rect.centery)
        self._spawn_ice_fragment(large_name, x, y, fighter.facing * 180.0, -340.0)
        self._spawn_ice_fragment("small_1", x, y, -250.0, -180.0)
        self._spawn_ice_fragment("small_1", x, y, 250.0, -180.0)

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
            attack_rect = self._melee_attack_rect(attacker)
            for column in columns:
                if column.finished:
                    continue
                if abs(attacker.lane_y - column.lane_y) <= 36 and attack_rect.colliderect(column.rect()):
                    column.break_apart(attacker.facing)

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
            if attacker.name == "dark_bat" and attacker.state == "jump_throw" and attacker.jump_attack_active:
                attack_range = 96
            attack_rect = self._melee_attack_rect(attacker, attack_range)
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
                elif attacker.name != "armored_bandit":
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
            self._deal_damage(attacker, defender, attacker.touch_damage)
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
            self._deal_damage(attacker, defender, attacker.touch_damage)
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
                self._deal_damage(fighter, target, fighter.touch_damage)
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
                self._deal_damage(fighter, target, fighter.touch_damage)
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
            while fighter.firzen_sounds_pending:
                self.audio.play(fighter.firzen_sounds_pending.pop(0))
            if fighter.armored_bandit_attack_sfx_pending is not None:
                self.audio.play(fighter.armored_bandit_attack_sfx_pending)
                fighter.armored_bandit_attack_sfx_pending = None
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
        if fighter.name == "henry" and fighter.state == "sp_move_attack_1":
            if not fighter.henry_sp_move_attack_1_projectile_pending:
                return
            fighter.henry_sp_move_attack_1_projectile_pending = False

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

    def _spawn_reece_buzz_ball(self, fighter: Fighter) -> None:
        if fighter.name != "reece" or fighter.state != "sp_move_attack_1" or not fighter.reece_buzz_ball_pending:
            return
        fighter.reece_buzz_ball_pending = False
        fighter.attack_projectile_fired = True
        reference_frame = fighter.animations["sp_move_attack_1"]["surfaces"][7]
        anchor_x, anchor_y = REECE_SP_MOVE_ATTACK_1_CHEST_ANCHOR
        origin_x = fighter.x + fighter.facing * (
            reference_frame.get_width() * anchor_x
            - reference_frame.get_width() / 2
            + self.buzz_ball_throw_frames[0].get_width() / 2
        )
        origin_y = (
            GROUND_Y
            + fighter.lane_y
            - fighter.z
            - reference_frame.get_height()
            + reference_frame.get_height() * anchor_y
        )
        self.projectiles.append(
            BuzzBallProjectile(
                fighter,
                origin_x,
                fighter.lane_y,
                fighter.facing,
                self.buzz_ball_throw_frames,
                origin_y=origin_y,
            )
        )

    def _spawn_reece_biggie_ball(self, fighter: Fighter) -> None:
        if (
            fighter.name != "reece"
            or fighter.state != "sp_vert_attack_2"
            or not fighter.reece_biggie_ball_pending
        ):
            return
        fighter.reece_biggie_ball_pending = False
        fighter.attack_projectile_fired = True
        drop_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 1.1)
        self.projectiles.append(
            BiggieBallProjectile(
                fighter,
                drop_x,
                fighter.lane_y,
                self.biggie_ball_drop_frames,
            )
        )

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
            self.audio.play("julian_ball_explode")
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

    def _spawn_ashley_blast(self, fighter: Fighter) -> None:
        if fighter.name != "ashley" or fighter.state != "sp_move_attack_1" or not fighter.ashley_blast_pending:
            return
        fighter.ashley_blast_pending = False
        fighter.attack_projectile_fired = True
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.48)
        origin_y = fighter.world_hitbox_rect().centery
        self.projectiles.append(
            AshleyBlastProjectile(fighter, origin_x, origin_y, fighter.facing)
        )
        self.projectiles.append(
            AshleySpriteEffect(
                "particals/blue_sparkles",
                origin_x,
                origin_y,
                facing=fighter.facing,
            )
        )
        self.projectiles.append(
            AshleySpriteEffect(
                "shared_sprites/ashley_blast/create",
                origin_x,
                origin_y,
                facing=fighter.facing,
            )
        )
        self.audio.play("julian_ball_create")

    def _spawn_ashley_missiles(self, fighter: Fighter) -> None:
        if fighter.name != "ashley" or fighter.state != "sp_move_attack_2" or not fighter.ashley_missiles_pending:
            return
        fighter.ashley_missiles_pending = False
        fighter.attack_projectile_fired = True
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.48)
        origin_y = fighter.world_hitbox_rect().centery
        targets = sorted(
            (
                target
                for target in self._opponents_of(fighter)
                if not target.is_dead
                and (target.world_hitbox_rect().centerx - fighter.x) * fighter.facing >= 0.0
            ),
            key=lambda target: (target.lane_y, abs(target.x - fighter.x)),
        )
        targets_by_lane: dict[float, list[Fighter]] = {}
        for target in targets:
            targets_by_lane.setdefault(float(target.lane_y), []).append(target)
        lane_order = sorted(targets_by_lane, key=lambda lane: abs(lane - fighter.lane_y))
        targets = []
        while any(targets_by_lane.values()):
            for lane in lane_order:
                if targets_by_lane[lane]:
                    targets.append(targets_by_lane[lane].pop(0))
        fallback_lanes = tuple(sorted({LANE_MIN_Y, fighter.lane_y, LANE_MAX_Y}))
        for missile_index in range(3):
            target = targets[missile_index % len(targets)] if targets else None
            ground_target_x = None
            if target is not None:
                target_lane_y = target.lane_y
            else:
                target_lane_y = random.choice(fallback_lanes)
                distance = random.uniform(360.0, 480.0)
                ground_target_x = origin_x + fighter.facing * distance
            self.projectiles.append(
                AshleyMissileProjectile(
                    fighter,
                    target,
                    origin_x,
                    origin_y,
                    fighter.facing,
                    target_lane_y,
                    missile_index,
                    ground_target_x,
                )
            )

    def _spawn_ashley_barrier(self, fighter: Fighter) -> None:
        if fighter.name != "ashley":
            return
        if fighter.state == "sp_vert_attack_1" and fighter.ashley_barrier_pending:
            fighter.ashley_barrier_pending = False
            fighter.attack_projectile_fired = True
            origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.58)
            origin_y = fighter.world_hitbox_rect().centery
            self.projectiles.append(
                AshleyMagicalBarrierEffect(fighter, origin_x, origin_y, fighter.facing)
            )
        if fighter.state == "sp_vert_attack_1" and fighter.ashley_barrier_start_pending:
            fighter.ashley_barrier_start_pending = False
            barrier = next(
                (
                    projectile
                    for projectile in reversed(self.projectiles)
                    if isinstance(projectile, AshleyMagicalBarrierEffect)
                    and projectile.owner is fighter
                    and projectile.phase != "burst"
                ),
                None,
            )
            if barrier is not None:
                barrier.start_moving()

    def _spawn_ashley_mana_orb(self, fighter: Fighter) -> None:
        if fighter.name != "ashley" or fighter.state != "sp_vert_attack_2" or not fighter.ashley_mana_orb_pending:
            return
        fighter.ashley_mana_orb_pending = False
        fighter.attack_projectile_fired = True
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.72)
        origin_y = fighter.world_hitbox_rect().centery
        self.projectiles.append(AshleyManaOrbProjectile(fighter, origin_x, origin_y, fighter.facing))
        self.audio.play("john_heal_orb")

    def _spawn_ashley_attack_sparkles(self, fighter: Fighter) -> None:
        if fighter.name != "ashley" or not fighter.ashley_sparkles_pending:
            return
        fighter.ashley_sparkles_pending = False
        self.projectiles.append(
            AshleySpriteEffect(
                "particals/blue_sparkles",
                fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.6),
                fighter.world_hitbox_rect().centery,
                facing=fighter.facing,
                frame_prefix=random.choice(("1_", "2_")),
                foreground=True,
            )
        )

    def _spawn_john_barrier(self, fighter: Fighter) -> None:
        is_john_barrier = fighter.name == "john" and fighter.john_barrier_pending
        is_reece_barrier = fighter.name == "reece" and fighter.reece_vape_barrier_pending
        if fighter.state != "sp_move_attack_2" or not (is_john_barrier or is_reece_barrier):
            return
        if is_john_barrier:
            fighter.john_barrier_pending = False
        else:
            fighter.reece_vape_barrier_pending = False
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.68)
        origin_y = fighter.world_hitbox_rect().centery
        asset_folder = "vape_barrier" if is_reece_barrier else "john_magical_barrier"
        self.projectiles.append(
            JohnBarrierEffect(fighter, origin_x, origin_y, fighter.facing, asset_folder=asset_folder)
        )
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
        fighter.health = min(fighter.max_health, fighter.health + 3)
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
        for item in self.consumable_items:
            if item.phase == "breaking":
                continue
            if abs(item.x - fighter.x) > 240.0 or abs(item.lane_y - fighter.lane_y) > 52.0:
                continue
            item.start_henry_float()

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

    def _apply_firzen_target_orb_hit(
        self,
        projectile: FirzenTargetOrbProjectile,
        target: Fighter,
    ) -> None:
        if id(target) in projectile.hit_targets:
            return
        projectile.hit_targets.add(id(target))
        if target.state == "block" and target.block_strength > 0:
            target.block_strength = 0
            target.block_hold_timer = 0.0
            self.audio.play("hit_guard")
        elif target.state == "block":
            target._start_block_break()
            self.audio.play("hit_guard")
        else:
            self._deal_damage(projectile.owner, target, projectile.damage)
            if not target.is_dead:
                target._start_ice_knockdown(push_back=False)
                self.audio.play("freeze")

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

    def _spawn_reece_fire_breath(self, fighter: Fighter) -> None:
        if fighter.name != "reece":
            return
        while fighter.reece_fire_breath_projectiles_pending > 0:
            fighter.reece_fire_breath_projectiles_pending -= 1
            origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.40)
            hitbox = fighter.world_hitbox_rect()
            lane_spacing = (LANE_MAX_Y - LANE_MIN_Y) / 3.0
            lane_offset = lane_spacing / 6.0
            adjacent_lane = max(LANE_MIN_Y, fighter.lane_y - lane_offset)
            if adjacent_lane == fighter.lane_y:
                adjacent_lane = min(LANE_MAX_Y, fighter.lane_y + lane_offset)
            for lane_y in (fighter.lane_y, adjacent_lane):
                origin_y = hitbox.centery + lane_y - fighter.lane_y
                self.projectiles.append(
                    FireBreathProjectile(fighter, origin_x, origin_y, fighter.facing, lane_y=lane_y)
                )
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
            self._deal_damage(fighter, target, fighter.touch_damage)
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
        self._deal_damage(fighter, target, fighter.touch_damage)
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
            self.audio.play_fire_breath()

    def _spawn_firen_explosion(self, fighter: Fighter) -> None:
        if fighter.name != "firen":
            return
        while fighter.firen_fire_explosion_pending > 0:
            fighter.firen_fire_explosion_pending -= 1
            hitbox = fighter.world_hitbox_rect()
            origin_x = float(hitbox.centerx)
            origin_y = float(hitbox.centery)
            self.projectiles.append(FireExplosionEffect(fighter, origin_x, origin_y))
            self.audio.play("fire_explode")

    def _reflect_projectile(
        self,
        projectile: object,
        barrier: JohnBarrierEffect | AshleyMagicalBarrierEffect,
    ) -> bool:
        phase = getattr(projectile, "phase", None)
        if (
            not getattr(projectile, "can_damage", False)
            or phase not in (None, "fly", "play")
            or (phase is None and not hasattr(projectile, "speed_x"))
            or not all(hasattr(projectile, attribute) for attribute in ("owner", "x", "y", "facing"))
        ):
            return False

        original_owner = projectile.owner
        reflected_facing = (
            -projectile.facing
            if isinstance(barrier, AshleyMagicalBarrierEffect)
            else barrier.facing
        )
        projectile.owner = barrier.owner
        projectile.facing = reflected_facing
        projectile.x = barrier.x + reflected_facing * (
            barrier.rect().width / 2 + projectile.rect().width / 2 + 2
        )
        if hasattr(projectile, "origin_x"):
            projectile.origin_x = projectile.x
        if hasattr(projectile, "distance_travelled"):
            projectile.distance_travelled = 0.0
        if hasattr(projectile, "target"):
            target = (
                original_owner
                if isinstance(barrier, AshleyMagicalBarrierEffect)
                and isinstance(original_owner, Fighter)
                and original_owner is not barrier.owner
                and not original_owner.is_dead
                and original_owner in self._opponents_of(barrier.owner)
                else self._target_for(barrier.owner)
            )
            projectile.target = target if target is not None and not target.is_dead else None
            if projectile.target is not None and hasattr(projectile, "target_lane_y"):
                projectile.target_lane_y = float(projectile.target.lane_y)
        if hasattr(projectile, "hit_targets"):
            projectile.hit_targets.clear()
        return True

    def _shoot_firzen_target_orbs(self, projectile: object) -> None:
        if (
            not getattr(projectile, "can_damage", False)
            or getattr(projectile, "phase", None) not in {"fly", "play"}
        ):
            return
        owner = getattr(projectile, "owner", None)
        rect_method = getattr(projectile, "rect", None)
        if owner is None or not callable(rect_method):
            return
        projectile_rect = rect_method()
        for orb in self.projectiles:
            if (
                not isinstance(orb, FirzenTargetOrbProjectile)
                or orb.phase != "fly"
                or orb.owner is owner
                or not projectile_rect.colliderect(orb.rect())
            ):
                continue
            orb._start_burst()
            self.audio.play("firzen_fire_ice_orb_shoot")
            break

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
            if isinstance(projectile, AshleySpriteEffect):
                if projectile.finished:
                    self.projectiles.remove(projectile)
                continue
            if isinstance(projectile, AshleyManaOrbProjectile):
                for target in self._fighters():
                    if (
                        target.is_dead
                        or abs(target.lane_y - projectile.lane_y) > 24.0
                        or not projectile.contact_rect().colliderect(target.world_hitbox_rect())
                    ):
                        continue
                    target.grant_mana_regen_boost(3.0)
                    projectile.finished = True
                    self.audio.play("john_heal_orb_heal")
                    break
                if projectile.finished:
                    self.projectiles.remove(projectile)
                continue
            if isinstance(projectile, BuzzBallProjectile):
                if projectile.phase == "fly":
                    target = next(
                        (
                            target
                            for target in self._opponents_of(projectile.owner)
                            if target is not None
                            and not target.is_dead
                            and abs(target.lane_y - projectile.lane_y) <= 28.0
                            and (
                                target.world_hitbox_rect().centerx - projectile.start_x
                            ) * projectile.facing >= 0
                            and projectile.rect().colliderect(target.world_hitbox_rect())
                        ),
                        None,
                    )
                    if target is not None:
                        self._break_buzz_ball(projectile)
                        if target.state == "block" and target.block_strength > 0:
                            target.block_strength = 0
                            target.block_hold_timer = 0.0
                            self.audio.play("hit_guard")
                        elif target.state == "block":
                            target._start_block_break()
                            self.audio.play("hit_guard")
                        else:
                            previous_health = target.health
                            self._deal_damage(projectile.owner, target, projectile.damage)
                            if not target.is_dead:
                                target._start_knockdown()
                            if target.health < previous_health:
                                self.audio.play("hit_success")
                        self.projectiles.remove(projectile)
                        continue
                if projectile.just_ground_hit:
                    projectile.just_ground_hit = False
                    self._break_buzz_ball(projectile)
                    self.projectiles.remove(projectile)
                elif projectile.finished:
                    self.projectiles.remove(projectile)
                continue
            if isinstance(projectile, BiggieBallProjectile):
                if projectile.just_ground_hit:
                    projectile.just_ground_hit = False
                    self._break_biggie_ball(projectile)
                    for target in self._opponents_of(projectile.owner):
                        if target is None or target.is_dead:
                            continue
                        dx = target.world_hitbox_rect().centerx - projectile.x
                        lane_delta = target.lane_y - projectile.lane_y
                        if (
                            abs(lane_delta) > 36.0
                            or dx * dx + lane_delta * lane_delta > BIGGIE_BALL_BLAST_RADIUS**2
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
                            previous_health = target.health
                            self._deal_damage(projectile.owner, target, projectile.DAMAGE)
                            if not target.is_dead:
                                target._start_knockdown()
                            if target.health < previous_health:
                                self.audio.play("hit_success")
                    self.projectiles.remove(projectile)
                elif projectile.finished:
                    self.projectiles.remove(projectile)
                continue
            self._shoot_firzen_target_orbs(projectile)
            self._damage_heavy_box_with_projectile(projectile)
            if isinstance(projectile, FirzenFireIceOrb) and projectile.just_split:
                projectile.just_split = False
                self.audio.play("firzen_fire_ice_orb_burst")
                self._spawn_firzen_ground_orbs(projectile)
            if isinstance(projectile, FirzenTargetOrbProjectile) and projectile.just_hit_ground:
                projectile.just_hit_ground = False
                impact_rect = projectile.rect()
                for target in self._opponents_of(projectile.owner):
                    if (
                        target is None
                        or target.is_dead
                        or abs(target.lane_y - projectile.target_lane_y) > 36.0
                        or not impact_rect.colliderect(target.world_hitbox_rect())
                    ):
                        continue
                    self._apply_firzen_target_orb_hit(projectile, target)
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
                            blocks_movement=False,
                        )
                    )
                else:
                    fire_trail = FireTrailEffect(
                        projectile.owner,
                        projectile.target_x,
                        ground_y - 22.0,
                    )
                    fire_trail.hit_targets.update(projectile.hit_targets)
                    self.projectiles.append(fire_trail)
                    self.audio.play_fire_breath()
            if isinstance(projectile, AxleShotProjectile) and projectile.just_axle_shot_hit:
                self.audio.play("axle_shot_hit")
                projectile.just_axle_shot_hit = False
            if isinstance(projectile, JulianSkullProjectile) and projectile.just_burst_sound:
                self.audio.play("summon_bats_died")
                projectile.just_burst_sound = False
            if getattr(projectile, "just_ground_hit", False):
                if isinstance(projectile, AshleyMissileProjectile):
                    self.projectiles.append(
                        AshleySpriteEffect(
                            "shared_sprites/ashley_fire",
                            projectile.x,
                            GROUND_Y + projectile.target_lane_y,
                            facing=projectile.facing,
                            scale=1.5,
                            ground_anchored=True,
                        )
                    )
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
            if isinstance(projectile, AshleyMagicalBarrierEffect):
                if projectile.phase == "barrier" and projectile.movement_enabled:
                    if projectile.x <= visible_left or projectile.x >= visible_right:
                        projectile.x = max(visible_left, min(visible_right, projectile.x))
                        projectile._start_burst()
                    else:
                        heavy_object = next(
                            (
                                item
                                for item in self.consumable_items
                                if item.item_id in HEAVY_ITEM_IDS
                                and abs(item.lane_y - projectile.lane_y) <= 24.0
                                and projectile.rect().colliderect(item.world_rect())
                            ),
                            None,
                        )
                        if heavy_object is not None:
                            self._break_heavy_box(heavy_object)
                            projectile.take_damage()
                        else:
                            for target in self._opponents_of(projectile.owner):
                                if (
                                    target.is_dead
                                    or abs(target.lane_y - projectile.lane_y) > 18.0
                                    or not projectile.rect().colliderect(target.world_hitbox_rect())
                                    or not projectile.hit_enemy(target)
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
                                    self._deal_damage(projectile.owner, target, 1)
                                    if not target.is_dead:
                                        target._start_knockdown()
                                break
                if projectile.finished:
                    self.projectiles.remove(projectile)
                continue
            if isinstance(projectile, AshleyBlastProjectile) and projectile.just_burst:
                self.audio.play("john_blast_hit")
                projectile.just_burst = False
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
                        target.health = min(target.max_health, target.health + 3)
                        projectile._start_burst()
                        projectile.just_heal_sound = False
                        self.audio.play("john_heal_orb_heal")
                        break
                if projectile.finished:
                    self.projectiles.remove(projectile)
                continue
            if getattr(projectile, "just_expired", False):
                if isinstance(projectile, FreezeColumnEffect):
                    self._spawn_freeze_column_fragments(projectile)
                self.audio.play("freeze_break")
                projectile.just_expired = False
            if getattr(projectile, "just_broke", False):
                if not (isinstance(projectile, ArrowProjectile) and projectile.style == "rudolf"):
                    self.audio.play("broken_arrow")
                projectile.just_broke = False
            if getattr(projectile, "just_burst", False):
                if isinstance(projectile, AshleyBlastProjectile):
                    self.audio.play("john_blast_hit")
                elif isinstance(projectile, FireballProjectile):
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
            if isinstance(projectile, FirzenTargetOrbProjectile):
                if projectile.phase == "fly":
                    for target in self._opponents_of(projectile.owner):
                        if (
                            target is None
                            or target.is_dead
                            or abs(target.lane_y - projectile.target_lane_y) > 36.0
                            or abs(projectile.y - target.world_hitbox_rect().centery) > 42.0
                            or not projectile.rect().colliderect(target.world_hitbox_rect())
                        ):
                            continue
                        self._apply_firzen_target_orb_hit(projectile, target)
                        projectile._start_burst()
                        break
                continue
            if isinstance(projectile, FirzenFireIceOrb):
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
            if isinstance(projectile, AshleyBlastProjectile) and projectile.phase == "fly":
                if projectile.x <= visible_left or projectile.x >= visible_right:
                    projectile.x = max(visible_left, min(visible_right, projectile.x))
                    projectile._start_burst()
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
                                isinstance(barrier, (JohnBarrierEffect, AshleyMagicalBarrierEffect))
                                and barrier.can_reflect
                                and projectile_rect.colliderect(barrier.rect())
                                and self._reflect_projectile(projectile, barrier)
                            ):
                                if isinstance(barrier, AshleyMagicalBarrierEffect):
                                    barrier.take_damage()
                                else:
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
                            outward_direction = getattr(projectile, "facing", None)
                            if outward_direction not in (-1, 1):
                                outward_direction = 1 if projectile_rect.centerx <= column.x else -1
                            if isinstance(projectile, JulianBallProjectile) and projectile.register_hit(column):
                                if projectile.hit_count >= 2:
                                    projectile._start_burst()
                                    self.audio.play("julian_ball_explode")
                                    column.break_apart(outward_direction)
                                    break
                            column.break_apart(outward_direction)
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
                    target.health = min(target.max_health, target.health + 1)
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
                        self._deal_damage(projectile.owner, target, projectile.damage)
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
                        self._deal_damage(projectile.owner, target, projectile.damage)
                        if not target.is_dead:
                            target._start_knockdown()
                        self.audio.play("arrow_hit")
                    projectile._start_burst()
                continue
            if isinstance(projectile, AshleyBlastProjectile):
                if projectile.phase == "fly" and projectile.can_damage:
                    for target in self._opponents_of(projectile.owner):
                        target_rect = target.world_hitbox_rect()
                        if (
                            target.is_dead
                            or abs(target.lane_y - projectile.lane_y) > 36.0
                            or abs(projectile.y - target_rect.centery) > 42.0
                            or (target_rect.centerx - projectile.origin_x) * projectile.facing < 0.0
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
                            self._deal_damage(projectile.owner, target, projectile.damage)
                            if not target.is_dead:
                                target._start_knockdown()
                        projectile._start_burst()
                        break
                if projectile.just_burst:
                    self.audio.play("john_blast_hit")
                    projectile.just_burst = False
                if projectile.finished:
                    self.projectiles.remove(projectile)
                continue
            if isinstance(projectile, AshleyMissileProjectile):
                if projectile.phase == "fly" and projectile.can_damage:
                    for target in self._opponents_of(projectile.owner):
                        target_rect = target.world_hitbox_rect()
                        if (
                            target.is_dead
                            or abs(target.lane_y - projectile.target_lane_y) > 36.0
                            or abs(projectile.y - target_rect.centery) > 42.0
                            or (target_rect.centerx - projectile.origin_x) * projectile.facing < 0.0
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
                            self._deal_damage(projectile.owner, target, projectile.damage)
                            if not target.is_dead:
                                target._start_fire_knockdown()
                        projectile._start_burst()
                        break
                if projectile.finished:
                    self.projectiles.remove(projectile)
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
                            self._deal_damage(projectile.owner, target, projectile.damage)
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
                        self._deal_damage(projectile.owner, target, projectile.damage)
                        if not target.is_dead:
                            if projectile.launch:
                                target._start_launch_knockdown()
                            else:
                                target._start_knockdown()
                continue

            targets = (
                self._fighters()
                if getattr(projectile, "hits_all_fighters", False)
                else self._opponents_of(projectile.owner)
            )
            for target in targets:
                if (
                    target is None
                    or (target is projectile.owner and not getattr(projectile, "hits_all_fighters", False))
                    or target.is_dead
                ):
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
                        self._deal_damage(projectile.owner, target, projectile.damage)
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
                        self._deal_damage(projectile.owner, target, projectile.damage)
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
                        self._deal_damage(projectile.owner, target, projectile.damage)
                        if not target.is_dead:
                            target._start_fire_knockdown(push_back=False)
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
                        self._deal_damage(projectile.owner, target, projectile.damage)
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
                    if isinstance(projectile, WhiskeyFireTrailEffect):
                        self._deal_damage(
                            projectile.owner,
                            target,
                            projectile.damage,
                            ignore_invulnerability=knocked_and_vulnerable,
                            apply_whiskey_multiplier=False,
                        )
                    elif knocked_and_vulnerable:
                        self._deal_damage(projectile.owner, target, projectile.damage, ignore_invulnerability=True)
                    else:
                        self._deal_damage(projectile.owner, target, projectile.damage)
                    if not target.is_dead:
                        if projectile.owner.name == "firzen" and not isinstance(projectile, WhiskeyFireTrailEffect):
                            target._start_ice_knockdown(push_back=False)
                            self.audio.play("freeze")
                        else:
                            target._start_fire_knockdown()
                            self.audio.play_fire_breath()
                    continue
                if isinstance(projectile, FireBreathProjectile):
                    if abs(target.lane_y - projectile.lane_y) > 10:
                        continue
                    if projectile.facing > 0 and target.world_hitbox_rect().centerx < projectile.x:
                        continue
                    if projectile.facing < 0 and target.world_hitbox_rect().centerx > projectile.x:
                        continue
                    if abs(target.world_hitbox_rect().centery - projectile.y) > 24:
                        continue
                    if not projectile.rect().colliderect(target.world_hitbox_rect()):
                        continue
                    self._deal_damage(projectile.owner, target, projectile.damage, ignore_invulnerability=True)
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
                if isinstance(projectile, JulianSkullProjectile) and abs(target.lane_y - projectile.lane_y) > 36:
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
                        self._deal_damage(projectile.owner, target, projectile.damage, ignore_invulnerability=True)
                    else:
                        self._deal_damage(projectile.owner, target, projectile.damage)
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
            mode_label = self.small_font.render(
                "TEST MODE  |  XP / LEVEL PREVIEW",
                True,
                TEXT_COLOR,
            )
            surface.blit(mode_label, mode_label.get_rect(midtop=(SCREEN_WIDTH // 2, 24)))
        elif self.stage_mode:
            progress_text, encounter_title, countdown_text = self._stage_run_hud_labels()
            progress = self.small_font.render(progress_text, True, TEXT_COLOR)
            surface.blit(progress, progress.get_rect(midtop=(SCREEN_WIDTH // 2, 18)))
            encounter_title = self.stage_banner_subtitle_font.render(
                encounter_title,
                True,
                (200, 211, 224),
            )
            surface.blit(
                encounter_title,
                encounter_title.get_rect(midtop=(SCREEN_WIDTH // 2, 49)),
            )
            if countdown_text is not None:
                countdown = self.small_font.render(countdown_text, True, (255, 214, 139))
                surface.blit(
                    countdown,
                    countdown.get_rect(midtop=(SCREEN_WIDTH // 2, 68)),
                )
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

    def _stage_run_hud_labels(self) -> tuple[str, str, str | None]:
        encounter = self._endless_encounter(self.stage_index + 1)
        progress = (
            f"STAGE {self.stage_index + 1}  |  "
            f"WAVE {self.stage_wave_index + 1}/{len(encounter.waves)}  |  "
            f"SCORE {self.campaign_score}"
        )
        timer = getattr(self, "stage_wave_clear_timer", None)
        countdown = (
            f"WAVE CLEARED  -  NEXT WAVE IN {timer:.1f}s"
            if timer is not None and timer > 0.0
            else None
        )
        return progress, encounter.title, countdown

    def _draw_stage_progression_hud(self, surface: pygame.Surface) -> None:
        progress = self._stage_progress_display()
        if progress is None:
            return

        level, xp_into_level, xp_for_next_level = progress
        panel = pygame.Rect(20, 82, 420, 48)
        pygame.draw.rect(surface, (18, 27, 40), panel, border_radius=6)
        pygame.draw.rect(surface, (74, 88, 105), panel, width=1, border_radius=6)
        label = self.small_font.render(
            f"LEVEL {level}  |  XP {xp_into_level}/{xp_for_next_level}",
            True,
            TEXT_COLOR,
        )
        surface.blit(label, (panel.x + 8, panel.y + 3))
        bar = pygame.Rect(panel.x + 8, panel.y + 31, panel.width - 16, 9)
        pygame.draw.rect(surface, (52, 63, 76), bar, border_radius=3)
        fill_width = round(bar.width * xp_into_level / xp_for_next_level)
        if fill_width:
            pygame.draw.rect(
                surface,
                (66, 213, 155),
                pygame.Rect(bar.x, bar.y, fill_width, bar.height),
                border_radius=3,
            )

    def _draw_stage_mode_card(self, surface: pygame.Surface) -> None:
        if not self.stage_mode:
            return

        show_title = self.stage_card_timer > 0.0
        if not (
            show_title
            or self.stage_intermission
            or self.stage_mode_failed
        ):
            return

        if show_title and not self.stage_intermission and not self.stage_mode_failed:
            encounter = self._endless_encounter(self.stage_index + 1)
            banner = pygame.Rect(
                (SCREEN_WIDTH - STAGE_TITLE_BANNER_WIDTH) // 2,
                STAGE_TITLE_BANNER_TOP,
                STAGE_TITLE_BANNER_WIDTH,
                STAGE_TITLE_BANNER_HEIGHT,
            )
            panel = pygame.Surface(banner.size, pygame.SRCALPHA)
            pygame.draw.rect(
                panel,
                (18, 27, 40, 224),
                panel.get_rect(),
                border_radius=12,
            )
            pygame.draw.rect(
                panel,
                (220, 169, 91, 230),
                panel.get_rect(),
                width=2,
                border_radius=12,
            )
            if self.stage_card_mode == "wave":
                wave = encounter.waves[self.stage_wave_index]
                tag = f"WAVE {self.stage_wave_index + 1}"
                title = f"{tag}  ·  {wave.banner}"
                subtitle = encounter.title
            else:
                tag = f"STAGE {self.stage_index + 1}"
                title = f"{tag}  ·  {encounter.title}"
                subtitle = encounter.description
            if encounter.is_milestone:
                tag = f"MILESTONE  ·  {tag}"
                title = f"{tag}  ·  {encounter.title}"
            act = self.stage_act_font.render(encounter.act, True, (255, 214, 139))
            heading = self.stage_banner_heading_font.render(
                title,
                True,
                (241, 245, 250),
            )
            detail = self.stage_banner_subtitle_font.render(
                subtitle,
                True,
                (195, 205, 218),
            )
            panel.blit(act, act.get_rect(midtop=(banner.width // 2, 8)))
            panel.blit(heading, heading.get_rect(midtop=(banner.width // 2, 34)))
            panel.blit(detail, detail.get_rect(midtop=(banner.width // 2, 75)))
            surface.blit(panel, banner.topleft)
            return

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 20, 175))
        surface.blit(overlay, (0, 0))
        card = pygame.Rect(460, 330, 1000, 420)
        pygame.draw.rect(surface, (24, 32, 44), card, border_radius=18)
        pygame.draw.rect(surface, (220, 169, 91), card, width=3, border_radius=18)

        if self.stage_intermission:
            health_recovery = min(
                max(0, self.fighter.max_health - self.fighter.health),
                max(1, self.fighter.max_health // 4),
            )
            mana_recovery = min(
                max(0, self.fighter.max_mana - self.fighter.mana),
                max(1, self.fighter.max_mana // 4),
            )
            act = self.stage_act_font.render(
                f"SUPPLY BREAK - AFTER STAGE {self.stage_index + 1}",
                True,
                (255, 214, 139),
            )
            heading = self.stage_title_font.render("FIELD SUPPLIES", True, TEXT_COLOR)
            surface.blit(act, act.get_rect(center=(card.centerx, 385)))
            surface.blit(heading, heading.get_rect(center=(card.centerx, 458)))

            options = (
                f"HEAL +{health_recovery} HP" if health_recovery else "HEALTH FULL",
                f"RESTORE +{mana_recovery} MP" if mana_recovery else "MANA FULL",
            )
            option_rects = (
                pygame.Rect(card.x + 74, 512, 400, 94),
                pygame.Rect(card.right - 474, 512, 400, 94),
            )
            for index, (option, rect) in enumerate(zip(options, option_rects)):
                selected = index == self.stage_intermission_choice
                fill = (79, 76, 53) if selected else (34, 43, 56)
                border = (255, 214, 139) if selected else (104, 121, 139)
                pygame.draw.rect(surface, fill, rect, border_radius=12)
                pygame.draw.rect(surface, border, rect, width=3 if selected else 1, border_radius=12)
                label = self.stage_choice_font.render(option, True, TEXT_COLOR)
                surface.blit(label, label.get_rect(center=rect.center))
            prompt = self.stage_subtitle_font.render(
                f"{KEY_BINDINGS.label('move_left')} / {KEY_BINDINGS.label('move_right')} to choose  -  "
                f"{KEY_BINDINGS.label('attack')} to continue",
                True,
                (195, 205, 218),
            )
            surface.blit(prompt, prompt.get_rect(center=(card.centerx, 660)))
            return

        if self.stage_mode_failed:
            act_text = "RUN ENDED"
            heading_text = "STAGE FAILED"
            detail_text = f"STAGE {self.stage_index + 1}"
            secondary_text = self._endless_encounter(self.stage_index + 1).title
            prompt_text = f"Press {KEY_BINDINGS.label('attack')} to return to the menu"
        elif self.stage_card_mode == "wave":
            encounter = self._endless_encounter(self.stage_index + 1)
            wave = encounter.waves[self.stage_wave_index]
            act_text = encounter.act
            heading_text = "REINFORCEMENTS"
            detail_text = encounter.title
            secondary_text = wave.banner
            prompt_text = ""
        else:
            encounter = self._endless_encounter(self.stage_index + 1)
            act_text = encounter.act
            heading_text = f"STAGE {self.stage_index + 1}"
            detail_text = encounter.title
            secondary_text = encounter.description
            prompt_text = "Clear all waves to continue."

        act = self.stage_act_font.render(act_text, True, (255, 214, 139))
        heading = self.stage_title_font.render(heading_text, True, TEXT_COLOR)
        detail = self.stage_name_font.render(detail_text, True, (220, 228, 237))
        surface.blit(act, act.get_rect(center=(card.centerx, 390)))
        surface.blit(heading, heading.get_rect(center=(card.centerx, 465)))
        surface.blit(detail, detail.get_rect(center=(card.centerx, 535)))
        secondary = self.stage_subtitle_font.render(secondary_text, True, (195, 205, 218))
        surface.blit(secondary, secondary.get_rect(center=(card.centerx, 590)))
        if prompt_text:
            prompt = self.small_font.render(prompt_text, True, (170, 183, 198))
            surface.blit(prompt, prompt.get_rect(center=(card.centerx, 650)))

    def _draw_stage_milestone_reward(self, surface: pygame.Surface) -> None:
        reward_xp = getattr(self, "stage_milestone_reward_xp", 0)
        if (
            reward_xp <= 0
            or getattr(self, "stage_milestone_reward_timer", 0.0) <= 0.0
        ):
            return
        banner = pygame.Rect(
            (SCREEN_WIDTH - 620) // 2,
            STAGE_TITLE_BANNER_TOP + STAGE_TITLE_BANNER_HEIGHT + 12,
            620,
            52,
        )
        panel = pygame.Surface(banner.size, pygame.SRCALPHA)
        pygame.draw.rect(
            panel,
            (18, 27, 40, 232),
            panel.get_rect(),
            border_radius=10,
        )
        pygame.draw.rect(
            panel,
            (91, 207, 155, 235),
            panel.get_rect(),
            width=2,
            border_radius=10,
        )
        label = self.stage_subtitle_font.render(
            f"STAGE {self.stage_milestone_reward_stage} CLEAR  ·  +{reward_xp} XP",
            True,
            (198, 255, 222),
        )
        panel.blit(label, label.get_rect(center=panel.get_rect().center))
        surface.blit(panel, banner.topleft)

    def _draw_marker(self, surface: pygame.Surface, fighter: Fighter, camera_x: float, text: str) -> None:
        marker = self.small_font.render(text, True, (255, 240, 120))
        rect = marker.get_rect(midtop=(fighter.world_hitbox_rect().centerx - int(camera_x), fighter.world_hitbox_rect().bottom + 6))
        if rect.bottom < SCREEN_HEIGHT:
            surface.blit(marker, rect)

    def update(self, dt: float, inputs: FighterInput) -> None:
        if self.paused:
            if pygame.display.get_init():
                self._update_pause_card_hover(dt, pygame.mouse.get_pos())
            return
        self._pause_hover_candidate_key = None
        self._pause_hover_dwell = 0.0
        self._pause_card_hover_progress = {}
        if self.stage_mode and self.stage_mode_failed:
            if inputs.attack_just_pressed:
                self.return_to_menu_requested = True
            return
        if self.stage_mode and self.stage_intermission:
            if inputs.left_just_pressed:
                self.stage_intermission_choice = (self.stage_intermission_choice - 1) % 2
            elif inputs.right_just_pressed:
                self.stage_intermission_choice = (self.stage_intermission_choice + 1) % 2
            if inputs.attack_just_pressed:
                self._confirm_recovery_choice()
            return
        if self.stage_mode:
            self._ensure_stage_level_up_slot()
            if self.stage_level_up_slot.active:
                self._update_stage_level_up_slot(dt, inputs)
                for fighter in self._fighters():
                    fighter.animation_player.update(dt, facing=fighter.facing)
                return
        elif self.test_mode:
            self._ensure_stage_level_up_slot()
            if (
                self.stage_level_up_slot.active
                and not self.stage_level_up_slot.visual_only
            ):
                self._update_stage_level_up_slot(dt, inputs)
                for fighter in self._fighters():
                    fighter.animation_player.update(dt, facing=fighter.facing)
                return
            if self._update_test_level_up_slot(dt, inputs):
                for fighter in self._fighters():
                    fighter.animation_player.update(dt, facing=fighter.facing)
                return
        if self.stage_mode:
            self._age_stage_enemy_corpses(dt)
        if self.stage_mode and self.stage_card_timer > 0.0:
            self.stage_card_timer = max(0.0, self.stage_card_timer - dt)
        if getattr(self, "stage_milestone_reward_timer", 0.0) > 0.0:
            self.stage_milestone_reward_timer = max(
                0.0,
                self.stage_milestone_reward_timer - dt,
            )

        self.consumable_spawn_timer -= dt
        while self.consumable_spawn_timer <= 0.0:
            self._spawn_consumable(random.choice(self.spawnable_items))
            self.consumable_spawn_timer += 18.0
        if inputs.spawn_random_item_just_pressed:
            self._spawn_consumable(random.choice(self.spawnable_items))
        if inputs.spawn_heavy_item_just_pressed:
            self._spawn_consumable(HEAVY_BOX_ITEM_ID)
        if getattr(self, "test_mode", False) and inputs.test_spawn_xp_orb_just_pressed:
            self._spawn_test_xp_orb()
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
            enemy_input = self._npc_item_input(
                enemy,
                self.fighter,
                brain.build_input(enemy.snapshot, self.fighter.snapshot),
            )
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
            clone_input = self._npc_item_input(
                clone.fighter,
                clone_target if clone_target is not None and not clone_target.is_dead else None,
                clone.brain.build_input(clone.fighter.snapshot, clone_target.snapshot)
                if clone_target is not None and not clone_target.is_dead
                else FighterInput(),
            )
            was_drinking[clone.fighter] = clone.fighter.state == "drink"
            clone_throw_was_active = clone.fighter.item_throw_animation is not None
            clone_throw_handled = self._handle_held_item_throw_input(clone.fighter, clone_input)
            if clone_throw_was_active or clone_throw_handled:
                clone_input = self._suppress_item_throw_inputs(clone_input)
                clone_item = None
            else:
                clone_item = self._item_to_drink(clone.fighter, clone_input)
                if clone_item is not None:
                    clone_input = replace(
                        clone_input,
                        attack_pressed=False,
                        attack_just_pressed=False,
                        drink_just_pressed=True,
                    )
                elif self._try_pick_up_consumable(clone.fighter, clone_input):
                    clone_input = replace(clone_input, attack_just_pressed=False)
            if clone.fighter.held_item is not None and _is_throwable_item(clone.fighter.held_item):
                clone_input = replace(clone_input, drink_just_pressed=False)
            clone.fighter.update(dt, clone_input, target=clone_target, controlled=True)
            items_to_drink[clone.fighter] = clone_item
        for fighter in self._fighters():
            self._spawn_character_freeze_break_fragments(fighter)
        for fighter in self._fighters():
            self._transform_luis_if_pending(fighter)
        for fighter in self._fighters():
            self._finish_held_item_throw(fighter)
        for fighter, previously_drinking in was_drinking.items():
            item_id = items_to_drink.get(fighter)
            if fighter.state == "drink" and not previously_drinking:
                self.audio.play("drink_drink")
                if item_id is not None:
                    if item_id == "consumables/milk":
                        fighter.health = min(fighter.max_health, fighter.health + 5)
                    elif item_id == "consumables/whiskey":
                        self._start_whiskey_effect(fighter)
                    self.start_item_overlay(fighter, item_id, "drink", active_state="drink")

        for fighter in self._fighters():
            self._apply_henry_flute_attack(fighter)
            self._spawn_freeze_ball(fighter)
            self._spawn_reece_buzz_ball(fighter)
            self._spawn_reece_biggie_ball(fighter)
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
            self._spawn_ashley_blast(fighter)
            self._spawn_ashley_missiles(fighter)
            self._spawn_ashley_barrier(fighter)
            self._spawn_ashley_mana_orb(fighter)
            self._spawn_ashley_attack_sparkles(fighter)
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
            self._spawn_reece_fire_breath(fighter)
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
        self._update_whiskey_effects(dt)
        for effect in tuple(self.rudolf_clone_smoke_effects):
            if effect.update(dt):
                self.rudolf_clone_smoke_effects.remove(effect)
        for item in tuple(self.consumable_items):
            item_event = item.update(dt)
            if item_event == "landed":
                if item.item_id in HEAVY_ITEM_IDS:
                    self.audio.play_heavy_box_land()
                elif item.item_id == "weapons/ice_sword":
                    self.audio.play("ice_sword_land")
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
                elif item.item_id == "consumables/whiskey":
                    self._break_whiskey_item(item, spawn_fire=True)
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
                            self.milk_break_frames["large_1"],
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
        if self.stage_mode:
            self._update_stage_curse_attacks(dt)
        self._update_projectiles(dt)
        self._remove_finished_rudolf_clones()
        self._handle_woody_punches()
        self._handle_woody_dash_hits(previous_x_by_fighter)
        self._handle_combat()
        self._remove_finished_rudolf_clones()
        self._handle_audio(dt)
        if self.stage_mode:
            self._dispatch_stage_enemy_spawns()
            self._register_stage_enemy_corpses()
            self._update_stage_xp_orbs(dt)
            if self.fighter.state == "dead":
                self.stage_mode_failed = True
            else:
                self._ensure_stage_level_up_slot()
                if (
                    not getattr(self, "_stage_enemy_spawn_queue", [])
                    and self.stage_wave_enemies
                    and all(enemy.is_dead for enemy in self.stage_wave_enemies)
                ):
                    if self.stage_wave_clear_timer is None:
                        self.stage_wave_clear_timer = STAGE_WAVE_GRACE_DURATION
                    else:
                        self.stage_wave_clear_timer = max(0.0, self.stage_wave_clear_timer - dt)
                        if self.stage_wave_clear_timer <= 1e-6:
                            self.stage_wave_clear_timer = 0.0
                            self._advance_stage_mode()
                else:
                    self.stage_wave_clear_timer = None
        elif getattr(self, "test_mode", False):
            self._update_stage_xp_orbs(dt)
            self._ensure_stage_level_up_slot()

    def _pause_card_fan_layout(
        self,
    ) -> tuple[
        list[tuple[int, StageCard, int, float, int, pygame.Surface, pygame.Rect]],
        int,
        int,
    ]:
        ranks = getattr(self, "stage_card_ranks", {})
        owned_cards = [
            (card, ranks[card.key])
            for card in STAGE_CARD_CATALOG
            if ranks.get(card.key, 0) > 0
        ]
        count = len(owned_cards)
        step = min(90.0, 660.0 / max(1, count - 1))
        middle = (count - 1) / 2
        fan_center_x = pygame.Rect(38, 148, 914, 790).centerx
        baseline_y = pygame.Rect(38, 148, 914, 790).bottom - 42
        specs: list[
            tuple[int, StageCard, int, float, int, pygame.Surface, pygame.Rect]
        ] = []
        for index, (card, rank) in enumerate(owned_cards):
            angle_step = min(9.0, 44.0 / max(1, count - 1))
            angle = (index - middle) * angle_step
            center_x = round(fan_center_x + (index - middle) * step)
            image = _pause_card_surface(card.key, rank, *PAUSE_CARD_SIZE)
            rotated = pygame.transform.rotate(image, angle)
            rect = rotated.get_rect(midbottom=(center_x, baseline_y))
            specs.append((index, card, rank, angle, center_x, rotated, rect))
        return specs, fan_center_x, baseline_y

    def _pause_card_render_state(
        self,
        spec: tuple[int, StageCard, int, float, int, pygame.Surface, pygame.Rect],
        progress: float,
        baseline_y: int,
    ) -> tuple[pygame.Surface, pygame.Rect, float]:
        _, card, rank, angle, center_x, base_image, base_rect = spec
        progress = max(0.0, min(1.0, progress))
        eased = progress * progress * (3.0 - 2.0 * progress)
        if eased <= 0.0:
            image = base_image.copy()
            _apply_stage_card_glow(
                image,
                card.key,
                PAUSE_CARD_SIZE,
                angle,
            )
            return image, base_rect, eased
        width = round(
            PAUSE_CARD_SIZE[0]
            + (PAUSE_CARD_HOVER_SIZE[0] - PAUSE_CARD_SIZE[0]) * eased
        )
        height = round(
            PAUSE_CARD_SIZE[1]
            + (PAUSE_CARD_HOVER_SIZE[1] - PAUSE_CARD_SIZE[1]) * eased
        )
        scaled = pygame.transform.smoothscale(
            _pause_card_surface(card.key, rank, *PAUSE_CARD_SIZE),
            (width, height),
        )
        rotation = angle * (1.0 - eased)
        image = pygame.transform.rotate(scaled, rotation)
        _apply_stage_card_glow(
            image,
            card.key,
            (width, height),
            rotation,
        )
        rect = image.get_rect(
            midbottom=(
                center_x,
                baseline_y - round(48 * eased),
            )
        )
        return image, rect, eased

    def _pause_card_mouse_target(
        self,
        mouse_pos: tuple[int, int],
        specs: list[
            tuple[int, StageCard, int, float, int, pygame.Surface, pygame.Rect]
        ],
        baseline_y: int,
    ) -> str | None:
        progress_by_key = getattr(self, "_pause_card_hover_progress", {})
        base_candidates = [
            spec for spec in specs if spec[6].collidepoint(mouse_pos)
        ]
        if base_candidates:
            nearest = min(
                base_candidates,
                key=lambda spec: (
                    (mouse_pos[0] - spec[4]) ** 2
                    + (mouse_pos[1] - spec[6].centery) ** 2,
                    -spec[0],
                ),
            )
            return nearest[1].key

        animated = [
            spec
            for spec in specs
            if progress_by_key.get(spec[1].key, 0.0) > 0.0
        ]
        if animated:
            foreground = max(
                animated,
                key=lambda spec: progress_by_key.get(spec[1].key, 0.0),
            )
            _, rect, _ = self._pause_card_render_state(
                foreground,
                progress_by_key.get(foreground[1].key, 0.0),
                baseline_y,
            )
            if rect.collidepoint(mouse_pos):
                return foreground[1].key
            for spec in reversed(animated):
                if spec is foreground:
                    continue
                _, rect, _ = self._pause_card_render_state(
                    spec,
                    progress_by_key.get(spec[1].key, 0.0),
                    baseline_y,
                )
                if rect.collidepoint(mouse_pos):
                    return spec[1].key
        return None

    def _update_pause_card_hover(
        self,
        dt: float,
        mouse_pos: tuple[int, int],
    ) -> None:
        specs, _, baseline_y = self._pause_card_fan_layout()
        hovered_key = self._pause_card_mouse_target(mouse_pos, specs, baseline_y)
        candidate = getattr(self, "_pause_hover_candidate_key", None)
        if hovered_key != candidate:
            self._pause_hover_candidate_key = hovered_key
            self._pause_hover_dwell = 0.0
        elif hovered_key is not None:
            self._pause_hover_dwell += max(0.0, dt)
        ready_key = (
            hovered_key
            if hovered_key is not None
            and self._pause_hover_dwell >= PAUSE_CARD_HOVER_DELAY
            else None
        )
        owned_keys = {spec[1].key for spec in specs}
        progress_by_key = getattr(self, "_pause_card_hover_progress", {})
        for key in tuple(progress_by_key):
            if key not in owned_keys:
                del progress_by_key[key]
        for key in owned_keys:
            current = progress_by_key.get(key, 0.0)
            if key == ready_key:
                current = min(
                    1.0,
                    current + max(0.0, dt) / PAUSE_CARD_HOVER_IN_DURATION,
                )
            else:
                current = max(
                    0.0,
                    current - max(0.0, dt) / PAUSE_CARD_HOVER_OUT_DURATION,
                )
            progress_by_key[key] = current
        self._pause_card_hover_progress = progress_by_key

    def _draw_pause_card_fan(
        self,
        surface: pygame.Surface,
        mouse_pos: tuple[int, int],
    ) -> str | None:
        left_panel = pygame.Rect(38, 148, 914, 790)
        pygame.draw.rect(surface, (13, 17, 28), left_panel, border_radius=18)
        pygame.draw.rect(surface, (108, 121, 145), left_panel, 2, border_radius=18)
        heading = self.stage_subtitle_font.render(
            "COLLECTED CARDS",
            True,
            (255, 222, 154),
        )
        surface.blit(
            heading,
            heading.get_rect(midtop=(left_panel.centerx, left_panel.y + 24)),
        )
        specs, _, baseline_y = self._pause_card_fan_layout()
        if not specs:
            empty = self.small_font.render(
                "No cards collected yet",
                True,
                (180, 191, 208),
            )
            surface.blit(
                empty,
                empty.get_rect(center=(left_panel.centerx, left_panel.centery)),
            )
            return None

        hovered_key = self._pause_card_mouse_target(
            mouse_pos,
            specs,
            baseline_y,
        )
        progress_by_key = getattr(self, "_pause_card_hover_progress", {})
        foreground = max(
            (
                spec
                for spec in specs
                if progress_by_key.get(spec[1].key, 0.0) > 0.0
            ),
            key=lambda spec: progress_by_key.get(spec[1].key, 0.0),
            default=None,
        )
        for spec in specs:
            if spec is foreground:
                continue
            progress = progress_by_key.get(spec[1].key, 0.0)
            image, rect, _ = self._pause_card_render_state(
                spec,
                progress,
                baseline_y,
            )
            if progress > 0.0:
                pygame.draw.rect(
                    surface,
                    (3, 5, 10),
                    rect.inflate(10, 10).move(0, 6),
                    border_radius=10,
                )
            surface.blit(image, rect)

        if foreground is not None:
            progress = progress_by_key.get(foreground[1].key, 0.0)
            image, rect, eased = self._pause_card_render_state(
                foreground,
                progress,
                baseline_y,
            )
            pygame.draw.rect(
                surface,
                (3, 5, 10),
                rect.inflate(14, 14).move(0, 8),
                border_radius=12,
            )
            surface.blit(image, rect)
            if eased > 0.78:
                pygame.draw.rect(
                    surface,
                    (255, 218, 125),
                    rect.inflate(6, 6),
                    3,
                    border_radius=8,
                )

        return hovered_key

    def _draw_pause_stats_panel(self, surface: pygame.Surface) -> None:
        panel = pygame.Rect(978, 148, 904, 790)
        pygame.draw.rect(surface, (13, 17, 28), panel, border_radius=18)
        pygame.draw.rect(surface, (108, 121, 145), panel, 2, border_radius=18)
        heading = self.stage_subtitle_font.render(
            "CHARACTER STATS",
            True,
            (255, 222, 154),
        )
        surface.blit(heading, heading.get_rect(midtop=(panel.centerx, panel.y + 24)))

        fighter = self.fighter
        character_name = fighter.definition.get("display_name", "Player")
        name = self.pause_font.render(character_name, True, TEXT_COLOR)
        surface.blit(name, name.get_rect(midtop=(panel.centerx, panel.y + 68)))

        bar_x = panel.x + 54
        bar_width = panel.width - 108
        self._draw_hud_bar(
            surface,
            bar_x,
            panel.y + 146,
            bar_width,
            34,
            fighter.health,
            fighter.max_health,
            (194, 58, 58),
            "HP",
        )
        self._draw_hud_bar(
            surface,
            bar_x,
            panel.y + 194,
            bar_width,
            30,
            fighter.mana,
            fighter.max_mana,
            (72, 122, 235),
            "MP",
        )

        effects = stage_card_effects(getattr(self, "stage_card_ranks", {}))
        stats = (
            ("WALK SPEED", f"{fighter.movement.get('walk_speed', 0):.0f} px/s"),
            ("RUN SPEED", f"{fighter.movement.get('run_speed', 0):.0f} px/s"),
            ("TOUCH DAMAGE", str(getattr(fighter, "touch_damage", 0))),
            ("DAMAGE BONUS", f"+{(effects['damage_multiplier'] - 1) * 100:.0f}%"),
            ("DAMAGE REDUCTION", f"{effects['damage_reduction'] * 100:.0f}%"),
            ("MAX HP BONUS", f"+{effects['max_health_bonus']:.0f}"),
            ("XP PICKUP RANGE", f"+{(effects['xp_range_multiplier'] - 1) * 100:.0f}%"),
            ("XP GAIN", f"+{(effects['xp_gain_multiplier'] - 1) * 100:.0f}%"),
        )
        column_width = (panel.width - 120) // 2
        for index, (label, value) in enumerate(stats):
            column = index % 2
            row = index // 2
            x = panel.x + 54 + column * (column_width + 12)
            y = panel.y + 278 + row * 72
            label_surface = self.small_font.render(
                label,
                True,
                (167, 181, 201),
            )
            value_surface = self.stage_subtitle_font.render(
                value,
                True,
                (239, 242, 248),
            )
            surface.blit(label_surface, (x, y))
            surface.blit(value_surface, (x, y + 27))

        progression = getattr(self, "stage_progression", None)
        if progression is not None:
            progress_y = panel.y + 590
            progress_text = self.small_font.render(
                f"LEVEL {progression.level}    "
                f"XP {progression.xp_into_level}/{progression.xp_for_next_level}",
                True,
                (255, 222, 154),
            )
            surface.blit(
                progress_text,
                progress_text.get_rect(midtop=(panel.centerx, progress_y)),
            )
            bar = pygame.Rect(panel.x + 54, progress_y + 36, bar_width, 18)
            pygame.draw.rect(surface, (35, 40, 52), bar, border_radius=8)
            fill = round(
                bar.width
                * progression.xp_into_level
                / max(1, progression.xp_for_next_level)
            )
            if fill:
                pygame.draw.rect(
                    surface,
                    (53, 199, 143),
                    (bar.x, bar.y, fill, bar.height),
                    border_radius=8,
                )

    def _draw_pause_menu(self, surface: pygame.Surface) -> None:
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((4, 7, 14, 224))
        surface.blit(overlay, (0, 0))
        paused = self.pause_font.render("PAUSED", True, TEXT_COLOR)
        surface.blit(
            paused,
            paused.get_rect(center=(SCREEN_WIDTH // 2, 66)),
        )
        self._draw_pause_card_fan(surface, pygame.mouse.get_pos())
        self._draw_pause_stats_panel(surface)
        resume = self.small_font.render(
            f"{KEY_BINDINGS.label('back_pause')}: Resume",
            True,
            TEXT_COLOR,
        )
        menu = self.small_font.render(
            f"{KEY_BINDINGS.label('return_to_menu')}: Main Menu",
            True,
            TEXT_COLOR,
        )
        surface.blit(
            resume,
            resume.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 74)),
        )
        surface.blit(
            menu,
            menu.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 42)),
        )

    def draw(self, surface: pygame.Surface) -> None:
        focus_x = self._camera_focus_x()
        camera_x = self.stage.camera_x(focus_x)
        self.stage.draw(surface, focus_x)

        for projectile in self.projectiles:
            if isinstance(projectile, AshleySpriteEffect) and projectile.foreground:
                continue
            if not isinstance(projectile, (AxleShotProjectile, FireExplosionEffect, JulianExplosionEffect)):
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
            self._draw_dark_bat_weapon_phase(surface, fighter, camera_x)
            self._draw_held_item(surface, fighter, camera_x)
            self._draw_item_overlay(surface, fighter, camera_x)
            self._draw_whiskey_status(surface, fighter, camera_x)
            self._draw_speech_bubble(surface, fighter, camera_x)
        if self.stage_mode or getattr(self, "test_mode", False):
            for orb in self.stage_xp_orbs:
                orb.draw(surface, camera_x)
        for projectile in self.projectiles:
            if isinstance(projectile, (AxleShotProjectile, FireExplosionEffect, JulianExplosionEffect)):
                projectile.draw(surface, camera_x)
        for projectile in self.projectiles:
            if isinstance(projectile, AshleySpriteEffect) and projectile.foreground:
                projectile.draw(surface, camera_x)
            elif isinstance(projectile, AshleyMagicalBarrierEffect):
                projectile.draw_reflect_overlay(surface, camera_x)

        self._draw_marker(surface, self.fighter, camera_x, "P1")
        self._draw_hud(surface)
        self._draw_stage_progression_hud(surface)
        self._draw_stage_mode_card(surface)
        self._draw_stage_milestone_reward(surface)
        self._draw_stage_level_up_slot(surface)
        if self.paused:
            self._draw_pause_menu(surface)
