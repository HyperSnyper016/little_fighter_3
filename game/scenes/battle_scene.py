from __future__ import annotations

from pathlib import Path

import pygame

from game.constants import GROUND_Y, SCREEN_HEIGHT, SCREEN_WIDTH, TEXT_COLOR
from game.data.characters import CHARACTERS
from game.entities.fighter import COMBAT_ATTACK_STATES, Fighter, FighterConfig, FighterInput, FighterSnapshot
from game.systems.audio import AudioBank
from game.systems.stage import ForestStage


class ArrowProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = 480.0
        self.velocity_y = -300.0
        self.gravity = 480.0
        self.ground_y = GROUND_Y + owner.lane_y - 18.0
        self.damage = 1
        self.frame_timer = 0.0
        self.frame_index = 0
        self.after_peak_timer = 0.0
        self.phase = "fly"
        self.can_damage = True
        self.finished = False
        self.just_broke = False
        arrows_root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "arrow"
        self.fly_frames = self._load_frames(arrows_root, "fly", 7)
        self.break_frames = self._load_frames(arrows_root, "arrowbreak", 10)
        self.frames = self.fly_frames if self.fly_frames else [pygame.Surface((12, 12), pygame.SRCALPHA)]

    def _load_frames(self, arrows_root: Path, prefix: str, count: int) -> list[pygame.Surface]:
        frames: list[pygame.Surface] = []
        for index in range(1, count + 1):
            path = arrows_root / f"{prefix}{index}.bmp"
            if not path.exists():
                continue
            frame = pygame.image.load(str(path)).convert()
            frame.set_colorkey((0, 0, 0))
            frames.append(frame)
        return frames

    def _start_break(self) -> None:
        if self.phase == "break":
            return
        self.phase = "break"
        self.just_broke = True
        self.can_damage = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.after_peak_timer = 0.0
        self.frames = self.break_frames or self.frames
        self.velocity_y = 120.0

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        if self.phase == "fly":
            if self.velocity_y < -90.0:
                self.frame_index = 0
                self.after_peak_timer = 0.0
            elif self.velocity_y < 30.0:
                self.frame_index = 1 if len(self.fly_frames) > 1 else 0
                self.after_peak_timer = 0.0
            else:
                self.after_peak_timer += dt
                descent_frame = 2 + int(self.after_peak_timer / 0.12)
                self.frame_index = min(max(0, len(self.fly_frames) - 1), descent_frame) if self.fly_frames else 0

            self.x += self.facing * self.speed_x * dt
            self.velocity_y += self.gravity * dt
            self.y += self.velocity_y * dt
            if self.y >= self.ground_y:
                self.y = self.ground_y
                self._start_break()
        else:
            self.frame_timer += dt
            while self.frame_timer >= 0.05:
                self.frame_timer -= 0.05
                self.frame_index += 1
                if self.frame_index >= len(self.break_frames):
                    self.frame_index = len(self.break_frames) - 1 if self.break_frames else 0
                    self.finished = True
                    break

            self.x += self.facing * self.speed_x * dt
            self.y += self.velocity_y * dt
            if self.y >= self.ground_y:
                self.y = self.ground_y
                self.velocity_y = 0.0

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class BallProjectile:
    def __init__(self, owner: Fighter, x: float, y: float, facing: int, ball_index: int) -> None:
        self.owner = owner
        self.x = float(x)
        self.y = float(y)
        self.facing = 1 if facing >= 0 else -1
        self.speed_x = 110.0
        self.max_speed_x = 560.0
        self.acceleration_x = 62.0
        self.damage = 1
        self.phase = "fly"
        self.can_damage = True
        self.finished = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.use_fast_frames = False
        self.fly_time = 0.0
        root = Path(__file__).resolve().parents[2] / "assets" / "sprites" / "shared_sprites" / "blue_ball" / f"ball_{ball_index}"
        self.slow_frames = self._load_frames(root / "slow")
        self.fast_frames = self._load_frames(root / "fast")
        self.burst_frames = self._load_frames(root.parent / "ball_burst")
        self.frames = self.slow_frames or self.fast_frames or [pygame.Surface((16, 16), pygame.SRCALPHA)]

    def _load_frames(self, folder: Path) -> list[pygame.Surface]:
        frames: list[pygame.Surface] = []
        if not folder.exists():
            return frames
        for path in sorted(folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".png", ".bmp"}:
                continue
            frame = pygame.image.load(str(path)).convert()
            frame.set_colorkey((0, 0, 0))
            frames.append(frame)
        return frames

    def _start_burst(self) -> None:
        if self.phase == "burst":
            return
        self.phase = "burst"
        self.can_damage = False
        self.frame_timer = 0.0
        self.frame_index = 0
        self.frames = self.burst_frames or self.frames

    def rect(self) -> pygame.Rect:
        frame = self.frames[self.frame_index]
        return pygame.Rect(int(self.x - frame.get_width() / 2), int(self.y - frame.get_height() / 2), frame.get_width(), frame.get_height())

    def update(self, dt: float) -> None:
        if self.phase == "fly":
            self.fly_time += dt
            speed_gain = self.acceleration_x * dt * (1.0 + (self.fly_time * 2.5))
            self.speed_x = min(self.max_speed_x, self.speed_x + speed_gain)
            self.use_fast_frames = self.speed_x >= 180.0 and bool(self.fast_frames)
            self.frames = self.fast_frames if self.use_fast_frames else (self.slow_frames or self.fast_frames or self.frames)
            self.x += self.facing * self.speed_x * dt
            if self.x < -240 or self.x > SCREEN_WIDTH + 240:
                self.finished = True
        else:
            self.frame_timer += dt
            while self.frame_timer >= 0.05:
                self.frame_timer -= 0.05
                self.frame_index += 1
                if self.frame_index >= len(self.frames):
                    self.frame_index = len(self.frames) - 1 if self.frames else 0
                    self.finished = True
                    break

    def draw(self, surface: pygame.Surface, camera_x: float) -> None:
        frame = self.frames[self.frame_index]
        if self.facing < 0:
            frame = pygame.transform.flip(frame, True, False)
        surface.blit(frame, (int(self.x - camera_x - frame.get_width() / 2), int(self.y - frame.get_height() / 2)))


