import unittest
from pathlib import Path

import pygame

from game.data.characters import CHARACTERS
from game.scenes.character_select_scene import (
    PREVIEW_CLONE_MOVES,
    PREVIEW_COMPANIONS,
    PREVIEW_PROJECTILES,
    PreviewCompanion,
    PreviewClone,
    PreviewProjectile,
)


class CharacterPreviewEffectTests(unittest.TestCase):
    REQUIRED_PROJECTILE_MOVES = {
        ("hunter", "attack_punch"),
        ("henry", "attack_1"),
        ("henry", "sp_move_attack_1"),
        ("henry", "sp_move_attack_2"),
        ("henry", "sp_vert_attack_1"),
        ("rudolf", "attack_1"),
        ("rudolf", "attack_2"),
        ("rudolf", "sp_move_attack_1"),
        ("jack", "sp_move_attack_1"),
        ("axle", "sp_move_attack_1"),
        ("julian", "sp_move_attack_1"),
        ("julian", "sp_move_attack_2"),
        ("julian", "sp_vert_attack_1"),
        ("julian", "sp_vert_attack_2"),
        ("john", "sp_move_attack_1"),
        ("john", "sp_move_attack_2"),
        ("john", "sp_vert_attack_1"),
        ("john", "sp_vert_attack_2"),
        ("jan", "sp_vert_attack_1"),
        ("jan", "sp_vert_attack_2"),
        ("bat", "sp_move_attack_2"),
        ("bat", "sp_vert_attack_2"),
        ("dark_bat", "sp_move_attack_2"),
        ("dark_bat", "sp_vert_attack_1"),
        ("freeze", "sp_move_attack_1"),
        ("freeze", "sp_move_attack_2"),
        ("freeze", "sp_vert_attack_1"),
        ("sorcerer", "sp_move_attack_1"),
        ("sorcerer", "sp_move_attack_2"),
        ("sorcerer", "sp_vert_attack_2"),
        ("template", "sp_move_attack_1"),
        ("davis", "sp_move_attack_1"),
        ("denis", "sp_move_attack_1"),
        ("denis", "sp_vert_attack_2"),
        ("deep", "sp_move_attack_1"),
        ("firen", "sp_move_attack_1"),
        ("firen", "sp_move_attack_2"),
        ("firen", "sp_vert_attack_1"),
        ("firen", "sp_vert_attack_2"),
        ("firzen", "sp_move_attack_1"),
        ("firzen", "sp_move_attack_2"),
        ("firzen", "sp_vert_attack_1"),
        ("firzen", "sp_vert_attack_2"),
        ("woody", "sp_move_attack_1"),
        ("luis", "sp_move_attack_2"),
        ("luis_liberated", "sp_move_attack_2"),
        ("monk", "sp_move_attack_1"),
    }

    @staticmethod
    def _frames(count: int) -> list[pygame.Surface]:
        return [pygame.Surface((8, 8), pygame.SRCALPHA) for _ in range(count)]

    def test_firen_fireball_and_jan_healing_birds_are_timed_to_their_moves(self) -> None:
        self.assertEqual(
            PREVIEW_PROJECTILES[("firen", "sp_move_attack_1")][0].trigger_frames,
            (2,),
        )
        self.assertEqual(
            PREVIEW_COMPANIONS[("jan", "sp_vert_attack_1")].trigger_frame,
            3,
        )
        self.assertEqual(PREVIEW_CLONE_MOVES[("rudolf", "sp_vert_attack_2")], (4, 2))

    def test_every_registered_preview_uses_existing_sprite_folders(self) -> None:
        sprite_root = Path(__file__).resolve().parents[1] / "assets" / "sprites"
        registered_moves = set(PREVIEW_PROJECTILES) | set(PREVIEW_COMPANIONS) | set(PREVIEW_CLONE_MOVES)
        self.assertTrue(self.REQUIRED_PROJECTILE_MOVES <= registered_moves)
        for specs in PREVIEW_PROJECTILES.values():
            for spec in specs:
                self.assertTrue(sprite_root.joinpath("shared_sprites", *spec.travel_frames).is_dir())
                if spec.impact_frames is not None:
                    self.assertTrue(sprite_root.joinpath("shared_sprites", *spec.impact_frames).is_dir())
        for spec in PREVIEW_COMPANIONS.values():
            self.assertTrue(sprite_root.joinpath(*spec.create_frames).is_dir())
            self.assertTrue(sprite_root.joinpath(*spec.fly_frames).is_dir())

    def test_all_effect_triggers_exist_in_their_preview_animations(self) -> None:
        for (character, animation), specs in PREVIEW_PROJECTILES.items():
            files = CHARACTERS[character]["animations"][animation]["files"]
            for spec in specs:
                self.assertTrue(all(0 <= frame < len(files) for frame in spec.trigger_frames))
        for (character, animation), spec in PREVIEW_COMPANIONS.items():
            files = CHARACTERS[character]["animations"][animation]["files"]
            self.assertLess(spec.trigger_frame, len(files))
        for (character, animation), (trigger_frame, _) in PREVIEW_CLONE_MOVES.items():
            files = CHARACTERS[character]["animations"][animation]["files"]
            self.assertLess(trigger_frame, len(files))

    def test_volley_specs_preserve_multiple_launch_frames_and_sprites(self) -> None:
        denis_orbs = PREVIEW_PROJECTILES[("denis", "sp_move_attack_1")][0]
        self.assertEqual(len(denis_orbs.trigger_frames), 5)
        henry_arrows = PREVIEW_PROJECTILES[("henry", "sp_vert_attack_1")][0]
        self.assertEqual(henry_arrows.count, 5)
        firzen_shots = PREVIEW_PROJECTILES[("firzen", "sp_move_attack_2")][0]
        self.assertEqual(firzen_shots.count, 3)
        woody_shots = PREVIEW_PROJECTILES[("woody", "sp_move_attack_1")][0]
        self.assertEqual(woody_shots.count, 3)
        self.assertEqual(woody_shots.trigger_frames, (4, 7))
        self.assertEqual(len(PREVIEW_COMPANIONS[("dark_bat", "sp_vert_attack_1")].offsets), 6)

    def test_preview_projectile_travels_then_plays_its_impact(self) -> None:
        projectile = PreviewProjectile(
            self._frames(3),
            self._frames(2),
            (10.0, 20.0),
            110.0,
            0.5,
        )
        projectile.update(0.25)
        self.assertAlmostEqual(projectile.x, 60.0)
        self.assertFalse(projectile.impacting)

        projectile.update(0.25)
        self.assertTrue(projectile.impacting)
        self.assertEqual(projectile.x, 110.0)
        projectile.update(0.1)
        self.assertTrue(projectile.finished)

    def test_preview_sprite_without_impact_finishes_after_its_travel(self) -> None:
        projectile = PreviewProjectile(
            self._frames(3),
            None,
            (10.0, 20.0),
            10.0,
            0.2,
        )
        projectile.update(0.2)
        self.assertTrue(projectile.finished)
        self.assertFalse(projectile.impacting)

    def test_preview_companion_plays_creation_and_flight(self) -> None:
        companion = PreviewCompanion(
            self._frames(2),
            self._frames(3),
            (100.0, 100.0),
            (80.0, -50.0),
            0.8,
            0.0,
        )
        companion.update(0.08)
        self.assertEqual(companion.frame_index, 1)
        companion.update(0.24)
        self.assertNotEqual((companion.x, companion.y), (100.0, 100.0))
        companion.update(0.5)
        self.assertTrue(companion.finished)

    def test_preview_clone_uses_attack_frames_and_expires(self) -> None:
        clone = PreviewClone(self._frames(3), (100, 120), -80, 0.5, True)
        clone.update(0.24)
        self.assertFalse(clone.finished)
        clone.update(0.3)
        self.assertTrue(clone.finished)


if __name__ == "__main__":
    unittest.main()
