#!/usr/bin/env python3
"""Unit tests for dialog/conditions.py — the mini-DSL condition engine (T-032).

Run from the project root:
    .venv/bin/python tests/test_dialog_conditions.py

Pure logic (no pygame / SDL). Covers: predicate evaluation, boolean / unary /
comparison composition, the real conditions ported from the RPG prototype
(Bob, Potioneer, sentiment, cross-NPC visited), and that malformed or
out-of-whitelist conditions raise ConditionError (never eval to a silent False).
"""

import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))

from dialog import ConditionError, check_condition, validate_condition


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


@dataclass(slots=True)
class StubContext:
    """In-memory ConditionContext for tests (the game supplies a live adapter)."""

    selected_options: set[str] = field(default_factory=set)
    visited_nodes: set[str] = field(default_factory=set)
    inventory: set[str] = field(default_factory=set)
    _sentiment: int = 0
    npc_visited: dict[str, set[str]] = field(default_factory=dict)

    def selected(self, option_key: str) -> bool:
        return option_key in self.selected_options

    def visited(self, node_key: str, npc: str | None = None) -> bool:
        if npc is None:
            return node_key in self.visited_nodes
        return node_key in self.npc_visited.get(npc, set())

    def has_item(self, item_key: str) -> bool:
        return item_key in self.inventory

    @property
    def sentiment(self) -> int:
        return self._sentiment


def _expect_condition_error(fn, msg: str) -> None:  # type: ignore[no-untyped-def]
    try:
        fn()
    except ConditionError:
        return
    raise AssertionError(f"expected ConditionError: {msg}")


# ---------------------------------------------------------------------------
# Constants and trivial conditions
# ---------------------------------------------------------------------------


def test_constants() -> None:
    ctx = StubContext()
    assert_true(check_condition("True", ctx), "literal True")
    assert_true(not check_condition("False", ctx), "literal False")


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------


def test_selected_predicate() -> None:
    ctx = StubContext(selected_options={"BOB_DO_HOBBY_BIKE"})
    assert_true(check_condition('selected("BOB_DO_HOBBY_BIKE")', ctx), "selected true")
    assert_true(not check_condition('selected("BOB_DO_HOBBY_CAR")', ctx), "selected false")
    assert_true(
        check_condition('not selected("BOB_DO_HOBBY_CAR")', ctx), "not selected"
    )


def test_visited_predicate_self() -> None:
    ctx = StubContext(visited_nodes={"003"})
    assert_true(check_condition('visited("003")', ctx), "visited true")
    assert_true(not check_condition('visited("004")', ctx), "visited false")
    assert_true(not check_condition('not visited("003")', ctx), "not visited")


def test_visited_predicate_other_npc() -> None:
    ctx = StubContext(npc_visited={"HAMMER_HOAXHEART_001": {"004"}})
    assert_true(
        check_condition('visited("HAMMER_HOAXHEART_001", "004")', ctx),
        "cross-npc visited true",
    )
    assert_true(
        not check_condition('visited("HAMMER_HOAXHEART_001", "005")', ctx),
        "cross-npc visited false (wrong node)",
    )
    assert_true(
        not check_condition('visited("POTIONEER_PUZZLEMINT_001", "004")', ctx),
        "cross-npc visited false (wrong npc)",
    )


def test_has_item_predicate() -> None:
    ctx = StubContext(inventory={"MERMAIDS_TEAR"})
    assert_true(check_condition('has_item("MERMAIDS_TEAR")', ctx), "has item")
    assert_true(not check_condition('has_item("PHOENIX_FEATHER")', ctx), "missing item")


def test_sentiment_comparisons() -> None:
    ctx = StubContext(_sentiment=42)
    assert_true(check_condition("sentiment >= 42", ctx), "sentiment >= 42")
    assert_true(not check_condition("sentiment < 42", ctx), "sentiment < 42")
    assert_true(check_condition("sentiment == 42", ctx), "sentiment == 42")
    assert_true(check_condition("sentiment != 0", ctx), "sentiment != 0")
    assert_true(check_condition("0 < sentiment <= 42", ctx), "chained compare")
    # negative literal via unary minus
    assert_true(check_condition("sentiment > -1", ctx), "sentiment > -1")


# ---------------------------------------------------------------------------
# Real RPG conditions (Bob, Potioneer), translated to the mini-DSL
# ---------------------------------------------------------------------------


def test_real_conditions_bob() -> None:
    # RPG: character.selected_options_dict.get('BOB_DN_HOBBY','') == 'BOB_DO_HOBBY_BIKE'
    bike = StubContext(selected_options={"BOB_DO_HOBBY_BIKE"})
    car = StubContext(selected_options={"BOB_DO_HOBBY_CAR"})
    assert_true(check_condition('selected("BOB_DO_HOBBY_BIKE")', bike), "bob picked bike")
    assert_true(
        not check_condition('selected("BOB_DO_HOBBY_BIKE")', car), "bob picked car"
    )
    # the negated RPG variant
    assert_true(
        check_condition('not selected("BOB_DO_HOBBY_BIKE")', car), "bob not-bike"
    )


