# AGENTS.md — rdzeń silnika i gry (`project/`)

Logika gry. Zanim cokolwiek zmienisz, przeczytaj sekcję **desktop ↔ web** — to najczęstsze
źródło regresji. Reguły nadrzędne i lista katalogów do pominięcia: [`../AGENTS.md`](../AGENTS.md).

## Pętla gry i maszyna stanów (FSM)

- **Pętla gry: `game.py`** — asynchroniczna (`Game.loop()` → `Game.run()`), z
  `await asyncio.sleep(0)` żeby oddać sterowanie przeglądarce. Liczy `dt`, czyta input,
  woła `update()`/`draw()` aktualnego stanu, robi `pygame.display.flip()`.
- **Stos stanów: `game.states`** (lista). Bazowa klasa `State` w `state.py`:
  - `enter_state()` — wkłada stan na stos, `exit_state()` — zdejmuje.
  - **Tylko `states[-1]` (wierzch stosu) dostaje `update()` i `draw()`** w danej klatce.
- **Stany:** `Scene` (`scene.py`, rozgrywka na mapie), `MenuScreen` i podklasy
  (`ui/panels/main_menu.py`), `SplashScreen` (`splash_screen.py`). Przejścia ekranowe
  (fade/koło): `transition.py`.

## Mapa plików rdzenia

| Plik                       | Rola                                                                                            | Uwaga                                            |
| -------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `scene.py`                 | Ładowanie mapy `.tmx` (pytmx), render pyscroll `BufferedRenderer`, kolizje, czas/dzień-noc, NPC | **73K — duży**                                   |
| `characters.py`            | `NPC` i `Player`: animacja, A*, movement, walka, inventory                                      | **66K — duży**                                   |
| `ui/`                      | **Własny toolkit UI** (retained-mode, czysty pygame-ce). Patrz niżej.                           | zastąpił `ui.py`+`menus.py`+`rich_text.py`       |
| `dialog/`                  | **System dialogów** (encje grafu, builder, silnik warunków mini-DSL). Patrz niżej.              | czysta logika, bez pygame; web-safe              |
| `settings.py`              | **Wszystkie stałe** gry + definicje sprite-sheetów                                              | **30K**                                          |
| `objects.py`               | Sprite'y: `ItemSprite`, `ChestSprite`, `HealthBar`, `EmoteSprite`, `Collider`, `Notification`   |                                                  |
| `npc_state.py`             | FSM NPC (Idle/Walk/Run/Jump/Fly/Stunned/Attacking/Talk/Dead)                                    |                                                  |
| `particles.py`             | System cząstek (liście, deszcz, wiatr)                                                          |                                                  |
| `nine_patch.py`            | Skalowalne panele UI (9-patch) — używany przez `ui/theme.py`                                    |                                                  |
| `opengl_shader.py`         | Wrapper zengl do shaderów post-process                                                          | patrz [`shaders/AGENTS.md`](./shaders/AGENTS.md) |
| `camera.py`                | Viewport + zoom (steruje `map_view.zoom`)                                                       |                                                  |
| `transition.py`            | Efekty przejść (`Transition`, `TransitionCircle`)                                               |                                                  |
| `second_order_dynamics.py` | Gładkie animacje (Second Order Dynamics) — POC                                                  |                                                  |
| `enums.py`                 | Typy wyliczeniowe (Race, Attitude, ItemType, …)                                                 |                                                  |
| `save_load/display_settings.py` | Persystencja ustawień wyświetlania (rozdzielczość, fullscreen)                              | desktop `settings.json`, web `localStorage`      |
| `main.py`                  | Entry point + CLI (Click na desktopie)                                                          |                                                  |

## Toolkit UI (`ui/`)

Własny, lekki system UI (retained-mode, **czysty pygame-ce**, kompatybilny z pygbag).
Zastąpił sklejkę `pygame_menu` + `thorpy/sftext`. Widżety **cache'ują wyrenderowaną
powierzchnię** (dirty-flag) — statyczne UI = jeden blit/klatkę, zero alokacji `Surface`.

