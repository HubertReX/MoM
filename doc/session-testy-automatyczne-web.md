# Testy automatyczne web

**Session ID:** ses_0e1678ce7ffeQmvX3lNirVmLBm
**Created:** 7/1/2026, 6:52:15 PM
**Updated:** 7/3/2026, 6:39:26 PM

---

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

