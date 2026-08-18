"""Markdown -> quest config importer (build-time tool, desktop only).

Sibling of ``dialog/markdown_importer.py``, same shape: read the ``doc/``
Obsidian vault, emit the ``quests`` and ``messages`` sections of
``config.json``. Run via ``just import-quests``.

Source layout (decision **D1**: one file = one quest)::

    doc/PL/Misje/Q03_S01 Kto ma wiedzę o magii.md    <- source of truth
    doc/EN/Quests/Q03_S01 Who knows about magic.md   <- prose only

**The frontmatter alias is the quest's config key**, globally unique across the
vault, and the ``# H1`` heading is the quest's title::

    ---
    aliases:
      - Q03_S01_WHO_HAS_MORE_KNOWLEDGE
    ---
    # Kto ma wiedzę o magii?

The alias doubles as Obsidian's link target, which is what makes a ``Requires``
clickable and independent of the localized file name (see ``_parse_requires``).
The file name is only a localized display name; by convention it repeats the
``Qxx_Syy`` prefix so the vault sorts in play order.

``parent`` is derived from the key (decision **D1**): every ``Qxx_Syy_...``
belongs to chain ``Qxx``, and ``Qxx_S00_...`` is that chain's umbrella. A step
never repeats its parent — one less thing to get wrong — while ordering between
steps stays explicit, via ``**Requires**:``.

Body (decision **D2**: machine fields live in the body, not in frontmatter,
because subquests cannot fit in YAML)::

    Barman wspomniał, że ktoś w miasteczku zna się na klątwach.

    **Requires**: [[Q03_S00 Znajdź kogoś kto wie o klątwach]]
    **Completion**: `test`
    **Test**: `visited(`[[Zielarka Zmora#014|Zielarka#014]]`)`
    **Sukces**: Puzzlemint wie o klątwach więcej, niż chciałby przyznać.
    **Nagroda**: `add_money(50)`

Anything that is not a ``**Field**:`` line is prose and becomes the quest
description. Field names accept PL or EN spelling (``Sukces``/``Success``), so
the EN file reads naturally. Prose keeps its paragraphs (a blank line between
two blocks survives as ``\n\n``) and its inline Markdown emphasis: ``**bold**``
and ``_italic_`` become the RichText spans the panel draws, exactly as in the
dialogue importer (``**bold**`` maps to ``[shadow]``, the only emphasis the pixel
font actually shows). Without that pass the player read the asterisks.

**Machine-readable values are wrapped in backticks** so Obsidian renders them as
code rather than prose, and entity references inside them are written as real
wikilinks, interleaved with the backticks::

    `visited(`[[Zielarka Zmora#014|Zielarka#014]]`)`

That way one expression is both a runnable condition *and* an edge in the
Obsidian graph. :func:`dialog.vault_links.expand_links` puts it back together:
backticks are dropped and every wikilink becomes the key(s) it points at —
``[[Note#anchor]]`` -> ``"KEY", "anchor"``, ``[[Note]]`` -> ``"KEY"``.

Everything from the first ``##`` heading onwards is **author notes** and is
ignored (``## Notatki``). That is where chain-level commentary goes, since the
prose above it belongs to the player.

**Machine fields are read from PL only** (decision D2). The EN file supplies the
title, ``Sukces`` and prose and nothing else; a ``**Test**:`` written there is
ignored with a warning. This is what makes the EN file safe to regenerate with an
LLM: the worst it can do is write bad prose, never break the quest logic.

Nothing here mutates game state: ``config.json`` is a generated artifact and the
player's progress lives in the save (decision D13).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Allow running this file directly from project/quest/ as a CLI tool.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from dialog.conditions import (
    ConditionError,
    ConditionScope,
    validate_condition,
    validate_number,
)
from dialog.effects import EffectError, EffectScope, parse_effect
from dialog.vault_links import (
    WIKI_RE as _WIKI_RE,
    VaultIndex,
    VaultLinkError,
    build_vault_index,
    expand_links,
    note_key,
    render_links,
    resolve_entity as _resolve_entity,
)
from quest.graph import init_quests


class QuestImportError(ValueError):
    """A quest source Markdown is malformed.

    Carries ``file`` and ``line`` so the author gets ``file:line``, not a stack
    trace — an import that fails must say exactly which line to go fix.
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
# Vault layout
# ---------------------------------------------------------------------------

