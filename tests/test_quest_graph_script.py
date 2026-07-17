#!/usr/bin/env python3
"""Unit tests for scripts/quest_graph.py - the quest DAG picture (Q-11).

Run from the project root:
    .venv/bin/python tests/test_quest_graph_script.py

The drawing is checked by eye in Obsidian; what is pinned here is the analysis
underneath, which is the part that can be quietly wrong: the ranks the picture
implies, and `uncloseable` - the one check `validate_references()` cannot make,
because it lives in the gap between config and game code.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.dirname(__file__))

from quest.graph import init_quests
from quest_graph import graph_to_dict, levels, markup_runs, uncloseable
from test_quest_entities import SAMPLE

Q00 = "Q00_S00_WHAT_IS_GOING_ON"
Q01_S00 = "Q01_S00_BREAK_THE_CURSE"
Q01_S01 = "Q01_S01_LEARN_ABOUT_CURSE"
Q01_S05 = "Q01_S05_MEET_MADAME_SARCASMIA"
Q03_S00 = "Q03_S00_LEARN_ABOUT_CURSE"
Q03_S01 = "Q03_S01_WHO_HAS_MORE_KNOWLEDGE"


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def _defs():  # type: ignore[no-untyped-def]
    return init_quests(SAMPLE)  # type: ignore[arg-type]


def test_rank_follows_the_longest_unlock_path() -> None:
    """A quest waits for *all* of its requires, so its rank is its slowest dep + 1.

    Q01_S05 is the case that separates this from a BFS: its parent sits at rank 1,
    but it also requires Q01_S01 at rank 2. Shortest-path would draw it at rank 2,
    beside the very quest it is waiting for - a picture claiming the two open
    together, when one gates the other.
    """
    rank = levels(_defs())

    assert_eq(rank[Q00], 0, "nothing gates the opening quest")
    assert_eq(rank[Q01_S00], 1, "one requires deep")
    assert_eq(rank[Q01_S01], 2, "a step sits one past its thread")
    assert_eq(rank[Q01_S05], 3, "past its requires (2), not just its parent (1)")
    assert_true(rank[Q01_S05] > rank[Q01_S01], "drawn after what it waits for")
    assert_eq(rank[Q03_S00], 3, "a cross-chain requires still ranks")
    assert_eq(rank[Q03_S01], 4, "and its steps follow it")


def test_manual_quests_are_flagged_as_uncloseable() -> None:
    """`manual` is a promise kept in code - and nothing in config keeps it.

    `is_complete` returns False for `manual` forever (engine.py), so the only
    thing that closes one is a `mark_done` call somebody has to write. That gap
    is invisible to `init_quests`, which is why the graph asks about it.
    """
    broken = uncloseable(_defs())

    assert_eq(list(broken), [Q01_S00], f"only the manual quest: {broken}")
    assert_true("manual" in broken[Q01_S00], "the reason names the mode")
    assert_true("mark_done" in broken[Q01_S00], "and names what would close it")


def test_an_umbrella_inherits_its_steps_problem() -> None:
    """A thread over a step nothing can close is a thread that never ends."""
    config = {**SAMPLE, Q03_S01: {**SAMPLE[Q03_S01], "completion": "manual", "test": None}}  # type: ignore[dict-item]
    broken = uncloseable(init_quests(config))  # type: ignore[arg-type]

    assert_true(Q03_S01 in broken, "the step itself")
    assert_true(Q03_S00 in broken, "and the umbrella over it")
    assert_true(Q03_S01 in broken[Q03_S00], "the umbrella's reason names the guilty step")


def test_a_healthy_chain_is_not_flagged() -> None:
    """Q03: an all_subquests umbrella over three test steps closes by itself."""
    broken = uncloseable(_defs())

    for key in (Q00, Q01_S01, Q01_S05, Q03_S00, Q03_S01):
        assert_true(key not in broken, f"{key} closes on its own")


def test_both_gate_kinds_become_edges() -> None:
    """requires and parent are different gates and must stay distinguishable."""
    data = graph_to_dict(_defs(), {}, {})
    edges = {(e["from"], e["to"]): e["kind"] for e in data["edges"]}

    assert_eq(edges[(Q00, Q01_S00)], "requires", "done-gate")
    assert_eq(edges[(Q01_S00, Q01_S01)], "parent", "unlocked-gate, drawn thread -> step")
    assert_eq(edges[(Q01_S01, Q03_S00)], "requires", "the cross-chain edge is not lost")
    # Q01_S05 is gated both ways: both edges exist, neither swallows the other
    assert_eq(edges[(Q01_S00, Q01_S05)], "parent", "its thread")
    assert_eq(edges[(Q01_S01, Q01_S05)], "requires", "and its prerequisite")


def test_names_resolve_through_messages() -> None:
    """D3: quests hold i18n keys; the picture shows what the player would read."""
    defs = _defs()
    messages = {"M_QUEST_Q00_S00_WHAT_IS_GOING_ON_NAME": "O co tu chodzi?"}
    nodes = {n["id"]: n for n in graph_to_dict(defs, messages, {})["nodes"]}

    assert_eq(nodes[Q00]["name"], "O co tu chodzi?", "resolved")
    # an unresolved key falls back to the key itself rather than an empty node
    assert_eq(nodes[Q01_S00]["name"], "M_QUEST_Q01_S00_BREAK_THE_CURSE_NAME", "fallback")


def test_markup_flattens_to_bold_runs() -> None:
    """Every kind of styling becomes bold, and nothing prints its own tags.

    The tooltip is an Obsidian note in the reader's theme, with none of MoM's
    palette. Inventing colours here would imply distinctions the game does not
    make; bold says "the author marked this" and stops.
    """
    runs = markup_runs("[char]Zielarka[/char] warzy [num]3[/num] mikstury")

    assert_eq([r["text"] for r in runs], ["Zielarka", " warzy ", "3", " mikstury"], "split on tags")
    assert_eq([r["bold"] for r in runs], [True, False, True, False], "any tag -> bold")
    assert_true(all("[" not in r["text"] for r in runs), "no tag leaks into the text")


def test_markup_runs_coalesce() -> None:
    """One DOM node per run, so runs that read the same must not be split."""
    assert_eq(markup_runs("zwykła proza bez tagów"),
              [{"text": "zwykła proza bez tagów", "bold": False}], "one run")
    # [/] and [/char] mean the same thing, so they must produce the same runs
    assert_eq(markup_runs("[char]X[/]y"), markup_runs("[char]X[/char]y"), "closers agree")


def test_markup_runs_drop_inline_sprites() -> None:
    """A coin sprite has no tooltip equivalent; dropping beats printing ':name:'."""
    runs = markup_runs("koszt :heart: dużo")
    assert_true(all(":heart:" not in r["text"] for r in runs), f"the marker is gone: {runs}")


def test_node_labels_are_plain() -> None:
    """vis-network draws labels on a canvas and knows no markup."""
    defs = _defs()
    messages = {"M_QUEST_Q00_S00_WHAT_IS_GOING_ON_NAME": "[char]Malachi[/char] się budzi"}
    nodes = {n["id"]: n for n in graph_to_dict(defs, messages, {})["nodes"]}

    assert_eq(nodes[Q00]["name"], "Malachi się budzi", "label is stripped")
    assert_eq(
        [r["bold"] for r in nodes[Q00]["name_runs"]], [True, False], "the tooltip keeps the styling"
    )


def test_threads_and_roots_are_marked() -> None:
    data = graph_to_dict(_defs(), {}, {})
    nodes = {n["id"]: n for n in data["nodes"]}

    assert_true(nodes[Q03_S00]["is_thread"], "it has subquests")
    assert_true(not nodes[Q03_S01]["is_thread"], "a leaf is not a thread")
    assert_true(nodes[Q00]["is_root"], "no requires, no parent: available at start")
    assert_true(not nodes[Q01_S00]["is_root"], "it waits on Q00")
    assert_eq(data["meta"]["counts"], {"quests": 8, "threads": 2, "roots": 1}, "counts")


def test_rewards_are_labelled_for_the_tooltip() -> None:
    nodes = {n["id"]: n for n in graph_to_dict(_defs(), {}, {})["nodes"]}

    assert_eq(nodes[Q00]["rewards"], ["+50 zł"], "money")
    # the umbrella pays three ways; all three show (the SSiS `break` bug, again)
    assert_eq(
        nodes[Q03_S00]["rewards"],
        ["+100 zł", "+20 max HP", "MERMAIDS_TEAR"],
        "every reward is listed, not just the first",
    )


def main() -> None:
    tests = [
        test_rank_follows_the_longest_unlock_path,
        test_manual_quests_are_flagged_as_uncloseable,
        test_an_umbrella_inherits_its_steps_problem,
        test_a_healthy_chain_is_not_flagged,
        test_both_gate_kinds_become_edges,
        test_names_resolve_through_messages,
        test_markup_flattens_to_bold_runs,
        test_markup_runs_coalesce,
        test_markup_runs_drop_inline_sprites,
        test_node_labels_are_plain,
        test_threads_and_roots_are_marked,
        test_rewards_are_labelled_for_the_tooltip,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} quest graph script tests passed.")


if __name__ == "__main__":
    main()
