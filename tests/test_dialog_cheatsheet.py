#!/usr/bin/env python3
"""Testy jednostkowe dla ``scripts/gen_dialog_cheatsheet.py``.

Sens generowania tej notatki jest jeden: nie może rozjechać się z kodem. Dlatego
przypięte jest dokładnie to - każde emoji sentymentu, każdy predykat z whitelisty,
każdy czasownik efektu i każdy znacznik ma dojechać na stronę. Ściągawka, która
po cichu gubi kategorię, jest gorsza niż żadna: kłamie z autorytetem.

Uruchamianie z katalogu głównego repo::

    .venv/bin/python tests/test_dialog_cheatsheet.py
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from dialog.conditions import _BARK_PREDICATES, _DIALOG_PREDICATES
from dialog.effects import EFFECTS_BY_SCOPE, EffectScope
from dialog.markdown_importer import _FRONTMATTER_WEIGHT_KEYS, _TAG_CONVERSIONS
from dialog.vault_links import WIKI_RE, build_entity_index
from gen_dialog_cheatsheet import _TEMPLATE, DEFAULT_OUT, render
from md_tables import display_width
from settings import SENTIMENT_EMOJI_TO_NAME, SENTIMENT_NAME_TO_EMOTE
from ui.text.markup import TAG_STYLES

_REPO_ROOT = Path(__file__).resolve().parent.parent


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


PAGE = render(DEFAULT_OUT)


def test_every_sentiment_is_documented() -> None:
    """Emoji, nazwa kanoniczna i ikonka - autor pisze pierwsze, kod widzi resztę."""
    for emoji, name in SENTIMENT_EMOJI_TO_NAME.items():
        assert_true(emoji in PAGE, f"emoji {emoji} jest na stronie")
        assert_true(f"`{name}`" in PAGE, f"nazwa sentymentu {name!r} jest na stronie")
        emote = SENTIMENT_NAME_TO_EMOTE[name]
        assert_true(f"`:{emote}:`" in PAGE, f"ikonka :{emote}: jest na stronie")


def test_every_dialog_predicate_is_documented() -> None:
    for name in _DIALOG_PREDICATES:
        assert_true(f"{name}(" in PAGE, f"predykat {name} jest na stronie")


def test_bark_only_predicates_are_documented() -> None:
    """Różnica whitelist, nie ręczna lista - inaczej nowy predykat barka przepada."""
    for name in set(_BARK_PREDICATES) - set(_DIALOG_PREDICATES):
        assert_true(f"`{name}()`" in PAGE, f"predykat barka {name} jest na stronie")


def test_every_dialog_effect_is_documented() -> None:
    """Zasięg `dialog`: czasownik questowy na tej stronie byłby ściemą."""
    for verb in EFFECTS_BY_SCOPE[EffectScope.dialog]:
        assert_true(f"`{verb}(" in PAGE, f"efekt {verb} jest na stronie")


def test_quest_only_effects_are_marked_as_such() -> None:
    """Autor musi wiedzieć, czego w rozmowie NIE wolno, a nie zgadywać."""
    for verb in set(EFFECTS_BY_SCOPE[EffectScope.quest]) - set(
        EFFECTS_BY_SCOPE[EffectScope.dialog]
    ):
        assert_true(f"`{verb}`" in PAGE, f"czasownik questowy {verb} jest wymieniony")


def test_every_frontmatter_weight_is_documented() -> None:
    for key in _FRONTMATTER_WEIGHT_KEYS:
        assert_true(f"`{key}`" in PAGE, f"waga {key!r} jest na stronie")


def test_every_legacy_tag_conversion_is_documented() -> None:
    for old, new in _TAG_CONVERSIONS.items():
        assert_true(f"`[{old}]" in PAGE, f"stary znacznik [{old}] jest na stronie")
        assert_true(f"`[{new}]" in PAGE, f"jego odpowiednik [{new}] jest na stronie")


def test_every_tag_is_documented() -> None:
    for tag in TAG_STYLES:
        # `[link]` bierze argument i tylko tak się go pisze, więc na stronie
        # stoi jako `[link https://...]`
        documented = f"[{tag}]" in PAGE or f"[{tag} " in PAGE
        assert_true(documented, f"znacznik [{tag}] jest na stronie")


def _table_blocks() -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in PAGE.splitlines():
        if line.startswith("|"):
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def test_tables_are_padded_for_obsidian() -> None:
    """Obsidian justuje tabele przy otwarciu; generowana strona ma tam już wylądować.

    Inaczej samo **przeczytanie** notatki przepisuje plik, którego ręcznie
    edytować nie wolno, i notatka ląduje w `git diff`.

    Mierzona jest szerokość **wyświetlana**, nie `len()`: emoji sentymentu zajmuje
    dwie kolumny, ale jeden znak, więc wiersz z emoji jest krótszy w znakach
    i równy w kolumnach - i to jest ta równość, którą widać w edytorze.
    """
    blocks = _table_blocks()
    assert_true(bool(blocks), "strona w ogóle ma tabele")
    for index, block in enumerate(blocks):
        widths = {display_width(line) for line in block}
        assert_eq(len(widths), 1, f"tabela {index} ma jedną szerokość dla każdego wiersza")


def test_no_code_span_starts_with_an_equals_sign() -> None:
    """Dataview czyta `` `= x` `` jako inline query i wypisuje błąd parsera.

    `` `==` `` przy operatorze porównania to przypadek, który naprawdę ugryzł
    w ściągawce questów. Spacja po backquote wygląda tak samo i wyłącza Dataview.
    """
    offenders = re.findall(r"`=[^`\n]*`", PAGE)
    assert_eq(offenders, [], "żaden code span nie zaczyna się od '='")
    assert_true("` ==`" in PAGE, "operator równości dalej jest udokumentowany, ze spacją")


def test_live_wikilinks_resolve_in_the_vault() -> None:
    """Link poza blokiem kodu jest w Obsidianie **żywy** - i ma dokądś prowadzić.

    Ściągawka pisze przykłady tak, jak pisze się dialogi (encja = wikilink), więc
    literówka albo zmiana nazwy notatki zostawiłaby na stronie martwy link. Ten
    test przypina przykłady do vaultu zamiast do napisów.
    """
    index = build_entity_index(_REPO_ROOT / "doc")
    assert_true(bool(index), "indeks vaultu nie jest pusty")

    outside_fences: list[str] = []
    in_fence = False
    for line in PAGE.splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            outside_fences.append(line)

    # code span (`...`) zostaje dosłownym tekstem, więc link w nim nie jest żywy
    text = re.sub(r"``.+?``|`[^`\n]*`", "", "\n".join(outside_fences))

    dangling = [
        match.group("target")
        for match in WIKI_RE.finditer(text)
        if match.group("target") and match.group("target") not in index
    ]
    # notatki spoza katalogów encji (ściągawka barków, checklista) i osadzone
    # obrazki linkujemy po ścieżce - nie mają klucza, więc nie ma ich w indeksie
    def exists(target: str) -> bool:
        base = _REPO_ROOT / "doc" / target
        return base.exists() or base.with_suffix(".md").exists()

    dangling = [target for target in dangling if not exists(target)]
    assert_eq(dangling, [], "każdy żywy wikilink prowadzi do istniejącej notatki")


def test_the_page_is_not_in_the_import_path() -> None:
    """`doc/PL/Postacie/` jest globowany przez importer dialogów.

    Szablon z aliasem w frontmatterze zostałby wzięty za prawdziwą postać, więc
    strona musi leżeć tam, gdzie importer nie zagląda.
    """
    parts = DEFAULT_OUT.parts
    assert_true("Postacie" not in parts, f"nie w katalogu postaci PL: {DEFAULT_OUT}")
    assert_true("Characters" not in parts, f"ani EN: {DEFAULT_OUT}")
    assert_eq(Path(*parts[-2:]), Path("doc/dialog-cheatsheet.md"), "leży w korzeniu vaultu")


def test_the_template_is_on_the_page() -> None:
    """Szablon jest pierwszą rzeczą, którą autor kopiuje - musi być widoczny w całości."""
    assert_true(_TEMPLATE in PAGE, "szablon postaci stoi na stronie dosłownie")
    for marker in ("aliases:", "## Barki", "## 000", "## 990-end", "[[#001]]"):
        assert_true(marker in _TEMPLATE, f"szablon pokazuje {marker!r}")


def test_the_template_really_imports() -> None:
    """Najmocniejsze, co ten plik może sprawdzić: skopiuj szablon, odpal importer.

    Reszta testów porównuje napisy z napisami. Ten bierze postać z bloku kodu,
    zapisuje ją do jednorazowego vaultu i przepuszcza przez `import_character_dialog`,
    więc szablon dokumentujący składnię, której importer już nie czyta, wywala się
    tutaj, a nie w twarz autorowi.
    """
    from dialog.markdown_importer import import_character_dialog

    block = re.search(r"```markdown\n(---\naliases:.*?)```", PAGE, re.S)
    assert_true(block is not None, "strona dalej ma szablon postaci")
    template = block.group(1)  # type: ignore[union-attr]

    def note(key: str, title: str) -> str:
        return f"---\naliases:\n  - {key}\n---\n# {title}\n\nProza.\n"

    barman = (
        "---\naliases:\n  - BARMAN_ABSINTHRAYNER\n---\n"
        "# Barman Absyntnent\n\n## 012\n\n* Gada.\n"
    )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for sub in ("PL/Postacie", "EN/Characters", "PL/Lokalizacje", "PL/Przedmioty"):
            (root / sub).mkdir(parents=True)
        (root / "PL/Postacie/Barman Absyntnent.md").write_text(barman, encoding="utf-8")
        (root / "PL/Postacie/Zielarka Zmora.md").write_text(template, encoding="utf-8")
        (root / "EN/Characters/Potioneer Puzzlemint.md").write_text(template, encoding="utf-8")
        (root / "PL/Lokalizacje/Tawerna Brakująca klepka.md").write_text(
            note("TAVERN", "Tawerna Brakująca klepka"), encoding="utf-8"
        )
        (root / "PL/Przedmioty/Łza Syrenki.md").write_text(
            note("MERMAIDS_TEAR", "Łza Syrenki"), encoding="utf-8"
        )

        messages, dialogs, meta = import_character_dialog(
            root, "Zielarka Zmora", valid_items={"MERMAIDS_TEAR"}
        )

    config = dialogs["ZIELARKA_ZMORA"]
    assert_eq(config["START_NODE"], "000", "pierwszy węzeł w pliku jest startowym")
    assert_eq(config["DIALOG_NODES"]["990"]["is_final"], True, "`-end` daje węzeł końcowy")
    assert_eq(
        config["DIALOG_NODES"]["990"]["resume_node"],
        "001",
        "link pod nagłówkiem `-end` to resume",
    )
    assert_eq(
        config["DIALOG_OPTIONS"]["000to002_2"]["condition"],
        'visited("BARMAN_ABSINTHRAYNER", "012")',
        "przeplatany wikilink stał się warunkiem",
    )
    assert_eq(
        config["DIALOG_OPTIONS"]["000to001_1"]["sentiment"],
        "kind",
        "emoji opcji stało się nazwą kanoniczną",
    )
    effect = config["NODE_RESULTS"]["ZIELARKA_ZMORA_NR_001"]
    assert_eq(effect["items"], ["MERMAIDS_TEAR"], "efekt węzła rozwinął link przedmiotu")
    assert_eq(meta["sprite"], "Hunter", "frontmatter PL dał metadane postaci")
    assert_eq(meta["disposition"]["angry"], -2, "wagi sentymentów też")
    assert_true(
        "[loc]" in messages["PL"]["M_ZIELARKA_ZMORA_DN_000"],
        "wikilink lokalizacji stał się znacznikiem",
    )


def main() -> None:
    tests = [
        test_every_sentiment_is_documented,
        test_every_dialog_predicate_is_documented,
        test_bark_only_predicates_are_documented,
        test_every_dialog_effect_is_documented,
        test_quest_only_effects_are_marked_as_such,
        test_every_frontmatter_weight_is_documented,
        test_every_legacy_tag_conversion_is_documented,
        test_every_tag_is_documented,
        test_tables_are_padded_for_obsidian,
        test_no_code_span_starts_with_an_equals_sign,
        test_live_wikilinks_resolve_in_the_vault,
        test_the_page_is_not_in_the_import_path,
        test_the_template_is_on_the_page,
        test_the_template_really_imports,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} dialog cheat sheet tests passed.")


if __name__ == "__main__":
    main()
