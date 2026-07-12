#!/usr/bin/env python3
"""Integration tests for dialog-state persistence in save/load.

Run from the project root:
    .venv/bin/python tests/test_save_load_dialog_state.py
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from characters import NPC
from dialog.entities import DialogNode, DialogOption
from enums import AttitudeEnum
from save_load.manager import SaveManager
from save_load.models import NPCDialogState


def _make_graph() -> tuple[DialogNode, DialogNode, DialogOption]:
    """Build a tiny two-node graph: N1 --OPT1--> N2."""
    node2 = DialogNode(key="N2", text="txt_n2")
    opt = DialogOption(key="OPT1", next_node=node2, text="txt_opt1")
    node1 = DialogNode(key="N1", text="txt_n1", options=[opt])
    return node1, node2, opt


def test_build_npc_dialog_state_captures_state() -> None:
    """_build_npc_dialog_state serialises cursor, selected options, visited nodes, sentiment and known disposition."""
    node1, node2, opt = _make_graph()
    node1.visited = True
    opt.selected = True

    npc = SimpleNamespace(
        model=SimpleNamespace(has_dialog=True),
        dialog_nodes={"N1": node1, "N2": node2},
        dialog=node2,
        dialog_start_node=node1,
        selected_options_dict={"OPT1": True},
        sentiment=73,
        known_disposition={"neutral": 0},
    )

    mgr = SaveManager.__new__(SaveManager)
    state = mgr._build_npc_dialog_state(npc)

    assert state is not None
    assert state.current_node_key == "N2"
    assert state.dialog_start_node_key == "N1"
    assert state.selected_options == {"OPT1": True}
    assert state.visited_nodes == {"N1": True}
    assert state.sentiment == 73
    assert state.known_disposition == {"neutral": 0}


def test_build_npc_dialog_state_returns_none_without_graph() -> None:
    """NPCs without a dialog graph produce no dialog state."""
    npc = SimpleNamespace(model=SimpleNamespace(has_dialog=False), dialog_nodes=None)
    mgr = SaveManager.__new__(SaveManager)
    assert mgr._build_npc_dialog_state(npc) is None


def test_restore_dialog_state_rebuilds_conversation() -> None:
    """NPC.restore_dialog_state applies a saved NPCDialogState to a freshly built graph."""
    old_node1, old_node2, old_opt = _make_graph()
    old_node1.visited = True
    old_opt.selected = True

    state = NPCDialogState(
        current_node_key="N2",
        dialog_start_node_key="N1",
        selected_options={"OPT1": True},
        visited_nodes={"N1": True},
        sentiment=81,
        known_disposition={"neutral": 0},
    )

    # Simulate a fresh graph rebuild after load: new node/option objects, default flags.
    new_node1, new_node2, new_opt = _make_graph()
    npc = NPC.__new__(NPC)
    npc.model = SimpleNamespace(has_dialog=True)
    npc.config_key = "DIALOG_HAMMER"
    npc.dialog_nodes = {"N1": new_node1, "N2": new_node2}
    npc.dialog = new_node1  # would normally be the start node
    npc.dialog_start_node = new_node1
    npc.selected_options_dict = {}
    npc.sentiment = 50
    npc.known_disposition = {}
    npc.game = SimpleNamespace(
        conf=SimpleNamespace(dialogs={"DIALOG_HAMMER": {"START_NODE": "N1"}})
    )

    npc.restore_dialog_state(state)

    assert npc.dialog is new_node2
    assert npc.dialog.key == "N2"
    assert npc.selected_options_dict == {"OPT1": True}
    assert npc.sentiment == 81
    assert npc.known_disposition == {"neutral": 0}
    assert new_node1.visited is True
    assert new_node2.visited is False
    assert new_opt.selected is True


def test_restore_dialog_state_falls_back_to_start() -> None:
    """When the saved cursor key is missing, restore falls back to the graph entry node."""
    node1, node2, _opt = _make_graph()
    state = NPCDialogState(current_node_key="MISSING")

    npc = NPC.__new__(NPC)
    npc.model = SimpleNamespace(has_dialog=True)
    npc.config_key = "DIALOG_HAMMER"
    npc.dialog_nodes = {"N1": node1, "N2": node2}
    npc.dialog = None
    npc.dialog_start_node = None
    npc.selected_options_dict = {}
    npc.sentiment = 50
    npc.known_disposition = {}
    npc.game = SimpleNamespace(
        conf=SimpleNamespace(dialogs={"DIALOG_HAMMER": {"START_NODE": "N1"}})
    )

    npc.restore_dialog_state(state)

    assert npc.dialog is node1


def test_restore_dialog_state_is_noop_without_dialog() -> None:
    """NPCs that cannot converse ignore restore_dialog_state."""
    npc = NPC.__new__(NPC)
    npc.model = SimpleNamespace(has_dialog=False)
    npc.selected_options_dict = {}
    npc.sentiment = 50

    state = NPCDialogState(selected_options={"OPT1": True}, sentiment=99)
    npc.restore_dialog_state(state)

    assert npc.selected_options_dict == {}
    assert npc.sentiment == 50


if __name__ == "__main__":
    tests = [
        ("build captures state", test_build_npc_dialog_state_captures_state),
        ("build returns None without graph", test_build_npc_dialog_state_returns_none_without_graph),
        ("restore rebuilds conversation", test_restore_dialog_state_rebuilds_conversation),
        ("restore falls back to start", test_restore_dialog_state_falls_back_to_start),
        ("restore no-op without dialog", test_restore_dialog_state_is_noop_without_dialog),
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
