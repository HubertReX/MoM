#!/usr/bin/env python3
"""Generuje `doc/_attachements/design-system-progress.html` - log before/after design-systemu UI.

- **PRZED** = zaszyte bazowe zrzuty w `doc/_attachements/_progress_assets/before/`
  (stan sprzed prac; wyekstrahowane z audytu, nie zmieniają się).
- **PO** = świeże zrzuty bieżącego stanu gry (przechwytywane headless) + rendery
  syntetyczne (pasek sentymentu z kodu, zbliżenia keycapów).

Użycie::

    python scripts/gen_design_system_progress.py              # capture + build
    python scripts/gen_design_system_progress.py --no-capture # sam build z ostatnich zrzutów

Zrzuty lecą do `screenshots/agent/` (gitignored) pod prefiksem ``progress_after``;
wynikowy HTML osadza wszystko jako base64, więc jest samowystarczalny.
"""
from __future__ import annotations

import argparse
import base64
import os
import subprocess
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402  (po ustawieniu dummy sterowników)
from PIL import Image  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SS = REPO / "screenshots/agent"
BEFORE = REPO / "doc/_attachements/_progress_assets/before"
SCRATCH = REPO / "doc/_attachements/_progress_assets/_after"
OUT = REPO / "doc/_attachements/design-system-progress.html"
PREFIX = "progress_after"
PY = str(REPO / ".venv/bin/python3")

# --- 1. capture -------------------------------------------------------------

