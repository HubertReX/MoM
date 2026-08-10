#!/usr/bin/env python3
"""Zakres `bark` w mini-DSL warunków (H01/D1).

Bark to trzeci kontekst warunków, obok dialogu i questa. Ma mówiącego (więc
`sentiment` i jednoargumentowe `visited()` mają sens), ale dzieje się w świecie,
a nie w rozmowie - stąd cztery predykaty, których nie zna żaden inny zakres:
`time_of_day`, `activity`, `at`, `on_map`.

Testowana jest granica zakresu, nie treść: co wolno napisać w warunku barka,
czego nie wolno napisać nigdzie indziej, i że pomyłka jest **głośna**. Cichy
`False` to najgorszy tryb awarii treści w tej grze - tak zniknął kiedyś cały
dialog Miecza.

Uruchamianie z katalogu projektu:
    .venv/bin/python tests/test_bark_conditions.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from dialog.conditions import (
    ConditionError,
    ConditionScope,
    check_condition,
    validate_condition,
)

BARK = ConditionScope.bark


class FakeBarkContext:
    """Minimalny kontekst barka - dokładnie te metody, których żąda protokół."""

    def __init__(
        self,
        *,
        phase: str = "day",
        activity_name: str = "stand",
        slot_at: str = "type:work",
        map_key: str = "BLUNDERHAVEN",
        sentiment: int = 50,
        items: dict[str, int] | None = None,
        visited_nodes: set[tuple[str | None, str]] | None = None,
        done_quests: set[str] | None = None,
    ) -> None:
        self._phase = phase
        self._activity = activity_name
        self._at = slot_at
        self._map = map_key
        self._sentiment = sentiment
        self._items = items or {}
        self._visited = visited_nodes or set()
        self._quests = done_quests or set()

    def visited(self, node_key: str, npc: str | None = None) -> bool:
        return (npc, node_key) in self._visited

    def has_item(self, item_key: str) -> bool:
        return self._items.get(item_key, 0) > 0

    def item_count(self, item_key: str) -> int:
        return self._items.get(item_key, 0)

    def quest_done(self, quest_key: str) -> bool:
        return quest_key in self._quests

    @property
    def sentiment(self) -> int:
        return self._sentiment

    def time_of_day(self, phase: str) -> bool:
        return phase == self._phase

    def activity(self, name: str) -> bool:
        return name == self._activity

    def at(self, spec: str) -> bool:
        return spec == self._at

    def on_map(self, map_key: str) -> bool:
        return map_key == self._map


def _rejects(condition: str, scope: ConditionScope = BARK) -> str:
    """Zwróć komunikat błędu; brak błędu to porażka testu."""
    try:
        validate_condition(condition, scope)
    except ConditionError as exc:
        return str(exc)
    raise AssertionError(f"warunek {condition!r} przeszedł walidację w zakresie {scope.value}")


# ---------------------------------------------------------------------------
# Co wolno w zakresie bark
# ---------------------------------------------------------------------------

def test_the_four_world_predicates_validate() -> None:
    for condition in (
        'time_of_day("morning")',
        'activity("sleep")',
        'at("type:work")',
        'on_map("BLUNDERHAVEN")',
    ):
        validate_condition(condition, BARK)


def test_the_shared_predicates_still_work() -> None:
    """Linia przeniesiona z opcji dialogowej do barka ma znaczyć to samo."""
    for condition in (
        'visited("012")',
        'visited("BARMAN_ABSINTHRAYNER", "012")',
        'has_item("golden_key")',
        'item_count("golden_key") >= 2',
        'quest_done("Q01_S01_LEARN_ABOUT_CURSE")',
        "sentiment > 60",
    ):
        validate_condition(condition, BARK)


def test_predicates_compose() -> None:
    validate_condition(
        'time_of_day("evening") and not activity("sleep") '
        'or (sentiment > 60 and on_map("LOST_CORK_TAVERN"))',
        BARK,
    )


# ---------------------------------------------------------------------------
# Czego nie wolno - i gdzie
# ---------------------------------------------------------------------------

def test_selected_is_not_a_bark_predicate() -> None:
    """Bark nie jest częścią rozmowy, więc „którą opcję wybrałeś" nie ma znaczenia."""
    message = _rejects('selected("SOME_OPTION")')

    assert "selected" in message, message
    assert "bark" in message, f"komunikat nie nazywa zakresu: {message}"


