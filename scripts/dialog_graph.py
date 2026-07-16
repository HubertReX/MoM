"""Render dialog graphs from ``doc/PL/Postacie/*.md`` as Excalidraw drawings.

The dialog system is a directed graph with loops (see ``project/dialog/AGENTS.md``).
Most authoring bugs are graph properties - an unreachable node, a dead end, a
condition that can never hold - which are obvious in a picture and invisible in
Markdown.  This script reads the Markdown source through the very same parser the
game importer uses (``project/dialog/markdown_importer.py``), so the picture shows
what the game actually sees, then lays the graph out and writes it as an Obsidian
Excalidraw drawing.

Usage::

    .venv/bin/python scripts/dialog_graph.py --all
    .venv/bin/python scripts/dialog_graph.py --character MADAME_SARCASMIA \
        --style boxes --layout dot --format svg

Layers: read -> analyze -> layout (py | dot) -> render (boxes | arrows) -> write.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import shutil
import subprocess
import sys
import textwrap
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal
from xml.sax.saxutils import escape as xml_escape

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "project"))

from dialog import conditions as dialog_conditions  # noqa: E402
from dialog import markdown_importer as mi  # noqa: E402

DOC_DIR = _REPO_ROOT / "doc"
DEFAULT_OUT = DOC_DIR / "_graphs"
CHARACTERS_CSV = _REPO_ROOT / "project" / "config_model" / "characters.csv"
CONFIG_JSON = _REPO_ROOT / "project" / "config_model" / "config.json"

Style = Literal["boxes", "arrows"]
LayoutName = Literal["py", "dot"]
OutFormat = Literal["obsidian", "excalidraw", "svg", "json"]

# --------------------------------------------------------------------------
# Visual constants
# --------------------------------------------------------------------------

FONT_FAMILY = 5  # Excalifont
FONT_SIZE = 16
LINE_HEIGHT = 1.25
CHAR_W = FONT_SIZE * 0.55  # rough advance width for Excalifont
LINE_H = FONT_SIZE * LINE_HEIGHT

NODE_W = 320
OPT_W = 250
PAD = 12
H_GAP = 40
V_GAP = 70
ARROW_V_GAP = 170  # arrows style needs room for the option label on the arrow

SENTIMENT_BG = {
    "kind": "#b2f2bb",
    "weak": "#a5d8ff",
    "neutral": "#e9ecef",
    "angry": "#ffc9c9",
    "smart": "#d0bfff",
    "funny": "#ffd8a8",
    "technical": "#c3fae8",
}
SENTIMENT_FG = {
    "kind": "#2f9e44",
    "weak": "#1971c2",
    "neutral": "#868e96",
    "angry": "#e03131",
    "smart": "#7048e8",
    "funny": "#f08c00",
    "technical": "#0ca678",
}

NODE_BG_PLAIN = "#a5d8ff"
NODE_BG_START = "#b2f2bb"
NODE_BG_FINAL = "#ffc9c9"
NODE_BG_RESULT = "#fff3bf"
STROKE_DEFAULT = "#1e1e1e"
STROKE_START = "#2f9e44"
STROKE_FINAL = "#e03131"
STROKE_PROBLEM = "#f06595"
STROKE_RESUME = "#7048e8"
STROKE_BACK = "#f08c00"
STROKE_TEXT = "#1e1e1e"

# --------------------------------------------------------------------------
# 1. read
# --------------------------------------------------------------------------


@dataclass
class GOption:
    key: str
    source: str
    target: str
    order: int
    condition: str
    sentiment: str
    text: str


@dataclass
class GNode:
    key: str
    text: str
    is_final: bool
    resume_node: str | None
    result: dict[str, Any] | None
    options: list[GOption] = field(default_factory=list)


@dataclass
class DialogGraph:
    char_key: str
    file_stem: str
    start: str
    nodes: dict[str, GNode]
    problems: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    global_problems: list[str] = field(default_factory=list)

    def option_list(self) -> list[GOption]:
        return [opt for node in self.nodes.values() for opt in node.options]


_TAG_RE = re.compile(r"\[/?[a-z_]+\]")
_SHORTCODE_RE = re.compile(r":[a-z_]+:")
_WIKI_RE = re.compile(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]")
_CHAR_TAG_RE = re.compile(r"\[/?char\]")


def plain(text: str, limit: int = 0) -> str:
    """Strip rich-text tags, shortcodes and wikilinks; collapse whitespace."""
    out = _WIKI_RE.sub(r"\1", text)
    out = _CHAR_TAG_RE.sub("", out)
    out = _TAG_RE.sub("", out)
    out = _SHORTCODE_RE.sub("", out)
    out = re.sub(r"\s+", " ", out).strip()
    if limit and len(out) > limit:
        out = out[: limit - 1].rstrip() + "…"
    return out


def read_graph(char_key: str, *, src_dir: Path = DOC_DIR) -> DialogGraph:
    """Parse one character's Markdown into a DialogGraph.

    Delegates to ``markdown_importer.import_character_dialog`` so the result is
    byte-for-byte the config the game would get from ``just import-dialogs``.
    """
    valid_items = _load_valid_items()
    messages, config, _meta = mi.import_character_dialog(
        src_dir, char_key, valid_items=valid_items
    )
    data = config[char_key]
    pl = messages["PL"]

    nodes: dict[str, GNode] = {}
    for nkey, ncfg in data["DIALOG_NODES"].items():
        result_key = ncfg.get("result")
        nodes[nkey] = GNode(
            key=nkey,
            text=plain(pl.get(ncfg["text"], "")),
            is_final=bool(ncfg.get("is_final")),
            resume_node=ncfg.get("resume_node"),
            result=data["NODE_RESULTS"].get(result_key) if result_key else None,
        )

    for nkey, opt_keys in data["NODES_OPTIONS"].items():
        for okey in opt_keys:
            ocfg = data["DIALOG_OPTIONS"][okey]
            nodes[nkey].options.append(
                GOption(
                    key=okey,
                    source=nkey,
                    target=ocfg["next_node"],
                    order=ocfg.get("order", 0),
                    condition=ocfg.get("condition", "True"),
                    sentiment=ocfg.get("sentiment", "neutral"),
                    text=plain(pl.get(ocfg["text"], "")),
                )
            )

    stem = mi._find_markdown_file(src_dir, "PL", char_key).stem
    return DialogGraph(
        char_key=char_key,
        file_stem=stem,
        start=data["START_NODE"],
        nodes=nodes,
    )


def _load_valid_items() -> set[str] | None:
    try:
        return mi.load_valid_items(CHARACTERS_CSV.parent / "items.csv")
    except Exception:
        return None


# --------------------------------------------------------------------------
# 2. analyze
# --------------------------------------------------------------------------

_VISITED_SELF = re.compile(r'visited\(\s*"(\d+)"\s*\)')
_VISITED_NPC = re.compile(r'visited\(\s*"([A-Z0-9_]+)"\s*,\s*"(\d+)"\s*\)')
_HAS_ITEM = re.compile(r'has_item\(\s*"([A-Z0-9_]+)"\s*\)')
_SELECTED = re.compile(r'selected\(\s*"([^"]+)"\s*\)')


def analyze(graph: DialogGraph, *, known_keys: set[str], known_items: set[str]) -> None:
    """Fill ``graph.problems`` / ``graph.global_problems`` with graph anomalies."""
    nodes = graph.nodes
    option_keys = {opt.key for opt in graph.option_list()}

    # reachability: options + resume edges, exactly like importer's _validate_graph
    seen: set[str] = set()
    queue = deque([graph.start])
    while queue:
        cur = queue.popleft()
        if cur in seen or cur not in nodes:
            continue
        seen.add(cur)
        for opt in nodes[cur].options:
            queue.append(opt.target)
        if nodes[cur].resume_node:
            queue.append(nodes[cur].resume_node)

    for key, node in nodes.items():
        if key not in seen:
            graph.problems[key].append("nieosiągalny (orphan)")
        if not node.is_final and not node.options:
            graph.problems[key].append("ślepy zaułek (brak opcji, brak -end)")
        elif not node.is_final and node.options and all(
            opt.condition != "True" for opt in node.options
        ):
            graph.problems[key].append("wszystkie opcje warunkowe (możliwy dead-end)")
        if node.is_final and not node.resume_node:
            graph.problems[key].append("-end bez resume (wróci do START)")

        for opt in node.options:
            cond = opt.condition
            if cond == "True":
                continue
            try:
                dialog_conditions.validate_condition(cond)
            except Exception as exc:  # noqa: BLE001 - report, don't crash
                graph.problems[key].append(f"opcja {opt.order}: zły warunek ({exc})")
                continue
            for ref in _VISITED_SELF.findall(cond):
                if ref not in nodes:
                    graph.problems[key].append(
                        f'opcja {opt.order}: visited("{ref}") - brak takiego węzła'
                    )
            for npc, ref in _VISITED_NPC.findall(cond):
                if npc not in known_keys:
                    graph.problems[key].append(
                        f'opcja {opt.order}: visited("{npc}", ...) - nieznany dialog_key'
                    )
            for item in _HAS_ITEM.findall(cond):
                if known_items and item not in known_items:
                    graph.problems[key].append(
                        f'opcja {opt.order}: has_item("{item}") - nieznany przedmiot'
                    )
            for sel in _SELECTED.findall(cond):
                if sel not in option_keys:
                    graph.problems[key].append(
                        f'opcja {opt.order}: selected("{sel}") - brak takiej opcji'
                    )

    if graph.start not in nodes:
        graph.global_problems.append(f"START_NODE {graph.start!r} nie istnieje")


# --------------------------------------------------------------------------
# 3. layout
# --------------------------------------------------------------------------


@dataclass
class Box:
    id: str
    lines: list[str]
    width: float
    height: float
    x: float = 0.0
    y: float = 0.0
    kind: str = "node"  # node | option
    bg: str = "#ffffff"
    stroke: str = STROKE_DEFAULT
    stroke_width: int = 2
    dashed: bool = False
    link: str | None = None


@dataclass
class Edge:
    src: str
    dst: str
    color: str = "#868e96"
    label: str = ""
    dashed: bool = False
    dotted: bool = False
    kind: str = "flow"  # flow | resume
    # fraction along the edge where the label sits; staggered so that the
    # labels of sibling options leaving one node do not pile up on each other
    label_t: float = 0.5


def wrap(text: str, width_px: float) -> list[str]:
    cols = max(8, int(width_px / CHAR_W))
    return textwrap.wrap(text, width=cols) or [""]


def _box(lines: list[str], width: float) -> tuple[list[str], float]:
    height = len(lines) * LINE_H + 2 * PAD
    return lines, height


def build_boxes(graph: DialogGraph, style: Style) -> tuple[dict[str, Box], list[Edge]]:
    boxes: dict[str, Box] = {}
    edges: list[Edge] = []

    for key, node in graph.nodes.items():
        header = f"#{key}"
        if key == graph.start:
            header += "  ▶ START"
        if node.is_final:
            header += "  ■ END"
        if node.resume_node:
            header += f"  ↺ resume {node.resume_node}"

        lines = [header]
        if node.result:
            lines += wrap(_result_badge(node.result), NODE_W - 2 * PAD)
        lines += wrap(plain(node.text, 200), NODE_W - 2 * PAD)
        for problem in graph.problems.get(key, []):
            lines += wrap("!! " + problem, NODE_W - 2 * PAD)

        _, height = _box(lines, NODE_W)
        bg = NODE_BG_PLAIN
        stroke, sw = STROKE_DEFAULT, 2
        if node.result:
            bg = NODE_BG_RESULT
        if node.is_final:
            bg, stroke, sw = NODE_BG_FINAL, STROKE_FINAL, 2
        if key == graph.start:
            bg, stroke, sw = NODE_BG_START, STROKE_START, 4
        problem = bool(graph.problems.get(key))
        boxes[f"n:{key}"] = Box(
            id=f"n:{key}",
            lines=lines,
            width=NODE_W,
            height=height,
            kind="node",
            bg=bg,
            stroke=STROKE_PROBLEM if problem else stroke,
            stroke_width=4 if problem else sw,
            dashed=problem,
            link=f"[[{graph.file_stem}#{key}]]",
        )

    for node in graph.nodes.values():
        for opt in node.options:
            fg = SENTIMENT_FG[opt.sentiment]
            if style == "boxes":
                lines = [f"{opt.order}  ·  {opt.sentiment}"]
                if opt.condition != "True":
                    lines += wrap("? " + opt.condition, OPT_W - 2 * PAD)
                lines += wrap(plain(opt.text, 90), OPT_W - 2 * PAD)
                _, height = _box(lines, OPT_W)
                oid = f"o:{opt.key}"
                boxes[oid] = Box(
                    id=oid,
                    lines=lines,
                    width=OPT_W,
                    height=height,
                    kind="option",
                    bg=SENTIMENT_BG[opt.sentiment],
                    stroke=fg,
                    dashed=opt.condition != "True",
                )
                edges.append(Edge(f"n:{opt.source}", oid, color="#adb5bd"))
                edges.append(Edge(oid, f"n:{opt.target}", color=fg))
            else:
                label = f"{opt.order} · {opt.sentiment}"
                if opt.condition != "True":
                    label += f"\n? {plain(opt.condition, 40)}"
                label += f"\n{plain(opt.text, 40)}"
                edges.append(
                    Edge(
                        f"n:{opt.source}",
                        f"n:{opt.target}",
                        color=fg,
                        label=label,
                        dashed=opt.condition != "True",
                        label_t=0.28 + 0.18 * ((opt.order - 1) % 4),
                    )
                )

    for key, node in graph.nodes.items():
        if node.resume_node and node.resume_node in graph.nodes:
            edges.append(
                Edge(
                    f"n:{key}",
                    f"n:{node.resume_node}",
                    color=STROKE_RESUME,
                    label="resume",
                    dotted=True,
                    kind="resume",
                )
            )

    return boxes, edges


def _result_badge(result: dict[str, Any]) -> str:
    parts = [str(result.get("category", "")).upper()]
    if result.get("money"):
        parts.append(f"money {result['money']:+d}")
    if result.get("health"):
        parts.append(f"health {result['health']:+d}")
    if result.get("value"):
        parts.append(f"sentiment {result['value']:+d}")
    if result.get("items"):
        parts.append(", ".join(result["items"]))
    return "[ " + "  ".join(p for p in parts if p) + " ]"


def _adjacency(boxes: dict[str, Box], edges: list[Edge]) -> dict[str, list[str]]:
    adj: dict[str, list[str]] = {b: [] for b in boxes}
    for e in edges:
        if e.src in adj and e.dst in boxes:
            adj[e.src].append(e.dst)
    return adj


def find_back_edges(
    boxes: dict[str, Box], edges: list[Edge], start: str
) -> set[tuple[str, str]]:
    """DFS from *start* (then any unvisited box); edges to a node on the stack loop."""
    adj = _adjacency(boxes, edges)
    color: dict[str, int] = {b: 0 for b in boxes}
    back: set[tuple[str, str]] = set()
    order = [start] + [b for b in boxes if b != start]

    for root in order:
        if root not in color or color[root] != 0:
            continue
        stack: list[tuple[str, Iterable[str]]] = [(root, iter(adj[root]))]
        color[root] = 1
        while stack:
            node, it = stack[-1]
            child = next(it, None)
            if child is None:
                color[node] = 2
                stack.pop()
                continue
            if color[child] == 1:
                back.add((node, child))
            elif color[child] == 0:
                color[child] = 1
                stack.append((child, iter(adj[child])))
    return back


def layout_py(
    boxes: dict[str, Box], edges: list[Edge], start: str, vgap: float = V_GAP
) -> None:
    """Layered (Sugiyama-lite) top-down layout, mutating box x/y in place."""
    back = find_back_edges(boxes, edges, start)
    fwd = [(e.src, e.dst) for e in edges if (e.src, e.dst) not in back and e.src != e.dst]

    succ: dict[str, list[str]] = defaultdict(list)
    indeg: dict[str, int] = {b: 0 for b in boxes}
    for s, d in fwd:
        succ[s].append(d)
        indeg[d] += 1

    # longest-path ranking over the DAG of forward edges
    rank: dict[str, int] = {b: 0 for b in boxes}
    queue = deque([b for b in boxes if indeg[b] == 0])
    processed = 0
    while queue:
        cur = queue.popleft()
        processed += 1
        for nxt in succ[cur]:
            rank[nxt] = max(rank[nxt], rank[cur] + 1)
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)

    layers: dict[int, list[str]] = defaultdict(list)
    for b in sorted(boxes, key=lambda k: (rank[k], k)):
        layers[rank[b]].append(b)

    # barycenter crossing reduction
    preds: dict[str, list[str]] = defaultdict(list)
    for s, d in fwd:
        preds[d].append(s)
    for _ in range(4):
        for r in sorted(layers)[1:]:
            pos = {b: i for i, b in enumerate(layers[r - 1])}
            layers[r].sort(
                key=lambda b: (
                    sum(pos.get(p, 0) for p in preds[b]) / len(preds[b])
                    if preds[b]
                    else 0.0
                )
            )
        for r in sorted(layers, reverse=True)[1:]:
            pos = {b: i for i, b in enumerate(layers[r + 1])} if (r + 1) in layers else {}
            layers[r].sort(
                key=lambda b: (
                    sum(pos.get(s, 0) for s in succ[b]) / len(succ[b])
                    if succ[b] and pos
                    else 0.0
                )
            )

    widest = max(
        (sum(boxes[b].width + H_GAP for b in row) for row in layers.values()),
        default=1000.0,
    )
    y = 0.0
    for r in sorted(layers):
        row = layers[r]
        row_w = sum(boxes[b].width for b in row) + H_GAP * (len(row) - 1)
        x = (widest - row_w) / 2
        for b in row:
            boxes[b].x = x
            boxes[b].y = y
            x += boxes[b].width + H_GAP
        y += max(boxes[b].height for b in row) + vgap


def layout_dot(
    boxes: dict[str, Box], edges: list[Edge], start: str, vgap: float = V_GAP
) -> None:
    """Position boxes with graphviz ``dot -Tplain`` (coordinates only)."""
    if not shutil.which("dot"):
        raise SystemExit(
            "graphviz not found - run `brew install graphviz` or use --layout py"
        )

    ids = {b: f"b{i}" for i, b in enumerate(boxes)}
    lines = ["digraph G {", "  rankdir=TB;", "  splines=ortho;", "  nodesep=0.5;", f"  ranksep={vgap / 72:.2f};"]
    for key, box in boxes.items():
        lines.append(
            f'  {ids[key]} [shape=box, fixedsize=true, '
            f"width={box.width / 72:.3f}, height={box.height / 72:.3f}];"
        )
    for e in edges:
        if e.src in ids and e.dst in ids:
            weight = 1 if e.kind == "resume" else 4
            lines.append(f"  {ids[e.src]} -> {ids[e.dst]} [weight={weight}];")
    lines.append("}")

    plain_out = subprocess.run(
        ["dot", "-Tplain"],
        input="\n".join(lines),
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    rev = {v: k for k, v in ids.items()}
    graph_h = 0.0
    coords: dict[str, tuple[float, float]] = {}
    for line in plain_out.splitlines():
        parts = line.split()
        if parts and parts[0] == "graph":
            graph_h = float(parts[3])
        elif parts and parts[0] == "node" and parts[1] in rev:
            coords[rev[parts[1]]] = (float(parts[2]), float(parts[3]))

    for key, (cx, cy) in coords.items():
        box = boxes[key]
        box.x = cx * 72 - box.width / 2
        box.y = (graph_h - cy) * 72 - box.height / 2


LAYOUTS = {"py": layout_py, "dot": layout_dot}


# --------------------------------------------------------------------------
# 4. render (Excalidraw)
# --------------------------------------------------------------------------


class ElementFactory:
    def __init__(self, seed: int = 1) -> None:
        self.rng = random.Random(seed)
        self.elements: list[dict[str, Any]] = []
        self._n = 0

    def _id(self, prefix: str) -> str:
        self._n += 1
        return f"{prefix}{self._n:04d}"

    def _base(self, eid: str, etype: str, x: float, y: float, w: float, h: float) -> dict:
        return {
            "id": eid,
            "type": etype,
            "x": round(x, 2),
            "y": round(y, 2),
            "width": round(w, 2),
            "height": round(h, 2),
            "angle": 0,
            "strokeColor": STROKE_DEFAULT,
            "backgroundColor": "transparent",
            "fillStyle": "solid",
            "strokeWidth": 2,
            "strokeStyle": "solid",
            "roughness": 1,
            "opacity": 100,
            "groupIds": [],
            "roundness": {"type": 3},
            "seed": self.rng.randint(1, 2**31 - 1),
            "version": 1,
            "isDeleted": False,
            "boundElements": None,
            "updated": 1,
            "link": None,
            "locked": False,
        }

    def container(self, box: Box) -> str:
        rid = self._id("r")
        tid = self._id("t")
        rect = self._base(rid, "rectangle", box.x, box.y, box.width, box.height)
        rect.update(
            {
                "backgroundColor": box.bg,
                "strokeColor": box.stroke,
                "strokeWidth": box.stroke_width,
                "strokeStyle": "dashed" if box.dashed else "solid",
                "boundElements": [{"type": "text", "id": tid}],
                "link": box.link,
            }
        )
        text = "\n".join(box.lines)
        txt = self._base(
            tid, "text", box.x + PAD, box.y + PAD, box.width - 2 * PAD,
            len(box.lines) * LINE_H,
        )
        txt.update(
            {
                "strokeColor": STROKE_TEXT,
                "text": text,
                "originalText": text,
                "fontSize": FONT_SIZE,
                "fontFamily": FONT_FAMILY,
                "textAlign": "left",
                "verticalAlign": "top",
                "containerId": rid,
                "autoResize": False,
                "lineHeight": LINE_HEIGHT,
                "boundElements": None,
            }
        )
        self.elements.append(rect)
        self.elements.append(txt)
        return rid

    def arrow(
        self,
        points: list[tuple[float, float]],
        *,
        color: str,
        dashed: bool = False,
        dotted: bool = False,
        label: str = "",
        label_t: float = 0.5,
        start_id: str | None = None,
        end_id: str | None = None,
    ) -> str:
        aid = self._id("a")
        x0, y0 = points[0]
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        el = self._base(
            aid, "arrow", x0, y0, max(xs) - min(xs), max(ys) - min(ys)
        )
        style = "dotted" if dotted else ("dashed" if dashed else "solid")
        el.update(
            {
                "strokeColor": color,
                "strokeStyle": style,
                "roundness": {"type": 2},
                "points": [[round(px - x0, 2), round(py - y0, 2)] for px, py in points],
                "lastCommittedPoint": None,
                "startBinding": (
                    {"elementId": start_id, "focus": 0, "gap": 4} if start_id else None
                ),
                "endBinding": (
                    {"elementId": end_id, "focus": 0, "gap": 4} if end_id else None
                ),
                "startArrowhead": None,
                "endArrowhead": "arrow",
                "elbowed": False,
            }
        )
        self.elements.append(el)

        if label:
            # An unbound text placed at ``label_t`` along the polyline: Excalidraw
            # always centres a *bound* arrow label, which makes sibling options
            # leaving the same node stack on top of each other.
            lx, ly = point_at(points, label_t)
            self.label(lx, ly, label, size=13, color=color, center=True)
        return aid

    def label(
        self,
        x: float,
        y: float,
        text: str,
        size: int = 20,
        color: str = STROKE_TEXT,
        center: bool = False,
    ) -> None:
        tid = self._id("t")
        lines = text.split("\n")
        width = max(len(ln) for ln in lines) * size * 0.55
        height = len(lines) * size * LINE_HEIGHT
        if center:
            x -= width / 2
            y -= height / 2
        el = self._base(tid, "text", x, y, width, height)
        el.update(
            {
                "strokeColor": color,
                "text": text,
                "originalText": text,
                "fontSize": size,
                "fontFamily": FONT_FAMILY,
                "textAlign": "center" if center else "left",
                "verticalAlign": "top",
                "containerId": None,
                "autoResize": True,
                "lineHeight": LINE_HEIGHT,
                "boundElements": None,
            }
        )
        self.elements.append(el)


def point_at(points: list[tuple[float, float]], t: float) -> tuple[float, float]:
    """Point at fraction *t* of the polyline's total length."""
    segs = [
        (points[i], points[i + 1], math.dist(points[i], points[i + 1]))
        for i in range(len(points) - 1)
    ]
    total = sum(s[2] for s in segs) or 1.0
    target = total * min(max(t, 0.0), 1.0)
    run = 0.0
    for (x0, y0), (x1, y1), length in segs:
        if run + length >= target:
            f = (target - run) / length if length else 0.0
            return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)
        run += length
    return points[-1]


