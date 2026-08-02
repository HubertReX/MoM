#!/usr/bin/env python3
"""Mgła wojny w labiryncie (E03) - logika widoczności, pamięci i zapisu.

Uruchomienie z katalogu repo:
    .venv/bin/python tests/test_fog_of_war.py

Testowana jest warstwa, która decyduje o tym, CO gracz widzi i CO zapamiętuje -
niezależnie od tego, jak to potem wygląda na ekranie:

- shadowcast i raycast nie przeciekają przez ścianę (mgła bez LOS byłaby
  "prześwietlaniem" korytarzy, co w labiryncie o szerokości jednego kafla widać
  natychmiast);
- gradient jasności jest monotoniczny i kwantowany na zadaną liczbę stopni;
- kafle "powierzchni" (ściany, wnętrza bloków, wnęki) dostają jasność
  z sąsiedztwa - to jest lek na artefakt "czarnych kwadratów", który w prototypie
  wracał trzy razy z rzędu;
- **pamięć odkrycia rośnie WYŁĄCZNIE od gracza** (decyzja D7): potwór świeci
  także w nieodkrytym korytarzu, ale po jego przejściu kafel wraca do czerni,
  a nie do poziomu pamięci;
- bitset odkrycia przeżywa rundę base64, a niezgodny rozmiar mapy daje pustą
  mgłę zamiast wyjątku przy wczytywaniu zapisu.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

import settings  # noqa: E402
from settings import STEP_COST_GROUND, STEP_COST_WALL, TILE_SIZE  # noqa: E402
from scene import fog_of_war as fow  # noqa: E402


def assert_eq(a: object, b: object, msg: str = "") -> None:
    if a != b:
        raise AssertionError(f"{msg}\n  expected: {b!r}\n  actual:   {a!r}")


def assert_true(cond: bool, msg: str = "") -> None:
    if not cond:
        raise AssertionError(msg)


def make_fog(rows: list[str]) -> fow.FogState:
    """Zbuduj mgłę z rysunku ASCII: ``#`` = ściana, ``.`` = podłoga."""
    h, w = len(rows), len(rows[0])
    grid = [[STEP_COST_WALL if ch == "#" else STEP_COST_GROUND for ch in row] for row in rows]
    solid = [[ch == "#" for ch in row] for row in rows]
    surface = [[solid[y][x] or fow._is_pocket(solid, x, y, w, h) for x in range(w)] for y in range(h)]
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    mask.fill((*settings.FOG_COLOR, settings.FOG_ALPHA_UNSEEN))
    return fow.FogState(w=w, h=h, grid=grid, surface=surface,
                        discovered=bytearray((w * h + 7) // 8), mask=mask)


# korytarz w kształcie L: gracz w (1,1), za rogiem odnoga w dół
L_CORRIDOR = [
    "#######",
    "#.....#",
    "#.###.#",
    "#.#...#",
    "#.#.#.#",
    "#...#.#",
    "#######",
]

# prosty korytarz przedzielony ścianą - najprostszy test przeciekania
BLOCKED_ROW = [
    "#########",
    "#...#...#",
    "#########",
]

# pokój 3x3 - kafle w środku nie są "wnękami", więc mogą być źródłem jasności
ROOM = [
    "#####",
    "#...#",
    "#...#",
    "#...#",
    "#####",
]


###############################################################################################################
def test_shadowcast_stops_at_wall() -> None:
    fog = make_fog(BLOCKED_ROW)
    visible = fow.shadowcast(fog, 1, 1, 6)
    assert_true((3, 1) in visible, "kafel przed ścianą jest widoczny")
    assert_true((5, 1) not in visible, "kafel ZA ścianą nie jest widoczny (brak LOS)")
    assert_true((7, 1) not in visible, "koniec drugiego korytarza też nie")


def test_shadowcast_sees_the_wall_itself() -> None:
    """Ściana ma być widoczna - gracz widzi jej lico, tylko nie widzi za nią."""
    fog = make_fog(BLOCKED_ROW)
    visible = fow.shadowcast(fog, 1, 1, 6)
    assert_true((4, 1) in visible, "sama ściana zamykająca korytarz jest widoczna")


def test_shadowcast_respects_range() -> None:
    fog = make_fog(["#" * 12] + ["#" + "." * 10 + "#"] + ["#" * 12])
    visible = fow.shadowcast(fog, 1, 1, 3)
    assert_true((4, 1) in visible, "kafel w zasięgu widoczny")
    assert_true((6, 1) not in visible, "kafel poza zasięgiem niewidoczny")


def test_raycast_stops_at_wall() -> None:
    fog = make_fog(BLOCKED_ROW)
    _dists, hits = fow.cast_rays(fog, 1 * TILE_SIZE + 8, 1 * TILE_SIZE + 8,
                                 6 * TILE_SIZE, settings.FOG_RAY_COUNT)
    assert_true((3, 1) in hits, "kafel przed ścianą trafiony")
    assert_true((5, 1) not in hits, "kafel ZA ścianą nietrafiony")


def test_raycast_does_not_leak_around_the_corner() -> None:
    """Zza rogu wolno wychylić się klinowi światła, ale nie przez ścianę."""
    fog = make_fog(L_CORRIDOR)
    _dists, hits = fow.cast_rays(fog, 1 * TILE_SIZE + 8, 1 * TILE_SIZE + 8,
                                 5 * TILE_SIZE, settings.FOG_RAY_COUNT)
    assert_true((3, 3) not in hits, "kafel za blokiem ścian (1 kafel w prawo od rogu) niewidoczny")
    assert_true((1, 3) in hits, "kafel w tym samym korytarzu, w dół - widoczny")


def test_raycast_polygon_ends_on_the_wall_face() -> None:
    """Dystans promienia w ścianę kończy się na LICU kafla, nie w jego środku."""
    fog = make_fog(BLOCKED_ROW)
    px = 1 * TILE_SIZE + 8
    dists, _hits = fow.cast_rays(fog, px, 1 * TILE_SIZE + 8, 6 * TILE_SIZE, 4)
    # promień 0 leci w prawo (cos=1): ściana zaczyna się na x = 4 * TILE_SIZE
    expected = 4 * TILE_SIZE - px
    assert_true(abs(dists[0] - expected) < 0.51,
                f"promień w prawo kończy się na licu ściany ({dists[0]:.2f} vs {expected})")


###############################################################################################################
def test_grade_is_monotonic_and_quantised() -> None:
    values = [fow.grade_distance(d / 4.0, 4.0, 1.0, 4) for d in range(0, 17)]
    assert_eq(values[0], settings.FOG_ALPHA_CLEAR, "w rdzeniu obraz jest nietknięty")
    assert_eq(values[-1], settings.FOG_ALPHA_VISIBLE_EDGE, "na granicy zasięgu pełne przyciemnienie")
    assert_true(all(b >= a for a, b in zip(values, values[1:])), "alfa rośnie z odległością")
    steps = sorted(set(v for v in values if v > settings.FOG_ALPHA_CLEAR))
    assert_eq(len(steps), 4, f"kwantyzacja daje dokładnie 4 stopnie: {steps}")


def test_grade_smooth_has_no_quantisation() -> None:
    values = [fow.grade_distance(d / 8.0, 4.0, 1.0, 0) for d in range(0, 33)]
    distinct = len(set(values))
    assert_true(distinct > 8, f"bez kwantyzacji stopni jest dużo więcej niż 4 ({distinct})")


###############################################################################################################
def test_wall_face_takes_brightness_from_the_floor() -> None:
    """Artefakt "czarnych kwadratów": ściana bez trafienia promieniem musi dostać
    jasność sąsiedniej widocznej podłogi, inaczej zostaje czarna w oświetlonym korytarzu."""
    fog = make_fog(ROOM)
    lit = {(1, 1): 0, (2, 1): 40}
    out = fow._expand_surfaces(fog, lit)
    assert_true(out[(1, 0)] <= 0, "ściana nad graczem świeci tak jak kafel gracza")
    assert_true(out[(2, 0)] <= 40, "ściana nad drugim kaflem bierze jego jasność")
    assert_true(all(alpha < settings.FOG_ALPHA_UNSEEN for alpha in out.values()),
                "żaden kafel dotknięty widocznością nie zostaje czarny")


def test_dead_end_tile_is_a_pocket_and_is_lit_from_the_corridor() -> None:
    """W korytarzu szerokości jednego kafla ślepy zaułek jest zamknięty z trzech stron.

    Promień z sąsiedniego kafla nie ma do jego środka linii wzroku (zmierzone
    w prototypie: żaden z pięciu punktów), więc bez zaliczenia go do "powierzchni"
    zostaje jednokaflową czarną dziurą pośrodku oświetlonego korytarza - dokładnie
    tam, gdzie generator lubi stawiać skrzynię.
    """
    fog = make_fog(BLOCKED_ROW)
    assert_true(fog.surface[1][3], "ślepy zaułek liczy się jak powierzchnia ściany")
    out = fow._expand_surfaces(fog, {(2, 1): 30})
    assert_true(out.get((3, 1), 255) <= 30, "zaułek dostaje jasność od korytarza")


def test_pocket_counts_as_surface() -> None:
    """Nisza na skrzynię (podłoga zamknięta z 3 stron) świeci jak lico ściany."""
    fog = make_fog([
        "#####",
        "#...#",
        "##.##",   # (2,2) to wnęka: ściany z lewej, prawej i z dołu
        "#####",
    ])
    assert_true(fog.surface[2][2], "wnęka jest traktowana jak powierzchnia ściany")
    out = fow._expand_surfaces(fog, {(2, 1): 20})
    assert_true(out.get((2, 2), 255) <= 20, "wnęka dostaje jasność od sąsiedniego kafla")


###############################################################################################################
def _observer(fog: fow.FogState, key: str, is_player: bool, tile: tuple[int, int],
              alpha: int = 0) -> None:
    obs = fow.Observer(is_player=is_player)
    obs.tiles = {tile: alpha}
    obs.origin = (tile[0] * TILE_SIZE + 8, tile[1] * TILE_SIZE + 8)
    fog.observers[key] = obs


def test_only_the_player_writes_memory() -> None:
    """D7: potwór świeci też w nieodkrytym korytarzu, ale nie zostawia pamięci."""
    fog = make_fog(L_CORRIDOR)
    _observer(fog, "@player", True, (1, 1))
    _observer(fog, "monster", False, (5, 5))
    fow._commit(fog)

    assert_true(fog.is_discovered(1, 1), "kafel gracza trafił do pamięci")
    assert_true(not fog.is_discovered(5, 5), "kafel potwora NIE trafił do pamięci")
    assert_eq(fog.mask.get_at((5, 5)).a, settings.FOG_ALPHA_CLEAR,
              "kafel potwora jest w tej klatce rozjaśniony")


def test_monster_trail_fades_back_to_black_not_to_memory() -> None:
    """Po przejściu potwora kafel wraca do 255, a kafel gracza do 230."""
    fog = make_fog(L_CORRIDOR)
    _observer(fog, "@player", True, (1, 1))
    _observer(fog, "monster", False, (5, 5))
    fow._commit(fog)

    # obie postacie odchodzą gdzie indziej
    fog.observers.clear()
    _observer(fog, "@player", True, (3, 1))
    fow._commit(fog)

    assert_eq(fog.mask.get_at((1, 1)).a, settings.FOG_ALPHA_REMEMBERED,
              "korytarz, w którym gracz był, zostaje w pamięci")
    assert_eq(fog.mask.get_at((5, 5)).a, settings.FOG_ALPHA_UNSEEN,
              "ślad potwora wraca do czerni - to nie jest pamięć gracza")


def test_discovery_survives_leaving_and_counts_once() -> None:
    fog = make_fog(L_CORRIDOR)
    _observer(fog, "@player", True, (1, 1))
    fow._commit(fog)
    first = fog.discovered_tiles
    fow._commit(fog)
    assert_eq(fog.discovered_tiles, first, "ponowny commit nie liczy tych samych kafli dwa razy")
    assert_true(first > 1, "gracz odkrył też lica ścian dookoła, nie tylko swój kafel")


def test_brightest_light_wins_on_overlap() -> None:
    fog = make_fog(L_CORRIDOR)
    _observer(fog, "@player", True, (1, 1), alpha=100)
    _observer(fog, "monster", False, (1, 1), alpha=20)
    fow._commit(fog)
    assert_eq(fog.mask.get_at((1, 1)).a, 20, "przy nakładaniu się świateł wygrywa jaśniejsze")


###############################################################################################################
def test_bitset_round_trip() -> None:
    fog = make_fog(L_CORRIDOR)
    _observer(fog, "@player", True, (1, 1))
    fow._commit(fog)
    data, w, h = fow.to_save(fog)

    fresh = make_fog(L_CORRIDOR)
    fow.apply_save(fresh, data, w, h)
    assert_eq(bytes(fresh.discovered), bytes(fog.discovered), "bitset przeżywa rundę base64")
    assert_eq(fresh.discovered_tiles, fog.discovered_tiles, "licznik odkrycia odtworzony")
    assert_eq(fresh.mask.get_at((1, 1)).a, settings.FOG_ALPHA_REMEMBERED,
              "maska przemalowana z bitsetu po wczytaniu")


def test_save_from_a_different_map_size_is_ignored() -> None:
    fog = make_fog(L_CORRIDOR)
    _observer(fog, "@player", True, (1, 1))
    fow._commit(fog)
    data, _w, _h = fow.to_save(fog)

    fresh = make_fog(BLOCKED_ROW)
    fow.apply_save(fresh, data, 7, 7)          # rozmiar z innego poziomu
    assert_eq(fresh.discovered_tiles, 0, "niezgodny rozmiar = mgła pusta, nie wyjątek")


def test_corrupt_save_is_survivable() -> None:
    fog = make_fog(BLOCKED_ROW)
    fow.apply_save(fog, "to nie jest base64!!", fog.w, fog.h)
    assert_eq(fog.discovered_tiles, 0, "śmieci w zapisie = mgła pusta")


def test_empty_save_leaves_fog_untouched() -> None:
    fog = make_fog(BLOCKED_ROW)
    _observer(fog, "@player", True, (1, 1))
    fow._commit(fog)
    before = fog.discovered_tiles
    fow.apply_save(fog, "", fog.w, fog.h)
    assert_eq(fog.discovered_tiles, before, "brak pola w starym zapisie niczego nie kasuje")


###############################################################################################################
def test_destroyed_wall_opens_the_view_without_rebuilding_fog() -> None:
    """Mgła czyta `path_finding_grid` ŻYWO - rozwalona ściana od razu przepuszcza wzrok."""
    fog = make_fog(BLOCKED_ROW)
    assert_true((5, 1) not in fow.shadowcast(fog, 1, 1, 6), "przed zniszczeniem ściana zasłania")
    fog.grid[1][4] = STEP_COST_GROUND                      # gracz rozwalił ścianę
    assert_true((5, 1) in fow.shadowcast(fog, 1, 1, 6), "po zniszczeniu widać dalej")


def main() -> None:
    pygame.init()
    tests = [
        test_shadowcast_stops_at_wall,
        test_shadowcast_sees_the_wall_itself,
        test_shadowcast_respects_range,
        test_raycast_stops_at_wall,
        test_raycast_does_not_leak_around_the_corner,
        test_raycast_polygon_ends_on_the_wall_face,
        test_grade_is_monotonic_and_quantised,
        test_grade_smooth_has_no_quantisation,
        test_wall_face_takes_brightness_from_the_floor,
        test_dead_end_tile_is_a_pocket_and_is_lit_from_the_corridor,
        test_pocket_counts_as_surface,
        test_only_the_player_writes_memory,
        test_monster_trail_fades_back_to_black_not_to_memory,
        test_discovery_survives_leaving_and_counts_once,
        test_brightest_light_wins_on_overlap,
        test_bitset_round_trip,
        test_save_from_a_different_map_size_is_ignored,
        test_corrupt_save_is_survivable,
        test_empty_save_leaves_fog_untouched,
        test_destroyed_wall_opens_the_view_without_rebuilding_fog,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} fog of war tests passed.")
    pygame.quit()


if __name__ == "__main__":
    main()