_LANG_SUBDIRS: dict[str, tuple[str, ...]] = {
    "PL": ("PL/Misje",),
    "EN": ("EN/Quests",),
}

_DEFAULT_QUEST_SRC = _PROJECT_ROOT.parent / "doc"
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config_model" / "config.json"

# Message keys owned by this importer. The dialog importer sweeps orphaned
# message keys and must not touch ours (and vice versa), so the two live in
# separate namespaces.
MESSAGE_PREFIX = "M_QUEST_"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_TITLE_RE = re.compile(r"^#\s+(?P<title>\S.*?)\s*$")
_NOTES_RE = re.compile(r"^#{2,}\s")
_FIELD_RE = re.compile(r"^\*\*(?P<name>[^*]+)\*\*\s*:\s*(?P<value>.*)$")
_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# `Q03_S01_WHO_HAS_MORE_KNOWLEDGE` -> chain `Q03`, step `01`. Step 00 is the
# chain's umbrella, which is where `parent` comes from.
_QUEST_KEY_RE = re.compile(r"^(?P<chain>Q\d+)_S(?P<step>\d+)_(?P<slug>[A-Z][A-Z0-9_]*)$")
_UMBRELLA_STEP = "00"

# PL or EN spelling -> canonical field name. The title is the `# H1` heading,
# not a field, so it is deliberately absent here.
_FIELD_ALIASES: dict[str, str] = {
    "sukces": "success", "success": "success",
    "completion": "completion", "ukończenie": "completion", "ukonczenie": "completion",
    "test": "test",
    "requires": "requires", "wymaga": "requires",
    "postęp": "progress", "postep": "progress", "progress": "progress",
    "nagroda": "reward", "reward": "reward",
}

# Read from PL only (D2). In EN they are ignored, loudly.
_MACHINE_FIELDS = frozenset({"completion", "test", "requires", "progress", "reward"})

# Fields whose value is an engine expression: backticks come off, wikilinks
# become the keys they point at.
_EXPRESSION_FIELDS = frozenset({"completion", "test", "progress", "reward"})

# --- inline Markdown -> RichText ------------------------------------------
# Prose is authored in Obsidian, so emphasis is written the Markdown way. The
# panel draws RichText markup and has no idea what an asterisk means, so the
# author's `**Twój**` reached the player *with the asterisks*. Same conversion
# the dialogue importer does (`dialog.markdown_importer._convert_text`), tag for
# tag - including `**bold**` -> `[shadow]`.
#
# **Why not `[bold]`.** MoM sets prose in a pixel font (`font_pixel.ttf`), where
# `set_bold` is pygame's synthetic emboldening: one extra pixel of stem. Measured
# at FONT_SIZE_SMALL it widens "zwykly Twoj" from 154px to 165px and is invisible
# in a paragraph - the whole block just reads slightly uneven. The drop shadow is
# what carries weight in this font, which is why the dialogue importer picked it
# first. Emphasis has to be *seen*; matching the CSS name is worth nothing.
_MD_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
# `_x_` only between non-word characters, so a config key (`Q00_S00_WHAT`) or a
# snake_case reward category is never mistaken for emphasis.
_MD_ITALIC_RE = re.compile(r"(?<!\w)_(?!\s)([^_]+)_(?!\w)")


def _convert_emphasis(text: str) -> str:
    """Turn Markdown ``**bold**`` / ``_italic_`` into RichText tags."""
    text = _MD_BOLD_RE.sub(r"[shadow]\1[/shadow]", text)
    return _MD_ITALIC_RE.sub(r"[italic]\1[/italic]", text)


def _join_prose(lines: list[str]) -> str:
    """Join description lines into paragraphs separated by a blank line.

    A hard-wrapped paragraph is one paragraph: the lines inside it join with a
    space (wrapping belongs to the renderer, not to the file). A blank line in
    the source is the author separating two blocks, and it survives as ``\n\n``
    — the panel's RichText renders that as the empty line it looks like. Joining
    everything with a space, as this used to, silently glued two paragraphs of
    `Q01_S02` into one wall of text.
    """
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


