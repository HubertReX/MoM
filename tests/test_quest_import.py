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

# A chain is named by its umbrella quest's own key - the same string that is its
# alias, its `## ` heading, and the target of a wikilink to it.
Q00_KEY = "Q00_S00_WHAT_IS_GOING_ON"
Q03_KEY = "Q03_S00_LEARN_ABOUT_CURSE"

Q00_PL = """---
aliases:
  - Q00_S00_WHAT_IS_GOING_ON
---

# O co tu chodzi?

## Q00_S00_WHAT_IS_GOING_ON

**Tytuł**: O co tu chodzi?

Miecz gada. Miecz gada i nie zamierza przestać.

**Completion**: test
**Test**: visited("CLAPBACK_SWORD", "015")
**Sukces**: No dobrze. Miecz gada, a ty masz problem.
**Nagroda**: money=50
"""

Q00_EN = """---
aliases:
  - Q00_S00_WHAT_IS_GOING_ON
---

# What is going on?

## Q00_S00_WHAT_IS_GOING_ON

**Title**: What is going on?

The sword talks. It talks and has no intention of stopping.

**Success**: Fine. The sword talks, and you have a problem.
"""

Q03_PL = """---
aliases:
  - Q03_S00_LEARN_ABOUT_CURSE
---

# Znajdź kogoś kto wie o klątwach

## Q03_S00_LEARN_ABOUT_CURSE

**Tytuł**: Znajdź kogoś kto wie o klątwach

Ktoś w tym miasteczku musi wiedzieć, jak się zdejmuje klątwy.

**Completion**: all_subquests
**Requires**: [[Q00_S00_WHAT_IS_GOING_ON]]
**Sukces**: Wiesz już, kto, gdzie i jak.
**Nagroda**: money=100
**Nagroda**: max_health=20

## Q03_S01_WHO_HAS_MORE_KNOWLEDGE

**Tytuł**: Kto ma wiedzę o magii?

Barman wspomniał, że ktoś w miasteczku zna się na klątwach.

**Completion**: test
**Test**: visited("POTIONEER_PUZZLEMINT", "014") or visited("POTIONEER_PUZZLEMINT", "017")
**Sukces**: Puzzlemint wie więcej, niż chciałby przyznać.

## Q03_S02_WHERE_TO_FIND_THIS_PERSON

**Tytuł**: Gdzie znaleźć tę osobę?

Wiedza to jedno, adres to drugie.

**Completion**: test
**Test**: visited("HAMMER_HOAXHEART", "009")
**Sukces**: Kowal narysował mapkę. Na piasku. Palcem.
"""

Q03_EN = """---
aliases:
  - Q03_S00_LEARN_ABOUT_CURSE
---

# Find someone who knows about curses

## Q03_S00_LEARN_ABOUT_CURSE

**Title**: Find someone who knows about curses

Someone in this town must know how curses come off.

**Success**: You now know who, where and how.

## Q03_S01_WHO_HAS_MORE_KNOWLEDGE

**Title**: Who knows about magic?

The barman mentioned someone in town knows about curses.

**Success**: Puzzlemint knows more than he would admit.

## Q03_S02_WHERE_TO_FIND_THIS_PERSON

**Title**: Where to find this person?

Knowledge is one thing, an address is another.

**Success**: The smith drew a map. In the sand. With a finger.
"""


