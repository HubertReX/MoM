#!/usr/bin/env python3
"""Unit tests for the quest half of the condition mini-DSL (Q-02).

Run from the project root:
    .venv/bin/python tests/test_quest_conditions.py

Pure logic (no pygame / SDL). Covers the three things Q-02 adds:
``quest_done()``, ``item_count()`` / :func:`eval_number`, and the ``quest``
scope — which rejects the conversation-only names (``selected()``,
``sentiment``) and forces ``visited()`` to name its NPC.

The dialog-side behaviour is covered by ``test_dialog_conditions.py``; here we
only check that adding a scope did not disturb it.
"""

import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))

from dialog import (
    ConditionError,
    ConditionScope,
    check_condition,
    eval_number,
    validate_condition,
    validate_number,
)


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


@dataclass(slots=True)
class StubQuestContext:
    """In-memory ConditionContext for a quest (no current NPC, by design)."""

    npc_visited: dict[str, set[str]] = field(default_factory=dict)
    inventory: dict[str, int] = field(default_factory=dict)
    done_quests: set[str] = field(default_factory=set)

    def visited(self, node_key: str, npc: str | None = None) -> bool:
        if npc is None:
            # A quest has no current NPC. Scope validation rejects the 1-arg
            # form before it can get here, so this must never fire.
            raise AssertionError("quest ctx asked for visited() without an npc")
        return node_key in self.npc_visited.get(npc, set())

    def has_item(self, item_key: str) -> bool:
        return self.inventory.get(item_key, 0) > 0

    def item_count(self, item_key: str) -> int:
        return self.inventory.get(item_key, 0)

    def quest_done(self, quest_key: str) -> bool:
        return quest_key in self.done_quests


def _expect_condition_error(fn, msg: str) -> None:  # type: ignore[no-untyped-def]
    try:
        fn()
    except ConditionError:
        return
    raise AssertionError(f"expected ConditionError: {msg}")


QUEST = ConditionScope.quest
DIALOG = ConditionScope.dialog


def test_quest_done_predicate() -> None:
    ctx = StubQuestContext(done_quests={"Q01_S01_LEARN_ABOUT_CURSE"})

    assert_true(
        check_condition('quest_done("Q01_S01_LEARN_ABOUT_CURSE")', ctx, QUEST),
        "done quest is true",
    )
    assert_true(
        not check_condition('quest_done("Q03_S00_LEARN_ABOUT_CURSE")', ctx, QUEST),
        "unfinished quest is false",
    )
    # composes with the boolean operators like any other predicate
    assert_true(
        check_condition(
            'quest_done("Q01_S01_LEARN_ABOUT_CURSE") and not quest_done("Q99")', ctx, QUEST
        ),
        "quest_done composes",
    )
    # ...and is available to dialogs too ("option only after quest X")
    assert_true(
        check_condition('quest_done("Q01_S01_LEARN_ABOUT_CURSE")', ctx, DIALOG),
        "quest_done works in dialog scope",
    )


def test_real_quest_tests_from_the_plan() -> None:
    """The actual `test` expressions of the 8 quests in the 1st iteration."""
    ctx = StubQuestContext(
        npc_visited={
            "CLAPBACK_SWORD": {"015"},
            "BARMAN_ABSINTHRAYNER": {"012"},
            "POTIONEER_PUZZLEMINT": {"017"},
        }
    )

    assert_true(check_condition('visited("CLAPBACK_SWORD", "015")', ctx, QUEST), "Q00_S00")
    assert_true(check_condition('visited("BARMAN_ABSINTHRAYNER", "012")', ctx, QUEST), "Q01_S01")
    # Q03_S01 — the `or` form, second branch true
    assert_true(
        check_condition(
            'visited("POTIONEER_PUZZLEMINT","014") or visited("POTIONEER_PUZZLEMINT","017")',
            ctx,
            QUEST,
        ),
        "Q03_S01 via the second branch",
    )
    # not yet talked to Hammer
    assert_true(
        not check_condition('visited("HAMMER_HOAXHEART", "009")', ctx, QUEST),
        "Q03_S02 not yet",
    )
    # unknown NPC is simply false, never an error
    assert_true(not check_condition('visited("NOBODY", "001")', ctx, QUEST), "unknown npc")


