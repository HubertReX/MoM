"""Render the quest DAG from ``config.json`` as an interactive Obsidian note.

Quests form a directed acyclic graph: ``requires`` says what must be *done*
first, ``parent`` says which thread a step belongs to (and must be *unlocked*).
Both are unlock edges, and the shape they make - which thread gates which, how
deep a chain runs, what opens at the start - is a picture, not a paragraph.

A third gate is drawn too, in a different shape on purpose. ``requires_test``
opens a quest on a fact about the *world* - almost always "the player has heard
about it", i.e. ``visited(NPC, NODE)``. The conversation that triggers a thread
is the one thing an author cannot find from the quest file alone, and it was
invisible here: a quest gated only that way sat unconnected, looking like a
starting point. Each such node gets its own hexagon, linked to the character
note it lives in, so the picture answers "what makes this appear?".

What this reuses from ``scripts/dialog_graph.py``: the vendored
``_graphs/lib/vis-network.min.js`` (loaded, not copied), the ``_graphs/data/``
convention, and the DataviewJS note pattern. What it does *not* reuse is the
``DialogGraph`` model - a quest has no options, no sentiment and no resume
edge, so bending it through that shape would cost more than it saves.

The graph is built by the game's own :func:`quest.graph.init_quests`, so a
config that renders here is a config the game can run, and every malformed one
fails here exactly as it fails at import.

**This is an author's tool, not a validator.** ``validate_references()`` (Q-04)
already rejects dangling references, cycles and the ``Q01_S07`` corpse at import
time - earlier, and without looking at a picture. The one thing left that config
alone cannot answer is asked here: :func:`uncloseable`.

Usage::

    .venv/bin/python scripts/quest_graph.py
    .venv/bin/python scripts/quest_graph.py --lang EN --out /tmp/graphs
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "project"))

from dialog.vault_links import KIND_BY_SUBDIR, note_key  # noqa: E402
from quest import markdown_importer as qi  # noqa: E402
from quest.entities import CompletionMode, QuestDef  # noqa: E402
from quest.graph import children_of, init_quests  # noqa: E402
from ui.text.markup import parse, strip_tags  # noqa: E402
from ui.text.style import Style  # noqa: E402

DOC_DIR = _REPO_ROOT / "doc"
DEFAULT_OUT = DOC_DIR / "_graphs"
CONFIG_JSON = _REPO_ROOT / "project" / "config_model" / "config.json"

# One note for every chain, unlike dialogs (one per character): the whole point
# is seeing the edges that cross chains - Q03 gating on a step of Q01 is
# invisible in either file on its own.
DATA_KEY = "QUESTS"
NOTE_STEM = "Questy - graf"

# Colour by completion mode - what closes this quest. The panel (Q-08) colours by
# *state* (done / active / locked); the graph has no savegame and must not
# pretend otherwise, so it answers a different question with a different palette.
MODE_COLOUR: dict[CompletionMode, dict[str, str]] = {
    CompletionMode.test: {"bg": "#a5d8ff", "border": "#1971c2"},
    CompletionMode.all_subquests: {"bg": "#b2f2bb", "border": "#2f9e44"},
    CompletionMode.manual: {"bg": "#ffd8a8", "border": "#f08c00"},
}
MODE_LABEL: dict[CompletionMode, str] = {
    CompletionMode.test: "warunek zamyka ją sam",
    CompletionMode.all_subquests: "zamyka się, gdy zamkną się jej kroki",
    CompletionMode.manual: "zamyka ją tylko kod gry",
}

# A dialog node is not a quest and must not read as one: different shape
# (hexagon), different palette, different edge. The graph already spends green /
# blue / orange on "what closes this quest", so violet is the only free slot -
# and being *outside* that scale is the point, since this node is not a quest at
# all and has no completion mode to colour by.
DIALOG_COLOUR: dict[str, str] = {"bg": "#e5dbff", "border": "#7048e8"}

# `## 023`, `## 015-end`, `## 005-end [011](#011)` - the heading that holds one
# dialog node. Only the leading number is the node key the config uses; the rest
# is the author's bookkeeping and belongs in the anchor, not in the key.
_NODE_HEADING_RE = re.compile(r"^##\s+(?P<key>\d+)(?P<suffix>\S*)\s*(?P<rest>.*?)\s*$")

REWARD_UNIT: dict[str, str] = {
    "money": "złota",
    "health": "HP",
    "max_health": "max HP",
    "damage": "obrażeń",
    "max_items": "slotów",
    "sentiment": "sympatii",
}


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def read_quests(
    config_path: Path = CONFIG_JSON, *, lang: str = "PL"
) -> tuple[dict[str, QuestDef], dict[str, str]]:
    """``(defs, messages)`` from config.json, built by the game's own builder."""
    config = json.loads(config_path.read_text(encoding="utf-8"))
    defs = init_quests(config.get("quests", {}))
    messages = config.get("messages", {}).get(lang, {})
    return defs, messages


def source_links(src_dir: Path = DOC_DIR, *, lang: str = "PL") -> dict[str, str]:
    """``{quest_key: "<file stem>"}`` for the double-click jump.

    One file is one quest, so the link is just the note - nothing to compose and
    no anchor to keep in sync. A quest the vault does not have simply gets no
    link: the graph is still drawable, and config.json is the source of truth for
    the shape.
    """
    links: dict[str, str] = {}
    try:
        lang_dir = qi._lang_dir(src_dir, lang)
    except qi.QuestImportError:
        return links

    for path in sorted(lang_dir.glob("*.md")):
        try:
            links[qi._key_of(path)] = path.stem
        except qi.QuestImportError:
            continue
    return links


