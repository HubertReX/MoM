#!/usr/bin/env python3
"""Notatki przedmiotów <-> `items.csv` (config_model/items_markdown.py).

Vault stał się źródłem prawdy dla przedmiotów po to, żeby dało się do nich
linkować z warunków. Ten plik pilnuje dwóch rzeczy, na których to stoi:

- **round-trip jest dokładny** - notatki wygenerowane z CSV wracają do bajt
  w bajt tego samego CSV, bo inaczej samo otwarcie narzędzia robiłoby diff
  w pliku, którego nikt nie edytował (`5.0` przepuszczone przez `float` wraca
  jako `5`),
- **błąd w notatce jest głośny** - zły `type`, `value: dużo` albo brak klucza
  zatrzymują import, zamiast dolecieć do walidacji całego configu.

Uruchamianie z katalogu projektu:
    .venv/bin/python tests/test_items_markdown.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))

from config_model.items_markdown import (
    COLUMNS,
    ItemImportError,
    build_rows,
    export_notes,
    read_notes,
    write_csv,
)
from dialog.vault_links import build_entity_index, expand_links

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_CSV = REPO_ROOT / "project" / "config_model" / "items.csv"
REAL_VAULT = REPO_ROOT / "doc"

_CSV = (
    "key;name_EN;name_PL;type;value;weight;damage;cooldown_time;health_impact\n"
    "MERMAIDS_TEAR;Mermaid's tear;Łza Syrenki;key;800;0.1;;;\n"
    "club;War hammer;Maczuga;weapon;;7.0;30;0.6;\n"
    "hammer;War hammer;Młot wojenny;weapon;70;5.0;25;0.5;\n"
    "life_pot;Life potion;Mikstura zdrowia;consumable;300;0.15;;;100\n"
)


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def _vault(root: Path) -> tuple[Path, Path]:
    """Zapisz testowy CSV i rozwiń go w notatki. Zwraca ``(csv, vault)``."""
    csv_path = root / "items.csv"
    csv_path.write_text(_CSV, encoding="utf-8")
    export_notes(csv_path, root)
    return csv_path, root


def _fails(fn) -> str:  # type: ignore[no-untyped-def]
    try:
        fn()
    except ItemImportError as error:
        return str(error)
    raise AssertionError("import przeszedł, a miał się wywalić")


# ---------------------------------------------------------------------------


def test_export_writes_one_note_per_item_per_language() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _, vault = _vault(Path(tmp))

        assert_eq(len(list((vault / "PL/Przedmioty").glob("*.md"))), 4, "cztery notatki PL")
        assert_eq(len(list((vault / "EN/Items").glob("*.md"))), 4, "i cztery EN")
        assert_true((vault / "PL/Przedmioty/Łza Syrenki.md").exists(), "nazwa pliku = nazwa PL")
        assert_true((vault / "EN/Items/Mermaid's tear.md").exists(), "i angielska po stronie EN")


def test_all_columns_are_properties() -> None:
    """„Wszystkie kolumny jako properties" - łącznie z kluczem i obiema nazwami."""
    with tempfile.TemporaryDirectory() as tmp:
        _, vault = _vault(Path(tmp))
        notes = read_notes(vault, "PL")

        _, fields = notes["life_pot"]
        for column in COLUMNS:
            assert_true(column in fields, f"kolumna {column} jest właściwością")
        assert_eq(fields["value"], "300", "wartość liczbowa")
        assert_eq(fields["health_impact"], "100", "i ta z końca wiersza")
        assert_eq(fields["damage"], "", "pusta komórka zostaje pusta")


def test_round_trip_is_byte_identical() -> None:
    """CSV -> notatki -> CSV nie może niczego przemielić.

    `weight: 7.0` przepuszczone przez `float` wróciłoby jako `7.0`, ale `value: 300`
    przez `int` już nie zawsze - dlatego właściwości jadą jako surowe napisy.
    """
    with tempfile.TemporaryDirectory() as tmp:
        csv_path, vault = _vault(Path(tmp))
        changed = write_csv(build_rows(vault), csv_path)

        assert_true(not changed, "drugi przebieg nie rusza pliku")
        assert_eq(csv_path.read_text(encoding="utf-8"), _CSV, "CSV bajt w bajt")


def test_the_real_vault_round_trips() -> None:
    """To samo na prawdziwych 39 przedmiotach - inaczej test opisuje fikcję."""
    if not (REAL_VAULT / "PL/Przedmioty").exists():
        return
    rows = build_rows(REAL_VAULT)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "items.csv"
        write_csv(rows, out)
        assert_eq(
            out.read_text(encoding="utf-8"),
            REAL_CSV.read_text(encoding="utf-8"),
            "notatki w doc/ dają dokładnie ten items.csv, który leży w repo",
        )