def test_world_predicates_are_rejected_in_dialog_and_quest() -> None:
    """Trzy nowe nazwy NIE mogą wyciec do pozostałych zakresów.

    Gdyby wyciekły, quest pytałby o `activity()` postaci, której nie ma - czyli
    o dokładnie ten cichy `False`, przed którym broni podział na zakresy.
    """
    for scope in (ConditionScope.dialog, ConditionScope.quest):
        for condition in ('time_of_day("day")', 'activity("stand")',
                          'at("type:work")', 'on_map("X")'):
            _rejects(condition, scope)


def test_bark_predicates_take_exactly_one_string() -> None:
    _rejects("time_of_day()")
    _rejects('time_of_day("day", "night")')
    _rejects("on_map(BLUNDERHAVEN)")          # goła nazwa, nie literał
    _rejects('activity(phase="sleep")')       # argument nazwany
    _rejects("at()")
    _rejects('at("type:work", "type:home")')


def test_the_sandbox_still_holds_in_the_bark_scope() -> None:
    """Nowy zakres nie może być furtką: żadnych atrybutów, indeksów ani lambd."""
    _rejects("__import__('os').system('true')")
    _rejects("scene.hour")
    _rejects("items[0]")


# ---------------------------------------------------------------------------
# Ewaluacja
# ---------------------------------------------------------------------------

def test_time_of_day_reads_the_context() -> None:
    ctx = FakeBarkContext(phase="night")

    assert check_condition('time_of_day("night")', ctx, BARK)
    assert not check_condition('time_of_day("morning")', ctx, BARK)


def test_activity_is_not_the_same_question_as_time_of_day() -> None:
    """Barman ma lunch o innej porze niż Bart - „głodny" to krok rutyny, nie godzina."""
    ctx = FakeBarkContext(phase="day", activity_name="wander")

    assert check_condition('activity("wander")', ctx, BARK)
    assert not check_condition('activity("stand")', ctx, BARK)
    assert check_condition('time_of_day("day") and activity("wander")', ctx, BARK)


def test_at_names_the_step_not_the_activity() -> None:
    """Ten sam `activity`, dwa różne kroki dnia - `at` je rozróżnia.

    `stand` znaczy „stoi" i tyle: barman za barem i Bart przy straganie mają go
    tak samo. Dopiero `at` mówi, KTÓRY to krok - i to jest odpowiedź na pytanie
    „co ta postać teraz robi w swoim dniu".
    """
    working = FakeBarkContext(activity_name="stand", slot_at="type:work")
    lunching = FakeBarkContext(activity_name="stand", slot_at="type:social")

    assert check_condition('at("type:work")', working, BARK)
    assert not check_condition('at("type:social")', working, BARK)
    assert check_condition('activity("stand") and at("type:social")', lunching, BARK)
    assert not check_condition('activity("stand") and at("type:work")', lunching, BARK)


def test_at_takes_the_spec_verbatim() -> None:
    """Wartość jest dokładnie tym, co autor napisał w routines.toml - z prefiksem."""
    ctx = FakeBarkContext(slot_at="location:Tavern")

    assert check_condition('at("location:Tavern")', ctx, BARK)
    # sam argument bez rodzaju nie pasuje - i nie ma pasować; walidator świata
    # (reguła 20) odrzuci taki warunek już przy `just validate-world`
    assert not check_condition('at("Tavern")', ctx, BARK)


def test_on_map_reads_the_context() -> None:
    ctx = FakeBarkContext(map_key="LOST_CORK_TAVERN")

    assert check_condition('on_map("LOST_CORK_TAVERN")', ctx, BARK)
    assert not check_condition('on_map("BLUNDERHAVEN")', ctx, BARK)


def test_sentiment_is_the_speakers() -> None:
    assert check_condition("sentiment > 60", FakeBarkContext(sentiment=75), BARK)
    assert not check_condition("sentiment > 60", FakeBarkContext(sentiment=20), BARK)


