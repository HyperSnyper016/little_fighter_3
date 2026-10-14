import unittest

from game.data.archetypes import (
    ARCHETYPES,
    CHARACTER_ARCHETYPES,
    resolve_character_profile,
)
from game.data.characters import CHARACTERS


class ArchetypeProfileTests(unittest.TestCase):
    def test_every_character_has_a_valid_archetype(self) -> None:
        self.assertEqual(set(CHARACTER_ARCHETYPES), set(CHARACTERS))
        for character_key, definition in CHARACTERS.items():
            archetype, stats, movement = resolve_character_profile(character_key, definition)
            self.assertEqual(archetype.key, CHARACTER_ARCHETYPES[character_key])
            self.assertGreater(int(stats["max_health"]), 0)
            self.assertGreaterEqual(int(stats["max_mana"]), 0)
            self.assertIn("walk_speed", movement)
            self.assertIn("run_speed", movement)

    def test_archetypes_supply_distinct_stat_baselines(self) -> None:
        expected = {
            "bandit": (10, 20),
            "davis": (11, 80),
            "henry": (9, 110),
            "firen": (9, 120),
            "luis": (12, 70),
            "julian": (15, 120),
            "template": (10, 20),
            "dummy": (9999, 20),
        }
        for character_key, values in expected.items():
            with self.subTest(character=character_key):
                _, stats, _ = resolve_character_profile(
                    character_key,
                    CHARACTERS[character_key],
                )
                self.assertEqual((stats["max_health"], stats["max_mana"]), values)

    def test_character_overrides_and_movement_are_preserved(self) -> None:
        archetype, stats, movement = resolve_character_profile(
            "davis",
            {
                "stat_overrides": {"max_health": 25, "max_mana": 60},
                "stats": {"touch_damage": 3},
                "movement": {"walk_speed": 500.0},
            },
        )
        self.assertEqual(archetype.key, "brawler")
        self.assertEqual(
            (stats["max_health"], stats["max_mana"], stats["touch_damage"]),
            (25, 60, 3),
        )
        self.assertEqual(movement["walk_speed"], 500.0)
        self.assertEqual(movement["run_speed"], ARCHETYPES["brawler"].movement["run_speed"])

    def test_luis_transformation_keeps_matching_archetype_baselines(self) -> None:
        luis, luis_stats, _ = resolve_character_profile("luis", CHARACTERS["luis"])
        liberated, liberated_stats, _ = resolve_character_profile(
            "luis_liberated",
            CHARACTERS["luis_liberated"],
        )
        self.assertEqual(luis.key, liberated.key)
        self.assertEqual(
            (luis_stats["max_health"], luis_stats["max_mana"]),
            (liberated_stats["max_health"], liberated_stats["max_mana"]),
        )


if __name__ == "__main__":
    unittest.main()
