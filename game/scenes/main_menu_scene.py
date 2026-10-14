from __future__ import annotations

import random
import re
from dataclasses import dataclass
from pathlib import Path

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR
from game.data.difficulty import DEFAULT_DIFFICULTY, DIFFICULTY_PROFILES, get_difficulty_profile
from game.systems.audio import AudioBank
from game.systems.keybindings import KEY_BINDINGS, KEYBINDING_ROWS


@dataclass
class UpdateHistoryRelease:
    version: str
    title: str
    version_key: tuple[int, int, int]
    entries: list[tuple[str, str]]


class MainMenuScene:
    MAIN_OPTIONS = ("Play", "Test Mode", "Stage Mode", "Settings", "Quit")
    HISTORY_BUTTON = pygame.Rect(24, SCREEN_HEIGHT - 64, 220, 42)
    HISTORY_PANEL = pygame.Rect(SCREEN_WIDTH - 650, 64, 626, SCREEN_HEIGHT - 88)
    KEYBINDINGS_VIEWPORT = pygame.Rect(420, 330, 1080, 570)
    KEYBINDINGS_BACK = pygame.Rect(SCREEN_WIDTH // 2 - 150, 930, 300, 54)
    KEYBINDING_ROW_HEIGHT = 42

    def __init__(self, difficulty: str = DEFAULT_DIFFICULTY) -> None:
        self.title_font = pygame.font.Font(None, 72)
        self.option_font = pygame.font.Font(None, 40)
        self.credit_font = pygame.font.Font(None, 24)
        self.history_button_font = pygame.font.Font(None, 24)
        self.history_heading_font = pygame.font.Font(None, 34)
        self.history_category_font = pygame.font.Font(None, 24)
        self.history_entry_font = pygame.font.Font(None, 21)
        self.history_hint_font = pygame.font.Font(None, 20)
        self.start_requested = False
        self.test_mode_requested = False
        self.stage_mode_requested = False
        self.difficulty = get_difficulty_profile(difficulty).name
        self.quit_requested = False
        self.settings_open = False
        self.keybindings_open = False
        self.keybinding_scroll = 0
        self.keybinding_selected_index = 0
        self.keybinding_capture: str | None = None
        self.keybinding_notice = ""
        self.history_open = False
        self.history_scroll = 0
        self.history_drag_offset: int | None = None
        self.selected_index = 0
        self._up_pressed = False
        self._down_pressed = False
        self._left_pressed = False
        self._right_pressed = False
        self._confirm_pressed = False
        self._escape_pressed = False
        self.sprites_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "characters"
        self.tile_size = (176, 132)
        self.scroll_x = 0.0
        self.scroll_y = 0.0
        self.scroll_speed_x = 11.0
        self.scroll_speed_y = 18.0
        self.grid_seed = random.randrange(1, 1_000_000_000)
        self.background_tiles = self._load_background_tiles()
        self.title_logo = self._load_title_logo()
        sounds_root = Path(__file__).resolve().parents[2] / "assets" / "sounds"
        self.audio = AudioBank(sounds_root)
        self.audio.play("menu_start")
        self.history_releases = self._load_update_history()
        self.history_lines, self.history_content_height = self._build_history_layout()

    def _load_update_history(self) -> list[UpdateHistoryRelease]:
        history_path = Path(__file__).resolve().parents[2] / "UPDATE_HISTORY.md"
        if not history_path.exists():
            return []

        releases: list[UpdateHistoryRelease] = []
        current_release: UpdateHistoryRelease | None = None
        version_pattern = re.compile(r"^##\s+(v?(\d+)\.(\d+)(?:\.(\d+))?)(?:\s*[-–—]\s*(.*))?$")

        def save_release() -> None:
            if current_release is not None:
                releases.append(current_release)

        for line in history_path.read_text(encoding="utf-8").splitlines():
            match = version_pattern.match(line)
            if match:
                save_release()
                version = match.group(1)
                version_numbers = tuple(int(match.group(index) or 0) for index in (2, 3, 4))
                current_release = UpdateHistoryRelease(
                    version,
                    (match.group(5) or "").strip(),
                    version_numbers,
                    [],
                )
                continue
            if current_release is None:
                continue

            stripped = line.strip()
            if stripped.startswith("### "):
                current_release.entries.append(("category", stripped[4:]))
            elif stripped.startswith("- "):
                current_release.entries.append(("bullet", stripped[2:].strip()))
            elif line.startswith("  ") and current_release.entries and current_release.entries[-1][0] == "bullet":
                kind, text = current_release.entries[-1]
                current_release.entries[-1] = (kind, f"{text} {stripped}")

        save_release()
        releases.sort(key=lambda release: release.version_key, reverse=True)
        return releases

    @staticmethod
    def _wrap_history_text(
        text: str,
        font: pygame.font.Font,
        max_width: int,
    ) -> list[str]:
        words = text.split()
        if not words:
            return [""]

        lines: list[str] = []
        current_line = words[0]
        for word in words[1:]:
            candidate = f"{current_line} {word}"
            if font.size(candidate)[0] > max_width:
                lines.append(current_line)
                current_line = word
            else:
                current_line = candidate
        lines.append(current_line)
        return lines

    def _build_history_layout(self) -> tuple[list[tuple[pygame.Surface, int]], int]:
        lines: list[tuple[pygame.Surface, int]] = []
        content_width = self.HISTORY_PANEL.width - 64
        y = 8

        for release in self.history_releases:
            heading = release.version
            if release.title:
                heading = f"{heading} - {release.title}"
            for text in self._wrap_history_text(heading, self.history_heading_font, content_width):
                rendered = self.history_heading_font.render(text, True, (255, 207, 122))
                lines.append((rendered, y))
                y += rendered.get_height() + 2
            y += 4

            for kind, text in release.entries:
                if kind == "category":
                    y += 4
                    rendered = self.history_category_font.render(text, True, (154, 204, 231))
                    lines.append((rendered, y))
                    y += rendered.get_height() + 3
                    continue

                wrapped_lines = self._wrap_history_text(
                    text,
                    self.history_entry_font,
                    content_width - 18,
                )
                for index, wrapped_line in enumerate(wrapped_lines):
                    prefix = "- " if index == 0 else "  "
                    rendered = self.history_entry_font.render(
                        f"{prefix}{wrapped_line}",
                        True,
                        (224, 228, 234),
                    )
                    lines.append((rendered, y))
                    y += rendered.get_height() + 2

            y += 12

        return lines, y

    def _history_viewport(self) -> pygame.Rect:
        return pygame.Rect(
            self.HISTORY_PANEL.x + 22,
            self.HISTORY_PANEL.y + 66,
            self.HISTORY_PANEL.width - 48,
            self.HISTORY_PANEL.height - 112,
        )

    def _clamp_history_scroll(self) -> None:
        viewport = self._history_viewport()
        self.history_scroll = max(0, min(self.history_scroll, self.history_content_height - viewport.height))

    def _resolve_background_path(self, directory: Path) -> Path | None:
        preferred_names = (
            f"{directory.name}.bmp",
            f"{directory.name}.png",
            f"{directory.name}_profile.bmp",
            f"{directory.name}_profile.png",
            f"{directory.name.capitalize()}.bmp",
            f"{directory.name.capitalize()}.png",
        )

        for filename in preferred_names:
            candidate = directory / filename
            if candidate.exists():
                return candidate

        fallback_images = sorted(
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() in {".bmp", ".png"}
        )
        if fallback_images:
            return fallback_images[0]

        return None

    def _load_background_tiles(self) -> list[pygame.Surface]:
        if not self.sprites_root.exists():
            return []

        tiles: list[pygame.Surface] = []
        for directory in sorted(path for path in self.sprites_root.iterdir() if path.is_dir()):
            background_path = self._resolve_background_path(directory)
            if background_path is None:
                continue

            image = pygame.image.load(str(background_path)).convert()
            image.set_colorkey((0, 0, 0))
            tiles.append(pygame.transform.smoothscale(image, self.tile_size))
        return tiles

    def _load_title_logo(self) -> pygame.Surface | None:
        logo_path = Path(__file__).resolve().parents[2] / "assets" / "LF3_logo.jpg"
        if not logo_path.exists():
            return None

        logo = pygame.image.load(str(logo_path)).convert()
        logo.set_colorkey((0, 0, 0))
        width, height = logo.get_size()
        target_width = 980
        target_height = max(1, int(height * (target_width / width)))
        scaled = pygame.transform.smoothscale(logo, (target_width, target_height))
        scaled.set_colorkey((0, 0, 0))
        return scaled

    def _menu_options(self) -> tuple[str, ...]:
        if self.settings_open:
            sound_state = "Off" if AudioBank.muted else "On"
            return (f"Sound: {sound_state}", "Volume", "Difficulty", "Key Bindings", "Back")
        return self.MAIN_OPTIONS

    def _cycle_difficulty(self, step: int) -> None:
        difficulties = tuple(DIFFICULTY_PROFILES)
        current_index = difficulties.index(self.difficulty)
        self.difficulty = difficulties[(current_index + step) % len(difficulties)]

    def _option_rects(self) -> list[pygame.Rect]:
        options = self._menu_options()
        return [
            pygame.Rect(0, 0, 300, 54).move(
                SCREEN_WIDTH // 2 - 150,
                310 + index * 68,
            )
            for index in range(len(options))
        ]

    def _activate_selected(self) -> None:
        self.audio.play("menu_accept")
        if self.settings_open:
            if self.selected_index == 0:
                AudioBank.set_muted(not AudioBank.muted)
            elif self.selected_index == 1:
                AudioBank.set_master_volume(AudioBank.master_volume + 0.1)
            elif self.selected_index == 2:
                self._cycle_difficulty(1)
            elif self.selected_index == 3:
                self.keybindings_open = True
                self.keybinding_selected_index = 0
                self.keybinding_scroll = 0
            else:
                self.settings_open = False
                self.selected_index = 0
            return

        self.test_mode_requested = False
        self.stage_mode_requested = False
        if self.selected_index == 0:
            self.start_requested = True
        elif self.selected_index == 1:
            self.start_requested = True
            self.test_mode_requested = True
        elif self.selected_index == 2:
            self.start_requested = True
            self.stage_mode_requested = True
        elif self.selected_index == 3:
            self.settings_open = True
            self.selected_index = 0
        else:
            self.quit_requested = True

    def update(
        self,
        dt: float,
        mouse_pos: tuple[int, int] | None = None,
        mouse_click: tuple[int, int] | None = None,
        mouse_wheel_y: int = 0,
        mouse_left_down: bool = False,
        pressed_keys: list[int] | None = None,
    ) -> None:
        keys = pygame.key.get_pressed()
        up_pressed = KEY_BINDINGS.is_pressed("move_up", keys)
        down_pressed = KEY_BINDINGS.is_pressed("move_down", keys)
        left_pressed = KEY_BINDINGS.is_pressed("move_left", keys)
        right_pressed = KEY_BINDINGS.is_pressed("move_right", keys)
        confirm_pressed = (
            KEY_BINDINGS.is_pressed("menu_confirm", keys)
            or KEY_BINDINGS.is_pressed("main_menu_confirm_space", keys)
        )
        escape_pressed = KEY_BINDINGS.is_pressed("back_pause", keys)
        options = self._menu_options()
        rects = self._option_rects()

        self.start_requested = False
        self.quit_requested = False
        close_rect = pygame.Rect(self.HISTORY_PANEL.right - 52, self.HISTORY_PANEL.y + 12, 36, 36)
        if self.keybindings_open:
            self._update_keybindings(
                mouse_click,
                mouse_wheel_y,
                pressed_keys or [],
                keys,
                up_pressed,
                down_pressed,
                confirm_pressed,
                escape_pressed,
            )
        elif self.history_open:
            if mouse_click is not None and (
                not self.HISTORY_PANEL.collidepoint(mouse_click) or close_rect.collidepoint(mouse_click)
            ):
                self.history_open = False
                self.history_drag_offset = None
            if self.history_open:
                if escape_pressed and not self._escape_pressed:
                    self.history_open = False
                    self.history_drag_offset = None
                else:
                    self.history_scroll -= mouse_wheel_y * 52
                    if up_pressed and not self._up_pressed:
                        self.history_scroll -= 54
                    elif down_pressed and not self._down_pressed:
                        self.history_scroll += 54
                    if KEY_BINDINGS.is_pressed("history_page_up", keys):
                        self.history_scroll -= self._history_viewport().height
                    elif KEY_BINDINGS.is_pressed("history_page_down", keys):
                        self.history_scroll += self._history_viewport().height
                    track, thumb, max_scroll = self._history_scrollbar()
                    if mouse_click is not None and mouse_pos is not None:
                        hit_area = track.inflate(16, 0)
                        if hit_area.collidepoint(mouse_click) and max_scroll:
                            if thumb.collidepoint(mouse_click):
                                self.history_drag_offset = mouse_click[1] - thumb.y
                            else:
                                self.history_drag_offset = thumb.height // 2
                            mouse_y = max(track.top, min(mouse_pos[1], track.bottom))
                            thumb_travel = track.height - thumb.height
                            thumb_y = max(
                                track.top,
                                min(mouse_y - self.history_drag_offset, track.top + thumb_travel),
                            )
                            self.history_scroll = round(
                                (thumb_y - track.top) * max_scroll / thumb_travel
                            )
                    if mouse_left_down and self.history_drag_offset is not None and mouse_pos is not None:
                        thumb_travel = track.height - thumb.height
                        thumb_y = max(
                            track.top,
                            min(mouse_pos[1] - self.history_drag_offset, track.top + thumb_travel),
                        )
                        self.history_scroll = round(
                            (thumb_y - track.top) * max_scroll / thumb_travel
                        )
                    elif not mouse_left_down:
                        self.history_drag_offset = None
                    self._clamp_history_scroll()
        elif mouse_click is not None and self.HISTORY_BUTTON.collidepoint(mouse_click):
            self.history_open = True
            self.history_scroll = 0
            self.audio.play("menu_accept")
        else:
            if mouse_pos is not None:
                for index, rect in enumerate(rects):
                    if rect.collidepoint(mouse_pos):
                        self.selected_index = index
                        break
            if up_pressed and not self._up_pressed:
                self.selected_index = (self.selected_index - 1) % len(options)
            elif down_pressed and not self._down_pressed:
                self.selected_index = (self.selected_index + 1) % len(options)
            if self.settings_open:
                if self.selected_index == 1:
                    if left_pressed and not self._left_pressed:
                        AudioBank.set_master_volume(AudioBank.master_volume - 0.1)
                    elif right_pressed and not self._right_pressed:
                        AudioBank.set_master_volume(AudioBank.master_volume + 0.1)
                elif self.selected_index == 2:
                    if left_pressed and not self._left_pressed:
                        self._cycle_difficulty(-1)
                    elif right_pressed and not self._right_pressed:
                        self._cycle_difficulty(1)

            if mouse_click is not None:
                for index, rect in enumerate(rects):
                    if rect.collidepoint(mouse_click):
                        self.selected_index = index
                        if self.settings_open and index == 1:
                            bar_rect = pygame.Rect(rect.x + 100, rect.y + 17, 130, 20)
                            if bar_rect.collidepoint(mouse_click):
                                volume = (mouse_click[0] - bar_rect.left) / bar_rect.width
                                AudioBank.set_master_volume(volume)
                        else:
                            self._activate_selected()
                        break
            elif confirm_pressed and not self._confirm_pressed:
                self._activate_selected()
            elif self.settings_open and escape_pressed and not self._escape_pressed:
                self.settings_open = False
                self.selected_index = 0

        self._up_pressed = up_pressed
        self._down_pressed = down_pressed
        self._left_pressed = left_pressed
        self._right_pressed = right_pressed
        self._confirm_pressed = confirm_pressed
        self._escape_pressed = escape_pressed
        self.scroll_x += self.scroll_speed_x * dt
        self.scroll_y += self.scroll_speed_y * dt

    def _update_keybindings(
        self,
        mouse_click: tuple[int, int] | None,
        mouse_wheel_y: int,
        pressed_keys: list[int],
        keys: pygame.key.ScancodeWrapper,
        up_pressed: bool,
        down_pressed: bool,
        confirm_pressed: bool,
        escape_pressed: bool,
    ) -> None:
        if self.keybinding_capture is not None:
            if pressed_keys:
                key_code = pressed_keys[-1]
                if key_code == pygame.K_ESCAPE:
                    self.keybinding_notice = "Rebinding cancelled."
                else:
                    KEY_BINDINGS.set_binding(self.keybinding_capture, key_code)
                    self.keybinding_notice = "Key binding saved."
                self.keybinding_capture = None
            return

        if mouse_click is not None:
            if self.KEYBINDINGS_BACK.collidepoint(mouse_click):
                self.keybindings_open = False
                self.keybinding_capture = None
                return
            if self.KEYBINDINGS_VIEWPORT.collidepoint(mouse_click):
                index = (mouse_click[1] - self.KEYBINDINGS_VIEWPORT.top + self.keybinding_scroll) // self.KEYBINDING_ROW_HEIGHT
                if index < len(KEYBINDING_ROWS):
                    self.keybinding_selected_index = index
                    self.keybinding_capture = KEYBINDING_ROWS[index][1]
                    self.keybinding_notice = "Press any key to assign it. Escape cancels."
                    self.audio.play("menu_accept")
                    return

        if escape_pressed and not self._escape_pressed:
            self.keybindings_open = False
            return
        if confirm_pressed and not self._confirm_pressed:
            self.keybinding_capture = KEYBINDING_ROWS[self.keybinding_selected_index][1]
            self.keybinding_notice = "Press any key to assign it. Escape cancels."
            return

        selection_moved = False
        if up_pressed and not self._up_pressed:
            self.keybinding_selected_index = (self.keybinding_selected_index - 1) % len(KEYBINDING_ROWS)
            selection_moved = True
        elif down_pressed and not self._down_pressed:
            self.keybinding_selected_index = (self.keybinding_selected_index + 1) % len(KEYBINDING_ROWS)
            selection_moved = True

        if mouse_wheel_y:
            self.keybinding_scroll -= mouse_wheel_y * self.KEYBINDING_ROW_HEIGHT * 3
        elif KEY_BINDINGS.is_pressed("history_page_up", keys):
            self.keybinding_scroll -= self.KEYBINDINGS_VIEWPORT.height
        elif KEY_BINDINGS.is_pressed("history_page_down", keys):
            self.keybinding_scroll += self.KEYBINDINGS_VIEWPORT.height
        if selection_moved:
            self._ensure_keybinding_visible()
        else:
            max_scroll = max(
                0,
                len(KEYBINDING_ROWS) * self.KEYBINDING_ROW_HEIGHT - self.KEYBINDINGS_VIEWPORT.height,
            )
            self.keybinding_scroll = max(0, min(self.keybinding_scroll, max_scroll))

    def _ensure_keybinding_visible(self) -> None:
        selected_top = self.keybinding_selected_index * self.KEYBINDING_ROW_HEIGHT
        selected_bottom = selected_top + self.KEYBINDING_ROW_HEIGHT
        if selected_top < self.keybinding_scroll:
            self.keybinding_scroll = selected_top
        elif selected_bottom > self.keybinding_scroll + self.KEYBINDINGS_VIEWPORT.height:
            self.keybinding_scroll = selected_bottom - self.KEYBINDINGS_VIEWPORT.height
        max_scroll = max(
            0,
            len(KEYBINDING_ROWS) * self.KEYBINDING_ROW_HEIGHT - self.KEYBINDINGS_VIEWPORT.height,
        )
        self.keybinding_scroll = max(0, min(self.keybinding_scroll, max_scroll))

    def _draw_history_button(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, (35, 38, 48), self.HISTORY_BUTTON, border_radius=8)
        pygame.draw.rect(surface, (210, 210, 220), self.HISTORY_BUTTON, 2, border_radius=8)
        label = self.history_button_font.render("Update History", True, TEXT_COLOR)
        surface.blit(label, label.get_rect(center=self.HISTORY_BUTTON.center))

    def _history_scrollbar(self) -> tuple[pygame.Rect, pygame.Rect, int]:
        viewport = self._history_viewport()
        track = pygame.Rect(viewport.right + 5, viewport.y, 6, viewport.height)
        max_scroll = max(0, self.history_content_height - viewport.height)
        if max_scroll:
            thumb_height = max(30, round(track.height * viewport.height / self.history_content_height))
            thumb_y = track.y + round((track.height - thumb_height) * self.history_scroll / max_scroll)
        else:
            thumb_height = track.height
            thumb_y = track.y
        return track, pygame.Rect(track.x, thumb_y, track.width, thumb_height), max_scroll

    def _draw_history_panel(self, surface: pygame.Surface) -> None:
        panel = self.HISTORY_PANEL
        pygame.draw.rect(surface, (5, 8, 14), panel.move(5, 5), border_radius=16)
        panel_surface = pygame.Surface(panel.size, pygame.SRCALPHA)
        panel_surface.fill((18, 23, 32, 248))
        surface.blit(panel_surface, panel)
        pygame.draw.rect(surface, (108, 132, 156), panel, 2, border_radius=16)

        title = self.history_heading_font.render("Update History", True, TEXT_COLOR)
        surface.blit(title, (panel.x + 22, panel.y + 18))
        close_rect = pygame.Rect(panel.right - 52, panel.y + 12, 36, 36)
        pygame.draw.rect(surface, (48, 58, 72), close_rect, border_radius=8)
        close_label = self.history_button_font.render("X", True, TEXT_COLOR)
        surface.blit(close_label, close_label.get_rect(center=close_rect.center))

        viewport = self._history_viewport()
        old_clip = surface.get_clip()
        surface.set_clip(viewport)
        if self.history_lines:
            for rendered, y in self.history_lines:
                draw_y = viewport.y + y - self.history_scroll
                if draw_y + rendered.get_height() < viewport.top:
                    continue
                if draw_y > viewport.bottom:
                    break
                surface.blit(rendered, (viewport.x, draw_y))
        else:
            empty = self.history_entry_font.render("No update history found.", True, TEXT_COLOR)
            surface.blit(empty, (viewport.x, viewport.y))
        surface.set_clip(old_clip)

        track, thumb, _ = self._history_scrollbar()
        pygame.draw.rect(surface, (43, 51, 62), track, border_radius=3)
        pygame.draw.rect(
            surface,
            (147, 166, 184),
            thumb,
            border_radius=3,
        )
        hint = self.history_hint_font.render(
            "Drag bar / Scroll: wheel, "
            f"{KEY_BINDINGS.label('move_up')}/{KEY_BINDINGS.label('move_down')}, "
            f"{KEY_BINDINGS.label('history_page_up')}/{KEY_BINDINGS.label('history_page_down')}    "
            f"{KEY_BINDINGS.label('back_pause')}: close",
            True,
            (174, 188, 204),
        )
        surface.blit(hint, hint.get_rect(midbottom=(panel.centerx, panel.bottom - 14)))

    def _draw_background(self, surface: pygame.Surface) -> None:
        if not self.background_tiles:
            surface.fill((14, 14, 18))
            return

        tile_w, tile_h = self.tile_size
        cols = (SCREEN_WIDTH // tile_w) + 3
        rows = (SCREEN_HEIGHT // tile_h) + 3
        col_base = int(self.scroll_x // tile_w)
        row_base = int(self.scroll_y // tile_h)
        col_offset = self.scroll_x % tile_w
        row_offset = self.scroll_y % tile_h

        for row in range(-1, rows):
            source_row = row_base + row
            y = int(source_row * tile_h - self.scroll_y)
            for col in range(-1, cols):
                source_col = col_base + col
                seed = self.grid_seed ^ (source_row * 374761393) ^ (source_col * 668265263)
                tile = self.background_tiles[abs(seed) % len(self.background_tiles)]
                x = int(source_col * tile_w - self.scroll_x)
                surface.blit(tile, (x, y))

        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 14, 120))
        surface.blit(overlay, (0, 0))

    def _draw_keybindings(self, surface: pygame.Surface) -> None:
        viewport = self.KEYBINDINGS_VIEWPORT
        panel = pygame.Rect(viewport.x - 24, viewport.y - 34, viewport.width + 48, viewport.height + 132)
        pygame.draw.rect(surface, (18, 23, 32), panel, border_radius=16)
        pygame.draw.rect(surface, (108, 132, 156), panel, 2, border_radius=16)

        instruction_text = (
            self.keybinding_notice
            or "Select a row and press a key to rebind. Changes save automatically."
        )
        instruction = self.history_hint_font.render(instruction_text, True, (174, 188, 204))
        surface.blit(instruction, instruction.get_rect(midtop=(viewport.centerx, viewport.top - 26)))

        old_clip = surface.get_clip()
        surface.set_clip(viewport)
        for index, (label, action, test_only) in enumerate(KEYBINDING_ROWS):
            row_y = viewport.top + index * self.KEYBINDING_ROW_HEIGHT - self.keybinding_scroll
            row_rect = pygame.Rect(viewport.x, row_y, viewport.width - 14, self.KEYBINDING_ROW_HEIGHT - 4)
            if not viewport.colliderect(row_rect):
                continue
            selected = index == self.keybinding_selected_index
            row_color = (59, 82, 105) if selected else (29, 37, 49)
            pygame.draw.rect(surface, row_color, row_rect, border_radius=7)
            if selected:
                pygame.draw.rect(surface, (255, 190, 92), row_rect, 2, border_radius=7)
            display_label = f"{label}  [TEST]" if test_only else label
            label_surface = self.history_button_font.render(display_label, True, TEXT_COLOR)
            surface.blit(label_surface, label_surface.get_rect(midleft=(row_rect.x + 16, row_rect.centery)))
            binding_text = (
                "Press a key..."
                if self.keybinding_capture == action
                else KEY_BINDINGS.label(action)
            )
            binding = self.history_button_font.render(binding_text, True, (255, 207, 122))
            surface.blit(binding, binding.get_rect(midright=(row_rect.right - 16, row_rect.centery)))
        surface.set_clip(old_clip)

        track = pygame.Rect(viewport.right + 2, viewport.top, 6, viewport.height)
        pygame.draw.rect(surface, (43, 51, 62), track, border_radius=3)
        max_scroll = max(
            0,
            len(KEYBINDING_ROWS) * self.KEYBINDING_ROW_HEIGHT - viewport.height,
        )
        if max_scroll:
            thumb_height = max(32, round(track.height * viewport.height / (max_scroll + viewport.height)))
            thumb_y = track.top + round(
                (track.height - thumb_height) * self.keybinding_scroll / max_scroll
            )
        else:
            thumb_height = track.height
            thumb_y = track.top
        pygame.draw.rect(
            surface,
            (147, 166, 184),
            pygame.Rect(track.x, thumb_y, track.width, thumb_height),
            border_radius=3,
        )
        pygame.draw.rect(surface, (48, 58, 72), self.KEYBINDINGS_BACK, border_radius=8)
        pygame.draw.rect(surface, (210, 210, 220), self.KEYBINDINGS_BACK, 2, border_radius=8)
        back = self.history_button_font.render("Back", True, TEXT_COLOR)
        surface.blit(back, back.get_rect(center=self.KEYBINDINGS_BACK.center))

    def _draw_title(self, surface: pygame.Surface) -> None:
        credit = self.credit_font.render("Official game by Josh Olsson", True, TEXT_COLOR)

        if self.title_logo is not None:
            logo_rect = self.title_logo.get_rect(center=(SCREEN_WIDTH // 2, 140))
            shadow = self.title_logo.copy()
            shadow.fill((0, 0, 0, 120), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(shadow, (logo_rect.x + 3, logo_rect.y + 3))
            surface.blit(self.title_logo, logo_rect)
        else:
            title = self.title_font.render("Little Fighter 3", True, TEXT_COLOR)
            title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 140))
            shadow = title.copy()
            shadow.fill((0, 0, 0, 120), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(shadow, (title_rect.x + 3, title_rect.y + 3))
            surface.blit(title, title_rect)

        if self.settings_open:
            heading_text = "Key Bindings" if self.keybindings_open else "Settings"
            heading = self.option_font.render(heading_text, True, TEXT_COLOR)
            surface.blit(heading, heading.get_rect(center=(SCREEN_WIDTH // 2, 260)))
        if self.keybindings_open:
            self._draw_keybindings(surface)
            credit_rect = credit.get_rect(bottomright=(SCREEN_WIDTH - 20, SCREEN_HEIGHT - 16))
            surface.blit(credit, credit_rect)
            return

        for index, (label, rect) in enumerate(zip(self._menu_options(), self._option_rects())):
            color = (80, 110, 165) if index == self.selected_index else (35, 38, 48)
            pygame.draw.rect(surface, color, rect, border_radius=8)
            pygame.draw.rect(surface, (210, 210, 220), rect, 2, border_radius=8)
            if self.settings_open and index == 1:
                label_text = self.option_font.render(label, True, TEXT_COLOR)
                surface.blit(label_text, label_text.get_rect(midleft=(rect.x + 14, rect.centery)))
                bar_rect = pygame.Rect(rect.x + 100, rect.y + 17, 130, 20)
                pygame.draw.rect(surface, (20, 22, 28), bar_rect, border_radius=6)
                fill_rect = bar_rect.copy()
                fill_rect.width = round(bar_rect.width * AudioBank.master_volume)
                if fill_rect.width:
                    pygame.draw.rect(surface, (100, 190, 120), fill_rect, border_radius=6)
                volume_text = self.credit_font.render(f"{round(AudioBank.master_volume * 100)}%", True, TEXT_COLOR)
                surface.blit(volume_text, volume_text.get_rect(midright=(rect.right - 12, rect.centery)))
                continue
            if self.settings_open and index == 2:
                label_text = self.option_font.render(label, True, TEXT_COLOR)
                surface.blit(label_text, label_text.get_rect(midleft=(rect.x + 14, rect.centery)))
                difficulty_text = self.credit_font.render(
                    f"< {self.difficulty.upper()} >",
                    True,
                    TEXT_COLOR,
                )
                surface.blit(
                    difficulty_text,
                    difficulty_text.get_rect(midright=(rect.right - 12, rect.centery)),
                )
                continue
            text = self.option_font.render(label, True, TEXT_COLOR)
            surface.blit(text, text.get_rect(center=rect.center))

        credit_rect = credit.get_rect(bottomright=(SCREEN_WIDTH - 20, SCREEN_HEIGHT - 16))
        surface.blit(credit, credit_rect)

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        self._draw_title(surface)
        if not self.keybindings_open:
            self._draw_history_button(surface)
        if self.history_open:
            self._draw_history_panel(surface)
