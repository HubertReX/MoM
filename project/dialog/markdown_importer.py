"""Markdown -> dialog config importer (build-time tool, desktop only).

Port of RPG ``import_dialog_from_md.py`` with the improvements required by
Decision **D6**: one regex with named groups for options, graph validation
with ``file:line`` error reporting, and Decision **D3**: one-shot conversion
of RPG rich-markup / emoji to MoM ``RichText`` tags and ``:key:`` emotes.

The importer is pure logic (no pygame, no Pydantic) so it can be unit-tested
in isolation, but it is intended as a **build-time** tool: it reads source
Markdown and emits the ``messages`` / ``character_dialogs`` sections that
can be merged into ``config.json``.

Source MD files live in the ``doc/`` Obsidian vault under ``PL/Postacie/``
and ``EN/Characters/`` (file name = localized display name, e.g.
``Barman Absyntnent.md``; the config key lives in the frontmatter
``aliases``). The **PL file is the source of truth** for character metadata
(``sprite``, ``friendly``, sentiment weights); EN copies are synced by the
dialog-en-sync skill. Run ``just import-dialogs`` (or invoke
``python project/dialog/markdown_importer.py`` directly) to rebuild
``config_model/config.json`` and the metadata columns of
``config_model/characters.csv`` from them (``import-entities`` then merges
the CSV into the ``characters`` section). By default **every** character
file in ``PL/Postacie/`` is discovered and imported (see
``_discover_character_keys``); files whose format the importer cannot parse
yet (work-in-progress) are skipped with a warning. A newly imported
character with no ``characters.csv`` row yet is appended automatically.

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
                "sentiment": sentiment_name,  # e.g. "kind", "neutral"
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
from typing import Any, Callable

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

from settings import (
    SENTIMENT_EMOJI_TO_NAME,
    SENTIMENT_NAME_TO_EMOTE,
)

# emoji appearing inside node/option text -> inline :emote: tag
# (author emoji -> canonical name -> MoM emote sprite key)
_EMOJI_TO_EMOTE_TAG: dict[str, str] = {
    emoji: f":{SENTIMENT_NAME_TO_EMOTE[name]}:"
    for emoji, name in SENTIMENT_EMOJI_TO_NAME.items()
}

# sentiment weights that may appear in character frontmatter (PL is the
# source of truth); ``neutral`` and ``technical`` are implicit with weight 0.
_FRONTMATTER_WEIGHT_KEYS: tuple[str, ...] = (
    "kind", "weak", "angry", "smart", "funny",
)

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
# Supports both old [anchor](#target) and new [[#target]] formats.
_OPTION_RE = re.compile(
    r"^\*\s*"
    r"(?:"
    r"\[\[#(?P<new_target>[^]]+)\]\]"
    r"|"
    r"\[(?P<anchor>[^\]]+)\]\(#(?P<target>[^)]+)\)"
    r")"
    r"\s*(?P<order>\d+)"
    r"(?:\[(?P<condition>[^\]]+)\])?"
    r"(?P<sentiment>[^\s:]+)"
    r"\s*:\s*"
    r"(?P<text>.*)$"
)

# heading that starts a node: "## 000", "## 990-end" (preferred) or the
# legacy "### 000" / "### 990-end [011](#011)".  Node keys are digits only,
# so prose headings inside the "# Info" section never collide.
_NODE_HEADING_RE = re.compile(
    r"^#{2,3}\s*(?P<key>\d+(?:-end)?)"
    r"(?:\s*\[(?P<resume_anchor>[^\]]+)\]\(#(?P<resume_target>[^)]+)\))?\s*$"
)

# standalone resume link on its own line: "[011](#011)" or "[[#011]]"
_RESUME_LINK_RE = re.compile(
    r"^\[(?:\[#(?P<new_target>[^]]+)\]\]|"
    r"(?P<anchor>[^\]]+)\]\(#(?P<target>[^)]+)\))\s*$"
)

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
    resume_node: str | None = None
    options: list[_ParsedOption] = field(default_factory=list)
    line_no: int = 0
    _prev_empty: bool = field(default=True, repr=False)

    @property
    def text(self) -> str:
        return "\n\n".join(self.text_lines)


@dataclass
class _Frontmatter:
    """Parsed character-file frontmatter (the subset the importer cares about)."""

    aliases: list[str] = field(default_factory=list)
    sprite: str = ""
    friendly: float | None = None
    weights: dict[str, int] = field(default_factory=dict)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _parse_frontmatter(text: str, *, path: str = "") -> _Frontmatter:
    """Parse the YAML frontmatter block with a minimal, dependency-free parser.

    Supports the flat ``key: value`` entries and one-level ``- item`` lists
    used by character files. Unknown keys are ignored (the file may carry
    Obsidian-only metadata like ``location`` or ``inspirations``).
    """
    fm = _Frontmatter()
    lines = text.splitlines()
    # Tolerate leading blank lines before the opening `---` (some vault files
    # start with an empty line); otherwise the whole frontmatter - including
    # the config-key alias - would be silently ignored.
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start >= len(lines) or lines[start].strip() != "---":
        return fm

    current_list: list[str] | None = None
    for idx in range(start + 1, len(lines)):
        stripped = lines[idx].strip()
        if stripped == "---":
            break
        if not stripped:
            continue
        if stripped.startswith("- "):
            if current_list is not None:
                item = _unquote(stripped[2:].strip())
                if item:
                    current_list.append(item)
            continue
        if ":" not in stripped:
            continue
        key, _sep, raw_value = stripped.partition(":")
        key = key.strip()
        value = _unquote(raw_value.strip())
        current_list = None
        if key == "aliases":
            fm.aliases = []
            current_list = fm.aliases
            if value:
                fm.aliases.append(value)
        elif key == "sprite":
            fm.sprite = value
        elif key == "friendly":
            if value:
                try:
                    fm.friendly = float(value)
                except ValueError:
                    raise DialogImportError(
                        f"frontmatter 'friendly' expects a number, got {value!r}",
                        file=path,
                        line=idx + 1,
                    )
        elif key in _FRONTMATTER_WEIGHT_KEYS:
            if value:
                try:
                    fm.weights[key] = int(value)
                except ValueError:
                    raise DialogImportError(
                        f"frontmatter {key!r} expects an integer weight, got {value!r}",
                        file=path,
                        line=idx + 1,
                    )
    return fm


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# Preferred vault layout (doc/ Obsidian vault) with fallback to the legacy
# flat {PL,EN} directories used before the doc/ migration.
_LANG_SUBDIRS: dict[str, tuple[str, ...]] = {
    "PL": ("PL/Postacie", "PL"),
    "EN": ("EN/Characters", "EN"),
}


def _lang_dir(src_dir: Path, lang: str) -> Path:
    for sub in _LANG_SUBDIRS.get(lang, (lang,)):
        candidate = src_dir / sub
        if candidate.exists():
            return candidate
    raise DialogImportError(
        f"Language directory not found under {src_dir} for {lang!r}",
        file=str(src_dir),
    )


def _find_markdown_file(src_dir: Path, lang: str, character_name: str) -> Path:
    """Locate the character's Markdown file by its frontmatter aliases.

    File names are localized display names (e.g. ``Barman Absyntnent.md``);
    the dictionary key lives only in the frontmatter ``aliases`` list.
    """
    lang_dir = _lang_dir(src_dir, lang)
    character_key = _character_name_to_key(character_name)
    for p in sorted(lang_dir.glob("*.md")):
        fm = _parse_frontmatter(p.read_text(encoding="utf-8"), path=str(p))
        if character_key in fm.aliases:
            return p
    raise DialogImportError(
        f"no Markdown file with alias {character_key!r} in {lang_dir}",
        file=str(lang_dir),
    )


# A config key is UPPER_SNAKE (e.g. ``MISS_INFORMATION``). Used to pick the
# key out of a frontmatter ``aliases`` list that may also carry display-name
# aliases (e.g. ``[MISS_INFORMATION, Mariolka]``).
_KEY_ALIAS_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _discover_character_keys(src_dir: Path) -> list[str]:
    """Discover character config keys from the PL source files.

    Globs the PL character directory (``doc/PL/Postacie``, legacy ``PL/``),
    reads each file's frontmatter and returns the config key of every file
    that declares one. The key is the alias matching the UPPER_SNAKE pattern
    (falling back to the first alias), so display-name aliases don't shadow
    it. Files without aliases are skipped; the result is sorted for stable
    output.
    """
    try:
        pl_dir = _lang_dir(src_dir, "PL")
    except DialogImportError:
        return []
    keys: list[str] = []
    for p in sorted(pl_dir.glob("*.md")):
        fm = _parse_frontmatter(p.read_text(encoding="utf-8"), path=str(p))
        if not fm.aliases:
            continue
        key = next(
            (a for a in fm.aliases if _KEY_ALIAS_RE.match(a)), fm.aliases[0]
        )
        keys.append(key)
    return sorted(keys)


def _make_name_resolver(
    characters: dict[str, Any], lang: str
) -> Callable[[str, str | None], str | None] | None:
    """Build a wikilink resolver for the given language.

    Returns a callable ``(target, display) -> str | None``: *target* is the
    wikilink target (character key, localized file name, or a legacy
    ``lang/File_Name`` path), *display* is the optional pipe text (used for
    grammatical declension, e.g. ``[[Barman Absyntnent|Barmana Absyntnenta]]``).
    The callable returns the text to render inside ``[char]...[/char]``, or
    ``None`` when the target is not a known character (link left as-is).
    Returns ``None`` when *characters* is empty (no resolution at all).
    """
    if not characters:
        return None
    field = "name_PL" if lang == "PL" else "name_EN"

    # Lookup by config key and by display names in BOTH languages, so links
    # in PL files to EN-named files (and vice versa) still resolve.
    lookup: dict[str, dict[str, Any]] = {}
    for key, ch in characters.items():
        lookup[key] = ch
        for name_field in ("name_PL", "name_EN"):
            name = ch.get(name_field, "")
            if name:
                lookup.setdefault(name, ch)

    def _resolve(target: str, display: str | None) -> str | None:
        # strip legacy "PL/"/"EN/" path prefix and normalise underscores
        candidate = target.rsplit("/", 1)[-1].strip()
        ch = lookup.get(candidate) or lookup.get(candidate.replace("_", " "))
        if ch is None and display:
            # legacy links carried the config key in the pipe part
            # (e.g. ``[[PL/Hammer_Hoaxheart|HAMMER_HOAXHEART]]``)
            d = display.strip()
            ch = lookup.get(d) or lookup.get(d.replace("_", " "))
            if ch is not None:
                display = None  # the pipe was an identifier, not display text
        if ch is None:
            return None
        canonical = ch.get(field, ch.get("name_EN", candidate))
        if display:
            # Legacy links used the config key / file stem as pipe text
            # (e.g. ``[[EN/Clapback_Sword|Clapback_Sword]]``) - treat an
            # identifier-like pipe as a reference, not display text.
            if display in characters or "_" in display:
                return str(canonical)
            return display
        return str(canonical)

    return _resolve


def import_character_dialog(
    src_dir: Path,
    character_name: str,
    *,
    valid_items: set[str] | None = None,
    characters: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, str]], dict[str, Any], dict[str, Any]]:
    """Import one character from its Markdown source.

    Locates the PL and EN files by the frontmatter ``aliases`` (the file
    names themselves are localized display names), validates the graph,
    converts markup and conditions, and returns
    ``(messages, character_dialogs, character_meta)``.

    The **PL file is the source of truth** for character metadata: the
    frontmatter ``sprite``, ``friendly`` and sentiment weights
    (``kind/weak/angry/smart/funny``) are read from PL only; the EN copies
    exist for the author's convenience (synced by the dialog-en-sync skill).

    Args:
        src_dir: vault root containing ``PL/Postacie`` and ``EN/Characters``
            (or legacy flat ``PL``/``EN``) subdirectories.
        character_name: canonical character name, e.g. ``"Hammer Hoaxheart"``.
        valid_items: optional set of item keys (from ``items.csv``) used to
            validate item names referenced by ``[ITEMS+...]`` node results.
        characters: optional dict of character config data (key -> props)
            used to resolve ``[[...]]`` wikilinks to entity names.

    Returns:
        A tuple ``(messages, character_dialogs, character_meta)`` where
        ``messages`` has the shape ``{lang: {key: text}}``,
        ``character_dialogs`` has the shape described in the module
        docstring, and ``character_meta`` is
        ``{"sprite": str, "friendly": float | None, "disposition": dict,
        "name_PL": str, "name_EN": str}`` built from the PL frontmatter and
        the localized file names (empty/None values mean "not set").
    """
    character_key = _character_name_to_key(character_name)
    pl_path = _find_markdown_file(src_dir, "PL", character_name)
    en_path = _find_markdown_file(src_dir, "EN", character_name)
    pl_nodes = _parse_file(pl_path)
    en_nodes = _parse_file(en_path)

    frontmatter = _parse_frontmatter(
        pl_path.read_text(encoding="utf-8"), path=str(pl_path)
    )
    character_meta: dict[str, Any] = {
        "sprite": frontmatter.sprite,
        "friendly": frontmatter.friendly,
        "disposition": dict(frontmatter.weights),
        # Localized display names (file stems) - used when a new character
        # row is auto-appended to characters.csv.
        "name_PL": pl_path.stem,
        "name_EN": en_path.stem,
    }

    _validate_language_consistency(
        pl_nodes, en_nodes, character_name, str(src_dir)
    )

    resolve_pl = _make_name_resolver(characters, "PL") if characters else None
    resolve_en = _make_name_resolver(characters, "EN") if characters else None

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

        messages["PL"][node_message_key] = _convert_text(pl_text, resolve_pl)
        messages["EN"][node_message_key] = _convert_text(en_text, resolve_en)

        node_config = {
            "is_final": pl_node.is_final,
            "result": result_key,
            "text": node_message_key,
        }
        if pl_node.resume_node:
            node_config["resume_node"] = pl_node.resume_node
        dialog_config[character_key]["DIALOG_NODES"][node_key] = node_config

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
                str(pl_path),
                pl_opt.line_no,
            )

            messages["PL"][option_message_key] = _convert_text(pl_opt.text, resolve_pl)
            messages["EN"][option_message_key] = _convert_text(en_opt.text, resolve_en)

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
        str(pl_path),
    )

    return messages, dialog_config, character_meta


def import_dialogs(
    src_dir: Path,
    character_names: list[str],
    *,
    valid_items: set[str] | None = None,
) -> tuple[dict[str, dict[str, str]], dict[str, Any], dict[str, Any]]:
    """Import several characters and merge their configs.

    Args:
        src_dir: vault root containing the per-language subdirectories.
        character_names: list of canonical character names.
        valid_items: optional set of valid item keys.

    Returns:
        A tuple ``(messages, character_dialogs, character_meta)`` with all
        characters merged; ``character_meta`` maps character key to the
        frontmatter metadata (sprite/friendly/disposition).
    """
    messages: dict[str, dict[str, str]] = {"PL": {}, "EN": {}}
    character_dialogs: dict[str, Any] = {}
    character_meta: dict[str, Any] = {}

    for name in character_names:
        char_messages, char_dialog, char_meta = import_character_dialog(
            src_dir, name, valid_items=valid_items
        )
        for lang in ("PL", "EN"):
            messages[lang].update(char_messages[lang])
        character_dialogs.update(char_dialog)
        character_meta[_character_name_to_key(name)] = char_meta

    return messages, character_dialogs, character_meta


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

# Default source directory for dialog Markdown files: the doc/ Obsidian
# vault (PL/Postacie + EN/Characters subdirectories via _lang_dir).
_DEFAULT_DIALOG_SRC = _PROJECT_ROOT.parent / "doc"
# Default config.json path
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config_model" / "config.json"
# characters.csv - the author-facing intermediate of the
# MD -> CSV -> config.json pipeline
_DEFAULT_CHARACTERS_CSV = _PROJECT_ROOT / "config_model" / "characters.csv"

# CSV columns owned by this importer (filled from the PL frontmatter).
_CSV_META_COLUMNS: tuple[str, ...] = ("sprite", "friendly") + _FRONTMATTER_WEIGHT_KEYS


# Defaults for columns that the importer cannot derive from the dialog
# frontmatter when auto-appending a brand-new character row.
_CSV_APPEND_DEFAULTS: dict[str, str] = {
    "attitude": "friendly",
    "race": "humanoid",
    "has_dialog": "true",
}


def _apply_meta_to_row(
    row: list[str], meta: dict[str, Any], col_idx: dict[str, int]
) -> None:
    """Write the importer-owned metadata columns (sprite/friendly/weights)."""
    if meta.get("sprite"):
        row[col_idx["sprite"]] = meta["sprite"]
    if meta.get("friendly") is not None:
        row[col_idx["friendly"]] = f"{meta['friendly']:g}"
    for sentiment, weight in meta.get("disposition", {}).items():
        if sentiment in col_idx:
            row[col_idx[sentiment]] = str(weight)


def _update_characters_csv(csv_path: Path, character_meta: dict[str, Any]) -> bool:
    """Upsert imported characters into ``characters.csv``.

    Existing rows have their sprite/friendly/sentiment columns refreshed from
    the frontmatter (other rows and columns stay as-is). Characters discovered
    from the dialog vault that have no row yet are **appended** with their
    localized names, the metadata columns and sensible defaults
    (attitude/race/has_dialog). ``import_entities.py`` remains the sole writer
    of the ``characters`` section in ``config.json`` (run via just cascade).
    """
    if not csv_path.exists():
        print(f"characters.csv not found: {csv_path}", file=sys.stderr)
        return False

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))
    if not rows:
        return False

    header = rows[0]
    for column in _CSV_META_COLUMNS:
        if column not in header:
            header.append(column)
    col_idx = {name: i for i, name in enumerate(header)}

    existing_keys = {row[0] for row in rows[1:] if row}

    updated = 0
    for row in rows[1:]:
        while len(row) < len(header):
            row.append("")
        meta = character_meta.get(row[0])
        if not meta:
            continue
        _apply_meta_to_row(row, meta, col_idx)
        updated += 1

    appended = 0
    for key, meta in character_meta.items():
        if key in existing_keys:
            continue
        row = [""] * len(header)
        row[0] = key  # the ``key`` column is always first
        if "name_EN" in col_idx and meta.get("name_EN"):
            row[col_idx["name_EN"]] = meta["name_EN"]
        if "name_PL" in col_idx and meta.get("name_PL"):
            row[col_idx["name_PL"]] = meta["name_PL"]
        for column, default in _CSV_APPEND_DEFAULTS.items():
            if column in col_idx:
                row[col_idx[column]] = default
        _apply_meta_to_row(row, meta, col_idx)
        rows.append(row)
        appended += 1

    import io
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\n")
    writer.writerows(rows)
    csv_path.write_text(buf.getvalue(), encoding="utf-8")
    print(f"Updated {updated}, appended {appended} character row(s) in {csv_path}")
    return True


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


def _collect_quest_text_references(quests: dict[str, Any]) -> set[str]:
    """Message keys the *quests* point at — not ours to sweep.

    ``config.json["messages"]`` is shared: dialogs and quests both live there
    (decision D3). The orphan sweep below deletes every key no dialog references,
    so without this the first ``just import-dialogs`` after a quest import would
    silently delete every quest title, description and success line.
    """
    refs: set[str] = set()
    for quest in quests.values():
        for name in ("name", "description", "success"):
            if quest.get(name):
                refs.add(quest[name])
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
            Defaults to **every** character discovered in the vault's PL
            directory (via ``_discover_character_keys``).

    Returns:
        0 on success. When importing an explicit ``character_names`` list,
        returns 1 if any import failed. When auto-discovering (default),
        files that fail to parse (e.g. work-in-progress characters) are
        skipped with a warning and the return code stays 0 so the
        ``import-entities`` cascade proceeds.
    """
    import json

    # Whether we import the whole vault (default) or an explicit list. Auto
    # discovery tolerates unparseable/WIP files (skip + warn, exit 0).
    auto_discovered = character_names is None

    if src_dir is None:
        src_dir = _DEFAULT_DIALOG_SRC
    if config_path is None:
        config_path = _DEFAULT_CONFIG_PATH
    if character_names is None:
        character_names = _discover_character_keys(src_dir)

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
    new_meta: dict[str, Any] = {}
    imported: list[str] = []
    errors: list[str] = []

    characters_config: dict[str, Any] = config.get("characters", {})

    for name in character_names:
        try:
            char_messages, char_dialog, char_meta = import_character_dialog(
                src_dir, name, valid_items=valid_items, characters=characters_config
            )
            for lang in ("PL", "EN"):
                new_messages[lang].update(char_messages[lang])
            new_dialogs.update(char_dialog)
            new_meta[_character_name_to_key(name)] = char_meta
            imported.append(name)
        except DialogImportError as exc:
            errors.append(f"  {exc}")
        except Exception as exc:
            errors.append(f"  {name}: {exc}")

    if imported:
        print(f"Imported {len(imported)} character(s): {', '.join(imported)}")

    if errors:
        if auto_discovered:
            # Expected for WIP/incomplete files - skip loudly, don't fail.
            print(
                f"Skipped {len(errors)} incomplete/unimportable file(s):",
                file=sys.stderr,
            )
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

    # Remove orphaned message keys (dialog keys only — quest keys belong to
    # quest/markdown_importer.py and are swept there)
    referenced = _collect_text_references(existing_dialogs)
    referenced |= _collect_quest_text_references(config.get("quests", {}))
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

    # MD -> CSV: surface frontmatter metadata (sprite/friendly/weights) in
    # characters.csv; `just import-dialogs` then cascades import-entities
    # which merges the CSV into config.json's `characters` section.
    if new_meta:
        _update_characters_csv(config_path.parent / "characters.csv", new_meta)

    # Auto-discovery tolerates WIP files: skipped imports are warnings, not
    # failures, so the just cascade to import-entities still runs.
    if auto_discovered:
        return 0
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

    idx = 0
    while idx < len(lines):
        raw_line = lines[idx]
        line_no = idx + 1  # 1-based for error messages
        line = raw_line.rstrip()
        idx += 1

        node_match = _NODE_HEADING_RE.match(line)
        if node_match:
            node_key = node_match.group("key")
            is_final = node_key.endswith("-end")
            node_key = node_key.replace("-end", "")
            resume_node = node_match.group("resume_target")

            # New format: resume link on separate line after -end heading
            if resume_node is None and is_final and idx < len(lines):
                peek_match = _RESUME_LINK_RE.match(lines[idx].rstrip())
                if peek_match:
                    resume_target = (
                        peek_match.group("new_target")
                        or peek_match.group("target")
                    )
                    resume_node = resume_target.replace("-end", "")
                    idx += 1  # consume the resume link line

            current_node = _ParsedNode(
                key=node_key,
                is_final=is_final,
                resume_node=resume_node,
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
            opt_text = option_match.group("text").strip()
            # Resolve anchor/target from whichever format matched.
            new_target = option_match.group("new_target")
            if new_target is not None:
                opt_target = new_target
                opt_anchor = new_target
            else:
                opt_target = option_match.group("target")
                opt_anchor = option_match.group("anchor")
            # "technical loop back" is a directive, not a real option — it
            # sets the resume_node for backward-compat heading format.
            if opt_text == "technical loop back" and current_node.is_final:
                if current_node.resume_node is None:
                    current_node.resume_node = opt_target.replace("-end", "")
                continue
            current_node.options.append(
                _ParsedOption(
                    anchor=opt_anchor,
                    target=opt_target.replace("-end", ""),
                    order=option_match.group("order"),
                    condition=option_match.group("condition"),
                    sentiment=option_match.group("sentiment"),
                    text=opt_text,
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
            "no dialog nodes found (missing '## <number>' node headings?)",
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
    """Map an option-line emoji to its canonical sentiment name (D3b)."""
    if emoji not in SENTIMENT_EMOJI_TO_NAME:
        raise DialogImportError(
            f"unknown sentiment emoji {emoji!r}; expected one of "
            f"{sorted(SENTIMENT_EMOJI_TO_NAME)}"
        )
    return SENTIMENT_EMOJI_TO_NAME[emoji]


# wikilink [[Target]] or [[Target|display text]] - target may be a config
# key (``BARMAN_ABSINTHRAYNER``), a localized file name with spaces and
# diacritics (``Miecz Ciętej-riposty``) or a legacy ``lang/File_Name`` path.
# ``[[#001]]`` option/resume links are excluded (target cannot start with #).
_WIKILINK_RE = re.compile(
    r"\[\[(?P<target>[^\]|#][^\]|]*?)(?:\|(?P<display>[^\]]+))?\]\]"
)


def _convert_text(
    text: str,
    resolve_name: Callable[[str, str | None], str | None] | None = None,
) -> str:
    """Apply D3 markup/emoji conversion to a node or option text.

    If *resolve_name* is a callable ``(target, display) -> str | None``,
    character wikilinks are replaced by ``[char]...[/char]`` with its
    return value; unknown targets are left as-is.
    """
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

    # wikilinks [[Target]] / [[Target|display]] -> [char]display name[/char]
    if resolve_name is not None:
        def _resolve_wikilink(m: re.Match[str]) -> str:
            display = m.group("display")
            resolved = resolve_name(
                m.group("target"), display.strip() if display else None
            )
            if resolved is None:
                return m.group(0)  # unknown target - leave as-is
            return f"[char]{resolved}[/char]"

        text = _WIKILINK_RE.sub(_resolve_wikilink, text)

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
    # resume targets from final-node headings also count as incoming edges
    for node in nodes.values():
        if node.resume_node:
            targets.add(node.resume_node)
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


def main(argv: list[str] | None = None) -> None:
    """CLI entry point.

    Usage:
        .venv/bin/python project/dialog/markdown_importer.py
            Build all compatible characters from the dialog vault
            (``doc/``) into ``config.json`` + ``characters.csv``.

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
        messages, character_dialogs, character_meta = import_character_dialog(
            src_dir, character_name, valid_items=valid_items
        )
        output = {
            "messages": messages,
            "character_dialogs": character_dialogs,
            "character_meta": character_meta,
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
