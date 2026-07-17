---
tags: [graf-questow]
---

# Questy - graf

> [!info] Wygenerowane przez `scripts/quest_graph.py` - nie edytuj ręcznie.
> Klik w węzeł: podświetl sąsiadów. Podwójny klik: otwórz quest w źródłowym pliku.
> Najedź na węzeł, żeby zobaczyć opis, warunek zamknięcia i nagrody.

```dataviewjs
const KEY = "QUESTS";
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