def _anchor_points(
    a: Box, b: Box, back: bool, gutter_x: float
) -> list[tuple[float, float]]:
    """Route an edge: straight down for forward edges, around the side for loops."""
    if not back:
        return [
            (a.x + a.width / 2, a.y + a.height),
            (b.x + b.width / 2, b.y),
        ]
    y_a = a.y + a.height / 2
    y_b = b.y + b.height / 2
    return [
        (a.x + a.width, y_a),
        (gutter_x, y_a),
        (gutter_x, y_b),
        (b.x + b.width, y_b),
    ]


def render_excalidraw(
    graph: DialogGraph,
    boxes: dict[str, Box],
    edges: list[Edge],
    style: Style,
    layout: LayoutName,
) -> dict[str, Any]:
    fac = ElementFactory(seed=hash(graph.char_key) & 0xFFFF)
    rect_ids: dict[str, str] = {}

    min_x = min(b.x for b in boxes.values())
    max_x = max(b.x + b.width for b in boxes.values())
    min_y = min(b.y for b in boxes.values())
    max_y = max(b.y + b.height for b in boxes.values())

    _title_and_legend(fac, graph, style, layout, min_x, min_y)

    for box in boxes.values():
        rect_ids[box.id] = fac.container(box)

    back = find_back_edges(boxes, edges, f"n:{graph.start}")
    gutter = max_x + 60
    for e in edges:
        if e.src not in boxes or e.dst not in boxes:
            continue
        a, b = boxes[e.src], boxes[e.dst]
        is_back = (e.src, e.dst) in back or e.kind == "resume" or b.y <= a.y
        pts = _anchor_points(a, b, is_back, gutter)
        if is_back and e.kind != "resume":
            gutter += 24
        color = STROKE_BACK if (is_back and e.kind != "resume") else e.color
        aid = fac.arrow(
            pts,
            color=color,
            dashed=e.dashed,
            dotted=e.dotted,
            label=e.label,
            label_t=e.label_t,
            start_id=rect_ids[e.src] if not is_back else None,
            end_id=rect_ids[e.dst] if not is_back else None,
        )
        if not is_back:
            for bid in (e.src, e.dst):
                el = next(x for x in fac.elements if x["id"] == rect_ids[bid])
                el["boundElements"] = (el["boundElements"] or []) + [
                    {"type": "arrow", "id": aid}
                ]

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "https://github.com/zsviczian/obsidian-excalidraw-plugin",
        "elements": fac.elements,
        "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
        "files": {},
    }


