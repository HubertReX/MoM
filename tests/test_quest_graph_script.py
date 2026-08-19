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

# Before the imports, not after: `quest_graph` lives in `scripts/` and `quest` in
# `project/`, so a path set up below them only works when something else already
# put those directories on `sys.path`. Running this file through
# `scripts/run_unit_tests.py` (which is what `just test-unit` does) does not, so
# the whole file died on ModuleNotFoundError and every test in it was silently
# skipped by the suite - it only ever passed when run by hand with PYTHONPATH.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.dirname(__file__))

from test_quest_entities import SAMPLE  # noqa: E402
from quest_graph import (  # noqa: E402
    DialogSource,
    QuestDoneRef,
    VisitedRef,
    alternatives,
    columns,
    graph_to_dict,
    markup_runs,
    quest_done_refs,
    rows,
    uncloseable,
    visited_refs,
)
from quest.graph import init_quests  # noqa: E402


Q00 = "Q00_S00_WHAT_IS_GOING_ON"
Q01_S00 = "Q01_S00_BREAK_THE_CURSE"
Q01_S01 = "Q01_S01_LEARN_ABOUT_CURSE"
Q01_S02 = "Q01_S03_MEET_MADAME_SARCASMIA"
Q03_S00 = "Q03_S00_LEARN_ABOUT_CURSE"
Q03_S01 = "Q03_S01_WHO_HAS_MORE_KNOWLEDGE"


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def _defs():  # type: ignore[no-untyped-def]
    return init_quests(SAMPLE)  # type: ignore[arg-type]


def test_a_thread_keeps_its_steps_in_one_column() -> None:
    """The complaint this layout exists to fix: a thread you cannot follow.

    Ranking by unlock depth put ``Q01_S02`` one column past ``Q01_S01`` (it waits
    on its sibling), so a thread read as a staircase and its steps could not be
    traced. Order between siblings is carried by the ``requires`` arrow between
    them; the column only says which thread they belong to.
    """
    col = columns(_defs())

    assert_eq(col[Q01_S01], col[Q01_S02], "siblings share a column")
    assert_eq(col[Q03_S01], col["Q03_S02_WHERE_TO_FIND_THIS_PERSON"], "and so do these")
    assert_eq(
        col["Q03_S02_WHERE_TO_FIND_THIS_PERSON"],
        col["Q03_S03_HOW_TO_GET_THERE"],
        "the whole thread, however long the chain inside it",
    )


def test_the_column_template_runs_left_to_right() -> None:
    """thread -> steps, and a chain that waits on another starts past its extent."""
    col = columns(_defs())

    assert_eq(col[Q00], 0, "nothing gates the opening quest")
    assert_true(col[Q01_S00] > col[Q00], "a requires reads left to right")
    assert_eq(col[Q01_S01], col[Q01_S00] + 1, "steps sit in the very next column")
    # Q00 closes on a conversation, so Q01_S00 starts past *that*, not past Q00
    assert_eq(col[Q01_S00], col[Q00] + 2, "past the dependency's own conversation")
    # Q03_S00 waits on Q01_S01, which itself has closing conversations
    assert_true(col[Q03_S00] > col[Q01_S01] + 1, "a cross-chain wait clears the whole extent")
    assert_eq(col[Q03_S01], col[Q03_S00] + 1, "and its steps follow it")


def test_an_umbrella_with_no_test_does_not_reserve_a_column() -> None:
    """The slots are a template, not a reservation - an empty one costs nothing."""
    col = columns(_defs())

    # Q01_S00 closes on its subquests (all_subquests), so it names no conversation
    # and its steps take the next column rather than skipping one
    assert_eq(col[Q01_S01] - col[Q01_S00], 1, "no gap where the thread has no Test")


def test_a_trigger_conversation_gets_room_on_the_left() -> None:
    """A thread nothing else gates still cannot start at column 0 if a
    conversation has to come before it."""
    col = columns(init_quests(_gated()))  # type: ignore[arg-type]

    assert_eq(col["Q09_S00_TOLD_BY_THE_BARMAN"], 1, "column 0 is left for the hexagon")


