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
    O P              - rdzeń bez przyciemnienia -/+ (tryby kafelkowe, w kaflach)
    - =              - ziarnistość gradientu -/+ (0 = płynnie); osobno dla trybów
                       kafelkowych i dla raycastu, bo dobra wartość jest inna
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
    IMAGE_DIRECTION_TO_CHEST,
    MARGIN,
    SUBTILE_COLS,
    SUBTILE_ROWS,
    analyze_maze,
    build_tileset_map_from_maze,
    clear_maze_cache,
    find_dead_ends,
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
#  - kafelkowe (radius/shadowcast): regulowane pod [O]/[P], gradient dopiero POWYŻEJ
#    tej odległości. Rdzeń zjada zasięg: przy rdzeniu 3 i zasięgu 4 na gradient
#    zostaje jeden kafel i gradacji nie widać - stąd domyślne 1,5.
#  - raycast: połowa dzisiejszej aureoli z gry (CIRCLE_RADIUS to ok. 3,2 kafla),
#    czyli 1,6 kafla - dzięki temu pierścienie gradientu zaczynają się NA ZEWNĄTRZ
#    rdzenia i widać ich skok, zamiast być przykryte jednolitą plamą światła.
CLEAR_TILES_GRID = 1.5
CLEAR_TILES_RAYCAST = (settings.CIRCLE_RADIUS * settings.FILTER_SCALE
                       / settings.ZOOM_LEVEL / settings.TILE_SIZE) / 2.0
# liczba pierścieni gradientu między rdzeniem a granicą zasięgu (tryb raycast)
RING_COUNT = 5
# ile pierścieni rysować, gdy ziarnistość ustawiona na "płynnie" (raycast nie umie
# gradientu inaczej niż wielokątami, więc "płynnie" = tyle, że skoku nie widać)
SMOOTH_RINGS = 16

MODES = ["off (today's night)", "radius (no LOS)", "shadowcast (tiles)", "raycast (polygon)"]

# HUD: klawisz / etykieta / wybrana wartość / liczba pomiarowa
C_KEY = (255, 196, 84)
C_LABEL = (176, 180, 190)
C_VALUE = (124, 226, 172)
C_NUMBER = (140, 186, 255)

Segment = tuple[str, tuple[int, int, int]]


def _key_segments(keys: str, label: str, value: str = "") -> list[Segment]:
    """``[klawisz] etykieta wartość`` w trzech kolorach.

    Nawiasy klamrowe MUSZĄ być w kolorze tekstu, a nie klawisza: skrót do zmiany
    zasięgu to nawiasy kwadratowe, więc pomarańczowe `[ [ ] ]` zlewało się w jedną
    plamę, w której nie dało się odróżnić ramki od klawiszy.
    """
    out: list[Segment] = [("  [", C_LABEL), (keys, C_KEY), ("] ", C_LABEL), (label, C_LABEL)]
    if value:
        out.append((f" {value}", C_VALUE))
    return out

# ile promieni w trybie raycast - 180 to co 2 stopnie, wystarcza przy zasięgu ~8 kafli
RAY_COUNT = 180


#################################################################################################################
def read_maze_configs() -> dict[int, tuple[int, int, int]]:
    """{poziom: (kolumny, wiersze, liczba małych skrzyń)} z CSV, z którego czyta gra."""
    path = REPO_ROOT / "project" / "config_model" / "maze_configs.csv"
    out: dict[int, tuple[int, int, int]] = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter=";"):
            out[int(row["key"])] = (int(row["maze_cols"]), int(row["maze_rows"]),
                                    int(row["small_chest_count"]))
    return out


def load_chest_images() -> dict[str, pygame.Surface]:
    """Zamknięte skrzynie z tego samego arkusza, którego używa `ChestSprite`.

    Gra tnie arkusz w `Scene.import_sheet`; tutaj wystarczą dwa kadry, więc
    powtarzam samo cięcie zamiast ciągnąć całą scenę i konfigurację.
    """
    sheet = pygame.image.load(str(settings.ITEMS_SHEET_FILE)).convert_alpha()
    out: dict[str, pygame.Surface] = {}
    for key in ("small_chest", "big_chest"):
        x, y = settings.ITEMS_SHEET_DEFINITION[key][0]
        out[key] = sheet.subsurface(pygame.Rect(x * TILE, y * TILE, TILE, TILE))
    return out


