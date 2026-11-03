import unittest
from types import SimpleNamespace

import pygame

from game.data.characters import CHARACTERS
from game.entities.fighter import (
    BLOCK_DODGE_COOLDOWN,
    BLOCK_DODGE_DURATION,
    DEFAULT_BASIC_ATTACK_CANCELS,
    Fighter,
    FighterConfig,
    FighterInput,
)
from game.scenes.battle_scene import BattleScene


class BasicAttackTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.display.init()
        pygame.font.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    def _fighter(self) -> Fighter:
        fighter = Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (120.0, 180.0))
        fighter.attack_animation = fighter._next_basic_attack_animation()
        fighter._start_attack_state("basic_attack")
        fighter.animation_player.play(fighter.attack_animation)
        return fighter

    def _combat_scene(self, attacker: Fighter, defender: Fighter) -> BattleScene:
        scene = BattleScene.__new__(BattleScene)
        scene._damage_heavy_boxes_with_melee = lambda: None
        scene._break_freeze_columns_with_melee = lambda: None
        scene._fighters = lambda: [attacker, defender]
        scene._opponents_of = lambda fighter: [defender] if fighter is attacker else []
        scene._deal_damage = lambda source, target, amount: setattr(
            target,
            "health",
            target.health - amount,
        )
        scene.audio = SimpleNamespace(
            play=lambda *args: None,
            play_hit_miss=lambda: None,
            play_freeze_basic_miss=lambda: None,
        )
        return scene

    def test_basic_attack_phases_follow_animation_frames(self) -> None:
        fighter = self._fighter()
        timing = fighter.basic_attack_timing
        self.assertIsNotNone(timing)
        animation = fighter.animations[timing.animation_name]
        frame_count = len(animation["surfaces"])

        self.assertEqual(timing.startup_frames, 1 if frame_count > 1 else 0)
        self.assertEqual(timing.active_frames, 1)
        self.assertEqual(
            timing.recovery_frames,
            frame_count - timing.startup_frames - timing.active_frames,
        )
        self.assertAlmostEqual(
            timing.total_duration,
            max(
                fighter.combat["attack_duration"],
                animation["frame_duration"] * frame_count,
            ),
        )
        self.assertEqual(
            timing.cancel_into,
            DEFAULT_BASIC_ATTACK_CANCELS,
        )

    def test_attack_hit_window_is_after_startup_and_before_recovery(self) -> None:
        fighter = self._fighter()
        timing = fighter.basic_attack_timing
        self.assertIsNotNone(timing)

        fighter.attack_elapsed = max(0.0, timing.startup_duration - 0.001)
        self.assertFalse(fighter.basic_attack_is_active)

        fighter.attack_elapsed = timing.startup_duration
        self.assertTrue(fighter.basic_attack_is_active)
        self.assertFalse(fighter.basic_attack_is_recovering)

        fighter.attack_elapsed = timing.startup_duration + timing.active_duration
        self.assertFalse(fighter.basic_attack_is_active)
        self.assertTrue(fighter.basic_attack_is_recovering)

    def test_move_profile_can_override_timing_hitbox_and_cancels(self) -> None:
        fighter = self._fighter()
        animation_name = fighter.attack_animation
        fighter.combat["basic_attack_profiles"] = {
            animation_name: {
                "startup_frames": 0,
                "active_frames": 2,
                "recovery_frames": 1,
                "forward_reach": 88,
                "rear_reach": 4,
                "lane_tolerance": 24,
                "cancel_into": ["block"],
            }
        }

        timing = fighter._resolve_basic_attack_timing(animation_name)

        self.assertEqual(timing.startup_frames, 0)
        self.assertEqual(timing.active_frames, 2)
        self.assertEqual(timing.recovery_frames, 1)
        self.assertEqual(timing.forward_reach, 88)
        self.assertEqual(timing.rear_reach, 4)
        self.assertEqual(timing.lane_tolerance, 24)
        self.assertEqual(timing.cancel_into, frozenset({"block"}))

    def test_buffered_basic_attack_cancels_only_in_recovery(self) -> None:
        fighter = self._fighter()
        timing = fighter.basic_attack_timing
        self.assertIsNotNone(timing)

        fighter.update(0.0, FighterInput(attack_just_pressed=True))
        self.assertEqual(fighter.state, "basic_attack")
        self.assertGreater(fighter.attack_input_buffer_timer, 0.0)

        fighter.attack_elapsed = timing.startup_duration + timing.active_duration
        fighter.update(0.0, FighterInput())
        self.assertEqual(fighter.state, "basic_attack")
        self.assertEqual(fighter.attack_input_buffer_timer, 0.0)
        self.assertNotEqual(fighter.basic_attack_timing.animation_name, timing.animation_name)
        self.assertEqual(fighter.attack_elapsed, 0.0)

    def test_combat_only_resolves_basic_hits_during_the_active_window(self) -> None:
        attacker = self._fighter()
        defender = self._fighter()
        defender.x = attacker.x + 20
        scene = self._combat_scene(attacker, defender)
        timing = attacker.basic_attack_timing
        self.assertIsNotNone(timing)

        attacker.attack_elapsed = 0.0
        scene._handle_combat()
        self.assertEqual(defender.health, defender.max_health)
        self.assertTrue(attacker.attack_started)

        attacker.attack_elapsed = timing.startup_duration
        scene._handle_combat()
        self.assertLess(defender.health, defender.max_health)
        self.assertTrue(attacker.has_applied_attack_damage)

    def test_block_dodge_is_a_recovery_cancel_with_defined_timing(self) -> None:
        fighter = self._fighter()
        timing = fighter.basic_attack_timing
        self.assertIsNotNone(timing)
        fighter.attack_elapsed = timing.startup_duration + timing.active_duration

        fighter.update(
            0.0,
            FighterInput(
                right=True,
                block_pressed=True,
                block_just_pressed=True,
            ),
        )

        self.assertEqual(fighter.state, "block_dodge")
        self.assertEqual(fighter.state_timer, BLOCK_DODGE_DURATION)
        self.assertEqual(fighter.defense_cooldown, BLOCK_DODGE_COOLDOWN)
        self.assertTrue(fighter.is_invulnerable)

    def test_basic_attack_hitbox_extends_forward_not_equally_behind(self) -> None:
        fighter = self._fighter()
        timing = fighter.basic_attack_timing
        self.assertIsNotNone(timing)
        body_rect = fighter.world_hitbox_rect()

        facing_right_rect = BattleScene._melee_attack_rect(fighter)
        self.assertEqual(facing_right_rect.left, body_rect.left - timing.rear_reach)
        self.assertEqual(facing_right_rect.right, body_rect.right + timing.forward_reach)

        fighter.facing = -1
        facing_left_rect = BattleScene._melee_attack_rect(fighter)
        self.assertEqual(facing_left_rect.left, body_rect.left - timing.forward_reach)
        self.assertEqual(facing_left_rect.right, body_rect.right + timing.rear_reach)


if __name__ == "__main__":
    unittest.main()
