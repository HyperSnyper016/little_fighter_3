from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


CARD_OFFER_WEIGHT_PER_RANK = 0.95
MIN_CARD_OFFER_WEIGHT = 1e-12
BANDIT_HORDE_MAX_BONUS = 3
JULIAN_SKULL_BASE_INTERVAL = 24.0
JULIAN_SKULL_MIN_INTERVAL = 12.0
JULIAN_SKULL_INTERVAL_REDUCTION_PER_RANK = 3.0


@dataclass(frozen=True)
class StageCard:
    key: str
    title: str
    description: str
    perk: str
    image: str
    effect: str
    amount_per_rank: float


STAGE_CARD_CATALOG = (
    StageCard("heavy_hands", "Heavy Hands", "Hit harder with every attack.", "+6% damage", "perk_cards/heavy_hands.png", "damage", 0.06),
    StageCard("iron_skin", "Iron Skin", "Take less damage from every hit.", "-5% damage taken", "perk_cards/iron_skin.png", "damage_reduction", 0.05),
    StageCard("quick_step", "Quickstep", "Move faster across the arena.", "+5% movement speed", "perk_cards/quick_step.png", "movement_speed", 0.05),
    StageCard("vitality", "Vitality", "Increase your maximum health.", "+1 max HP", "perk_cards/vitality.png", "max_health", 1.0),
    StageCard("xp_magnet", "XP Magnet", "Collect XP orbs from farther away.", "+20% pickup range", "perk_cards/xp_magnet.png", "xp_range", 0.20),
    StageCard("fast_learner", "Fast Learner", "Gain more XP from every orb.", "+8% XP per orb", "perk_cards/fast_learner.png", "xp_gain", 0.08),
    StageCard(
        "bandit_horde",
        "Bandit Horde",
        "More enemies crowd the arena at once.",
        "+1 active enemy / rank (max +3)",
        "curse_cards/bandit_horde.png",
        "active_enemy",
        1.0,
    ),
    StageCard(
        "hardened_gang",
        "Hardened Gang",
        "The gang grows tougher with every curse rank.",
        "+1 enemy max HP / rank",
        "curse_cards/hardened_gang.png",
        "enemy_health",
        1.0,
    ),
    StageCard(
        "julians_skull",
        "Julian's Skull",
        "A skull streaks across your lane to hunt you down.",
        "Skull every 24 sec; -3 sec / rank (min 12)",
        "curse_cards/julians_skull.png",
        "julian_skull",
        JULIAN_SKULL_INTERVAL_REDUCTION_PER_RANK,
    ),
)
CARDS_BY_KEY = {card.key: card for card in STAGE_CARD_CATALOG}
CARDS_BY_TITLE = {card.title: card for card in STAGE_CARD_CATALOG}


def roman_rank(rank: int) -> str:
    if rank < 1:
        raise ValueError(f"Card rank must be positive, got {rank}.")
    numerals = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    result = []
    for value, numeral in numerals:
        count, rank = divmod(rank, value)
        result.append(numeral * count)
    return "".join(result)


def card_rank_title(card: StageCard | str, rank: int) -> str:
    entry = CARDS_BY_TITLE[card] if isinstance(card, str) else card
    return f"{entry.title} Lvl {roman_rank(rank)}"


def eligible_cards() -> tuple[StageCard, ...]:
    return STAGE_CARD_CATALOG


def card_offer_weight(rank: int) -> float:
    """Return a positive relative offer weight that decreases by 5% per rank."""
    weight = CARD_OFFER_WEIGHT_PER_RANK ** max(0, int(rank))
    return max(MIN_CARD_OFFER_WEIGHT, weight)


def stage_card_effects(ranks: Mapping[str, int] | None = None) -> dict[str, float]:
    owned = ranks or {}
    effects = {
        "damage_multiplier": 1.0,
        "damage_reduction": 0.0,
        "movement_multiplier": 1.0,
        "max_health_bonus": 0.0,
        "xp_range_multiplier": 1.0,
        "xp_gain_multiplier": 1.0,
        "enemy_health_bonus": 0.0,
        "active_enemy_bonus": 0.0,
        "julian_skull_interval": 0.0,
    }
    effect_keys = {
        "damage": "damage_multiplier",
        "damage_reduction": "damage_reduction",
        "movement_speed": "movement_multiplier",
        "max_health": "max_health_bonus",
        "xp_range": "xp_range_multiplier",
        "xp_gain": "xp_gain_multiplier",
        "enemy_health": "enemy_health_bonus",
    }
    for card in STAGE_CARD_CATALOG:
        rank = max(0, int(owned.get(card.key, 0)))
        if card.effect == "active_enemy":
            effects["active_enemy_bonus"] = min(
                BANDIT_HORDE_MAX_BONUS,
                rank,
            )
            continue
        if card.effect == "julian_skull":
            if rank > 0:
                effects["julian_skull_interval"] = max(
                    JULIAN_SKULL_MIN_INTERVAL,
                    JULIAN_SKULL_BASE_INTERVAL
                    - card.amount_per_rank * (rank - 1),
                )
            continue
        key = effect_keys[card.effect]
        if card.effect in {"damage", "movement_speed", "xp_gain", "xp_range"}:
            effects[key] += card.amount_per_rank * rank
        elif card.effect == "damage_reduction":
            effects[key] = min(0.9, effects[key] + card.amount_per_rank * rank)
        else:
            effects[key] += card.amount_per_rank * rank
    return effects
