# Stage Mode Roguelike Tasks

## Completed

- [x] Review the existing Stage Mode campaign, encounters, and battle flow.
- [x] Replace the fixed campaign with an endless run that starts with one Bandit and progressively adds enemies and enemy types.
- [x] Spawn Stage Mode enemies beyond the camera viewport so they run into the arena.
- [x] Add a four-second between-wave grace period while keeping gameplay active.
- [x] Scale endless waves with a threat budget, enemy variety, milestones, and an active-enemy cap.
- [x] Keep defeated enemy bodies for about 15 seconds without blocking wave progression.
- [x] Replace obstructive Stage Mode title cards with compact, non-blocking banners.
- [x] Add procedural XP orbs dropped by defeated Stage Mode enemies and collectable by the player.
- [x] Add XP thresholds and level progression; display level and XP progress during the run.
- [x] Add a temporary slot-machine level-up UI with queued, selectable ranked card offers.
- [x] Add cached card artwork, clipped/eased staggered reels, and progressive randomized card-detail reveals.
- [x] Add the ranked perk-and-curse catalog, distinct eligible offers, and Stage/Test Mode perk application.
- [x] Add Bandit Horde, Hardened Gang, and Julian's Skull curse effects to Stage Mode.
- [x] Move perk artwork into its own folder and glow curse artwork in card views.
- [x] Award XP scaled to the stage cleared after every fifth Stage Mode stage.

## Remaining

- [x] Update the run HUD to show wave, level, XP progress, and concise wave-transition cues.
- [ ] Test and balance a complete run, including endless progression, XP collection, level-ups, ranked cards, and wave transitions.

The six perks are Heavy Hands (+6% damage/rank), Iron Skin (-5% damage taken/rank), Quickstep (+5% movement speed/rank), Vitality (+1 max HP/rank), XP Magnet (+20% pickup range/rank), and Fast Learner (+8% XP/orb/rank). The curses are Bandit Horde (+1 active enemy/rank, capped at +3), Hardened Gang (+1 enemy max HP/rank), and Julian's Skull (a telegraphed lane projectile every 24 seconds, with a 12-second minimum interval). Each card's offer weight decreases by 5% per rank, and three distinct offers are selected by weight. Test Mode's F8 sequence remains visual-only.
