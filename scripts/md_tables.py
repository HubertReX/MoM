"""Wyrównywanie tabel Markdown - wspólne dla generatorów notatek w ``doc/``.

Obsidian (Linter / edytor tabel) sam justuje tabele spacjami w chwili otwarcia
pliku. Generowana notatka, która tego nie robi, zmienia się więc **od samego
zajrzenia do niej** i ląduje w ``git diff`` jako ręczna edycja pliku, którego
ręcznie edytować nie wolno. Generator, który od razu pisze wyrównaną tabelę,
zamyka tę pętlę.

Szerokość liczona jest w kolumnach terminala (emoji i znaki CJK zajmują dwie),
minimum 3 znaki na kolumnę - tak samo jak robi to skill ``md-table-format``.
"""

from __future__ import annotations

from unicodedata import category, east_asian_width

_ZERO_WIDTH_CATEGORIES = {"Mn", "Me", "Cf"}
_ZERO_WIDTH_CODEPOINTS = frozenset(
    {0xAD, 0x34F, 0x61C, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2028, 0x2029,
     0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2060, 0x2061, 0x2062, 0x2063,
     0x2064, 0xFE0F, 0xFE0E, 0xFEFF}
)
_MIN_WIDTH = 3


def display_width(text: str) -> int:
    """Szerokość tekstu w kolumnach - to, co widać, nie to, co liczy ``len()``."""
    total = 0
    for char in text:
        code = ord(char)
        if code < 32 and code != 9:
            continue
        if code in _ZERO_WIDTH_CODEPOINTS or category(char) in _ZERO_WIDTH_CATEGORIES:
            continue
        total += 2 if east_asian_width(char) in ("W", "F") else 1
    return total


def table(header: list[str], rows: list[list[str]]) -> str:
    """Tabela Markdown z kolumnami dopełnionymi spacjami (wszystko do lewej)."""
    widths = [max(_MIN_WIDTH, display_width(cell)) for cell in header]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], display_width(cell))

    def line(cells: list[str]) -> str:
        padded = (cell + " " * (widths[i] - display_width(cell)) for i, cell in enumerate(cells))
        return "| " + " | ".join(padded) + " |"

    out = [line(header), "| " + " | ".join("-" * width for width in widths) + " |"]
    out.extend(line(row) for row in rows)
    return "\n".join(out)


__all__ = ["display_width", "table"]
