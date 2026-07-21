#!/usr/bin/env python3
"""Tests for reaching a destination that is not standing on a floor tile.

A* refuses to enter a blocked tile, so a goal placed on one is unreachable and
`a_star` returns nothing - and `NPC.find_path` reacts to nothing by clearing the
waypoints and zeroing the velocity, i.e. the character freezes where it stands.

That is a fine answer for "walk into this wall" and the wrong one for every named
place an author puts on a map. Markers land *on* the thing they mark: the tavern,
a market stall, a doorway. Measured on Village.tmx, five of the eleven places
added for the daily routines sat on wall tiles - the tavern and all four homes -
which is exactly why nobody ever walked home at night.

Run from the project root:
    .venv/bin/python tests/test_pathfinding_goal.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from maze_generator.maze_utils import a_star, nearest_walkable

FLOOR = -100
WALL = 100

#  0 1 2 3 4
#  . . . . .   0
#  . # # # .   1
#  . # # # .   2   <- (2,2) is the middle of a solid block
#  . # # # .   3
#  . . . . .   4
_BUILDING = [
    [FLOOR, FLOOR, FLOOR, FLOOR, FLOOR],
    [FLOOR, WALL, WALL, WALL, FLOOR],
    [FLOOR, WALL, WALL, WALL, FLOOR],
    [FLOOR, WALL, WALL, WALL, FLOOR],
    [FLOOR, FLOOR, FLOOR, FLOOR, FLOOR],
]


def test_a_walkable_goal_is_returned_unchanged() -> None:
    """The common case must cost nothing and move nothing."""
    assert nearest_walkable(_BUILDING, (0, 0)) == (0, 0)
    assert nearest_walkable(_BUILDING, (4, 2)) == (4, 2)


def test_a_goal_on_a_wall_snaps_to_the_edge() -> None:
    """A marker on the tavern means "walk up to the tavern"."""
    snapped = nearest_walkable(_BUILDING, (1, 1))

    assert snapped is not None, "goal on a wall was given up on"
    assert _BUILDING[snapped[0]][snapped[1]] <= 0, f"snapped onto another wall: {snapped}"
    assert max(abs(snapped[0] - 1), abs(snapped[1] - 1)) == 1, f"took a longer way than needed: {snapped}"


def test_the_closest_ring_wins() -> None:
    """Deep inside the block the answer must still be the nearest floor tile."""
    snapped = nearest_walkable(_BUILDING, (2, 2))

    assert snapped is not None
    assert max(abs(snapped[0] - 2), abs(snapped[1] - 2)) == 2, f"not the nearest ring: {snapped}"


def test_the_snapped_goal_is_actually_reachable() -> None:
    """The point of the whole exercise: A* finds a path where it found none."""
    start = (0, 0)
    blocked_goal = (2, 2)

    assert a_star(_BUILDING, start, blocked_goal) is None, "test grid is not blocking anything"

    snapped = nearest_walkable(_BUILDING, blocked_goal)
    assert a_star(_BUILDING, start, snapped), f"snapped goal {snapped} still unreachable"


def test_a_hopeless_goal_still_returns_none() -> None:
    """Walled in beyond the search radius: give up honestly rather than wander."""
    solid = [[WALL] * 5 for _ in range(5)]

    assert nearest_walkable(solid, (2, 2)) is None


def test_out_of_bounds_goal_does_not_raise() -> None:
    assert nearest_walkable(_BUILDING, (99, 99), max_radius=2) is None


def test_every_place_on_the_village_map_is_now_reachable() -> None:
    """The real map, the real regression: no named place may be a dead end.

    Fails loudly if a future edit puts a place somewhere genuinely walled in, and
    documents which of them needed the snap.
    """
    import pygame

    pygame.init()
    pygame.display.set_mode((64, 64))
    from pytmx.util_pygame import load_pygame

    from settings import STEP_COST_WALL, TILE_SIZE

    tmx = load_pygame(os.path.join(os.path.dirname(__file__), "..", "project",
                                   "assets", "NinjaAdventure", "maps", "Village.tmx"))
    walls = tmx.get_layer_by_name("walls")
    grid = [[FLOOR] * walls.width for _ in range(walls.height)]
    for x, y, _sprite in walls.tiles():
        grid[y][x] = STEP_COST_WALL

    snapped_count = 0
    for obj in tmx.get_layer_by_name("places"):
        goal = (int(obj.y // TILE_SIZE), int(obj.x // TILE_SIZE))
        walkable = nearest_walkable(grid, goal)
        assert walkable is not None, f"place '{obj.name}' is walled in beyond rescue"
        if walkable != goal:
            snapped_count += 1

    assert snapped_count, "no place needed snapping - has the map or the fix changed?"


if __name__ == "__main__":
    tests = [
        ("walkable goal returned unchanged", test_a_walkable_goal_is_returned_unchanged),
        ("goal on a wall snaps to the edge", test_a_goal_on_a_wall_snaps_to_the_edge),
        ("closest ring wins", test_the_closest_ring_wins),
        ("snapped goal is actually reachable", test_the_snapped_goal_is_actually_reachable),
        ("hopeless goal returns None", test_a_hopeless_goal_still_returns_none),
        ("out of bounds does not raise", test_out_of_bounds_goal_does_not_raise),
        ("every place on Village.tmx reachable", test_every_place_on_the_village_map_is_now_reachable),
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
