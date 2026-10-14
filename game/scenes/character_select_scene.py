from __future__ import annotations

from pathlib import Path

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR
from game.data.characters import (
    CHARACTER_CATEGORIES,
    CHARACTER_GROUPS,
    CHARACTERS,
    NON_PLAYABLE_CHARACTER_KEYS,
)
from game.systems.animation import AnimationPlayer
from game.systems.assets import load_character_animations
from game.systems.keybindings import KEY_BINDINGS
from game.systems.stage import STAGE_CONFIGS

PROFILE_SIZE = (132, 132)
ROSTER_PANEL = pygame.Rect(42, 842, SCREEN_WIDTH - 84, 220)
ROSTER_CARD_TOP = 862
ROSTER_CARD_HEIGHT = 184
ROSTER_CARD_GAP = 14
CATEGORY_TOP = 132
CATEGORY_HEIGHT = 44
CONFIRM_BUTTON = pygame.Rect(SCREEN_WIDTH - 352, 45, 292, 62)
LEFT_INFO_PANEL = pygame.Rect(68, 286, 430, 430)
RIGHT_INFO_PANEL = pygame.Rect(SCREEN_WIDTH - 500, 286, 430, 430)
PREVIEW_CENTER = (SCREEN_WIDTH // 2, 820)
PREVIEW_MAX_SIZE = (500, 560)
PREVIEW_SWITCH_DELAY = 0.12

SPECIAL_MOVE_LABELS = {
    "sp_move_attack_1": "Moving Special I",
    "sp_move_attack_2": "Moving Special II",
    "sp_vert_attack_1": "Vertical Special I",
    "sp_vert_attack_2": "Vertical Special II",
}


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
        self.tab_font = pygame.font.SysFont("bahnschrift", 18, bold=True)
        self.card_font = pygame.font.SysFont("bahnschrift", 24, bold=True)
        self.badge_font = pygame.font.SysFont("segoeui", 16, bold=True)
        self.button_font = pygame.font.SysFont("bahnschrift", 24, bold=True)
        self.characters = self._discover_characters()
        self.character_index = {character["key"]: index for index, character in enumerate(self.characters)}
        self.category_members = {
            category: [
                self.character_index[key]
                for key in keys
                if key in self.character_index
            ]
            for category, keys in CHARACTER_GROUPS
        }
        self.categories = [
            category for category, _ in CHARACTER_GROUPS
            if self.category_members[category]
        ]
        self.category_tab_rects: list[pygame.Rect] = []
        self._build_category_tab_rects()

        self.selected_index = 0
        if initial_character is not None:
            self.selected_index = self.character_index.get(initial_character, -1)
            if self.selected_index == -1:
                raise ValueError(f"Selected character is unavailable: {initial_character}")
        self.current_category = (
            self.characters[self.selected_index]["category"]
            if self.characters
            else self.categories[0] if self.categories else ""
        )
        self.last_selected_by_category: dict[str, str] = {}
        if self.characters:
            selected_key = self.characters[self.selected_index]["key"]
            self.last_selected_by_category[self.current_category] = selected_key

        self.selected_character = self.characters[self.selected_index]["key"] if self.characters else None
        self.selected_opponents: set[str] = set()
        self.selection_confirmed = False
        self._up_pressed = False
        self._down_pressed = False
        self._left_pressed = False
        self._right_pressed = False
        self._confirm_pressed = confirm_already_pressed
        self._toggle_pressed = toggle_already_pressed
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
        self.preview_glow = pygame.Surface((720, 190), pygame.SRCALPHA)
        pygame.draw.ellipse(self.preview_glow, (244, 180, 75, 42), self.preview_glow.get_rect())

        maps_root = Path(__file__).resolve().parents[2] / "assets" / "maps"
        stage_directory, stage_type = STAGE_CONFIGS.get(map_name, STAGE_CONFIGS["City"])
        self.backdrop = stage_type(maps_root / stage_directory)
        if self.selected_character is not None:
            self._load_preview(self.selected_character)

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
            characters.append(
                {
                    "key": character_key,
                    "display_name": CHARACTERS[character_key]["display_name"].title(),
                    "category": CHARACTER_CATEGORIES[character_key],
                    "profile": profile,
                }
            )
        category_order = {category: index for index, (category, _) in enumerate(CHARACTER_GROUPS)}
        characters.sort(key=lambda character: category_order[character["category"]])
        return characters

    def _resolve_profile_path(self, directory: Path) -> Path | None:
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

        fallback_profiles = sorted(
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() in {".bmp", ".png"}
            and "profile" in path.stem.lower()
        )
        if fallback_profiles:
            return fallback_profiles[0]

        fallback_frames = sorted(
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in {".bmp", ".png"}
        )
        if fallback_frames:
            return fallback_frames[0]

        nested_frames = sorted(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in {".bmp", ".png"}
        )
        return nested_frames[0] if nested_frames else None

    def _build_category_tab_rects(self) -> None:
        if not self.categories:
            return
        margin = 48
        gap = 8
        tab_width = (SCREEN_WIDTH - margin * 2 - gap * (len(self.categories) - 1)) // len(self.categories)
        self.category_tab_rects = [
            pygame.Rect(margin + index * (tab_width + gap), CATEGORY_TOP, tab_width, CATEGORY_HEIGHT)
            for index in range(len(self.categories))
        ]

    def _category_character_indices(self) -> list[int]:
        return self.category_members.get(self.current_category, [])

    def _roster_card_rect(self, visible_index: int) -> pygame.Rect:
        character_indices = self._category_character_indices()
        count = len(character_indices)
        gap = ROSTER_CARD_GAP
        card_width = min(440, (ROSTER_PANEL.width - 36 - gap * max(0, count - 1)) // max(1, count))
        row_width = count * card_width + max(0, count - 1) * gap
        x = (SCREEN_WIDTH - row_width) // 2 + visible_index * (card_width + gap)
        return pygame.Rect(x, ROSTER_CARD_TOP, card_width, ROSTER_CARD_HEIGHT)

    def _set_selected_index(self, index: int, *, defer_preview: bool = False) -> None:
        if not self.characters:
            return
        index %= len(self.characters)
        character = self.characters[index]
        if character["category"] != self.current_category:
            return
        changed = index != self.selected_index
        self.selected_index = index
        self.selected_character = character["key"]
        self.last_selected_by_category[self.current_category] = self.selected_character
        if changed and self.preview_player is not None:
            self.preview_pending_key = self.selected_character
            self.preview_pending_elapsed = 0.0
            if not defer_preview:
                self._load_preview(self.selected_character)

    def _change_category(self, direction: int) -> None:
        if not self.categories:
            return
        current_index = self.categories.index(self.current_category)
        self.current_category = self.categories[(current_index + direction) % len(self.categories)]
        remembered_key = self.last_selected_by_category.get(self.current_category)
        character_index = self.character_index.get(remembered_key, -1)
        if character_index not in self.category_members[self.current_category]:
            character_index = self.category_members[self.current_category][0]
        self._set_selected_index(character_index)

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
        for animation in animations.values():
            scaled_frames = []
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
        self.preview_pending_key = None
        self.preview_pending_elapsed = 0.0

    def _update_preview(self, dt: float) -> None:
        if self.preview_pending_key is not None:
            self.preview_pending_elapsed += dt
            if self.preview_pending_elapsed >= PREVIEW_SWITCH_DELAY:
                self._load_preview(self.preview_pending_key)
        if self.preview_player is None or not self.preview_sequence:
            return

        self.preview_player.update(dt, 1)
        self.preview_elapsed += dt
        _, _, duration = self.preview_sequence[self.preview_sequence_index]
        if self.preview_player.finished or self.preview_elapsed >= duration:
            self.preview_sequence_index = (self.preview_sequence_index + 1) % len(self.preview_sequence)
            animation_name, self.preview_label, _ = self.preview_sequence[self.preview_sequence_index]
            self.preview_player.play(animation_name)
            self.preview_elapsed = 0.0

    def update(
        self,
        dt: float,
        mouse_pos: tuple[int, int] | None = None,
        mouse_click: tuple[int, int] | None = None,
        mouse_wheel_y: int = 0,
    ) -> None:
        self._elapsed_time += dt
        self._update_preview(dt)
        keys = pygame.key.get_pressed()
        up_pressed = KEY_BINDINGS.is_pressed("move_up", keys)
        down_pressed = KEY_BINDINGS.is_pressed("move_down", keys)
        left_pressed = KEY_BINDINGS.is_pressed("move_left", keys)
        right_pressed = KEY_BINDINGS.is_pressed("move_right", keys)
        confirm_pressed = KEY_BINDINGS.is_pressed("menu_confirm", keys)
        toggle_pressed = KEY_BINDINGS.is_pressed("toggle_opponent", keys)

        if self.characters:
            if up_pressed and not self._up_pressed:
                self._change_category(-1)
            elif down_pressed and not self._down_pressed:
                self._change_category(1)
            elif left_pressed and not self._left_pressed:
                members = self._category_character_indices()
                member_position = members.index(self.selected_index)
                self._set_selected_index(members[(member_position - 1) % len(members)])
            elif right_pressed and not self._right_pressed:
                members = self._category_character_indices()
                member_position = members.index(self.selected_index)
                self._set_selected_index(members[(member_position + 1) % len(members)])

            if mouse_pos is not None:
                for index, tab_rect in enumerate(self.category_tab_rects):
                    if tab_rect.collidepoint(mouse_pos):
                        if mouse_click is not None:
                            self._change_category_to(index)
                        break
                else:
                    for visible_index, character_index in enumerate(self._category_character_indices()):
                        if self._roster_card_rect(visible_index).collidepoint(mouse_pos):
                            self._set_selected_index(character_index, defer_preview=True)
                            break

            if mouse_click is not None:
                clicked_tab = next(
                    (index for index, rect in enumerate(self.category_tab_rects) if rect.collidepoint(mouse_click)),
                    None,
                )
                if clicked_tab is not None:
                    self._change_category_to(clicked_tab)
                elif CONFIRM_BUTTON.collidepoint(mouse_click):
                    self.selection_confirmed = bool(self.selected_opponents) if self.opponent_selection else True
                else:
                    for visible_index, character_index in enumerate(self._category_character_indices()):
                        if self._roster_card_rect(visible_index).collidepoint(mouse_click):
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
                if self.opponent_selection:
                    self.selection_confirmed = bool(self.selected_opponents)
                else:
                    self.selection_confirmed = True
            if self.opponent_selection and toggle_pressed and not self._toggle_pressed:
                self._toggle_opponent(self.selected_character)

        self._up_pressed = up_pressed
        self._down_pressed = down_pressed
        self._left_pressed = left_pressed
        self._right_pressed = right_pressed
        self._confirm_pressed = confirm_pressed
        self._toggle_pressed = toggle_pressed

    def _change_category_to(self, category_index: int) -> None:
        if not self.categories:
            return
        category_index %= len(self.categories)
        category = self.categories[category_index]
        if category == self.current_category:
            return
        self.current_category = category
        remembered_key = self.last_selected_by_category.get(category)
        character_index = self.character_index.get(remembered_key, -1)
        if character_index not in self.category_members[category]:
            character_index = self.category_members[category][0]
        self._set_selected_index(character_index)

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
        self.backdrop.draw(surface, self.backdrop.world_width / 2)
        shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        shade.fill((5, 10, 20, 166))
        surface.blit(shade, (0, 0))
        surface.blit(self.preview_glow, (PREVIEW_CENTER[0] - self.preview_glow.get_width() // 2, 720))
        pygame.draw.line(surface, (134, 160, 183), (0, 820), (SCREEN_WIDTH, 820), 1)

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

        subtitle = self.subtitle_font.render(
            "Click a fighter or use arrows to browse; each preview cycles through their moves",
            True,
            (189, 204, 218),
        )
        surface.blit(subtitle, (64, 100))

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

    def _draw_category_tabs(self, surface: pygame.Surface) -> None:
        for index, rect in enumerate(self.category_tab_rects):
            selected = self.categories[index] == self.current_category
            fill = (126, 73, 42) if selected else (15, 24, 36)
            outline = (255, 190, 92) if selected else (88, 111, 133)
            pygame.draw.rect(surface, fill, rect, border_radius=9)
            pygame.draw.rect(surface, outline, rect, 2 if selected else 1, border_radius=9)
            label_text = self.categories[index].upper()
            label_font = self.tab_font
            if label_font.size(label_text)[0] > rect.width - 12:
                label_font = pygame.font.SysFont("bahnschrift", 14, bold=True)
            label = label_font.render(label_text, True, (255, 232, 193) if selected else (194, 208, 221))
            surface.blit(label, label.get_rect(center=rect.center))

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

    def _draw_character_details(self, surface: pygame.Surface, character: dict) -> None:
        self._draw_panel(surface, LEFT_INFO_PANEL, (9, 17, 29, 225))
        category_surface = self.badge_font.render(character["category"].upper(), True, (255, 209, 129))
        surface.blit(category_surface, (LEFT_INFO_PANEL.x + 26, LEFT_INFO_PANEL.y + 24))
        name = character["display_name"].upper()
        name_font = self.name_font
        if name_font.size(name)[0] > LEFT_INFO_PANEL.width - 48:
            name_font = pygame.font.SysFont("bahnschrift", 38, bold=True)
        name_surface = name_font.render(name, True, (250, 248, 241))
        surface.blit(name_surface, (LEFT_INFO_PANEL.x + 24, LEFT_INFO_PANEL.y + 52))
        pygame.draw.line(
            surface,
            (225, 157, 75),
            (LEFT_INFO_PANEL.x + 24, LEFT_INFO_PANEL.y + 116),
            (LEFT_INFO_PANEL.right - 24, LEFT_INFO_PANEL.y + 116),
            2,
        )

        definition = CHARACTERS[character["key"]]
        stats = definition["stats"]
        max_health = int(stats.get("max_health", 0))
        max_mana = int(stats.get("max_mana", 0))
        self._draw_stat_bar(
            surface,
            "HP",
            max_health,
            max_health,
            pygame.Rect(LEFT_INFO_PANEL.x + 28, LEFT_INFO_PANEL.y + 168, LEFT_INFO_PANEL.width - 56, 14),
            (217, 79, 78),
        )
        self._draw_stat_bar(
            surface,
            "MP",
            max_mana,
            max_mana,
            pygame.Rect(LEFT_INFO_PANEL.x + 28, LEFT_INFO_PANEL.y + 226, LEFT_INFO_PANEL.width - 56, 14),
            (77, 147, 229),
        )

        movement = definition.get("movement", {})
        walk_speed = round(movement.get("walk_speed", 0))
        run_speed = round(movement.get("run_speed", 0))
        speed_y = LEFT_INFO_PANEL.y + 276
        speed_label = self.small_font.render("MOBILITY", True, (148, 174, 196))
        surface.blit(speed_label, (LEFT_INFO_PANEL.x + 28, speed_y))
        speed_text = self.body_font.render(f"WALK  {walk_speed}     RUN  {run_speed}", True, (225, 232, 237))
        surface.blit(speed_text, (LEFT_INFO_PANEL.x + 28, speed_y + 27))

        selected_index = self.selected_index + 1
        roster_position = self.small_font.render(f"FIGHTER  {selected_index:02d} / {len(self.characters):02d}", True, (148, 174, 196))
        surface.blit(roster_position, (LEFT_INFO_PANEL.x + 28, LEFT_INFO_PANEL.bottom - 52))

    def _draw_moves(self, surface: pygame.Surface, character: dict) -> None:
        self._draw_panel(surface, RIGHT_INFO_PANEL, (9, 17, 29, 225))
        heading = self.section_font.render("MOVESET", True, (250, 248, 241))
        surface.blit(heading, (RIGHT_INFO_PANEL.x + 24, RIGHT_INFO_PANEL.y + 22))
        current = self.badge_font.render(
            f"PREVIEW: {self.preview_label}",
            True,
            (255, 209, 129),
        )
        surface.blit(current, (RIGHT_INFO_PANEL.x + 24, RIGHT_INFO_PANEL.y + 60))
        pygame.draw.line(
            surface,
            (82, 106, 130),
            (RIGHT_INFO_PANEL.x + 24, RIGHT_INFO_PANEL.y + 92),
            (RIGHT_INFO_PANEL.right - 24, RIGHT_INFO_PANEL.y + 92),
            1,
        )

        moves = self._move_list(character["key"])
        if not moves:
            empty = self.body_font.render("No move animations listed.", True, (188, 202, 216))
            surface.blit(empty, (RIGHT_INFO_PANEL.x + 24, RIGHT_INFO_PANEL.y + 124))
            return
        y = RIGHT_INFO_PANEL.y + 116
        for move_type, name in moves:
            tag = self.badge_font.render(move_type, True, (255, 209, 129) if move_type == "SPECIAL" else (131, 202, 228))
            surface.blit(tag, (RIGHT_INFO_PANEL.x + 24, y))
            move_name = self.body_font.render(name, True, (232, 237, 241))
            surface.blit(move_name, (RIGHT_INFO_PANEL.x + 24, y + 23))
            y += 58

    def _draw_preview(self, surface: pygame.Surface) -> None:
        label = self.badge_font.render("FIGHTER SHOWCASE", True, (221, 231, 239))
        surface.blit(label, label.get_rect(center=(PREVIEW_CENTER[0], 234)))
        if self.preview_player is None:
            return
        frame = self.preview_player.current_frame
        surface.blit(frame, frame.get_rect(midbottom=PREVIEW_CENTER))

    def _draw_roster(self, surface: pygame.Surface) -> None:
        self._draw_panel(surface, ROSTER_PANEL, (6, 12, 21, 239))
        section = self.badge_font.render(
            f"ROSTER  /  {self.current_category.upper()}",
            True,
            (201, 216, 228),
        )
        surface.blit(section, (ROSTER_PANEL.x + 18, ROSTER_PANEL.y + 2))
        controls = self.small_font.render(
            f"{KEY_BINDINGS.label('move_left')}/{KEY_BINDINGS.label('move_right')} fighter   "
            f"{KEY_BINDINGS.label('move_up')}/{KEY_BINDINGS.label('move_down')} category   "
            f"{KEY_BINDINGS.label('menu_confirm')} confirm",
            True,
            (167, 188, 207),
        )
        surface.blit(controls, controls.get_rect(midright=(ROSTER_PANEL.right - 18, ROSTER_PANEL.y + 13)))

        for visible_index, character_index in enumerate(self._category_character_indices()):
            character = self.characters[character_index]
            rect = self._roster_card_rect(visible_index)
            selected = character_index == self.selected_index
            chosen = character["key"] in self.selected_opponents
            fill = (93, 56, 37) if selected else (33, 44, 58)
            outline = (255, 190, 92) if selected else (105, 210, 148) if chosen else (76, 96, 116)
            pygame.draw.rect(surface, fill, rect, border_radius=12)
            pygame.draw.rect(surface, outline, rect, 3 if selected or chosen else 1, border_radius=12)
            image_rect = character["profile"].get_rect(
                center=(rect.centerx, rect.top + 70),
                width=PROFILE_SIZE[0],
                height=PROFILE_SIZE[1],
            )
            surface.blit(character["profile"], image_rect)
            name = self.card_font.render(character["display_name"].upper(), True, (250, 248, 241))
            surface.blit(name, name.get_rect(center=(rect.centerx, rect.bottom - 26)))
            number = self.badge_font.render(f"{visible_index + 1:02d}", True, (255, 209, 129) if selected else (151, 171, 190))
            surface.blit(number, (rect.x + 10, rect.y + 8))
            if chosen:
                selected_label = self.badge_font.render("SELECTED", True, (169, 240, 190))
                surface.blit(selected_label, selected_label.get_rect(midright=(rect.right - 10, rect.y + 18)))

    def draw(self, surface: pygame.Surface) -> None:
        self._draw_background(surface)
        self._draw_header(surface)
        self._draw_category_tabs(surface)
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
        self._draw_character_details(surface, character)
        self._draw_moves(surface, character)
        self._draw_roster(surface)
