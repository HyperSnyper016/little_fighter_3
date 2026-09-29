from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame

from game.constants import BG_COLOR, GROUND_Y, SCREEN_HEIGHT, SCREEN_WIDTH


def _load_bitmap(path: Path, *, colorkey: tuple[int, int, int] | None = None) -> pygame.Surface | None:
    if not path.exists():
        return None

    image = pygame.image.load(str(path)).convert()
    if colorkey is not None:
        image.set_colorkey(colorkey)
    return image


def _load_city_image(path: Path, *, colorkey: tuple[int, int, int] | None = None) -> pygame.Surface:
    image = pygame.image.load(str(path)).convert_alpha()
    if colorkey is not None:
        image.set_colorkey(colorkey)
    return image


def _scale_width(surface: pygame.Surface, width: int) -> pygame.Surface:
    scaled_height = max(1, int(surface.get_height() * (width / surface.get_width())))
    return pygame.transform.smoothscale(surface, (width, scaled_height))


@dataclass
class StageLayer:
    surface: pygame.Surface
    y: int
    parallax: float
    repeat_x: bool = True


class ForestStage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.world_width = SCREEN_WIDTH * 3
        self.play_min_x = 80.0
        self.play_max_x = self.world_width - 80.0
        self.floor_top = GROUND_Y
        self.layers = self._build_layers()
        self.platform_surface, self.platform_y = self._build_platform()

    def _fallback_surface(self) -> pygame.Surface:
        background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        background.fill(BG_COLOR)
        horizon_y = GROUND_Y - 120
        pygame.draw.rect(background, (54, 90, 122), (0, 0, SCREEN_WIDTH, horizon_y))
        pygame.draw.rect(background, (84, 96, 84), (0, horizon_y, SCREEN_WIDTH, GROUND_Y - horizon_y))
        pygame.draw.rect(background, (105, 111, 118), (0, GROUND_Y, SCREEN_WIDTH, SCREEN_HEIGHT - GROUND_Y))
        pygame.draw.line(background, (180, 184, 188), (0, GROUND_Y + 26), (SCREEN_WIDTH, GROUND_Y + 26), 3)
        return background

    def _build_layers(self) -> list[StageLayer]:
        if not self.root.exists():
            return [StageLayer(self._fallback_surface(), 0, 0.0, False)]

        layers: list[StageLayer] = []

        sky = _load_bitmap(self.root / "background.bmp")
        if sky is not None:
            sky = pygame.transform.smoothscale(sky, (SCREEN_WIDTH, self.floor_top))
            layers.append(StageLayer(sky, 0, 0.02, False))

        moon = _load_bitmap(self.root / "moon.bmp", colorkey=(0, 0, 0))
        if moon is not None:
            moon = pygame.transform.smoothscale(moon, (140, 140))
            layers.append(StageLayer(moon, 48, 0.05, False))

        tree_line = _load_bitmap(self.root / "foreground1.bmp", colorkey=(0, 0, 0))
        if tree_line is not None:
            tree_line = _scale_width(tree_line, max(SCREEN_WIDTH, int(SCREEN_WIDTH * 0.9)))
            layers.append(StageLayer(tree_line, max(72, self.floor_top - 96), 0.10))

        for file_name, y_offset, parallax in (
            ("forestm4.bmp", 210, 0.16),
            ("forestm3.bmp", 180, 0.20),
            ("forestm2.bmp", 150, 0.26),
            ("foreground2.bmp", 120, 0.32),
        ):
            surface = _load_bitmap(self.root / file_name, colorkey=(0, 0, 0))
            if surface is None:
                continue
            layers.append(StageLayer(surface, max(40, self.floor_top - y_offset), parallax))

        return layers or [StageLayer(self._fallback_surface(), 0, 0.0, False)]

    def _build_platform(self) -> tuple[pygame.Surface, int]:
        segment_names = ["land1.bmp", "floor1.bmp", "floor2.bmp", "land4.bmp"]
        segments: list[pygame.Surface] = []
        for name in segment_names:
            surface = _load_bitmap(self.root / name, colorkey=(0, 0, 0))
            if surface is not None:
                segments.append(surface)

        if not segments:
            fallback = pygame.Surface((self.world_width, max(1, SCREEN_HEIGHT - self.floor_top)))
            fallback.fill((96, 104, 84))
            return fallback, self.floor_top

        floor_height = max(1, SCREEN_HEIGHT - self.floor_top)
        canvas = pygame.Surface((self.world_width, floor_height), pygame.SRCALPHA)

        total_width = sum(segment.get_width() for segment in segments)
        strip_height = max(segment.get_height() for segment in segments)
        strip = pygame.Surface((total_width, strip_height), pygame.SRCALPHA)
        x = 0
        for segment in segments:
            y = strip_height - segment.get_height()
            strip.blit(segment, (x, y))
            x += segment.get_width()

        stretched = pygame.transform.smoothscale(strip, (self.world_width, floor_height))
        canvas.blit(stretched, (0, 0))
        return canvas, self.floor_top

    def _camera_x(self, focus_x: float) -> float:
        max_camera = max(0, self.world_width - SCREEN_WIDTH)
        return max(0.0, min(max_camera, focus_x - (SCREEN_WIDTH / 2)))

    def camera_x(self, focus_x: float) -> float:
        return self._camera_x(focus_x)

    def draw(self, surface: pygame.Surface, focus_x: float) -> None:
        camera_x = self.camera_x(focus_x)
        surface.fill(BG_COLOR)

        for layer in self.layers:
            if layer.repeat_x:
                width = layer.surface.get_width()
                offset = -int(camera_x * layer.parallax) % width
                draw_x = offset - width
                while draw_x < SCREEN_WIDTH:
                    surface.blit(layer.surface, (draw_x, layer.y))
                    draw_x += width
            else:
                draw_x = -int(camera_x * layer.parallax)
                surface.blit(layer.surface, (draw_x, layer.y))

        platform_offset = int(camera_x)
        visible = pygame.Rect(platform_offset, 0, SCREEN_WIDTH, self.platform_surface.get_height())
        surface.blit(self.platform_surface, (0, self.platform_y), visible)


