import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from game.data.campaign import (
    ENDLESS_MILESTONE_INTERVAL,
    ENDLESS_REINFORCEMENT_INTERVAL,
    ENDLESS_STAGE_MILESTONES,
    get_endless_encounter,
)
from game.data.characters import CHARACTERS
from game.data.stage_progression import StageProgression
from game.constants import LANE_MAX_Y, LANE_MIN_Y, SCREEN_WIDTH
from game.entities.fighter import FighterInput
from game.scenes.battle_scene import (
    BattleScene,
    STAGE_CARD_DURATION,
    STAGE_CORPSE_DURATION,
    STAGE_ENEMY_SPAWN_MARGIN,
    STAGE_MAX_ACTIVE_ENEMIES,
    STAGE_TITLE_BANNER_HEIGHT,
    STAGE_TITLE_BANNER_TOP,
    STAGE_WAVE_GRACE_DURATION,
)


class EndlessStageDataTests(unittest.TestCase):
    def test_first_stage_is_one_bandit(self) -> None:
        encounter = get_endless_encounter(1)

        self.assertEqual(len(encounter.waves), 1)
        self.assertEqual(encounter.waves[0].enemies, (("bandit", 1),))

    def test_milestones_add_enemies_and_unlock_roster_types(self) -> None:
        stage_one = get_endless_encounter(1)
        stage_three = get_endless_encounter(3)
        stage_five = get_endless_encounter(5)

        self.assertEqual(sum(count for _, count in stage_one.waves[0].enemies), 1)
        self.assertGreater(
            sum(count for _, count in stage_three.waves[0].enemies),
            sum(count for _, count in stage_one.waves[0].enemies),
        )
        self.assertIn("hunter", {name for name, _ in stage_three.waves[0].enemies})
        self.assertIn("jack", {name for name, _ in stage_five.waves[0].enemies})
        self.assertIn("knight", {name for name, _ in stage_five.waves[0].enemies})

    def test_schedule_is_valid_deterministic_and_continues_past_ten(self) -> None:
        for stage_number in (1, 2, 3, 4, 5, 10, 11, 23, 40):
            with self.subTest(stage_number=stage_number):
                encounter = get_endless_encounter(stage_number)
                self.assertEqual(encounter, get_endless_encounter(stage_number))
                self.assertTrue(encounter.waves)
                for wave in encounter.waves:
                    self.assertTrue(wave.enemies)
                    self.assertTrue(wave.banner)
                    for character, count in wave.enemies:
                        self.assertIn(character, CHARACTERS)
                        self.assertGreater(count, 0)

        previous_composition = None
        for stage_number in range(1, 41):
            composition = tuple(
                character
                for wave in get_endless_encounter(stage_number).waves
                for character, count in wave.enemies
                for _ in range(count)
            )
            self.assertNotEqual(composition, previous_composition)
            previous_composition = composition

        self.assertIn(
            "firen",
            {name for wave in get_endless_encounter(19).waves for name, _ in wave.enemies},
        )
        self.assertGreater(
            sum(count for wave in get_endless_encounter(11).waves for _, count in wave.enemies),
            sum(count for wave in get_endless_encounter(10).waves for _, count in wave.enemies),
        )
        self.assertGreater(
            sum(count for wave in get_endless_encounter(40).waves for _, count in wave.enemies),
            sum(count for wave in get_endless_encounter(23).waves for _, count in wave.enemies),
        )

    def test_threat_budget_roster_mix_milestones_and_difficulty(self) -> None:
        encounters = [get_endless_encounter(stage) for stage in (1, 2, 5, 10, 20)]
        budgets = [encounter.threat_budget for encounter in encounters]
        self.assertTrue(all(later > earlier for earlier, later in zip(budgets, budgets[1:])))
        self.assertEqual(encounters[0].waves[0].enemies, (("bandit", 1),))
        for encounter in encounters:
            self.assertAlmostEqual(
                sum(wave.threat_budget for wave in encounter.waves),
                encounter.threat_budget,
            )

        stage_three_names = {
            name
            for wave in get_endless_encounter(3).waves
            for name, _ in wave.enemies
        }
        self.assertIn("bandit", stage_three_names)
        self.assertIn("hunter", stage_three_names)
        self.assertTrue(get_endless_encounter(5).is_milestone)
        self.assertTrue(get_endless_encounter(ENDLESS_MILESTONE_INTERVAL * 2).is_milestone)
        self.assertIn("knight", {name for name, _ in get_endless_encounter(5).waves[0].enemies})
        self.assertIn("firen", {name for wave in get_endless_encounter(19).waves for name, _ in wave.enemies})

        easy = get_endless_encounter(10, "Easy")
        medium = get_endless_encounter(10, "Medium")
        hard = get_endless_encounter(10, "Hard")
        self.assertLess(easy.threat_budget, medium.threat_budget)
        self.assertLess(medium.threat_budget, hard.threat_budget)
        self.assertLessEqual(
            sum(count for wave in easy.waves for _, count in wave.enemies),
            sum(count for wave in hard.waves for _, count in wave.enemies),
        )

    def test_milestone_rosters_and_reinforcement_schedule_are_maintainable(self) -> None:
        self.assertEqual(ENDLESS_STAGE_MILESTONES[0].first_stage, 1)
        self.assertEqual(
            tuple(milestone.first_stage for milestone in ENDLESS_STAGE_MILESTONES),
            tuple(sorted(milestone.first_stage for milestone in ENDLESS_STAGE_MILESTONES)),
        )
        for milestone in ENDLESS_STAGE_MILESTONES:
            self.assertTrue(milestone.title and milestone.description)
            self.assertTrue(milestone.roster)
            self.assertGreater(milestone.enemy_count, 0)
            self.assertGreater(milestone.growth_interval, 0)
            for character in milestone.roster:
                self.assertIn(character, CHARACTERS)
        self.assertIn("ashley", ENDLESS_STAGE_MILESTONES[-1].roster)

        self.assertEqual(len(get_endless_encounter(ENDLESS_REINFORCEMENT_INTERVAL).waves), 2)
        with self.assertRaises(ValueError):
            get_endless_encounter(0)

    def test_large_squads_split_into_two_waves_without_changing_threat(self) -> None:
        for stage_number in (6, 7, 10, 23):
            with self.subTest(stage_number=stage_number):
                encounter = get_endless_encounter(stage_number)
                wave_counts = tuple(
                    sum(count for _, count in wave.enemies)
                    for wave in encounter.waves
                )

                self.assertEqual(len(wave_counts), 2)
                self.assertGreaterEqual(sum(wave_counts), 5)
                self.assertAlmostEqual(
                    sum(wave.threat_budget for wave in encounter.waves),
                    encounter.threat_budget,
                )