def _tile_entry(px: float, py: float, dx: float, dy: float, tx: int, ty: int) -> float:
    """Dystans, na którym promień (px,py)+t*(dx,dy) WCHODZI w kafel (tx,ty).

    Krok próbkowania promienia jest zgrubny (1/3 kafla), więc surowy dystans
    trafienia skacze między sąsiednimi promieniami i wielokąt dostaje ząbki.
    Dokładne przecięcie z krawędzią kafla daje gładki obrys.
    """
    small = -1e9
    if dx > 1e-9:
        ex = (tx * TILE - px) / dx
    elif dx < -1e-9:
        ex = ((tx + 1) * TILE - px) / dx
    else:
        ex = small
    if dy > 1e-9:
        ey = (ty * TILE - py) / dy
    elif dy < -1e-9:
        ey = ((ty + 1) * TILE - py) / dy
    else:
        ey = small
    return max(ex, ey)


def _is_pocket(solid: list[list[bool]], x: int, y: int) -> bool:
    """Kafel podłogi zamknięty ścianami z co najmniej trzech stron."""
    if solid[y][x]:
        return False
    h, w = len(solid), len(solid[0])
    walls = 0
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if not (0 <= nx < w and 0 <= ny < h) or solid[ny][nx]:
            walls += 1
    return walls >= 3


