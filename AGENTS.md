# AGENTS.md — Misadventures of Malachi (root)

Top-down RPG w **Pygame-CE** (~11.9K LOC własnego kodu), na etapie tech-demo: gotowe
mechaniki (NPC AI + A*, inventory, dialogi, cutscene, proceduralne labirynty, cykl
dzień/noc), brak fabuły i pełnej mapy świata. Pełna lista feature'ów: [`README.md`](./README.md).

## 🔑 Złota zasada: dual-target desktop + web

Gra działa **zarówno na desktopie, jak i w przeglądarce** (pygbag/WASM).
**Każda zmiana musi działać w obu trybach.** Wykrywanie środowiska:

```python
# project/settings.py:84
IS_WEB = __import__("sys").platform == "emscripten" or USE_WEB_SIMULATOR
```

Web ma ograniczenia wydajności i runtime'u (m.in. brak Pydantic, wyłączone shadery/filtr
dzień-noc). Szczegóły rozgałęzień: [`project/AGENTS.md`](./project/AGENTS.md).

## Co gdzie jest

| Katalog | Zawartość | Edytować? |
|---|---|---|
| `project/` | Rdzeń kodu gry (source) | ✅ tak — patrz [`project/AGENTS.md`](./project/AGENTS.md) |
| `art/` | Assety menu + pomocnicze grafiki NinjaAdventure | ✅ ostrożnie |
| `doc/` | Scenariusz intro (cutscene, odpalany **F4**) | ✅ |
| `.github/workflows/` | CI: `pygbag.yml` (GitHub Pages), `itch_io.yml` (itch.io) | ✅ ostrożnie |
| `tests` | Zestawy scenariuszy testów automatycznych | ✅ tak - patrz sekcja
„Testowanie gry przez agentów AI" w [`project/AGENTS.md`](./project/AGENTS.md) |
| `Tasks` | Zadania dla Ciebie do wykonania | ✅ tak, ale zgodnie ze ściśle określonymi zasadami |
| `utils/` | Śmietnik skryptów/eksperymentów | ⛔ **pomijać** |
| `references/` | Screenshoty z innych gier (referencje) | ⛔ **pomijać** |
| `screenshots/` | Migawki z rozwoju gry | ⛔ **pomijać** |
| `.venv/` | Wirtualne środowisko | ⛔ **pomijać** |

## Uruchamianie i build

```bash
./run.sh          # desktop
./serve_web.sh    # web lokalnie → http://localhost:8000 (REPL debug: http://localhost:8000#debug)
./build_itchio.sh # build paczki web.zip dla itch.io
```

CI: ręczne `workflow_dispatch` → GitHub Pages (`pygbag.yml`) oraz itch.io (`itch_io.yml`).

## Środowisko deweloperskie

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

`pyproject.toml`: isort (py3.11, line 80), mypy (py3.12, `disallow_untyped_defs=true`,
wyklucza `utils`/`pygame_menu`). **Type hints są wymagane** w nowym kodzie.

## Tablica zadań — MOAB

Zarządzanie zadaniami (człowiek ↔ agenci) odbywa się przez **MOAB**
(Markdown Obsidian Agent Board) — osobny projekt: `~/Projects/moab`
([HubertReX/moab](https://github.com/HubertReX/moab)) dodany do katalogu `Tasks`.
Pełny protokół i opis: `Tasks/AGENTS.md`.

## Praca z agentami AI

Po zakończeniu realizacji zadania, aktualizuj pliki `AGENTS.md`. Zapytaj czy zrobić commit - oferuj to
często, aby móc wrócić do poprzedniej wersji w razie zepsucia czegoś.

Dłuższe analizy/zadania **deleguj do podagentów**, dzieląc zakres na
mniejsze części. Nie analizuj katalogów oznaczonych ⛔.

**Uruchamianie i testowanie gry przez agenta:** Szczegóły: sekcja
„Testowanie gry przez agentów AI" w [`project/AGENTS.md`](./project/AGENTS.md).

## Zagnieżdżone AGENTS.md

- [`project/AGENTS.md`](./project/AGENTS.md) — silnik, pętla gry, FSM, desktop↔web
- [`project/config_model/AGENTS.md`](./project/config_model/AGENTS.md) — konfiguracja
- [`project/maze_generator/AGENTS.md`](./project/maze_generator/AGENTS.md) — labirynty
- [`project/assets/AGENTS.md`](./project/assets/AGENTS.md) — assety i lokalizacja
- [`project/shaders/AGENTS.md`](./project/shaders/AGENTS.md) — shadery OpenGL/WebGL
