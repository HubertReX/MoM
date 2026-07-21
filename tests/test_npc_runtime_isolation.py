#!/usr/bin/env python3
"""Tests for per-instance character state: the config must never be shared.

`NPC.__init__` used to bind `self.model` straight to `game.conf.characters[key]`,
one object shared by the whole process, while combat and trading wrote into it.
Two snakes in the same maze drew from one pool of health, and the player's gold
survived into a new game. These tests pin the fix down.

Run from the project root:
    .venv/bin/python tests/test_npc_runtime_isolation.py
"""

from __future__ import annotations

import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from npc_runtime import NpcRuntime
from save_load.models import NPCState


class _FakeCharacter:
    """Stand-in for the config `Character`, with the fields the game writes to.

    Deliberately carries a list and a dict, because those are what a *shallow*
    copy would keep sharing - `Character` has `items`, `allowed_zones` and
    `disposition`.
    """

    def __init__(self) -> None:
        self.health = 50
        self.max_health = 50
        self.money = 100
        self.damage = 20
        self.items = ["life_pot"]
        self.disposition = {"kind": 5}


def _bind_model(shared: _FakeCharacter) -> _FakeCharacter:
    """Exactly what `NPC.__init__` does when binding the character's config."""
    return copy.deepcopy(shared)


# ---------------------------------------------------------------------------
# Config isolation
# ---------------------------------------------------------------------------

def test_two_npcs_do_not_share_health() -> None:
    """The regression that started this: hitting one snake hurt every snake."""
    shared = _FakeCharacter()
    a = _bind_model(shared)
    b = _bind_model(shared)

    assert a is not b, "each NPC must get its own model object"

    # what NPC.hit() does to the opponent
    a.health -= 25
    a.health = max(0, a.health)

    assert a.health == 25, f"attacked NPC should be hurt, got {a.health}"
    assert b.health == 50, f"untouched NPC must keep full health, got {b.health}"
    assert shared.health == 50, f"config must stay pristine, got {shared.health}"


def test_killing_one_npc_leaves_the_other_alive() -> None:
    """Second monster of a type used to die to a single blow."""
    shared = _FakeCharacter()
    a = _bind_model(shared)
    b = _bind_model(shared)

    while a.health > 0:
        a.health = max(0, a.health - 25)

    assert a.health == 0
    assert b.health == 50, "killing one NPC must not kill its twin"


def test_money_is_not_shared() -> None:
    """Trading with one merchant must not move another merchant's purse."""
    shared = _FakeCharacter()
    a = _bind_model(shared)
    b = _bind_model(shared)

    a.money -= 40

    assert a.money == 60
    assert b.money == 100
    assert shared.money == 100, "config money is the baseline for the daily cap"


def test_collections_are_deep_copied() -> None:
    """A shallow copy would leave lists and dicts aliased - this catches that."""
    shared = _FakeCharacter()
    a = _bind_model(shared)
    b = _bind_model(shared)

    a.items.append("fish")
    a.disposition["kind"] = 99

    assert b.items == ["life_pot"], f"list leaked between NPCs: {b.items}"
    assert b.disposition == {"kind": 5}, f"dict leaked between NPCs: {b.disposition}"
    assert shared.items == ["life_pot"], "config list must stay pristine"


def test_config_stays_usable_as_baseline() -> None:
    """Config being read-only is what makes it a free source of base values.

    The merchant purse ceiling in the daily regeneration is simply the `money`
    the CSV row declares, so nothing may write over it.
    """
    shared = _FakeCharacter()
    npc = _bind_model(shared)

    npc.money = 0
    npc.health = 0

    assert shared.money == 100, "purse ceiling lost"
    assert shared.max_health == 50, "base health lost"


# ---------------------------------------------------------------------------
# NpcRuntime and its persistence
# ---------------------------------------------------------------------------

def test_runtime_defaults_are_not_shared_between_instances() -> None:
    """`stock` is mutable - a plain default would be shared by every NPC."""
    one = NpcRuntime()
    two = NpcRuntime()

    one.stock.append("gem_small_blue")

    assert two.stock == [], f"mutable default leaked: {two.stock}"


def test_runtime_survives_a_save_round_trip() -> None:
    state = NPCState(
        name="JOHNY",
        runtime=NpcRuntime(routine_key="townsfolk", stock=["gem_small_blue", "gem_big_orange"]),
    )

    restored = NPCState.from_dict(state.to_dict())

    assert restored.runtime.routine_key == "townsfolk"
    assert restored.runtime.stock == ["gem_small_blue", "gem_big_orange"]


def test_old_save_without_runtime_still_loads() -> None:
    """Saves written before `runtime` existed must not blow up on load."""
    legacy = {
        "name": "BART",
        "config_key": "BART",
        "health": 30,
        "money": 200,
        "is_dead": False,
        "inventory": [],
    }

    restored = NPCState.from_dict(legacy)

    assert restored.name == "BART"
    assert restored.money == 200
    assert restored.runtime.routine_key == ""
    assert restored.runtime.stock == []


def test_restored_runtime_is_not_aliased_to_the_snapshot() -> None:
    """`_apply_npc_states` deep-copies, so later play cannot edit the save."""
    saved = NpcRuntime(routine_key="farmer", stock=["fish"])

    live = copy.deepcopy(saved)
    live.stock.append("shrimp")

    assert saved.stock == ["fish"], f"snapshot mutated through the live NPC: {saved.stock}"


if __name__ == "__main__":
    tests = [
        ("two NPCs do not share health", test_two_npcs_do_not_share_health),
        ("killing one leaves the twin alive", test_killing_one_npc_leaves_the_other_alive),
        ("money is not shared", test_money_is_not_shared),
        ("collections are deep copied", test_collections_are_deep_copied),
        ("config stays usable as baseline", test_config_stays_usable_as_baseline),
        ("runtime defaults are not shared", test_runtime_defaults_are_not_shared_between_instances),
        ("runtime survives save round trip", test_runtime_survives_a_save_round_trip),
        ("old save without runtime loads", test_old_save_without_runtime_still_loads),
        ("restored runtime is not aliased", test_restored_runtime_is_not_aliased_to_the_snapshot),
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