def capture() -> None:
    """Uruchom grę headless i przechwyć 5 ekranów (dialog przez pewny spacer do Barmana)."""
    inp = REPO / "agent_input.txt"
    env = dict(os.environ)
    env.update(MOM_AGENT_CONTROL="1", SDL_VIDEODRIVER="dummy",
               SDL_AUDIODRIVER="dummy", MOM_AGENT_SS_PREFIX=PREFIX)
    proc = subprocess.Popen([PY, "project/main.py"], cwd=str(REPO), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def step(tokens: str, wait: float) -> None:
        inp.write_text(tokens)
        time.sleep(wait)

    try:
        time.sleep(6.0)
        step("screenshot:main_menu", 2.0)
        step("accept", 5.0)                       # nowa gra -> mapa
        step("screenshot:gameplay", 1.5)
        step("help", 1.5)
        step("screenshot:help", 1.5)
        step("help", 1.0)
        step("quest_log", 1.5)
        step("screenshot:quest", 1.5)
        step("quest_log", 1.0)
        # dialog: zejdź i skręć w prawo do Barmana (sekwencja sprawdzona empirycznie)
        step("down:25", 2.0)
        step("talk:5", 1.5)
        step("right:15", 1.5)
        step("talk:5", 1.5)
        step("screenshot:dialog", 1.5)
        step("exit", 1.0)
    finally:
        time.sleep(1.0)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def latest(label: str) -> Path:
    """Najnowszy zrzut `agent_<PREFIX>_*_<label>.png`."""
    cands = list(SS.glob(f"agent_{PREFIX}_*_{label}.png"))
    if not cands:
        raise FileNotFoundError(f"brak zrzutu dla '{label}' - uruchom bez --no-capture")
    return max(cands, key=os.path.getmtime)


# --- 2. syntetyczne rendery -------------------------------------------------

def render_sentiment(new: bool, out: Path) -> None:
    """Pasek sentymentu wprost z logiki kodu (stary vs nowy) na ciemnym tle dialogu."""
    pygame.init()
    if not pygame.display.get_surface():
        pygame.display.set_mode((1, 1))
    W, H = 120, 40
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    s.fill((26, 34, 38, 255))
    bar_w, bar_h = 80, 8
    x, y = (W - bar_w) // 2, (H - bar_h) // 2
    sentiment = 65
    fill_w = int(bar_w * sentiment / 100)
    col = (int(255 * (100 - sentiment) / 50), 255, 0) if sentiment >= 50 \
        else (255, int(255 * sentiment / 50), 0)
    if new:
        r = bar_h // 2
        pygame.draw.rect(s, (18, 18, 18), (x, y, bar_w, bar_h), border_radius=r)
        pygame.draw.rect(s, col, (x, y, fill_w, bar_h), border_radius=r)
    else:
        pygame.draw.rect(s, (40, 40, 40), (x, y, bar_w, bar_h), border_radius=2)
        pygame.draw.rect(s, col, (x, y, fill_w, bar_h), border_radius=2)
        pygame.draw.rect(s, (255, 252, 103), (x, y, bar_w, bar_h), width=1, border_radius=2)
    pygame.image.save(pygame.transform.scale_by(s, 6), str(out))


def crop_hotbar(src: Path, out: Path) -> None:
    Image.open(src).crop((250, 560, 780, 680)).save(out)


# --- 3. build HTML ----------------------------------------------------------

def uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def img(path: Path) -> str:
    return f'<img src="{uri(path)}">'


STYLE = """
:root{--bg:#16161a;--card:#1e1e24;--bd:#33333c;--tx:#e8e8e6;--mut:#9a9a96;--ac:#748ffc}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);
font-family:-apple-system,Segoe UI,Roboto,system-ui,sans-serif;line-height:1.5}
.wrap{max-width:1200px;margin:0 auto;padding:32px 20px}
h1{font-size:1.6rem;margin:0 0 4px}.lead{color:var(--mut);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:20px;margin-bottom:20px}
h2{font-size:1.15rem;margin:0 0 4px}.note{color:var(--mut);font-size:.9rem;margin:0 0 14px}
.ba{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:760px){.ba{grid-template-columns:1fr}}
figure{margin:0}figcaption{font-size:.72rem;letter-spacing:.08em;color:var(--mut);
font-weight:700;margin-bottom:6px}
img{width:100%;border:1px solid var(--bd);border-radius:6px;image-rendering:pixelated;display:block}
.tag{display:inline-block;background:#26304d;color:#9db4ff;font-size:.72rem;font-weight:700;
padding:2px 10px;border-radius:999px;margin-right:6px;margin-bottom:4px}
table{border-collapse:collapse;width:100%;font-size:.86rem}
th,td{border:1px solid var(--bd);padding:6px 10px;text-align:left}
th{color:var(--mut);font-weight:700}
code{background:#0d0d10;padding:1px 6px;border-radius:4px;font-size:.85em}
.done{color:#6ecf68}.wip{color:#e8920c}.todo{color:#9a9a96}
"""

STATUS_ROWS = [
    ("C", "Paleta → tokeny theme.py", "done", "zrobione"),
    ("B", "Cień pomocy → model questów", "done", "zrobione"),
    ("D", "Kanty zamiast border_radius / linie 1px→2px / UI_BORDER 8", "done",
     "zrobione (wyjątek: pasek sentymentu)"),
    ("E", "Min. font - nazwa postaci 8→10px", "done", "zrobione"),
    ("G", "Skalowanie ikon emoji całkowitą krotnością", "done", "zrobione"),
    ("H", "Pasek sentymentu: pełny, bez ramki, zaokrąglony", "done", "zrobione"),
    ("A", "Komponent klawisza = sprite wszędzie", "wip",
     "pomoc, hotbar, hinty pomocy i questów zrobione; TODO: ręczny art strzałek + "
     "ciemne lico kafli arkusza (Esc/Enter/Shift/Space/Alt)"),
]

COMMITS = [
    ("47027bc", "G+H", "skalowanie emoji, pasek sentymentu, keycapy , . 9"),
    ("81c45c8", "D+E", "kanty zamiast border_radius, nazwa postaci 8→10px"),
    ("fa7dcf7", "A", "placeholderowe strzałki key_up/down/left/right"),
    ("7648a06", "A", "keycapy w pomocy jako sprite'y ÷2 + kontrast lica"),
    ("e6e812d", "A", "keycapy w hintach nawigacji pomocy i questów"),
]


def build(sections: list[tuple]) -> None:
    def section(title, note, tags, before, after):
        t = "".join(f'<span class="tag">{x}</span>' for x in tags)
        return (f'    <section class="card">\n      <h2>{title}</h2>\n'
                f'      <p class="note">{t}<br>{note}</p>\n      <div class="ba">\n'
                f'        <figure><figcaption>PRZED</figcaption>{img(before)}</figure>\n'
                f'        <figure><figcaption>PO</figcaption>{img(after)}</figure>\n'
                f'      </div>\n    </section>\n')

    status = "".join(
        f'<tr><td><b>{c}</b></td><td>{d}</td><td class="{cls}">{s}</td></tr>\n'
        for c, d, cls, s in STATUS_ROWS)
    status_tbl = (f'    <section class="card">\n      <h2>Tabela decyzji - status</h2>\n'
                  f'      <table><thead><tr><th>#</th><th>Odstępstwo</th><th>Status</th></tr></thead>\n'
                  f'      <tbody>\n{status}      </tbody></table>\n    </section>\n')

    commits = "".join(f'<tr><td><code>{h}</code></td><td>{g}</td><td>{m}</td></tr>\n'
                      for h, g, m in COMMITS)
    commits_tbl = (f'    <section class="card">\n      <h2>Commity (branch docs/design-system-ui)</h2>\n'
                   f'      <table><thead><tr><th>hash</th><th>grupa</th><th>opis</th></tr></thead>\n'
                   f'      <tbody>\n{commits}      </tbody></table>\n    </section>\n')

    all_tags = "".join(f'<span class="tag">{t}</span>' for t in
                       ["C paleta", "B cień", "D kanty", "E font", "G emoji", "H sentyment", "A keycapy"])
    body = "".join(section(*s) for s in sections)
    html = (f'<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>Design System - postępy (before/after)</title>\n'
            f'<style>{STYLE}</style></head><body><div class="wrap">\n'
            f'<h1>Design System UI - postępy (before / after)</h1>\n'
            f'<p class="lead">{all_tags}<br>Log zmian design-systemu MoM. PRZED = stan sprzed prac '
            f'(audyt 2026-07-18), PO = stan bieżący. Audyt z tabelą decyzji i paletą: '
            f'<code>design-system-2026-07-18.html</code>; zasady: <code>project/ui/AGENTS.md</code>. '
            f'Regeneracja: <code>python scripts/gen_design_system_progress.py</code>.</p>\n'
            f'{status_tbl}{body}{commits_tbl}</div></body></html>')
    OUT.write_text(html, encoding="utf-8")
    print(f"zapisano {OUT} ({len(html)} znaków, {html.count('<img ')} obrazów)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-capture", action="store_true",
                    help="pomiń przechwytywanie; użyj ostatnich zrzutów progress_after_*")
    args = ap.parse_args()

    SCRATCH.mkdir(parents=True, exist_ok=True)
    if not args.no_capture:
        print("== przechwytywanie ekranów (headless) ==")
        capture()

    after = {lbl: latest(lbl) for lbl in ("main_menu", "gameplay", "quest", "help", "dialog")}

    # rendery syntetyczne + zbliżenia
    render_sentiment(False, SCRATCH / "sentiment_before.png")
    render_sentiment(True, SCRATCH / "sentiment_after.png")
    crop_hotbar(after["gameplay"], SCRATCH / "keycap_after.png")

    sections = [
        ("Menu główne",
         "Kontrola refaktora palety - ma wyglądać identycznie (kolory do tokenów theme.py).",
         ["C paleta"], BEFORE / "01_main_menu.png", after["main_menu"]),
        ("Rozgrywka + HUD",
         "UI_BORDER_WIDTH 9→8. Keycapy hotbara i przycisków akcji: jasne lico → ciemne "
         "(kontrast białego glifu). Ikony emoji na toastach tylko całkowitą krotnością.",
         ["D border 9→8", "A keycapy", "G emoji"], BEFORE / "02_gameplay.png", after["gameplay"]),
        ("Keycapy - zbliżenie hotbara",
         "Ten sam komponent klawisza wszędzie. Lico pustego key przyciemnione mnożnikiem "
         "(75,82,105); biały glif (1-6, ‹ ›) czytelny. Ręczne kafle arkusza - Aseprite.",
         ["A keycapy", "kontrast"], BEFORE / "06_keycap_hotbar.png", SCRATCH / "keycap_after.png"),
        ("Dziennik zadań (J)",
         "Znacznik locked ○ i chip nagrody 1px→2px. Usunięcie border_radius z pasków postępu "
         "i chipa (kanty). Stopka: hinty nawigacji jako keycapy zamiast tekstu. Paleta z tokenów.",
         ["D kanty", "A keycapy", "C paleta"], BEFORE / "03_quest.png", after["quest"]),
        ("Panel pomocy (H)",
         "Cień tylko na chromie (model questów). Rysowane chipy/trójkąty → sprite'y hotbara ÷2 do "
         "16px (jednoznakowe = świeży glif, reszta = art). Nagłówek: hint zamknięcia jako keycapy. "
         "Lico klawisza przyciemnione dla kontrastu.",
         ["B cień", "A keycapy", "kontrast"], BEFORE / "04_help.png", after["help"]),
        ("Dialog z NPC",
         "Pasek sentymentu nad nazwą: pełny/bez ramki/zaokrąglony (było: ramka 1px + gradient). "
         "Podświetlenie opcji: kanty zamiast border_radius. Keycapy przycisków akcji ciemne. "
         "Emote sentymentu skalowane ×2.",
         ["H sentyment", "D kanty", "A keycapy", "G emoji"], BEFORE / "05_dialog.png", after["dialog"]),
        ("Pasek sentymentu - zbliżenie (render z kodu)",
         "PRZED: zaokrąglony prostokąt z ramką 1px (żółtą) + gradient - 1px zdradza udawany "
         "pixel-art. PO: pełny pasek, bez ramki, zaokrąglony po bokach (decyzja usera).",
         ["H sentyment", "D kanty"], SCRATCH / "sentiment_before.png", SCRATCH / "sentiment_after.png"),
    ]
    build(sections)


if __name__ == "__main__":
    main()
