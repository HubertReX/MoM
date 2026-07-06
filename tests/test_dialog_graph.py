#!/usr/bin/env python3
"""Unit tests for dialog/graph.py — build a sample graph and walk a path.

Run from the project root:
    .venv/bin/python tests/test_dialog_graph.py

Pure logic (no pygame / SDL needed), but we add ``project`` to the path the
same way the save_load tests do.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))

from dialog import (
    DialogNode,
    DialogOption,
    NodeVisitResult,
    NodeVisitResultCategory,
    get_start_node,
    init_dialog,
)


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


# A small but complete graph, mirroring RPG config.json shape:
# START --(go)--> MIDDLE --(take_reward)--> END(is_final, gives 10 gold)
#            \--(leave)------------------> END
SAMPLE: dict[str, object] = {
    "START_NODE": "T_DN_START",
    "NODE_RESULTS": {
        "T_NR_REWARD": {
            "category": "money_received",
            "money": 10,
            "items": [],
        },
    },
    "DIALOG_NODES": {
        "T_DN_START": {"text": "M_T_DN_START"},
        "T_DN_MIDDLE": {"text": "M_T_DN_MIDDLE"},
        "T_DN_END": {
            "text": "M_T_DN_END",
            "is_final": True,
            "result": "T_NR_REWARD",
        },
    },
    "DIALOG_OPTIONS": {
        "T_DO_GO": {"next_node": "T_DN_MIDDLE", "text": "M_T_DO_GO", "order": 1},
        "T_DO_TAKE": {
            "next_node": "T_DN_END",
            "text": "M_T_DO_TAKE",
            "order": 1,
            "sentiment": "😇",
        },
        "T_DO_LEAVE": {"next_node": "T_DN_END", "text": "M_T_DO_LEAVE", "order": 2},
    },
    "NODES_OPTIONS": {
        "T_DN_START": ["T_DO_GO"],
        "T_DN_MIDDLE": ["T_DO_TAKE", "T_DO_LEAVE"],
    },
}


def test_build_shapes() -> None:
    nodes = init_dialog(SAMPLE)  # type: ignore[arg-type]
    assert_eq(len(nodes), 3, "node count")
    assert_true(all(isinstance(n, DialogNode) for n in nodes.values()), "node types")

    start = get_start_node(SAMPLE, nodes)  # type: ignore[arg-type]
    assert_eq(start.key, "T_DN_START", "start node key")
    assert_eq(len(start.options), 1, "start option count")
    assert_true(isinstance(start.options[0], DialogOption), "option type")

    # result resolved and enum coerced
    end = nodes["T_DN_END"]
    assert_true(end.is_final, "end is_final")
    assert_true(isinstance(end.result, NodeVisitResult), "result attached")
    assert_eq(end.result.category, NodeVisitResultCategory.MONEY_RECEIVED, "category enum")
    assert_eq(end.result.money, 10, "result money")

    # nodes without a result stay None
    assert_true(nodes["T_DN_MIDDLE"].result is None, "middle has no result")


def test_walk_path_to_final() -> None:
    """Follow next_node references in memory from START to a final node."""
    nodes = init_dialog(SAMPLE)  # type: ignore[arg-type]
    node = get_start_node(SAMPLE, nodes)  # type: ignore[arg-type]

    visited_keys = [node.key]
    guard = 0
    while not node.is_final:
        guard += 1
        assert_true(guard < 10, "path did not terminate (cycle?)")
        assert_true(len(node.options) > 0, f"dead end at {node.key}")
        # take the first option; next_node is a live object reference
        node = node.options[0].next_node
        visited_keys.append(node.key)

    assert_eq(visited_keys, ["T_DN_START", "T_DN_MIDDLE", "T_DN_END"], "walked path")
    assert_true(node.is_final, "ended on final node")

    # option object identity: next_node is the same object as in the graph dict
    take = nodes["T_DN_MIDDLE"].options[0]
    assert_true(take.next_node is nodes["T_DN_END"], "next_node is shared instance")
    assert_eq(take.sentiment, "😇", "option sentiment carried through")


def test_debug_options() -> None:
    plain = init_dialog(SAMPLE)  # type: ignore[arg-type]
    dbg = init_dialog(SAMPLE, debug=True)  # type: ignore[arg-type]

    assert_eq(len(plain["T_DN_START"].options), 1, "plain start options")
    # debug adds: DEBUG_START_NODE + one DEBUG_END_NODE per is_final node (1)
    dbg_keys = [o.key for o in dbg["T_DN_START"].options]
    assert_true("DEBUG_START_NODE" in dbg_keys, "debug start option present")
    assert_true("DEBUG_END_NODE_T_DN_END" in dbg_keys, "debug end option present")
    assert_eq(len(dbg["T_DN_START"].options), 3, "start options with debug")


def _expect_value_error(fn, msg: str) -> None:  # type: ignore[no-untyped-def]
    try:
        fn()
    except ValueError:
        return
    raise AssertionError(f"expected ValueError: {msg}")


def test_validation_errors() -> None:
    # dangling next_node
    bad_opt = {
        "START_NODE": "N",
        "NODE_RESULTS": {},
        "DIALOG_NODES": {"N": {"text": "t"}},
        "DIALOG_OPTIONS": {"O": {"next_node": "MISSING", "text": "t"}},
        "NODES_OPTIONS": {"N": ["O"]},
    }
    _expect_value_error(lambda: init_dialog(bad_opt), "dangling next_node")  # type: ignore[arg-type]

    # missing START_NODE
    no_start = {
        "NODE_RESULTS": {},
        "DIALOG_NODES": {"N": {"text": "t"}},
        "DIALOG_OPTIONS": {},
        "NODES_OPTIONS": {},
    }
    _expect_value_error(lambda: init_dialog(no_start), "missing START_NODE")  # type: ignore[arg-type]

    # node references unknown result
    bad_result = {
        "START_NODE": "N",
        "NODE_RESULTS": {},
        "DIALOG_NODES": {"N": {"text": "t", "result": "NOPE"}},
        "DIALOG_OPTIONS": {},
        "NODES_OPTIONS": {},
    }
    _expect_value_error(lambda: init_dialog(bad_result), "unknown result")  # type: ignore[arg-type]


def main() -> None:
    tests = [
        test_build_shapes,
        test_walk_path_to_final,
        test_debug_options,
        test_validation_errors,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} dialog graph tests passed.")


if __name__ == "__main__":
    main()
