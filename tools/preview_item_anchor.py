from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import pygame


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHARACTER_ROOT = PROJECT_ROOT / "assets" / "sprites" / "characters"
ITEM_ROOT = PROJECT_ROOT / "assets" / "sprites" / "item_sprites"
MILK_ROOT = ITEM_ROOT / "consumables" / "milk"
HEAVY_CARRY_ITEM_ROOT = ITEM_ROOT / "throwables" / "heavy_box"
WEAPON_ROOT = ITEM_ROOT / "weapons"
WEAPON_ANCHOR_REFERENCE = "ice_sword"
ANCHOR_FILE = ITEM_ROOT / "hand_anchors.json"
IMAGE_EXTENSIONS = {".bmp", ".png"}
ANIMATION_FOLDERS = {
    "idle": ("idle",),
    "walk": ("movement", "walking"),
    "run": ("movement", "sprinting"),
    "drink": ("hold_item", "drink"),
    "spawn": ("hold_item", "throw_item", "ground_throw"),
    "jump_throw": ("hold_item", "throw_item", "jump_throw"),
    "get_up": ("fall", "get_up"),
    "heavy_carry_walk": ("hold_item", "heavy_carry", "walk"),
    "heavy_carry_sprint": ("hold_item", "heavy_carry", "sprint"),
    "heavy_carry_throw": ("hold_item", "heavy_carry", "throw"),
    "weapon_idle": ("idle",),
    "weapon_jump_normal": ("movement", "jump_actions", "basic_jump"),
    "weapon_jump_second": ("movement", "jump_actions", "second_jump"),
    "weapon_ground_throw": ("hold_item", "throw_item", "ground_throw"),
    "weapon_jump_throw": ("hold_item", "throw_item", "jump_throw"),
    "weapon_basic_attack": ("hold_item", "weapon_carry", "basic_attack"),
    "weapon_jump_attack": ("hold_item", "weapon_carry", "jump_attack"),
    "weapon_sprint_basic_attack": ("hold_item", "weapon_carry", "sprint_basic_attack"),
    "weapon_sprint_jump_basic_attack": ("hold_item", "weapon_carry", "sprint_jump_basic_attack"),
    "weapon_get_up": ("fall", "get_up"),
}
MILK_ANIMATIONS = ("idle", "walk", "run", "drink", "spawn", "jump_throw", "get_up")
HEAVY_CARRY_ANIMATIONS = (
    "heavy_carry_walk",
    "heavy_carry_sprint",
    "heavy_carry_throw",
)
WEAPON_ANIMATIONS = (
    "weapon_idle",
    "weapon_jump_normal",
    "weapon_jump_second",
    "weapon_ground_throw",
    "weapon_jump_throw",
    "weapon_basic_attack",
    "weapon_jump_attack",
    "weapon_sprint_basic_attack",
    "weapon_sprint_jump_basic_attack",
    "weapon_get_up",
)
ITEM_ANIMATIONS = {
    "milk": MILK_ANIMATIONS,
    "heavy-carry": HEAVY_CARRY_ANIMATIONS,
    "weapon": WEAPON_ANIMATIONS,
}
ANIMATION_ALIASES = {"ground_throw": "spawn"}
FOLDER_ANIMATION_KEYS: dict[tuple[str, ...], str] = {}
for animation, folder in ANIMATION_FOLDERS.items():
    FOLDER_ANIMATION_KEYS.setdefault(folder, animation)
HEAVY_CARRY_FOLDER_ANIMATION_KEYS = {
    ("hold_item", "heavy_carry", "walk"): "heavy_carry_walk",
    ("hold_item", "heavy_carry", "sprint"): "heavy_carry_sprint",
    ("hold_item", "heavy_carry", "throw"): "heavy_carry_throw",
}
WEAPON_FOLDER_ANIMATION_KEYS = {
    ("idle",): "weapon_idle",
    ("movement", "jump_actions", "basic_jump"): "weapon_jump_normal",
    ("movement", "jump_actions", "second_jump"): "weapon_jump_second",
    ("hold_item", "throw_item", "ground_throw"): "weapon_ground_throw",
    ("hold_item", "throw_item", "jump_throw"): "weapon_jump_throw",
    ("fall", "get_up"): "weapon_get_up",
    ("hold_item", "weapon_carry", "basic_attack"): "weapon_basic_attack",
    ("hold_item", "weapon_carry", "jump_attack"): "weapon_jump_attack",
    ("hold_item", "weapon_carry", "sprint_basic_attack"): "weapon_sprint_basic_attack",
    ("hold_item", "weapon_carry", "sprint_jump_basic_attack"): "weapon_sprint_jump_basic_attack",
}
OPTIONAL_ANIMATIONS = {
    "spawn",
    "jump_throw",
    "heavy_carry_walk",
    "heavy_carry_sprint",
    "heavy_carry_throw",
    *WEAPON_ANIMATIONS,
}
FALLBACK_ANCHOR = (0.30, 0.62)
HEAVY_CARRY_FALLBACK_ANCHOR = (0.50, 0.18)


