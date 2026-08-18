#!/usr/bin/env python3
"""Unit tests for quest/markdown_importer.py (Q-04).

Run from the project root:
    .venv/bin/python tests/test_quest_import.py

Builds throwaway vaults in a temp dir and imports them, so the tests exercise the
real file discovery / parsing / validation path without touching doc/.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))

from quest.markdown_importer import (
    MESSAGE_PREFIX,
    QuestImportError,
    build_quest_config,
    import_quests,
    validate_references,
)


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


# --- fixture vault ---------------------------------------------------------

# One file is one quest, and the frontmatter alias is its key - the same string
# a wikilink to it resolves to.
Q00 = "Q00_S00_WHAT_IS_GOING_ON"
Q03_S00 = "Q03_S00_LEARN_ABOUT_CURSE"
Q03_S01 = "Q03_S01_WHO_HAS_MORE_KNOWLEDGE"
Q03_S02 = "Q03_S02_WHERE_TO_FIND_THIS_PERSON"

ALL_KEYS = [Q00, Q03_S00, Q03_S01, Q03_S02]

# A character note, so a `visited(`[[...]]`)` in a test has something to resolve.
SWORD_NOTE = """---
aliases:
  - CLAPBACK_SWORD
  - Miecz
---
# Miecz Ciętej-riposty

## 015-end

Gada.
"""

POTIONEER_NOTE = """---
aliases:
  - POTIONEER_PUZZLEMINT
  - Zielarka
---
# Zielarka Zmora

## 014

Warzy.
"""

Q00_PL = """---
aliases:
  - Q00_S00_WHAT_IS_GOING_ON
---
# O co tu chodzi?

Miecz gada. Miecz gada i nie zamierza przestać.

**Completion**: `test`
**Test**: `visited("CLAPBACK_SWORD", "015")`
**Sukces**: No dobrze. Miecz gada, a ty masz problem.
**Nagroda**: `money=50`
"""

Q00_EN = """---
aliases:
  - Q00_S00_WHAT_IS_GOING_ON
---
# What is going on?

The sword talks. It talks and has no intention of stopping.

**Success**: Fine. The sword talks, and you have a problem.
"""

Q03_S00_PL = """---
aliases:
  - Q03_S00_LEARN_ABOUT_CURSE
---
# Znajdź kogoś kto wie o klątwach

Ktoś w tym miasteczku musi wiedzieć, jak się zdejmuje klątwy.

**Requires**: [[Q00_S00_WHAT_IS_GOING_ON]]
**Completion**: `all_subquests`
**Sukces**: Wiesz już, kto, gdzie i jak.
**Nagroda**: `money=100`
**Nagroda**: `max_health=20`

## Notatki

Parasol wątku śledczego. Tego akapitu gracz nigdy nie zobaczy.
"""

Q03_S00_EN = """---
aliases:
  - Q03_S00_LEARN_ABOUT_CURSE
---
# Find someone who knows about curses

Someone in this town must know how curses come off.

**Success**: You now know who, where and how.
"""

Q03_S01_PL = """---
aliases:
  - Q03_S01_WHO_HAS_MORE_KNOWLEDGE
---
# Kto ma wiedzę o magii?

Barman wspomniał, że ktoś w miasteczku zna się na klątwach.

**Requires**: [[Q03_S00 Znajdz kogos kto wie o klatwach]]
**Completion**: `test`
**Test**: `visited("POTIONEER_PUZZLEMINT", "014") or visited("POTIONEER_PUZZLEMINT", "017")`
**Sukces**: Puzzlemint wie więcej, niż chciałby przyznać.
"""

Q03_S01_EN = """---
aliases:
  - Q03_S01_WHO_HAS_MORE_KNOWLEDGE
---
# Who knows about magic?

The barman mentioned someone in town knows about curses.

**Success**: Puzzlemint knows more than he would admit.
"""

Q03_S02_PL = """---
aliases:
  - Q03_S02_WHERE_TO_FIND_THIS_PERSON
---
# Gdzie znaleźć tę osobę?

Wiedza to jedno, adres to drugie.

**Requires**: [[Q03_S01 Kto ma wiedze o magii]]
**Completion**: `test`
**Test**: `visited("HAMMER_HOAXHEART", "009")`
**Sukces**: Kowal narysował mapkę. Na piasku. Palcem.
"""

Q03_S02_EN = """---
aliases:
  - Q03_S02_WHERE_TO_FIND_THIS_PERSON
---
# Where to find this person?

Knowledge is one thing, an address is another.

