#!/usr/bin/env python3
"""Off-map routine NPCs survive save/load (v5, buildings).

`_build_npc_states` / `_apply_npc_states` only ever walk the current map's
`scene.NPCs`. A routine character that is off doing its rounds on another map at
save time - a merchant at lunch in the tavern while the player is in the village -
is therefore invisible to both, and would be dropped from the save and reset to
config defaults on load. `_pin_routine_npcs_to_origin` and
`_apply_routine_npc_states` close that gap by reading and writing the live
`loaded_NPCs` objects directly, pinned to each character's home map.

Run from the project root:
    .venv/bin/python tests/test_save_load_routine_npc.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from pygame.math import Vector2 as pvec

from npc_runtime import NpcRuntime
from save_load.manager import SaveManager
from save_load.models import MapState, NPCState


def _mgr() -> SaveManager:
    # Skip __init__: these methods need only self, not a game or a backend.
    return SaveManager.__new__(SaveManager)


def _fake_npc(name: str, money: int, *, routine_key: str = "townsfolk",
              origin_map: str = "Village", logical_map: str = "Village"):
    npc = type("N", (), {})()
    npc.name = name
    npc.config_key = name
    npc.is_dead = False
    npc.items = []
    npc.pos = pvec(10, 20)
    npc.origin_map = origin_map
    npc.dialog_nodes = None
    npc.runtime = NpcRuntime(routine_key=routine_key, logical_map=logical_map)
    npc.model = type("M", (), {
        "attitude": "friendly", "health": 100, "money": money, "has_dialog": False,
    })()
    return npc


def _scene(current_map: str, **npcs):
    scene = type("S", (), {})()
    scene.current_map = current_map
    scene.loaded_NPCs = dict(npcs)
    return scene


# ---------------------------------------------------------------------------
# Saving: pin to the home map, from the live object
# ---------------------------------------------------------------------------

def test_off_map_routine_npc_is_saved_under_its_origin() -> None:
    """The player is in the village; Johny is at lunch in the tavern (another map)."""
    mgr = _mgr()
    johny = _fake_npc("JOHNY", money=999, origin_map="Village", logical_map="VillageHouse")
    scene = _scene("Village", JOHNY=johny)
    # Nothing for Johny on the current map (he is off it), and a stale copy left on
    # the map he is visiting - both wrong homes.
    maps = {
        "Village": MapState(name="Village"),
        "VillageHouse": MapState(name="VillageHouse", npc_states={"JOHNY": NPCState(name="JOHNY", money=1)}),
    }

    mgr._pin_routine_npcs_to_origin(scene, maps)

    assert "JOHNY" in maps["Village"].npc_states, "off-map merchant dropped from the save"
    assert maps["Village"].npc_states["JOHNY"].money == 999, "saved config default, not the live purse"
    assert maps["Village"].npc_states["JOHNY"].runtime.logical_map == "VillageHouse", "lost where it was"
    assert "JOHNY" not in maps["VillageHouse"].npc_states, "stale off-origin copy left behind (duplicate)"


def test_pin_creates_the_origin_map_if_it_has_no_state_yet() -> None:
    """Saving from inside the tavern must still file the villager under the village."""
    mgr = _mgr()
    bart = _fake_npc("BART", money=500, origin_map="Village", logical_map="Village")
    scene = _scene("VillageHouse", BART=bart)
    maps = {"VillageHouse": MapState(name="VillageHouse")}

    mgr._pin_routine_npcs_to_origin(scene, maps)

    assert "Village" in maps, "origin map was not created for a routine NPC that lives there"
    assert maps["Village"].npc_states["BART"].money == 500


def test_non_routine_npcs_are_left_to_the_normal_path() -> None:
    mgr = _mgr()
    snake = _fake_npc("SNAKE", money=0, routine_key="")
    scene = _scene("Maze_01", SNAKE=snake)
    maps = {"Maze_01": MapState(name="Maze_01")}

    mgr._pin_routine_npcs_to_origin(scene, maps)

    assert "SNAKE" not in maps["Maze_01"].npc_states, "a routine-less NPC was pinned"


# ---------------------------------------------------------------------------
# Loading: reach the live object even when it is off the current map
# ---------------------------------------------------------------------------

def test_restore_reaches_an_off_map_routine_npc() -> None:
    """The fresh object starts at config defaults; the save's purse must win."""
    mgr = _mgr()
    johny = _fake_npc("JOHNY", money=0, logical_map="Village")     # fresh, default purse
    scene = _scene("VillageHouse", JOHNY=johny)                    # loaded map is not his home
    saved_runtime = NpcRuntime(routine_key="townsfolk", logical_map="VillageHouse")
    maps = {"Village": MapState(name="Village", npc_states={
        "JOHNY": NPCState(name="JOHNY", money=999, health=100, runtime=saved_runtime, pos_x=5, pos_y=6),
    })}

    mgr._apply_routine_npc_states(scene, maps)

    assert johny.model.money == 999, "off-map merchant kept its config default purse"
    assert johny.runtime.logical_map == "VillageHouse", "did not restore where it was"


def test_restore_ignores_non_routine_npcs() -> None:
    mgr = _mgr()
    snake = _fake_npc("SNAKE", money=0, routine_key="")
    scene = _scene("Maze_01", SNAKE=snake)
    maps = {"Maze_01": MapState(name="Maze_01", npc_states={"SNAKE": NPCState(name="SNAKE", money=999)})}

    mgr._apply_routine_npc_states(scene, maps)

    assert snake.model.money == 0, "non-routine NPC should be restored by the normal path, not here"


if __name__ == "__main__":
    tests = [
        ("off-map routine NPC saved under origin", test_off_map_routine_npc_is_saved_under_its_origin),
        ("pin creates the origin map if absent", test_pin_creates_the_origin_map_if_it_has_no_state_yet),
        ("non-routine NPCs left to the normal path", test_non_routine_npcs_are_left_to_the_normal_path),
        ("restore reaches an off-map routine NPC", test_restore_reaches_an_off_map_routine_npc),
        ("restore ignores non-routine NPCs", test_restore_ignores_non_routine_npcs),
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
    if failures:
        print(f"  FAILED  {failures}/{total} tests")
        sys.exit(1)
    else:
        print(f"  PASSED  {total}/{total} tests")