def test_real_conditions_potioneer_quest_items() -> None:
    # RPG: all three ingredients in hero.inventory.items
    all_three = 'has_item("MERMAIDS_TEAR") and has_item("GNOMES_WHISKER") and has_item("PHOENIX_FEATHER")'
    ctx_all = StubContext(inventory={"MERMAIDS_TEAR", "GNOMES_WHISKER", "PHOENIX_FEATHER"})
    ctx_two = StubContext(inventory={"MERMAIDS_TEAR", "GNOMES_WHISKER"})
    assert_true(check_condition(all_three, ctx_all), "has all three ingredients")
    assert_true(not check_condition(all_three, ctx_two), "missing one ingredient")

    # RPG: MERMAIDS_TEAR missing AND (GNOMES_WHISKER OR PHOENIX_FEATHER present)
    partial = (
        'not has_item("MERMAIDS_TEAR") and '
        '(has_item("GNOMES_WHISKER") or has_item("PHOENIX_FEATHER"))'
    )
    ctx_no_tear = StubContext(inventory={"GNOMES_WHISKER"})
    assert_true(check_condition(partial, ctx_no_tear), "no tear but has whisker")
    assert_true(not check_condition(partial, ctx_all), "has tear -> false")


def test_real_conditions_sentiment_gate() -> None:
    # RPG: character.sentiment>=42 gates a friendly option; <42 gates the guarded one
    friendly = StubContext(_sentiment=50)
    cold = StubContext(_sentiment=10)
    assert_true(check_condition("sentiment >= 42", friendly), "friendly gate open")
    assert_true(not check_condition("sentiment >= 42", cold), "friendly gate closed")
    assert_true(check_condition("sentiment < 42", cold), "guarded gate open")


def test_real_conditions_cross_npc_quest_state() -> None:
    # RPG: "004" in config['characters']['HAMMER_HOAXHEART_001'].selected_options_dict
    done = StubContext(npc_visited={"HAMMER_HOAXHEART_001": {"004"}})
    not_done = StubContext(npc_visited={"HAMMER_HOAXHEART_001": {"001"}})
    cond = 'visited("HAMMER_HOAXHEART_001", "004")'
    assert_true(check_condition(cond, done), "hammer reached 004")
    assert_true(not check_condition(cond, not_done), "hammer not at 004")


# ---------------------------------------------------------------------------
# Validation / sandboxing — must raise, never eval to a silent False
# ---------------------------------------------------------------------------


def test_validate_accepts_good_conditions() -> None:
    for cond in [
        "True",
        'selected("X")',
        'visited("A", "B")',
        'has_item("K")',
        "sentiment >= 42 and not selected('Y')",
    ]:
        validate_condition(cond)  # should not raise


def test_rejects_attribute_access() -> None:
    _expect_condition_error(
        lambda: check_condition("character.sentiment >= 42", StubContext()),
        "attribute access must be rejected",
    )


def test_rejects_subscript() -> None:
    _expect_condition_error(
        lambda: check_condition("config['x']", StubContext()),
        "subscript must be rejected",
    )


def test_rejects_unknown_name() -> None:
    _expect_condition_error(
        lambda: check_condition("disposition >= 1", StubContext()),
        "unknown bare name must be rejected",
    )


def test_rejects_unknown_predicate() -> None:
    _expect_condition_error(
        lambda: check_condition('knows("secret")', StubContext()),
        "unknown predicate must be rejected",
    )


def test_rejects_wrong_arity() -> None:
    _expect_condition_error(
        lambda: check_condition('selected("a", "b")', StubContext()),
        "selected takes exactly one arg",
    )
    _expect_condition_error(
        lambda: check_condition("has_item()", StubContext()),
        "has_item needs one arg",
    )
    _expect_condition_error(
        lambda: check_condition('visited("a", "b", "c")', StubContext()),
        "visited takes at most two args",
    )


def test_rejects_non_string_predicate_arg() -> None:
    _expect_condition_error(
        lambda: check_condition("selected(sentiment)", StubContext()),
        "predicate args must be string literals",
    )


def test_rejects_syntax_error() -> None:
    _expect_condition_error(
        lambda: check_condition('selected("x" and', StubContext()),
        "syntax error must raise ConditionError",
    )


def test_rejects_dangerous_calls() -> None:
    # the whole reason for the whitelist: no builtins, no dunder traversal
    for evil in [
        '__import__("os")',
        "().__class__.__bases__",
        "open('/etc/passwd')",
    ]:
        _expect_condition_error(
            lambda evil=evil: check_condition(evil, StubContext()),
            f"dangerous expression {evil!r} must be rejected",
        )


def main() -> None:
    tests = [
        test_constants,
        test_selected_predicate,
        test_visited_predicate_self,
        test_visited_predicate_other_npc,
        test_has_item_predicate,
        test_sentiment_comparisons,
        test_real_conditions_bob,
        test_real_conditions_potioneer_quest_items,
        test_real_conditions_sentiment_gate,
        test_real_conditions_cross_npc_quest_state,
        test_validate_accepts_good_conditions,
        test_rejects_attribute_access,
        test_rejects_subscript,
        test_rejects_unknown_name,
        test_rejects_unknown_predicate,
        test_rejects_wrong_arity,
        test_rejects_non_string_predicate_arg,
        test_rejects_syntax_error,
        test_rejects_dangerous_calls,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} dialog condition tests passed.")


if __name__ == "__main__":
    main()