LEGEND_TEXT = (
    "LEGENDA:  zielony = START   czerwony = -end (final)   żółty = węzeł z efektem\n"
    "różowa przerywana ramka = PROBLEM   fioletowa kropkowana = resume   "
    "pomarańczowa = pętla wsteczna\n"
    "sentyment (kolor opcji): kind / weak / neutral / angry / smart / funny / technical"
)


def _problem_text(graph: DialogGraph) -> tuple[str, bool]:
    problems = [
        f"#{k}: {p}" for k, ps in sorted(graph.problems.items()) for p in ps
    ] + list(graph.global_problems)
    if not problems:
        return "PROBLEMY: brak", False
    head = f"PROBLEMY ({len(problems)}):\n" + "\n".join(problems[:20])
    if len(problems) > 20:
        head += f"\n… i {len(problems) - 20} więcej"
    return head, True


def _subtitle(graph: DialogGraph, style: Style, layout: LayoutName) -> str:
    return (
        f"{len(graph.nodes)} węzłów, {len(graph.option_list())} opcji  "
        f"|  START #{graph.start}  |  style={style} layout={layout}"
    )


def _title_and_legend(
    fac: ElementFactory,
    graph: DialogGraph,
    style: Style,
    layout: LayoutName,
    min_x: float,
    min_y: float,
) -> None:
    x = min_x
    y = min_y - 260
    fac.label(x, y, f"{graph.file_stem}  ({graph.char_key})", size=28, color="#1e40af")
    fac.label(x, y + 40, _subtitle(graph, style, layout), size=16, color="#495057")
    fac.label(x, y + 70, LEGEND_TEXT, size=14, color="#495057")
    head, has_problems = _problem_text(graph)
    fac.label(x, y + 145, head, size=14, color="#e03131" if has_problems else "#2f9e44")


