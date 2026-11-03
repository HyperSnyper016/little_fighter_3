from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CampaignWave:
    enemies: tuple[tuple[str, int], ...]
    banner: str
    threat_budget: float = 0.0


@dataclass(frozen=True)
class CampaignEncounter:
    title: str
    act: str
    description: str
    waves: tuple[CampaignWave, ...]
    threat_budget: float = 0.0
    is_milestone: bool = False


@dataclass(frozen=True)
class EndlessStageMilestone:
    """A roster and group-size milestone for the indefinitely repeating Stage Mode."""

    first_stage: int
    title: str
    act: str
    description: str
    roster: tuple[str, ...]
    enemy_count: int
    growth_interval: int = 2


# Milestones introduce a few new combatants at a time and set a minimum budget
# that grows within each tier. The final roster remains in rotation, so there
# is no final encounter or automatic health-scaling curve.
ENDLESS_STAGE_MILESTONES = (
    EndlessStageMilestone(
        1,
        "Street Warm-Up",
        "ENDLESS RUN - THE CITY",
        "A lone bandit tests your footing.",
        ("bandit",),
        1,
        growth_interval=1,
    ),
    EndlessStageMilestone(
        3,
        "Ranged Trouble",
        "ENDLESS RUN - THE CITY",
        "Hunters join the street gang.",
        ("bandit", "hunter"),
        3,
    ),
    EndlessStageMilestone(
        5,
        "Fighters in the Shadows",
        "ENDLESS RUN - THE CITY",
        "Jack and the knights reinforce the gang.",
        ("bandit", "hunter", "jack", "knight"),
        4,
    ),
    EndlessStageMilestone(
        7,
        "Dojo and Nightfall",
        "ENDLESS RUN - THE CITY",
        "Monks and bat fighters join the attack.",
        ("bandit", "hunter", "jack", "knight", "monk", "bat"),
        5,
    ),
    EndlessStageMilestone(
        9,
        "Armored Rivals",
        "ENDLESS RUN - THE CITY",
        "Armored bandits and Mark's crew take the field.",
        ("bandit", "hunter", "jack", "knight", "monk", "bat", "armored_bandit", "mark"),
        6,
    ),
    EndlessStageMilestone(
        11,
        "Arcane Front",
        "ENDLESS RUN - THE CITY",
        "Sorcerers and Axle's guards join the fight.",
        (
            "bandit",
            "hunter",
            "jack",
            "knight",
            "monk",
            "bat",
            "armored_bandit",
            "mark",
            "sorcerer",
            "axle",
        ),
        7,
    ),
    EndlessStageMilestone(
        14,
        "Last Stand",
        "ENDLESS RUN - THE CITY",
        "Henry and Liberated Luis enter the fray.",
        (
            "bandit",
            "hunter",
            "jack",
            "knight",
            "monk",
            "bat",
            "armored_bandit",
            "mark",
            "sorcerer",
            "axle",
            "henry",
            "luis_liberated",
        ),
        9,
    ),
    EndlessStageMilestone(
        18,
        "Elemental Assault",
        "ENDLESS RUN - THE CITY",
        "Dark bat fighters, Firen, and Freeze join the rotation.",
        (
            "bandit",
            "hunter",
            "jack",
            "knight",
            "monk",
            "bat",
            "armored_bandit",
            "mark",
            "sorcerer",
            "axle",
            "henry",
            "luis_liberated",
            "dark_bat",
            "firen",
            "freeze",
        ),
        11,
    ),
    EndlessStageMilestone(
        23,
        "Full Roster",
        "ENDLESS RUN - THE CITY",
        "The full roster cycles into increasingly large squads.",
        (
            "bandit",
            "hunter",
            "jack",
            "knight",
            "monk",
            "bat",
            "armored_bandit",
            "mark",
            "sorcerer",
            "axle",
            "henry",
            "luis_liberated",
            "dark_bat",
            "firen",
            "freeze",
            "deep",
            "firzen",
            "davis",
            "denis",
            "jan",
            "john",
            "julian",
            "luis",
            "reece",
            "rudolf",
            "woody",
            "ashley",
        ),
        14,
    ),
)

