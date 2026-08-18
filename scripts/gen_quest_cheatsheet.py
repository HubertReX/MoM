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
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from dialog.conditions import (  # noqa: E402
    _COMPARE_OPS,
    _NUMERIC_PREDICATES,
    _QUEST_PREDICATES,
    _VALUE_NAMES_BY_SCOPE,
    ConditionScope,
)
from dialog.vault_links import KIND_BY_SUBDIR  # noqa: E402
from md_tables import table  # noqa: E402
from quest.entities import CompletionMode, QuestRewardCategory  # noqa: E402
from quest.markdown_importer import (  # noqa: E402
    _FIELD_ALIASES,
    _MACHINE_FIELDS,
    _REWARD_CATEGORIES,
)
from settings import MAX_HOTBAR_ITEMS_LIMIT  # noqa: E402
from ui.text.markup import TAG_STYLES  # noqa: E402

DEFAULT_OUT = _REPO_ROOT / "doc" / "quest-cheatsheet.md"

# Które pola są obowiązkowe - źródło prawdy: _validate_parsed (Sukces, Completion
# oraz proza opisu) i _validate_completion (Test tylko gdy completion: test).
# Reszta jest opcjonalna. Tytułu tu nie ma: to nagłówek `# H1`, nie pole.
_FIELD_REQUIRED: dict[str, str] = {
    "success": "tak",
    "completion": "tak",
    "test": "gdy `completion: test`",
    "requires": "nie",
    "progress": "nie",
    "reward": "nie",
}

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

# (znaczenie, przykład). Sam zapis - czasownik i kształt argumentów - bierze się
# z `_REWARD_CATEGORIES` importera, więc dopisanie kategorii bez opisu wywala
# generator, a nie ściągawkę.
_REWARD_DOC: dict[QuestRewardCategory, tuple[str, str]] = {
    QuestRewardCategory.money: ("złoto", "`add_money(50)`"),
    QuestRewardCategory.items: (
        "przedmioty - pierwszy argument to **krotność każdego** z nich",
        "`add_n_items(2,`[[Łza Syrenki]]`,`[[Pióro Feniksa]]`)`",
    ),
    QuestRewardCategory.health: ("leczy bieżące HP", "`restore_health(20)`"),
    QuestRewardCategory.max_health: (
        "podnosi max HP **i bieżące o tyle samo**", "`raise_max_health(20)`"
    ),
    QuestRewardCategory.damage: (
        "zwiększa obrażenia zadawane przez gracza", "`raise_damage(5)`"
    ),
    QuestRewardCategory.max_items: (
        f"sloty w pasku (limit `MAX_HOTBAR_ITEMS_LIMIT={MAX_HOTBAR_ITEMS_LIMIT}`)",
        "`raise_max_items(7)`",
    ),
    QuestRewardCategory.sentiment: (
        "sympatia NPC - **wymaga adresata**, bo quest nie ma bieżącej postaci",
        "`shift_sentiment_of(`[[Barman Absyntnent]]`,10)`",
    ),
}

# Kształt argumentów per czasownik - jedyne, czego nie widać w mapowaniu importera.
_REWARD_SHAPE: dict[str, str] = {
    "add_n_items": "add_n_items(nn, ITEM, …)",
    "shift_sentiment_of": "shift_sentiment_of(NPC, nn)",
}

_COMPLETION_DOC: dict[CompletionMode, str] = {
    CompletionMode.test: "zamyka się sama, gdy `Test:` staje się prawdą",
    CompletionMode.all_subquests: "parasol - zamyka się, gdy zamkną się wszystkie jej podrzędne kroki",
    CompletionMode.manual: "zamyka ją **wyłącznie kod gry** (`mark_done`)",
}

_OP_DOC: dict[str, str] = {
    "Eq": "==", "NotEq": "!=", "Lt": "<", "LtE": "<=",
    "Gt": ">", "GtE": ">=", "In": "in", "NotIn": "not in",
}


def _code(text: str) -> str:
    """Tekst w backquote'ach, bezpieczny dla Dataview.

    Dataview czyta `` `= cokolwiek` `` jako **inline query** i na `` `==` ``
    wywala się błędem parsera zamiast pokazać operator. Spacja po otwierającym
    backquote nic nie zmienia wizualnie, a wyłącza to rozpoznanie.
    """
    return f"` {text}`" if text.startswith("=") else f"`{text}`"


