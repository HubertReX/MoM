# Testy automatyczne web

**Session ID:** ses_0e1678ce7ffeQmvX3lNirVmLBm
**Created:** 7/1/2026, 6:52:15 PM
**Updated:** 7/3/2026, 6:39:26 PM


## User:

Ta gra działa jednocześnie w trybie desktop i przez web. Sprawdź, czy obecny mechanizm testów automatycznych przez Agentów AI obsługuje również tryb web? Czy poprawnie generowane są screenshoty, czy obecny zestaw scenariuszy testowych działa również dla trybu web?
Zbadam ten problem. Przejrzę kod testowy i infrastrukturę z obu trybów.

Odpowiedź: Tryb web NIE jest obsługiwany przez obecny mechanizm testów automatycznych
Krótko: Cały harness scenariuszowy jest desktop-only. Żaden test nie jest uruchamiany w trybie web, screenshoty z weba nie są możliwe do pobrania przez runner, a sam agent control jest w trybie web jawne wyłączony.

## Dowody (file:line)

1. Runner jest desktop-only, brak ścieżki web

tests/automate_display_test.py:17 — polecenie startu gry to dosłownie SDL_VIDEODRIVER=dummy ... .venv/bin/python3 project/main.py. Brak jakiejkolwiek gałęzi emscripten/pygbag/--web.
automate_display_test.py:143-145 — start przez subprocess.Popen + os.setsid (POSIX), co w WASM/przeglądarce w ogóle nie istnieje.
Komendy są dostarczane przez echo "CMD" > agent_input.txt (automate_display_test.py:77-78) — w przeglądarce WASM nie ma dostępnego host-filesystemu, więc ten kanał jest martwy.
2. Agent control jest w trybie web wyłączony na sztywno

project/game.py:210 — if USE_AGENT_CONTROL and not IS_WEB: → IS_WEB=True ⇒ self.agent_ctrl zostaje None. Hooki apply/capture (game.py:988-989) to no-opy.
project/agent_ctrl.py:14-15 — docstring potwierdza: „Tryb wyłącznie desktop (operacje na plikach) i opt-in". poll() (agent_ctrl.py:107-113) otwiera plik dyskowy; capture() (agent_ctrl.py:225-227) robi pygame.image.save(surface, path) na dysk.
3. Screenshoty w trybie web nie trafiają do runnera

Mechanizm w grze (game.py:575-596): w web robie platform.window.download_from_browser_fs(...) — screenshot idzie jako pobranie przeglądarki, nie plik możliwy do wczytania przez proces testowy.
Mechanizm agentowy (agent_ctrl.py:217-231): pygame.image.save na dysk — nieosiągalny w web bo agent_ctrl jest gated off (patrz pkt 2), a zresztą SDL w emscripten renderuje na canvas, nie działa SDL_VIDEODRIVER=dummy.
4. Scenariusze nie są web-aware

tests/scenarios.json: 9 scenariuszy. Żaden nie ma pola platform/web/target/mode (schema parsera w automate_display_test.py:164-184 czyta tylko name, actions, assertions, cleanup_saves).
Każdy scenariusz z quick_save/quick_load/debug_map_change i assertions.file_exists opiera się na FileSaveBackend (host FS). Web build używa LocalStorageSaveBackend (project/save_load/backends.py:92-126), więc te assercje nie mają sensu w web.
5. Save helper jest desktop-only

tests/test_save_load_corrupt.py:24-32 — _get_save_dir() zna tylko ~/Library/Application Support/mom/saves, ~/.local/share/mom/saves, AppData\Local\mom\saves. Brak obsługi window.localStorage.
6. Brak automatyzacji przeglądarki

