#!/usr/bin/env python3
"""Unit tests for quest/engine.py — unlocking, completion, cascade (Q-03).

Run from the project root:
    .venv/bin/python tests/test_quest_engine.py

Pure logic. Runs against the real 8-quest graph from
``doc/quest-migration-plan.md`` (reused from ``test_quest_entities.py`` so the
fixture has one home) and the real stub context from
``test_quest_conditions.py``.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
sys.path.insert(0, os.path.dirname(__file__))

from quest import CompletionMode, QuestState, init_quests
from quest.engine import (
    QuestEngineError,
    check_quests,
    is_complete,
    is_unlocked,
    quest_progress,
    unlocked_keys,
)
from test_quest_conditions import StubQuestContext
from test_quest_entities import SAMPLE, _msgs

Q00 = "Q00_S00_WHAT_IS_GOING_ON"
Q01_S00 = "Q01_S00_BREAK_THE_CURSE"
Q01_S01 = "Q01_S01_LEARN_ABOUT_CURSE"
Q01_S05 = "Q01_S05_MEET_MADAME_SARCASMIA"
Q03_S00 = "Q03_S00_LEARN_ABOUT_CURSE"
Q03_S01 = "Q03_S01_WHO_HAS_MORE_KNOWLEDGE"
Q03_S02 = "Q03_S02_WHERE_TO_FIND_THIS_PERSON"
Q03_S03 = "Q03_S03_HOW_TO_GET_THERE"


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def _defs():  # type: ignore[no-untyped-def]
    return init_quests(SAMPLE)  # type: ignore[arg-type]


def _ctx(*visit_sets: dict[str, set[str]]) -> StubQuestContext:
    """Context built from one or more "who did the player talk to" fragments.

    Merges per NPC, so two fragments can name different nodes of the same
    character (the barman carries two separate quest beats).
    """
    merged: dict[str, set[str]] = {}
    for fragment in visit_sets:
        for npc, nodes in fragment.items():
            merged.setdefault(npc, set()).update(nodes)
    return StubQuestContext(npc_visited=merged)


# The individual conversation beats that satisfy each quest's `test`, per the plan.
CLAPBACK = {"CLAPBACK_SWORD": {"015"}}                    # Q00_S00
BARMAN_CURSE = {"BARMAN_ABSINTHRAYNER": {"012"}}          # Q01_S01
BARMAN_ROUTE = {"BARMAN_ABSINTHRAYNER": {"017"}}          # Q03_S03
POTIONEER = {"POTIONEER_PUZZLEMINT": {"014"}}             # Q03_S01
HAMMER = {"HAMMER_HOAXHEART": {"009"}}                    # Q03_S02
SARCASMIA = {"MADAME_SARCASMIA": {"SARCASMIA_AA_BACK_SO_SOON"}}  # Q01_S05


def test_only_the_opening_quest_is_unlocked_at_start() -> None:
    """A fresh game exposes exactly one thread head, not eight tasks."""
    defs, state = _defs(), QuestState()

    assert_eq(unlocked_keys(defs, state), {Q00}, "only Q00 is open at the start")

    # Q01_S01 has no `requires` of its own — it is gated purely by its parent
    # thread, which is gated by Q00. Without the parent gate it would be live now.
    assert_true(not is_unlocked(defs, state, Q01_S01), "curse step gated by its thread")
    assert_true(not is_unlocked(defs, state, Q03_S01), "Q03 step gated by its thread")


def test_finishing_the_opening_quest_opens_the_curse_thread() -> None:
    defs, state = _defs(), QuestState()
    ctx = _ctx(CLAPBACK)

    result = check_quests(defs, state, ctx)

    assert_eq(result.newly_done, [Q00], "Q00 completed")
    assert_true(state.is_done(Q00), "state updated")
    # the umbrella and its first step are now reachable
    assert_true(is_unlocked(defs, state, Q01_S00), "curse umbrella unlocked")
    assert_true(is_unlocked(defs, state, Q01_S01), "first curse step unlocked")
    assert_true(Q01_S00 in result.newly_unlocked, "umbrella reported as newly unlocked")
    assert_true(Q01_S01 in result.newly_unlocked, "step reported as newly unlocked")
    # ...but Q01_S05 waits on S01, and the Q03 thread waits on S01 too
    assert_true(not is_unlocked(defs, state, Q01_S05), "Sarcasmia still gated")
    assert_true(not is_unlocked(defs, state, Q03_S00), "Q03 thread still gated")


def test_cascade_completes_a_chain_in_one_sweep() -> None:
    """The world does not care in what order the player learned things.

    Player talked to Clapback AND the Barman before any quest was even open.
    One sweep must settle the whole chain, not dribble one step per sweep.
    """
    defs, state = _defs(), QuestState()
    ctx = _ctx(CLAPBACK, BARMAN_CURSE)

    result = check_quests(defs, state, ctx)

    assert_true(state.is_done(Q00), "Q00 done")
    assert_true(state.is_done(Q01_S01), "Q01_S01 done in the same sweep (cascade)")
    assert_eq(result.newly_done, [Q00, Q01_S01], "both reported, in order")
    # Q01_S01 unlocked and completed within the sweep -> reported as done, not as unlocked
    assert_true(Q01_S01 not in result.newly_unlocked, "no 'you may now start' for a finished quest")
    # and its completion opened the next two things
    assert_true(is_unlocked(defs, state, Q03_S00), "Q03 thread opened by the cascade")
    assert_true(is_unlocked(defs, state, Q01_S05), "Sarcasmia opened by the cascade")
    assert_true(Q03_S00 in result.newly_unlocked, "reported as newly unlocked")

    # a second sweep with nothing new is quiet
    again = check_quests(defs, state, ctx)
    assert_true(not again, "idempotent: nothing new on a repeat sweep")


def test_cascade_runs_three_levels_deep() -> None:
    """A player who chatted to everyone before starting gets the whole chain at once.

    Q00 completes -> unlocks the curse thread -> Q01_S01 completes -> unlocks the
    Q03 thread -> Q03_S03 (its `test` is another node of the same barman
    conversation) completes. Three levels, one sweep, no waiting for the 1s
    safety sweep to dribble them out.
    """
    defs, state = _defs(), QuestState()
    ctx = _ctx(CLAPBACK, BARMAN_CURSE, BARMAN_ROUTE)

    result = check_quests(defs, state, ctx)

    assert_eq(result.newly_done, [Q00, Q01_S01, Q03_S03], "three levels in one sweep")
    assert_true(not state.is_done(Q03_S00), "the umbrella still wants its other two steps")
    assert_eq(quest_progress(defs, state, ctx, Q03_S00), (1, 3), "1/3 of the way")


def test_umbrella_completes_only_when_every_child_is_done() -> None:
    defs, state = _defs(), QuestState()
    # open the Q03 thread, and take two of its three steps
    ctx = _ctx(CLAPBACK, BARMAN_CURSE, BARMAN_ROUTE, POTIONEER)
    check_quests(defs, state, ctx)

    assert_true(state.is_done(Q03_S01), "step 1 done (potioneer)")
    assert_true(state.is_done(Q03_S03), "step 3 done (barman 017)")
    assert_true(not state.is_done(Q03_S02), "step 2 not done (never met the smith)")
    assert_true(not state.is_done(Q03_S00), "umbrella waits for the last step")
    assert_eq(quest_progress(defs, state, ctx, Q03_S00), (2, 3), "2/3")

    # the last step closes the thread
    ctx = _ctx(CLAPBACK, BARMAN_CURSE, BARMAN_ROUTE, POTIONEER, HAMMER)
    result = check_quests(defs, state, ctx)
    assert_true(state.is_done(Q03_S02), "step 2 done")
    assert_true(state.is_done(Q03_S00), "umbrella completes with its last child")
    assert_eq(result.newly_done, [Q03_S02, Q03_S00], "step then umbrella, in one sweep")
    assert_eq(quest_progress(defs, state, ctx, Q03_S00), (3, 3), "3/3")


def test_manual_quest_never_completes_on_its_own() -> None:
    """Q01_S00 is the parasol that waits on content still owed (D15)."""
    defs, state = _defs(), QuestState()
    # satisfy everything the world can offer
    ctx = _ctx(CLAPBACK, BARMAN_CURSE, BARMAN_ROUTE, POTIONEER, HAMMER, SARCASMIA)
    check_quests(defs, state, ctx)

    assert_true(state.is_done(Q01_S01), "its children can finish")
    assert_true(state.is_done(Q01_S05), "both children finish")
    assert_true(not state.is_done(Q01_S00), "but the manual umbrella stays open")
    assert_true(not is_complete(defs, state, ctx, Q01_S00), "manual is never complete automatically")

    # the story closes it by hand
    state.mark_done(Q01_S00)
    assert_true(state.is_done(Q01_S00), "manual closes only when told")


def test_locked_quests_are_not_even_evaluated() -> None:
    """A locked quest's test must not run: no surprise completions, no side effects."""
    asked: list[str] = []

    class SpyContext(StubQuestContext):
        def visited(self, node_key: str, npc: str | None = None) -> bool:
            asked.append(f"{npc}:{node_key}")
            return super().visited(node_key, npc)

    defs, state = _defs(), QuestState()
    ctx = SpyContext(npc_visited={"BARMAN_ABSINTHRAYNER": {"012"}})

    check_quests(defs, state, ctx)

    assert_true(not state.is_done(Q01_S01), "gated quest stays open even though its test would pass")
    assert_true(
        not any(q.startswith("BARMAN") for q in asked),
        f"the barman test was evaluated for a locked quest: {asked}",
    )


