import math
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from settings import EmitterSchedule
from rich import print

import pygame
from camera import Camera
from pygame.math import Vector2 as vec
from pyscroll.group import PyscrollGroup
import settings
from settings import PARTICLES_DIR, ZOOM_LEVEL


#####################################################################################################################


@dataclass
# MARK: Particle
class Particle():
    # MARK: Particle
    start_view: pygame.Rect
    x: int = 0
    y: int = 0
    speed_x: int = 0
    speed_y: int = 0
    scale: float = 1.0
    rotation: float = 0.0
    alpha: int = 255
    # 1 = 1 second
    lifetime: float = 1.0
    time_elapsed: float = 0.0

    ###################################################################################################################
    # MARK: x_oscillation
    # def x_oscillation(self) -> int:
    #     return 0

#####################################################################################################################


def static_x_oscillation() -> float:
    return 0.0


class ParticleImageBased:
    # MARK: ParticleImageBased
    def __init__(
        self,
        screen: pygame.Surface,
        image: pygame.Surface,
        group: PyscrollGroup,
        camera: Camera,
        animation: list[pygame.Surface] | None = None,
        animation_speed: float = 0.0,
        loop_animation: bool = True,
        freeze_after_nth_frame: int = 10_000,
        rate: int | float = 1,
        scale_speed: float = 1.0,
        rotation_speed: float = 1.0,
        alpha_speed: float = 1.0,
        spawn_rect: pygame.Rect | pygame.FRect | None = None,
        x_oscillation: Callable | None = None,
    ):

        self.particles: list[Particle] = []

        self.screen = screen
        self.image = image
        self.group = group
        self.camera = camera
        self.animation = animation
        self.animation_speed = animation_speed
        self.loop_animation = loop_animation
        self.freeze_after_nth_frame = freeze_after_nth_frame
        self.frame_index: float = 0.0
        self.width = self.image.get_rect().width
        self.height = self.image.get_rect().height
        self.rect = pygame.Rect(0, 0, self.width, self.height)
        self.center = self.rect.center

        # amount of new particles per second
        self.rate: int | float = rate
        self.custom_event_id: int  = pygame.event.custom_type()

        # timer is NOT started here - the WeatherDirector controls spawning via
        # start()/stop(); this keeps emitters idle until an episode activates them
        self.interval: float = 1000.0 // rate
        self.is_running: bool = False

        # scale_speed: 1.0 ==> from 100% to 0% size in 1 second
        self.scale_speed = scale_speed
        # rotation_speed: 1.0 ==> full 360 degree rotation in 1 second
        self.rotation_speed = rotation_speed
        # alpha_speed: 1.0 ==> from not transparent to fully transparent in 1 second
        self.alpha_speed = alpha_speed
        # (optional) if provided, add_particles function will choose random start point from inside this rect
        self.spawn_rect = spawn_rect
        # (optional) if provided, x position will oscillate
        self.x_oscillation: Callable = x_oscillation or (lambda x: 0.0)

    ###################################################################################################################
    # MARK: start / stop
    def start(self) -> None:
        # (re)arm the spawn timer; from now on custom_event_id fires every `interval` ms
        if self.is_running:
            return
        # NOTE: pass the int event-type, NOT pygame.event.Event(...): pygbag's
        # patch_set_timer does `if event in THREADS` and an Event object is
        # unhashable -> TypeError that freezes the game in the browser.
        pygame.time.set_timer(self.custom_event_id, int(self.interval))
        self.is_running = True

    def stop(self) -> None:
        # disarm the spawn timer (interval 0 cancels it); existing particles keep
        # animating and fade out on their own via emit()
        if not self.is_running:
            return
        # int event-type, not an Event object (see start() note re: pygbag freeze)
        pygame.time.set_timer(self.custom_event_id, 0)
        self.is_running = False

    ###################################################################################################################
    # MAR: animate
    def animate(self, time_elapsed: float) -> None:
        if not self.animation:
            return

        self.frame_index = (self.animation_speed * time_elapsed)

        if int(self.frame_index) >= len(self.animation):
            self.frame_index = 0.0 if self.loop_animation else len(self.animation) - 1.0
        # print(f"{len(self.animation)=} {self.frame_index:4.1f} {int(self.frame_index)=}")

        self.image = self.animation[int(self.frame_index)].copy()

    ###################################################################################################################
    # MARK: emit
    def emit(self, dt: float) -> None:
        if not self.particles:
            return

        self.delete_old_particles()
        # test = 0
        for particle in self.particles:
            particle.time_elapsed += dt
            if self.animation:
                self.animate(particle.time_elapsed)

            if int(self.frame_index) < self.freeze_after_nth_frame:
                particle.x += int((particle.speed_x * dt) + self.x_oscillation(particle.time_elapsed))
                particle.y += int(particle.speed_y * dt)

            particle.lifetime -= dt

            particle.scale -= dt * self.scale_speed

            if particle.scale <= 0:
                continue

            particle.rotation += self.rotation_speed * 360 * dt
            particle.rotation = particle.rotation % 360

            particle.alpha -= int(self.alpha_speed * 255 * dt)
            particle.alpha = max(particle.alpha, 0)
            self.image.set_alpha(particle.alpha)

            surface  = self.image
            surface = pygame.transform.scale(
                self.image,
                (self.width * particle.scale, self.height * particle.scale)
            )

            self.rect = surface.get_rect(topleft=(particle.x, particle.y))

            # need to compensate for the camera move and zoom change since the creation of particle
            # this ensures that the particles are always in the same place relative to the ground
            view_offset = vec(
                particle.start_view.centerx - self.group.view.centerx,
                particle.start_view.centery - self.group.view.centery) * self.camera.zoom

            self.rect = self.rect.move(view_offset.x, view_offset.y)
            self.screen.blit(surface, self.rect.topleft)

    ###################################################################################################################
    # MARK: add_particles
    def add_particles(
        self,
        start_pos: tuple[int | float, int | float] | None = None,
        move_speed: float = 100.0,
        move_dir: int = 180,
        rotation: int = 0,
        scale: float = 1.0,
        alpha: int = 255,
        lifetime: float = 1.0
    ) -> None:
        # move_speed: 100 ==> 100 px per sec
        # move_dir:     0 ==> up, 90 ==> right (in degrees, clockwise)
        # rotation:     0 ==> no rotation; 180 ==> flip upside down (initial rotation in degrees, clockwise)
        # scale:        1 ==> no change; 2 ==> extend 2 times (initial)
        # lifetime:     1 ==> 1 second
        if not start_pos and not self.spawn_rect:
            print("[red]ERROR[/] no start position for particle!")

        # if spawn area is provided use it; otherwise use the middle of the screen
        if self.spawn_rect:
            pos_x = int(self.spawn_rect.x + random.random() * self.spawn_rect.width)
            pos_y = int(self.spawn_rect.y + random.random() * self.spawn_rect.height)
        elif start_pos:
            pos_x = int(start_pos[0] - self.width / 2)
            pos_y = int(start_pos[1] - self.height / 2)

        dir_vec = vec(0, -1).rotate(move_dir).normalize() * move_speed
        direction_x = int(dir_vec.x)
        direction_y = int(dir_vec.y)
        # compensate the camera zoom level change
        p = Particle(self.group.view,
                     pos_x, pos_y,
                     direction_x, direction_y,
                     scale * (self.camera.zoom / ZOOM_LEVEL),
                     rotation,
                     alpha,
                     lifetime
                     )
        # if self.x_oscillation:
        #     p.x_oscillation = self.x_oscillation

        self.particles.append(p)

    ###################################################################################################################
    # MARK: delete_particles
    def delete_old_particles(self) -> None:
        particle_copy = [particle for particle in self.particles if particle.lifetime > 0.0]
        self.particles = particle_copy


