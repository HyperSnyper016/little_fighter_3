# Update History

Append each new release at the bottom with its version and player-facing changes.

## v0.1.0 - Build the initial basic playable prototype with menu flow
### Added
- add main menu with Test Game entry and title/credit text
- add character select scene with discovered playable characters and
  profile portraits from assets\sprites
- add optional idle enemy toggle for Test Game
- wire bandit character data to file-based sprite assets
- add idle, walk, run, jump, move attack, punch, kick, block, block
  dodge, block break, grapple, grappled, grappled hit, knocked, get up,
  lift heavy, and die animations
- alternate basic attacks between punch and kick
- add move attack, knockdown, death, revive, block, dodge, grapple, and
  get-up state logic
- add revive flashing, directional pushback, grapple cancel behavior,
  and jump state locking while airborne
- add basic AI for idle, walk, run, jump, move attack, knockdown, death,
  revive, block, dodge, grapple, and get-up states
- add revive flashing, directional pushback, grapple cancel behavior,
  and jump state locking while airborne
- switch battle controls to latched per-frame action input so jump and
  other actions are handled reliably
- expand arena lane movement and ground rendering
- increase window size and update in-game control hints

## v0.2.0 - Core Systems & Combat Foundation
### Added
- Reworked the project into a modular game structure with dedicated systems for fighters, scenes, assets, audio, stages, and character data.
- Added the first playable battle scene with a forest arena, layered environment graphics, stage boundaries, and camera movement.
- Added the Bandit fighter with sprite-based animations and a complete initial combat state system.
- Added movement, walking, running, jumping, double jumping, sprint attacks, blocking, dodging, grappling, knockdowns, recovery, and death states.
- Added directional combat and collision handling with lane-based positioning.
- Added health, damage, knockback, blocking, block breaks, and combat hit detection.
- Added player input handling with support for held and newly pressed actions.
- Added initial enemy AI capable of movement, attacking, blocking, jumping, and reacting to the player's state.
- Added character selection and character data definitions.
- Added centralized asset and audio management.
- Added combat sound effects for attacks, hits, blocks, movement, jumping, knockdowns, and other gameplay events.
- Added initial item and consumable support, including drinking animations.
- Added animation state tracking and sprite frame timing.
- Added configurable game constants and stage settings.

## v0.3.0 - Asset reorganization and combat improvements
### Added
- Asset reorg. All playable character sprites were moved under assets/sprites/characters/, and code was updated to point there. Character select now scans the new root
- New character Hunter. Hunter now has all sprites and animations, is a ranged/archer class character
- Main menu refresh. The main menu now renders a randomized tiled character-art background that shifts diagnally down right with a light overlay and cleaner title treatment
- Gameplay constraints. Ground position was raised, which shifts fighter/projectile placement to match new layout

## v0.4.0 - Sprite Refresh and standardization for future models
### Added
- Sprite refresh. Playable cahracter sprite folders were again reorganized in order to make for a more standardized naming setup for future additional move combinations
- Template now uses the new frames and a exciting new projectile called the "Blue Ball" is now added to the game
- New Template projectile behavior, and new special movesets were added. This means sp move repeatedly spawns blue ball projectiles while held. Projectiles from the blue balls will rapidly speed up during ball TTL
- Input and combat refresh. Controls were remapped to J K L, attack state handling was expanded, and animation finished-state tracking was added so non-looping actions can reply cleanly

## v0.4.1 - Added Deep and John Characters
### Added
- Added Deep as a playable character with his full combat and animation set.
- Defend can now be held continuously instead of requiring repeated input.
- Fixed drink animations so they loop correctly.
- Updated asset discovery to ignore _example_asset.

## v0.4.2 - Corrected attacks and move sets
### Added
- Hunter audio polish. Basic attack now plays draw/shoot arrow cues, and broken arrows play a ground-impact break sound
- Defense and jump flow update. Defend now holds while the key is held, and sprint jumping can skip directly to the second jump
- Special move refactor. sp_move_attack and sp_vert_attack were renamed to *_1, with mechanics updated for the new 1/2 attack+defend or attack+jump input combos
- Asset and animation cleanup. Sprite folders were reorganized to match the new move names and code paths were updated to load them

