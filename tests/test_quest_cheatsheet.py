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
from quest.markdown_importer import _FIELD_ALIASES, _MACHINE_FIELDS
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

    The reward table leads with the syntax (``money=nn``), not the bare name, so
    the category value appears as the start of a code span rather than alone.
    """
    for category in QuestRewardCategory:
        assert_true(f"`{category.value}" in PAGE, f"reward {category.value} is on the page")


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


def test_pl_only_fields_are_marked_as_such() -> None:
    """D2 is the reason an LLM can safely rewrite the EN file; it has to be visible."""
    assert_true("**tylko PL**" in PAGE, "the PL-only marking exists")
    # the count of marked rows must match the machine fields, not merely be non-zero
    assert_eq(PAGE.count("| **tylko PL** |"), len(_MACHINE_FIELDS), "every machine field marked")


def test_the_fields_table_marks_what_is_mandatory() -> None:
    """The column the author asked for: title/success/completion are required.

    Mirrors what `_validate_parsed` enforces (those three plus the description
    prose) and `_validate_completion` (test only when completion is test).
    """
    assert_true("| Obowiązkowe |" in PAGE, "the table has a mandatory column")
    # the three always-required fields each sit in a row marked mandatory
    for field in ("title", "success", "completion"):
        row = next((line for line in PAGE.splitlines() if line.startswith(f"| `{field}`")), "")
        assert_true(row.endswith("|"), f"{field} has a table row: {row!r}")
        assert_true("| tak |" in row, f"{field} is marked mandatory: {row!r}")
    # test is conditionally required; the page has to say on what
    test_row = next((line for line in PAGE.splitlines() if line.startswith("| `test`")), "")
    assert_true("completion: test" in test_row, f"test's condition is stated: {test_row!r}")
    # and the description prose is called out beyond the field rows
    assert_true("proza opisu" in PAGE, "the mandatory prose is mentioned too")


def test_the_visited_arity_trap_is_spelled_out() -> None:
    """The quest scope forces 2 args, and the reason is not guessable."""
    low, high = _QUEST_PREDICATES["visited"]
    assert_eq((low, high), (2, 2), "the whitelist still forces both arguments")
    assert_true(f"**{low} argumentów**" in PAGE, "the page says how many, from the whitelist")


def test_the_template_matches_the_importer_schema() -> None:
    """The template is the first thing an author copies; it has to be importable.

    Alias = the umbrella's own key, headings = full keys, and a Requires wikilink -
    the schema the importer actually reads, not the one it used to.
    """
    assert_true("  - Q01_S00_BREAK_THE_CURSE" in PAGE, "alias is a full umbrella key")
    assert_true("## Q01_S00_BREAK_THE_CURSE" in PAGE, "heading is that same key")
    assert_true("## Q01_S01_LEARN_ABOUT_CURSE" in PAGE, "a step is a full key too")
    assert_true("**Requires**: [[Q00_S00_WHAT_IS_GOING_ON]]" in PAGE, "and Requires is a wikilink")


def test_the_template_really_imports() -> None:
    """The strongest thing this file can check: copy the template, run the importer.

    Every other test here compares strings against strings. This one takes the
    fenced chain out of the page, writes it into a throwaway vault and puts it
    through `import_quests` - so a template that documents a schema the importer
    no longer reads fails here rather than in the author's face.
    """
    import re
    import tempfile

    from quest.markdown_importer import import_quests

    block = re.search(r"```markdown\n(---\naliases:.*?)```", PAGE, re.S)
    assert_true(block is not None, "the page still has a chain template")
    template = block.group(1)  # type: ignore[union-attr]

    # the chain the template's Requires points at
    q00 = (
        "---\naliases:\n  - Q00_S00_WHAT_IS_GOING_ON\n---\n\n"
        "## Q00_S00_WHAT_IS_GOING_ON\n\n**Tytuł**: O co tu chodzi?\n\nMiecz gada.\n\n"
        '**Completion**: test\n**Test**: visited("CLAPBACK_SWORD", "015")\n'
        "**Sukces**: To klątwa.\n"
    )

    def as_en(text: str) -> str:
        return text.replace("**Tytuł**:", "**Title**:").replace("**Sukces**:", "**Success**:")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for sub in ("PL/Misje", "EN/Quests"):
            (root / sub).mkdir(parents=True)
        (root / "PL/Misje/a.md").write_text(template, encoding="utf-8")
        (root / "EN/Quests/a.md").write_text(as_en(template), encoding="utf-8")
        (root / "PL/Misje/b.md").write_text(q00, encoding="utf-8")
        (root / "EN/Quests/b.md").write_text(as_en(q00), encoding="utf-8")

        _, quests = import_quests(root, ["Q00_S00_WHAT_IS_GOING_ON", "Q01_S00_BREAK_THE_CURSE"])

    umbrella = "Q01_S00_BREAK_THE_CURSE"
    assert_true(umbrella in quests, f"the umbrella imported: {list(quests)}")
    assert_eq(quests[umbrella]["requires"], ["Q00_S00_WHAT_IS_GOING_ON"], "the wikilink resolved")
    assert_eq(
        quests["Q01_S01_LEARN_ABOUT_CURSE"]["parent"], umbrella, "the step took the alias as parent"
    )
    # two reward lines, two rewards - the template teaches the shape the SSiS
    # `break` used to quietly halve
    assert_eq(len(quests[umbrella]["rewards"]), 2, "both Nagroda lines survived")


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