# --------------------------------------------------------------------------
# 5. write
# --------------------------------------------------------------------------

_OBSIDIAN_HEADER = """---
excalidraw-plugin: parsed
tags: [excalidraw]
---
==⚠  Switch to EXCALIDRAW VIEW in the MORE OPTIONS menu of this document. ⚠== You can decompress Drawing data with the command palette: 'Decompress current Excalidraw file'. For more info check in plugin settings under 'Saving'

# Excalidraw Data

## Text Elements
%%
## Drawing
```json
"""

_OBSIDIAN_FOOTER = "\n```\n%%\n"


def write_obsidian(scene: dict[str, Any], path: Path) -> None:
    path.write_text(
        _OBSIDIAN_HEADER + json.dumps(scene, ensure_ascii=False, indent=2) + _OBSIDIAN_FOOTER,
        encoding="utf-8",
    )


def write_excalidraw(scene: dict[str, Any], path: Path) -> None:
    scene = dict(scene, source="https://excalidraw.com")
    path.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")


def _levels(graph: DialogGraph) -> dict[str, int]:
    """BFS depth from START over option edges only.

    vis-network's own ``sortMethod: "directed"`` chokes on this graph: the resume
    loops (e.g. 990 -> 001) are cycles, and it ends up piling most nodes onto one
    rank.  Feeding it an explicit ``level`` per node keeps the ranks honest.
    """
    level = {graph.start: 0}
    queue = deque([graph.start])
    while queue:
        cur = queue.popleft()
        for opt in graph.nodes[cur].options:
            if opt.target in graph.nodes and opt.target not in level:
                level[opt.target] = level[cur] + 1
                queue.append(opt.target)
    # nodes reachable only via resume (or not at all) go one rank past the deepest
    tail = max(level.values(), default=0) + 1
    return {key: level.get(key, tail) for key in graph.nodes}


