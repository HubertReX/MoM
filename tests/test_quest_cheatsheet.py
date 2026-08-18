#!/usr/bin/env python3
"""Unit tests for scripts/gen_quest_cheatsheet.py (Q-12).

Run from the project root:
    .venv/bin/python tests/test_quest_cheatsheet.py

The whole point of generating this page is that it cannot drift from the code, so
what is pinned here is exactly that: every enum member, every whitelisted
predicate and every tag has to reach the page. A cheat sheet that quietly drops a
category is worse than none - it lies with authority.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from dialog.conditions import _QUEST_PREDICATES
from gen_quest_cheatsheet import DEFAULT_OUT, render
from quest.entities import CompletionMode, QuestRewardCategory
from quest.markdown_importer import _FIELD_ALIASES, _MACHINE_FIELDS, _REWARD_CATEGORIES
from ui.text.markup import TAG_STYLES


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


PAGE = render(DEFAULT_OUT)


def test_every_completion_mode_is_documented() -> None:
    for mode in CompletionMode:
        assert_true(f"`{mode.value}`" in PAGE, f"completion {mode.value} is on the page")


def test_every_reward_category_is_documented() -> None:
    """A category nobody documents is a category nobody uses.

    The reward table leads with the **call** an author writes
    (``add_money(nn)``), not with the category name, so what has to reach the
    page is the verb the importer maps onto that category.
    """
    verb_of = {category: verb for verb, category in _REWARD_CATEGORIES.items()}
    for category in QuestRewardCategory:
        verb = verb_of[category.value]
        assert_true(f"`{verb}(" in PAGE, f"reward {category.value} (`{verb}`) is on the page")


def test_every_quest_predicate_is_documented() -> None:
    for name in _QUEST_PREDICATES:
        assert_true(f"{name}(" in PAGE, f"predicate {name} is on the page")


def test_every_field_spelling_is_documented() -> None:
    """Both languages, because the EN file reads naturally or authors stop using it."""
    for spelling in _FIELD_ALIASES:
        assert_true(f"`{spelling}`" in PAGE, f"field spelling {spelling!r} is on the page")


def test_every_tag_is_documented() -> None:
    for tag in TAG_STYLES:
        # `[link]` takes an argument and is only ever written with one, so it is
        # documented as `[link https://...]` - which is the useful spelling
        documented = f"[{tag}]" in PAGE or f"[{tag} " in PAGE
        assert_true(documented, f"tag [{tag}] is on the page")


def _cells(line: str) -> list[str]:
    """A table row -> its cells, without the padding that keeps Obsidian quiet."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _row(first_cell: str) -> list[str]:
    """The table row whose first cell is exactly ``first_cell``."""
    for line in PAGE.splitlines():
        if line.startswith("|") and _cells(line)[:1] == [first_cell]:
            return _cells(line)
    return []


def test_tables_are_padded_for_obsidian() -> None:
    """Obsidian justifies tables on open; a generated page must land there already.

    Otherwise merely *reading* the note rewrites it, and a file nobody is allowed
    to edit by hand shows up in `git diff`.
    """
    rows = [line for line in PAGE.splitlines() if line.startswith("|")]
    assert_true(bool(rows), "the page has tables at all")

    widths: dict[int, set[int]] = {}
    block = 0
    previous_was_table = False
    for line in PAGE.splitlines():
        if line.startswith("|"):
            if not previous_was_table:
                block += 1
            widths.setdefault(block, set()).add(len(line))
            previous_was_table = True
        else:
            previous_was_table = False

    for index, line_widths in widths.items():
        assert_eq(len(line_widths), 1, f"table {index} has one width for every row")


def test_no_code_span_starts_with_an_equals_sign() -> None:
    """Dataview reads `` `= x` `` as an inline query and prints a parser error.

    `` `==` `` for the equality operator is the case that actually bit: the note
    rendered a PARSING FAILED block instead of the operator. A space after the
    backquote looks identical and switches Dataview off.
    """
    import re

    offenders = re.findall(r"`=[^`\n]*`", PAGE)
    assert_eq(offenders, [], "no code span may open with '='")
    assert_true("` ==`" in PAGE, "the equality operator is still documented, spaced")


def test_pl_only_fields_are_marked_as_such() -> None:
    """D2 is the reason an LLM can safely rewrite the EN file; it has to be visible."""
    assert_true("**tylko PL**" in PAGE, "the PL-only marking exists")
    # the count of marked rows must match the machine fields, not merely be non-zero
    marked = [line for line in PAGE.splitlines() if "**tylko PL**" in _cells(line)]
    assert_eq(len(marked), len(_MACHINE_FIELDS), "every machine field marked")


def test_the_fields_table_marks_what_is_mandatory() -> None:
    """The column the author asked for: success/completion are required.

    Mirrors what `_validate_parsed` enforces (those two plus the description
    prose) and `_validate_completion` (test only when completion is test). The
    title is not in the table because it is not a field - it is the `# H1`.
    """
    assert_true("Obowiązkowe" in PAGE, "the table has a mandatory column")
    for field in ("success", "completion"):
        row = _row(f"`{field}`")
        assert_true(bool(row), f"{field} has a table row")
        assert_true("tak" in row, f"{field} is marked mandatory: {row!r}")
    # test is conditionally required; the page has to say on what
    test_row = _row("`test`")
    assert_true(
        any("completion: test" in cell for cell in test_row),
        f"test's condition is stated: {test_row!r}",
    )
    # and the description prose is called out beyond the field rows
    assert_true("proza opisu" in PAGE, "the mandatory prose is mentioned too")
    # the title moved out of the table, so the page has to say where it lives
    assert_true("nagłówek `# H1`" in PAGE, "the page says the title is the H1")