class EndlessStageFlowTests(unittest.TestCase):
    @staticmethod
    def _battle_scene(stage_index: int = 3) -> BattleScene:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_mode_failed = False
        scene.paused = False
        scene.stage_index = stage_index
        scene.stage_wave_index = 0
        scene.stage_wave_clear_timer = None
        scene.stage_wave_enemies = [object()]
        scene._stage_corpse_timers = {}
        scene.stage_card_mode = "stage"
        scene.stage_card_timer = 0.0
        scene.campaign_score = 0
        scene.victory_played = True
        scene.enemies = [object()]
        scene.fighter = SimpleNamespace(
            x=250.0,
            health=50,
            max_health=100,
            mana=95,
            max_mana=100,
        )
        scene.stage = SimpleNamespace(play_min_x=80.0, play_max_x=2800.0)
        scene._spawn_encounter = lambda bounds, start_x: None
        return scene

    def test_wave_clear_spawns_reinforcements_then_advances(self) -> None:
        scene = self._battle_scene()

        scene._advance_stage_mode()
        self.assertEqual(scene.campaign_score, 100)
        self.assertEqual(scene.stage_wave_index, 1)
        self.assertEqual(scene.stage_card_mode, "wave")
        self.assertEqual(scene.stage_card_timer, STAGE_CARD_DURATION)
        scene._advance_stage_mode()
        self.assertEqual(scene.campaign_score, 200)
        self.assertEqual(scene.stage_index, 4)
        self.assertEqual(scene.stage_wave_index, 0)

    def test_third_stage_clear_advances_without_recovery(self) -> None:
        scene = self._battle_scene(stage_index=2)
        scene.fighter.health = 25
        scene.fighter.mana = 40

        scene._advance_stage_mode()

        self.assertEqual(scene.fighter.mana, 40)
        self.assertEqual(scene.fighter.health, 25)
        self.assertEqual(scene.stage_index, 3)
        self.assertEqual(scene.stage_wave_index, 0)
        self.assertEqual(scene.stage_card_mode, "stage")

    def test_stage_mode_continues_after_former_tenth_encounter(self) -> None:
        scene = self._battle_scene(stage_index=9)

        scene._advance_stage_mode()
        self.assertEqual(scene.stage_index, 9)
        self.assertEqual(scene.stage_wave_index, 1)

        scene._advance_stage_mode()
        self.assertEqual(scene.stage_index, 10)
        self.assertEqual(get_endless_encounter(scene.stage_index + 1).title, "Arcane Front")

    def test_every_fifth_stage_awards_xp_scaled_to_the_stage_cleared(self) -> None:
        scene = self._battle_scene(stage_index=4)
        scene.stage_progression = StageProgression()
        scene.stage_xp_total = 0
        scene.stage_card_ranks = {}
        scene._stage_xp_remainder = 0.0

        scene._start_next_campaign_stage()
        self.assertEqual(scene.stage_index, 5)
        self.assertEqual(scene.stage_xp_total, 50)
        self.assertEqual(scene.stage_milestone_reward_xp, 50)
        self.assertEqual(scene.stage_milestone_reward_stage, 5)

        scene.stage_index = 9
        scene._start_next_campaign_stage()
        self.assertEqual(scene.stage_index, 10)
        self.assertEqual(scene.stage_xp_total, 150)
        self.assertEqual(scene.stage_milestone_reward_xp, 100)
        self.assertEqual(scene.stage_progression.pending_levels, [2])

    def test_wave_spawns_outside_camera_view_facing_into_the_arena(self) -> None:
        focus_x = 1_200.0
        scene = BattleScene.__new__(BattleScene)
        scene.stage = SimpleNamespace(camera_x=lambda focus: focus)
        scene.fighter = SimpleNamespace(x=focus_x + SCREEN_WIDTH / 2)

        positions, facing = scene._stage_wave_spawn_positions(
            4,
            (80.0, 5_680.0),
            focus_x,
        )

        self.assertEqual(facing, -1)
        self.assertEqual(len(positions), 4)
        for x, lane_y in positions:
            self.assertGreaterEqual(x, focus_x + SCREEN_WIDTH + STAGE_ENEMY_SPAWN_MARGIN)
            self.assertLessEqual(x, 5_680.0)
            self.assertGreaterEqual(lane_y, LANE_MIN_Y)
            self.assertLessEqual(lane_y, LANE_MAX_Y)

    def test_stage_encounter_uses_camera_relative_spawn_positions(self) -> None:
        class SpawnedEnemy:
            def __init__(self, config, start_pos, x_bounds):
                self.name = config.name
                self.x, self.lane_y = start_pos
                self.facing = 1
                self.max_health = 100
                self.health = 100
                self.controls_enabled = False

        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.test_mode = False
        scene.stage_index = 0
        scene.stage_wave_index = 0
        scene.camera_focus_x = 2_160.0
        scene.stage = SimpleNamespace(camera_x=lambda focus: 1_200.0)
        scene.fighter = SimpleNamespace(x=2_160.0)
        scene.enemies = []
        scene.enemy_brains = {}
        scene.stage_wave_enemies = []
        scene.difficulty = SimpleNamespace(scale_enemy_health=lambda health: health)

        with patch("game.scenes.battle_scene.Fighter", SpawnedEnemy), patch(
            "game.scenes.battle_scene.BanditBrain",
            return_value=object(),
        ):
            scene._spawn_encounter((80.0, 5_680.0), scene.fighter.x)

        enemy = scene.stage_wave_enemies[0]
        self.assertGreater(
            enemy.x,
            1_200.0 + SCREEN_WIDTH + STAGE_ENEMY_SPAWN_MARGIN - 1.0,
        )
        self.assertLess(enemy.x, scene.fighter.x + SCREEN_WIDTH)
        self.assertEqual(enemy.facing, -1)
        self.assertGreaterEqual(enemy.lane_y, LANE_MIN_Y)
        self.assertLessEqual(enemy.lane_y, LANE_MAX_Y)
        self.assertEqual(enemy.max_health, 50)
        self.assertEqual(enemy.health, 50)

    def test_stage_enemy_cap_queues_and_dispatches_remaining_spawns(self) -> None:
        class SpawnedEnemy:
            def __init__(self, config, start_pos, x_bounds):
                self.name = config.name
                self.x, self.lane_y = start_pos
                self.facing = 1
                self.max_health = 100
                self.health = 100
                self.controls_enabled = False
                self.is_dead = False

        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage = SimpleNamespace(
            play_min_x=80.0,
            play_max_x=5_680.0,
            camera_x=lambda focus: 1_200.0,
        )
        scene.fighter = SimpleNamespace(x=2_160.0)
        scene.camera_focus_x = 2_160.0
        scene.difficulty = SimpleNamespace(
            scale_enemy_health=lambda health: health,
        )
        scene.stage_wave_enemies = []
        scene._stage_enemy_spawn_queue = ["bandit"] * 6
        scene.enemies = []
        scene.enemy_brains = {}

        with patch("game.scenes.battle_scene.Fighter", SpawnedEnemy), patch(
            "game.scenes.battle_scene.BanditBrain",
            return_value=object(),
        ):
            scene._dispatch_stage_enemy_spawns()
            self.assertEqual(len(scene.stage_wave_enemies), STAGE_MAX_ACTIVE_ENEMIES)
            self.assertEqual(len(scene._stage_enemy_spawn_queue), 2)
            for enemy in scene.stage_wave_enemies:
                self.assertGreater(
                    enemy.x,
                    1_200.0 + SCREEN_WIDTH + STAGE_ENEMY_SPAWN_MARGIN - 1.0,
                )
                self.assertEqual(enemy.max_health, 50)
                self.assertEqual(enemy.health, 50)

            scene.stage_wave_enemies[0].is_dead = True
            scene.stage_wave_enemies[1].is_dead = True
            scene._dispatch_stage_enemy_spawns()

        self.assertEqual(len(scene._stage_enemy_spawn_queue), 0)
        self.assertEqual(len(scene.stage_wave_enemies), 6)
        self.assertEqual(
            sum(not enemy.is_dead for enemy in scene.stage_wave_enemies),
            STAGE_MAX_ACTIVE_ENEMIES,
        )

    @staticmethod
    def _running_wave_scene() -> BattleScene:
        class Player:
            item_throw_animation = None
            held_item = None
            state = "idle"
            x = 250.0
            snapshot = SimpleNamespace()
            is_dead = False

            def update(self, dt, inputs, **kwargs):
                self.x += 100.0 * dt if inputs.right else 0.0

        class Enemy:
            state = "dead"
            is_dead = True
            x = 500.0

            def update(self, *args, **kwargs):
                return None

        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_mode_failed = False
        scene.paused = False
        scene.stage_index = 0
        scene.stage_wave_index = 0
        scene.stage_wave_clear_timer = None
        scene.stage_wave_enemies = [Enemy()]
        scene.enemies = list(scene.stage_wave_enemies)
        scene.enemy_brains = {}
        scene._stage_corpse_timers = {}
        scene.stage_card_timer = STAGE_CARD_DURATION
        scene.stage_card_mode = "stage"
        scene.fighter = Player()
        scene.campaign_score = 0
        scene.victory_played = True
        scene.consumable_spawn_timer = 60.0
        scene.spawnable_items = []
        scene.consumable_items = []
        scene.consumable_break_effects = []
        scene.rudolf_clone_smoke_effects = []
        scene.rudolf_clones = []
        scene.projectiles = []
        scene.active_item_overlays = {}
        scene.held_item_animations = {}
        scene.whiskey_status_effects = {}
        scene._handle_held_item_throw_input = lambda *args: False
        scene._fighters = lambda: []
        scene._item_to_drink = lambda *args: None
        scene._try_pick_up_consumable = lambda *args: False
        scene._spawn_rudolf_clones = lambda *args: None
        scene._update_camera_focus = lambda *args: None
        scene._update_projectiles = lambda *args: None
        scene._remove_finished_rudolf_clones = lambda *args: None
        scene._handle_woody_punches = lambda *args: None
        scene._handle_woody_dash_hits = lambda *args: None
        scene._handle_combat = lambda *args: None
        scene._handle_audio = lambda *args: None
        scene._resolve_thrown_item_hits = lambda *args: None
        scene._update_whiskey_effects = lambda *args: None
        scene._advance_stage_mode = lambda: setattr(scene, "advanced", True)
        scene.advanced = False
        return scene

    def test_wave_grace_timer_keeps_player_movable_and_advances_after_four_seconds(self) -> None:
        scene = self._running_wave_scene()

        scene.update(0.1, FighterInput(right=True))
        self.assertEqual(scene.fighter.x, 260.0)
        self.assertEqual(scene.stage_card_timer, STAGE_CARD_DURATION - 0.1)
        self.assertEqual(scene.stage_wave_clear_timer, STAGE_WAVE_GRACE_DURATION)
        self.assertFalse(scene.advanced)

        scene.update(3.9, FighterInput(right=True))
        self.assertEqual(scene.fighter.x, 650.0)
        self.assertAlmostEqual(scene.stage_wave_clear_timer, 0.1)
        self.assertFalse(scene.advanced)

        scene.update(0.1, FighterInput(right=True))
        self.assertTrue(scene.advanced)
        self.assertIn(scene.stage_wave_enemies[0], scene.enemies)

    def test_stage_corpses_persist_for_fifteen_seconds_then_are_removed(self) -> None:
        scene = self._running_wave_scene()
        corpse = scene.stage_wave_enemies[0]
        scene._register_stage_enemy_corpses()

        scene._age_stage_enemy_corpses(STAGE_CORPSE_DURATION - 0.1)
        self.assertIn(corpse, scene.enemies)
        self.assertAlmostEqual(scene._stage_corpse_timers[corpse], 0.1)
        self.assertTrue(all(enemy.is_dead for enemy in scene.stage_wave_enemies))
        self.assertEqual(scene.stage_wave_clear_timer, None)

        scene._age_stage_enemy_corpses(0.1)
        self.assertNotIn(corpse, scene.enemies)
        self.assertNotIn(corpse, scene._stage_corpse_timers)

    def test_stage_title_card_is_a_compact_top_banner_not_a_playfield_overlay(self) -> None:
        pygame.font.init()
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_card_timer = STAGE_CARD_DURATION
        scene.stage_mode_failed = False
        scene.stage_card_mode = "stage"
        scene.stage_index = 0
        scene.stage_wave_index = 0
        scene.difficulty = SimpleNamespace(name="Medium")
        scene.stage_act_font = pygame.font.Font(None, 28)
        scene.stage_banner_heading_font = pygame.font.Font(None, 38)
        scene.stage_banner_subtitle_font = pygame.font.Font(None, 24)

        surface = pygame.Surface((SCREEN_WIDTH, 1080))
        surface.fill((70, 80, 90))
        scene._draw_stage_mode_card(surface)

        self.assertGreaterEqual(STAGE_TITLE_BANNER_TOP, 80)
        self.assertLess(STAGE_TITLE_BANNER_TOP + STAGE_TITLE_BANNER_HEIGHT, 360)
        self.assertNotEqual(surface.get_at((SCREEN_WIDTH // 2, STAGE_TITLE_BANNER_TOP + 10))[:3], (70, 80, 90))
        self.assertEqual(surface.get_at((SCREEN_WIDTH // 2, 600))[:3], (70, 80, 90))

        scene.stage_card_mode = "wave"
        scene.stage_index = 3
        scene.stage_wave_index = 1
        surface.fill((70, 80, 90))
        scene._draw_stage_mode_card(surface)
        self.assertNotEqual(surface.get_at((SCREEN_WIDTH // 2, STAGE_TITLE_BANNER_TOP + 10))[:3], (70, 80, 90))
        self.assertEqual(surface.get_at((SCREEN_WIDTH // 2, 600))[:3], (70, 80, 90))


if __name__ == "__main__":
    unittest.main()
