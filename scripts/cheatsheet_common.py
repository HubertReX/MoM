"""Kawałki wspólne dla generowanych ściągawek autorskich w ``doc/``.

Ściągawka questów i ściągawka dialogów opisują **ten sam** mini-DSL warunków
i **te same** znaczniki RichText - to jeden system, tylko oglądany z dwóch
stron. Gdyby każdy generator trzymał własną kopię tabeli znaczników, dopisanie
znacznika poprawiałoby jedną notatkę, a drugą zostawiało kłamiącą.

Co tu **nie** trafia: wszystko, co ma sens tylko w jednym zasięgu (pola questa,
gramatyka opcji dialogu). Wspólny moduł ma być listą rzeczy naprawdę wspólnych,
a nie workiem na funkcje.
"""

from __future__ import annotations

import ast

from md_tables import table
from ui.text.markup import TAG_STYLES

# Węzeł operatora AST -> zapis, który autor wpisuje w warunku.
OP_DOC: dict[str, str] = {
    "Eq": "==", "NotEq": "!=", "Lt": "<", "LtE": "<=",
    "Gt": ">", "GtE": ">=", "In": "in", "NotIn": "not in",
}


def code(text: str) -> str:
    """Tekst w backquote'ach, bezpieczny dla Dataview.

    Dataview czyta `` `= cokolwiek` `` jako **inline query** i na `` `==` ``
    wywala się błędem parsera zamiast pokazać operator. Spacja po otwierającym
    backquote nic nie zmienia wizualnie, a wyłącza to rozpoznanie.
    """
    return f"` {text}`" if text.startswith("=") else f"`{text}`"


def operators_line(compare_ops: dict[type[ast.cmpop], object]) -> str:
    """Lista porównań, prosto z whitelisty ``conditions._COMPARE_OPS``."""
    return " ".join(
        code(OP_DOC[op.__name__]) for op in compare_ops if op.__name__ in OP_DOC
    )


def tags_table() -> str:
    """Znaczniki RichText pogrupowane po tym, co faktycznie robią ze stylem.

    Kolejność sprawdzania nie jest dowolna: `[h1]` zmienia i rozmiar, i wyrównanie,
    więc gdyby `align` szło pierwsze, nagłówki wylądowałyby wśród `[center]`.
    """
    groups: dict[str, list[str]] = {
        "kolor": [], "rozmiar / nagłówek": [], "wyróżnienie": [], "cień": [], "wyrównanie": []
    }
    for name, mutation in sorted(TAG_STYLES.items()):
        if name == "link":
            continue
        if "color" in mutation:
            groups["kolor"].append(name)
        elif "size" in mutation:
            groups["rozmiar / nagłówek"].append(name)
        elif {"bold", "italic", "underline"} & set(mutation):
            groups["wyróżnienie"].append(name)
        elif {"shadow", "shadow_color"} & set(mutation):
            groups["cień"].append(name)
        elif "align" in mutation:
            groups["wyrównanie"].append(name)

    rows = [
        [label, ", ".join(f"`[{n}]`" for n in names)]
        for label, names in groups.items()
        if names
    ]
    rows.append(["link", "`[link https://...]tekst[/link]`"])
    return table(["Rodzaj", "Znaczniki"], rows)


__all__ = ["OP_DOC", "code", "operators_line", "tags_table"]