# stary zapis nagrody (`money=50`, `sentiment=10 @BARMAN`) - już nieobsługiwany,
# rozpoznawany po to, żeby import powiedział, na co go zamienić
_LEGACY_REWARD_RE = re.compile(r"^(?P<category>[a-z_]+)\s*=\s*(?P<value>.+)$")

# czasownik efektu -> kategoria `QuestRewardCategory`. Nagroda daje, a nie
# zabiera, więc `remove_money` czy `lose_health` tu nie stoją - `dialog.effects`
# odrzuca je zasięgiem, wskazując, co wolno napisać.
_REWARD_CATEGORIES: dict[str, str] = {
    "add_money": "money",
    "add_n_items": "items",
    "restore_health": "health",
    "raise_max_health": "max_health",
    "raise_damage": "damage",
    "raise_max_items": "max_items",
    "shift_sentiment_of": "sentiment",
}


@dataclass(slots=True)
class _ParsedQuest:
    """One quest file, before it becomes config."""

    key: str  # the quest's config key: the frontmatter alias, verbatim
    path: Path
    title: str = ""
    description: list[str] = field(default_factory=list)
    success: str = ""
    completion: str = ""
    test: str | None = None
    requires: list[str] = field(default_factory=list)
    progress: str | None = None
    progress_total: int = 0
    rewards: list[dict[str, Any]] = field(default_factory=list)
    line: int = 0  # the H1, so an error about the quest as a whole points at it


def _lang_dir(src_dir: Path, lang: str) -> Path:
    for sub in _LANG_SUBDIRS.get(lang, (lang,)):
        candidate = src_dir / sub
        if candidate.exists():
            return candidate
    raise QuestImportError(
        f"quest directory not found under {src_dir} for {lang!r} "
        f"(expected {'/'.join(_LANG_SUBDIRS.get(lang, (lang,)))})",
        file=str(src_dir),
    )


def _key_of(path: Path) -> str:
    """The quest's config key: the UPPER_SNAKE alias in the frontmatter.

    The alias *is* the key (``Q03_S01_WHO_HAS_MORE_KNOWLEDGE``), not a prefix to
    compose one from. That is what lets a ``Requires`` read
    ``[[Q03_S01_WHO_HAS_MORE_KNOWLEDGE]]`` as well as ``[[Kto ma wiedzę o
    magii]]``: Obsidian resolves both to the same note.
    """
    key = note_key(path.read_text(encoding="utf-8"))
    if not key:
        raise QuestImportError(
            "no quest key in frontmatter aliases (expected the quest's own key, "
            "e.g. 'Q03_S01_WHO_HAS_MORE_KNOWLEDGE')",
            file=str(path),
        )
    return key


def _split_key(key: str, path: Path) -> tuple[str, str]:
    """``('Q03', '01')`` for ``Q03_S01_...`` — the chain and the step within it."""
    match = _QUEST_KEY_RE.match(key)
    if not match:
        raise QuestImportError(
            f"quest key {key!r} does not read 'Qxx_Syy_NAME' — the chain and the step "
            f"number are what say which umbrella this quest belongs to",
            file=str(path),
        )
    return match.group("chain"), match.group("step")


def discover_quest_keys(src_dir: Path) -> list[str]:
    """Every quest key declared in the PL quest directory, sorted.

    Sorted by key, which sorts by chain and then by step — the order the author
    numbered them in, and the order the HUD walks when suggesting what to do next.
    """
    try:
        pl_dir = _lang_dir(src_dir, "PL")
    except QuestImportError:
        return []
    keys: list[str] = []
    for path in sorted(pl_dir.glob("*.md")):
        try:
            keys.append(_key_of(path))
        except QuestImportError:
            continue
    return sorted(keys)


def _find_quest_file(src_dir: Path, lang: str, key: str) -> Path:
    lang_dir = _lang_dir(src_dir, lang)
    for path in sorted(lang_dir.glob("*.md")):
        try:
            if _key_of(path) == key:
                return path
        except QuestImportError:
            continue
    raise QuestImportError(
        f"no Markdown file with alias {key!r} in {lang_dir}",
        file=str(lang_dir),
    )