def graph_to_dict(graph: DialogGraph) -> dict[str, Any]:
    """Serialize a DialogGraph for the DataviewJS renderer (vis-network draws it)."""
    level = _levels(graph)
    nodes = [
        {
            "id": key,
            "level": level[key],
            "text": node.text,
            "is_start": key == graph.start,
            "is_final": node.is_final,
            "result": _result_badge(node.result) if node.result else None,
            "resume": node.resume_node,
            "problems": list(graph.problems.get(key, [])),
            "link": f"{graph.file_stem}#{key}",
        }
        for key, node in graph.nodes.items()
    ]

    edges: list[dict[str, Any]] = []
    for node in graph.nodes.values():
        for opt in node.options:
            edges.append(
                {
                    "from": opt.source,
                    "to": opt.target,
                    "kind": "option",
                    "key": opt.key,
                    "order": opt.order,
                    "sentiment": opt.sentiment,
                    "text": opt.text,
                    "condition": None if opt.condition == "True" else opt.condition,
                }
            )
        if node.resume_node:
            edges.append(
                {
                    "from": node.key,
                    "to": node.resume_node,
                    "kind": "resume",
                    "key": None,
                    "order": 0,
                    "sentiment": None,
                    "text": None,
                    "condition": None,
                }
            )

    return {
        "meta": {
            "character": graph.file_stem,
            "dialog_key": graph.char_key,
            "source": f"PL/Postacie/{graph.file_stem}.md",
            "start_node": graph.start,
            "counts": {"nodes": len(graph.nodes), "options": len(graph.option_list())},
            "global_problems": list(graph.global_problems),
            "palette": {
                name: {"bg": bg, "fg": SENTIMENT_FG[name]}
                for name, bg in SENTIMENT_BG.items()
            },
        },
        "nodes": nodes,
        "edges": edges,
    }


