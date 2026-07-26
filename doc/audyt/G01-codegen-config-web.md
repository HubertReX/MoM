# G01 - codegen `config.py` (web) z `config_pydantic.py`

Priorytet: **P1** (Faza 2). Rozmiar: M.
Zależności: F03 (mypy wyzerowany) i C01 (`just validate-world`) - zrealizowane.
Realizacja: po B01 (rdzeń stabilny), niezależna od B02.

Decyzja kierunkowa z audytu (znalezisko **D-2**): *"config: wersja web (dataclassy)
generowana z modeli pydantic"*.

## Kontekst i problem

Model konfiguracji istnieje **dwa razy**, bo pydantic nie ładuje się w pygbag/WASM:

| Plik | Tryb | Rola |
|---|---|---|
| `project/config_model/config_pydantic.py` (341 l.) | desktop | modele pydantic + `model_validator` (walidacja spójności przy starcie i przy imporcie) |
| `project/config_model/config.py` (287 l.) | web | ręczne `@dataclass(slots=True)` + `from_dict` |

Wybór następuje w `game.py:87-94` (`if IS_WEB: from config_model.config import load_config`),
a punktowo także w `objects.py:19-23`, `characters/npc.py:33-36`, `ui/panels/hud.py:52`,
`ui/panels/inventory.py:42`.

`config_model/AGENTS.md` (linie 47-58) mówi wprost: *"Zmiana struktury configu =
aktualizacja OBU plików"*. Ta zasada **już zawiodła** - w kodzie na `main` siedzą dwa
ciche rozjazdy, oba wykryte przy projektowaniu tego zadania:

1. **`config.py:174`** - `Chest.from_dict` czyta `data.get("random_items_count", 0)`,
   a pole modelu i klucz w `config.json` nazywa się **`total_items_count`** (ma go 8 z 10
   skrzyń). Konsument: `objects.py:461-484` dopełnia skrzynię losowym łupem
   `for _ in range(self.model.total_items_count - curr_count)`.
   **Efekt na web: każda skrzynia ma `total_items_count == 0`, więc nigdy nie dostaje
   losowej zawartości** - są w niej tylko przedmioty z jawnej listy `items`.

2. **`config.py:52`** - `MazeLevelProperties.from_dict` czyta `data.get("chest_count", 1)`,
   a pole i klucz to **`small_chest_count`** (w `config.json` np. 2). Konsument:
   `scene/map_loader.py:309` `scene.maze_rng.sample(candidates, level_properties.small_chest_count)`.
   **Efekt na web: labirynt dostaje 1 małą skrzynię zamiast skonfigurowanych**, a ponieważ
   zmienia się liczba losowań z `maze_rng`, rozjeżdża się **cały dalszy strumień RNG** -
   ten sam seed daje na web inny labirynt niż na desktopie.

Żaden z tych błędów nie wywala gry ani nie loguje ostrzeżenia. Objaw to "na web gra się
trochę inaczej", czyli dokładnie klasa problemu opisana w notatce pamięci
`web-desktop-config-model-mirror` (traceback tylko w konsoli JS, F12). Ręczne lustro
przetrwało kilka rund synchronizacji i mimo to się rozjechało - to jest argument za
generowaniem zamiast przepisywania.

## Cel

- `project/config_model/config.py` przestaje być plikiem pisanym ręcznie i staje się
  **artefaktem generowanym** z `config_pydantic.py`, z banerem "nie edytuj ręcznie".
- Test jednostkowy **czerwieni się, gdy plik na dysku różni się od tego, co generator
  wypluje teraz** - dryf nie da się scommitować (CI `unit_tests.yml` odpala `just test-unit`).
- Drugi, niezależny test **ładuje prawdziwy `config.json` obydwoma modelami i porównuje
  pole po polu** - to on wyłapuje oba błędy powyżej i będzie je wyłapywał w przyszłości.

