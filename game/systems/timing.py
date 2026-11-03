from __future__ import annotations


MAX_FRAME_DELTA = 1.0 / 15.0


def clamp_frame_delta(frame_delta: float) -> float:
    return min(MAX_FRAME_DELTA, max(0.0, frame_delta))