class CityStage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.world_width = SCREEN_WIDTH * 3
        self.play_min_x = 80.0
        self.play_max_x = self.world_width - 80.0
        self.floor_top = GROUND_Y
        self.layers = self._build_layers()
        self.platform_surface = self._build_platform()

    def _build_layers(self) -> list[StageLayer]:
        max_camera = self.world_width - SCREEN_WIDTH
        backdrop_parallax = 0.015
        backdrop_width = SCREEN_WIDTH + round(max_camera * backdrop_parallax)
        backdrop = pygame.transform.smoothscale(
            _load_city_image(self.root / "backdrop.jpg"),
            (backdrop_width, self.floor_top),
        )
        layer_specs = (
            ("near_scenery.png", 0.03, None, 1.0),
            ("foreground elenment 1.png", 0.06, (0, 0, 0), 0.75),
            ("foreground elenment 3.png", 0.10, None, 0.75),
            ("foreground elenment 2.png", 0.14, None, 0.75),
        )
        layers = [StageLayer(backdrop, 0, backdrop_parallax, False)]

        for file_name, parallax, colorkey, scale in layer_specs:
            image = _load_city_image(self.root / file_name, colorkey=colorkey)
            layer_width = SCREEN_WIDTH + round(max_camera * parallax)
            image = pygame.transform.smoothscale(image, (layer_width, self.floor_top))
            y = 0
            if scale < 1.0:
                scaled_size = (round(layer_width * scale), round(self.floor_top * scale))
                scaled = pygame.transform.smoothscale(image, scaled_size)
                image = pygame.Surface((layer_width, self.floor_top), pygame.SRCALPHA)
                image.blit(
                    scaled,
                    ((layer_width - scaled_size[0]) // 2, self.floor_top - scaled_size[1]),
                )
            elif file_name == "near_scenery.png":
                y = self.floor_top - image.get_bounding_rect(min_alpha=8).bottom
            layers.append(StageLayer(image, y, parallax, False))

        return layers

    def _build_platform(self) -> pygame.Surface:
        ground = _load_city_image(self.root / "ground.jpg")
        floor_height = max(1, SCREEN_HEIGHT - self.floor_top)
        tile_width = max(1, round(floor_height * ground.get_width() / ground.get_height()))
        tile = pygame.transform.smoothscale(ground, (tile_width, floor_height))
        platform = pygame.Surface((self.world_width, floor_height))
        for x in range(0, self.world_width, tile_width):
            platform.blit(tile, (x, 0))
        return platform

    def camera_x(self, focus_x: float) -> float:
        max_camera = max(0, self.world_width - SCREEN_WIDTH)
        return max(0.0, min(max_camera, focus_x - (SCREEN_WIDTH / 2)))

    def draw(self, surface: pygame.Surface, focus_x: float) -> None:
        camera_x = self.camera_x(focus_x)
        surface.fill(BG_COLOR)

        for layer in self.layers:
            if layer.repeat_x:
                width = layer.surface.get_width()
                offset = -round(camera_x * layer.parallax) % width
                draw_x = offset - width
                while draw_x < SCREEN_WIDTH:
                    surface.blit(layer.surface, (draw_x, layer.y))
                    draw_x += width
            else:
                surface.blit(layer.surface, (-round(camera_x * layer.parallax), layer.y))

        platform_offset = int(camera_x)
        visible = pygame.Rect(platform_offset, 0, SCREEN_WIDTH, self.platform_surface.get_height())
        surface.blit(self.platform_surface, (0, self.floor_top), visible)
