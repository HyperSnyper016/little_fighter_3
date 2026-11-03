import unittest
from pathlib import Path
from types import SimpleNamespace

import pygame

from game.data.characters import CHARACTERS
from game.entities.fighter import Fighter, FighterConfig, FighterInput
from game.scenes.battle_scene import (
    BattleScene,
    IceFragmentEffect,
    ThrownItem,
    WhiskeyFireTrailEffect,
    _load_item_sprite_animations,
)
from game.systems.assets import load_character_animations


class WhiskeyFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.display.init()
        if not pygame.display.get_init() or pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def test_whiskey_assets_register_all_standard_and_break_animations(self) -> None:
        sprite_root = Path(__file__).resolve().parents[1] / "assets" / "sprites"
        animations = _load_item_sprite_animations(sprite_root / "item_sprites")[
            "consumables/whiskey"
        ]
        for animation in ("spawn", "holding", "drink", "throw", "land"):
            with self.subTest(animation=animation):
                self.assertTrue(animations[animation])
        for animation in (
            "broken/dust",
            "broken/large",
            "broken/small_1",
            "broken/small_2",
        ):
            with self.subTest(animation=animation):
                self.assertTrue(animations[animation])
        self.assertTrue((sprite_root / "particals" / "drunk_bubbles").is_dir())
        self.assertTrue((sprite_root / "particals" / "sleep").is_dir())

    def test_reece_jump_attack_frames_are_loadable(self) -> None:
        animation = load_character_animations(
            CHARACTERS["reece"],
            animation_names={"jump_attack"},
        )["jump_attack"]
        self.assertTrue(animation["surfaces"])
        self.assertFalse(animation["loop"])

    def test_whiskey_damage_boost_expires_and_starts_normal_knockdown(self) -> None:
        class Drinker:
            state = "idle"
            is_dead = False
            knock_hold_timer = 1.0

            def _start_knockdown(self) -> None:
                self.state = "fall"

        class Target:
            def __init__(self) -> None:
                self.received = []

            def receive_damage(self, amount: int, ignore_invulnerability: bool = False) -> None:
                self.received.append((amount, ignore_invulnerability))

        scene = object.__new__(BattleScene)
        drinker = Drinker()
        target = Target()
        frame = pygame.Surface((4, 4), pygame.SRCALPHA)
        scene.whiskey_status_effects = {
            drinker: {
                "remaining": 3.0,
                "sleeping": False,
                "just_started": False,
                "bubbles": SimpleNamespace(
                    frames=[frame, frame, frame],
                    frame_index=0,
                    frame_timer=0.0,
                    update=lambda dt: None,
                    current_frame=frame,
                ),
                "sleep": SimpleNamespace(update=lambda dt: None),
            }
        }

        scene._deal_damage(drinker, target, 2)
        self.assertEqual(target.received, [(4, False)])
        scene._update_whiskey_effects(2.99)
        self.assertEqual(drinker.state, "idle")
        self.assertEqual(drinker.knock_hold_timer, 1.0)
        scene._update_whiskey_effects(0.01)
        self.assertEqual(drinker.state, "fall")
        self.assertEqual(drinker.knock_hold_timer, 2.0)
        self.assertTrue(scene.whiskey_status_effects[drinker]["sleeping"])
        self.assertEqual(scene.whiskey_status_effects[drinker]["bubbles"].frame_index, 2)

    def test_whiskey_sleep_cycles_hold_fighter_down_before_get_up(self) -> None:
        frame = pygame.Surface((8, 8), pygame.SRCALPHA)
        scene = object.__new__(BattleScene)
        scene.drunk_bubbles_frames = [frame]
        scene.sleep_frames = [frame] * 6
        scene.whiskey_status_effects = {}
        drinker = Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (120, 40))
        scene._start_whiskey_effect(drinker)
        scene._update_whiskey_effects(0.0)
        scene._update_whiskey_effects(3.0)
        self.assertEqual(drinker.knock_hold_timer, 2.0)
        self.assertEqual(drinker.state, "fall")
        self.assertTrue(drinker.whiskey_sleep_hold)
        effect = scene.whiskey_status_effects[drinker]
        self.assertTrue(effect["sleep"].loop)

        for _ in range(25):
            drinker.update(0.08, FighterInput())
            scene._update_whiskey_effects(0.08)
            self.assertEqual(drinker.state, "fall")
            self.assertIn(drinker, scene.whiskey_status_effects)
        self.assertEqual(effect["sleep"].frame_index, 1)
        self.assertFalse(drinker.whiskey_sleep_hold)

        drinker.update(0.016, FighterInput())
        self.assertEqual(drinker.state, "get_up")
        scene._update_whiskey_effects(0.016)
        self.assertNotIn(drinker, scene.whiskey_status_effects)

    def test_whiskey_overlay_is_anchored_to_upper_sprite_and_camera(self) -> None:
        overlay = pygame.Surface((10, 12), pygame.SRCALPHA)
        sprite = pygame.Surface((40, 100), pygame.SRCALPHA)
        fighter = type("Fighter", (), {})()
        fighter.x = 120
        fighter.draw_pos = lambda camera_x: (80, 40)
        fighter.animation_player = SimpleNamespace(current_frame=sprite)
        scene = object.__new__(BattleScene)
        scene.whiskey_status_effects = {
            fighter: {
                "sleeping": False,
                "bubbles": SimpleNamespace(current_frame=overlay),
            }
        }
        blits = []
        surface = SimpleNamespace(blit=lambda image, rect: blits.append((image, rect)))

        scene._draw_whiskey_status(surface, fighter, camera_x=30)

        self.assertEqual(len(blits), 1)
        self.assertEqual(blits[0][0], overlay)
        self.assertEqual(blits[0][1].center, (90, 68))

    def test_whiskey_break_launches_both_fragments_and_spawns_fire_on_landing_break(self) -> None:
        class Audio:
            def play(self, sound: str) -> None:
                pass

        frame = pygame.Surface((8, 8), pygame.SRCALPHA)
        scene = object.__new__(BattleScene)
        scene.fighter = SimpleNamespace(name="reece")
        scene.audio = Audio()
        scene.consumable_items = []
        scene.consumable_break_effects = []
        scene.projectiles = []
        scene.whiskey_break_frames = {
            name: [frame]
            for name in ("dust", "large", "small_1", "small_2")
        }
        item = SimpleNamespace(
            item_id="consumables/whiskey",
            x=120.0,
            lane_y=40.0,
        )
        scene.consumable_items.append(item)

        self.assertTrue(scene._break_whiskey_item(item, spawn_fire=True))
        self.assertFalse(scene.consumable_items)
        self.assertEqual(len(scene.consumable_break_effects), 3)
        self.assertTrue(all(isinstance(effect, IceFragmentEffect) for effect in scene.consumable_break_effects[1:]))
        self.assertIsInstance(scene.projectiles[0], WhiskeyFireTrailEffect)
        self.assertTrue(scene.projectiles[0].hits_all_fighters)

    def test_thrown_whiskey_breaks_and_fire_knocks_down_its_target(self) -> None:
        class Audio:
            def play(self, sound: str) -> None:
                pass

        class Target:
            lane_y = 40.0
            is_dead = False

            def __init__(self) -> None:
                self.health = 5
                self.state = "idle"

            def world_hitbox_rect(self) -> pygame.Rect:
                return pygame.Rect(96, 96, 32, 32)

            def receive_damage(self, amount: int, ignore_invulnerability: bool = False) -> None:
                self.health -= amount

            def _start_fire_knockdown(self) -> None:
                self.state = "knocked_fire"

        frame = pygame.Surface((8, 8), pygame.SRCALPHA)
        owner = object()
        item = object.__new__(ThrownItem)
        item.item_id = "consumables/whiskey"
        item.owner = owner
        item.lane_y = 40.0
        item.x = 104.0
        item.phase = "thrown"
        item.world_rect = lambda: pygame.Rect(96, 96, 16, 16)
        target = Target()
        scene = object.__new__(BattleScene)
        scene.audio = Audio()
        scene.consumable_items = [item]
        scene.consumable_break_effects = []
        scene.projectiles = []
        scene.whiskey_status_effects = {}
        scene.whiskey_break_frames = {
            name: [frame]
            for name in ("dust", "large", "small_1", "small_2")
        }
        scene._heavy_box_obstacles = lambda: []
        scene._opponents_of = lambda attacker: [target]
        scene._resolve_thrown_item_hits()

        self.assertFalse(scene.consumable_items)
        self.assertEqual(target.health, 4)
        self.assertEqual(target.state, "knocked_fire")
        self.assertFalse(scene.projectiles)


if __name__ == "__main__":
    unittest.main()
