from __future__ import annotations

import json
import math
from pathlib import Path


HandAnchor = tuple[float, float]
AnimationHandAnchors = dict[str, list[HandAnchor | None]]


def load_hand_anchors(path: Path) -> dict[str, AnimationHandAnchors]:
    if not path.exists():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError(f"Unsupported hand-anchor file format: {path}")

    characters = data.get("characters")
    if not isinstance(characters, dict):
        raise ValueError(f"Invalid characters object in hand-anchor file: {path}")

    anchors: dict[str, AnimationHandAnchors] = {}
    for character, animations in characters.items():
        if not isinstance(character, str) or not isinstance(animations, dict):
            raise ValueError(f"Invalid character entry in hand-anchor file: {path}")
        character_anchors: AnimationHandAnchors = {}
        for animation, points in animations.items():
            if not isinstance(animation, str) or not isinstance(points, list):
                raise ValueError(f"Invalid {character} animation anchors in {path}")
            parsed_points: list[HandAnchor | None] = []
            for point in points:
                if point is None:
                    parsed_points.append(None)
                    continue
                if (
                    not isinstance(point, list)
                    or len(point) != 2
                    or any(type(value) not in (int, float) or not math.isfinite(value) for value in point)
                ):
                    raise ValueError(f"Invalid {character} {animation} hand anchor in {path}")
                parsed_points.append((float(point[0]), float(point[1])))
            character_anchors[animation] = parsed_points
        anchors[character] = character_anchors
    return anchors
