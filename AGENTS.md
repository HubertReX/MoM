# AGENTS.md — Misadventures of Malachi (root)

Top-down RPG w **Pygame-CE** (~26K LOC własnego kodu; aktualnie:
`find project -name "*.py" -not -path "*/animation/*" | xargs wc -l | tail -1`).
Mechaniki gotowe (NPC AI + A*, rutyny dobowe, inventory, dialogi, questy, save/load,
cutscene, proceduralne labirynty, cykl dzień/noc); fabuła spisana (`doc/PL/fabuła.md`),
**prolog (Akt 1) w budowie** - 8 questów i 6 grafów dialogowych. Pełna lista
feature'ów: [`README.md`](./README.md).

## 🔑 Złota zasada: dual-target desktop + web

Gra działa **zarówno na desktopie, jak i w przeglądarce** (pygbag/WASM).
**Każda zmiana musi działać w obu trybach.** Wykrywanie środowiska:

```python
# project/settings.py
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
| `scripts/`           | Skrypty narzędziowe repo (walidatory, generatory, fixtures, szablon pygbag) | ✅ tak — tu trafia każdy skrypt, od którego coś zależy       |
| `utils/`             | Śmietnik skryptów/eksperymentów                          | ⛔ **pomijać** — patrz uwaga niżej                                            |
| `references/`        | Screenshoty z innych gier (referencje)                   | ⛔ **pomijać**                                                                |
| `screenshots/`       | Migawki z rozwoju gry                                    | ⛔ **pomijać**                                                                |
| `.venv/`             | Wirtualne środowisko                                     | ⛔ **pomijać**                                                                |

> **`utils/` to piaskownica i nic produkcyjnego nie może z niej korzystać.** Szablon
> pygbag (`scripts/pygbag/black.tmpl`) oraz narzędzia PNG (`scripts/find_bad_png.py`,
> `scripts/fix_bad_png.py`) mieszkały tam wcześniej i zostały przeniesione do `scripts/`
> — jeśli piszesz recepturę `just`, workflow CI albo test, który czegoś potrzebuje,
> **to coś ma leżeć w `scripts/`**, nie w `utils/`. Sama piaskownica zostaje nietknięta.
> `utils/`, `screenshots/` i `references/` są wyłączone z indeksu CodeGraph przez
> `codegraph.json` (`exclude`), żeby eksploracja kodu nie zwracała szumu.

## Uruchamianie i build

```bash
just run          # desktop
just serve-web    # web lokalnie → http://localhost:8000 (REPL debug: http://localhost:8000#debug)
just build-itchio # build paczki web.zip dla itch.io
```

CI: ręczne `workflow_dispatch` → GitHub Pages (`pygbag.yml`) oraz itch.io (`itch_io.yml`).

### Walidacja spójności świata

```bash
just validate-world            # tabela naruszeń + podsumowanie, exit 1 przy ERROR
just validate-world --strict   # ostrzeżenia też failują
just validate-world --json     # wynik maszynowo
```

Klucze encji żyją w kilku przestrzeniach nazw (config.json, characters.csv, mapy Tiled,
routines.toml, sprite'y), a nic ich ze sobą nie wiąże. `scripts/validate_world.py`
sprawdza je krzyżowo: spawn pointy vs `config.characters`, `home/work/social/hobby` vs
warstwa `places`, rutyny vs `routines.toml`, kroki rutyn vs `places`/`waypoints`, sprite'y
vs katalogi assetów, przedmioty (ekwipunki, skrzynie, nagrody questów, warunki
`has_item()`) vs `config.items`, `dialog_key` vs `config.dialogs`, a także `audio.toml`
(pliki ogg, klucze map, eventy SFX w obie strony - patrz `project/AGENTS.md`, sekcja
„Audio").

Walidator **tylko diagnozuje** - nigdy nie edytuje źródeł. Nie importuje pygame ani modułów
gry (surowe JSON/CSV/TOML/XML), więc chodzi na czystym interpreterze i w CI, w ~0,05 s.
Jest w agregacie `just check` oraz na końcu `import-entities` i `import-quests`
(`import-dialogs` dziedziczy przez kaskadę) - błąd spójności ma wychodzić przy edycji
treści, nie w runtime jako cichy `print` albo brakujący NPC.

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

## Testy jednostkowe - szybki start dla agenta

**Nie używamy pytesta** (nie ma go w zależnościach). Każdy `tests/test_*.py` to samodzielny
skrypt: `main()` woła ręcznie utrzymywaną listę `tests = [...]` i wychodzi z kodem != 0 przy
błędzie. Runner `scripts/run_unit_tests.py` odpala wszystkie pliki i **pilnuje, żeby każdy
zdefiniowany `test_*` był na tej liście** - inaczej test nigdy by się nie wykonał, a plik i tak
zwróciłby 0.

```bash
just test-unit                # wszystko (30+ plików, 400+ testów - dokładną liczbę wypisuje sam)
just test-unit save_load      # tylko pliki z "save_load" w nazwie
just test-unit quest -v       # z pełnym outputem każdego pliku
```

Dodając nowy test, **dopisz go do listy `tests = [...]`** w swoim pliku - `just test-unit`
zgłosi to jako `WARN` i zwróci 1, jeśli o tym zapomnisz.

## Testy wizualne i save/load - szybki start dla agenta

Testowanie przez agenta AI: `tests/scenarios.json` + `tests/automate_display_test.py` (runner)
+ `project/agent_ctrl.py` (interpreter komend w grze). Główny sposób weryfikacji UI i save/load.
Skrót: `just test-agent "<scenariusz>"` (desktop), `just test-web "<scenariusz>"` (web).

Trzy poziomy bramki - wybieraj najtańszą, która pokrywa zmianę:

| Komenda | Zakres | Czas |
|---|---|---|
| `just test-agent "<nazwa>"` | jeden scenariusz | ~30-60 s |
| `just test-smoke` | zestaw smoke: 6 scenariuszy z rozłącznych obszarów (save/load, dialog, labirynt, panele UI, ustawienia, text input) - lista w `TEST_CONFIG["SMOKE_SCENARIOS"]` | ~4-5 min |
| `just test-agent` / `just test-web` | wszystko na danym backendzie | ~18 / ~10 min |

`just test-web` trzyma **jeden serwer pygbag i jedną przeglądarkę na cały przebieg** -
scenariusz startuje przez reload strony (build WASM jest w przebiegu identyczny).
Gdy podejrzewasz przeciekanie stanu między scenariuszami, odpal
`just test-web --web-restart-per-scenario` (zachowanie sprzed A08).

**Runner jest singletonem - jeden przebieg naraz.** Wszystkie tryby dzielą
`agent_input.txt`, `agent_status.txt` i `screenshots/agent/`, a web dodatkowo port 8001,
więc dwa równoległe przebiegi nie failują głośno - mieszają sobie wejście i zrzuty,
a wyniki są nieważne. Runner pilnuje tego sam: blokada PID
(`$TMPDIR/mom-automate-display-test.pid`) + kontrola portu, oba sprawdzane **przed**
buildem, z komunikatem, co ubić. Zasady dla agenta:

- każde uruchomienie kieruj do **własnego pliku loga** - `>` na plik, do którego pisze
  żywy przebieg, obcina go i przebieg wygląda na martwy (urwany log ≠ martwy proces:
  najpierw `pgrep -f automate_display_test`, potem diagnoza),
- po przerwanym przebiegu:
  `pkill -f tests/automate_display_test.py` → `pkill -f "m pygbag"` →
  `pkill -f chromium_headless_shell` (`SIGTERM` jest obsłużony i runner sprząta sam;
  `kill -9` zostawia sieroty), potem sprawdź `lsof -ti :8001`.

Runner odpala grę z `XDG_DATA_HOME` przestawionym na `.test-data/` w repo, więc scenariusze
**nie ruszają prawdziwych zapisów ani `settings.json`**. Dotyczy to też wywołania wprost
(`python tests/automate_display_test.py`), nie tylko przez `just`.

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

## 🔑 Złota zasada: jak pisać teksty w tym repo

Dwie rzeczy obowiązują **wszędzie**: w plikach `.md`, w komentarzach w kodzie, w docstringach, w komunikatach dla gracza, w opisach commitów i w treści w Obsidianie.

- **Nie łam akapitów twardym enterem.** Akapit (albo punkt listy) to **jedna linia**, choćby miała 400 znaków — zawijanie jest sprawą czytnika, nie pliku. Autor czyta te pliki w kilku programach o różnej szerokości i każdy zawija po swojemu, a sztywne łamanie po ~80 znakach oznacza, że poprawka jednego słowa wymusza przelanie całego akapitu (i produkuje diff, w którym nie widać, co się naprawdę zmieniło). Łamiemy linię tylko tam, gdzie łamie ją Markdown: między akapitami, punktami listy, wierszami tabeli, liniami bloku kodu. Przykład **jak nie robić**: `doc/audyt/H03-sidequesty-i-klatwa.md`.
- **Polski tekst piszemy z polskimi znakami.** `ą ć ę ł ń ó ś ź ż` — zawsze, bez wyjątków dla komentarzy w kodzie i plików konfiguracyjnych. Wszystko w tym projekcie jest w UTF-8 i każdy system to poprawnie wyświetla; „uproszczony" zapis bez ogonków jest błędem ortograficznym, który autor musi po agencie poprawiać, a edytory podkreślają go jako literówki. Przykład **jak nie robić**: `project/config_model/routines.toml` sprzed poprawki autora.
- **Tabele Markdown justujemy spacjami.** Obsidian sam wyrównuje tabelę w chwili otwarcia notatki, więc tabela zapisana „na wąsko" zmienia się od samego zajrzenia do pliku i ląduje w `git diff` — a w notatkach generowanych (`doc/quest-cheatsheet.md`) wygląda to jak ręczna edycja pliku, którego ręcznie edytować nie wolno. Ręcznie pisane pliki formatuj skillem `md-table-format`, a generatory niech budują tabelę przez `scripts/md_tables.py`.
- **Nie zaczynaj bloku w backquote'ach od znaku równości.** Dataview czyta taką zawartość jako **inline query** i zamiast tekstu wypisuje w notatce błąd parsera (zapis równości wpisany wprost zabił tak sekcję „Porównania" w ściągawce questów). Wstaw spację po otwierającym backquote: ` ==`.

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