| Moduł                           | Rola                                                                               |
| ------------------------------- | ---------------------------------------------------------------------------------- |
| `ui/widget.py`, `ui/manager.py` | `Widget` (bazowa, cache) + `UIManager` (eventy/update/draw, z-order)               |
| `ui/theme.py`                   | Cache fontów `(rozmiar,bold,italic)`, palety, teł 9-patch                          |
| `ui/text/`                      | `markup.py` (parser tagów z `STYLE_TAGS_DICT` + emoji), `style.py` (`Style`)       |
| `ui/widgets/`                   | `Label`, `Image`, `Button`, `RichText` (zawijanie, scroll, linki, animowane emoji), `TextInput` (`CharSet`, max_length, password, placeholder, `TEXTINPUT`+caret) |
| `ui/panels/`                    | `main_menu`, `hud`, `dialog`, `modal`, `inventory`, `trade`, `text_input_demo` (stan demo `TextInput`; hotkey **F7** = akcja `text_demo`, lub komenda agenta `debug_text_input`) |
| `ui/game_ui.py`                 | **`GameUI`** — kontroler HUD+paneli per-`Scene`                                    |

**Czyste API** (`Scene.ui` to `GameUI`): `ui.open(PanelType, **kw)`, `ui.close(PanelType)`,
`ui.toggle(PanelType)`, `ui.is_open(PanelType)`, `ui.update(dt, events)`, `ui.draw()`,
`ui.reset()`. Stan paneli jest wewnątrz nich (np. `TradePanel.is_buying`) — bez luźnych
boolean-flag. Dialogi w `assets/dialogs/**/*.md` używają tagów `[bold]`/`[link URL]`/`:emoji:`
(tabela `STYLE_TAGS_DICT` w `settings.py`).

## System dialogów (`dialog/`)

Logika dialogów przeniesiona z prototypu RPG (osobne repo — patrz [`../Tasks/DS-epic-brief.md`](../Tasks/DS-epic-brief.md),
epic **DS**). **Czysta logika, zero pygame** — testowalna w izolacji i web-safe (działa
w pygbag/WASM, bez Pydantic). Renderowanie i wpięcie w rozgrywkę robi `ui/panels/dialog.py`
(osobne zadania DS).

| Moduł                         | Rola                                                                                                    | Zadanie |
| ----------------------------- | ------------------------------------------------------------------------------------------------------ | ------- |
| `dialog/entities.py`          | Dataclassy `slots=True`: `DialogNode`, `DialogOption`, `NodeVisitResult` + `NodeVisitResultCategory`   | T-029   |
| `dialog/graph.py`             | `init_dialog(dialog_dict)` — buduje `{key: DialogNode}` z sekcji configu; wiszące referencje = `ValueError` | T-029   |
| `dialog/conditions.py`        | Silnik warunków opcji (mini-DSL) — `check_condition()` / `validate_condition()`                        | T-032   |
| `dialog/result_sink.py`       | `ResultSink` (Protocol) + `apply_result()` / `visit_node()` — efekty węzłów bez importów z gry        | T-034   |
| `result_sink_adapter.py`      | `GameResultSink(ResultSink)` — adapter do `Inventory`, HP, złota i sentymentu NPC                      | T-034   |
| `dialog/markdown_importer.py` | Build-time importer Markdown -> `messages` + `character_dialogs` (regex opcji, walidacja grafu, D3/D7)  | T-024   |

``dialog/markdown_importer.py`` reads source Markdown from
``project/assets/dialogs/{EN,PL}/`` (the single source of truth for dialogs)
and emits the machine-generated ``messages`` and ``character_dialogs`` sections
consumed by ``dialog.graph.init_dialog``. It uses a single named-group regex
for option lines, validates dangling references, orphan nodes, anchor/target
agreement and START presence with ``file:line`` errors, converts RPG rich
markup / emoji to MoM ``RichText`` tags (D3), and rewrites RPG conditions to
the mini-DSL understood by ``dialog.conditions``.

**Regeneracja:** ``just import-dialogs`` (nie trzeba zmieniać `config.json` ręcznie).
Smoke tests: ``.venv/bin/python tests/test_dialog_import.py``.

### Silnik warunków (mini-DSL, decyzja D1)

Warunek widoczności opcji (`DialogOption.condition`) to **wyrażenie w mini-DSL**, nie kod
Pythona. `check_condition()` parsuje je przez `ast.parse(mode="eval")` i interpretuje
**własnym walkerem** wyłącznie po whiteliście węzłów (`BoolOp`, `UnaryOp`, `Compare`,
`Call`-do-predykatów, `Name`, `Constant`). **Nigdy `eval`/`exec`** — brak dostępu do
builtins, atrybutów, subscriptów. Zastąpiło to `eval(condition, cfg)` z RPG
(`dialog_loc.py:check_condition`).

