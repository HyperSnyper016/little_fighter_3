import unittest
from pathlib import Path
from types import SimpleNamespace

import pygame

from game.data.characters import CHARACTERS
from game.entities.fighter import Fighter, FighterConfig, FighterInput
from game.scenes.battle_scene import (
    BUZZ_BALL_ITEM_ID,
    BattleScene,
    BuzzBallProjectile,
    IceFragmentEffect,
    _is_spawnable_item,
    _load_item_sprite_animations,
)


class BuzzBallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.display.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def test_assets_load_and_buzz_ball_is_excluded_from_random_spawns(self) -> None:
        sprite_root = Path(__file__).resolve().parents[1] / "assets" / "sprites" / "item_sprites"
        animations = _load_item_sprite_animations(sprite_root)[BUZZ_BALL_ITEM_ID]
        self.assertTrue(animations["throw"])
        for name in ("large", "small_1", "small_2"):
            with self.subTest(fragment=name):
                self.assertTrue(animations[f"broken/{name}"])

        spawn_animations = {"spawn": [object()], "holding": [object()], "throw": [object()]}
        self.assertFalse(_is_spawnable_item(BUZZ_BALL_ITEM_ID, spawn_animations, True))
        self.assertTrue(_is_spawnable_item("throwables/baseball", spawn_animations, True))

    def test_reece_launches_buzz_ball_on_sprite_frame_seven_from_frame_eight_chest_anchor(self) -> None:
        fighter = Fighter(FighterConfig("reece", CHARACTERS["reece"]), (120.0, 40.0))
        fighter._start_attack_state("sp_move_attack_1")
        fighter.animation_player.play("sp_move_attack_1")
        fighter.animation_player.frame_index = 4
        fighter.animation_player.timer = 0.07

        fighter.update(0.01, FighterInput())
        self.assertFalse(fighter.reece_buzz_ball_pending)
        fighter.update(0.081, FighterInput())
        self.assertEqual(fighter.animation_player.frame_index, 6)
        self.assertTrue(fighter.reece_buzz_ball_pending)

        scene = object.__new__(BattleScene)
        scene.projectiles = []
        scene.buzz_ball_throw_frames = [pygame.Surface((12, 12), pygame.SRCALPHA)]
        reference_frame = fighter.animations["sp_move_attack_1"]["surfaces"][7]
        for facing in (1, -1):
            with self.subTest(facing=facing):
                fighter.facing = facing
                fighter.reece_buzz_ball_pending = True
                scene._spawn_reece_buzz_ball(fighter)
                self.assertEqual(len(scene.projectiles), 1)
                projectile = scene.projectiles.pop()
                self.assertIsInstance(projectile, BuzzBallProjectile)
                self.assertEqual(projectile.facing, facing)
                self.assertAlmostEqual(
                    projectile.x,
                    fighter.x + facing * (scene.buzz_ball_throw_frames[0].get_width() / 2),
                )
                expected_chest_y = fighter.draw_pos()[1] + reference_frame.get_height() * 0.53
                self.assertAlmostEqual(projectile.y, expected_chest_y)
                self.assertFalse(fighter.reece_buzz_ball_pending)

    def test_buzz_ball_enemy_and_ground_impacts_play_break_effects(self) -> None:
        class Audio:
            def __init__(self) -> None:
                self.played = []

            def play(self, sound: str) -> None:
                self.played.append(sound)

        class Target:
            lane_y = 20.0
            is_dead = False
            state = "idle"
            health = 3
            x = 86.0

            def world_hitbox_rect(self) -> pygame.Rect:
                return pygame.Rect(70, 740, 32, 48)

            def receive_damage(self, amount: int, ignore_invulnerability: bool = False) -> None:
                self.health -= amount

            def _start_knockdown(self) -> None:
                self.state = "fall"

        frame = pygame.Surface((8, 8), pygame.SRCALPHA)
        owner = type("Owner", (), {"x": 20.0})()
        target = Target()
        scene = object.__new__(BattleScene)
        scene.fighter = owner
        scene.enemies = [target]
        scene.rudolf_clones = []
        scene.stage = SimpleNamespace(
            camera_x=lambda focus_x: 0.0,
            play_min_x=0.0,
            play_max_x=1000.0,
        )
        scene.projectiles = [
            BuzzBallProjectile(owner, 40.0, target.lane_y, 1, [frame])
        ]
        scene.consumable_break_effects = []
        scene.buzz_ball_break_frames = {
            "large": [frame],
            "small_1": [frame],
            "small_2": [frame],
        }
        scene.audio = Audio()
        scene.whiskey_status_effects = {}
        scene._opponents_of = lambda attacker: [target]

        scene._update_projectiles(0.06)

        self.assertFalse(scene.projectiles)
        self.assertEqual(target.health, 2)
        self.assertEqual(target.state, "fall")
        self.assertEqual(scene.audio.played, ["drink_break", "hit_success"])
        self.assertEqual(len(scene.consumable_break_effects), 3)
        self.assertTrue(all(isinstance(effect, IceFragmentEffect) for effect in scene.consumable_break_effects))
        velocities = [effect.velocity_x for effect in scene.consumable_break_effects]
        self.assertTrue(any(speed < 0 for speed in velocities))
        self.assertTrue(any(speed > 0 for speed in velocities))

        scene.projectiles = [
            BuzzBallProjectile(owner, 40.0, target.lane_y, 1, [frame])
        ]
        scene._opponents_of = lambda attacker: []
        scene._update_projectiles(0.75)
        self.assertFalse(scene.projectiles)
        self.assertEqual(scene.audio.played.count("drink_break"), 2)
        self.assertEqual(len(scene.consumable_break_effects), 6)


if __name__ == "__main__":
    unittest.main()