def test_empty_columns_are_squeezed_out() -> None:
    """A column nothing lands on is a band of blank screen; order is all it meant."""
    data = graph_to_dict(_defs(), {}, {})
    used = sorted({n["level"] for n in data["nodes"]})

    assert_eq(used, list(range(len(used))), f"no gaps in the columns: {used}")
    assert_eq(used[0], 0, "and the first column is 0")


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

    for key in (Q00, Q01_S01, Q01_S02, Q03_S00, Q03_S01):
        assert_true(key not in broken, f"{key} closes on its own")


def test_both_gate_kinds_become_edges() -> None:
    """requires and parent are different gates and must stay distinguishable."""
    data = graph_to_dict(_defs(), {}, {})
    edges = {(e["from"], e["to"]): e["kind"] for e in data["edges"]}

    assert_eq(edges[(Q00, Q01_S00)], "requires", "done-gate")
    assert_eq(edges[(Q01_S00, Q01_S01)], "parent", "unlocked-gate, drawn thread -> step")
    assert_eq(edges[(Q01_S01, Q03_S00)], "requires", "the cross-chain edge is not lost")
    # Q01_S02 is gated both ways: both edges exist, neither swallows the other
    assert_eq(edges[(Q01_S00, Q01_S02)], "parent", "its thread")
    assert_eq(edges[(Q01_S01, Q01_S02)], "requires", "and its prerequisite")


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
    assert_eq(markup_runs("zwykła proza bez tagów"), [{"text": "zwykła proza bez tagów", "bold": False}], "one run")
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
    assert_eq([r["bold"] for r in nodes[Q00]["name_runs"]], [True, False], "the tooltip keeps the styling")


def test_threads_and_roots_are_marked() -> None:
    data = graph_to_dict(_defs(), {}, {})
    nodes = {n["id"]: n for n in data["nodes"]}

    assert_true(nodes[Q03_S00]["is_thread"], "it has subquests")
    assert_true(not nodes[Q03_S01]["is_thread"], "a leaf is not a thread")
    assert_true(nodes[Q00]["is_root"], "no requires, no parent: available at start")
    assert_true(not nodes[Q01_S00]["is_root"], "it waits on Q00")
    # 7 dialog nodes: every `visited()` the eight sample quests name in their
    # `test`, deduplicated - the conversations that close them. No `quest_done()`
    # anywhere in the sample, so no quest-on-quest gate either.
    assert_eq(
        data["meta"]["counts"],
        {"quests": 8, "threads": 2, "roots": 1, "dialogs": 7, "quest_gates": 0},
        "counts",
    )


# --- the dialog node that triggers a thread --------------------------------

_SWORD = DialogSource(
    "CLAPBACK_SWORD",
    name="Miecz Ciętej-riposty",
    anchors={"015": "015-end"},
    texts={"015": "M_SWORD_DN_015"},
)

_BARMAN = DialogSource(
    "BARMAN_ABSINTHRAYNER",
    name="Barman Absyntnent",
    anchors={"023": "023", "015": "015-end"},
    texts={"023": "M_BARMAN_DN_023"},
)


def _gated(**extra: object) -> dict[str, object]:
    """SAMPLE plus one quest opened by a conversation instead of by another quest."""
    sample = dict(SAMPLE)
    sample["Q09_S00_TOLD_BY_THE_BARMAN"] = {
        "name": "M_Q09_NAME", "description": "M_Q09_DESC", "success": "M_Q09_OK",
        "completion": "manual",
        "requires_test": 'visited("BARMAN_ABSINTHRAYNER", "023")',
        **extra,
    }
    return sample


