import unittest
from pathlib import Path
from types import SimpleNamespace

import pygame

from game.data.characters import CHARACTERS
from game.entities.fighter import Fighter, FighterConfig, FighterInput
from game.scenes.battle_scene import (
    BIGGIE_BALL_ITEM_ID,
    BiggieBallProjectile,
    BattleScene,
    IceFragmentEffect,
    _is_spawnable_item,
    _load_item_sprite_animations,
)


class BiggieBallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.display.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def test_biggie_ball_assets_load_and_are_excluded_from_random_spawns(self) -> None:
        sprite_root = Path(__file__).resolve().parents[1] / "assets" / "sprites" / "item_sprites"
        animations = _load_item_sprite_animations(sprite_root)[BIGGIE_BALL_ITEM_ID]
        self.assertTrue(animations["spawn"])
        for name in ("large", "small_1", "small_2"):
            with self.subTest(fragment=name):
                self.assertTrue(animations[f"broken/{name}"])

        spawn_animations = {"spawn": [object()], "holding": [object()], "throw": [object()]}
        self.assertFalse(_is_spawnable_item(BIGGIE_BALL_ITEM_ID, spawn_animations, True))
        self.assertTrue(_is_spawnable_item("throwables/baseball", spawn_animations, True))

    def test_reece_releases_biggie_ball_on_animation_frame_three_in_front(self) -> None:
        fighter = Fighter(FighterConfig("reece", CHARACTERS["reece"]), (120.0, 40.0))
        fighter._start_attack_state("sp_vert_attack_2")
        fighter.animation_player.play("sp_vert_attack_2")
        fighter.animation_player.frame_index = 1
        fighter.animation_player.timer = 0.07

        fighter.update(0.01, FighterInput())
        self.assertTrue(fighter.reece_biggie_ball_pending)

        scene = object.__new__(BattleScene)
        scene.projectiles = []
        scene.biggie_ball_drop_frames = [pygame.Surface((20, 20), pygame.SRCALPHA)]
        scene._spawn_reece_biggie_ball(fighter)

        self.assertEqual(len(scene.projectiles), 1)
        projectile = scene.projectiles[0]
        self.assertIsInstance(projectile, BiggieBallProjectile)
        self.assertAlmostEqual(projectile.x, fighter.x + fighter.facing * fighter.hitbox_size[0] * 1.1)
        self.assertEqual(projectile.lane_y, fighter.lane_y)
        self.assertAlmostEqual(projectile.y + projectile.frames[0].get_height() / 2, 0.0)
        self.assertLess(projectile.y, projectile.ground_y - 300)
        self.assertFalse(fighter.reece_biggie_ball_pending)

    def test_ground_impact_damages_and_knocks_down_only_nearby_same_lane_opponents(self) -> None:
        class Target:
            def __init__(self, center_x: float, lane_y: float) -> None:
                self.lane_y = lane_y
                self.is_dead = False
                self.state = "idle"
                self.health = 5
                self.center_x = center_x

            def world_hitbox_rect(self) -> pygame.Rect:
                return pygame.Rect(round(self.center_x - 16), 0, 32, 48)

            def receive_damage(self, amount: int) -> None:
                self.health -= amount

            def _start_knockdown(self) -> None:
                self.state = "fall"

        class Audio:
            def __init__(self) -> None:
                self.played = []

            def play(self, sound: str) -> None:
                self.played.append(sound)

        owner = SimpleNamespace(x=20.0)
        near = Target(120, 0)
        far = Target(235, 0)
        other_lane = Target(120, 40)
        frame = pygame.Surface((12, 12), pygame.SRCALPHA)
        scene = object.__new__(BattleScene)
        scene.fighter = owner
        scene.enemies = []
        scene.stage = SimpleNamespace(camera_x=lambda focus_x: 0.0)
        scene.projectiles = [BiggieBallProjectile(owner, 120, 0, [frame])]
        scene.biggie_ball_break_frames = {
            name: [frame] for name in ("large", "small_1", "small_2")
        }
        scene.consumable_break_effects = []
        scene.audio = Audio()
        scene.whiskey_status_effects = {}
        scene._opponents_of = lambda attacker: [near, far, other_lane]
        scene._deal_damage = lambda attacker, target, amount: target.receive_damage(amount)

        scene._update_projectiles(1.1)

        self.assertFalse(scene.projectiles)
        self.assertEqual((near.health, near.state), (3, "fall"))
        self.assertEqual((far.health, far.state), (5, "idle"))
        self.assertEqual((other_lane.health, other_lane.state), (5, "idle"))
        self.assertEqual(scene.audio.played, ["drink_break", "hit_success"])
        self.assertEqual(len(scene.consumable_break_effects), 3)
        self.assertTrue(all(isinstance(effect, IceFragmentEffect) for effect in scene.consumable_break_effects))
        self.assertEqual(
            [effect.frames for effect in scene.consumable_break_effects],
            [
                scene.biggie_ball_break_frames[name]
                for name in ("large", "small_1", "small_2")
            ],
        )


if __name__ == "__main__":
    unittest.main()
