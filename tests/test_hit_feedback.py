import unittest

import pygame

from game.data.characters import CHARACTERS
from game.entities.fighter import Fighter, FighterConfig
from game.scenes.battle_scene import (
    HIT_STOP_ON_BLOCK,
    HIT_STOP_ON_HIT,
    IMPACT_FEEDBACK_DURATION,
    BattleScene,
)


class HitFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.display.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    @staticmethod
    def _fighter() -> Fighter:
        return Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (120.0, 40.0))

    @staticmethod
    def _scene() -> BattleScene:
        scene = BattleScene.__new__(BattleScene)
        scene.hit_stop_timer = 0.0
        scene.impact_feedback_effects = []
        scene.whiskey_status_effects = {}
        return scene

    def test_successful_damage_registers_a_hit_feedback_effect(self) -> None:
        scene = self._scene()
        attacker = self._fighter()
        target = self._fighter()
        previous_health = target.health

        scene._deal_damage(attacker, target, 3)

        self.assertEqual(target.health, previous_health - 3)
        self.assertEqual(scene.hit_stop_timer, HIT_STOP_ON_HIT)
        self.assertEqual(len(scene.impact_feedback_effects), 1)
        self.assertFalse(scene.impact_feedback_effects[0].blocked)

    def test_prevented_damage_does_not_register_hit_feedback(self) -> None:
        scene = self._scene()
        target = self._fighter()
        target.state = "fall"

        scene._deal_damage(self._fighter(), target, 3)

        self.assertEqual(scene.hit_stop_timer, 0.0)
        self.assertEqual(scene.impact_feedback_effects, [])

    def test_block_feedback_uses_distinct_effect_and_shorter_hit_stop(self) -> None:
        scene = self._scene()
        target = self._fighter()

        scene._register_impact_feedback(target, blocked=True)

        self.assertEqual(scene.hit_stop_timer, HIT_STOP_ON_BLOCK)
        self.assertTrue(scene.impact_feedback_effects[0].blocked)

    def test_combat_block_registers_block_feedback(self) -> None:
        scene = self._scene()
        attacker = self._fighter()
        attacker.attack_animation = attacker._next_basic_attack_animation()
        attacker._start_attack_state("basic_attack")
        attacker.animation_player.play(attacker.attack_animation)
        attacker.attack_started = True
        timing = attacker.basic_attack_timing
        self.assertIsNotNone(timing)
        attacker.attack_elapsed = timing.startup_duration
        defender = self._fighter()
        defender.x = attacker.x + 20
        defender.state = "block"
        defender.block_strength = 1

        class Audio:
            def play(self, sound: str) -> None:
                pass

        scene.audio = Audio()
        scene._damage_heavy_boxes_with_melee = lambda: None
        scene._break_freeze_columns_with_melee = lambda: None
        scene._fighters = lambda: [attacker, defender]
        scene._opponents_of = lambda fighter: [defender] if fighter is attacker else []

        scene._handle_combat()

        self.assertEqual(defender.block_strength, 0)
        self.assertEqual(scene.hit_stop_timer, HIT_STOP_ON_BLOCK)
        self.assertEqual(len(scene.impact_feedback_effects), 1)
        self.assertTrue(scene.impact_feedback_effects[0].blocked)

    def test_hit_stop_only_removes_elapsed_pause_time(self) -> None:
        scene = self._scene()
        scene.hit_stop_timer = HIT_STOP_ON_HIT

        self.assertEqual(scene._consume_hit_stop(0.02), 0.0)
        self.assertAlmostEqual(scene.hit_stop_timer, HIT_STOP_ON_HIT - 0.02)
        self.assertAlmostEqual(
            scene._consume_hit_stop(0.04),
            0.04 - (HIT_STOP_ON_HIT - 0.02),
        )
        self.assertEqual(scene.hit_stop_timer, 0.0)

    def test_impact_feedback_expires_quickly(self) -> None:
        scene = self._scene()
        effect = scene.impact_feedback_effects
        scene._register_impact_feedback(self._fighter())

        self.assertFalse(effect[0].update(IMPACT_FEEDBACK_DURATION / 2))
        self.assertTrue(effect[0].update(IMPACT_FEEDBACK_DURATION / 2))


if __name__ == "__main__":
    unittest.main()