def test_visited_refs_reads_the_condition() -> None:
    assert_eq(
        visited_refs('visited("BARMAN_ABSINTHRAYNER", "023")'),
        [VisitedRef("BARMAN_ABSINTHRAYNER", "023", False)],
        "one reference",
    )
    assert_eq(visited_refs(None), [], "no condition, no references")
    assert_eq(visited_refs('has_item("MERMAIDS_TEAR")'), [], "not every condition names a node")
    # the same node twice in one expression is still one node in the picture
    assert_eq(visited_refs('visited("N", "1") or visited("N", "1")'), [VisitedRef("N", "1")],
              "deduplicated")
    # a hand-edited config must degrade to "no references", not take the graph down
    assert_eq(visited_refs("visited("), [], "unparseable is empty, not fatal")


def test_negation_survives_into_the_picture() -> None:
    """`not visited(X)` is the opposite claim; an unmarked arrow would state the
    reverse of what the quest actually does."""
    assert_eq(
        visited_refs('not visited("A", "1")'), [VisitedRef("A", "1", True)], "negated"
    )
    assert_eq(
        visited_refs('visited("A", "1") and not visited("B", "2")'),
        [VisitedRef("A", "1", False), VisitedRef("B", "2", True)],
        "polarity is per reference, not per expression",
    )
    # De Morgan: the `not` distributes over the group
    assert_eq(
        visited_refs('not (visited("A", "1") or visited("B", "2"))'),
        [VisitedRef("A", "1", True), VisitedRef("B", "2", True)],
        "a negated group negates every reference in it",
    )


def test_alternatives_says_when_one_conversation_is_enough() -> None:
    assert_true(alternatives('visited("A", "1") or visited("B", "2")'), "either one closes it")
    assert_true(not alternatives('visited("A", "1") and visited("B", "2")'), "both needed")
    assert_true(not alternatives('visited("A", "1")'), "a single node has no alternative")
    # `not (A or B)` is "neither", which is an AND of the negated edges - calling
    # it "either one" would label them with the opposite of what they mean
    assert_true(
        not alternatives('not (visited("A", "1") or visited("B", "2"))'),
        "De Morgan flips the joiner",
    )
    assert_true(
        alternatives('not (visited("A", "1") and visited("B", "2"))'), "and flips it back"
    )


def test_a_dialog_node_becomes_its_own_node_and_edge() -> None:
    """The conversation that opens a thread is the one thing the quest file
    cannot tell you, so it gets drawn - and drawn as something else."""
    data = graph_to_dict(
        init_quests(_gated()),  # type: ignore[arg-type]
        {"M_Q09_NAME": "Sprawy najwyższej wagi", "M_BARMAN_DN_023": "Za mojej kadencji ANI jednej!"},
        {},
        {"BARMAN_ABSINTHRAYNER": _BARMAN},
    )
    nodes = {n["id"]: n for n in data["nodes"]}
    node = nodes["dlg:BARMAN_ABSINTHRAYNER#023"]

    assert_eq(node["kind"], "dialog", "not a quest, and says so")
    assert_eq(node["name"], "Barman Absyntnent #023", "labelled by who says it and where")
    assert_eq(node["link"], "Barman Absyntnent#023", "clickable through to the character note")
    assert_eq(node["unlocks"], ["Sprawy najwyższej wagi"], "and names what it opens")
    assert_true(node["text_runs"], "the line itself is in the tooltip")
    assert_true(not node["is_root"] and not node["is_thread"], "it is neither")

    edges = {(e["from"], e["to"]): e["kind"] for e in data["edges"]}
    assert_eq(
        edges[("dlg:BARMAN_ABSINTHRAYNER#023", "Q09_S00_TOLD_BY_THE_BARMAN")],
        "unlocks",
        "a third kind of gate, distinguishable from requires and parent",
    )
    # 7 from the sample's own `test` conditions + this one from `requires_test`
    assert_eq(data["meta"]["counts"]["dialogs"], 8, "counted separately from quests")
    assert_eq(data["meta"]["counts"]["quests"], 9, "and not counted as one")