- **Predykaty = jedyny most do danych gry:** `selected(opt)`, `visited(node)`,
  `visited(npc, node)`, `has_item(key)` oraz gołe `sentiment` (int, do porównań).
- **Kontekst** przez `ConditionContext` (`Protocol`) — grę podłącza adapter (zadanie T-023),
  testy używają stuba. Silnik nie importuje niczego z gry.
- **Walidacja przy imporcie:** `graph._build_options` woła `validate_condition()` — błędny
  warunek (nieznana nazwa/predykat, zła arność, dostęp do atrybutu) = `ValueError` przy
  budowie grafu, **nie cichy `False`** w trakcie rozmowy. Parsowanie cache'owane (`lru_cache`),
  bo warunki sprawdzane są co klatkę.

Przykłady: `sentiment >= 42 and selected("BOB_DO_HOBBY_BIKE")`,
`not visited("003") or has_item("MERMAIDS_TEAR")`,
`visited("HAMMER_HOAXHEART_001", "004")`.

### Efekty węzłów (ResultSink, T-034)

Węzły mogą mieć efekt uboczny (`NodeVisitResult`).  `dialog.result_sink` definiuje
`ResultSink` (Protocol) i bezimportowo rozdziela 7 kategorii na metody sinku;
`result_sink_adapter.GameResultSink` mapuje je na systemy MoM:

| Kategoria           | Metoda sinku     | Efekt w grze                                      |
| ------------------- | ---------------- | ------------------------------------------------- |
| `money_received`    | `add_money()`    | `player.model.money += amount`                    |
| `money_returned`    | `remove_money()` | `player.model.money` z clamp do 0                 |
| `items_received`    | `add_items()`    | `scene.create_item()` + `player.pick_up()`        |
| `items_returned`    | `remove_items()` | usuwa/zmniejsza stack z `player.items`            |
| `health_restored`   | `restore_health()` | `player.model.health` z clamp do `max_health`   |
| `health_lost`       | `lose_health()`  | `player.model.health` z clamp do 0                |
| `sentiment_shift`   | `shift_sentiment()` | `npc.sentiment` z clamp do 0–100               |

`visit_node(node, sink)` aplikuje efekt **dokładnie raz** — `DialogNode.visited`
chroni przed dublem przy ponownym otwarciu dialogu lub cofnięciu się do węzła.
Wpięcie w grze: `DialogPanel._visit_current_node()` wywoływane przy otwarciu
panelu oraz po wyborze opcji (`activate_selected`).

### Testy

Czysta logika — testy to samodzielne skrypty (bez SDL), uruchamiane wprost interpreterem:

```bash
.venv/bin/python tests/test_dialog_graph.py        # encje + builder (T-029)
.venv/bin/python tests/test_dialog_conditions.py   # silnik warunków (T-032)
.venv/bin/python tests/test_dialog_result_sink.py  # efekty węzłów + GameSink (T-034)
```

## 🔑 KRYTYCZNE: różnice desktop ↔ web

`IS_WEB` zdefiniowane w `settings.py:130-131`. Najważniejsze rozgałęzienia:

| Obszar                  | Desktop                         | Web                     | Lokalizacja                                                            |
| ----------------------- | ------------------------------- | ----------------------- | ---------------------------------------------------------------------- |
| Config                  | `config_pydantic.py` (Pydantic) | `config.py` (dataclass) | `if IS_WEB:` w `characters.py:48`, `objects.py:19`, `ui/panels/hud.py` |
| Shadery                 | dostępne (gdy `USE_SHADERS`)    | wyłączone (wydajność)   | `USE_SHADERS=False` `settings.py:141`                                  |
| Filtr dzień-noc (alpha) | tak                             | **nie**                 | `scene.py:1515` `if USE_ALPHA_FILTER and not IS_WEB:`                  |
| Logowanie               | `print`                         | `platform.console.log`  | `game.py`                                                              |
| Asyncio                 | stdlib                          | `pygbag.aio`            | `main.py`                                                              |
| Wyjście z gry           | zamyka okno                     | zostaje w przeglądarce  | `state.py`                                                             |
| Screenshoty             | zapis na dysk                   | download w przeglądarce | `game.py`                                                              |
| Gamepad                 | XBOX/Steam Deck                 | `WEB_CONTROL_NAMES`     | `settings.py`, `game.py`                                               |