def write_json(graph: DialogGraph, out_dir: Path) -> Path:
    """Write ``_graphs/data/<KEY>.json`` + the DataviewJS note that renders it."""
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    data_path = data_dir / f"{graph.char_key}.json"
    data_path.write_text(
        json.dumps(graph_to_dict(graph), ensure_ascii=False, indent=1), encoding="utf-8"
    )

    note_path = out_dir / f"{graph.file_stem} - graf.md"
    note_path.write_text(
        _DATAVIEW_NOTE.replace("__KEY__", graph.char_key).replace(
            "__CHARACTER__", graph.file_stem
        ),
        encoding="utf-8",
    )
    return note_path


_DATAVIEW_NOTE = """---
tags: [graf-dialogu]
---

# __CHARACTER__ - graf dialogu

> [!info] Wygenerowane przez `scripts/dialog_graph.py --format json` - nie edytuj ręcznie.
> Klik w węzeł: podświetl sąsiadów. Podwójny klik: otwórz węzeł w źródłowym pliku.
> Najedź na węzeł lub strzałkę, żeby zobaczyć treść, warunek i efekt.

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
    .mom-tip-q { font-style: italic; color: var(--text-muted); }
    .mom-tip-r { margin-top: 6px; font-family: var(--font-monospace); font-size: 12px; }
    .mom-tip-c { margin-top: 6px; font-family: var(--font-monospace); font-size: 12px;
        color: var(--text-accent); word-break: break-word; }
    .mom-tip-p { margin-top: 6px; color: var(--text-error); font-size: 12px; }
    .mom-tip-hint { margin-top: 8px; font-size: 11px; color: var(--text-faint); }
    .mom-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
    .mom-bar button { font-size: 12px; padding: 3px 10px; cursor: pointer; }
    .mom-count { font-size: 12px; color: var(--text-muted); margin-left: auto; }
    .mom-probs { margin-bottom: 8px; padding: 8px 12px; border-radius: 6px; font-size: 12px;
        background: var(--background-modifier-error-hover); border: 1px solid var(--text-error); }
    .mom-probs b { color: var(--text-error); }
    .mom-probs li { cursor: pointer; }
    .mom-probs li:hover { text-decoration: underline; }
    .mom-net { border: 1px solid var(--background-modifier-border); border-radius: 8px; }
    `;
    document.head.appendChild(st);
}

// ---------------------------------------------------------------------- dane
const G = JSON.parse(await app.vault.adapter.read(DATA));
const PAL = G.meta.palette;
const NOTE = dv.current().file.path;
const box = dv.container;

const ROLE = (n) =>
      n.is_start ? { background: "#b2f2bb", border: "#2f9e44" }
    : n.is_final ? { background: "#ffc9c9", border: "#e03131" }
    : n.result   ? { background: "#fff3bf", border: "#f08c00" }
    :              { background: "#a5d8ff", border: "#1971c2" };

const el = (tag, cls, txt) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt) e.textContent = txt;
    return e;
};

function nodeTip(n) {
    const t = el("div", "mom-tip");
    const role = n.is_start ? " - START" : n.is_final ? " - END" : "";
    t.append(el("div", "mom-tip-h", `#${n.id}${role}`));
    t.append(el("div", "mom-tip-q", n.text || "(brak tekstu)"));
    if (n.result) t.append(el("div", "mom-tip-r", `efekt: ${n.result}`));
    if (n.resume) t.append(el("div", "mom-tip-r", `resume -> #${n.resume}`));
    for (const p of n.problems) t.append(el("div", "mom-tip-p", `! ${p}`));
    t.append(el("div", "mom-tip-hint", "podwójny klik - otwórz w źródle"));
    return t;
}

function edgeTip(e) {
    const t = el("div", "mom-tip");
    if (e.kind === "resume") {
        t.append(el("div", "mom-tip-h", `resume: #${e.from} -> #${e.to}`));
        t.append(el("div", "mom-tip-q", "powrót po zakończeniu rozmowy"));
        return t;
    }
    t.append(el("div", "mom-tip-h", `opcja ${e.order} - ${e.sentiment}`));
    t.append(el("div", "mom-tip-q", e.text || "(brak tekstu)"));
    t.append(el("div", "mom-tip-c", e.condition ? `warunek: ${e.condition}` : "bez warunku"));
    return t;
}

const visNodes = G.nodes.map((n) => ({
    id: n.id,
    level: n.level,
    label: n.id,
    title: nodeTip(n),
    color: ROLE(n),
    borderWidth: n.problems.length ? 4 : 2,
    shapeProperties: { borderDashes: n.problems.length ? [6, 4] : false },
    shape: "circle",
    font: { size: 15, face: "var(--font-interface)", color: "#1e1e1e" },
}));

const LINE = "#9aa0a8";  // wszystkie krawędzie jednolicie szare; sentyment niesie etykieta
const RESUME = "#0dcaf0";  // cyjan - unikalny, nie koliduje z fioletem sentymentu "smart"
// Ile krawędzi biegnie tą samą parą w tym samym kierunku - żeby równoległe opcje
// rozłożyć na osobne łuki (inaczej nakładają się na jedną krzywą i giną).
const pairSeen = {};
const pairTotal = {};
G.edges.forEach((e) => { const k = e.from + ">" + e.to; pairTotal[k] = (pairTotal[k] || 0) + 1; });
const visEdges = G.edges.map((e, i) => {
    const col = e.kind === "resume" ? RESUME : (PAL[e.sentiment]?.fg ?? "#868e96");
    const k = e.from + ">" + e.to;
    const idx = (pairSeen[k] = (pairSeen[k] || 0) + 1) - 1;
    const round = pairTotal[k] === 1 ? 0.15 : 0.12 + idx * 0.22;
    return {
        id: i,
        from: e.from,
        to: e.to,
        title: edgeTip(e),
        label: e.kind === "resume" ? "resume" : `${e.order} ${e.sentiment}${e.condition ? " ?" : ""}`,
        color: { color: LINE, highlight: LINE, hover: LINE, opacity: 0.8 },
        dashes: e.kind === "resume" ? [2, 4] : e.condition ? [6, 4] : false,
        width: 0.8,
        smooth: { enabled: true, type: "curvedCW", roundness: round },
        arrows: { to: { enabled: true, scaleFactor: 0.8 } },
        font: { size: 11, color: col, strokeWidth: 4, strokeColor: "#ffffff", align: "horizontal" },
    };
});

// -------------------------------------------------------------------- widok
const bar = box.appendChild(el("div", "mom-bar"));
const btnLay = bar.appendChild(el("button", null, "Ułóż od nowa"));
const btnPhys = bar.appendChild(el("button", null, "Fizyka: wył"));
const btnFit = bar.appendChild(el("button", null, "Dopasuj"));
const btnReset = bar.appendChild(el("button", null, "Odznacz"));
bar.appendChild(
    el("span", "mom-count",
       `${G.meta.counts.nodes} węzłów, ${G.meta.counts.options} opcji, START #${G.meta.start_node}`)
);

const probs = [
    ...G.meta.global_problems.map((m) => [null, m]),
    ...G.nodes.flatMap((n) => n.problems.map((m) => [n.id, m])),
];

const graphEl = el("div", "mom-net");
graphEl.style.height = HEIGHT;

// Force-directed (ten sam silnik i solver co pyvis: barnesHut). Hierarchia
// rozciągała graf w jedną stronę; fizyka daje naturalny, promienisty układ,
// w którym hub (001) siada w środku, a wątki rozchodzą się dokoła. improvedLayout
// (Kamada-Kawai dla <100 węzłów) daje dobry punkt startowy i minimalizuje przecięcia.
const options = {
    layout: { improvedLayout: true, randomSeed: 42 },
    physics: {
        enabled: true,
        solver: "barnesHut",
        // Jak pyvis: mocne odpychanie + słabe sprężyny + wyraźna grawitacja do środka.
        // Sztywne sprężyny prostują łańcuch w nitkę; słabe pozwalają mu zwinąć się w kłębek.
        barnesHut: { gravitationalConstant: -38000, centralGravity: 0.55,
                     springLength: 90, springConstant: 0.002, damping: 0.45, avoidOverlap: 0.1 },
        stabilization: { enabled: true, iterations: 700, updateInterval: 25, fit: true },
        maxVelocity: 45, minVelocity: 0.75,
    },
    interaction: { dragNodes: true, hover: true, tooltipDelay: 120, navigationButtons: true,
                   zoomView: true, multiselect: false },
    edges: { smooth: { enabled: true, type: "curvedCW", roundness: 0.2 } },
    nodes: { margin: 8, widthConstraint: { maximum: 180 } },
};

if (probs.length) {
    const p = box.appendChild(el("div", "mom-probs"));
    p.append(el("b", null, `PROBLEMY (${probs.length})`));
    const ul = p.appendChild(document.createElement("ul"));
    for (const [id, msg] of probs) {
        const li = ul.appendChild(el("li", null, id ? `#${id}: ${msg}` : msg));
        if (id) li.onclick = () => { highlight(id); network.selectNodes([id]);
                                     network.focus(id, { scale: 1.1, animation: true }); };
    }
}
box.appendChild(graphEl);

const nodesDS = new vis.DataSet(visNodes);
const edgesDS = new vis.DataSet(visEdges);
let network;

// Fizyka rozkłada graf, po czym ją zamrażamy: węzły zostają tam, gdzie usiadły,
// i dają się swobodnie przeciągać (dragNodes), bez rozjeżdżania się przy każdym
// ruchu. Czyścimy zapisane pozycje, żeby "Ułóż od nowa" liczyło layout od zera.
function buildNetwork() {
    if (network) network.destroy();
    nodesDS.update(visNodes.map((n) => ({ id: n.id, x: undefined, y: undefined, fixed: false })));

    network = new vis.Network(graphEl, { nodes: nodesDS, edges: edgesDS }, options);
    network.once("stabilizationIterationsDone", () => {
        network.setOptions({ physics: { enabled: false } });
        phys = false;
        btnPhys.textContent = "Fizyka: wył";
        network.fit({ animation: false });
    });
    bindEvents();
}

function bindEvents() {
    network.on("click", (p) => (p.nodes.length ? highlight(p.nodes[0]) : clearHighlight()));
    network.on("doubleClick", (p) => {
        const n = byId.get(p.nodes[0]);
        if (n) app.workspace.openLinkText(n.link, NOTE, "tab");
    });
}

// ------------------------------------------------- klik: podświetl sąsiadów
const adj = new Map(G.nodes.map((n) => [n.id, new Set()]));
for (const e of G.edges) {
    adj.get(e.from)?.add(e.to);
    adj.get(e.to)?.add(e.from);
}
const DIM_N = { background: "#f1f3f5", border: "#dee2e6" };

function highlight(id) {
    const keep = new Set([id, ...(adj.get(id) ?? [])]);
    nodesDS.update(visNodes.map((n) => keep.has(n.id)
        ? { id: n.id, color: n.color, font: { ...n.font, color: "#1e1e1e" }, hidden: false }
        : { id: n.id, color: DIM_N, font: { ...n.font, color: "#ced4da" } }));
    edgesDS.update(visEdges.map((e) => (e.from === id || e.to === id)
        ? { id: e.id, color: { color: LINE, opacity: 1 }, width: 1.4, font: e.font }
        : { id: e.id, color: { color: "#e9ecef", opacity: 0.15 },
            width: e.width, font: { ...e.font, color: "rgba(0,0,0,0)", strokeWidth: 0 } }));
}

function clearHighlight() {
    nodesDS.update(visNodes);
    edgesDS.update(visEdges);
}

const byId = new Map(G.nodes.map((n) => [n.id, n]));

// ------------------------------------------------------------------ toolbar
let phys = false;

btnLay.onclick = () => buildNetwork();
btnPhys.onclick = () => {
    phys = !phys;
    network.setOptions({ physics: { enabled: phys } });
    btnPhys.textContent = `Fizyka: ${phys ? "wł" : "wył"}`;
};
btnFit.onclick = () => network.fit({ animation: true });
btnReset.onclick = () => { network.unselectAll(); clearHighlight(); };

buildNetwork();
```
"""