def test_a_test_condition_draws_the_conversation_that_closes_the_quest() -> None:
    """The other half of the picture, and the arrow points the other way: the
    quest is already open and sends the player to that conversation."""
    sample = dict(SAMPLE)
    data = graph_to_dict(
        init_quests(sample), {}, {}, {"CLAPBACK_SWORD": _SWORD}  # type: ignore[arg-type]
    )
    nodes = {n["id"]: n for n in data["nodes"]}
    edges = {(e["from"], e["to"]): e for e in data["edges"]}

    node = nodes["dlg:CLAPBACK_SWORD#015"]
    assert_eq(node["closes"], ["M_QUEST_Q00_S00_WHAT_IS_GOING_ON_NAME"], "names what it closes")
    assert_eq(node["unlocks"], [], "and does not claim to open it")

    edge = edges[(Q00, "dlg:CLAPBACK_SWORD#015")]
    assert_eq(edge["kind"], "closes", "quest -> conversation, not the reverse")
    assert_true(not edge["negated"], "a plain condition")
    assert_eq(node["level"], nodes[Q00]["level"] + 1, "drawn below the quest it closes")


def test_a_negated_test_marks_its_edge() -> None:
    sample = dict(SAMPLE)
    sample[Q00] = {**sample[Q00], "test": 'not visited("CLAPBACK_SWORD", "015")'}  # type: ignore[index]
    data = graph_to_dict(init_quests(sample), {}, {})  # type: ignore[arg-type]

    edge = {(e["from"], e["to"]): e for e in data["edges"]}[(Q00, "dlg:CLAPBACK_SWORD#015")]
    assert_true(edge["negated"], "the picture must not state the opposite of the quest")


def test_alternative_conversations_are_labelled_on_the_edge() -> None:
    """Two nodes joined by `or` and two joined by `and` draw identically otherwise."""
    sample = dict(SAMPLE)
    sample[Q00] = {  # type: ignore[index]
        **sample[Q00],  # type: ignore[dict-item]
        "test": 'visited("CLAPBACK_SWORD", "015") or visited("CLAPBACK_SWORD", "016")',
    }
    data = graph_to_dict(init_quests(sample), {}, {})  # type: ignore[arg-type]
    closes = [e for e in data["edges"] if e["kind"] == "closes" and e["from"] == Q00]

    assert_eq(len(closes), 2, "both conversations drawn")
    assert_true(all(e["alt"] for e in closes), "and both marked as alternatives")


def test_one_conversation_can_close_one_quest_and_open_another() -> None:
    """Same node, two relations, one hexagon - and it lands between the two."""
    sample = _gated()
    sample["Q09_S00_TOLD_BY_THE_BARMAN"]["requires_test"] = (  # type: ignore[index]
        'visited("CLAPBACK_SWORD", "015")'
    )
    data = graph_to_dict(
        init_quests(sample), {}, {}, {"CLAPBACK_SWORD": _SWORD}  # type: ignore[arg-type]
    )
    nodes = {n["id"]: n for n in data["nodes"]}
    node = nodes["dlg:CLAPBACK_SWORD#015"]

    assert_eq(node["closes"], ["M_QUEST_Q00_S00_WHAT_IS_GOING_ON_NAME"], "closes Q00")
    assert_eq(node["unlocks"], ["M_Q09_NAME"], "and opens Q09")
    kinds = sorted(
        e["kind"] for e in data["edges"] if node["id"] in (e["from"], e["to"])
    )
    assert_eq(kinds, ["closes", "unlocks"], "one node, both edges")


def test_the_dialog_node_sits_left_of_what_it_opens() -> None:
    """The conversation happens first, so it is drawn first - rightward is later."""
    data = graph_to_dict(
        init_quests(_gated()), {}, {}, {"BARMAN_ABSINTHRAYNER": _BARMAN}  # type: ignore[arg-type]
    )
    nodes = {n["id"]: n for n in data["nodes"]}

    assert_eq(nodes["dlg:BARMAN_ABSINTHRAYNER#023"]["level"], 0, "leftmost column")
    assert_eq(
        nodes["Q09_S00_TOLD_BY_THE_BARMAN"]["level"], 1, "the quest one column right"
    )
    # Q00 owes nothing to that conversation, so it keeps column 0 and the two
    # chains sit side by side rather than one pushing the other along
    assert_eq(nodes[Q00]["level"], 0, "an independent chain starts at the left edge")
    assert_true(all(n["level"] >= 0 for n in data["nodes"]), "no negative columns")


