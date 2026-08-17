#!/usr/bin/env python3
"""Notatki przedmiotów w Obsidianie <-> ``items.csv`` (narzędzie build-time).

Trzeci importer tego samego kształtu, co ``dialog/markdown_importer.py``
i ``quest/markdown_importer.py``: vault jest źródłem prawdy, plik konfiguracyjny
artefaktem. Powód, dla którego przedmioty w ogóle dostały notatki, jest ten sam,
co przy postaciach i misjach - **żeby dało się do nich linkować**::

    **Test**: `has_item(`[[Łza Syrenki]]`)`
    * [[#012]] 1[`has_item(`[[Pióro Feniksa]]`)`]😐: Mam wszystko, o co prosiłaś.

Bez notatki taki link nie miał do czego prowadzić, a `"MERMAIDS_TEAR"` w warunku
było napisem, którego graf Obsidiana nie widzi.

Układ (jedna notatka = jeden przedmiot)::

    doc/PL/Przedmioty/Łza Syrenki.md    <- źródło prawdy, wszystkie kolumny
    doc/EN/Items/Mermaid's tear.md      <- sama nazwa angielska

**Wszystkie kolumny są properties notatki PL**, łącznie z ``key`` i obiema
nazwami. Klucz nie jest aliasem-UPPER_SNAKE jak u postaci, bo przedmioty mają
klucze pisane małymi literami (`golden_key`, `life_pot`) - pole ``key:`` mówi to
wprost i nie da się go pomylić z nazwą. Puste zostają puste: pusta komórka w CSV
znaczy „weź domyślne z modelu" i notatka mówi to samo.

Nazwa pliku jest **nazwą wyświetlaną** - po to, żeby ``[[Łza Syrenki]]`` czytało
się jak zdanie - ale danymi nie jest: nazwy jadą do CSV z properties. To nie jest
podwójny zapis dla ozdoby. Dwa przedmioty potrafią mieć tę samą nazwę wyświetlaną
(dziś `club` i `hammer` to oba „War hammer"), a dwa pliki o tej samej nazwie
w jednym katalogu być nie mogą; taka notatka dostaje więc sufiks ``(klucz)``
i ostrzeżenie, zamiast po cichu nadpisać sąsiada albo zmienić autorowi treść gry.

Notatka EN niesie sam klucz i link do PL - ``name_EN`` czyta się z notatki PL,
bo źródłem prawdy jest PL (ta sama decyzja D2, co przy dialogach i questach).

Kierunki::

    just import-items            # notatki -> items.csv -> config.json
    just import-items --export   # items.csv -> notatki (pierwsze zasianie, regeneracja)

Eksport **nie nadpisuje treści notatki** poza frontmatterem: proza pod nagłówkiem
jest dla autora i przeżywa regenerację.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from dialog.vault_links import note_key, parse_frontmatter  # noqa: E402
from enums import ItemTypeEnum  # noqa: E402

DEFAULT_CSV = _PROJECT_ROOT / "config_model" / "items.csv"
DEFAULT_SRC = _PROJECT_ROOT.parent / "doc"

#: Katalog notatek per język. Nazwa pliku = nazwa wyświetlana w tym języku.
LANG_SUBDIRS: dict[str, str] = {"PL": "PL/Przedmioty", "EN": "EN/Items"}

#: Kolumny `items.csv`, w kolejności, w jakiej stoją w pliku.
COLUMNS: tuple[str, ...] = (
    "key", "name_EN", "name_PL", "type", "value", "weight",
    "damage", "cooldown_time", "health_impact",
)

#: Kolumny zapisane jako properties notatki PL - czyli wszystkie.
PROPERTY_COLUMNS: tuple[str, ...] = COLUMNS

#: Jak sprawdzić wartość kolumny. Pusta komórka zawsze przechodzi - znaczy
#: „domyślne z modelu", nie „zapomniałem".
_NUMERIC: dict[str, type] = {
    "value": int, "damage": int, "health_impact": int,
    "weight": float, "cooldown_time": float,
}

DELIMITER = ";"


class ItemImportError(ValueError):
    """Notatka przedmiotu jest zepsuta. Niesie ``file``, żeby autor wiedział którą."""

    def __init__(self, message: str, *, file: str = "") -> None:
        self.file = file
        super().__init__(f"{file}: {message}" if file else message)


# ---------------------------------------------------------------------------
# Odczyt
# ---------------------------------------------------------------------------


def read_csv(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=DELIMITER))


def _lang_dir(src_dir: Path, lang: str) -> Path:
    return src_dir / LANG_SUBDIRS[lang]


def read_notes(src_dir: Path, lang: str) -> dict[str, tuple[Path, dict[str, str]]]:
    """``{klucz: (ścieżka, właściwości)}`` dla wszystkich notatek jednego języka."""
    directory = _lang_dir(src_dir, lang)
    if not directory.exists():
        return {}

    notes: dict[str, tuple[Path, dict[str, str]]] = {}
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        key = note_key(text)
        if not key:
            raise ItemImportError(
                "no item key in the frontmatter (expected a 'key:' field with the "
                "key from items.csv, e.g. 'key: MERMAIDS_TEAR')",
                file=str(path),
            )
        if key in notes:
            raise ItemImportError(
                f"duplicate item key {key!r} (also in {notes[key][0].name})", file=str(path)
            )
        notes[key] = (path, parse_frontmatter(text))
    return notes


def _validate(key: str, fields: dict[str, str], path: Path) -> None:
    """Co da się sprawdzić bez modelu: typ z enuma i liczby, które są liczbami.

    Reszta należy do Pydantic w `import-entities` - ale literówka w `type` albo
    `value: dużo` powinna zatrzymać autora tutaj, przy notatce, którą właśnie
    pisze, a nie dwa kroki dalej przy walidacji całego configu.
    """
    item_type = fields.get("type", "")
    if not item_type:
        raise ItemImportError(f"item {key!r} has no 'type:' property", file=str(path))
    if item_type not in {member.value for member in ItemTypeEnum}:
        raise ItemImportError(
            f"item {key!r} has type {item_type!r}; expected one of "
            f"{', '.join(sorted(member.value for member in ItemTypeEnum))}",
            file=str(path),
        )

    for column, caster in _NUMERIC.items():
        raw = fields.get(column, "")
        if not raw:
            continue
        try:
            caster(raw)
        except ValueError:
            raise ItemImportError(
                f"item {key!r} has {column}={raw!r}, which is not a "
                f"{'whole number' if caster is int else 'number'}",
                file=str(path),
            ) from None


def build_rows(src_dir: Path) -> list[dict[str, str]]:
    """Notatki PL -> wiersze `items.csv`, posortowane tak jak plik CSV.

    Notatka EN nie wnosi danych - istnieje po to, żeby dało się linkować do
    przedmiotu z angielskich dialogów. Jej brak jest więc ostrzeżeniem, nie
    błędem: przedmiot bez tłumaczenia ma dalej działać w grze.
    """
    pl_notes = read_notes(src_dir, "PL")
    en_notes = read_notes(src_dir, "EN")
    if not pl_notes:
        raise ItemImportError(
            f"no item notes found in {_lang_dir(src_dir, 'PL')}",
            file=str(_lang_dir(src_dir, "PL")),
        )

    rows: list[dict[str, str]] = []
    for key in sorted(pl_notes, key=_csv_sort_key):
        path, fields = pl_notes[key]
        _validate(key, fields, path)
        _warn_on_renamed_file(key, fields, path)
        if key not in en_notes:
            print(f"{path}: warning: no EN note for {key!r}", file=sys.stderr)
        rows.append({column: fields.get(column, "") for column in COLUMNS} | {"key": key})

    for key, (path, _) in sorted(en_notes.items()):
        if key not in pl_notes:
            print(
                f"{path}: warning: EN note for {key!r} has no PL counterpart and is ignored "
                f"(PL is the source of truth)",
                file=sys.stderr,
            )
    return rows


def _warn_on_renamed_file(key: str, fields: dict[str, str], path: Path) -> None:
    """Nazwa pliku rozjechana z ``name_PL`` - właściwość wygrywa, ale głośno.

    Zmiana nazwy notatki w Obsidianie jest jednym kliknięciem i nie rusza
    frontmatteru, więc bez tego ostrzeżenia przedmiot nazywałby się w grze inaczej
    niż w vaulcie i nikt by tego nie zauważył.
    """
    name = fields.get("name_PL", "")
    stem = path.stem.removesuffix(f" ({key})")
    if name and stem != name:
        print(
            f"{path}: warning: file is named {stem!r} but name_PL is {name!r}; "
            f"the property wins - rename one of them",
            file=sys.stderr,
        )


def _csv_sort_key(key: str) -> tuple[int, str]:
    """UPPER_SNAKE first, then the lowercase keys - the order `items.csv` already has."""
    return (0, key) if key[:1].isupper() else (1, key)


# ---------------------------------------------------------------------------
# Zapis
# ---------------------------------------------------------------------------


def write_csv(rows: list[dict[str, str]], csv_path: Path) -> bool:
    """Zapisz `items.csv`. Zwraca ``True``, gdy plik faktycznie się zmienił."""
    lines = [DELIMITER.join(COLUMNS)]
    lines.extend(DELIMITER.join(row.get(column, "") for column in COLUMNS) for row in rows)
    text = "\n".join(lines) + "\n"

    if csv_path.exists() and csv_path.read_text(encoding="utf-8") == text:
        return False
    csv_path.write_text(text, encoding="utf-8")
    return True


def _frontmatter(key: str, row: dict[str, str], lang: str, other_name: str) -> str:
    """Frontmatter notatki - kolumny jako properties (PL) i alias do linkowania."""
    other_lang = "EN" if lang == "PL" else "PL"
    columns = PROPERTY_COLUMNS if lang == "PL" else ("key",)
    lines = ["---"]
    lines.extend(f"{column}: {row.get(column, '')}".rstrip() for column in columns)
    lines.extend(("aliases:", f"  - {key}"))
    if other_name:
        lines.append(f'{other_lang}: "[[{other_name}]]"')
    lines.append("---")
    return "\n".join(lines)


def _note_names(rows: list[dict[str, str]]) -> dict[tuple[str, str], str]:
    """``{(klucz, język): nazwa pliku}`` - z sufiksem ``(klucz)`` przy kolizji.

    Dwa przedmioty mogą nazywać się tak samo (to zwykle błąd w treści, ale nie
    nasz do naprawiania); dwa pliki w katalogu nie mogą. Sufiks jest tylko
    w nazwie pliku - dane w CSV zostają nietknięte.
    """
    names: dict[tuple[str, str], str] = {}
    for lang in ("PL", "EN"):
        column = f"name_{lang}"
        seen: dict[str, str] = {}
        for row in rows:
            name = row[column]
            if name in seen:
                print(
                    f"warning: {row['key']!r} and {seen[name]!r} share the {lang} name "
                    f"{name!r}; the note gets a '({row['key']})' suffix",
                    file=sys.stderr,
                )
                names[(row["key"], lang)] = f"{name} ({row['key']})"
                continue
            seen[name] = row["key"]
            names[(row["key"], lang)] = name
    return names


#: Ciało nowej notatki: nagłówek i ikona z `doc/_attachements/` (`just gen-item-icons`).
#: Dataview składa nazwę pliku z klucza, więc nie trzeba jej wpisywać ręcznie.
ICON_LINE = '`= "![[item_" + this.key + ".png|64]]"`'


def _new_body(name: str) -> str:
    return f"# {name}\n\n{ICON_LINE}\n"


def _split_note(path: Path) -> str:
    """Treść notatki pod frontmatterem, albo ``""`` dla nowej notatki."""
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return text
    return "\n".join(lines[end + 1:]).lstrip("\n")


def export_notes(csv_path: Path, src_dir: Path) -> tuple[int, int]:
    """`items.csv` -> notatki. Zwraca ``(zapisane, bez zmian)``.

    Proza pod frontmatterem przeżywa: eksport przepisuje wyłącznie frontmatter,
    więc opis przedmiotu napisany przez autora nie ginie przy regeneracji.
    """
    rows = read_csv(csv_path)
    note_names = _note_names(rows)
    written = unchanged = 0

    for lang in ("PL", "EN"):
        directory = _lang_dir(src_dir, lang)
        directory.mkdir(parents=True, exist_ok=True)

    for row in rows:
        key = row["key"]
        for lang in ("PL", "EN"):
            path = _lang_dir(src_dir, lang) / f"{note_names[(key, lang)]}.md"
            other = note_names[(key, "EN" if lang == "PL" else "PL")]
            body = _split_note(path) or _new_body(row[f"name_{lang}"])
            text = f"{_frontmatter(key, row, lang, other)}\n{body}"
            if not text.endswith("\n"):
                text += "\n"
            if path.exists() and path.read_text(encoding="utf-8") == text:
                unchanged += 1
                continue
            path.write_text(text, encoding="utf-8")
            written += 1
    return written, unchanged


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--export", action="store_true",
        help="go the other way: items.csv -> notes (first seeding, regeneration)",
    )
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="vault root (doc/)")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="items.csv")
    args = parser.parse_args(argv)

    if args.export:
        written, unchanged = export_notes(args.csv, args.src)
        print(f"Wrote {written} item note(s), {unchanged} unchanged  ->  {args.src}")
        return 0

    try:
        rows = build_rows(args.src)
    except ItemImportError as error:
        print(f"Item import failed: {error}", file=sys.stderr)
        print("items.csv left untouched.", file=sys.stderr)
        return 1

    before = {row["key"] for row in read_csv(args.csv)} if args.csv.exists() else set()
    after = {row["key"] for row in rows}
    for key in sorted(before - after):
        print(f"warning: {key!r} lost its note and is gone from items.csv", file=sys.stderr)
    for key in sorted(after - before):
        print(f"New item: {key}")

    changed = write_csv(rows, args.csv)
    print(f"Imported {len(rows)} item(s)  ->  {args.csv}" if changed
          else f"{len(rows)} item(s), items.csv already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "COLUMNS",
    "ItemImportError",
    "PROPERTY_COLUMNS",
    "build_rows",
    "export_notes",
    "read_notes",
    "write_csv",
]
