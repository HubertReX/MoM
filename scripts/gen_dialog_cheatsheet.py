#!/usr/bin/env python3
"""Regeneruje ściągawkę autorską dialogów: ``doc/dialog-cheatsheet.md``.

Bliźniak ``scripts/gen_quest_cheatsheet.py`` i z tego samego powodu: wszystko,
co ściągawka wymienia - emoji sentymentów, predykaty warunków, czasowniki
efektów, znaczniki tekstu - jest **wyprowadzone z kodu**, z tych samych tabel,
których używa import i silnik. Ręcznie pisana ściągawka rozjeżdża się przy
pierwszej zmianie tabeli i wtedy jest gorsza niż żadna: kłamie z autorytetem.

Notatka celowo **nie leży w ``doc/PL/Postacie/``** - importer globuje ten katalog
po aliasie z frontmatteru, a szablon postaci zostałby wzięty za prawdziwą postać.

Użycie::

    just gen-dialog-cheatsheet
    .venv/bin/python scripts/gen_dialog_cheatsheet.py --out /tmp/sciagawka.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "project"))
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from cheatsheet_common import operators_line, tags_table  # noqa: E402
from dialog.conditions import (  # noqa: E402
    _BARK_PREDICATES,
    _COMPARE_OPS,
    _DIALOG_PREDICATES,
    _VALUE_NAMES_BY_SCOPE,
    ConditionScope,
)
from dialog.effects import EFFECTS_BY_SCOPE, _SIGNATURES, EffectScope  # noqa: E402
from dialog.markdown_importer import (  # noqa: E402
    _EMOJI_TO_EMOTE_TAG,
    _FRONTMATTER_WEIGHT_KEYS,
    _TAG_CONVERSIONS,
    _TRADE_TARGET_ANCHOR,
)
from dialog.vault_links import KIND_BY_SUBDIR  # noqa: E402
from md_tables import table  # noqa: E402
from settings import (  # noqa: E402
    BARK_LINE_CHARS,
    BARK_MAX_LINES,
    DAY_PHASES,
    DEFAULT_DISPOSITION_WEIGHTS,
    SENTIMENT_EMOJI_TO_NAME,
    SENTIMENT_NAME_TO_EMOTE,
)
from ui.text.markup import TAG_STYLES  # noqa: E402

DEFAULT_OUT = _REPO_ROOT / "doc" / "dialog-cheatsheet.md"

# Co robi każdy predykat w zasięgu `dialog` - jedyna rzecz, której nie da się
# wyczytać z whitelisty. Brak opisu dla nazwy z whitelisty wywala generator,
# a nie ściągawkę.
_PREDICATE_DOC: dict[str, str] = {
    "visited": "gracz był już w węźle `NODE` - u **tej** postaci (1 argument) "
               "albo u wskazanej (2 argumenty)",
    "has_item": "gracz ma przedmiot `ITEM` w ekwipunku",
    "item_count": "ile sztuk `ITEM` gracz ma (liczba, nie prawda/fałsz)",
    "quest_done": "quest `KEY` jest ukończony",
    "selected": "gracz wybrał **kiedykolwiek** opcję o tym kluczu u tej postaci",
}

_PREDICATE_EXAMPLE: dict[str, str] = {
    "visited": "`visited(`[[#004]]`)`",
    "has_item": "`has_item(`[[Łza Syrenki]]`)`",
    "item_count": "`item_count(`[[Łza Syrenki]]`) >= 3`",
    "quest_done": "`quest_done(`[[Q01_S01 Kto wie więcej o klątwie]]`)`",
    "selected": '`selected("001to002_3")`',
}

# Predykaty barka, których w dialogu nie ma - opisy tylko dla nich, resztę
# ściągawka barków ma u siebie.
_BARK_ONLY_DOC: dict[str, str] = {
    "time_of_day": "pora dnia w świecie gry",
    "activity": "co mówiący właśnie robi (krok rutyny)",
    "at": "dokąd prowadzi bieżący krok rutyny (`type:`, `location:`, `route:`)",
    "on_map": "na której mapie stoi mówiący",
}

# (znaczenie, przykład) per czasownik. Sam zapis - kształt argumentów - bierze
# się z `_SIGNATURES`, więc dopisanie czasownika bez opisu wywala generator.
_EFFECT_DOC: dict[str, tuple[str, str]] = {
    "add_money": ("daje graczowi złoto", "`` [`add_money(50)`] ``"),
    "remove_money": ("zabiera graczowi złoto", "`` [`remove_money(20)`] ``"),
    "add_n_items": (
        "daje przedmioty - pierwszy argument to **krotność każdego** z nich",
        "`` [`add_n_items(1,`[[Łza Syrenki]]`)`] ``",
    ),
    "remove_n_items": (
        "zabiera przedmioty (tak płaci się postaci za przysługę)",
        "`` [`remove_n_items(1,`[[Wąs Gnoma]]`,`[[Łza Syrenki]]`)`] ``",
    ),
    "restore_health": ("leczy bieżące HP", "`` [`restore_health(20)`] ``"),
    "lose_health": ("odbiera HP", "`` [`lose_health(10)`] ``"),
    "shift_sentiment": (
        "zmienia sympatię **tej** postaci - jedyny czasownik ze znakiem",
        "`` [`shift_sentiment(-10)`] ``",
    ),
}

# Kształt argumentów per sygnatura z `dialog.effects._SIGNATURES`.
_SIGNATURE_SHAPE: dict[str, str] = {
    "amount": "{verb}(nn)",
    "signed_amount": "{verb}(±nn)",
    "count_items": "{verb}(nn, ITEM, …)",
    "npc_amount": "{verb}(NPC, ±nn)",
}

# Pola frontmatteru, które importer naprawdę czyta (`_parse_frontmatter`).
# Wagi dochodzą z `_FRONTMATTER_WEIGHT_KEYS`, żeby dopisanie sentymentu nie
# wymagało ruszania tej listy.
_FRONTMATTER_DOC: dict[str, tuple[str, str]] = {
    "aliases": (
        "**klucz postaci** (`SCREAMING_SNAKE`) - pierwszy alias pisany wielkimi "
        "literami; dalsze aliasy to skróty do linkowania",
        "tak",
    ),
    "sprite": ("katalog assetów z `NinjaAdventure/characters/`", "tak"),
    "friendly": ("startowa sympatia 0..1 (`NPC.sentiment = friendly * 100`)", "nie"),
}

_SENTIMENT_ROLE: dict[str, str] = {
    "kind": "życzliwie",
    "weak": "żałośnie",
    "neutral": "rzeczowo",
    "angry": "gniewnie",
    "smart": "z głową",
    "funny": "żartem",
    "technical": "techniczne (nie postawa gracza, tylko obsługa rozmowy)",
}

# Szablon postaci: to, co autor kopiuje jako pierwsze. Trzymany w stałej, bo
# `tests/test_dialog_cheatsheet.py` wyjmuje go ze strony i przepuszcza przez
# prawdziwy importer - szablon dokumentujący nieistniejącą składnię wywala test,
# a nie autora.
_TEMPLATE = """---
aliases:
  - ZIELARKA_ZMORA
  - Zielarka