def test_the_visited_arity_trap_is_spelled_out() -> None:
    """The quest scope forces 2 args, and the reason is not guessable."""
    low, high = _QUEST_PREDICATES["visited"]
    assert_eq((low, high), (2, 2), "the whitelist still forces both arguments")
    assert_true(f"**{low} argumentów**" in PAGE, "the page says how many, from the whitelist")


def test_the_template_matches_the_importer_schema() -> None:
    """The template is the first thing an author copies; it has to be importable.

    Alias = the quest's own key, `# H1` = its title, a Requires wikilink and a
    `## Notatki` section - the schema the importer actually reads, not the one it
    used to.
    """
    assert_true("  - Q01_S01_LEARN_ABOUT_CURSE" in PAGE, "alias is the quest's full key")
    assert_true("# Dowiedz się więcej o klątwie" in PAGE, "the title is an H1")
    assert_true("**Requires**: [[Q01_S00 Przełamać klątwę]]" in PAGE, "Requires is a wikilink")
    assert_true("## Notatki" in PAGE, "and the notes section is shown")


def test_the_template_really_imports() -> None:
    """The strongest thing this file can check: copy the template, run the importer.

    Every other test here compares strings against strings. This one takes the
    fenced quest out of the page, writes it into a throwaway vault and puts it
    through `import_quests` - so a template that documents a schema the importer
    no longer reads fails here rather than in the author's face.
    """
    import re
    import tempfile

    from quest.markdown_importer import import_quests

    block = re.search(r"```markdown\n(---\naliases:.*?)```", PAGE, re.S)
    assert_true(block is not None, "the page still has a quest template")
    template = block.group(1)  # type: ignore[union-attr]

    # the umbrella the template's Requires points at, named the way the link is
    umbrella_note = (
        "---\naliases:\n  - Q01_S00_BREAK_THE_CURSE\n---\n"
        "# Przełamać klątwę\n\nKlątwa nie zdejmie się sama.\n\n"
        "**Completion**: `all_subquests`\n**Sukces**: Klątwa zdjęta.\n"
    )
    barman = (
        "---\naliases:\n  - BARMAN_ABSINTHRAYNER\n  - Barman\n---\n"
        "# Barman Absyntnent\n\n## 012\n\nGada.\n"
    )

    def as_en(text: str) -> str:
        return text.replace("**Sukces**:", "**Success**:")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for sub in ("PL/Misje", "EN/Quests", "PL/Postacie"):
            (root / sub).mkdir(parents=True)
        (root / "PL/Postacie/Barman Absyntnent.md").write_text(barman, encoding="utf-8")
        (root / "PL/Misje/Q01_S01 Dowiedz sie wiecej.md").write_text(template, encoding="utf-8")
        (root / "EN/Quests/Q01_S01 Learn more.md").write_text(as_en(template), encoding="utf-8")
        (root / "PL/Misje/Q01_S00 Przełamać klątwę.md").write_text(umbrella_note, encoding="utf-8")
        (root / "EN/Quests/Q01_S00 Break the curse.md").write_text(
            as_en(umbrella_note), encoding="utf-8"
        )

        _, quests = import_quests(root, ["Q01_S00_BREAK_THE_CURSE", "Q01_S01_LEARN_ABOUT_CURSE"])

    step = "Q01_S01_LEARN_ABOUT_CURSE"
    assert_true(step in quests, f"the template imported: {list(quests)}")
    assert_eq(quests[step]["requires"], ["Q01_S00_BREAK_THE_CURSE"], "the wikilink resolved")
    assert_eq(quests[step]["parent"], "Q01_S00_BREAK_THE_CURSE", "parent came from the key")
    assert_eq(
        quests[step]["test"],
        'visited("BARMAN_ABSINTHRAYNER", "012")',
        "the interleaved wikilink became a condition",
    )
    assert_eq(len(quests[step]["rewards"]), 1, "the Nagroda line survived")


def test_the_page_is_not_in_the_import_path() -> None:
    """`doc/PL/Misje/` is globbed by the importer.

    A template carrying an alias would be picked up as a real chain, so the page
    has to live somewhere the importer never looks.
    """
    parts = DEFAULT_OUT.parts
    assert_true("Misje" not in parts, f"not in the PL quest dir: {DEFAULT_OUT}")
    assert_true("Quests" not in parts, f"nor the EN one: {DEFAULT_OUT}")
    assert_eq(Path(*parts[-2:]), Path("doc/quest-cheatsheet.md"), "lives at the vault root")


def main() -> None:
    tests = [
        test_every_completion_mode_is_documented,
        test_every_reward_category_is_documented,
        test_every_quest_predicate_is_documented,
        test_every_field_spelling_is_documented,
        test_every_tag_is_documented,
        test_tables_are_padded_for_obsidian,
        test_no_code_span_starts_with_an_equals_sign,
        test_pl_only_fields_are_marked_as_such,
        test_the_fields_table_marks_what_is_mandatory,
        test_the_visited_arity_trap_is_spelled_out,
        test_the_template_matches_the_importer_schema,
        test_the_template_really_imports,
        test_the_page_is_not_in_the_import_path,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} quest cheat sheet tests passed.")


if __name__ == "__main__":
    main()