## v0.4.3 - Combat, NPC, and audio updates
### Added
- Add Deep-specific special handling: mana costs/gating, move-1 continuation, move-2 follow behavior, vertical lift, blade swipe tuning/sound, and speech bubble warnings for low mana.
- Add a bandit-based training NPC with lighter HP and passive AI tweaks; stop it from over-blocking or stunlocking the player.
- Add combat/audio updates: alternating whiff sounds, sword swing/cut cues, arrow hit cue, menu start/accept sounds, and win.wav on enemy defeat.
- Change jump landings to recover through get_up instead of snapping straight to idle.
- Refresh asset/sound mappings and rename the arrow sound files to the new shot/broken names.

## v0.4.4 - Combat tuning, dodge cycling, and debug controls
### Added
- Deep now features different dodge variants. They cycle
- Jumping overhaul: Normal jumping is at the same pace as walking, whereas second jump is at the same pace as sprinting
- Sprint attack gating tightened to only trigger when basic attack after sprinting
- Enemy melee reach widened for less frustrating melee interactions
- Added [F9] as mute toggle, [F10] as kill-all enemey debug hotkey
- Audio mute state is reflected in the battle HUD
- Removed old legacy sprites (will be replaced going forward)

## v0.4.5 - Combat & Character System Overhaul
### Added
- Overhauled combat, movement, and special-attack behavior.
- Improved NPC AI, projectile handling, and knockdown mechanics.
- Added new combat audio and effects across multiple attacks and abilities.
- Standardized the character asset structure to support the growing roster.
- Refined input handling and character interactions throughout combat.

## v0.4.6 - Corrected movesets for action attacks and special moves
### Added
- Tightened SP attacks: Input adjustments so movement + attack alone falls back to basic attacks
- Introduced new character, Bat
- Refined Bat's laser visuals to use a single point sprite only
- Reworked Bat's summon behavior to slide faster, homing loosely with wide vertical movement
- Make expired bat summons die after 4 seconds
- Keep Bat's vert attack 1
- Updated game version

## v0.4.7 - Tune Bat combat, NPC AI, and arena movement
### Added
- Simplified Bat's laser toa  single point sprite and align hit behavior to the lane/body
- Removed extra laser point assets to keep laser visuals to a one point only
- Reworked bat summon to skate more aggressively with wide horizontal swings during virtical movement
- Made bat summons faster, less linear, and less capable of hovering in place to nerf the move
- Improved NPC behavior with advance/pressure/flank/retreat/dodge/defend/jump choices
- Expanded virtual movement range ot the bottom of the screen

## v0.4.8 - Added new character, Dark Bat
### Added
- Added new character, Dark Bat, as a playable character
- Made Dark Bat's second jump into a timed flight with early cancel
- Added Dark bat's bat-like gameplay and special move behavior and sounds
- Updated main menu/background and character select presentation

## v0.5.0 - Added Davis and Denis as playable characters
### Added
- Added Davis and Denis as playable fighters with their special attack behavior, sounds, and projectile effects.
- Added staged orb behavior, including frame-based spawning, speed-up progression, burst effects, and the new Denis follow-orb
- Updated the main menu with a larger LF3_logo.jpg and cleaner transparent presentation
- Tuned attack timing and visual polish across the new character animations and effects

## v0.6.0 - Added Firen, Henry, and expanded projectile combat
### Added
- Add Firen and Henry as playable characters with full animation and combat data
- Wire Firen’s fire specials, staged hold attacks, fire trails, explosions, and fire knockdowns
- Add Henry’s arrow and wind special handling, including enchanted arrows and wind impact behavior
- Update Hunter/Henry arrow asset references after the folder move
- Add shared projectile/audio support for fireball, fire breath, enchanted arrow, Henry wind, and Davis uppercut sounds
- Tune arrow flight, arrow break behavior, and knock interactions

