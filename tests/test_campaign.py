import unittest
from types import SimpleNamespace

from game.data.campaign import CAMPAIGN_ENCOUNTERS, RECOVERY_STAGES
from game.data.characters import CHARACTERS
from game.entities.fighter import FighterInput
from game.scenes.battle_scene import BattleScene, STAGE_CARD_DURATION


class CampaignDataTests(unittest.TestCase):
    def test_campaign_has_ten_named_stages_across_three_acts(self) -> None:
        self.assertEqual(len(CAMPAIGN_ENCOUNTERS), 10)
        self.assertEqual(
            {encounter.act for encounter in CAMPAIGN_ENCOUNTERS},
            {
                "ACT I - CITY UNDER PRESSURE",
                "ACT II - FIGHTERS IN THE SHADOWS",
                "ACT III - THE FINAL CONSPIRACY",
            },
        )
        self.assertTrue(all(encounter.title and encounter.description for encounter in CAMPAIGN_ENCOUNTERS))

    def test_waves_reference_valid_characters_and_positive_counts(self) -> None:
        for encounter in CAMPAIGN_ENCOUNTERS:
            self.assertTrue(encounter.waves)
            for wave in encounter.waves:
                self.assertTrue(wave.banner)
                self.assertTrue(wave.enemies)
                for character, count in wave.enemies:
                    self.assertIn(character, CHARACTERS)
                    self.assertGreater(count, 0)

    def test_campaign_has_three_supply_breaks_and_multi_wave_climaxes(self) -> None:
        self.assertEqual(RECOVERY_STAGES, frozenset({3, 6, 9}))
        self.assertEqual(
            [index + 1 for index, encounter in enumerate(CAMPAIGN_ENCOUNTERS) if len(encounter.waves) > 1],
            [3, 4, 6, 7, 8, 9, 10],
        )
        for encounter in CAMPAIGN_ENCOUNTERS:
            for wave in encounter.waves:
                self.assertLessEqual(sum(count for _, count in wave.enemies), 2)


class CampaignFlowTests(unittest.TestCase):
    @staticmethod
    def _battle_scene() -> BattleScene:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_mode_complete = False
        scene.stage_mode_failed = False
        scene.paused = False
        scene.stage_intermission = False
        scene.stage_intermission_choice = 0
        scene.stage_index = 2
        scene.stage_wave_index = 0
        scene.stage_card_mode = "stage"
        scene.stage_card_timer = 0.0
        scene.campaign_score = 0
        scene.victory_played = True
        scene.enemies = [object(), object(), object()]
        scene.fighter = SimpleNamespace(
            x=250.0,
            health=50,
            max_health=100,
            mana=95,
            max_mana=100,
        )
        scene.stage = SimpleNamespace(play_min_x=80.0, play_max_x=2800.0)
        scene._spawn_encounter = lambda bounds, start_x: None
        scene.enemies = [object()]
        return scene

    def test_wave_clear_spawns_reinforcements_then_opens_supply_break(self) -> None:
        scene = self._battle_scene()

        scene._advance_stage_mode()
        self.assertEqual(scene.campaign_score, 100)
        self.assertEqual(scene.stage_wave_index, 1)
        self.assertEqual(scene.stage_card_mode, "wave")
        self.assertEqual(scene.stage_card_timer, STAGE_CARD_DURATION)
        self.assertFalse(scene.stage_intermission)

        scene._advance_stage_mode()
        self.assertEqual(scene.campaign_score, 200)
        self.assertEqual(scene.stage_wave_index, 2)
        self.assertFalse(scene.stage_intermission)

        scene._advance_stage_mode()
        self.assertEqual(scene.campaign_score, 300)
        self.assertTrue(scene.stage_intermission)
        self.assertEqual(scene.stage_intermission_choice, 0)
        self.assertEqual(scene.stage_index, 2)

    def test_supply_break_choice_restores_a_capped_resource_and_advances(self) -> None:
        scene = self._battle_scene()
        scene.stage_intermission = True
        scene.stage_intermission_choice = 1

        scene._confirm_recovery_choice()

        self.assertEqual(scene.fighter.mana, 100)
        self.assertEqual(scene.fighter.health, 50)
        self.assertFalse(scene.stage_intermission)
        self.assertEqual(scene.stage_index, 3)
        self.assertEqual(scene.stage_wave_index, 0)
        self.assertEqual(scene.stage_card_mode, "stage")

    def test_intermission_controls_change_choice_and_confirm(self) -> None:
        scene = self._battle_scene()
        scene.stage_intermission = True

        scene.update(0.016, FighterInput(right_just_pressed=True))
        self.assertEqual(scene.stage_intermission_choice, 1)
        self.assertEqual(scene.stage_index, 2)

        scene.update(0.016, FighterInput(attack_just_pressed=True))
        self.assertEqual(scene.stage_index, 3)
        self.assertFalse(scene.stage_intermission)


if __name__ == "__main__":
    unittest.main()