### Czego NIE robimy w tym zadaniu

- Nie generujemy `config_schema.json` - jest już generowany (`just update-config-schema`).
- Nie ruszamy **trzeciego lustra**: `CONF_ENTITIES_TO_STORE` w `settings.py:819-842`
  (kolumny CSV). To osobny temat, blisko C02.
- Nie przenosimy walidacji pydantic na web. Web świadomie nie waliduje - walidacja
  dzieje się na desktopie, przy imporcie treści (decyzja **D4**, komentarz
  `config_pydantic.py:156-159`).

## Pliki do zmiany

- `scripts/gen_web_config.py` - **NOWY** generator (konwencja: skrypty pomocnicze
  w `scripts/`, wzorzec nagłówka i `sys.path` - `scripts/gen_dialog_doc_assets.py:20-33`)
- `project/config_model/config.py` - od teraz artefakt generowany
- `tests/test_config_web_codegen.py` - **NOWY**: guard świeżości + parytet modeli
- `justfile` - recipe `gen-web-config` (`[unix]` + `[windows]`, wzór: `gen-faces`)
- `project/config_model/AGENTS.md` - sekcja "Dwie implementacje modelu (workaround
  pygbag)", linie 47-58: ostrzeżenie "aktualizuj OBA pliki" zastępuje procedura
  "edytuj pydantic → `just gen-web-config`"
- `project/AGENTS.md` - tabela "KRYTYCZNE: różnice desktop ↔ web" (~linia 203), wiersz "Config"

## Kroki

Każdy krok osobno zielony i osobno commitowalny.

### Krok 1 - test parytetu, potem ręczna naprawa dwóch dryfów

Napisz `tests/test_config_web_codegen.py` z testem, który:

- ładuje `project/config_model/config.json` przez `config_pydantic.load_config()`
  **oraz** przez `config.load_config()`,
- dla każdej sekcji (`characters`, `items`, `chests`, `maze_configs`) porównuje zbiory
  kluczy, a potem dla każdego klucza i **każdego pola z `model_fields` modelu pydantic**
  porównuje wartości (enumy porównują się wprost - obie strony używają tych samych klas
  z `enums.py`),
- raportuje różnice jako `<sekcja>.<klucz>.<pole>: desktop=<x> web=<y>` (nie pierwszy
  błąd - **wszystkie**, inaczej naprawa idzie po jednym rozjeździe na przebieg).

Uruchom: test musi paść na dokładnie dwóch polach - `chests.*.total_items_count`
i `maze_configs.*.small_chest_count`. Jeśli pada na innych, **zatrzymaj się i wypisz je
w opisie commita** - znalazłeś kolejny rozjazd, którego to zadanie nie przewidziało.

Napraw oba ręcznie w `config.py` (zmiana kluczy w `.get()`), test na zielono.
Commit osobno - to naprawa błędu w grze, nie refactor, i ma trafić do historii jako taka.

Pułapka: po naprawie `small_chest_count` labirynty na web zmieniają układ dla tego samego
seeda (patrz wyżej - inna liczba losowań). To jest zamierzone, desktop jest referencją.
Sprawdź, że `just test-unit maze_reproducible` dalej przechodzi (ten test chodzi ścieżką
desktopową, więc nie powinien drgnąć).

### Krok 2 - generator

`scripts/gen_web_config.py` importuje modele z `config_pydantic` i emituje cały
`config.py`. Podział na to, co **wyprowadzalne** i co **deklarowane**:

**Wyprowadzalne z modelu** (`Model.model_fields` daje `FieldInfo` z `.annotation`,
`.default`, `.default_factory`, `.is_required()`):

