#!/usr/bin/env python3
"""Regeneruje ściągawkę autorską questów: ``doc/quest-cheatsheet.md``.

Wszystko, co ściągawka wymienia, jest **wyprowadzone z kodu** - z tych samych
enumów, whitelist i walidatorów, których używa import i silnik. Ręcznie pisana
ściągawka rozjeżdża się przy pierwszej zmianie enuma i wtedy jest gorsza niż
żadna: kłamie z autorytetem.

Wzorzec: ``scripts/gen_dialog_doc_assets.py``.

Notatka celowo **nie leży w ``doc/PL/Misje/``** - importer globuje ten katalog,
a szablon z aliasem zostałby wzięty za prawdziwy łańcuch.

Użycie::

    just quest-cheatsheet
    .venv/bin/python scripts/gen_quest_cheatsheet.py --out /tmp/sciagawka.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "project"))

from dialog.conditions import (  # noqa: E402
    _COMPARE_OPS,
    _QUEST_PREDICATES,
    _VALUE_NAMES_BY_SCOPE,
    ConditionScope,
)
from quest.entities import CompletionMode, QuestRewardCategory  # noqa: E402
from quest.markdown_importer import _FIELD_ALIASES, _MACHINE_FIELDS  # noqa: E402
from ui.text.markup import TAG_STYLES  # noqa: E402

DEFAULT_OUT = _REPO_ROOT / "doc" / "quest-cheatsheet.md"

# Co robi każdy predykat - jedyna rzecz, której nie da się wyczytać z whitelisty.
_PREDICATE_DOC: dict[str, str] = {
    "visited": "gracz odwiedził węzeł dialogu `NODE` u postaci `NPC`",
    "has_item": "gracz ma przedmiot `ITEM` w ekwipunku",
    "item_count": "ile sztuk `ITEM` gracz ma (liczba, nie prawda/fałsz)",
    "quest_done": "quest `KEY` jest ukończony",
}

_PREDICATE_EXAMPLE: dict[str, str] = {
    "visited": 'visited("BARMAN_ABSINTHRAYNER", "012")',
    "has_item": 'has_item("MERMAIDS_TEAR")',
    "item_count": 'item_count("MERMAIDS_TEAR") >= 3',
    "quest_done": 'quest_done("Q01_S01_LEARN_ABOUT_CURSE")',
}

_REWARD_DOC: dict[QuestRewardCategory, tuple[str, str]] = {
    QuestRewardCategory.money: ("złoto", "money=50"),
    QuestRewardCategory.items: ("przedmioty (po przecinku)", "items=MERMAIDS_TEAR, PHOENIX_FEATHER"),
    QuestRewardCategory.health: ("leczy bieżące HP", "health=20"),
    QuestRewardCategory.max_health: ("podnosi max HP **i bieżące o tyle samo**", "max_health=20"),
    QuestRewardCategory.damage: ("obrażenia gracza", "damage=5"),
    QuestRewardCategory.max_items: ("sloty w pasku (limit `MAX_HOTBAR_ITEMS_LIMIT`)", "max_items=1"),
    QuestRewardCategory.sentiment: ("sympatia NPC - **wymaga `@NPC_KEY`**", "sentiment=10 @BARMAN_ABSINTHRAYNER"),
}

_COMPLETION_DOC: dict[CompletionMode, str] = {
    CompletionMode.test: "zamyka się sama, gdy `**Test**:` staje się prawdą",
    CompletionMode.all_subquests: "parasol - zamyka się, gdy zamkną się wszystkie jej kroki",
    CompletionMode.manual: "zamyka ją **wyłącznie kod gry** (`mark_done`)",
}

_OP_DOC: dict[str, str] = {
    "Eq": "==", "NotEq": "!=", "Lt": "<", "LtE": "<=",
    "Gt": ">", "GtE": ">=", "In": "in", "NotIn": "not in",
}


def _fields_table() -> str:
    """Nazwy pól, PL i EN, z zaznaczeniem które są czytane tylko z PL (D2)."""
    by_canonical: dict[str, list[str]] = {}
    for spelling, canonical in _FIELD_ALIASES.items():
        by_canonical.setdefault(canonical, []).append(spelling)

    rows = ["| Pole | Można też napisać | Skąd czytane |", "| --- | --- | --- |"]
    for canonical, spellings in by_canonical.items():
        pl_only = canonical in _MACHINE_FIELDS
        names = ", ".join(f"`{s}`" for s in sorted(spellings))
        source = "**tylko PL**" if pl_only else "PL i EN"
        rows.append(f"| `{canonical}` | {names} | {source} |")
    return "\n".join(rows)


def _completion_table() -> str:
    rows = ["| Wartość | Znaczenie |", "| --- | --- |"]
    for mode in CompletionMode:
        rows.append(f"| `{mode.value}` | {_COMPLETION_DOC[mode]} |")
    return "\n".join(rows)


def _predicates_table() -> str:
    rows = ["| Wywołanie | Znaczenie |", "| --- | --- |"]
    for name in sorted(_QUEST_PREDICATES):
        example = _PREDICATE_EXAMPLE.get(name, f"{name}(...)")
        rows.append(f"| `{example}` | {_PREDICATE_DOC.get(name, '')} |")
    return "\n".join(rows)


def _rewards_table() -> str:
    rows = ["| Kategoria | Znaczenie | Przykład |", "| --- | --- | --- |"]
    for category in QuestRewardCategory:
        doc, example = _REWARD_DOC[category]
        rows.append(f"| `{category.value}` | {doc} | `{example}` |")
    return "\n".join(rows)


def _tags_table() -> str:
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

    rows = ["| Rodzaj | Znaczniki |", "| --- | --- |"]
    for label, names in groups.items():
        if names:
            rows.append(f"| {label} | {', '.join(f'`[{n}]`' for n in names)} |")
    rows.append("| link | `[link https://...]tekst[/link]` |")
    return "\n".join(rows)


def _arity_note() -> str:
    low, high = _QUEST_PREDICATES["visited"]
    return (
        f"`visited()` w queście wymaga **{low} argumentów** (`NPC`, `NODE`), inaczej niż w dialogu, "
        f"gdzie postać wynika z rozmowy. Quest nie ma \"bieżącego NPC\", więc `visited(\"012\")` "
        f"parsowałoby się, wiecznie zwracało fałsz i cicho blokowało łańcuch."
    )


def render(out_path: Path) -> str:
    values = sorted(_VALUE_NAMES_BY_SCOPE[ConditionScope.quest])
    values_line = (
        f"Gołe nazwy-wartości: {', '.join(f'`{v}`' for v in values)}."
        if values
        else "Gołych nazw-wartości nie ma - `sentiment` działa tylko w dialogu, bo quest nie ma bieżącej postaci."
    )
    operators = " ".join(f"`{_OP_DOC[op.__name__]}`" for op in _COMPARE_OPS if op.__name__ in _OP_DOC)

    return f"""---
