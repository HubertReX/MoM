# A07 - zmienne środowiskowe testów działające także na web

Priorytet: **P1** (Faza 1, domknięcie A04). Rozmiar: M. Zależności: A02 i A04 (zrobione).

## Kontekst i problem

Tryb deterministyczny z A04 (`MOM_TEST_DETERMINISTIC`, `MOM_TEST_START_HOUR`) jest
**desktop-only**. Runner ustawia te zmienne w `env` podprocesu gry
(`apply_determinism_env` w `tests/automate_display_test.py`), a w trybie web gra nie jest
podprocesem - jest WASM-em w przeglądarce i `env` runnera do niej nie dociera. Skutek:
`just test-web` zawsze chodzi na losowym seedzie świata i losowej pogodzie, więc zrzuty
web są nieporównywalne między uruchomieniami, mimo że desktopowe już są.

Ta sama bariera dotknie **każdą kolejną flagę**. Dzisiaj jedyna flaga, która działa na web,
przechodzi osobnym, ręcznie dopisanym kanałem: runner pisze `localStorage['MoM.agent_control']`,
a `game.py` (ok. linii 243) czyta ten jeden klucz w miejscu, gdzie tworzy `AgentController`.
Każda następna zmienna wymagałaby powtórzenia tego wzorca w kolejnym miejscu.

## Cel

**Jeden kanał na wszystkie zmienne**: cokolwiek runner ustawia dla gry desktopowej w `env`,
ma tak samo działać na web. `settings.py` czyta zmienne przez wspólny helper, który na
desktopie sięga do `os.environ`, a na web do jednego klucza localStorage.

## Pliki do zmiany

- `project/settings.py` - helper czytający zmienne + przestawienie na niego wszystkich
  odczytów `os.environ` związanych z trybami testowymi
- `project/game.py` - odczyt flagi agenta przez helper zamiast osobnego klucza
- `tests/automate_display_test.py` - `WebRunner` wstrzykuje zebrane zmienne
- `project/AGENTS.md` - opis kanału (sekcje "Tryb deterministyczny" i "agent_ctrl")

## Krok 1: helper w `settings.py`

Tuż **po** definicji `IS_WEB` (`settings.py:304` - kolejność ma znaczenie, helper musi
znać tryb) dodaj:

```python
def _test_env() -> dict[str, str]:
    """Zmienne sterujące trybami testowymi, niezależnie od targetu.

    Desktop: `os.environ`. Web: jeden klucz localStorage `MoM.env` z obiektem JSON
    (`{"MOM_TEST_DETERMINISTIC": "1", ...}`), wstrzykiwany przez runner PRZED
    przeładowaniem strony - ten moduł czyta go przy imporcie, więc później byłoby za późno.
    """
```

Implementacja: gdy `IS_WEB and not USE_WEB_SIMULATOR` - `from platform import window`,
`json.loads(window.localStorage.getItem("MoM.env") or "{}")`, każdy wyjątek => `{}`
(gra musi wstać także bez tego klucza). W przeciwnym razie `dict(os.environ)`.

Wynik wołaj **raz**, do stałej modułowej (`_ENV = _test_env()`), i przestaw na nią:

- `USE_AGENT_CONTROL` (dziś `os.environ.get("MOM_AGENT_CONTROL")`)
- `TEST_DETERMINISTIC` / `TEST_WORLD_SEED`
- nadpisanie `INITIAL_HOUR` z `MOM_TEST_START_HOUR`

`USE_WEB_SIMULATOR` (desktop udający web) ma dalej czytać `os.environ` - stąd warunek
`and not USE_WEB_SIMULATOR` wyżej.

## Krok 2: `game.py` przestaje mieć własny kanał

Odczyt `window.localStorage.getItem("MoM.agent_control")` w `game.py` (ok. 243) zastąp
zwykłym `USE_AGENT_CONTROL` - po kroku 1 ta stała jest już prawdziwa na obu targetach.
Gałęzie `if USE_AGENT_CONTROL and not IS_WEB` / `elif IS_WEB ...` zwijają się do jednego
warunku, w którym różnicą zostaje wyłącznie `web_mode=IS_WEB` przekazywane do
`AgentController`.

Zostaw odczyt starego klucza `MoM.agent_control` jako fallback (`_ENV` puste, a stary
klucz ustawiony => traktuj jak `MOM_AGENT_CONTROL=1`) i oznacz komentarzem jako przejściowy
- inaczej otwarta karta ze starą sesją zachowa się inaczej niż świeża i będzie to
wyglądać na losowy błąd.

