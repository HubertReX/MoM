# A08 - web-runner: jeden serwer pygbag na przebieg + `just test-smoke`

Priorytet: **P1** (Faza 2, robić w trakcie B01 - wprost obniża koszt bramek).
Rozmiar: M. Zależności: A07 (jeden kanał `MoM.env`) - zrealizowane.

## Kontekst i problem

Bramki testowe w B01 są drogie czasowo, więc realnie odpalane rzadziej niż plan
zakłada (decyzja autora 2026-07-25: pełne zestawy tylko po wybranych krokach).
Dwa konkretne powody:

1. **Web-runner restartuje pygbag dla KAŻDEGO scenariusza.** `run_scenarios()`
   (`tests/automate_display_test.py:1181`) woła `runner.cleanup()` w `finally` po
   każdym scenariuszu, a `WebRunner.cleanup()` (:1109) zamyka stronę, przeglądarkę
   **i zabija proces pygbag** (`os.killpg`). Kolejny scenariusz w `start_game()`
   (:896) startuje pygbag od zera: build WASM + serve (`PYGBAG_BOOT_TIMEOUT` 90 s),
   nowy Chromium, `goto`, wstrzyknięcie env, `reload`, `INIT_WAIT_WEB` 12 s.
   Build jest za każdym razem identyczny - kod nie zmienia się w trakcie przebiegu.
   Efekt: pełny `just test-web` (~24 scenariusze web) trwa **~25 min**.

   Per scenariusz naprawdę potrzebne jest tylko: wyczyszczenie kluczy w
   `localStorage` (save sloty, `MoM.input`, ui-state), wstrzyknięcie `MoM.env`
   (z `start_hour` bieżącego scenariusza), ewentualne `setup_saves` i `reload`
   strony (reload = świeży interpreter Pythona w świeżej instancji WASM).

   Uboczny objaw tego samego problemu: `WebRunner.cleanup_saves_before()` (:1071)
   ma komentarz "wykonujemy pomiędzy scenariuszami, gdy pygbag jest jeszcze aktywny
   z poprzedniego", ale `self.page` jest wtedy zawsze `None` (bo `cleanup()` je
   zamknął), więc ta gałąź **nigdy się nie wykonuje** - czyszczenie działa tylko
   przypadkiem, przez ścieżkę w `start_game()`.

2. **Nie ma szybkiej bramki.** Pełny desktop to ~18 min, a bramka "3 scenariusze
   z nazwy" (`Save and Load Basic`, `Hammer Dialog Flow`) jest za wąska, żeby
   wyłapać regresję w menu/UI/labiryncie. Brakuje pośredniego poziomu: kilka
   scenariuszy pokrywających rozłączne obszary, ~4-5 min.

## Cel

- Pełny `just test-web` startuje pygbag **raz** na przebieg i mieści się w **< 15 min**
  bez utraty izolacji między scenariuszami.
- `just test-smoke` uruchamia 6 wybranych scenariuszy (desktop) w < 5 min i jest
  domyślną bramką "po każdym kroku" zamiast pojedynczych nazw.
- Zachowana furtka do starego zachowania na wypadek podejrzenia zanieczyszczenia
  stanu między scenariuszami.

## Pliki do zmiany

- `tests/automate_display_test.py` - cykl życia runnera (`RunnerBase`,
  `DesktopRunner`, `WebRunner`, `run_scenarios`, `main`), `TEST_CONFIG`
- `justfile` - nowe recipe `test-smoke` (`[unix]` + `[windows]` stub jak przy
  `test-agent`), komentarz przy `test-web`
- `AGENTS.md` - sekcja o testach agentowych (okolice linii 141): dopisz `test-smoke`
  i informację, że web-runner reużywa jednego serwera

## Kroki

1. **Rozdziel cykl życia na sesję i scenariusz.** W `RunnerBase` dodaj trzy metody
   z domyślnym no-op / delegacją:

   ```python
   def start_session(self) -> None: ...   # raz na przebieg (przed pętlą scenariuszy)
   def stop_game(self) -> None: ...       # po każdym scenariuszu
   def end_session(self) -> None: ...     # raz na przebieg (w finally po pętli)
   ```

   `cleanup()` zostaw jako "zamknij wszystko" (`stop_game()` + `end_session()`) -
   jest wołane z `WebRunner.start_game()` w obsłudze błędu startu pygbag (:914).

2. **`run_scenarios()`**: `runner.start_session()` przed pętlą, w pętli w `finally`
   `runner.stop_game()`, a `runner.end_session()` w `finally` obejmującym całą pętlę
   (musi się wykonać także przy `KeyboardInterrupt` - inaczej zostaje żywy pygbag).

3. **`DesktopRunner`**: `stop_game()` = dzisiejsza treść `cleanup()` (killpg procesu
   gry), `start_session()`/`end_session()` = no-op. Zachowanie desktopu **bez zmian**
   (gra i tak musi startować per scenariusz - czyta env przy imporcie `settings`).

4. **`WebRunner`**: przenieś start infrastruktury do `start_session()`:
   pygbag (`Popen` + `_wait_for_pygbag_url`), Playwright, `chromium.launch`,
   `new_page`, listener konsoli, pierwsze `goto(url)`. W `start_game()` zostaw
   wyłącznie per-scenariusz: wyczyszczenie kluczy (`WEB_INPUT_KEY`,
   `WEB_AGENT_FLAG`, ui-state), `MoM.env` z `apply_determinism_env(..., self.start_hour)`,
   `_inject_setup_saves()`, `reload()`, `wait_for_selector("canvas")`, `init_wait`.
   `stop_game()` = no-op (strona zostaje żywa, żeby `cleanup_saves_before()` i
   `clear_ui_state()` miały na czym działać). `end_session()` = zamknięcie strony,
   przeglądarki, `pw.stop()` i killpg pygbag.