tags: [sciagawka, questy]
---

# Questy - ściągawka

> [!warning] Wygenerowane przez `scripts/gen_quest_cheatsheet.py` (`just quest-cheatsheet`).
> Nie edytuj ręcznie - wszystko poniżej jest wyprowadzone z kodu (enumy, whitelista
> warunków, walidatory), więc nie może rozjechać się z tym, co robi import i silnik.

## Szablon łańcucha

Jeden plik = jeden łańcuch. Nagłówek sekcji **jest** kluczem questa, dosłownie, i musi być
globalnie unikalny. Alias to **własny klucz parasola** - sekcji, której podlegają wszystkie
pozostałe w pliku.

PL (`doc/PL/Misje/<Tytuł łańcucha>.md`) jest źródłem prawdy; EN (`doc/EN/Quests/`) daje samą prozę.

```markdown
---
aliases:
  - Q01_S00_BREAK_THE_CURSE
---

# Przełamać klątwę

Proza wprowadzająca do łańcucha (opcjonalna, nie trafia do gry).

## Q01_S00_BREAK_THE_CURSE

**Tytuł**: Przełamać klątwę

Opis, który gracz zobaczy w dzienniku. Obsługuje znaczniki: [char]Kowal[/].

**Completion**: manual
**Requires**: [[Q00_S00_WHAT_IS_GOING_ON]]
**Sukces**: Klątwa zdjęta. Miecz milczy pierwszy raz od tygodni.
**Nagroda**: max_health=20
**Nagroda**: damage=5

## Q01_S01_LEARN_ABOUT_CURSE

**Tytuł**: Dowiedz się więcej o klątwie

Każda sekcja poza tą z aliasu jest krokiem parasola - `parent` bierze się z pliku.

**Completion**: test
**Test**: visited("BARMAN_ABSINTHRAYNER", "012")
**Sukces**: Barman gada. Barman zawsze gada.
```

## Pola sekcji

{_fields_table()}

