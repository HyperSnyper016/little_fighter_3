from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CampaignWave:
    enemies: tuple[tuple[str, int], ...]
    banner: str


@dataclass(frozen=True)
class CampaignEncounter:
    title: str
    act: str
    description: str
    waves: tuple[CampaignWave, ...]


CAMPAIGN_ENCOUNTERS = (
    CampaignEncounter(
        "First Contact",
        "ACT I - CITY UNDER PRESSURE",
        "A street gang blocks the way forward.",
        (CampaignWave((("bandit", 1),), "Clear the street gang."),),
    ),
    CampaignEncounter(
        "Ranged Ambush",
        "ACT I - CITY UNDER PRESSURE",
        "Hunters join the gang's attack.",
        (CampaignWave((("bandit", 1), ("hunter", 1)), "Watch for ranged support."),),
    ),
    CampaignEncounter(
        "Jack's Challenge",
        "ACT I - CITY UNDER PRESSURE",
        "Break through the gang before Jack steps in.",
        (
            CampaignWave((("bandit", 1),), "The gang blocks the street."),
            CampaignWave((("hunter", 1),), "A hunter reinforces the gang."),
            CampaignWave((("jack", 1),), "Jack enters the fight."),
        ),
    ),
    CampaignEncounter(
        "Dojo Line",
        "ACT II - FIGHTERS IN THE SHADOWS",
        "Knights and monks defend the route.",
        (
            CampaignWave((("knight", 2),), "The knights guard the route."),
            CampaignWave((("monk", 1),), "A monk joins the defense."),
        ),
    ),
    CampaignEncounter(
        "Nightfall",
        "ACT II - FIGHTERS IN THE SHADOWS",
        "A lone bat fighter tests your defenses.",
        (CampaignWave((("bat", 1),), "Hold off the bat fighter."),),
    ),
    CampaignEncounter(
        "Ironclad Patrol",
        "ACT II - FIGHTERS IN THE SHADOWS",
        "Clear the street gang, then face its armored guard.",
        (
            CampaignWave((("bandit", 2),), "The bandits block the street."),
            CampaignWave(
                (("bandit", 1), ("armored_bandit", 1)),
                "An armored guard joins the last bandit.",
            ),
        ),
    ),
    CampaignEncounter(
        "Rivals Assemble",
        "ACT III - THE FINAL CONSPIRACY",
        "Mark's crew attacks before a sorcerer joins the fight.",
        (
            CampaignWave((("mark", 2),), "Mark's crew closes in."),
            CampaignWave((("mark", 1), ("sorcerer", 1)), "A sorcerer joins the last rival."),
        ),
    ),
    CampaignEncounter(
        "Arcane Front",
        "ACT III - THE FINAL CONSPIRACY",
        "A coordinated squad makes its final stand.",
        (
            CampaignWave(
                (("hunter", 2),),
                "The hunters open the attack.",
            ),
            CampaignWave(
                (("mark", 1),),
                "Mark cuts off the route.",
            ),
            CampaignWave(
                (("sorcerer", 1), ("monk", 1)),
                "The sorcerer and monk make their stand.",
            ),
        ),
    ),
    CampaignEncounter(
        "Axle's Last Stand",
        "ACT III - THE FINAL CONSPIRACY",
        "Jack's guards stall you while Axle prepares.",
        (
            CampaignWave((("jack", 2),), "Jack's guards hold the line."),
            CampaignWave((("axle", 2),), "Axle enters the fight."),
            CampaignWave((("axle", 1),), "Axle's final fighter steps in."),
        ),
    ),
    CampaignEncounter(
        "The Final Duel",
        "ACT III - THE FINAL CONSPIRACY",
        "Henry stands between you and Liberated Luis.",
        (
            CampaignWave((("henry", 1),), "Defeat Henry."),
            CampaignWave((("luis_liberated", 1),), "Liberated Luis challenges you."),
        ),
    ),
)

RECOVERY_STAGES = frozenset({3, 6, 9})
