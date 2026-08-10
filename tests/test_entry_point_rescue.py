#!/usr/bin/env python3
"""Bohater nie ma prawa wylądować w ścianie po zmianie mapy.

Punkt wejścia, którego mapa nie zna (literówka w `destination_entry_point`,
przemianowany obiekt w Tiled, poziom labiryntu zbudowany z szablonu), stawiał
bohatera na pozycji awaryjnej = **geometrycznym środku mapy**. Środek
BLUNDERHAVEN wypada w środku lasu: gracz widzi las, nie może się ruszyć i nie
dostaje żadnej informacji, co się stało - awaria wygląda jak zawieszona gra.

Test pilnuje dwóch rzeczy, obu w `scene/map_loader.walkable_pos_near`:

1. kafel, po którym da się chodzić, **nie jest ruszany** (inaczej każda normalna
   zmiana mapy przesuwałaby bohatera, a punkty wejścia stoją dokładnie na granicy
   kafli - naiwne `pos // TILE_SIZE` wskazuje tam kafel POD nogami),
2. kafel w ścianie jest ratowany najbliższym wolnym.

Uruchamianie z katalogu projektu:
    .venv/bin/python tests/test_entry_point_rescue.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from settings import TILE_SIZE, Point, vec                       # noqa: E402
from scene.map_loader import walkable_pos_near                   # noqa: E402

WALL = 100      # dowolna wartość dodatnia = ściana, jak w `path_finding_grid`
FREE = 0


class FakePlayer:
    """Tyle z `NPC`, ile czyta ratunek: mapowanie pozycji na kafel.

    Kopia `NPC.get_tileset_coord` co do offsetu: pozycja postaci to `midbottom`,
    więc kafel liczy się od `y - 4`. Gdyby test miał własną, prostszą regułę,
    przestałby pilnować dokładnie tego, co się zepsuło.
    """

    def get_tileset_coord(self, pos: vec, offset_y: int = -4) -> Point:
        return Point(int(pos.x // TILE_SIZE), int((pos.y + offset_y) // TILE_SIZE))


class FakeScene:
    def __init__(self, grid: list[list[int]]) -> None:
        self.path_finding_grid = grid
        self.player = FakePlayer()


def _grid(rows: int = 8, cols: int = 8, wall: bool = False) -> list[list[int]]:
    return [[WALL if wall else FREE for _ in range(cols)] for _ in range(rows)]


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}\n  expected: {b!r}\n  actual:   {a!r}"


def test_a_walkable_tile_is_left_alone() -> None:
    """Zwykła zmiana mapy: `None` = nie ma czego ratować."""
    scene = FakeScene(_grid())

    assert_eq(walkable_pos_near(scene, vec(40, 40)), None)      # type: ignore[arg-type]


def test_an_entry_point_on_a_tile_border_is_not_a_false_positive() -> None:
    """Punkt wejścia stoi NA granicy kafli - i to jest normalny stan.

    `LOST_CORK_TAVERN_DOOR` ma y=752, czyli dokładnie granicę wierszy 46/47.
    Kafel pod nogami to 46; gdyby ratunek liczył `752 // 16 = 47`, przesuwałby
    bohatera przy każdym wyjściu z tawerny.
    """
    grid = _grid(rows=6, cols=6)
    grid[3][2] = WALL              # kafel POD nogami (ten "za granicą")
    scene = FakeScene(grid)

    # y = 48 to granica wierszy 2/3; postać stoi w wierszu 2
    assert_eq(walkable_pos_near(scene, vec(40, 48)), None)      # type: ignore[arg-type]


def test_a_tile_in_a_wall_is_rescued_to_the_nearest_free_one() -> None:
    grid = _grid(rows=6, cols=6, wall=True)
    grid[2][4] = FREE
    scene = FakeScene(grid)

    # bohater w ścianie w kaflu (2, 2) - najbliższy wolny to (2, 4)
    rescued = walkable_pos_near(scene, vec(2 * TILE_SIZE + 8, 2 * TILE_SIZE + 12))  # type: ignore[arg-type]

    assert rescued is not None, "ratunek nie znalazł wolnego kafla"
    assert_eq(int(rescued.x // TILE_SIZE), 4)
    assert_eq(int(rescued.y // TILE_SIZE), 2)


def test_a_map_with_no_free_tile_in_range_gives_up_quietly() -> None:
    """Brak ratunku to `None`, nie wyjątek - lepiej stać w ścianie niż wywalić grę."""
    scene = FakeScene(_grid(rows=4, cols=4, wall=True))

    assert_eq(walkable_pos_near(scene, vec(20, 20), max_tiles=2), None)   # type: ignore[arg-type]


def test_no_grid_at_all_is_not_an_error() -> None:
    """Mapa bez siatki A* (np. w połowie budowy) po prostu nie ma ratunku."""
    scene = FakeScene([])

    assert_eq(walkable_pos_near(scene, vec(20, 20)), None)      # type: ignore[arg-type]


if __name__ == "__main__":
    tests = [
        ("wolny kafel zostaje nietknięty", test_a_walkable_tile_is_left_alone),
        ("punkt wejścia na granicy kafli to nie awaria",
         test_an_entry_point_on_a_tile_border_is_not_a_false_positive),
        ("kafel w ścianie jest ratowany", test_a_tile_in_a_wall_is_rescued_to_the_nearest_free_one),
        ("brak wolnego kafla nie wywala gry", test_a_map_with_no_free_tile_in_range_gives_up_quietly),
        ("brak siatki nie jest błędem", test_no_grid_at_all_is_not_an_error),
    ]
    failures = 0
    for name, func in tests:
        try:
            func()
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            import traceback

            traceback.print_exc()
            failures += 1

    print(f"\n{'─' * 40}")
    total = len(tests)
    passed = total - failures
    if failures:
        print(f"  FAILED  {failures}/{total} tests")
        sys.exit(1)
    else:
        print(f"  PASSED  {passed}/{total} tests")