## v0.7.0 - Added Freeze and refined character special moves
### Added
- Added Freeze roster entry, assets, sounds, and ice special attacks
- Improved Henry's arrow design, and flute attacks, including synchronized animation and effects
- Fixed Davis and Template projectile handling and sped up Denis's second movement SP attack
- Updated combat audio, knockdown handling, README, and version

## v0.8.0 - Added consumables and item anchor calibrations
### Added
- Added milk spawning (by key), pickup, holding, and drinking with audio
- Generalize item overlays and add per-frame character anchors for future implementations of items, consumables, and weapons.
- Added calibration tooling for idle, movement, drink, and get-up poses (dev tool)
- Include milk and weapon-carry sprite assets

## v0.9.0 - Added consumable gameplay and sprite-anchoring testing from tools
### Added
- Discover consumables from standardized folders while ignoring templates
- Add ground and air throws, impact damage and drops, and milk healing
- Spawn a random configured consumable every 12 seconds
- Add item break effects and throw-anchor preview support

## v0.9.1 - Keep unfinished Jack assets out of fighter select
### Added
- Add Jack animation and blast sprite frames
- Exclude asset-only folders without character definitions from fighter selection

## v0.10.0 - Added Jack and Jan with new special attacks
### Added
- Add Jack and Jan to the playable roster with their character assets
- Implement Jack Blast, knockdown attacks, and character-specific sounds
- Add Jan's healing birds and homing orb with targeting, effects, and audio
- Update README with the new characters and special attack controls

## v0.11.0 - Added Jack, Jan, John, Axle, Julian, and Knight as playable characters
### Added
- Each new playable characters have unique movesets and projectiles
- More projectiles, summons, animations, and audio
- Updated character selection screen
- Documentatin and version bump

## v0.12.0 - Expanded playable roster and combat
### Added
- Add Luis and Liberated Luis, including Luis's transformation and
  Liberated Luis's sword combos, wind attacks, and dash
- Add Mark's mana-powered charge, which can carry through one enemy and
  ends after a second target is hit
- Add Monk's wind strike and Rudolf's multi-lane shuriken volley and
  sword attacks
- Add fighter-specific attack animations, effects, and audio, including
  Rudolf's metal fragments when shurikens hit the ground
- Add armor-piece throwable sprites and sounds, with throws traveling
  twice as far as consumables
- Support mouse clicks in the title and character-selection screens
- Add second-jump attack animation handling
- Update sprite workflow, playable roster, controls, and move descriptions
  in the README

## v0.13.0 - Added Firzen, Sorcerer, and Woody
### Added
- Add Firzen with character blast, fire shots, and fire/ice orb attacks
- Add Sorcerer with fireball, freeze ball, and healing-orb attacks
- Add Woody with projectile volleys, chained punches, and dash attacks
- Add Rudolf's timed clone summon, including clone AI, combat handling,
  and smoke effects when clones disappear
- Extend combat targeting and projectile handling for the new fighters,
  attacks, and clones
- Add fighter animations, attack effects, and audio assets
- Add a missing Julian basic-hurt animation frame

## v0.14.0 - Add Stage Mode, City scenery, and heavy-box gameplay
### Added
- Add a ten-stage campaign with character selection and Roman-numeral
  title cards
- Integrate the City backdrop and layered arena
- Add heavy-box carrying, throwing, obstacle interactions, break effects,
  and audio
- Add a scrollable, newest-first Update History panel
- Update sprite-anchor tooling and release controls documentation

## v0.15.0 - Add Test Mode, opponent selection, and baseballs
### Added
- Add Test Mode for practicing without enemies and let players select one or more opponents for Play Mode.
- Buffer special-move chord inputs so the keys can be pressed in any order.
- Add baseballs with spawn, carry, throw, and landing animations; baseballs bounce once and play a break sound.
- Smooth camera following and refine Davis, Bat, and Dark Bat move presentation.
- Update the README with the revised modes and controls.