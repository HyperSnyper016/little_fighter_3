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
- Item sprites are discovered under `assets/sprites/item_sprites/<category>/<item>/<action>/`. Put held idle frames in `holding/idle`; action frames go directly in their action folder, with variants allowed in nested subfolders. Directories beginning with `_` are ignored, so `_blank_consumable` can hold a reusable folder template without being treated as an item.
- Milk break effects use `broken/dust`, `broken/large`, and `broken/small` frame folders.
- Held item IDs are category-relative paths such as `consumables/milk`. Use `BattleScene.start_item_overlay` to play other item actions over a fighter.
- The included prototype uses the provided `sprite example/bandit_0.bmp` as the initial source asset path reference.

## Current prototype

- Title screen prompt
- Character selection with a roster of playable fighters, including Jan, Jack, and Freeze
- 2.5D arena movement
- Idle, walk, run, jump, attack, defend states
- Spawned consumables stay on the ground until picked up; after pickup, they can be thrown and land twice before breaking
- A random consumable spawns every 12 seconds; milk restores 10 HP when consumed, and thrown items damage enemies before dropping where they hit
- Jan's healing-bird summon and homing orb, and Freeze's ice-ball, ice-column, and moving tornado special attacks
- Data-driven animation timing and frame layout

## Controls

- Left / Right: move
- Up / Down: lane movement
- K: jump
- J: attack, pick up a consumable while idle and standing over it, or drink while holding one
- J + L: throw a held consumable; ground and airborne throws use different character animations
- P: spawn milk manually
- L: defend
- Left Shift: run
- Escape: quit

Jan summons three healing birds with Attack + Defend + Up and fires her homing orb with Attack + Jump + Up. Jack's special attacks use Attack + Defend + Left/Right to fire Jack Blast, Attack + Jump + Left/Right for a knockdown attack, and Attack + Defend + Up for a launching attack. Freeze's special attacks use Attack + Defend + Left/Right for the ice ball, Attack + Jump + Left/Right for the ice columns, and Attack + Defend + Up for the ice tornado.
