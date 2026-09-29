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
    "heavy_carry_idle": ("hold_item", "heavy_carry", "walking"),
    "heavy_carry_get_up": ("fall", "get_up"),
    "heavy_carry_walk": ("hold_item", "heavy_carry", "walking"),
    "heavy_carry_sprint": ("hold_item", "heavy_carry", "sprinting"),
    "heavy_carry_throw": ("hold_item", "heavy_carry", "throw"),
    "heavy_carry_jump_throw": ("hold_item", "throw_item", "jump_throw"),
}
MILK_ANIMATIONS = ("idle", "walk", "run", "drink", "spawn", "jump_throw", "get_up")
HEAVY_CARRY_ANIMATIONS = (
    "heavy_carry_idle",
    "heavy_carry_get_up",
    "heavy_carry_walk",
    "heavy_carry_sprint",
    "heavy_carry_throw",
    "heavy_carry_jump_throw",
)
ITEM_ANIMATIONS = {
    "milk": MILK_ANIMATIONS,
    "heavy-carry": HEAVY_CARRY_ANIMATIONS,
}
ANIMATION_ALIASES = {"ground_throw": "spawn"}
FOLDER_ANIMATION_KEYS: dict[tuple[str, ...], str] = {}
for animation, folder in ANIMATION_FOLDERS.items():
    FOLDER_ANIMATION_KEYS.setdefault(folder, animation)
FOLDER_ANIMATION_KEYS[("hold_item", "heavy_carry", "walking")] = "heavy_carry_walk"
FOLDER_ANIMATION_KEYS[("hold_item", "heavy_carry", "walk")] = "heavy_carry_walk"
FOLDER_ANIMATION_KEYS[("hold_item", "heavy_carry", "sprinting")] = "heavy_carry_sprint"
FOLDER_ANIMATION_KEYS[("hold_item", "heavy_carry", "sprint")] = "heavy_carry_sprint"
HEAVY_CARRY_FOLDER_ANIMATION_KEYS = {
    ("hold_item", "heavy_carry", "walking"): "heavy_carry_walk",
    ("hold_item", "heavy_carry", "walk"): "heavy_carry_walk",
    ("hold_item", "heavy_carry", "sprinting"): "heavy_carry_sprint",
    ("hold_item", "heavy_carry", "sprint"): "heavy_carry_sprint",
    ("fall", "get_up"): "heavy_carry_get_up",
    ("hold_item", "heavy_carry", "throw"): "heavy_carry_throw",
    ("hold_item", "throw_item", "jump_throw"): "heavy_carry_jump_throw",
}
OPTIONAL_ANIMATIONS = {
    "spawn",
    "jump_throw",
    "heavy_carry_idle",
    "heavy_carry_walk",
    "heavy_carry_sprint",
    "heavy_carry_throw",
    "heavy_carry_jump_throw",
}
HEAVY_CARRY_FOLDER_CANDIDATES = {
    "heavy_carry_idle": ("walking", "walk"),
    "heavy_carry_walk": ("walking", "walk"),
    "heavy_carry_sprint": ("sprinting", "sprint"),
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


def _natural_sort_key(path: Path) -> list[str | int]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def _image_paths(folder: Path) -> list[Path]:
    return sorted(
        (path for path in folder.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS),
        key=_natural_sort_key,
    )


def _character_names() -> list[str]:
    return sorted(path.name for path in CHARACTER_ROOT.iterdir() if path.is_dir() and not path.name.startswith("_"))


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
) -> list[SpriteTask]:
    if not folder.is_dir():
        raise FileNotFoundError(f"{character} {animation} sprite folder not found: {folder}")
    paths = _image_paths(folder)
    if not paths:
        raise FileNotFoundError(f"No {character} {animation} frames found in {folder}")
    return [
        SpriteTask(character, animation, frame_index, len(paths), path, item_type)
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
    if animation in HEAVY_CARRY_FOLDER_CANDIDATES:
        carry_root = folder / "hold_item" / "heavy_carry"
        for folder_name in HEAVY_CARRY_FOLDER_CANDIDATES[animation]:
            candidate = carry_root / folder_name
            if candidate.is_dir() and _image_paths(candidate):
                return candidate
    for part in ANIMATION_FOLDERS[animation]:
        folder /= part
    return folder


def _build_tasks(
    character_names: list[str],
    animations: list[str] | None = None,
    folders: list[str] | None = None,
    animation_key: str | None = None,
    item_type: str = "milk",
) -> list[SpriteTask]:
    tasks: list[SpriteTask] = []
    if folders:
        for selector in folders:
            character, animation, folder = _specific_folder_task_group(selector, animation_key)
            if item_type == "heavy-carry" and animation_key is None:
                relative_parts = folder.relative_to(CHARACTER_ROOT).parts[1:]
                animation = HEAVY_CARRY_FOLDER_ANIMATION_KEYS.get(relative_parts, animation)
            tasks.extend(_tasks_for_folder(character, animation, folder, item_type))
        return tasks

    selected_animations = [
        ANIMATION_ALIASES.get(animation, animation)
        for animation in (animations or ITEM_ANIMATIONS[item_type])
    ]
    for character in character_names:
        for animation in selected_animations:
            folder = _animation_folder(character, animation)
            if animation in OPTIONAL_ANIMATIONS and not _image_paths(folder):
                continue
            animation_tasks = _tasks_for_folder(character, animation, folder, item_type)
            if animation == "heavy_carry_idle":
                tasks.append(replace(animation_tasks[0], frame_count=1))
            else:
                tasks.extend(animation_tasks)
    return tasks


def _empty_anchor_data() -> dict:
    return {"version": 1, "characters": {}}


def _load_anchor_data(path: Path) -> dict:
    if not path.exists():
        return _empty_anchor_data()

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError(f"Unsupported anchor file format: {path}")
    characters = data.get("characters")
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
    return data


def _save_anchor_data(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def _existing_anchor(data: dict, task: SpriteTask) -> tuple[float, float] | None:
    point = (
        data["characters"]
        .get(task.character, {})
        .get(task.animation, [])
    )
    if task.frame_index >= len(point) or point[task.frame_index] is None:
        return None
    return float(point[task.frame_index][0]), float(point[task.frame_index][1])


def _ensure_anchor_slot(data: dict, task: SpriteTask) -> list:
    characters = data["characters"]
    character = characters.setdefault(task.character, {})
    points = character.setdefault(task.animation, [None] * task.frame_count)
    if len(points) < task.frame_count:
        points.extend([None] * (task.frame_count - len(points)))
    elif len(points) > task.frame_count:
        del points[task.frame_count:]
    return points


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
    item: pygame.Surface,
    character_pos: tuple[int, int],
    item_center: tuple[int, int],
    facing: str,
) -> None:
    surface.fill((62, 66, 72))
    character_frame = character if facing == "right" else pygame.transform.flip(character, True, False)
    item_frame = item if facing == "right" else pygame.transform.flip(item, True, False)
    surface.blit(character_frame, character_pos)
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
) -> tuple[float, float]:
    width, height = character_size
    local_x = (item_center[0] - character_pos[0]) / width
    x = local_x if facing == "right" else 1 - local_x
    y = (item_center[1] - character_pos[1]) / height
    point = [round(x, 6), round(y, 6)]
    points = _ensure_anchor_slot(data, task)
    points[task.frame_index] = point
    return point[0], point[1]