def test_one_conversation_opening_two_threads_is_one_node() -> None:
    """Drawing it twice would claim there are two of it."""
    sample = _gated()
    sample["Q08_S00_ALSO_TOLD"] = {
        "name": "M_Q08_NAME", "description": "M_Q08_DESC", "success": "M_Q08_OK",
        "completion": "manual",
        "requires_test": 'visited("BARMAN_ABSINTHRAYNER", "023")',
    }
    data = graph_to_dict(
        init_quests(sample), {}, {}, {"BARMAN_ABSINTHRAYNER": _BARMAN}  # type: ignore[arg-type]
    )

    unlocking = [n for n in data["nodes"] if n.get("unlocks")]
    assert_eq(len(unlocking), 1, "one node does the opening")
    assert_eq(
        len([e for e in data["edges"] if e["kind"] == "unlocks"]), 2, "two edges out of it"
    )


def test_the_graph_still_draws_without_the_vault() -> None:
    """config.json is the source of truth for the shape; the vault only adds links."""
    data = graph_to_dict(init_quests(_gated()), {}, {})  # type: ignore[arg-type]
    node = {n["id"]: n for n in data["nodes"]}["dlg:BARMAN_ABSINTHRAYNER#023"]

    assert_eq(node["name"], "BARMAN_ABSINTHRAYNER #023", "falls back to the config key")
    assert_eq(node["link"], None, "nothing to open, and it does not pretend otherwise")


def test_a_dialog_gated_quest_is_not_a_root() -> None:
    """It is not available at the start: somebody has to mention it first."""
    nodes = {
        n["id"]: n
        for n in graph_to_dict(init_quests(_gated()), {}, {})["nodes"]  # type: ignore[arg-type]
    }
    assert_true(not nodes["Q09_S00_TOLD_BY_THE_BARMAN"]["is_root"], "gated on a conversation")


def test_rewards_are_labelled_for_the_tooltip() -> None:
    nodes = {n["id"]: n for n in graph_to_dict(_defs(), {}, {})["nodes"]}

    assert_eq(nodes[Q00]["rewards"], ["+50 złota"], "money")
    # the umbrella pays three ways; all three show (the SSiS `break` bug, again)
    assert_eq(
        nodes[Q03_S00]["rewards"],
        ["+100 złota", "+20 max HP", "MERMAIDS_TEAR"],
        "every reward is listed, not just the first",
    )


# --- the quest that waits on another quest ---------------------------------
#
# `Test: quest_done(...)` is the one gate the picture used to drop entirely: a
# step waiting on three chapters of another chain looked like it closed on
# nothing. Mirrors the real Q01_S02 -> Q03_S00 shape.


def _quest_gated(key: str = Q03_S00) -> dict[str, object]:
    """SAMPLE with ``Q01_S01`` closing on another quest instead of a conversation."""
    sample = dict(SAMPLE)
    sample[Q01_S01] = {
        **SAMPLE[Q01_S01],  # type: ignore[dict-item]
        "test": f'quest_done("{key}")',
    }
    return sample


def test_quest_done_refs_reads_the_condition() -> None:
    assert_eq(
        quest_done_refs('quest_done("Q03_S00_LEARN_ABOUT_CURSE")'),
        [QuestDoneRef("Q03_S00_LEARN_ABOUT_CURSE", False)],
        "one reference",
    )
    assert_eq(quest_done_refs(None), [], "no condition, no references")
    assert_eq(quest_done_refs('visited("N", "1")'), [], "a conversation is not a quest gate")
    assert_eq(
        quest_done_refs('not quest_done("A")'), [QuestDoneRef("A", True)],
        "the `not` is half the meaning here too",
    )
    assert_eq(
        quest_done_refs('quest_done("A") or quest_done("A")'), [QuestDoneRef("A")],
        "named twice, drawn once",
    )
    assert_eq(quest_done_refs("quest_done("), [], "unparseable is empty, not fatal")