**Reguła:** nowy kod zależny od platformy chowaj za `if IS_WEB:`; testuj `just run` **oraz**
`just serve-web`.

### `USE_WEB_SIMULATOR` (`settings.py:130`)

Flaga desktopowa do **testowania ścieżek web bez przeglądarki**. Ustawiona na `True` wymusza
`IS_WEB=True` (`settings.py:131`) i przełącza asyncio na `pygbag.aio` (`main.py:35`, `game.py:73`),
ale loguje przez `print` (a nie `platform.console.log`, dostępne tylko w realnej przeglądarce —
`game.py:105` `if IS_WEB and not USE_WEB_SIMULATOR`). Domyślnie `False`.

## Testowanie gry przez agentów AI (`agent_ctrl.py`)

Mechanizm pozwalający agentowi **uruchomić grę, „naciskać" klawisze i robić zrzuty ekranu**
(debug). Działa na desktopie (plikowy kanał komend) i w web (localStorage + Playwright).
**Opt-in**, domyślnie wyłączony — nie wpływa na normalną rozgrywkę.
Wysyła **prawdziwe zdarzenia klawiszy** (`pygame.event.post`), więc działa i w menu,
i w scenie. Nie nadaje się do szybkich scen walki (rozdzielczość = klatki).

**Włączenie** (zmienna środowiskowa):

```bash
MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python3 project/main.py
```

`SDL_VIDEODRIVER=dummy` i `SDL_AUDIODRIVER=dummy` pozwalają uruchomić grę bez okna
i bez dźwięku — wymagane w środowisku agenta. Flaga `USE_AGENT_CONTROL` w `settings.py`
czyta `os.environ`.

**Sterowanie** (z innego terminala, gdy gra działa):

```bash
python project/agent_ctrl.py down accept            # w menu: zaznacz i uruchom (Play)
python project/agent_ctrl.py up:30 right:15 attack  # ruch + atak (':N' = liczba klatek)
python project/agent_ctrl.py screenshot             # zrzut → screenshots/agent/
python project/agent_ctrl.py exit                   # zamknij grę
# albo bezpośrednio: echo "up:30 screenshot" > agent_input.txt
```

Format komendy: `<akcja>[:klatek]`. `klatek` określa, ile klatek klawisz jest
przytrzymywany. Dla ruchu sensowne wartości to 10–60; w menu wystarczy 1.

**Komendy:**

- Zwykłe akcje z `ACTIONS` w `settings.py`: `left`, `right`, `up`, `down`, `run`,
  `jump`, `attack`, `talk`, `open`, `pick_up`, `drop`, `inventory`, `menu`, `accept`,
  `quit`, `zoom_in`, `zoom_out`, `reload`, `next_day`, `quick_save` (F5), `quick_load` (F9),
  `slot_rename` (R) / `slot_delete` (D) - akcje na zaznaczonym slocie w panelu Save/Load
  (`ui/panels/save_load.py`: `LoadPanel`/`SavePanel` - zmiana nazwy przez `TextInput` i
  usunięcie z potwierdzeniem; panel otwarty w grze przez F9 zamraża scenę), itd.
- Specjalne komendy interpretera (`project/agent_ctrl.py`):
  - `screenshot` / `shot` - zapisuje bieżącą klatkę do `screenshots/agent/`.
  - `exit` / `quit_game` - zamyka grę.
  - `debug_settings` - loguje aktualne ustawienia wyświetlania.
  - `debug_death_screen` - wymusza ekran śmierci.
  - `debug_load_last_save` - wczytuje ostatni zajęty slot.
  - `debug_text_input` - pokazuje stan demo widgetu `TextInput` (`ui/panels/text_input_demo.py`).
  - `debug_set_maze` - wymusza `is_maze=True` na bieżącej scenie (test zakazu zapisu w lochu).
  - `type:<tekst>` - wpisuje tekst do pola z fokusem (jedno słowo, bez spacji); wysyła
    realne zdarzenia `TEXTINPUT` (syntetyczne `KEYDOWN` ich nie generują). Np. `type:Abc123`.
  - `backspace` - kasuje znak przed kursorem w polu tekstowym (wysyła `KEYDOWN` Backspace).

