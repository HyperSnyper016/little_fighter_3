from __future__ import annotations

import pygame


class AnimationPlayer:
    def __init__(self, animations: dict[str, dict], initial_animation: str) -> None:
        self.animations = animations
        self.current_name = initial_animation
        self.frame_index = 0
        self.timer = 0.0
        self.current_frame = self.animations[initial_animation]["surfaces"][0]
        self.facing = 1
        self.finished = False

    def play(self, name: str) -> None:
        if name == self.current_name and not self.finished:
            return
        self.current_name = name
        self.frame_index = 0
        self.timer = 0.0
        self.finished = False

    def update(self, dt: float, facing: int) -> None:
        animation = self.animations[self.current_name]
        self.timer += dt
        duration = animation["frame_duration"]
        surfaces = animation["surfaces"]

        while self.timer >= duration:
            self.timer -= duration
            self.frame_index += 1
            if self.frame_index >= len(surfaces):
                if animation["loop"]:
                    self.frame_index = 0
                else:
                    self.frame_index = len(surfaces) - 1
                    self.finished = True
                    self.timer = 0.0
                    break

        frame = surfaces[self.frame_index]
        if facing != self.facing:
            self.facing = facing
        self.current_frame = frame if self.facing == 1 else pygame.transform.flip(frame, True, False)