def write_svg(
    graph: DialogGraph,
    boxes: dict[str, Box],
    edges: list[Edge],
    path: Path,
    style: Style = "boxes",
    layout: LayoutName = "py",
) -> None:
    """Cheap debug render - same layout, so overlaps/sizing are visible instantly."""
    min_x = min(b.x for b in boxes.values()) - 40
    min_y = min(b.y for b in boxes.values()) - 300
    max_x = max(b.x + b.width for b in boxes.values()) + 400
    max_y = max(b.y + b.height for b in boxes.values()) + 40
    w, h = max_x - min_x, max_y - min_y

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x} {min_y} {w} {h}" '
        f'width="{w:.0f}" height="{h:.0f}" font-family="sans-serif">',
        f'<rect x="{min_x}" y="{min_y}" width="{w}" height="{h}" fill="#fff"/>',
        '<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="7" refY="3" '
        'orient="auto"><path d="M0,0 L7,3 L0,6 z" fill="context-stroke"/></marker></defs>',
    ]

    hx = min_x + 40
    hy = min_y + 30
    out.append(
        f'<text x="{hx}" y="{hy}" font-size="26" fill="#1e40af" font-weight="bold">'
        f"{xml_escape(graph.file_stem)} ({graph.char_key})</text>"
    )
    out.append(
        f'<text x="{hx}" y="{hy + 26}" font-size="14" fill="#495057">'
        f"{xml_escape(_subtitle(graph, style, layout))}</text>"
    )
    for i, line in enumerate(LEGEND_TEXT.split("\n")):
        out.append(
            f'<text x="{hx}" y="{hy + 52 + i * 16}" font-size="12" fill="#495057">'
            f"{xml_escape(line)}</text>"
        )
    head, has_problems = _problem_text(graph)
    color = "#e03131" if has_problems else "#2f9e44"
    for i, line in enumerate(head.split("\n")):
        out.append(
            f'<text x="{hx}" y="{hy + 120 + i * 16}" font-size="12" fill="{color}">'
            f"{xml_escape(line)}</text>"
        )

    back = find_back_edges(boxes, edges, f"n:{graph.start}")
    gutter = max(b.x + b.width for b in boxes.values()) + 60
    for e in edges:
        if e.src not in boxes or e.dst not in boxes:
            continue
        a, b = boxes[e.src], boxes[e.dst]
        is_back = (e.src, e.dst) in back or e.kind == "resume" or b.y <= a.y
        pts = _anchor_points(a, b, is_back, gutter)
        if is_back and e.kind != "resume":
            gutter += 24
        color = STROKE_BACK if (is_back and e.kind != "resume") else e.color
        dash = ' stroke-dasharray="2 6"' if e.dotted else (
            ' stroke-dasharray="8 4"' if e.dashed else ""
        )
        d = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        out.append(
            f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="2"'
            f'{dash} marker-end="url(#ah)"/>'
        )
        if e.label:
            lx, ly = point_at(pts, e.label_t)
            lines = e.label.split("\n")
            ly -= len(lines) * 13 / 2
            for i, line in enumerate(lines):
                out.append(
                    f'<text x="{lx:.1f}" y="{ly + (i + 1) * 13:.1f}" font-size="11" '
                    f'fill="{color}" text-anchor="middle">{xml_escape(line)}</text>'
                )

    for box in boxes.values():
        dash = ' stroke-dasharray="6 4"' if box.dashed else ""
        out.append(
            f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{box.width:.1f}" '
            f'height="{box.height:.1f}" rx="8" fill="{box.bg}" stroke="{box.stroke}" '
            f'stroke-width="{box.stroke_width}"{dash}/>'
        )
        for i, line in enumerate(box.lines):
            out.append(
                f'<text x="{box.x + PAD:.1f}" y="{box.y + PAD + (i + 1) * LINE_H - 4:.1f}" '
                f'font-size="{FONT_SIZE - 2}">{xml_escape(line)}</text>'
            )

    out.append("</svg>")
    path.write_text("\n".join(out), encoding="utf-8")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def generate(
    char_key: str,
    *,
    style: Style,
    layout: LayoutName,
    fmt: OutFormat,
    out_dir: Path,
    known_keys: set[str],
    known_items: set[str],
    suffix: str = "",
) -> Path:
    graph = read_graph(char_key)
    analyze(graph, known_keys=known_keys, known_items=known_items)

    out_dir.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        # vis-network lays the graph out itself, so layers 3-4 are skipped.
        path = write_json(graph, out_dir)
        _report(char_key, graph, path)
        return path

    boxes, edges = build_boxes(graph, style)
    vgap = ARROW_V_GAP if style == "arrows" else V_GAP
    LAYOUTS[layout](boxes, edges, f"n:{graph.start}", vgap=vgap)

    stem = graph.file_stem + suffix
    if fmt == "obsidian":
        path = out_dir / f"{stem}.excalidraw.md"
        write_obsidian(render_excalidraw(graph, boxes, edges, style, layout), path)
    elif fmt == "excalidraw":
        path = out_dir / f"{stem}.excalidraw"
        write_excalidraw(render_excalidraw(graph, boxes, edges, style, layout), path)
    else:
        path = out_dir / f"{stem}.svg"
        write_svg(graph, boxes, edges, path, style, layout)

    _report(char_key, graph, path)
    return path