def test_quest_scope_rejects_conversation_only_names() -> None:
    """`selected()` and `sentiment` need a current NPC — a quest has none."""
    _expect_condition_error(
        lambda: validate_condition('selected("BOB_DO_HOBBY_BIKE")', QUEST),
        "selected() in a quest",
    )
    _expect_condition_error(
        lambda: validate_condition("sentiment >= 42", QUEST),
        "sentiment in a quest",
    )
    # both stay legal for dialogs
    validate_condition('selected("BOB_DO_HOBBY_BIKE")', DIALOG)
    validate_condition("sentiment >= 42", DIALOG)


def test_quest_scope_requires_npc_on_visited() -> None:
    """Pułapka 5: `visited("012")` in a quest would sit at False forever."""
    _expect_condition_error(
        lambda: validate_condition('visited("012")', QUEST),
        "1-arg visited() in a quest",
    )
    # the 2-arg form is the only one a quest may use
    validate_condition('visited("BARMAN_ABSINTHRAYNER", "012")', QUEST)
    # dialogs keep both forms
    validate_condition('visited("012")', DIALOG)
    validate_condition('visited("BARMAN_ABSINTHRAYNER", "012")', DIALOG)


def test_eval_number_and_item_count() -> None:
    ctx = StubQuestContext(inventory={"MERMAIDS_TEAR": 2, "GNOMES_WHISKER": 0})

    assert_eq(eval_number('item_count("MERMAIDS_TEAR")', ctx), 2, "item_count")
    assert_eq(eval_number('item_count("GNOMES_WHISKER")', ctx), 0, "zero count")
    assert_eq(eval_number('item_count("NO_SUCH_ITEM")', ctx), 0, "unknown item counts zero")
    # a bare number is a valid (if dull) progress expression
    assert_eq(eval_number("3", ctx), 3, "constant")

    # item_count composes into conditions as a number
    assert_true(check_condition('item_count("MERMAIDS_TEAR") >= 2', ctx, QUEST), "count compare")
    assert_true(not check_condition('item_count("MERMAIDS_TEAR") > 5', ctx, QUEST), "count compare false")
    # has_item still works alongside it
    assert_true(check_condition('has_item("MERMAIDS_TEAR")', ctx, QUEST), "has_item")
    assert_true(not check_condition('has_item("GNOMES_WHISKER")', ctx, QUEST), "has_item zero count")


def test_eval_number_rejects_non_numbers() -> None:
    """A yes/no fact is not a quantity — don't let it read as 1/3 on a progress bar."""
    ctx = StubQuestContext(npc_visited={"BARMAN_ABSINTHRAYNER": {"012"}}, done_quests={"Q01"})

    _expect_condition_error(
        lambda: eval_number('visited("BARMAN_ABSINTHRAYNER", "012")', ctx),
        "bool from visited()",
    )
    _expect_condition_error(
        lambda: eval_number('quest_done("Q01")', ctx),
        "bool from quest_done()",
    )
    _expect_condition_error(
        lambda: eval_number('has_item("MERMAIDS_TEAR")', ctx),
        "bool from has_item()",
    )
    _expect_condition_error(lambda: eval_number('"nope"', ctx), "string is not a number")


def test_validate_number_catches_at_import_what_eval_number_caught_at_runtime() -> None:
    """The whole point: a non-numeric progress fails at import, not on journal open.

    ``eval_number`` already rejected a yes/no result — but only while drawing the
    bar. ``validate_number`` is the static twin the importer calls, so
    ``progress: has_item("X")`` names its line instead of crashing the game later.
    No context: it decides from the expression's shape alone.
    """
    # numeric shapes pass, exactly the ones eval_number would return a number for
    validate_number('item_count("MERMAIDS_TEAR")', QUEST)
    validate_number("3", QUEST)

    # yes/no shapes are rejected up front — these were the runtime crashes
    for bad in (
        'has_item("X")',
        'visited("NPC", "012")',
        'quest_done("Q01")',
        'item_count("X") >= 3',
        'not item_count("X")',
    ):
        _expect_condition_error(lambda expr=bad: validate_number(expr, QUEST), f"boolean progress {bad!r}")

    # and the whitelist still applies before the numeric check
    _expect_condition_error(lambda: validate_number("__import__('os')", QUEST), "dunder still blocked")
    _expect_condition_error(lambda: validate_number('visited("012")', QUEST), "quest arity still enforced")


