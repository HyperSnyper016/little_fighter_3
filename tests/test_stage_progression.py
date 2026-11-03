import unittest
from types import SimpleNamespace

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from game.data.stage_progression import StageProgression
from game.entities.xp_orb import XPOrb
from game.scenes.battle_scene import BattleScene


class StageProgressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.font.init()

    def test_thresholds_are_seventy_five_percent_of_original_curve(self) -> None:
        self.assertEqual(
            [StageProgression.threshold_for_level(level) for level in range(1, 6)],
            [0, 75, 188, 338, 525],
        )
        progression = StageProgression()
        self.assertEqual(progression.xp_for_next_level, 75)
        progression.add_xp(75)
        self.assertEqual(progression.xp_for_next_level, 113)

    def test_overflow_can_award_multiple_levels_and_queues_each_one(self) -> None:
        progression = StageProgression()

        earned = progression.add_xp(475)

        self.assertEqual(earned, [2, 3, 4])
        self.assertEqual(progression.level, 4)
        self.assertEqual(progression.xp_into_level, 137)
        self.assertEqual(progression.xp_for_next_level, 187)
        self.assertEqual(progression.level_up_events, [2, 3, 4])
        self.assertEqual(progression.pending_levels, [2, 3, 4])
        self.assertEqual(progression.consume_pending_level(), 2)
        self.assertEqual(progression.pending_levels, [3, 4])
        self.assertEqual(progression.level_up_events, [2, 3, 4])

    def test_one_collected_orb_can_cross_multiple_thresholds(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_progression = StageProgression()
        scene.stage_xp_total = 0
        scene.stage_xp_orbs = [XPOrb(100, 20, 475)]
        scene.fighter = SimpleNamespace(x=125, lane_y=40)

        scene._update_stage_xp_orbs(0.016)

        self.assertEqual(scene.stage_xp_total, 475)
        self.assertEqual(scene._stage_progress_display(), (4, 137, 187))
        self.assertEqual(scene.stage_progression.pending_levels, [2, 3, 4])
        self.assertEqual(scene.consume_stage_level_up(), 2)
        self.assertEqual(scene.stage_progression.pending_levels, [3, 4])

    def test_progression_hud_displays_stage_state_only(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_progression = StageProgression()
        scene.stage_progression.add_xp(40)
        scene.small_font = pygame.font.Font(None, 24)
        surface = pygame.Surface((640, 360))

        scene._draw_stage_progression_hud(surface)

        self.assertNotEqual(surface.get_at((30, 90))[:3], (0, 0, 0))
        self.assertEqual(scene._stage_progress_display(), (1, 40, 75))

        scene.stage_mode = False
        untouched = pygame.Surface((640, 360))
        scene._draw_stage_progression_hud(untouched)
        self.assertEqual(untouched.get_at((30, 90))[:3], (0, 0, 0))

        scene.test_mode = True
        scene._draw_stage_progression_hud(untouched)
        self.assertNotEqual(untouched.get_at((30, 90))[:3], (0, 0, 0))

    def test_stage_run_hud_shows_wave_and_live_grace_countdown(self) -> None:
        pygame.font.init()
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.test_mode = False
        scene.stage_index = 2
        scene.stage_wave_index = 1
        scene.campaign_score = 700
        scene.stage_wave_clear_timer = 2.75
        scene.stage_progression = StageProgression()
        scene.stage_progression.add_xp(40)
        scene.small_font = pygame.font.Font(None, 24)
        scene.stage_banner_subtitle_font = pygame.font.Font(None, 24)
        scene.fighter = SimpleNamespace(
            health=8,
            max_health=10,
            mana=3,
            max_mana=5,
            definition={"display_name": "Test Fighter"},
        )
        scene.enemies = []
        scene._endless_encounter = lambda stage: SimpleNamespace(
            title="Ranged Trouble",
            waves=(object(), object()),
        )
        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surface.fill((0, 0, 0))

        self.assertEqual(
            scene._stage_run_hud_labels(),
            (
                "STAGE 3  |  WAVE 2/2  |  SCORE 700",
                "Ranged Trouble",
                "WAVE CLEARED  -  NEXT WAVE IN 2.8s",
            ),
        )
        scene._draw_hud(surface)
        scene._draw_stage_progression_hud(surface)

        self.assertNotEqual(surface.get_at((30, 90))[:3], (0, 0, 0))
        countdown_rect = scene.small_font.render(
            "WAVE CLEARED  -  NEXT WAVE IN 2.8s", True, (255, 214, 139)
        ).get_rect(midtop=(SCREEN_WIDTH // 2, 68))
        self.assertTrue(
            any(
                surface.get_at((x, y))[:3] != (0, 0, 0)
                for x in range(countdown_rect.left, countdown_rect.right)
                for y in range(countdown_rect.top, countdown_rect.bottom)
            )
        )
        scene.stage_wave_clear_timer = None
        self.assertIsNone(scene._stage_run_hud_labels()[2])

    def test_run_reset_clears_xp_level_events_and_pending_levels(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_progression = StageProgression()
        scene.stage_progression.add_xp(475)
        scene.stage_xp_total = 475

        scene._reset_stage_progression()

        self.assertEqual(scene.stage_xp_total, 0)
        self.assertEqual(scene._stage_progress_display(), (1, 0, 75))
        self.assertEqual(scene.stage_progression.level_up_events, [])
        self.assertEqual(scene.stage_progression.pending_levels, [])


if __name__ == "__main__":
    unittest.main()
