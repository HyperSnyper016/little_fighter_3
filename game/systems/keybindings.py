from __future__ import annotations

import json
from pathlib import Path

import pygame

from game.systems.audio import AudioBank


KEYBINDING_ROWS = (
    ("Move Up / Menu Up", "move_up", False),
    ("Move Down / Menu Down", "move_down", False),
    ("Move Left / Menu Left", "move_left", False),
    ("Move Right / Menu Right", "move_right", False),
    ("Sprint", "sprint", False),
    ("Attack", "attack", False),
    ("Jump", "jump", False),
    ("Defend", "defend", False),
    ("Menu Confirm", "menu_confirm", False),
    ("Main Menu Confirm (Space)", "main_menu_confirm_space", False),
    ("Back / Pause", "back_pause", False),
    ("Return to Menu (while paused)", "return_to_menu", False),
    ("Toggle Opponent", "toggle_opponent", False),
    ("History Page Up", "history_page_up", False),
    ("History Page Down", "history_page_down", False),
    ("Mute", "mute", False),
    ("Knock Down", "knock_down", True),
    ("Lift", "lift", True),
    ("Break Block", "break_block", True),
    ("Die", "die", True),
    ("Revive", "revive", True),
    ("Drink Held Item", "drink", True),
    ("Fire Knockdown", "fire_knockdown", True),
    ("Ice Knockdown", "ice_knockdown", True),
    ("Hurt Reaction", "hurt", True),
    ("Spawn Random Item", "spawn_item", True),
    ("Spawn Heavy Box", "spawn_heavy_box", True),
    ("Defeat Enemy", "defeat_enemy", True),
)


class KeyBindings:
    DEFAULTS = {
        "move_up": (pygame.K_UP,),
        "move_down": (pygame.K_DOWN,),
        "move_left": (pygame.K_LEFT,),
        "move_right": (pygame.K_RIGHT,),
        "sprint": (pygame.K_LSHIFT, pygame.K_RSHIFT),
        "attack": (pygame.K_j,),
        "jump": (pygame.K_k,),
        "defend": (pygame.K_l,),
        "menu_confirm": (pygame.K_j, pygame.K_RETURN, pygame.K_KP_ENTER),
        "main_menu_confirm_space": (pygame.K_SPACE,),
        "back_pause": (pygame.K_ESCAPE,),
        "return_to_menu": (pygame.K_m,),
        "toggle_opponent": (pygame.K_SPACE,),
        "history_page_up": (pygame.K_PAGEUP,),
        "history_page_down": (pygame.K_PAGEDOWN,),
        "mute": (pygame.K_F9,),
        "knock_down": (pygame.K_v,),
        "lift": (pygame.K_b,),
        "break_block": (pygame.K_g,),
        "die": (pygame.K_n,),
        "revive": (pygame.K_m,),
        "drink": (pygame.K_q,),
        "fire_knockdown": (pygame.K_f,),
        "ice_knockdown": (pygame.K_i,),
        "hurt": (pygame.K_h,),
        "spawn_item": (pygame.K_p,),
        "spawn_heavy_box": (pygame.K_o,),
        "defeat_enemy": (pygame.K_F10,),
    }

    def __init__(self) -> None:
        self.bindings = dict(self.DEFAULTS)
        self.load()

    @staticmethod
    def settings_file_path() -> Path:
        return AudioBank.settings_file_path().with_name("keybindings.json")

    def load(self) -> None:
        path = self.settings_file_path()
        if not path.exists():
            return

        settings = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            raise ValueError(f"Key bindings must be a JSON object: {path}")
        for action, key_codes in settings.items():
            if action not in self.DEFAULTS:
                continue
            if not isinstance(key_codes, list) or not key_codes:
                raise ValueError(f"Invalid key binding for {action}: {path}")
            if any(
                isinstance(key_code, bool)
                or not isinstance(key_code, int)
                or not pygame.key.name(key_code)
                for key_code in key_codes
            ):
                raise ValueError(f"Invalid key binding for {action}: {path}")
            self.bindings[action] = tuple(key_codes)

    def save(self) -> None:
        path = self.settings_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(
                {action: list(key_codes) for action, key_codes in self.bindings.items()},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(path)

    def set_binding(self, action: str, key_code: int) -> None:
        if action not in self.DEFAULTS:
            raise KeyError(f"Unknown key binding: {action}")
        if not pygame.key.name(key_code):
            raise ValueError(f"Unsupported key code: {key_code}")
        self.bindings[action] = (key_code,)
        self.save()

    def matches(self, action: str, key_code: int) -> bool:
        return key_code in self.bindings[action]

    def is_pressed(self, action: str, keys: pygame.key.ScancodeWrapper) -> bool:
        return any(keys[key_code] for key_code in self.bindings[action])

    def was_pressed(self, action: str, pressed_keys: set[int]) -> bool:
        return any(key_code in pressed_keys for key_code in self.bindings[action])

    def label(self, action: str) -> str:
        return " / ".join(
            pygame.key.name(key_code).replace("kp ", "numpad ").title()
            for key_code in self.bindings[action]
        )


if (
    len({action for _, action, _ in KEYBINDING_ROWS}) != len(KEYBINDING_ROWS)
    or {action for _, action, _ in KEYBINDING_ROWS} != set(KeyBindings.DEFAULTS)
):
    raise ValueError("Every key binding must appear in the settings list exactly once.")


KEY_BINDINGS = KeyBindings()