def _report(char_key: str, graph: DialogGraph, path: Path) -> None:
    n_problems = sum(len(v) for v in graph.problems.values()) + len(graph.global_problems)
    try:
        shown = path.relative_to(_REPO_ROOT)
    except ValueError:
        shown = path
    print(
        f"{char_key:<24} {len(graph.nodes):>3} węzłów  {len(graph.option_list()):>3} opcji  "
        f"{n_problems:>2} problemów  ->  {shown}"
    )


def _known_items() -> set[str]:
    try:
        config = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
        return set(config.get("items", {}))
    except Exception:
        return set()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--character", "-c", help="dialog key, e.g. MADAME_SARCASMIA")
    ap.add_argument("--all", action="store_true", help="all characters")
    ap.add_argument("--style", choices=["boxes", "arrows"], default="boxes")
    ap.add_argument("--layout", choices=["py", "dot"], default="py")
    ap.add_argument(
        "--format", choices=["obsidian", "excalidraw", "svg", "json"], default="obsidian"
    )
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--suffix", default="", help="append to output file stem")
    args = ap.parse_args(argv)

    keys = mi._discover_character_keys(DOC_DIR)
    if args.all:
        targets = keys
    elif args.character:
        targets = [args.character]
    else:
        ap.error("pass --character KEY or --all")

    known_items = _known_items()
    failed = 0
    for key in targets:
        try:
            generate(
                key,
                style=args.style,
                layout=args.layout,
                fmt=args.format,
                out_dir=args.out,
                known_keys=set(keys),
                known_items=known_items,
                suffix=args.suffix,
            )
        except mi.DialogImportError as exc:
            failed += 1
            print(f"{key:<24} POMINIĘTY - błąd importu: {exc}", file=sys.stderr)
    if failed and len(targets) == 1:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
