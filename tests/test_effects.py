#!/usr/bin/env python3
"""Testy gramatyki efektów (`dialog/effects.py`).

Uruchamianie z katalogu projektu:
    .venv/bin/python tests/test_effects.py

Efekt to jedno zdanie pisane w vaulcie i czytane przez dwa silniki (węzeł
dialogu, nagroda questa), więc pilnujemy tu trzech rzeczy: że krotność rozwija
się na listę kluczy, że zasięg odcina czasowniki, których dany silnik nie ma,
i że każdy odrzut mówi autorowi, co napisać zamiast.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))

from dialog.effects import (
    EFFECTS_BY_SCOPE,
    EffectError,
    EffectScope,
    parse_effect,
)


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def _expect_error(expression: str, scope: EffectScope, needle: str, label: str) -> None:
    try:
        parse_effect(expression, scope)
    except EffectError as error:
        assert_true(
            needle in str(error), f"{label}: message {str(error)!r} lacks {needle!r}"
        )
        return
    raise AssertionError(f"{label}: {expression!r} was accepted")


def test_one_of_each() -> None:
    """``remove_n_items(1, A, B, C)`` - po jednej sztuce z listy."""
    effect = parse_effect(
        'remove_n_items(1,"GNOMES_WHISKER","MERMAIDS_TEAR","PHOENIX_FEATHER")',
        EffectScope.dialog,
    )
    assert_eq(effect.name, "remove_n_items", "verb")
    assert_eq(
        effect.items,
        ["GNOMES_WHISKER", "MERMAIDS_TEAR", "PHOENIX_FEATHER"],
        "one of each",
    )


def test_count_repeats_the_key() -> None:
    """Krotność rozwija się na listę, bo sink i config operują listą kluczy."""
    effect = parse_effect('remove_n_items(5,"fish")', EffectScope.dialog)
    assert_eq(effect.items, ["fish"] * 5, "five fish")
    assert_eq(effect.value, 5, "count kept for the caller that wants it")


def test_count_applies_to_every_item() -> None:
    effect = parse_effect('add_n_items(2,"fish","honey")', EffectScope.dialog)
    assert_eq(effect.items, ["fish", "fish", "honey", "honey"], "two of each")


def test_amounts() -> None:
    assert_eq(parse_effect("add_money(50)", EffectScope.dialog).value, 50, "money")
    assert_eq(
        parse_effect("shift_sentiment(-10)", EffectScope.dialog).value, -10, "sentiment"
    )
    assert_eq(
        parse_effect("restore_health(20)", EffectScope.quest).value, 20, "health"
    )


def test_targeted_sentiment_carries_the_npc() -> None:
    effect = parse_effect(
        'shift_sentiment_of("BARMAN_ABSINTHRAYNER",10)', EffectScope.quest
    )
    assert_eq(effect.target, "BARMAN_ABSINTHRAYNER", "target NPC")
    assert_eq(effect.value, 10, "amount")


def test_a_quest_reward_gives_and_does_not_take() -> None:
    """Nagroda nie ma czym zabrać - `QuestRewardCategory` nie zna takiej kategorii."""
    for expression in ("remove_money(50)", "lose_health(10)", 'remove_n_items(1,"fish")'):
        _expect_error(
            expression, EffectScope.quest, "cannot be used in a quest", "taking reward"
        )


def test_a_dialog_cannot_raise_stats() -> None:
    """Statystyki na stałe podnosi tylko quest - węzeł dialogu nie ma takiej kategorii."""
    for expression in ("raise_max_health(20)", "raise_damage(5)", "raise_max_items(1)"):
        _expect_error(
            expression, EffectScope.dialog, "cannot be used in a dialog", "raising in a dialog"
        )


def test_a_dialog_shifts_the_sentiment_of_whoever_is_talking() -> None:
    """W rozmowie adresat wynika z kontekstu, w queście trzeba go nazwać."""
    _expect_error(
        'shift_sentiment_of("BARMAN_ABSINTHRAYNER",10)',
        EffectScope.dialog,
        "cannot be used in a dialog",
        "targeted shift in a dialog",
    )
    _expect_error(
        "shift_sentiment(10)", EffectScope.quest, "cannot be used in a quest", "bare shift in a quest"
    )


def test_zero_and_negative_are_refused() -> None:
    _expect_error("add_money(0)", EffectScope.dialog, "positive number", "zero money")
    _expect_error(
        "add_money(-50)", EffectScope.dialog, "positive number", "negative money"
    )
    _expect_error(
        "shift_sentiment(0)", EffectScope.dialog, "changes nothing", "zero sentiment"
    )
    _expect_error(
        'add_n_items(0,"fish")', EffectScope.dialog, "positive count", "zero count"
    )


def test_a_malformed_effect_says_what_to_write() -> None:
    _expect_error("50 money", EffectScope.quest, "not a call", "not an expression")
    _expect_error("add_money", EffectScope.dialog, "must be a call", "bare name")
    _expect_error(
        "add_money(amount=50)", EffectScope.dialog, "positional", "keyword argument"
    )
    _expect_error(
        "give_stuff(1)", EffectScope.dialog, "unknown effect", "invented verb"
    )
    _expect_error(
        'add_n_items(1,fish)', EffectScope.dialog, "wikilink", "unquoted item"
    )
    _expect_error(
        'add_n_items("fish")', EffectScope.dialog, "<count>", "no count"
    )


def test_every_verb_belongs_to_some_scope() -> None:
    """Czasownik, którego nie da się nigdzie napisać, jest martwym kodem."""
    from dialog.effects import _SIGNATURES

    reachable = {name for names in EFFECTS_BY_SCOPE.values() for name in names}
    assert_eq(sorted(reachable), sorted(_SIGNATURES), "every verb is usable somewhere")


def main() -> None:
    tests = [
        ("test_one_of_each", test_one_of_each),
        ("test_count_repeats_the_key", test_count_repeats_the_key),
        ("test_count_applies_to_every_item", test_count_applies_to_every_item),
        ("test_amounts", test_amounts),
        ("test_targeted_sentiment_carries_the_npc", test_targeted_sentiment_carries_the_npc),
        ("test_a_quest_reward_gives_and_does_not_take",
         test_a_quest_reward_gives_and_does_not_take),
        ("test_a_dialog_cannot_raise_stats", test_a_dialog_cannot_raise_stats),
        ("test_a_dialog_shifts_the_sentiment_of_whoever_is_talking",
         test_a_dialog_shifts_the_sentiment_of_whoever_is_talking),
        ("test_zero_and_negative_are_refused", test_zero_and_negative_are_refused),
        ("test_a_malformed_effect_says_what_to_write",
         test_a_malformed_effect_says_what_to_write),
        ("test_every_verb_belongs_to_some_scope", test_every_verb_belongs_to_some_scope),
    ]
    failed = 0
    for name, test in tests:
        try:
            test()
            print(f"  PASS  {name}")
        except AssertionError as error:
            print(f"  FAIL  {name}: {error}")
            failed += 1

    print()
    if failed:
        print(f"{failed} of {len(tests)} effect tests FAILED.")
        sys.exit(1)
    print(f"All {len(tests)} effect tests passed.")


if __name__ == "__main__":
    main()
