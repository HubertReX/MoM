"""Filtry pory dnia, światła i ramka cutscenki - warstwa rysowana po scenie.

Moduł systemu wg B01 (D1): bezstanowe funkcje operujące na przekazanej scenie.
``get_lights`` jest czytane przez shadery w ``game.py``, więc ``Scene`` zachowuje
dla niego delegat (K3). Stałe kolorów i wymiary ekranu czytamy dynamicznie przez
``settings`` (K6) - rozdzielczość zmienia się w locie w ustawieniach.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

import settings
from settings import (
    _,
    BG_COLOR,
    CIRCLE_RADIUS,
    CUTSCENE_BG_COLOR,
    DAY_FILTER,
    FILTER_SCALE,
    FONT_SIZE_MEDIUM,
    NIGHT_FILTER,
    TEXT_ROW_SPACING,
    ZOOM_LEVEL,
    to_vector,
    tuple_to_vector,
    vec,
    vec3,
)

if TYPE_CHECKING:
    from scene.scene import Scene


def apply_time_of_day_filter(scene: "Scene", screen: pygame.Surface) -> None:
    # MARK: apply_time_of_day_filter
    # do not apply night and day filter indoors
    if not scene.outdoor and not scene.is_maze:
        return

    filter = list(BG_COLOR)
    hour: float = scene.hour + (scene.minute / 60)

    if scene.is_maze:
        filter = list(NIGHT_FILTER)
    else:
        if hour < 6 or hour >= 20:
            filter = list(NIGHT_FILTER)
        elif 6 <= hour < 9:
            weight = (hour - 6) / (9 - 6)
            for i in range(4):
                filter[i] = pygame.math.lerp(NIGHT_FILTER[i], DAY_FILTER[i], weight)  # type: ignore[call-overload]
        elif 9 <= hour < 17:
            filter = list(DAY_FILTER)
        elif 17 <= hour < 20:
            weight = (hour - 17) / (20 - 17)
            for i in range(4):
                filter[i] = pygame.math.lerp(DAY_FILTER[i], NIGHT_FILTER[i], weight)  # type: ignore[call-overload]

    scene.filter_surf.fill(filter)

    if (hour > 17 or hour < 9) or scene.is_maze:
        scale = (scene.camera.zoom / ZOOM_LEVEL)
        for npc in scene.NPCs + [scene.player]:
            pos = scene.map_view.translate_point(npc.pos + vec(0, -8))
            pos_vec = (tuple_to_vector(pos) / FILTER_SCALE) - vec(CIRCLE_RADIUS, CIRCLE_RADIUS) * scale
            scene.filter_surf.blit(
                # scene.b_and_w_circle,
                pygame.transform.scale_by(scene.b_and_w_circle, scale),
                pos_vec,
                special_flags=pygame.BLEND_RGBA_MIN)

        if "intro" in scene.waypoints:
            scale = 2 * (scene.camera.zoom / ZOOM_LEVEL)
            village_pos = to_vector(scene.waypoints["intro"][0])
            pos = scene.map_view.translate_point(village_pos + vec(0, 0))
            pos_vec = (tuple_to_vector(pos) / FILTER_SCALE) - vec(CIRCLE_RADIUS, CIRCLE_RADIUS) * scale
            scene.filter_surf.blit(
                pygame.transform.scale_by(scene.b_and_w_circle, scale),
                pos_vec,
                special_flags=pygame.BLEND_RGBA_MIN)

            village_pos = to_vector(scene.waypoints["intro"][-1])
            pos = scene.map_view.translate_point(village_pos)
            pos_vec = (tuple_to_vector(pos) / FILTER_SCALE) - vec(CIRCLE_RADIUS, CIRCLE_RADIUS) * scale
            scene.filter_surf.blit(
                pygame.transform.scale_by(scene.b_and_w_circle, scale),
                pos_vec,
                special_flags=pygame.BLEND_RGBA_MIN)

    screen.blit(pygame.transform.scale(scene.filter_surf, (settings.WIDTH, settings.HEIGHT)))  # FILTER_SCALE
    # print(screen.get_bitsize(), scene.filter_surf.get_bitsize())
    # pygame.transform.scale(scene.filter_surf, (WIDTH, HEIGHT), screen)  # FILTER_SCALE


def get_lights(scene: "Scene") -> tuple[list[vec3], float]:
    # return list of light source coordinates with sizes and day/night ratio as float
    # in range [0.0, 1.0] (0.0 ==> day)
    light_sources: list[vec3] = []
    ratio: float = 0.0

    # indoors it's always day except mazes
    # no light sources
    if not scene.outdoor and not scene.is_maze:
        ratio = 0.0
    else:
        # in maze it's always night
        if scene.is_maze:
            ratio = 1.0
        else:
            hour: float = scene.hour + (scene.minute / 60)
            if hour < 6.00 or hour >= 20.00:
                ratio = 1.0
            elif 6.00 <= hour < 9.00:
                ratio = 1.0 - ((hour - 6.00) / (9.00 - 6.00))
                # for i in range(4):
                #     filter[i] = pygame.math.lerp(NIGHT_FILTER[i], DAY_FILTER[i], weight)
            elif 9.00 <= hour < 17.00:
                ratio = 0.0
            else:
                ratio = (hour - 17.00) / (20.00 - 17.00)
        # if it's not full day add light sources
        if ratio > 0.0:
            for npc in scene.NPCs + [scene.player]:
                pos = scene.map_view.translate_point(npc.pos + vec(0, -8))
                # pos_list = scene.map_view.translate_point(npc.pos + vec(0, -8))
                light = vec3(pos[0], settings.HEIGHT - pos[1], 64.0)
                light_sources.append(light)
                # pygame.draw.circle(filter_surf, DAY_FILTER, pos, 196)
            if "intro" in scene.waypoints:
                get_light_from_intro(scene, light_sources)
                # pygame.draw.circle(filter_surf, DAY_FILTER, pos, 256)

    return (light_sources, ratio)


def get_light_from_intro(scene: "Scene", light_sources: list[vec3]) -> None:
    village_pos = scene.waypoints["intro"][0].as_vector
    pos = scene.map_view.translate_point(village_pos + vec(0, 0))
    light = vec3(pos[0], settings.HEIGHT - pos[1], 64.0)
    light_sources.append(light)

    village_pos = scene.waypoints["intro"][-1].as_vector
    pos = scene.map_view.translate_point(village_pos + vec(0, 0))
    light = vec3(pos[0], settings.HEIGHT - pos[1], 64.0)
    light_sources.append(light)


def apply_alpha_filter(scene: "Scene", screen: pygame.Surface) -> None:
    # MARK: apply_alpha_filter
    h = settings.HEIGHT // 2
    scene.game.render_text(_("scene.day_label"),   (0, int(h - FONT_SIZE_MEDIUM * TEXT_ROW_SPACING)))
    scene.game.render_text(_("scene.night_label"), (0, int(h +                    TEXT_ROW_SPACING)))

    # sunny, warm yellow light during daytime
    half_screen = pygame.Surface((settings.WIDTH, h), pygame.SRCALPHA)
    half_screen.fill(DAY_FILTER)
    screen.blit(half_screen, (0, 0))

    # cold, dark and bluish light at night
    half_screen.fill(NIGHT_FILTER)
    screen.blit(half_screen, (0, h))


def apply_cutscene_framing(scene: "Scene", screen: pygame.Surface, percentage: float) -> None:
    # MARK: apply_cutscene_framing
    if percentage <= 0.001:
        return

    surface_h = settings.HEIGHT // 2
    framing_h = int(settings.HEIGHT * 0.1)
    framing_offset = int(framing_h * percentage)
    half_screen = pygame.Surface((settings.WIDTH, surface_h), pygame.SRCALPHA)
    half_screen.fill(CUTSCENE_BG_COLOR)
    # blit a black rect at the top of the screen
    screen.blit(half_screen, (0, -surface_h + framing_offset))
    # blit a black rect at the bottom of the screen
    screen.blit(half_screen, (0, settings.HEIGHT - framing_offset))

#############################################################################################################