def test_quest_done_carries_the_world_fact(  ) -> None:
    """D3: „wieś wie o klątwie" to jeden quest, a nie nowy rejestr stanu."""
    curse = "Q01_S01_LEARN_ABOUT_CURSE"
    before = FakeBarkContext()
    after = FakeBarkContext(done_quests={curse})

    assert not check_condition(f'quest_done("{curse}")', before, BARK)
    assert check_condition(f'quest_done("{curse}")', after, BARK)


def test_visited_defaults_to_the_speaker() -> None:
    ctx = FakeBarkContext(visited_nodes={(None, "012")})

    assert check_condition('visited("012")', ctx, BARK)
    assert not check_condition('visited("013")', ctx, BARK)


# ---------------------------------------------------------------------------
# Adapter na żywe dane
# ---------------------------------------------------------------------------

def test_speaker_activity_is_empty_without_a_routine() -> None:
    """Postać bez rutyny nie pasuje do żadnego `activity(...)` - i to nie jest błąd."""
    from dialog.bark_context import speaker_activity

    class NoRoutine:
        _schedule_slot = None

    assert speaker_activity(NoRoutine()) == ""


def test_speaker_activity_reads_the_current_slot() -> None:
    from dialog.bark_context import speaker_activity
    from npc_schedule import Slot

    class WithSlot:
        _schedule_slot = Slot(from_minutes=8 * 60, at="type:work", activity="stand")

    assert speaker_activity(WithSlot()) == "stand"


def test_speaker_slot_at_reads_the_current_step() -> None:
    from dialog.bark_context import speaker_slot_at
    from npc_schedule import Slot

    class WithSlot:
        _schedule_slot = Slot(from_minutes=8 * 60, at="type:work", activity="stand")

    class NoRoutine:
        _schedule_slot = None

    assert speaker_slot_at(WithSlot()) == "type:work"
    # postać bez rutyny nie pasuje do żadnego `at(...)` - tak samo jak do `activity(...)`
    assert speaker_slot_at(NoRoutine()) == ""


def test_speaker_map_prefers_the_logical_map() -> None:
    from dialog.bark_context import speaker_map
    from npc_runtime import NpcRuntime

    class Npc:
        runtime = NpcRuntime(logical_map="LOST_CORK_TAVERN")
        current_map = "BLUNDERHAVEN"

    class Fresh:
        runtime = NpcRuntime()
        current_map = "BLUNDERHAVEN"

    assert speaker_map(Npc()) == "LOST_CORK_TAVERN"
    # pusty `logical_map` (świeży obiekt / stary zapis) degraduje się do mapy spawnu
    assert speaker_map(Fresh()) == "BLUNDERHAVEN"


if __name__ == "__main__":
    tests = [
        ("cztery predykaty świata przechodzą walidację", test_the_four_world_predicates_validate),
        ("wspólne predykaty nadal działają", test_the_shared_predicates_still_work),
        ("predykaty się składają", test_predicates_compose),
        ("selected() nie jest predykatem barka", test_selected_is_not_a_bark_predicate),
        ("predykaty świata odrzucane w dialogu i queście", test_world_predicates_are_rejected_in_dialog_and_quest),
        ("predykaty barka biorą jeden literał", test_bark_predicates_take_exactly_one_string),
        ("piaskownica trzyma się w zakresie bark", test_the_sandbox_still_holds_in_the_bark_scope),
        ("time_of_day czyta kontekst", test_time_of_day_reads_the_context),
        ("activity to nie to samo co time_of_day", test_activity_is_not_the_same_question_as_time_of_day),
        ("at nazywa krok rutyny, nie aktywność", test_at_names_the_step_not_the_activity),
        ("at bierze zapis wprost z routines.toml", test_at_takes_the_spec_verbatim),
        ("on_map czyta kontekst", test_on_map_reads_the_context),
        ("sentyment jest mówiącego", test_sentiment_is_the_speakers),
        ("quest_done niesie fakt świata", test_quest_done_carries_the_world_fact),
        ("visited domyślnie o mówiącym", test_visited_defaults_to_the_speaker),
        ("brak rutyny = pusta aktywność", test_speaker_activity_is_empty_without_a_routine),
        ("aktywność z bieżącego slotu", test_speaker_activity_reads_the_current_slot),
        ("krok `at` z bieżącego slotu", test_speaker_slot_at_reads_the_current_step),
        ("mapa mówiącego to mapa logiczna", test_speaker_map_prefers_the_logical_map),
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
