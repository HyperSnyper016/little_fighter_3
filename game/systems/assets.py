from __future__ import annotations

from pathlib import Path

import pygame


def _placeholder_surface(size: tuple[int, int], label: str) -> pygame.Surface:
    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill((120, 72, 72))
    pygame.draw.rect(surface, (250, 218, 94), surface.get_rect(), 2)
    font = pygame.font.Font(None, 18)
    text = font.render(label, True, (255, 255, 255))
    surface.blit(text, (6, 6))
    return surface


def _load_animation_frames(animation_name: str, animation: dict, scale: int) -> list[pygame.Surface]:
    surfaces: list[pygame.Surface] = []

    for raw_path in animation.get("files", []):
        frame_path = Path(raw_path)
        if not frame_path.exists():
            surfaces.append(_placeholder_surface((64 * scale, 64 * scale), animation_name))
            continue

        frame = pygame.image.load(str(frame_path)).convert()
        frame.set_colorkey((0, 0, 0))
        width, height = frame.get_size()
        surfaces.append(pygame.transform.scale(frame, (width * scale, height * scale)))

    if not surfaces:
        surfaces.append(_placeholder_surface((64 * scale, 64 * scale), animation_name))

    return surfaces


def load_character_sheet(definition: dict) -> dict[str, dict]:
    scale = definition["scale"]
    animations = {}

    for name, animation in definition["animations"].items():
        animations[name] = {
            "surfaces": _load_animation_frames(name, animation, scale),
            "frame_duration": animation["frame_duration"],
            "loop": animation["loop"],
        }

    return animations