class EnemyBrain:
    def __init__(self) -> None:
        self.attack_cooldown = 0.0

    def update(self, dt: float) -> None:
        if self.attack_cooldown > 0.0:
            self.attack_cooldown = max(0.0, self.attack_cooldown - dt)

    def build_input(self, fighter: FighterSnapshot, target: FighterSnapshot) -> FighterInput:
        input_state = FighterInput()
        lane_delta = target.lane_y - fighter.lane_y
        horizontal_delta = target.x - fighter.x
        distance = abs(horizontal_delta)

        if not fighter.controls_enabled:
            return input_state

        if target.state in {"knocked", "knocked_fire", "knocked_freeze"} and distance < 72 and fighter.z == 0:
            input_state.lift_just_pressed = True
            return input_state

        if fighter.state in {"knocked", "knocked_fire", "knocked_freeze", "get_up", "hurt", "die", "dead"}:
            return input_state

        if lane_delta < -12:
            input_state.up = True
        elif lane_delta > 12:
            input_state.down = True

        if horizontal_delta < -26:
            input_state.left = True
        elif horizontal_delta > 26:
            input_state.right = True

        if self.attack_cooldown > 0.0:
            input_state.horizontal_move_active = input_state.left or input_state.right
            return input_state

        if distance > 280:
            input_state.run = True
        elif distance < 56 and fighter.block_broken:
            input_state.attack_pressed = True
            input_state.attack_just_pressed = True
            self.attack_cooldown = 0.7
            return input_state

        if target.state in (COMBAT_ATTACK_STATES | {"jump"}) and fighter.defense_cooldown == 0.0 and distance < 96 and abs(lane_delta) < 30:
            input_state.block_pressed = True
            if distance < 72:
                if horizontal_delta < 0:
                    input_state.right = True
                else:
                    input_state.left = True
            return input_state

        if fighter.block_broken and distance < 56 and abs(lane_delta) < 18:
            input_state.attack_pressed = True
            input_state.attack_just_pressed = True
            self.attack_cooldown = 0.7
        elif fighter.z == 0 and target.z == 0 and 96 <= distance <= 132 and abs(lane_delta) < 18:
            if input_state.run and distance < 120:
                input_state.attack_pressed = True
                input_state.attack_just_pressed = True
                self.attack_cooldown = 0.45
            elif distance < 108:
                input_state.attack_pressed = True
                input_state.attack_just_pressed = True
                self.attack_cooldown = 0.45

        if fighter.z == 0 and target.z == 0 and 210 <= distance <= 320 and abs(lane_delta) < 18:
            input_state.jump_just_pressed = True

        input_state.horizontal_move_active = input_state.left or input_state.right
        return input_state


