"""Mgła wojny w labiryncie (E03) - trzy stany widoczności kafla.

Moduł systemu wg B01 (D1): bezstanowe funkcje operujące na przekazanej scenie,
plus jeden dataclass stanu trzymany na ``scene.fog`` (jak ``path_finding_grid``).

Trzy stany kafla, zapisane jako TRZY WARTOŚCI ALFY w jednej masce:

- **nieodkryty** (``FOG_ALPHA_UNSEEN`` = 255) - czerń, tileset niewidoczny,
- **odkryty, poza wzrokiem** (``FOG_ALPHA_REMEMBERED`` = 230) - dokładnie ta alfa,
  którą ma dziś ``NIGHT_FILTER``, czyli cały labirynt sprzed E03,
- **w zasięgu wzroku** - gradient od ``FOG_ALPHA_CLEAR`` (rdzeń) do
  ``FOG_ALPHA_VISIBLE_EDGE`` (granica zasięgu).

Warunek twardy zadania: mgła NIE dokłada drugiego pełnoekranowego
``transform.scale``. Maska ma JEDEN PIKSEL NA KAFEL (78x60 px dla największego
poziomu); do powierzchni filtra trafia jej wycinek widoku (~24x14 px)
przeskalowany do 160x90 px. Dalej idzie ta sama kompozycja co w E01.

Dwa algorytmy widoczności (wybór w SettingsMenu, ``settings.FOG_ALGORITHM``):

- ``"raycast"``   - wielokąt widzenia liczony w pikselach świata; krawędź cienia
  gładka, zza rogu wychyla się wąski klin światła,
- ``"shadowcast"``- klasyczny recursive shadowcasting na siatce kafli; krawędź
  biegnie po kaflach, kosztuje ułamek tego co raycast.

Źródła światła to gracz ORAZ potwory (decyzja W5). Potwory świecą tym samym
algorytmem i - decyzja D7 - także w korytarzach, w których gracz nigdy nie był,
ale ULOTNIE: bit w ``discovered`` ustawia wyłącznie gracz, więc po przejściu
potwora kafel wraca do czerni, a nie do pamięci.
"""
from __future__ import annotations

import base64
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

import settings
from settings import STEP_COST_WALL, TILE_SIZE

if TYPE_CHECKING:
    from characters.npc import NPC
    from scene.scene import Scene


# Ósemka oktantów dla recursive shadowcastingu (transformacje układu współrzędnych).
_MULT = (
    (1, 0, 0, -1, -1, 0, 0, 1),
    (0, 1, -1, 0, 0, -1, 1, 0),
    (0, 1, 1, 0, 0, -1, -1, 0),
    (1, 0, 0, 1, -1, 0, 0, -1),
)

#: Tablice sin/cos per liczba promieni - liczone raz, nie co klatkę.
_RAY_DIRS: dict[int, list[tuple[float, float]]] = {}


def _ray_dirs(count: int) -> list[tuple[float, float]]:
    dirs = _RAY_DIRS.get(count)
    if dirs is None:
        step = 2.0 * math.pi / count
        dirs = [(math.cos(step * i), math.sin(step * i)) for i in range(count)]
        _RAY_DIRS[count] = dirs
    return dirs


###############################################################################################################
# Bitset odkrycia (jedyna prawda, którą zapisujemy do pliku)
###############################################################################################################

def bit_get(bits: bytearray, index: int) -> bool:
    return bool(bits[index >> 3] & (1 << (index & 7)))


def bit_set(bits: bytearray, index: int) -> None:
    bits[index >> 3] |= 1 << (index & 7)


def bits_to_base64(bits: bytearray) -> str:
    return base64.b64encode(bytes(bits)).decode("ascii")


