#!/usr/bin/env python3
"""Wskaźnik „co teraz?" - czysta logika śledzonego questa (H01/D7).

Dziennik pokazuje wszystko; wskaźnik odpowiada na jedno pytanie. Ten plik pilnuje
trzech rzeczy, które łatwo pomylić: **kto wybiera**, **co się dzieje po
ukończeniu** i **co, gdy nie ma czego śledzić**.

Kaskada ma pięć kroków i każdy jest tu testowany OSOBNO - to nie jest ozdoba
metodologiczna: kroki 2-4 odpalają się rzadko (dopiero gdy quest niczego nie
odblokował, gdy domknął się cały wątek, gdy skończyła się gałąź), więc test „na
oko" przechodziłby na pierwszym kroku i milczał o pozostałych.

Bez ekranu i bez sceny - `quest/tracker.py` jest czystą funkcją na definicjach
i stanie.

Uruchamianie z katalogu projektu:
    .venv/bin/python tests/test_quest_tracking.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from quest import tracker
from quest.entities import CompletionMode, QuestDef, QuestState


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}\n  expected: {b!r}\n  actual:   {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def _quest(key: str, *, parent: str | None = None, requires: list[str] | None = None,
           completion: CompletionMode = CompletionMode.manual) -> QuestDef:
    return QuestDef(
        key, f"name.{key}", f"desc.{key}", f"success.{key}", completion,
        requires=requires or [], parent=parent,
    )


def _defs(*quests: QuestDef) -> dict[str, QuestDef]:
    """Kolejność argumentów = kolejność definicji = kolejność sekcji w Obsidianie."""
    return {quest.key: quest for quest in quests}


def _state(*done: str) -> QuestState:
    state = QuestState()
    for key in done:
        state.mark_done(key)
    return state


#: Drzewko z dwoma wątkami po dwa kroki - najmniejszy kształt, na którym widać
#: różnicę między "co ten krok odblokował", "rodzeństwo" i "gałąź wyżej".
def _tree() -> dict[str, QuestDef]:
    return _defs(
        _quest("T1", completion=CompletionMode.all_subquests),
        _quest("T1_A", parent="T1"),
        _quest("T1_B", parent="T1"),
        _quest("T2", completion=CompletionMode.all_subquests, requires=["T1"]),
        _quest("T2_A", parent="T2"),
    )


# ---------------------------------------------------------------------------
# Kto wybiera: automat
# ---------------------------------------------------------------------------

def test_the_automat_picks_the_first_open_step() -> None:
    """Kolejność definicji to kolejność sekcji w pliku questa - sterowalna treścią."""
    assert_eq(tracker.auto_pick(_tree(), _state()), "T1_A")


def test_the_automat_never_picks_an_umbrella() -> None:
    """Parasol mówi „przełam klątwę" - to tytuł rozdziału, nie instrukcja."""
    steps = tracker.open_steps(_tree(), _state())

    assert_true("T1" not in steps and "T2" not in steps, f"parasol w kandydatach: {steps}")


def test_the_automat_never_picks_a_locked_step() -> None:
    """T2_A czeka na swój parasol, a ten na T1 - nie ma czego tam podpowiadać."""
    assert_true("T2_A" not in tracker.open_steps(_tree(), _state()))


def test_a_finished_step_is_not_a_candidate() -> None:
    assert_eq(tracker.auto_pick(_tree(), _state("T1_A")), "T1_B")


def test_nothing_to_track_yields_none() -> None:
    """Gdy wszystko zrobione, wskaźnik ma zniknąć - bez pustej ramki."""
    assert_eq(tracker.auto_pick(_tree(), _state("T1_A", "T1_B", "T1", "T2_A", "T2")), None)


# ---------------------------------------------------------------------------
# Kaskada - każdy z pięciu kroków osobno
# ---------------------------------------------------------------------------

def test_cascade_1_follows_what_the_step_just_unlocked() -> None:
    """Wprost życzenie autora: quest prowadzi gracza do tego, co odblokował."""
    defs = _defs(
        _quest("A"),
        _quest("Z"),
        _quest("B", requires=["A"]),
    )
    state = _state("A")

    assert_eq(tracker.cascade(defs, state, "A", ["B"]), "B")


