import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from game.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from game.data.stage_progression import StageProgression
from game.entities.fighter import FighterInput
from game.entities.xp_orb import XPOrb
from game.scenes.battle_scene import (
    STAGE_CARD_SIZE,
    STAGE_SLOT_SCALE,
    STAGE_CARD_WINDOWS,
    BattleScene,
    _load_stage_card_glow_layer,
    _load_stage_card_image,
    _scale_stage_slot_rect,
    _stage_card_glow_alpha,
)
from game.systems.stage_cards import (
    CARDS_BY_KEY,
    STAGE_CARD_CATALOG,
    card_offer_weight,
    card_rank_title,
    eligible_cards,
    roman_rank,
    stage_card_effects,
)
from game.systems.stage_level_up_slot import StageLevelUpSlot


class StageCardCatalogTests(unittest.TestCase):
    def test_catalog_effects_and_roman_ranks(self) -> None:
        self.assertEqual(len(STAGE_CARD_CATALOG), 9)
        self.assertEqual(roman_rank(1), "I")
        self.assertEqual(roman_rank(2), "II")
        self.assertEqual(roman_rank(3), "III")
        self.assertEqual(roman_rank(4), "IV")
        self.assertEqual(roman_rank(5), "V")
        self.assertEqual(roman_rank(50), "L")
        self.assertEqual(card_rank_title("Vitality", 1), "Vitality Lvl I")
        self.assertEqual(card_rank_title("Vitality", 2), "Vitality Lvl II")
        with self.assertRaises(ValueError):
            roman_rank(0)

        effects = stage_card_effects(
            {"heavy_hands": 2, "iron_skin": 1, "quick_step": 3, "vitality": 2}
        )
        self.assertAlmostEqual(effects["damage_multiplier"], 1.12)
        self.assertAlmostEqual(effects["damage_reduction"], 0.05)
        self.assertAlmostEqual(effects["movement_multiplier"], 1.15)
        self.assertEqual(effects["max_health_bonus"], 2)

    def test_curse_effects_scale_with_ranks_and_remain_bounded(self) -> None:
        effects = stage_card_effects(
            {
                "bandit_horde": 5,
                "hardened_gang": 2,
                "julians_skull": 2,
            }
        )

        self.assertEqual(effects["active_enemy_bonus"], 3)
        self.assertEqual(effects["enemy_health_bonus"], 2)
        self.assertEqual(effects["julian_skull_interval"], 21.0)
        self.assertEqual(
            stage_card_effects({"julians_skull": 10})["julian_skull_interval"],
            12.0,
        )

    def test_curse_art_glow_layer_pulses_softly(self) -> None:
        glow = _load_stage_card_glow_layer("bandit_horde", *STAGE_CARD_SIZE)
        self.assertGreater(glow.get_bounding_rect().width, 0)
        with patch("game.scenes.battle_scene.pygame.time.get_ticks", return_value=650):
            pulse_peak = _stage_card_glow_alpha()
        with patch("game.scenes.battle_scene.pygame.time.get_ticks", return_value=1_950):
            pulse_low = _stage_card_glow_alpha()
        self.assertGreater(pulse_peak, pulse_low)

    def test_cards_remain_eligible_without_a_rank_cap(self) -> None:
        self.assertEqual(
            eligible_cards(),
            STAGE_CARD_CATALOG,
        )
        self.assertEqual(card_rank_title("Vitality", 51), "Vitality Lvl LI")

    def test_offer_ranks_advance_without_a_rank_cap(self) -> None:
        ranks = {"vitality": 1}
        slot = StageLevelUpSlot(random.Random(24))

        with patch(
            "game.systems.stage_level_up_slot.eligible_cards",
            return_value=(CARDS_BY_KEY["vitality"],),
        ):
            self.assertTrue(slot.start(4, ranks))
            self.assertEqual(slot.offers, ["Vitality"])
            self.assertEqual(slot.offer_ranks, [2])

            ranks["vitality"] = 50
            self.assertTrue(slot.start(5, ranks))
            self.assertEqual(slot.offers, ["Vitality"])
            self.assertEqual(slot.offer_ranks, [51])

    def test_card_offer_weight_drops_by_five_percent_per_rank_without_reaching_zero(self) -> None:
        self.assertEqual(card_offer_weight(0), 1.0)
        self.assertAlmostEqual(card_offer_weight(1), 0.95)
        self.assertAlmostEqual(card_offer_weight(5), 0.95**5)
        self.assertGreater(card_offer_weight(100_000), 0.0)
        self.assertGreater(card_offer_weight(5), card_offer_weight(6))

    def test_slot_uses_weighted_unique_offers(self) -> None:
        class CaptureRng:
            def __init__(self) -> None:
                self.weights: list[list[float]] = []

            def choices(self, population, weights, k):
                self.weights.append(list(weights))
                return [population[0]]

            @staticmethod
            def choice(population):
                return population[0]

            @staticmethod
            def shuffle(values) -> None:
                return None

        rng = CaptureRng()
        slot = StageLevelUpSlot(rng)

        self.assertTrue(slot.start(2, {"heavy_hands": 5}))
        self.assertEqual(len(slot.offers), 3)
        self.assertEqual(len(set(slot.offers)), 3)
        self.assertEqual(slot.offers[0], "Heavy Hands")
        self.assertAlmostEqual(rng.weights[0][0], 0.95**5)
        self.assertTrue(all(weight == 1.0 for weight in rng.weights[0][1:]))

    def test_selected_rank_applies_before_the_next_queued_offer(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_mode_failed = False
        scene.stage_progression = StageProgression()
        scene.stage_progression.pending_levels = [2, 3]
        scene.stage_card_ranks = {"vitality": 1}
        scene.stage_level_up_slot = StageLevelUpSlot(random.Random(25))
        with patch(
            "game.systems.stage_level_up_slot.eligible_cards",
            return_value=(CARDS_BY_KEY["vitality"],),
        ):
            scene.stage_level_up_slot.start(2, scene.stage_card_ranks)
            scene.stage_level_up_slot.update(2.0)
            scene._update_stage_level_up_slot(
                0.0, FighterInput(attack_just_pressed=True)
            )

        self.assertEqual(scene.stage_card_ranks["vitality"], 2)
        self.assertEqual(scene.stage_progression.pending_levels, [3])
        self.assertEqual(scene.stage_level_up_slot.level_id, 3)
        self.assertEqual(scene.stage_level_up_slot.offer_ranks, [3])

    def test_test_mode_xp_opens_ranked_offers_and_repeated_picks_upgrade_cards(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = False
        scene.test_mode = True
        scene.stage_mode_failed = False
        scene.stage_progression = StageProgression()
        scene.stage_progression.add_xp(100)
        scene.stage_xp_total = 100
        scene.stage_card_ranks = {"vitality": 1}
        scene.stage_level_up_slot = StageLevelUpSlot(random.Random(26))
        scene._stage_base_movement = None
        scene.fighter = SimpleNamespace(
            movement={"walk_speed": 200.0, "run_speed": 300.0, "lane_speed": 100.0},
            stats={"max_health": 10},
            max_health=10,
            health=10,
        )

        with patch(
            "game.systems.stage_level_up_slot.eligible_cards",
            return_value=(CARDS_BY_KEY["vitality"],),
        ):
            scene._ensure_stage_level_up_slot()
            self.assertTrue(scene.stage_level_up_slot.active)
            self.assertEqual(scene.stage_level_up_slot.offer_ranks, [2])
            scene._update_stage_level_up_slot(2.0, FighterInput())
            scene._update_stage_level_up_slot(
                0.0, FighterInput(attack_just_pressed=True)
            )
            self.assertEqual(scene.stage_card_ranks["vitality"], 2)

            scene._award_stage_xp(150)
            scene._ensure_stage_level_up_slot()
            self.assertTrue(scene.stage_level_up_slot.active)
            self.assertEqual(scene.stage_level_up_slot.level_id, 3)
            self.assertEqual(scene.stage_level_up_slot.offer_ranks, [3])
            scene._update_stage_level_up_slot(2.0, FighterInput())
            scene._update_stage_level_up_slot(
                0.0, FighterInput(attack_just_pressed=True)
            )
        self.assertEqual(scene.stage_card_ranks["vitality"], 3)

    def test_all_supplied_card_art_loads_at_valid_render_size(self) -> None:
        self.assertGreater(STAGE_CARD_SIZE[0], 300)
        self.assertAlmostEqual(STAGE_CARD_SIZE[0] / 208, STAGE_SLOT_SCALE, places=2)
        for card in STAGE_CARD_CATALOG:
            with self.subTest(card=card.key):
                self.assertEqual(
                    _load_stage_card_image(card.key).get_size(),
                    STAGE_CARD_SIZE,
                )

    def test_stage_effects_apply_to_player_stats_and_gameplay_only(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_card_ranks = {}
        scene._stage_base_movement = None
        scene._stage_damage_remainder = 0.0
        scene._stage_damage_reduction_remainder = 0.0
        scene._stage_xp_remainder = 0.0
        scene.stage_progression = None
        scene.stage_xp_total = 0
        scene.fighter = SimpleNamespace(
            movement={"walk_speed": 200.0, "run_speed": 300.0, "lane_speed": 100.0},
            stats={"max_health": 10},
            max_health=10,
            health=10,
        )

        self.assertTrue(scene._apply_stage_card("Quickstep"))
        self.assertEqual(scene.fighter.movement["run_speed"], 315.0)
        self.assertTrue(scene._apply_stage_card("Vitality"))
        self.assertEqual(scene.fighter.max_health, 11)
        self.assertEqual(scene.fighter.health, 10)
        self.assertTrue(scene._apply_stage_card("Fast Learner"))
        scene._award_stage_xp(100)
        self.assertEqual(scene.stage_progression.xp_total, 108)

        scene._reset_stage_progression()
        self.assertEqual(scene.stage_card_ranks, {})
        self.assertEqual(scene.fighter.max_health, 10)
        self.assertEqual(scene.fighter.movement["run_speed"], 300.0)

    def test_hardened_gang_increases_health_of_living_enemies(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.test_mode = False
        scene.stage_card_ranks = {}
        scene._stage_base_movement = None
        scene.fighter = SimpleNamespace(
            movement={"walk_speed": 200.0, "run_speed": 300.0, "lane_speed": 100.0},
            stats={"max_health": 10},
            max_health=10,
            health=10,
        )
        enemy = SimpleNamespace(is_dead=False, max_health=4, health=2)
        defeated_enemy = SimpleNamespace(is_dead=True, max_health=4, health=0)
        scene.stage_wave_enemies = [enemy, defeated_enemy]

        self.assertTrue(scene._apply_stage_card("Hardened Gang"))

        self.assertEqual((enemy.max_health, enemy.health), (5, 3))
        self.assertEqual((defeated_enemy.max_health, defeated_enemy.health), (4, 0))

    def test_horde_and_hardened_ranks_affect_stage_enemy_spawns(self) -> None:
        class SpawnedFighter:
            def __init__(self, _config, _position, x_bounds) -> None:
                self.max_health = 10
                self.health = 10
                self.is_dead = False
                self.x_bounds = x_bounds

        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_card_ranks = {"bandit_horde": 1, "hardened_gang": 2}
        scene.stage_wave_enemies = []
        scene._stage_enemy_spawn_queue = ["bandit"] * 7
        scene.fighter = SimpleNamespace(x=100.0)
        scene.stage = SimpleNamespace(play_min_x=0.0, play_max_x=1000.0)
        scene.difficulty = SimpleNamespace(scale_enemy_health=lambda health: health)
        scene.enemies = []
        scene.enemy_brains = {}
        scene._stage_wave_spawn_positions = lambda slots, _bounds, _focus: (
            [(float(index), 0.0) for index in range(slots)],
            1,
        )

        with (
            patch("game.scenes.battle_scene.Fighter", SpawnedFighter),
            patch("game.scenes.battle_scene.BanditBrain", return_value=object()),
        ):
            scene._dispatch_stage_enemy_spawns()

        self.assertEqual(len(scene.stage_wave_enemies), 5)
        self.assertEqual(len(scene._stage_enemy_spawn_queue), 2)
        self.assertTrue(
            all(enemy.max_health == 7 for enemy in scene.stage_wave_enemies)
        )

    def test_julians_skull_spawns_telegraphed_lane_projectile(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_card_ranks = {"julians_skull": 1}
        scene.fighter = SimpleNamespace(is_dead=False, x=500.0, lane_y=24.0)
        enemy = SimpleNamespace(is_dead=False)
        scene.stage_wave_enemies = [enemy]
        scene.stage = SimpleNamespace(camera_x=lambda _focus_x: 0.0)
        scene.projectiles = []
        scene._stage_julian_skull_timer = 0.0
        skull = SimpleNamespace(lane_y=0.0)

        with patch(
            "game.scenes.battle_scene.JulianSkullProjectile",
            return_value=skull,
        ) as create_skull:
            scene._update_stage_curse_attacks(0.0)

        self.assertEqual(len(scene.projectiles), 1)
        self.assertIs(scene.projectiles[0], skull)
        self.assertIs(create_skull.call_args.args[0], enemy)
        self.assertIs(create_skull.call_args.args[1], scene.fighter)
        self.assertEqual(skull.lane_y, 24.0)
        self.assertEqual(scene._stage_julian_skull_timer, 24.0)

    def test_stage_card_modifiers_are_reapplied_after_player_transforms(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.test_mode = False
        scene.stage_card_ranks = {}
        scene._stage_base_movement = None
        scene.fighter = SimpleNamespace(
            luis_transform_pending=True,
            movement={"walk_speed": 200.0, "run_speed": 300.0, "lane_speed": 100.0},
            stats={"max_health": 10},
            max_health=10,
            health=10,
        )

        def transform_to(_config) -> None:
            scene.fighter.luis_transform_pending = False
            scene.fighter.movement = {
                "walk_speed": 180.0,
                "run_speed": 270.0,
                "lane_speed": 90.0,
            }
            scene.fighter.stats = {"max_health": 20}
            scene.fighter.max_health = 20

        scene.fighter.transform_to = transform_to
        self.assertTrue(scene._apply_stage_card("Quickstep"))
        self.assertTrue(scene._apply_stage_card("Vitality"))
        self.assertEqual(scene.fighter.movement["run_speed"], 315.0)
        self.assertEqual(scene.fighter.max_health, 11)

        scene._transform_luis_if_pending(scene.fighter)

        self.assertEqual(scene.fighter.movement["run_speed"], 283.5)
        self.assertEqual(scene.fighter.movement["walk_speed"], 189.0)
        self.assertEqual(scene.fighter.movement["lane_speed"], 94.5)
        self.assertEqual(scene.fighter.max_health, 21)
        self.assertEqual(scene._stage_base_movement["run_speed"], 270.0)

    def test_xp_magnet_expands_orb_pickup_range_in_stage_mode(self) -> None:
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_card_ranks = {"xp_magnet": 1}
        scene.stage_xp_total = 0
        scene.stage_xp_orbs = [XPOrb(35, 32, 1)]
        scene.fighter = SimpleNamespace(x=0, lane_y=0)

        scene._update_stage_xp_orbs(0.016)

        self.assertEqual(scene.stage_xp_total, 1)
        self.assertEqual(scene.stage_xp_orbs, [])

    def test_damage_bonus_and_reduction_accumulate_fractional_effects(self) -> None:
        class DamageTarget:
            def __init__(self) -> None:
                self.received = []

            def receive_damage(self, amount, **kwargs) -> None:
                self.received.append(amount)

        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.stage_card_ranks = {"heavy_hands": 1, "iron_skin": 1}
        scene._stage_damage_remainder = 0.0
        scene._stage_damage_reduction_remainder = 0.0
        scene.whiskey_status_effects = {}

        player = DamageTarget()
        scene.fighter = player
        target = DamageTarget()
        npc = DamageTarget()

        for _ in range(17):
            scene._deal_damage(player, target, 1)
        self.assertEqual(sum(target.received), 18)

        for _ in range(20):
            scene._deal_damage(npc, player, 1)
        self.assertEqual(sum(player.received), 19)

        scene.stage_mode = False
        scene.test_mode = True
        scene._stage_damage_remainder = 0.0
        scene._stage_damage_reduction_remainder = 0.0
        test_player = DamageTarget()
        test_target = DamageTarget()
        scene.fighter = test_player
        for _ in range(17):
            scene._deal_damage(test_player, test_target, 1)
        self.assertEqual(sum(test_target.received), 18)

        test_npc = DamageTarget()
        for _ in range(20):
            scene._deal_damage(test_npc, test_player, 1)
        self.assertEqual(sum(test_player.received), 19)

    def test_visual_test_slot_reveals_only_after_staggered_reel_stops(self) -> None:
        slot = StageLevelUpSlot(random.Random(21))
        self.assertTrue(slot.start(1, visual_only=True))
        self.assertTrue(all(rank == 1 for rank in slot.offer_ranks))
        self.assertNotEqual(
            slot.reveal_orders[0][0],
            sorted(slot.reveal_orders[0][0]),
        )
        self.assertEqual(slot.revealed_text(0, 0), "")
        slot.update(1.35)
        self.assertTrue(slot.stopped[0])
        self.assertFalse(slot.stopped[1])
        self.assertEqual(slot.revealed_text(0, 0), "")

        slot.update(0.05)
        first_reveal = slot.revealed_text(0, 0)
        self.assertEqual(first_reveal, slot.revealed_text(0, 0))
        self.assertGreater(sum(character != " " for character in first_reveal), 0)
        slot.update(0.2)
        later_reveal = slot.revealed_text(0, 0)
        self.assertGreaterEqual(
            sum(character != " " for character in later_reveal),
            sum(character != " " for character in first_reveal),
        )

    def test_reels_ease_to_zero_speed_and_art_is_clipped_to_windows(self) -> None:
        slot = StageLevelUpSlot(random.Random(22))
        slot.start(2)
        slot.update(0.2)
        fast_speed = slot.reel_scroll_speeds[0]
        slot.update(0.7)
        slow_speed = slot.reel_scroll_speeds[0]
        self.assertLess(slow_speed, fast_speed)
        slot.update(1.1)
        self.assertEqual(slot.reel_scroll_speeds, [0.0, 0.0, 0.0])
        self.assertEqual(slot.reel_scroll_offsets, [0.0, 0.0, 0.0])
        self.assertEqual(slot.reel_scroll_positions, [10.0, 10.0, 10.0])
        self.assertEqual(
            [sequence[10] for sequence in slot.reel_card_sequences],
            slot.offers,
        )

        pygame.font.init()
        scene = BattleScene.__new__(BattleScene)
        scene.stage_mode = True
        scene.test_mode = False
        scene.stage_mode_failed = False
        scene.paused = False
        scene.stage_level_up_slot = slot
        scene.stage_title_font = pygame.font.Font(None, 76)
        scene.stage_subtitle_font = pygame.font.Font(None, 26)
        scene.small_font = pygame.font.Font(None, 24)
        surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        scene._draw_stage_level_up_slot(surface)
        frame = scene._get_stage_level_up_slot_frame()
        panel = frame.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        right_window = _scale_stage_slot_rect(STAGE_CARD_WINDOWS[2]).move(
            panel.topleft
        )
        baseline = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        baseline.fill((1, 2, 3))
        shade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        shade.fill((4, 8, 16, 205))
        baseline.blit(shade, (0, 0))
        baseline.blit(frame, panel.topleft)
        self.assertEqual(
            surface.get_at((right_window.right + 1, right_window.centery)),
            baseline.get_at((right_window.right + 1, right_window.centery)),
        )

        spinning_slot = StageLevelUpSlot(random.Random(23))
        spinning_slot.start(2)
        spinning_slot.update(0.2)
        scene.stage_level_up_slot = spinning_slot
        surface.fill((1, 2, 3))
        scene._draw_stage_level_up_slot(surface)
        self.assertEqual(
            surface.get_at((right_window.right + 1, right_window.centery)),
            baseline.get_at((right_window.right + 1, right_window.centery)),
        )


if __name__ == "__main__":
    unittest.main()
