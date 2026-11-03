import unittest
from pathlib import Path

import pygame

from game.data.characters import CHARACTERS
from game.entities.fighter import Fighter, FighterConfig, FighterInput
from game.scenes.battle_scene import BattleScene, FireBreathProjectile, JohnBarrierEffect


class ReeceSpecialMoveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.display.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def test_move_attack_one_repeats_only_after_animation_and_pays_mana_again(self) -> None:
        fighter = Fighter(FighterConfig("reece", CHARACTERS["reece"]), (120.0, 40.0))
        fighter.mana = 20
        held_chord = FighterInput(
            left=True,
            horizontal_move_active=True,
            attack_pressed=True,
            block_pressed=True,
        )

        fighter.update(0.01, held_chord)
        self.assertEqual(fighter.state, "sp_move_attack_1")
        self.assertEqual(fighter.mana, 15)

        for _ in range(6):
            fighter.update(0.08, held_chord)
        self.assertEqual(fighter.state, "sp_move_attack_1")
        self.assertEqual(fighter.mana, 15)
        self.assertEqual(fighter.animation_player.frame_index, 6)

        fighter.update(0.08, held_chord)
        self.assertEqual(fighter.state, "sp_move_attack_1")
        self.assertEqual(fighter.mana, 16)
        self.assertEqual(fighter.animation_player.frame_index, 7)

        fighter.update(0.08, held_chord)
        self.assertEqual(fighter.state, "sp_move_attack_1")
        self.assertEqual(fighter.mana, 11)
        self.assertEqual(fighter.animation_player.frame_index, 0)
        self.assertFalse(fighter.animation_player.finished)

    def test_move_attack_one_does_not_repeat_without_enough_mana(self) -> None:
        fighter = Fighter(FighterConfig("reece", CHARACTERS["reece"]), (120.0, 40.0))
        fighter.mana = 5
        held_chord = FighterInput(
            left=True,
            horizontal_move_active=True,
            attack_pressed=True,
            block_pressed=True,
        )

        fighter.update(0.01, held_chord)
        for _ in range(9):
            fighter.update(0.08, held_chord)

        self.assertNotEqual(fighter.state, "sp_move_attack_1")
        self.assertLess(fighter.mana, 5)
        self.assertIsNone(fighter.special_move_followup_state)

    def test_move_attack_two_queues_vape_barrier_on_animation_frame_three(self) -> None:
        fighter = Fighter(FighterConfig("reece", CHARACTERS["reece"]), (120.0, 40.0))
        fighter._start_attack_state("sp_move_attack_2")
        fighter.animation_player.play("sp_move_attack_2")
        fighter.animation_player.frame_index = 0
        fighter.animation_player.timer = 0.07

        fighter.update(0.01, FighterInput())
        self.assertFalse(fighter.reece_vape_barrier_pending)
        fighter.update(0.081, FighterInput())
        self.assertTrue(fighter.reece_vape_barrier_pending)

        class Audio:
            def __init__(self) -> None:
                self.played = []

            def play(self, sound: str) -> None:
                self.played.append(sound)

        scene = object.__new__(BattleScene)
        scene.projectiles = []
        scene.audio = Audio()
        scene._spawn_john_barrier(fighter)

        self.assertFalse(fighter.reece_vape_barrier_pending)
        self.assertEqual(scene.audio.played, ["john_barrier_create"])
        self.assertEqual(len(scene.projectiles), 1)
        barrier = scene.projectiles[0]
        self.assertIsInstance(barrier, JohnBarrierEffect)
        self.assertEqual(barrier.phase, "create")
        self.assertEqual(len(barrier.barrier_frames), 3)

        asset = (
            Path(__file__).resolve().parents[1]
            / "assets"
            / "sprites"
            / "shared_sprites"
            / "vape_barrier"
            / "barrier"
            / "3.png"
        )
        expected_frame = pygame.image.load(str(asset)).convert()
        expected_frame.set_colorkey((0, 0, 0))
        expected_frame = pygame.transform.scale(
            expected_frame,
            (
                max(1, round(expected_frame.get_width() * 1.25)),
                max(1, round(expected_frame.get_height() * 1.25)),
            ),
        )
        self.assertEqual(
            pygame.image.tobytes(barrier.barrier_frames[2], "RGBA"),
            pygame.image.tobytes(expected_frame, "RGBA"),
        )

        barrier.update(0.16)
        self.assertTrue(barrier.can_reflect)
        barrier.update(8.0)
        self.assertEqual(barrier.phase, "burst")
        barrier.update(0.25)
        self.assertTrue(barrier.finished)

    def test_vert_attack_one_starts_fire_on_frame_two_loops_while_held_and_ends_on_release(self) -> None:
        fighter = Fighter(FighterConfig("reece", CHARACTERS["reece"]), (120.0, 200.0))
        fighter.mana = 20
        held_chord = FighterInput(up=True, attack_pressed=True, block_pressed=True)

        fighter.update(0.01, held_chord)
        self.assertEqual(fighter.state, "sp_vert_attack_1")
        self.assertEqual(fighter.mana, 10)
        scene = object.__new__(BattleScene)
        scene.projectiles = []

        class Audio:
            def __init__(self) -> None:
                self.plays = 0

            def play_fire_breath(self) -> None:
                self.plays += 1

        scene.audio = Audio()
        for _ in range(3):
            fighter.update(0.08, held_chord)
            self.assertEqual(fighter.reece_fire_breath_projectiles_pending, 0)
        self.assertEqual(fighter.animation_player.frame_index, 3)

        fighter.update(0.08, held_chord)
        self.assertEqual(fighter.reece_fire_breath_projectiles_pending, 1)
        scene._spawn_reece_fire_breath(fighter)
        self.assertEqual(len(scene.projectiles), 2)
        self.assertTrue(all(isinstance(projectile, FireBreathProjectile) for projectile in scene.projectiles))
        lane_positions = [projectile.lane_y for projectile in scene.projectiles]
        self.assertIn(fighter.lane_y, lane_positions)
        self.assertGreater(abs(lane_positions[0] - lane_positions[1]), 0)
        self.assertLessEqual(abs(lane_positions[0] - lane_positions[1]), 20)
        self.assertTrue(all(projectile.facing == fighter.facing for projectile in scene.projectiles))
        initial_x_positions = [projectile.x for projectile in scene.projectiles]
        for projectile in scene.projectiles:
            projectile.update(0.1)
        self.assertTrue(
            all(
                projectile.x > initial_x
                for projectile, initial_x in zip(scene.projectiles, initial_x_positions)
            )
        )
        self.assertEqual(scene.audio.plays, 2)

        mana_after_start = fighter.mana
        for _ in range(2):
            fighter.update(0.08, held_chord)
            scene._spawn_reece_fire_breath(fighter)
        self.assertEqual(fighter.animation_player.frame_index, 4)
        self.assertEqual(len(scene.projectiles), 6)
        self.assertGreaterEqual(fighter.mana, mana_after_start)

        for _ in range(6):
            fighter.update(0.08, FighterInput())
            scene._spawn_reece_fire_breath(fighter)
        self.assertEqual(fighter.state, "idle")
        self.assertEqual(fighter.animation_player.frame_index, 7)
        self.assertEqual(len(scene.projectiles), 14)


if __name__ == "__main__":
    unittest.main()