def _fields_table() -> str:
    """Pola, ich pisownie PL/EN, obowiązkowość i skąd są czytane (D2)."""
    by_canonical: dict[str, list[str]] = {}
    for spelling, canonical in _FIELD_ALIASES.items():
        by_canonical.setdefault(canonical, []).append(spelling)

    rows = []
    for canonical, spellings in by_canonical.items():
        names = ", ".join(f"`{s}`" for s in sorted(spellings))
        required = _FIELD_REQUIRED.get(canonical, "nie")
        source = "**tylko PL**" if canonical in _MACHINE_FIELDS else "PL i EN"
        rows.append([f"`{canonical}`", names, required, source])
    return table(["Pole", "Można też napisać", "Obowiązkowe", "Skąd czytane"], rows)


def _completion_table() -> str:
    return table(
        ["Wartość", "Znaczenie"],
        [[f"`{mode.value}`", _COMPLETION_DOC[mode]] for mode in CompletionMode],
    )


def _predicates_table() -> str:
    rows = []
    for name in sorted(_QUEST_PREDICATES):
        example = _PREDICATE_EXAMPLE.get(name, f"{name}(...)")
        rows.append([f"`{example}`", _PREDICATE_DOC.get(name, "")])
    return table(["Wywołanie", "Znaczenie"], rows)


def _rewards_table() -> str:
    """Czasownik -> kategoria: prosto z mapowania, którym parsuje importer."""
    verb_of = {category: verb for verb, category in _REWARD_CATEGORIES.items()}
    rows = []
    for category in QuestRewardCategory:
        verb = verb_of[category.value]
        doc, example = _REWARD_DOC[category]
        rows.append([f"`{_REWARD_SHAPE.get(verb, f'{verb}(nn)')}`", doc, example])
    return table(["Zapis", "Znaczenie", "Przykład"], rows)


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

    rows = [
        [label, ", ".join(f"`[{n}]`" for n in names)]
        for label, names in groups.items()
        if names
    ]
    rows.append(["link", "`[link https://...]tekst[/link]`"])
    return table(["Rodzaj", "Znaczniki"], rows)


def _arity_note() -> str:
    low, _high = _QUEST_PREDICATES["visited"]
    return (
        f"`visited()` w queście wymaga **{low} argumentów** (`NPC`, `NODE`), inaczej niż "
        f"w dialogu, gdzie postać wynika z kontekstu rozmowy."
    )


def _numeric_predicates_note() -> str:
    """Które predykaty zwracają liczbę - z tego, co uznaje `validate_number`."""
    names = ", ".join(f"`{name}()`" for name in sorted(_NUMERIC_PREDICATES))
    return names


