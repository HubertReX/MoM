"""Markdown -> dialog config importer (build-time tool, desktop only).

Port of RPG ``import_dialog_from_md.py`` with the improvements required by
Decision **D6**: one regex with named groups for options, graph validation
with ``file:line`` error reporting, and Decision **D3**: one-shot conversion
of RPG rich-markup / emoji to MoM ``RichText`` tags and ``:key:`` emotes.

The importer is pure logic (no pygame, no Pydantic) so it can be unit-tested
in isolation, but it is intended as a **build-time** tool: it reads source
Markdown and emits the ``messages`` / ``character_dialogs`` sections that
can be merged into ``config.json``.

Source MD files live in ``project/assets/dialogs/{EN,PL}/`` (naming
convention: ``Name_Surname.md``). Run ``just import-dialogs`` (or invoke
``python project/dialog/markdown_importer.py`` directly) to rebuild
``config_model/config.json`` from them. Characters whose format the importer
can parse are listed in ``IMPORTABLE_CHARACTERS``; non-compatible dialogs
(e.g. Madame Sarcasmia) are preserved untouched.

Output shape matches ``dialog.graph.init_dialog`` expectations:

.. code-block:: python

    character_dialogs[character_key] = {
        "DIALOG_NODES": {
            node_key: {
                "text": message_key,
                "is_final": bool,
                "result": result_key | None,
            }
        },
        "DIALOG_OPTIONS": {
            option_key: {
                "next_node": target_node_key,
                "text": message_key,
                "order": int,
                "condition": mini_dsl_string,
                "sentiment": emote_name,  # e.g. "blessed", "neutral"
            }
        },
        "NODES_OPTIONS": {node_key: [option_key, ...]},
        "NODE_RESULTS": {result_key: {...}},
        "START_NODE": first_node_key,
    }
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Allow running this file directly from project/dialog/ as a CLI tool.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from dialog.conditions import ConditionError, validate_condition


class DialogImportError(ValueError):
    """A dialog source Markdown is malformed.

    Carries ``file`` and ``line`` so callers can report ``file:line`` errors.
    """

    def __init__(self, message: str, *, file: str = "", line: int = 0) -> None:
        self.file = file
        self.line = line
        if file and line:
            super().__init__(f"{file}:{line}: {message}")
        elif file:
            super().__init__(f"{file}: {message}")
        else:
            super().__init__(message)


# ---------------------------------------------------------------------------
# Conversion tables (Decision D3)
# ---------------------------------------------------------------------------

from settings import SENTIMENT_EMOJI_TO_EMOTE

# emoji appearing inside node/option text -> inline :emote: tag
_EMOJI_TO_EMOTE_TAG: dict[str, str] = {
    emoji: f":{name}:"
    for emoji, name in SENTIMENT_EMOJI_TO_EMOTE.items()
}

# RPG rich tags -> MoM RichText tags
_TAG_CONVERSIONS: dict[str, str] = {
    "reverse": "shadow",
    "red": "error",
    "blue": "item",
    "yellow": "char",
}

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

# one regex with named groups (Decision D6)
_OPTION_RE = re.compile(
    r"^\*\s*"
    r"\[(?P<anchor>[^\]]+)\]"
    r"\(#(?P<target>[^)]+)\)"
    r"\s*(?P<order>\d+)"
    r"(?:\[(?P<condition>[^\]]+)\])?"
    r"(?P<sentiment>[^\s:]+)"
    r"\s*:\s*"
    r"(?P<text>.*)$"
)

# heading that starts a node: "### 000" or "### 990-end"
_NODE_HEADING_RE = re.compile(r"^###\s*(?P<key>[A-Za-z0-9_\-]+)$")

# bullet that carries node text: "* Some text..."
_NODE_TEXT_RE = re.compile(r"^\*\s+(?P<text>.+)$")

# result prefix embedded at the start of node text: [SENTIMENT-10], [MONEY+5]
_RESULT_RE = re.compile(
    r"^\[(?P<category>[A-Z]+)(?P<sign>[+-])(?P<rest>.+?)\]"
)

# condition conversion: character.sentiment -> sentiment
_SENTIMENT_COND_RE = re.compile(
    r"(?<![A-Za-z0-9_])character\.sentiment(?![A-Za-z0-9_])"
)

# condition conversion: NPC.node.visited / NPC.node.not_visited
_VISITED_NPC_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?P<npc>[A-Za-z_][A-Za-z0-9_]*)\."
    r"(?P<node>\d+)\."
    r"(?P<neg>not_)?visited"
    r"(?![A-Za-z0-9_])"
)

# condition conversion: node.visited / node.not_visited (current NPC)
_VISITED_SELF_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?P<node>\d+)\."
    r"(?P<neg>not_)?visited"
    r"(?![A-Za-z0-9_])"
)


@dataclass
class _ParsedOption:
    anchor: str
    target: str
    order: str
    condition: str | None
    sentiment: str
    text: str
    line_no: int


@dataclass
class _ParsedNode:
    key: str
    text_lines: list[str] = field(default_factory=list)
    is_final: bool = False
    options: list[_ParsedOption] = field(default_factory=list)
    line_no: int = 0
    _prev_empty: bool = field(default=True, repr=False)

    @property
    def text(self) -> str:
        return "\n\n".join(self.text_lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _find_markdown_file(src_dir: Path, lang: str, character_name: str) -> Path:
    lang_dir = src_dir / lang
    if not lang_dir.exists():
        raise DialogImportError(f"Language directory not found: {lang_dir}", file=str(lang_dir))

    # Try case-insensitive matching: char-<name>.md, chara-<name>.md, <name>.md
    normalized_name = character_name.replace(" ", "_").lower()
    candidates = (
        f"char-{normalized_name}.md",
        f"chara-{normalized_name}.md",
        f"{normalized_name}.md",
    )
    for p in lang_dir.iterdir():
        if p.is_file() and p.suffix == ".md":
            name_lower = p.name.lower()
            if name_lower in candidates:
                return p

    # Fallback to char- prefixed default
    character_key = _character_name_to_key(character_name)
    default = lang_dir / f"char-{character_key}.md"
    # Also try bare <KEY>.md as last resort
    bare = lang_dir / f"{character_key.lower()}.md"
    return bare if bare.exists() else default


def import_character_dialog(
    src_dir: Path,
    character_name: str,
    *,
    valid_items: set[str] | None = None,
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    """Import one character from RPG Markdown source.

    Reads ``PL/<Name>.md`` and ``EN/<Name>.md`` under ``src_dir``,
    validates the graph, converts markup and conditions, and returns
    ``(messages, character_dialogs)``.

    The importer looks for files in this order (case-insensitive):
    ``char-<name>.md``, ``chara-<name>.md``, ``<name>.md``.

    Args:
        src_dir: directory containing ``PL/`` and ``EN/`` subdirectories.
        character_name: canonical character name, e.g. ``"Hammer Hoaxheart"``.
        valid_items: optional set of item keys (from ``items.csv``) used to
            validate item names referenced by ``[ITEMS+...]`` node results.

    Returns:
        A tuple ``(messages, character_dialogs)`` where ``messages`` has the
        shape ``{lang: {key: text}}`` and ``character_dialogs`` has the shape
        described in the module docstring.
    """
    character_key = _character_name_to_key(character_name)
    pl_nodes = _parse_file(_find_markdown_file(src_dir, "PL", character_name))
    en_nodes = _parse_file(_find_markdown_file(src_dir, "EN", character_name))

    _validate_language_consistency(
        pl_nodes, en_nodes, character_name, str(src_dir)
    )

    messages: dict[str, dict[str, str]] = {"PL": {}, "EN": {}}
    dialog_config: dict[str, Any] = {
        character_key: {
            "DIALOG_NODES": {},
            "DIALOG_OPTIONS": {},
            "NODES_OPTIONS": {},
            "NODE_RESULTS": {},
            "START_NODE": "",
        }
    }

    start_node_set = False
    for node_key, pl_node in pl_nodes.items():
        en_node = en_nodes[node_key]

        if not start_node_set:
            dialog_config[character_key]["START_NODE"] = node_key
            start_node_set = True

        node_message_key = f"M_{character_key}_DN_{node_key}"
        result_key, pl_text = _extract_result(
            pl_node.text, node_key, character_key, valid_items
        )
        _, en_text = _extract_result(
            en_node.text, node_key, character_key, valid_items
        )

        messages["PL"][node_message_key] = _convert_text(pl_text)
        messages["EN"][node_message_key] = _convert_text(en_text)

        dialog_config[character_key]["DIALOG_NODES"][node_key] = {
            "is_final": pl_node.is_final,
            "result": result_key,
            "text": node_message_key,
        }

        if result_key:
            dialog_config[character_key]["NODE_RESULTS"][result_key] = (
                _build_result_dict(
                    result_key,
                    pl_node.text,
                    node_key,
                    character_key,
                    valid_items,
                )
            )

        node_options: list[str] = []
        for pl_opt, en_opt in zip(pl_node.options, en_node.options):
            option_key = (
                f"{node_key}to{pl_opt.target}_{pl_opt.order}"
            )
            option_message_key = (
                f"M_{character_key}_DO_{option_key}"
            )

            condition = _convert_condition(
                pl_opt.condition or "True",
                option_key,
                str(src_dir / "PL" / f"char-{character_key}.md"),
                pl_opt.line_no,
            )

            messages["PL"][option_message_key] = _convert_text(pl_opt.text)
            messages["EN"][option_message_key] = _convert_text(en_opt.text)

            dialog_config[character_key]["DIALOG_OPTIONS"][option_key] = {
                "next_node": pl_opt.target,
                "condition": condition,
                "sentiment": _convert_sentiment(pl_opt.sentiment),
                "order": int(pl_opt.order) if pl_opt.order.isdigit() else 0,
                "text": option_message_key,
            }
            node_options.append(option_key)

        dialog_config[character_key]["NODES_OPTIONS"][node_key] = node_options

    _validate_graph(
        pl_nodes,
        dialog_config[character_key],
        str(src_dir / "PL" / f"char-{character_key}.md"),
    )

    return messages, dialog_config


def import_dialogs(
    src_dir: Path,
    character_names: list[str],
    *,
    valid_items: set[str] | None = None,
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    """Import several characters and merge their configs.

    Args:
        src_dir: directory containing ``PL/`` and ``EN/`` subdirectories.
        character_names: list of canonical character names.
        valid_items: optional set of valid item keys.

    Returns:
        A tuple ``(messages, character_dialogs)`` with all characters merged.
    """
    messages: dict[str, dict[str, str]] = {"PL": {}, "EN": {}}
    character_dialogs: dict[str, Any] = {}

    for name in character_names:
        char_messages, char_dialog = import_character_dialog(
            src_dir, name, valid_items=valid_items
        )
        for lang in ("PL", "EN"):
            messages[lang].update(char_messages[lang])
        character_dialogs.update(char_dialog)

    return messages, character_dialogs


def load_valid_items(csv_path: Path) -> set[str]:
    """Load item keys from MoM ``items.csv`` (semicolon-delimited)."""
    keys: set[str] = set()
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            key = row.get("key", "").strip()
            if key:
                keys.add(key)
    return keys


# ---------------------------------------------------------------------------
# Full-config rebuild
# ---------------------------------------------------------------------------

# Default source directory for dialog Markdown files
_DEFAULT_DIALOG_SRC = _PROJECT_ROOT / "assets" / "dialogs"
# Default config.json path
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config_model" / "config.json"

# Characters whose Markdown format is supported by the importer.
IMPORTABLE_CHARACTERS: list[str] = [
    "Hammer Hoaxheart",
    "Barman Absinthrayner",
    "Clapback Sword",
    "Potioneer Puzzlemint",
    "Madame Sarcasmia",
]


def _collect_text_references(dialogs: dict[str, Any]) -> set[str]:
    """Collect all message-key references from a dialog config dict."""
    refs: set[str] = set()
    for dlg in dialogs.values():
        for node in dlg.get("DIALOG_NODES", {}).values():
            if node.get("text"):
                refs.add(node["text"])
        for opt in dlg.get("DIALOG_OPTIONS", {}).values():
            if opt.get("text"):
                refs.add(opt["text"])
    return refs


def build_dialog_config(
    src_dir: Path | None = None,
    config_path: Path | None = None,
    character_names: list[str] | None = None,
) -> int:
    """Rebuild dialog sections of ``config.json`` from Markdown sources.

    Reads the existing ``config.json``, imports each character in
    ``character_names`` from ``src_dir``, merges the generated
    ``messages`` and ``dialogs`` sections, preserves entries for
    characters not in the import list, removes orphaned message keys
    (not referenced by any dialog), and writes the file back.

    Args:
        src_dir: directory containing ``PL/`` and ``EN/`` subdirectories.
            Defaults to ``project/assets/dialogs/``.
        config_path: path to ``config.json``.
            Defaults to ``project/config_model/config.json``.
        character_names: list of canonical character names to import.
            Defaults to ``IMPORTABLE_CHARACTERS``.

    Returns:
        0 on success, 1 if any import failed.
    """
    import json

    if src_dir is None:
        src_dir = _DEFAULT_DIALOG_SRC
    if config_path is None:
        config_path = _DEFAULT_CONFIG_PATH
    if character_names is None:
        character_names = list(IMPORTABLE_CHARACTERS)

    if not config_path.exists():
        print(
            f"config.json not found: {config_path}",
            file=sys.stderr,
        )
        return 1

    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    existing_dialogs: dict[str, Any] = config.get("dialogs", {})
    existing_messages: dict[str, dict[str, str]] = config.get(
        "messages", {"PL": {}, "EN": {}}
    )

    items_csv = config_path.parent / "items.csv"
    valid_items = load_valid_items(items_csv) if items_csv.exists() else None

    new_messages: dict[str, dict[str, str]] = {"PL": {}, "EN": {}}
    new_dialogs: dict[str, Any] = {}
    imported: list[str] = []
    errors: list[str] = []

    for name in character_names:
        try:
            char_messages, char_dialog = import_character_dialog(
                src_dir, name, valid_items=valid_items
            )
            for lang in ("PL", "EN"):
                new_messages[lang].update(char_messages[lang])
            new_dialogs.update(char_dialog)
            imported.append(name)
        except DialogImportError as exc:
            errors.append(f"  {exc}")
        except Exception as exc:
            errors.append(f"  {name}: {exc}")

    if imported:
        print(f"Imported {len(imported)} character(s): {', '.join(imported)}")

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        print(
            "Preserving existing config entries for failed characters.",
            file=sys.stderr,
        )

    # Merge new content into existing
    for lang in ("PL", "EN"):
        existing_messages.setdefault(lang, {})
        existing_messages[lang].update(new_messages[lang])

    existing_dialogs.update(new_dialogs)

    # Remove orphaned message keys
    referenced = _collect_text_references(existing_dialogs)
    for lang in ("PL", "EN"):
        if lang in existing_messages:
            orphaned = set(existing_messages[lang]) - referenced
            for key in orphaned:
                del existing_messages[lang][key]
            if orphaned:
                print(f"Removed {len(orphaned)} orphaned message keys from {lang}")

    config["messages"] = existing_messages
    config["dialogs"] = existing_dialogs

    with config_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
        f.write("\n")

    print(f"Written: {config_path}")
    return 0 if not errors else 1


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _character_name_to_key(name: str) -> str:
    return name.upper().replace(" ", "_")


def _parse_file(path: Path) -> dict[str, _ParsedNode]:
    """Parse one Markdown file into an ordered dict of nodes."""
    if not path.exists():
        raise DialogImportError(f"file not found: {path}", file=str(path))

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    nodes: dict[str, _ParsedNode] = {}
    current_node: _ParsedNode | None = None
    in_language_section = False

    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip()

        # skip everything before the "## PL" / "## EN" section
        if line.startswith("## "):
            in_language_section = True
            continue
        if not in_language_section:
            continue

        node_match = _NODE_HEADING_RE.match(line)
        if node_match:
            node_key = node_match.group("key")
            is_final = node_key.endswith("-end")
            node_key = node_key.replace("-end", "")
            current_node = _ParsedNode(
                key=node_key,
                is_final=is_final,
                line_no=line_no,
            )
            if node_key in nodes:
                raise DialogImportError(
                    f"duplicate node {node_key!r}",
                    file=str(path),
                    line=line_no,
                )
            nodes[node_key] = current_node
            continue

        if current_node is None:
            continue

        option_match = _OPTION_RE.match(line)
        if option_match:
            current_node.options.append(
                _ParsedOption(
                    anchor=option_match.group("anchor"),
                    target=option_match.group("target").replace("-end", ""),
                    order=option_match.group("order"),
                    condition=option_match.group("condition"),
                    sentiment=option_match.group("sentiment"),
                    text=option_match.group("text").strip(),
                    line_no=line_no,
                )
            )
            continue

        text_match = _NODE_TEXT_RE.match(line)
        if text_match:
            processed = text_match.group("text").strip()
        elif line:
            processed = line
        else:
            # Empty line = paragraph separator
            current_node._prev_empty = True
            continue

        if current_node._prev_empty:
            current_node.text_lines.append(processed)
        else:
            current_node.text_lines[-1] += "\n" + processed
        current_node._prev_empty = False
        continue

    if not nodes:
        raise DialogImportError(
            "no dialog nodes found (missing '## PL'/'## EN' section?)",
            file=str(path),
        )

    return nodes


def _validate_language_consistency(
    pl_nodes: dict[str, _ParsedNode],
    en_nodes: dict[str, _ParsedNode],
    character_name: str,
    src_dir: str,
) -> None:
    """Ensure PL and EN files describe the same graph shape."""
    pl_keys = set(pl_nodes)
    en_keys = set(en_nodes)
    if pl_keys != en_keys:
        missing_pl = en_keys - pl_keys
        missing_en = pl_keys - en_keys
        raise DialogImportError(
            f"PL/EN node mismatch for {character_name!r}: "
            f"missing in PL={sorted(missing_pl)}, missing in EN={sorted(missing_en)}",
            file=src_dir,
        )

    for key in pl_keys:
        pl_node = pl_nodes[key]
        en_node = en_nodes[key]
        if len(pl_node.options) != len(en_node.options):
            raise DialogImportError(
                f"option count mismatch for node {key!r} "
                f"(PL={len(pl_node.options)}, EN={len(en_node.options)})",
                file=src_dir,
            )


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------


def _convert_sentiment(emoji: str) -> str:
    if emoji not in SENTIMENT_EMOJI_TO_EMOTE:
        raise DialogImportError(
            f"unknown sentiment emoji {emoji!r}; expected one of "
            f"{sorted(SENTIMENT_EMOJI_TO_EMOTE)}"
        )
    return SENTIMENT_EMOJI_TO_EMOTE[emoji]


def _convert_text(text: str) -> str:
    """Apply D3 markup/emoji conversion to a node or option text."""
    # bold -> shadow (RPG calls it reverse)
    text = re.sub(
        r"\*\*([^\*]+)\*\*",
        r"[shadow]\1[/shadow]",
        text,
    )
    # italic
    text = re.sub(
        r"(?<!\w)_(?!\s)([^_]+)_(?!\w)",
        r"[italic]\1[/italic]",
        text,
    )

    # rich tag pairs
    for old_tag, new_tag in _TAG_CONVERSIONS.items():
        text = re.sub(
            rf"\[{old_tag}\](.*?)\[/\]",
            rf"[{new_tag}]\1[/{new_tag}]",
            text,
            flags=re.DOTALL,
        )
        text = re.sub(
            rf"\[{old_tag}\](.*?)\[/{old_tag}\]",
            rf"[{new_tag}]\1[/{new_tag}]",
            text,
            flags=re.DOTALL,
        )

    # key -> :key_X:
    text = re.sub(
        r"\[key\](.*?)\[/key\]",
        lambda m: f":key_{m.group(1)}:",
        text,
        flags=re.DOTALL,
    )

    # symbol / e -> :name:
    text = re.sub(
        r"\[symbol\](.*?)\[/symbol\]",
        lambda m: f":{m.group(1)}:",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(
        r"\[e\](.*?)\[/e\]",
        lambda m: f":{m.group(1)}:",
        text,
        flags=re.DOTALL,
    )

    # inline emoji -> :emote:
    for emoji, tag in _EMOJI_TO_EMOTE_TAG.items():
        text = text.replace(emoji, tag)

    return text


def _convert_condition(
    condition: str,
    option_key: str,
    file: str,
    line: int,
) -> str:
    """Convert RPG condition syntax to the MoM mini-DSL."""
    if condition == "True":
        return condition

    out = condition
    out = _SENTIMENT_COND_RE.sub("sentiment", out)
    out = _VISITED_NPC_RE.sub(_replace_visited_npc, out)
    out = _VISITED_SELF_RE.sub(_replace_visited_self, out)

    try:
        validate_condition(out)
    except ConditionError as exc:
        raise DialogImportError(
            f"invalid condition for option {option_key!r}: {exc}",
            file=file,
            line=line,
        ) from exc

    return out


def _replace_visited_npc(match: re.Match[str]) -> str:
    npc = match.group("npc").upper()
    node = match.group("node")
    neg = "not " if match.group("neg") else ""
    return f'{neg}visited("{npc}", "{node}")'


def _replace_visited_self(match: re.Match[str]) -> str:
    node = match.group("node")
    neg = "not " if match.group("neg") else ""
    return f'{neg}visited("{node}")'


# ---------------------------------------------------------------------------
# Result parsing
# ---------------------------------------------------------------------------


def _extract_result(
    text: str,
    node_key: str,
    character_key: str,
    valid_items: set[str] | None,
) -> tuple[str | None, str]:
    """Return (result_key, remaining_text) for a node text.

    If no result prefix is present, returns ``(None, text)``.
    """
    match = _RESULT_RE.match(text)
    if not match:
        return None, text

    result_key = f"{character_key}_NR_{node_key}"
    remaining = text[match.end() :].lstrip()
    return result_key, remaining


def _build_result_dict(
    result_key: str,
    text: str,
    node_key: str,
    character_key: str,
    valid_items: set[str] | None,
) -> dict[str, Any]:
    """Build the NODE_RESULTS entry from a node text result prefix."""
    match = _RESULT_RE.match(text)
    if not match:
        raise DialogImportError(
            f"internal error: no result prefix in node {node_key!r}"
        )

    category_text = match.group("category").upper()
    sign = match.group("sign")
    rest = match.group("rest")

    base: dict[str, Any] = {"items": [], "money": 0, "health": 0, "value": 0}

    if category_text == "MONEY":
        base["category"] = (
            "money_received" if sign == "+" else "money_returned"
        )
        base["money"] = _parse_result_number(rest, node_key, result_key)
    elif category_text == "HEALTH":
        base["category"] = (
            "health_restored" if sign == "+" else "health_lost"
        )
        base["health"] = _parse_result_number(rest, node_key, result_key)
    elif category_text == "SENTIMENT":
        base["category"] = "sentiment_shift"
        value = _parse_result_number(rest, node_key, result_key)
        base["value"] = value if sign == "+" else -value
    elif category_text == "ITEMS":
        base["category"] = (
            "items_received" if sign == "+" else "items_returned"
        )
        base["items"] = _parse_result_items(
            rest, node_key, result_key, valid_items
        )
    else:
        raise DialogImportError(
            f"unknown result category {category_text!r} in node {node_key!r}"
        )

    return base


def _parse_result_number(
    rest: str, node_key: str, result_key: str
) -> int:
    number = rest.strip()
    if not number.isdigit():
        raise DialogImportError(
            f"result {result_key!r} for node {node_key!r} expects a number, "
            f"got {number!r}"
        )
    return int(number)


def _parse_result_items(
    rest: str,
    node_key: str,
    result_key: str,
    valid_items: set[str] | None,
) -> list[str]:
    # strip optional surrounding parentheses or quotes, then split
    cleaned = rest.strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1]
    items = [
        item.strip().strip('"').strip("'")
        for item in cleaned.split(",")
        if item.strip()
    ]
    if valid_items is not None:
        for item in items:
            if item not in valid_items:
                raise DialogImportError(
                    f"result {result_key!r} references unknown item {item!r}"
                )
    return items


# ---------------------------------------------------------------------------
# Graph validation
# ---------------------------------------------------------------------------


def _validate_graph(
    nodes: dict[str, _ParsedNode],
    dialog_config: dict[str, Any],
    file: str,
) -> None:
    """Validate the parsed graph and raise DialogImportError on problems."""
    start_node = dialog_config["START_NODE"]
    if start_node not in nodes:
        raise DialogImportError(
            f"START_NODE {start_node!r} is not a known node",
            file=file,
        )

    # dangling next_node / anchor-target mismatch
    for node in nodes.values():
        for option in node.options:
            if option.target not in nodes:
                raise DialogImportError(
                    f"option points at unknown node {option.target!r}",
                    file=file,
                    line=option.line_no,
                )
            canonical_anchor = option.anchor.replace("-end", "")
            if canonical_anchor != option.target:
                raise DialogImportError(
                    f"option anchor {option.anchor!r} does not match target "
                    f"{option.target!r}",
                    file=file,
                    line=option.line_no,
                )

    # orphan nodes (no incoming edge except START)
    targets = {opt.target for node in nodes.values() for opt in node.options}
    orphans = [
        (key, node.line_no)
        for key, node in nodes.items()
        if key != start_node and key not in targets
    ]
    if orphans:
        key, line = orphans[0]
        raise DialogImportError(
            f"orphan node {key!r} has no incoming options",
            file=file,
            line=line,
        )


# Characters whose dialog format the importer can parse
IMPORTABLE_CHARACTERS: list[str] = [
    "Hammer Hoaxheart",
    "Barman Absinthrayner",
    "Clapback Sword",
    "Potioneer Puzzlemint",
    "Madame Sarcasmia",
]

# Default paths (relative to project root)
_DEFAULT_DIALOG_SRC = _PROJECT_ROOT / "assets" / "dialogs"
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config_model" / "config.json"


def build_dialog_config(
    src_dir: Path | None = None,
    config_path: Path | None = None,
    character_names: list[str] | None = None,
) -> None:
    """Rebuild dialog sections of ``config.json`` from Markdown sources.

    Reads existing ``config.json``, imports each character from its Markdown
    files under ``src_dir``, merges results, preserves dialogs for non-imported
    characters (e.g. ``Madame Sarcasmia`` which uses a custom format), removes
    orphaned message keys no longer referenced by any dialog, and writes back.

    Args:
        src_dir: directory with ``PL/`` and ``EN/`` subdirectories of Markdown
            source files.  Defaults to ``project/assets/dialogs/``.
        config_path: path to ``config.json``.  Defaults to
            ``project/config_model/config.json``.
        character_names: character names to import.  Defaults to
            ``IMPORTABLE_CHARACTERS``.
    """
    import json

    if src_dir is None:
        src_dir = _DEFAULT_DIALOG_SRC
    if config_path is None:
        config_path = _DEFAULT_CONFIG_PATH
    if character_names is None:
        character_names = list(IMPORTABLE_CHARACTERS)

    # Suppress the pygame-ce banner on import
    import os
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

    with config_path.open("r", encoding="utf-8") as f:
        config: dict[str, Any] = json.load(f)

    existing_dialogs: dict[str, Any] = config.get("dialogs", {})
    existing_messages: dict[str, dict[str, str]] = config.get(
        "messages", {"PL": {}, "EN": {}}
    )
    for lang in ("PL", "EN"):
        existing_messages.setdefault(lang, {})

    items_csv = config_path.parent / "items.csv"
    valid_items = load_valid_items(items_csv) if items_csv.exists() else None

    new_messages: dict[str, dict[str, str]] = {"PL": {}, "EN": {}}
    new_dialogs: dict[str, Any] = {}

    for name in character_names:
        char_messages, char_dialog = import_character_dialog(
            src_dir, name, valid_items=valid_items
        )
        for lang in ("PL", "EN"):
            new_messages[lang].update(char_messages[lang])
        new_dialogs.update(char_dialog)

    for lang in ("PL", "EN"):
        existing_messages[lang].update(new_messages[lang])

    existing_dialogs.update(new_dialogs)

    # Remove orphaned message keys (not referenced by any dialog)
    referenced_keys: set[str] = set()
    for dlg in existing_dialogs.values():
        for node in dlg.get("DIALOG_NODES", {}).values():
            if node.get("text"):
                referenced_keys.add(node["text"])
        for opt in dlg.get("DIALOG_OPTIONS", {}).values():
            if opt.get("text"):
                referenced_keys.add(opt["text"])

    for lang in ("PL", "EN"):
        orphaned = set(existing_messages[lang]) - referenced_keys
        for key in orphaned:
            del existing_messages[lang][key]

    config["messages"] = existing_messages
    config["dialogs"] = existing_dialogs

    with config_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
        f.write("\n")


def main(argv: list[str] | None = None) -> None:
    """CLI entry point.

    Usage:
        .venv/bin/python project/dialog/markdown_importer.py
            Build all compatible characters from
            ``project/assets/dialogs/`` into ``config.json``.

        .venv/bin/python project/dialog/markdown_importer.py "Hammer Hoaxheart"
            Build a single character (or space-separated list).

        .venv/bin/python project/dialog/markdown_importer.py \\
            /path/to/rpg/dialogs "Hammer Hoaxheart"
            Legacy mode when first arg contains a ``/`` path separator.
    """
    import json

    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        build_dialog_config()
        return

    # Detect legacy usage: first arg looks like a filesystem path
    if "/" in argv[0] or "\\" in argv[0] or argv[0].startswith("."):
        if len(argv) < 2:
            print(
                "usage: markdown_importer.py <src_dir> <character_name>",
                file=sys.stderr,
            )
            sys.exit(1)
        src_dir = Path(argv[0])
        character_name = argv[1]
        items_csv = Path("project/config_model/items.csv")
        valid_items = load_valid_items(items_csv) if items_csv.exists() else None
        messages, character_dialogs = import_character_dialog(
            src_dir, character_name, valid_items=valid_items
        )
        output = {
            "messages": messages,
            "character_dialogs": character_dialogs,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        build_dialog_config(character_names=list(argv))


if __name__ == "__main__":
    main()


__all__ = [
    "DialogImportError",
    "import_character_dialog",
    "import_dialogs",
    "load_valid_items",
]
