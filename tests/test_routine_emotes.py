#!/usr/bin/env python3
"""Emoji z kroku rutyny i reakcje zwierząt (H01, etap 3 / D6, W3, W7).

Drugi kanał ambientu, niezależny od barków tekstowych: nad głową postaci
pokazuje się obrazek pasujący do tego, co ona akurat robi.

Trzy rzeczy, które muszą być prawdą, żeby to nie zamieniło się w szum:

- **brak pola `emotes` = brak emoji**, i to nie jest błąd - dokładnie ta sama
  filozofia, co pusta komórka destynacji („zostań gdzie jesteś", nie wyjątek"),
- **literówka w nazwie emoji NIE MOŻE być cicha** - `EMOTE_SHEET_DEFINITION` to
  zwykły słownik, więc `zzz_animm` daje albo `KeyError` w losowym momencie
  rozgrywki, albo postać, która po prostu nigdy nic nie pokaże (gorsze, bo nie
  do zauważenia),
- **wariant `_anim` jest osobnym wpisem listy** - to lista waży częstość
  (`["food", "food", "food_anim"]` = jeden na trzy), a nie próg zaszyty w kodzie.
  Podstawienie zastępcze musi więc trzymać wariant, inaczej ważenie przestaje
  cokolwiek znaczyć.

Uruchamianie z katalogu projektu:
    .venv/bin/python tests/test_routine_emotes.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import settings
from npc_schedule import Slot, parse_routines
from settings import (
    EMOTE_FALLBACKS,
    EMOTE_SHEET_DEFINITION,
    known_emote_names,
    resolve_emote,
)


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}\n  expected: {b!r}\n  actual:   {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def _routine(**slot: object) -> dict:
    base = {"from": "08:00", "at": "type:work", "activity": "stand"}
    base.update(slot)
    return {"routine": {"townsfolk": {"slot": [base]}}}


def _first_slot(data: dict, **kwargs: object) -> Slot:
    return parse_routines(data, **kwargs).routines["townsfolk"].slots[0]


# ---------------------------------------------------------------------------
# Parsowanie pola `emotes`
# ---------------------------------------------------------------------------

def test_a_slot_without_emotes_gets_an_empty_tuple() -> None:
    """Brak pola to normalny stan: wieś nie musi być cała oplakatowana emoji."""
    assert_eq(_first_slot(_routine()).emotes, ())


def test_emotes_are_read_in_order() -> None:
    slot = _first_slot(_routine(emotes=["sweat", "star"]), known_emotes=known_emote_names())

    assert_eq(slot.emotes, ("sweat", "star"))


def test_an_anim_variant_is_just_another_entry() -> None:
    """Częstość wariantu steruje sama lista, nie próg w kodzie."""
    slot = _first_slot(_routine(emotes=["food", "food", "food_anim"]),
                       known_emotes=known_emote_names())

    assert_eq(slot.emotes, ("food", "food", "food_anim"))
    assert_eq(slot.emotes.count("food"), 2, "ważenie powtórzeniem przepadło")


def test_an_unknown_emote_is_dropped_loudly() -> None:
    """Sedno: literówka nie ma prawa przejść po cichu."""
    warnings: list[str] = []
    slot = _first_slot(_routine(emotes=["zzz", "zzz_animm"]),
                       warn=warnings.append, known_emotes=known_emote_names())

    assert_eq(slot.emotes, ("zzz",), "nieznana nazwa trafiła do slotu")
    assert_true(any("zzz_animm" in w for w in warnings),
                f"literówka przeszła bez ostrzeżenia: {warnings}")


def test_a_non_list_emotes_field_is_reported_not_crashed() -> None:
    warnings: list[str] = []
    slot = _first_slot(_routine(emotes="zzz"), warn=warnings.append,
                       known_emotes=known_emote_names())

    assert_eq(slot.emotes, ())
    assert_true(any("emotes" in w for w in warnings), f"{warnings}")


def test_without_a_known_set_names_pass_through() -> None:
    """Testy karmione literalnym dictem nie mają skąd wziąć arkusza - i nie muszą."""
    assert_eq(_first_slot(_routine(emotes=["cokolwiek"])).emotes, ("cokolwiek",))


def test_a_bad_emote_does_not_take_the_whole_slot_down() -> None:
    """Krok z jedną literówką nadal działa - degradacja, nie wyjątek."""
    slot = _first_slot(_routine(activity="sleep", emotes=["nie_ma_takiego"]),
                       known_emotes=known_emote_names())

    assert_eq(slot.activity, "sleep")
    assert_eq(slot.emotes, ())


# ---------------------------------------------------------------------------
# Podstawienia zastępcze (assety, których jeszcze nie ma)
# ---------------------------------------------------------------------------

def test_fallbacks_resolve_to_emotes_that_exist() -> None:
    """Inaczej podstawienie tylko przesuwa `KeyError` o jedno miejsce dalej."""
    for name, target in EMOTE_FALLBACKS.items():
        assert_true(target in EMOTE_SHEET_DEFINITION,
                    f"podstawienie '{name}' -> '{target}', którego nie ma w arkuszu")


def test_a_fallback_keeps_the_animated_variant() -> None:
    """`["food", "food", "food_anim"]` przestaje cokolwiek ważyć, gdy oba dają to samo."""
    for name, target in EMOTE_FALLBACKS.items():
        assert_eq(target.endswith("_anim"), name.endswith("_anim"),
                  f"podstawienie '{name}' -> '{target}' gubi wariant")


def test_a_real_emote_resolves_to_itself() -> None:
    assert_eq(resolve_emote("zzz"), "zzz")
    assert_eq(resolve_emote("dots_anim"), "dots_anim")


def test_a_fallback_name_resolves_to_the_stand_in() -> None:
    assert_eq(resolve_emote("food"), EMOTE_FALLBACKS["food"])


def test_a_fallback_never_shadows_a_real_asset() -> None:
    """Gdy autor dorysuje sprite'a, wpis z podstawień MUSI zniknąć.

    Inaczej nazwa dalej rozwiązywałaby się na atrapę, mimo że prawdziwy obrazek
    już leży w arkuszu - i nikt by się nie zorientował, bo coś przecież widać.
    """
    shadowed = [name for name in EMOTE_FALLBACKS if name in EMOTE_SHEET_DEFINITION]

    assert_eq(shadowed, [], "te nazwy mają już swój sprite - skasuj je z EMOTE_FALLBACKS")


def test_known_names_are_the_sum_of_both_sources() -> None:
    known = known_emote_names()

    assert_true("zzz" in known and "food" in known, "brakuje którejś ze stron")
    assert_true("zzz_animm" not in known, "literówka uznana za znaną nazwę")


# ---------------------------------------------------------------------------
# Prawdziwy plik rutyn
# ---------------------------------------------------------------------------

def test_the_real_routines_file_uses_only_known_emotes() -> None:
    """Bramka regresji: `just validate-world` sprawdza to samo, ale w CI."""
    from npc_schedule import load_routines

    warnings: list[str] = []
    load_routines(settings.ROUTINES_FILE, warn=warnings.append,
                  known_emotes=known_emote_names())

    bad = [w for w in warnings if "emote" in w]
    assert_eq(bad, [], "routines.toml używa emoji, którego nie ma")


def test_sleep_steps_declare_a_resting_emote() -> None:
    """`zzz` na kroku `sleep` to jedyny stan STAŁY - spanie nie jest chwilą."""
    from npc_schedule import load_routines

    routines = load_routines(settings.ROUTINES_FILE, known_emotes=known_emote_names())
    sleep_slots = [slot for routine in routines.routines.values()
                   for slot in routine.slots if slot.activity == "sleep"]

    assert_true(bool(sleep_slots), "w rutynach nie ma ani jednego kroku `sleep`")
    for slot in sleep_slots:
        assert_true(any(name.startswith("zzz") for name in slot.emotes),
                    f"krok `sleep` bez `zzz`: {slot}")


# ---------------------------------------------------------------------------
# Reakcje zwierząt (W7)
# ---------------------------------------------------------------------------

def test_animal_reaction_emotes_all_exist() -> None:
    known = known_emote_names()

    for name in settings.ANIMAL_REACTION_EMOTES:
        assert_true(name in known, f"reakcja zwierząt używa nieznanego emoji '{name}'")


def test_animal_reaction_is_weighted_by_repetition() -> None:
    """Ta sama konwencja, co w liście `emotes` slotu - jeden mechanizm, nie dwa."""
    emotes = settings.ANIMAL_REACTION_EMOTES

    assert_true(len(emotes) > len(set(emotes)),
                "pula reakcji nie waży niczego powtórzeniem - to nie błąd, ale i nie zamiar")


if __name__ == "__main__":
    tests = [
        ("brak pola = pusta krotka", test_a_slot_without_emotes_gets_an_empty_tuple),
        ("emoji czytane w kolejności", test_emotes_are_read_in_order),
        ("wariant _anim to zwykły wpis", test_an_anim_variant_is_just_another_entry),
        ("nieznane emoji odrzucone głośno", test_an_unknown_emote_is_dropped_loudly),
        ("emotes nie-lista zgłoszone", test_a_non_list_emotes_field_is_reported_not_crashed),
        ("bez arkusza nazwy przechodzą", test_without_a_known_set_names_pass_through),
        ("zła nazwa nie kładzie slotu", test_a_bad_emote_does_not_take_the_whole_slot_down),
        ("podstawienia wskazują istniejące", test_fallbacks_resolve_to_emotes_that_exist),
        ("podstawienie trzyma wariant", test_a_fallback_keeps_the_animated_variant),
        ("prawdziwe emoji to ono samo", test_a_real_emote_resolves_to_itself),
        ("nazwa zastępcza -> atrapa", test_a_fallback_name_resolves_to_the_stand_in),
        ("podstawienie nie zasłania assetu", test_a_fallback_never_shadows_a_real_asset),
        ("znane nazwy to suma źródeł", test_known_names_are_the_sum_of_both_sources),
        ("routines.toml używa znanych emoji", test_the_real_routines_file_uses_only_known_emotes),
        ("kroki `sleep` mają `zzz`", test_sleep_steps_declare_a_resting_emote),
        ("emoji reakcji zwierząt istnieją", test_animal_reaction_emotes_all_exist),
        ("pula reakcji waży powtórzeniem", test_animal_reaction_is_weighted_by_repetition),
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