#################################################################################################################
class FogGrid:
    """Stan odkrycia i widoczności na siatce KAFLI mapy labiryntu.

    Reprezentacja celowo najprostsza z możliwych: dwie tablice bajtów o rozmiarze
    mapy w kaflach (78x60 = 4680 pól dla poziomu 4). Dzięki temu maska do rysowania
    jest tym samym obiektem co dane - nie ma osobnej konwersji per klatka.
    """

    def __init__(self, blocked: list[list[bool]], solid: list[list[bool]]) -> None:
        self.blocked = blocked
        # "solid" to wszystko, co nie jest korytarzem: kafel ściany ALBO kafel bez
        # podłogi (wnętrze bloku ściany). Promień nigdy tam nie dotrze, bo zatrzymuje
        # się na licu ściany, więc bez dolewki takie kafle zostają czarne pośrodku
        # odkrytego terenu i czyta się je jako dziurę w renderowaniu.
        self.solid = solid
        # Wnęka: kafel PODŁOGI zamknięty ścianami z co najmniej trzech stron - typowo
        # nisza na skrzynię. Stojąc obok, gracz nie ma do jej środka linii wzroku
        # (zmierzone: żaden z pięciu punktów - środek i cztery rogi - nie ma LOS),
        # więc raycast i shadowcast gaszą ją tak samo jak ścianę. Jednokaflowa czerń
        # pośrodku oświetlonego korytarza czyta się jednak jak dziura w renderowaniu
        # i chowa skrzynię, po którą gracz przyszedł - traktujemy taki kafel jak
        # POWIERZCHNIĘ ściany, czyli oświetla go sąsiedztwo.
        self.surface = [[solid[y][x] or _is_pocket(solid, x, y)
                         for x in range(len(solid[0]))] for y in range(len(solid))]
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
        # promień (w kaflach) bez żadnego przyciemnienia - tryby kafelkowe, [O]/[P]
        self.core_tiles: float = CLEAR_TILES_GRID
        # liczba stopni gradientu; 0 = płynnie (bez kwantyzacji) - [-]/[=]
        self.steps: int = 0

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

        Do ``core_tiles`` kafli od gracza obraz jest nietknięty (alfa 0) - tak jak
        dziś w środku aureoli. Dopiero POWYŻEJ tej odległości zaczyna się gaśnięcie
        do ``ALPHA_VISIBLE_EDGE``. ``steps`` = 0 daje przejście płynne (alfa liczona
        wprost z odległości), a wartość > 0 kwantuje je na tyle stopni - do szukania
        złotego środka między "papka" a "widoczne kwadraty".
        """
        span = ALPHA_VISIBLE_EDGE - ALPHA_CLEAR
        core = self.core_tiles
        ramp = max(0.001, radius - core)
        steps = self.steps
        alpha: dict[tuple[int, int], int] = {}
        for (x, y) in self.visible:
            d = math.hypot(x - cx, y - cy)
            if d <= core:
                alpha[(x, y)] = ALPHA_CLEAR
            else:
                t = min(1.0, (d - core) / ramp)
                if steps:
                    t = math.ceil(t * steps) / steps
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
        dists: list[float] = []
        # najbliższe trafienie każdego kafla - z tego liczy się jego jasność
        hit_dist: dict[tuple[int, int], float] = {}
        step = TILE * 0.34  # krok próbkowania - 1/3 kafla wystarcza przy 16 px
        for i in range(RAY_COUNT):
            dx, dy = _COS[i], _SIN[i]
            dist = 0.0
            tx = ty = 0
            hit = False
            while dist < radius_px:
                dist += step
                tx, ty = int((px + dx * dist) // TILE), int((py + dy * dist) // TILE)
                if hit_dist.get((tx, ty), 1e9) > dist:
                    hit_dist[(tx, ty)] = dist
                if self.is_wall(tx, ty):
                    hit = True
                    break
            if hit:
                # Wielokąt kończy się DOKŁADNIE na licu ściany. Wcześniej był
                # przedłużany na trafiony kafel, żeby ściana się świeciła - ale
                # sąsiednie promienie trafiają w różne kafle, więc obrys skakał
                # o cały kafel i zostawiał na ścianie czarne, schodkowane wcięcia.
                # Ścianę oświetla teraz MASKA (jak w shadowcaście), a wielokąt
                # odpowiada już tylko za podłogę.
                dist = _tile_entry(px, py, dx, dy, tx, ty)
            dists.append(dist)
        self.visible = set(hit_dist)
        self.ray_origin = (px, py)
        self.ray_dist = dists
        self._grade_hits(hit_dist, float(radius_px) / TILE)

    def _grade_hits(self, hit_dist: dict[tuple[int, int], float], radius: float) -> None:
        """Jasność kafli trafionych promieniem - tą samą krzywą co pierścienie."""
        span = ALPHA_VISIBLE_EDGE - ALPHA_CLEAR
        core = min(CLEAR_TILES_RAYCAST, radius * 0.8)
        ramp = max(0.001, radius - core)
        alpha: dict[tuple[int, int], int] = {}
        for tile, dist in hit_dist.items():
            d = dist / TILE
            if d <= core:
                alpha[tile] = ALPHA_CLEAR
            else:
                t = min(1.0, (d - core) / ramp)
                if self.steps:
                    t = math.ceil(t * self.steps) / self.steps
                alpha[tile] = ALPHA_CLEAR + int(span * t ** 1.4)
        self.vis_alpha = alpha

    # ---------------------------------------------------------------- maska

    def commit(self, memory_alpha: int, floor_from_polygon: bool) -> None:
        """Wpisz bieżącą widoczność do maski (i do pamięci odkrycia).

        Trzy stany zapisane jako trzy wartości alfy w jednej powierzchni:
        nieodkryte zostaje 255, odkryte spada do ``memory_alpha``, widoczne do
        wartości z ``vis_alpha``. Zapis jest per kafel i tylko przy zmianie
        widoczności. ``floor_from_polygon`` (raycast) mówi, że jasność PODŁOGI
        rysuje wielokąt z dokładnością do piksela, więc maska zapisuje dla niej
        tylko pamięć - ale jasność z ``vis_alpha`` i tak jest potrzebna, bo to
        z niej biorą jasność ściany dookoła.
        """
        mask = self.mask
        # 1. skasuj poprzednią widoczność do poziomu pamięci
        for (x, y) in self._last_visible:
            if (x, y) not in self.visible:
                mask.set_at((x, y), (*FOG_COLOR, memory_alpha))
        # 2. wpisz nową
        written: dict[tuple[int, int], int] = {}
        bright: dict[tuple[int, int], int] = {}
        for (x, y) in self.visible:
            if 0 <= x < self.w and 0 <= y < self.h:
                a = self.vis_alpha.get((x, y), ALPHA_CLEAR)
                bright[(x, y)] = a
                written[(x, y)] = memory_alpha if (floor_from_polygon and not self.solid[y][x]) else a
        # 3. Kafle "solid" (ściana albo wnętrze bloku ściany) w dwóch krokach, bo
        # to dwie różne sytuacje:
        #  a) ściana stykająca się z WIDOCZNĄ PODŁOGĄ to lico ściany - gracz je
        #     widzi, więc dostaje jasność tej podłogi. Bez tego kafel ściany,
        #     w który przypadkiem nie trafił żaden promień (bo zasłoniły go
        #     sąsiednie), zostaje czarnym kwadratem pośrodku oświetlonego korytarza;
        #  b) każdy inny solid dotknięty widocznością dostaje tylko poziom PAMIĘCI
        #     - ma nie być czarny, ale też nie udawać, że gracz widzi w głąb ściany.
        for (x, y), a in bright.items():
            if self.surface[y][x]:
                continue
            for nx in (x - 1, x, x + 1):
                for ny in (y - 1, y, y + 1):
                    if 0 <= nx < self.w and 0 <= ny < self.h and self.surface[ny][nx]:
                        if written.get((nx, ny), 256) > a:
                            written[(nx, ny)] = a
        for (x, y) in list(written):
            for nx in (x - 1, x, x + 1):
                for ny in (y - 1, y, y + 1):
                    if 0 <= nx < self.w and 0 <= ny < self.h and self.surface[ny][nx]:
                        if (nx, ny) not in written:
                            written[(nx, ny)] = memory_alpha
        for (x, y), a in written.items():
            mask.set_at((x, y), (*FOG_COLOR, a))
        seen = set(written)
        self.discovered |= seen
        self._last_visible = seen

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
        # Ziarnistość gradientu, osobno dla każdej rodziny trybów, bo dobra wartość
        # jest inna: na kaflach kwantyzacja robi widoczne kwadraty (stąd "płynnie"),
        # a wielokąty raycastu z wyraźnym skokiem pierścieni wyglądają dobrze.
        self.steps_grid = 0
        self.steps_ray = RING_COUNT

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
        self.chest_images = load_chest_images()
        self.props: list[tuple[pygame.Surface, tuple[int, int]]] = []
        self.build_level()

    # ---------------------------------------------------------------- budowa mapy

    def build_level(self) -> None:
        cols, rows, chest_count = self.configs.get(self.level, self.configs[max(self.configs)])
        # ten sam warunek co w `map_loader.load_map`: `analyze_maze` cache'uje ścieżki
        # A* po współrzędnych, więc bez czyszczenia drugi labirynt dostaje trasy
        # z pierwszego (i wejście/wyjście lądują w bzdurnych miejscach)
        clear_maze_cache()
        rng = random.Random(self.seed)
        maze = HuntAndKillMaze(cols, rows)
        maze.generate(rng)
        stats: dict[str, Any] = analyze_maze(maze)
        stats["current_map_level"] = self.level
        stats["max_level"] = len(self.configs)

        tmx = load_pygame(str(settings.MAZE_DIR / "MazeTileset_Ninja.tmx"))
        build_tileset_map_from_maze(tmx, maze, stats, f"Maze_{self.level:02}",
                                    to_map=settings.START_MAP, entry_point="MazeEntry", rng=rng)
        self.tmx = tmx
        self.maze = maze
        self.stats = stats
        self.build_props(maze, stats, rng, chest_count)

        self.map_view = pyscroll.BufferedRenderer(
            data=pyscroll.data.TiledMapData(tmx),
            size=(settings.WIDTH, settings.HEIGHT),
            clamp_camera=True,
        )
        self.map_view.zoom = 1.0 if self.map_overview else settings.ZOOM_LEVEL

        walls = tmx.get_layer_by_name("walls")
        floor = tmx.get_layer_by_name("floor")
        blocked = [[bool(gid) for gid in row] for row in walls.data]
        solid = [[bool(w) or not f for w, f in zip(wrow, frow)]
                 for wrow, frow in zip(walls.data, floor.data)]
        previous = getattr(self, "fog", None)
        self.fog = FogGrid(blocked, solid)
        if previous is not None:
            # nastawy przeżywają [R] i zmianę poziomu - inaczej każde porównanie
            # dwóch labiryntów zaczyna się od ustawiania suwaków od nowa
            self.fog.core_tiles = previous.core_tiles
        self._props_scaled: dict[float, list[tuple[pygame.Surface, tuple[int, int]]]] = {}

        # start gracza tam, gdzie gra go stawia (kafel wejścia na poziom)
        sx, sy = stats["start"]
        self.px = float((MARGIN + sx * SUBTILE_COLS + SUBTILE_COLS // 2) * TILE)
        self.py = float((MARGIN + sy * SUBTILE_ROWS + SUBTILE_ROWS // 2) * TILE)
        self.recompute_fog(force=True)

    def build_props(self, maze: HuntAndKillMaze, stats: dict[str, Any],
                    rng: random.Random, chest_count: int) -> None:
        """Skrzynie jako sprite'y - w grze nie są kaflami, tylko obiektami.

        Drzwi, schody i dekoracje ścian to warstwy kafli i rysuje je pyscroll same
        z siebie (jest ich rzadko: ok. 15 na mapę 66x48, więc łatwo trafić na
        korytarz bez żadnej). Skrzyń pyscroll nie narysuje, bo powstają dopiero w
        `map_loader.load_interactions` - tutaj powtarzam sam algorytm rozstawienia
        (ślepe zaułki bez startu i mety, losowanie z `maze_rng`), żeby pozycje
        wypadały tam, gdzie w grze.
        """
        props: list[tuple[pygame.Surface, tuple[int, int]]] = []
        big = self.chest_images["big_chest"]
        small = self.chest_images["small_chest"]

        for layer in self.tmx.layers:
            objects = getattr(layer, "objects", None)
            if objects is None:
                continue
            for obj in layer:
                if obj.name == "BigChest_Maze":
                    props.append((big, (int(obj.x), int(obj.y))))

        candidates = find_dead_ends(maze)
        for key in ("start", "end"):
            if stats[key] in candidates:
                candidates.remove(stats[key])
        for cx, cy in rng.sample(candidates, min(chest_count, len(candidates))):
            off = IMAGE_DIRECTION_TO_CHEST[maze.cell_rows[cy][cx].image_index]
            props.append((small, ((MARGIN + cx * SUBTILE_COLS + off[0]) * TILE,
                                  (MARGIN + cy * SUBTILE_ROWS + off[1]) * TILE)))
        self.props = props

    def draw_props(self, screen: pygame.Surface) -> None:
        """Sprite'y rysowane PRZED nakładką - mgła ma je gasić tak jak mapę."""
        zoom = round(self.map_view.zoom, 2)
        scaled = self._props_scaled.get(zoom)
        if scaled is None:
            scaled = [(pygame.transform.scale_by(img, zoom), pos) for img, pos in self.props]
            self._props_scaled[zoom] = scaled
        for img, pos in scaled:
            screen.blit(img, self.map_view.translate_point(pos))

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
        self.fog.steps = self.steps_ray if self.mode == 3 else self.steps_grid
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
            self.fog.commit(self.memory_alpha, floor_from_polygon=self.mode == 3)
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
        # 0 = "płynnie": wielokątów musi być tyle, żeby skoku nie było widać
        rings = self.steps_ray or SMOOTH_RINGS
        for i in range(rings, 0, -1):
            k = core_k + (1.0 - core_k) * i / rings
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
        cols, rows, _chests = self.configs.get(self.level, self.configs[max(self.configs)])
        pct = 100.0 * len(self.fog.discovered) / (self.fog.w * self.fog.h)
        la, v, n = C_LABEL, C_VALUE, C_NUMBER
        steps = self.steps_ray if self.mode == 3 else self.steps_grid
        seg = _key_segments  # [nawias szary] [klawisz pomarańczowy] etykieta wartość
        lines: list[list[tuple[str, tuple[int, int, int]]]] = [
            [*seg("F", "mode", MODES[self.mode]),
             *seg("G", "memory", "hard" if not self.soft_edges else "soft"),
             *seg("B", "upscale", "smooth" if self.smooth_upscale else "nearest")],
            [*seg("[ ]", "range", f"{self.vision_tiles} tiles"),
             *seg("O P", "core", f"{self.fog.core_tiles:g} tiles"),
             *seg("- =", "steps", f"{steps}" if steps else "smooth"),
             *seg(", .", "alpha", f"{self.memory_alpha}"),
             *seg("L", "game halo", "on" if self.show_light else "off")],
            [*seg("1-4", "level", f"{self.level}"),
             (f" ({cols}x{rows} cells = {self.fog.w}x{self.fog.h} tiles)", la),
             *seg("R", "seed", f"{self.seed}"),
             *seg("C", "clear"), *seg("M", "map overview")],
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
        self.draw_props(self.screen)
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
        elif key in (pygame.K_EQUALS, pygame.K_MINUS):
            # ziarnistość dotyczy AKTYWNEJ rodziny trybów - każda ma inną dobrą wartość
            delta = 1 if key == pygame.K_EQUALS else -1
            if self.mode == 3:
                self.steps_ray = max(0, min(16, self.steps_ray + delta))
            else:
                self.steps_grid = max(0, min(16, self.steps_grid + delta))
            self.recompute_fog(force=True)
        elif key == pygame.K_p:
            self.fog.core_tiles = min(8.0, self.fog.core_tiles + 0.5)
            self.recompute_fog(force=True)
        elif key == pygame.K_o:
            self.fog.core_tiles = max(0.0, self.fog.core_tiles - 0.5)
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

    def selftest(self, frames: int = 4000) -> int:
        """Poluj na artefakt "czarny kwadrat" na WYRENDEROWANEJ klatce.

        Powód istnienia: trzy rundy z rzędu poprawka wyglądała dobrze na moim
        pojedynczym zrzucie i sypała się u autora po minucie chodzenia. Test
        chodzi losowo po mapie i co piątą klatkę zlicza kafle ciemne (średnia
        z czterech próbek) mające co najmniej trzech jasnych sąsiadów.

        To LICZNIK, nie bramka zero-jedynkowa: część takich kafli to poprawnie
        zgaszone wyloty korytarzy w nieodkryty teren. Sens ma porównanie liczby
        przed zmianą i po niej - dlatego wynik to liczba RÓŻNYCH kafli, a nie
        pierwsze trafienie.

        Kafel gracza jest pomijany: jego znacznik ma ciemną obwódkę i sam w sobie
        wyglądał jak trafienie.
        """
        def lum(tx: int, ty: int) -> float | None:
            total = 0.0
            for ox, oy in ((4, 4), (12, 4), (4, 12), (12, 12)):
                sx, sy = self.map_view.translate_point((tx * TILE + ox, ty * TILE + oy))
                if not (0 <= sx < settings.WIDTH and 0 <= sy < settings.HEIGHT):
                    return None
                c = self.screen.get_at((sx, sy))
                total += c.r + c.g + c.b
            return total / 4

        def scan() -> list[tuple[int, int]]:
            view = self.map_view.view_rect
            ptx, pty = int(self.px // TILE), int(self.py // TILE)
            hits = []
            for ty in range(int(view.top // TILE), int(view.bottom // TILE) + 2):
                for tx in range(int(view.left // TILE), int(view.right // TILE) + 2):
                    if abs(tx - ptx) <= 1 and abs(ty - pty) <= 1:
                        continue
                    v = lum(tx, ty)
                    if v is None or v > 90:
                        continue
                    nb = [lum(tx + a, ty + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))]
                    if len([n for n in nb if n is not None and n > 250]) >= 3:
                        hits.append((tx, ty))
            return hits

        total = 0
        for mode in (1, 2, 3):
            self.mode = mode
            self.show_light = False
            self.fog.clear()
            rnd = random.Random(11)
            step = (1, 0)
            found: set[tuple[int, int]] = set()
            for i in range(frames):
                if rnd.random() < 0.06:
                    step = rnd.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
                if self.walkable(self.px + step[0] * 3, self.py + step[1] * 3):
                    self.px += step[0] * 3
                    self.py += step[1] * 3
                else:
                    step = rnd.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
                self.recompute_fog()
                # pierwsze klatki po wyczyszczeniu mgły pomijamy: pamięć jest pusta,
                # więc prawie każdy kafel graniczy z czernią i pomiar nic nie mówi
                if i % 5 or i < 300:
                    continue
                self.draw()
                found.update(scan())
            total += len(found)
            sample = sorted(found)[:4]
            print(f"[selftest] {MODES[mode]:22} ciemnych kafli w jasnym otoczeniu: "
                  f"{len(found):3}  {sample}")
        return total

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
    ap.add_argument("--selftest", action="store_true",
                    help="poluj na artefakty renderowania (czarne kafle) i zwróć kod != 0 przy trafieniu")
    args = ap.parse_args()

    headless = args.shots is not None or args.selftest
    if headless:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    proto = Prototype(args.level, args.seed, headless)
    if args.selftest:
        sys.exit(1 if proto.selftest() else 0)
    if args.shots:
        proto.shots(Path(args.shots))
    else:
        proto.run()


if __name__ == "__main__":
    main()
