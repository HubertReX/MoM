#!/usr/bin/env python3
"""Unit tests for the quest/dialog condition adapters (Q-02).

Run from the project root:
    .venv/bin/python tests/test_quest_context_adapter.py

The point of these: ``visited(npc, node)`` must answer truthfully about an NPC
the player is not standing next to — on another map, or on a map not re-entered
since loading a save. That is Pułapka 5, and getting it wrong means a quest
silently never fires.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from dialog.context_adapter import find_visited_node
from quest.context_adapter import QuestConditionContext
from save_load.models import MapState, NPCDialogState, NPCState


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def _npc(config_key: str, visited: dict[str, bool]) -> SimpleNamespace:
    nodes = {
        key: SimpleNamespace(key=key, visited=was_visited)
        for key, was_visited in visited.items()
    }
    return SimpleNamespace(config_key=config_key, dialog_nodes=nodes)


def _item(name: str, count: int = 1) -> SimpleNamespace:
    return SimpleNamespace(name=name, model=SimpleNamespace(count=count))


def _pending_map(config_key: str, visited: dict[str, bool]) -> MapState:
    return MapState(
        name="Tavern",
        npc_states={
            "Barman": NPCState(
                name="Barman",
                config_key=config_key,
                dialog_state=NPCDialogState(visited_nodes=visited),
            )
        },
    )


def _scene(
    *,
    loaded: dict[str, SimpleNamespace] | None = None,
    cached_maps: dict[str, Any] | None = None,
    pending: dict[str, MapState] | None = None,
    items: list[SimpleNamespace] | None = None,
    quest_state: object | None = None,
) -> SimpleNamespace:
    scene = SimpleNamespace(
        loaded_NPCs=loaded or {},
        loaded_maps=cached_maps or {},
        pending_map_states=pending or {},
        player=SimpleNamespace(items=items or []),
    )
    if quest_state is not None:
        scene.quest_state = quest_state
    return scene


def test_visited_finds_npc_on_current_map() -> None:
    scene = _scene(loaded={"barman": _npc("BARMAN_ABSINTHRAYNER", {"012": True, "013": False})})

    assert_true(find_visited_node(scene, "BARMAN_ABSINTHRAYNER", "012"), "visited node")
    assert_true(not find_visited_node(scene, "BARMAN_ABSINTHRAYNER", "013"), "unvisited node")
    assert_true(not find_visited_node(scene, "BARMAN_ABSINTHRAYNER", "999"), "unknown node")


def test_visited_finds_npc_on_another_loaded_map() -> None:
    """The NPC is on a map visited earlier this session: objects still cached."""
    scene = _scene(
        loaded={"smith": _npc("HAMMER_HOAXHEART", {"009": False})},
        cached_maps={"Tavern": {"NPCs": [_npc("BARMAN_ABSINTHRAYNER", {"012": True})]}},
    )

    assert_true(
        find_visited_node(scene, "BARMAN_ABSINTHRAYNER", "012"),
        "off-map NPC found in the loaded_maps cache",
    )
    # the current map still wins for NPCs that are here
    assert_true(not find_visited_node(scene, "HAMMER_HOAXHEART", "009"), "current map NPC")


def test_visited_finds_npc_in_a_pending_map_state() -> None:
    """After a load, a map not re-entered yet has no NPC objects at all.

    Only `pending_map_states` knows the Barman was ever spoken to — without this
    tier the quest silently reads False until the player happens to walk back
    into the tavern.
    """
    scene = _scene(pending={"Tavern": _pending_map("BARMAN_ABSINTHRAYNER", {"012": True})})

    assert_true(find_visited_node(scene, "BARMAN_ABSINTHRAYNER", "012"), "found in pending state")
    assert_true(not find_visited_node(scene, "BARMAN_ABSINTHRAYNER", "013"), "unvisited node")


def test_visited_is_false_for_unknown_npc() -> None:
    """Never met = never visited. False here is the truth, not a failure."""
    scene = _scene(loaded={"barman": _npc("BARMAN_ABSINTHRAYNER", {"012": True})})
    assert_true(not find_visited_node(scene, "MADAME_SARCASMIA", "001"), "never-seen NPC")


def test_quest_context_visited_and_items() -> None:
    scene = _scene(
        loaded={"barman": _npc("BARMAN_ABSINTHRAYNER", {"012": True})},
        items=[_item("MERMAIDS_TEAR", 2), _item("GNOMES_WHISKER")],
    )
    ctx = QuestConditionContext(scene)

    assert_true(ctx.visited("012", npc="BARMAN_ABSINTHRAYNER"), "quest ctx visited")
    assert_true(ctx.has_item("MERMAIDS_TEAR"), "has_item")
    assert_true(not ctx.has_item("PHOENIX_FEATHER"), "missing item")
    assert_eq(ctx.item_count("MERMAIDS_TEAR"), 2, "item_count counts the stack")
    assert_eq(ctx.item_count("GNOMES_WHISKER"), 1, "single item")
    assert_eq(ctx.item_count("PHOENIX_FEATHER"), 0, "absent item counts zero")


def test_quest_context_rejects_visited_without_npc() -> None:
    """A quest has no current NPC — answering False would hang the quest forever."""
    ctx = QuestConditionContext(_scene())
    try:
        ctx.visited("012")
    except ValueError:
        return
    raise AssertionError("expected ValueError for visited() without an npc")


def test_quest_done_reads_scene_state() -> None:
    class FakeQuestState:
        def is_done(self, key: str) -> bool:
            return key == "Q01_S01_LEARN_ABOUT_CURSE"

    ctx = QuestConditionContext(_scene(quest_state=FakeQuestState()))
    assert_true(ctx.quest_done("Q01_S01_LEARN_ABOUT_CURSE"), "done quest")
    assert_true(not ctx.quest_done("Q03_S00_LEARN_ABOUT_CURSE"), "unfinished quest")

    # before the quest runtime is wired up (Q-07) there is simply nothing to ask
    assert_true(not QuestConditionContext(_scene()).quest_done("Q01"), "no quest state yet")


def main() -> None:
    tests = [
        test_visited_finds_npc_on_current_map,
        test_visited_finds_npc_on_another_loaded_map,
        test_visited_finds_npc_in_a_pending_map_state,
        test_visited_is_false_for_unknown_npc,
        test_quest_context_visited_and_items,
        test_quest_context_rejects_visited_without_npc,
        test_quest_done_reads_scene_state,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} quest context adapter tests passed.")


if __name__ == "__main__":
    main()