def test_cascade_1_skips_an_umbrella_it_unlocked() -> None:
    """Odblokowany parasol to nagłówek - gracz potrzebuje kroku w środku."""
    defs = _defs(
        _quest("A"),
        _quest("T", completion=CompletionMode.all_subquests, requires=["A"]),
        _quest("T_A", parent="T"),
    )
    state = _state("A")

    assert_eq(tracker.cascade(defs, state, "A", ["T", "T_A"]), "T_A")


def test_cascade_2_falls_back_to_a_sibling() -> None:
    """Krok, który nic nie odblokował - zostaje reszta tego samego wątku."""
    defs = _tree()
    state = _state("T1_A")

    assert_eq(tracker.cascade(defs, state, "T1_A", []), "T1_B")


def test_cascade_3_climbs_to_the_thread_above() -> None:
    """Cały wątek się domknął: szukamy w gałęzi piętro wyżej, a nie globalnie."""
    defs = _defs(
        _quest("ROOT", completion=CompletionMode.all_subquests),
        _quest("BRANCH", parent="ROOT", completion=CompletionMode.all_subquests),
        _quest("BRANCH_A", parent="BRANCH"),
        _quest("ROOT_B", parent="ROOT"),
        _quest("ELSEWHERE"),
    )
    state = _state("BRANCH_A", "BRANCH")

    assert_eq(tracker.cascade(defs, state, "BRANCH_A", []), "ROOT_B")


def test_cascade_4_falls_back_globally() -> None:
    """Nic w pobliżu - bierzemy cokolwiek otwartego, deterministycznie."""
    defs = _defs(
        _quest("T", completion=CompletionMode.all_subquests),
        _quest("T_A", parent="T"),
        _quest("LONE_1"),
        _quest("LONE_2"),
    )
    state = _state("T_A", "T")

    picked = tracker.cascade(defs, state, "T_A", [])

    assert_true(picked in ("LONE_1", "LONE_2"), f"globalny fallback nie zadziałał: {picked}")
    assert_eq(picked, "LONE_2", "fallback ma być ostatni w kolejności definicji")


def test_cascade_5_gives_up_cleanly() -> None:
    """Ostatni quest w grze zamknięty: wskaźnik znika, nie zostaje pusta ramka."""
    defs = _defs(_quest("ONLY"))

    assert_eq(tracker.cascade(defs, _state("ONLY"), "ONLY", []), None)


def test_the_cascade_prefers_the_unlocked_over_the_sibling() -> None:
    """Kolejność kroków ma znaczenie, więc pilnujemy jej wprost."""
    defs = _defs(
        _quest("T", completion=CompletionMode.all_subquests),
        _quest("T_A", parent="T"),
        _quest("T_B", parent="T"),
        _quest("NEW", requires=["T_A"]),
    )
    state = _state("T_A")

    assert_eq(tracker.cascade(defs, state, "T_A", ["NEW"]), "NEW",
              "rodzeństwo wygrało z tym, co krok właśnie odblokował")


# ---------------------------------------------------------------------------
# Pin: przypięcie, odpięcie, odmowa
# ---------------------------------------------------------------------------

def test_t_pins_the_selected_quest() -> None:
    defs, state = _tree(), _state()

    key, pinned, message = tracker.toggle_pin(defs, state, "T1_A", "T1_B")

    assert_eq((key, pinned), ("T1_B", True))
    assert_eq(message, "quest.track_on")


def test_t_on_a_pinned_quest_unpins_it() -> None:
    """Jeden klawisz robi obie rzeczy - drugi skrót nikt by nigdy nie użył."""
    defs, state = _tree(), _state()

    key, pinned, message = tracker.toggle_pin(defs, state, "T1_B", "T1_B", pinned=True)

    assert_eq(pinned, False, "odpięcie nie zdjęło pinu")
    assert_eq(key, tracker.auto_pick(defs, state), "po odpięciu wraca wybór automatu")
    assert_eq(message, "quest.track_off")


def test_t_pins_the_quest_the_automat_had_chosen() -> None:
    """Inaczej questa wybranego automatem nie dałoby się przypiąć NIGDY.

    Dokument opisywał ten wiersz jako „aktualnie śledzony -> odpięcie", zakładając
    milcząco, że śledzony znaczy przypięty. Wskaźnik jest jednak ustawiony także
    wtedy, gdy wybrał go automat - i wtedy „odpięcie" byłoby operacją, która nic
    nie zmienia, a jeszcze mówiłaby graczowi, że wraca do trybu, z którego nigdy
    nie wyszedł.
    """
    defs, state = _tree(), _state()

    key, pinned, message = tracker.toggle_pin(defs, state, "T1_A", "T1_A", pinned=False)

    assert_eq((key, pinned), ("T1_A", True))
    assert_eq(message, "quest.track_on")