@dataclass(slots=True)
class DialogSource:
    """One character's dialog, as far as this graph cares: where it is readable.

    ``anchors`` maps the config's node key onto the *heading* that holds it, which
    is not always the same string: the vault writes ``## 015-end`` (and sometimes
    ``## 005-end [011](#011)``) while the config key is plain ``015``. Linking to
    the bare key would land on a heading that does not exist, so the heading is
    read from the note rather than guessed from the key.
    """

    key: str
    name: str
    anchors: dict[str, str] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)

    def link(self, node: str) -> str | None:
        """``Barman Absyntnent#023`` - what ``openLinkText`` needs, or the bare note."""
        if not self.name:
            return None
        anchor = self.anchors.get(node)
        return f"{self.name}#{anchor}" if anchor else self.name


def dialog_sources(
    config_path: Path = CONFIG_JSON, src_dir: Path = DOC_DIR, *, lang: str = "PL"
) -> dict[str, DialogSource]:
    """``{npc_key: DialogSource}`` - the config's dialogs, matched to their notes.

    Two halves, deliberately: the **config** says which nodes exist and which
    message each one speaks (that is what the game runs), the **vault** says where
    to click through to. A character with dialog but no note still gets an entry,
    just without a link - the graph is drawable either way, and config.json stays
    the source of truth for the shape.
    """
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    sources: dict[str, DialogSource] = {}
    for npc, section in (config.get("dialogs") or {}).items():
        nodes = (section or {}).get("DIALOG_NODES") or {}
        sources[npc] = DialogSource(
            npc,
            name="",
            texts={key: node.get("text", "") for key, node in nodes.items()},
        )

    for sub, kind in KIND_BY_SUBDIR.items():
        if kind != "char" or not sub.startswith(f"{lang}/"):
            continue
        for path in sorted((src_dir / sub).glob("*.md")):
            text = path.read_text(encoding="utf-8")
            key = note_key(text)
            source = sources.get(key)
            if source is None:
                continue  # a character note without dialog in the config
            source.name = path.stem
            for line in text.splitlines():
                heading = _NODE_HEADING_RE.match(line)
                if heading:
                    # `## 005-end [011](#011)` -> anchor `005-end`: the trailing
                    # markdown link is navigation the author added for themselves,
                    # and dragging it into the anchor only breaks the jump.
                    source.anchors[heading.group("key")] = (
                        heading.group("key") + heading.group("suffix")
                    )
    return sources


@dataclass(frozen=True, slots=True)
class VisitedRef:
    """One ``visited(npc, node)`` inside a condition, with its polarity.

    ``negated`` is not decoration. ``not visited(X)`` is the *opposite* claim -
    "this closes while the player has NOT had that conversation" - and drawing it
    as a plain arrow would state the reverse of what the quest does. It is the one
    piece of the boolean structure that a picture cannot afford to drop.
    """

    npc: str
    node: str
    negated: bool = False


def visited_refs(expression: str | None) -> list[VisitedRef]:
    """Every ``visited()`` in a condition, in source order, with polarity.

    An AST walk rather than a regex, and its own walk rather than the importer's
    ``_predicate_args``: that one finds calls but flattens ``not`` away, and here
    the ``not`` is half the meaning. Everything the quest scope allows is walked
    (``and`` / ``or`` / ``not`` / comparisons); anything else holds no dialog
    reference and is skipped rather than half-read.

    The expression has already been whitelist-validated at import, so a parse
    failure here means the config was hand-edited - the picture degrades to "no
    references" instead of taking the whole graph down with it.
    """
    if not expression:
        return []
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return []

    found: list[VisitedRef] = []

    def walk(node: ast.AST, negated: bool) -> None:
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            walk(node.operand, not negated)
        elif isinstance(node, ast.BoolOp):
            for value in node.values:
                walk(value, negated)
        elif isinstance(node, ast.Compare):
            walk(node.left, negated)
            for comparator in node.comparators:
                walk(comparator, negated)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id != "visited":
                return
            args = [
                a.value for a in node.args
                if isinstance(a, ast.Constant) and isinstance(a.value, str)
            ]
            if len(args) == 2:
                ref = VisitedRef(args[0], args[1], negated)
                if ref not in found:
                    found.append(ref)

    walk(tree.body, False)
    return found


def alternatives(expression: str | None) -> bool:
    """Are this condition's dialog nodes **alternatives** (``or``) rather than all required?

    The only piece of boolean structure worth one word on an edge. "Talk to either
    of these two" and "talk to both of these two" draw identically otherwise, and
    the difference is exactly the kind of thing an author wants to catch by eye.

    Deliberately shallow: it asks what the *outermost* operator is, and says
    nothing about a nested mix. A condition that needs more than that needs
    reading, not a diagram - and the quest's tooltip carries it verbatim.
    """
    if not expression or len(visited_refs(expression)) < 2:
        return False
    try:
        root = ast.parse(expression, mode="eval").body
    except SyntaxError:
        return False
    # De Morgan: under a `not`, an `or` of conversations is really "neither of
    # them", which is an AND of the negated edges the graph draws. Reporting it as
    # "either one" would label the edges with the opposite of what they mean.
    flipped = False
    while isinstance(root, ast.UnaryOp) and isinstance(root.op, ast.Not):
        root = root.operand
        flipped = not flipped
    if not isinstance(root, ast.BoolOp):
        return False
    return isinstance(root.op, ast.And) if flipped else isinstance(root.op, ast.Or)


# ---------------------------------------------------------------------------
# Analyze
# ---------------------------------------------------------------------------