def _make_vault(root: Path, files: dict[str, str]) -> Path:
    """files maps 'PL/Misje/Name.md' -> content."""
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _full_vault(root: Path) -> Path:
    return _make_vault(
        root,
        {
            "PL/Misje/O co tu chodzi.md": Q00_PL,
            "EN/Quests/What is going on.md": Q00_EN,
            "PL/Misje/Znajdz kogos kto wie o klatwach.md": Q03_PL,
            "EN/Quests/Find someone who knows about curses.md": Q03_EN,
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


def test_imports_a_chain() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        vault = _full_vault(Path(tmp))
        messages, quests = import_quests(vault, [Q00_KEY, Q03_KEY])

    assert_eq(len(quests), 4, "four quests across two chains")
    assert_true("Q00_S00_WHAT_IS_GOING_ON" in quests, "chain key + section = quest key")
    assert_true("Q03_S01_WHO_HAS_MORE_KNOWLEDGE" in quests, "subquest key")

    step = quests["Q03_S01_WHO_HAS_MORE_KNOWLEDGE"]
    assert_eq(step["completion"], "test", "completion parsed")
    assert_eq(
        step["test"],
        'visited("POTIONEER_PUZZLEMINT", "014") or visited("POTIONEER_PUZZLEMINT", "017")',
        "test preserved verbatim",
    )
    # D1: the file is the thread, so parent is implied
    assert_eq(step["parent"], "Q03_S00_LEARN_ABOUT_CURSE", "parent implied by the file")
    assert_true("parent" not in quests["Q03_S00_LEARN_ABOUT_CURSE"], "umbrella has no parent")
    # cross-chain edges stay explicit
    assert_eq(
        quests["Q03_S00_LEARN_ABOUT_CURSE"]["requires"],
        ["Q00_S00_WHAT_IS_GOING_ON"],
        "requires parsed",
    )


def test_rewards_are_a_list_in_order() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _, quests = import_quests(_full_vault(Path(tmp)), [Q00_KEY, Q03_KEY])

    rewards = quests["Q03_S00_LEARN_ABOUT_CURSE"]["rewards"]
    assert_eq(len(rewards), 2, "both **Nagroda** lines kept")
    assert_eq(rewards[0], {"category": "money", "value": 100}, "first reward")
    assert_eq(rewards[1], {"category": "max_health", "value": 20}, "second reward")


def test_messages_carry_both_languages() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        messages, quests = import_quests(_full_vault(Path(tmp)), [Q00_KEY, Q03_KEY])

    key = "Q00_S00_WHAT_IS_GOING_ON"
    name_key = f"{MESSAGE_PREFIX}{key}_NAME"
    # quests hold i18n keys, never text (D3)
    assert_eq(quests[key]["name"], name_key, "quest points at a message key")
    assert_eq(messages["PL"][name_key], "O co tu chodzi?", "PL title")
    assert_eq(messages["EN"][name_key], "What is going on?", "EN title")
    assert_eq(
        messages["PL"][f"{MESSAGE_PREFIX}{key}_DESCRIPTION"],
        "Miecz gada. Miecz gada i nie zamierza przestać.",
        "prose becomes the description",
    )
    assert_eq(
        messages["EN"][f"{MESSAGE_PREFIX}{key}_SUCCESS"],
        "Fine. The sword talks, and you have a problem.",
        "EN success",
    )


def test_machine_fields_are_read_from_pl_only() -> None:
    """The whole point of D2: an LLM regenerating EN cannot break the logic."""
    sabotaged_en = Q00_EN.replace(
        "**Success**:", '**Test**: visited("WRONG_NPC", "999")\n**Success**:'
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(
            Path(tmp),
            {"PL/Misje/a.md": Q00_PL, "EN/Quests/a.md": sabotaged_en},
        )
        _, quests = import_quests(vault, [Q00_KEY])

    assert_eq(
        quests["Q00_S00_WHAT_IS_GOING_ON"]["test"],
        'visited("CLAPBACK_SWORD", "015")',
        "PL test wins; the EN one is ignored",
    )


def test_invalid_test_names_the_file_and_line() -> None:
    """DoD: a broken condition fails the import loudly, pointing at the source."""
    broken = Q00_PL.replace(
        '**Test**: visited("CLAPBACK_SWORD", "015")', "**Test**: agility > 3"
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(Path(tmp), {"PL/Misje/a.md": broken, "EN/Quests/a.md": Q00_EN})
        _expect_import_error(
            lambda: import_quests(vault, [Q00_KEY]), "a.md", "unknown name in a test"
        )


def test_quest_scope_is_enforced_at_import() -> None:
    """`selected()` and a bare `visited()` are dialog-only — catch them at authoring time."""
    for bad_test in ('**Test**: selected("SOME_OPTION")', '**Test**: visited("015")'):
        broken = Q00_PL.replace('**Test**: visited("CLAPBACK_SWORD", "015")', bad_test)
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(Path(tmp), {"PL/Misje/a.md": broken, "EN/Quests/a.md": Q00_EN})
            _expect_import_error(
                lambda: import_quests(vault, [Q00_KEY]), "invalid Test", f"rejected: {bad_test}"
            )


def test_graph_problems_fail_the_import() -> None:
    """init_quests runs on the merged set: dangling requires cannot slip through."""
    dangling = Q03_PL.replace(
        "**Requires**: [[Q00_S00_WHAT_IS_GOING_ON]]", "**Requires**: Q99_DOES_NOT_EXIST"
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(
            Path(tmp),
            {
                "PL/Misje/O co tu chodzi.md": Q00_PL,
                "EN/Quests/What is going on.md": Q00_EN,
                "PL/Misje/b.md": dangling,
                "EN/Quests/b.md": Q03_EN,
            },
        )
        _expect_import_error(
            lambda: import_quests(vault, [Q00_KEY, Q03_KEY]), "Q99_DOES_NOT_EXIST", "dangling requires"
        )


def test_untranslated_section_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(
            Path(tmp),
            {
                "PL/Misje/a.md": Q03_PL,
                "EN/Quests/a.md": Q03_EN.replace("## Q03_S02_WHERE_TO_FIND_THIS_PERSON", "## Q03_S99_EXTRA"),
            },
        )
        _expect_import_error(
            lambda: import_quests(vault, [Q03_KEY]), "section mismatch", "PL/EN mismatch"
        )


def test_missing_pieces_fail_with_a_useful_message() -> None:
    cases = [
        (Q00_PL.replace("**Tytuł**: O co tu chodzi?\n", ""), "Tytuł", "missing title"),
        (Q00_PL.replace("**Sukces**: No dobrze. Miecz gada, a ty masz problem.\n", ""), "Sukces", "missing success"),
        (Q00_PL.replace("**Completion**: test\n", ""), "Completion", "missing completion"),
        (Q00_PL.replace("**Nagroda**: money=50", "**Nagroda**: money=dużo"), "whole number", "bad reward value"),
        (Q00_PL.replace("**Nagroda**: money=50", "**Nagroda**: 50 money"), "category", "bad reward shape"),
        (Q00_PL.replace("**Tytuł**:", "**Naglowek**:"), "unknown field", "unknown field name"),
    ]
    for source, needle, label in cases:
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(Path(tmp), {"PL/Misje/a.md": source, "EN/Quests/a.md": Q00_EN})
            _expect_import_error(lambda: import_quests(vault, [Q00_KEY]), needle, label)


def test_alias_must_name_a_section() -> None:
    """The alias *is* the umbrella's key, so it has to name a heading in the file.

    Replaces the old "chain has no S00 section" check: the umbrella is now named
    outright instead of being spotted by a magic prefix.
    """
    orphan = Q00_PL.replace("## Q00_S00_WHAT_IS_GOING_ON", "## Q00_S01_WHAT_IS_GOING_ON")
    orphan_en = Q00_EN.replace("## Q00_S00_WHAT_IS_GOING_ON", "## Q00_S01_WHAT_IS_GOING_ON")
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(Path(tmp), {"PL/Misje/a.md": orphan, "EN/Quests/a.md": orphan_en})
        _expect_import_error(
            lambda: import_quests(vault, [Q00_KEY]), "names no section", "alias names nothing"
        )


def test_headings_are_the_config_keys() -> None:
    """No composition: what the heading says is what the game gets.

    The old scheme glued ``<alias>_<section>``, so two different quests read as
    near-identical headings across files (``S01_LEARN_ABOUT_CURSE`` in Q01 vs
    ``S00_LEARN_ABOUT_CURSE`` in Q03) and a vault-wide search hit both.
    """
    with tempfile.TemporaryDirectory() as tmp:
        _, quests = import_quests(_full_vault(Path(tmp)), [Q00_KEY, Q03_KEY])

    for key in quests:
        assert_true(key.startswith("Q0"), f"every key carries its chain: {key}")
    assert_true(Q03_KEY in quests, "the umbrella is keyed by its heading, verbatim")
    assert_true("parent" not in quests[Q03_KEY], "the umbrella takes no parent")
    assert_eq(
        quests["Q03_S01_WHO_HAS_MORE_KNOWLEDGE"]["parent"], Q03_KEY, "a step parents to the alias"
    )


def test_every_requires_spelling_means_the_same_edge() -> None:
    """Bare key, chain-note link, alias+heading, alias with display text - one key.

    Which one an author writes is an Obsidian concern (``[[#X]]`` only resolves
    inside the current note, so a cross-chain edge cannot use it), and the graph
    must not be able to tell them apart.
    """
    for spelling in (
        "Q00_S00_WHAT_IS_GOING_ON",
        "[[Q00_S00_WHAT_IS_GOING_ON]]",
        "[[Q00_S00_WHAT_IS_GOING_ON#Q00_S00_WHAT_IS_GOING_ON]]",
        "[[Q00_S00_WHAT_IS_GOING_ON|o co tu chodzi]]",
    ):
        source = Q03_PL.replace(
            "**Requires**: [[Q00_S00_WHAT_IS_GOING_ON]]", f"**Requires**: {spelling}"
        )
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(
                Path(tmp),
                {
                    "PL/Misje/O co tu chodzi.md": Q00_PL,
                    "EN/Quests/What is going on.md": Q00_EN,
                    "PL/Misje/b.md": source,
                    "EN/Quests/b.md": Q03_EN,
                },
            )
            _, quests = import_quests(vault, [Q00_KEY, Q03_KEY])
            assert_eq(quests[Q03_KEY]["requires"], [Q00_KEY], f"same edge: {spelling}")


def test_a_same_file_requires_link_resolves() -> None:
    """``[[#KEY]]`` - the only form Obsidian resolves inside one note."""
    source = Q03_PL.replace(
        '**Test**: visited("HAMMER_HOAXHEART", "009")',
        '**Requires**: [[#Q03_S01_WHO_HAS_MORE_KNOWLEDGE]]\n'
        '**Test**: visited("HAMMER_HOAXHEART", "009")',
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(
            Path(tmp),
            {
                "PL/Misje/O co tu chodzi.md": Q00_PL,
                "EN/Quests/What is going on.md": Q00_EN,
                "PL/Misje/b.md": source,
                "EN/Quests/b.md": Q03_EN,
            },
        )
        _, quests = import_quests(vault, [Q00_KEY, Q03_KEY])
        assert_eq(
            quests["Q03_S02_WHERE_TO_FIND_THIS_PERSON"]["requires"],
            ["Q03_S01_WHO_HAS_MORE_KNOWLEDGE"],
            "names a step in the same file",
        )


def test_a_broken_wikilink_in_requires_fails() -> None:
    source = Q03_PL.replace(
        "**Requires**: [[Q00_S00_WHAT_IS_GOING_ON]]", "**Requires**: [[Q00_S00_WHAT_IS_GOING_ON"
    )
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(Path(tmp), {"PL/Misje/a.md": source, "EN/Quests/a.md": Q03_EN})
        _expect_import_error(
            lambda: import_quests(vault, [Q03_KEY]), "broken wikilink", "unclosed [["
        )


def test_the_qxx_shorthand_resolves_at_the_cli() -> None:
    """``just import-quests Q03`` beats typing the umbrella key from memory.

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
        assert_true(Q03_KEY in config["quests"], "and imported the right ones")


def test_build_writes_config_and_leaves_dialogs_alone() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        vault = _full_vault(root)
        config_path = root / "config.json"
        config_path.write_text(json.dumps(_fixture_config()), encoding="utf-8")

        rc = build_quest_config(src_dir=vault, config_path=config_path, chains=[Q00_KEY, Q03_KEY])
        assert_eq(rc, 0, "import succeeded")

        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert_eq(len(config["quests"]), 4, "quests written")
        assert_true("M_SOMEONE_DN_000" in config["messages"]["PL"], "dialog messages untouched")
        assert_true(
            f"{MESSAGE_PREFIX}Q00_S00_WHAT_IS_GOING_ON_NAME" in config["messages"]["PL"],
            "quest messages written",
        )
        assert_true("dialogs" in config, "dialogs section preserved")


def test_failed_import_leaves_config_untouched() -> None:
    """All or nothing: a half-imported quest set is a silently broken game."""
    broken = Q00_PL.replace('**Test**: visited("CLAPBACK_SWORD", "015")', "**Test**: nonsense(1)")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        vault = _make_vault(root, {"PL/Misje/a.md": broken, "EN/Quests/a.md": Q00_EN})
        config_path = root / "config.json"
        original = json.dumps({"messages": {"PL": {}, "EN": {}}, "quests": {"OLD": {}}})
        config_path.write_text(original, encoding="utf-8")

        rc = build_quest_config(src_dir=vault, config_path=config_path, chains=[Q00_KEY])

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

        build_quest_config(src_dir=vault, config_path=config_path, chains=[Q00_KEY, Q03_KEY])

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

        build_quest_config(src_dir=vault, config_path=config_path, chains=[Q00_KEY, Q03_KEY])
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
        "Q01_S05": {
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
        "Q01_S05": {
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

        rc = build_quest_config(src_dir=vault, config_path=config_path, chains=[Q00_KEY])

        assert_eq(rc, 1, "import reports failure")
        assert_eq(config_path.read_text(encoding="utf-8"), original, "config.json byte-identical")


def test_no_sources_is_not_an_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        rc = build_quest_config(src_dir=Path(tmp), config_path=Path(tmp) / "config.json")
        assert_eq(rc, 0, "an empty vault is a no-op, not a failure")


def main() -> None:
    tests = [
        test_imports_a_chain,
        test_rewards_are_a_list_in_order,
        test_messages_carry_both_languages,
        test_machine_fields_are_read_from_pl_only,
        test_invalid_test_names_the_file_and_line,
        test_quest_scope_is_enforced_at_import,
        test_graph_problems_fail_the_import,
        test_untranslated_section_fails,
        test_missing_pieces_fail_with_a_useful_message,
        test_alias_must_name_a_section,
        test_headings_are_the_config_keys,
        test_every_requires_spelling_means_the_same_edge,
        test_a_same_file_requires_link_resolves,
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
