import unittest
from unittest.mock import patch
from types import SimpleNamespace

import pygame
from game.scenes.character_select_scene import (
    BACK_BUTTON,
    DISTANT_SKYLINE_PATH,
    FAST_PARTICLES_PATH,
    FAR_SKY_PATH,
    FAST_PARTICLE_DRIFT_SPEED,
    GROUND_SCROLL_WORLD_SCALE,
    GROUND_TILE_PATH,
    PARTICLES_PATH,
    SLOW_PARTICLE_DRIFT_SPEED,
    SELECTION_GROUND_Y,
    ROSTER_CARD_GAP,
    ROSTER_CATEGORY_GAP,
    ROSTER_GRID_COLUMNS,
    ROSTER_PANEL,
    SELECTION_GLOW_PERIOD,
    INFO_PANEL,
    CharacterSelectScene,
)


class CharacterSelectRosterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scene = CharacterSelectScene.__new__(CharacterSelectScene)
        categories = (
            ["Grunts"] * 3
            + ["Veterans"] * 6
            + ["Elementals"] * 6
            + ["Rangers"] * 2
            + ["Brawlers"] * 5
            + ["Heavyweights"] * 2
            + ["Ace's"] * 2
            + ["Bosses", "Training / Placeholder"]
        )
        self.scene.characters = [
            {"key": f"fighter_{index}", "category": category}
            for index, category in enumerate(categories)
        ]
        self.scene.selected_index = 0
        self.scene.selected_character = "fighter_0"
        self.scene.preview_player = None
        self.scene.preview_character_key = "bandit"
        self.scene.preview_forward_displacement = 0.0
        self.scene.opponent_selection = False
        self.scene.selected_opponents = set()
        self.scene.selection_confirmed = False
        self.scene.back_requested = False
        self.scene._elapsed_time = 0.0
        self.scene._up_pressed = False
        self.scene._down_pressed = False
        self.scene._left_pressed = False
        self.scene._right_pressed = False
        self.scene._tab_pressed = False
        self.scene._back_pressed = False
        self.scene._confirm_pressed = False
        self.scene._toggle_pressed = False
        self.scene.moveset_expanded = False
        self.scene.moveset_focused = False
        self.scene.moveset_hovered = False
        self.scene.moveset_toggle_rect = pygame.Rect(
            INFO_PANEL.x + 24,
            INFO_PANEL.y + 256,
            INFO_PANEL.width - 48,
            44,
        )
        self.scene.far_sky_tile = pygame.Surface((100, 8), pygame.SRCALPHA)
        self.scene.skyline_tile = pygame.Surface((100, 8), pygame.SRCALPHA)
        self.scene.slow_particle_tile = pygame.Surface((100, 8), pygame.SRCALPHA)
        self.scene.fast_particle_tile = pygame.Surface((100, 8), pygame.SRCALPHA)
        self.scene.ground_tile = pygame.Surface((100, 8))
        self.scene.far_sky_scroll_offset = 0.0
        self.scene.skyline_scroll_offset = 0.0
        self.scene.slow_particle_scroll_offset = 0.0
        self.scene.fast_particle_scroll_offset = 0.0
        self.scene.ground_scroll_offset = 0.0
        self.scene.ground_scroll_speed = 0.0
        self.scene._update_preview = lambda dt: None

    def test_roster_tiles_form_two_rows_inside_the_panel(self) -> None:
        first = self.scene._roster_card_rect(0)
        next_row = self.scene._roster_card_rect(ROSTER_GRID_COLUMNS)
        last = self.scene._roster_card_rect(len(self.scene.characters) - 1)

        self.assertEqual(next_row.y, first.bottom + ROSTER_CARD_GAP)
        self.assertTrue(ROSTER_PANEL.contains(first))
        self.assertTrue(ROSTER_PANEL.contains(last))

    def test_category_changes_have_extra_spacing_between_tiles(self) -> None:
        before_group = self.scene._roster_card_rect(2)
        next_group = self.scene._roster_card_rect(3)

        self.assertEqual(
            next_group.left - before_group.right,
            ROSTER_CARD_GAP + ROSTER_CATEGORY_GAP,
        )

    def test_navigation_crosses_category_boundaries(self) -> None:
        self.scene.selected_index = 2

        self.scene._move_selection(1, 0)

        self.assertEqual(self.scene.selected_index, 3)
        self.assertEqual(self.scene.selected_character, "fighter_3")

    def test_horizontal_navigation_wraps_within_each_row(self) -> None:
        self.scene.selected_index = ROSTER_GRID_COLUMNS - 1

        self.scene._move_selection(1, 0)

        self.assertEqual(self.scene.selected_index, 0)

    def test_vertical_navigation_keeps_the_column_on_the_short_last_row(self) -> None:
        self.scene.selected_index = 27

        self.scene._move_selection(0, -1)

        self.assertEqual(self.scene.selected_index, 13)

    def test_selected_roster_glow_pulses_between_bright_and_dim(self) -> None:
        self.scene._elapsed_time = SELECTION_GLOW_PERIOD / 4
        bright = self.scene._selection_glow_strength()
        self.scene._elapsed_time = SELECTION_GLOW_PERIOD * 3 / 4
        dim = self.scene._selection_glow_strength()

        self.assertAlmostEqual(bright, 1.0)
        self.assertAlmostEqual(dim, 0.0)

    def test_mouse_click_expands_and_collapses_moveset(self) -> None:
        keys = [False] * 512
        with (
            patch("game.scenes.character_select_scene.pygame.key.get_pressed", return_value=keys),
            patch("game.scenes.character_select_scene.KEY_BINDINGS.is_pressed", return_value=False),
        ):
            self.scene.update(0, mouse_click=INFO_PANEL.center)
            self.assertTrue(self.scene.moveset_expanded)
            self.assertTrue(self.scene.moveset_focused)

            self.scene.update(0, mouse_click=INFO_PANEL.center)
            self.assertFalse(self.scene.moveset_expanded)

    def test_tab_focus_and_menu_confirm_toggle_moveset(self) -> None:
        keys = [False] * 512
        keys[pygame.K_TAB] = True
        with (
            patch("game.scenes.character_select_scene.pygame.key.get_pressed", return_value=keys),
            patch("game.scenes.character_select_scene.KEY_BINDINGS.is_pressed", return_value=False),
        ):
            self.scene.update(0)
        self.assertTrue(self.scene.moveset_focused)

        keys[pygame.K_TAB] = False
        with (
            patch("game.scenes.character_select_scene.pygame.key.get_pressed", return_value=keys),
            patch(
                "game.scenes.character_select_scene.KEY_BINDINGS.is_pressed",
                side_effect=lambda action, _keys: action == "menu_confirm",
            ),
        ):
            self.scene.update(0)
        self.assertTrue(self.scene.moveset_expanded)

    def test_back_button_requests_return_to_previous_screen(self) -> None:
        keys = [False] * 512
        with (
            patch("game.scenes.character_select_scene.pygame.key.get_pressed", return_value=keys),
            patch("game.scenes.character_select_scene.KEY_BINDINGS.is_pressed", return_value=False),
        ):
            self.scene.update(0, mouse_click=BACK_BUTTON.center)

        self.assertTrue(self.scene.back_requested)
        self.assertFalse(self.scene.selection_confirmed)

    def test_back_key_requests_return_to_previous_screen(self) -> None:
        keys = [False] * 512
        with (
            patch("game.scenes.character_select_scene.pygame.key.get_pressed", return_value=keys),
            patch(
                "game.scenes.character_select_scene.KEY_BINDINGS.is_pressed",
                side_effect=lambda action, _keys: action == "back_pause",
            ),
        ):
            self.scene.update(0)

        self.assertTrue(self.scene.back_requested)

    def test_wide_generated_image_is_available_for_ground_tiling(self) -> None:
        self.assertTrue(GROUND_TILE_PATH.is_file())
        self.assertGreater(pygame.image.load(str(GROUND_TILE_PATH)).get_width(), 1920)

    def test_new_background_layers_are_available(self) -> None:
        for path in (
            FAR_SKY_PATH,
            DISTANT_SKYLINE_PATH,
            PARTICLES_PATH,
            FAST_PARTICLES_PATH,
        ):
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())

    def test_ground_scroll_eases_into_and_out_of_walking(self) -> None:
        self.scene.ground_tile = pygame.Surface((100, 8))
        self.scene.ground_scroll_offset = 0.0
        self.scene.ground_scroll_speed = 0.0
        self.scene.preview_player = SimpleNamespace(current_name="walk", frame_index=0)

        self.scene._update_ground_scroll(0.1)

        self.assertGreater(self.scene.ground_scroll_speed, 0)
        self.assertLess(self.scene.ground_scroll_speed, 220.0 * GROUND_SCROLL_WORLD_SCALE)
        self.assertGreater(self.scene.ground_scroll_offset, 0)
        walking_speed = self.scene.ground_scroll_speed

        self.scene.preview_player.current_name = "idle"
        self.scene._update_ground_scroll(0.1)

        self.assertGreater(self.scene.ground_scroll_speed, 0)
        self.assertLess(self.scene.ground_scroll_speed, walking_speed)

    def test_ground_speed_tracks_walk_and_sprint_velocity(self) -> None:
        self.scene.preview_player = SimpleNamespace(current_name="walk", frame_index=0)

        for animation, expected_speed in (("walk", 220.0), ("run", 475.0)):
            self.scene.ground_scroll_speed = 0.0
            self.scene.preview_player.current_name = animation
            for _ in range(60):
                self.scene._update_ground_scroll(0.1)

            with self.subTest(animation=animation):
                self.assertAlmostEqual(
                    self.scene.ground_scroll_speed,
                    expected_speed,
                    delta=0.1,
                )

    def test_background_layers_scroll_at_different_parallax_rates(self) -> None:
        self.scene.preview_player = SimpleNamespace(current_name="walk", frame_index=0)

        self.scene._update_ground_scroll(0.1)

        self.assertGreater(self.scene.far_sky_scroll_offset, 0)
        self.assertGreater(self.scene.skyline_scroll_offset, self.scene.far_sky_scroll_offset)
        self.assertGreater(self.scene.slow_particle_scroll_offset, 0)
        self.assertGreater(
            self.scene.fast_particle_scroll_offset,
            self.scene.slow_particle_scroll_offset,
        )

    def test_both_particle_layers_move_while_the_preview_is_idle(self) -> None:
        self.scene.preview_player = SimpleNamespace(current_name="idle", frame_index=0)

        self.scene._update_ground_scroll(0.1)

        self.assertAlmostEqual(
            self.scene.slow_particle_scroll_offset,
            SLOW_PARTICLE_DRIFT_SPEED * 0.1,
        )
        self.assertAlmostEqual(
            self.scene.fast_particle_scroll_offset,
            FAST_PARTICLE_DRIFT_SPEED * 0.1,
        )

    def test_preview_forward_speed_uses_character_movement_stats(self) -> None:
        self.scene.preview_player = SimpleNamespace(current_name="walk", frame_index=0)
        walk_speed = self.scene._preview_forward_world_speed()

        self.scene.preview_player.current_name = "run"
        run_speed = self.scene._preview_forward_world_speed()

        self.assertEqual(walk_speed, 220.0)
        self.assertEqual(run_speed, 380.0 * 1.25)

    def test_preview_forward_special_uses_frame_gates(self) -> None:
        self.scene.preview_character_key = "davis"
        self.scene.preview_player = SimpleNamespace(
            current_name="sp_move_attack_2",
            frame_index=0,
        )
        self.assertEqual(self.scene._preview_forward_world_speed(), 0.0)

        self.scene.preview_player.frame_index = 1
        self.assertEqual(
            self.scene._preview_forward_world_speed(),
            380.0,
        )

    def test_frame_stepped_forward_special_moves_the_background(self) -> None:
        self.scene.preview_character_key = "luis"
        self.scene.preview_player = SimpleNamespace(
            current_name="sp_move_attack_1",
            frame_index=0,
            animations={"sp_move_attack_1": {"surfaces": [None] * 6}},
        )
        distance = self.scene._preview_frame_step_distance(
            "luis",
            "sp_move_attack_1",
            0,
            5,
        )
        self.scene.preview_forward_displacement = distance

        self.scene._update_ground_scroll(0.1)

        expected = 380.0 * 0.08 * 3 * GROUND_SCROLL_WORLD_SCALE
        self.assertAlmostEqual(distance, 380.0 * 0.08 * 3)
        self.assertAlmostEqual(self.scene.ground_scroll_offset, expected)

    def test_ground_texture_repeats_without_rescaling(self) -> None:
        self.scene.ground_tile = pygame.Surface((4, 4))
        colors = ((200, 0, 0), (0, 200, 0), (0, 0, 200), (200, 200, 0))
        for x, color in enumerate(colors):
            pygame.draw.line(self.scene.ground_tile, color, (x, 0), (x, 3))
        self.scene.ground_scroll_offset = 0.0
        surface = pygame.Surface((1920, 1080))

        self.scene._draw_background(surface)

        self.assertEqual(surface.get_at((0, SELECTION_GROUND_Y))[:3], colors[0])
        self.assertEqual(surface.get_at((3, SELECTION_GROUND_Y))[:3], colors[3])
        self.assertEqual(surface.get_at((4, SELECTION_GROUND_Y))[:3], colors[0])

    def test_background_layer_repeats_across_the_screen(self) -> None:
        self.scene.far_sky_tile = pygame.Surface((4, 4))
        self.scene.far_sky_tile.fill((20, 30, 40))
        self.scene.far_sky_scroll_offset = 0.0
        surface = pygame.Surface((1920, 1080))

        self.scene._draw_background(surface)

        self.assertEqual(surface.get_at((0, 0))[:3], (20, 30, 40))
        self.assertEqual(surface.get_at((4, 0))[:3], (20, 30, 40))


if __name__ == "__main__":
    unittest.main()