**Tylko PL** (decyzja D2): logika questa mieszka w PL. To samo pole napisane w EN jest
ignorowane z ostrzeżeniem - dzięki temu plik EN można bezpiecznie wygenerować LLM-em:
najgorsze, co zrobi, to zła proza, nigdy zepsuty quest.

## Requires - linkowanie questów

Klucz to tekst po ostatnim `#`, więc każdy zapis znaczy to samo. Wybór jest kwestią
Obsidiana, nie importu:

| Zapis | Kiedy |
| --- | --- |
| `[[#Q01_S05_MEET_MADAME_SARCASMIA]]` | cel w **tym samym pliku** - jedyna forma, którą Obsidian rozwiązuje wewnątrz notatki |
| `[[Q01_S00_BREAK_THE_CURSE#Q01_S01_LEARN_ABOUT_CURSE]]` | **krok innego łańcucha** - alias rozwiązuje plik, więc link przeżyje zmianę nazwy pliku |
| `[[Q00_S00_WHAT_IS_GOING_ON]]` | **parasol innego łańcucha** - alias JEST jego kluczem, więc powtarzanie go po `#` mówiłoby to samo dwa razy |
| `Q01_S01_LEARN_ABOUT_CURSE` | goły klucz, dalej działa |

Kilka naraz: po przecinku.

## Completion

{_completion_table()}

Odrzucane przy imporcie:

- `all_subquests` bez kroków - nic by jej nigdy nie zamknęło (to był bug `Q01_S07` w SSiS).
- `test` bez `**Test**:` - nie ma czego sprawdzać.
- `manual` **z** `**Test**:` - test nigdy by nie wystartował.

> [!tip] `manual` to obietnica do dotrzymania w kodzie
> Nic w configu nie zamknie questa `manual`. Jeśli nikt nie woła `mark_done`, wątek zostaje
> otwarty na zawsze. `just quest-graph` wypisuje takie questy wprost.

## Test i Postęp - składnia

Mini-DSL, nie `eval()`: whitelista, wszystko poza nią to błąd importu z numerem linii.

{_predicates_table()}

Łączenie: `and`, `or`, `not`, nawiasy. Porównania: {operators}.

{values_line}

{_arity_note()}

`**Postęp**:` to wyrażenie **liczbowe** i licznik, po ukośniku - oba albo żadne:

```markdown
**Postęp**: item_count("MERMAIDS_TEAR") / 3
```

## Nagroda

Jedna linia `**Nagroda**:` na nagrodę - **wszystkie są aplikowane**, nie tylko pierwsza.

{_rewards_table()}

Odrzucane przy imporcie:

- nagroda o wartości `0` (albo `items=` bez przedmiotów) - to kształt, na którym SSiS cicho
  przechodził dalej; nigdy nie jest zamierzony,
- `sentiment` bez `@NPC_KEY` - quest nie ma bieżącej postaci, więc nie byłoby komu polubić gracza,
- `@NPC_KEY` przy czymkolwiek poza `sentiment`.

Etykiety nagród składa silnik z liczb - nie pisz ich w `**Sukces**:`. Dzięki temu przeważenie
nagrody nie dotyka tłumaczeń.

## Znaczniki tekstu

Działają w `**Tytuł**`, w prozie opisu i w `**Sukces**`. W grze renderują się stylem,
w tooltipie grafu spłaszczają się do pogrubienia.

{_tags_table()}

`[/]` zamyka **ostatni otwarty** znacznik, więc `[char]Kowal[/]` == `[char]Kowal[/char]`,
a `[h3][char]X[/][/]` domyka najpierw `char`, potem `h3`.

Emotki wstawia się jako `:nazwa:` - pełen arkusz z kluczami:
![[_attachements/mom-emote-sheet.png]]

## Po edycji

```bash
just import-quests          # wszystkie łańcuchy; Qxx albo pełny klucz = jeden
just quest-graph            # graf DAG do doc/_graphs/
```

Import jest **wszystko albo nic**: quest, który się nie zaimportuje, to quest, którego po cichu
nie ma w grze - więc `config.json` zostaje nietknięty, a błąd wskazuje plik i linię.
"""


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(args.out), encoding="utf-8")

    try:
        shown = args.out.relative_to(_REPO_ROOT)
    except ValueError:
        shown = args.out
    print(
        f"{len(CompletionMode)} trybów completion, {len(QuestRewardCategory)} kategorii nagród, "
        f"{len(_QUEST_PREDICATES)} predykatów, {len(TAG_STYLES)} znaczników  ->  {shown}"
    )


if __name__ == "__main__":
    main()