ENDLESS_REINFORCEMENT_INTERVAL = 4
ENDLESS_MILESTONE_INTERVAL = 5
ENDLESS_ENEMY_THREAT = {
    "bandit": 1.0,
    "hunter": 1.2,
    "jack": 1.1,
    "knight": 1.5,
    "monk": 1.1,
    "bat": 1.2,
    "armored_bandit": 1.7,
    "mark": 2.0,
    "sorcerer": 1.5,
    "axle": 1.8,
    "henry": 2.0,
    "luis_liberated": 2.0,
    "dark_bat": 2.0,
    "firen": 2.0,
    "freeze": 2.0,
    "deep": 2.0,
    "firzen": 2.5,
    "davis": 1.5,
    "denis": 1.5,
    "jan": 1.5,
    "john": 1.5,
    "julian": 2.5,
    "luis": 1.5,
    "reece": 1.5,
    "rudolf": 1.5,
    "woody": 1.5,
    "ashley": 1.5,
}
ENDLESS_RANGED_ENEMIES = frozenset(
    {"hunter", "sorcerer", "axle", "henry", "dark_bat", "firen", "freeze", "deep", "firzen"}
)
ENDLESS_ARMORED_ENEMIES = frozenset({"armored_bandit"})
ENDLESS_STRONG_ENEMIES = frozenset(
    {
        "knight",
        "mark",
        "axle",
        "henry",
        "luis_liberated",
        "dark_bat",
        "firen",
        "freeze",
        "deep",
        "firzen",
        "julian",
    }
)
ENDLESS_MILESTONE_ENEMY_ROTATION = (
    "armored_bandit",
    "mark",
    "axle",
    "henry",
    "luis_liberated",
    "dark_bat",
    "firen",
    "freeze",
    "deep",
    "firzen",
    "julian",
)


def _enemy_threat(character_name: str) -> float:
    return ENDLESS_ENEMY_THREAT.get(character_name, 1.5)


