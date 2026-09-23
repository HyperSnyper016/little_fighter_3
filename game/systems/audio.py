from __future__ import annotations

from pathlib import Path

import pygame


class AudioBank:
    muted = False

    @classmethod
    def toggle_mute(cls) -> bool:
        cls.muted = not cls.muted
        return cls.muted

    @classmethod
    def set_muted(cls, muted: bool) -> None:
        cls.muted = bool(muted)

    def __init__(self, root: Path) -> None:
        self.root = root
        self.sounds = self._load_sounds()
        self.step_toggle = 0
        self.miss_toggle = 0

    def _load_sound(self, file_name: str) -> pygame.mixer.Sound | None:
        path = self.root / file_name
        if not path.exists():
            return None
        return pygame.mixer.Sound(str(path))

    def _load_sounds(self) -> dict[str, pygame.mixer.Sound | None]:
        return {
            "footsteps1": self._load_sound("footsteps1.wav"),
            "footsteps2": self._load_sound("footsteps2.wav"),
            "draw_arrow": self._load_sound("draw_arrow.wav"),
            "shoot_arrow": self._load_sound("arrow_shot.wav"),
            "arrow_hit": self._load_sound("arrow_hit.wav"),
            "broken_arrow": self._load_sound("arrow_broken.wav"),
            "blade_swipe_sound": self._load_sound("blade_swipe_sound.wav"),
            "sword_swing": self._load_sound("sword_swing.wav"),
            "uppercut_shear": self._load_sound("uppercut_shear.wav"),
            "orb": self._load_sound("orb.wav"),
            "orb_burst": self._load_sound("orb_burst.wav"),
            "ice_break": self._load_sound("ice_break.wav"),
            "fire_knock": self._load_sound("fire_knock.wav"),
            "shadow_step": self._load_sound("shadow_step.wav"),
            "lazer": self._load_sound("lazer.wav"),
            "summon_bats": self._load_sound("summon_bats.wav"),
            "hit_guard": self._load_sound("hit_guard.wav"),
            "hit_miss1": self._load_sound("hit_miss1.wav"),
            "hit_miss2": self._load_sound("hit_miss2.wav"),
            "hit_success": self._load_sound("hit_success.wav"),
            "sword_cut": self._load_sound("sword_cut.wav"),
            "win": self._load_sound("win.wav"),
            "menu_start": self._load_sound("menu/menu_start.wav"),
            "menu_accept": self._load_sound("menu/menu_accept.wav"),
            "jump_throw": self._load_sound("jump1.wav"),
            "jump_land": self._load_sound("jump_land.wav"),
            "knockdown": self._load_sound("knockdown.wav"),
        }

    def play(self, name: str) -> None:
        if self.muted:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def play_footstep(self) -> None:
        self.step_toggle = 1 - self.step_toggle
        self.play("footsteps1" if self.step_toggle == 0 else "footsteps2")

    def play_hit_miss(self) -> None:
        self.miss_toggle = 1 - self.miss_toggle
        self.play("hit_miss1" if self.miss_toggle == 0 else "hit_miss2")