@dataclass(frozen=True)
class SpriteTask:
    character: str
    animation: str
    frame_index: int
    frame_count: int
    path: Path
    item_type: str = "milk"
    weapon: str | None = None
    reference_sprite: str | None = None


def _natural_sort_key(path: Path) -> list[str | int]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def _image_paths(folder: Path) -> list[Path]:
    return sorted(
        (path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS),
        key=_natural_sort_key,
    )


def _character_names() -> list[str]:
    return sorted(path.name for path in CHARACTER_ROOT.iterdir() if path.is_dir() and not path.name.startswith("_"))


def _weapon_names() -> list[str]:
    if not WEAPON_ROOT.is_dir():
        return []
    return sorted(
        path.name
        for path in WEAPON_ROOT.iterdir()
        if path.is_dir()
        and not path.name.startswith("_")
        and (path / "holding" / "idle").is_dir()
        and (path / "holding" / "swing").is_dir()
        and _image_paths(path / "holding" / "idle")
        and _image_paths(path / "holding" / "swing")
    )


def _load_frame(path: Path, scale: float = 1.0) -> pygame.Surface:
    frame = pygame.image.load(str(path)).convert()
    frame.set_colorkey((0, 0, 0))
    if scale != 1.0:
        frame = pygame.transform.scale(
            frame,
            (round(frame.get_width() * scale), round(frame.get_height() * scale)),
        )
    return frame


def _load_trimmed_item_frames(folder: Path) -> list[pygame.Surface]:
    paths = _image_paths(folder)
    if not paths:
        raise FileNotFoundError(f"No item sprite frames found in {folder}")

    frames: list[pygame.Surface] = []
    for path in paths:
        frame = _load_frame(path, scale=1.2)
        bounds = pygame.mask.from_surface(frame).get_bounding_rects()
        if not bounds:
            raise ValueError(f"Item sprite frame is fully transparent: {path}")

        left = min(rect.left for rect in bounds)
        top = min(rect.top for rect in bounds)
        right = max(rect.right for rect in bounds)
        bottom = max(rect.bottom for rect in bounds)
        content = pygame.Rect(left, top, right - left, bottom - top)
        trimmed = pygame.Surface(content.size).convert()
        trimmed.fill((0, 0, 0))
        trimmed.blit(frame, (0, 0), content)
        trimmed.set_colorkey((0, 0, 0))
        frames.append(trimmed)
    return frames


def _tasks_for_folder(
    character: str,
    animation: str,
    folder: Path,
    item_type: str = "milk",
    weapon: str | None = None,
) -> list[SpriteTask]:
    if not folder.is_dir():
        raise FileNotFoundError(f"{character} {animation} sprite folder not found: {folder}")
    paths = _image_paths(folder)
    if not paths:
        raise FileNotFoundError(f"No {character} {animation} frames found in {folder}")
    return [
        SpriteTask(character, animation, frame_index, len(paths), path, item_type, weapon)
        for frame_index, path in enumerate(paths)
    ]


def _specific_folder_task_group(
    selector: str,
    animation_key: str | None,
) -> tuple[str, str, Path]:
    root = CHARACTER_ROOT.resolve()
    selected_path = Path(selector)
    folder = (selected_path if selected_path.is_absolute() else root / selected_path).resolve()
    try:
        relative_parts = folder.relative_to(root).parts
    except ValueError as error:
        raise ValueError(f"Sprite folder must be inside {root}: {selector}") from error
    if len(relative_parts) < 2:
        raise ValueError(f"Select a sprite folder beneath a character folder: {selector}")

    character, *folder_parts = relative_parts
    if character not in _character_names():
        raise ValueError(f"Unknown character sprite folder: {selector}")
    inferred_key = FOLDER_ANIMATION_KEYS.get(tuple(folder_parts), "_".join(folder_parts))
    return character, animation_key or inferred_key, folder