5. **Odporność na crash WASM.** Jeśli strona padnie w środku przebiegu, wszystkie
   kolejne scenariusze posypią się kaskadowo. W `start_game()` sprawdź żywotność
   (`page is None` lub `page.evaluate("() => 1")` rzuca) i wtedy **raz** odbuduj
   stronę (`new_page` + `goto`); przy drugim niepowodzeniu z rzędu przerwij przebieg
   z jasnym komunikatem.

6. **Furtka**: flaga `--web-restart-per-scenario` (i pole w `TEST_CONFIG`), która
   przywraca stare zachowanie (`stop_game()` robi pełny `cleanup()`, `start_game()`
   pełny start). Opisz ją w docstringu modułu obok `--url`/`--timeout`.

7. **`--smoke`**: lista nazw w `TEST_CONFIG["SMOKE_SCENARIOS"]` + flaga filtrująca
   `selected` w `main()` (działa dla oba backendów: `just test-smoke` i
   `just test-web --smoke`). Skład (rozłączne obszary, wszystkie desktop+web):

   | Scenariusz | Co pokrywa |
   |---|---|
   | `Save and Load Basic` | menu zapisu/wczytania, format save |
   | `Hammer Dialog Flow` | dialog + wybór opcji + skutek w świecie |
   | `Auto Save on Maze Entry` | labirynt, autosave, przejście mapy |
   | `UI Flow - Menu Save then Load` | pełny obieg paneli UI |
   | `Display Settings Flow` | ustawienia, zmiana rozdzielczości/layout |
   | `TextInput Basic` | wejście tekstowe (klawiatura, kursor) |

8. **`just test-smoke`** = `.venv/bin/python3 tests/automate_display_test.py --smoke`
   (desktop). Recipe `[windows]` - stub z komunikatem jak przy `test-agent`.

## Kryteria akceptacji

1. `MOM_SKIP_SS_REVIEW=1 just test-web 2>&1 | tee /tmp/web.log` - wszystkie
   scenariusze pass, `grep -c "Starting pygbag" /tmp/web.log` = **1**, całość
   **< 15 min** (mierz `time`; baseline ~25 min).
2. `just test-web "Save and Load Basic"` (jeden scenariusz) - pass, bez zmian
   w obserwowanym zachowaniu.
3. `just test-web --web-restart-per-scenario` na dwóch scenariuszach - `grep -c
   "Starting pygbag"` = **2** (furtka działa).
4. `MOM_SKIP_SS_REVIEW=1 just test-agent` (pełny desktop) - tyle samo pass co przed
   zmianą; `grep -c "Cleaning up"` = liczba scenariuszy (desktop nadal restartuje grę).
5. `MOM_SKIP_SS_REVIEW=1 just test-smoke` - 6 scenariuszy pass, **< 5 min**; po
   celowym zepsuciu jednej asercji exit code != 0.
6. `just test-unit` pass, `just mypy` = `Success: no issues found`.
7. `AGENTS.md` i komentarze recipe w `justfile` opisują nowy tryb.

## Pułapki

- **`start_hour` per scenariusz**: env musi być wstrzyknięty PRZED `reload()`, bo gra
  czyta `MoM.env` przy imporcie `settings`. Przy żywej stronie łatwo zgubić kolejność
  i odziedziczyć godzinę z poprzedniego scenariusza - dodaj do smoke/web logu
  wypis wstrzykniętego `MoM.env` (dziś jest, :955 - nie usuwaj).
- **Kolejność w `run_scenarios`**: `begin_scenario` → `cleanup_saves_before` →
  `setup_saves` → `start_game`. Przy żywej stronie gałęzie `if self.page is not None`
  wreszcie się wykonują - sprawdź, czy nie czyszczą czegoś, co `setup_saves` właśnie
  wstrzyknęło (dziś `_inject_setup_saves()` jest po czyszczeniu w `start_game`).
- **Nie skracaj `INIT_WAIT_WEB`** "bo assety są w cache" bez pomiaru - to pierwsze
  źródło web-flaków. Optymalizacja tego zadania to usunięcie **buildu**, nie czekania.
- Web-flaki najpierw powtórz 2x, potem oglądaj `screenshots/agent/` (Read czyta PNG).
- pygbag nie startuje w świeżym worktree poza repo - testuj w głównym repo.
- `localStorage` przetrwa `reload()` i zamknięcie strony (ten sam origin) - pętla
  czyszcząca sloty 0..9 oraz `MoM.input` jest obowiązkowa, nie "na wszelki wypadek".
- Listener `page.on("console", ...)` rejestruj RAZ (w `start_session`), inaczej po
  każdym scenariuszu dochodzi kolejna kopia i log się multiplikuje.

## Po zakończeniu

- odhacz A08 w `doc/audyt/audyt.md`
- odnotuj nowy czas pełnego web w `doc/audyt/B01-stan-realizacji.md` (sekcja bramek)
- commit: `A08: web-runner reużywa jednego serwera pygbag + just test-smoke`
