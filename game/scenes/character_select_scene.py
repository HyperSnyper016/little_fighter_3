from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pygame

from game.constants import GROUND_Y, SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR
from game.data.archetypes import resolve_character_profile
from game.data.characters import (
    CHARACTER_CATEGORIES,
    CHARACTER_GROUPS,
    CHARACTERS,
    NON_PLAYABLE_CHARACTER_KEYS,
)
from game.systems.animation import AnimationPlayer
from game.systems.assets import load_character_animations
from game.systems.keybindings import KEY_BINDINGS

PROFILE_SIZE = (68, 68)
PROFILE_FILENAME_ALIASES = {
    "luis": ("louis.png",),
    "luis_liberated": ("liberated_louis.png",),
}
ROSTER_PANEL = pygame.Rect(42, 824, SCREEN_WIDTH - 84, 238)
ROSTER_CARD_TOP = 872
ROSTER_CARD_HEIGHT = 86
ROSTER_CARD_GAP = 4
ROSTER_GRID_COLUMNS = 14
ROSTER_MARGIN = 12
ROSTER_CATEGORY_GAP = 8
SELECTION_GLOW_PERIOD = 1.4
BACK_BUTTON = pygame.Rect(1280, 45, 120, 62)
CONFIRM_BUTTON = pygame.Rect(SCREEN_WIDTH - 352, 45, 292, 62)
INFO_PANEL = pygame.Rect(1120, 230, 760, 530)
INFO_COLLAPSED_HEIGHT = 320
SIGNATURE_MAX_SIZE = (INFO_PANEL.width - 48, 60)
PREVIEW_CENTER = (450, 850)
PREVIEW_MAX_SIZE = (760, 640)
PREVIEW_SWITCH_DELAY = 0.12
BACKGROUND_DIR = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "sprites"
    / "ui"
    / "character_selection"
    / "background"
)
FAR_SKY_PATH = BACKGROUND_DIR / "far_sky.jpg"
DISTANT_SKYLINE_PATH = BACKGROUND_DIR / "distant_skyline.png"
PARTICLES_PATH = BACKGROUND_DIR / "particals.png"
FAST_PARTICLES_PATH = BACKGROUND_DIR / "particals_2.png"
GROUND_TILE_PATH = BACKGROUND_DIR / "Gemini_Generated_Image_qefwajqefwajqefw.jpg"
GROUND_TILE_TOP_TRIM = 80
GROUND_SCROLL_WORLD_SCALE = 1.0
GROUND_SCROLL_RESPONSE = 0.42
FAR_SKY_PARALLAX = 0.1
SKYLINE_PARALLAX = 0.36
SLOW_PARTICLE_PARALLAX = 0.12
FAST_PARTICLE_PARALLAX = 0.3
SLOW_PARTICLE_DRIFT_SPEED = 3.0
FAST_PARTICLE_DRIFT_SPEED = 14.0
PARTICLE_TINT = (110, 75, 38)
SLOW_PARTICLE_TINT = (50, 54, 60)
SELECTION_GROUND_Y = GROUND_Y - 40

CATEGORY_ACCENTS = (
    (229, 160, 82),
    (126, 174, 207),
    (206, 112, 103),
    (127, 196, 171),
    (214, 174, 99),
    (158, 138, 205),
    (190, 107, 154),
    (218, 111, 80),
    (146, 161, 175),
)
CATEGORY_ACCENT_BY_NAME = {
    category: CATEGORY_ACCENTS[index % len(CATEGORY_ACCENTS)]
    for index, (category, _) in enumerate(CHARACTER_GROUPS)
}

SPECIAL_MOVE_LABELS = {
    "sp_move_attack_1": "Moving Special I",
    "sp_move_attack_2": "Moving Special II",
    "sp_vert_attack_1": "Vertical Special I",
    "sp_vert_attack_2": "Vertical Special II",
}


@dataclass(frozen=True)
class PreviewForwardMotion:
    movement_stat: str | None = None
    multiplier: float = 1.0
    active_frames: frozenset[int] | None = None
    start_frame: int | None = None
    fixed_speed: float | None = None


@dataclass(frozen=True)
class PreviewForwardStep:
    frames: frozenset[int]
    movement_stat: str | None = None
    multiplier: float = 1.0
    fixed_distance: float | None = None


# Mirrors forward movement in Fighter.update for animations shown by the preview.
PREVIEW_FORWARD_MOTIONS = {
    ("bat", "sp_vert_attack_1"): PreviewForwardMotion("walk_speed"),
    ("davis", "sp_vert_attack_1"): PreviewForwardMotion("walk_speed", 0.5),
    ("deep", "sp_vert_attack_2"): PreviewForwardMotion("walk_speed", 0.4),
    ("deep", "sp_move_attack_2"): PreviewForwardMotion(fixed_speed=220.0),
    ("davis", "sp_move_attack_2"): PreviewForwardMotion(
        "run_speed",
        active_frames=frozenset({1, 2}),
    ),
    ("firen", "sp_vert_attack_1"): PreviewForwardMotion("run_speed"),
    ("jack", "sp_vert_attack_1"): PreviewForwardMotion("walk_speed", 0.5),
    ("luis", "sp_vert_attack_1"): PreviewForwardMotion("run_speed"),
    ("luis_liberated", "sp_vert_attack_1"): PreviewForwardMotion("run_speed"),
    ("mark", "sp_move_attack_1"): PreviewForwardMotion("run_speed", 1.5),
    ("denis", "sp_move_attack_2"): PreviewForwardMotion("run_speed", 1.25),
    ("woody", "sp_vert_attack_1"): PreviewForwardMotion(
        "run_speed",
        2.5,
        start_frame=3,
    ),
}

PREVIEW_FORWARD_STEPS = {
    ("luis", "sp_move_attack_1"): PreviewForwardStep(
        frozenset({1, 3, 5}),
        "run_speed",
        0.08,
    ),
    ("axle", "sp_move_attack_2"): PreviewForwardStep(
        frozenset({1, 3}),
        "walk_speed",
        0.1,
    ),
    ("axle", "sp_vert_attack_1"): PreviewForwardStep(
        frozenset({1, 3}),
        "walk_speed",
        0.1,
    ),
    ("woody", "sp_vert_attack_2"): PreviewForwardStep(
        frozenset({5}),
        fixed_distance=240.0,
    ),
}


@dataclass(frozen=True)
class PreviewProjectileSpec:
    trigger_frames: tuple[int, ...]
    travel_frames: tuple[str, ...]
    impact_frames: tuple[str, ...] | None = None
    travel_duration: float = 0.55
    travel_distance: float = 340.0
    count: int = 1
    vertical_spread: float = 0.0
    scale: float = 1.0
    origin_x: float = 0.19
    origin_y: float = 0.34


@dataclass(frozen=True)
class PreviewCompanionSpec:
    trigger_frame: int
    create_frames: tuple[str, ...]
    fly_frames: tuple[str, ...]
    offsets: tuple[tuple[float, float], ...]
    lifetime: float = 1.35


def _projectile(
    trigger_frames: tuple[int, ...],
    travel_frames: tuple[str, ...],
    impact_frames: tuple[str, ...] | None = None,
    *,
    travel_duration: float = 0.55,
    travel_distance: float = 340.0,
    count: int = 1,
    vertical_spread: float = 0.0,
    scale: float = 1.0,
    origin_x: float = 0.19,
    origin_y: float = 0.34,
) -> PreviewProjectileSpec:
    return PreviewProjectileSpec(
        trigger_frames=trigger_frames,
        travel_frames=travel_frames,
        impact_frames=impact_frames,
        travel_duration=travel_duration,
        travel_distance=travel_distance,
        count=count,
        vertical_spread=vertical_spread,
        scale=scale,
        origin_x=origin_x,
        origin_y=origin_y,
    )