def test_eval_number_uses_the_same_whitelist() -> None:
    """eval_number is check_condition's twin: same parser, same sandbox."""
    ctx = StubQuestContext()

    _expect_condition_error(lambda: eval_number("__import__('os').system('ls')", ctx), "dunder call")
    _expect_condition_error(lambda: eval_number("ctx.inventory", ctx), "attribute access")
    _expect_condition_error(lambda: eval_number("item_count()", ctx), "wrong arity")
    _expect_condition_error(lambda: eval_number("sentiment", ctx), "dialog-only name in quest scope")
    _expect_condition_error(lambda: eval_number("item_count('X'", ctx), "syntax error")


def test_unknown_names_still_fail_loudly() -> None:
    """The DoD of Q-02: validate_condition keeps rejecting what it always did."""
    for scope in (DIALOG, QUEST):
        _expect_condition_error(lambda s=scope: validate_condition("nonsense_predicate('x')", s), "unknown predicate")
        _expect_condition_error(lambda s=scope: validate_condition("agility > 3", s), "unknown name")
        _expect_condition_error(lambda s=scope: validate_condition("has_item(item)", s), "non-literal arg")
        _expect_condition_error(lambda s=scope: validate_condition("[1, 2]", s), "list literal")
        _expect_condition_error(lambda s=scope: validate_condition("lambda: True", s), "lambda")


def test_whitelist_did_not_grow_beyond_the_plan() -> None:
    """Q-02 DoD: only quest_done + item_count were added."""
    from dialog.conditions import _DIALOG_PREDICATES, _QUEST_PREDICATES, _VALUE_NAMES_BY_SCOPE

    assert_eq(
        set(_DIALOG_PREDICATES),
        {"selected", "visited", "has_item", "item_count", "quest_done"},
        "dialog predicates",
    )
    assert_eq(
        set(_QUEST_PREDICATES),
        {"visited", "has_item", "item_count", "quest_done"},
        "quest predicates (no selected)",
    )
    assert_eq(_VALUE_NAMES_BY_SCOPE[QUEST], frozenset(), "quest has no bare value names")
    assert_eq(_VALUE_NAMES_BY_SCOPE[DIALOG], frozenset({"sentiment"}), "dialog keeps sentiment")


def test_scope_is_part_of_the_cache_key() -> None:
    """Same string, different scope, different verdict — the LRU must not confuse them."""
    validate_condition('visited("012")', DIALOG)  # legal, caches
    _expect_condition_error(
        lambda: validate_condition('visited("012")', QUEST),
        "same string must still fail in quest scope",
    )
    # and the other way round, to catch an ordering-dependent cache bug
    _expect_condition_error(
        lambda: validate_condition("sentiment > 1", QUEST),
        "sentiment fails in quest scope",
    )
    validate_condition("sentiment > 1", DIALOG)


def main() -> None:
    tests = [
        test_quest_done_predicate,
        test_real_quest_tests_from_the_plan,
        test_quest_scope_rejects_conversation_only_names,
        test_quest_scope_requires_npc_on_visited,
        test_eval_number_and_item_count,
        test_eval_number_rejects_non_numbers,
        test_validate_number_catches_at_import_what_eval_number_caught_at_runtime,
        test_eval_number_uses_the_same_whitelist,
        test_unknown_names_still_fail_loudly,
        test_whitelist_did_not_grow_beyond_the_plan,
        test_scope_is_part_of_the_cache_key,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} quest condition tests passed.")


if __name__ == "__main__":
    main()