def test_progress_counts_umbrella_children() -> None:
    defs, state = _defs(), QuestState()
    ctx = _ctx(CLAPBACK, BARMAN_CURSE)
    check_quests(defs, state, ctx)

    assert_eq(quest_progress(defs, state, ctx, Q03_S00), (0, 3), "0/3 with the thread just opened")

    check_quests(defs, state, _ctx(CLAPBACK, BARMAN_CURSE, BARMAN_ROUTE, POTIONEER))
    assert_eq(quest_progress(defs, state, ctx, Q03_S00), (2, 3), "2/3 — the panel figure from Q-08")

    # a plain test quest has no progress bar
    assert_true(quest_progress(defs, state, ctx, Q00) is None, "no progress for a simple step")


def test_progress_from_an_explicit_expression() -> None:
    quests = {
        "Q_COLLECT": {
            **_msgs("Q_COLLECT"),
            "completion": "test",
            "test": 'item_count("MERMAIDS_TEAR") >= 3',
            "progress": 'item_count("MERMAIDS_TEAR")',
            "progress_total": 3,
        }
    }
    defs, state = init_quests(quests), QuestState()  # type: ignore[arg-type]
    ctx = StubQuestContext(inventory={"MERMAIDS_TEAR": 2})

    assert_eq(quest_progress(defs, state, ctx, "Q_COLLECT"), (2, 3), "2/3 from the expression")

    # over-collecting does not overflow the bar
    ctx.inventory["MERMAIDS_TEAR"] = 9
    assert_eq(quest_progress(defs, state, ctx, "Q_COLLECT"), (3, 3), "clamped to the total")

    # and a done quest reads full, whatever the expression says
    check_quests(defs, state, ctx)
    assert_true(state.is_done("Q_COLLECT"), "completed")
    ctx.inventory["MERMAIDS_TEAR"] = 0  # spent them
    assert_eq(quest_progress(defs, state, ctx, "Q_COLLECT"), (3, 3), "a done quest never reads 0/3")