def test_an_umbrella_may_be_pinned_by_hand() -> None:
    """Automat parasole odrzuca, ale jawny wybór gracza bije heurystykę."""
    defs, state = _tree(), _state()

    key, pinned, _message = tracker.toggle_pin(defs, state, None, "T1")

    assert_eq((key, pinned), ("T1", True))


def test_a_finished_quest_is_refused_with_a_message() -> None:
    """Odmowa NIE jest ciszą: bez komunikatu gracz nie wie, czy gra go usłyszała."""
    defs, state = _tree(), _state("T1_A")

    key, pinned, message = tracker.toggle_pin(defs, state, "T1_B", "T1_A")

    assert_eq((key, pinned), ("T1_B", False), "odmowa nie może ruszyć wskaźnika")
    assert_eq(message, "quest.track_refused_done")


def test_a_locked_quest_is_refused_with_a_message() -> None:
    defs, state = _tree(), _state()

    _key, _pinned, message = tracker.toggle_pin(defs, state, "T1_A", "T2_A")

    assert_eq(message, "quest.track_refused_locked")


def test_an_unknown_key_is_refused() -> None:
    _key, _pinned, message = tracker.toggle_pin(_tree(), _state(), "T1_A", "NIE_MA")

    assert_eq(message, "quest.track_refused")


# ---------------------------------------------------------------------------
# next_tracked - reguły spotykają się w jednym miejscu
# ---------------------------------------------------------------------------

def test_a_pin_survives_an_unrelated_quest_event() -> None:
    """Po to jest pin: automat NIE rusza świadomego wyboru gracza."""
    defs = _tree()
    state = _state()

    key, pinned = tracker.next_tracked(defs, state, "T1_B", True, [], ["T1_A"])

    assert_eq((key, pinned), ("T1_B", True))


def test_the_pin_does_not_survive_the_cascade() -> None:
    """Nowy wybór jest wyborem AUTOMATU.

    Przeniesienie pinu przykleiłoby wskaźnik do questa, którego gracz nigdy nie
    wskazał, i nie dałoby się tego cofnąć inaczej niż przez dziennik.
    """
    defs = _tree()
    state = _state("T1_A")

    key, pinned = tracker.next_tracked(defs, state, "T1_A", True, ["T1_A"], [])

    assert_eq(key, "T1_B")
    assert_eq(pinned, False, "pin przeżył kaskadę")


def test_an_automatic_choice_is_replaced_when_it_closes() -> None:
    defs = _tree()
    state = _state("T1_A")

    assert_eq(tracker.next_tracked(defs, state, "T1_A", False, ["T1_A"], []), ("T1_B", False))


def test_no_tracked_quest_lets_the_automat_pick() -> None:
    assert_eq(tracker.next_tracked(_tree(), _state(), None, False, [], []), ("T1_A", False))


def test_a_key_the_content_no_longer_defines_falls_back_to_the_automat() -> None:
    """Zapis sprzed przemianowania questa: cichy powrót do automatu, nie wyjątek."""
    defs = _tree()

    key, pinned = tracker.next_tracked(defs, _state(), "SKASOWANY_QUEST", True, [], [])

    assert_eq(key, "T1_A")
    assert_eq(pinned, False, "pin na nieistniejącym queście przetrwał")


def test_a_pinned_quest_that_got_locked_falls_back() -> None:
    """Teoretyczny, ale tani: quest, który przestał być odblokowany, nie może wisieć."""
    defs = _defs(_quest("A"), _quest("B", requires=["A"]))

    key, pinned = tracker.next_tracked(defs, _state(), "B", True, [], [])

    assert_eq((key, pinned), ("A", False))


def test_is_still_valid_accepts_a_pinned_umbrella() -> None:
    """Parasol jest legalnym CELEM śledzenia, choć automat go nie wybierze."""
    defs, state = _tree(), _state()

    assert_true(tracker.is_still_valid(defs, state, "T1"))
    assert_true(not tracker.is_trackable(defs, state, "T1"))


