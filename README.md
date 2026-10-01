# little_fighter_3

PyCharm-friendly Python prototype for a Little Fighter 2-inspired side-scrolling beat 'em up.

## Stack

- Python 3.12+
- Pygame CE

## Setup

1. Create a PyCharm project interpreter.
2. Install dependencies:
   `pip install pygame-ce`
3. Run:
   `python main.py`

## Sprite workflow

- Put source sprite sheets under `assets/sprites/characters/`.
- Character definitions live in `game/data/characters.py`.
- Item sprites are discovered under `assets/sprites/item_sprites/<category>/<item>/<action>/`. Put held idle frames in `holding/idle`; action frames go directly in their action folder, with variants allowed in nested subfolders. Directories beginning with `_` are ignored, so `_blank_consumable` and `_blank_throwable` can hold reusable templates without being treated as items.
- `python tools/preview_item_anchor.py` calibrates milk, heavy-carry walk/sprint/throw, and the canonical Ice Sword weapon hand-anchor template. Weapon calibration previews the selected sprite over the character; the mouse wheel selects the exact reference for each character pose frame, including normal/second jumps, ground/jump throws, and a separate get-up pose. At runtime, held weapons use matching filename stems from their `holding/swing` or `throw` folders, so standardized names let weapons share the frame mapping while keeping anchors weapon-specific.
- Milk break effects use `broken/dust`, `broken/large`, and `broken/small` frame folders.
- Held item IDs are category-relative paths such as `consumables/milk`. Use `BattleScene.start_item_overlay` to play other item actions over a fighter.
- The included prototype uses the provided `sprite example/bandit_0.bmp` as the initial source asset path reference.

## Current prototype

- Title screen prompt
- Play mode lets you choose a playable fighter and one or more opponents from the character roster
- Test Mode lets you choose a fighter and practice in the arena without enemies
- 2.5D arena movement
- Idle, walk, run, jump, attack, defend states
- Spawned items stay on the ground until picked up; after pickup, they can be thrown and land twice before breaking
- A random consumable or throwable spawns every 18 seconds; milk restores 10 HP when consumed, armor-piece throwables cannot be consumed, and thrown items damage enemies before dropping where they hit
- Heavy boxes use their spawn, carry, throw, and landing animations; fighters lift them with the get-up animation, use the first heavy-carry walking frame while idle, and switch between carry-walking and carry-sprinting sprites when moving. Landed boxes block movement and break into jumping fragments when hit; box landings alternate between two impact sounds
- Armor-piece throwables travel twice as far as consumables when thrown
- Baseballs bounce once on landing and play `baseball_break.wav` when they break
- Jan's healing-bird summon and homing orb, John's blast, projectile-reflecting barrier, homing disk, and healing orb, Axle's ranged shot and knockdown/launching attacks, Julian's height-guided skulls, piercing ball, and area attacks, Luis's advancing knockdown, bidirectional wind attack, and held sprinting attack, Liberated Luis's sword combos, wind knockdown, and forward dash, Mark's mana-powered charge through the first enemy until a second enemy is hurt, Monk's wind strike, and Freeze's ice-ball, ice-column, and moving tornado special attacks
- Rudolf's four-lane shuriken volley and air-launching sword strikes
- The City battle stage, with a parallax sunset-city backdrop, ground-aligned scenery, and a tiled fighting floor
- Stage Mode campaign with ten increasingly varied enemy encounters
- Data-driven animation timing and frame layout

## Controls

### Menus and character selection

- Main menu: use Up / Down or click an option; press J, Enter, or Space to select it. Choose Test Mode to practice without enemies. Click Update History to open the release notes, then scroll with the mouse wheel or Up / Down / Page Up / Page Down; press Escape or click outside the panel to close it.
- Settings: select Sound or Volume; use Left / Right to adjust volume, or click the volume bar. Press Escape to return to the main menu. F9 toggles mute during play.
- Character selection: choose your fighter with the arrow keys or by clicking a portrait, then press J, Enter, or numpad Enter, click Confirm, or double-click the portrait.
- Opponent selection: choose one or more enemies with the arrow keys and Space, or click portraits to toggle them; press J or Enter, or click Start Battle, to begin.
- Stage Mode runs through ten encounters. After winning or losing the campaign, press J to return to the main menu.

### Battle

- Left / Right: move; double-tap a direction or hold Shift while moving to run.
- Up / Down: move between lanes.
- K: jump.
- J: basic attack; pick up an item while idle and standing near it, or drink a held consumable.
- L: defend while held.
- J + L: throw a held item. Ground and airborne throws use different animations.
- Carrying an item disables basic and special attacks.
- P: spawn a random available item. O: spawn a heavy box for testing.
- Escape: pause or resume. While paused, press M to return to the main menu.

### Special attacks

Special attacks cost mana. Press J while holding the listed keys; available moves vary by fighter:

- Chord inputs are buffered for 0.18 seconds, so you can press the keys in any order.
- J + L + Left / Right: moving special 1.
- J + K + Left / Right: moving special 2.
- J + L + Up: vertical special 1.
- J + K + Up: vertical special 2.

Examples: Jan summons healing birds with J + L + Up and fires her homing orb with J + K + Up. Jack uses J + L + Left / Right for Jack Blast, J + K + Left / Right for a knockdown attack, and J + L + Up for a launching attack. John uses those same directional chords for John Blast, a projectile-reflecting barrier, a homing disk (J + L + Up), and a healing orb (J + K + Up). Axle fires Axle Shot with J + L + Left / Right, uses J + K + Left / Right for a knockdown attack, and J + L + Up for a launching attack. Julian fires successive skulls by holding J + L + Left / Right, fires a piercing ball with J + K + Left / Right, and uses J + L + Up or J + K + Up for his area attacks.

Luis uses J + L + Left / Right for an advancing knockdown attack, J + K + Left / Right for a wind attack, J + L + Up for a forward dash, and J + K + Up for an uppercut that transforms him into Liberated Luis without changing his HP. Holding the dash chord extends the move. Liberated Luis uses J + L + Left / Right for a shear attack, J + K + Left / Right for a wind knockdown, and J + L + Up for a forward dash. Mark charges with J + L + Left / Right; holding the chord continues the charge while he has mana. Monk uses that moving-special chord for a wind strike. Freeze uses J + L + Left / Right for an ice ball, J + K + Left / Right for ice columns, and J + L + Up for an ice tornado.

### Testing controls

These extra keys are intended for testing: V knocks the player down, B lifts, G breaks the player's block, N starts the player's death animation, M revives the player, Q consumes a held item, F / I trigger fire / ice knockdown, H applies a hurt reaction, and F10 defeats the current enemy when one is present.