def columns(defs: dict[str, QuestDef]) -> dict[str, int]:
    """Which **column** each quest sits in, left to right.

    The layout is horizontal and role-based, not a longest-path rank, because the
    two questions an author asks are "what is the sequence of this thread?" and
    "which conversation hangs off which step?" - and a rank ordering answers
    neither. It buries the thread's own steps at different depths (a step that
    waits on its sibling ranks one deeper, so the thread reads as a staircase) and
    it drops every dialog node into whatever row its arithmetic lands on.

    The pattern, per thread::

        [rozmowa otwierająca]  [WĄTEK]  [rozmowy z Test wątku]  [kroki]  [rozmowy z Test kroków]

    with two rules that make it fit on a screen:

    - **Every step of a thread shares one column**, stacked. Their order is carried
      by the ``requires`` arrows between them, which is where it belongs; spreading
      them across columns is what made the thread impossible to follow.
    - **An empty slot costs nothing.** A thread with no opening conversation starts
      at the far left; an umbrella with no ``test`` (the usual case, since it closes
      on its steps) puts its steps in the very next column. The slots are a
      template, not a reservation.

    A thread that waits on another chain starts one column past that chain's
    rightmost extent, so ``requires`` still reads left to right and the two chains
    cannot be mistaken for parallel.

    Safe to recurse: ``init_quests`` has already proved the unlock graph acyclic.
    """
    closes = {key: bool(visited_refs(quest.test)) for key, quest in defs.items()}
    triggers = {key: bool(visited_refs(quest.requires_test)) for key, quest in defs.items()}
    column: dict[str, int] = {}

    def extent(key: str) -> int:
        """The rightmost column ``key`` occupies, its own closing conversations included."""
        return visit(key) + (1 if closes[key] else 0)

    def visit(key: str) -> int:
        if key in column:
            return column[key]
        quest = defs[key]
        column[key] = 0  # cycle guard; init_quests already rejected real ones

        if quest.parent is not None:
            parent = defs[quest.parent]
            # the thread, then its own conversations if it has any, then the steps
            place = visit(quest.parent) + (2 if closes[quest.parent] else 1)
            # A step that waits on something outside its own thread has to sit past
            # it, even at the cost of leaving the shared column - an arrow pointing
            # backwards would be a worse lie than a step out of line.
            for dep in quest.requires:
                if defs[dep].parent != quest.parent and dep != quest.parent:
                    place = max(place, extent(dep) + 1)
            _ = parent
        else:
            place = 0
            for dep in quest.requires:
                place = max(place, extent(dep) + 1)
            # room on the left for the conversation that opens it
            if triggers[key]:
                place = max(place, 1)

        column[key] = place
        return place

    for key in defs:
        visit(key)
    return column


def _squeeze(nodes: list[dict[str, Any]]) -> None:
    """Renumber columns so no column is empty and the first is 0.

    Per-thread the template already skips slots it does not need, but a column can
    still end up empty *globally* - nothing anywhere lands on it - and vis-network
    would draw that as a band of blank screen. Squeezing is safe because it
    preserves order, which is the only thing a column index means here.
    """
    if not nodes:
        return
    used = sorted({node["level"] for node in nodes})
    renumbered = {old: new for new, old in enumerate(used)}
    for node in nodes:
        node["level"] = renumbered[node["level"]]


def uncloseable(defs: dict[str, QuestDef]) -> dict[str, str]:
    """``{key: why}`` for every quest config alone can never close.

    The one question left for a picture to answer. ``init_quests`` proves a quest
    is *well-formed*; it cannot prove one is *closeable*, because ``manual`` is a
    promise kept in game code:

    - ``manual`` returns ``False`` from ``is_complete`` forever (engine.py). Only
      ``mark_done`` closes it, and that is a call somebody has to write.
    - ``all_subquests`` inherits the problem: an umbrella over a step nothing can
      close is a thread that never ends.

    This is ``Q01_S07`` one level up - a quest reading "in progress" forever -
    and it lives in the gap between config and code, which no config-time
    validator can see. Flagged, not failed: an unwired ``manual`` quest is a
    to-do, and only the author knows whether the code is coming.
    """
    verdict: dict[str, str] = {}

    def closeable(key: str) -> bool:
        if key in verdict:
            return False
        quest = defs[key]

        if quest.completion is CompletionMode.manual:
            verdict[key] = "completion: manual - zamknie ją tylko kod gry (mark_done)"
            return False
        if quest.completion is CompletionMode.test:
            return True

        blocked = [child for child in children_of(defs, key) if not closeable(child)]
        if blocked:
            verdict[key] = (
                "parasol nad krokiem, którego nic nie zamyka: " + ", ".join(blocked)
            )
            return False
        return True

    for key in defs:
        closeable(key)
    return verdict


# ---------------------------------------------------------------------------
# Serialize
# ---------------------------------------------------------------------------


def markup_runs(text: str) -> list[dict[str, Any]]:
    """MoM markup -> ``[{"text": ..., "bold": ...}]`` for the tooltip.

    Every kind of styling flattens to bold. The graph has none of MoM's palette
    (the tooltip is an Obsidian note, in the reader's theme), and a tooltip that
    invented its own colours would imply distinctions the game does not make.
    Bold says "the author marked this" and stops there.

    Parsed with the game's own parser rather than a regex, so ``[/]``, unknown
    tags and inline emoji behave here exactly as they do in the game.
    """
    base = Style()
    runs: list[dict[str, Any]] = []
    for token in parse(text, base):
        if token.kind == "image":
            continue  # a sprite has no tooltip equivalent; dropping beats a stray ":name:"
        value = " " if token.kind == "newline" else token.value
        if not value:
            continue
        bold = token.style != base
        if runs and runs[-1]["bold"] == bold:
            runs[-1]["text"] += value  # keep the run count down; the DOM is per-run
        else:
            runs.append({"text": value, "bold": bold})
    return runs