Zrzuty trafiają do `screenshots/agent/` (zapisywany `self.screen`). Przy `USE_SHADERS=True`
finalny obraz idzie przez GL i `self.screen` może nie zawierać klatki — testuj z shaderami off.

**Wpięcie w kod (minimalne, 4 miejsca w `game.py`):** instancja w `__init__` (gdy flaga),
`agent_ctrl.apply(self)` po `get_inputs()` w `run()`, `agent_ctrl.capture(self.screen)`
po `flip()`. Cała logika w `project/agent_ctrl.py`.

**Automatyczne testowanie (Scenario Framework):**
Używamy struktury scenariuszy zdefiniowanych w `tests/scenarios.json`. Każdy scenariusz to
lista `TestAction`, które wykonują komendy przez bezpośredni zapis do `agent_input.txt`.
To pozwala na szybkie, powtarzalne testowanie przepływów UI i logiki gry bez narzutu
procesów Pythonowych dla każdej akcji.

```bash
# Pojedynczy scenariusz - zalecany do weryfikacji:
MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python3 tests/automate_display_test.py "Save and Load Basic"

# Wszystkie scenariusze naraz:
MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python3 tests/automate_display_test.py
```

Akcje są oddzielone pauzami (`TRANSITION_WAIT`), aby zapewnić stabilność przejść
między stanami gry. Każda akcja może mieć własne `wait`.

Runner uruchamia **osobną instancję gry przed każdym scenariuszem** i zabija
proces po jego zakończeniu, więc pełny przebieg wykonuje się na żywych
procesach. `cleanup()` czeka na zakończenie procesu (z fallbackiem na SIGKILL),
aby uniknąć wiszących instancji między scenariuszami.

Scenariusz może opcjonalnie zawierać:

- `cleanup_saves: [0]` — lista slotów do wyczyszczenia przed startem gry
  (redundantna, ponieważ runner domyślnie czyści **wszystkie** sloty przed
  każdym scenariuszem; pozostawiona dla jawnej dokumentacji scenariusza).
- `assertions` — lista asercji plikowych wykonywanych po scenariuszu, np.
  `{"type": "file_exists", "path": "<save_dir>/save_0.mom", "min_size": 100}`.
  Ścieżka `<save_dir>` jest rozwijana do katalogu save'ów danego systemu.

**Persystencja w testach:**

Pliki save na desktopie (jeśli zdefiniowano zmienną środowiskową `XDG_DATA_HOME`, zapisy trafiają do `<XDG_DATA_HOME>/mom/saves/`, w przeciwnym razie stosowane są domyślne ścieżki systemowe):

- macOS: `~/Library/Application Support/mom/saves/save_N.mom` (lub `<XDG_DATA_HOME>/mom/saves/save_N.mom`)
- Linux: `~/.local/share/mom/saves/save_N.mom` (domyślny fallback dla XDG)

Helper do manipulowania zapisami: `tests/test_save_load_corrupt.py`:

```bash
.venv/bin/python3 tests/test_save_load_corrupt.py clear     # usuń wszystkie save'y
.venv/bin/python3 tests/test_save_load_corrupt.py corrupt 0 # zepsuj slot 0
.venv/bin/python3 tests/test_save_load_corrupt.py create 0  # utwórz minimalny save
.venv/bin/python3 tests/test_save_load_corrupt.py delete 0  # usuń slot 0

### Web (pygbag + Playwright)

Runner wspiera również testowanie przez przeglądarkę — uruchamia pygbag, otwiera
stronę w headless Chromium i steruje grą przez `window.localStorage`.

**Wymagania:** `requirements-dev.txt` zawiera `playwright>=1.50`. Po instalacji:

```bash
# instalacja pakietu + binary chromium (jednorazowo)
rtk uv pip install playwright
rtk .venv/bin/playwright install chromium
```

**Uruchamianie:**

```bash
# Pojedynczy scenariusz:
.venv/bin/python3 tests/automate_display_test.py --web "Save and Load Basic"

# Wszystkie web-kompatybilne scenariusze:
.venv/bin/python3 tests/automate_display_test.py --web

# Wolniejszy sprzęt / CI: wydłuż boot gry i okno startu pygbag
.venv/bin/python3 tests/automate_display_test.py --web --timeout 25 --pygbag-timeout 180 "Save and Load Basic"
```

**Flagi (tylko web):**

- `--timeout <s>` — ile czekać na boot gry po pojawieniu się canvasu (domyślnie 12s).
- `--pygbag-timeout <s>` — ile czekać na zbudowanie + serwowanie przez pygbag (domyślnie 90s).
- `--url <url>` — nadpisz URL pygbag (domyślnie `http://127.0.0.1:8001/`).

