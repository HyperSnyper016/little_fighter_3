SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080
GROUND_Y = 780
LANE_MIN_Y = 36
LANE_MAX_Y = SCREEN_HEIGHT - GROUND_Y
FPS = 60
VERSION = "v0.18.0"

HENRY_FLUTE_SEQUENCE_DURATION = 1.805  # Combined duration of flute_1.wav, flute_2.wav, and flute_3.wav.
HEAVY_BOX_ITEM_ID = "throwables/heavy_box"
HEAVY_ITEM_IDS = frozenset({HEAVY_BOX_ITEM_ID})
JUMP_LAUNCH_SPEED_MULTIPLIER = 1.1
JUMP_GRAVITY_MULTIPLIER = 1.6
JUMP_LANDING_RECOVERY_DURATION = 0.06
HEAVY_ITEM_ANCHOR_KEYS = {
    "lift_heavy": "heavy_carry_walk",
    "heavy_carry_walk": "heavy_carry_walk",
    "heavy_carry_sprint": "heavy_carry_sprint",
    "throw_heavy": "heavy_carry_throw",
}
HEAVY_ITEM_FALLBACK_ANCHOR = (0.50, 0.18)

BG_COLOR = (24, 28, 36)
GROUND_COLOR = (69, 78, 92)
LANE_COLOR = (95, 108, 126)
TEXT_COLOR = (236, 239, 244)
SHADOW_COLOR = (0, 0, 0, 100)
