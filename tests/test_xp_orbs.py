import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from game.constants import LANE_MAX_Y, LANE_MIN_Y
from game.data.stage_progression import StageProgression
from game.data.xp_rewards import enemy_xp_reward
from game.entities.xp_orb import XPOrb, xp_orb_surface
from game.scenes.battle_scene import BattleScene, STAGE_CORPSE_DURATION
from game.systems.keybindings import KEYBINDING_ROWS, KeyBindings
from game.systems.stage_level_up_slot import StageLevelUpSlot


class XPOrbTests(unittest.TestCase):
    def test_procedural_orb_frames_are_cached_pixel_art_with_a_bright_core(self) -> None:
        first = xp_orb_surface(0)

        self.assertIsInstance(first, pygame.Surface)
        self.assertEqual(first.get_size(), (24, 24))
        self.assertIs(first, xp_orb_surface(0))
        self.assertIsNot(first, xp_orb_surface(1))
        visible_colors = {
            first.get_at((x, y))[:3]
            for x in range(first.get_width())
            for y in range(first.get_height())
            if first.get_at((x, y)).a > 0
        }
        self.assertIn((204, 255, 238), visible_colors)
        self.assertIn((39, 199, 119), visible_colors)

    def test_enemy_rewards_scale_with_campaign_threat(self) -> None:
        self.assertEqual(enemy_xp_reward("bandit"), 10)
        self.assertGreater(enemy_xp_reward("knight"), enemy_xp_reward("bandit"))
        self.assertGreater(enemy_xp_reward("firzen"), enemy_xp_reward("knight"))
        self.assertGreater(enemy_xp_reward("unlisted_enemy"), 0)

    def test_dead_enemy_drops_once_and_corpse_cleanup_does_not_repeat_it(self) -> None:
        class Enemy:
            name = "bandit"
            x = 120.0
            lane_y = 36.0
            is_dead = True

        enemy = Enemy()
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.enemies = [enemy]
        scene.enemy_brains = {}
        scene._stage_corpse_timers = {}
        scene.stage_xp_orbs = []

        scene._register_stage_enemy_corpses()
        scene._register_stage_enemy_corpses()
        self.assertEqual(len(scene.stage_xp_orbs), 1)
        self.assertEqual(scene.stage_xp_orbs[0].xp_value, enemy_xp_reward("bandit"))
        self.assertEqual(scene._stage_corpse_timers[enemy], STAGE_CORPSE_DURATION)

        for _ in range(int(STAGE_CORPSE_DURATION)):
            scene._age_stage_enemy_corpses(1.0)
            scene._register_stage_enemy_corpses()
        self.assertEqual(len(scene.stage_xp_orbs), 1)
        self.assertNotIn(enemy, scene.enemies)

    def test_player_contact_collects_orb_and_increments_run_total_once(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_xp_total = 0
        scene.stage_xp_orbs = [XPOrb(100, 20, 15)]
        scene.fighter = SimpleNamespace(x=125, lane_y=40)

        scene._update_stage_xp_orbs(0.016)
        self.assertEqual(scene.stage_xp_total, 15)
        self.assertEqual(scene.stage_xp_orbs, [])
        scene._update_stage_xp_orbs(0.016)
        self.assertEqual(scene.stage_xp_total, 15)

    def test_test_mode_hotkey_spawns_random_orb_inside_visible_arena(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.test_mode = True
        scene.stage_mode = False
        scene.stage = SimpleNamespace(
            play_min_x=80.0,
            play_max_x=2800.0,
            camera_x=lambda focus: 300.0,
        )
        scene._camera_focus_x = lambda: 500.0
        scene.fighter = SimpleNamespace(x=500.0)
        scene.stage_xp_orbs = []
        with (
            patch("game.scenes.battle_scene.random.uniform", side_effect=[700.0, 120.0]),
            patch("game.scenes.battle_scene.random.choice", return_value=15),
        ):
            scene._spawn_test_xp_orb()

        self.assertEqual(len(scene.stage_xp_orbs), 1)
        orb = scene.stage_xp_orbs[0]
        self.assertEqual((orb.x, orb.lane_y, orb.xp_value), (700.0, 120.0, 15))
        self.assertGreaterEqual(orb.x, 348.0)
        self.assertLessEqual(orb.x, 2172.0)
        self.assertGreaterEqual(orb.lane_y, LANE_MIN_Y)
        self.assertLessEqual(orb.lane_y, LANE_MAX_Y)
        self.assertEqual(KeyBindings.DEFAULTS["test_spawn_xp_orb"], (pygame.K_F7,))
        self.assertIn(("Spawn XP Orb", "test_spawn_xp_orb", True), KEYBINDING_ROWS)

    def test_test_mode_collects_orbs_and_updates_level_progress(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = False
        scene.test_mode = True
        scene.stage_progression = StageProgression()
        scene.stage_xp_total = 0
        scene.stage_card_ranks = {}
        scene.stage_level_up_slot = StageLevelUpSlot()
        scene.stage_xp_orbs = [XPOrb(100, 20, 100)]
        scene.fighter = SimpleNamespace(x=100, lane_y=20)

        scene._update_stage_xp_orbs(0.016)

        self.assertEqual(scene.stage_xp_total, 100)
        self.assertEqual(scene._stage_progress_display(), (2, 25, 113))
        self.assertEqual(scene.stage_xp_orbs, [])
        scene._ensure_stage_level_up_slot()
        self.assertTrue(scene.stage_level_up_slot.active)
        self.assertEqual(scene.stage_level_up_slot.level_id, 2)

    def test_orb_hovers_and_bobs_over_time(self) -> None:
        orb = XPOrb(120, 40, 10)
        initial_offset = orb.bob_offset

        orb.update(0.6)

        self.assertNotEqual(orb.bob_offset, initial_offset)
        self.assertGreaterEqual(orb.bob_offset, -5.0)
        self.assertLessEqual(orb.bob_offset, 5.0)

    def test_non_stage_modes_do_not_drop_or_collect_xp(self) -> None:
        class Enemy:
            name = "bandit"
            x = 100.0
            lane_y = 0.0
            is_dead = True

        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = False
        scene.enemies = [Enemy()]
        scene._stage_corpse_timers = {}
        scene.stage_xp_orbs = [XPOrb(100, 0, 10)]
        scene.stage_xp_total = 0
        scene.fighter = SimpleNamespace(x=100, lane_y=0)

        scene._register_stage_enemy_corpses()
        scene._update_stage_xp_orbs(0.016)
        self.assertEqual(scene.stage_xp_orbs[0].xp_value, 10)
        self.assertEqual(scene.stage_xp_total, 0)
        self.assertEqual(scene._stage_corpse_timers, {})


if __name__ == "__main__":
    unittest.main()