PREVIEW_PROJECTILES: dict[tuple[str, str], tuple[PreviewProjectileSpec, ...]] = {
    ("hunter", "attack_punch"): (
        _projectile((1,), ("arrow", "arrow_fly"), ("arrow", "arrow_break"), travel_duration=0.7),
    ),
    ("henry", "attack_1"): (
        _projectile((1,), ("arrow", "arrow_fly"), ("arrow", "arrow_break"), travel_duration=0.7),
    ),
    ("henry", "sp_move_attack_1"): (
        _projectile((4,), ("arrow", "arrow_fly"), ("arrow", "arrow_break"), travel_duration=0.7),
    ),
    ("henry", "sp_move_attack_2"): (
        _projectile(
            (7,),
            ("wind",),
            travel_duration=0.65,
            scale=2.0,
        ),
    ),
    ("henry", "sp_vert_attack_1"): (
        _projectile(
            (1,),
            ("arrow", "arrow_fly"),
            ("arrow", "arrow_break"),
            count=5,
            vertical_spread=34.0,
            travel_duration=0.7,
        ),
    ),
    ("rudolf", "sp_move_attack_1"): (
        _projectile(
            (1,),
            ("rudolf_shuriken",),
            travel_duration=0.65,
            count=3,
            vertical_spread=28.0,
        ),
    ),
    ("rudolf", "attack_1"): (
        _projectile((1,), ("rudolf_shuriken",), travel_duration=0.65),
    ),
    ("rudolf", "attack_2"): (
        _projectile((1,), ("rudolf_shuriken",), travel_duration=0.65),
    ),
    ("jack", "sp_move_attack_1"): (
        _projectile((2,), ("jack_blast", "fly"), ("jack_blast", "burst"), travel_duration=0.7),
    ),
    ("axle", "sp_move_attack_1"): (
        _projectile((2,), ("axle_shot", "fly"), ("axle_shot", "burst"), travel_duration=0.65),
    ),
    ("julian", "sp_move_attack_1"): (
        _projectile(
            (1,),
            ("julian_skull", "slow"),
            ("julian_skull", "burst"),
            travel_duration=0.8,
        ),
    ),
    ("julian", "sp_move_attack_2"): (
        _projectile((3,), ("julian_ball", "fly"), ("julian_ball", "burst"), travel_duration=0.8),
    ),
    ("julian", "sp_vert_attack_1"): (
        _projectile((2,), ("julian_explode",), travel_duration=0.5, travel_distance=0.0, scale=1.5, origin_x=0.0),
    ),
    ("julian", "sp_vert_attack_2"): (
        _projectile((4,), ("julian_explode",), travel_duration=0.5, travel_distance=0.0, scale=1.5, origin_x=0.0),
    ),
    ("john", "sp_move_attack_1"): (
        _projectile((5,), ("john_blast", "fly"), ("john_blast", "burst"), travel_duration=0.7),
    ),
    ("john", "sp_move_attack_2"): (
        _projectile((5,), ("john_magical_barrier", "barrier"), travel_duration=1.1, travel_distance=0.0, origin_x=0.0, origin_y=0.5),
    ),
    ("john", "sp_vert_attack_1"): (
        _projectile((1,), ("john_follow_disk", "fly"), ("john_follow_disk", "burst"), travel_duration=0.85),
    ),
    ("john", "sp_vert_attack_2"): (
        _projectile((3,), ("john_heal_orb", "idle"), ("john_heal_orb", "burst"), travel_duration=0.75, travel_distance=170.0),
    ),
    ("jan", "sp_vert_attack_2"): (
        _projectile((3,), ("jan_follow_orb", "fly"), ("jan_follow_orb", "burst"), travel_duration=0.8),
    ),
    ("bat", "sp_move_attack_2"): (
        _projectile((1,), ("laser", "lazer_point"), ("laser", "lazer_hit"), travel_duration=0.45, travel_distance=320.0),
    ),
    ("dark_bat", "sp_move_attack_2"): (
        _projectile((1,), ("laser", "lazer_point"), ("laser", "lazer_hit"), travel_duration=0.45, travel_distance=320.0),
    ),
    ("freeze", "sp_move_attack_1"): (
        _projectile((2,), ("freeze_ball", "freeze_ball_projectile"), ("freeze_ball", "freeze_ball_burst"), travel_duration=0.75),
    ),
    ("freeze", "sp_move_attack_2"): (
        _projectile((3,), ("freeze_colum", "freeze_colum_1"), travel_duration=0.75, travel_distance=0.0, count=4, vertical_spread=62.0, origin_x=0.0, origin_y=0.5),
    ),
    ("freeze", "sp_vert_attack_1"): (
        _projectile((3,), ("freeze_tornado",), travel_duration=1.0, travel_distance=120.0, scale=1.4),
    ),
    ("sorcerer", "sp_move_attack_1"): (
        _projectile((4,), ("fireball", "fireball_travel"), ("fireball", "fireball_hit"), travel_duration=0.7),
    ),
    ("sorcerer", "sp_move_attack_2"): (
        _projectile((3,), ("freeze_ball", "freeze_ball_projectile"), ("freeze_ball", "freeze_ball_burst"), travel_duration=0.75),
    ),
    ("sorcerer", "sp_vert_attack_2"): (
        _projectile((2,), ("john_heal_orb", "idle"), ("john_heal_orb", "burst"), travel_duration=0.75, travel_distance=170.0),
    ),
    ("template", "sp_move_attack_1"): (
        _projectile((1,), ("blue_ball", "ball_1", "slow"), ("blue_ball", "ball_burst"), travel_duration=0.75),
    ),
    ("davis", "sp_move_attack_1"): (
        _projectile((3,), ("davis_ball", "davis_ball_medium"), ("davis_ball", "davis_ball_burst"), travel_duration=0.75),
    ),
    ("denis", "sp_move_attack_1"): (
        _projectile((2, 7, 13, 16, 17), ("denis_orb", "1"), ("denis_orb", "burst"), travel_duration=0.75),
    ),
    ("denis", "sp_vert_attack_2"): (
        _projectile((2,), ("denis_follow_orb", "medium"), ("denis_follow_orb", "burst"), travel_duration=0.85),
    ),
    ("deep", "sp_move_attack_1"): (
        _projectile((1,), ("blade_swipe",), travel_duration=0.38, travel_distance=90.0, scale=1.5),
    ),
    ("firen", "sp_move_attack_1"): (
        _projectile((2,), ("fireball", "fireball_travel"), ("fireball", "fireball_hit")),
    ),
    ("firen", "sp_move_attack_2"): (
        _projectile((2,), ("fire_breath",), travel_duration=0.55, travel_distance=210.0, scale=1.6),
    ),
    ("firen", "sp_vert_attack_1"): (
        _projectile((1, 3, 5), ("fire_trail",), travel_duration=0.45, travel_distance=0.0, origin_x=0.0, origin_y=0.65),
    ),
    ("firen", "sp_vert_attack_2"): (
        _projectile((4,), ("explode",), travel_duration=0.5, travel_distance=0.0, origin_x=0.0),
    ),
    ("firzen", "sp_move_attack_1"): (
        _projectile((2,), ("firzen_char_blast", "body"), travel_duration=0.75, travel_distance=0.0, scale=1.25, origin_x=0.0),
        _projectile((2,), ("firzen_char_blast", "front"), ("firzen_char_blast", "burst"), travel_duration=0.75, scale=1.25),
    ),
    ("firzen", "sp_move_attack_2"): (
        _projectile((2,), ("firzen_fire", "fly"), ("firzen_fire", "burst"), travel_duration=0.55, count=3, vertical_spread=36.0),
    ),
    ("firzen", "sp_vert_attack_1"): (
        _projectile((2,), ("firzen_fire_ice_orb", "fire_orb", "fly"), ("firzen_fire_ice_orb", "fire_orb", "burst"), travel_duration=0.8),
    ),
    ("firzen", "sp_vert_attack_2"): (
        _projectile((5,), ("freeze_colum", "freeze_colum_1"), travel_duration=0.75, travel_distance=0.0, count=4, vertical_spread=62.0, origin_x=0.0, origin_y=0.5),
        _projectile((5,), ("firzen_fire_ice_orb", "ice_orb", "fly"), ("firzen_fire_ice_orb", "ice_orb", "burst"), travel_duration=0.8, count=3, vertical_spread=34.0),
    ),
    ("woody", "sp_move_attack_1"): (
        _projectile((4, 7), ("woody_shot", "1"), ("woody_shot", "burst"), travel_duration=0.7, count=3, vertical_spread=25.0),
    ),
    ("luis", "sp_move_attack_2"): (
        _projectile((3,), ("wind",), travel_duration=0.65, scale=2.0),
    ),
    ("luis_liberated", "sp_move_attack_2"): (
        _projectile((2,), ("wind",), travel_duration=0.65, scale=2.0),
    ),
    ("monk", "sp_move_attack_1"): (
        _projectile((3,), ("wind",), travel_duration=0.65, scale=2.0),
    ),
}