| Annotacja pydantic | Pole dataclassy | Wyrażenie w `from_dict` |
|---|---|---|
| `str` / `int` / `float` / `bool` | to samo | `str(...)` / `int(...)` / `float(...)` / `bool(...)` wokół `data.get("f", <default>)` |
| `RaceEnum`, `AttitudeEnum`, `ItemTypeEnum` | ten sam enum | `RaceEnum(data.get("race", ""))` |
| `list[str]` | `list[str]` | `[str(x) for x in data.get("f", [])]` |
| `list[ItemTypeEnum]` | `list[ItemTypeEnum]` | `[ItemTypeEnum(x) for x in data.get("f", [])]` |
| `str \| None` | `str \| None` | `data.get("f")` |
| `dict[str, Any]` | `dict[str, Any]` | `data.get("f", {})` |
| `dict[int, X]` (`maze_configs`) | `dict[int, X]` | pętla z `int(name)` na kluczu |

Kolejność pól = kolejność deklaracji w modelu pydantic. Pola bez wartości domyślnej
zostają bez domyślnej także w dataclassie (`RaceEnum(data.get("race", ""))` rzuci
`ValueError` przy braku klucza - **to jest pożądane**, brak wymaganego pola ma być głośny).

**Deklarowane w generatorze** (jedna widoczna tabela `OVERRIDES`, nie sprytna heurystyka):

- `("Character", "disposition")` - pydantic ma `int | dict[str, int]` z walidatorem
  `_convert_disposition` (`config_pydantic.py:101-108`). Na web: typ `dict[str, int]`,
  default `field(default_factory=lambda: dict(DEFAULT_DISPOSITION_WEIGHTS))`, wyrażenie
  = wywołanie funkcji pomocniczej odtwarzającej semantykę walidatora (int → domyślne wagi,
  dict → skopiowany i przecastowany, cokolwiek innego → domyślne wagi).
- `("Config", "quests")` - pydantic ma `dict[str, Quest]`, web ma `dict[str, Any]`
  (decyzja D4: runtime czyta surowy dict przez `quest.graph.init_quests`). Zostaw
  w wygenerowanym pliku komentarz z tym uzasadnieniem - dziś jest w `config.py:195-197`
  i nie może zniknąć.
- `SKIP_MODELS = {"Quest", "QuestReward", "ConfigForSchemaGen"}` - nie są częścią modelu
  web.

**Stały szablon** (prolog i epilog, wklejane dosłownie): docstring modułu, baner, importy
(`json`, `dataclasses`, `typing`, `from enums import ...`, `from settings import
DEFAULT_DISPOSITION_WEIGHTS`), helper `disposition` i funkcja `load_config`.
`Config.build` jest wyprowadzalny (pętla po polach typu `dict[str, Model]`).

### Krok 3 - guard świeżości, recipe, dokumentacja

- Dopisz do `tests/test_config_web_codegen.py` test, który woła generator **w pamięci**
  (funkcja zwracająca `str`, nie tylko `main()` piszący plik) i porównuje z treścią
  `config.py` na dysku. Komunikat błędu musi mówić `uruchom: just gen-web-config`.
- Drugi mikro-test: wygenerowane źródło **nie zawiera słowa `pydantic`** (ani w importach,
  ani w komentarzach) - to jedyna rzecz, której złamanie wywala grę na web natychmiast.
- `just gen-web-config` = `.venv/bin/python scripts/gen_web_config.py`.
- Zaktualizuj oba `AGENTS.md` (lista wyżej).

Uwaga do konwencji runnera: `scripts/run_unit_tests.py` **wywala test-plik, w którym
funkcja `test_*` nie jest wypisana w liście `tests = [...]`** na dole pliku. Trzymaj się
wzorca z `tests/test_save_load_models.py:404-420`.

## Kryteria akceptacji

1. `just gen-web-config` uruchomione dwa razy z rzędu - po drugim `git diff` pusty
   (generator deterministyczny).
2. `just test-unit config_web_codegen` zielony. Kontrola negatywna: dopisz ręcznie pole
   do `Character` w `config_pydantic.py`, **nie** regeneruj - test świeżości musi paść.
   Cofnij zmianę.