def _resolve_chain(src_dir: Path, wanted: str) -> list[str]:
    """Accept a full quest key, or a bare ``Qxx`` prefix meaning the whole chain.

    ``just import-quests Q01_S01_LEARN_ABOUT_CURSE`` is exact; ``just
    import-quests Q01`` is the shorthand nobody has to look up.
    """
    known = discover_quest_keys(src_dir)
    if wanted in known:
        return [wanted]

    matches = [key for key in known if key.startswith(f"{wanted}_")]
    if matches:
        return matches
    raise QuestImportError(
        f"no quest or chain {wanted!r} (known: {', '.join(known) or 'none'})"
    )


# ---------------------------------------------------------------------------
# Parsing a quest file
# ---------------------------------------------------------------------------


def _expand_expression(
    value: str, index: dict[str, str], path: Path, line_no: int, *, label: str
) -> str:
    """:func:`dialog.vault_links.expand_links`, with this importer's error type.

    A quest has no current character, so ``[[#005]]`` - the "a node of mine" form
    that dialog options use - has nothing to resolve against and is refused.
    """
    try:
        return expand_links(value, index, label=label)
    except VaultLinkError as error:
        raise QuestImportError(str(error), file=str(path), line=line_no) from error


def _parse_file(path: Path, index: dict[str, str], *, machine_fields: bool) -> _ParsedQuest:
    """Parse one quest file.

    ``machine_fields`` is False for EN: those fields are read from PL only (D2),
    so finding one here means someone edited the translation expecting it to
    matter. Warn rather than obey.
    """
    if not path.exists():
        raise QuestImportError(f"file not found: {path}", file=str(path))

    quest = _ParsedQuest(key=_key_of(path), path=path)
    in_notes = False

    for idx, raw in enumerate(path.read_text(encoding="utf-8").splitlines()):
        line_no = idx + 1
        line = raw.strip()

        if _NOTES_RE.match(line):
            # `## Notatki` and anything after it is for the author, not the game.
            in_notes = True
            continue

        if in_notes:
            if _FIELD_RE.match(line):
                print(
                    f"{path}:{line_no}: warning: '{line.split(':', 1)[0]}' sits below a "
                    f"'##' heading, where the importer stops reading — move it above",
                    file=sys.stderr,
                )
            continue

        title = _TITLE_RE.match(line)
        if title and not quest.title:
            quest.title = title.group("title")
            quest.line = line_no
            continue

        if not quest.title:
            continue  # frontmatter, before the title

        field_match = _FIELD_RE.match(line)
        if field_match:
            _apply_field(quest, field_match, path, line_no, index, machine_fields=machine_fields)
            continue

        # A blank line is data: it is the author's paragraph break (see
        # `_join_prose`). Leading blanks - between the H1 and the first sentence -
        # are not, so they are dropped rather than opening an empty paragraph.
        if line or quest.description:
            quest.description.append(line)

    if not quest.title:
        raise QuestImportError(
            "no title found (expected a '# Tytuł questa' heading)", file=str(path)
        )
    return quest


def _apply_field(
    quest: _ParsedQuest,
    match: re.Match[str],
    path: Path,
    line_no: int,
    index: dict[str, str],
    *,
    machine_fields: bool,
) -> None:
    raw_name = match.group("name").strip()
    value = match.group("value").strip()
    name = _FIELD_ALIASES.get(raw_name.casefold())

    if name is None:
        raise QuestImportError(
            f"unknown field {raw_name!r} (allowed: "
            f"{', '.join(sorted(set(_FIELD_ALIASES.values())))})",
            file=str(path),
            line=line_no,
        )

    if name in _MACHINE_FIELDS and not machine_fields:
        print(
            f"{path}:{line_no}: warning: '{raw_name}' is read from the PL file only "
            f"and is ignored here; quest logic lives in PL (D2)",
            file=sys.stderr,
        )
        return

    if not value and name != "test":
        raise QuestImportError(f"field {raw_name!r} is empty", file=str(path), line=line_no)

    if name in _EXPRESSION_FIELDS:
        value = _expand_expression(value, index, path, line_no, label=f"field {raw_name!r}")

    if name == "success":
        quest.success = value
    elif name == "completion":
        quest.completion = value
    elif name == "test":
        quest.test = value or None
    elif name == "requires":
        quest.requires = _parse_requires(value, index, path, line_no)
    elif name == "progress":
        quest.progress, quest.progress_total = _parse_progress(value, path, line_no)
    elif name == "reward":
        quest.rewards.append(_parse_reward(value, path, line_no))