PREVIEW_COMPANIONS = {
    ("jan", "sp_vert_attack_1"): PreviewCompanionSpec(
        trigger_frame=3,
        create_frames=("summons", "healing_birds", "create"),
        fly_frames=("summons", "healing_birds", "fly"),
        offsets=((-100.0, -65.0), (0.0, -100.0), (100.0, -65.0)),
    ),
    ("bat", "sp_vert_attack_2"): PreviewCompanionSpec(
        trigger_frame=1,
        create_frames=("shared_sprites", "summons", "bats", "bats_flying"),
        fly_frames=("shared_sprites", "summons", "bats", "bats_flying"),
        offsets=((-90.0, -45.0), (0.0, -75.0), (90.0, -45.0)),
        lifetime=1.0,
    ),
    ("dark_bat", "sp_vert_attack_1"): PreviewCompanionSpec(
        trigger_frame=1,
        create_frames=("shared_sprites", "summons", "bats", "bats_flying"),
        fly_frames=("shared_sprites", "summons", "bats", "bats_flying"),
        offsets=((-120.0, -65.0), (-72.0, -90.0), (-24.0, -110.0), (24.0, -110.0), (72.0, -90.0), (120.0, -65.0)),
        lifetime=1.0,
    ),
}

PREVIEW_CLONE_MOVES = {
    ("rudolf", "sp_vert_attack_2"): (4, 2),
}


class PreviewProjectile:
    TRAVEL_FRAME_DURATION = 0.08
    IMPACT_FRAME_DURATION = 0.05

    def __init__(
        self,
        travel_frames: list[pygame.Surface],
        impact_frames: list[pygame.Surface] | None,
        start: tuple[float, float],
        end_x: float,
        travel_duration: float,
    ) -> None:
        self.travel_frames = travel_frames
        self.x, self.y = start
        self.start_x = self.x
        self.end_x = end_x
        self.travel_duration = travel_duration
        self.impact_frames = impact_frames or []
        self.elapsed = 0.0
        self.frame_index = 0
        self.impacting = False
        self.finished = False

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if not self.impacting:
            progress = min(1.0, self.elapsed / self.travel_duration)
            self.x = self.start_x + (self.end_x - self.start_x) * progress
            self.frame_index = int(self.elapsed / self.TRAVEL_FRAME_DURATION) % len(self.travel_frames)
            if progress >= 1.0:
                if self.impact_frames:
                    self.impacting = True
                    self.elapsed = 0.0
                    self.frame_index = 0
                else:
                    self.finished = True
            return

        self.frame_index = int(self.elapsed / self.IMPACT_FRAME_DURATION)
        if self.frame_index >= len(self.impact_frames):
            self.finished = True
            self.frame_index = len(self.impact_frames) - 1

    def draw(self, surface: pygame.Surface) -> None:
        frames = self.impact_frames if self.impacting else self.travel_frames
        if not frames:
            return
        frame = frames[self.frame_index]
        surface.blit(frame, frame.get_rect(center=(round(self.x), round(self.y))))


class PreviewCompanion:
    FRAME_DURATION = 0.08
    CREATE_DURATION = 0.16

    def __init__(
        self,
        create_frames: list[pygame.Surface],
        fly_frames: list[pygame.Surface],
        origin: tuple[float, float],
        offset: tuple[float, float],
        lifetime: float,
        phase: float,
    ) -> None:
        self.create_frames = create_frames
        self.fly_frames = fly_frames
        self.origin_x, self.origin_y = origin
        self.offset_x, self.offset_y = offset
        self.x, self.y = origin
        self.lifetime = lifetime
        self.phase = phase
        self.elapsed = 0.0
        self.frame_index = 0
        self.finished = False

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.elapsed < self.CREATE_DURATION:
            self.frame_index = min(
                int(self.elapsed / self.FRAME_DURATION),
                len(self.create_frames) - 1,
            )
            return

        fly_elapsed = self.elapsed - self.CREATE_DURATION
        if self.elapsed >= self.lifetime:
            self.finished = True
            return

        spread = min(1.0, fly_elapsed / 0.3)
        self.x = (
            self.origin_x
            + self.offset_x * spread
            + 14.0 * math.sin(fly_elapsed * 4 + self.phase)
        )
        self.y = (
            self.origin_y
            + self.offset_y * spread
            + 10.0 * math.cos(fly_elapsed * 4 + self.phase)
        )
        self.frame_index = int(fly_elapsed / self.FRAME_DURATION) % len(self.fly_frames)

    def draw(self, surface: pygame.Surface) -> None:
        frames = self.create_frames if self.elapsed < self.CREATE_DURATION else self.fly_frames
        frame = frames[self.frame_index]
        surface.blit(frame, frame.get_rect(center=(round(self.x), round(self.y))))


class PreviewClone:
    FRAME_DURATION = 0.08

    def __init__(
        self,
        frames: list[pygame.Surface],
        center: tuple[int, int],
        offset_x: float,
        lifetime: float,
        mirrored: bool,
    ) -> None:
        self.frames = frames
        self.center = center
        self.offset_x = offset_x
        self.lifetime = lifetime
        self.mirrored = mirrored
        self.elapsed = 0.0
        self.finished = False

    def update(self, dt: float) -> None:
        self.elapsed += dt
        self.finished = self.elapsed >= self.lifetime

    def draw(self, surface: pygame.Surface) -> None:
        frame = self.frames[int(self.elapsed / self.FRAME_DURATION) % len(self.frames)]
        if self.mirrored:
            frame = pygame.transform.flip(frame, True, False)
        frame = frame.copy()
        frame.set_alpha(150)
        rect = frame.get_rect(midbottom=(round(self.center[0] + self.offset_x), self.center[1]))
        surface.blit(frame, rect)


