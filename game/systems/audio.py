from __future__ import annotations

from collections import deque
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
        self.freeze_basic_miss_toggle = 0
        self.fireball_toggle = 0
        self.fire_breath_toggle = 0
        self._sequence_channel: pygame.mixer.Channel | None = None
        self._sequence_queue: deque[pygame.mixer.Sound] = deque()

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
            "davis_uppercut": self._load_sound("davis_uppercut.wav"),
            "jack_blast": self._load_sound("jack_blast.wav"),
            "jack_yell": self._load_sound("jack_yell.wav"),
            "bat_die": self._load_sound("bat_die.wav"),
            "jan_burst": self._load_sound("jan_burst.wav"),
            "bird_summon": self._load_sound("summons/healing bird/bird_summon.wav"),
            "healed_target": self._load_sound("summons/healing bird/healed_target.wav"),
            "orb": self._load_sound("orb.wav"),
            "orb_burst": self._load_sound("orb_burst.wav"),
            "denis_ball": self._load_sound("denis_ball.wav"),
            "denis_orb_follow_create": self._load_sound("denis_orb_follow_create.wav"),
            "ice_break": self._load_sound("ice_break.wav"),
            "freeze": self._load_sound("freeze.wav"),
            "freeze_ball": self._load_sound("freeze_ball.wav"),
            "freeze_break": self._load_sound("freeze_break.wav"),
            "freeze_colum": self._load_sound("freeze_colum.wav"),
            "freeze_tornado": self._load_sound("freeze_tornado.wav"),
            "fire_knock": self._load_sound("fire_knock.wav"),
            "fireball_1": self._load_sound("fireball_1.wav"),
            "fireball_2": self._load_sound("fireball_2.wav"),
            "fire_breath_1": self._load_sound("fire_breath_1.wav"),
            "fire_breath_2": self._load_sound("fire_breath_2.wav"),
            "arrow_enchanted_shot": self._load_sound("arrow_enchanted_shot.wav"),
            "henry_wind": self._load_sound("henry_wind.wav"),
            "flute_1": self._load_sound("flute/flute_1.wav"),
            "flute_2": self._load_sound("flute/flute_2.wav"),
            "flute_3": self._load_sound("flute/flute_3.wav"),
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
            "drink_break": self._load_sound("drink/drink_break.wav"),
            "drink_land": self._load_sound("drink/drink_land.wav"),
            "drink_drink": self._load_sound("drink/drink_drink.wav"),
        }

    def play(self, name: str) -> None:
        if self.muted:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def play_sequence(self, names: tuple[str, ...]) -> None:
        if self.muted:
            return
        for name in names:
            sound = self.sounds.get(name)
            if sound is not None:
                self._sequence_queue.append(sound)
        self.update_sequences()

    def update_sequences(self) -> None:
        if not self._sequence_queue:
            return
        if self._sequence_channel is not None and self._sequence_channel.get_busy():
            return
        if self._sequence_channel is None:
            self._sequence_channel = pygame.mixer.find_channel()
        if self._sequence_channel is not None:
            self._sequence_channel.play(self._sequence_queue.popleft())

    def play_footstep(self) -> None:
        self.step_toggle = 1 - self.step_toggle
        self.play("footsteps1" if self.step_toggle == 0 else "footsteps2")

    def play_hit_miss(self) -> None:
        self.miss_toggle = 1 - self.miss_toggle
        self.play("hit_miss1" if self.miss_toggle == 0 else "hit_miss2")

    def play_freeze_basic_miss(self) -> None:
        self.play("hit_miss1" if self.freeze_basic_miss_toggle == 0 else "hit_miss2")
        self.freeze_basic_miss_toggle = 1 - self.freeze_basic_miss_toggle

    def play_fireball(self) -> None:
        self.fireball_toggle = 1 - self.fireball_toggle
        self.play("fireball_1" if self.fireball_toggle == 0 else "fireball_2")

    def play_fire_breath(self) -> None:
        self.fire_breath_toggle = 1 - self.fire_breath_toggle
        self.play("fire_breath_1" if self.fire_breath_toggle == 0 else "fire_breath_2")