def _expect_value_error(fn, msg: str) -> None:  # type: ignore[no-untyped-def]
    try:
        fn()
    except ValueError:
        return
    raise AssertionError(f"expected ValueError: {msg}")


def test_dependency_cycles_fail_loudly() -> None:
    """A cycle is a deadlock in play and infinite recursion in is_unlocked."""
    two = {
        "Q_A": {**_msgs("Q_A"), "completion": "manual", "requires": ["Q_B"]},
        "Q_B": {**_msgs("Q_B"), "completion": "manual", "requires": ["Q_A"]},
    }
    _expect_value_error(lambda: init_quests(two), "two-quest requires cycle")  # type: ignore[arg-type]

    longer = {
        "Q_A": {**_msgs("Q_A"), "completion": "manual", "requires": ["Q_B"]},
        "Q_B": {**_msgs("Q_B"), "completion": "manual", "requires": ["Q_C"]},
        "Q_C": {**_msgs("Q_C"), "completion": "manual", "requires": ["Q_A"]},
    }
    _expect_value_error(lambda: init_quests(longer), "three-quest cycle")  # type: ignore[arg-type]

    # a cycle mixing a parent edge with a requires edge is just as deadly
    mixed = {
        "Q_UP": {**_msgs("Q_UP"), "completion": "all_subquests", "requires": ["Q_SUB"]},
        "Q_SUB": {**_msgs("Q_SUB"), "completion": "manual", "parent": "Q_UP"},
    }
    _expect_value_error(lambda: init_quests(mixed), "parent/requires cycle")  # type: ignore[arg-type]


def test_umbrella_and_children_are_not_a_cycle() -> None:
    """The normal thread shape must survive the cycle check.

    An umbrella waits on its children (completion) while its children wait on the
    umbrella being *unlocked* — different directions, not a loop. Flagging this
    would reject every well-formed thread in the game.
    """
    defs = _defs()
    assert_eq(len(defs), 8, "the real 8-quest graph builds fine")
    assert_eq(defs[Q03_S00].completion, CompletionMode.all_subquests, "umbrella intact")


def test_engine_rejects_hand_built_nonsense() -> None:
    """is_complete raises rather than guessing when defs bypassed init_quests."""
    from quest.entities import QuestDef

    orphan = QuestDef("Q_X", "n", "d", "s", CompletionMode.all_subquests)
    defs = {"Q_X": orphan}
    state, ctx = QuestState(), StubQuestContext()

    try:
        is_complete(defs, state, ctx, "Q_X")
    except QuestEngineError:
        return
    raise AssertionError("expected QuestEngineError for an umbrella with no children")


def main() -> None:
    tests = [
        test_only_the_opening_quest_is_unlocked_at_start,
        test_finishing_the_opening_quest_opens_the_curse_thread,
        test_cascade_completes_a_chain_in_one_sweep,
        test_cascade_runs_three_levels_deep,
        test_umbrella_completes_only_when_every_child_is_done,
        test_manual_quest_never_completes_on_its_own,
        test_locked_quests_are_not_even_evaluated,
        test_progress_counts_umbrella_children,
        test_progress_from_an_explicit_expression,
        test_dependency_cycles_fail_loudly,
        test_umbrella_and_children_are_not_a_cycle,
        test_engine_rejects_hand_built_nonsense,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} quest engine tests passed.")


if __name__ == "__main__":
    main()