def _parse_requires(
    value: str, index: dict[str, str], path: Path, line_no: int
) -> list[str]:
    """Every spelling of a quest reference -> the bare key.

    Which spelling an author reaches for is an Obsidian concern, not ours — all
    of these are the same edge in the graph:

    - ``[[Q01_S01 Dowiedz się więcej o klątwie]]`` — by note name, which is what
      Obsidian's autocomplete offers and what the graph view draws.
    - ``[[Q01_S01_LEARN_ABOUT_CURSE]]`` — by alias, i.e. by the key itself; the
      alias resolves the note, so the link survives renaming the file.
    - ``Q01_S01_LEARN_ABOUT_CURSE`` — bare key, still accepted.

    A link to something that is not a quest survives parsing and dies in
    ``init_quests`` as a dangling ``requires`` — which names the offender, and is
    exactly what should happen.

    Several are separated by commas.
    """
    keys: list[str] = []
    for raw in value.split(","):
        item = raw.strip().strip("`").strip()
        if not item:
            continue

        wiki = _WIKI_RE.fullmatch(item)
        if wiki:
            target = wiki.group("target").strip()
            anchor = (wiki.group("anchor") or "").strip()
            # A `#`-anchored link named a section back when a file held a whole
            # chain; the anchor is the key, and it still is.
            candidate = anchor or target
            item = _resolve_entity(candidate, index) or candidate
        elif "[[" in item or "]]" in item:
            raise QuestImportError(
                f"requires {item!r} looks like a broken wikilink",
                file=str(path),
                line=line_no,
            )
        else:
            item = _resolve_entity(item, index) or item

        if item:
            keys.append(item)
    return keys


def _parse_progress(value: str, path: Path, line_no: int) -> tuple[str, int]:
    """``item_count("X") / 3`` -> ``('item_count("X")', 3)``."""
    if "/" not in value:
        raise QuestImportError(
            f"progress must read '<expression> / <total>', got {value!r}",
            file=str(path),
            line=line_no,
        )
    expression, _, total = value.rpartition("/")
    expression = expression.strip()
    try:
        parsed_total = int(total.strip())
    except ValueError:
        raise QuestImportError(
            f"progress total must be a whole number, got {total.strip()!r}",
            file=str(path),
            line=line_no,
        ) from None
    return expression, parsed_total


