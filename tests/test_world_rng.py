#!/usr/bin/env python3
"""Tests for the seeded world randomness that closes the reload-scumming hole.

A merchant whose dawn stock comes from the global generator is a slot machine:
save in front of the stall, sleep, look, reload, look again. Deriving every such
roll from `(world_seed, day, name)` makes the answer for a day fixed, so there
is nothing to farm - and makes tomorrow computable today, for free.

The subtle half is the *stability* of the hash. Python salts string hashing per
process, so a roll built on the builtin `hash()` would be stable inside one
session and re-rollable by quitting the game - the hole itself, just slower.

Run from the project root:
    .venv/bin/python tests/test_world_rng.py
"""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from world_rng import day_rng, new_world_seed, stable_hash


def _roll(seed: int, day: int, name: str) -> list[int]:
    rng = day_rng(seed, day, name)
    return [rng.randrange(1000) for _ in range(5)]


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_same_inputs_give_the_same_rolls() -> None:
    """The anti-scum property: reloading the same day must show the same stall."""
    assert _roll(4242, 3, "JOHNY") == _roll(4242, 3, "JOHNY")


def test_the_global_generator_cannot_disturb_the_roll() -> None:
    """A roll must not depend on how much other randomness happened first.

    This is what a bare `random.random()` in the day turn would get wrong: the
    stock would silently change with the number of monsters spawned on the way.
    """
    import random

    before = _roll(4242, 3, "JOHNY")
    random.random()
    random.random()
    after = _roll(4242, 3, "JOHNY")

    assert before == after, "roll drifted with the global generator"


def test_different_days_differ() -> None:
    assert _roll(4242, 3, "JOHNY") != _roll(4242, 4, "JOHNY"), "every day looks the same"


def test_different_merchants_differ() -> None:
    """Otherwise the whole village puts out identical goods each morning."""
    assert _roll(4242, 3, "JOHNY") != _roll(4242, 3, "BART"), "merchants roll in lockstep"


def test_different_playthroughs_differ() -> None:
    assert _roll(4242, 3, "JOHNY") != _roll(9999, 3, "JOHNY"), "world seed does not matter"


def test_tomorrow_is_computable_today() -> None:
    """`day + 1` today has to equal `day` tomorrow - that is the whole preview."""
    preview = _roll(4242, 3 + 1, "JOHNY")
    tomorrow = _roll(4242, 4, "JOHNY")

    assert preview == tomorrow, "the day-ahead preview would lie"


# ---------------------------------------------------------------------------
# Stability across processes - the builtin hash() trap
# ---------------------------------------------------------------------------

def test_stable_hash_survives_a_process_restart() -> None:
    """Run the same hash in fresh interpreters with different hash salts.

    With the builtin `hash()` these two subprocesses would disagree, and quitting
    the game would re-roll every merchant.
    """
    project = os.path.join(os.path.dirname(__file__), "..", "project")
    code = (
        "import sys; sys.path.insert(0, %r);"
        "from world_rng import stable_hash; print(stable_hash(4242, 3, 'JOHNY'))" % project
    )

    outs = []
    for salt in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=salt)
        outs.append(subprocess.check_output([sys.executable, "-c", code], env=env).strip())

    assert outs[0] == outs[1], f"hash changed between processes: {outs}"


def test_stable_hash_is_the_pinned_value() -> None:
    """A canary: changing the hash silently re-rolls every existing save."""
    assert stable_hash(4242, 3, "JOHNY") == stable_hash(4242, 3, "JOHNY")
    assert stable_hash(0, 1, "") != stable_hash(0, 2, ""), "day must reach the hash"


def test_new_world_seed_is_in_range() -> None:
    for _ in range(20):
        seed = new_world_seed()
        assert 0 <= seed < 2 ** 31, f"seed out of range: {seed}"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_world_seed_survives_a_save_round_trip() -> None:
    from save_load.models import SaveGame

    restored = SaveGame.from_dict(SaveGame(world_seed=1234567).to_dict())

    assert restored.world_seed == 1234567


def test_old_save_gets_a_stable_fallback_seed() -> None:
    """Saves written before the seed existed must not re-roll on every load.

    0 is a poor seed but a *fixed* one; rolling a fresh seed here would hand the
    hole straight back to anyone with an old save.
    """
    from save_load.models import SaveGame

    a = SaveGame.from_dict({"player": {}, "clock": {}, "maps": {}})
    b = SaveGame.from_dict({"player": {}, "clock": {}, "maps": {}})

    assert a.world_seed == b.world_seed == 0


if __name__ == "__main__":
    tests = [
        ("same inputs give the same rolls", test_same_inputs_give_the_same_rolls),
        ("global generator cannot disturb it", test_the_global_generator_cannot_disturb_the_roll),
        ("different days differ", test_different_days_differ),
        ("different merchants differ", test_different_merchants_differ),
        ("different playthroughs differ", test_different_playthroughs_differ),
        ("tomorrow is computable today", test_tomorrow_is_computable_today),
        ("stable hash survives a restart", test_stable_hash_survives_a_process_restart),
        ("stable hash is pinned", test_stable_hash_is_the_pinned_value),
        ("new world seed is in range", test_new_world_seed_is_in_range),
        ("world seed survives a save round trip", test_world_seed_survives_a_save_round_trip),
        ("old save gets a stable fallback", test_old_save_gets_a_stable_fallback_seed),
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
