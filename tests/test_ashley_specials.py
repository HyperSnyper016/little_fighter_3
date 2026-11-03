import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pygame

from game.constants import LANE_MAX_Y, LANE_MIN_Y
from game.data.characters import CHARACTERS
from game.entities.fighter import Fighter, FighterConfig, FighterInput
from game.scenes.battle_scene import (
    AshleyBlastProjectile,
    AshleyMagicalBarrierEffect,
    AshleyManaOrbProjectile,
    AshleyMissileProjectile,
    AshleySpriteEffect,
    BattleScene,
)


class _Audio:
    def __init__(self) -> None:
        self.played: list[str] = []

    def play(self, sound: str) -> None:
        self.played.append(sound)


class AshleySpecialMoveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.display.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((1, 1))

    @staticmethod
    def _fighter() -> Fighter:
        return Fighter(FighterConfig("ashley", CHARACTERS["ashley"]), (120.0, 40.0))

    @classmethod
    def _scene(cls, fighter: Fighter, enemies: list[Fighter], projectiles: list[object]) -> BattleScene:
        scene = object.__new__(BattleScene)
        scene.fighter = fighter
        scene.enemies = enemies
        scene.rudolf_clones = []
        scene.projectiles = projectiles
        scene.consumable_items = []
        scene.stage = SimpleNamespace(
            camera_x=lambda _: 0.0,
            play_min_x=-1000.0,
            play_max_x=3000.0,
        )
        scene.audio = _Audio()
        scene._deal_damage = lambda attacker, target, amount: setattr(
            target,
            "health",
            max(0, target.health - amount),
        )
        return scene

    @staticmethod
    def _cross_to_frame(fighter: Fighter, state: str, frame_index: int) -> None:
        fighter._start_attack_state(state)
        fighter.animation_player.play(state)
        fighter.animation_player.frame_index = frame_index - 1
        fighter.animation_player.timer = 0.07
        fighter.update(0.02, FighterInput())

    def test_ashley_basic_attack_cycle_uses_only_available_attacks(self) -> None:
        fighter = self._fighter()
        self.assertEqual(fighter.basic_attack_cycle, ["attack_1", "attack_2", "attack_3"])
        self.assertNotIn("attack_4", fighter.animations)
        self.assertEqual(
            [len(fighter.animations[name]["surfaces"]) for name in fighter.basic_attack_cycle],
            [3, 3, 4],
        )

    def test_ashley_attack_animations_spawn_random_sparkle_sets(self) -> None:
        attack_cases = (
            ("basic_attack", "attack_1", 2, 0.0),
            ("basic_attack", "attack_2", 2, 0.0),
            ("basic_attack", "attack_3", 1, 0.0),
            ("sprint_punch", "sprint_punch", 1, 0.0),
            ("jump_throw", "jump_attack", 1, 80.0),
            ("jump_throw", "second_jump_basic_attack", 2, 80.0),
        )
        sparkle_sets = ("1_", "2_", "1_", "2_", "1_", "2_")

        for (state, animation_name, frame_index, height), sparkle_set in zip(
            attack_cases,
            sparkle_sets,
        ):
            with self.subTest(state=state, animation=animation_name):
                fighter = self._fighter()
                if state == "jump_throw":
                    fighter.jump_stage = 2 if animation_name == "second_jump_basic_attack" else 1
                    fighter.z = height
                    fighter._start_jump_attack()
                else:
                    fighter.attack_animation = animation_name if state == "basic_attack" else "attack_1"
                    fighter._start_attack_state(state)
                if state == "jump_throw":
                    fighter.current_jump_animation = animation_name

                fighter.animation_player.play(animation_name)
                fighter.animation_player.frame_index = frame_index - 1
                fighter.animation_player.timer = fighter.animations[animation_name]["frame_duration"]
                fighter.update(0.01, FighterInput())
                self.assertTrue(fighter.ashley_sparkles_pending)

                scene = self._scene(fighter, [], [])
                with patch(
                    "game.scenes.battle_scene.random.choice",
                    return_value=sparkle_set,
                ):
                    scene._spawn_ashley_attack_sparkles(fighter)
                self.assertFalse(fighter.ashley_sparkles_pending)
                self.assertEqual(len(scene.projectiles), 1)
                effect = scene.projectiles[0]
                self.assertIsInstance(effect, AshleySpriteEffect)
                self.assertEqual(effect.frame_prefix, sparkle_set)
                self.assertEqual(len(effect.frames), 4)
                self.assertEqual(
                    effect.x,
                    fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.6),
                )
                self.assertEqual(effect.y, fighter.world_hitbox_rect().centery)
                self.assertTrue(effect.foreground)

    def test_projectile_and_orb_spawns_are_timed_to_ashley_animation_frames(self) -> None:
        fighter = self._fighter()
        self._cross_to_frame(fighter, "sp_move_attack_1", 2)
        self.assertTrue(fighter.ashley_blast_pending)

        scene = object.__new__(BattleScene)
        scene.projectiles = []
        scene.audio = _Audio()
        scene._spawn_ashley_blast(fighter)
        self.assertEqual(scene.audio.played, ["julian_ball_create"])
        self.assertEqual(sum(isinstance(item, AshleyBlastProjectile) for item in scene.projectiles), 1)
        self.assertEqual(sum(isinstance(item, AshleySpriteEffect) for item in scene.projectiles), 2)
        self.assertEqual(
            [item.scale for item in scene.projectiles if isinstance(item, AshleySpriteEffect)],
            [1.0, 1.0],
        )

        fighter = self._fighter()
        self._cross_to_frame(fighter, "sp_move_attack_2", 2)
        self.assertTrue(fighter.ashley_missiles_pending)
        targets = [
            Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (240.0, LANE_MIN_Y)),
            Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (260.0, fighter.lane_y)),
            Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (280.0, LANE_MAX_Y)),
        ]
        scene.enemies = targets
        scene.fighter = fighter
        scene._spawn_ashley_missiles(fighter)
        missiles = [item for item in scene.projectiles if isinstance(item, AshleyMissileProjectile)]
        self.assertEqual(len(missiles), 3)
        self.assertEqual(
            {missile.target_lane_y for missile in missiles},
            {LANE_MIN_Y, fighter.lane_y, LANE_MAX_Y},
        )

        fighter = self._fighter()
        self._cross_to_frame(fighter, "sp_vert_attack_1", 5)
        self.assertTrue(fighter.ashley_barrier_pending)
        scene.projectiles = []
        scene._spawn_ashley_barrier(fighter)
        barrier = scene.projectiles[0]
        self.assertIsInstance(barrier, AshleyMagicalBarrierEffect)
        self.assertFalse(barrier.movement_enabled)
        fighter.animation_player.frame_index = 7
        fighter.animation_player.timer = 0.07
        fighter.update(0.02, FighterInput())
        self.assertTrue(fighter.ashley_barrier_start_pending)
        scene._spawn_ashley_barrier(fighter)
        self.assertTrue(barrier.movement_enabled)

        fighter = self._fighter()
        self._cross_to_frame(fighter, "sp_vert_attack_2", 1)
        self.assertTrue(fighter.ashley_mana_orb_pending)
        scene.projectiles = []
        scene.audio = _Audio()
        scene._spawn_ashley_mana_orb(fighter)
        self.assertEqual(scene.audio.played, ["john_heal_orb"])
        self.assertEqual(len(scene.projectiles), 1)
        self.assertIsInstance(scene.projectiles[0], AshleyManaOrbProjectile)

    def test_ashley_blast_flys_then_bursts(self) -> None:
        fighter = self._fighter()
        projectile = AshleyBlastProjectile(fighter, 200.0, 240.0, 1)
        projectile.update(0.1)
        self.assertGreater(projectile.x, 200.0)
        self.assertEqual(projectile.phase, "fly")

        projectile._start_burst()
        self.assertEqual(projectile.phase, "burst")
        self.assertFalse(projectile.can_damage)
        projectile.update(1.0)
        self.assertTrue(projectile.finished)

    def test_missiles_descend_to_ground_and_play_burst(self) -> None:
        fighter = self._fighter()
        missile = AshleyMissileProjectile(
            fighter,
            None,
            200.0,
            240.0,
            1,
            fighter.lane_y,
            0,
        )
        missile.update(0.2)
        self.assertLess(missile.y, 240.0)
        missile.update(1.1)
        for _ in range(30):
            if missile.just_ground_hit:
                break
            missile.update(0.1)
        self.assertTrue(missile.just_ground_hit)
        self.assertEqual(missile.phase, "burst")

    def test_untargeted_missiles_arc_to_random_ground_spots(self) -> None:
        fighter = self._fighter()
        self._cross_to_frame(fighter, "sp_move_attack_2", 2)
        scene = self._scene(fighter, [], [])
        lanes = [LANE_MIN_Y, fighter.lane_y, LANE_MAX_Y]
        distances = [360.0, 420.0, 480.0]
        with patch("game.scenes.battle_scene.random.choice", side_effect=lanes), patch(
            "game.scenes.battle_scene.random.uniform",
            side_effect=distances,
        ):
            scene._spawn_ashley_missiles(fighter)

        missiles = [item for item in scene.projectiles if isinstance(item, AshleyMissileProjectile)]
        self.assertEqual([missile.target for missile in missiles], [None, None, None])
        self.assertEqual([missile.target_lane_y for missile in missiles], lanes)
        for missile, distance in zip(missiles, distances):
            self.assertAlmostEqual(missile.ground_target_x, missile.origin_x + distance)

        first_missile = missiles[0]
        first_missile.update(0.2)
        self.assertLess(first_missile.y, first_missile.start_y)
        self.assertGreater(first_missile.x, first_missile.origin_x)
        for _ in range(50):
            if first_missile.just_ground_hit:
                break
            first_missile.update(0.03)
        self.assertTrue(first_missile.just_ground_hit)
        self.assertAlmostEqual(first_missile.x, first_missile.ground_target_x)

    def test_barrier_waits_for_launch_then_reflects_and_bursts(self) -> None:
        fighter = self._fighter()
        barrier = AshleyMagicalBarrierEffect(fighter, 200.0, 240.0, 1)
        barrier.update(0.16)
        self.assertEqual(barrier.phase, "barrier")
        self.assertFalse(barrier.movement_enabled)
        barrier.update(0.1)
        self.assertEqual(barrier.x, 200.0)

        barrier.start_moving()
        barrier.update(0.1)
        self.assertGreater(barrier.x, 200.0)
        self.assertEqual(barrier.health, 2)
        barrier.take_damage()
        self.assertEqual(barrier.phase, "barrier")
        self.assertTrue(barrier.reflect_active)
        self.assertIs(barrier.frames, barrier.barrier_frames)
        barrier.update(0.4)
        self.assertEqual(barrier.phase, "barrier")
        self.assertFalse(barrier.reflect_active)
        barrier.take_damage()
        barrier.update(0.4)
        self.assertEqual(barrier.phase, "burst")

    def test_barrier_bursts_after_reflecting_its_second_enemy(self) -> None:
        owner = self._fighter()
        first_target = Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (240.0, owner.lane_y))
        second_target = Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (260.0, owner.lane_y))
        barrier = AshleyMagicalBarrierEffect(owner, 200.0, 240.0, 1)
        barrier.phase = "barrier"
        barrier.frames = barrier.barrier_frames

        self.assertTrue(barrier.hit_enemy(first_target))
        barrier.update(0.4)
        self.assertEqual(barrier.phase, "barrier")
        self.assertTrue(barrier.hit_enemy(second_target))
        barrier.update(0.4)
        self.assertEqual(barrier.phase, "burst")

    def test_mana_orb_pickup_doubles_regeneration_for_three_seconds(self) -> None:
        fighter = self._fighter()
        fighter.mana = 0
        orb = AshleyManaOrbProjectile(
            fighter,
            fighter.x,
            fighter.world_hitbox_rect().centery,
            1,
        )
        scene = object.__new__(BattleScene)
        scene.fighter = fighter
        scene.enemies = []
        scene.rudolf_clones = []
        scene.projectiles = [orb]
        scene.stage = SimpleNamespace(camera_x=lambda _: 0.0)
        scene.audio = _Audio()

        scene._update_projectiles(0.01)
        self.assertEqual(fighter.mana_regen_boost_timer, 3.0)
        self.assertEqual(scene.audio.played, ["john_heal_orb_heal"])
        fighter.update(0.5, FighterInput())
        self.assertEqual(fighter.mana, 2)

    def test_blast_and_missiles_knock_down_their_targets(self) -> None:
        owner = self._fighter()
        target = Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (240.0, owner.lane_y))
        target_rect = target.world_hitbox_rect()
        blast = AshleyBlastProjectile(owner, target_rect.centerx, target_rect.centery, owner.facing)
        blast.origin_x = owner.x
        scene = self._scene(owner, [target], [blast])
        scene._update_projectiles(0.0)
        self.assertEqual(target.state, "fall")
        self.assertEqual(blast.phase, "burst")
        self.assertIn("john_blast_hit", scene.audio.played)

        target = Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (240.0, owner.lane_y))
        target_rect = target.world_hitbox_rect()
        missile = AshleyMissileProjectile(
            owner,
            target,
            target_rect.centerx,
            target_rect.centery,
            owner.facing,
            target.lane_y,
            0,
        )
        missile.origin_x = owner.x
        scene = self._scene(owner, [target], [missile])
        scene._update_projectiles(0.0)
        self.assertEqual(target.state, "knocked_fire")
        self.assertEqual(missile.phase, "burst")

    def test_missed_missile_leaves_ashley_fire_and_barrier_hits_enemies(self) -> None:
        owner = self._fighter()
        missile = AshleyMissileProjectile(
            owner,
            None,
            240.0,
            300.0,
            owner.facing,
            owner.lane_y,
            0,
        )
        missile.phase = "burst"
        missile.can_damage = False
        missile.just_ground_hit = True
        missile._start_burst()
        scene = self._scene(owner, [], [missile])
        scene._update_projectiles(0.0)
        fire = next(item for item in scene.projectiles if isinstance(item, AshleySpriteEffect))
        self.assertTrue(fire.ground_anchored)
        self.assertEqual(fire.frames and len(fire.frames), 16)

        target = Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (240.0, owner.lane_y))
        barrier = AshleyMagicalBarrierEffect(
            owner,
            target.world_hitbox_rect().centerx,
            target.world_hitbox_rect().centery,
            owner.facing,
        )
        barrier.phase = "barrier"
        barrier.frames = barrier.barrier_frames
        barrier.start_moving()
        scene = self._scene(owner, [target], [barrier])
        scene._update_projectiles(0.0)
        self.assertEqual(target.state, "fall")
        self.assertEqual(barrier.enemy_hits, 1)
        self.assertEqual(barrier.phase, "barrier")
        self.assertTrue(barrier.reflect_active)

    def test_projectile_reflected_by_ashley_barrier_can_hit_its_shooter(self) -> None:
        owner = self._fighter()
        shooter = Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (80.0, owner.lane_y))
        barrier = AshleyMagicalBarrierEffect(
            owner,
            200.0,
            owner.world_hitbox_rect().centery,
            owner.facing,
        )
        barrier.phase = "barrier"
        barrier.frames = barrier.barrier_frames
        incoming = AshleyBlastProjectile(shooter, barrier.x, barrier.y, owner.facing)
        scene = self._scene(owner, [shooter], [barrier, incoming])

        scene._update_projectiles(0.0)

        self.assertIs(incoming.owner, owner)
        self.assertEqual(incoming.facing, -owner.facing)
        self.assertLess(incoming.x, barrier.x)
        self.assertEqual(barrier.health, 1)
        self.assertEqual(barrier.phase, "barrier")
        self.assertTrue(barrier.reflect_active)
        self.assertIs(barrier.frames, barrier.barrier_frames)

        scene._update_projectiles(0.0)

        self.assertEqual(shooter.state, "fall")
        self.assertEqual(incoming.phase, "burst")


if __name__ == "__main__":
    unittest.main()
