#!/usr/bin/env python3
"""Import barków z Obsidiana: sekcja `## Barki` i wspólne pule (H01/D2, D4, D5).

Autor pisze barki w dwóch miejscach - w pliku postaci i we wspólnym
`doc/PL/Barki.md` - a importer ma z tego zrobić jedną rzecz: listę kandydatów
z warunkami. Ten plik pilnuje granicy między tym, co autor napisał, a tym, co
dostaje runtime.

Trzy rzeczy, które muszą być GŁOŚNE, bo inaczej autor dowie się o nich dopiero
z gry (albo wcale):

- bark, który nie mieści się w dwóch liniach po 28 znaków,
- warunek spoza zakresu `bark`,
- nagłówek puli, który nie jest kluczem encji.

I jedna, która musi być CICHA, bo to normalny stan: brak sekcji `## Barki`.

Uruchamianie z katalogu projektu:
    .venv/bin/python tests/test_bark_import.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from dialog.markdown_importer import (
    BARK_MESSAGE_PREFIX,
    DialogImportError,
    _emit_barks,
    parse_bark_pools,
    parse_character_barks,
    wrap_bark,
)
from settings import BARK_LINE_CHARS, BARK_MAX_LINES


def _write(text: str, name: str = "file.md") -> Path:
    tmp = Path(tempfile.mkdtemp()) / name
    tmp.write_text(text, encoding="utf-8")
    return tmp


def _fails(func, *args) -> str:
    try:
        func(*args)
    except DialogImportError as exc:
        return str(exc)
    raise AssertionError("import przeszedł, a miał się wywalić")


# ---------------------------------------------------------------------------
# Sekcja `## Barki` w pliku postaci
# ---------------------------------------------------------------------------

def test_no_section_is_not_an_error() -> None:
    """Postać bez barków po prostu milczy - jak pusta komórka destynacji w rutynie."""
    path = _write("---\naliases:\n  - X\n---\n\n## 000\n\n* Cześć\n")

    assert parse_character_barks(path) == []


def test_a_missing_file_is_not_an_error() -> None:
    assert parse_character_barks(Path("/nie/ma/takiego/pliku.md")) == []


def test_bullets_under_the_section_are_read_in_order() -> None:
    path = _write(
        "## Tło historyczne\n\nProza.\n\n"
        "## Barki\n\n"
        "- Kufle same się nie umyją.\n"
        '- [time_of_day("morning")] Tylko ja i myszy.\n'
        "- [sentiment > 60] Mój ulubiony klient!\n"
    )

    barks = parse_character_barks(path)

    assert [b.text for b in barks] == [
        "Kufle same się nie umyją.",
        "Tylko ja i myszy.",
        "Mój ulubiony klient!",
    ]
    assert [b.condition for b in barks] == [None, 'time_of_day("morning")', "sentiment > 60"]


def test_the_section_ends_at_the_next_heading() -> None:
    """Sekcja pod `## Barki` nie może zjeść dialogu, który stoi niżej."""
    path = _write(
        "## Barki\n\n- Jeden.\n\n## 000\n\n* To jest węzeł dialogu, nie bark\n"
    )

    assert [b.text for b in parse_character_barks(path)] == ["Jeden."]


def test_prose_inside_the_section_is_ignored() -> None:
    path = _write("## Barki\n\nNotka dla autora, nie do gry.\n\n- Jeden.\n")

    assert [b.text for b in parse_character_barks(path)] == ["Jeden."]


def test_the_english_heading_is_accepted_too() -> None:
    """Kopia EN może zostać przy nagłówku PL albo dostać swój - oba działają."""
    assert parse_character_barks(_write("## Barks\n\n- One.\n"))
    assert parse_character_barks(_write("## Barki\n\n- Jeden.\n"))


def test_both_bullet_markers_work() -> None:
    path = _write("## Barki\n\n- Kreska.\n* Gwiazdka.\n")

    assert [b.text for b in parse_character_barks(path)] == ["Kreska.", "Gwiazdka."]


# ---------------------------------------------------------------------------
# Głośne odmowy (D4)
# ---------------------------------------------------------------------------

def test_a_too_long_bark_is_a_hard_error_with_a_line_number() -> None:
    """Autor ma się dowiedzieć przy imporcie, a nie zobaczyć obcięty żart w grze."""
    long_text = "słowo " * 30
    path = _write(f"## Barki\n\n- Krótki.\n- {long_text}\n")

    message = _fails(parse_character_barks, path)

    assert str(BARK_MAX_LINES) in message, message
    assert ":4:" in message, f"komunikat nie wskazuje linii: {message}"


def test_an_unbreakable_run_is_refused() -> None:
    """Jedno bardzo długie słowo nie zawinie się na spacji - i też nie zmieści."""
    path = _write(f"## Barki\n\n- {'x' * (BARK_LINE_CHARS + 5)}\n")

    assert "unbreakable" in _fails(parse_character_barks, path)


def test_a_bark_condition_is_validated_in_the_bark_scope() -> None:
    """`selected()` jest legalne w dialogu i nielegalne w barku - importer to widzi."""
    path = _write('## Barki\n\n- [selected("OPT")] Nie tutaj.\n')

    message = _fails(parse_character_barks, path)

    assert "selected" in message, message


def test_a_typo_in_a_predicate_name_is_refused() -> None:
    path = _write('## Barki\n\n- [time_of_dya("morning")] Literówka.\n')

    assert "time_of_dya" in _fails(parse_character_barks, path)


def test_markup_does_not_count_towards_the_length() -> None:
    """Tagi RichText i `:emote:` nie zajmują pikseli, więc nie zajmują też znaków.

    Bez tego opakowanie krótkiego tekstu w `[shadow]...[/shadow]` wywalałoby
    import za przekroczenie limitu, którego gracz w ogóle by nie zobaczył.
    """
    path = _write("## Barki\n\n- Krótko [shadow]i grubo[/shadow] :happy:\n")

    assert [b.text for b in parse_character_barks(path)] == [
        "Krótko [shadow]i grubo[/shadow] :happy:"
    ]


def test_a_leading_bracket_is_always_read_as_a_condition() -> None:
    """Świadoma, udokumentowana granica: nawias NA POCZĄTKU to warunek, nie tag.

    Alternatywą byłoby zgadywanie („czy to wygląda na warunek?"), a wtedy
    literówka w warunku po cichu stawałaby się tekstem - czyli dokładnie ten
    cichy `False`, przed którym cały ten import broni. Bark zaczynający się od
    tagu trzeba przestawić tak, żeby zaczynał się od słowa; błąd jest głośny
    i wskazuje linię.
    """
    path = _write("## Barki\n\n- [shadow]Grubo[/shadow] od razu na starcie.\n")

    message = _fails(parse_character_barks, path)

    assert "shadow" in message, message
    assert ":3:" in message, f"komunikat nie wskazuje linii: {message}"


# ---------------------------------------------------------------------------
# Wspólne pule
# ---------------------------------------------------------------------------

def test_a_pool_heading_is_the_key_literally() -> None:
    path = _write(
        "# Barki\n\nWstęp.\n\n"
        "## VILLAGERS\n\nProza dla autora.\n\n"
        '- [time_of_day("morning")] Dzień dobry.\n'
        '- [activity("stand")] Robota sama się nie zrobi.\n\n'
        "## FARM_ANIMALS\n\n- Muuu.\n- Mu?\n"
    )

    pools = parse_bark_pools(path)

    assert sorted(pools) == ["FARM_ANIMALS", "VILLAGERS"]
    assert [b.text for b in pools["FARM_ANIMALS"]] == ["Muuu.", "Mu?"]
    assert len(pools["VILLAGERS"]) == 2


def test_a_pool_heading_must_be_an_entity_key() -> None:
    """Po C02 klucz encji to SCREAMING_SNAKE - bez spacji i bez polskich znaków."""
    assert "Mieszkańcy wsi" in _fails(parse_bark_pools, _write("## Mieszkańcy wsi\n\n- Cześć.\n"))
    assert "villagers" in _fails(parse_bark_pools, _write("## villagers\n\n- Cześć.\n"))


def test_a_duplicate_pool_is_refused() -> None:
    path = _write("## VILLAGERS\n\n- Raz.\n\n## VILLAGERS\n\n- Dwa.\n")

    assert "duplicate" in _fails(parse_bark_pools, path)


def test_a_missing_pool_file_yields_no_pools() -> None:
    assert parse_bark_pools(Path("/nie/ma/Barki.md")) == {}


def test_a_pool_file_with_no_sections_yields_no_pools() -> None:
    """Stan wyjściowy repo: plik jest, pul nie ma. Gra wygląda dokładnie jak dziś."""
    assert parse_bark_pools(_write("# Barki\n\nSama proza, żadnej puli.\n")) == {}


# ---------------------------------------------------------------------------
# Co wychodzi do configu
# ---------------------------------------------------------------------------

def test_emitted_keys_and_entries_have_the_documented_shape() -> None:
    pl = parse_character_barks(_write(
        "## Barki\n\n- Bez warunku.\n- [sentiment > 60] Z warunkiem.\n"
    ))
    en = parse_character_barks(_write("## Barks\n\n- No condition.\n- With one.\n"))

    messages, entries = _emit_barks("BARMAN_ABSINTHRAYNER", pl, en, source="x")

    assert entries == [
        {"msg": f"{BARK_MESSAGE_PREFIX}BARMAN_ABSINTHRAYNER.001", "condition": "True"},
        {"msg": f"{BARK_MESSAGE_PREFIX}BARMAN_ABSINTHRAYNER.002", "condition": "sentiment > 60"},
    ]
    assert messages["PL"][entries[1]["msg"]] == "Z warunkiem."
    assert messages["EN"][entries[1]["msg"]] == "With one."


def test_conditions_come_from_pl_only() -> None:
    """PL jest źródłem prawdy dla zachowania; EN dostarcza wyłącznie tłumaczenie."""
    pl = parse_character_barks(_write('## Barki\n\n- [time_of_day("night")] W nocy.\n'))
    en = parse_character_barks(_write("## Barks\n\n- At night.\n"))

    _messages, entries = _emit_barks("X", pl, en, source="x")

    assert entries[0]["condition"] == 'time_of_day("night")'


def test_a_count_mismatch_between_pl_and_en_is_refused() -> None:
    """Inaczej dwa pliki po cichu opisują różne zachowanie - jak przy węzłach dialogu."""
    pl = parse_character_barks(_write("## Barki\n\n- Raz.\n- Dwa.\n"))
    en = parse_character_barks(_write("## Barks\n\n- One.\n"))

    assert "mismatch" in _fails(lambda: _emit_barks("X", pl, en, source="x"))


def test_a_missing_en_section_falls_back_to_pl() -> None:
    """Brak tłumaczenia nie może wyłączyć barka - gracz zobaczy tekst PL."""
    pl = parse_character_barks(_write("## Barki\n\n- Raz.\n"))

    messages, entries = _emit_barks("X", pl, [], source="x")

    assert messages["EN"][entries[0]["msg"]] == "Raz."


# ---------------------------------------------------------------------------
# Zawijanie - wspólne z BarkSprite
# ---------------------------------------------------------------------------

def test_wrap_breaks_at_spaces() -> None:
    lines = wrap_bark("Kufle same sie nie umyja, a klienci nie poczekaja", 20)

    assert all(len(line) <= 20 for line in lines), lines
    assert " ".join(lines) == "Kufle same sie nie umyja, a klienci nie poczekaja"


def test_wrap_and_the_importer_agree_on_what_fits() -> None:
    """„Mieści się" musi znaczyć to samo w imporcie i przy rysowaniu."""
    fits = "Kufle same sie nie umyja."

    assert len(wrap_bark(fits)) <= BARK_MAX_LINES
    assert parse_character_barks(_write(f"## Barki\n\n- {fits}\n"))


if __name__ == "__main__":
    tests = [
        ("brak sekcji nie jest błędem", test_no_section_is_not_an_error),
        ("brak pliku nie jest błędem", test_a_missing_file_is_not_an_error),
        ("wypunktowania czytane w kolejności", test_bullets_under_the_section_are_read_in_order),
        ("sekcja kończy się na następnym nagłówku", test_the_section_ends_at_the_next_heading),
        ("proza w sekcji jest ignorowana", test_prose_inside_the_section_is_ignored),
        ("nagłówek EN też działa", test_the_english_heading_is_accepted_too),
        ("oba znaczniki wypunktowania działają", test_both_bullet_markers_work),
        ("za długi bark to twardy błąd z linią", test_a_too_long_bark_is_a_hard_error_with_a_line_number),
        ("niełamliwy ciąg odrzucony", test_an_unbreakable_run_is_refused),
        ("warunek walidowany w zakresie bark", test_a_bark_condition_is_validated_in_the_bark_scope),
        ("literówka w predykacie odrzucona", test_a_typo_in_a_predicate_name_is_refused),
        ("markup nie liczy się do długości", test_markup_does_not_count_towards_the_length),
        ("nawias na początku to zawsze warunek", test_a_leading_bracket_is_always_read_as_a_condition),
        ("nagłówek puli jest kluczem dosłownie", test_a_pool_heading_is_the_key_literally),
        ("nagłówek puli musi być kluczem encji", test_a_pool_heading_must_be_an_entity_key),
        ("zduplikowana pula odrzucona", test_a_duplicate_pool_is_refused),
        ("brak pliku pul = brak pul", test_a_missing_pool_file_yields_no_pools),
        ("plik bez sekcji = brak pul", test_a_pool_file_with_no_sections_yields_no_pools),
        ("kształt kluczy i wpisów", test_emitted_keys_and_entries_have_the_documented_shape),
        ("warunki pochodzą tylko z PL", test_conditions_come_from_pl_only),
        ("rozjazd liczby PL/EN odrzucony", test_a_count_mismatch_between_pl_and_en_is_refused),
        ("brak EN spada na PL", test_a_missing_en_section_falls_back_to_pl),
        ("zawijanie na spacjach", test_wrap_breaks_at_spaces),
        ("import i rysowanie zgadzają się co do limitu", test_wrap_and_the_importer_agree_on_what_fits),
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