def bits_from_base64(data: str, size: int) -> bytearray:
    """Bitset z base64 albo pusty, gdy wejście jest nie tym, czego oczekujemy.

    Nigdy nie rzuca: uszkodzony (albo pochodzący z innego rozmiaru mapy) zapis ma
    dać labirynt nieodkryty, a nie wywalić wczytywanie gry.
    """
    empty = bytearray(size)
    if not data:
        return empty
    try:
        raw = base64.b64decode(data.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        return empty
    if len(raw) != size:
        return empty
    return bytearray(raw)


###############################################################################################################
# Stan
###############################################################################################################

@dataclass
class Observer:
    """Jedno źródło światła: gracz albo potwór, z własnym wynikiem widoczności."""

    is_player: bool
    #: świat, piksele - punkt, z którego liczona jest widoczność
    origin: tuple[float, float] = (0.0, 0.0)
    #: kafel -> alfa (0 = pełna jasność)
    tiles: dict[tuple[int, int], int] = field(default_factory=dict)
    #: raycast: dystans trafienia dla każdego promienia (w pikselach świata)
    ray_dist: list[float] = field(default_factory=list)
    #: parametry, którymi ten obserwator był liczony (do rysowania wielokątów)
    range_px: float = 0.0
    core_px: float = 0.0
    steps: int = 0
    _last_tile: tuple[int, int] | None = None
    _last_pos: tuple[float, float] | None = None


@dataclass
class FogState:
    """Mgła jednej mapy. Żyje na ``scene.fog`` i w ``MAP_PROPERTIES``."""

    w: int
    h: int
    #: siatka A* sceny - ta SAMA lista, nie kopia: zniszczenie ściany zmienia
    #: geometrię widzenia natychmiast, bez żadnej inwalidacji stanu mgły
    grid: list[list[int]]
    #: "powierzchnia": kafel ściany, kafel bez podłogi (wnętrze bloku ściany) albo
    #: wnęka - czyli wszystko, czego nie trafi żaden promień, a co MUSI dostać
    #: jasność od sąsiedniej podłogi (inaczej: czarne kwadraty w oświetlonym korytarzu)
    surface: list[list[bool]]
    #: bitset odkrycia (rośnie wyłącznie od gracza) - to idzie do zapisu
    discovered: bytearray
    #: maska 1 piksel = 1 kafel, gotowa do skalowania na powierzchnię filtra
    mask: pygame.Surface
    observers: dict[str, Observer] = field(default_factory=dict)
    #: kafle rozjaśnione w poprzedniej klatce - do przywrócenia przy zmianie
    written: dict[tuple[int, int], int] = field(default_factory=dict)
    #: procent odkrycia mapy (diagnostyka; liczony przy commicie, nie co klatkę)
    discovered_tiles: int = 0

    # ------------------------------------------------------------------ pomocnicze

    def is_wall(self, x: int, y: int) -> bool:
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.grid[y][x] >= STEP_COST_WALL
        return True

    def is_discovered(self, x: int, y: int) -> bool:
        return bit_get(self.discovered, y * self.w + x)

    @property
    def discovered_pct(self) -> float:
        total = self.w * self.h
        return (100.0 * self.discovered_tiles / total) if total else 0.0

    def clear(self) -> None:
        """Wyczyść odkrycie (nowy poziom / debug). Maska wraca do czerni."""
        self.discovered = bytearray(len(self.discovered))
        self.discovered_tiles = 0
        self.observers.clear()
        self.written.clear()
        self.mask.fill((*settings.FOG_COLOR, settings.FOG_ALPHA_UNSEEN))


###############################################################################################################
# Budowa
###############################################################################################################

def is_enabled(scene: "Scene") -> bool:
    """Czy mgła ma się w tej klatce liczyć i rysować.

    Tryb czytany ŻYWO z modułu ``settings`` (kontrakt K6) - to pokrętło
    z SettingsMenu, nie stała z importu.
    """
    return (bool(getattr(scene, "is_maze", False))
            and settings.FOG_ALGORITHM != "off"
            and getattr(scene, "fog", None) is not None)


def build(scene: "Scene", tileset_map: object) -> None:
    """Zbuduj mgłę dla świeżo wczytanej mapy (albo skasuj ją poza labiryntem).

    Wołane z ``map_loader.load_map`` PO ``load_walls`` - potrzebuje gotowej
    ``scene.path_finding_grid`` oraz warstw ``walls`` i ``floor`` z TMX.
    """
    if not scene.is_maze:
        scene.fog = None
        return

    grid = scene.path_finding_grid
    h = len(grid)
    w = len(grid[0]) if h else 0
    if not w or not h:
        scene.fog = None
        return

    solid = _build_solid(scene, tileset_map, w, h)
    surface = [[solid[y][x] or _is_pocket(solid, x, y, w, h) for x in range(w)] for y in range(h)]
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    mask.fill((*settings.FOG_COLOR, settings.FOG_ALPHA_UNSEEN))
    scene.fog = FogState(
        w=w, h=h, grid=grid, surface=surface,
        discovered=bytearray((w * h + 7) // 8), mask=mask,
    )


def _build_solid(scene: "Scene", tileset_map: object, w: int, h: int) -> list[list[bool]]:
    """"Nie-korytarz": kafel ściany ALBO kafel bez podłogi (wnętrze bloku ściany).

    Wnętrza bloków ścian nie trafi żaden promień (ten zatrzymuje się na licu), więc
    bez dolewki jasności z sąsiedztwa zostają czarne pośrodku odkrytego terenu
    i czyta się je jako dziurę w renderowaniu.
    """
    floor_data: list[list[int]] | None = None
    try:
        layer = tileset_map.get_layer_by_name("floor")  # type: ignore[attr-defined]
        floor_data = layer.data
    except (ValueError, AttributeError):
        floor_data = None

    solid: list[list[bool]] = []
    for y in range(h):
        row = []
        floor_row = floor_data[y] if floor_data is not None and y < len(floor_data) else None
        for x in range(w):
            wall = scene.path_finding_grid[y][x] >= STEP_COST_WALL
            has_floor = bool(floor_row[x]) if floor_row is not None and x < len(floor_row) else True
            row.append(wall or not has_floor)
        solid.append(row)
    return solid


def _is_pocket(solid: list[list[bool]], x: int, y: int, w: int, h: int) -> bool:
    """Kafel PODŁOGI zamknięty ścianami z co najmniej trzech stron (nisza na skrzynię).

    Stojąc obok, gracz nie ma linii wzroku do jej środka, więc raycast i shadowcast
    gaszą ją tak samo jak ścianę. Jednokaflowa czerń pośrodku oświetlonego korytarza
    czyta się jednak jak dziura w renderowaniu i chowa skrzynię, po którą gracz
    przyszedł - traktujemy taki kafel jak POWIERZCHNIĘ ściany.
    """
    if solid[y][x]:
        return False
    walls = 0
    for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if not (0 <= nx < w and 0 <= ny < h) or solid[ny][nx]:
            walls += 1
    return walls >= 3


###############################################################################################################
# Widoczność - czyste funkcje (bez pygame, bez sceny) - to one idą do testów
###############################################################################################################

def shadowcast(fog: FogState, cx: int, cy: int, radius: int) -> set[tuple[int, int]]:
    """Recursive shadowcasting - zbiór kafli widocznych z (cx, cy)."""
    vis: set[tuple[int, int]] = {(cx, cy)}
    for oct_i in range(8):
        _cast_light(fog, vis, cx, cy, 1, 1.0, 0.0, radius,
                    _MULT[0][oct_i], _MULT[1][oct_i], _MULT[2][oct_i], _MULT[3][oct_i])
    return vis


def _cast_light(fog: FogState, vis: set[tuple[int, int]], cx: int, cy: int, row: int,
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
            if dx * dx + dy * dy <= radius_sq and 0 <= x < fog.w and 0 <= y < fog.h:
                vis.add((x, y))
            if blocked_flag:
                if fog.is_wall(x, y):
                    new_start = r_slope
                    continue
                blocked_flag = False
                start = new_start
            elif fog.is_wall(x, y) and j < radius:
                blocked_flag = True
                _cast_light(fog, vis, cx, cy, j + 1, start, l_slope, radius, xx, xy, yx, yy)
                new_start = r_slope
        if blocked_flag:
            break


def cast_rays(fog: FogState, px: float, py: float, radius_px: float,
              ray_count: int) -> tuple[list[float], dict[tuple[int, int], float]]:
    """Wielokąt widzenia: ``ray_count`` promieni + próbkowanie po kaflach.

    Zwraca (dystans trafienia każdego promienia, najbliższy dystans trafienia
    każdego kafla). Z tego drugiego liczy się jasność kafli w masce, z pierwszego
    - wielokąty rysowane na powierzchni filtra.
    """
    dists: list[float] = []
    hit_dist: dict[tuple[int, int], float] = {}
    step = TILE_SIZE * settings.FOG_RAY_STEP_TILES
    for dx, dy in _ray_dirs(ray_count):
        dist = 0.0
        tx = ty = 0
        hit = False
        while dist < radius_px:
            dist += step
            tx, ty = int((px + dx * dist) // TILE_SIZE), int((py + dy * dist) // TILE_SIZE)
            if hit_dist.get((tx, ty), 1e9) > dist:
                hit_dist[(tx, ty)] = dist
            if fog.is_wall(tx, ty):
                hit = True
                break
        if hit:
            # Wielokąt kończy się DOKŁADNIE na licu ściany (ścianę oświetla maska).
            # Przedłużanie promienia o stałą wartość wchodziło w kafel za ścianą
            # i pokazywało fragment sąsiedniego korytarza.
            dist = _tile_entry(px, py, dx, dy, tx, ty)
        dists.append(dist)
    return dists, hit_dist


def _tile_entry(px: float, py: float, dx: float, dy: float, tx: int, ty: int) -> float:
    """Dystans, na którym promień (px,py)+t*(dx,dy) WCHODZI w kafel (tx,ty).

    Krok próbkowania jest zgrubny (1/3 kafla), więc surowy dystans trafienia skacze
    między sąsiednimi promieniami i wielokąt dostaje ząbki. Dokładne przecięcie
    z krawędzią kafla daje gładki obrys.
    """
    small = -1e9
    if dx > 1e-9:
        ex = (tx * TILE_SIZE - px) / dx
    elif dx < -1e-9:
        ex = ((tx + 1) * TILE_SIZE - px) / dx
    else:
        ex = small
    if dy > 1e-9:
        ey = (ty * TILE_SIZE - py) / dy
    elif dy < -1e-9:
        ey = ((ty + 1) * TILE_SIZE - py) / dy
    else:
        ey = small
    return max(ex, ey)


def grade_distance(distance_tiles: float, radius_tiles: float, core_tiles: float,
                   steps: int) -> int:
    """Alfa kafla oddalonego o ``distance_tiles`` od obserwatora.

    Do ``core_tiles`` obraz jest nietknięty (alfa 0) - tak jak dziś w środku
    aureoli. Dopiero POWYŻEJ zaczyna się gaśnięcie do ``FOG_ALPHA_VISIBLE_EDGE``.
    ``steps`` = 0 daje przejście płynne, wartość > 0 kwantuje je na tyle stopni.
    """
    span = settings.FOG_ALPHA_VISIBLE_EDGE - settings.FOG_ALPHA_CLEAR
    if distance_tiles <= core_tiles:
        return settings.FOG_ALPHA_CLEAR
    ramp = max(0.001, radius_tiles - core_tiles)
    t = min(1.0, (distance_tiles - core_tiles) / ramp)
    if steps:
        t = math.ceil(t * steps) / steps
    return settings.FOG_ALPHA_CLEAR + int(span * t ** settings.FOG_FALLOFF_EXP)


###############################################################################################################
# Aktualizacja per klatka (wołana ze `Scene.update`)
###############################################################################################################

def update(scene: "Scene") -> None:
    """Przelicz widoczność wszystkich źródeł światła i wpisz ją do maski.

    Przeliczanie jest leniwe (D9): tryb kafelkowy i potwory liczą się przy zmianie
    kafla, raycast gracza - przy ruchu o co najmniej ``FOG_RAY_MIN_MOVE_PX``.
    Gdy nic się nie zmieniło, funkcja kończy się przed ``_commit`` (czyli zwykle
    kosztuje jedno porównanie krotek na klatkę).
    """
    if not is_enabled(scene):
        return
    fog = scene.fog
    assert fog is not None
    algorithm = settings.FOG_ALGORITHM
    dirty = False
    live: set[str] = set()

    player = scene.player
    live.add("@player")
    if _refresh(fog, "@player", True, player.pos.x, player.pos.y, algorithm):
        dirty = True

    for npc in _light_npcs(scene):
        key = npc.name
        live.add(key)
        if _refresh(fog, key, False, npc.pos.x, npc.pos.y, algorithm):
            dirty = True

    # potwór, który wyszedł z kadru albo zginął, przestaje świecić
    for key in [k for k in fog.observers if k not in live]:
        del fog.observers[key]
        dirty = True

    if dirty:
        _commit(fog)


def _light_npcs(scene: "Scene") -> list["NPC"]:
    """Potwory, które w tej klatce świecą: w kadrze, N najbliższych graczowi (D6).

    Cullowanie po prostokącie widoku, bo potwór poza kadrem nie ma czego
    rozświetlić, a limit daje twardy sufit kosztu klatki niezależny od poziomu
    labiryntu (poziom 4 to 7 potworów + boss).
    """
    if not settings.FOG_NPC_LIGHTS or not scene.NPCs:
        return []
    view = scene.map_view.view_rect
    margin = settings.FOG_NPC_RANGE_TILES * TILE_SIZE
    left, top = view.left - margin, view.top - margin
    right, bottom = view.right + margin, view.bottom + margin
    ppos = scene.player.pos
    near: list[tuple[float, "NPC"]] = []
    for npc in scene.NPCs:
        if npc.is_dead:
            continue
        x, y = npc.pos.x, npc.pos.y
        if not (left <= x <= right and top <= y <= bottom):
            continue
        near.append(((x - ppos.x) ** 2 + (y - ppos.y) ** 2, npc))
    if len(near) > settings.FOG_NPC_MAX_LIGHTS:
        near.sort(key=lambda pair: pair[0])
        near = near[:settings.FOG_NPC_MAX_LIGHTS]
    return [npc for _d, npc in near]


def _refresh(fog: FogState, key: str, is_player: bool, x: float, y: float,
             algorithm: str) -> bool:
    """Przelicz jednego obserwatora, jeśli ruszył się dostatecznie. True = zmiana."""
    obs = fog.observers.get(key)
    if obs is None:
        obs = Observer(is_player=is_player)
        fog.observers[key] = obs

    tile = (int(x // TILE_SIZE), int(y // TILE_SIZE))
    if algorithm == "raycast" and is_player:
        last = obs._last_pos
        if last is not None and (abs(x - last[0]) + abs(y - last[1])) < settings.FOG_RAY_MIN_MOVE_PX:
            return False
    elif obs._last_tile == tile:
        return False
    obs._last_tile = tile
    obs._last_pos = (x, y)

    if is_player:
        range_tiles = float(settings.FOG_RAYCAST_RANGE_TILES if algorithm == "raycast"
                            else settings.FOG_SHADOWCAST_RANGE_TILES)
        core_tiles = (settings.FOG_RAYCAST_CORE_TILES if algorithm == "raycast"
                      else settings.FOG_SHADOWCAST_CORE_TILES)
        steps = (settings.FOG_RAYCAST_STEPS if algorithm == "raycast"
                 else settings.FOG_SHADOWCAST_STEPS)
        rays = settings.FOG_RAY_COUNT
    else:
        # potwór świeci tym samym algorytmem, ale słabiej i taniej (D8) - gracz ma
        # zostać najjaśniejszym punktem sceny
        range_tiles = float(settings.FOG_NPC_RANGE_TILES)
        core_tiles = min(settings.FOG_NPC_CORE_TILES, range_tiles * 0.8)
        steps = settings.FOG_NPC_STEPS
        rays = settings.FOG_NPC_RAY_COUNT

    obs.range_px = range_tiles * TILE_SIZE
    obs.core_px = core_tiles * TILE_SIZE
    obs.steps = steps

    if algorithm == "raycast":
        obs.origin = (x, y)
        obs.ray_dist, hits = cast_rays(fog, x, y, obs.range_px, rays)
        obs.tiles = {tile_xy: grade_distance(dist / TILE_SIZE, range_tiles, core_tiles, steps)
                     for tile_xy, dist in hits.items()}
    else:
        cx, cy = tile
        obs.origin = (cx * TILE_SIZE + TILE_SIZE / 2, cy * TILE_SIZE + TILE_SIZE / 2)
        obs.ray_dist = []
        obs.tiles = {(tx, ty): grade_distance(math.hypot(tx - cx, ty - cy),
                                              range_tiles, core_tiles, steps)
                     for (tx, ty) in shadowcast(fog, cx, cy, int(range_tiles))}
    return True


def _commit(fog: FogState) -> None:
    """Wpisz bieżącą widoczność do maski i zaktualizuj pamięć odkrycia.

    Kolejność ma znaczenie:

    1. kafle zwolnione z widoczności wracają do ``FOG_ALPHA_REMEMBERED``, jeśli ich
       bit w ``discovered`` jest ustawiony, a w przeciwnym razie do
       ``FOG_ALPHA_UNSEEN``. Jedna wartość dla obu przypadków zostawiałaby na mapie
       ślad potwora jako fałszywą "pamięć" korytarza, którego gracz nie widział (D7);
    2. wkład gracza rozszerzany o lica ścian i dopisywany do ``discovered``;
    3. wkład potworów rozszerzany tak samo, ale BEZ dopisywania do pamięci;
    4. przy nakładaniu się świateł wygrywa jaśniejsze (mniejsza alfa).
    """
    player_tiles: dict[tuple[int, int], int] = {}
    npc_tiles: dict[tuple[int, int], int] = {}
    for obs in fog.observers.values():
        target = player_tiles if obs.is_player else npc_tiles
        for tile, alpha in obs.tiles.items():
            if target.get(tile, 256) > alpha:
                target[tile] = alpha

    player_written = _expand_surfaces(fog, player_tiles)
    written = dict(player_written)
    for tile, alpha in _expand_surfaces(fog, npc_tiles).items():
        if written.get(tile, 256) > alpha:
            written[tile] = alpha

    # 1. przywróć kafle, które przestały być oświetlone
    mask = fog.mask
    color = settings.FOG_COLOR
    remembered = settings.FOG_ALPHA_REMEMBERED
    unseen = settings.FOG_ALPHA_UNSEEN
    for (x, y) in fog.written:
        if (x, y) not in written:
            mask.set_at((x, y), (*color, remembered if fog.is_discovered(x, y) else unseen))

    # 2. pamięć odkrycia rośnie WYŁĄCZNIE od gracza
    width = fog.w
    for (x, y) in player_written:
        index = y * width + x
        if not bit_get(fog.discovered, index):
            bit_set(fog.discovered, index)
            fog.discovered_tiles += 1

    # 3. wpisz bieżącą widoczność
    for (x, y), alpha in written.items():
        mask.set_at((x, y), (*color, alpha))
    fog.written = written


def _expand_surfaces(fog: FogState, tiles: dict[tuple[int, int], int]) -> dict[tuple[int, int], int]:
    """Dolej jasność kaflom "powierzchni" (ściany, wnętrza bloków, wnęki).

    Dwie różne sytuacje, stąd dwa przebiegi:

    a) ściana stykająca się z WIDOCZNĄ PODŁOGĄ to lico ściany - gracz je widzi,
       więc dostaje jasność tej podłogi. Bez tego kafel ściany, w który przypadkiem
       nie trafił żaden promień (bo zasłoniły go sąsiednie), zostaje czarnym
       kwadratem pośrodku oświetlonego korytarza;
    b) każdy inny "solid" dotknięty widocznością dostaje tylko poziom PAMIĘCI - ma
       nie być czarny, ale też nie udawać, że gracz widzi w głąb ściany.
    """
    if not tiles:
        return {}
    out = dict(tiles)
    surface = fog.surface
    w, h = fog.w, fog.h
    for (x, y), alpha in tiles.items():
        if surface[y][x]:
            continue
        for nx in (x - 1, x, x + 1):
            if not 0 <= nx < w:
                continue
            for ny in (y - 1, y, y + 1):
                if 0 <= ny < h and surface[ny][nx] and out.get((nx, ny), 256) > alpha:
                    out[(nx, ny)] = alpha
    memory = settings.FOG_ALPHA_REMEMBERED
    for (x, y) in list(out):
        for nx in (x - 1, x, x + 1):
            if not 0 <= nx < w:
                continue
            for ny in (y - 1, y, y + 1):
                if 0 <= ny < h and surface[ny][nx] and (nx, ny) not in out:
                    out[(nx, ny)] = memory
    return out


###############################################################################################################
# Rysowanie (wołane z `night_filter.apply_time_of_day_filter`)
###############################################################################################################

def compose(scene: "Scene", filter_surf: pygame.Surface) -> None:
    """Wypełnij powierzchnię filtra mgłą zamiast jednolitym kolorem nocy.

    Cały koszt to wycinek maski (~24x14 px) przeskalowany do rozmiaru filtra
    (160x90 px) - żadnego drugiego pełnoekranowego ``transform.scale``.
    """
    fog = scene.fog
    assert fog is not None
    scale = settings.FILTER_SCALE
    view = scene.map_view.view_rect
    zoom = scene.map_view.zoom

    # wycinek maski dla widoku + margines 1 kafla, żeby skalowanie nie ucinało brzegu
    src = pygame.Rect(int(view.left / TILE_SIZE), int(view.top / TILE_SIZE),
                      int(view.width / TILE_SIZE) + 2, int(view.height / TILE_SIZE) + 2)
    src = src.clip(pygame.Rect(0, 0, fog.w, fog.h))
    filter_surf.fill((*settings.FOG_COLOR, settings.FOG_ALPHA_UNSEEN))
    if src.width <= 0 or src.height <= 0:
        return

    piece = fog.mask.subsurface(src)
    px_per_tile = (TILE_SIZE * zoom) / scale
    target = (max(1, int(src.width * px_per_tile)), max(1, int(src.height * px_per_tile)))
    scaler = pygame.transform.smoothscale if settings.FOG_MASK_SMOOTH else pygame.transform.scale
    scaled = scaler(piece, target)
    off_x = (src.x * TILE_SIZE - view.left) * zoom / scale
    off_y = (src.y * TILE_SIZE - view.top) * zoom / scale
    # BLEND_RGBA_MIN, nie zwykły blit: tło jest już wypełnione "nieodkryte" (alfa 255),
    # a maska ma alfy MNIEJSZE - zwykły blit zmieszałby je z tłem zamiast podmienić.
    # Przy okazji obszar poza mapą zostaje czarny.
    filter_surf.blit(scaled, (off_x, off_y), special_flags=pygame.BLEND_RGBA_MIN)

    if settings.FOG_ALGORITHM == "raycast":
        _draw_vision_polygons(scene, filter_surf)


def _draw_vision_polygons(scene: "Scene", filter_surf: pygame.Surface) -> None:
    """Pole widzenia jako zagnieżdżone wielokąty = gradient jasności.

    Każdy wielokąt to te same promienie ucięte na ``min(ściana, k * zasięg)``.
    Uwaga na pułapkę geometryczną: przy ``dystans_do_ściany * k`` wszystkie
    pierścienie kurczą się tam, gdzie blisko jest ściana, więc środek gradientu
    ucieka od niej i wygląda jak źle wycentrowana aureola.

    Druga pułapka, przy WIELU obserwatorach: ``draw.polygon`` nie miesza, tylko
    nadpisuje piksele. Dlatego malujemy POZIOMAMI - najpierw pierścień zewnętrzny
    (najciemniejszy) wszystkich obserwatorów, potem kolejny, na końcu rdzenie.
    Rysowane "per obserwator" ciemny pierścień potwora wymazywałby jasny rdzeń gracza.
    """
    fog = scene.fog
    assert fog is not None
    observers = [obs for obs in fog.observers.values() if obs.ray_dist]
    if not observers:
        return
    zoom = scene.map_view.zoom
    scale = settings.FILTER_SCALE
    span = settings.FOG_ALPHA_VISIBLE_EDGE - settings.FOG_ALPHA_CLEAR
    max_rings = max(obs.steps or settings.FOG_SMOOTH_RINGS for obs in observers)

    for level in range(max_rings, 0, -1):
        for obs in observers:
            rings = obs.steps or settings.FOG_SMOOTH_RINGS
            if level > rings:
                continue
            core_k = obs.core_px / obs.range_px if obs.range_px else 0.0
            k = core_k + (1.0 - core_k) * level / rings
            alpha = settings.FOG_ALPHA_CLEAR + int(span * k ** settings.FOG_FALLOFF_EXP)
            _draw_ring(scene, filter_surf, obs, k * obs.range_px, alpha, zoom, scale)
    for obs in observers:
        _draw_ring(scene, filter_surf, obs, obs.core_px, settings.FOG_ALPHA_CLEAR, zoom, scale)


def _draw_ring(scene: "Scene", filter_surf: pygame.Surface, obs: Observer,
               reach: float, alpha: int, zoom: float, scale: int) -> None:
    ox, oy = scene.map_view.translate_point(obs.origin)
    dirs = _ray_dirs(len(obs.ray_dist))
    points = []
    for i, dist in enumerate(obs.ray_dist):
        d = dist if dist < reach else reach
        cos_i, sin_i = dirs[i]
        points.append(((ox + cos_i * d * zoom) / scale, (oy + sin_i * d * zoom) / scale))
    pygame.draw.polygon(filter_surf, (*settings.FOG_COLOR, alpha), points)


###############################################################################################################
# Zapis / odczyt (save/load)
###############################################################################################################

def to_save(fog: "FogState | None") -> tuple[str, int, int]:
    """(base64 bitsetu, szerokość, wysokość) - to, co ląduje w ``MapState``."""
    if fog is None:
        return ("", 0, 0)
    return (bits_to_base64(fog.discovered), fog.w, fog.h)


def apply_save(fog: "FogState | None", data: str, w: int, h: int) -> None:
    """Odtwórz odkrycie z zapisu na świeżo zbudowanej mgle.

    Niezgodny rozmiar siatki (inny poziom, inna wersja generatora) = mgła pusta,
    a nie wyjątek: labirynt regeneruje się z seeda i musi się wczytać nawet wtedy,
    gdy zapis pochodzi z innego układu mapy.
    """
    if fog is None or not data:
        return
    if (w, h) != (fog.w, fog.h):
        print(f"[fog] rozmiar mapy z zapisu {w}x{h} != {fog.w}x{fog.h} - mgła zostaje pusta")
        return
    fog.discovered = bits_from_base64(data, len(fog.discovered))
    fog.discovered_tiles = sum(bin(byte).count("1") for byte in fog.discovered)
    fog.observers.clear()
    fog.written.clear()
    _repaint_memory(fog)


def _repaint_memory(fog: FogState) -> None:
    """Przemaluj całą maskę z bitsetu (po wczytaniu zapisu)."""
    color = settings.FOG_COLOR
    fog.mask.fill((*color, settings.FOG_ALPHA_UNSEEN))
    remembered = (*color, settings.FOG_ALPHA_REMEMBERED)
    width = fog.w
    for y in range(fog.h):
        base = y * width
        for x in range(width):
            if bit_get(fog.discovered, base + x):
                fog.mask.set_at((x, y), remembered)
