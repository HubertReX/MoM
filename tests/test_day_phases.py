#!/usr/bin/env python3
"""Fazy doby: podział bez dziur, bez zakładek i z zawinięciem przez północ (H01/D1).

`settings.DAY_PHASES` jest **jedynym** źródłem granic pory dnia: czyta je filtr
nocy (`scene/night_filter.py`) i predykat `time_of_day(faza)` w warunkach barków.
Dwa komplety tych samych liczb 6/9/17/20 to dokładnie to, czego H01 miało się
pozbyć, więc test pilnuje kontraktu samej funkcji, a nie wyglądu filtra.

Najbardziej podstępny przypadek to `night`: jedyna faza, dla której początek jest
większy od końca. Naiwne `start <= h < end` zwraca dla 02:00 pustkę - nocny bark
nigdy by nie zapalił i nikt by tego nie zauważył, bo o 02:00 rzadko kto gra.

Uruchamianie z katalogu projektu:
    .venv/bin/python tests/test_day_phases.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import settings
from scene.world_clock import day_phase, phase_bounds, phase_names


def _half_hours() -> list[float]:
    """Każda pełna i połówkowa godzina doby - 48 punktów kontrolnych."""
    return [step / 2 for step in range(48)]


# ---------------------------------------------------------------------------
# Kształt samej stałej
# ---------------------------------------------------------------------------

def test_phases_are_sorted_and_in_range() -> None:
    """`day_phase` przerywa pętlę na pierwszej fazie z przyszłości - kolejność to kontrakt."""
    starts = [start for _, start in settings.DAY_PHASES]

    assert starts == sorted(starts), f"DAY_PHASES nie jest posortowane rosnąco: {starts}"
    assert len(set(starts)) == len(starts), f"dwie fazy zaczynają się o tej samej godzinie: {starts}"
    for start in starts:
        assert 0.0 <= start < 24.0, f"godzina startu poza dobą: {start}"


def test_phase_names_are_unique() -> None:
    names = phase_names()

    assert len(set(names)) == len(names), f"powtórzona nazwa fazy: {names}"


# ---------------------------------------------------------------------------
# Podział doby
# ---------------------------------------------------------------------------

def test_every_hour_of_the_day_has_a_phase() -> None:
    """Bez dziur: gdyby któraś godzina nie miała fazy, bark z tamtej pory nigdy by nie zapalił."""
    known = set(phase_names())

    for hour in _half_hours():
        phase = day_phase(hour)
        assert phase in known, f"godzina {hour} dała nieznaną fazę {phase!r}"


def test_phases_do_not_overlap() -> None:
    """Bez zakładek: każda godzina ma DOKŁADNIE jedną fazę.

    Wynika to z kształtu funkcji (zwraca jedną nazwę), więc test sprawdza rzecz
    mocniejszą: że przynależność zgadza się z granicami z `phase_bounds`.
    """
    for hour in _half_hours():
        phase = day_phase(hour)
        start, end = phase_bounds(phase)
        if start < end:
            inside = start <= hour < end
        else:  # faza zawijająca się przez północ
            inside = hour >= start or hour < end
        assert inside, f"godzina {hour} wypadła w fazie {phase!r} o granicach {start}-{end}"


def test_boundaries_belong_to_the_phase_that_starts() -> None:
    """Godzina graniczna należy do fazy, która się o niej ZACZYNA, nie do poprzedniej."""
    for name, start in settings.DAY_PHASES:
        assert day_phase(start) == name, f"o {start} powinna zaczynać się faza {name!r}"


def test_night_wraps_through_midnight() -> None:
    """Sedno: 20:00, 23:59, 00:00 i 02:00 to ta sama faza."""
    late = day_phase(20.0)

    for hour in (20.0, 23.5, 0.0, 2.0, 5.5):
        assert day_phase(hour) == late, f"o {hour} faza to {day_phase(hour)!r}, a nie {late!r}"


def test_the_four_documented_phases_land_where_the_filter_draws_them() -> None:
    """Kotwice z dokumentu H01 - żeby przestawienie stałej nie przeszło po cichu."""
    assert day_phase(7.0) == "morning"
    assert day_phase(12.0) == "day"
    assert day_phase(18.0) == "evening"
    assert day_phase(22.0) == "night"


def test_hours_outside_the_day_are_normalised() -> None:
    """Zegar sceny nie powinien wyjść poza dobę, ale funkcja i tak nie ma prawa rzucić."""
    assert day_phase(24.0) == day_phase(0.0)
    assert day_phase(26.5) == day_phase(2.5)
    assert day_phase(-1.0) == day_phase(23.0)


# ---------------------------------------------------------------------------
# phase_bounds
# ---------------------------------------------------------------------------

def test_phase_bounds_chain_into_a_closed_loop() -> None:
    """Koniec każdej fazy jest początkiem następnej - inaczej interpolacja skacze."""
    names = phase_names()

    for index, name in enumerate(names):
        _start, end = phase_bounds(name)
        next_start = phase_bounds(names[(index + 1) % len(names)])[0]
        assert end == next_start, f"koniec {name!r} ({end}) nie styka się z początkiem następnej ({next_start})"


def test_phase_bounds_rejects_an_unknown_name() -> None:
    """Literówka w nazwie fazy ma być głośna, a nie dawać cichy `False` na zawsze."""
    try:
        phase_bounds("mornign")
    except KeyError:
        return
    raise AssertionError("phase_bounds przyjęło nieistniejącą fazę")


if __name__ == "__main__":
    tests = [
        ("fazy są posortowane i w dobie", test_phases_are_sorted_and_in_range),
        ("nazwy faz są unikalne", test_phase_names_are_unique),
        ("każda godzina ma fazę", test_every_hour_of_the_day_has_a_phase),
        ("fazy się nie zakładają", test_phases_do_not_overlap),
        ("granica należy do fazy, która się zaczyna", test_boundaries_belong_to_the_phase_that_starts),
        ("noc zawija się przez północ", test_night_wraps_through_midnight),
        ("cztery udokumentowane fazy", test_the_four_documented_phases_land_where_the_filter_draws_them),
        ("godziny spoza doby są normalizowane", test_hours_outside_the_day_are_normalised),
        ("granice faz tworzą zamkniętą pętlę", test_phase_bounds_chain_into_a_closed_loop),
        ("nieznana faza jest głośna", test_phase_bounds_rejects_an_unknown_name),
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