def test_alternatives_counts_both_gate_kinds() -> None:
    """The bug this pins: `visited(X) or quest_done(Y)` losing its `lub` label.

    Counting only the conversations left that condition at one reference - below
    the two-gate threshold - so the two edges drew as if BOTH were required, which
    is the opposite of what the quest does.
    """
    assert_true(
        alternatives('visited("A", "1") or quest_done("Q")'), "either one closes it"
    )
    assert_true(
        not alternatives('visited("A", "1") and quest_done("Q")'), "both needed"
    )
    assert_true(alternatives('quest_done("Q") or quest_done("R")'), "two quests, either one")
    assert_true(not alternatives('quest_done("Q")'), "a single gate has no alternative")


def test_a_quest_done_test_draws_an_edge_to_that_quest() -> None:
    """Drawn the same way round as a closing conversation: out of the quest that
    closes, into what closes it. The other direction would put a green arrow
    parallel to the grey `requires` ones, meaning the reverse."""
    data = graph_to_dict(init_quests(_quest_gated()), {}, {})  # type: ignore[arg-type]
    gates = [e for e in data["edges"] if e["kind"] == "closes_quest"]

    assert_eq(len(gates), 1, f"one quest-on-quest gate: {gates}")
    assert_eq(gates[0]["from"], Q01_S01, "out of the quest that closes")
    assert_eq(gates[0]["to"], Q03_S00, "into the quest that closes it")
    assert_true(not gates[0]["negated"], "a plain condition")
    assert_eq(data["meta"]["counts"]["quest_gates"], 1, "and it is counted for the legend")


def test_a_dangling_quest_done_is_skipped() -> None:
    """`validate_references()` rejects these at import; the picture must not die
    on a hand-edited config either."""
    data = graph_to_dict(init_quests(_quest_gated("Q99_NO_SUCH_QUEST")), {}, {})  # type: ignore[arg-type]

    assert_eq([e for e in data["edges"] if e["kind"] == "closes_quest"], [], "no edge")
    assert_true(len(data["nodes"]) >= 8, "and the rest of the graph still draws")


def test_a_dependency_always_reserves_its_conversation_column() -> None:
    """The rhythm: a quest unlocked by a quest is always TWO columns to its right.

    Reserved conditionally, it broke exactly where it hurt: a quest whose `Test`
    is `quest_done()` names no conversation, so its dependant fell into the
    *conversation* column - and that chain's steps then shared a column with
    another thread's steps.
    """
    col = columns(init_quests(_quest_gated()))  # type: ignore[arg-type]

    assert_eq(col[Q03_S00], col[Q01_S01] + 2, "two columns, conversation or not")


# --- rows: the three rules the drawing must never break --------------------


def _rowed() -> tuple[dict[str, dict[str, object]], dict[str, float]]:
    data = graph_to_dict(_defs(), {}, {})
    return {n["id"]: n for n in data["nodes"]}, rows(data["nodes"], data["edges"])


def test_the_first_child_opening_right_shares_its_parents_row() -> None:
    """Rule 1. Otherwise the two sit rows apart and the edge between them is a
    long diagonal across everything else.

    Stated as the invariant rather than as a pair of keys: *which* child comes
    first is the layout's business (nearest column, then smallest subtree), and
    pinning one name here would pin that ordering by accident.
    """
    nodes, row = _rowed()
    edges = graph_to_dict(_defs(), {}, {})["edges"]

    opened: dict[str, list[float]] = {}
    for edge in edges:
        if edge["kind"] not in ("requires", "parent"):
            continue
        if nodes[edge["to"]]["level"] <= nodes[edge["from"]]["level"]:
            continue  # a step of the same thread - it goes below, not beside
        opened.setdefault(edge["from"], []).append(row[edge["to"]])

    assert_true(bool(opened), "the sample does open something to the right")
    for key, child_rows in opened.items():
        assert_eq(row[key], min(child_rows), f"{key} sits level with its topmost child")