class CharacterSelectScene:
    def __init__(
        self,
        sprites_root: Path,
        confirm_already_pressed: bool = False,
        stage_mode: bool = False,
        test_mode: bool = False,
        opponent_selection: bool = False,
        player_character: str | None = None,
        toggle_already_pressed: bool = False,
        map_name: str = "City",
        initial_character: str | None = None,
    ) -> None:
        self.sprites_root = sprites_root
        self.map_name = map_name
        self.stage_mode = stage_mode
        self.test_mode = test_mode
        self.opponent_selection = opponent_selection
        self.player_character = player_character
        self.title_font = pygame.font.SysFont("bahnschrift", 68, bold=True)
        self.name_font = pygame.font.SysFont("bahnschrift", 48, bold=True)
        self.subtitle_font = pygame.font.SysFont("segoeui", 23)
        self.section_font = pygame.font.SysFont("bahnschrift", 26, bold=True)
        self.body_font = pygame.font.SysFont("segoeui", 22)
        self.small_font = pygame.font.SysFont("segoeui", 18)
        self.badge_font = pygame.font.SysFont("segoeui", 16, bold=True)
        self.button_font = pygame.font.SysFont("bahnschrift", 24, bold=True)
        self.characters = self._discover_characters()
        self.character_index = {character["key"]: index for index, character in enumerate(self.characters)}
        available_categories = {character["category"] for character in self.characters}
        self.categories = [
            category
            for category, _ in CHARACTER_GROUPS
            if category in available_categories
        ]

        self.selected_index = 0
        if initial_character is not None:
            self.selected_index = self.character_index.get(initial_character, -1)
            if self.selected_index == -1:
                raise ValueError(f"Selected character is unavailable: {initial_character}")
        self.selected_character = self.characters[self.selected_index]["key"] if self.characters else None
        self.selected_opponents: set[str] = set()
        self.selection_confirmed = False
        self.back_requested = False
        self._up_pressed = False
        self._down_pressed = False
        self._left_pressed = False
        self._right_pressed = False
        self._tab_pressed = False
        self._back_pressed = False
        self._confirm_pressed = confirm_already_pressed
        self._toggle_pressed = toggle_already_pressed
        self.moveset_expanded = False
        self.moveset_focused = False
        self.moveset_hovered = False
        self.moveset_toggle_rect = pygame.Rect(0, 0, 0, 0)
        self._elapsed_time = 0.0
        self._last_clicked_character: str | None = None
        self._last_click_time = 0.0

        self.preview_player: AnimationPlayer | None = None
        self.preview_sequence: list[tuple[str, str, float]] = []
        self.preview_sequence_index = 0
        self.preview_elapsed = 0.0
        self.preview_pending_key: str | None = None
        self.preview_pending_elapsed = 0.0
        self.preview_label = "IDLE"
        self.preview_character_key: str | None = None
        self.preview_display_scales: dict[str, float] = {}
        self.preview_projectiles: list[PreviewProjectile] = []
        self.preview_companions: list[PreviewCompanion] = []
        self.preview_clones: list[PreviewClone] = []
        self.preview_projectile_frames: dict[
            PreviewProjectileSpec,
            tuple[list[pygame.Surface], list[pygame.Surface]],
        ] = {}
        self.preview_companion_frames: dict[
            tuple[str, str],
            tuple[list[pygame.Surface], list[pygame.Surface]],
        ] = {}
        self.far_sky_tile = self._load_background_layer(FAR_SKY_PATH)
        self.skyline_tile = self._load_background_layer(DISTANT_SKYLINE_PATH)
        self.slow_particle_tile = self._load_background_layer(
            PARTICLES_PATH,
            tint=SLOW_PARTICLE_TINT,
        )
        self.fast_particle_tile = self._load_background_layer(
            FAST_PARTICLES_PATH,
            tint=PARTICLE_TINT,
        )
        self.ground_tile = self._load_ground_tile()
        self.far_sky_scroll_offset = 0.0
        self.skyline_scroll_offset = 0.0
        self.slow_particle_scroll_offset = 0.0
        self.fast_particle_scroll_offset = self.fast_particle_tile.get_width() / 2
        self.ground_scroll_offset = 0.0
        self.ground_scroll_speed = 0.0
        self.preview_forward_displacement = 0.0

        if self.selected_character is not None:
            self._load_preview(self.selected_character)

    @staticmethod
    def _load_background_layer(
        path: Path,
        tint: tuple[int, int, int] | None = None,
    ) -> pygame.Surface:
        image = pygame.image.load(str(path)).convert_alpha()
        if tint is not None:
            image.fill(tint, special_flags=pygame.BLEND_RGB_ADD)
        return pygame.transform.smoothscale(image, (SCREEN_WIDTH, SCREEN_HEIGHT))

    @staticmethod
    def _load_ground_tile() -> pygame.Surface:
        image = pygame.image.load(str(GROUND_TILE_PATH)).convert()
        if image.get_height() <= GROUND_TILE_TOP_TRIM:
            raise ValueError(f"Ground tile is too short to trim: {GROUND_TILE_PATH}")
        ground_rect = pygame.Rect(
            0,
            GROUND_TILE_TOP_TRIM,
            image.get_width(),
            image.get_height() - GROUND_TILE_TOP_TRIM,
        )
        return image.subsurface(ground_rect).copy()

    def _discover_characters(self) -> list[dict]:
        characters: list[dict] = []
        if not self.sprites_root.exists():
            return characters

        for directory in sorted(path for path in self.sprites_root.iterdir() if path.is_dir()):
            character_key = directory.name.lower()
            if (
                directory.name.startswith("_")
                or character_key not in CHARACTERS
                or character_key in NON_PLAYABLE_CHARACTER_KEYS
            ):
                continue
            profile_path = self._resolve_profile_path(directory)
            if profile_path is None:
                continue

            profile = pygame.image.load(str(profile_path)).convert()
            profile.set_colorkey((0, 0, 0))
            profile = pygame.transform.smoothscale(profile, PROFILE_SIZE)
            signature = self._load_character_signature(directory)
            characters.append(
                {
                    "key": character_key,
                    "display_name": CHARACTERS[character_key]["display_name"].title(),
                    "category": CHARACTER_CATEGORIES[character_key],
                    "archetype": resolve_character_profile(
                        character_key,
                        CHARACTERS[character_key],
                    )[0].label,
                    "profile": profile,
                    "signature": signature,
                }
            )
        category_order = {category: index for index, (category, _) in enumerate(CHARACTER_GROUPS)}
        characters.sort(key=lambda character: category_order[character["category"]])
        return characters

    def _resolve_profile_path(self, directory: Path) -> Path | None:
        preferred_names = (
            f"{directory.name}.bmp",
            f"{directory.name}.png",
            f"{directory.name}.jpg",
            f"{directory.name}.jpeg",
            f"{directory.name}_profile.bmp",
            f"{directory.name}_profile.png",
            f"{directory.name}_profile.jpg",
            f"{directory.name}_profile.jpeg",
            f"{directory.name.capitalize()}.bmp",
            f"{directory.name.capitalize()}.png",
            f"{directory.name.capitalize()}.jpg",
            f"{directory.name.capitalize()}.jpeg",
            *PROFILE_FILENAME_ALIASES.get(directory.name.lower(), ()),
        )
        for filename in preferred_names:
            candidate = directory / filename
            if candidate.exists():
                return candidate

        fallback_profiles = sorted(
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() in {".bmp", ".png", ".jpg", ".jpeg"}
            and "profile" in path.stem.lower()
        )
        if fallback_profiles:
            return fallback_profiles[0]

        idle_files = (
            CHARACTERS.get(directory.name.lower(), {})
            .get("animations", {})
            .get("idle", {})
            .get("files", [])
        )
        if idle_files and Path(idle_files[0]).is_file():
            return Path(idle_files[0])

        fallback_frames = sorted(
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in {".bmp", ".png", ".jpg", ".jpeg"}
        )
        if fallback_frames:
            return fallback_frames[0]

        nested_frames = sorted(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in {".bmp", ".png", ".jpg", ".jpeg"}
        )
        return nested_frames[0] if nested_frames else None

    @staticmethod
    def _load_character_signature(directory: Path) -> pygame.Surface | None:
        signature_path = directory / "signature.png"
        if not signature_path.is_file():
            return None

        signature = pygame.image.load(str(signature_path))
        bounds = signature.get_bounding_rect(min_alpha=8)
        if not bounds.width or not bounds.height:
            raise ValueError(f"Signature image is fully transparent: {signature_path}")
        signature = signature.subsurface(bounds).copy()
        scale = min(
            SIGNATURE_MAX_SIZE[0] / signature.get_width(),
            SIGNATURE_MAX_SIZE[1] / signature.get_height(),
            1.0,
        )
        if scale < 1.0:
            signature = pygame.transform.smoothscale(
                signature,
                (
                    max(1, round(signature.get_width() * scale)),
                    max(1, round(signature.get_height() * scale)),
                ),
            )
        return signature

    def _roster_card_rect(self, visible_index: int) -> pygame.Rect:
        row, column = divmod(visible_index, ROSTER_GRID_COLUMNS)
        row_start = row * ROSTER_GRID_COLUMNS
        row_end = min(row_start + ROSTER_GRID_COLUMNS, len(self.characters))
        category_breaks = [
            index
            for index in range(row_start + 1, row_end)
            if self.characters[index]["category"] != self.characters[index - 1]["category"]
        ]
        row_count = row_end - row_start
        available_width = ROSTER_PANEL.width - ROSTER_MARGIN * 2
        card_width = (
            available_width
            - ROSTER_CARD_GAP * max(0, row_count - 1)
            - ROSTER_CATEGORY_GAP * len(category_breaks)
        ) // max(1, row_count)
        row_width = (
            row_count * card_width
            + ROSTER_CARD_GAP * max(0, row_count - 1)
            + ROSTER_CATEGORY_GAP * len(category_breaks)
        )
        breaks_before = sum(index <= visible_index for index in category_breaks)
        x = (
            ROSTER_PANEL.x
            + ROSTER_MARGIN
            + (available_width - row_width) // 2
            + column * (card_width + ROSTER_CARD_GAP)
            + breaks_before * ROSTER_CATEGORY_GAP
        )
        y = ROSTER_CARD_TOP + row * (ROSTER_CARD_HEIGHT + ROSTER_CARD_GAP)
        return pygame.Rect(x, y, card_width, ROSTER_CARD_HEIGHT)

    def _set_selected_index(self, index: int, *, defer_preview: bool = False) -> None:
        if not self.characters:
            return
        index %= len(self.characters)
        character = self.characters[index]
        changed = index != self.selected_index
        self.selected_index = index
        self.selected_character = character["key"]
        if changed and self.preview_player is not None:
            self.preview_pending_key = self.selected_character
            self.preview_pending_elapsed = 0.0
            if not defer_preview:
                self._load_preview(self.selected_character)

    def _move_selection(self, horizontal: int, vertical: int) -> None:
        if not self.characters:
            return
        row, column = divmod(self.selected_index, ROSTER_GRID_COLUMNS)
        row_count = (len(self.characters) + ROSTER_GRID_COLUMNS - 1) // ROSTER_GRID_COLUMNS
        if horizontal:
            row_start = row * ROSTER_GRID_COLUMNS
            characters_in_row = min(ROSTER_GRID_COLUMNS, len(self.characters) - row_start)
            column = (column + horizontal) % characters_in_row
        else:
            row = (row + vertical) % row_count
            characters_in_row = min(
                ROSTER_GRID_COLUMNS,
                len(self.characters) - row * ROSTER_GRID_COLUMNS,
            )
            column = min(column, characters_in_row - 1)
        self._set_selected_index(row * ROSTER_GRID_COLUMNS + column)

    def _available_preview_animations(self, character_key: str) -> list[tuple[str, str]]:
        definition = CHARACTERS[character_key]
        animation_definitions = definition["animations"]
        names: list[tuple[str, str]] = []

        def add(name: str, label: str) -> None:
            animation = animation_definitions.get(name)
            if animation is not None and animation.get("files"):
                if name not in {existing_name for existing_name, _ in names}:
                    names.append((name, label))

        add("idle", "IDLE")
        add("walk", "MOVEMENT")
        add("run", "MOVEMENT")
        for attack_name in definition.get("basic_attack_cycle", ()):
            add(attack_name, "BASIC ATTACK")
        for name, label in SPECIAL_MOVE_LABELS.items():
            add(name, label.upper())
        return names or [("idle", "IDLE")]

    def _load_preview(self, character_key: str) -> None:
        definition = CHARACTERS[character_key]
        sequence = self._available_preview_animations(character_key)
        animation_names = {name for name, _ in sequence}
        animations = load_character_animations(definition, animation_names)
        self.preview_display_scales = {}
        for name, animation in animations.items():
            scaled_frames = []
            first_frame = animation["surfaces"][0]
            self.preview_display_scales[name] = min(
                PREVIEW_MAX_SIZE[0] / first_frame.get_width(),
                PREVIEW_MAX_SIZE[1] / first_frame.get_height(),
            )
            for frame in animation["surfaces"]:
                scale = min(
                    PREVIEW_MAX_SIZE[0] / frame.get_width(),
                    PREVIEW_MAX_SIZE[1] / frame.get_height(),
                )
                size = (
                    max(1, round(frame.get_width() * scale)),
                    max(1, round(frame.get_height() * scale)),
                )
                scaled_frames.append(pygame.transform.scale(frame, size))
            animation["surfaces"] = scaled_frames

        sequence = [(name, label) for name, label in sequence if name in animations]
        if not sequence:
            return
        self.preview_sequence = [
            (
                name,
                label,
                1.35 if animations[name]["loop"] else
                max(0.35, animations[name]["frame_duration"] * len(animations[name]["surfaces"]) + 0.18),
            )
            for name, label in sequence
        ]
        self.preview_sequence_index = 0
        self.preview_elapsed = 0.0
        self.preview_label = self.preview_sequence[0][1]
        self.preview_player = AnimationPlayer(animations, self.preview_sequence[0][0])
        self.preview_character_key = character_key
        self.preview_pending_key = None
        self.preview_pending_elapsed = 0.0
        self.preview_projectiles.clear()
        self.preview_companions.clear()
        self.preview_clones.clear()

    @staticmethod
    def _load_preview_sprite_frames(
        folder: Path,
        frame_duration: float,
        loop: bool,
    ) -> list[pygame.Surface]:
        files = sorted(
            (
                path
                for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() in {".png", ".bmp"}
            ),
            key=lambda path: path.name.casefold(),
        )
        if not files:
            raise FileNotFoundError(f"No preview sprite frames found in {folder}")
        return load_character_animations(
            {
                "scale": 1,
                "animations": {
                    "preview": {
                        "files": files,
                        "frame_duration": frame_duration,
                        "loop": loop,
                    }
                },
            },
            {"preview"},
        )["preview"]["surfaces"]

    def _get_preview_projectile_frames(
        self,
        animation_name: str,
        spec: PreviewProjectileSpec,
    ) -> tuple[list[pygame.Surface], list[pygame.Surface]]:
        frames = self.preview_projectile_frames.get(spec)
        if frames is None:
            asset_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites"
            frames = (
                self._load_preview_sprite_frames(
                    asset_root.joinpath(*spec.travel_frames),
                    PreviewProjectile.TRAVEL_FRAME_DURATION,
                    True,
                ),
                self._load_preview_sprite_frames(
                    asset_root.joinpath(*spec.impact_frames),
                    PreviewProjectile.IMPACT_FRAME_DURATION,
                    False,
                )
                if spec.impact_frames is not None
                else [],
            )
            self.preview_projectile_frames[spec] = frames

        scale = self.preview_display_scales[animation_name] * spec.scale
        scaled_frames = tuple(
            [
                pygame.transform.smoothscale(
                    frame,
                    (
                        max(1, round(frame.get_width() * scale)),
                        max(1, round(frame.get_height() * scale)),
                    ),
                )
                for frame in animation_frames
            ]
            for animation_frames in frames
        )
        return scaled_frames[0], scaled_frames[1]

    def _get_preview_companion_frames(
        self,
        character_key: str,
        animation_name: str,
    ) -> tuple[list[pygame.Surface], list[pygame.Surface]]:
        cache_key = (character_key, animation_name)
        frames = self.preview_companion_frames.get(cache_key)
        if frames is None:
            spec = PREVIEW_COMPANIONS[cache_key]
            asset_root = Path(__file__).resolve().parents[2] / "assets" / "sprites"
            frames = (
                self._load_preview_sprite_frames(
                    asset_root.joinpath(*spec.create_frames),
                    PreviewCompanion.FRAME_DURATION,
                    False,
                ),
                self._load_preview_sprite_frames(
                    asset_root.joinpath(*spec.fly_frames),
                    PreviewCompanion.FRAME_DURATION,
                    True,
                ),
            )
            self.preview_companion_frames[cache_key] = frames

        scale = self.preview_display_scales[animation_name]
        scaled_frames = []
        for animation_frames in frames:
            scaled_frames.append(
                [
                    pygame.transform.smoothscale(
                        frame,
                        (
                            max(1, round(frame.get_width() * scale)),
                            max(1, round(frame.get_height() * scale)),
                        ),
                    )
                    for frame in animation_frames
                ]
            )
        return scaled_frames[0], scaled_frames[1]

    def _spawn_preview_projectile(
        self,
        character_key: str,
        animation_name: str,
        spec: PreviewProjectileSpec,
    ) -> None:
        frame = self.preview_player.current_frame
        fighter_rect = frame.get_rect(midbottom=PREVIEW_CENTER)
        start_x = fighter_rect.centerx + fighter_rect.width * spec.origin_x
        start_y = fighter_rect.bottom - fighter_rect.height * spec.origin_y
        travel_frames, impact_frames = self._get_preview_projectile_frames(
            animation_name,
            spec,
        )
        for index in range(spec.count):
            offset_y = (
                (index - (spec.count - 1) / 2) * spec.vertical_spread
                if spec.count > 1
                else 0.0
            )
            self.preview_projectiles.append(
                PreviewProjectile(
                    travel_frames,
                    impact_frames,
                    (start_x, start_y + offset_y),
                    min(INFO_PANEL.left - 32, start_x + spec.travel_distance),
                    spec.travel_duration,
                )
            )

    def _spawn_preview_companions(
        self,
        character_key: str,
        animation_name: str,
        spec: PreviewCompanionSpec,
    ) -> None:
        frame = self.preview_player.current_frame
        fighter_rect = frame.get_rect(midbottom=PREVIEW_CENTER)
        origin = (fighter_rect.centerx, fighter_rect.top + fighter_rect.height * 0.48)
        create_frames, fly_frames = self._get_preview_companion_frames(
            character_key,
            animation_name,
        )
        self.preview_companions.extend(
            PreviewCompanion(
                create_frames,
                fly_frames,
                origin,
                offset,
                spec.lifetime,
                index * math.tau / len(spec.offsets),
            )
            for index, offset in enumerate(spec.offsets)
        )

    def _spawn_preview_clones(self, animation_name: str, count: int) -> None:
        if self.preview_player is None:
            return
        frames = self.preview_player.animations[animation_name]["surfaces"]
        center = (PREVIEW_CENTER[0], PREVIEW_CENTER[1])
        offsets = tuple(
            (index - (count - 1) / 2) * 180.0
            for index in range(count)
        )
        self.preview_clones.extend(
            PreviewClone(frames, center, offset, 1.0, offset < 0)
            for offset in offsets
        )

    def _update_preview(self, dt: float) -> None:
        self.preview_forward_displacement = 0.0
        if self.preview_pending_key is not None:
            self.preview_pending_elapsed += dt
            if self.preview_pending_elapsed >= PREVIEW_SWITCH_DELAY:
                self._load_preview(self.preview_pending_key)
        if self.preview_player is None or not self.preview_sequence:
            return

        animation_name = self.preview_player.current_name
        previous_frame_index = self.preview_player.frame_index
        self.preview_player.update(dt, 1)
        character_key = self.preview_character_key
        self.preview_forward_displacement = self._preview_frame_step_distance(
            character_key,
            animation_name,
            previous_frame_index,
            self.preview_player.frame_index,
        )
        if character_key is not None:
            for projectile_spec in PREVIEW_PROJECTILES.get((character_key, animation_name), ()):
                for trigger_frame in projectile_spec.trigger_frames:
                    if previous_frame_index < trigger_frame <= self.preview_player.frame_index:
                        self._spawn_preview_projectile(character_key, animation_name, projectile_spec)
            companion_spec = PREVIEW_COMPANIONS.get((character_key, animation_name))
            if (
                companion_spec is not None
                and previous_frame_index < companion_spec.trigger_frame <= self.preview_player.frame_index
            ):
                self._spawn_preview_companions(character_key, animation_name, companion_spec)
            clone_move = PREVIEW_CLONE_MOVES.get((character_key, animation_name))
            if (
                clone_move is not None
                and previous_frame_index < clone_move[0] <= self.preview_player.frame_index
            ):
                self._spawn_preview_clones(animation_name, clone_move[1])
        self.preview_elapsed += dt
        _, _, duration = self.preview_sequence[self.preview_sequence_index]
        if self.preview_player.finished or self.preview_elapsed >= duration:
            self.preview_sequence_index = (self.preview_sequence_index + 1) % len(self.preview_sequence)
            animation_name, self.preview_label, _ = self.preview_sequence[self.preview_sequence_index]
            self.preview_player.play(animation_name)
            self.preview_elapsed = 0.0
        for projectile in self.preview_projectiles:
            projectile.update(dt)
        self.preview_projectiles = [
            projectile for projectile in self.preview_projectiles if not projectile.finished
        ]
        for companion in self.preview_companions:
            companion.update(dt)
        self.preview_companions = [
            companion for companion in self.preview_companions if not companion.finished
        ]
        for clone in self.preview_clones:
            clone.update(dt)
        self.preview_clones = [clone for clone in self.preview_clones if not clone.finished]

    @staticmethod
    def _crossed_animation_frames(
        previous_frame: int,
        current_frame: int,
        frame_count: int,
    ) -> tuple[int, ...]:
        if current_frame == previous_frame or frame_count <= 0:
            return ()
        if current_frame > previous_frame:
            return tuple(range(previous_frame + 1, current_frame + 1))
        return tuple(range(previous_frame + 1, frame_count)) + tuple(range(current_frame + 1))

    def _preview_frame_step_distance(
        self,
        character_key: str | None,
        animation_name: str,
        previous_frame: int,
        current_frame: int,
    ) -> float:
        if character_key is None or self.preview_player is None:
            return 0.0
        step = PREVIEW_FORWARD_STEPS.get((character_key, animation_name))
        if step is None:
            return 0.0
        frames = self._crossed_animation_frames(
            previous_frame,
            current_frame,
            len(self.preview_player.animations[animation_name]["surfaces"]),
        )
        if step.fixed_distance is not None:
            distance_per_step = step.fixed_distance
        else:
            movement = CHARACTERS[character_key].get("movement", {})
            distance_per_step = movement.get(step.movement_stat or "", 0.0) * step.multiplier
        return sum(distance_per_step for frame in frames if frame in step.frames)

    def _preview_forward_world_speed(self) -> float:
        if self.preview_player is None or self.preview_character_key is None:
            return 0.0
        character_key = self.preview_character_key
        animation_name = self.preview_player.current_name
        movement = CHARACTERS[character_key].get("movement", {})
        if animation_name == "walk":
            return movement.get("walk_speed", 0.0)
        if animation_name == "run":
            return movement.get("run_speed", 0.0) * 1.25

        motion = PREVIEW_FORWARD_MOTIONS.get((character_key, animation_name))
        if motion is None:
            return 0.0
        frame_index = self.preview_player.frame_index
        if motion.active_frames is not None and frame_index not in motion.active_frames:
            return 0.0
        if motion.start_frame is not None and frame_index < motion.start_frame:
            return 0.0
        if motion.fixed_speed is not None:
            return motion.fixed_speed
        return movement.get(motion.movement_stat or "", 0.0) * motion.multiplier

    def _update_ground_scroll(self, dt: float) -> None:
        target_speed = self._preview_forward_world_speed() * GROUND_SCROLL_WORLD_SCALE

        response = 1.0 - math.exp(-dt / GROUND_SCROLL_RESPONSE)
        self.ground_scroll_speed += (target_speed - self.ground_scroll_speed) * response
        frame_scroll_distance = self.preview_forward_displacement * GROUND_SCROLL_WORLD_SCALE
        self.ground_scroll_offset = (
            self.ground_scroll_offset + self.ground_scroll_speed * dt + frame_scroll_distance
        ) % self.ground_tile.get_width()
        self.far_sky_scroll_offset = (
            self.far_sky_scroll_offset
            + (self.ground_scroll_speed * dt + frame_scroll_distance) * FAR_SKY_PARALLAX
        ) % self.far_sky_tile.get_width()
        self.skyline_scroll_offset = (
            self.skyline_scroll_offset
            + (self.ground_scroll_speed * dt + frame_scroll_distance) * SKYLINE_PARALLAX
        ) % self.skyline_tile.get_width()
        self.slow_particle_scroll_offset = (
            self.slow_particle_scroll_offset
            + SLOW_PARTICLE_DRIFT_SPEED * dt
            + (self.ground_scroll_speed * dt + frame_scroll_distance) * SLOW_PARTICLE_PARALLAX
        ) % self.slow_particle_tile.get_width()
        self.fast_particle_scroll_offset = (
            self.fast_particle_scroll_offset
            + FAST_PARTICLE_DRIFT_SPEED * dt
            + (self.ground_scroll_speed * dt + frame_scroll_distance) * FAST_PARTICLE_PARALLAX
        ) % self.fast_particle_tile.get_width()

    def update(
        self,
        dt: float,
        mouse_pos: tuple[int, int] | None = None,
        mouse_click: tuple[int, int] | None = None,
        mouse_wheel_y: int = 0,
    ) -> None:
        self._elapsed_time += dt
        self._update_preview(dt)
        self._update_ground_scroll(dt)
        keys = pygame.key.get_pressed()
        up_pressed = KEY_BINDINGS.is_pressed("move_up", keys)
        down_pressed = KEY_BINDINGS.is_pressed("move_down", keys)
        left_pressed = KEY_BINDINGS.is_pressed("move_left", keys)
        right_pressed = KEY_BINDINGS.is_pressed("move_right", keys)
        confirm_pressed = KEY_BINDINGS.is_pressed("menu_confirm", keys)
        back_pressed = KEY_BINDINGS.is_pressed("back_pause", keys)
        toggle_pressed = KEY_BINDINGS.is_pressed("toggle_opponent", keys)
        tab_pressed = keys[pygame.K_TAB]

        back_clicked = mouse_click is not None and BACK_BUTTON.collidepoint(mouse_click)
        if back_clicked or (back_pressed and not self._back_pressed):
            self.back_requested = True

        if self.characters:
            if tab_pressed and not self._tab_pressed:
                self.moveset_focused = not self.moveset_focused

            moving_roster = (
                (up_pressed and not self._up_pressed)
                or (down_pressed and not self._down_pressed)
                or (left_pressed and not self._left_pressed)
                or (right_pressed and not self._right_pressed)
            )
            if self.moveset_focused and moving_roster:
                self.moveset_focused = False

            if not self.moveset_focused and up_pressed and not self._up_pressed:
                self._move_selection(0, -1)
            elif not self.moveset_focused and down_pressed and not self._down_pressed:
                self._move_selection(0, 1)
            elif not self.moveset_focused and left_pressed and not self._left_pressed:
                self._move_selection(-1, 0)
            elif not self.moveset_focused and right_pressed and not self._right_pressed:
                self._move_selection(1, 0)

            self.moveset_hovered = (
                mouse_pos is not None
                and self.moveset_toggle_rect.collidepoint(mouse_pos)
            )
            if mouse_pos is not None:
                for character_index in range(len(self.characters)):
                    if self._roster_card_rect(character_index).collidepoint(mouse_pos):
                        self.moveset_focused = False
                        self._set_selected_index(character_index, defer_preview=True)
                        break

            if mouse_click is not None and not back_clicked:
                if CONFIRM_BUTTON.collidepoint(mouse_click):
                    self.selection_confirmed = bool(self.selected_opponents) if self.opponent_selection else True
                elif self.moveset_toggle_rect.collidepoint(mouse_click):
                    self.moveset_expanded = not self.moveset_expanded
                    self.moveset_focused = True
                else:
                    for character_index in range(len(self.characters)):
                        if self._roster_card_rect(character_index).collidepoint(mouse_click):
                            self.moveset_focused = False
                            self._set_selected_index(character_index)
                            if self.opponent_selection:
                                self._toggle_opponent(self.selected_character)
                            elif (
                                self._last_clicked_character == self.selected_character
                                and self._elapsed_time - self._last_click_time <= 0.35
                            ):
                                self.selection_confirmed = True
                            else:
                                self._last_clicked_character = self.selected_character
                                self._last_click_time = self._elapsed_time
                            break

            if confirm_pressed and not self._confirm_pressed:
                if self.moveset_focused:
                    self.moveset_expanded = not self.moveset_expanded
                elif self.opponent_selection:
                    self.selection_confirmed = bool(self.selected_opponents)
                else:
                    self.selection_confirmed = True
            if self.opponent_selection and toggle_pressed and not self._toggle_pressed:
                self._toggle_opponent(self.selected_character)

        self._up_pressed = up_pressed
        self._down_pressed = down_pressed
        self._left_pressed = left_pressed
        self._right_pressed = right_pressed
        self._tab_pressed = tab_pressed
        self._back_pressed = back_pressed
        self._confirm_pressed = confirm_pressed
        self._toggle_pressed = toggle_pressed

    def _toggle_opponent(self, character: str | None) -> None:
        if character is None:
            return
        if character in self.selected_opponents:
            self.selected_opponents.remove(character)
        else:
            self.selected_opponents.add(character)

    @staticmethod
    def _pretty_move_name(name: str) -> str:
        if name in SPECIAL_MOVE_LABELS:
            return SPECIAL_MOVE_LABELS[name]
        return name.replace("_", " ").title()

    def _move_list(self, character_key: str) -> list[tuple[str, str]]:
        definition = CHARACTERS[character_key]
        animations = definition["animations"]
        moves: list[tuple[str, str]] = []
        basic_cycle = [
            name
            for name in definition.get("basic_attack_cycle", ())
            if name in animations and animations[name].get("files")
        ]
        if basic_cycle:
            moves.append(("BASIC", " / ".join(self._pretty_move_name(name) for name in basic_cycle[:3])))
        for name, label in SPECIAL_MOVE_LABELS.items():
            animation = animations.get(name)
            if animation is not None and animation.get("files"):
                moves.append(("SPECIAL", label))
        return moves[:5]

    def _draw_panel(self, surface: pygame.Surface, rect: pygame.Rect, fill: tuple[int, int, int, int]) -> None:
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill(fill)
        surface.blit(panel, rect)
        pygame.draw.rect(surface, (157, 177, 199), rect, 1, border_radius=14)

    def _draw_background(self, surface: pygame.Surface) -> None:
        surface.fill((0, 0, 0))
        for tile, offset in (
            (self.far_sky_tile, self.far_sky_scroll_offset),
            (self.skyline_tile, self.skyline_scroll_offset),
            (self.slow_particle_tile, self.slow_particle_scroll_offset),
            (self.fast_particle_tile, self.fast_particle_scroll_offset),
        ):
            tile_width = tile.get_width()
            tile_x = -(round(offset) % tile_width)
            while tile_x < SCREEN_WIDTH:
                surface.blit(tile, (tile_x, 0))
                tile_x += tile_width

        tile_width = self.ground_tile.get_width()
        tile_x = -(round(self.ground_scroll_offset) % tile_width)
        while tile_x < SCREEN_WIDTH:
            surface.blit(self.ground_tile, (tile_x, SELECTION_GROUND_Y))
            tile_x += tile_width

    def _draw_header(self, surface: pygame.Surface) -> None:
        title_text = "CHOOSE YOUR OPPONENTS" if self.opponent_selection else "CHOOSE YOUR FIGHTER"
        title_shadow = self.title_font.render(title_text, True, (0, 0, 0))
        title = self.title_font.render(title_text, True, (247, 244, 235))
        surface.blit(title_shadow, (62, 42))
        surface.blit(title, (58, 38))

        mode = "OPPONENT SELECT" if self.opponent_selection else (
            "STAGE MODE" if self.stage_mode else "TEST MODE" if self.test_mode else "PLAY MODE"
        )
        mode_surface = self.badge_font.render(mode, True, (255, 214, 139))
        surface.blit(mode_surface, mode_surface.get_rect(midright=(CONFIRM_BUTTON.left - 22, 76)))

        pygame.draw.rect(surface, (28, 43, 58), BACK_BUTTON, border_radius=12)
        pygame.draw.rect(surface, (119, 153, 177), BACK_BUTTON, 2, border_radius=12)
        back_button = self.button_font.render("BACK", True, (236, 242, 247))
        surface.blit(back_button, back_button.get_rect(center=BACK_BUTTON.center))

        if self.opponent_selection:
            button_text = f"START BATTLE  {len(self.selected_opponents)}"
            button_enabled = bool(self.selected_opponents)
        elif self.test_mode:
            button_text = "PRACTICE"
            button_enabled = True
        elif self.stage_mode:
            button_text = "SELECT FIGHTER"
            button_enabled = True
        else:
            button_text = "CONFIRM FIGHTER"
            button_enabled = True
        button_fill = (131, 76, 41) if button_enabled else (36, 46, 58)
        button_outline = (255, 193, 99) if button_enabled else (81, 99, 117)
        button_text_color = (255, 247, 224) if button_enabled else (142, 158, 174)
        pygame.draw.rect(surface, button_fill, CONFIRM_BUTTON, border_radius=12)
        pygame.draw.rect(surface, button_outline, CONFIRM_BUTTON, 2, border_radius=12)
        button = self.button_font.render(button_text, True, button_text_color)
        surface.blit(button, button.get_rect(center=CONFIRM_BUTTON.center))

    def _draw_stat_bar(
        self,
        surface: pygame.Surface,
        label: str,
        value: int,
        maximum: int,
        rect: pygame.Rect,
        color: tuple[int, int, int],
    ) -> None:
        label_surface = self.small_font.render(f"{label}  {value}", True, (230, 236, 240))
        surface.blit(label_surface, (rect.x, rect.y - 24))
        pygame.draw.rect(surface, (8, 14, 22), rect, border_radius=6)
        fill_width = 0 if maximum <= 0 else round(rect.width * max(0, min(value, maximum)) / maximum)
        if fill_width:
            pygame.draw.rect(
                surface,
                color,
                pygame.Rect(rect.x, rect.y, fill_width, rect.height),
                border_radius=6,
            )

    def _draw_character_info(self, surface: pygame.Surface, character: dict) -> None:
        panel = INFO_PANEL.copy()
        panel.height = INFO_PANEL.height if self.moveset_expanded else INFO_COLLAPSED_HEIGHT
        self._draw_panel(surface, panel, (9, 17, 29, 238))

        category = f"{character['category'].upper()}  |  {character['archetype'].upper()}"
        category_surface = self.badge_font.render(category, True, (255, 209, 129))
        surface.blit(category_surface, (panel.x + 24, panel.y + 20))
        selected_index = self.selected_index + 1
        roster_position = self.small_font.render(
            f"FIGHTER  {selected_index:02d} / {len(self.characters):02d}",
            True,
            (148, 174, 196),
        )
        surface.blit(roster_position, roster_position.get_rect(topright=(panel.right - 24, panel.y + 20)))

        signature = character.get("signature")
        if signature is not None:
            signature_rect = signature.get_rect(
                midleft=(panel.x + 24, panel.y + 82),
            )
            surface.blit(signature, signature_rect)
        else:
            name = character["display_name"].upper()
            name_font = self.name_font
            if name_font.size(name)[0] > panel.width - 48:
                name_font = pygame.font.SysFont("bahnschrift", 38, bold=True)
            name_surface = name_font.render(name, True, (250, 248, 241))
            surface.blit(name_surface, (panel.x + 24, panel.y + 52))
        pygame.draw.line(
            surface,
            (225, 157, 75),
            (panel.x + 24, panel.y + 116),
            (panel.right - 24, panel.y + 116),
            2,
        )

        definition = CHARACTERS[character["key"]]
        _, stats, movement = resolve_character_profile(character["key"], definition)
        max_health = int(stats.get("max_health", 0))
        max_mana = int(stats.get("max_mana", 0))
        stat_width = 350
        self._draw_stat_bar(
            surface,
            "HP",
            max_health,
            max_health,
            pygame.Rect(panel.x + 28, panel.y + 158, stat_width, 16),
            (217, 79, 78),
        )
        self._draw_stat_bar(
            surface,
            "MP",
            max_mana,
            max_mana,
            pygame.Rect(panel.x + 28, panel.y + 218, stat_width, 16),
            (77, 147, 229),
        )

        walk_speed = round(movement.get("walk_speed", 0))
        run_speed = round(movement.get("run_speed", 0))
        mobility_x = panel.x + 420
        mobility_y = panel.y + 136
        speed_label = self.small_font.render("MOBILITY", True, (148, 174, 196))
        surface.blit(speed_label, (mobility_x, mobility_y))
        speed_text = self.body_font.render(
            f"WALK  {walk_speed}     RUN  {run_speed}",
            True,
            (225, 232, 237),
        )
        surface.blit(speed_text, (mobility_x, mobility_y + 28))
        preview = self.badge_font.render(
            f"PREVIEW: {self.preview_label}",
            True,
            (255, 209, 129),
        )
        surface.blit(preview, (mobility_x, mobility_y + 70))

        self.moveset_toggle_rect = pygame.Rect(
            panel.x + 24,
            panel.y + 256,
            panel.width - 48,
            44,
        )
        toggle_outline = (255, 190, 92) if self.moveset_focused or self.moveset_hovered else (82, 106, 130)
        toggle_fill = (40, 35, 31) if self.moveset_focused or self.moveset_hovered else (17, 27, 40)
        pygame.draw.rect(surface, toggle_fill, self.moveset_toggle_rect, border_radius=8)
        pygame.draw.rect(surface, toggle_outline, self.moveset_toggle_rect, 2, border_radius=8)

        heading = self.section_font.render("MOVESET", True, (250, 248, 241))
        surface.blit(heading, (self.moveset_toggle_rect.x + 18, self.moveset_toggle_rect.y + 7))
        toggle_hint = self.small_font.render(
            f"CLICK OR TAB + {KEY_BINDINGS.label('menu_confirm')}",
            True,
            (167, 188, 207),
        )
        surface.blit(
            toggle_hint,
            toggle_hint.get_rect(midright=(self.moveset_toggle_rect.right - 150, self.moveset_toggle_rect.centery)),
        )
        toggle_text = self.badge_font.render(
            "COLLAPSE  -" if self.moveset_expanded else "EXPAND  +",
            True,
            (255, 232, 193),
        )
        surface.blit(
            toggle_text,
            toggle_text.get_rect(midright=(self.moveset_toggle_rect.right - 16, self.moveset_toggle_rect.centery)),
        )

        if not self.moveset_expanded:
            return
        moves = self._move_list(character["key"])
        if not moves:
            empty = self.body_font.render("No move animations listed.", True, (188, 202, 216))
            surface.blit(empty, (panel.x + 30, self.moveset_toggle_rect.bottom + 14))
            return
        y = self.moveset_toggle_rect.bottom + 8
        for move_type, move_name in moves:
            row = pygame.Rect(panel.x + 24, y, panel.width - 48, 36)
            pygame.draw.line(surface, (49, 67, 83), row.bottomleft, row.bottomright, 1)
            tag = self.badge_font.render(
                move_type,
                True,
                (255, 209, 129) if move_type == "SPECIAL" else (131, 202, 228),
            )
            surface.blit(tag, (row.x + 18, row.y + 8))
            name_surface = self.body_font.render(move_name, True, (232, 237, 241))
            surface.blit(name_surface, (row.x + 146, row.y + 4))
            y += 40

    def _draw_preview(self, surface: pygame.Surface) -> None:
        if self.preview_player is None:
            return
        for projectile in self.preview_projectiles:
            projectile.draw(surface)
        for companion in self.preview_companions:
            companion.draw(surface)
        for clone in self.preview_clones:
            clone.draw(surface)
        frame = self.preview_player.current_frame
        surface.blit(frame, frame.get_rect(midbottom=PREVIEW_CENTER))

    def _draw_roster(self, surface: pygame.Surface) -> None:
        self._draw_panel(surface, ROSTER_PANEL, (6, 12, 21, 239))
        section = self.badge_font.render(
            f"FIGHTER ROSTER  /  {len(self.characters)}",
            True,
            (240, 223, 195),
        )
        surface.blit(section, (ROSTER_PANEL.x + 16, ROSTER_PANEL.y + 8))
        controls = self.small_font.render(
            f"{KEY_BINDINGS.label('move_left')}/{KEY_BINDINGS.label('move_right')}/"
            f"{KEY_BINDINGS.label('move_up')}/{KEY_BINDINGS.label('move_down')} browse   "
            f"{KEY_BINDINGS.label('menu_confirm')} confirm   "
            f"{KEY_BINDINGS.label('back_pause')} back",
            True,
            (167, 188, 207),
        )
        surface.blit(controls, controls.get_rect(midright=(ROSTER_PANEL.right - 16, ROSTER_PANEL.y + 16)))

        legend_x = ROSTER_PANEL.x + 16
        legend_y = ROSTER_PANEL.y + 30
        legend_font = pygame.font.SysFont("segoeui", 12, bold=True)
        for category in self.categories:
            accent = CATEGORY_ACCENT_BY_NAME[category]
            pygame.draw.rect(surface, accent, pygame.Rect(legend_x, legend_y + 3, 8, 8), border_radius=2)
            label = legend_font.render(category.upper(), True, accent)
            surface.blit(label, (legend_x + 12, legend_y))
            legend_x += label.get_width() + 28

        pulse = self._selection_glow_strength()
        if self.characters:
            self._draw_selection_glow(
                surface,
                self._roster_card_rect(self.selected_index),
                pulse,
            )
        for character_index, character in enumerate(self.characters):
            rect = self._roster_card_rect(character_index)
            selected = character_index == self.selected_index
            chosen = character["key"] in self.selected_opponents
            accent = CATEGORY_ACCENT_BY_NAME[character["category"]]
            fill = (74, 47, 35) if selected else (25, 32, 42)
            if selected:
                outline = (255, round(180 + pulse * 65), round(72 + pulse * 64))
            else:
                outline = (105, 210, 148) if chosen else (62, 76, 91)
            pygame.draw.rect(surface, fill, rect, border_radius=6)
            pygame.draw.rect(surface, accent, pygame.Rect(rect.x, rect.y, rect.width, 4), border_radius=2)
            outline_width = 2 + round(pulse * 2) if selected else 3 if chosen else 1
            pygame.draw.rect(surface, outline, rect, outline_width, border_radius=6)
            image_rect = character["profile"].get_rect(
                center=rect.center,
            )
            surface.blit(character["profile"], image_rect)
            if chosen:
                pygame.draw.circle(surface, (169, 240, 190), (rect.right - 8, rect.y + 11), 4)

    def _selection_glow_strength(self) -> float:
        return (math.sin(math.tau * self._elapsed_time / SELECTION_GLOW_PERIOD) + 1.0) / 2.0

    @staticmethod
    def _draw_selection_glow(
        surface: pygame.Surface,
        rect: pygame.Rect,
        strength: float,
    ) -> None:
        padding = 10
        glow = pygame.Surface(
            (rect.width + padding * 2, rect.height + padding * 2),
            pygame.SRCALPHA,
        )
        base_rect = pygame.Rect(padding, padding, rect.width, rect.height)
        glow_layers = (
            (round(10 + strength * 4), 18 + round(strength * 18)),
            (round(6 + strength * 2), 30 + round(strength * 28)),
            (round(2 + strength * 2), 48 + round(strength * 42)),
        )
        for expansion, alpha in glow_layers:
            pygame.draw.rect(
                glow,
                (255, 174, 78, alpha),
                base_rect.inflate(expansion, expansion),
                2,
                border_radius=9,
            )
        surface.blit(glow, (rect.x - padding, rect.y - padding))

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        self._draw_header(surface)
        if not self.characters:
            empty = self.subtitle_font.render(
                "No playable fighters found in assets\\sprites\\characters",
                True,
                TEXT_COLOR,
            )
            surface.blit(empty, empty.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)))
            return

        character = self.characters[self.selected_index]
        self._draw_preview(surface)
        self._draw_character_info(surface, character)
        self._draw_roster(surface)