def _animation_folder(character: str, animation: str) -> Path:
    folder = CHARACTER_ROOT / character
    for part in ANIMATION_FOLDERS[animation]:
        folder /= part
    return folder


def _build_tasks(
    character_names: list[str],
    animations: list[str] | None = None,
    folders: list[str] | None = None,
    animation_key: str | None = None,
    item_type: str = "milk",
    weapon_names: list[str] | None = None,
) -> list[SpriteTask]:
    tasks: list[SpriteTask] = []
    if folders:
        for selector in folders:
            character, animation, folder = _specific_folder_task_group(selector, animation_key)
            if item_type == "heavy-carry":
                relative_parts = folder.relative_to(CHARACTER_ROOT).parts[1:]
                if animation_key is not None:
                    if animation_key not in HEAVY_CARRY_ANIMATIONS:
                        raise ValueError(
                            "Heavy-carry folders only support heavy_carry_walk, "
                            "heavy_carry_sprint, and heavy_carry_throw."
                        )
                else:
                    animation = HEAVY_CARRY_FOLDER_ANIMATION_KEYS.get(relative_parts, "")
                    if not animation:
                        raise ValueError(
                            "Heavy-carry calibration only supports the character "
                            "heavy_carry walk, sprint, and throw folders."
                        )
            if item_type == "weapon" and animation_key is None:
                relative_parts = folder.relative_to(CHARACTER_ROOT).parts[1:]
                animation = WEAPON_FOLDER_ANIMATION_KEYS.get(relative_parts, animation)
            selected_weapons = (weapon_names or [WEAPON_ANCHOR_REFERENCE]) if item_type == "weapon" else [None]
            for weapon in selected_weapons:
                tasks.extend(_tasks_for_folder(character, animation, folder, item_type, weapon))
        return _attach_weapon_reference_sprites(tasks)

    selected_animations = [
        ANIMATION_ALIASES.get(animation, animation)
        for animation in (animations or ITEM_ANIMATIONS[item_type])
    ]
    selected_weapons = (weapon_names or [WEAPON_ANCHOR_REFERENCE]) if item_type == "weapon" else [None]
    for weapon in selected_weapons:
        for character in character_names:
            for animation in selected_animations:
                folder = _animation_folder(character, animation)
                if animation in OPTIONAL_ANIMATIONS and not _image_paths(folder):
                    continue
                animation_tasks = _tasks_for_folder(character, animation, folder, item_type, weapon)
                tasks.extend(animation_tasks)
    return _attach_weapon_reference_sprites(tasks)


def _empty_anchor_data() -> dict:
    return {
        "version": 3,
        "characters": {},
        "weapons": {},
        "weapon_reference": WEAPON_ANCHOR_REFERENCE,
        "weapon_reference_sprites": {},
    }


def _weapon_reference_sprite_choices(task: SpriteTask) -> list[str]:
    if task.animation == "weapon_idle":
        folder = WEAPON_ROOT / WEAPON_ANCHOR_REFERENCE / "holding" / "idle"
    elif task.animation in {"weapon_ground_throw", "weapon_jump_throw"}:
        folder = WEAPON_ROOT / WEAPON_ANCHOR_REFERENCE / "throw"
    else:
        folder = WEAPON_ROOT / WEAPON_ANCHOR_REFERENCE / "holding" / "swing"
    paths = _image_paths(folder)
    if not paths:
        raise FileNotFoundError(f"No canonical weapon reference frames found in {folder}")
    return [path.relative_to(ITEM_ROOT).as_posix() for path in paths]


