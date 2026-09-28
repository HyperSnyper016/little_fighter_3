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
- Armor-piece throwables travel twice as far as consumables when thrown
- Jan's healing-bird summon and homing orb, John's blast, projectile-reflecting barrier, homing disk, and healing orb, Axle's ranged shot and knockdown/launching attacks, Julian's height-guided skulls, piercing ball, and area attacks, Luis's advancing knockdown, bidirectional wind attack, and held sprinting attack, Liberated Luis's sword combos, wind knockdown, and forward dash, Mark's mana-powered charge through the first enemy until a second enemy is hurt, Monk's wind strike, and Freeze's ice-ball, ice-column, and moving tornado special attacks
- Rudolf's four-lane shuriken volley and air-launching sword strikes
- Data-driven animation timing and frame layout

## Controls

- Left / Right: move
- Up / Down: lane movement
- K: jump
- J: attack, pick up an item while idle and standing over it, or drink a consumable while holding one
- J + L: throw a held item; ground and airborne throws use different character animations
- P: spawn milk manually
- L: defend
- Left Shift: run
- Escape: quit

Jan summons three healing birds with Attack + Defend + Up and fires her homing orb with Attack + Jump + Up. Jack's special attacks use Attack + Defend + Left/Right to fire Jack Blast, Attack + Jump + Left/Right for a knockdown attack, and Attack + Defend + Up for a launching attack. John's special attacks use Attack + Defend + Left/Right for John Blast, Attack + Jump + Left/Right for his projectile-reflecting barrier, Attack + Defend + Up for his homing disk, and Attack + Jump + Up for his healing orb. Axle fires Axle Shot with Attack + Defend + Left/Right, uses Attack + Jump + Left/Right for a knockdown attack, and Attack + Defend + Up for a launching attack. Julian fires successive skulls while holding Attack + Defend + Left/Right (up to five shots), fires his piercing ball with Attack + Jump + Left/Right, and uses Attack + Defend + Up and Attack + Jump + Up for his two area attacks. Luis uses Attack + Defend + Left/Right for an advancing knockdown attack, Attack + Jump + Left/Right for the wind attack, Attack + Defend + Up for a forward dash (hold to extend the attack), and Attack + Jump + Up for his uppercut, which transforms him into Liberated Luis when the move completes without changing his HP. Liberated Luis uses Attack + Defend + Left/Right for his shear attack, Attack + Jump + Left/Right for a wind knockdown, and Attack + Defend + Up for a forward dash. Mark charges with Attack + Defend + Left/Right; holding the chord continues the charge while he has mana, carries through the first enemy, and stops when a second enemy is hurt. Both targets are knocked down when hit. Monk uses Attack + Defend + Left/Right for a wind strike that damages and knocks down an enemy in front of him on the same lane. Freeze's special attacks use Attack + Defend + Left/Right for the ice ball, Attack + Jump + Left/Right for the ice columns, and Attack + Defend + Up for the ice tornado.
