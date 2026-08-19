---
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
