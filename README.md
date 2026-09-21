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
- The included prototype uses the provided `sprite example/bandit_0.bmp` as the initial source asset path reference.

## Current prototype

- Title screen prompt
- One playable fighter
- 2.5D arena movement
- Idle, walk, run, jump, attack, defend states
- Data-driven animation timing and frame layout

## Controls

- Left / Right: move
- Up / Down: lane movement
- K: jump
- J: attack
- L: defend
- Left Shift: run
- Escape: quit
