"""Markdown -> quest config importer (build-time tool, desktop only).

Sibling of ``dialog/markdown_importer.py``, same shape: read the ``doc/``
Obsidian vault, emit the ``quests`` and ``messages`` sections of
``config.json``. Run via ``just import-quests``.

Source layout (decision **D1**: one file = one chain)::

    doc/PL/Misje/Znajdz kogos kto wie o klatwach.md   <- source of truth
    doc/EN/Quests/Find someone who knows about curses.md  <- prose only

The file name is the localized chain title; the chain key lives in the
frontmatter ``aliases`` (e.g. ``Q03``), exactly like characters. Each ``## S01``
section is one quest, and its config key is ``<chain>_<section>``, so
``## S01_WHO_HAS_MORE_KNOWLEDGE`` in chain ``Q03`` becomes
``Q03_S01_WHO_HAS_MORE_KNOWLEDGE``.

Section body (decision **D2**: machine fields live in the body, not in
frontmatter, because subquests cannot fit in YAML)::

    ## S01_WHO_HAS_MORE_KNOWLEDGE

    **Tytuł**: Kto ma wiedzę o magii?

    Barman wspomniał, że ktoś w miasteczku zna się na klątwach.

    **Completion**: test
    **Test**: visited("POTIONEER_PUZZLEMINT", "014")
    **Sukces**: Puzzlemint wie o klątwach więcej, niż chciałby przyznać.
    **Nagroda**: money=50

Anything that is not a ``**Field**:`` line is prose and becomes the quest
description. Field names accept PL or EN spelling (``Tytuł``/``Title``), so the
EN file reads naturally.

**Machine fields are read from PL only** (decision D2). The EN file supplies
``Tytuł`` / ``Sukces`` / prose and nothing else; a ``**Test**:`` written there is
ignored with a warning. This is what makes the EN file safe to regenerate with an
LLM: the worst it can do is write bad prose, never break the quest logic.

``parent`` is implied by the file (D1): the ``S00`` section is the chain's
umbrella and every other section in the file is one of its steps. Cross-chain
edges are explicit, via ``**Requires**:`` with full quest keys.

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

from dialog.conditions import ConditionError, ConditionScope, validate_condition
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

_SECTION_RE = re.compile(r"^##\s+(?P<key>[A-Z][A-Z0-9_]*)\s*$")
_FIELD_RE = re.compile(r"^\*\*(?P<name>[^*]+)\*\*\s*:\s*(?P<value>.*)$")
_ALIAS_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# The umbrella section of a chain. Everything else in the file is its step.
_UMBRELLA_SECTION = "S00"

# PL or EN spelling -> canonical field name.
_FIELD_ALIASES: dict[str, str] = {
    "tytuł": "title", "tytul": "title", "title": "title",
    "sukces": "success", "success": "success",
    "completion": "completion", "ukończenie": "completion", "ukonczenie": "completion",
    "test": "test",
    "requires": "requires", "wymaga": "requires",
    "postęp": "progress", "postep": "progress", "progress": "progress",
    "nagroda": "reward", "reward": "reward",
}

# Read from PL only (D2). In EN they are ignored, loudly.
_MACHINE_FIELDS = frozenset({"completion", "test", "requires", "progress", "reward"})

_REWARD_RE = re.compile(r"^(?P<category>[a-z_]+)\s*=\s*(?P<value>.+)$")


@dataclass(slots=True)
class _ParsedQuest:
    """One ``## S01`` section, before it becomes config."""

    section: str
    line: int
    title: str = ""
    description: list[str] = field(default_factory=list)
    success: str = ""
    completion: str = ""
    test: str | None = None
    requires: list[str] = field(default_factory=list)
    progress: str | None = None
    progress_total: int = 0
    rewards: list[dict[str, Any]] = field(default_factory=list)


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