Przeszukanie repo (poza .venv//utils/): zero selenium|playwright|puppeteer|MCP server. Żadnego tests/test_web*.py, żadnego conftest.py, żadnego mcp.json.
7. Build/web skrypty bez testów

serve_web.sh i build_itchio.sh — tylko uruchamiają pygbag, bez --test i bez jakiegokolwiek hooka integrującego tests/.
CI (.github/workflows/pygbag.yml, itch_io.yml) — tylko build. W project/AGENTS.md:73 jedyną wskazówką dla web jest ręczne uruchomienie ./serve_web.sh (weryfikacja manualna).
Co trzeba by dodać, by web test zadziałał
Kanał komend dla web — Playwright (Python) sterujący serve_web.sh, tłumaczący TestAction.commands na page.keyboard.press(...) (zamiast echo do pliku) + zdjęcie blokady not IS_WEB w game.py:210 albo dedykowany branch w AgentController.poll() (agent_ctrl.py:105-116) czytający z localStorage/kolejki JS.
Screenshot z web — page.screenshot() Playwright (najprościej), lub wystawienie game.py:575-596 na bocznym kanale zamiast download_from_browser_fs.
Save assertion web — nowy typ localStorage_exists ewaluowany przez page.evaluate(...) na kluczach save_<N>; corrupt helper piszący złe dane do localStorage zamiast na dysk.
Schema scenariuszy — pole platform/target (lub osobny tests/scenarios_web.json), żeby scenariusze zależne od FileSaveBackend nie leciały ślepo na web.
Runner — WebRunner (uruchamia serve_web.sh + kontekst Playwright) zamiast TestRunner.start_game (automate_display_test.py:139-147).
CI — job serwujący zbudowaną stronę i odpalający suite Playwright, z artifactem screenshots/agent/.
Zgłoszenie vedette (opcjonalne)
project/AGENTS.md:60,76,79 podaje settings.py:84/83/92, ale realna definicja IS_WEBjest teraz w settings.py:130-131 — numery wierszy w AGENTS.md są nieaktualne.


## Assistant (Build · Big Pickle · 173.7s)

**Co udało się zrobić:**

| Komponent | Status |
|---|---|
| `project/agent_ctrl.py` | Dodany `web_mode` z localStorage backend (`_poll_localstorage`) + screenshot no-op w web |
| `project/game.py:210` | Rozpięty AgentController w web mode przez `MoM.agent_control` flag w localStorage |
| `tests/automate_display_test.py` | **Zrefaktorowany** — `RunnerBase` → `DesktopRunner` + `WebRunner` (Playwright). Flaga `--web` |
| `tests/scenarios.json` | Dodane pole `platform` i `setup_saves` (Corrupt Save) |
| `tests/test_save_load_corrupt.py` | `minimal_save_dict`/`corrupt_save_text` publiczne — współdzielone z WebRunner |
| `requirements-dev.txt` | Dodany `playwright>=1.50` |
| `project/AGENTS.md` | Dodana sekcja "Web (pygbag + Playwright)" + poprawione numery linii `settings.py` |
| `AGENTS.md` (root) | Skrócony duplikat test info, odsyła do `project/AGENTS.md` |

**Zweryfikowane działanie:**
- Desktop regression: `Empty Slot Load` → OK (screenshoty 2x, pełny przebieg)
- Web mode: `Empty Slot Load` → OK (16.6s init, screenshots 31KB/38KB z realnego canvas)
- Web mode save scenario: `Save and Load Basic` → OK (5 screenshotów, quick_save/quick_load)
- Web mode z asercjami: `Multiple Quick Saves` → **Assertions passed** (file_exists → localStorage tlumaczenie dziala)

**Co zostało do zrobienia** (w przyszłej sesji):

## Assistant (Build · Big Pickle · 8.3s)

Commit `dd0a2f2` gotowy. Oto **podsumowanie**:

## ✅ Zrobione (commit `dd0a2f2`)

| Plik | Zmiana |
|---|---|
| `project/agent_ctrl.py` | `web_mode` + localStorage polling (`_poll_localstorage`), screenshot no-op w web |
| `project/game.py:210` | AgentController włączany przez `localStorage['MoM.agent_control']` w web |
| `tests/automate_display_test.py` | **Totalny refaktor**: `RunnerBase` → `DesktopRunner` + `WebRunner` (Playwright). Flaga `--web` |
| `tests/scenarios.json` | Pole `platform` + `setup_saves` (dla Corrupt Save) |
| `tests/test_save_load_corrupt.py` | `minimal_save_dict()`/`corrupt_save_text()` publiczne |
| `requirements-dev.txt` | `playwright>=1.50` |
| `project/AGENTS.md` | Sekcja "Web (pygbag + Playwright)" + fixy numerów linii `settings.py:84→130` itd. |
| `AGENTS.md` (root) | Skrócony duplikat |

## 🔜 Do dokończenia (sesja wznowiona)

1. **CI workflow dla Playwright** — `.github/workflows/` z jobem: `pygbag build` → `playwright install chromium` → `automate_display_test.py --web`
2. **Corrupt Save Handling w web** — scenario `setup_saves` jest zaimplementowane (wstrzykiwanie przez `page.evaluate()`), ale jeszcze nie przetestowane end-to-end
3. **Lepsze assertion type** — obecny jest regex `file_exists` → localStorage; dodać explicit `localstorage_exists` w scenarios.json
4. **Ograniczenie timeoutów** — Dłuższy `INIT_WAIT_WEB` / możliwość konfiguracji przez CLI `--timeout`

## Jak kontynuować

```bash
# desktop regression
MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python3 tests/automate_display_test.py

# web test
.venv/bin/python3 tests/automate_display_test.py --web

# pojedynczy scenariusz
.venv/bin/python3 tests/automate_display_test.py --web "Save and Load Basic"
```

---

## Assistant (Build · Big Pickle · 2026-07-08) — Fix ss-review

**Co zrobiono** (commit `d50c801`):

| Komponent | Zmiana |
|---|---|
| `tests/automate_display_test.py` | `-f` → inline path w prompcie; `--pure` zamiast pluginów; `gtimeout` hard kill; `SS_REVIEW_TIMEOUT` 150→60s; `SS_REVIEW_MODELS` jawny `opencode-go/mimo-v2.5` zamiast `None` |
| `ss-rev.sh` | Przyjmuje `$1` (ścieżka) + `$2` (expected state); dokumentacja inline path vs `-f` |
| `AGENTS.md` (root) | Dodane przykłady z `MOM_SS_REVIEW_MODEL` i `MOM_SKIP_SS_REVIEW` |
| `project/AGENTS.md` | Nowa sekcja "ss-review (wizualna analiza screenshotów)" |

**Ustalenia:**
- `--plain` nie istnieje w OC 1.17.10; poprawna flaga to `--pure` (wyłącza pluginy, w tym discover-models.js)
- `opencode-go/mimo-v2.5` ma vision i działa jako tani model do ss-review
- `-f` wymaga modelu z `attachment: true` + `modalities.input: ["text","image"]` — bez tego error
- `gtimeout` (GNU coreutils) dostępny na macOS przez Homebrew; fallback do `timeout` na Linux

**Przykłady:**
```bash
# Test z domyślnym modelem (mimo-v2.5)
MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  .venv/bin/python3 tests/automate_display_test.py "TextInput Demo Hotkey"

# Z wymuszonym modelem Gemini
MOM_SS_REVIEW_MODEL='google/gemini-3.1-flash-lite' MOM_AGENT_CONTROL=1 \
  SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  .venv/bin/python3 tests/automate_display_test.py "Display Settings Flow"

# Pomiń ss-review (szybka iteracja)
MOM_SKIP_SS_REVIEW=1 MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  .venv/bin/python3 tests/automate_display_test.py

# Ręczna analiza screenshotu
./ss-rev.sh screenshots/agent/agent_20260708_151153_textinput_demo_hotkey_01_at_main_menu.png MENU_MAIN
```