def test_a_shared_display_name_gets_a_suffix_not_a_lost_note() -> None:
    """`club` i `hammer` to oba „War hammer" - dwa pliki o tej nazwie być nie mogą.

    Sufiks siedzi w nazwie pliku, nie w danych: `name_EN` obu przedmiotów zostaje
    takie, jakie autor napisał, bo zmiana nazwy w grze to nie jest decyzja importera.
    """
    with tempfile.TemporaryDirectory() as tmp:
        _, vault = _vault(Path(tmp))

        assert_true((vault / "EN/Items/War hammer.md").exists(), "pierwszy bierze nazwę")
        assert_true((vault / "EN/Items/War hammer (hammer).md").exists(), "drugi z sufiksem")

        rows = {row["key"]: row for row in build_rows(vault)}
        assert_eq(rows["club"]["name_EN"], "War hammer", "dane nietknięte")
        assert_eq(rows["hammer"]["name_EN"], "War hammer", "u obu")


def test_prose_survives_a_regeneration() -> None:
    """Eksport przepisuje sam frontmatter - opis przedmiotu nie jest jego własnością."""
    with tempfile.TemporaryDirectory() as tmp:
        csv_path, vault = _vault(Path(tmp))
        note = vault / "PL/Przedmioty/Łza Syrenki.md"
        note.write_text(
            note.read_text(encoding="utf-8") + "\nPłakała nad tym godzinami.\n", encoding="utf-8"
        )

        export_notes(csv_path, vault)

        assert_true(
            "Płakała nad tym godzinami." in note.read_text(encoding="utf-8"),
            "proza przeżyła regenerację",
        )


def test_a_broken_note_stops_the_import() -> None:
    cases = [
        ("type: consumable", "type: sword", "expected one of"),
        ("value: 300", "value: dużo", "not a whole number"),
        ("weight: 0.15", "weight: ciężka", "not a number"),
        ("type: consumable\n", "", "has no 'type:'"),
    ]
    for broken_from, broken_to, needle in cases:
        with tempfile.TemporaryDirectory() as tmp:
            _, vault = _vault(Path(tmp))
            note = vault / "PL/Przedmioty/Mikstura zdrowia.md"
            text = note.read_text(encoding="utf-8")
            assert_true(broken_from in text, f"fixture ma {broken_from!r}")
            note.write_text(text.replace(broken_from, broken_to), encoding="utf-8")

            message = _fails(lambda: build_rows(vault))
            assert_true(needle in message, f"{broken_to!r}: {message!r} nie mówi {needle!r}")


def test_a_note_without_a_key_stops_the_import() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _, vault = _vault(Path(tmp))
        (vault / "PL/Przedmioty/Bez klucza.md").write_text(
            "---\ntype: gem\n---\n# Bez klucza\n", encoding="utf-8"
        )
        assert_true("no item key" in _fails(lambda: read_notes(vault, "PL")), "mówi czego brak")


def test_two_notes_with_one_key_stop_the_import() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _, vault = _vault(Path(tmp))
        (vault / "PL/Przedmioty/Kopia.md").write_text(
            "---\nkey: life_pot\ntype: consumable\n---\n# Kopia\n", encoding="utf-8"
        )
        assert_true("duplicate item key" in _fails(lambda: read_notes(vault, "PL")), "nazywa kolizję")


def test_an_item_note_is_linkable_from_a_condition() -> None:
    """Po co to wszystko było: `has_item(`[[Łza Syrenki]]`)` ma dawać klucz."""
    with tempfile.TemporaryDirectory() as tmp:
        _, vault = _vault(Path(tmp))
        index = build_entity_index(vault)

        assert_eq(
            expand_links("`has_item(`[[Łza Syrenki]]`)`", index),
            'has_item("MERMAIDS_TEAR")',
            "polska nazwa notatki -> klucz z items.csv",
        )
        assert_eq(
            expand_links("`has_item(`[[Life potion]]`)`", index),
            'has_item("life_pot")',
            "klucz pisany małymi literami też się rozwiązuje",
        )


def main() -> None:
    tests = [
        test_export_writes_one_note_per_item_per_language,
        test_all_columns_are_properties,
        test_round_trip_is_byte_identical,
        test_the_real_vault_round_trips,
        test_a_shared_display_name_gets_a_suffix_not_a_lost_note,
        test_prose_survives_a_regeneration,
        test_a_broken_note_stops_the_import,
        test_a_note_without_a_key_stops_the_import,
        test_two_notes_with_one_key_stop_the_import,
        test_an_item_note_is_linkable_from_a_condition,
    ]
    for test in tests:
        test()
        print(f"  PASS  {test.__name__}")
    print(f"\nAll {len(tests)} item note tests passed.")


if __name__ == "__main__":
    main()
