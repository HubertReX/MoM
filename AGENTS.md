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

## 🔑 CodeGraph: use MCP tool before grep

**Before any grep/find/read for code questions: USE `codegraph_codegraph_explore` FIRST.** It returns verbatim source + call paths in one call. grep misses dynamic dispatch and costs more tokens.

## 🔑 Złota zasada: pixel-perfect rendering (natywny 1:1, więcej kafelków)

Gra **musi renderować się pixel-perfect** i **nigdy nie skaluje** obrazu na ekran.
Wyższa rozdzielczość = **większy viewport = więcej kafelków**, nie powiększony obraz.
Kafelek i postać mają zawsze ten sam rozmiar w pikselach (`TILE_SIZE = 16` natywnie).

- Rozdzielczość logiczna == fizyczna: `settings.WIDTH`/`HEIGHT` **podążają** za wybraną
  opcją (`DISPLAY_RES_OPTIONS`, w kafelkach), a `settings.SCALE == 1.0` zawsze
  (`settings.py` `_calc_resolution`). Canvas tworzony jest w rozmiarze okna, a finalny
  blit to zwykłe 1:1 (`self.screen.blit(self.canvas, (0, 0))` w `game.py:render()`).
  Zero `transform.scale`/`smoothscale` na pełnym canvasie, zero letterboxa.
- **NIE importuj `WIDTH`/`HEIGHT`/`WIDTH_SCALED`/`HEIGHT_SCALED` po nazwie**
  (`from settings import WIDTH`) — te wartości zmieniają się w runtime przy zmianie
  rozdzielczości, a import łapie je raz przy starcie (stąd rozjazdy centrowania UI).
  Zawsze czytaj dynamicznie: `import settings` → `settings.WIDTH`. Domyślne argumenty
  z `WIDTH`/`HEIGHT` też są zakazane (liczone raz przy definicji) — użyj `None` i licz
  w środku (wzorzec: `main_menu.py`, `display_settings.py`, `help.py::_recompute_geometry`).
- Świat (pyscroll) sam bierze rozmiar viewportu z `canvas.get_size()` — rośnie automatem.
  UI/HUD/panele muszą kotwiczyć się do `settings.WIDTH`/`HEIGHT` (krawędzie/środek), żeby
  rozciągały się na cały viewport.

## Co gdzie jest

| Katalog              | Zawartość                                                | Edytować?                                                                     |
| -------------------- | -------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `project/`           | Rdzeń kodu gry (source)                                  | ✅ tak — patrz [`project/AGENTS.md`](./project/AGENTS.md)                     |
| `art/`               | Assety menu + pomocnicze grafiki NinjaAdventure          | ✅ ostrożnie                                                                  |
| `doc/`               | Scenariusz intro (cutscene, odpalany **F4**)             | ✅                                                                            |
| `.github/workflows/` | CI: `pygbag.yml` (GitHub Pages), `itch_io.yml` (itch.io) | ✅ ostrożnie                                                                  |
| `tests`              | Zestawy scenariuszy testów automatycznych                | ✅ tak - patrz [`project/AGENTS.md`](./project/AGENTS.md)                     |
| `Tasks`              | Zadania dla Ciebie do wykonania                          | ✅ tak, ale zgodnie ze ściśle określonymi zasadami                            |
| `utils/`             | Śmietnik skryptów/eksperymentów                          | ⛔ **pomijać**                                                                |
| `references/`        | Screenshoty z innych gier (referencje)                   | ⛔ **pomijać**                                                                |
| `screenshots/`       | Migawki z rozwoju gry                                    | ⛔ **pomijać**                                                                |
| `.venv/`             | Wirtualne środowisko                                     | ⛔ **pomijać**                                                                |

## Uruchamianie i build

```bash
just run          # desktop
just serve-web    # web lokalnie → http://localhost:8000 (REPL debug: http://localhost:8000#debug)
just build-itchio # build paczki web.zip dla itch.io
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

## Testy wizualne i save/load - szybki start dla agenta

Testowanie przez agenta AI: `tests/scenarios.json` + `tests/automate_display_test.py` (runner)
+ `project/agent_ctrl.py` (interpreter komend w grze). Główny sposób weryfikacji UI i save/load.

```bash
# Pojedynczy scenariusz - ZAWSZE uruchamiaj tak do weryfikacji:
MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python3 tests/automate_display_test.py "Save and Load Basic"

# Z wizualną weryfikacją screenshotów (wymaga modelu z vision):
MOM_SS_REVIEW_MODEL='google/gemini-3.1-flash-lite' MOM_AGENT_CONTROL=1 \
  SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  .venv/bin/python3 tests/automate_display_test.py "TextInput Demo Hotkey"

# Pomiń ss-review (szybka iteracja):
MOM_SKIP_SS_REVIEW=1 MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  .venv/bin/python3 tests/automate_display_test.py
```

**Pełny protokół, komendy agenta, struktura scenariuszy, izolacja, ścieżki save'ów,
znane ograniczenia:** [`project/AGENTS.md`](./project/AGENTS.md) - sekcja „Testowanie gry przez agentów AI".

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
- [`project/dialog/AGENTS.md`](./project/dialog/AGENTS.md) — system dialogów (graf, warunki DSL, adaptery, przepływ)
- [`project/shaders/AGENTS.md`](./project/shaders/AGENTS.md) — shadery OpenGL/WebGL