**Różnice w stosunku do desktop runnera:**

1. Komendy są wstrzykiwane przez `page.evaluate("localStorage.setItem('MoM.agent_input', ...)")`
   zamiast `echo > agent_input.txt`.
2. Zrzuty ekranu wykonuje Playwright (`page.screenshot()`) zamiast `pygame.image.save`.
3. Asercje `file_exists` są tłumaczone na sprawdzanie kluczy `MoM.save_<N>` w localStorage.
   Można też użyć jawnego typu `localstorage_exists` (`{"type": "localstorage_exists",
   "key": "MoM.save_0", "min_size": 50}`) w scenariuszu oznaczonym `"platform": "web"`.
4. Setup saves (corrupt/minimal) wstrzykiwane przed reloadem strony przez localStorage.

**CI:** `.github/workflows/web_agent_tests.yml` (trigger ręczny — `workflow_dispatch`)
instaluje `pygbag` + `playwright`, pobiera Chromium i uruchamia wybrane scenariusze web,
publikując `screenshots/agent/` jako artifact.

**Ograniczenia:**

- pygbag potrzebuje ~40-60s na boot (assets packaging + WASM compile) przed rozpoczęciem
  scenariusza — testy są wolniejsze niż desktop.
- Port 8001 jest używany domyślnie (konfigurowalny przez `--url`).
- Nie wspiera `USE_WEB_SIMULATOR` — web runner uruchamia prawdziwy pygbag.

## Persystencja stanu

- **Brak systemu save/load na dysk** — zamknięcie gry traci postęp (na liście TODO w README).
- **Persystencja między mapami = tylko w RAM** podczas sesji: `Scene` cache'uje stan w
  `loaded_maps` (`scene.py:158`) i `loaded_NPCs` (`scene.py:214`). Wyjście z mapy →
  `store_map()` (`scene.py:717`) robi snapshot; powrót → `restore_map()` (`scene.py:726`)
  przywraca. Wygenerowany labirynt zachowuje układ póki jest w `loaded_maps` (`scene.py:669`).
- **Śmierć gracza** (`characters.py:811`): przy `health <= 0` → `exit_state()` bieżącej sceny,
  `player.reset()` (`characters.py:1020`: pełne zdrowie, **przeładowanie startowego ekwipunku
  z configu — zebrane przedmioty przepadają**, wyczyszczenie flag), nowa `Scene("Village",
  "start")` + splash `"GAME OVER"`. To pełny respawn w wiosce, nie wczytanie zapisu.
