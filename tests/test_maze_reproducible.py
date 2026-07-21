#!/usr/bin/env python3
"""The maze must be reproducible from the single seed stored in the save.

Run from the project root:
    .venv/bin/python tests/test_maze_reproducible.py

A save file records a maze level as one integer. Everything the player can see
or interact with - the grid, where the chests stand, which monster model spawns
where - is drawn from a `random.Random` seeded with it. If any of those draws
leaks back to the global `random`, two runs with the same seed diverge, and the
saved health of "Maze_01_Bat_003" lands on a monster that is now a different
creature in a different corridor.

These tests pin exactly that: same seed -> same maze, and an unrelated consumer
hammering the global `random` in between must not change the outcome.
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))

from maze_generator.hunt_and_kill_maze import HuntAndKillMaze  # noqa: E402


def assert_eq(a: object, b: object, msg: str = "") -> None:
    if a != b:
        raise AssertionError(f"{msg}\n  expected: {b!r}\n  actual:   {a!r}")


def assert_true(cond: bool, msg: str = "") -> None:
    if not cond:
        raise AssertionError(msg)


COLS, ROWS = 8, 6


def _build(seed: int) -> list[list[int]]:
    """Generate a maze from ``seed`` and return its per-cell image indices."""
    maze = HuntAndKillMaze(COLS, ROWS)
    maze.generate(random.Random(seed))
    return [[cell.image_index for cell in row] for row in maze.cell_rows]


def _draws_after(seed: int, n_draws: int) -> list[int]:
    """Values a maze's generator yields *after* the layout, e.g. chest positions.

    Stands in for `Scene.load_interactions` / `load_NPCs`, which keep drawing from
    the same generator once the grid exists.
    """
    rng = random.Random(seed)
    maze = HuntAndKillMaze(COLS, ROWS)
    maze.generate(rng)
    return [rng.randrange(1000) for _ in range(n_draws)]


def test_same_seed_gives_same_layout() -> None:
    assert_eq(_build(12345), _build(12345), "same seed must rebuild the same grid")


def test_different_seeds_give_different_layouts() -> None:
    assert_true(_build(1) != _build(2), "different seeds must not collide")


def test_global_random_cannot_disturb_the_maze() -> None:
    """The whole point of a dedicated generator.

    Between saving and loading, the game draws from the global `random` for all
    sorts of things - weather, particles, loot elsewhere. None of it may shift
    the maze.
    """
    baseline = _build(999)

    random.seed(0)
    for _ in range(500):
        random.random()
    after_noise = _build(999)

    assert_eq(after_noise, baseline, "global random noise must not affect the maze")


def test_post_layout_draws_are_reproducible() -> None:
    """Chest and monster placement draw from the same generator, after the grid."""
    assert_eq(_draws_after(4242, 12), _draws_after(4242, 12),
              "placement draws must repeat for the same seed")


def test_generate_without_rng_still_works() -> None:
    """A brand new level has no seed yet and may fall back to global random."""
    maze = HuntAndKillMaze(COLS, ROWS)
    maze.generate()
    assert_eq(len(maze.cell_rows), ROWS, "maze built with the default generator")
    assert_true(any(cell.image_index for row in maze.cell_rows for cell in row),
                "cells got their image indices")


def main() -> None:
    tests = [
        test_same_seed_gives_same_layout,
        test_different_seeds_give_different_layouts,
        test_global_random_cannot_disturb_the_maze,
        test_post_layout_draws_are_reproducible,
        test_generate_without_rng_still_works,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} maze reproducibility tests passed.")


if __name__ == "__main__":
    main()