def render(out_path: Path) -> str:
    values = sorted(_VALUE_NAMES_BY_SCOPE[ConditionScope.quest])
    values_line = (
        f"Gołe nazwy-wartości: {', '.join(f'`{v}`' for v in values)}."
        if values
        else "Gołych nazw-wartości nie ma - `sentiment` działa tylko w dialogu, "
        "bo quest nie ma kontekstu bieżącej postaci."
    )
    operators = " ".join(_code(_OP_DOC[op.__name__]) for op in _COMPARE_OPS if op.__name__ in _OP_DOC)
    # Znacznik encji bierze się z katalogu notatki - ta tabela czyta go stamtąd,
    # zamiast powtarzać mapowanie, które mogłoby się rozjechać.
    _KIND_EXAMPLE = {
        "char": ("[[Zielarka Zmora]]", "Zielarka Zmora"),
        "loc": ("[[Tawerna Brakująca klepka]]", "Tawerna Brakująca klepka"),
        "item": ("[[Łza Syrenki]]", "Łza Syrenki"),
    }
    entities_rows = [
        [f"`{link}`", f"`[{kind}]{shown}[/{kind}]`"]
        for kind, (link, shown) in _KIND_EXAMPLE.items()
        if kind in set(KIND_BY_SUBDIR.values())
    ]
    entities_rows.append(
        ["`[[Barman Absyntnent\\|Barmana]]`", "`[char]Barmana[/char]` - odmiana z kreski"]
    )
    entities_table = table(["W notatce", "W grze"], entities_rows)
    requires_table = table(
        ["Zapis", "Kiedy"],
        [
            ["`[[Q01_S01 Dowiedz się więcej o klątwie]]`",
             "**po nazwie notatki** - to podpowiada autouzupełnianie Obsidiana i to rysuje graf"],
            ["`[[Q01_S01_LEARN_ABOUT_CURSE]]`",
             "**po aliasie**, czyli po kluczu - alias rozwiązuje notatkę, więc link przeżyje zmianę nazwy pliku"],
            ["`Q01_S01_LEARN_ABOUT_CURSE`", "goły klucz, dalej działa"],
        ],
    )

    return f"""---
tags: [sciagawka, questy]
---

# Questy - ściągawka

> [!warning] Wygenerowane przez `scripts/gen_quest_cheatsheet.py` (`just quest-cheatsheet`).
> Nie edytuj ręcznie - wszystko poniżej jest wyprowadzone z kodu (enumy, whitelista warunków, walidatory), więc nie może rozjechać się z tym, co robi import i silnik.

> [!important] Kolejność kluczy jest kolejnością podpowiadaną graczowi
> HUD pokazuje **jeden** quest naraz - wskaźnik „co teraz?" (H01/D7). Gdy śledzony krok się zamknie, gra przechodzi do następnego: najpierw do tego, co ten krok właśnie odblokował, potem do nieukończonego rodzeństwa - a w obu przypadkach bierze **pierwszy w kolejności definicji**, czyli pierwszy po kluczu (`Q01_S01` przed `Q01_S02`). Numer w kluczu jest więc kolejnością, w jakiej gracz to zobaczy. Parasole wskaźnik pomija (to tytuł rozdziału, nie instrukcja), choć gracz może przypiąć dowolny quest ręcznie klawiszem `T` w dzienniku.

## Szablon questa

**Jeden plik = jeden quest.** Alias we frontmatterze jest **kluczem** questa, dosłownie, i musi być globalnie unikalny; nagłówek `# H1` jest jego tytułem.

**PL** (`doc/PL/Misje/Qxx_Syy <Tytuł questa>.md`) jest źródłem prawdy;
**EN** (`doc/EN/Quests/Qxx_Syy <Quest title>.md`) daje samą prozę.

```markdown
---
aliases:
  - Q01_S01_LEARN_ABOUT_CURSE
---
# Dowiedz się więcej o klątwie

Opis, który gracz zobaczy w dzienniku. Obsługuje znaczniki: [char]Kowal[/].

**Requires**: [[Q01_S00 Przełamać klątwę]]
**Completion**: `test`
**Test**: `visited(`[[Barman Absyntnent#012|Barman#012]]`)`
**Sukces**: Barman gada. Barman zawsze gada.
**Nagroda**: `restore_health(20)`

## Notatki

Cokolwiek dla autora - importer przestaje czytać na pierwszym `##`.
```

### Klucz mówi, do jakiego wątku należy quest

Klucz czyta się `Qxx_Syy_NAZWA`: `Qxx` to **wątek**, `Syy` to **krok w nim**. Krok `S00` jest parasolem wątku, a każdy inny krok tego samego `Qxx` jest jego podquestem - `parent` **nie jest nigdzie zapisywany**, tylko wyliczany z klucza. Dlatego:

- wątek bez `S00` to błąd importu (kroki nie miałyby rodzica),
- dwa `S00` w jednym wątku to też błąd,
- nazwa pliku powtarza prefiks `Qxx_Syy` po to, żeby katalog sortował się w kolejności gry.

Kolejność **między krokami** to osobna rzecz: mówi o niej `Requires`, nie numeracja.

### Notatki - to, czego gracz nie zobaczy

Wszystko od **pierwszego nagłówka `##`** w dół importer pomija. Tam trafiają uwagi autorskie, długi treści, „dlaczego tak" - proza **nad** nim należy do gracza i ląduje w dzienniku. Pole `**Coś**:` zapisane poniżej `##` nie działa; import wypisze o tym ostrzeżenie zamiast po cichu je zjeść.

## Lista pól

{_fields_table()}

**Tytuł** nie jest polem - to nagłówek `# H1` pliku.

Poza tymi polami obowiązkowa jest też **proza opisu** - akapit, który nie jest linią `Pole:`. To on trafia do dziennika jako opis questa. **Pusta linia rozdziela akapity** i przeżywa import (w dzienniku widać pustą linię); łamanie linii wewnątrz akapitu nie - zawijanie należy do panelu.

**Tylko PL** (decyzja D2): logika questa mieszka w **PL**. To samo pole napisane w **EN** jest ignorowane z ostrzeżeniem - dzięki temu plik **EN** można bezpiecznie wygenerować LLM-em: najgorsze, co zrobi, to źle napisana proza, nigdy zepsuty quest.

## Backquote i wikilinki - jak się pisze wartości

Wartość, którą czyta silnik (`Completion`, `Test`, `Postęp`, `Nagroda`), zamyka się w **backquote'ach**: w Obsidianie widać wtedy od razu, gdzie kończy się proza, a zaczyna kod. Importer je zdejmuje.

Odwołanie do postaci albo questa pisze się w środku jako **prawdziwy wikilink**, przeplatany z backquote'ami - dzięki temu jedno wyrażenie jest jednocześnie warunkiem dla silnika i krawędzią w grafie Obsidiana, po którym widać, kto od czego zależy:

```markdown
**Test**: `visited(`[[Barman Absyntnent#012|Barman#012]]`) or visited(`[[Barman Absyntnent#009|Barman#009]]`)`
```

Import rozwija linki po kluczach z frontmatteru notatki, na którą wskazują:

- `[[Notatka#kotwica]]` -> `"KLUCZ", "kotwica"` - kotwica to węzeł dialogu, więc jeden link daje **oba** argumenty `visited()`. Sufiks `-end` w nagłówku dialogu nie należy do klucza węzła i jest obcinany.
- `[[Notatka]]` -> `"KLUCZ"` - sama encja.

Link do notatki, której w vaulcie nie ma, to błąd importu z numerem linii - literówka w nazwie postaci nie ma szans dożyć do gry. Stary zapis z gołymi stringami (`visited("BARMAN_ABSINTHRAYNER", "012")`) nadal działa, ale nie rysuje się w grafie.

> [!warning] Nie zaczynaj backquote'a od znaku równości
> Zawartość backquote'a zaczynającą się od znaku równości Dataview bierze za **inline query** i zamiast operatora wypisuje w notatce błąd parsera (tak umiera zapis równości wpisany wprost). Wstaw spację po otwierającym backquote - ` ==` - wygląda tak samo, a Dataview przestaje się tym interesować.

## Requires - zależności między questami

Link do questa, który musi być ukończony, aby **odblokować** ten krok. Każdy poniższy zapis znaczy to samo:

{requires_table}

Można wymienić kilka naraz, **po przecinku**.

`Requires` to jedyne miejsce, w którym zapisuje się **kolejność kroków w wątku**: parasol bierze się z klucza, ale to, czy kroki idą po kolei, czy równolegle, wynika wyłącznie stąd.

## Completion - kiedy quest się zamyka

{_completion_table()}

Odrzucane przy imporcie (`just import-quests`):

- `all_subquests` bez kroków - nic by jej nigdy nie zamknęło (to był bug `Q01_S07` w SSiS).
- `test` bez `Test:` - nie ma czego sprawdzać.
- `manual` **z** `Test:` - test nigdy by nie wystartował.

> [!tip] `manual` to obietnica do dotrzymania w kodzie
> Nic w configu nie zamknie questa `manual`. Jeśli nikt nie woła `mark_done`, wątek zostaje otwarty na zawsze. `just quest-graph` wypisuje takie questy wprost.

## Test - kiedy quest jest ukończony

Mini-DSL, nie `eval()`: whitelista dopuszczalnych komend, wszystko inne to błąd importu (`just import-quests`) z numerem linii.

{_predicates_table()}

**Łączenie**: `and`, `or`, `not`, nawiasy.
**Porównania**: {operators}.

{values_line}

{_arity_note()}

## Pasek postępu - n / m

`Postęp:` rysuje **pasek postępu w dzienniku** i nic poza tym - questa nie zamyka. Ukośnik nie jest dzieleniem, tylko separatorem dla wartości *"z ilu"*:

```markdown
**Postęp**: item_count("MERMAIDS_TEAR") / 3
```

czyta się "ile **Łez syrenki** gracz ma, z **3** potrzebnych" i rysuje np.: `2 / 3`.

- **Po lewej**: coś, co zwraca **liczbę** - w praktyce {_numeric_predicates_note()}, jedyny predykat, który zwraca liczbę. Wyrażenie prawda/fałsz (`has_item`, `visited`, porównanie `>=`) jest **odrzucane przy imporcie** z numerem linii, a nie dopiero przy otwarciu dziennika. Arytmetyki (`+`, `*`) whitelista nie przepuszcza.
- **Po prawej**: liczba całkowita - oczekiwana wartość do spełnienia. Trzeba podać oba albo żadne; `Postęp:` bez licznika to błąd importu.
- Wartość bieżąca (po lewej) jest przycinana do zakresu, a ukończony quest zawsze pokazuje pełny pasek.

> [!warning] Pasek postępu to nie warunek ukończenia
> Quest z paskiem `3 / 3` **nadal się nie zamknie**, dopóki nie napiszesz `Test:`. Pasek mówi ile brakuje; `Test:` decyduje kiedy jest gotowe. Zwykle chcesz obu:
>
> ```markdown
> **Completion**: test
> **Test**: item_count("MERMAIDS_TEAR") >= 3
> **Postęp**: item_count("MERMAIDS_TEAR") / 3
> ```

Parasole (`all_subquests`) dostają pasek **za darmo**, liczony z kroków - nie dodawaj dla nich `Postęp:`.

## Nagroda - co dostanie gracz

Jedna linia `Nagroda:` per bonus dla gracza - **wszystkie są aplikowane**, nie tylko pierwsza.

{_rewards_table()}

Nagroda **daje**, a nie zabiera, więc czasowniki odbierające (`remove_money`, `lose_health`, `remove_n_items`) są tu błędem importu - te mieszkają w dialogu, gdzie NPC może coś graczowi wziąć. Ta sama gramatyka opisuje jedno i drugie: to ten sam mechanizm (`dialog/effects.py`), a nazwy czasowników są nazwami metod `ResultSink` w kodzie.

Odrzucane przy imporcie:

- nagroda o wartości `0` (albo `add_n_items` bez przedmiotu) - to kształt, który nigdy nie jest zamierzony,
- liczba ujemna przy czasowniku, który już mówi, w którą stronę idzie (`add_money(-50)`),
- `shift_sentiment(10)` bez adresata - quest nie ma bieżącej postaci, więc nie byłoby komu polubić gracza; adresata podaje `shift_sentiment_of`.

Etykiety nagród składa silnik gry - nie pisz wartości liczbowej nagrody w `Sukces:`. Dzięki temu przeważenie nagrody nie dotyka tłumaczeń.

## Encje w prozie - pisze się je linkiem

Postać, lokalizację i przedmiot pisze się w tytule, opisie i `Sukces` **wikilinkiem**; import zamienia go na znacznik, którym gra koloruje encję:

{entities_table}

Znacznik bierze się z **katalogu notatki**, więc nie trzeba go wybierać, a napis po pionowej kresce niesie odmianę. Link bez kreski pokazuje nazwę notatki w języku pliku, więc `[[Zielarka Zmora]]` w pliku EN wyświetli się jako „Potioneer Puzzlemint".

Znacznikiem wprost pisze się dalej to, co **nie ma notatki**: istoty ze wspomnień, rzeczowniki pospolite, zaimki (`[char]Ty[/char]`). Link do nieistniejącej notatki zostaje w tekście dosłownie i `just validate-world` (reguła 22) uzna to za błąd - gracz zobaczyłby surowe `[[nawiasy]]`.

## Znaczniki tekstu - MoM RichText

Działają w `Tytuł`, w prozie opisu i w `Sukces`. W grze renderują się odpowiednim stylem, a w tooltipie grafu spłaszczają się do **pogrubienia**.

Markdownowe wyróżnienia pisze się **po markdownowemu**: `**pogrubienie**` i `_kursywa_` importer sam zamienia na `[shadow]` i `[italic]` - tak samo, jak w dialogach. Znaczników wyróżnienia nie trzeba pisać ręcznie.

`**` idzie na `[shadow]`, a nie na `[bold]`, bo font pikselowy nie ma prawdziwego pogrubienia: `[bold]` to jeden dodatkowy piksel grubości kreski i w akapicie go po prostu nie widać. Wyróżnia cień.

{_tags_table()}

`[/]` zamyka **ostatni otwarty** znacznik, więc `[char]Kowal[/]` znaczy to samo co `[char]Kowal[/char]`, a `[h3][char]X[/][/]` domyka najpierw `char`, potem `h3`.

Emotki wstawia się jako `:nazwa:` - pełen arkusz z kluczami:
![[_attachements/mom-emote-sheet.png]]

## Co zrobić po edycji

```bash
just import-quests  # importuje wszystkie łańcuchy do config.json; Qxx albo pełny klucz = tylko ten jeden
just quest-graph    # generuje graf w doc/_graphs/
```

Import działa na zasadzie **wszystko albo nic**: quest, który się nie zaimportuje, to quest, którego nie ma w grze - więc `config.json` zostaje nietknięty, a błąd wskazuje plik i linię.
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
