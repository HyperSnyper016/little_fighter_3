from __future__ import annotations

from functools import lru_cache
import math

import pygame

from game.constants import GROUND_Y


_ORB_PIXELS = (
    "....o....",
    "..oogoo..",
    ".oogcgoo.",
    ".ogcccg..",
    "ogccHcgo.",
    ".ogcccg..",
    ".oogcgoo.",
    "..oogoo..",
    "....o....",
)
_ORB_COLORS = {
    "o": (17, 83, 68),
    "g": (39, 199, 119),
    "c": (60, 235, 202),
    "H": (204, 255, 238),
}


@lru_cache(maxsize=3)
def xp_orb_surface(pulse: int = 0) -> pygame.Surface:
    """Build one of three cached, original pixel-art XP orb frames."""
    pulse %= 3
    surface = pygame.Surface((24, 24), pygame.SRCALPHA)
    glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.circle(glow, (48, 255, 201, 22 + pulse * 8), (12, 12), 11 + pulse)
    pygame.draw.circle(glow, (61, 251, 219, 28 + pulse * 6), (12, 12), 8 + pulse)
    surface.blit(glow, (0, 0))

    pixel_size = 2
    offset = 3
    for row, pixels in enumerate(_ORB_PIXELS):
        for column, pixel in enumerate(pixels):
            color = _ORB_COLORS.get(pixel)
            if color is not None:
                pygame.draw.rect(
                    surface,
                    color,
                    (
                        offset + column * pixel_size,
                        offset + row * pixel_size,
                        pixel_size,
                        pixel_size,
                    ),
                )
    return surface


class XPOrb:
    def __init__(self, x: float, lane_y: float, xp_value: int) -> None:
        self.x = float(x)
        self.lane_y = float(lane_y)
        self.xp_value = max(1, int(xp_value))
        self.elapsed = 0.0
        self.bob_phase = math.fmod(abs(self.x) * 0.013 + abs(self.lane_y) * 0.071, math.tau)

    def overlaps(
        self,
        fighter: object,
        pickup_range_multiplier: float = 1.0,
    ) -> bool:
        multiplier = max(1.0, pickup_range_multiplier)
        return (
            abs(self.x - fighter.x) <= 30.0 * multiplier
            and abs(self.lane_y - fighter.lane_y) <= 28.0 * multiplier
        )

    def update(self, dt: float) -> None:
        self.elapsed = (self.elapsed + max(0.0, dt)) % (math.tau * 1000.0)

    @property
    def bob_offset(self) -> float:
        return math.sin(self.elapsed * 2.6 + self.bob_phase) * 5.0

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        pulse = int((self.elapsed % 1.2) / 0.4)
        frame = xp_orb_surface(pulse)
        center = (
            round(self.x - camera_x),
            round(GROUND_Y + self.lane_y - 34.0 + self.bob_offset),
        )
        surface.blit(frame, frame.get_rect(center=center))