# ---------------------------------------------------------------------------
# Zapis
# ---------------------------------------------------------------------------

def test_the_tracked_quest_survives_a_save_round_trip() -> None:
    from save_load.models import SaveGame

    restored = SaveGame.from_dict(
        SaveGame(tracked_quest_key="T1_B", tracked_quest_pinned=True).to_dict())

    assert_eq(restored.tracked_quest_key, "T1_B")
    assert_eq(restored.tracked_quest_pinned, True)


def test_a_save_written_before_h01_loads_into_automatic_mode() -> None:
    """Pola opcjonalne z wartością domyślną - BEZ podbijania wersji zapisu (jak E03)."""
    from save_load.models import SaveGame

    old = SaveGame.from_dict({"player": {}, "clock": {}, "maps": {}})

    assert_eq(old.tracked_quest_key, "")
    assert_eq(old.tracked_quest_pinned, False)


def test_the_save_version_did_not_move() -> None:
    """Bramka: dodanie tych pól nie ma prawa odrzucić żadnego istniejącego zapisu."""
    from enums import SaveCompatEnum
    from save_load.models import SaveGame, save_compatibility
    from settings import VERSION

    save = SaveGame(tracked_quest_key="T1_B", tracked_quest_pinned=True)

    assert_eq(save_compatibility(VERSION), SaveCompatEnum.ok,
              "dodanie pól wskaźnika odrzuciłoby bieżące zapisy")
    assert_true("tracked_quest_key" in save.to_dict(), "pole nie trafiło do zapisu")


if __name__ == "__main__":
    tests = [
        ("automat bierze pierwszy otwarty krok", test_the_automat_picks_the_first_open_step),
        ("automat nie bierze parasola", test_the_automat_never_picks_an_umbrella),
        ("automat nie bierze zablokowanego", test_the_automat_never_picks_a_locked_step),
        ("ukończony nie jest kandydatem", test_a_finished_step_is_not_a_candidate),
        ("brak kandydata = None", test_nothing_to_track_yields_none),
        ("kaskada 1: co krok odblokował", test_cascade_1_follows_what_the_step_just_unlocked),
        ("kaskada 1 pomija parasol", test_cascade_1_skips_an_umbrella_it_unlocked),
        ("kaskada 2: rodzeństwo", test_cascade_2_falls_back_to_a_sibling),
        ("kaskada 3: gałąź wyżej", test_cascade_3_climbs_to_the_thread_above),
        ("kaskada 4: globalnie", test_cascade_4_falls_back_globally),
        ("kaskada 5: czyste poddanie się", test_cascade_5_gives_up_cleanly),
        ("kolejność kroków kaskady", test_the_cascade_prefers_the_unlocked_over_the_sibling),
        ("T przypina zaznaczony", test_t_pins_the_selected_quest),
        ("T na przypiętym odpina", test_t_on_a_pinned_quest_unpins_it),
        ("T przypina wybór automatu", test_t_pins_the_quest_the_automat_had_chosen),
        ("parasol wolno przypiąć ręcznie", test_an_umbrella_may_be_pinned_by_hand),
        ("ukończony odmawia z komunikatem", test_a_finished_quest_is_refused_with_a_message),
        ("zablokowany odmawia z komunikatem", test_a_locked_quest_is_refused_with_a_message),
        ("nieznany klucz odmawia", test_an_unknown_key_is_refused),
        ("pin przeżywa obce zdarzenie", test_a_pin_survives_an_unrelated_quest_event),
        ("pin NIE przeżywa kaskady", test_the_pin_does_not_survive_the_cascade),
        ("wybór automatu podmieniany", test_an_automatic_choice_is_replaced_when_it_closes),
        ("brak śledzonego = automat", test_no_tracked_quest_lets_the_automat_pick),
        ("skasowany quest -> automat", test_a_key_the_content_no_longer_defines_falls_back_to_the_automat),
        ("zablokowany pin -> automat", test_a_pinned_quest_that_got_locked_falls_back),
        ("przypięty parasol jest ważny", test_is_still_valid_accepts_a_pinned_umbrella),
        ("wskaźnik przeżywa zapis", test_the_tracked_quest_survives_a_save_round_trip),
        ("stary zapis = tryb automatyczny", test_a_save_written_before_h01_loads_into_automatic_mode),
        ("wersja zapisu bez zmian", test_the_save_version_did_not_move),
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