def _parse_reward(value: str, path: Path, line_no: int) -> dict[str, Any]:
    """``add_money(50)``, ``add_n_items(2,"MERMAIDS_TEAR")``, ``shift_sentiment_of("BARMAN",10)``.

    Wchodzi wywołanie już po :func:`_expand_expression` (bez backquote'ów,
    wikilinki zamienione na klucze) - ta sama gramatyka, którą pisze się efekt
    węzła dialogu, bo to ta sama rzecz: zmiana stanu gracza (:mod:`dialog.effects`).
    """
    legacy = _LEGACY_REWARD_RE.match(value)
    if legacy:
        raise QuestImportError(
            f"reward {value!r} uses the old grammar; rewards are calls now, "
            f"e.g. `add_money(50)`, `raise_max_health(20)` or "
            f"`add_n_items(1,`[[ITEM]]`)`",
            file=str(path),
            line=line_no,
        )

    try:
        effect = parse_effect(value, EffectScope.quest)
    except EffectError as error:
        raise QuestImportError(str(error), file=str(path), line=line_no) from error

    category = _REWARD_CATEGORIES[effect.name]
    if category == "items":
        return {"category": category, "items": list(effect.items)}

    reward: dict[str, Any] = {"category": category, "value": effect.value}
    if effect.target:
        reward["target"] = effect.target
    return reward


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def import_quest(
    src_dir: Path, key: str, vault: VaultIndex | None = None
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    """Import one quest file (PL + EN) into ``(messages, {key: entry})``."""
    vault = build_vault_index(src_dir) if vault is None else vault

    pl_path = _find_quest_file(src_dir, "PL", key)
    en_path = _find_quest_file(src_dir, "EN", key)

    pl_quest = _parse_file(pl_path, vault.keys, machine_fields=True)
    en_quest = _parse_file(en_path, vault.keys, machine_fields=False)
    _validate_parsed(pl_quest, key, pl_path)
    _validate_translation(en_quest, key, en_path)

    name_key = f"{MESSAGE_PREFIX}{key}_NAME"
    description_key = f"{MESSAGE_PREFIX}{key}_DESCRIPTION"
    success_key = f"{MESSAGE_PREFIX}{key}_SUCCESS"

    # Prose is where the player meets an entity, so a wikilink becomes the
    # RichText span the game colours (`[char]`, `[loc]`, `[item]`). Emphasis is
    # converted *before* the links, while the text is still plain Markdown: after
    # `render_links` the string is full of `[tag]` spans that an emphasis regex
    # has no business walking into.
    messages: dict[str, dict[str, str]] = {
        lang: {
            name_key: render_links(_convert_emphasis(quest.title), vault, lang),
            description_key: render_links(
                _convert_emphasis(_join_prose(quest.description)), vault, lang
            ),
            success_key: render_links(_convert_emphasis(quest.success), vault, lang),
        }
        for lang, quest in (("PL", pl_quest), ("EN", en_quest))
    }

    entry: dict[str, Any] = {
        "name": name_key,
        "description": description_key,
        "success": success_key,
        "completion": pl_quest.completion,
    }
    if pl_quest.test:
        entry["test"] = pl_quest.test
    if pl_quest.requires:
        entry["requires"] = pl_quest.requires
    if pl_quest.progress:
        entry["progress"] = pl_quest.progress
        entry["progress_total"] = pl_quest.progress_total
    if pl_quest.rewards:
        entry["rewards"] = pl_quest.rewards

    return messages, {key: entry}


def _assign_parents(quests: dict[str, Any], paths: dict[str, Path]) -> None:
    """``parent`` from the key (D1): ``Qxx_Syy_...`` is a step of ``Qxx_S00_...``.

    Derived rather than written down, because a step that names its own parent is
    a step that can name the wrong one. The cost is that the numbering carries
    meaning: an umbrella is step ``00``, and a chain without one is an error here
    rather than a set of orphans nobody notices.
    """
    umbrellas: dict[str, str] = {}
    for key in quests:
        chain, step = _split_key(key, paths[key])
        if step == _UMBRELLA_STEP:
            if chain in umbrellas:
                raise QuestImportError(
                    f"chain {chain} has two umbrellas ({umbrellas[chain]} and {key}) — "
                    f"step {_UMBRELLA_STEP} is the umbrella, so there can be only one",
                    file=str(paths[key]),
                )
            umbrellas[chain] = key

    for key, entry in quests.items():
        chain, step = _split_key(key, paths[key])
        if step == _UMBRELLA_STEP:
            continue
        umbrella = umbrellas.get(chain)
        if umbrella is None:
            raise QuestImportError(
                f"quest {key!r} is a step of chain {chain}, which has no umbrella — "
                f"expected a quest keyed {chain}_S{_UMBRELLA_STEP}_...",
                file=str(paths[key]),
            )
        entry["parent"] = umbrella


def _validate_parsed(quest: _ParsedQuest, key: str, path: Path) -> None:
    """Check what only the source file can tell us; the rest is init_quests' job."""
    if not quest.success:
        raise QuestImportError(
            f"quest {key!r} has no '**Sukces**:' line", file=str(path), line=quest.line
        )
    if not quest.description:
        raise QuestImportError(
            f"quest {key!r} has no description prose", file=str(path), line=quest.line
        )
    if not quest.completion:
        raise QuestImportError(
            f"quest {key!r} has no '**Completion**:' line", file=str(path), line=quest.line
        )

    # Validate conditions here, against the quest scope, so a typo names its file
    # and line instead of evaluating to a silent False for the rest of the game.
    # Test is a yes/no condition; Postęp drives a bar and must be numeric, so it
    # gets the stricter check — otherwise `Postęp: has_item("X")` imports fine and
    # crashes the moment the journal opens (validate_number spells out why).
    checks = (("Test", quest.test, validate_condition), ("Postęp", quest.progress, validate_number))
    for label, expression, validator in checks:
        if not expression:
            continue
        try:
            validator(expression, ConditionScope.quest)
        except ConditionError as error:
            raise QuestImportError(
                f"quest {key!r} has an invalid {label}: {error}",
                file=str(path),
                line=quest.line,
            ) from error


def _validate_translation(quest: _ParsedQuest, key: str, path: Path) -> None:
    """PL and EN must describe the same quest, and EN must actually be written."""
    if not quest.title or not quest.success or not quest.description:
        raise QuestImportError(
            f"quest {key!r} is not fully translated (needs a title, Success and prose)",
            file=str(path),
            line=quest.line,
        )


def import_quests(
    src_dir: Path, keys: list[str]
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    """Import several quests and merge them, then validate the whole graph.

    The graph check runs on the merged set on purpose: ``requires`` crosses
    chains, so no single file can be validated alone.
    """
    messages: dict[str, dict[str, str]] = {"PL": {}, "EN": {}}
    quests: dict[str, Any] = {}
    paths: dict[str, Path] = {}
    vault = build_vault_index(src_dir)

    for key in keys:
        quest_messages, quest_entry = import_quest(src_dir, key, vault)
        for lang in ("PL", "EN"):
            messages[lang].update(quest_messages[lang])
        if key in quests:
            raise QuestImportError(f"duplicate quest key {key!r}")
        quests.update(quest_entry)
        paths[key] = _find_quest_file(src_dir, "PL", key)

    _assign_parents(quests, paths)

    # Dangling requires, completion modes that can never fire, dependency cycles.
    try:
        init_quests(quests)
    except ValueError as error:
        raise QuestImportError(str(error)) from error

    return messages, quests


def _predicate_args(expression: str, name: str) -> list[list[str]]:
    """Every string-literal argument list passed to predicate ``name`` in ``expression``.

    The expression has already been whitelist-validated, so this walk only ever
    sees the shapes the mini-DSL allows.
    """
    calls: list[list[str]] = []
    for node in ast.walk(ast.parse(expression, mode="eval")):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
            and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in node.args)
        ):
            calls.append([a.value for a in node.args])  # type: ignore[attr-defined]
    return calls


