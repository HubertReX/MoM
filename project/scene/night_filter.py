"""Filtry pory dnia, światła i ramka cutscenki - warstwa rysowana po scenie.

Moduł systemu wg B01 (D1): bezstanowe funkcje operujące na przekazanej scenie.
``get_lights`` jest czytane przez shadery w ``game.py``, więc ``Scene`` zachowuje
dla niego delegat (K3). Stałe kolorów i wymiary ekranu czytamy dynamicznie przez
``settings`` (K6) - rozdzielczość zmienia się w locie w ustawieniach.

E01: jedna ścieżka kodu na desktop i web - w tym module nie ma i nie może być
gałęzi ``IS_WEB``. Żeby filtr zmieścił się w budżecie klatki na WASM, kosztowne
operacje są scache'owane:

- skalowane koła świateł (``_scaled_circle``) - bez cache było to ``scale_by``
  na KAŻDEGO NPC w KAŻDEJ klatce;
- bufor pełnoekranowy (``scene.filter_surf_full``) - ``transform.scale`` bez
  powierzchni docelowej alokował 3 MB co klatkę;
- pełny dzień (``ratio == 0``) kończy się natychmiastowym ``return`` - dawniej
  wypełniał i skalował całą powierzchnię, żeby nałożyć kolor o alfie 0.
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

from scene import fog_of_war

if TYPE_CHECKING:
    from scene.scene import Scene


# Kwantyzacja skali kół świateł. Zoom kamery zmienia się płynnie, więc bez
# zaokrąglenia cache nigdy by nie trafił; 0,05 to pół procenta promienia koła
# (48 px * 0,05 = 2,4 px na skali 1.0) - niewidoczne, a daje trafienia cache
# przez cały płynny zoom.
_SCALE_QUANT = 0.05
# {(szerokość koła, wysokość koła, skala): przeskalowane koło}. Rozmiar źródła
# jest w kluczu, bo `b_and_w_circle` jest budowane raz na scenę - gdyby kiedyś
# zmienił się CIRCLE_RADIUS, cache nie oddałby koła w złym rozmiarze.
_circle_cache: dict[tuple[int, int, float], pygame.Surface] = {}


def build_filter_surfaces(scene: "Scene") -> None:
    """(Prze)buduj bufory filtra pod bieżącą rozdzielczość.

    Wołane z ``Scene.__init__`` i ``Scene.on_resize`` - jedno miejsce, bo bufory
    są dwa i rozjechanie się ich przy zmianie rozdzielczości daje filtr rysowany
    w starym rozmiarze (albo wyjątek w ``transform.scale``).
    """
    w, h = settings.WIDTH, settings.HEIGHT
    scene.filter_surf = pygame.Surface((w // FILTER_SCALE, h // FILTER_SCALE), pygame.SRCALPHA)
    # docelowa powierzchnia dla skalowania na pełny ekran - alokowana raz,
    # nie co klatkę (E01)
    scene.filter_surf_full = pygame.Surface((w, h), pygame.SRCALPHA)
    # bufory trybu "overlay_half": klatka i filtr w połowie rozdzielczości.
    # Bufor klatki BEZ SRCALPHA - `transform.scale` wymaga zgodności formatu
    # ze źródłem (canvas gry), a canvas nie ma per-pixel alfy.
    scene.frame_surf_half = pygame.Surface((w // 2, h // 2))
    scene.filter_surf_half = pygame.Surface((w // 2, h // 2), pygame.SRCALPHA)


def _scaled_circle(circle: pygame.Surface, scale: float) -> tuple[pygame.Surface, float]:
    """Koło światła przeskalowane do (skwantyzowanej) ``scale``, z cache.

    Zwraca też użytą skalę - pozycja koła liczy się z niej, żeby po kwantyzacji
    światło zostało wyśrodkowane na postaci.
    """
    quant = round(round(scale / _SCALE_QUANT) * _SCALE_QUANT, 3)
    if quant <= 0.0:
        quant = _SCALE_QUANT
    key = (circle.get_width(), circle.get_height(), quant)
    scaled = _circle_cache.get(key)
    if scaled is None:
        scaled = pygame.transform.scale_by(circle, quant)
        _circle_cache[key] = scaled
    return scaled, quant


def _blit_light(scene: "Scene", world_pos: vec, scale: float) -> None:
    """Nałóż jedno źródło światła na ``scene.filter_surf`` (rozjaśnienie)."""
    circle, quant = _scaled_circle(scene.b_and_w_circle, scale)
    pos = scene.map_view.translate_point(world_pos)
    pos_vec = (tuple_to_vector(pos) / FILTER_SCALE) - vec(CIRCLE_RADIUS, CIRCLE_RADIUS) * quant
    scene.filter_surf.blit(circle, pos_vec, special_flags=pygame.BLEND_RGBA_MIN)


def filter_color(scene: "Scene") -> list[int]:
    """Kolor (RGBA) filtra pory dnia dla bieżącego stanu sceny."""
    color: list[int] = list(BG_COLOR)
    hour: float = scene.hour + (scene.minute / 60)

    if scene.is_maze:
        return list(NIGHT_FILTER)
    if hour < 6 or hour >= 20:
        return list(NIGHT_FILTER)
    if 6 <= hour < 9:
        weight = (hour - 6) / (9 - 6)
        for i in range(4):
            color[i] = pygame.math.lerp(NIGHT_FILTER[i], DAY_FILTER[i], weight)  # type: ignore[call-overload]
    elif 9 <= hour < 17:
        return list(DAY_FILTER)
    elif 17 <= hour < 20:
        weight = (hour - 17) / (20 - 17)
        for i in range(4):
            color[i] = pygame.math.lerp(DAY_FILTER[i], NIGHT_FILTER[i], weight)  # type: ignore[call-overload]
    return color


def apply_time_of_day_filter(scene: "Scene", screen: pygame.Surface) -> None:
    # MARK: apply_time_of_day_filter
    # do not apply night and day filter indoors
    if not scene.outdoor and not scene.is_maze:
        return

    # Pełny dzień: kolor filtra to DAY_FILTER z alfą 0 i nie ma świateł, więc
    # cała reszta funkcji jest no-opem - a kosztowała 0,49 ms z 1,28 ms `draw`
    # (fill + skalowanie na pełny ekran). Ten sam warunek co ratio == 0 dla shaderów.
    if day_night_ratio(scene) == 0.0:
        return

    color = filter_color(scene)
    # tryb czytany ŻYWO z modułu (K6) - to pokrętło do empirycznego testowania
    # na różnym sprzęcie, nie stała z importu
    mode = settings.NIGHT_FILTER_MODE
    # E03: w labiryncie z włączoną mgłą powierzchnia filtra NIE jest jednolita -
    # niesie maskę trzech stanów widoczności, a aureole zastępuje pole widzenia
    fog_on = fog_of_war.is_enabled(scene)
    if mode == "multiply" and not fog_on:
        _composite_multiply(screen, color)
        return

    if scene.filter_surf_full.get_size() != (settings.WIDTH, settings.HEIGHT):
        # rozdzielczość zmieniona poza `on_resize` (np. inna scena na stosie) -
        # bufory muszą pasować do ekranu, inaczej `transform.scale` rzuci wyjątek
        build_filter_surfaces(scene)

    if fog_on:
        fog_of_war.compose(scene, scene.filter_surf)
    else:
        scene.filter_surf.fill(color)

        hour: float = scene.hour + (scene.minute / 60)
        if (hour > 17 or hour < 9) or scene.is_maze:
            scale = (scene.camera.zoom / ZOOM_LEVEL)
            for npc in scene.NPCs + [scene.player]:
                _blit_light(scene, npc.pos + vec(0, -8), scale)

            if "intro" in scene.waypoints:
                scale = 2 * (scene.camera.zoom / ZOOM_LEVEL)
                _blit_light(scene, to_vector(scene.waypoints["intro"][0]) + vec(0, 0), scale)
                _blit_light(scene, to_vector(scene.waypoints["intro"][-1]), scale)

    # `multiply` nie czyta powierzchni filtra (to sam `fill(BLEND_RGB_MULT)`), więc
    # mgły nie da się w nim narysować - w labiryncie z mgłą kompozycja idzie
    # najtańszą ścieżką, która maskę honoruje
    if mode == "overlay_half" or (mode == "multiply" and fog_on):
        _composite_overlay_half(scene, screen)
    else:
        _composite_overlay(scene, screen)


def _composite_overlay(scene: "Scene", screen: pygame.Surface) -> None:
    """Wygląd referencyjny: alpha-blend filtra w pełnej rozdzielczości."""
    pygame.transform.scale(scene.filter_surf, (settings.WIDTH, settings.HEIGHT), scene.filter_surf_full)
    # `dest` jest OBOWIĄZKOWY: pygame w buildzie web jest starsze niż pygame-ce na
    # desktopie i jednoargumentowy blit kończy się tam `TypeError: function missing
    # required argument 'dest'` (wywrotka gry przy pierwszej klatce nocy)
    screen.blit(scene.filter_surf_full, (0, 0))


def _composite_overlay_half(scene: "Scene", screen: pygame.Surface) -> None:
    """Ten sam efekt, ale mieszany w połowie rozdzielczości.

    Na WASM koszt filtra to wyłącznie liczba pikseli mieszanych per-pixel-alfą,
    więc złożenie na ćwiartce powierzchni jest ~3x tańsze (5,8 -> 1,8 ms).
    Płacimy 2x grubszym pikselem świata na czas nocy; HUD i panele rysują się
    PO filtrze, więc zostają ostre.
    """
    half = scene.frame_surf_half
    size = half.get_size()
    pygame.transform.scale(screen, size, half)
    pygame.transform.scale(scene.filter_surf, size, scene.filter_surf_half)
    half.blit(scene.filter_surf_half, (0, 0))
    pygame.transform.scale(half, (settings.WIDTH, settings.HEIGHT), screen)


def _composite_multiply(screen: pygame.Surface, color: list[int]) -> None:
    """Najtańszy wariant: jeden mnożący `fill`, BEZ aureoli świateł.

    ``fill`` nie czyta ekranu, więc nie da się nim odtworzyć "dziur" po światłach -
    scena ciemnieje równomiernie, także wokół gracza. Mnożnik jest tak dobrany,
    żeby na białym tle dać ten sam kolor co alpha-blend: ``255*(1-w) + c*w``.
    """
    weight = color[3] / 255.0
    mult = tuple(int(255 * (1.0 - weight) + color[i] * weight) for i in range(3))
    screen.fill(mult, special_flags=pygame.BLEND_RGB_MULT)


def day_night_ratio(scene: "Scene") -> float:
    """Stopień nocy w [0.0, 1.0] (0.0 = pełny dzień) dla bieżącego stanu sceny.

    Jedno źródło prawdy dla filtra rastrowego i dla shaderów - wcześniej ten sam
    rozkład godzin był policzony dwa razy i mógł się rozjechać.
    """
    # indoors it's always day except mazes
    if not scene.outdoor and not scene.is_maze:
        return 0.0
    # in maze it's always night
    if scene.is_maze:
        return 1.0

    hour: float = scene.hour + (scene.minute / 60)
    if hour < 6.00 or hour >= 20.00:
        return 1.0
    if 6.00 <= hour < 9.00:
        return 1.0 - ((hour - 6.00) / (9.00 - 6.00))
    if 9.00 <= hour < 17.00:
        return 0.0
    return (hour - 17.00) / (20.00 - 17.00)


def get_lights(scene: "Scene") -> tuple[list[vec3], float]:
    # return list of light source coordinates with sizes and day/night ratio as float
    # in range [0.0, 1.0] (0.0 ==> day)
    light_sources: list[vec3] = []
    ratio: float = day_night_ratio(scene)

    # if it's not full day add light sources (ratio > 0 implies outdoor or maze)
    if ratio > 0.0:
        for npc in scene.NPCs + [scene.player]:
            pos = scene.map_view.translate_point(npc.pos + vec(0, -8))
            light = vec3(pos[0], settings.HEIGHT - pos[1], 64.0)
            light_sources.append(light)
        if "intro" in scene.waypoints:
            get_light_from_intro(scene, light_sources)

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