def _parse_aliases(text: str, path: str) -> list[str]:
    """Pull the ``aliases`` list out of the YAML frontmatter.

    Deliberately tiny: the vault has no YAML parser dependency, and the only
    frontmatter a quest file needs is its chain key.
    """
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "---"), None)
    if start is None:
        return []
    end = next((i for i in range(start + 1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return []

    aliases: list[str] = []
    in_aliases = False
    for line in lines[start + 1:end]:
        stripped = line.strip()
        if stripped.startswith("aliases:"):
            in_aliases = True
            inline = stripped[len("aliases:"):].strip()
            if inline.startswith("[") and inline.endswith("]"):
                aliases.extend(a.strip().strip("\"'") for a in inline[1:-1].split(",") if a.strip())
                in_aliases = False
            continue
        if in_aliases:
            if stripped.startswith("- "):
                aliases.append(stripped[2:].strip().strip("\"'"))
                continue
            in_aliases = False
    return [a for a in aliases if a]


def _chain_key_of(path: Path) -> str:
    """The chain's config key: the UPPER_SNAKE alias in the frontmatter."""
    aliases = _parse_aliases(path.read_text(encoding="utf-8"), str(path))
    key = next((a for a in aliases if _ALIAS_RE.match(a)), "")
    if not key:
        raise QuestImportError(
            "no chain key in frontmatter aliases (expected an UPPER_SNAKE alias, e.g. 'Q03')",
            file=str(path),
        )
    return key


def _discover_chain_keys(src_dir: Path) -> list[str]:
    """Every chain key declared in the PL quest directory, sorted."""
    try:
        pl_dir = _lang_dir(src_dir, "PL")
    except QuestImportError:
        return []
    keys: list[str] = []
    for path in sorted(pl_dir.glob("*.md")):
        try:
            keys.append(_chain_key_of(path))
        except QuestImportError:
            continue
    return sorted(keys)


def _find_chain_file(src_dir: Path, lang: str, chain_key: str) -> Path:
    lang_dir = _lang_dir(src_dir, lang)
    for path in sorted(lang_dir.glob("*.md")):
        try:
            if _chain_key_of(path) == chain_key:
                return path
        except QuestImportError:
            continue
    raise QuestImportError(
        f"no Markdown file with chain alias {chain_key!r} in {lang_dir}",
        file=str(lang_dir),
    )


def _parse_file(path: Path, *, machine_fields: bool) -> dict[str, _ParsedQuest]:
    """Parse one chain file into ``{section: _ParsedQuest}``, in file order.

    ``machine_fields`` is False for EN: those fields are read from PL only (D2),
    so finding one here means someone edited the translation expecting it to
    matter. Warn rather than obey.
    """
    if not path.exists():
        raise QuestImportError(f"file not found: {path}", file=str(path))

    quests: dict[str, _ParsedQuest] = {}
    current: _ParsedQuest | None = None

    for idx, raw in enumerate(path.read_text(encoding="utf-8").splitlines()):
        line_no = idx + 1
        line = raw.strip()

        section = _SECTION_RE.match(line)
        if section:
            key = section.group("key")
            if key in quests:
                raise QuestImportError(f"duplicate section {key!r}", file=str(path), line=line_no)
            current = _ParsedQuest(section=key, line=line_no)
            quests[key] = current
            continue

        if current is None:
            continue  # frontmatter / chain-level prose before the first section

        field_match = _FIELD_RE.match(line)
        if field_match:
            _apply_field(current, field_match, path, line_no, machine_fields=machine_fields)
            continue

        if line:
            current.description.append(line)

    if not quests:
        raise QuestImportError(
            "no quest sections found (expected at least one '## S00_...' heading)",
            file=str(path),
        )
    return quests


def _apply_field(
    quest: _ParsedQuest,
    match: re.Match[str],
    path: Path,
    line_no: int,
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

    if name == "title":
        quest.title = value
    elif name == "success":
        quest.success = value
    elif name == "completion":
        quest.completion = value
    elif name == "test":
        quest.test = value or None
    elif name == "requires":
        quest.requires = [r.strip() for r in value.split(",") if r.strip()]
    elif name == "progress":
        quest.progress, quest.progress_total = _parse_progress(value, path, line_no)
    elif name == "reward":
        quest.rewards.append(_parse_reward(value, path, line_no))


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
    """``money=50`` or ``items=MERMAIDS_TEAR, PHOENIX_FEATHER``."""
    match = _REWARD_RE.match(value)
    if not match:
        raise QuestImportError(
            f"reward must read '<category>=<value>', got {value!r}",
            file=str(path),
            line=line_no,
        )
    category = match.group("category")
    raw_value = match.group("value").strip()

    if category == "items":
        return {"category": "items", "items": [i.strip() for i in raw_value.split(",") if i.strip()]}

    try:
        return {"category": category, "value": int(raw_value)}
    except ValueError:
        raise QuestImportError(
            f"reward {category!r} needs a whole number, got {raw_value!r}",
            file=str(path),
            line=line_no,
        ) from None


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def import_quest_chain(
    src_dir: Path, chain_key: str
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    """Import one chain file (PL + EN) into ``(messages, quests)``."""
    pl_path = _find_chain_file(src_dir, "PL", chain_key)
    en_path = _find_chain_file(src_dir, "EN", chain_key)

    pl_quests = _parse_file(pl_path, machine_fields=True)
    en_quests = _parse_file(en_path, machine_fields=False)
    _validate_language_consistency(pl_quests, en_quests, chain_key, pl_path, en_path)

    if _UMBRELLA_SECTION not in {s.split("_")[0] for s in pl_quests}:
        raise QuestImportError(
            f"chain {chain_key!r} has no '{_UMBRELLA_SECTION}' section — every chain needs "
            f"its umbrella, and the other sections take it as their parent",
            file=str(pl_path),
        )

    umbrella_key = next(
        f"{chain_key}_{section}"
        for section in pl_quests
        if section.split("_")[0] == _UMBRELLA_SECTION
    )

    messages: dict[str, dict[str, str]] = {"PL": {}, "EN": {}}
    quests: dict[str, Any] = {}

    for section, pl_quest in pl_quests.items():
        en_quest = en_quests[section]
        key = f"{chain_key}_{section}"
        _validate_parsed(pl_quest, key, pl_path)

        name_key = f"{MESSAGE_PREFIX}{key}_NAME"
        description_key = f"{MESSAGE_PREFIX}{key}_DESCRIPTION"
        success_key = f"{MESSAGE_PREFIX}{key}_SUCCESS"

        messages["PL"][name_key] = pl_quest.title
        messages["PL"][description_key] = " ".join(pl_quest.description)
        messages["PL"][success_key] = pl_quest.success
        messages["EN"][name_key] = en_quest.title
        messages["EN"][description_key] = " ".join(en_quest.description)
        messages["EN"][success_key] = en_quest.success

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
        if key != umbrella_key:
            # D1: the file *is* the thread, so parent is implied rather than
            # repeated on every step (one less thing to get wrong).
            entry["parent"] = umbrella_key

        quests[key] = entry

    return messages, quests


def _validate_parsed(quest: _ParsedQuest, key: str, path: Path) -> None:
    """Check what only the source file can tell us; the rest is init_quests' job."""
    for name, value in (("Tytuł", quest.title), ("Sukces", quest.success)):
        if not value:
            raise QuestImportError(
                f"quest {key!r} has no '**{name}**:' line", file=str(path), line=quest.line
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
    for label, expression in (("Test", quest.test), ("Postęp", quest.progress)):
        if not expression:
            continue
        try:
            validate_condition(expression, ConditionScope.quest)
        except ConditionError as error:
            raise QuestImportError(
                f"quest {key!r} has an invalid {label}: {error}",
                file=str(path),
                line=quest.line,
            ) from error


def _validate_language_consistency(
    pl_quests: dict[str, _ParsedQuest],
    en_quests: dict[str, _ParsedQuest],
    chain_key: str,
    pl_path: Path,
    en_path: Path,
) -> None:
    """PL and EN must describe the same chain — same sections, both translated."""
    pl_keys, en_keys = set(pl_quests), set(en_quests)
    if pl_keys != en_keys:
        raise QuestImportError(
            f"PL/EN section mismatch for chain {chain_key!r}: "
            f"missing in PL={sorted(en_keys - pl_keys)}, missing in EN={sorted(pl_keys - en_keys)}",
            file=str(en_path),
        )
    for section, en_quest in en_quests.items():
        if not en_quest.title or not en_quest.success or not en_quest.description:
            raise QuestImportError(
                f"section {section!r} is not fully translated (needs Title, Success and prose)",
                file=str(en_path),
                line=en_quest.line,
            )


def import_quests(src_dir: Path, chain_keys: list[str]) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    """Import several chains and merge them, then validate the whole graph.

    The graph check runs on the merged set on purpose: ``requires`` crosses
    chains, so no single file can be validated alone.
    """
    messages: dict[str, dict[str, str]] = {"PL": {}, "EN": {}}
    quests: dict[str, Any] = {}

    for chain_key in chain_keys:
        chain_messages, chain_quests = import_quest_chain(src_dir, chain_key)
        for lang in ("PL", "EN"):
            messages[lang].update(chain_messages[lang])
        for key, entry in chain_quests.items():
            if key in quests:
                raise QuestImportError(f"duplicate quest key {key!r} across chains")
            quests[key] = entry

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
    chain_keys: list[str] | None = None,
) -> int:
    """Rebuild the ``quests`` + quest ``messages`` sections of ``config.json``.

    Unlike the dialog importer, a broken quest file is never skipped with a
    warning: a quest that fails to import is a quest that silently does not exist
    in game, which is the whole class of bug this epic is removing. Import all or
    change nothing.
    """
    src_dir = src_dir or _DEFAULT_QUEST_SRC
    config_path = config_path or _DEFAULT_CONFIG_PATH

    if chain_keys is None:
        chain_keys = _discover_chain_keys(src_dir)
    if not chain_keys:
        print(f"No quest chains found under {src_dir} — nothing to import.")
        return 0

    if not config_path.exists():
        print(f"config.json not found: {config_path}", file=sys.stderr)
        return 1

    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    try:
        messages, quests = import_quests(src_dir, chain_keys)
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

    print(f"Imported {len(quests)} quest(s) from {len(chain_keys)} chain(s): {', '.join(chain_keys)}")
    print(f"Written: {config_path}")
    return 0


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    sys.exit(build_quest_config(chain_keys=argv or None))


if __name__ == "__main__":
    main()


__all__ = [
    "MESSAGE_PREFIX",
    "QuestImportError",
    "build_quest_config",
    "collect_message_references",
    "import_quest_chain",
    "import_quests",
]
