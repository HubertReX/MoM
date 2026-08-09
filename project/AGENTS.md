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
- **Stany:** `Scene` (`scene/scene.py`, rozgrywka na mapie), `MenuScreen` i podklasy
  (`ui/panels/main_menu.py`), `SplashScreen` (`splash_screen.py`). Przejścia ekranowe
  (fade/koło): `transition.py`.

### `FPS_CAP` i profiler sekcji klatki (`MOM_PROFILE`, E02)

`settings.FPS_CAP = 60` (`clock.tick(FPS_CAP)` w `Game.run`) - `0` istnieje dalej jako
tryb bez limitu, tylko do profilowania/benchmarków (mielenie CPU na maksa i niestabilne
`dt` na desktopie, patrz D-6). Web i tak jest throttlowany do vsync przez przeglądarkę
niezależnie od `FPS_CAP` - nie próbuj tego "naprawiać" po stronie kodu.

Profiler sekcji klatki mierzy `update`/`draw`/`flip` w `Game.run` przez `perf_counter`,
agreguje co 1 s (**avg + p95 + max** per sekcja, bez `statistics` na gorącej klatce -
tylko listy próbek czyszczone raz na sekundę) i loguje przez `self.log` (desktop `print`,
web `platform.console.log` - widoczne w konsoli JS z `#debug`). Osobno raportuje `dt`
(krok czasowy z `clock.tick`) jako **min/avg/max**, nie avg/p95 - przy `dt` liczy się
rozrzut, bo to on przekłada się na ruch i cząstki. `max` per sekcja nie jest ozdobą:
pojedynczy stall podnosi `avg` nie ruszając `p95`, więc bez niego widać tylko mylące
`avg=26.79ms p95=0.91ms`:

```bash
MOM_PROFILE=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy just run
```

Na web: ten sam kanał `MoM.env` co inne flagi testowe (A07) - `{"MOM_PROFILE": "1"}`.
Wyłączony (domyślnie) = **zero kosztu**, `Game.run` nie woła ani jednego `perf_counter`.

**Pułapka (naprawiona, nie cofaj):** `Game.__init__` wiąże `self.log` z `builtins.print`,
a NIE ze zwykłym `print`. W `game.py` `print` to `rich.print` (`from rich import print`),
które czyta `[coś]` jako znacznik stylu i po cichu go POŁYKA, gdy `coś` nie jest znaną
nazwą stylu. Póki `self.log` był richem, prefiksy `[test] ...` (`Game.__init__`) oraz
wszystkie ~40 linii `[agent_ctrl] ...` / `[agent] ...` (`agent_ctrl.py` dostaje
`log=self.log`) znikały na desktopie, choć na web (`platform.console.log`, bez markupu)
były widoczne - a nawiasy w treści tracebacka z `_show_fatal_error` były okrajane.
Jeśli kiedyś zmienisz to z powrotem na `self.log = print`, log desktopowy znów po cichu
zgubi prefiksy.

Pod tą samą flagą `map_state.go_to_map` loguje **jedną linię na zmianę mapy** z
rozbiciem kosztu na podkroki - zmiana mapy to jedna bardzo droga klatka, która w
zwykłym oknie agregacji ginie jako odstający pomiar w `update`:

```text
profile: map_change -> Maze_01 (first_load) total=  76.3ms weather_stop=0.0ms reset+player=0.8ms load_map=69.9ms particles=0.0ms audio=2.8ms quests=0.0ms autosave=2.8ms
```

