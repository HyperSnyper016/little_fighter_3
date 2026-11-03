import unittest
from unittest.mock import patch

from game.scenes.map_select_scene import MapSelectScene
from game.systems.stage import STAGE_CONFIGS


class MapSelectSceneTests(unittest.TestCase):
    def _create_scene(self, *, initial_map: str | None = None) -> MapSelectScene:
        with (
            patch("game.scenes.map_select_scene.pygame.font.Font"),
            patch.object(MapSelectScene, "_load_previews", return_value={}),
        ):
            return MapSelectScene("bandit", initial_map=initial_map)

    def test_initial_map_is_restored_when_returning_to_map_select(self) -> None:
        initial_map = tuple(STAGE_CONFIGS)[-1]

        scene = self._create_scene(initial_map=initial_map)

        self.assertEqual(scene.selected_map, initial_map)

    def test_back_button_requests_return_to_character_selection(self) -> None:
        scene = self._create_scene()
        keys = [False] * 512
        with (
            patch("game.scenes.map_select_scene.pygame.key.get_pressed", return_value=keys),
            patch("game.scenes.map_select_scene.KEY_BINDINGS.is_pressed", return_value=False),
        ):
            scene.update(0, mouse_click=scene.BACK_BUTTON.center)

        self.assertTrue(scene.back_requested)

    def test_back_key_requests_return_to_character_selection(self) -> None:
        scene = self._create_scene()
        keys = [False] * 512
        with (
            patch("game.scenes.map_select_scene.pygame.key.get_pressed", return_value=keys),
            patch(
                "game.scenes.map_select_scene.KEY_BINDINGS.is_pressed",
                side_effect=lambda action, _keys: action == "back_pause",
            ),
        ):
            scene.update(0)

        self.assertTrue(scene.back_requested)


if __name__ == "__main__":
    unittest.main()
