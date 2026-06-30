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
| `ui/widgets/`                   | `Label`, `Image`, `Button`, `RichText` (zawijanie, scroll, linki, animowane emoji) |
| `ui/panels/`                    | `main_menu`, `hud`, `dialog`, `modal`, `inventory`, `trade`                        |
| `ui/game_ui.py`                 | **`GameUI`** — kontroler HUD+paneli per-`Scene`                                    |

**Czyste API** (`Scene.ui` to `GameUI`): `ui.open(PanelType, **kw)`, `ui.close(PanelType)`,
`ui.toggle(PanelType)`, `ui.is_open(PanelType)`, `ui.update(dt, events)`, `ui.draw()`,
`ui.reset()`. Stan paneli jest wewnątrz nich (np. `TradePanel.is_buying`) — bez luźnych
boolean-flag. Dialogi w `assets/dialogs/**/*.md` używają tagów `[bold]`/`[link URL]`/`:emoji:`
(tabela `STYLE_TAGS_DICT` w `settings.py`).

## 🔑 KRYTYCZNE: różnice desktop ↔ web

`IS_WEB` zdefiniowane w `settings.py:84`. Najważniejsze rozgałęzienia:

| Obszar                  | Desktop                         | Web                     | Lokalizacja                                                            |
| ----------------------- | ------------------------------- | ----------------------- | ---------------------------------------------------------------------- |
| Config                  | `config_pydantic.py` (Pydantic) | `config.py` (dataclass) | `if IS_WEB:` w `characters.py:48`, `objects.py:19`, `ui/panels/hud.py` |
| Shadery                 | dostępne (gdy `USE_SHADERS`)    | wyłączone (wydajność)   | `USE_SHADERS=False` `settings.py:92`                                   |
| Filtr dzień-noc (alpha) | tak                             | **nie**                 | `scene.py:1515` `if USE_ALPHA_FILTER and not IS_WEB:`                  |
| Logowanie               | `print`                         | `platform.console.log`  | `game.py`                                                              |
| Asyncio                 | stdlib                          | `pygbag.aio`            | `main.py`                                                              |
| Wyjście z gry           | zamyka okno                     | zostaje w przeglądarce  | `state.py`                                                             |
| Screenshoty             | zapis na dysk                   | download w przeglądarce | `game.py`                                                              |
| Gamepad                 | XBOX/Steam Deck                 | `WEB_CONTROL_NAMES`     | `settings.py`, `game.py`                                               |

**Reguła:** nowy kod zależny od platformy chowaj za `if IS_WEB:`; testuj `./run.sh` **oraz**
`./serve_web.sh`.

### `USE_WEB_SIMULATOR` (`settings.py:83`)

Flaga desktopowa do **testowania ścieżek web bez przeglądarki**. Ustawiona na `True` wymusza
`IS_WEB=True` (`settings.py:84`) i przełącza asyncio na `pygbag.aio` (`main.py:35`, `game.py:73`),
ale loguje przez `print` (a nie `platform.console.log`, dostępne tylko w realnej przeglądarce —
`game.py:105` `if IS_WEB and not USE_WEB_SIMULATOR`). Domyślnie `False`.

## Testowanie gry przez agentów AI (`agent_ctrl.py`)

Mechanizm pozwalający agentowi **uruchomić grę, „naciskać" klawisze i robić zrzuty ekranu**
(debug). Desktop-only, **opt-in**, domyślnie wyłączony — nie wpływa na normalną rozgrywkę.
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
  itd.
- Specjalne komendy interpretera (`project/agent_ctrl.py`):
  - `screenshot` / `shot` - zapisuje bieżącą klatkę do `screenshots/agent/`.
  - `exit` / `quit_game` - zamyka grę.
  - `debug_settings` - loguje aktualne ustawienia wyświetlania.
  - `debug_death_screen` - wymusza ekran śmierci.
  - `debug_load_last_save` - wczytuje ostatni zajęty slot.

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

**Persystencja w testach:**

Pliki save na desktopie:

- macOS: `~/Library/Application Support/mom/saves/save_N.mom`
- Linux: `~/.local/share/mom/saves/save_N.mom`

Helper do manipulowania zapisami: `tests/test_save_load_corrupt.py`:

```bash
.venv/bin/python3 tests/test_save_load_corrupt.py clear     # usuń wszystkie save'y
.venv/bin/python3 tests/test_save_load_corrupt.py corrupt 0 # zepsuj slot 0
.venv/bin/python3 tests/test_save_load_corrupt.py create 0  # utwórz minimalny save
.venv/bin/python3 tests/test_save_load_corrupt.py delete 0  # usuń slot 0
```

## Persystencja stanu (uwaga: brak zapisu na dysk)

- **Brak systemu save/load na dysk** — zamknięcie gry traci postęp (na liście TODO w README).
- **Persystencja między mapami = tylko w RAM** podczas sesji: `Scene` cache'uje stan w
  `loaded_maps` (`scene.py:158`) i `loaded_NPCs` (`scene.py:214`). Wyjście z mapy →
  `store_map()` (`scene.py:717`) robi snapshot; powrót → `restore_map()` (`scene.py:726`)
  przywraca. Wygenerowany labirynt zachowuje układ póki jest w `loaded_maps` (`scene.py:669`).
- **Śmierć gracza** (`characters.py:811`): przy `health <= 0` → `exit_state()` bieżącej sceny,
  `player.reset()` (`characters.py:1020`: pełne zdrowie, **przeładowanie startowego ekwipunku
  z configu — zebrane przedmioty przepadają**, wyczyszczenie flag), nowa `Scene("Village",
  "start")` + splash `"GAME OVER"`. To pełny respawn w wiosce, nie wczytanie zapisu.

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