def test_a_dialog_node_never_sits_level_with_its_parent() -> None:
    """Rule 2. Its arc returns from below; drawn level it lands exactly on the
    horizontal line running from that parent to its own child."""
    nodes, row = _rowed()
    edges = graph_to_dict(_defs(), {}, {})["edges"]

    for edge in edges:
        if edge["kind"] != "closes":
            continue
        quest, dialog = edge["from"], edge["to"]
        assert_true(
            row[dialog] > row[quest],
            f"{dialog} must sit below {quest}: {row[dialog]} vs {row[quest]}",
        )


def test_two_nodes_never_share_a_row_in_one_column() -> None:
    """The packing invariant. Rows are per-column cursors, not per-subtree bands -
    that is what lets two nodes in *different* columns sit level, and it is the
    only reason the picture stays short.

    Checked on `_gated()` too, and not for symmetry: the live config has no
    `Requires: visited(...)` at all, so an *opening* conversation is a branch no
    real data exercises. There the hexagon owns the quest instead of hanging off
    it - the one case where a dialog node is a parent - and a collision would be
    a real bug found by nobody.
    """
    for label, defs in (("SAMPLE", _defs()), ("gated", init_quests(_gated()))):  # type: ignore[arg-type]
        data = graph_to_dict(defs, {}, {})
        row = rows(data["nodes"], data["edges"])
        seen: dict[tuple[int, float], str] = {}
        for node in data["nodes"]:
            slot = (node["level"], row[node["id"]])
            assert_true(
                slot not in seen,
                f"[{label}] {node['id']} collides with {seen.get(slot)} at {slot}",
            )
            seen[slot] = node["id"]


def test_rows_do_not_depend_on_the_order_of_the_input() -> None:
    """The forest is built from one incoming edge per node, tie-broken by rank,
    column and key - so the picture is a function of the config, not of whatever
    order `dict` happened to hand over. Reversing both lists is what makes this
    test able to fail; running it twice in one process never could.
    """
    data = graph_to_dict(_defs(), {}, {})
    forward = rows(data["nodes"], data["edges"])
    backward = rows(list(reversed(data["nodes"])), list(reversed(data["edges"])))

    assert_eq(backward, forward, "same config, same rows, whatever the order")


def main() -> None:
    tests = [
        test_a_thread_keeps_its_steps_in_one_column,
        test_the_column_template_runs_left_to_right,
        test_an_umbrella_with_no_test_does_not_reserve_a_column,
        test_a_trigger_conversation_gets_room_on_the_left,
        test_empty_columns_are_squeezed_out,
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
        test_visited_refs_reads_the_condition,
        test_negation_survives_into_the_picture,
        test_alternatives_says_when_one_conversation_is_enough,
        test_a_test_condition_draws_the_conversation_that_closes_the_quest,
        test_a_negated_test_marks_its_edge,
        test_alternative_conversations_are_labelled_on_the_edge,
        test_one_conversation_can_close_one_quest_and_open_another,
        test_a_dialog_node_becomes_its_own_node_and_edge,
        test_the_dialog_node_sits_left_of_what_it_opens,
        test_one_conversation_opening_two_threads_is_one_node,
        test_the_graph_still_draws_without_the_vault,
        test_a_dialog_gated_quest_is_not_a_root,
        test_rewards_are_labelled_for_the_tooltip,
        test_quest_done_refs_reads_the_condition,
        test_alternatives_counts_both_gate_kinds,
        test_a_quest_done_test_draws_an_edge_to_that_quest,
        test_a_dangling_quest_done_is_skipped,
        test_a_dependency_always_reserves_its_conversation_column,
        test_the_first_child_opening_right_shares_its_parents_row,
        test_a_dialog_node_never_sits_level_with_its_parent,
        test_two_nodes_never_share_a_row_in_one_column,
        test_rows_do_not_depend_on_the_order_of_the_input,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} quest graph script tests passed.")


if __name__ == "__main__":
    main()