def _milestone_enemy(roster: tuple[str, ...], stage_number: int) -> str | None:
    unlocked = set(roster)
    available = tuple(
        character
        for character in ENDLESS_MILESTONE_ENEMY_ROTATION
        if character in unlocked
    )
    if available:
        return available[((stage_number // ENDLESS_MILESTONE_INTERVAL) - 1) % len(available)]
    return next((name for name in reversed(roster) if name != "bandit"), None)


def _choose_endless_enemy(
    roster: tuple[str, ...],
    stage_number: int,
    selection_index: int,
    used: tuple[str, ...] = (),
) -> str:
    role = ("melee", "ranged", "melee", "armored", "strong", "melee")[selection_index % 6]
    if role == "ranged":
        candidates = tuple(name for name in roster if name in ENDLESS_RANGED_ENEMIES)
    elif role == "armored":
        candidates = tuple(name for name in roster if name in ENDLESS_ARMORED_ENEMIES)
    elif role == "strong":
        candidates = tuple(name for name in roster if name in ENDLESS_STRONG_ENEMIES)
    else:
        candidates = tuple(
            name
            for name in roster
            if name not in ENDLESS_RANGED_ENEMIES
            and name not in ENDLESS_ARMORED_ENEMIES
            and name not in ENDLESS_STRONG_ENEMIES
        )
    if not candidates:
        candidates = roster
    unused = tuple(name for name in candidates if name not in used)
    if unused:
        candidates = unused
    return candidates[(stage_number + selection_index + 2) % len(candidates)]


def get_endless_encounter(
    stage_number: int,
    difficulty: str = "Medium",
) -> CampaignEncounter:
    """Return the deterministic encounter for a one-based endless stage.

    The budget rises by 0.9 threat per stage. Difficulty adjusts the budget,
    while fixed enemy threat values keep fighter stats stable. Every fifth
    stage is a deterministic milestone; every fourth stage and every squad
    of five or more split into an opening wave and reinforcements.
    """
    if stage_number < 1:
        raise ValueError("stage_number must be positive")

    milestone = ENDLESS_STAGE_MILESTONES[0]
    for candidate in ENDLESS_STAGE_MILESTONES:
        if candidate.first_stage > stage_number:
            break
        milestone = candidate

    difficulty_scale = {"Easy": 0.9, "Medium": 1.0, "Hard": 1.1}.get(difficulty)
    if difficulty_scale is None:
        raise ValueError(f"Unknown difficulty: {difficulty}")
    stage_offset = stage_number - milestone.first_stage
    milestone_budget = milestone.enemy_count + stage_offset // milestone.growth_interval
    threat_budget = max(1.0 + (stage_number - 1) * 0.9, milestone_budget)
    threat_budget *= difficulty_scale
    if stage_number == 1:
        threat_budget = 1.0
    is_milestone = stage_number > 1 and stage_number % ENDLESS_MILESTONE_INTERVAL == 0
    remaining_budget = threat_budget
    squad_names: list[str] = []
    if stage_number == 1:
        squad_names = ["bandit"]
        remaining_budget = 0.0
    else:
        previous_roster = next(
            (
                candidate.roster
                for candidate in reversed(ENDLESS_STAGE_MILESTONES)
                if candidate.first_stage < milestone.first_stage
            ),
            (),
        )
        newly_unlocked = tuple(
            name for name in milestone.roster if name not in previous_roster
        )
        if (
            stage_number == milestone.first_stage + 1
            and newly_unlocked
        ):
            introduced_enemy = newly_unlocked[
                stage_number % len(newly_unlocked)
            ]
            if _enemy_threat(introduced_enemy) <= remaining_budget:
                squad_names.append(introduced_enemy)
                remaining_budget -= _enemy_threat(introduced_enemy)

        if is_milestone:
            milestone_enemy = _milestone_enemy(milestone.roster, stage_number)
            if milestone_enemy is not None and _enemy_threat(milestone_enemy) <= remaining_budget:
                squad_names.append(milestone_enemy)
                remaining_budget -= _enemy_threat(milestone_enemy)

        selection_index = 0
        while remaining_budget >= 1.0:
            character = _choose_endless_enemy(
                milestone.roster,
                stage_number,
                selection_index + (1 if is_milestone else 0),
                tuple(squad_names),
            )
            threat = _enemy_threat(character)
            if threat > remaining_budget:
                affordable = tuple(
                    name
                    for name in milestone.roster
                    if _enemy_threat(name) <= remaining_budget
                )
                if not affordable:
                    break
                character = affordable[(stage_number + selection_index) % len(affordable)]
                threat = _enemy_threat(character)
            squad_names.append(character)
            remaining_budget -= threat
            selection_index += 1

    squad = tuple((character, 1) for character in squad_names)
    squad_threat = sum(_enemy_threat(character) for character in squad_names)
    if stage_number > 1 and (
        stage_number % ENDLESS_REINFORCEMENT_INTERVAL == 0
        or len(squad) >= 5
    ):
        split_at = (len(squad) + 1) // 2
        if split_at < len(squad):
            opening, reinforcement = squad[:split_at], squad[split_at:]
            waves = (
                CampaignWave(
                    opening,
                    "The opening squad blocks the street.",
                    threat_budget
                    * sum(_enemy_threat(name) * count for name, count in opening)
                    / squad_threat,
                ),
                CampaignWave(
                    reinforcement,
                    "Reinforcements join the fight.",
                    threat_budget
                    * sum(_enemy_threat(name) * count for name, count in reinforcement)
                    / squad_threat,
                ),
            )
        else:
            waves = (
                CampaignWave(
                    squad,
                    "Clear the enemy squad.",
                    squad_threat,
                ),
            )
    else:
        waves = (CampaignWave(squad, "Clear the enemy squad.", threat_budget),)

    return CampaignEncounter(
        milestone.title,
        milestone.act,
        milestone.description,
        waves,
        threat_budget,
        is_milestone,
    )