def validate_references(
    quests: dict[str, Any], dialogs: dict[str, Any], items: dict[str, Any]
) -> list[str]:
    """Check that every key a quest condition names actually exists.

    This is the check that would have caught ``SARCASMIA_AA_BACK_SO_SOON``: a
    quest whose ``test`` names a dialog node that does not exist parses fine,
    validates fine, and then sits at ``False`` for the entire game. The mini-DSL
    cannot catch it (the string is a valid argument) and neither can
    ``init_quests`` (it never sees the dialogs), so it has to happen here, where
    the whole config is on the table.

    Returns a list of human-readable problems; empty means clean.
    """
    problems: list[str] = []

    for key, quest in quests.items():
        for label, expression in (("test", quest.get("test")), ("progress", quest.get("progress"))):
            if not expression:
                continue

            for args in _predicate_args(expression, "visited"):
                if len(args) != 2:
                    continue  # quest scope forces 2; anything else already failed
                npc, node = args
                if npc not in dialogs:
                    problems.append(
                        f"{key}: {label} names character {npc!r}, which has no dialog "
                        f"(known: {', '.join(sorted(dialogs)) or 'none'})"
                    )
                elif node not in dialogs[npc].get("DIALOG_NODES", {}):
                    problems.append(
                        f"{key}: {label} names node {node!r} of {npc!r}, which does not exist "
                        f"— the quest could never complete"
                    )

            for args in _predicate_args(expression, "quest_done"):
                if args and args[0] not in quests:
                    problems.append(f"{key}: {label} names unknown quest {args[0]!r}")

            for predicate in ("has_item", "item_count"):
                for args in _predicate_args(expression, predicate):
                    if args and args[0] not in items:
                        problems.append(f"{key}: {label} names unknown item {args[0]!r}")

        for reward in quest.get("rewards", []):
            for item_key in reward.get("items", []):
                if item_key not in items:
                    problems.append(f"{key}: reward names unknown item {item_key!r}")

            target = reward.get("target")
            if target and target not in dialogs:
                problems.append(
                    f"{key}: sentiment reward targets {target!r}, which has no dialog "
                    f"— nobody would ever like you more"
                )

    return problems