def main() -> int:
    names = _character_names()
    parser = argparse.ArgumentParser(
        description=(
            "Calibrate per-frame item anchors for milk or heavy-carry items. Only characters with authored sprite frames are included."
        )
    )
    parser.add_argument("--character", choices=names, help="Calibrate only this character (default: all characters)")
    parser.add_argument(
        "--item",
        choices=tuple(ITEM_ANIMATIONS),
        help="Item to preview; by default, calibrates milk and heavy-carry items",
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
        parser.error("--folder requires --item milk or --item heavy-carry")
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
                )
            )
        if not tasks:
            raise FileNotFoundError("No character sprite frames found for the selected animation folders")
        anchor_data = _load_anchor_data(args.anchors_path)
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
        current_item_frame: pygame.Surface

        def load_task() -> None:
            nonlocal screen, character, character_pos, item_center, current_item_frame
            task = tasks[task_index]
            character = _load_frame(task.path, scale=args.scale)
            current_item_frame = (
                milk_drink_frames[task.frame_index]
                if task.item_type == "milk" and task.animation == "drink"
                else holding_frames[task.item_type]
            )
            width, height = character.get_size()
            canvas_size = (max(900, width + current_item_frame.get_width() * 2 + 180), max(700, height + 180))
            character_pos = ((canvas_size[0] - width) // 2, canvas_size[1] - height - 90)
            item_center = _current_item_center(anchor_data, task, character.get_size(), character_pos, args.facing)
            screen = pygame.display.set_mode(canvas_size)
            pygame.display.set_caption(
                f"Item anchor: {task.character} / {task.animation} "
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
                        )
                        _save_anchor_data(args.anchors_path, anchor_data)
                        print(f"Saved {task.character} {task.animation} frame {task.frame_index + 1}: ({point[0]:.3f}, {point[1]:.3f})")
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
                controls = "Drag: place item | Arrows: nudge (Shift: 5 px) | Enter: save/next | N: skip | Backspace: previous | Esc: quit"
                screen.blit(font.render(progress, True, (255, 255, 255)), (16, 16))
                screen.blit(font.render(controls, True, (255, 255, 255)), (16, 44))
                pygame.display.flip()
                clock.tick(60)
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
