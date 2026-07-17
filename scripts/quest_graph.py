"""Render the quest DAG from ``config.json`` as an interactive Obsidian note.

Quests form a directed acyclic graph: ``requires`` says what must be *done*
first, ``parent`` says which thread a step belongs to (and must be *unlocked*).
Both are unlock edges, and the shape they make - which thread gates which, how
deep a chain runs, what opens at the start - is a picture, not a paragraph.

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
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "project"))

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

REWARD_UNIT: dict[str, str] = {
    "money": "zł",
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
    """``{quest_key: "<file stem>#<quest_key>"}`` for the double-click jump.

    A section heading *is* the quest's config key, so the link is the heading
    verbatim - nothing to compose. A chain the vault does not have simply gets no
    link: the graph is still drawable, and config.json is the source of truth for
    the shape.
    """
    links: dict[str, str] = {}
    try:
        lang_dir = qi._lang_dir(src_dir, lang)
    except qi.QuestImportError:
        return links

    for path in sorted(lang_dir.glob("*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            section = qi._SECTION_RE.match(line)
            if section:
                key = section.group("key")
                links[key] = f"{path.stem}#{key}"
    return links


# ---------------------------------------------------------------------------
# Analyze
# ---------------------------------------------------------------------------


def levels(defs: dict[str, QuestDef]) -> dict[str, int]:
    """Rank each quest by the *longest* unlock path reaching it.

    Longest, not BFS-shortest: a quest waits for **all** of its ``requires``, so
    the earliest rank it can possibly open at is one past its slowest dependency.
    Shortest-path would draw it as available sooner than it can ever be.

    Safe to recurse: ``init_quests`` has already proved the unlock graph acyclic.
    """
    rank: dict[str, int] = {}

    def visit(key: str) -> int:
        if key in rank:
            return rank[key]
        quest = defs[key]
        deps = list(quest.requires) + ([quest.parent] if quest.parent else [])
        rank[key] = 1 + max((visit(dep) for dep in deps), default=-1)
        return rank[key]

    for key in defs:
        visit(key)
    return rank


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
) -> dict[str, Any]:
    """Serialize the quest DAG for the DataviewJS renderer (vis-network draws it)."""
    rank = levels(defs)
    broken = uncloseable(defs)

    def name(key: str) -> str:
        return messages.get(defs[key].name, defs[key].name)

    nodes = [
        {
            "id": key,
            "level": rank[key],
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
            "progress": quest.progress,
            "progress_total": quest.progress_total,
            "is_thread": bool(children_of(defs, key)),
            "is_root": not quest.requires and not quest.parent,
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

    return {
        "meta": {
            "source": "project/config_model/config.json",
            "counts": {
                "quests": len(defs),
                "threads": sum(1 for n in nodes if n["is_thread"]),
                "roots": sum(1 for n in nodes if n["is_root"]),
            },
            "modes": {str(mode): MODE_COLOUR[mode] for mode in CompletionMode},
        },
        "nodes": nodes,
        "edges": edges,
    }


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
> Klik w węzeł: podświetl sąsiadów. Podwójny klik: otwórz quest w źródłowym pliku.
> Najedź na węzeł, żeby zobaczyć opis, warunek zamknięcia i nagrody.

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
    if (n.test) t.append(el("div", "mom-tip-c", `test: ${n.test}`));
    if (n.progress) t.append(el("div", "mom-tip-c", `postęp: ${n.progress} / ${n.progress_total}`));
    if (n.rewards.length) t.append(el("div", "mom-tip-r", `nagroda: ${n.rewards.join(" · ")}`));
    if (n.problem) t.append(el("div", "mom-tip-p", `! ${n.problem}`));
    if (n.link) t.append(el("div", "mom-tip-hint", "podwójny klik - otwórz w źródle"));
    return t;
}

const visNodes = G.nodes.map((n) => ({
    id: n.id,
    level: n.level,
    label: n.name,
    title: nodeTip(n),
    color: { background: n.colour.bg, border: n.colour.border },
    borderWidth: n.problem ? 4 : 2,
    shapeProperties: { borderDashes: n.problem ? [6, 4] : false },
    shape: n.is_thread ? "box" : "ellipse",
    font: { size: 14, face: "var(--font-interface)", color: "#1e1e1e" },
}));

// requires = "to musi być ZROBIONE"; parent = "ten wątek musi być ODBLOKOWANY".
// Dwie różne bramki, więc dwa różne style - inaczej graf kłamie o tym, co gate'uje co.
const REQ = "#9aa0a8";
const PAR = "#0dcaf0";
const visEdges = G.edges.map((e, i) => ({
    id: i,
    from: e.from,
    to: e.to,
    kind: e.kind,
    color: { color: e.kind === "parent" ? PAR : REQ, opacity: 0.85 },
    dashes: e.kind === "parent" ? [2, 4] : false,
    width: e.kind === "parent" ? 1 : 1.6,
    arrows: { to: { enabled: true, scaleFactor: 0.75 } },
    smooth: { enabled: true, type: "cubicBezier", forceDirection: "vertical", roundness: 0.5 },
}));

// -------------------------------------------------------------------- widok
const bar = box.appendChild(el("div", "mom-bar"));
const btnLay = bar.appendChild(el("button", null, "Układ: hierarchia"));
const btnFit = bar.appendChild(el("button", null, "Dopasuj"));
const btnReset = bar.appendChild(el("button", null, "Odznacz"));
bar.appendChild(
    el("span", "mom-count",
       `${G.meta.counts.quests} questów, ${G.meta.counts.threads} wątków, ` +
       `${G.meta.counts.roots} na starcie`)
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
legend.append(el("span", null, "──  requires (musi być zrobione)"));
legend.append(el("span", null, "┄┄  parent (wątek odblokowany)"));

const broken = G.nodes.filter((n) => n.problem);

const graphEl = el("div", "mom-net");
graphEl.style.height = HEIGHT;

// Hierarchia, nie fizyka - i to jest różnica względem grafu dialogów. Tam
// sortMethod: "directed" gubił rangi, bo pętle resume tworzą cykle; tu graf jest
// acyklyczny z walidacji (_validate_acyclic), więc rangi są uczciwe. Poziom liczy
// Python (najdłuższa ścieżka odblokowań), vis tylko go rysuje.
const HIER = {
    layout: { hierarchical: { enabled: true, direction: "UD", sortMethod: "directed",
                              levelSeparation: 130, nodeSpacing: 190, treeSpacing: 220 } },
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
        // Hierarchia układa się synchronicznie - nie ma stabilizacji, na którą
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
        ? { id: e.id, color: { color: e.kind === "parent" ? PAR : REQ, opacity: 1 }, width: e.width + 1 }
        : { id: e.id, color: { color: "#e9ecef", opacity: 0.15 }, width: e.width }));
}

function clearHighlight() {
    nodesDS.update(visNodes);
    edgesDS.update(visEdges);
}

// ------------------------------------------------------------------ toolbar
btnLay.onclick = () => {
    hier = !hier;
    btnLay.textContent = `Układ: ${hier ? "hierarchia" : "swobodny"}`;
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
    data = graph_to_dict(defs, messages, links)

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
