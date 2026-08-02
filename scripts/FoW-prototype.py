#!/usr/bin/env python3
"""E03 - PRÓBKA mgły wojny w labiryncie (do oceny wizualnej, nie kod produkcyjny).

Prototyp buduje PRAWDZIWY labirynt tym samym kodem co gra (`HuntAndKillMaze` +
`build_tileset_map_from_maze` + `pyscroll` + zoom `ZOOM_LEVEL`), więc to, co widać
na ekranie, to realny wygląd mechaniki - nie makieta.

Cel: porównać na żywo cztery warianty widoczności i dwa style krawędzi, zanim
powstanie kod produkcyjny (etap 1 zadania E03).

Uruchomienie (z katalogu repo):

    just fow-prototype
    just fow-prototype --level 3 --seed 42

Zrzuty bez okna (do dokumentu; UWAGA: zrzut headless nie jest w 100% wierny -
ocena końcowa musi być na realnym ekranie):

    just fow-prototype --shots doc/_attachements/fog

Sterowanie (opisane też w HUD na górze ekranu):

    strzałki / WSAD  - ruch
    F                - tryb widoczności: off / radius / shadowcast / raycast
    G                - pamięć: hard (nearest) / soft (smoothscale)
    B                - skalowanie nakładki na ekran: nearest / smooth
    [ ]              - zasięg wzroku -/+ (w kaflach)
    , .              - alfa pamięci (odkryte, poza wzrokiem) -/+ o 5
    L                - aureola światła z gry (nieprzycinana ścianami) on/off
    M                - podgląd całej mapy (zoom out) - kontrola, ile już odkryto
    R                - nowy labirynt (nowy seed)
    1..4             - poziom labiryntu (rozmiar siatki z maze_configs.csv)
    C                - wyczyść pamięć odkrycia
    S                - zrzut ekranu do screenshots/
    ESC / Q          - wyjście

Kluczowa właściwość architektoniczna (warunek twardy z E03): mgła NIE dokłada
drugiego pełnoekranowego `transform.scale`. Cała mgła powstaje w tej samej
powierzchni 1/FILTER_SCALE co filtr nocy, z maski o rozdzielczości JEDNEGO PIKSELA
NA KAFEL - skalowanej z rozmiaru widoku (~24x14 px) do 160x90 px. To jest tańsze
niż cokolwiek, co gra robi dziś w klatce.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "project"))

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pyscroll  # noqa: E402
import pyscroll.data  # noqa: E402
import settings  # noqa: E402
from maze_generator.hunt_and_kill_maze import HuntAndKillMaze  # noqa: E402
from maze_generator.maze_utils import (  # noqa: E402
    MARGIN,
    SUBTILE_COLS,
    SUBTILE_ROWS,
    analyze_maze,
    build_tileset_map_from_maze,
)
from pytmx.util_pygame import load_pygame  # noqa: E402

TILE = settings.TILE_SIZE
FILTER_SCALE = settings.FILTER_SCALE

# Trzy stany widoczności = trzy wartości alfy w JEDNEJ masce (kolor stały).
# Punkt odniesienia: dzisiejszy `NIGHT_FILTER` ma alfę 230, czyli CAŁY labirynt
# wygląda dziś tak, jak tu wygląda stan "odkryte, poza wzrokiem".
ALPHA_UNSEEN = 255        # nigdy nie widziane - czerń bez tilesetu
ALPHA_REMEMBERED = 230    # odkryte, poza zasięgiem wzroku (pamięć gracza)
ALPHA_CLEAR = 0           # bez przyciemnienia - rdzeń pola widzenia
ALPHA_VISIBLE_EDGE = 175  # w zasięgu wzroku, na granicy zasięgu
FOG_COLOR = (0, 0, 30)    # ten sam odcień co NIGHT_FILTER

# Rdzeń bez przyciemnienia, wspólny pomysł dla obu rodzin trybów, ale w innym
# rozmiarze - bo inaczej wypada wizualnie przy takim samym zasięgu:
#  - kafelkowe (radius/shadowcast): 3 kafle, gradient dopiero POWYŻEJ tej odległości,
#  - raycast: połowa dzisiejszej aureoli z gry (CIRCLE_RADIUS to ok. 3,2 kafla),
#    czyli 1,6 kafla - dzięki temu pierścienie gradientu zaczynają się NA ZEWNĄTRZ
#    rdzenia i widać ich skok, zamiast być przykryte jednolitą plamą światła.
CLEAR_TILES_GRID = 3.0
CLEAR_TILES_RAYCAST = (settings.CIRCLE_RADIUS * settings.FILTER_SCALE
                       / settings.ZOOM_LEVEL / settings.TILE_SIZE) / 2.0
# liczba pierścieni gradientu między rdzeniem a granicą zasięgu (tryb raycast)
RING_COUNT = 5

MODES = ["off (today's night)", "radius (no LOS)", "shadowcast (tiles)", "raycast (polygon)"]

# HUD: klawisz / etykieta / wybrana wartość / liczba pomiarowa
C_KEY = (255, 196, 84)
C_LABEL = (176, 180, 190)
C_VALUE = (124, 226, 172)
C_NUMBER = (140, 186, 255)

# ile promieni w trybie raycast - 180 to co 2 stopnie, wystarcza przy zasięgu ~8 kafli
RAY_COUNT = 180


#################################################################################################################
def read_maze_configs() -> dict[int, tuple[int, int]]:
    """{poziom: (kolumny, wiersze)} z tego samego CSV, z którego czyta gra."""
    path = REPO_ROOT / "project" / "config_model" / "maze_configs.csv"
    out: dict[int, tuple[int, int]] = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter=";"):
            out[int(row["key"])] = (int(row["maze_cols"]), int(row["maze_rows"]))
    return out


#################################################################################################################
class FogGrid:
    """Stan odkrycia i widoczności na siatce KAFLI mapy labiryntu.

    Reprezentacja celowo najprostsza z możliwych: dwie tablice bajtów o rozmiarze
    mapy w kaflach (78x60 = 4680 pól dla poziomu 4). Dzięki temu maska do rysowania
    jest tym samym obiektem co dane - nie ma osobnej konwersji per klatka.
    """

    def __init__(self, blocked: list[list[bool]]) -> None:
        self.blocked = blocked
        self.h = len(blocked)
        self.w = len(blocked[0])
        self.discovered: set[tuple[int, int]] = set()
        self.visible: set[tuple[int, int]] = set()
        # alfa per widoczny kafel (gaśnięcie z odległością) - tryby kafelkowe
        self.vis_alpha: dict[tuple[int, int], int] = {}
        self._last_visible: set[tuple[int, int]] = set()
        # maska 1 piksel = 1 kafel; skalowana per klatka do rozmiaru filtra
        self.mask = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        self.mask.fill((*FOG_COLOR, ALPHA_UNSEEN))
        # tryb raycast: pozycja obserwatora + dystans trafienia dla każdego promienia
        self.ray_origin: tuple[float, float] = (0.0, 0.0)
        self.ray_dist: list[float] = []

    def clear(self) -> None:
        self.discovered.clear()
        self.visible.clear()
        self.vis_alpha.clear()
        self._last_visible.clear()
        self.ray_dist.clear()
        self.mask.fill((*FOG_COLOR, ALPHA_UNSEEN))

    def is_wall(self, x: int, y: int) -> bool:
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.blocked[y][x]
        return True

    # ---------------------------------------------------------------- widoczność

    def compute_radius(self, cx: int, cy: int, radius: int) -> None:
        """Najtańszy wariant: koło w kaflach, bez sprawdzania ścian.

        Odkrywa też kafle za ścianą - w labiryncie o korytarzach szerokości
        jednego kafla to widać od razu (gracz "prześwietla" ściany).
        """
        vis: set[tuple[int, int]] = set()
        r_sq = radius * radius
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= r_sq:
                    x, y = cx + dx, cy + dy
                    if 0 <= x < self.w and 0 <= y < self.h:
                        vis.add((x, y))
        self.visible = vis
        self._grade(cx, cy, radius)

    def compute_shadowcast(self, cx: int, cy: int, radius: int) -> None:
        """Klasyczny recursive shadowcasting - raycast policzony na siatce kafli.

        Rezultat jest zbiorem kafli, więc krawędź cienia biegnie po kaflach
        (styl "kafelkowy"). Kosztuje ułamek milisekundy i liczy się tylko przy
        zmianie kafla gracza.
        """
        vis: set[tuple[int, int]] = {(cx, cy)}
        for oct_i in range(8):
            self._cast_light(vis, cx, cy, 1, 1.0, 0.0, radius,
                             _MULT[0][oct_i], _MULT[1][oct_i], _MULT[2][oct_i], _MULT[3][oct_i])
        self.visible = vis
        self._grade(cx, cy, radius)

    def _grade(self, cx: int, cy: int, radius: int) -> None:
        """Alfa widocznych kafli: rdzeń bez przyciemnienia + gradient do granicy.

        Do ``CLEAR_TILES_GRID`` kafli od gracza obraz jest nietknięty (alfa 0) -
        tak jak dziś w środku aureoli. Dopiero POWYŻEJ tej odległości zaczyna się
        gaśnięcie do ``ALPHA_VISIBLE_EDGE``. Bez rdzenia widoczność ma krawędź jak
        nożem uciętą i wygląda jak reflektor, a nie jak zasięg wzroku.
        """
        span = ALPHA_VISIBLE_EDGE - ALPHA_CLEAR
        ramp = max(0.001, radius - CLEAR_TILES_GRID)
        alpha: dict[tuple[int, int], int] = {}
        for (x, y) in self.visible:
            d = math.hypot(x - cx, y - cy)
            if d <= CLEAR_TILES_GRID:
                alpha[(x, y)] = ALPHA_CLEAR
            else:
                t = min(1.0, (d - CLEAR_TILES_GRID) / ramp)
                alpha[(x, y)] = ALPHA_CLEAR + int(span * t ** 1.4)
        self.vis_alpha = alpha

    def _cast_light(self, vis: set[tuple[int, int]], cx: int, cy: int, row: int,
                    start: float, end: float, radius: int,
                    xx: int, xy: int, yx: int, yy: int) -> None:
        if start < end:
            return
        radius_sq = radius * radius
        blocked_flag = False
        new_start = start
        for j in range(row, radius + 1):
            dx, dy = -j - 1, -j
            blocked_flag = False
            while dx <= 0:
                dx += 1
                x, y = cx + dx * xx + dy * xy, cy + dx * yx + dy * yy
                l_slope = (dx - 0.5) / (dy + 0.5)
                r_slope = (dx + 0.5) / (dy - 0.5)
                if start < r_slope:
                    continue
                if end > l_slope:
                    break
                if dx * dx + dy * dy <= radius_sq and 0 <= x < self.w and 0 <= y < self.h:
                    vis.add((x, y))
                if blocked_flag:
                    if self.is_wall(x, y):
                        new_start = r_slope
                        continue
                    blocked_flag = False
                    start = new_start
                elif self.is_wall(x, y) and j < radius:
                    blocked_flag = True
                    self._cast_light(vis, cx, cy, j + 1, start, l_slope, radius, xx, xy, yx, yy)
                    new_start = r_slope
            if blocked_flag:
                break

    def compute_raycast(self, px: float, py: float, radius_px: float) -> None:
        """Wielokąt widzenia w pikselach świata: RAY_COUNT promieni + DDA po kaflach.

        Różnica wobec shadowcastu: krawędź cienia jest gładka i liczona w pikselach,
        więc zza rogu wychyla się wąski klin światła, a nie schodkowy zbiór kafli.
        To wariant "ładniejszy i droższy" z opisu zadania.
        """
        vis: set[tuple[int, int]] = set()
        dists: list[float] = []
        step = TILE * 0.34  # krok próbkowania - 1/3 kafla wystarcza przy 16 px
        for i in range(RAY_COUNT):
            dx, dy = _COS[i], _SIN[i]
            dist = 0.0
            while dist < radius_px:
                dist += step
                tx, ty = int((px + dx * dist) // TILE), int((py + dy * dist) // TILE)
                vis.add((tx, ty))
                if self.is_wall(tx, ty):
                    break
            dists.append(dist)
        self.visible = vis
        self.vis_alpha = {}
        self.ray_origin = (px, py)
        self.ray_dist = dists

    # ---------------------------------------------------------------- maska

    def commit(self, memory_alpha: int, bright: bool) -> None:
        """Wpisz bieżącą widoczność do maski (i do pamięci odkrycia).

        Trzy stany zapisane jako trzy wartości alfy w jednej powierzchni:
        nieodkryte zostaje 255, odkryte spada do ``memory_alpha``, widoczne do
        wartości z ``vis_alpha``. Zapis jest per kafel i tylko przy zmianie
        widoczności. ``bright=False`` (raycast) wpisuje wyłącznie pamięć - jasność
        pola widzenia rysuje wtedy wielokąt, z dokładnością do piksela.
        """
        mask = self.mask
        # 1. skasuj poprzednią widoczność do poziomu pamięci
        for (x, y) in self._last_visible:
            if (x, y) not in self.visible:
                mask.set_at((x, y), (*FOG_COLOR, memory_alpha))
        # 2. wpisz nową
        for (x, y) in self.visible:
            if 0 <= x < self.w and 0 <= y < self.h:
                a = self.vis_alpha.get((x, y), ALPHA_CLEAR) if bright else memory_alpha
                mask.set_at((x, y), (*FOG_COLOR, a))
        self.discovered |= self.visible
        self._last_visible = set(self.visible) if bright else set()

    def refill_memory(self, memory_alpha: int) -> None:
        """Przemaluj pamięć po zmianie suwaka jasności (tylko prototyp)."""
        for (x, y) in self.discovered:
            if (x, y) not in self.visible:
                self.mask.set_at((x, y), (*FOG_COLOR, memory_alpha))


_MULT = [
    [1, 0, 0, -1, -1, 0, 0, 1],
    [0, 1, -1, 0, 0, -1, 1, 0],
    [0, 1, 1, 0, 0, -1, -1, 0],
    [1, 0, 0, 1, -1, 0, 0, -1],
]

_COS = [math.cos(6.283185307179586 * i / RAY_COUNT) for i in range(RAY_COUNT)]
_SIN = [math.sin(6.283185307179586 * i / RAY_COUNT) for i in range(RAY_COUNT)]


#################################################################################################################
class Prototype:
    def __init__(self, level: int, seed: int | None, headless: bool) -> None:
        self.headless = headless
        pygame.init()
        flags = 0
        self.screen = pygame.display.set_mode((settings.WIDTH, settings.HEIGHT), flags)
        pygame.display.set_caption("MoM - E03 proba mgly wojny (raycast)")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 22)

        self.configs = read_maze_configs()
        self.level = level
        self.seed = seed if seed is not None else random.randint(0, 2**31 - 1)

        # parametry do pokręcenia na żywo (domyślne = ustawienia zaakceptowane
        # przez autora przy pierwszej ocenie prototypu)
        self.mode = 3               # domyślnie raycast - to jest przedmiot oceny
        self.soft_edges = False     # pamięć: ostra (nearest)
        self.vision_tiles = 4
        self.memory_alpha = ALPHA_REMEMBERED
        # dzisiejsza aureola z gry - domyślnie WYŁĄCZONA w trybach mgły, bo świeci
        # przez ściany; [L] włącza ją do porównania z rdzeniem raycastu
        self.show_light = False
        self.smooth_upscale = False
        self.map_overview = False

        # bufory jak w grze (E01): filtr w 1/FILTER_SCALE + bufor pełnoekranowy
        self.filter_surf = pygame.Surface(
            (settings.WIDTH // FILTER_SCALE, settings.HEIGHT // FILTER_SCALE), pygame.SRCALPHA)
        self.filter_full = pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)
        self.b_and_w_circle = pygame.Surface(
            (2 * settings.CIRCLE_RADIUS, 2 * settings.CIRCLE_RADIUS), pygame.SRCALPHA)
        self.b_and_w_circle.fill((255, 255, 255, 255))
        pygame.draw.circle(self.b_and_w_circle, settings.DAY_FILTER,
                           (settings.CIRCLE_RADIUS, settings.CIRCLE_RADIUS), settings.CIRCLE_RADIUS)

        self.t_fog = 0.0        # ms - liczenie widoczności
        self.t_compose = 0.0    # ms - złożenie nakładki na klatkę
        self.build_level()

    # ---------------------------------------------------------------- budowa mapy

    def build_level(self) -> None:
        cols, rows = self.configs.get(self.level, self.configs[max(self.configs)])
        rng = random.Random(self.seed)
        maze = HuntAndKillMaze(cols, rows)
        maze.generate(rng)
        stats: dict[str, Any] = analyze_maze(maze)
        stats["current_map_level"] = self.level
        stats["max_level"] = len(self.configs)

        tmx = load_pygame(str(settings.MAZE_DIR / "MazeTileset_Ninja.tmx"))
        build_tileset_map_from_maze(tmx, maze, stats, f"Maze_{self.level:02}",
                                    to_map="Village", entry_point="MazeEntry", rng=rng)
        self.tmx = tmx
        self.maze = maze
        self.stats = stats

        self.map_view = pyscroll.BufferedRenderer(
            data=pyscroll.data.TiledMapData(tmx),
            size=(settings.WIDTH, settings.HEIGHT),
            clamp_camera=True,
        )
        self.map_view.zoom = 1.0 if self.map_overview else settings.ZOOM_LEVEL

        walls = tmx.get_layer_by_name("walls")
        blocked = [[bool(gid) for gid in row] for row in walls.data]
        self.fog = FogGrid(blocked)

        # start gracza tam, gdzie gra go stawia (kafel wejścia na poziom)
        sx, sy = stats["start"]
        self.px = float((MARGIN + sx * SUBTILE_COLS + SUBTILE_COLS // 2) * TILE)
        self.py = float((MARGIN + sy * SUBTILE_ROWS + SUBTILE_ROWS // 2) * TILE)
        self.recompute_fog(force=True)

    # ---------------------------------------------------------------- logika

    def walkable(self, x: float, y: float) -> bool:
        tx, ty = int(x // TILE), int(y // TILE)
        return not self.fog.is_wall(tx, ty)

    def move(self, dt: float, keys: pygame.key.ScancodeWrapper) -> bool:
        speed = 90.0 * dt
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        if not dx and not dy:
            return False
        nx, ny = self.px + dx * speed, self.py + dy * speed
        moved = False
        if self.walkable(nx, self.py):
            self.px, moved = nx, True
        if self.walkable(self.px, ny):
            self.py, moved = ny, True
        return moved

    def recompute_fog(self, force: bool = False) -> None:
        """Policz widoczność. Modele kafelkowe - tylko przy zmianie kafla."""
        t0 = time.perf_counter()
        tx, ty = int(self.px // TILE), int(self.py // TILE)
        last = getattr(self, "_last_tile", None)
        if self.mode == 0:
            self.fog.visible = set()
        elif self.mode == 1:
            if force or (tx, ty) != last:
                self.fog.compute_radius(tx, ty, self.vision_tiles)
        elif self.mode == 2:
            if force or (tx, ty) != last:
                self.fog.compute_shadowcast(tx, ty, self.vision_tiles)
        else:
            # raycast liczy się w pikselach, więc odświeżamy przy każdym ruchu
            self.fog.compute_raycast(self.px, self.py, self.vision_tiles * TILE)
        self._last_tile = (tx, ty)
        if self.mode:
            self.fog.commit(self.memory_alpha, bright=self.mode != 3)
        self.t_fog = (time.perf_counter() - t0) * 1000.0

    # ---------------------------------------------------------------- rysowanie

    def compose_fog(self, screen: pygame.Surface) -> None:
        """Nakładka mgły + nocy, JEDNA powierzchnia, JEDNO skalowanie na pełny ekran.

        Dokładnie tyle pracy, ile robi dziś sam filtr nocy: mgła dokłada tylko
        wycięcie fragmentu maski (78x60 px) i przeskalowanie go do 160x90 px.
        """
        t0 = time.perf_counter()
        fs = self.filter_surf
        if self.mode == 0:
            fs.fill(settings.NIGHT_FILTER)
        else:
            # obszar świata widoczny na ekranie, w kaflach - z niego wycinamy maskę
            view = self.map_view.view_rect  # prostokąt świata w pikselach
            t_x0 = view.left / TILE
            t_y0 = view.top / TILE
            t_w = view.width / TILE
            t_h = view.height / TILE
            # wycinek maski + margines 1 kafla, żeby skalowanie nie ucinało brzegu
            src = pygame.Rect(int(t_x0), int(t_y0), int(t_w) + 2, int(t_h) + 2)
            src = src.clip(pygame.Rect(0, 0, self.fog.w, self.fog.h))
            piece = self.fog.mask.subsurface(src)
            # px na kafel w powierzchni filtra
            zoom = self.map_view.zoom
            ppt = (TILE * zoom) / FILTER_SCALE
            target = (max(1, int(src.width * ppt)), max(1, int(src.height * ppt)))
            scaler = pygame.transform.smoothscale if self.soft_edges else pygame.transform.scale
            scaled = scaler(piece, target)
            fs.fill((*FOG_COLOR, ALPHA_UNSEEN))
            off_x = (src.x * TILE - view.left) * zoom / FILTER_SCALE
            off_y = (src.y * TILE - view.top) * zoom / FILTER_SCALE
            # BLEND_RGBA_MIN, nie zwykły blit: tło jest już wypełnione "nieodkryte"
            # (alfa 255), a maska ma alfy MNIEJSZE - zwykły blit by je zmieszał
            # z tłem zamiast podmienić. Przy okazji obszar poza mapą zostaje czarny.
            fs.blit(scaled, (off_x, off_y), special_flags=pygame.BLEND_RGBA_MIN)

            if self.mode == 3 and self.fog.ray_dist:
                self._draw_vision_polygons(fs)

        if self.show_light:
            # Bez przesunięcia (0, -8), które gra stosuje, żeby światło siedziało
            # na tułowiu postaci - tutaj gracz to kropka, więc offset czytało się
            # jako źle wycentrowaną aureolę.
            sx, sy = self.map_view.translate_point((self.px, self.py))
            pos = (sx / FILTER_SCALE - settings.CIRCLE_RADIUS,
                   sy / FILTER_SCALE - settings.CIRCLE_RADIUS)
            fs.blit(self.b_and_w_circle, pos, special_flags=pygame.BLEND_RGBA_MIN)

        # Ostatni krok jest identyczny jak w grze (E01, tryb "overlay"): JEDNO
        # skalowanie filtra na pełny ekran + jeden blit. `smoothscale` wygładza
        # krawędzie wielokąta widzenia (bez niego 8x powiększenie daje schodki
        # po 8 px); koszt na desktopie w HUD, na web trzeba go zmierzyć osobno.
        scaler = pygame.transform.smoothscale if self.smooth_upscale else pygame.transform.scale
        scaler(fs, (settings.WIDTH, settings.HEIGHT), self.filter_full)
        screen.blit(self.filter_full, (0, 0))
        self.t_compose = (time.perf_counter() - t0) * 1000.0

    def _draw_vision_polygons(self, fs: pygame.Surface) -> None:
        """Pole widzenia jako kilka zagnieżdżonych wielokątów = gradient jasności.

        Każdy wielokąt to te same promienie ucięte na ``min(ściana, k * zasięg)``.
        Uwaga na pułapkę: przy ``dystans_do_ściany * k`` (pierwsza wersja) wszystkie
        pierścienie kurczą się tam, gdzie blisko jest ściana, więc środek gradientu
        ucieka od ściany i wygląda jak źle wycentrowana aureola. Z ``min(...)``
        pierścienie są współśrodkowe z graczem, a ściana je po prostu ucina.

        Rdzeń (aureola) to ostatni, najmniejszy wielokąt z alfą 0 - przycinany
        ścianami tak samo jak reszta, więc nie przecieka za róg. Pierścienie
        gradientu zaczynają się NA ZEWNĄTRZ rdzenia i dzielą resztę zasięgu
        proporcjonalnie, żeby aureola ich nie przykrywała.
        """
        zoom = self.map_view.zoom
        ox, oy = self.map_view.translate_point(self.fog.ray_origin)
        radius_px = self.vision_tiles * TILE
        core_px = min(CLEAR_TILES_RAYCAST * TILE, radius_px * 0.8)
        core_k = core_px / radius_px
        span = ALPHA_VISIBLE_EDGE - ALPHA_CLEAR
        for i in range(RING_COUNT, 0, -1):
            k = core_k + (1.0 - core_k) * i / RING_COUNT
            self._draw_ring(fs, ox, oy, zoom, k * radius_px,
                            ALPHA_CLEAR + int(span * k ** 1.4))
        self._draw_ring(fs, ox, oy, zoom, core_px, ALPHA_CLEAR)

    def _draw_ring(self, fs: pygame.Surface, ox: int, oy: int, zoom: float,
                   reach: float, alpha: int) -> None:
        pts = []
        for i, dist in enumerate(self.fog.ray_dist):
            d = dist if dist < reach else reach
            pts.append(((ox + _COS[i] * d * zoom) / FILTER_SCALE,
                        (oy + _SIN[i] * d * zoom) / FILTER_SCALE))
        pygame.draw.polygon(fs, (*FOG_COLOR, alpha), pts)

    def draw_player(self, screen: pygame.Surface) -> None:
        sx, sy = self.map_view.translate_point((self.px, self.py))
        pygame.draw.circle(screen, (240, 220, 120), (sx, sy), 9)
        pygame.draw.circle(screen, (30, 20, 10), (sx, sy), 9, 2)

    def draw_hud(self, screen: pygame.Surface) -> None:
        """HUD w segmentach (tekst, kolor): klawisz / etykieta / wartość / liczba.

        Trzy kolory zamiast jednej ściany tekstu - przy ośmiu przełącznikach
        czytanie "co jest teraz ustawione" ma być rzutem oka, nie parsowaniem.
        """
        cols, rows = self.configs.get(self.level, self.configs[max(self.configs)])
        pct = 100.0 * len(self.fog.discovered) / (self.fog.w * self.fog.h)
        k, la, v, n = C_KEY, C_LABEL, C_VALUE, C_NUMBER
        lines: list[list[tuple[str, tuple[int, int, int]]]] = [
            [("[F]", k), (" mode ", la), (MODES[self.mode], v),
             ("   [G]", k), (" memory ", la), ("hard" if not self.soft_edges else "soft", v),
             ("   [B]", k), (" upscale ", la), ("smooth" if self.smooth_upscale else "nearest", v)],
            [("[ [ ]", k), (" range ", la), (f"{self.vision_tiles} tiles", v),
             ("   [ , . ]", k), (" alpha ", la), (f"{self.memory_alpha}", v),
             ("   [L]", k), (" game halo ", la), ("on" if self.show_light else "off", v)],
            [("[1-4]", k), (" level ", la), (f"{self.level}", v),
             (f" ({cols}x{rows} cells = {self.fog.w}x{self.fog.h} tiles)", la),
             ("   [R]", k), (" seed ", la), (f"{self.seed}", v),
             ("   [C]", k), (" clear", la), ("   [M]", k), (" map overview", la)],
            [("fog ", la), (f"{self.t_fog:.2f} ms", n),
             ("   overlay ", la), (f"{self.t_compose:.2f} ms", n),
             ("   FPS ", la), (f"{self.clock.get_fps():.1f}", n),
             ("   discovered ", la), (f"{pct:.1f}%", n)],
        ]
        y = 6
        for segments in lines:
            rendered = [(self.font.render(text, True, color), color) for text, color in segments]
            width = sum(s.get_width() for s, _ in rendered)
            height = max(s.get_height() for s, _ in rendered)
            bg = pygame.Surface((width + 8, height + 2), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 170))
            screen.blit(bg, (4, y - 1))
            x = 8
            for surf, _color in rendered:
                screen.blit(surf, (x, y))
                x += surf.get_width()
            y += height + 2

    def draw(self) -> None:
        self.map_view.center((self.px, self.py))
        self.map_view.draw(self.screen, self.screen.get_rect())
        self.draw_player(self.screen)
        self.compose_fog(self.screen)
        self.draw_hud(self.screen)

    # ---------------------------------------------------------------- pętla

    def handle_key(self, key: int) -> bool:
        if key in (pygame.K_ESCAPE, pygame.K_q):
            return False
        if key == pygame.K_f:
            self.mode = (self.mode + 1) % len(MODES)
            # w trybie 0 (dzisiejsza gra) aureola JEST efektem, w trybach mgły
            # zastępuje ją gradient pola widzenia
            self.show_light = self.mode == 0
            self.recompute_fog(force=True)
        elif key == pygame.K_g:
            self.soft_edges = not self.soft_edges
        elif key == pygame.K_l:
            self.show_light = not self.show_light
        elif key == pygame.K_b:
            self.smooth_upscale = not self.smooth_upscale
        elif key == pygame.K_m:
            self.map_overview = not self.map_overview
            self.map_view.zoom = 1.0 if self.map_overview else settings.ZOOM_LEVEL
        elif key == pygame.K_RIGHTBRACKET:
            self.vision_tiles = min(24, self.vision_tiles + 1)
            self.recompute_fog(force=True)
        elif key == pygame.K_LEFTBRACKET:
            self.vision_tiles = max(2, self.vision_tiles - 1)
            self.recompute_fog(force=True)
        elif key == pygame.K_PERIOD:
            self.memory_alpha = max(ALPHA_VISIBLE_EDGE, self.memory_alpha - 5)
            self.fog.refill_memory(self.memory_alpha)
        elif key == pygame.K_COMMA:
            self.memory_alpha = min(255, self.memory_alpha + 5)
            self.fog.refill_memory(self.memory_alpha)
        elif key == pygame.K_c:
            self.fog.clear()
            self.recompute_fog(force=True)
        elif key == pygame.K_r:
            self.seed = random.randint(0, 2**31 - 1)
            self.build_level()
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            self.level = key - pygame.K_0
            self.build_level()
        elif key == pygame.K_s:
            out = REPO_ROOT / "screenshots" / f"FoW_{int(time.time())}.png"
            pygame.image.save(self.screen, str(out))
            print(f"[proto] zrzut: {out}")
        return True

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(settings.FPS_CAP) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = self.handle_key(event.key)
            if self.move(dt, pygame.key.get_pressed()):
                self.recompute_fog()
            self.draw()
            pygame.display.flip()
        pygame.quit()

    # ---------------------------------------------------------------- zrzuty

    def shots(self, out_dir: Path) -> None:
        """Przejdź skryptowo kilka kroków i zapisz porównawcze zrzuty."""
        out_dir.mkdir(parents=True, exist_ok=True)
        # przejdź kawałek korytarza, żeby powstała pamięć odkrycia
        for _ in range(600):
            for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                nx, ny = self.px + dx * 3, self.py + dy * 3
                if self.walkable(nx, ny):
                    self.px, self.py = nx, ny
                    break
            self.recompute_fog()
        for mode in range(4):
            self.mode = mode
            self.recompute_fog(force=True)
            for soft in (True, False):
                if mode == 0 and not soft:
                    continue
                self.soft_edges = soft
                self.draw()
                pygame.display.flip()
                name = f"fog_{mode}_{'soft' if soft else 'hard'}.png"
                pygame.image.save(self.screen, str(out_dir / name))
                print(f"[proto] {out_dir / name}  (mgla {self.t_fog:.2f} ms, nakladka {self.t_compose:.2f} ms)")
        pygame.quit()


#################################################################################################################
def main() -> None:
    ap = argparse.ArgumentParser(description="E03 - proba mgly wojny w labiryncie")
    ap.add_argument("--level", type=int, default=2, help="poziom labiryntu 1-4 (rozmiar siatki)")
    ap.add_argument("--seed", type=int, default=None, help="seed labiryntu")
    ap.add_argument("--shots", type=str, default=None, help="katalog na zrzuty (tryb bez interakcji)")
    args = ap.parse_args()

    headless = args.shots is not None
    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    proto = Prototype(args.level, args.seed, headless)
    if headless:
        proto.shots(Path(args.shots))
    else:
        proto.run()


if __name__ == "__main__":
    main()