def _reward_label(reward: Any) -> str:
    if reward.category == "items":
        return ", ".join(reward.items)
    unit = REWARD_UNIT.get(str(reward.category), str(reward.category))
    target = f" @{reward.target}" if reward.target else ""
    return f"+{reward.value} {unit}{target}"


def graph_to_dict(
    defs: dict[str, QuestDef],
    messages: dict[str, str],
    links: dict[str, str],
    dialogs: dict[str, DialogSource] | None = None,
) -> dict[str, Any]:
    """Serialize the quest DAG for the DataviewJS renderer (vis-network draws it).

    ``dialogs`` is optional: without it the picture is exactly what it was before
    ``requires_test`` existed, which is what keeps a caller that only has
    ``config.json`` (and no vault) able to draw the graph at all.
    """
    column = columns(defs)
    broken = uncloseable(defs)

    def name(key: str) -> str:
        return messages.get(defs[key].name, defs[key].name)

    nodes = [
        {
            "id": key,
            "level": column[key],
            # plain for the node label (vis-network draws it on a canvas and knows
            # no markup), runs for the tooltip (which is real DOM)
            "name": strip_tags(name(key)),
            "name_runs": markup_runs(name(key)),
            "description_runs": markup_runs(
                messages.get(quest.description, quest.description)
            ),
            "completion": str(quest.completion),
            "completion_text": MODE_LABEL[quest.completion],
            "test": quest.test,
            "requires_test": quest.requires_test,
            "progress": quest.progress,
            "progress_total": quest.progress_total,
            "kind": "quest",
            "is_thread": bool(children_of(defs, key)),
            "is_root": not quest.requires and not quest.parent and not quest.requires_test,
            "rewards": [_reward_label(r) for r in quest.rewards],
            "colour": MODE_COLOUR[quest.completion],
            "problem": broken.get(key),
            "link": links.get(key),
        }
        for key, quest in defs.items()
    ]

    edges: list[dict[str, Any]] = []
    for key, quest in defs.items():
        for req in quest.requires:
            edges.append({"from": req, "to": key, "kind": "requires"})
        if quest.parent:
            edges.append({"from": quest.parent, "to": key, "kind": "parent"})

    dialog_nodes, dialog_edges = _dialog_nodes(defs, messages, dialogs or {}, column)
    nodes.extend(dialog_nodes)
    edges.extend(dialog_edges)
    _squeeze(nodes)

    return {
        "meta": {
            "source": "project/config_model/config.json",
            "counts": {
                "quests": len(defs),
                "threads": sum(1 for n in nodes if n["is_thread"]),
                "roots": sum(1 for n in nodes if n["is_root"]),
                "dialogs": len(dialog_nodes),
            },
            "modes": {str(mode): MODE_COLOUR[mode] for mode in CompletionMode},
            "dialog_colour": DIALOG_COLOUR,
        },
        "nodes": nodes,
        "edges": edges,
    }


