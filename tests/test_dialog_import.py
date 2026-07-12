#!/usr/bin/env python3
"""Smoke tests for dialog/markdown_importer.py (T-024).

Run from the project root:
    .venv/bin/python tests/test_dialog_import.py

Pure logic (no pygame / SDL). Imports character dialogs from the doc/
Obsidian vault (PL/Postacie + EN/Characters, discovery by frontmatter
aliases) and verifies the generated config shape, markup/emoji conversion
(D3), canonical sentiment names (kind/weak/...), frontmatter metadata
(sprite/friendly/disposition), condition conversion to the mini-DSL, and
that ``dialog.graph.init_dialog`` accepts the output.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))

from dialog import init_dialog
from dialog.markdown_importer import (
    DialogImportError,
    _NODE_HEADING_RE,
    _OPTION_RE,
    _RESUME_LINK_RE,
    _convert_text,
    _make_name_resolver,
    _parse_frontmatter,
    import_character_dialog,
    import_dialogs,
    load_valid_items,
    )

VAULT = Path(__file__).resolve().parent.parent / "doc"
ITEMS_CSV = Path("project/config_model/items.csv")
_HAS_VAULT = (VAULT / "PL" / "Postacie").exists()


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def test_import_hammer_shape() -> None:
    messages, cfg, meta = import_character_dialog(VAULT, "Hammer Hoaxheart")

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


def test_frontmatter_meta() -> None:
    """PL frontmatter is the source of truth for sprite/friendly/weights."""
    _, _, meta = import_character_dialog(VAULT, "Hammer Hoaxheart")
    assert_eq(meta["sprite"], "Villager2", "sprite from frontmatter")
    assert_eq(meta["friendly"], 0.3, "friendly from frontmatter")
    assert_eq(
        meta["disposition"],
        {"kind": -1, "weak": 1, "angry": 2, "smart": -1, "funny": -2},
        "disposition weights from frontmatter",
    )


def test_hammer_graph_builds() -> None:
    messages, cfg, _ = import_character_dialog(VAULT, "Hammer Hoaxheart")
    nodes = init_dialog(cfg["HAMMER_HOAXHEART"])
    assert_eq(nodes["000"].key, "000", "start node built")
    assert_true(len(nodes["000"].options) > 0, "start has options")


def test_sentiment_conversion() -> None:
    messages, cfg, _ = import_character_dialog(VAULT, "Hammer Hoaxheart")
    option = cfg["HAMMER_HOAXHEART"]["DIALOG_OPTIONS"]["000to001_1"]
    assert_eq(option["sentiment"], "kind", "😇 -> kind (canonical name)")
    assert_eq(option["condition"], "True", "default condition")
    assert_eq(option["order"], 1, "order parsed")
    assert_eq(option["next_node"], "001", "target parsed")


def test_markup_conversion() -> None:
    items = load_valid_items(ITEMS_CSV)
    messages, cfg, _ = import_character_dialog(
        VAULT, "Barman Absinthrayner", valid_items=items
    )
    # bold -> shadow
    text_pl = messages["PL"]["M_BARMAN_ABSINTHRAYNER_DO_000to001_3"]
    assert_true("[shadow]Twoim[/shadow]" in text_pl, "** -> [shadow]")
    # sentiment emoji in text -> emote sprite tag
    messages, cfg, _ = import_character_dialog(VAULT, "Hammer Hoaxheart")
    text_pl = messages["PL"]["M_HAMMER_HOAXHEART_DO_004to009_2"]
    assert_true(
        "[italic]wielcy panicze[/italic]" in text_pl,
        "_ -> [italic]",
    )


def test_condition_conversion() -> None:
    items = load_valid_items(ITEMS_CSV)
    messages, cfg, _ = import_character_dialog(
        VAULT, "Barman Absinthrayner", valid_items=items
    )
    option = cfg["BARMAN_ABSINTHRAYNER"]["DIALOG_OPTIONS"]["004to010_1"]
    assert_eq(
        option["condition"],
        'not visited("POTIONEER_PUZZLEMINT", "004") and '
        'not visited("HAMMER_HOAXHEART", "004")',
        "cross-npc visited conversion",
    )

    messages, cfg, _ = import_character_dialog(
        VAULT, "Potioneer Puzzlemint", valid_items=items
    )
    option = cfg["POTIONEER_PUZZLEMINT"]["DIALOG_OPTIONS"]["012to014_2"]
    assert_eq(
        option["condition"],
        "sentiment>=42",
        "character.sentiment conversion",
    )


def test_result_parsing() -> None:
    items = load_valid_items(ITEMS_CSV)
    messages, cfg, _ = import_character_dialog(
        VAULT, "Potioneer Puzzlemint", valid_items=items
    )
    result = cfg["POTIONEER_PUZZLEMINT"]["NODE_RESULTS"][
        "POTIONEER_PUZZLEMINT_NR_991"
    ]
    assert_eq(result["category"], "sentiment_shift", "result category")
    assert_eq(result["value"], -10, "sentiment shift value")


def test_import_multiple_characters() -> None:
    items = load_valid_items(ITEMS_CSV)
    messages, cfg, meta = import_dialogs(
        VAULT,
        ["Hammer Hoaxheart", "Barman Absinthrayner"],
        valid_items=items,
    )
    assert_true("HAMMER_HOAXHEART" in cfg, "hammer present")
    assert_true("BARMAN_ABSINTHRAYNER" in cfg, "barman present")
    assert_true("BARMAN_ABSINTHRAYNER" in meta, "barman meta present")
    assert_eq(meta["BARMAN_ABSINTHRAYNER"]["sprite"], "Hunter", "barman sprite")
    assert_true(
        len(messages["PL"]) > len(
            {"M_HAMMER_HOAXHEART_DN_000": ""}
        ),
        "merged messages",
    )


def test_missing_file_raises() -> None:
    try:
        import_character_dialog(VAULT, "Nonexistent Character")
    except DialogImportError as exc:
        assert_true("no Markdown file with alias" in str(exc), "missing file error")
        return
    raise AssertionError("expected DialogImportError for missing file")


def test_parse_frontmatter() -> None:
    fm = _parse_frontmatter(
        "---\n"
        "aliases:\n"
        "  - HAMMER_HOAXHEART\n"
        "location: \"[[Gafowo Kolonia]]\"\n"
        "sprite: Villager2\n"
        "friendly: 0.3\n"
        "kind: -1\n"
        "weak: 1\n"
        "angry: 2\n"
        "smart: -1\n"
        "funny: -2\n"
        "---\n"
        "# Info\n"
    )
    assert_eq(fm.aliases, ["HAMMER_HOAXHEART"], "aliases parsed")
    assert_eq(fm.sprite, "Villager2", "sprite parsed")
    assert_eq(fm.friendly, 0.3, "friendly parsed")
    assert_eq(fm.weights["angry"], 2, "weight parsed")


def test_make_name_resolver_pl() -> None:
    chars = {
        "HAMMER_HOAXHEART": {"name_PL": "Kowal Kłamca", "name_EN": "Hammer Hoaxheart"},
    }
    resolve = _make_name_resolver(chars, "PL")
    assert resolve is not None
    assert_eq(resolve("HAMMER_HOAXHEART", None), "Kowal Kłamca")
    assert_eq(resolve("Kowal Kłamca", None), "Kowal Kłamca", "resolve by name")


def test_make_name_resolver_en() -> None:
    chars = {
        "HAMMER_HOAXHEART": {"name_PL": "Kowal Kłamca", "name_EN": "Hammer Hoaxheart"},
    }
    resolve = _make_name_resolver(chars, "EN")
    assert resolve is not None
    assert_eq(resolve("HAMMER_HOAXHEART", None), "Hammer Hoaxheart")


def test_make_name_resolver_declension() -> None:
    """Pipe text carries the grammatical form to display in-game."""
    chars = {
        "BARMAN_ABSINTHRAYNER": {"name_PL": "Barman Absyntnent", "name_EN": "Barman Absinthrayner"},
    }
    resolve = _make_name_resolver(chars, "PL")
    assert resolve is not None
    assert_eq(
        resolve("Barman Absyntnent", "Barmana Absyntnenta"),
        "Barmana Absyntnenta",
        "declension display kept",
    )
    # identifier-like pipe text (legacy link) falls back to canonical name
    assert_eq(
        resolve("Barman Absyntnent", "BARMAN_ABSINTHRAYNER"),
        "Barman Absyntnent",
        "key-like pipe ignored",
    )


def test_make_name_resolver_empty() -> None:
    assert _make_name_resolver({}, "PL") is None
    assert _make_name_resolver({}, "EN") is None


def test_make_name_resolver_unknown_key() -> None:
    chars = {"ARIA_SILVERSTONE": {"name_EN": "Aria Silverstone"}}
    resolve = _make_name_resolver(chars, "EN")
    assert resolve is not None
    assert_eq(resolve("UNKNOWN_KEY", None), None, "unknown -> None")


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


def test_convert_text_resolve_declension() -> None:
    chars = {"BARMAN_ABSINTHRAYNER": {"name_PL": "Barman Absyntnent"}}
    resolve = _make_name_resolver(chars, "PL")
    assert resolve is not None
    result = _convert_text(
        "Pytaj [[Barman Absyntnent|Barmana Absyntnenta]].", resolve
    )
    assert_eq(result, "Pytaj [char]Barmana Absyntnenta[/char].")


def test_convert_text_resolve_legacy_path_format() -> None:
    chars = {"HAMMER_HOAXHEART": {"name_PL": "Kowal Kłamca"}}
    resolve = _make_name_resolver(chars, "PL")
    assert resolve is not None
    result = _convert_text("Pytaj [[PL/Hammer_Hoaxheart|HAMMER_HOAXHEART]].", resolve)
    assert_eq(result, "Pytaj [char]Kowal Kłamca[/char].")


def test_node_heading_re() -> None:
    """Node headings are '## NNN' (preferred) or legacy '### NNN'."""
    m = _NODE_HEADING_RE.match("## 001")
    assert m is not None and m.group("key") == "001", "## digits matches"
    m = _NODE_HEADING_RE.match("## 990-end")
    assert m is not None and m.group("key") == "990-end", "## -end matches"
    m = _NODE_HEADING_RE.match("### 001")
    assert m is not None, "legacy ### still accepted"
    assert _NODE_HEADING_RE.match("## Cechy charakteru") is None, "prose heading ignored"
    assert _NODE_HEADING_RE.match("## PL") is None, "language heading ignored"


def test_option_re_new_format() -> None:
    """[[#KEY]] option format is parsed correctly."""
    line = "* [[#001]] 1😐: Some text"
    m = _OPTION_RE.match(line)
    assert m is not None, "new format matches"
    assert_eq(m.group("new_target"), "001", "new_target extracted")
    assert_eq(m.group("order"), "1", "order extracted")
    assert_eq(m.group("sentiment"), "😐", "sentiment extracted")
    assert_eq(m.group("text"), "Some text", "text extracted")


def test_option_re_new_format_with_condition() -> None:
    """[[#KEY]] with condition bracket is parsed."""
    line = '* [[#010]] 2[visited("003")]😐: Conditional option'
    m = _OPTION_RE.match(line)
    assert m is not None, "new format with condition matches"
    assert_eq(m.group("new_target"), "010", "target extracted")
    assert_eq(m.group("condition"), 'visited("003")', "condition extracted")


def test_option_re_new_format_end_node() -> None:
    """[[#KEY-end]] format targets an end node."""
    line = "* [[#990-end]] 9😐: Farewell"
    m = _OPTION_RE.match(line)
    assert m is not None, "end node format matches"
    assert_eq(m.group("new_target"), "990-end", "end target extracted")


def test_resume_link_re_new_format() -> None:
    """Standalone [[#KEY]] resume link is parsed."""
    line = "[[#011]]"
    m = _RESUME_LINK_RE.match(line)
    assert m is not None, "new resume format matches"
    assert_eq(m.group("new_target"), "011", "target extracted")


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

    if _HAS_VAULT:
        tests = [
            ("test_import_hammer_shape", test_import_hammer_shape),
            ("test_frontmatter_meta", test_frontmatter_meta),
            ("test_hammer_graph_builds", test_hammer_graph_builds),
            ("test_sentiment_conversion", test_sentiment_conversion),
            ("test_markup_conversion", test_markup_conversion),
            ("test_condition_conversion", test_condition_conversion),
            ("test_result_parsing", test_result_parsing),
            ("test_import_multiple_characters", test_import_multiple_characters),
            ("test_missing_file_raises", test_missing_file_raises),
        ]
    else:
        print("  SKIP  doc/ vault not found, skipping vault-dependent tests")

    self_contained_tests = [
        ("test_parse_frontmatter", test_parse_frontmatter),
        ("test_make_name_resolver_pl", test_make_name_resolver_pl),
        ("test_make_name_resolver_en", test_make_name_resolver_en),
        ("test_make_name_resolver_declension", test_make_name_resolver_declension),
        ("test_make_name_resolver_empty", test_make_name_resolver_empty),
        ("test_make_name_resolver_unknown_key", test_make_name_resolver_unknown_key),
        ("test_convert_text_no_resolver", test_convert_text_no_resolver),
        ("test_convert_text_resolve_known", test_convert_text_resolve_known),
        ("test_convert_text_resolve_unknown", test_convert_text_resolve_unknown),
        ("test_convert_text_resolve_declension", test_convert_text_resolve_declension),
        ("test_convert_text_with_markup_and_wikilink", test_convert_text_with_markup_and_wikilink),
        ("test_convert_text_resolve_legacy_path_format", test_convert_text_resolve_legacy_path_format),
        ("test_node_heading_re", test_node_heading_re),
        ("test_option_re_new_format", test_option_re_new_format),
        ("test_option_re_new_format_with_condition", test_option_re_new_format_with_condition),
        ("test_option_re_new_format_end_node", test_option_re_new_format_end_node),
        ("test_resume_link_re_new_format", test_resume_link_re_new_format),
    ]
    tests.extend(self_contained_tests)
    for name, func in tests:
        func()
        print(f"  PASS  {name}")
    print(f"\nAll {len(tests)} dialog import tests passed.")


if __name__ == "__main__":
    main()
