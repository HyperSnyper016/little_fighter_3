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


def _load_sheet_frame(sheet_path: Path, frame_rect: tuple[int, int, int, int], scale: int, animation_name: str) -> pygame.Surface:
    if not sheet_path.exists():
        return _placeholder_surface((64 * scale, 64 * scale), animation_name)

    sheet = pygame.image.load(str(sheet_path)).convert()
    sheet.set_colorkey((0, 0, 0))
    x, y, width, height = frame_rect
    frame = pygame.Surface((width, height)).convert()
    frame.blit(sheet, (0, 0), pygame.Rect(x, y, width, height))
    frame.set_colorkey((0, 0, 0))
    return pygame.transform.scale(frame, (width * scale, height * scale))


def _trim_small_components(surface: pygame.Surface, max_component_size: int) -> pygame.Surface:
    width, height = surface.get_size()
    visited = [[False for _ in range(height)] for _ in range(width)]
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1))

    for start_x in range(width):
        for start_y in range(height):
            if visited[start_x][start_y]:
                continue

            pixel = surface.get_at((start_x, start_y))
            if pixel.r == 0 and pixel.g == 0 and pixel.b == 0:
                visited[start_x][start_y] = True
                continue

            stack = [(start_x, start_y)]
            component: list[tuple[int, int]] = []
            visited[start_x][start_y] = True

            while stack:
                x, y = stack.pop()
                component.append((x, y))
                for dx, dy in directions:
                    nx = x + dx
                    ny = y + dy
                    if nx < 0 or ny < 0 or nx >= width or ny >= height:
                        continue
                    if visited[nx][ny]:
                        continue
                    neighbor = surface.get_at((nx, ny))
                    if neighbor.r == 0 and neighbor.g == 0 and neighbor.b == 0:
                        visited[nx][ny] = True
                        continue
                    visited[nx][ny] = True
                    stack.append((nx, ny))

            if len(component) <= max_component_size:
                for x, y in component:
                    surface.set_at((x, y), (0, 0, 0))

    return surface


def _load_animation_frames(animation_name: str, animation: dict, scale: int) -> list[pygame.Surface]:
    surfaces: list[pygame.Surface] = []

    if "sheet" in animation and "frames" in animation:
        sheet_path = Path(animation["sheet"])
        for frame_rect in animation["frames"]:
            surfaces.append(_load_sheet_frame(sheet_path, tuple(frame_rect), scale, animation_name))
        if surfaces:
            return surfaces

    for raw_path in animation.get("files", []):
        frame_path = Path(raw_path)
        if not frame_path.exists():
            surfaces.append(_placeholder_surface((64 * scale, 64 * scale), animation_name))
            continue

        frame = pygame.image.load(str(frame_path)).convert()
        if animation.get("trim_small_components"):
            frame = _trim_small_components(frame, int(animation["trim_small_components"]))
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