def _dialog_nodes(
    defs: dict[str, QuestDef],
    messages: dict[str, str],
    dialogs: dict[str, DialogSource],
    column: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """One hexagon per dialog node a quest names, plus its edges.

    Two relations, and the difference is the whole point:

    - ``requires_test`` **opens** a quest: the conversation happens first, so the
      node is drawn above and the arrow points down into the quest.
    - ``test`` **closes** it: the quest is already open and sends the player to
      that conversation, so the arrow points from the quest down into the node.

    Both read the same way - **downward is later** - which is what lets the whole
    picture be scanned as play order rather than as two unrelated conventions.

    Keyed by ``(npc, node)``: one conversation can serve several quests, and
    drawing it once per quest would claim there are several of it.
    """
    if not defs:
        return [], []

    # (npc, node) -> what this conversation does, and to which quests
    roles: dict[tuple[str, str], dict[str, list[tuple[str, bool]]]] = {}
    alt_by_quest: dict[str, bool] = {}
    for key, quest in defs.items():
        # `alt` describes the quest's own `test`, so it is a fact about the quest,
        # not about any one node it names.
        alt_by_quest[key] = alternatives(quest.test)
        for field_value, role in ((quest.requires_test, "unlocks"), (quest.test, "closes")):
            for ref in visited_refs(field_value):
                entry = roles.setdefault((ref.npc, ref.node), {"unlocks": [], "closes": []})
                entry[role].append((key, ref.negated))

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for (npc, node), role in roles.items():
        source = dialogs.get(npc)
        npc_name = source.name if source and source.name else npc
        text_key = source.texts.get(node) if source else None
        line = messages.get(text_key, "") if text_key else ""

        node_id = f"dlg:{npc}#{node}"
        nodes.append({
            "id": node_id,
            "level": _dialog_column(role, column),
            "name": f"{npc_name} #{node}",
            "name_runs": [{"text": f"{npc_name} #{node}", "bold": True}],
            "kind": "dialog",
            "npc": npc,
            "npc_name": npc_name,
            "node": node,
            "text_runs": markup_runs(line) if line else [],
            "unlocks": [_quest_label(defs, messages, k) for k, _ in role["unlocks"]],
            "closes": [_quest_label(defs, messages, k) for k, _ in role["closes"]],
            # Every other node type earns its shape from data; these two keys exist
            # so the renderer and the counters can stay branch-free.
            "is_thread": False,
            "is_root": False,
            "problem": None,
            "colour": DIALOG_COLOUR,
            "link": source.link(node) if source else None,
        })
        for key, negated in role["unlocks"]:
            edges.append({"from": node_id, "to": key, "kind": "unlocks", "negated": negated})
        for key, negated in role["closes"]:
            edges.append({
                "from": key, "to": node_id, "kind": "closes",
                "negated": negated, "alt": alt_by_quest.get(key, False),
            })

    return nodes, edges


def _quest_label(defs: dict[str, QuestDef], messages: dict[str, str], key: str) -> str:
    return strip_tags(messages.get(defs[key].name, defs[key].name))


def _dialog_column(role: dict[str, list[tuple[str, bool]]], column: dict[str, int]) -> int:
    """Which column a dialog node sits in.

    Two constraints, from the two relations: it must sit **left of** everything it
    opens (``min(col) - 1``) and **right of** everything it closes
    (``max(col) + 1``). A node that only does one of the two takes that one.

    When a node does both and they disagree - it closes a late quest and opens an
    early one - the *opening* constraint wins. The unlock arrow pointing rightward
    is what the whole layout's "rightward is later" reading rests on; a closing
    arrow that ends up pointing back left just says "you return to this
    conversation later", which is a real shape in a game and still reads.
    """
    left_of = min((column[key] - 1 for key, _ in role["unlocks"]), default=None)
    right_of = max((column[key] + 1 for key, _ in role["closes"]), default=None)
    if left_of is None:
        return right_of or 0
    if right_of is None:
        return left_of
    return min(left_of, right_of)


def write_json(data: dict[str, Any], out_dir: Path) -> Path:
    """Write ``_graphs/data/QUESTS.json`` + the DataviewJS note that renders it."""
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / f"{DATA_KEY}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    note_path = out_dir / f"{NOTE_STEM}.md"
    note_path.write_text(_DATAVIEW_NOTE.replace("__KEY__", DATA_KEY), encoding="utf-8")
    return note_path


_DATAVIEW_NOTE = """---
tags: [graf-questow]
---

# Questy - graf

> [!info] Wygenerowane przez `scripts/quest_graph.py` - nie edytuj ręcznie.
> Czyta się **od lewej do prawej**, kolumnami: rozmowa otwierająca -> wątek -> jego rozmowy -> kroki wątku (jedna kolumna, jeden pod drugim) -> rozmowy kroków. Pustej kolumny nie ma - wątek bez rozmowy otwierającej zaczyna od lewej krawędzi.
> Klik w węzeł: podświetl sąsiadów. Podwójny klik: otwórz quest w źródłowym pliku.
> Najedź na węzeł, żeby zobaczyć opis, warunek zamknięcia i nagrody.
> Sześciokąt to **węzeł dialogu** - podwójny klik prowadzi do kwestii w notatce postaci.
> Strzałka **w** quest (z lewej): ta rozmowa go odblokowuje (`Requires`). Strzałka **z** questa (w prawo): na tej rozmowie się zamyka (`Test`).
> Poprzeczka zamiast grotu = warunek zanegowany (`not`), podpis `lub` = wystarczy jedna z rozmów. Pełne wyrażenie jest w dymku questa.

```dataviewjs
const KEY = "__KEY__";
const LIB = "_graphs/lib/vis-network.min.js";
const DATA = `_graphs/data/${KEY}.json`;
const HEIGHT = "820px";

// ---------------------------------------------------------------- biblioteka
// vis-network to bundle UMD; z przesłoniętymi module/exports/define wchodzi
// w gałąź globalną i przypisuje się do globalThis.vis. Ładujemy raz na sesję.
if (!globalThis.vis?.Network) {
    const code = await app.vault.adapter.read(LIB);
    new Function("module", "exports", "define", code)(undefined, undefined, undefined);
}
const vis = globalThis.vis;

if (!document.getElementById("mom-graph-css")) {
    const st = document.createElement("style");
    st.id = "mom-graph-css";
    st.textContent = `
    .vis-tooltip { position: absolute; visibility: hidden; padding: 0 !important;
        border: none !important; background: transparent !important; box-shadow: none !important;
        z-index: 100; pointer-events: none; }
    .mom-tip { max-width: 420px; padding: 10px 12px; border-radius: 8px; font-size: 13px;
        line-height: 1.45; background: var(--background-primary); color: var(--text-normal);
        border: 1px solid var(--background-modifier-border);
        box-shadow: 0 4px 16px rgba(0,0,0,.3); white-space: normal; }
    .mom-tip-h { font-weight: 700; margin-bottom: 4px; }
    .mom-tip-k { font-family: var(--font-monospace); font-size: 11px; color: var(--text-faint);
        margin-bottom: 6px; }
    .mom-tip-q { font-style: italic; color: var(--text-muted); }
    .mom-tip-r { margin-top: 6px; font-family: var(--font-monospace); font-size: 12px; }
    .mom-tip-c { margin-top: 6px; font-family: var(--font-monospace); font-size: 12px;
        color: var(--text-accent); word-break: break-word; }
    .mom-tip-p { margin-top: 6px; color: var(--text-error); font-size: 12px; }
    .mom-tip-hint { margin-top: 8px; font-size: 11px; color: var(--text-faint); }
    .mom-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
    .mom-bar button { font-size: 12px; padding: 3px 10px; cursor: pointer; }
    .mom-count { font-size: 12px; color: var(--text-muted); margin-left: auto; }
    .mom-legend { display: flex; gap: 14px; align-items: center; flex-wrap: wrap;
        margin-bottom: 8px; font-size: 12px; color: var(--text-muted); }
    .mom-legend span.sw { display: inline-block; width: 11px; height: 11px; border-radius: 3px;
        margin-right: 5px; vertical-align: -1px; border: 1px solid; }
    /* próbka w kształcie węzła, bo to kształt odróżnia dialog od questa, nie kolor */
    .mom-legend span.sw.hex { border-radius: 0;
        clip-path: polygon(25% 0, 75% 0, 100% 50%, 75% 100%, 25% 100%, 0 50%); }
    .mom-probs { margin-bottom: 8px; padding: 8px 12px; border-radius: 6px; font-size: 12px;
        background: var(--background-modifier-error-hover); border: 1px solid var(--text-error); }
    .mom-probs b { color: var(--text-error); }
    .mom-probs li { cursor: pointer; }
    .mom-probs li:hover { text-decoration: underline; }
    .mom-probs .why { color: var(--text-muted); font-style: italic; margin-top: 4px; }
    .mom-net { border: 1px solid var(--background-modifier-border); border-radius: 8px; }
    `;
    document.head.appendChild(st);
}

// ---------------------------------------------------------------------- dane
const G = JSON.parse(await app.vault.adapter.read(DATA));
const NOTE = dv.current().file.path;
const box = dv.container;

const el = (tag, cls, txt) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt) e.textContent = txt;
    return e;
};

// Znaczniki MoM ([char], [loc], [num]...) sklejone w Pythonie do runow; kazdy
// wariant formatowania splaszcza sie do pogrubienia. textContent, nie innerHTML:
// to proza autora i nie ma prawa wstrzykiwac HTML-a do notatki.
const runs = (cls, list, fallback) => {
    const e = el("div", cls);
    if (!list || !list.length) {
        e.textContent = fallback;
        return e;
    }
    for (const r of list) e.append(el(r.bold ? "b" : "span", null, r.text));
    return e;
};

function nodeTip(n) {
    const t = el("div", "mom-tip");
    const role = n.is_thread ? " - WĄTEK" : n.is_root ? " - START" : "";
    const head = runs("mom-tip-h", n.name_runs, n.name);
    if (role) head.append(el("span", null, role));
    t.append(head);
    t.append(el("div", "mom-tip-k", n.id));
    t.append(runs("mom-tip-q", n.description_runs, "(brak opisu)"));
    t.append(el("div", "mom-tip-r", `${n.completion}: ${n.completion_text}`));
    if (n.requires_test) t.append(el("div", "mom-tip-c", `odblokowuje: ${n.requires_test}`));
    if (n.test) t.append(el("div", "mom-tip-c", `test: ${n.test}`));
    if (n.progress) t.append(el("div", "mom-tip-c", `postęp: ${n.progress} / ${n.progress_total}`));
    if (n.rewards.length) t.append(el("div", "mom-tip-r", `nagroda: ${n.rewards.join(" · ")}`));
    if (n.problem) t.append(el("div", "mom-tip-p", `! ${n.problem}`));
    if (n.link) t.append(el("div", "mom-tip-hint", "podwójny klik - otwórz w źródle"));
    return t;
}

// Węzeł dialogu nie jest questem i nie ma czego zamykać - stąd inny dymek:
// kto to mówi, co mówi i który wątek się przez to otwiera.
function dialogTip(n) {
    const t = el("div", "mom-tip");
    t.append(el("div", "mom-tip-h", `${n.npc_name} - węzeł ${n.node}`));
    t.append(el("div", "mom-tip-k", `${n.npc}#${n.node}`));
    t.append(runs("mom-tip-q", n.text_runs, "(brak kwestii w tym języku)"));
    if (n.unlocks.length) t.append(el("div", "mom-tip-r", `odblokowuje: ${n.unlocks.join(" · ")}`));
    if (n.closes.length) t.append(el("div", "mom-tip-r", `zamyka: ${n.closes.join(" · ")}`));
    if (n.link) t.append(el("div", "mom-tip-hint", "podwójny klik - otwórz dialog w źródle"));
    return t;
}

const visNodes = G.nodes.map((n) => ({
    id: n.id,
    level: n.level,
    label: n.name,
    title: n.kind === "dialog" ? dialogTip(n) : nodeTip(n),
    color: { background: n.colour.bg, border: n.colour.border },
    borderWidth: n.problem ? 4 : 2,
    shapeProperties: { borderDashes: n.problem ? [6, 4] : false },
    // Trzy kształty, trzy różne rzeczy: prostokąt = wątek, elipsa = krok,
    // sześciokąt = węzeł dialogu (w ogóle nie quest).
    shape: n.kind === "dialog" ? "hexagon" : n.is_thread ? "box" : "ellipse",
    font: { size: 14, face: "var(--font-interface)", color: "#1e1e1e" },
}));

// requires = "to musi być ZROBIONE"; parent = "ten wątek musi być ODBLOKOWANY".
// Dwie różne bramki, więc dwa różne style - inaczej graf kłamie o tym, co gate'uje co.
const REQ = "#9aa0a8";
const PAR = "#0dcaf0";
const UNL = "#7048e8";
const CLO = "#0ca678";
const EDGE_COLOUR = { requires: REQ, parent: PAR, unlocks: UNL, closes: CLO };
const EDGE_DASH = { requires: false, parent: [2, 4], unlocks: [7, 3], closes: [2, 3] };
const EDGE_WIDTH = { requires: 1.6, parent: 1, unlocks: 1.8, closes: 1.6 };

// Dwie rzeczy, których "bloczki i linie" nie oddadzą same z siebie, a które
// zmieniają sens na przeciwny albo prawie:
//   not  -> grot zmienia się w poprzeczkę (notacja "hamuje", czytelna bez legendy),
//   or   -> podpis "lub" na krawędzi: wystarczy JEDNA z tych rozmów.
// Reszta struktury boolowskiej zostaje w dymku questa, w oryginalnym zapisie -
// diagram, który udaje, że oddaje całe wyrażenie, kłamie dokładnie wtedy, gdy
// wyrażenie robi się na tyle zawiłe, że warto na nie spojrzeć.
const edgeNote = (e) => [e.negated ? "nie" : null, e.alt ? "lub" : null]
    .filter(Boolean).join(" ");

const visEdges = G.edges.map((e, i) => ({
    id: i,
    from: e.from,
    to: e.to,
    kind: e.kind,
    color: { color: EDGE_COLOUR[e.kind], opacity: 0.85 },
    dashes: EDGE_DASH[e.kind],
    width: EDGE_WIDTH[e.kind],
    label: edgeNote(e) || undefined,
    // Bez obwódki: etykieta jedzie na canvas, a canvas nie rozwiązuje `var(--...)`,
    // więc obwódka w kolorze motywu wychodziła czarną plamą zamiast tła. Sam
    // kolor krawędzi wystarczy - podpis jest krótki i siedzi na swojej linii.
    font: { size: 12, color: EDGE_COLOUR[e.kind], strokeWidth: 0, align: "middle" },
    arrows: { to: { enabled: true, scaleFactor: 0.75, type: e.negated ? "bar" : "arrow" } },
    smooth: { enabled: true, type: "cubicBezier", forceDirection: "horizontal", roundness: 0.5 },
}));

// -------------------------------------------------------------------- widok
const bar = box.appendChild(el("div", "mom-bar"));
const btnLay = bar.appendChild(el("button", null, "Układ: kolumny"));
const btnFit = bar.appendChild(el("button", null, "Dopasuj"));
const btnReset = bar.appendChild(el("button", null, "Odznacz"));
bar.appendChild(
    el("span", "mom-count",
       `${G.meta.counts.quests} questów, ${G.meta.counts.threads} wątków, ` +
       `${G.meta.counts.roots} na starcie` +
       (G.meta.counts.dialogs ? `, ${G.meta.counts.dialogs} węzłów dialogu` : ""))
);

const legend = box.appendChild(el("div", "mom-legend"));
const LEG_TEXT = { test: "test (warunek)", all_subquests: "wątek (kroki)", manual: "manual (kod gry)" };
for (const [mode, col] of Object.entries(G.meta.modes)) {
    const item = legend.appendChild(el("span", null, null));
    const sw = item.appendChild(el("span", "sw"));
    sw.style.background = col.bg;
    sw.style.borderColor = col.border;
    item.append(document.createTextNode(LEG_TEXT[mode] ?? mode));
}
if (G.meta.counts.dialogs) {
    const item = legend.appendChild(el("span", null, null));
    const sw = item.appendChild(el("span", "sw hex"));
    sw.style.background = G.meta.dialog_colour.bg;
    sw.style.borderColor = G.meta.dialog_colour.border;
    item.append(document.createTextNode("węzeł dialogu"));
}
legend.append(el("span", null, "──  requires (musi być zrobione)"));
legend.append(el("span", null, "┄┄  parent (wątek odblokowany)"));
if (G.meta.counts.dialogs) {
    legend.append(el("span", null, "╌╌  rozmowa ODBLOKOWUJE quest"));
    legend.append(el("span", null, "┈┈  quest ZAMYKA się na rozmowie"));
    legend.append(el("span", null, '⊣  poprzeczka zamiast grotu = "nie"'));
}

const broken = G.nodes.filter((n) => n.problem);

const graphEl = el("div", "mom-net");
graphEl.style.height = HEIGHT;

// Hierarchia, nie fizyka - i to jest różnica względem grafu dialogów. Tam
// sortMethod: "directed" gubił rangi, bo pętle resume tworzą cykle; tu graf jest
// acyklyczny z walidacji (_validate_acyclic), więc rangi są uczciwe. Poziom liczy
// Python (najdłuższa ścieżka odblokowań), vis tylko go rysuje.
// Poziomo, nie pionowo. Kolumnę liczy Python i niesie ją `level` (patrz
// `columns()`): rozmowa otwierająca, wątek, jego rozmowy, kroki, rozmowy kroków.
// vis tylko układa - `sortMethod: "directed"` porządkowałby kolumny po swojemu i
// rozjeżdżał kroki jednego wątku, więc zostaje "hubsize", które szanuje `level`.
// `levelSeparation` to odstęp MIĘDZY kolumnami, `nodeSpacing` - w pionie, wewnątrz
// kolumny; przy sześciokątach podpis jedzie pod kształtem, więc pionu trzeba więcej.
const HIER = {
    layout: { hierarchical: { enabled: true, direction: "LR", sortMethod: "hubsize",
                              levelSeparation: 260, nodeSpacing: 120, treeSpacing: 170,
                              blockShifting: true, edgeMinimization: true,
                              parentCentralization: true } },
    physics: { enabled: false },
};
const FREE = {
    layout: { hierarchical: { enabled: false }, improvedLayout: true, randomSeed: 42 },
    physics: { enabled: true, solver: "barnesHut",
               barnesHut: { gravitationalConstant: -20000, centralGravity: 0.4,
                            springLength: 140, springConstant: 0.02, damping: 0.5 },
               stabilization: { enabled: true, iterations: 400, fit: true } },
};
const BASE = {
    interaction: { dragNodes: true, hover: true, tooltipDelay: 120, navigationButtons: true,
                   zoomView: true, multiselect: false },
    nodes: { margin: 10, widthConstraint: { maximum: 170 } },
};
// fit() sam z siebie nie przybliża powyżej skali 1 (domyślny maxZoomLevel), więc
// mały graf siadał w środku płótna, wypełniając je w 1/3 - zmierzone. Limit tnie
// tylko przybliżanie, więc dla dużego grafu ta wartość jest bez znaczenia.
const FIT = { animation: false, maxZoomLevel: 2 };

if (broken.length) {
    const p = box.appendChild(el("div", "mom-probs"));
    p.append(el("b", null, `NIE DA SIĘ ZAMKNĄĆ Z SAMEGO CONFIGU (${broken.length})`));
    const ul = p.appendChild(document.createElement("ul"));
    for (const n of broken) {
        const li = ul.appendChild(el("li", null, `${n.name}: ${n.problem}`));
        li.onclick = () => { highlight(n.id); network.selectNodes([n.id]);
                             network.focus(n.id, { scale: 1.1, animation: true }); };
    }
    p.append(el("div", "why",
        "To nie musi być błąd: manual znaczy, że quest zamyka kod gry. " +
        "Jeśli takiego kodu nie ma, wątek zostaje otwarty na zawsze - to kształt Q01_S07."));
}
box.appendChild(graphEl);

const nodesDS = new vis.DataSet(visNodes);
const edgesDS = new vis.DataSet(visEdges);
let network;
let hier = true;

function buildNetwork() {
    if (network) network.destroy();
    nodesDS.update(visNodes.map((n) => ({ id: n.id, x: undefined, y: undefined, fixed: false })));
    network = new vis.Network(graphEl, { nodes: nodesDS, edges: edgesDS },
                              { ...BASE, ...(hier ? HIER : FREE) });
    if (hier) {
        // Układ kolumnowy powstaje synchronicznie - nie ma stabilizacji, na którą
        // można poczekać, więc stabilizationIterationsDone NIE padnie. Czekanie
        // na nie zostawiało graf niedopasowany, w rogu pustego płótna.
        network.fit(FIT);
    } else {
        // Fizyka rozkłada graf, po czym ją zamrażamy: węzły zostają tam, gdzie
        // usiadły, i dają się przeciągać, bez rozjeżdżania przy każdym ruchu.
        network.once("stabilizationIterationsDone", () => {
            network.setOptions({ physics: { enabled: false } });
            network.fit(FIT);
        });
    }
    network.on("click", (p) => (p.nodes.length ? highlight(p.nodes[0]) : clearHighlight()));
    network.on("doubleClick", (p) => {
        const n = byId.get(p.nodes[0]);
        if (n?.link) app.workspace.openLinkText(n.link, NOTE, "tab");
    });
}

// ------------------------------------------------- klik: podświetl sąsiadów
const adj = new Map(G.nodes.map((n) => [n.id, new Set()]));
for (const e of G.edges) {
    adj.get(e.from)?.add(e.to);
    adj.get(e.to)?.add(e.from);
}
const DIM_N = { background: "#f1f3f5", border: "#dee2e6" };
const byId = new Map(G.nodes.map((n) => [n.id, n]));

function highlight(id) {
    const keep = new Set([id, ...(adj.get(id) ?? [])]);
    nodesDS.update(visNodes.map((n) => keep.has(n.id)
        ? { id: n.id, color: n.color, font: { ...n.font, color: "#1e1e1e" } }
        : { id: n.id, color: DIM_N, font: { ...n.font, color: "#ced4da" } }));
    edgesDS.update(visEdges.map((e) => (e.from === id || e.to === id)
        ? { id: e.id, color: { color: EDGE_COLOUR[e.kind], opacity: 1 }, width: e.width + 1 }
        : { id: e.id, color: { color: "#e9ecef", opacity: 0.15 }, width: e.width }));
}

function clearHighlight() {
    nodesDS.update(visNodes);
    edgesDS.update(visEdges);
}

// ------------------------------------------------------------------ toolbar
btnLay.onclick = () => {
    hier = !hier;
    btnLay.textContent = `Układ: ${hier ? "kolumny" : "swobodny"}`;
    buildNetwork();
};
btnFit.onclick = () => network.fit({ ...FIT, animation: true });
btnReset.onclick = () => { network.unselectAll(); clearHighlight(); };

buildNetwork();
```
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def generate(*, out_dir: Path, lang: str, config_path: Path = CONFIG_JSON) -> Path:
    defs, messages = read_quests(config_path, lang=lang)
    if not defs:
        raise SystemExit(
            f"brak sekcji 'quests' w {config_path} - uruchom najpierw `just import-quests`"
        )

    links = source_links(lang=lang)
    data = graph_to_dict(defs, messages, links, dialog_sources(config_path, lang=lang))

    out_dir.mkdir(parents=True, exist_ok=True)
    path = write_json(data, out_dir)
    _report(data, path)
    return path


def _report(data: dict[str, Any], path: Path) -> None:
    counts = data["meta"]["counts"]
    broken = [n for n in data["nodes"] if n["problem"]]
    try:
        shown = path.relative_to(_REPO_ROOT)
    except ValueError:
        shown = path
    print(
        f"{counts['quests']:>3} questów  {counts['threads']:>2} wątków  "
        f"{len(broken):>2} niedomykalnych  ->  {shown}"
    )
    for node in broken:
        print(f"    ! {node['id']}: {node['problem']}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lang", default="PL", help="language for names (default: PL)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--config", type=Path, default=CONFIG_JSON)
    args = ap.parse_args(argv)

    generate(out_dir=args.out, lang=args.lang, config_path=args.config)


if __name__ == "__main__":
    main()
