#!/usr/bin/env python3
"""Smoke tests for dialog/markdown_importer.py (T-024).

Run from the project root:
    .venv/bin/python tests/test_dialog_import.py

Pure logic (no pygame / SDL). Imports the Hammer Hoaxheart dialog from the
RPG prototype Markdown source and verifies the generated config shape,
markup/emoji conversion (D3), condition conversion to the mini-DSL, and that
``dialog.graph.init_dialog`` accepts the output.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))

from dialog import init_dialog
from dialog.markdown_importer import (
    DialogImportError,
    _convert_text,
    _make_name_resolver,
    import_character_dialog,
    import_dialogs,
    load_valid_items,
    )

RPG_DIALOGS = Path("/Users/hubertnafalski/Projects/RPG/dialogs")
ITEMS_CSV = Path("project/config_model/items.csv")
_HAS_RPG_SOURCES = RPG_DIALOGS.exists()


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def test_import_hammer_shape() -> None:
    messages, cfg = import_character_dialog(RPG_DIALOGS, "Hammer Hoaxheart")

    assert_true("HAMMER_HOAXHEART" in cfg, "character key present")
    char_cfg = cfg["HAMMER_HOAXHEART"]

    assert_eq(char_cfg["START_NODE"], "000", "start node")
    assert_true(len(char_cfg["DIALOG_NODES"]) > 0, "has nodes")
    assert_true(len(char_cfg["DIALOG_OPTIONS"]) > 0, "has options")
    assert_true(len(char_cfg["NODES_OPTIONS"]) > 0, "has node->option mapping")

    assert_true("PL" in messages and "EN" in messages, "both languages")
    assert_true(
        "M_HAMMER_HOAXHEART_DN_000" in messages["PL"],
        "PL node message key",
    )
    assert_true(
        "M_HAMMER_HOAXHEART_DO_000to001_1" in messages["PL"],
        "PL option message key",
    )


def test_hammer_graph_builds() -> None:
    messages, cfg = import_character_dialog(RPG_DIALOGS, "Hammer Hoaxheart")
    nodes = init_dialog(cfg["HAMMER_HOAXHEART"])
    assert_eq(nodes["000"].key, "000", "start node built")
    assert_true(len(nodes["000"].options) > 0, "start has options")


def test_sentiment_conversion() -> None:
    messages, cfg = import_character_dialog(RPG_DIALOGS, "Hammer Hoaxheart")
    option = cfg["HAMMER_HOAXHEART"]["DIALOG_OPTIONS"]["000to001_1"]
    assert_eq(option["sentiment"], "blessed", "😇 -> blessed")
    assert_eq(option["condition"], "True", "default condition")
    assert_eq(option["order"], 1, "order parsed")
    assert_eq(option["next_node"], "001", "target parsed")


def test_markup_conversion() -> None:
    messages, cfg = import_character_dialog(RPG_DIALOGS, "Hammer Hoaxheart")
    # bold -> shadow
    text_pl = messages["PL"]["M_HAMMER_HOAXHEART_DO_990to000_9"]
    assert_true("[shadow]DEBUG[/shadow]" in text_pl, "** -> [shadow]")
    # italic -> italic
    text_pl = messages["PL"]["M_HAMMER_HOAXHEART_DO_004to009_2"]
    assert_true(
        "[italic]wielcy panicze[/italic]" in text_pl,
        "_ -> [italic]",
    )


def test_condition_conversion() -> None:
    items = load_valid_items(ITEMS_CSV)
    messages, cfg = import_character_dialog(
        RPG_DIALOGS, "Barman Absinthrayner", valid_items=items
    )
    option = cfg["BARMAN_ABSINTHRAYNER"]["DIALOG_OPTIONS"]["004to010_1"]
    assert_eq(
        option["condition"],
        'not visited("POTIONEER_PUZZLEMINT", "004") and '
        'not visited("HAMMER_HOAXHEART", "004")',
        "cross-npc visited conversion",
    )

    messages, cfg = import_character_dialog(
        RPG_DIALOGS, "Potioneer Puzzlemint", valid_items=items
    )
    option = cfg["POTIONEER_PUZZLEMINT"]["DIALOG_OPTIONS"]["012to014_2"]
    assert_eq(
        option["condition"],
        "sentiment>=42",
        "character.sentiment conversion",
    )


def test_result_parsing() -> None:
    items = load_valid_items(ITEMS_CSV)
    messages, cfg = import_character_dialog(
        RPG_DIALOGS, "Potioneer Puzzlemint", valid_items=items
    )
    result = cfg["POTIONEER_PUZZLEMINT"]["NODE_RESULTS"][
        "POTIONEER_PUZZLEMINT_NR_991"
    ]
    assert_eq(result["category"], "sentiment_shift", "result category")
    assert_eq(result["value"], -10, "sentiment shift value")


def test_import_multiple_characters() -> None:
    items = load_valid_items(ITEMS_CSV)
    messages, cfg = import_dialogs(
        RPG_DIALOGS,
        ["Hammer Hoaxheart", "Barman Absinthrayner"],
        valid_items=items,
    )
    assert_true("HAMMER_HOAXHEART" in cfg, "hammer present")
    assert_true("BARMAN_ABSINTHRAYNER" in cfg, "barman present")
    assert_true(
        len(messages["PL"]) > len(
            {"M_HAMMER_HOAXHEART_DN_000": ""}
        ),
        "merged messages",
    )


def test_missing_file_raises() -> None:
    try:
        import_character_dialog(RPG_DIALOGS, "Nonexistent Character")
    except DialogImportError as exc:
        assert_true("file not found" in str(exc), "missing file error")
        return
    raise AssertionError("expected DialogImportError for missing file")


def test_make_name_resolver_pl() -> None:
    chars = {
        "HAMMER_HOAXHEART": {"name_PL": "Młot Hoaxheart", "name_EN": "Hammer Hoaxheart"},
    }
    resolve = _make_name_resolver(chars, "PL")
    assert resolve is not None
    assert_eq(resolve("HAMMER_HOAXHEART"), "Młot Hoaxheart")


def test_make_name_resolver_en() -> None:
    chars = {
        "HAMMER_HOAXHEART": {"name_PL": "Młot Hoaxheart", "name_EN": "Hammer Hoaxheart"},
    }
    resolve = _make_name_resolver(chars, "EN")
    assert resolve is not None
    assert_eq(resolve("HAMMER_HOAXHEART"), "Hammer Hoaxheart")


def test_make_name_resolver_empty() -> None:
    assert _make_name_resolver({}, "PL") is None
    assert _make_name_resolver({}, "EN") is None


def test_make_name_resolver_unknown_key() -> None:
    chars = {"ARIA_SILVERSTONE": {"name_EN": "Aria Silverstone"}}
    resolve = _make_name_resolver(chars, "EN")
    assert resolve is not None
    assert_eq(resolve("UNKNOWN_KEY"), "[[UNKNOWN_KEY]]")


def test_convert_text_no_resolver() -> None:
    result = _convert_text("Hello [[HAMMER_HOAXHEART]]")
    assert_eq(result, "Hello [[HAMMER_HOAXHEART]]", "no resolver leaves wikilink as-is")


def test_convert_text_resolve_known() -> None:
    chars = {"ARIA_SILVERSTONE": {"name_EN": "Aria Silverstone"}}
    resolve = _make_name_resolver(chars, "EN")
    assert resolve is not None
    result = _convert_text("Go see [[ARIA_SILVERSTONE]] for help.", resolve)
    assert_eq(result, "Go see [char]Aria Silverstone[/char] for help.")


def test_convert_text_resolve_unknown() -> None:
    chars = {"ARIA_SILVERSTONE": {"name_EN": "Aria Silverstone"}}
    resolve = _make_name_resolver(chars, "EN")
    assert resolve is not None
    result = _convert_text("Talk to [[MISSING_NPC]] now.", resolve)
    assert_eq(result, "Talk to [[MISSING_NPC]] now.")


def test_convert_text_resolve_pipe_format() -> None:
    chars = {"HAMMER_HOAXHEART": {"name_PL": "Kowal Klamca"}}
    resolve = _make_name_resolver(chars, "PL")
    assert resolve is not None
    result = _convert_text("Pytaj [[PL/Hammer_Hoaxheart|HAMMER_HOAXHEART]].", resolve)
    assert_eq(result, "Pytaj [char]Kowal Klamca[/char].")


def test_convert_text_with_markup_and_wikilink() -> None:
    chars = {"HAMMER_HOAXHEART": {"name_EN": "Hammer Hoaxheart"}}
    resolve = _make_name_resolver(chars, "EN")
    assert resolve is not None
    result = _convert_text("Ask **[[HAMMER_HOAXHEART]]** about it.", resolve)
    assert_eq(
        result,
        "Ask [shadow][char]Hammer Hoaxheart[/char][/shadow] about it.",
        "wikilink resolved inside bold markup",
    )


def main() -> None:
    tests = []

    if _HAS_RPG_SOURCES:
        tests = [
            ("test_import_hammer_shape", test_import_hammer_shape),
            ("test_hammer_graph_builds", test_hammer_graph_builds),
            ("test_sentiment_conversion", test_sentiment_conversion),
            ("test_markup_conversion", test_markup_conversion),
            ("test_condition_conversion", test_condition_conversion),
            ("test_result_parsing", test_result_parsing),
            ("test_import_multiple_characters", test_import_multiple_characters),
            ("test_missing_file_raises", test_missing_file_raises),
        ]
    else:
        print("  SKIP  RPG sources not found, skipping RPG-dependent tests")

    self_contained_tests = [
        ("test_make_name_resolver_pl", test_make_name_resolver_pl),
        ("test_make_name_resolver_en", test_make_name_resolver_en),
        ("test_make_name_resolver_empty", test_make_name_resolver_empty),
        ("test_make_name_resolver_unknown_key", test_make_name_resolver_unknown_key),
        ("test_convert_text_no_resolver", test_convert_text_no_resolver),
        ("test_convert_text_resolve_known", test_convert_text_resolve_known),
        ("test_convert_text_resolve_unknown", test_convert_text_resolve_unknown),
        ("test_convert_text_with_markup_and_wikilink", test_convert_text_with_markup_and_wikilink),
        ("test_convert_text_resolve_pipe_format", test_convert_text_resolve_pipe_format),
    ]
    tests.extend(self_contained_tests)
    for name, func in tests:
        func()
        print(f"  PASS  {name}")
    print(f"\nAll {len(tests)} dialog import tests passed.")


if __name__ == "__main__":
    main()