**Success**: The smith drew a map. In the sand. With a finger.
"""

# File name -> content, relative to the vault root. The PL names carry the
# `Qxx_Syy` prefix the way the real vault does, because `Requires` links point at
# them by name.
_VAULT_FILES: dict[str, str] = {
    "PL/Misje/Q00_S00 O co tu chodzi.md": Q00_PL,
    "EN/Quests/Q00_S00 What is going on.md": Q00_EN,
    "PL/Misje/Q03_S00 Znajdz kogos kto wie o klatwach.md": Q03_S00_PL,
    "EN/Quests/Q03_S00 Find someone who knows about curses.md": Q03_S00_EN,
    "PL/Misje/Q03_S01 Kto ma wiedze o magii.md": Q03_S01_PL,
    "EN/Quests/Q03_S01 Who knows about magic.md": Q03_S01_EN,
    "PL/Misje/Q03_S02 Gdzie znalezc te osobe.md": Q03_S02_PL,
    "EN/Quests/Q03_S02 Where to find this person.md": Q03_S02_EN,
}


def _make_vault(root: Path, files: dict[str, str]) -> Path:
    """files maps 'PL/Misje/Name.md' -> content."""
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _full_vault(root: Path, **overrides: str) -> Path:
    """The whole fixture vault, with named files swapped out for a variant."""
    files = dict(_VAULT_FILES)
    files.update(overrides)
    return _make_vault(root, files)


def _character_vault(root: Path, **overrides: str) -> Path:
    """The fixture vault plus the character notes wikilinks resolve against."""
    return _full_vault(
        root,
        **{
            "PL/Postacie/Miecz Cietej-riposty.md": SWORD_NOTE,
            "PL/Postacie/Zielarka Zmora.md": POTIONEER_NOTE,
            **overrides,
        },
    )


def _fixture_config() -> dict[str, object]:
    """A config carrying every dialog node the fixture quests name.

    validate_references checks quest tests against the real dialogs, so a config
    stub has to actually contain them — otherwise the import correctly refuses.
    """
    def nodes(*keys: str) -> dict[str, object]:
        return {"DIALOG_NODES": {k: {"text": f"M_DN_{k}"} for k in keys}}

    return {
        "characters": {},
        "items": {"MERMAIDS_TEAR": {}},
        "dialogs": {
            "CLAPBACK_SWORD": nodes("015"),
            "POTIONEER_PUZZLEMINT": nodes("014", "017"),
            "HAMMER_HOAXHEART": nodes("009"),
            "SOMEONE": {"DIALOG_NODES": {"000": {"text": "M_SOMEONE_DN_000"}}},
        },
        "messages": {"PL": {"M_SOMEONE_DN_000": "cześć"}, "EN": {"M_SOMEONE_DN_000": "hi"}},
    }


def _expect_import_error(fn, needle: str, msg: str) -> None:  # type: ignore[no-untyped-def]
    try:
        fn()
    except QuestImportError as error:
        assert needle in str(error), f"{msg}: message {str(error)!r} lacks {needle!r}"
        return
    raise AssertionError(f"expected QuestImportError: {msg}")


# --- tests -----------------------------------------------------------------


def test_imports_the_vault() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        vault = _full_vault(Path(tmp))
        _, quests = import_quests(vault, ALL_KEYS)

    assert_eq(len(quests), 4, "four quests across two chains")
    assert_true(Q00 in quests, "the alias is the quest key")
    assert_true(Q03_S01 in quests, "a step is a quest of its own")

    step = quests[Q03_S01]
    assert_eq(step["completion"], "test", "completion parsed")
    assert_eq(
        step["test"],
        'visited("POTIONEER_PUZZLEMINT", "014") or visited("POTIONEER_PUZZLEMINT", "017")',
        "test kept, minus the backticks",
    )
    assert_eq(
        quests[Q03_S00]["requires"], [Q00], "requires parsed"
    )


def test_parent_comes_from_the_key() -> None:
    """D1: ``Qxx_Syy_...`` is a step of ``Qxx_S00_...``, nobody writes it down."""
    with tempfile.TemporaryDirectory() as tmp:
        _, quests = import_quests(_full_vault(Path(tmp)), ALL_KEYS)

    assert_eq(quests[Q03_S01]["parent"], Q03_S00, "step parents to its chain's S00")
    assert_eq(quests[Q03_S02]["parent"], Q03_S00, "and so does the next step")
    assert_true("parent" not in quests[Q03_S00], "the umbrella has no parent")
    assert_true("parent" not in quests[Q00], "a lone S00 is its own umbrella")


def test_a_chain_without_an_umbrella_fails() -> None:
    """A step whose S00 does not exist would be an orphan nobody notices."""
    orphan = Q00_PL.replace("Q00_S00_WHAT_IS_GOING_ON", "Q00_S01_WHAT_IS_GOING_ON")
    orphan_en = Q00_EN.replace("Q00_S00_WHAT_IS_GOING_ON", "Q00_S01_WHAT_IS_GOING_ON")
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(
            Path(tmp), {"PL/Misje/a.md": orphan, "EN/Quests/a.md": orphan_en}
        )
        _expect_import_error(
            lambda: import_quests(vault, ["Q00_S01_WHAT_IS_GOING_ON"]),
            "has no umbrella",
            "step without an S00",
        )


def test_two_umbrellas_in_one_chain_fail() -> None:
    twin = Q00_PL.replace("Q00_S00_WHAT_IS_GOING_ON", "Q00_S00_SOMETHING_ELSE")
    twin_en = Q00_EN.replace("Q00_S00_WHAT_IS_GOING_ON", "Q00_S00_SOMETHING_ELSE")
    with tempfile.TemporaryDirectory() as tmp:
        vault = _full_vault(
            Path(tmp),
            **{"PL/Misje/twin.md": twin, "EN/Quests/twin.md": twin_en},
        )
        _expect_import_error(
            lambda: import_quests(vault, [Q00, "Q00_S00_SOMETHING_ELSE"]),
            "two umbrellas",
            "two S00 in one chain",
        )


def test_a_key_that_is_not_qxx_syy_fails() -> None:
    """The numbering carries the parent, so a free-form key cannot be allowed."""
    odd = Q00_PL.replace("Q00_S00_WHAT_IS_GOING_ON", "OPENING_QUEST")
    odd_en = Q00_EN.replace("Q00_S00_WHAT_IS_GOING_ON", "OPENING_QUEST")
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(Path(tmp), {"PL/Misje/a.md": odd, "EN/Quests/a.md": odd_en})
        _expect_import_error(
            lambda: import_quests(vault, ["OPENING_QUEST"]),
            "does not read 'Qxx_Syy_NAME'",
            "free-form key",
        )


def test_notes_below_a_heading_are_not_the_players_business() -> None:
    """`## Notatki` is where the author writes; the journal never sees it."""
    with tempfile.TemporaryDirectory() as tmp:
        messages, _ = import_quests(_full_vault(Path(tmp)), ALL_KEYS)

    description = messages["PL"][f"{MESSAGE_PREFIX}{Q03_S00}_DESCRIPTION"]
    assert_eq(
        description,
        "Ktoś w tym miasteczku musi wiedzieć, jak się zdejmuje klątwy.",
        "prose above the heading only",
    )
    assert_true("gracz nigdy nie zobaczy" not in description, "the notes stayed out")


def test_markdown_emphasis_becomes_richtext() -> None:
    """`**bold**` / `_italic_` reach the player as tags, not as asterisks.

    The journal draws RichText markup and has no idea what an asterisk means, so
    without this pass the author's `**Twój**` was printed with its stars.

    `**` maps to `[shadow]`, not `[bold]`: MoM sets prose in a pixel font, where
    pygame's synthetic bold is one pixel of stem and vanishes in a paragraph. The
    drop shadow is what reads as weight here (and is what the dialogue importer
    already does), so this assertion pins the tag, not the CSS name.
    """
    emphasised = Q00_PL.replace(
        "Miecz gada. Miecz gada i nie zamierza przestać.",
        "Miecz gada. **Twój** miecz gada i _nie_ zamierza przestać.",
    ).replace(
        "**Sukces**: No dobrze.",
        "**Sukces**: No **dobrze**.",
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _full_vault(Path(tmp), **{"PL/Misje/Q00_S00 O co tu chodzi.md": emphasised})
        messages, _ = import_quests(vault, ALL_KEYS)

    description = messages["PL"][f"{MESSAGE_PREFIX}{Q00}_DESCRIPTION"]
    assert_eq(
        description,
        "Miecz gada. [shadow]Twój[/shadow] miecz gada i [italic]nie[/italic] zamierza przestać.",
        "both emphases converted",
    )
    assert_true("*" not in description, "no asterisk survives into the game")
    assert_true(
        "[shadow]dobrze[/shadow]" in messages["PL"][f"{MESSAGE_PREFIX}{Q00}_SUCCESS"],
        "the Sukces line is converted too",
    )


def test_a_field_name_is_not_read_as_emphasis() -> None:
    """`**Sukces**:` opens a field, and the emphasis pass must never see it.

    Conversion runs on the *value*, after the line has been recognised as a field,
    so the label cannot come out as `[bold]Sukces[/bold]:` prose.
    """
    with tempfile.TemporaryDirectory() as tmp:
        messages, quests = import_quests(_full_vault(Path(tmp)), ALL_KEYS)

    assert_true(
        "[shadow]" not in messages["PL"][f"{MESSAGE_PREFIX}{Q00}_DESCRIPTION"],
        "a plain quest gains no tags",
    )
    assert_eq(quests[Q00]["rewards"][0]["value"], 50, "the fields still parsed")


def test_a_blank_line_stays_a_paragraph_break() -> None:
    """Two blocks of prose stay two blocks; a hard-wrapped one stays one."""
    two_paragraphs = Q00_PL.replace(
        "Miecz gada. Miecz gada i nie zamierza przestać.",
        "Miecz gada.\n\nMiecz gada i nie\nzamierza przestać.",
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _full_vault(Path(tmp), **{"PL/Misje/Q00_S00 O co tu chodzi.md": two_paragraphs})
        messages, _ = import_quests(vault, ALL_KEYS)

    assert_eq(
        messages["PL"][f"{MESSAGE_PREFIX}{Q00}_DESCRIPTION"],
        "Miecz gada.\n\nMiecz gada i nie zamierza przestać.",
        "blank line survives, the wrap inside a paragraph does not",
    )


def test_a_field_below_the_notes_heading_is_ignored() -> None:
    """It is ignored, but loudly — a silently dropped Reward is the bug class."""
    with_late_field = Q00_PL + "\n## Notatki\n\n**Nagroda**: `money=999`\n"
    with tempfile.TemporaryDirectory() as tmp:
        vault = _full_vault(Path(tmp), **{"PL/Misje/Q00_S00 O co tu chodzi.md": with_late_field})
        _, quests = import_quests(vault, ALL_KEYS)

    rewards = quests[Q00]["rewards"]
    assert_eq(len(rewards), 1, "only the reward above the heading counts")
    assert_eq(rewards[0], {"category": "money", "value": 50}, "and it is the right one")


def test_wikilinks_in_a_test_become_keys() -> None:
    """The whole point of the interleaved spelling: one string, two readers.

    Obsidian sees a link and draws the edge; the engine gets the character key and
    the dialog node. `-end` marks a terminal node in the dialog file and is not
    part of the node key.
    """
    linked = Q00_PL.replace(
        '**Test**: `visited("CLAPBACK_SWORD", "015")`',
        "**Test**: `visited(`[[Miecz Cietej-riposty#015-end|Miecz#015-end]]`)`",
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _character_vault(
            Path(tmp), **{"PL/Misje/Q00_S00 O co tu chodzi.md": linked}
        )
        _, quests = import_quests(vault, ALL_KEYS)

    assert_eq(
        quests[Q00]["test"], 'visited("CLAPBACK_SWORD", "015")', "link expanded to both arguments"
    )


def test_an_alias_link_and_a_name_link_are_the_same_edge() -> None:
    """`[[Zielarka Zmora#014]]` and `[[POTIONEER_PUZZLEMINT#014]]` mean one thing."""
    expected = 'visited("POTIONEER_PUZZLEMINT", "014")'
    for spelling in (
        "[[Zielarka Zmora#014]]",
        "[[POTIONEER_PUZZLEMINT#014]]",
        "[[Zielarka#014|Zielarka, węzeł 014]]",
    ):
        linked = Q03_S01_PL.replace(
            '**Test**: `visited("POTIONEER_PUZZLEMINT", "014") '
            'or visited("POTIONEER_PUZZLEMINT", "017")`',
            f"**Test**: `visited(`{spelling}`)`",
        )
        with tempfile.TemporaryDirectory() as tmp:
            vault = _character_vault(
                Path(tmp), **{"PL/Misje/Q03_S01 Kto ma wiedze o magii.md": linked}
            )
            _, quests = import_quests(vault, ALL_KEYS)
            assert_eq(quests[Q03_S01]["test"], expected, f"same condition: {spelling}")


def test_a_link_to_nothing_fails_the_import() -> None:
    """A typo in a character name must not survive to the game as a silent False."""
    linked = Q00_PL.replace(
        '**Test**: `visited("CLAPBACK_SWORD", "015")`',
        "**Test**: `visited(`[[Miecz Ciętej-Ripostyy#015]]`)`",
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _character_vault(
            Path(tmp), **{"PL/Misje/Q00_S00 O co tu chodzi.md": linked}
        )
        _expect_import_error(
            lambda: import_quests(vault, ALL_KEYS),
            "is not a character, quest or location note",
            "unresolvable link",
        )


def test_messages_carry_both_languages() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        messages, quests = import_quests(_full_vault(Path(tmp)), ALL_KEYS)

    name_key = f"{MESSAGE_PREFIX}{Q00}_NAME"
    # quests hold i18n keys, never text (D3)
    assert_eq(quests[Q00]["name"], name_key, "quest points at a message key")
    assert_eq(messages["PL"][name_key], "O co tu chodzi?", "PL title is the H1")
    assert_eq(messages["EN"][name_key], "What is going on?", "EN title is the H1")
    assert_eq(
        messages["PL"][f"{MESSAGE_PREFIX}{Q00}_DESCRIPTION"],
        "Miecz gada. Miecz gada i nie zamierza przestać.",
        "prose becomes the description",
    )
    assert_eq(
        messages["EN"][f"{MESSAGE_PREFIX}{Q00}_SUCCESS"],
        "Fine. The sword talks, and you have a problem.",
        "EN success",
    )


def test_rewards_are_a_list_in_order() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _, quests = import_quests(_full_vault(Path(tmp)), ALL_KEYS)

    rewards = quests[Q03_S00]["rewards"]
    assert_eq(len(rewards), 2, "both **Nagroda** lines kept")
    assert_eq(rewards[0], {"category": "money", "value": 100}, "first reward")
    assert_eq(rewards[1], {"category": "max_health", "value": 20}, "second reward")


def test_machine_fields_are_read_from_pl_only() -> None:
    """The whole point of D2: an LLM regenerating EN cannot break the logic."""
    sabotaged_en = Q00_EN.replace(
        "**Success**:", '**Test**: `visited("WRONG_NPC", "999")`\n**Success**:'
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _full_vault(
            Path(tmp), **{"EN/Quests/Q00_S00 What is going on.md": sabotaged_en}
        )
        _, quests = import_quests(vault, ALL_KEYS)

    assert_eq(
        quests[Q00]["test"],
        'visited("CLAPBACK_SWORD", "015")',
        "PL test wins; the EN one is ignored",
    )


def test_invalid_test_names_the_file_and_line() -> None:
    """DoD: a broken condition fails the import loudly, pointing at the source."""
    broken = Q00_PL.replace(
        '**Test**: `visited("CLAPBACK_SWORD", "015")`', "**Test**: `agility > 3`"
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(Path(tmp), {"PL/Misje/a.md": broken, "EN/Quests/a.md": Q00_EN})
        _expect_import_error(
            lambda: import_quests(vault, [Q00]), "a.md", "unknown name in a test"
        )


def test_quest_scope_is_enforced_at_import() -> None:
    """`selected()` and a bare `visited()` are dialog-only — catch them at authoring time."""
    for bad_test in ('**Test**: `selected("SOME_OPTION")`', '**Test**: `visited("015")`'):
        broken = Q00_PL.replace('**Test**: `visited("CLAPBACK_SWORD", "015")`', bad_test)
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(Path(tmp), {"PL/Misje/a.md": broken, "EN/Quests/a.md": Q00_EN})
            _expect_import_error(
                lambda: import_quests(vault, [Q00]), "invalid Test", f"rejected: {bad_test}"
            )


def test_a_non_numeric_progress_fails_at_import() -> None:
    """A progress bar counts something, so a yes/no expression is caught here.

    Before this check, `Postęp: has_item("X") / 3` imported fine and crashed the
    game the moment the journal drew the bar (eval_number rejects a bool result).
    Now the import names the file and line instead.
    """
    with_progress = Q00_PL.replace(
        '**Test**: `visited("CLAPBACK_SWORD", "015")`',
        '**Test**: `visited("CLAPBACK_SWORD", "015")`\n'
        '**Postęp**: `has_item("CLAPBACK_SWORD") / 3`',
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(Path(tmp), {"PL/Misje/a.md": with_progress, "EN/Quests/a.md": Q00_EN})
        _expect_import_error(
            lambda: import_quests(vault, [Q00]), "must be a number", "bool progress rejected"
        )


def test_a_numeric_progress_imports() -> None:
    """The valid shape still passes and lands in the config with its total."""
    with_progress = Q00_PL.replace(
        '**Test**: `visited("CLAPBACK_SWORD", "015")`',
        '**Test**: `visited("CLAPBACK_SWORD", "015")`\n'
        '**Postęp**: `item_count("MERMAIDS_TEAR") / 3`',
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(Path(tmp), {"PL/Misje/a.md": with_progress, "EN/Quests/a.md": Q00_EN})
        _, quests = import_quests(vault, [Q00])

    assert_eq(quests[Q00]["progress"], 'item_count("MERMAIDS_TEAR")', "expression kept")
    assert_eq(quests[Q00]["progress_total"], 3, "total parsed off the slash")


def test_graph_problems_fail_the_import() -> None:
    """init_quests runs on the merged set: dangling requires cannot slip through."""
    dangling = Q03_S00_PL.replace(
        "**Requires**: [[Q00_S00_WHAT_IS_GOING_ON]]", "**Requires**: Q99_DOES_NOT_EXIST"
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _full_vault(
            Path(tmp), **{"PL/Misje/Q03_S00 Znajdz kogos kto wie o klatwach.md": dangling}
        )
        _expect_import_error(
            lambda: import_quests(vault, ALL_KEYS), "Q99_DOES_NOT_EXIST", "dangling requires"
        )


def test_an_untranslated_quest_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        vault = _full_vault(
            Path(tmp),
            **{
                "EN/Quests/Q00_S00 What is going on.md": Q00_EN.replace(
                    "**Success**: Fine. The sword talks, and you have a problem.\n", ""
                )
            },
        )
        _expect_import_error(
            lambda: import_quests(vault, ALL_KEYS), "not fully translated", "EN has no Success"
        )


def test_a_missing_en_file_fails() -> None:
    files = {k: v for k, v in _VAULT_FILES.items() if k != "EN/Quests/Q00_S00 What is going on.md"}
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(Path(tmp), files)
        _expect_import_error(
            lambda: import_quests(vault, ALL_KEYS), "no Markdown file with alias", "EN missing"
        )


def test_missing_pieces_fail_with_a_useful_message() -> None:
    cases = [
        (Q00_PL.replace("# O co tu chodzi?\n", ""), "no title found", "missing title"),
        (
            Q00_PL.replace("**Sukces**: No dobrze. Miecz gada, a ty masz problem.\n", ""),
            "Sukces",
            "missing success",
        ),
        (Q00_PL.replace("**Completion**: `test`\n", ""), "Completion", "missing completion"),
        (
            Q00_PL.replace("**Nagroda**: `money=50`", "**Nagroda**: `money=dużo`"),
            "whole number",
            "bad reward value",
        ),
        (
            Q00_PL.replace("**Nagroda**: `money=50`", "**Nagroda**: `50 money`"),
            "category",
            "bad reward shape",
        ),
        (Q00_PL.replace("**Sukces**:", "**Naglowek**:"), "unknown field", "unknown field name"),
        (
            Q00_PL.replace("Miecz gada. Miecz gada i nie zamierza przestać.\n", ""),
            "no description prose",
            "missing prose",
        ),
    ]
    for source, needle, label in cases:
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(Path(tmp), {"PL/Misje/a.md": source, "EN/Quests/a.md": Q00_EN})
            _expect_import_error(lambda: import_quests(vault, [Q00]), needle, label)


def test_a_file_without_a_key_is_not_a_quest() -> None:
    """No UPPER_SNAKE alias means the note is prose, not a quest - skip it."""
    with tempfile.TemporaryDirectory() as tmp:
        vault = _full_vault(
            Path(tmp), **{"PL/Misje/README.md": "# Jak pisać questy\n\nO tym jest ściągawka.\n"}
        )
        _, quests = import_quests(vault, ALL_KEYS)
        assert_eq(len(quests), 4, "the stray note did not become a quest")


def test_every_requires_spelling_means_the_same_edge() -> None:
    """Bare key, alias link, note-name link, link with display text - one key.

    Which one an author writes is an Obsidian concern, and the graph must not be
    able to tell them apart.
    """
    for spelling in (
        "Q00_S00_WHAT_IS_GOING_ON",
        "[[Q00_S00_WHAT_IS_GOING_ON]]",
        "[[Q00_S00 O co tu chodzi]]",
        "[[Q00_S00 O co tu chodzi|o co tu chodzi]]",
    ):
        source = Q03_S00_PL.replace(
            "**Requires**: [[Q00_S00_WHAT_IS_GOING_ON]]", f"**Requires**: {spelling}"
        )
        with tempfile.TemporaryDirectory() as tmp:
            vault = _full_vault(
                Path(tmp), **{"PL/Misje/Q03_S00 Znajdz kogos kto wie o klatwach.md": source}
            )
            _, quests = import_quests(vault, ALL_KEYS)
            assert_eq(quests[Q03_S00]["requires"], [Q00], f"same edge: {spelling}")


def test_a_broken_wikilink_in_requires_fails() -> None:
    source = Q03_S00_PL.replace(
        "**Requires**: [[Q00_S00_WHAT_IS_GOING_ON]]", "**Requires**: [[Q00_S00_WHAT_IS_GOING_ON"
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _full_vault(
            Path(tmp), **{"PL/Misje/Q03_S00 Znajdz kogos kto wie o klatwach.md": source}
        )
        _expect_import_error(
            lambda: import_quests(vault, ALL_KEYS), "broken wikilink", "unclosed [["
        )


def test_the_qxx_shorthand_resolves_at_the_cli() -> None:
    """``just import-quests Q03`` beats typing every step key from memory.

    The shorthand lives only at the CLI boundary, so the vault keeps exactly one
    spelling and ``import_quests`` stays exact.
    """
    with tempfile.TemporaryDirectory() as tmp:
        vault = _full_vault(Path(tmp))
        config_path = vault / "config.json"
        config_path.write_text(json.dumps(_fixture_config()), encoding="utf-8")

        rc = build_quest_config(src_dir=vault, config_path=config_path, chains=["Q00", "Q03"])

        assert_eq(rc, 0, "the prefix resolved to both chains")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert_eq(len(config["quests"]), 4, "a Qxx prefix takes the whole chain")
        assert_true(Q03_S02 in config["quests"], "including its last step")


def test_build_writes_config_and_leaves_dialogs_alone() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        vault = _full_vault(root)
        config_path = root / "config.json"
        config_path.write_text(json.dumps(_fixture_config()), encoding="utf-8")

        rc = build_quest_config(src_dir=vault, config_path=config_path)
        assert_eq(rc, 0, "import succeeded")

        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert_eq(len(config["quests"]), 4, "quests written")
        assert_true("M_SOMEONE_DN_000" in config["messages"]["PL"], "dialog messages untouched")
        assert_true(
            f"{MESSAGE_PREFIX}{Q00}_NAME" in config["messages"]["PL"],
            "quest messages written",
        )
        assert_true("dialogs" in config, "dialogs section preserved")


def test_failed_import_leaves_config_untouched() -> None:
    """All or nothing: a half-imported quest set is a silently broken game."""
    broken = Q00_PL.replace('**Test**: `visited("CLAPBACK_SWORD", "015")`', "**Test**: `nonsense(1)`")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        vault = _make_vault(root, {"PL/Misje/a.md": broken, "EN/Quests/a.md": Q00_EN})
        config_path = root / "config.json"
        original = json.dumps({"messages": {"PL": {}, "EN": {}}, "quests": {"OLD": {}}})
        config_path.write_text(original, encoding="utf-8")

        rc = build_quest_config(src_dir=vault, config_path=config_path, chains=[Q00])

        assert_eq(rc, 1, "import reports failure")
        assert_eq(config_path.read_text(encoding="utf-8"), original, "config.json byte-identical")


def test_orphaned_quest_messages_are_swept() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        vault = _full_vault(root)
        config_path = root / "config.json"
        config = _fixture_config()
        config["messages"] = {
            "PL": {f"{MESSAGE_PREFIX}Q99_GONE_NAME": "usunięty quest"},
            "EN": {f"{MESSAGE_PREFIX}Q99_GONE_NAME": "deleted quest"},
        }
        config["quests"] = {}
        config_path.write_text(json.dumps(config), encoding="utf-8")

        build_quest_config(src_dir=vault, config_path=config_path)

        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert_true(
            f"{MESSAGE_PREFIX}Q99_GONE_NAME" not in config["messages"]["PL"],
            "message of a deleted quest is swept",
        )


def test_dialog_import_does_not_eat_quest_messages() -> None:
    """The two importers share config['messages'] and must not sweep each other.

    The dialog importer deletes every message key no dialog references. Quest
    titles live in the same dict, so without an explicit guard the first
    `just import-dialogs` after `just import-quests` would silently delete every
    quest title, description and success line — and the quest log would render
    blank rows with no error anywhere.
    """
    from dialog.markdown_importer import build_dialog_config

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        vault = _full_vault(root)
        config_path = root / "config.json"
        config_path.write_text(json.dumps(_fixture_config()), encoding="utf-8")

        build_quest_config(src_dir=vault, config_path=config_path)
        before = json.loads(config_path.read_text(encoding="utf-8"))
        quest_keys = {k for k in before["messages"]["PL"] if k.startswith(MESSAGE_PREFIX)}
        assert_true(bool(quest_keys), "quest messages were written")

        # now run the dialog importer over a vault with no characters at all
        build_dialog_config(src_dir=vault, config_path=config_path, character_names=[])

        after = json.loads(config_path.read_text(encoding="utf-8"))
        survivors = {k for k in after["messages"]["PL"] if k.startswith(MESSAGE_PREFIX)}
        assert_eq(survivors, quest_keys, "quest messages survive a dialog import")


_DIALOGS = {
    "CLAPBACK_SWORD": {"DIALOG_NODES": {"015": {"text": "M_X"}}},
    "MADAME_SARCASMIA": {"DIALOG_NODES": {"001": {"text": "M_Y"}}},
}
_ITEMS = {"MERMAIDS_TEAR": {}}


def test_validate_references_catches_a_nonexistent_dialog_node() -> None:
    """The SARCASMIA_AA_BACK_SO_SOON bug, caught automatically.

    That key came from the migration plan, parses fine, whitelists fine, and does
    not exist in MoM — the quest would have sat at False for the entire game. The
    mini-DSL cannot see it (it is a valid string) and init_quests cannot either
    (it never sees the dialogs), so it has to be caught where the whole config is
    visible.
    """
    quests = {
        "Q01_S02": {
            "name": "n", "description": "d", "success": "s", "completion": "test",
            "test": 'visited("MADAME_SARCASMIA", "SARCASMIA_AA_BACK_SO_SOON")',
        }
    }
    problems = validate_references(quests, _DIALOGS, _ITEMS)
    assert_eq(len(problems), 1, "one problem")
    assert_true("SARCASMIA_AA_BACK_SO_SOON" in problems[0], "names the offending node")
    assert_true("could never complete" in problems[0], "explains the consequence")


def test_validate_references_catches_unknown_names() -> None:
    cases = [
        ('visited("NOBODY", "001")', "no dialog", "unknown character"),
        ('quest_done("Q99_GHOST")', "unknown quest", "unknown quest key"),
        ('has_item("NO_SUCH_ITEM")', "unknown item", "unknown item"),
        ('item_count("NO_SUCH_ITEM") > 1', "unknown item", "unknown item via item_count"),
    ]
    for test, needle, label in cases:
        quests = {
            "Q_X": {"name": "n", "description": "d", "success": "s", "completion": "test", "test": test}
        }
        problems = validate_references(quests, _DIALOGS, _ITEMS)
        assert_eq(len(problems), 1, f"{label}: expected one problem, got {problems}")
        assert_true(needle in problems[0], f"{label}: {problems[0]!r} lacks {needle!r}")


def test_validate_references_accepts_the_real_thing() -> None:
    quests = {
        "Q00_S00": {
            "name": "n", "description": "d", "success": "s", "completion": "test",
            "test": 'visited("CLAPBACK_SWORD", "015")',
            "rewards": [{"category": "items", "items": ["MERMAIDS_TEAR"]}],
        },
        "Q01_S02": {
            "name": "n", "description": "d", "success": "s", "completion": "test",
            "test": 'visited("MADAME_SARCASMIA", "001") and quest_done("Q00_S00")',
        },
    }
    assert_eq(validate_references(quests, _DIALOGS, _ITEMS), [], "valid references pass clean")


def test_validate_references_checks_reward_items() -> None:
    quests = {
        "Q_X": {
            "name": "n", "description": "d", "success": "s", "completion": "manual",
            "rewards": [{"category": "items", "items": ["GHOST_ITEM"]}],
        }
    }
    problems = validate_references(quests, _DIALOGS, _ITEMS)
    assert_eq(len(problems), 1, "reward item checked")
    assert_true("GHOST_ITEM" in problems[0], "names the item")


def test_broken_reference_fails_the_build_and_keeps_config() -> None:
    """End to end: a nonexistent node stops `just import-quests` cold."""
    broken = Q00_PL.replace('visited("CLAPBACK_SWORD", "015")', 'visited("CLAPBACK_SWORD", "999")')
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        vault = _make_vault(root, {"PL/Misje/a.md": broken, "EN/Quests/a.md": Q00_EN})
        config_path = root / "config.json"
        original = json.dumps({"messages": {"PL": {}, "EN": {}}, "dialogs": _DIALOGS, "items": _ITEMS})
        config_path.write_text(original, encoding="utf-8")

        rc = build_quest_config(src_dir=vault, config_path=config_path, chains=[Q00])

        assert_eq(rc, 1, "import reports failure")
        assert_eq(config_path.read_text(encoding="utf-8"), original, "config.json byte-identical")


def test_no_sources_is_not_an_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        rc = build_quest_config(src_dir=Path(tmp), config_path=Path(tmp) / "config.json")
        assert_eq(rc, 0, "an empty vault is a no-op, not a failure")


def main() -> None:
    tests = [
        test_imports_the_vault,
        test_parent_comes_from_the_key,
        test_a_chain_without_an_umbrella_fails,
        test_two_umbrellas_in_one_chain_fail,
        test_a_key_that_is_not_qxx_syy_fails,
        test_notes_below_a_heading_are_not_the_players_business,
        test_markdown_emphasis_becomes_richtext,
        test_a_field_name_is_not_read_as_emphasis,
        test_a_blank_line_stays_a_paragraph_break,
        test_a_field_below_the_notes_heading_is_ignored,
        test_wikilinks_in_a_test_become_keys,
        test_an_alias_link_and_a_name_link_are_the_same_edge,
        test_a_link_to_nothing_fails_the_import,
        test_messages_carry_both_languages,
        test_rewards_are_a_list_in_order,
        test_machine_fields_are_read_from_pl_only,
        test_invalid_test_names_the_file_and_line,
        test_quest_scope_is_enforced_at_import,
        test_a_non_numeric_progress_fails_at_import,
        test_a_numeric_progress_imports,
        test_graph_problems_fail_the_import,
        test_an_untranslated_quest_fails,
        test_a_missing_en_file_fails,
        test_missing_pieces_fail_with_a_useful_message,
        test_a_file_without_a_key_is_not_a_quest,
        test_every_requires_spelling_means_the_same_edge,
        test_a_broken_wikilink_in_requires_fails,
        test_the_qxx_shorthand_resolves_at_the_cli,
        test_build_writes_config_and_leaves_dialogs_alone,
        test_failed_import_leaves_config_untouched,
        test_orphaned_quest_messages_are_swept,
        test_dialog_import_does_not_eat_quest_messages,
        test_validate_references_catches_a_nonexistent_dialog_node,
        test_validate_references_catches_unknown_names,
        test_validate_references_accepts_the_real_thing,
        test_validate_references_checks_reward_items,
        test_broken_reference_fails_the_build_and_keeps_config,
        test_no_sources_is_not_an_error,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} quest import tests passed.")


if __name__ == "__main__":
    main()
