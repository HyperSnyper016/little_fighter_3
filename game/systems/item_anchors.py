from __future__ import annotations

import json
import math
from pathlib import Path


HandAnchor = tuple[float, float]
AnimationHandAnchors = dict[str, list[HandAnchor | None]]
CharacterHandAnchors = dict[str, AnimationHandAnchors]
WeaponHandAnchors = dict[str, CharacterHandAnchors]
WeaponReferenceSprites = dict[str, dict[str, dict[str, list[str | None]]]]
DEFAULT_WEAPON_ANCHOR_REFERENCE = "ice_sword"


def _read_anchor_data(path: Path) -> dict:
    if not path.exists():
        return {
            "version": 3,
            "characters": {},
            "weapons": {},
            "weapon_reference": DEFAULT_WEAPON_ANCHOR_REFERENCE,
            "weapon_reference_sprites": {},
        }

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") not in {1, 2, 3}:
        raise ValueError(f"Unsupported hand-anchor file format: {path}")
    if not isinstance(data.get("characters"), dict):
        raise ValueError(f"Invalid characters object in hand-anchor file: {path}")
    weapons = data.get("weapons", {})
    if not isinstance(weapons, dict):
        raise ValueError(f"Invalid weapons object in hand-anchor file: {path}")
    reference = data.get("weapon_reference", DEFAULT_WEAPON_ANCHOR_REFERENCE)
    if not isinstance(reference, str):
        raise ValueError(f"Invalid weapon reference in hand-anchor file: {path}")
    references = data.get("weapon_reference_sprites", {})
    _parse_weapon_reference_sprites(references, path)
    data["weapons"] = weapons
    data["weapon_reference"] = reference
    data["weapon_reference_sprites"] = references
    return data


def _parse_character_anchors(characters: object, path: Path) -> CharacterHandAnchors:
    if not isinstance(characters, dict):
        raise ValueError(f"Invalid characters object in hand-anchor file: {path}")
    anchors: CharacterHandAnchors = {}
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


def load_hand_anchors(path: Path) -> CharacterHandAnchors:
    data = _read_anchor_data(path)
    return _parse_character_anchors(data["characters"], path)


def load_weapon_hand_anchors(path: Path) -> WeaponHandAnchors:
    data = _read_anchor_data(path)
    anchors: WeaponHandAnchors = {}
    for weapon, characters in data["weapons"].items():
        if not isinstance(weapon, str):
            raise ValueError(f"Invalid weapon entry in hand-anchor file: {path}")
        anchors[weapon] = _parse_character_anchors(characters, path)
    return anchors


def _parse_weapon_reference_sprites(
    references: object,
    path: Path,
) -> WeaponReferenceSprites:
    if not isinstance(references, dict):
        raise ValueError(f"Invalid weapon reference sprites object in hand-anchor file: {path}")
    parsed: WeaponReferenceSprites = {}
    for weapon, characters in references.items():
        if not isinstance(weapon, str) or not isinstance(characters, dict):
            raise ValueError(f"Invalid weapon reference entry in hand-anchor file: {path}")
        parsed_characters: dict[str, dict[str, list[str | None]]] = {}
        for character, animations in characters.items():
            if not isinstance(character, str) or not isinstance(animations, dict):
                raise ValueError(f"Invalid {weapon} character reference entry in {path}")
            parsed_animations: dict[str, list[str | None]] = {}
            for animation, sprites in animations.items():
                if (
                    not isinstance(animation, str)
                    or not isinstance(sprites, list)
                    or any(sprite is not None and not isinstance(sprite, str) for sprite in sprites)
                ):
                    raise ValueError(f"Invalid {weapon} {character} reference sprites in {path}")
                parsed_animations[animation] = sprites
            parsed_characters[character] = parsed_animations
        parsed[weapon] = parsed_characters
    return parsed


def load_weapon_reference_sprites(path: Path) -> WeaponReferenceSprites:
    data = _read_anchor_data(path)
    return _parse_weapon_reference_sprites(data["weapon_reference_sprites"], path)


def load_weapon_anchor_reference(path: Path) -> str:
    return _read_anchor_data(path)["weapon_reference"]