def _load_weapon_preview_frame(task: SpriteTask, reference_sprite: str) -> pygame.Surface:
    if task.weapon is None:
        raise ValueError("Weapon preview task is missing its weapon name.")
    reference_name = Path(reference_sprite).stem.casefold()
    if task.animation == "weapon_idle":
        weapon_folder = WEAPON_ROOT / task.weapon / "holding" / "idle"
    elif task.animation in {"weapon_ground_throw", "weapon_jump_throw"}:
        weapon_folder = WEAPON_ROOT / task.weapon / "throw"
    else:
        weapon_folder = WEAPON_ROOT / task.weapon / "holding" / "swing"
    matching_paths = [
        path for path in _image_paths(weapon_folder)
        if path.stem.casefold() == reference_name
    ]
    if len(matching_paths) > 1:
        raise ValueError(f"Duplicate weapon sprite name {reference_name} in {weapon_folder}")
    if matching_paths:
        return _load_frame(matching_paths[0], scale=1.2)
    return _load_frame(ITEM_ROOT / reference_sprite, scale=1.2)


def _weapon_reference_sprite(task: SpriteTask) -> str:
    choices = _weapon_reference_sprite_choices(task)
    reference_index = (
        0
        if task.animation == "weapon_idle" or task.frame_count <= 1
        else round(task.frame_index * (len(choices) - 1) / (task.frame_count - 1))
    )
    return choices[reference_index]


def _attach_weapon_reference_sprites(tasks: list[SpriteTask]) -> list[SpriteTask]:
    return [
        replace(task, reference_sprite=_weapon_reference_sprite(task))
        if task.item_type == "weapon"
        else task
        for task in tasks
    ]


def _validate_character_anchors(characters: object, path: Path) -> None:
    if not isinstance(characters, dict):
        raise ValueError(f"Invalid characters object in anchor file: {path}")
    for character, animations in characters.items():
        if not isinstance(character, str) or not isinstance(animations, dict):
            raise ValueError(f"Invalid character entry in anchor file: {path}")
        for animation, points in animations.items():
            if not isinstance(animation, str) or not isinstance(points, list):
                raise ValueError(f"Invalid {character} {animation} anchors in {path}")
            for point in points:
                if point is None:
                    continue
                if (
                    not isinstance(point, list)
                    or len(point) != 2
                    or any(type(value) not in (int, float) or not math.isfinite(value) for value in point)
                ):
                    raise ValueError(f"Invalid {character} {animation} anchor point in {path}")


def _validate_weapon_reference_sprites(references: object, path: Path) -> None:
    if not isinstance(references, dict):
        raise ValueError(f"Invalid weapon reference sprites object in anchor file: {path}")
    for weapon, characters in references.items():
        if not isinstance(weapon, str) or not isinstance(characters, dict):
            raise ValueError(f"Invalid weapon reference entry in anchor file: {path}")
        for character, animations in characters.items():
            if not isinstance(character, str) or not isinstance(animations, dict):
                raise ValueError(f"Invalid {weapon} character reference entry in {path}")
            for animation, sprites in animations.items():
                if (
                    not isinstance(animation, str)
                    or not isinstance(sprites, list)
                    or any(sprite is not None and not isinstance(sprite, str) for sprite in sprites)
                ):
                    raise ValueError(f"Invalid {weapon} {character} reference sprites in {path}")


def _load_anchor_data(path: Path) -> dict:
    if not path.exists():
        return _empty_anchor_data()

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") not in {1, 2, 3}:
        raise ValueError(f"Unsupported anchor file format: {path}")
    data.setdefault("weapons", {})
    data.setdefault("weapon_reference", WEAPON_ANCHOR_REFERENCE)
    data.setdefault("weapon_reference_sprites", {})
    _validate_character_anchors(data.get("characters"), path)
    weapons = data.get("weapons")
    if not isinstance(weapons, dict):
        raise ValueError(f"Invalid weapons object in anchor file: {path}")
    for weapon, characters in weapons.items():
        if not isinstance(weapon, str):
            raise ValueError(f"Invalid weapon entry in anchor file: {path}")
        _validate_character_anchors(characters, path)
    if not isinstance(data["weapon_reference"], str):
        raise ValueError(f"Invalid weapon reference in anchor file: {path}")
    _validate_weapon_reference_sprites(data["weapon_reference_sprites"], path)
    data["version"] = 3
    return data