EN: "[[Potioneer Puzzlemint]]"
location: "[[Gafowo Kolonia]]"
sprite: Hunter
friendly: 0.5
kind: 1
weak: -1
angry: -2
smart: 2
funny: 1
---
# Info

## Tło historyczne

Notatki autorskie. Importer zaczyna czytać dopiero od pierwszego numerycznego
nagłówka, więc proza i podsekcje `# Info` nigdy nie kolidują z węzłami.

## Barki

- Zioła same się nie posieją.

## 000

* Witaj w [[Tawerna Brakująca klepka|Tawernie]]. Czego szukasz:question:

* [[#001]] 1😇: Szukam lekarstwa na _klątwę_.
* [[#002]] 2[`visited(`[[Barman Absyntnent#012]]`)`]🧠: [[Barman Absyntnent|Barman]] mówił, że **Ty** wiesz więcej.
* [[#990-end]] 9😐: Nic, tak tylko zaglądam.

## 001

* [`add_n_items(1,`[[Łza Syrenki]]`)`] Weź to i nie pytaj, skąd mam.

* [[#990-end]] 1😐: Dzięki:blink:

## 002

* [`shift_sentiment(-10)`] Barman gada, a ja pracuję.

* [[#990-end]] 1😐: Rozumiem.

## 990-end
[[#001]]

* Wracaj, gdy będziesz gotów.
"""


def _frontmatter_table() -> str:
    """Pola frontmatteru, które czyta importer - reszta jest tylko dla Obsidiana."""
    rows = [
        [f"`{name}`", doc, required]
        for name, (doc, required) in _FRONTMATTER_DOC.items()
    ]
    weights = ", ".join(f"`{key}`" for key in _FRONTMATTER_WEIGHT_KEYS)
    rows.append([
        weights,
        "wagi sentymentów (-2..2) - o tyle zmienia się sympatia po wyborze opcji "
        "z tym emoji; brak pola = wartość domyślna",
        "nie",
    ])
    return table(["Pole", "Znaczenie", "Obowiązkowe"], rows)


def _sentiment_table() -> str:
    """Emoji -> nazwa -> domyślna waga -> ikonka. Wszystko z tabel `settings`."""
    rows = []
    for emoji, name in SENTIMENT_EMOJI_TO_NAME.items():
        weight = DEFAULT_DISPOSITION_WEIGHTS[name]
        rows.append([
            emoji,
            f"`{name}`",
            f"`{weight:+d}`" if weight else "`0`",
            f"`:{SENTIMENT_NAME_TO_EMOTE[name]}:`",
            _SENTIMENT_ROLE[name],
        ])
    return table(["Emoji", "Nazwa", "Domyślna waga", "Ikonka", "Ton odpowiedzi"], rows)


def _predicates_table() -> str:
    rows = [
        [_PREDICATE_EXAMPLE[name], _PREDICATE_DOC[name]]
        for name in sorted(_DIALOG_PREDICATES)
    ]
    return table(["Wywołanie", "Znaczenie"], rows)


def _effects_table() -> str:
    """Czasownik -> co robi. Zasięg `dialog`, prosto z whitelisty efektów."""
    rows = []
    for verb in EFFECTS_BY_SCOPE[EffectScope.dialog]:
        shape = _SIGNATURE_SHAPE[_SIGNATURES[verb]].format(verb=verb)
        doc, example = _EFFECT_DOC[verb]
        rows.append([f"`{shape}`", doc, example])
    return table(["Zapis", "Znaczenie", "Przykład"], rows)


def _quest_only_effects_line() -> str:
    """Czasowniki, których w rozmowie nie ma - z różnicy whitelist, nie z pamięci."""
    extra = [
        verb
        for verb in EFFECTS_BY_SCOPE[EffectScope.quest]
        if verb not in EFFECTS_BY_SCOPE[EffectScope.dialog]
    ]
    return ", ".join(f"`{verb}`" for verb in extra)


def _legacy_tags_table() -> str:
    """Stare znaczniki z RPG-a, które importer sam tłumaczy na znaczniki MoM."""
    rows = [
        [f"`[{old}]…[/{old}]`", f"`[{new}]…[/{new}]`"]
        for old, new in _TAG_CONVERSIONS.items()
    ]
    rows.append(["`**pogrubienie**`", "`[shadow]…[/shadow]`"])
    rows.append(["`_kursywa_`", "`[italic]…[/italic]`"])
    return table(["Zapis w notatce", "W grze"], rows)


def _entities_table() -> str:
    """Znacznik encji bierze się z katalogu notatki - tabela czyta go stamtąd."""
    example = {
        "char": ("[[Zielarka Zmora]]", "Zielarka Zmora"),
        "loc": ("[[Tawerna Brakująca klepka]]", "Tawerna Brakująca klepka"),
        "item": ("[[Łza Syrenki]]", "Łza Syrenki"),
        "quest": ("[[Q01_S01 Kto wie więcej o klątwie]]", "Kto wie więcej o klątwie"),
    }
    rows = [
        [f"`{link}`", f"`[{kind}]{shown}[/{kind}]`"]
        for kind, (link, shown) in example.items()
        if kind in set(KIND_BY_SUBDIR.values())
    ]
    rows.append(
        ["`[[Barman Absyntnent\\|Barmana]]`", "`[char]Barmana[/char]` - odmiana z kreski"]
    )
    return table(["W notatce", "W grze"], rows)


def _emote_conversion_note() -> str:
    """Ile emoji importer zamienia na ikonki - liczba prosto z tabeli."""
    pairs = ", ".join(
        f"{emoji} -> `{tag}`" for emoji, tag in list(_EMOJI_TO_EMOTE_TAG.items())[:3]
    )
    return f"wszystkie {len(_EMOJI_TO_EMOTE_TAG)}: {pairs} i tak dalej"


def _bark_predicates_line() -> str:
    """Nazwy, które ma barek, a których dialog nie ma - z różnicy whitelist."""
    extra = sorted(set(_BARK_PREDICATES) - set(_DIALOG_PREDICATES))
    return ", ".join(f"`{name}()` - {_BARK_ONLY_DOC[name]}" for name in extra)


def _day_phases_line() -> str:
    return ", ".join(f"`{name}`" for name, _hour in DAY_PHASES)


def _option_grammar_table() -> str:
    """Rozbiór linii opcji na części - dokładnie tak, jak czyta ją `_OPTION_RE`."""
    return table(
        ["Kawałek", "Co znaczy", "Obowiązkowy"],
        [
            ["`* `", "wypunktowanie - tak zaczyna się **każda** opcja", "tak"],
            ["`[[#002]]`", "węzeł, do którego opcja prowadzi", "tak"],
            ["`3`", "kolejność na liście - opcje sortują się po tej liczbie", "tak"],
            [
                "`` [`visited(...)`] ``",
                "warunek - bez niego opcji nie widać; brak = zawsze widoczna",
                "nie",
            ],
            ["`😐`", "sentyment: jak gracz to mówi i o ile zmieni się sympatia", "tak"],
            ["`: tekst`", "kwestia gracza (dwukropek oddziela ją od reszty)", "tak"],
        ],
    )


def render(out_path: Path) -> str:
    values = sorted(_VALUE_NAMES_BY_SCOPE[ConditionScope.dialog])
    values_line = ", ".join(f"`{v}`" for v in values)
    operators = operators_line(_COMPARE_OPS)

    return f"""---
tags: [sciagawka, dialogi]
---

# Dialogi - ściągawka

> [!warning] Wygenerowane przez `scripts/gen_dialog_cheatsheet.py` (`just gen-dialog-cheatsheet`).
> Nie edytuj ręcznie - emoji sentymentów, predykaty warunków, czasowniki efektów i znaczniki tekstu są wyprowadzone z kodu, więc nie mogą rozjechać się z tym, co robi import i silnik.

> [!important] Jeden plik = jedna postać, a rozmowa to graf
> Węzeł (`## 000`) to **kwestia postaci**, opcja pod nim to **odpowiedź gracza** i zarazem krawędź do następnego węzła. Panel pokazuje jeden węzeł naraz; rozmowa kończy się na węźle z sufiksem `-end` albo tam, gdzie żadna opcja nie przeszła warunku.

## Szablon postaci

**PL** (`doc/PL/Postacie/<Nazwa postaci>.md`) jest źródłem prawdy dla logiki i metadanych;
**EN** (`doc/EN/Characters/<Character name>.md`) trzyma ten sam graf z samą prozą po angielsku.

```markdown
{_TEMPLATE}```

Oba pliki muszą mieć **te same numery węzłów i tyle samo opcji w każdym węźle** - inaczej import odmawia. Nazwa pliku to nazwa postaci w danym języku, a klucz żyje wyłącznie w `aliases`, więc zmiana nazwy pliku nie psuje żadnego warunku.

## Frontmatter

{_frontmatter_table()}

Pozostałe pola (`EN`, `location`, `inspirations`, `alternative`) importer ignoruje - są dla Obsidiana i dla autora. **Frontmatter PL jest źródłem prawdy**; kopię w EN synchronizuje skill `dialog-en-sync`.

## Sentymenty - emoji na końcu opcji

Emoji nie jest ozdobą: mówi, **jak** gracz to powiedział, i o tyle zmienia sympatię postaci. Wagę można nadpisać per postać we frontmatterze.

{_sentiment_table()}

Sympatia (0..100) rządzi cenami w handlu i warunkami `sentiment > n`, więc opcja „grubiańska" ma realny koszt. `technical` i `neutral` mają wagę zero z założenia - to opcje, które tylko przewijają rozmowę.

## Węzeł - `## numer`

Klucze węzłów są **wyłącznie cyframi**, dlatego nagłówki prozy (`## Cechy charakteru`, `## Barki`) nigdy z nimi nie kolidują - importer po prostu ich nie widzi.

- **Pierwszy węzeł w pliku jest węzłem startowym.** Nie ma osobnego pola: to, co stoi najwyżej, otwiera rozmowę.
- **Tekst węzła** zaczyna się od `* ` i może się ciągnąć przez wiele linii. Pusta linia = nowy akapit; kolejne linie bez pustej linii sklejają się w jeden.
- **`-end` w nagłówku** (`## 990-end`) znaczy „tu rozmowa się kończy": panel pokazuje kwestię i czeka na Accept, opcji nie wyświetla. Opcja na węźle `-end` jest błędem importu.
- **Link pod nagłówkiem `-end`** (`[[#001]]` w osobnej linii) to **resume**: następna rozmowa z tą postacią zacznie się od tego węzła zamiast od startowego. Tak się pisze „przywitanie tylko raz".
- Opcja wskazująca węzeł końcowy pisze się z sufiksem (`[[#990-end]]`) - importer sam go zdejmuje, a link zostaje klikalny w Obsidianie.

## Opcje - linia po linii

```markdown
* [[#002]] 3[`sentiment > 60`]😉: A może opowiesz mi o tej [quest]klątwie[/]:question:
```

{_option_grammar_table()}

Klucz opcji składa się sam: `<węzeł>to<cel>_<kolejność>`, czyli powyżej `002to003_3`. Ten klucz widać w save'ach i w warunkach `selected(...)`, więc numer kolejności nie jest kosmetyką - zmieniony przenumerowuje opcję i unieważnia warunek, który się na nią powoływał.

## Warunek opcji

Mini-DSL, nie `eval()`: whitelista dopuszczalnych nazw, wszystko inne to błąd importu z numerem linii. Ta sama gramatyka, co w questach - różni się tylko zestaw nazw.

{_predicates_table()}

**Łączenie**: `and`, `or`, `not`, nawiasy.
**Porównania**: {operators}.
Gołe nazwy-wartości: {values_line} - sympatia **tej** postaci do gracza (0..100).

`visited()` w dialogu bierze **jeden** argument (węzeł u tej samej postaci) albo **dwa** (`NPC`, `NODE`) - inaczej niż w queście, gdzie postać trzeba nazwać zawsze, bo quest nie ma bieżącego rozmówcy.

Warunek zamyka się w **backquote'ach**, a odwołania do encji w środku pisze się **wikilinkami**, przeplatanymi z backquote'ami - jedno wyrażenie jest wtedy naraz warunkiem dla silnika i krawędzią w grafie Obsidiana:

```markdown
* [[#021]] 7[`visited(`[[Zielarka Zmora#009]]`)`]😐: A może ja mogę coś dla **Ciebie** zrobić:question:
```

`[[#005]]` bez nazwy notatki znaczy „węzeł u mówiącego". Link do notatki, której w vaulcie nie ma, to błąd importu z numerem linii - literówka w nazwie postaci nie ma szans dożyć do gry. Stare zapisy (`Potioneer_Puzzlemint.004.visited`, `character.sentiment`, gołe stringi) nadal się importują, ale nie rysują się w grafie.

> [!warning] Niewidoczna opcja nie zamyka rozmowy sama z siebie
> Gdy **wszystkie** opcje węzła odpadną na warunkach, panel kończy rozmowę (auto-end) - gracz nie wisi. Ale to znaczy, że węzeł z samymi warunkowymi opcjami może być ślepym zaułkiem, którego nie widać w tekście. Panel **PROBLEMY** nad grafem wypisuje takie węzły.

## Efekt węzła - co gra robi, gdy gracz tu dotrze

Efekt pisze się **na początku tekstu węzła**, w nawiasie kwadratowym, jako wywołanie w backquote'ach. Aplikuje się **raz**: powtórna wizyta w tym samym węźle nic nie robi.

{_effects_table()}

Ta sama gramatyka opisuje nagrody questów (`dialog/effects.py`), a nazwy czasowników są nazwami metod `ResultSink` w kodzie - od notatki do kodu prowadzi jedno słowo. Czasowniki {_quest_only_effects_line()} należą **wyłącznie** do nagród questa: rozmowa daje i zabiera, ale nie przebudowuje bohatera na stałe i nie sięga do sympatii kogoś, kto właśnie nie stoi naprzeciwko.

Odrzucane przy imporcie:

- wartość `0` (albo `add_n_items` bez przedmiotu) - to kształt, który nigdy nie jest zamierzony,
- liczba ujemna przy czasowniku, który już mówi, w którą stronę idzie (`add_money(-50)`),
- przedmiot bez wiersza w `items.csv` - notatka istnieje, ale gra nie umie go stworzyć,
- stary zapis kategorią (`[GOLD+50]`) - import mówi wprost, na co go zamienić.

## `[[#{_TRADE_TARGET_ANCHOR}]]` - opcja, która oddaje gracza do sklepu

Postać może być naraz rozmówcą i handlarzem. Spacja zawsze otwiera dialog; do handlu wchodzi się **wybraną opcją**:

```markdown
* [[#{_TRADE_TARGET_ANCHOR}]] 7😐: A co masz na sprzedaż:question:
```

`trade` to zarezerwowany cel - klucze węzłów są cyframi, więc żaden prawdziwy węzeł się z nim nie zderzy. Sufiks `-end` czyta się tak samo jak w nagłówku: „to kończy rozmowę" - tu przez oddanie gracza, nie przez pożegnanie. Zapis bez sufiksu jest twardym błędem importu (jedna gramatyka, nie dwie), a `just validate-world` (reguła 23) zgłasza taką opcję u postaci bez `is_merchant`.

Sentyment liczy się **zanim** panel się przełączy - to ma znaczenie, bo sympatia ustala ceny, które gracz zaraz zobaczy.

## Encje w prozie - pisze się je linkiem

Postać, lokalizację, przedmiot i quest pisze się w kwestii i w opcji **wikilinkiem**; import zamienia go na znacznik, którym gra koloruje encję:

{_entities_table()}

Znacznik bierze się z **katalogu notatki**, więc nie trzeba go wybierać, a napis po pionowej kresce niesie odmianę. Link bez kreski pokazuje nazwę notatki w języku pliku, więc `[[Zielarka Zmora]]` w pliku EN wyświetli się jako „Potioneer Puzzlemint".

Znacznikiem wprost pisze się dalej to, co **nie ma notatki**: istoty ze wspomnień, rzeczowniki pospolite, zaimki (`[char]Ty[/char]`). Link do nieistniejącej notatki zostaje w tekście dosłownie i `just validate-world` (reguła 22) uzna to za błąd - gracz zobaczyłby surowe `[[nawiasy]]`.

## Znaczniki tekstu - MoM RichText

Markdownowe wyróżnienia pisze się **po markdownowemu**, a stare znaczniki z RPG-a importer tłumaczy sam:

{_legacy_tags_table()}

`**` idzie na `[shadow]`, a nie na `[bold]`, bo font pikselowy nie ma prawdziwego pogrubienia: `[bold]` to jeden dodatkowy piksel grubości kreski i w akapicie go po prostu nie widać. Wyróżnia cień.

{tags_table()}

`[/]` zamyka **ostatni otwarty** znacznik, więc `[char]Kowal[/]` znaczy to samo co `[char]Kowal[/char]`, a `[h3][char]X[/][/]` domyka najpierw `char`, potem `h3`.

Emotki wstawia się jako `:nazwa:`, a emoji wpisane wprost w tekst importer zamienia na nie sam - {_emote_conversion_note()}. Pełen arkusz z kluczami:
![[_attachements/mom-emote-sheet.png]]

Paleta znaczników w renderze silnika:
![[_attachements/mom-richtext-tags.png]]

## Barki - jedna linijka nad głową

Sekcja `## Barki` w pliku postaci to zaczepki rzucane, gdy gracz przechodzi obok - **nie** dialog: gracz nie odpowiada, nie ma panelu. Warunek pisze się w nawiasie **na początku** linii, tą samą gramatyką co warunek opcji:

```markdown
## Barki

- Kufle same się nie umyją.
- [`time_of_day("morning")`] O tej porze to tylko ja i myszy.
- [`sentiment > 60`] O, mój ulubiony klient!
```

Barek ma nazwy, których dialog nie ma: {_bark_predicates_line()}. Pory dnia: {_day_phases_line()}. Nie ma za to `selected()` - barek nie jest częścią rozmowy.

Limit jest twardy i sprawdzany przy imporcie: **{BARK_MAX_LINES} linie po {BARK_LINE_CHARS} znaków**. O za długim żarcie autor dowiaduje się z `file:line`, a nie widząc go uciętego w grze.

Pełna instrukcja (wspólna pula w `PL/Barki.md`, kolumna `barks` w `characters.csv`, rytm i limity): [[jak-napisac-barka|Jak napisać barka]].

## Czego import nie przepuści

Import działa na zasadzie **wszystko albo nic**: postać, która się nie zaimportuje, to postać, której nie ma w grze - `config.json` zostaje nietknięty, a błąd wskazuje plik i linię.

{table(["Co", "Dlaczego to błąd"], [
    ["węzeł-sierota", "żadna opcja ani resume na niego nie wskazuje - gracz nigdy go nie zobaczy"],
    ["opcja w nieznany węzeł", "literówka w numerze; w grze byłby ślepy skok"],
    ["kotwica ≠ cel", "`[[#002]]` prowadzące do `003` - link w Obsidianie kłamałby"],
    ["duplikat numeru węzła", "dwa `## 007` w jednym pliku"],
    ["nieznane emoji sentymentu", "sentyment musi być jedną z nazw kanonicznych"],
    ["opcja na węźle `-end`", "węzeł końcowy nigdy nie pokazuje opcji"],
    ["rozjazd PL/EN", "inne numery węzłów albo inna liczba opcji w węźle"],
    ["link do nieistniejącej notatki", "w warunku i w efekcie - twardy błąd, nie ciche `False`"],
])}

## Co zrobić po edycji

```bash
just import-dialogs   # kaskada MD -> characters.csv -> config.json; bez argumentu wszystkie postacie
just gen-dialog-graph # graf do doc/_graphs/; bez argumentu wszystkie postacie
just validate-world   # reguły spójności świata (m.in. 22 i 23)
```

Szczegółowa lista kroków: [[Aktualizacja dialogów - checklist]].

## Jak czytać graf

Graf rysuje `scripts/dialog_graph.py` i to na nim widać rzeczy, których w tekście nie widać wcale - większość historycznych bugów dialogów była **własnością grafu**, nie treści.

- **Węzły**: zielony START, czerwony `-end`, żółty z efektem, niebieski zwykły; różowa przerywana obwódka = problem.
- **Krawędzie**: etykieta w kolorze sentymentu (`3 smart`, `2 angry`), przerywana = warunkowa, kropkowana cyjanowa = `resume`.
- **Panel PROBLEMY** nad grafem wypisuje sieroty, ślepe zaułki i węzły z samymi warunkowymi opcjami; kliknięcie centruje kamerę na węźle.
- Klik = podświetl sąsiadów, podwójny klik = otwórz węzeł w źródłowym `.md`, hover = treść, warunek i efekt.

Wymóg jednorazowy: w Obsidianie **Dataview -> Enable JavaScript Queries = on**.
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
        f"{len(SENTIMENT_EMOJI_TO_NAME)} sentymentów, "
        f"{len(_DIALOG_PREDICATES)} predykatów, "
        f"{len(EFFECTS_BY_SCOPE[EffectScope.dialog])} efektów, "
        f"{len(TAG_STYLES)} znaczników  ->  {shown}"
    )


if __name__ == "__main__":
    main()
