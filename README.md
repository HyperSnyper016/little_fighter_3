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
- `python tools/preview_item_anchor.py` calibrates both milk and heavy-carry anchors; use `--item heavy-carry` to calibrate only the heavy-carry idle, get-up, walking, sprinting, and throw poses.
- Milk break effects use `broken/dust`, `broken/large`, and `broken/small` frame folders.
- Held item IDs are category-relative paths such as `consumables/milk`. Use `BattleScene.start_item_overlay` to play other item actions over a fighter.
- The included prototype uses the provided `sprite example/bandit_0.bmp` as the initial source asset path reference.

## Current prototype

- Title screen prompt
- Character selection with a roster of playable fighters, including Jan, Jack, John, Axle, Julian, Knight, Luis, Liberated Luis, Mark, Monk, Rudolf, and Freeze
- 2.5D arena movement
- Idle, walk, run, jump, attack, defend states
- Spawned items stay on the ground until picked up; after pickup, they can be thrown and land twice before breaking
- A random consumable or throwable spawns every 18 seconds; milk restores 10 HP when consumed, armor-piece throwables cannot be consumed, and thrown items damage enemies before dropping where they hit
- Heavy boxes use their spawn, carry, throw, and landing animations; fighters lift them with the get-up animation, use the first heavy-carry walking frame while idle, and switch between carry-walking and carry-sprinting sprites when moving. Landed boxes block movement and break into jumping fragments when hit; box landings alternate between two impact sounds
- Armor-piece throwables travel twice as far as consumables when thrown
- Jan's healing-bird summon and homing orb, John's blast, projectile-reflecting barrier, homing disk, and healing orb, Axle's ranged shot and knockdown/launching attacks, Julian's height-guided skulls, piercing ball, and area attacks, Luis's advancing knockdown, bidirectional wind attack, and held sprinting attack, Liberated Luis's sword combos, wind knockdown, and forward dash, Mark's mana-powered charge through the first enemy until a second enemy is hurt, Monk's wind strike, and Freeze's ice-ball, ice-column, and moving tornado special attacks
- Rudolf's four-lane shuriken volley and air-launching sword strikes
- The City battle stage, with a parallax sunset-city backdrop, ground-aligned scenery, and a tiled fighting floor
- Stage Mode campaign with ten increasingly varied enemy encounters
- Data-driven animation timing and frame layout

## Controls

### Menus and character selection

- Main menu: use Up / Down or click an option; press J, Enter, or Space to select it. Click Update History to open the release notes, then scroll with the mouse wheel or Up / Down / Page Up / Page Down; press Escape or click outside the panel to close it.
- Settings: select Sound or Volume; use Left / Right to adjust volume, or click the volume bar. Press Escape to return to the main menu. F9 toggles mute during play.
- Character selection: use the arrow keys or click a portrait; press J, Enter, or numpad Enter, or click Confirm, to start with the selected fighter.
- Stage Mode runs through ten encounters. After winning or losing the campaign, press J to return to the main menu.

### Battle

- Left / Right: move; double-tap a direction or hold Shift while moving to run.
- Up / Down: move between lanes.
- K: jump.
- J: basic attack; pick up an item while idle and standing near it, or drink a held consumable.
- L: defend while held.
- J + L: throw a held item. Ground and airborne throws use different animations.
- Carrying an item disables basic and special attacks.
- P / O: spawn milk / a heavy box for testing.
- Escape: pause or resume. While paused, press M to return to the main menu.

### Special attacks

Special attacks cost mana. Press J while holding the listed keys; available moves vary by fighter:

- J + L + Left / Right: moving special 1.
- J + K + Left / Right: moving special 2.
- J + L + Up: vertical special 1.
- J + K + Up: vertical special 2.

Examples: Jan summons healing birds with J + L + Up and fires her homing orb with J + K + Up. Jack uses J + L + Left / Right for Jack Blast, J + K + Left / Right for a knockdown attack, and J + L + Up for a launching attack. John uses those same directional chords for John Blast, a projectile-reflecting barrier, a homing disk (J + L + Up), and a healing orb (J + K + Up). Axle fires Axle Shot with J + L + Left / Right, uses J + K + Left / Right for a knockdown attack, and J + L + Up for a launching attack. Julian fires successive skulls by holding J + L + Left / Right, fires a piercing ball with J + K + Left / Right, and uses J + L + Up or J + K + Up for his area attacks.

Luis uses J + L + Left / Right for an advancing knockdown attack, J + K + Left / Right for a wind attack, J + L + Up for a forward dash, and J + K + Up for an uppercut that transforms him into Liberated Luis without changing his HP. Holding the dash chord extends the move. Liberated Luis uses J + L + Left / Right for a shear attack, J + K + Left / Right for a wind knockdown, and J + L + Up for a forward dash. Mark charges with J + L + Left / Right; holding the chord continues the charge while he has mana. Monk uses that moving-special chord for a wind strike. Freeze uses J + L + Left / Right for an ice ball, J + K + Left / Right for ice columns, and J + L + Up for an ice tornado.

### Testing controls

These extra keys are intended for testing: V knocks the player down, B lifts, G breaks the player's block, N starts the player's death animation, M revives the player, Q consumes a held item, F / I trigger fire / ice knockdown, H applies a hurt reaction, and F10 defeats the current enemy.
