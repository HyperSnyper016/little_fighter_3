# Item Anchor Preview Tool

`preview_item_anchor.py` opens a window with a character and held item preview for milk and heavy-carry calibration. During weapon calibration, the currently selected swing sprite is overlaid on the character with the target reticule at its pivot; drag the preview to place it, then press **Enter** to save that frame's normalized anchor and selected sprite.

By default, the tool calibrates milk, heavy-carry walk/sprint/throw poses, and the canonical `ice_sword` weapon hand-anchor template. Weapon anchors are stored by weapon, character, and pose in `assets/sprites/item_sprites/hand_anchors.json`; separately, each character-pose frame records one canonical swing sprite reference shared across weapons. During a weapon attack, the game uses that reference filename stem to select the matching swing image from the held weapon's `holding/swing` folder. Standardize swing filenames across weapons to share the same per-character mapping; if a mapped frame is missing, the weapon's holding sprite remains visible. Other weapons can reuse the Ice Sword hand-anchor template. Milk and heavy-carry anchors retain their existing character-based format. Saved frames are skipped on later runs, so an interrupted calibration resumes at the first missing anchor.

## Requirements

Run commands from the repository root. The project Python environment must have Pygame installed.

```powershell
py -3.12 tools\preview_item_anchor.py
```

The default character scale is `2`, matching the game. Dummy is not included because it has no authored sprite frames.

## Ways to select what to calibrate

Calibrate all item groups and supported animation folders:

```powershell
py -3.12 tools\preview_item_anchor.py
```

Calibrate only one character:

```powershell
py -3.12 tools\preview_item_anchor.py --character deep
```

Calibrate every pose for a different weapon as a weapon-specific override:

```powershell
py -3.12 tools\preview_item_anchor.py --item weapon --weapon weapon_name
```

Replace `weapon_name` with a folder name under `assets\sprites\item_sprites\weapons`. Repeat `--weapon` to calibrate multiple overrides in the same run. If omitted, weapon anchors are calibrated once against the canonical Ice Sword reference.

Calibrate a weapon pose for one character:

```powershell
py -3.12 tools\preview_item_anchor.py --item weapon --weapon weapon_name --character deep --animation weapon_basic_attack
```

Calibrate one or more animation folders for all characters, or combine this with `--character`:

```powershell
py -3.12 tools\preview_item_anchor.py --animation drink
py -3.12 tools\preview_item_anchor.py --character deep --animation drink
py -3.12 tools\preview_item_anchor.py --animation ground_throw --animation jump_throw
py -3.12 tools\preview_item_anchor.py --animation idle --animation walk
py -3.12 tools\preview_item_anchor.py --animation get_up
```

Supported `--animation` values depend on `--item`. Milk supports `idle`, `walk`, `run`, `drink`, `spawn` (or `ground_throw`), `jump_throw`, and `get_up`; heavy-carry supports only `heavy_carry_walk`, `heavy_carry_sprint`, and `heavy_carry_throw`, sourced from each character's `hold_item\heavy_carry\walk`, `sprint`, and `throw` folders. Weapons support `weapon_idle`, `weapon_jump_normal`, `weapon_jump_second`, `weapon_ground_throw`, `weapon_jump_throw`, the four weapon-carry attack poses, and `weapon_get_up`. Normal/second jump sprites come from `movement\jump_actions\basic_jump` and `second_jump`; weapon throw poses come from `hold_item\throw_item\ground_throw` and `jump_throw` and map against the weapon's own `throw` sprites; get-up comes from `fall\get_up` and has its own weapon anchor key, distinct from either throw pose. The selected weapon sprite is previewed at the reticule; use the mouse wheel to change it, then press **Enter** to save its selection and the anchor for that character frame.

Existing weapon anchors are initially paired to canonical swing frames proportionally. Run with `--item weapon --recalibrate` to adjust those pairings; the reticule opens at its saved anchor and the mouse-wheel selection is saved when you press **Enter**. Each saved selection applies to that specific character pose frame, is preserved on later tool runs, and selects matching weapon swing images by filename stem rather than frame order.

Target one or more exact sprite folders instead of selecting by character or animation:

```powershell
py -3.12 tools\preview_item_anchor.py --folder "deep\hold_item\drink"
py -3.12 tools\preview_item_anchor.py --folder "deep\idle" --folder "freeze\movement\walking"
```

Folder paths are relative to `assets\sprites\characters` (absolute paths inside that directory are also accepted). Recognized folders automatically map to the game's animation names. For a custom folder, supply the animation name the game uses:

```powershell
py -3.12 tools\preview_item_anchor.py --folder "deep\actions\basic_attack" --animation-key attack_punch
```

For a custom weapon folder, select the weapon group and weapon as well:

```powershell
py -3.12 tools\preview_item_anchor.py --item weapon --weapon weapon_name --folder "deep\hold_item\weapon_carry\basic_attack"
```

`--folder` cannot be combined with `--character` or `--animation`. `--animation-key` requires exactly one `--folder`.

## Parameters

| Parameter | Description |
| --- | --- |
| `--character NAME` | Calibrate only one character. Omit to include all authored characters. |
| `--item GROUP` | Select `milk`, `heavy-carry`, or `weapon`. Omit to calibrate all groups. |
| `--weapon NAME` | Select a weapon for `--item weapon`. Repeat to select several. |
| `--animation NAME` | Select one of the animation keys supported by the selected item group. Repeat to select several. |
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
| Left mouse button / drag | Move the item preview and target reticule |
| Arrow keys | Nudge the overlay or reticule by one pixel |
| Shift + arrow key | Nudge the overlay or reticule by five pixels |
| Mouse wheel up / down | Select the previous/next canonical swing reference during weapon attack calibration |
| Enter | Save the current anchor and advance |
| `N` | Skip the current frame without saving it |
| Backspace | Go to the previous frame |
| Escape or close window | Exit; previously saved anchors remain saved |

Drink-frame calibration pairs each character's `hold_item\drink` frame with the milk sprite at the same natural-sort index in `assets\sprites\item_sprites\consumables\milk\drink` (`1_1` with the first character frame, `1_2` with the second, and `1_3` with the third). The frame counts must match. During gameplay, the milk drink overlay follows the same frame index as the character's drink animation and loops while the character is drinking. Until a drink frame is calibrated, the game retains its existing mouth-level fallback placement. Other uncalibrated frames use the available idle anchor or the existing fallback position.

Weapon sprites are discovered under `assets\sprites\item_sprites\weapons\<weapon>\holding\`; each selectable weapon needs image frames in both `idle` and `swing`, and throw calibration uses its `throw` folder. Held weapon frames retain their source canvas so its center remains the sprite pivot. `hand_anchors.json` uses version 3 for weapon anchors and their per-character-frame `weapon_reference_sprites` mapping, while continuing to load version-1 and version-2 anchor data.