def collect_message_references(quests: dict[str, Any]) -> set[str]:
    """Every message key the quests point at (used by the orphan sweep)."""
    refs: set[str] = set()
    for entry in quests.values():
        for name in ("name", "description", "success"):
            if entry.get(name):
                refs.add(entry[name])
    return refs


def build_quest_config(
    src_dir: Path | None = None,
    config_path: Path | None = None,
    chains: list[str] | None = None,
) -> int:
    """Rebuild the ``quests`` + quest ``messages`` sections of ``config.json``.

    ``chains`` names quest keys, or the ``Qxx`` shorthand for a whole chain —
    resolution happens here, at the CLI boundary, so :func:`import_quests` stays
    exact.

    Unlike the dialog importer, a broken quest file is never skipped with a
    warning: a quest that fails to import is a quest that silently does not exist
    in game, which is the whole class of bug this epic is removing. Import all or
    change nothing.
    """
    src_dir = src_dir or _DEFAULT_QUEST_SRC
    config_path = config_path or _DEFAULT_CONFIG_PATH

    try:
        if chains is None:
            keys = discover_quest_keys(src_dir)
        else:
            keys = sorted({k for c in chains for k in _resolve_chain(src_dir, c)})
    except QuestImportError as error:
        print(f"Quest import failed: {error}", file=sys.stderr)
        return 1

    if not keys:
        print(f"No quests found under {src_dir} — nothing to import.")
        return 0

    if not config_path.exists():
        print(f"config.json not found: {config_path}", file=sys.stderr)
        return 1

    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    try:
        messages, quests = import_quests(src_dir, keys)
    except QuestImportError as error:
        print(f"Quest import failed: {error}", file=sys.stderr)
        print("config.json left untouched.", file=sys.stderr)
        return 1

    # Cross-section checks: only here is the whole config visible, so only here
    # can we tell that a quest points at a dialog node or item nobody defines.
    problems = validate_references(quests, config.get("dialogs", {}), config.get("items", {}))
    if problems:
        print(f"Quest import failed: {len(problems)} broken reference(s):", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print("config.json left untouched.", file=sys.stderr)
        return 1

    existing_messages: dict[str, dict[str, str]] = config.get("messages", {"PL": {}, "EN": {}})
    for lang in ("PL", "EN"):
        existing_messages.setdefault(lang, {})
        existing_messages[lang].update(messages[lang])

    # Sweep our own namespace only: message keys we no longer reference. Dialog
    # keys are not ours to delete (and vice versa - see the dialog importer).
    referenced = collect_message_references(quests)
    for lang in ("PL", "EN"):
        orphaned = {
            key
            for key in existing_messages[lang]
            if key.startswith(MESSAGE_PREFIX) and key not in referenced
        }
        for key in orphaned:
            del existing_messages[lang][key]
        if orphaned:
            print(f"Removed {len(orphaned)} orphaned quest message key(s) from {lang}")

    config["messages"] = existing_messages
    config["quests"] = quests

    with config_path.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
        f.write("\n")

    print(f"Imported {len(quests)} quest(s): {', '.join(quests)}")
    print(f"Written: {config_path}")
    return 0


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.exit(build_quest_config(chains=argv or None))


if __name__ == "__main__":
    main()


__all__ = [
    "MESSAGE_PREFIX",
    "QuestImportError",
    "build_vault_index",
    "build_quest_config",
    "collect_message_references",
    "discover_quest_keys",
    "import_quest",
    "import_quests",
    "validate_references",
]