3. Test parytetu zielony dla prawdziwego `config.json`. Kontrola negatywna: zepsuj
   jeden klucz w `.get()` w wygenerowanym pliku - test parytetu musi paść.
4. `just mypy` = `Success: no issues found` (wygenerowany plik przechodzi mypy strict).
5. `just test-unit` w całości zielony.
6. Ręczny smoke ścieżki web bez przeglądarki: ustaw `USE_WEB_SIMULATOR = True`
   (`settings.py:302` - to **stała w źródle, nie zmienna środowiskowa**), `just run`,
   wejdź do wioski, otwórz skrzynię, wejdź do labiryntu. Przywróć `False`.
7. `MOM_SKIP_SS_REVIEW=1 just test-smoke` zielony (6 scenariuszy).
8. `MOM_SKIP_SS_REVIEW=1 just test-web "Maze Persists Across Save Load"` zielony -
   jedyny test, który realnie ładuje wygenerowany model w prawdziwym WASM.
9. `just validate-world` bez nowych naruszeń.
10. `config_model/AGENTS.md` i `project/AGENTS.md` opisują nowy przepływ.

## Pułapki

- **Baner nie może zawierać daty ani wersji.** Cokolwiek zmiennego w nagłówku i guard
  świeżości pada przy każdym uruchomieniu.
- **Determinizm iteracji.** `model_fields` jest uporządkowany, ale własne słowniki
  w generatorze sortuj jawnie - jedno `set()` w złym miejscu i plik zmienia się między
  przebiegami.
- **Nie przenoś `frozen=IS_FROZEN`** z pól pydantic (`name_EN`, `name_PL`) na dataclassy.
  Runtime robi głęboką kopię modelu per instancja i mutuje na niej `health`/`money`
  (patrz docstring `npc_runtime.py:22-26`) - zamrożenie pól to crash na web.
- **Zachowaj `@dataclass(slots=True)` na encjach i gołe `@dataclass` na `Config`** -
  dokładnie jak dziś. `save_load/manager.py:39-42` (`_copy_item_model`) rozgałęzia się
  po `hasattr(item, "model_copy")` i na web robi `copy.copy` - działa ze slotami, ale
  nie testuj tego przypadkiem.
- **`load_config` w `config.py:273` robi `del config_json["$schema"]`** - `KeyError`
  przy pliku bez tego klucza. Skoro i tak przepisujesz szablon, zmień na
  `config_json.pop("$schema", None)` i odnotuj to w opisie commita (drobna zmiana
  zachowania, nie milczące).
- **Generator importuje `config_pydantic`, które importuje `settings`, `enums`,
  `quest.graph`.** Potrzebny `sys.path.insert(0, str(PROJECT))` i najpewniej
  `SDL_VIDEODRIVER=dummy` - skopiuj preambułę z `scripts/gen_dialog_doc_assets.py:26-33`.
- **Rozjazdy poza tabelą pól.** Parytet porównuje wartości po załadowaniu configu, więc
  nie zobaczy różnicy w polu, którego nikt w `config.json` nie ustawia (obie strony wezmą
  swój default). Dlatego guard świeżości jest potrzebny **obok** parytetu, nie zamiast.
- Web-flaki najpierw powtórz 2x, dopiero potem oglądaj `screenshots/agent/`.

## Po zakończeniu

- odhacz G01 w `doc/audyt/audyt.md`
- commit: `G01: config.py (web) generowany z modeli pydantic + guard dryfu`
  (osobno wcześniejszy commit z kroku 1: `fix(web): skrzynie i labirynty czytały złe klucze configu`)
- zaktualizuj notatkę pamięci `web-desktop-config-model-mirror` - lustro modelu jest
  od teraz generowane, ale klasa błędu zostaje aktualna dla lustra kolumn CSV
  (`CONF_ENTITIES_TO_STORE` w `settings.py`)