## Krok 3: runner wstrzykuje zmienne

W `WebRunner.start_game`, dokładnie tam gdzie dziś ustawiana jest flaga agenta (po
pierwszym `goto()`, **przed** `reload()` - gra czyta to przy imporcie `settings`), zapisz
klucz `MoM.env` z JSON-em zebranych zmiennych.

Zbierz je tą samą funkcją co desktop: `apply_determinism_env` operuje na zwykłym dict-cie,
więc wywołaj ją na pustym słowniku i wstrzyknij wynik. Dzięki temu **jedna** funkcja
decyduje o trybie dla obu backendów i pole scenariusza `start_hour` zaczyna działać na web
bez dodatkowego kodu.

Usuń z docstringu `WebRunner.start_game` (i z `project/AGENTS.md`) uwagę, że tryb
deterministyczny jest desktop-only.

## Krok 4: cząstki i pogoda na web

Sprawdź, czy `Scene._particle_rng()` faktycznie dostaje seed na web - `settings.TEST_WORLD_SEED`
po kroku 1 powinno być ustawione, ale zweryfikuj to empirycznie (krok w kryteriach), bo to
jedyne miejsce, gdzie łańcuch env → seed → emiter przechodzi przez trzy moduły.

## Kryteria akceptacji

1. `just test-web "Save and Load Basic"` wypisuje z gry linię
   `[test] deterministic mode: world seed 12345, start hour 9` (log gry trafia do konsoli
   przeglądarki - odczytaj przez `page.on("console")` albo dorzuć tymczasowy print w runnerze).
2. Dwa kolejne uruchomienia tego samego scenariusza web dają ten sam `world_seed`
   (najprościej: dopisz `world_seed` do zrzutu `debug_ui_state` w `agent_ctrl.py`
   i porównaj `ui_state` z dwóch przebiegów - to i tak przydatna informacja diagnostyczna).
3. Scenariusz z polem `"start_hour": 21` daje na web godzinę 21-22 w zrzucie `ui_state`
   (na desktopie już działa - patrz A04).
4. `MOM_TEST_LIVE_WORLD=1 just test-web "Save and Load Basic"` wraca do losowego świata.
5. `just test-web` (cały zestaw web) przechodzi z `MOM_SKIP_SS_REVIEW=1`.
6. `MOM_SKIP_SS_REVIEW=1 just test-agent` (desktop) przechodzi - refactor `settings.py`
   nie mógł ruszyć targetu, który już działał.
7. Zwykłe `just run` i `just serve-web` bez żadnych zmiennych zachowują się jak dotąd
   (losowy seed, start 9:00, brak sterowania agentem).
8. `just test-unit` i `just mypy` czyste.

## Pułapki

- **Kolejność w `settings.py` jest krytyczna.** Helper musi stać po `IS_WEB`, a odczyty
  flag po helperze. `scene.py` importuje `INITIAL_HOUR` **by-value**, więc nadpisanie
  godziny musi dalej dziać się w treści `settings.py`, nie później (patrz A04).
- **Runner musi pisać klucz przed `reload()`.** Po reloadzie gra już zaimportowała
  `settings` - ustawienie klucza później nie ma żadnego efektu i wygląda jak "flaga nie działa".
- `from platform import window` w pygbag: sprawdź, czy jest dostępne **na etapie importu
  `settings`** (dziś ten import robiony jest później, w `game.py` i `agent_ctrl.py`).
  Jeśli nie - opakuj w `try/except` i zrób z tego cichy fallback do `{}`, nigdy wyjątek.
- Nie wprowadzaj drugiego klucza na każdą flagę - sens tego zadania to **jeden** kanał
  (`MoM.env`), którego nie trzeba rozbudowywać przy kolejnej zmiennej.
- Nie serializuj `MoM.env` do save'ów ani nie mieszaj go z `MoM.settings` (persystencja
  ustawień gracza) - to osobna, testowa przestrzeń.

## Po zakończeniu

- zaktualizuj `project/AGENTS.md`: sekcja "Tryb deterministyczny świata" traci ograniczenie
  desktop-only, sekcja agent_ctrl dostaje opis kanału `MoM.env`
- odhacz A07 w `doc/audyt/audyt.md`
- commit: `A07: zmienne środowiskowe testów przez localStorage - tryb deterministyczny na web`