class BattleScene:
    def __init__(self, character_name: str = "bandit", include_idle_enemy: bool = True) -> None:
        self.font = pygame.font.Font(None, 32)
        self.small_font = pygame.font.Font(None, 24)
        self.pause_font = pygame.font.Font(None, 54)
        self.projectiles: list[ArrowProjectile] = []
        self.paused = False
        stage_root = Path(__file__).resolve().parents[2] / "assets" / "maps" / "Forrest"
        sounds_root = Path(__file__).resolve().parents[2] / "assets" / "sounds"
        self.stage = ForestStage(stage_root)
        self.audio = AudioBank(sounds_root)
        x_bounds = (self.stage.play_min_x, self.stage.play_max_x)
        start_x = SCREEN_WIDTH / 2
        self.fighter = Fighter(FighterConfig(character_name, CHARACTERS[character_name]), (start_x, 0), x_bounds=x_bounds)
        self.enemy = Fighter(FighterConfig("bandit", CHARACTERS["bandit"]), (start_x + 180, 0), x_bounds=x_bounds) if include_idle_enemy else None
        if self.enemy is not None:
            self.enemy.max_health = 10
            self.enemy.health = 10
        self.enemy_brain = EnemyBrain()
        if self.enemy is not None:
            self.enemy.facing = -1

    def _handle_combat(self) -> None:
        if self.enemy is None:
            return

        for attacker, defender in ((self.fighter, self.enemy), (self.enemy, self.fighter)):
            if attacker.is_dead or defender.is_dead:
                continue
            if attacker.state not in (COMBAT_ATTACK_STATES | {"jump"}):
                continue
            if attacker.name == "hunter" and attacker.state == "basic_attack":
                continue
            if attacker.state == "jump" and not attacker.jump_attack_active:
                continue
            if attacker.has_applied_attack_damage:
                continue
            if not attacker.attack_started:
                continue
            if attacker.attack_timer <= 0:
                attacker.has_applied_attack_damage = True
                attacker.attack_started = False
                continue
            if abs(attacker.lane_y - defender.lane_y) > 36:
                attacker.has_applied_attack_damage = True
                attacker.attack_started = False
                self.audio.play_hit_miss()
                continue
            if not attacker.world_hitbox_rect().inflate(72, 0).colliderect(defender.world_hitbox_rect()):
                attacker.has_applied_attack_damage = True
                attacker.attack_started = False
                self.audio.play_hit_miss()
                continue

            attacker.has_applied_attack_damage = True
            attacker.attack_started = False
            if defender.state == "block" and defender.block_strength > 0:
                defender.block_strength = 0
                defender.block_hold_timer = 0.0
                self.audio.play("hit_guard")
                continue
            if defender.state == "block" and defender.block_strength == 0:
                defender._start_block_break()
                self.audio.play("hit_guard")
                continue

            defender.receive_damage(attacker.touch_damage)
            if attacker.state == "jump" and attacker.jump_attack_active and not defender.is_dead:
                defender._start_knockdown()
            self.audio.play("hit_success")

    def _handle_audio(self, dt: float) -> None:
        fighters = [self.fighter]
        if self.enemy is not None:
            fighters.append(self.enemy)

        for fighter in fighters:
            if fighter.hunter_draw_arrow_sfx_pending:
                self.audio.play("draw_arrow")
                fighter.hunter_draw_arrow_sfx_pending = False
            if fighter.hunter_shoot_arrow_sfx_pending:
                self.audio.play("shoot_arrow")
                fighter.hunter_shoot_arrow_sfx_pending = False
            if fighter.just_knocked_down:
                self.audio.play("knockdown")
            if fighter.just_jumped:
                self.audio.play("jump")
            if fighter.just_landed:
                self.audio.play("jump_land")

            if fighter.z == 0 and fighter.state in {"walk", "run"}:
                if fighter.step_cycle_timer == 0.0:
                    self.audio.play_footstep()
                    fighter.step_cycle_timer = 0.22 if fighter.state == "walk" else 0.16
            else:
                fighter.step_cycle_timer = 0.0

    def _spawn_hunter_projectile(self, fighter: Fighter) -> None:
        if fighter.name != "hunter":
            return
        if fighter.state != "basic_attack":
            return
        if not fighter.attack_started or fighter.attack_projectile_fired:
            return

        fighter.attack_projectile_fired = True
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 58.0
        self.projectiles.append(ArrowProjectile(fighter, origin_x, origin_y, fighter.facing))

    def _spawn_template_projectile(self, fighter: Fighter) -> None:
        if fighter.name != "template":
            return
        if not fighter.state.startswith("sp_move_attack"):
            return
        if not fighter.attack_started or fighter.attack_projectile_fired:
            return

        fighter.attack_projectile_fired = True
        ball_index = fighter.next_special_move_projectile_index()
        origin_x = fighter.x + fighter.facing * (fighter.hitbox_size[0] * 0.42)
        origin_y = GROUND_Y + fighter.lane_y - fighter.z - 56.0
        self.projectiles.append(BallProjectile(fighter, origin_x, origin_y, fighter.facing, ball_index))
        fighter.special_move_projectile_timer = fighter.combat.get("special_projectile_interval", 0.2)

    def _update_projectiles(self, dt: float) -> None:
        for projectile in list(self.projectiles):
            projectile.update(dt)
            if getattr(projectile, "just_broke", False):
                self.audio.play("broken_arrow")
                projectile.just_broke = False
            if projectile.finished:
                self.projectiles.remove(projectile)
                continue
            if projectile.x < -200 or projectile.x > SCREEN_WIDTH + 400:
                self.projectiles.remove(projectile)
                continue

            for target in (self.fighter, self.enemy):
                if target is None or target is projectile.owner or target.is_dead:
                    continue
                if not projectile.can_damage:
                    continue
                if not projectile.rect().colliderect(target.world_hitbox_rect()):
                    continue

                if target.state == "block" and target.block_strength > 0:
                    target.block_strength = 0
                    target.block_hold_timer = 0.0
                    self.audio.play("hit_guard")
                elif target.state == "block" and target.block_strength == 0:
                    target._start_block_break()
                    self.audio.play("hit_guard")
                else:
                    target.receive_damage(projectile.damage)
                    self.audio.play("hit_success")

                if hasattr(projectile, "_start_burst"):
                    projectile._start_burst()
                else:
                    self.projectiles.remove(projectile)
                return

    def _draw_hud_bar(self, surface: pygame.Surface, x: int, y: int, width: int, height: int, value: int, maximum: int, color: tuple[int, int, int], label: str) -> None:
        pygame.draw.rect(surface, (28, 28, 32), (x, y, width, height), border_radius=6)
        pygame.draw.rect(surface, (215, 215, 220), (x, y, width, height), 2, border_radius=6)
        fill_width = 0 if maximum <= 0 else int((max(0, value) / maximum) * (width - 4))
        if fill_width > 0:
            pygame.draw.rect(surface, color, (x + 2, y + 2, fill_width, height - 4), border_radius=4)
        text = self.small_font.render(f"{label} {value}/{maximum}", True, TEXT_COLOR)
        surface.blit(text, (x + 10, y + 6))

    def _draw_hud(self, surface: pygame.Surface) -> None:
        panel_width = 420
        self._draw_hud_bar(surface, 20, 18, panel_width, 28, self.fighter.health, self.fighter.max_health, (194, 58, 58), f"{self.fighter.definition['display_name']} HP")
        self._draw_hud_bar(surface, 20, 52, panel_width, 24, self.fighter.mana, self.fighter.max_mana, (72, 122, 235), "MP")
        if self.enemy is not None:
            x = SCREEN_WIDTH - panel_width - 20
            self._draw_hud_bar(surface, x, 18, panel_width, 28, self.enemy.health, self.enemy.max_health, (194, 58, 58), f"{self.enemy.definition['display_name']} HP")
            self._draw_hud_bar(surface, x, 52, panel_width, 24, self.enemy.mana, self.enemy.max_mana, (72, 122, 235), "MP")

    def _draw_marker(self, surface: pygame.Surface, fighter: Fighter, camera_x: float, text: str) -> None:
        marker = self.small_font.render(text, True, (255, 240, 120))
        rect = marker.get_rect(midtop=(fighter.world_hitbox_rect().centerx - int(camera_x), fighter.world_hitbox_rect().bottom + 6))
        if rect.bottom < SCREEN_HEIGHT:
            surface.blit(marker, rect)

    def update(self, dt: float, inputs: FighterInput) -> None:
        if self.paused:
            return
        self.fighter.update(dt, inputs, target=self.enemy, controlled=True)
        if self.enemy is not None:
            self.enemy_brain.update(dt)
            enemy_input = self.enemy_brain.build_input(self.enemy.snapshot, self.fighter.snapshot)
            self.enemy.update(dt, enemy_input, target=self.fighter, controlled=True)

        for fighter in (self.fighter, self.enemy):
            if fighter is not None:
                self._spawn_hunter_projectile(fighter)
                self._spawn_template_projectile(fighter)

        self._update_projectiles(dt)
        self._handle_combat()
        self._handle_audio(dt)

    def draw(self, surface: pygame.Surface) -> None:
        focus_x = self.fighter.x
        if self.enemy is not None:
            player_margin = SCREEN_WIDTH * 0.3
            min_focus = self.fighter.x - player_margin
            max_focus = self.fighter.x + player_margin
            enemy_focus = (self.fighter.x + self.enemy.x) / 2
            focus_x = max(min_focus, min(max_focus, enemy_focus))

        camera_x = self.stage.camera_x(focus_x)
        self.stage.draw(surface, focus_x)

        for projectile in self.projectiles:
            projectile.draw(surface, camera_x)

        fighters = [self.fighter]
        if self.enemy is not None:
            fighters.append(self.enemy)
        fighters.sort(key=lambda fighter: fighter.lane_y)
        for fighter in fighters:
            fighter.draw(surface, camera_x)

        self._draw_marker(surface, self.fighter, camera_x, "P1")
        self._draw_hud(surface)
        if self.paused:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            surface.blit(overlay, (0, 0))
            paused = self.pause_font.render("Paused", True, TEXT_COLOR)
            resume = self.small_font.render("Esc: Resume", True, TEXT_COLOR)
            menu = self.small_font.render("M: Main Menu", True, TEXT_COLOR)
            surface.blit(paused, paused.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40)))
            surface.blit(resume, resume.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 10)))
            surface.blit(menu, menu.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 40)))