To ona wykryła zamrożenie ~0,7 s przy każdym przejściu mapy (blokujące `music.load`
w trakcie fade'u) - patrz
[`doc/audyt/D01-stall-muzyki-przy-zmianie-mapy.md`](../doc/audyt/D01-stall-muzyki-przy-zmianie-mapy.md).

Gdy włączony, ostatnia zaagregowana linia dopisywana jest też do overlaya debug
(` / Z, `debug_overlay.SHOW_DEBUG_INFO`) - do TEJ SAMEJ linii `FPS: ... M: ...`
(`Scene.draw`), overlay ma zostać jednolinijkowy.

**Pułapka: nie mierz taktowania klatek w sandboxie narzędzia Bash agenta.** Tam
`clock.tick(60)` daje ~110 ms na klatkę (~9 FPS) zamiast 16,7 ms, a `tick_busy_loop(60)`
twarde 16,00 ms - co wygląda jak błąd w `clock.tick`, ale nim NIE jest: w tym samym
środowisku samo `time.sleep(1/60)` (goły Python, zero pygame i SDL) trwa ~118 ms, czyli
sandbox koalescuje krótkie sleepy. Rozpoznanie po linii profilera: gdy `update`+`draw`
+`flip` sumują się do ~2 ms, a `dt` pokazuje ~100 ms, czas ginie w sleepie limitera, nie
w grze. `clock.tick` (a nie `tick_busy_loop`) jest tu świadomym domyślnym wyborem -
`tick_busy_loop` kręci pętlę na CPU i grzeje procesor/baterię. Zwalidowane na prawdziwej
maszynie (2026-08-01, mac-mini M4, 1920x1024): `dt` = 16,00-18,00 ms, avg ~16,9 ms,
fps ~59, budżet klatki wykorzystany w ~38%. Pełne liczby i interpretacja pików:
[`doc/audyt/E02-dt-jitter-desktop.md`](../doc/audyt/E02-dt-jitter-desktop.md).
Uwaga przy czytaniu logu: `clock.tick()` zwraca pełne milisekundy, więc `dt` 16/17/18 to
kwantyzacja, nie jitter; `avg` sekcji może przekroczyć `p95`, gdy jeden stall podniesie
średnią; a stall z ostatniej klatki okna trafia do `dt max` dopiero w oknie następnym.

### `MOM_DEBUG_TALK` - logi ścieżki rozmowy

`MOM_DEBUG_TALK=1 just run` włącza gadatliwe logi ścieżki rozmowy (KEYDOWN `talk`, stan
napotkanego NPC, otwarcie `DialogPanel`) w `Game.get_inputs` i `Player.control`.
Domyślnie wyłączone. Wcześniej te `print`-y leciały **bezwarunkowo** przy każdym
naciśnięciu klawisza rozmowy i zaśmiecały log gracza oraz log testów - jeśli dodajesz
podobną diagnostykę, od razu wystaw na nią flagę zamiast zostawiać gołego `print`.

Wyniki jednorazowego profilu web (przeglądarka, maszyna, tabela per scenariusz):
[`doc/audyt/E02-profil-web-wyniki.md`](../doc/audyt/E02-profil-web-wyniki.md).

## Mapa plików rdzenia

| Plik                       | Rola                                                                                            | Uwaga                                            |
| -------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `scene/`                   | Pakiet sceny (B01): `scene.py` orkiestrator + `map_loader`, `world_clock`, `collisions`, `player_actions`, `routines_director`, `map_state`, `night_filter`, `fog_of_war`, `intro`, `debug_overlay`, `agent_api` | `from scene import Scene` bez zmian |
| `characters/`              | Pakiet postaci (B01): `npc.py` (stan `NPC`) + `player.py`, `movement.py` (A*, waypointy, fizyka), `combat.py`, `animation.py`, `inventory.py` | `from characters import NPC, Player` bez zmian |
| `ui/`                      | **Własny toolkit UI** (retained-mode, czysty pygame-ce). Patrz niżej.                           | zastąpił `ui.py`+`menus.py`+`rich_text.py`       |
| `dialog/`                  | **System dialogów** (encje grafu, builder, silnik warunków mini-DSL). Patrz niżej.              | czysta logika, bez pygame; web-safe              |
| `settings.py`              | **Wszystkie stałe** gry + definicje sprite-sheetów                                              | **30K**                                          |
| `objects.py`               | Sprite'y: `ItemSprite`, `ChestSprite`, `HealthBar`, `EmoteSprite`, `Collider`, `Notification`   |                                                  |
| `npc_state.py`             | FSM NPC (Idle/Walk/Run/Jump/Fly/Stunned/Attacking/Talk/Dead)                                    |                                                  |
| `particles.py`             | System cząstek + reżyser pogody (liście, deszcz, rozpad obiektów) — patrz sekcja niżej           |                                                  |
| `nine_patch.py`            | Skalowalne panele UI (9-patch) — używany przez `ui/theme.py`                                    |                                                  |
| `opengl_shader.py`         | Wrapper zengl do shaderów post-process                                                          | patrz [`shaders/AGENTS.md`](./shaders/AGENTS.md) |
| `camera.py`                | Viewport + zoom (steruje `map_view.zoom`)                                                       |                                                  |
| `transition.py`            | Efekty przejść (`Transition`, `TransitionCircle`)                                               |                                                  |
| `second_order_dynamics.py` | Gładkie animacje (Second Order Dynamics) — POC                                                  |                                                  |
| `enums.py`                 | Typy wyliczeniowe (Race, Attitude, ItemType, …)                                                 |                                                  |
| `save_load/display_settings.py` | Persystencja ustawień (rozdzielczość, fullscreen, język, głośności, algorytm mgły)          | desktop `settings.json`, web `localStorage`      |
| `audio.py`                 | Muzyka per mapa + SFX eventów; manifest `config_model/audio.toml` — patrz sekcja niżej           | zero importów z `scene`/`characters`/`game`      |
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
boolean-flag. Dialogi w vaultcie `doc/{PL,EN}/**/*.md` używają tagów `[bold]`/`[link URL]`/`:emoji:`
(tabela `STYLE_TAGS_DICT` w `settings.py`).

**Design system** (paleta, komponent „klawisz", cień, skalowanie, min. font): zasady w
[`ui/AGENTS.md`](./ui/AGENTS.md), pełny audyt w
[`../doc/_attachements/design-system-2026-07-18.html`](../doc/_attachements/design-system-2026-07-18.html).

## System dialogów (`dialog/`)

**Szczegółowa dokumentacja przepływu, mapy plików i znanych pułapek:**
[`dialog/AGENTS.md`](./dialog/AGENTS.md).

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

``dialog/markdown_importer.py`` reads source Markdown from the ``doc/``
Obsidian vault (``doc/PL/Postacie/`` + ``doc/EN/Characters/``; **PL is the
single source of truth**, files found by frontmatter ``aliases``) and emits
the machine-generated ``messages`` and ``character_dialogs`` sections
consumed by ``dialog.graph.init_dialog``, plus the character metadata
columns (``sprite``/``friendly``/sentiment weights) of
``config_model/characters.csv``. It uses a single named-group regex
for option lines, validates dangling references, orphan nodes, anchor/target
agreement and START presence with ``file:line`` errors, converts RPG rich
markup / emoji to MoM ``RichText`` tags (D3), and rewrites RPG conditions to
the mini-DSL understood by ``dialog.conditions``. Option sentiment is stored
under canonical author-facing names (``kind/weak/neutral/angry/smart/funny/
technical``); mapping to emote sprites (``SENTIMENT_NAME_TO_EMOTE``) happens
only at UI render time.

**Regeneracja:** ``just import-dialogs`` — kaskada MD → ``characters.csv`` →
``config.json`` (na końcu odpala ``just import-entities``, jedynego writera
sekcji ``characters``). Smoke tests: ``.venv/bin/python tests/test_dialog_import.py``.

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

### Adapter warunków (`context_adapter.py`)

``NPCConditionContext`` (w ``dialog/context_adapter.py``) łączy mini-DSL z danymi gry:

- **``visited(node_key)``** sprawdza ``DialogNode.visited`` na pełnym grafie NPC
  (``dialog_nodes[node_key].visited``), **nie** bieżącą pozycję kursora (``npc.dialog.key``).
- **Cross-NPC ``visited(dialog_key, node_key)``** szuka NPC po ``dialog_key``
  (a nie po ``name`` — wcześniej ``"BARMAN_ABSINTHRAYNER"`` vs ``"Barman Absinthrayner"``
  nigdy nie matchowało).
- **``selected(opt_key)``** czyta z ``npc.selected_options_dict`` (poprawne).
- **``has_item(key)``** przeszukuje ``player.items`` po ``item.name`` (poprawne).

**Znane bugi (fix 2026-07-08):** oryginalna implementacja ``visited()`` porównywała
``npc.dialog.key == node_key`` (bieżący węzeł, nie historię odwiedzin) i cross-NPC
używała ``other.name`` zamiast ``other.dialog_key`` — wszystkie warunki ``visited()``
zwracały ``False``, przez co:
- Potioneer_Puzzlemint: warunek ``visited("BARMAN_ABSINTHRAYNER", "012")`` zawsze failował
  → pokazywana tylko opcja "nie znam cię".
- Clapback Sword: ``visited("003") and visited("004") and visited("005")`` zawsze ``False``
  → opcja kontynuacji (prowadząca do #006) nigdy niewidoczna → dialog nie do ukończenia.
- Warunek ``visited("005")`` w pętli ``not visited("005")`` zawsze ``True`` → ekspozycje
  zawsze pokazywane, nawet po odwiedzeniu.

### Reset kursora po rozmowie

Gdy dialog kończy się na węźle ``is_final`` (lub dead-endzie z 0 widocznymi opcjami),
``game_ui.py`` woła ``NPC.reset_dialog()``, która ustawia ``npc.dialog`` z powrotem na
węzeł startowy grafu. Dzięki temu każda rozmowa zaczyna się od zaprojektowanego punktu
wejścia, a warunki węzła startowego (np. gate node ``016`` u Potioneera) decydują o dalszej
ścieżce na podstawie zapamiętanego stanu (``visited``, ``selected``, ``has_item``).

### Auto-end dla dead-endów

Gdy po przejściu do nowego węzła lista widocznych opcji jest pusta (wszystkie
odfiltrowane przez warunki), ``DialogPanel`` automatycznie ustawia stan ``on_final_node``.
Gracz widzi tekst NPC i może zamknąć panel klawiszem Accept — rozmowa nie zawisa.

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

Czysta logika — testy to samodzielne skrypty (bez pytesta, bez SDL), uruchamiane wprost
interpreterem albo hurtem przez `just test-unit`:

```bash
just test-unit dialog                              # wszystkie pliki z "dialog" w nazwie
.venv/bin/python tests/test_dialog_graph.py        # encje + builder (T-029)
.venv/bin/python tests/test_dialog_conditions.py   # silnik warunków (T-032)
.venv/bin/python tests/test_dialog_result_sink.py  # efekty węzłów + GameSink (T-034)
```

Nowy test musi trafić do listy `tests = [...]` w `main()` swojego pliku — `just test-unit`
weryfikuje to po AST i zwraca błąd, gdy któryś `test_*` nie jest nigdzie zarejestrowany.

## 🔑 KRYTYCZNE: różnice desktop ↔ web

`IS_WEB` zdefiniowane w `settings.py:130-131`. Najważniejsze rozgałęzienia:

| Obszar                  | Desktop                         | Web                     | Lokalizacja                                                            |
| ----------------------- | ------------------------------- | ----------------------- | ---------------------------------------------------------------------- |
| Config                  | `config_pydantic.py` (Pydantic) | `config.py` (dataclass, **generowany** z `config_pydantic.py` przez `just gen-web-config` — zob. `config_model/AGENTS.md`) | `if IS_WEB:` w `characters/npc.py:33`, `objects.py:19`, `ui/panels/hud.py` |
| Shadery                 | dostępne (gdy `USE_SHADERS`)    | wyłączone (wydajność)   | `USE_SHADERS=False` `settings.py:141`                                  |
| Filtr dzień-noc (alpha) | tak                             | tak (E01 — ta sama ścieżka kodu) | `scene/night_filter.py`; koszt regulowany `settings.NIGHT_FILTER_MODE` |
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
  - `debug_ui_state` - zrzuca stan gry z runtime do `agent_ui_state.json` (web: localStorage
    `MoM.agent_ui_state`) na potrzeby asercji `ui_state` - patrz "Asercje stanu" niżej.
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

# Zestaw smoke (6 scenariuszy z rozłącznych obszarów, ~4-5 min) - domyślna bramka
# po zmianie w rdzeniu, gdy pełny przebieg (~18 min) jest za drogi:
MOM_SKIP_SS_REVIEW=1 just test-smoke     # = tests/automate_display_test.py --smoke
```

Lista smoke siedzi w `TEST_CONFIG["SMOKE_SCENARIOS"]` (runner). Zmieniając ją, pilnuj
zasady "rozłączne obszary": save/load, dialog, labirynt+autosave, panele UI, ustawienia,
text input. Literówka w nazwie = twardy błąd (`--smoke` nie przemilcza brakującego
scenariusza). `--smoke` działa też z `--web`.

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

> ⚠️ Runner **przestawia `XDG_DATA_HOME` na `.test-data/` w katalogu repo** (`isolate_game_data()`
> w `automate_display_test.py`) na czas całego przebiegu. Bez tego każdy scenariusz kasował
> prawdziwe zapisy dewelopera - `cleanup_saves_before()` woła `clear_all_saves()` przed **każdym**
> scenariuszem, a „Display Settings Flow" nadpisuje `settings.json`. Sandbox jest w `.gitignore`;
> zajrzyj do niego, gdy asercja `file_exists` padnie. Opt-out: `MOM_TEST_USE_REAL_SAVES=1`
> (wtedy scenariusze **skasują** Twoje zapisy).

Pliki save na desktopie (jeśli zdefiniowano zmienną środowiskową `XDG_DATA_HOME`, zapisy trafiają do `<XDG_DATA_HOME>/mom/saves/`, w przeciwnym razie stosowane są domyślne ścieżki systemowe):

- macOS: `~/Library/Application Support/mom/saves/save_N.mom` (lub `<XDG_DATA_HOME>/mom/saves/save_N.mom`)
- Linux: `~/.local/share/mom/saves/save_N.mom` (domyślny fallback dla XDG)

Helper do manipulowania zapisami: `scripts/save_fixtures.py`:

```bash
.venv/bin/python3 scripts/save_fixtures.py clear     # usuń wszystkie save'y
.venv/bin/python3 scripts/save_fixtures.py corrupt 0 # zepsuj slot 0
.venv/bin/python3 scripts/save_fixtures.py create 0  # utwórz minimalny save
.venv/bin/python3 scripts/save_fixtures.py delete 0  # usuń slot 0

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
- `--web-restart-per-scenario` — restart pygbag + przeglądarki dla każdego scenariusza
  (zachowanie sprzed A08); używaj tylko przy podejrzeniu przeciekania stanu.

**Cykl życia (A08):** pygbag i Chromium wstają **raz na cały przebieg**
(`WebRunner.start_session()`), a scenariusz to wyczyszczenie kluczy `localStorage`,
wstrzyknięcie `MoM.env` (z `start_hour`) + `setup_saves` i `page.reload()`
(`_prepare_scenario_page()`). Reload daje świeży interpreter Pythona w świeżej instancji
WASM, więc izolacja zostaje, a build WASM (identyczny w obrębie przebiegu) płacony jest
raz: pełny web ~25 min → ~10 min. Gdy strona przestanie odpowiadać (crash WASM), runner
odbudowuje ją **raz**; drugi taki wypadek przerywa przebieg (`RunnerFatal`), żeby nie
raportować kaskady fałszywych porażek.

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

- pygbag potrzebuje ~40-60s na boot (assets packaging + WASM compile) — od A08 płacone
  raz na przebieg, ale pierwszy scenariusz nadal startuje wolniej niż na desktopie.
- Port 8001 jest używany domyślnie (konfigurowalny przez `--url`).
- Nie wspiera `USE_WEB_SIMULATOR` — web runner uruchamia prawdziwy pygbag.

### Tryb deterministyczny świata (`MOM_TEST_DETERMINISTIC`, `MOM_TEST_START_HOUR`)

Scenariusze chodzą na "żywej" grze: epizody pogody startują w losowych momentach,
NPC-e wędrują random-walkiem, seed świata jest losowy przy każdej nowej grze. Efekt:
screenshoty nieporównywalne między uruchomieniami.

| zmienna | działanie |
|---|---|
| `MOM_TEST_DETERMINISTIC=1` | stały seed świata (`settings.TEST_WORLD_SEED = 12345`), zaseedowana pogoda i cząstki, `random.seed()` na globalnym generatorze |
| `MOM_TEST_START_HOUR=0..23` | wymusza godzinę startu; **niezależne** od powyższej |
| `MOM_TEST_LIVE_WORLD=1` | opt-out w runnerze: wraca w pełni losowy świat |

**Runner włącza tryb deterministyczny domyślnie** (`apply_determinism_env` w
`tests/automate_display_test.py`) i wypisuje jedną linię `[world] ...` z wybranym trybem.
Zwykłe `just run` bez zmiennych zachowuje się dokładnie jak dotąd.

Dwie decyzje projektowe, które warto znać, zanim się to "poprawi":

- **Cząstek NIE wyłączamy.** Test na wyłączonych cząstkach sprawdzałby inną grę niż ta,
  w którą gra gracz, a scenariusz może chcieć zweryfikować właśnie emiter. Zamiast tego
  `WeatherDirector` i emitery dostają wstrzyknięty `rng` (`Scene._particle_rng()`).
- **Godziny startu NIE wymuszamy globalnie.** Gra zaczyna o 9:00 i scenariusze mają
  widzieć rutyny NPC takie jak gracz. Godzina to **opcjonalne pole scenariusza**:

  ```json
  { "name": "Sklep zamkniety w nocy", "start_hour": 21, "actions": [ ... ] }
  ```

  Runner odpala osobną instancję gry per scenariusz, więc env jest per scenariusz.
  Brak pola = zmienna jest **usuwana** z env gry (pole scenariusza jest źródłem prawdy,
  odziedziczone `MOM_TEST_START_HOUR` nie przecieka do scenariusza, który go nie chce).

Czego tryb NIE robi: nie zamraża zegara gry (scenariusze polegają na upływie czasu) i nie
daje identyczności co do piksela - spawn cząstek napędzają timery pygame, a momenty klatek
nigdy nie są równe co do milisekundy. Powtarzalna jest **sekwencja decyzji**: ten sam
emiter, te same długości epizodów, ten sam seed świata.

Tryb działa na **obu targetach** (A07). Desktop: zwykły `env` podprocesu gry. Web: gra
nie dziedziczy env runnera, więc runner wkłada te same zmienne do **jednego** klucza
`localStorage['MoM.env']` (JSON `{"MOM_TEST_DETERMINISTIC": "1", ...}`) po pierwszym
`goto()`, a **przed** `reload()` - `settings._test_env()` czyta ten klucz przy imporcie
`settings`, później byłoby za późno. Każdą kolejną zmienną testową wystarczy ustawić
w env/`MoM.env`; nie dodawaj osobnych kluczy localStorage per flaga.
`MOM_AGENT_CONTROL` przechodzi tym samym kanałem (stary klucz `MoM.agent_control`
zostaje w `game.py` tylko jako przejściowy fallback dla otwartych starych kart).

Testy mechanizmu: `tests/test_deterministic_mode.py` (zmienne czytane są przy imporcie
`settings`, więc każdy przypadek leci w świeżym subprocessie - przeładowanie modułu nie
odtworzyłoby prawdziwej kolejności).

### Asercje stanu (`debug_ui_state` + `ui_state`) — weryfikacja bez vision

Vision (ss-review) jest niedeterministyczne z natury, a większość faktów, które testy chcą
sprawdzić ("panel dialogu jest otwarty", "gracz jest na mapie BLUNDERHAVEN", "HP > 0"), gra
**zna** i potrafi zrzucić. Zasada: **fakty asertuj z runtime, vision zostaw do ocen
estetycznych**.

Scenariusz wysyła `debug_ui_state` jako osobną akcję, a potem asertuje:

```json
{ "slug": "dump_state_in_dialog", "commands": ["debug_ui_state"], "wait": 0.5 }
```

```json
{
  "type": "ui_state",
  "expect": {
    "top_state": "Scene",
    "map": "BLUNDERHAVEN",
    "open_panels_contains": ["DialogPanel"],
    "dialog.npc": "BARMAN_ABSINTHRAYNER",
    "player.hp_min": 1
  }
}
```

Trzy rodzaje kluczy w `expect` (i tylko te trzy):

- `open_panels_contains` — każda nazwa klasy panelu musi być w `open_panels`
- `<ścieżka>_min` / `<ścieżka>_max` — porównanie liczbowe pola po ścieżce z kropkami
  (`"player.hp_min": 1` znaczy `player.hp >= 1`)
- dowolny inny klucz — równość z wartością spod tej ścieżki (`map`, `is_maze`, `dialog.npc`)

Zawartość zrzutu i pułapki opisuje docstring `project/agent_ctrl.py` (sekcja
"Zrzut stanu gry"). Najważniejsze:

- działa też w menu (`top_state: "MainMenuScreen"`, pola sceny `null` — to legalny wynik);
  scena jest szukana **w dół stosu**, więc menu otwarte NAD grą nadal raportuje mapę i gracza
- `debug_ui_state` wysyłaj jako **osobną akcję**, nie w paczce z klawiszami: komendy
  klawiszowe lecą jako posted `KEYDOWN` i gra obsłuży je dopiero w następnej klatce
- brak zrzutu = twardy FAIL asercji (runner kasuje zrzut na starcie każdego scenariusza,
  więc nie da się przypadkiem asertować stanu z poprzedniego przebiegu)
- panele czytane są przez publiczne `GameUI.open_panel_names`, nie przez prywatne `_open`

Wzorcowo używają tego: `Save and Load Basic` (desktop + web), `Dialog Open Deterministic`,
`Hammer Dialog Flow`, `Dialog Option Formatting`.

> **Uwaga o determinizmie dialogów.** Scenariusze dialogowe otwierają rozmowę przez
> `talk_to_char:<key>`, nie przez dojście "w ciemno" (`left:30 up:20`) i `talk`. NPC-e
> wędrują, więc ślepa nawigacja trafiała w pustkę — a testy tego nie wykrywały, bo bez
> asercji `ui_state` sprawdzały tylko `process_alive`.

### ss-review (wizualna analiza screenshotów)

Test runner deleguje analizę screenshotów do subagenta `ss-reviewer` przez `opencode run`.
Asercja `screenshot_review` w `scenarios.json` woła `review_screenshot()` w
`automate_display_test.py`.

**Ważne zasady:**

1. **Screenshot idzie jako ZAŁĄCZNIK przez `-f`**, nie jako ścieżka inline w prompcie
   (ścieżka inline przestała działać — zmiana zachowania OpenCode, zweryfikowana 2026-07-25).
   Kolejność argumentów ma znaczenie: **message PIERWSZY, `-f` PO nim**, bo `-f` jest greedy
   (`[array]`) i połknąłby trailing positional message jako nazwę pliku
   (`Error: File not found: <twój prompt>`).
2. **Każdy model w `SS_REVIEW_MODELS` MUSI mieć vision** (`attachment: true`,
   `modalities.input: ["text","image"]`) — `-f` z modelem bez vision kończy się **błędem**,
   nie degradacją. Oba obecne modele (Gemini, mimo) vision mają; np. deepseek-v4 czy glm — nie.
3. **Primary to `google/gemini-3.1-flash-lite`**, fallback `opencode-go/mimo-v2.5`.
   Odwrotna kolejność (mimo jako primary) powodowała regularne timeouty rc=124 — runner
   czekał 60 s na martwy model przed każdym fallbackiem. Wymuszenie jednego modelu:
   `MOM_SS_REVIEW_MODEL='opencode-go/mimo-v2.5'`.
4. **Używaj `--pure`** w komendzie `opencode run`, żeby wyłączyć plugin `discover-models.js`.
   Bez tego plugin robi HTTP requesty do wszystkich providerów przy starcie, co może
   powodować logi na stderr i opóźnienia. `--pure` uruchamia opencode bez zewnętrznych pluginów.
5. **Hard timeout**: subprocess jest dodatkowo owinięty w `gtimeout` (GNU coreutils, macOS)
   lub `timeout` (Linux), żeby ubić wiszący proces gdy model discovery hanguje.
   `SS_REVIEW_TIMEOUT = 60s`.
6. **Pomiń ss-review** przez `MOM_SKIP_SS_REVIEW=1` — szybka iteracja bez vision.

Konfiguracja w `automate_display_test.py` (stałe `SS_REVIEW_*`):
```python
SS_REVIEW_AGENT = "ss-reviewer"
SS_REVIEW_MODELS: list[str | None] = ["google/gemini-3.1-flash-lite", "opencode-go/mimo-v2.5"]
SS_REVIEW_TIMEOUT = 60.0
```

**Checklisty per-scenariusz.** Asercja `screenshot_review` ma dwa opcjonalne pola, które
trafiają wprost do prompta modelu:

```json
{
  "type": "screenshot_review",
  "target": "barman_dialog",
  "expected_state": "DIALOG",
  "expect": "opis oczekiwania (pole istniejące)",
  "expected_elements": ["yellow NPC name plate", "numbered list of reply options"],
  "ui_quality_checks": ["no text overflows or touches any panel frame"]
}
```

Bez tych pól scenariusz działa jak dotąd. **Model NIE ocenia jakości UI, jeśli go o to
nie poprosisz** — ten sam model z pytaniem o overflow wykrywa wadę 2/2, bez pytania
przepuszcza. Wzorcowo wypełnione są scenariusze dialogowe (`Hammer Dialog Flow`,
`Dialog Option Formatting`, `Dialog Open Deterministic`); do reszty dopisujemy przy okazji.

Pisząc checklistę pamiętaj, że model **nie zna** encji gry: nie każ mu rozstrzygać, który
portret należy do NPC, a który do gracza (gracz to zielony `GreenNinja`, barman to rudy
`Hunter` — model zgaduje odwrotnie), ani nie wpisuj angielskiej nazwy NPC, gdy gra chodzi
po polsku. Sprawdzalne jest to, co widać bez wiedzy o świecie: obecność elementu, jego
położenie na ekranie, przepełnienia, literalne tagi markupu.

**Werdykt jest parsowany z JSON.** ss-reviewer kończy odpowiedź fenced blokiem
`{"verdict": "PASS"|"FAIL", "state": "...", "failed_checks": ["..."]}`; runner czyta go
przez `parse_review_json()`, a `failed_checks` ląduje w logu i w komunikacie błędu asercji.
Stary regex po markdownie (`parse_review_verdict()`) został jako fallback dla modeli,
które nie wyprodukowały bloku JSON.

## Persystencja stanu

- **Save/load na dysk ISTNIEJE** — sloty zapisu, quick save/load (F5/F9), autosave przy
  wejściu do labiryntu; desktop pisze pliki `<data_dir>/mom/saves/save_N.mom`, web
  localStorage (klucze `MoM.save_N`). Kod: pakiet `save_load/` (`manager.py` buduje
  i przywraca `SaveGame`, `models.py` to schemat z wersją, `backends.py` wybiera
  plik vs localStorage), UI w `ui/panels/save_load.py`. Zachowanie przypięte
  scenariuszami agentowymi w `tests/scenarios.json` ("Save and Load Basic",
  "Corrupt Save Handling", "Maze Save Blocked", ...).
  Poniższe punkty opisują to, co **poza** tym systemem trzyma stan w RAM.
- **Wersjonowanie zapisów — JEDEN numer.** Wersja zapisu to wersja gry
  (`settings.VERSION`, string `"MAJOR.MINOR"`); nie ma osobnego numeru schematu, bo
  gracz zna wersję gry, a numeru schematu nigdy by nie zobaczył. Porównania idą przez
  `version_code()` (`"0.3"` → 3, `"1.3"` → 103; `MAJOR*100+MINOR`, MINOR w 0-99, brak
  poziomu patch w kontrakcie zapisu). Stare pliki trzymają `version` jako `float` —
  czytane przez `str()`, więc `0.3` → `"0.3"` → ten sam kod.
  - `save_compatibility()` (`save_load/models.py`) to **jedyne** miejsce decydujące,
    czy zapis się wczyta: `ok` / `too_old` / `from_future` / `unreadable`.
  - Migracja jest kluczowana wersją, w której **zmienił się format**
    (`@_register_migration("1.4")`), nie każdym wydaniem — wydanie bez zmiany formatu
    nie potrzebuje żadnego wpisu. Dzięki temu wspólny numer jest do utrzymania.
    Punkt wpięcia: `SaveSlot.from_dict`, na surowym dictcie, przed `SaveGame.from_dict`
    (`from_dict` jest tolerancyjny, więc po deserializacji nie ma już czego migrować).
    `migrate_save` nigdy nie rzuca i nie loguje — biegnie dla 10 slotów przy każdym
    otwarciu panelu. Nietknięta wersja = odmowa; stempel = sukces.
  - **Przed 1.0** `MIN_SUPPORTED_SAVE_CODE == CURRENT_SAVE_CODE` i `_MIGRATIONS` jest
    puste: starsze zapisy są odrzucane z komunikatem. **Od 1.0** stała zamarza na `100`
    i każda zmiana formatu jedzie z migracją.
  - Migracji **nie trzeba** przy dodaniu pola z wartością domyślną (przypadek domyślny:
    `NPCState.config_key`, `SaveGame.world_seed`, `SaveMetadata.migrated_from`).
    **Trzeba** przy zmianie nazwy, usunięciu pola, zmianie znaczenia lub typu.
  - Zapisu nie do odczytania gra nigdy nie kasuje: slot zostaje na liście, wyszarzony,
    z wersją i powodem zamiast daty; gracz może go usunąć (`D`) albo nadpisać. Odmowa
    wczytania nie rusza stanu gry (nie zwija stosu na ekranie śmierci).
- **Lista kontrolna przy podbiciu `VERSION`:** (1) czy zmienił się format zapisu — jeśli
  tak i jesteśmy po 1.0, dopisz migrację kluczowaną nową wersją; (2) przed 1.0 podbij
  `MIN_SUPPORTED_SAVE_CODE` razem z `VERSION`; (3) zaktualizuj `CURRENT_VERSION`
  w `scripts/save_fixtures.py` (pilnuje tego test `fixture version in sync`).
- **Persystencja między mapami w obrębie sesji = w RAM**: `Scene` cache'uje stan w
  `loaded_maps` (`scene/scene.py:102`) i `loaded_NPCs` (`scene/scene.py:202`). Wyjście z mapy →
  `store_map()` (`scene/map_state.py:75`) robi snapshot; powrót → `restore_map()`
  (`scene/map_state.py:83`) przywraca. Wygenerowany labirynt zachowuje układ póki jest w `loaded_maps`.
- **Śmierć gracza** (`characters/combat.py`, `die()`): przy `health <= 0` → `exit_state()` bieżącej sceny,
  `player.reset()` (`characters/npc.py:694`: pełne zdrowie, **przeładowanie startowego ekwipunku
  z configu — zebrane przedmioty przepadają**, wyczyszczenie flag), nowa `Scene(START_MAP,
  "start")` + splash `"GAME OVER"`. To pełny respawn w wiosce, nie wczytanie zapisu.
- **Persystencja ustawień** (`save_load/display_settings.py`): rozdzielczość, fullscreen,
  wybrany język (`LANG`) i trzy głośności są zapisywane automatycznie przy każdej zmianie
  i wczytywane przy starcie gry. Desktop: `<data_dir>/mom/settings.json` (taka sama logika
  ścieżek jak save'y). Web: localStorage klucz `MoM.settings`. Format JSON z `version`,
  `resolution_index`, `fullscreen`, `language`, `volume_master`/`volume_music`/`volume_sfx`
  i `resolution` (fallback px, gdyby lista opcji się zmieniła). Nowe pola dochodzą
  **z wartością domyślną w `_parse_settings`**, bez podbijania `CURRENT_VERSION` -
  podbicie kasuje cały plik gracza, więc razem z głośnościami wyleciałaby rozdzielczość.
  Fullscreen jest wyłączony na web (`IS_WEB` wymusza `fullscreen=False` — w przeglądarce
  fullscreen obsługuje F11, nie SDL). Język jest od razu stosowany w runtime przez
  `get_msg()` (dynamiczny lookup przez `settings.LANG`), a dialogi z postaciami używają
  wiadomości w wybranym języku z dwujęzycznego `messages` dicta (PL+EN).
  Uwaga: `XDG_DATA_HOME` zmienia położenie pliku na macOS (testowano z XDG_DATA_HOME=~/.local/share).
  Przypadki brzegowe: uszkodzony plik → log + domyślne; index poza zakresem → clamp do max_idx.

## Filtr dnia i nocy (`scene/night_filter.py`)

Cykl dobowy jest **jedną ścieżką kodu na desktopie i na web** (E01) - w tym module nie
ma i nie może być gałęzi `IS_WEB`. `Scene.draw` woła `apply_time_of_day_filter` bez
żadnego warunku platformowego; wnętrza (`not outdoor and not is_maze`) filtra nie mają,
a labirynt ma noc zawsze.

Trzy rzeczy trzymają koszt w ryzach:

- **Wczesne wyjście** przy `day_night_ratio(scene) == 0.0` (pełny dzień, 9:00-17:00 poza
  labiryntem). `DAY_FILTER` ma alfę 0, więc cała reszta była no-opem za 0,49 ms - desktop
  `draw` w dzień spadł z 1,27 do 0,76 ms.
- **Cache skalowanych kół świateł** (`_scaled_circle`, klucz = skala kwantowana do 0,05).
  Wcześniej `transform.scale_by` leciało na KAŻDEGO NPC w KAŻDEJ klatce.
- **Bufory alokowane raz** (`build_filter_surfaces`, wołane z `Scene.__init__` **i**
  `Scene.on_resize` - jedno miejsce, bo buforów jest kilka i rozjazd przy zmianie
  rozdzielczości kończy się wyjątkiem w `transform.scale`).

`day_night_ratio()` jest jedynym źródłem rozkładu godzin - czyta je i filtr rastrowy,
i `get_lights()` dla shaderów (kontrakt K3).

### `settings.NIGHT_FILTER_MODE` - pokrętło jakość/FPS

Na WASM koszt filtra to **wyłącznie liczba pikseli mieszanych per-pixel-alfą**: skalowanie
powierzchni filtra to 0,4 ms, wszystkie światła 0,3 ms, a `screen.blit` pełnoekranowej
powierzchni z alfą 5,8 ms. Dlatego `FILTER_SCALE` niczego tu nie ratuje i istnieją trzy
tryby kompozycji (zmierzone na pygbag, 1280x720, sam koszt złożenia klatki):

| tryb | koszt na web | wygląd |
| --- | --- | --- |
| `"overlay"` (domyślny) | 5,8 ms | referencyjny - ciemność z aureolami wokół postaci |
| `"overlay_half"` | 1,8 ms | ten sam efekt, świat na czas nocy ma 2x grubszy piksel (UI zostaje ostre) |
| `"multiply"` | 3,5 ms | jeden mnożący `fill`, **bez aureoli** - scena ciemnieje równomiernie |

Na desktopie różnice są nieistotne (cała klatka `draw` to ~1,25 ms w nocy), więc to
pokrętło pod słabszy sprzęt i przeglądarkę. Tryb czytany jest **żywo** z modułu
`settings` (K6), nie importem wartości.

**Pułapka dual-target:** pygame w buildzie web jest starsze niż pygame-ce na desktopie -
`screen.blit(surface)` bez `dest` wywala tam grę (`TypeError: function missing required
argument 'dest'`) przy pierwszej klatce nocy. Zawsze podawaj pozycję.

Scenariusz agentowy: **Night Filter On Blunderhaven** (`start_hour: 20`, dojście
`walk_to_point` pod kapliczkę na północ od wioski, gdzie las jest realnie czarny -
w centrum wioski dwa światła z waypointów `intro` rozświetlają prawie cały kadr).

## Mgła wojny w labiryncie (`scene/fog_of_war.py`, E03)

W labiryncie kafel ma **trzy** stany widoczności, nie dwa. Wszystkie trzy to trzy
wartości alfy w JEDNEJ masce o rozdzielczości **jeden piksel na kafel**:

| stan | alfa | co widać |
| --- | --- | --- |
| nieodkryty | `FOG_ALPHA_UNSEEN` = 255 | czerń, tileset niewidoczny |
| odkryty, poza wzrokiem | `FOG_ALPHA_REMEMBERED` = 230 | to samo, co cały labirynt przed E03 (alfa `NIGHT_FILTER`) |
| w zasięgu wzroku | gradient `FOG_ALPHA_CLEAR` (0) → `FOG_ALPHA_VISIBLE_EDGE` (175) | rdzeń nietknięty, gaśnięcie do granicy zasięgu |

**Warunek twardy:** mgła NIE dokłada drugiego pełnoekranowego `transform.scale`. Zamiast
`filter_surf.fill(color)` leci `fog_of_war.compose()`, czyli wycinek maski dla widoku
(~24x14 px) przeskalowany do rozmiaru powierzchni filtra (160x90 px). Dalej idzie ta sama
kompozycja co w E01. Koszt (desktop, poziom 4 = 78x60 kafli): cała nakładka 0,561 ms bez
mgły → 0,572 ms z mgłą kafelkową → 0,699 ms z raycastem. Na web (pygbag, 1280x720)
`draw` rośnie o ~0,3 ms (4,75 → 5,05 ms przy budżecie 16,7 ms).

### Dwa algorytmy, wybór w SettingsMenu

`settings.FOG_ALGORITHM` czytane **żywo** (K6), bo to pokrętło gracza: `"off"` (dzisiejsza
wieczna noc z aureolami przez ściany), `"raycast"` (wielokąt widzenia w pikselach - gładka
krawędź cienia, zza rogu wychyla się wąski klin), `"shadowcast"` (recursive shadowcasting
na kaflach - krawędź po kaflach, ~13x tańszy). Wybór trzyma
`save_load/display_settings.py` (pole `fog_algorithm`, **bez** podbicia `CURRENT_VERSION` -
niezgodna wersja zwraca całe ustawienia domyślne i skasowałaby rozdzielczość i głośności).
Cała reszta nastaw to stałe `FOG_*` w `settings.py` - fine tuning bez UI.

### Potwory jako źródła światła

W labiryncie aureole z `night_filter` są zastąpione mgłą, także dla NPC. Świecą
**tym samym algorytmem** co gracz, ale tańszymi nastawami (`FOG_NPC_*`: zasięg 3 kafle,
60 promieni, 2 pierścienie) i tylko te w kadrze - maksymalnie `FOG_NPC_MAX_LIGHTS` (3)
najbliższych graczowi. Dzięki temu koszt klatki nie zależy od poziomu labiryntu
(poziom 4 to 7 potworów + boss).

**Decyzja D7 (autor, 2026-08-02):** potwór świeci też w korytarzu, w którym gracz nigdy
nie był - "słyszy echo kroków", a narastająca poświata zbliżającego się potwora jest
ważniejsza niż czystość zasady. Ale świeci **ulotnie**: bit w `discovered` ustawia
wyłącznie gracz, więc kafel zwalniany z widoczności wraca do `FOG_ALPHA_REMEMBERED` tylko
wtedy, gdy gracz go widział, a w przeciwnym razie do `FOG_ALPHA_UNSEEN`. Jedna wartość dla
obu przypadków zostawiłaby na mapie ślad potwora jako fałszywą "pamięć".

Aggro potworów jest **nietknięte**: `movement_monster` dalej rusza w stronę gracza po samym
dystansie (`MONSTER_WAKE_DISTANCE` = 100 px = 6,25 kafla), także przez ścianę. Ponieważ to
więcej niż zasięg wzroku (5 / 4 kafle), potwór zawsze zaczyna iść, zanim gracz go zobaczy -
to jest zamierzone.

### Pułapki

- **Czarne kwadraty.** Kafle wnętrza bloku ściany i wnęki (podłoga zamknięta z 3 stron -
  typowo nisza na skrzynię) nie zostaną trafione żadnym promieniem. `_expand_surfaces`
  dolewa im jasność z sąsiedztwa; **tylko** kaflom "powierzchni" - dolanie zwykłej podłogi
  zdradza korytarz za ścianą. To wracało w prototypie trzy razy z rzędu, stąd
  `just fow-prototype --selftest` (licznik ciemnych kafli w jasnym otoczeniu).
- **Kolejność malowania wielokątów.** `draw.polygon` nie miesza, tylko nadpisuje, więc przy
  kilku obserwatorach maluje się POZIOMAMI: najpierw najciemniejszy pierścień wszystkich,
  potem kolejny, na końcu rdzenie. Per obserwator - ciemny pierścień potwora wymazuje
  jasny rdzeń gracza.
- **Tryb `multiply`** nie czyta powierzchni filtra (to sam `fill(BLEND_RGB_MULT)`), więc
  mgły nie da się w nim narysować. W labiryncie z mgłą kompozycja idzie `overlay_half`.
- **Stan mieszka na `scene.fog`** i jest w `MAP_PROPERTIES` - bez tego zejście piętro
  niżej i powrót kasowałoby odkryty teren. `clear_maze_cache()` (leci przy każdym
  ładowaniu mapy i zniszczeniu ściany) czyści tylko cache ścieżek A* i mgły nie dotyka.
- **Geometria czytana żywo** z `scene.path_finding_grid`, nie z kopii - rozwalona ściana
  natychmiast przepuszcza wzrok, bez inwalidacji czegokolwiek.

Scenariusze agentowe: **Fog Of War Maze** (trzy stany na jednym zrzucie + asercja
`fog_algorithm` / `fog_discovered_pct` z `debug_ui_state`) i **Maze Persists Across Save
Load** (mgła po wczytaniu). Testy jednostkowe: `tests/test_fog_of_war.py`,
a persystencja per mapa w `tests/test_save_load_multi_map.py`.

## Audio (`audio.py` + `config_model/audio.toml`)

Jedno wejście do dźwięku dla całej gry (D01). Reszta kodu woła **fasadę modułową** -
`audio.play_sfx("coins")`, `audio.play_music("BLUNDERHAVEN")` - i nigdy nie przekazuje sobie
referencji do managera ani nie zna nazw plików.

- **Manifest**: `project/config_model/audio.toml` (ręcznie edytowany TOML, jak
  `routines.toml`). `[music]` mapuje **nazwę mapy** (plik `.tmx` bez rozszerzenia) albo
  jeden z trzech kontekstów `main_menu` / `maze` / `death` na plik z `assets/audio/music/`.
  `[sfx]` mapuje **nazwę eventu** na plik z `assets/audio/sfx/`. `[music.settings]` trzyma
  `fade_ms` (crossfade) i `volume` (mnożnik pliku względem suwaka muzyki).
  Mapa **bez wpisu = cisza, nie błąd** - nowa mapa nie może wywalić gry.
- **Walidacja**: `just validate-world` → `check_audio_manifest`. Twardy błąd, gdy: plik
  z manifestu nie istnieje, klucz muzyki to ani mapa, ani kontekst specjalny, event
  w manifeście nie jest nigdzie wołany, albo `play_sfx("x")` nie ma wpisu w manifeście.
  Walidator czyta literały z nawiasu wywołania, więc **napis w warunku** rozpisujemy na
  dwie gałęzie (`if ...: play_sfx("a") else: play_sfx("b")`), zamiast `play_sfx("a" if
  x == "Player" else "b")` - inaczej `"Player"` zostanie wzięte za klucz eventu.
- **Tryb no-op**: brak karty dźwiękowej, `SDL_AUDIODRIVER=dummy`, CI, zepsuty manifest -
  każdy wyjątek gasi audio (`available = False`) i od tej pory wszystko jest ciche.
  Nic w `audio.py` nie ma prawa wywalić gry; nieznany klucz SFX to linia w logu, nie wyjątek.
- **Web: bramka gestu.** Przeglądarka odrzuca odtwarzanie przed pierwszym gestem gracza
  (`NotAllowedError`), a pygbagowe „will retry" nie działa - sprawdzone sondą w D01.
  Dlatego na web manager startuje zablokowany i **nie woła miksera w ogóle**; odłożony
  utwór rusza z `audio.unlock()`, wołanego z `Game.get_inputs` przy pierwszym
  `KEYDOWN`/`MOUSEBUTTONDOWN`/`JOYBUTTONDOWN`. Samo zdarzenie pygame nie wystarcza:
  runner testowy wstrzykuje syntetyczne `KEYDOWN` przez `pygame.event.post`, których
  przeglądarka nie uznaje - drugą bramką jest więc `navigator.userActivation.hasBeenActive`
  (`game._browser_user_activated`).
- **`mixer.music.get_busy()` na web kłamie** (zwraca `False` mimo grającego utworu).
  „Co teraz gra" trzyma `AudioManager._current_key`, nigdy pygame.
- **Głośności**: master / muzyka / SFX, po 0.0-1.0, krok 10%, trzy wiersze w
  `SettingsPanel` cyklowane strzałkami (jak rozdzielczość). Efektywna głośność to
  `master * kanał` (muzyka dodatkowo × `[music.settings].volume`). Zapisywane w
  `display_settings.py` - to ustawienie gracza, **nie** stan świata, więc nie ma go w save'ach.
- **Budżet rozmiaru**: całe `project/assets/audio/` ≤ **10 MB** (dziś 5,9 MB), muzyka
  ≤ 1,5 MB na utwór. Pygbag pakuje `assets/` w całości - `web.zip` urósł z 1,3 MB do
  7,1 MB. Konwersja i licencje: `project/assets/audio/SOURCES.md`.

## Klucz encji vs nazwa wyświetlana (C02)

Każda encja - także **mapa** - ma **klucz** (`LOST_CORK_TAVERN`, `Player`, `FISH_RED`),
którym posługują się dane, kod i dokumenty w Obsidianie, oraz **nazwę wyświetlaną**,
która jest tłumaczona i którą widzi gracz. Te dwie warstwy nie wymieniają się rolami:

- **Klucz nigdy nie trafia na ekran.** Nazwa mapy dla HUD-a siedzi w sekcji `[map]`
  plików `assets/locale/PL.toml` i `EN.toml`, kluczowana kluczem mapy (stem `.tmx`
  albo poziom labiryntu `MAZE_NN`). Źródłem napisów są dokumenty lokacji
  (`doc/PL/Lokalizacje/`, `doc/EN/Locations/`): nazwa pliku = napis, alias = klucz.
  Nowa mapa bez wpisu w obu językach = **błąd** `just validate-world` (reguła 12).
- **Napis nigdy nie służy za test tożsamości.** Bohatera rozpoznajemy przez
  `npc.config_key == PLAYER_CONFIG_KEY`, a nie przez `model.name_EN == "Player"` -
  inaczej wpisanie "Gracz" w kolumnę `name_PL` po cichu wyłącza walkę, śmierć
  i dźwięki gracza. `tests/test_map_display_names.py` pilnuje, że kod do tego nie wraca.
- **`NPC.name` ≠ `NPC.config_key`.** Pierwsze to nazwa obiektu Tiled (pod nią zapisuje się
  stan), drugie to klucz z `config.json` (pod nim żyją dialogi, questy i model).
- Napis czytamy na żywo: `_("map.<klucz>")` sięga po bieżące `settings.LANG`, więc zmiana
  języka działa bez restartu. Nie domykaj języka przez `from settings import LANG`,
  a cache w panelu kluczuj **wyrenderowanym napisem**, nie kluczem encji.

### Ściąga: gdzie używam jakiego klucza

Reguła w jednym zdaniu: **wszystko, co jest encją - postać, mapa, skrzynia, punkt wejścia -
nosi klucz `SCREAMING_SNAKE`**. Wyjątkiem są *miejsca wewnątrz mapy* (`house_bart`), bo nie
są encjami, tylko punktami na mapie; piszemy je małymi i zawsze z prefiksem mapy.

Nową **postać fabularną** dodaję w tej kolejności:

| # | Gdzie | Co wpisuję | Przykład |
| --- | --- | --- | --- |
| 1 | Obsidian: `doc/PL/Postacie/*.md` | frontmatter `aliases` = klucz encji | `BARMAN_ABSINTHRAYNER` |
| 2 | `config_model/characters.csv` | kolumna `key` = ten sam klucz; `sprite` = nazwa folderu z paczki | `BARMAN_ABSINTHRAYNER`; `Hunter` |
| 3 | Tiled: `maps/tilesets/CharacterTileset.tsx` | własność `model_name` na kaflu = ten sam klucz | `BARMAN_ABSINTHRAYNER` |
| 4 | Tiled: warstwa `spawn_points` | nazwa obiektu = klucz (sufiks `_NN` dopiero przy drugiej kopii) | `FISH_RED_01` |
| 5 | `characters.csv`, kolumny miejsc | `KLUCZ_MAPY:miejsce` - zawsze z prefiksem | `LOST_CORK_TAVERN:bar` |
| 6 | `characters.csv`, kolumna `routine` | nazwa rutyny z `routines.toml` | `barman` |
| 7 | dialogi i questy | ten sam klucz w `visited(...)`, `dialog_key` | `visited("BARMAN_ABSINTHRAYNER", "012")` |

Nową **mapę**:

| # | Gdzie | Co wpisuję | Przykład |
| --- | --- | --- | --- |
| 1 | Obsidian: `doc/EN/Locations/` + `doc/PL/Lokalizacje/` | para plików z szablonu, `aliases` = klucz mapy | `BLUNDERHAVEN` w „Blunderhaven.md" i „Gafowo Kolonia.md" |
| 2 | `maps/<KLUCZ>.tmx` | **nazwa pliku JEST kluczem mapy** | `LOST_CORK_TAVERN.tmx` |
| 3 | mapa źródłowa, warstwa `interactions` | obiekt o nazwie klucza mapy docelowej + `to_map` + `destination_entry_point` | `LOST_CORK_TAVERN`, `destination_entry_point=Door` |
| 4 | mapa docelowa, warstwa `entry_points` | obiekt wskazany w kroku 3 oraz zawsze `start` | `Door`, `start` |
| 5 | `config_model/audio.toml`, `[music]` | klucz = klucz mapy (brak wpisu = cisza + WARN) | `LOST_CORK_TAVERN = "…ogg"` |
| 6 | `assets/locale/PL.toml` i `EN.toml`, `[map]` | **napis dla gracza** - bez niego HUD pokaże klucz | `LOST_CORK_TAVERN = "Tawerna Brakująca klepka"` |

Rejestru map nie prowadzi żaden plik danych: `scene/map_registry.py` **wylicza** go ze stemów
`.tmx` plus `MAZE_01…MAZE_0N` dla N wierszy `maze_configs.csv` (D13). Nowa mapa istnieje
w chwili, w której powstaje jej plik.

Nowe **miejsce** (cel rutyny): obiekt w warstwie `places` (małymi, `house_smith`), a odwołanie
w `characters.csv`/`routines.toml` **zawsze** z prefiksem: `BLUNDERHAVEN:house_smith`. Miejsce
nie musi być unikalne w całej grze - dwie tawerny mogą mieć swój `bar`, prefiks to rozstrzyga.

### Zmiana nazwy encji: `just rename-entity`

Klucz encji żyje w kilku plikach naraz, więc rename robi się narzędziem, nie edytorem:

```bash
just rename-entity Village BLUNDERHAVEN        # rodzaj klucza wykryty z danych
just rename-entity Snake_01 SNAKE --kind instance
just rename-entity Village BLUNDERHAVEN --dry-run
just rename-entity --list                      # co dziś istnieje, per rodzaj
just rename-entity --sources                   # manifest plików, które skrypt zna
```

Rodzaje: `character`, `map`, `instance`, `chest`, `entry_point`, `place`, `item`. Skrypt jest
**dosłowny** - wie, w którym polu którego pliku żyje dany rodzaj klucza, więc rename modelu
`HORSE` nie rusza kolumny `name_EN` o tej samej treści. Mapę przemianowuje razem z plikiem
`.tmx` (`git mv`). Na koniec sam odpala `validate_world`.

**Zasięg nazwy.** `character`, `map`, `chest` i `item` są kluczami **globalnymi** - jeden
w całej grze. `instance`, `entry_point` i `place` są unikalne **tylko w obrębie jednej mapy**
(ładowarka trzyma je w słownikach per scena), więc dwie tawerny mogą mieć swój `bar` i swoje
`Door`. Stąd obowiązkowy prefiks mapy w odwołaniach do miejsc (D3), a `--list` dopisuje przy
nich mapę, **która je definiuje** - nie tę, która się do nich odwołuje.

Czego rename **nie** rusza i nie powinien:

- **zapisów gry** - stan NPC-a i skrzyni jest kluczowany nazwą obiektu Tiled, więc rename
  ten stan kasuje (O1). Polityka jest w D9: podbicie `settings.VERSION` = jawna odmowa
  wczytania starego zapisu, zamiast cichego resetu.
- **kodu** - mapa startowa mieszka w `settings.START_MAP`, klucz gracza w
  `settings.PLAYER_CONFIG_KEY`. Nowa nazwa encji w Pythonie = nowa stała w `settings.py`,
  nie nowy glob w skrypcie.
- **dokumentów w Obsidianie** - klucz jest tam aliasem we frontmatterze i bywa nazwą pliku,
  a treść należy do autora. Zamiast edytować, skrypt **wypisuje na koniec listę plików
  z `doc/`, w których stara nazwa jeszcze stoi**. Bez ich poprawienia pierwszy
  `just import-*` cofnie zmianę w `config.json` - dotyczy zwłaszcza `item`, bo klucze
  przedmiotów siedzą w warunkach `has_item("…")` dialogów i questów.

`tests/test_rename_entity.py` failuje w dniu, w którym ktoś doda plik danych nieobjęty
manifestem `SOURCES` - a nie przy pierwszym rename'ie po nim (D17). Nowy plik trzeba albo
objąć globem, albo wpisać do `UNTOUCHED_SOURCES` z powodem.

### Czego pilnuje `just validate-world` w sprawie kluczy (reguły 13-19)

- **13** - nazwa obiektu w `spawn_points` to klucz modelu, opcjonalnie z `_NN`
  (`FISH_RED_01`). Numer należy się instancji dopiero wtedy, gdy kopii na mapie jest
  więcej niż jedna - nadmiarowy numer to WARN.
- **14** - wyjście w `interactions` musi mieć `to_map` i `destination_entry_point`
  wskazujący obiekt z warstwy `entry_points` **mapy docelowej** (dla labiryntu: z szablonu
  `assets/MazeTileset/MazeTileset_Ninja.tmx`), a `return_entry_point` - obiekt na mapie,
  na której stoi. Obiekt `obj_type="chest"` musi nazywać klucz z `config.chests`.
- **15** - miejsce zawsze z prefiksem mapy: `BLUNDERHAVEN:well`, także wewnątrz jednej
  mapy. Dotyczy kolumn `home`/`work`/`social`/`hobby` i celów `location:` w `routines.toml`.
- **16** - `model_name` na kaflu tilesetu musi być kluczem postaci. Kafel bez spawnu jest
  niewidoczny dla reguły 1 i czeka uśpiony na `KeyError` przy pierwszym użyciu w Tiled.
- **17** - każde odwołanie do mapy (`to_map`, prefiks miejsca, cel rutyny) wskazuje klucz
  z rejestru `scene/map_registry.py`. Mapa nie „istnieje" dlatego, że istnieje plik `.tmx` -
  poziom labiryntu pliku nie ma.
- **18** (WARN) - mapa bez muzyki, mapa nieosiągalna z żadnej warstwy `interactions`,
  plik w `assets/audio/music/` bez wpisu w `audio.toml`.
- **19** - klucz przedmiotu znaczy to samo we wszystkich źródłach: `items.csv` ↔
  `config.json:items` (rozjazd = zapomniane `just import-entities`), `item_name` na kaflu
  `items/items.tsx` musi być kluczem z configu (`load_items` woła `conf.items[name]`, więc
  literówka wywala grę przy wczytaniu mapy), każdy przedmiot musi mieć sprite'a
  w `ITEMS_SHEET_DEFINITION` albo `GEMS_SHEET_DEFINITION`, a `chests.csv` (źródło, nie
  wynik importu) nie może wymieniać nieistniejącego przedmiotu. Reguła 6 sprawdza tylko
  *odwołania* do `config.items`, więc rozjazd samego configu z CSV był dotąd niewidoczny.

## Konwencje

- Stałe → `settings.py`; typy wyliczeniowe → `enums.py`. Nie hardkoduj magic numbers w logice.
- Type hints wymagane (mypy strict). Nie modyfikuj vendored libów (`animation`).
- Dane gry (postacie, przedmioty) **nie** w kodzie — w configu, patrz [`config_model/AGENTS.md`](./config_model/AGENTS.md).

## System cząstek i pogoda (`particles.py`)

Emitery cząstek dzielą się na **pogodę** (liście, deszcz — sterowane epizodycznie
przez `WeatherDirector`) i **jednorazowe efekty** (rozpad niszczonych obiektów).
Globalny wyłącznik: `USE_PARTICLES` (`settings.py`). Cząstki renderują się przez
`emit()` w `Scene.draw()` **bezwarunkowo**; flaga i reżyser sterują tylko *spawnem*.

**Architektura:**

- `ParticleImageBased` — silnik jednego emitera. Spawn napędza timer pygame
  (`custom_event_id`), uzbrajany/rozbrajany jawnie przez `start()` / `stop()`
  (`set_timer(event, 0)` = stop). Timer **nie** startuje w `__init__` — robi to reżyser.
- `ParticleSystem` (ABC) — kontrakt: `add()` / `emit(dt)` / `start()` / `stop()`.
  Implementacje: `ParticleLeafs`, `ParticleRain`, `ParticleDestructible`.
- `WeatherDirector` — planuje pogodę jako **losowe epizody** (idle → aktywny emiter →
  idle), zamiast ciągłego spawnu. Tykany co klatkę z `Scene.update()`.

**Grupy wykluczające:** każdy emiter ma `group` (`EmitterSchedule.group`). W obrębie
jednej grupy naraz aktywny jest **tylko jeden** emiter. `leafs` i `rain` są w grupie
`"sky"` → **nigdy nie grają jednocześnie**. Emiter w innej grupie działa **równolegle**
(niezależny cykl). Nowy równoległy efekt (np. mgła, świetliki) = nowa nazwa grupy.

**Konfiguracja — `EMITTER_SCHEDULES` w `settings.py`** (jedyna powierzchnia strojenia):
dataclass `EmitterSchedule(group, weight, active_min/max, gap_min/max)`. `weight` =
względna szansa wyboru w grupie; `active_*` = długość epizodu (s); `gap_*` = przerwa
między epizodami (s). Dodanie emitera: wpis w `PARTICLES` (klasa) **+** wpis w
`EMITTER_SCHEDULES` (harmonogram) **+** nazwa w property `particles` mapy `.tmx`.

**Allow-list per mapa:** `Scene.load_particles()` czyta property `particles="leafs,rain"`
z `.tmx` (dziś tylko `BLUNDERHAVEN.tmx`; reszta `n/a`), tworzy emitery i przekazuje te, które
mają wpis w `EMITTER_SCHEDULES`, do nowego `WeatherDirector`. Reżyser jest częścią stanu
mapy (`store_map`/`restore_map`), a `go_to_map()`/`reload_map()` wołają `weather.stop_all()`
przed przebudową, żeby nie przeciekały uzbrojone timery między mapami.

**Rozpad obiektów (`ParticleDestructible`)** działa **poza** reżyserem i flagą pogody:
`scene/collisions.py:115` przy zniszczeniu krzaka/kamienia woła `add()` bezpośrednio; `start()/stop()`
to no-opy. To jednorazowy wystrzał cząstek, nie cykl.

**Pułapka (przezroczystość):** `emit()` blituje z `special_flags=pygame.BLEND_ALPHA_SDL2`.
Przy zwykłym blicie i `set_alpha(255)` (czyli każdy emiter z `alpha_speed = 0.0` - np.
`particle_destruct`) SDL wybiera ścieżkę "copy" i wpisuje alfę **źródła** do celu, robiąc
w `game.canvas` całkowicie przezroczystą dziurę - na ekranie czarny prostokąt wokół
sprite'a. Emitery, które zanikają (alfa < 255 już w pierwszej klatce), nigdy tam nie
trafiają, więc psuł się **tylko** sprite rozpadu w miejscu.

**Wymagana siła broni:** `DESTRUCTIBLE_MIN_DAMAGE` (`settings.py`) mapuje `destruct_type`
(property kafla w `Nature.tsx`) na minimalny `damage` broni. Za słaba broń nie niszczy
obiektu, tylko wystawia toast `notify.weapon_too_weak` - raz na zamach (klucz:
`Player.attack_time`), nie raz na klatkę kolizji.

**Pułapka:** cząstki pogody używają `spawn_rect` (nie pozycji myszki) i pola `time_elapsed`
rosnącego co klatkę — nie memoizuj funkcji zależnych od `time_elapsed` (`x_oscillation`):
klucz nigdy się nie powtarza, `@cache` = 0 trafień + nieograniczony wzrost pamięci.

## Animacja sprite'ów / dodanie postaci

- Definicje klatek: `SPRITE_SHEET_DEFINITION_*` (`settings.py:484+`) → mapowanie po szerokości
  sprite'a w `SPRITE_SHEET_DEFINITIONS` (`settings.py:605`, warianty 2x1/2x2/3x3/4x7).
- Klucze animacji: `"{akcja}_{kierunek}"` (np. `run_left`, `weapon_up`).
- Kierunek liczony z kąta wektora prędkości (`get_direction_360` w `characters/movement.py`).
- **Dodanie postaci:** assety w `assets/NinjaAdventure/...` + wpis w `config.json`
  (sprite, statystyki); jeśli nietypowy layout sheetu — dodaj definicję w `settings.py`.

## NPC: FSM i AI

- **FSM (`npc_state.py`):** `get_new_state()` (`npc_state.py:14`) wybiera stan wg priorytetu
  (stunned > dead > attacking > fly > jump > talk > run > walk > bored > idle). Nowy stan:
  podklasa `NPC_State` + warunek w `get_new_state()` + klucze animacji w sheetcie.
- **AI ruchu:** waypointy z mapy Tiled / random-walk (animals) / pościg A* (monsters,
  budzą się w `MONSTER_WAKE_DISTANCE`, `settings.py:112`). Ścieżki: `find_path()`
  (`characters/movement.py:357`) → `a_star_cached` z `maze_generator` (`characters/movement.py:18`).
- **Dialog i sentyment (T-023):** instancja `NPC` (`characters/npc.py`) rozszerzona o:
  `dialog_key` (z modelu), `dialog` (bieżący `DialogNode` / kursor w grafie),
  `selected_options_dict`, `sentiment` (0–100, start = `model.friendly * 100`), `disposition`
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
  (`current_node_key`), start_node dla następnej rozmowy (`dialog_start_node_key`),
  `selected_options_dict`, odwiedzone węzły (`visited_nodes`),
  `sentiment` i `known_disposition`. `SaveManager` serializuje go w `NPCState.dialog_state`,
  a po loadzie `NPC.restore_dialog_state()` odbudowuje graf i przywraca kursor
  oraz flagi.

  **⚠️ Save/load rule:** Każda nowa funkcjonalność, która ma stan zmieniający się
  w trakcie gry (flagi, liczniki, pozycje, stany UI, odblokowane treści) MUSI być
  dodana do save/load — albo od razu, albo skonsultowana z autorem. Jeśli nie masz
  pewności, DOPYTAJ. Pominięcie powoduje utratę postępu po wczytaniu save'a.

## DialogPanel (T-033)

- `ui/panels/dialog.py` renderuje aktywny węzeł grafu (`npc.dialog`) oraz
  przefiltrowane opcje spełniające warunki mini-DSL.
- Wejście hybrydowe: strzałki / drążek + `accept`, klawisze `1-9`, kliknięcia myszy.
- `ui/game_ui.py` obsługuje nawigację i rising-edge dla `up`/`down`/`accept`/`talk`,
  a `characters/player.py:107` otwiera panel gdy gracz naciśnie `talk` w zasięgu NPC.
- Zasięg rozmowy to `FRIENDLY_WAKE_DISTANCE` (`settings.py:175`); wymagana bliskość
  NPC jest sprawdzana w `scene/collisions.py:151` (`npc.model.attitude == friendly` i warunek dialogu).
- Przykładowy dialog: Hammer w `config.json` + spawn w `BLUNDERHAVEN.tmx`;
  scenariusz testowy: `tests/scenarios.json` → "Hammer Dialog Flow".
