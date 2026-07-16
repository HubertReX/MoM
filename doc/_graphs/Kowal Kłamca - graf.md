---
tags: [graf-dialogu]
---

# Kowal Kłamca - graf dialogu

> [!info] Wygenerowane przez `scripts/dialog_graph.py --format json` - nie edytuj ręcznie.
> Klik w węzeł: podświetl sąsiadów. Podwójny klik: otwórz węzeł w źródłowym pliku.
> Najedź na węzeł lub strzałkę, żeby zobaczyć treść, warunek i efekt.

```dataviewjs
const KEY = "HAMMER_HOAXHEART";
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