#######################################################################################################################
# MARK: ParticleSystem
class ParticleSystem(ABC):
    @ abstractmethod
    def __init__(self, canvas: pygame.Surface, group: PyscrollGroup, camera: Camera) -> None:
        self.custom_event_id: int = 0

    @ abstractmethod
    def add(self) -> None:
        ...

    @ abstractmethod
    def emit(self, dt: float) -> None:
        ...

    @ abstractmethod
    def start(self) -> None:
        # arm the emitter so it begins spawning particles
        ...

    @ abstractmethod
    def stop(self) -> None:
        # disarm the emitter; existing particles fade out via emit()
        ...

#######################################################################################################################
# MARK: Leaf


class ParticleLeafs(ParticleSystem):
    def __init__(self, canvas: pygame.Surface, group: PyscrollGroup, camera: Camera) -> None:
        # leafs appears at the top half of the screen
        spawn_rect = pygame.Rect(0, 0, settings.WIDTH, settings.HEIGHT // 2)

        leaf_img = pygame.image.load(PARTICLES_DIR / "Leaf_single.png").convert_alpha()
        # emit: 1 particle/second
        self.particle = ParticleImageBased(
            screen=canvas,
            image=leaf_img,
            group=group,
            camera=camera,
            rate=5,
            scale_speed=0.25,
            alpha_speed=0.1,
            rotation_speed=0.0,
            spawn_rect=spawn_rect,
            x_oscillation=self.x_oscillation,
        )
        self.custom_event_id = self.particle.custom_event_id

    # plain method: input is particle.time_elapsed (a float growing every frame), so it
    # never repeats - caching it gave 0 hits and grew unbounded; just compute the sine
    def x_oscillation(self, time_elapsed: float) -> float:
        return math.sin(time_elapsed * 10.0) * 4.0

    ###################################################################################################################
    def add(self) -> None:
        # move 80 pixels/seconds into south-west (down-left) +/- 30 degree, enlarge 5 x, kill after 4 seconds
        # (spawn_rect drives the position; no mouse involved for weather particles)
        self.particle.add_particles(
            move_speed=80,
            move_dir=210 + random.randint(-30, 30),
            scale=5.0,
            lifetime=4.0
        )

    ###################################################################################################################
    def emit(self, dt: float) -> None:
        self.particle.emit(dt)

    ###################################################################################################################
    def start(self) -> None:
        self.particle.start()

    def stop(self) -> None:
        self.particle.stop()

#####################################################################################################################


class ParticleRain(ParticleSystem):
    # MARK: Rain
    def __init__(self, canvas: pygame.Surface, group: PyscrollGroup, camera: Camera) -> None:
        # rain appears at the top of the screen (16 pixels high, full width)
        spawn_rect = pygame.Rect(0, -settings.HEIGHT // 2, settings.WIDTH + 256, settings.HEIGHT)
        # leaf_img = pygame.image.load(PARTICLES_DIR / "Rain.png").convert_alpha()

        from settings import import_sprite_sheet, SPRITE_SHEET_DEFINITION_RAIN
        animation1 = import_sprite_sheet(str(PARTICLES_DIR / "Rain.png"), 8, 8,
                                         SPRITE_SHEET_DEFINITION_RAIN, add_missing_directions=False)
        animation2 = import_sprite_sheet(str(PARTICLES_DIR / "RainOnFloor.png"), 8, 8,
                                         SPRITE_SHEET_DEFINITION_RAIN, add_missing_directions=False)
        animation = animation1["rain"] + animation2["rain"]
        # emit: 1 particle/second
        self.particle = ParticleImageBased(
            screen=canvas,
            image=animation[0].copy(),
            group=group,
            camera=camera,
            animation=animation,
            animation_speed=6.0,
            freeze_after_nth_frame=3,
            rate=30,  # 30
            scale_speed=0.0,
            alpha_speed=0.0,
            rotation_speed=0.0,
            spawn_rect=spawn_rect,
        )
        self.custom_event_id = self.particle.custom_event_id

    ###################################################################################################################
    def add(self) -> None:
        # move 1500 pixels/seconds into south-west (down-left) enlarge 5 x, kill after half a second
        # (spawn_rect drives the position; no mouse involved for weather particles)
        self.particle.add_particles(
            move_speed=1500,
            move_dir=210,
            scale=4.0,
            lifetime=1.0
        )

    ###################################################################################################################
    def emit(self, dt: float) -> None:
        self.particle.emit(dt)

    ###################################################################################################################
    def start(self) -> None:
        self.particle.start()

    def stop(self) -> None:
        self.particle.stop()

#####################################################################################################################


class ParticleDestructible(ParticleSystem):
    # MARK: Destructible
    def __init__(self,
                 canvas: pygame.Surface,
                 group: PyscrollGroup,
                 camera: Camera,
                 spawn_rect: pygame.Rect | pygame.FRect,
                 type: str
                 ) -> None:
        self.spawn_rect = spawn_rect
        self.type = type

        from settings import (
            import_sprite_sheet,
            SPRITE_SHEET_DEFINITION_LEAF,
            SPRITE_SHEET_DEFINITION_DESTRUCTIBLE_FOLIAGE,
            SPRITE_SHEET_DEFINITION_ROCK,
            SPRITE_SHEET_DEFINITION_DESTRUCTIBLE_ROCK,
        )

        # animation of leaf moving sideways
        self.animations = import_sprite_sheet(str(PARTICLES_DIR / "Leaf.png"),
                                              12, 7,
                                              SPRITE_SHEET_DEFINITION_LEAF,
                                              add_missing_directions=False
                                              )

        # animation of destructible object in place
        dest_animations = import_sprite_sheet(str(PARTICLES_DIR / "Leaf_destruct.png"),
                                              32, 28,
                                              SPRITE_SHEET_DEFINITION_DESTRUCTIBLE_FOLIAGE,
                                              add_missing_directions=False
                                              )
        self.animations.update(dest_animations)
        dest_animations = import_sprite_sheet(str(PARTICLES_DIR / "Rock.png"),
                                              16, 16,
                                              SPRITE_SHEET_DEFINITION_ROCK,
                                              add_missing_directions=False
                                              )
        self.animations.update(dest_animations)
        dest_animations = import_sprite_sheet(str(PARTICLES_DIR / "Rock_destruct.png"),
                                              30, 30,
                                              SPRITE_SHEET_DEFINITION_DESTRUCTIBLE_ROCK,
                                              add_missing_directions=False
                                              )
        self.animations.update(dest_animations)

        animation_speed = 10.00
        scale_speed     =  0.10
        alpha_speed     =  0.80
        rate            =  0.50

        # leaf particles moving left
        animation = self.animations[f"{self.type}_left"]
        self.particle_left = ParticleImageBased(
            screen          = canvas,
            image           = animation[0].copy(),
            group           = group,
            camera          = camera,
            animation       = animation,
            animation_speed = animation_speed,
            rate            = rate,
            scale_speed     = scale_speed,
            alpha_speed     = alpha_speed,
            rotation_speed  = 0.0,
            spawn_rect      = spawn_rect,
        )

        # leaf particles moving right
        animation = self.animations[f"{self.type}_right"]
        self.particle_right = ParticleImageBased(
            screen          = canvas,
            image           = animation[0].copy(),
            group           = group,
            camera          = camera,
            animation       = animation,
            animation_speed = animation_speed,
            rate            = rate,
            scale_speed     = scale_speed,
            alpha_speed     = alpha_speed,
            rotation_speed  = 0.0,
            spawn_rect      = spawn_rect,
        )

        # destructible particle in place
        animation = self.animations[self.type]
        self.particle_destruct = ParticleImageBased(
            screen          = canvas,
            image           = animation[0].copy(),
            group           = group,
            camera          = camera,
            animation       = animation,
            animation_speed = animation_speed,
            loop_animation  = False,
            rate            = rate,
            scale_speed     = 0.0,
            alpha_speed     = 0.0,
            rotation_speed  = 0.0,
        )
        self.custom_event_id = self.particle_left.custom_event_id

    ###################################################################################################################
    def add(self) -> None:
        move_speed = 300
        scale      = 5.0
        lifetime   = 0.60
        dir_span   = 60

        #  3 x left + 3 x right, leaf moves 300 pixels/seconds
        #  moves left +/- 120 degree, enlarge 5 x, kill after 0.6 a second
        for _ in range(3):
            self.particle_right.add_particles(
                # start_pos=pygame.mouse.get_pos(),
                move_speed = move_speed,
                move_dir   = 90 + random.randint(-dir_span, dir_span),
                scale      = scale,
                lifetime   = lifetime
            )

            self.particle_left.add_particles(
                # start_pos=pygame.mouse.get_pos(),
                move_speed = move_speed,
                move_dir   = 270 + random.randint(-dir_span, dir_span),
                scale      = scale,
                lifetime   = lifetime
            )

        # one time, in place
        self.particle_destruct.add_particles(
            start_pos  = self.spawn_rect.topleft,
            move_speed = 0.0,
            move_dir   =   0,
            scale      = 4.0,
            lifetime   = 0.8
        )

    ###################################################################################################################
    def emit(self, dt: float) -> None:
        self.particle_left.emit(dt)
        self.particle_right.emit(dt)
        self.particle_destruct.emit(dt)

    ###################################################################################################################
    def start(self) -> None:
        # one-shot system: add() is called directly on destruction, not driven by a
        # recurring timer, so there is nothing to arm here
        pass

    def stop(self) -> None:
        pass

#####################################################################################################################
# MARK: WeatherDirector


class WeatherDirector:
    """Schedules weather emitters as random episodes instead of running them constantly.

    Emitters are bucketed into named exclusivity groups (via EmitterSchedule.group).
    Within one group only a single emitter is active at a time - so `leafs` and `rain`
    (both group "sky") never overlap. Emitters in different groups run independently and
    may therefore play in parallel. Each group alternates between an idle phase (no
    emitter) and an active phase (one weighted-random emitter running for a random
    duration). Driven per-frame from Scene.update() via update(dt).
    """

    # short randomized delay before the very first episode of a group, so weather shows
    # up soon after entering a map instead of waiting a full (long) idle gap
    INITIAL_DELAY_MIN: float = 1.0
    INITIAL_DELAY_MAX: float = 6.0

    def __init__(
        self,
        systems: dict[str, ParticleSystem],
        schedules: "dict[str, EmitterSchedule]",
    ) -> None:
        # keep only emitters that have both a live system on this map and a schedule
        self.schedules = {name: schedules[name] for name in systems if name in schedules}
        self.systems = {name: systems[name] for name in self.schedules}

        # group -> list of emitter names in that group
        self.groups: dict[str, list[str]] = {}
        for name, sched in self.schedules.items():
            self.groups.setdefault(sched.group, []).append(name)

        # per-group runtime state: which emitter is active (or None = idle) + countdown
        self._active: dict[str, str | None] = {}
        self._timer: dict[str, float] = {}
        for group in self.groups:
            self._active[group] = None
            self._timer[group] = random.uniform(self.INITIAL_DELAY_MIN, self.INITIAL_DELAY_MAX)

    ###################################################################################################################
    def update(self, dt: float) -> None:
        for group, names in self.groups.items():
            self._timer[group] -= dt
            if self._timer[group] > 0.0:
                continue

            active = self._active[group]
            if active is not None:
                # active episode ended -> stop emitter, enter idle for a random gap
                self.systems[active].stop()
                self._active[group] = None
                sched = self.schedules[active]
                self._timer[group] = random.uniform(sched.gap_min, sched.gap_max)
            else:
                # idle ended -> pick a weighted-random emitter and run it for a while
                chosen = self._pick(names)
                self.systems[chosen].start()
                self._active[group] = chosen
                sched = self.schedules[chosen]
                self._timer[group] = random.uniform(sched.active_min, sched.active_max)

    ###################################################################################################################
    def _pick(self, names: list[str]) -> str:
        weights = [self.schedules[name].weight for name in names]
        return random.choices(names, weights=weights, k=1)[0]

    ###################################################################################################################
    def pause(self) -> None:
        # temporarily disarm the running emitter's spawn timer WITHOUT losing the
        # schedule state (unlike stop_all). Used when the scene is backgrounded by a
        # menu/pause: while hidden, Scene.draw() -> emit() never runs, so particles
        # would never age; leaving the timer armed would pile up a backlog that bursts
        # all at once on resume.
        for active in self._active.values():
            if active is not None:
                self.systems[active].stop()

    ###################################################################################################################
    def resume(self) -> None:
        # re-arm whatever emitter was active before pause() (episode state is intact)
        for active in self._active.values():
            if active is not None:
                self.systems[active].start()

    ###################################################################################################################
    def stop_all(self) -> None:
        # disarm every active emitter (e.g. before a map change) so no timer leaks
        for group, active in self._active.items():
            if active is not None:
                self.systems[active].stop()
                self._active[group] = None