def _save_anchor_data(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def _existing_anchor(data: dict, task: SpriteTask) -> tuple[float, float] | None:
    if task.item_type == "weapon":
        if task.weapon is None:
            raise ValueError("Weapon anchor task is missing its weapon name.")
        characters = data["weapons"].get(task.weapon, {})
    else:
        characters = data["characters"]
    point = characters.get(task.character, {}).get(task.animation, [])
    if task.frame_index >= len(point) or point[task.frame_index] is None:
        return None
    return float(point[task.frame_index][0]), float(point[task.frame_index][1])


def _ensure_anchor_slot(data: dict, task: SpriteTask) -> list:
    if task.item_type == "weapon":
        if task.weapon is None:
            raise ValueError("Weapon anchor task is missing its weapon name.")
        characters = data["weapons"].setdefault(task.weapon, {})
    else:
        characters = data["characters"]
    character = characters.setdefault(task.character, {})
    points = character.setdefault(task.animation, [None] * task.frame_count)
    if len(points) < task.frame_count:
        points.extend([None] * (task.frame_count - len(points)))
    elif len(points) > task.frame_count:
        del points[task.frame_count:]
    return points


def _ensure_reference_slot(
    data: dict,
    task: SpriteTask,
    reference_sprite: str | None = None,
) -> list:
    selected_reference = reference_sprite or task.reference_sprite
    if task.weapon is None or selected_reference is None:
        raise ValueError("Weapon anchor task is missing its reference sprite.")
    characters = data["weapon_reference_sprites"].setdefault(data["weapon_reference"], {})
    character = characters.setdefault(task.character, {})
    references = character.setdefault(task.animation, [None] * task.frame_count)
    if len(references) < task.frame_count:
        references.extend([None] * (task.frame_count - len(references)))
    elif len(references) > task.frame_count:
        del references[task.frame_count:]
    references[task.frame_index] = selected_reference
    return references


def _fill_existing_weapon_references(data: dict, tasks: list[SpriteTask]) -> bool:
    changed = False
    for task in tasks:
        if task.item_type != "weapon" or _existing_anchor(data, task) is None:
            continue
        if task.reference_sprite is None or task.weapon is None:
            raise ValueError("Weapon anchor task is missing its reference sprite.")
        characters = data["weapon_reference_sprites"].setdefault(data["weapon_reference"], {})
        character = characters.setdefault(task.character, {})
        references = character.setdefault(task.animation, [])
        if len(references) <= task.frame_index:
            references.extend([None] * (task.frame_index + 1 - len(references)))
        if references[task.frame_index] is None:
            references[task.frame_index] = (
                _existing_reference_sprite(data, task) or task.reference_sprite
            )
            changed = True
    return changed


def _next_task_index(
    tasks: list[SpriteTask],
    data: dict,
    start_index: int,
    recalibrate: bool,
) -> int:
    for index in range(start_index, len(tasks)):
        if recalibrate or _existing_anchor(data, tasks[index]) is None:
            return index
    return len(tasks)


def _task_start_index(tasks: list[SpriteTask], data: dict, recalibrate: bool) -> int:
    return _next_task_index(tasks, data, 0, recalibrate)


def _draw_crosshair(surface: pygame.Surface, position: tuple[int, int]) -> None:
    x, y = position
    color = (40, 255, 120)
    pygame.draw.circle(surface, color, position, 8, 1)
    pygame.draw.line(surface, color, (x - 13, y), (x + 13, y), 1)
    pygame.draw.line(surface, color, (x, y - 13), (x, y + 13), 1)


def _draw_preview(
    surface: pygame.Surface,
    character: pygame.Surface,
    item: pygame.Surface | None,
    character_pos: tuple[int, int],
    item_center: tuple[int, int],
    facing: str,
) -> None:
    surface.fill((62, 66, 72))
    character_frame = character if facing == "right" else pygame.transform.flip(character, True, False)
    surface.blit(character_frame, character_pos)
    if item is not None:
        item_frame = item if facing == "right" else pygame.transform.flip(item, True, False)
        surface.blit(item_frame, item_frame.get_rect(center=item_center))
    _draw_crosshair(surface, item_center)


def _current_item_center(
    data: dict,
    task: SpriteTask,
    character_size: tuple[int, int],
    character_pos: tuple[int, int],
    facing: str,
) -> list[int]:
    width, height = character_size
    if task.animation.startswith("heavy_carry_"):
        default_anchor = HEAVY_CARRY_FALLBACK_ANCHOR
    else:
        default_anchor = (0.68, 0.22) if task.animation == "drink" else FALLBACK_ANCHOR
    anchor = _existing_anchor(data, task) or default_anchor
    facing_x = anchor[0] if facing == "right" else 1 - anchor[0]
    return [
        round(character_pos[0] + width * facing_x),
        round(character_pos[1] + height * anchor[1]),
    ]


def _store_current_anchor(
    data: dict,
    task: SpriteTask,
    character_size: tuple[int, int],
    character_pos: tuple[int, int],
    item_center: tuple[int, int],
    facing: str,
    reference_sprite: str | None = None,
) -> tuple[float, float]:
    width, height = character_size
    local_x = (item_center[0] - character_pos[0]) / width
    x = local_x if facing == "right" else 1 - local_x
    y = (item_center[1] - character_pos[1]) / height
    point = [round(x, 6), round(y, 6)]
    points = _ensure_anchor_slot(data, task)
    points[task.frame_index] = point
    if task.item_type == "weapon":
        _ensure_reference_slot(data, task, reference_sprite)
    return point[0], point[1]


def _existing_reference_sprite(data: dict, task: SpriteTask) -> str | None:
    reference_weapons = dict.fromkeys((data["weapon_reference"], task.weapon))
    for reference_weapon in reference_weapons:
        if reference_weapon is None:
            continue
        references = data["weapon_reference_sprites"].get(reference_weapon, {})
        points = references.get(task.character, {}).get(task.animation, [])
        if task.frame_index < len(points) and points[task.frame_index] is not None:
            return points[task.frame_index]
    return None


def main() -> int:
    names = _character_names()
    weapons = _weapon_names()
    parser = argparse.ArgumentParser(
        description=(
            "Calibrate per-frame anchors for milk, heavy-carry items, and weapons. "
            "Only characters with authored sprite frames are included."
        )
    )
    parser.add_argument("--character", choices=names, help="Calibrate only this character (default: all characters)")
    parser.add_argument(
        "--item",
        choices=tuple(ITEM_ANIMATIONS),
        help="Item/anchor group to calibrate; by default, calibrates all supported groups",
    )
    parser.add_argument(
        "--weapon",
        choices=weapons,
        action="append",
        help="Calibrate only this weapon; repeat to select several (requires --item weapon)",
    )
    parser.add_argument(
        "--animation",
        choices=(*ANIMATION_FOLDERS, *ANIMATION_ALIASES),
        action="append",
        help="Calibrate only these animation folders; may be repeated",
    )
    parser.add_argument(
        "--folder",
        action="append",
        metavar="CHARACTER\\PATH",
        help=(
            "Calibrate a specific folder relative to assets/sprites/characters; "
            "may be repeated, for example deep\\hold_item\\drink"
        ),
    )
    parser.add_argument(
        "--animation-key",
        help="Anchor key for a custom --folder path (defaults to the relative folder path joined with underscores)",
    )
    parser.add_argument("--facing", choices=("right", "left"), default="right")
    parser.add_argument("--scale", type=float, default=2.0, help="Character sprite scale used in-game (default: 2)")
    parser.add_argument("--anchors-path", type=Path, default=ANCHOR_FILE, help="Anchor JSON path")
    parser.add_argument("--recalibrate", action="store_true", help="Start at the beginning, including saved anchors")
    args = parser.parse_args()
    if args.scale <= 0:
        parser.error("--scale must be greater than zero")
    if args.folder and (args.character or args.animation):
        parser.error("--folder cannot be combined with --character or --animation")
    if args.folder and args.item is None:
        parser.error("--folder requires --item milk, heavy-carry, or weapon")
    if args.weapon and args.item != "weapon":
        parser.error("--weapon requires --item weapon")
    if args.animation_key and (not args.folder or len(args.folder) != 1):
        parser.error("--animation-key requires exactly one --folder")
    item_types = tuple(ITEM_ANIMATIONS) if args.item is None else (args.item,)
    available_animations = {
        animation
        for item_type in item_types
        for animation in ITEM_ANIMATIONS[item_type]
    }
    if args.animation and any(
        ANIMATION_ALIASES.get(animation, animation) not in available_animations
        for animation in args.animation
    ):
        parser.error(f"--animation choices are: {', '.join(sorted(available_animations))}")

    character_names = [args.character] if args.character else names
    try:
        tasks: list[SpriteTask] = []
        for item_type in item_types:
            item_animations = (
                [
                    animation
                    for animation in args.animation
                    if ANIMATION_ALIASES.get(animation, animation) in ITEM_ANIMATIONS[item_type]
                ]
                if args.animation
                else None
            )
            if args.animation and not item_animations:
                continue
            tasks.extend(
                _build_tasks(
                    character_names,
                    item_animations,
                    args.folder,
                    args.animation_key,
                    item_type=item_type,
                    weapon_names=args.weapon if item_type == "weapon" else None,
                )
            )
        if not tasks:
            raise FileNotFoundError("No character sprite frames found for the selected animation folders")
        anchor_data = _load_anchor_data(args.anchors_path)
        if _fill_existing_weapon_references(anchor_data, tasks):
            _save_anchor_data(args.anchors_path, anchor_data)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(error, file=sys.stderr)
        return 1

    start_index = _task_start_index(tasks, anchor_data, args.recalibrate)
    if start_index == len(tasks):
        print(f"All {len(tasks)} item anchors are already calibrated in {args.anchors_path}.")
        print("Run again with --recalibrate to review or adjust them.")
        return 0
    pygame.init()
    try:
        pygame.display.set_mode((1, 1))
        task_item_types = {task.item_type for task in tasks}
        holding_frames: dict[str, pygame.Surface] = {}
        if "milk" in task_item_types:
            holding_frames["milk"] = _load_trimmed_item_frames(MILK_ROOT / "holding" / "idle")[0]
        if "heavy-carry" in task_item_types:
            holding_frames["heavy-carry"] = _load_trimmed_item_frames(HEAVY_CARRY_ITEM_ROOT / "holding")[0]
        drink_tasks = [task for task in tasks if task.item_type == "milk" and task.animation == "drink"]
        milk_drink_frames = _load_trimmed_item_frames(MILK_ROOT / "drink") if drink_tasks else []
        character_frame_counts = {task.character: task.frame_count for task in drink_tasks}
        mismatched_characters = [
            character
            for character, frame_count in character_frame_counts.items()
            if frame_count != len(milk_drink_frames)
        ]
        if mismatched_characters:
            raise ValueError(
                "Milk drink frames must match each character's drink frame count; "
                f"item has {len(milk_drink_frames)} frames, mismatch: {', '.join(mismatched_characters)}"
            )
        screen: pygame.Surface | None = None
        font = pygame.font.Font(None, 24)
        clock = pygame.time.Clock()
        task_index = start_index
        character: pygame.Surface
        character_pos: tuple[int, int]
        item_center: list[int]
        current_item_frame: pygame.Surface | None
        current_reference_choices: list[str] = []
        current_reference_index = 0
        current_reference_sprite: str | None = None

        def load_task() -> None:
            nonlocal screen, character, character_pos, item_center, current_item_frame
            nonlocal current_reference_choices, current_reference_index, current_reference_sprite
            task = tasks[task_index]
            character = _load_frame(task.path, scale=args.scale)
            if task.item_type == "weapon":
                if task.weapon is None:
                    raise RuntimeError("Weapon anchor task is missing its weapon name.")
                current_item_frame = None
                current_reference_choices = _weapon_reference_sprite_choices(task)
                current_reference_sprite = (
                    _existing_reference_sprite(anchor_data, task) or task.reference_sprite
                )
                if current_reference_sprite not in current_reference_choices:
                    current_reference_sprite = task.reference_sprite or current_reference_choices[0]
                current_reference_index = current_reference_choices.index(current_reference_sprite)
                current_item_frame = _load_weapon_preview_frame(task, current_reference_sprite)
            else:
                current_reference_choices = []
                current_reference_sprite = None
                current_item_frame = (
                    milk_drink_frames[task.frame_index]
                    if task.item_type == "milk" and task.animation == "drink"
                    else holding_frames[task.item_type]
                )
            width, height = character.get_size()
            item_width = current_item_frame.get_width() if current_item_frame else 0
            item_height = current_item_frame.get_height() if current_item_frame else 0
            canvas_size = (
                max(900, width + item_width * 2 + 180),
                max(700, height + item_height + 180),
            )
            character_pos = ((canvas_size[0] - width) // 2, canvas_size[1] - height - 90)
            item_center = _current_item_center(anchor_data, task, character.get_size(), character_pos, args.facing)
            screen = pygame.display.set_mode(canvas_size)
            anchor_kind = f"{task.weapon} weapon" if task.weapon else task.item_type
            pygame.display.set_caption(
                f"{anchor_kind} anchor: {task.character} / {task.animation} "
                f"{task.frame_index + 1}/{task.frame_count} ({task_index + 1}/{len(tasks)})"
            )

        load_task()
        dragging = False
        running = True
        while running:
            task = tasks[task_index]
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                    event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
                ):
                    running = False
                elif (
                    event.type == pygame.MOUSEWHEEL
                    and task.item_type == "weapon"
                    and task.animation != "weapon_idle"
                    and current_reference_choices
                    and event.y
                ):
                    current_reference_index = (
                        current_reference_index - event.y
                    ) % len(current_reference_choices)
                    current_reference_sprite = current_reference_choices[current_reference_index]
                    current_item_frame = _load_weapon_preview_frame(task, current_reference_sprite)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    dragging = True
                    item_center[:] = event.pos
                elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    dragging = False
                elif event.type == pygame.MOUSEMOTION and dragging:
                    item_center[:] = event.pos
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        point = _store_current_anchor(
                            anchor_data,
                            task,
                            character.get_size(),
                            character_pos,
                            (item_center[0], item_center[1]),
                            args.facing,
                            reference_sprite=current_reference_sprite,
                        )
                        _save_anchor_data(args.anchors_path, anchor_data)
                        print(
                            f"Saved {task.weapon + ' ' if task.weapon else ''}{task.character} "
                            f"{task.animation} frame {task.frame_index + 1}: "
                            f"({point[0]:.3f}, {point[1]:.3f})"
                        )
                        task_index = _next_task_index(tasks, anchor_data, task_index + 1, args.recalibrate)
                        if task_index >= len(tasks):
                            print(f"Reached the end of the calibration list. Saved anchors are in {args.anchors_path}.")
                            running = False
                        else:
                            load_task()
                    elif event.key == pygame.K_n:
                        task_index = _next_task_index(tasks, anchor_data, task_index + 1, args.recalibrate)
                        if task_index >= len(tasks):
                            print(f"Calibration finished. Saved anchors are in {args.anchors_path}.")
                            running = False
                        else:
                            load_task()
                    elif event.key == pygame.K_BACKSPACE:
                        task_index = max(0, task_index - 1)
                        load_task()
                    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                        step = 5 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
                        if event.key == pygame.K_LEFT:
                            item_center[0] -= step
                        elif event.key == pygame.K_RIGHT:
                            item_center[0] += step
                        elif event.key == pygame.K_UP:
                            item_center[1] -= step
                        else:
                            item_center[1] += step

            if running and screen is not None:
                task = tasks[task_index]
                _draw_preview(
                    screen,
                    character,
                    current_item_frame,
                    character_pos,
                    (item_center[0], item_center[1]),
                    args.facing,
                )
                progress = (
                    f"{task.character} | {task.animation} frame {task.frame_index + 1}/{task.frame_count} "
                    f"| {task_index + 1}/{len(tasks)} overall"
                )
                if task.weapon:
                    progress += f" | {task.weapon}"
                    if current_reference_sprite:
                        progress += f" | ref: {Path(current_reference_sprite).name}"
                controls = "Drag: place item | Arrows: nudge (Shift: 5 px) | Enter: save/next | N: skip | Backspace: previous | Esc: quit"
                if task.item_type == "weapon":
                    controls = "Drag: move item/reticule | Arrows: nudge (Shift: 5 px) | Enter: save/next | N: skip | Backspace: previous | Esc: quit"
                    if task.animation != "weapon_idle":
                        controls = "Drag: move item/reticule | Arrows: nudge (Shift: 5 px) | Scroll: select sprite | Enter: save/next | N: skip | Backspace: previous | Esc: quit"
                screen.blit(font.render(progress, True, (255, 255, 255)), (16, 16))
                screen.blit(font.render(controls, True, (255, 255, 255)), (16, 44))
                pygame.display.flip()
                clock.tick(60)
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
