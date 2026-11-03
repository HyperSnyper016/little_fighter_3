import random
import unittest
from types import SimpleNamespace

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from game.data.stage_progression import StageProgression
from game.entities.fighter import FighterInput
from game.scenes.battle_scene import (
    STAGE_CARD_WINDOWS,
    STAGE_SLOT_DISPLAY_SIZE,
    STAGE_SLOT_SCALE,
    BattleScene,
    _scale_stage_slot_rect,
)
from game.systems.keybindings import KEYBINDING_ROWS, KeyBindings
from game.systems.stage_level_up_slot import (
    REEL_STOP_TIMES,
    SAMPLE_CARD_LABELS,
    StageLevelUpSlot,
)


class StageLevelUpSlotTests(unittest.TestCase):
    def test_pending_level_activates_one_roll(self) -> None:
        progression = StageProgression()
        progression.add_xp(100)
        slot = StageLevelUpSlot(random.Random(1))

        slot.start(progression.pending_levels[0])

        self.assertTrue(slot.active)
        self.assertEqual(slot.level_id, 2)
        self.assertEqual(progression.pending_levels, [2])
        self.assertEqual(len(slot.offers), 3)

    def test_reels_stop_staggered_with_three_unique_offers(self) -> None:
        slot = StageLevelUpSlot(random.Random(2))
        slot.start(2)

        slot.update(REEL_STOP_TIMES[0])
        self.assertEqual(slot.stopped, [True, False, False])
        slot.update(REEL_STOP_TIMES[1] - REEL_STOP_TIMES[0])
        self.assertEqual(slot.stopped, [True, True, False])
        slot.update(REEL_STOP_TIMES[2] - REEL_STOP_TIMES[1])

        self.assertEqual(slot.stopped, [True, True, True])
        self.assertTrue(slot.ready)
        self.assertEqual(len(set(slot.offers)), 3)
        self.assertTrue(set(slot.offers).issubset(SAMPLE_CARD_LABELS))
        self.assertEqual(slot.reel_labels, slot.offers)

    def test_selection_controls_wrap_and_confirm_only_when_ready(self) -> None:
        slot = StageLevelUpSlot(random.Random(3))
        slot.start(2)

        self.assertIsNone(slot.confirm())
        slot.move_selection(-1)
        self.assertEqual(slot.selected_index, 0)
        slot.update(2.0)
        slot.move_selection(-1)
        self.assertEqual(slot.selected_index, 2)
        slot.move_selection(1)
        self.assertEqual(slot.selected_index, 0)
        selected = slot.offers[0]

        self.assertEqual(slot.confirm(), selected)
        self.assertFalse(slot.active)
        self.assertEqual(slot.last_selection, selected)

    def test_confirm_consumes_exactly_one_level_and_starts_next_roll(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_mode_failed = False
        scene.stage_progression = StageProgression()
        scene.stage_progression.add_xp(475)
        scene.stage_level_up_slot = StageLevelUpSlot(random.Random(4))

        scene._update_stage_level_up_slot(2.0, FighterInput())
        self.assertEqual(scene.stage_level_up_slot.level_id, 2)
        scene._update_stage_level_up_slot(0.0, FighterInput(attack_just_pressed=True))

        self.assertEqual(scene.stage_progression.pending_levels, [3, 4])
        self.assertTrue(scene.stage_level_up_slot.active)
        self.assertEqual(scene.stage_level_up_slot.level_id, 3)
        self.assertEqual(scene.stage_level_up_slot.elapsed, 0.0)

        scene._update_stage_level_up_slot(2.0, FighterInput())
        scene._update_stage_level_up_slot(0.0, FighterInput(attack_just_pressed=True))
        self.assertEqual(scene.stage_progression.pending_levels, [4])
        self.assertEqual(scene.stage_level_up_slot.level_id, 4)

        scene._update_stage_level_up_slot(2.0, FighterInput())
        scene._update_stage_level_up_slot(0.0, FighterInput(attack_just_pressed=True))
        self.assertEqual(scene.stage_progression.pending_levels, [])
        self.assertFalse(scene.stage_level_up_slot.active)

    def test_slot_pauses_gameplay_but_advances_fighter_animation(self) -> None:
        progression = StageProgression()
        progression.add_xp(100)
        animation = SimpleNamespace(calls=0)
        animation.update = lambda dt, facing: setattr(animation, "calls", animation.calls + 1)
        fighter = SimpleNamespace(
            animation_player=animation,
            facing=1,
            x=120,
            state="idle",
        )
        scene = BattleScene.__new__(BattleScene)
        scene.paused = False
        scene.stage_mode = True
        scene.stage_mode_failed = False
        scene._stage_corpse_timers = {}
        scene.stage_progression = progression
        scene.stage_level_up_slot = StageLevelUpSlot(random.Random(5))
        scene.fighter = fighter
        scene.enemies = []
        scene.rudolf_clones = []
        scene.stage_card_timer = 1.0

        scene.update(0.25, FighterInput(right=True))

        self.assertTrue(scene.stage_level_up_slot.active)
        self.assertEqual(scene.stage_level_up_slot.elapsed, 0.25)
        self.assertEqual(animation.calls, 1)
        self.assertEqual(fighter.x, 120)
        self.assertEqual(fighter.state, "idle")
        self.assertEqual(scene.stage_card_timer, 1.0)

        scene.paused = True
        scene.update(0.5, FighterInput())
        self.assertEqual(scene.stage_level_up_slot.elapsed, 0.25)
        self.assertEqual(animation.calls, 1)

    def test_non_stage_scene_does_not_activate_or_draw_slot(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = False
        scene.stage_mode_failed = False
        scene.stage_progression = StageProgression()
        scene.stage_progression.add_xp(100)
        scene.stage_level_up_slot = StageLevelUpSlot(random.Random(6))
        scene._ensure_stage_level_up_slot()
        self.assertFalse(scene.stage_level_up_slot.active)
        self.assertIsNone(scene.consume_stage_level_up())
        surface = pygame.Surface((32, 32))
        surface.fill((1, 2, 3))
        scene._draw_stage_level_up_slot(surface)
        self.assertEqual(surface.get_at((16, 16))[:3], (1, 2, 3))

    def test_draws_cabinet_frame_and_keeps_reel_selection_live(self) -> None:
        pygame.font.init()
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.test_mode = False
        scene.stage_mode_failed = False
        scene.paused = False
        scene.stage_level_up_slot = StageLevelUpSlot(random.Random(9))
        scene.stage_level_up_slot.start(2)
        scene.stage_level_up_slot.update(2.0)
        scene.stage_title_font = pygame.font.Font(None, 76)
        scene.stage_subtitle_font = pygame.font.Font(None, 26)
        scene.small_font = pygame.font.Font(None, 24)
        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surface.fill((1, 2, 3))

        scene._draw_stage_level_up_slot(surface)

        frame = scene._get_stage_level_up_slot_frame()
        self.assertIs(frame, scene._get_stage_level_up_slot_frame())
        self.assertEqual(frame.get_size(), STAGE_SLOT_DISPLAY_SIZE)
        self.assertGreater(frame.get_width(), SCREEN_WIDTH * 0.85)
        self.assertGreater(frame.get_height(), SCREEN_HEIGHT * 0.85)
        panel = pygame.Rect((0, 0), STAGE_SLOT_DISPLAY_SIZE)
        panel.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        frame_sample = (
            round(180 * STAGE_SLOT_SCALE),
            round(160 * STAGE_SLOT_SCALE),
        )
        self.assertEqual(
            surface.get_at((panel.x + frame_sample[0], panel.y + frame_sample[1])),
            frame.get_at(frame_sample),
        )
        self.assertGreater(
            _scale_stage_slot_rect(STAGE_CARD_WINDOWS[1]).width,
            STAGE_CARD_WINDOWS[1].width,
        )
        self.assertEqual(scene.stage_level_up_slot.selected_index, 0)
        scene._update_stage_level_up_slot(0.0, FighterInput(right_just_pressed=True))
        self.assertEqual(scene.stage_level_up_slot.selected_index, 1)

    def test_test_mode_hotkey_runs_one_visual_only_offer_sequence(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = False
        scene.test_mode = True
        scene.stage_level_up_slot = StageLevelUpSlot(random.Random(7))
        scene.stage_progression = StageProgression()
        animation = SimpleNamespace(calls=0)
        animation.update = lambda dt, facing: setattr(animation, "calls", animation.calls + 1)
        scene.fighter = SimpleNamespace(
            health=8,
            max_health=10,
            mana=3,
            animation_player=animation,
            facing=1,
        )
        scene.paused = False
        scene.enemies = []
        scene.rudolf_clones = []
        scene.stage_mode_failed = False
        original_stats = vars(scene.fighter).copy()
        original_stats.pop("animation_player")

        scene.update(0.1, FighterInput(test_level_up_just_pressed=True))
        self.assertTrue(scene.stage_level_up_slot.active)
        self.assertEqual(scene.stage_level_up_slot.level_id, 1)
        self.assertEqual(scene.stage_level_up_slot.offer_ranks, [1, 1, 1])
        self.assertEqual(scene.stage_progression.xp_total, 0)
        self.assertEqual(scene.stage_progression.pending_levels, [])

        scene.update(2.0, FighterInput(right_just_pressed=True))
        self.assertTrue(scene.stage_level_up_slot.ready)
        self.assertEqual(scene.stage_level_up_slot.selected_index, 1)
        scene.update(
            0.0,
            FighterInput(test_level_up_just_pressed=True, attack_just_pressed=True),
        )

        self.assertFalse(scene.stage_level_up_slot.active)
        self.assertEqual(scene.stage_level_up_slot.last_selection, scene.stage_level_up_slot.offers[1])
        self.assertEqual(scene.stage_progression.xp_total, 0)
        self.assertEqual(scene.stage_progression.pending_levels, [])
        self.assertFalse(hasattr(scene, "stage_card_ranks"))
        self.assertEqual(
            {
                key: value
                for key, value in vars(scene.fighter).items()
                if key != "animation_player"
            },
            original_stats,
        )

    def test_test_level_up_binding_is_configurable_and_mode_gated(self) -> None:
        self.assertEqual(KeyBindings.DEFAULTS["test_level_up"], (pygame.K_F8,))
        self.assertIn(("Test Level-Up Slot", "test_level_up", True), KEYBINDING_ROWS)

        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = False
        scene.test_mode = False
        scene.stage_level_up_slot = StageLevelUpSlot(random.Random(8))
        self.assertFalse(
            scene._update_test_level_up_slot(
                0.1, FighterInput(test_level_up_just_pressed=True)
            )
        )
        self.assertFalse(scene.stage_level_up_slot.active)

        scene.stage_mode = True
        scene.test_mode = True
        self.assertFalse(
            scene._update_test_level_up_slot(
                0.1, FighterInput(test_level_up_just_pressed=True)
            )
        )
        self.assertFalse(scene.stage_level_up_slot.active)


if __name__ == "__main__":
    unittest.main()
