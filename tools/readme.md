# Item Anchor Preview Tool

`preview_item_anchor.py` opens a window with a character sprite and the milk holding sprite overlaid. Drag the milk to the desired attachment point, then press **Enter** to save that frame's normalized anchor and move to the next frame.

By default, the tool visits every authored character's idle, walking, running, drinking, and get-up frames. It saves progress to `assets/sprites/item_sprites/hand_anchors.json`; the game reads that file when it starts. Saved frames are skipped on later runs, so an interrupted calibration resumes at the first missing anchor.

## Requirements

Run commands from the repository root. The project Python environment must have Pygame installed.

```powershell
py -3.12 tools\preview_item_anchor.py
```

The default character scale is `2`, matching the game. Dummy is not included because it has no authored sprite frames.

## Ways to select what to calibrate

Calibrate all characters and supported animation folders:

```powershell
py -3.12 tools\preview_item_anchor.py
```

Calibrate only one character:

```powershell
py -3.12 tools\preview_item_anchor.py --character deep
```

Calibrate one or more animation folders for all characters, or combine this with `--character`:

```powershell
py -3.12 tools\preview_item_anchor.py --animation drink
py -3.12 tools\preview_item_anchor.py --character deep --animation drink
py -3.12 tools\preview_item_anchor.py --animation idle --animation walk
py -3.12 tools\preview_item_anchor.py --animation get_up
```

Supported `--animation` values are `idle`, `walk`, `run`, `drink`, `milk_drink`, and `get_up`. `drink` is a short alias for the character's `milk_drink` animation, which uses the `hold_item\drink` sprite folder. `get_up` uses each character's `fall\get_up` sprite folder.

Target one or more exact sprite folders instead of selecting by character or animation:

```powershell
py -3.12 tools\preview_item_anchor.py --folder "deep\hold_item\drink"
py -3.12 tools\preview_item_anchor.py --folder "deep\idle" --folder "freeze\movement\walking"
```

Folder paths are relative to `assets\sprites\characters` (absolute paths inside that directory are also accepted). Recognized folders automatically map to the game's animation names. For a custom folder, supply the animation name the game uses:

```powershell
py -3.12 tools\preview_item_anchor.py --folder "deep\actions\basic_attack" --animation-key attack_punch
```

`--folder` cannot be combined with `--character` or `--animation`. `--animation-key` requires exactly one `--folder`.

## Parameters

| Parameter | Description |
| --- | --- |
| `--character NAME` | Calibrate only one character. Omit to include all authored characters. |
| `--animation NAME` | Select an animation folder: `idle`, `walk`, `run`, `drink`, `milk_drink`, or `get_up`. Repeat to select several. |
| `--folder PATH` | Select a specific character sprite folder relative to `assets\sprites\characters`. Repeat to select several. |
| `--animation-key NAME` | Save anchors under this game animation key for one custom `--folder`. |
| `--facing right\|left` | Preview the character facing direction. Stored anchors are normalized to the unflipped frame; the game mirrors them when needed. Default: `right`. |
| `--scale NUMBER` | Scale applied to character frames. Default: `2`. |
| `--anchors-path PATH` | JSON file to read/write. Default: `assets\sprites\item_sprites\hand_anchors.json`. |
| `--recalibrate` | Start from the first selected frame and revisit saved anchors instead of skipping them. |
| `-h`, `--help` | Show command help. |

## Preview controls

| Input | Action |
| --- | --- |
| Left mouse button / drag | Move the milk overlay |
| Arrow keys | Nudge the overlay by one pixel |
| Shift + arrow key | Nudge the overlay by five pixels |
| Enter | Save the current anchor and advance |
| `N` | Skip the current frame without saving it |
| Backspace | Go to the previous frame |
| Escape or close window | Exit; previously saved anchors remain saved |

Drink-frame calibration pairs each character's `hold_item\drink` frame with the milk sprite at the same natural-sort index in `assets\sprites\item_sprites\consumables\milk\milk_drink` (`1_1` with the first character frame, `1_2` with the second, and `1_3` with the third). The frame counts must match. During gameplay, the milk drink overlay follows the same frame index as the character's drink animation and loops while the character is drinking. Until a drink frame is calibrated, the game retains its existing mouth-level fallback placement. Other uncalibrated frames use the available idle anchor or the existing fallback position.