- **Persystencja ustawień wyświetlania** (`save_load/display_settings.py`): rozdzielczość i
  stan fullscreen są zapisywane automatycznie przy każdej zmianie i wczytywane przy starcie gry.
  Desktop: `<data_dir>/mom/settings.json` (taka sama logika ścieżek jak save'y). Web:
   localStorage klucz `MoM.settings`. Format JSON z `version`, `resolution_index`, `fullscreen`
   i `resolution` (fallback px, gdyby lista opcji się zmieniła). Fullscreen jest wyłączony na
   web (`IS_WEB` wymusza `fullscreen=False` — w przeglądarce fullscreen obsługuje F11, nie SDL).
   Uwaga: `XDG_DATA_HOME` zmienia położenie pliku na macOS (testowano z XDG_DATA_HOME=~/.local/share).
   Przypadki brzegowe: uszkodzony plik → log + domyślne; index poza zakresem → clamp do max_idx.

## Konwencje

- Stałe → `settings.py`; typy wyliczeniowe → `enums.py`. Nie hardkoduj magic numbers w logice.
- Type hints wymagane (mypy strict). Nie modyfikuj vendored libów (`animation`).
- Dane gry (postacie, przedmioty) **nie** w kodzie — w configu, patrz [`config_model/AGENTS.md`](./config_model/AGENTS.md).

## Animacja sprite'ów / dodanie postaci

- Definicje klatek: `SPRITE_SHEET_DEFINITION_*` (`settings.py:484+`) → mapowanie po szerokości
  sprite'a w `SPRITE_SHEET_DEFINITIONS` (`settings.py:605`, warianty 2x1/2x2/3x3/4x7).
- Klucze animacji: `"{akcja}_{kierunek}"` (np. `run_left`, `weapon_up`).
- Kierunek liczony z kąta wektora prędkości (`get_direction_360` w `characters.py`).
- **Dodanie postaci:** assety w `assets/NinjaAdventure/...` + wpis w `config.json`
  (sprite, statystyki); jeśli nietypowy layout sheetu — dodaj definicję w `settings.py`.

## NPC: FSM i AI

- **FSM (`npc_state.py`):** `get_new_state()` (`npc_state.py:14`) wybiera stan wg priorytetu
  (stunned > dead > attacking > fly > jump > talk > run > walk > bored > idle). Nowy stan:
  podklasa `NPC_State` + warunek w `get_new_state()` + klucze animacji w sheetcie.
- **AI ruchu:** waypointy z mapy Tiled / random-walk (animals) / pościg A* (monsters,
  budzą się w `MONSTER_WAKE_DISTANCE`, `settings.py:112`). Ścieżki: `find_path()`
  (`characters.py:647`) → `a_star_cached` z `maze_generator` (`characters.py:11`).
- **Dialog i sentyment (T-023):** instancja `NPC` (`characters.py`) rozszerzona o:
  `dialog_key` (z modelu), `dialog` (bieżący `DialogNode` / kursor w grafie),
  `selected_options_dict`, `sentiment` (0–100, domyślnie 50), `disposition`
  (z modelu) oraz `known_disposition` (odkrywana przez gracza, pusta na start).
  Przy ładowaniu `load_dialogs()` buduje graf z `Config.dialogs[dialog_key]`
  przez `dialog.graph.init_dialog` i ustawia `dialog` na `START_NODE`.
  Stare pole `dialogs: str` (markdown) pozostawione bez zmian do czasu migracji.
- **Odkrywanie sentymentu (T-035):** `NPC.apply_option_sentiment(sentiment_key)`
  wyciąga wagę z `self.disposition[sentiment_key]`, dodaje do `self.sentiment`
  (clamp 0–100) i zapisuje w `self.known_disposition[sentiment_key]` = waga.
  W `DialogPanel._build_weight_indicator()`: jeśli `sentiment` jest w
  `known_disposition` — pokazuje wagę (np. `+4`), jeśli nie — `?`.
  Nad nazwą NPC rysowany jest `_draw_sentiment_indicator()`: poziomy pasek
  od czerwonego (0) przez żółty (50) do zielonego (100).
- **Handel a sentyment (T-035):** ceny zakupu i sprzedaży zależą od sentymentu
  NPC. `get_buy_price_multiplier(sentiment)` (zakres 0.5×–1.5×, clamped ≥0.1)
  i `get_sell_price_multiplier(sentiment)` (odwrotnie). Sentiment 50 → oba 1.0×.
  Cena = `round(item.value * multiplier)`.
- **Persystencja rozmowy (T-030):** pełny stan dialogu per-NPC jest zapisywany
  w save/load przez `NPCDialogState` (`save_load/models.py`): bieżący węzeł
  (`current_node_key`), `selected_options_dict`, odwiedzone węzły (`visited_nodes`),
  `sentiment` i `known_disposition`. `SaveManager` serializuje go w `NPCState.dialog_state`,
  a po loadzie `NPC.restore_dialog_state()` odbudowuje graf i przywraca kursor
  oraz flagi.

## DialogPanel (T-033)

- `ui/panels/dialog.py` renderuje aktywny węzeł grafu (`npc.dialog`) oraz
  przefiltrowane opcje spełniające warunki mini-DSL.
- Wejście hybrydowe: strzałki / drążek + `accept`, klawisze `1-9`, kliknięcia myszy.
- `ui/game_ui.py` obsługuje nawigację i rising-edge dla `up`/`down`/`accept`/`talk`,
  a `characters.py` otwiera panel gdy gracz naciśnie `talk` w zasięgu NPC.
- Zasięg rozmowy to `FRIENDLY_WAKE_DISTANCE` (`settings.py:175`); wymagana bliskość
  NPC jest sprawdzana w `scene.py` (`npc.model.attitude == friendly` i warunek dialogu).
- Przykładowy dialog: Hammer w `config.json` + spawn w `Village.tmx`;
  scenariusz testowy: `tests/scenarios.json` → "Hammer Dialog Flow".
