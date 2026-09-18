from __future__ import annotations

from pathlib import Path

import pygame


class AudioBank:
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
            "hit_guard": self._load_sound("hit_guard.wav"),
            "hit_miss1": self._load_sound("hit_miss1.wav"),
            "hit_miss2": self._load_sound("hit_miss2.wav"),
            "hit_success": self._load_sound("hit_success.wav"),
            "jump": self._load_sound("jump1.wav"),
            "jump_land": self._load_sound("jump_land.wav"),
            "knockdown": self._load_sound("knockdown.wav"),
        }

    def play(self, name: str) -> None:
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def play_footstep(self) -> None:
        self.step_toggle = 1 - self.step_toggle
        self.play("footsteps1" if self.step_toggle == 0 else "footsteps2")

    def play_hit_miss(self) -> None:
        self.miss_toggle = 1 - self.miss_toggle
        self.play("hit_miss1" if self.miss_toggle == 0 else "hit_miss2")
