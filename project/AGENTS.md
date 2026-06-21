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
- **Stany:** `Scene` (`scene.py`, rozgrywka na mapie), `MenuScreen` i podklasy (`menus.py`),
  `SplashScreen` (`splash_screen.py`). Przejścia ekranowe (fade/koło): `transition.py`.

## Mapa plików rdzenia

| Plik | Rola | Uwaga |
|---|---|---|
| `scene.py` | Ładowanie mapy `.tmx` (pytmx), render pyscroll `BufferedRenderer`, kolizje, czas/dzień-noc, NPC | **73K — duży** |
| `characters.py` | `NPC` i `Player`: animacja, A*, movement, walka, inventory | **66K — duży** |
| `ui.py` | HUD, panele dialogów, inventory, notyfikacje (NinePatch + SFText) | **45K — duży** |
| `settings.py` | **Wszystkie stałe** gry + definicje sprite-sheetów | **30K** |
| `objects.py` | Sprite'y: `ItemSprite`, `ChestSprite`, `HealthBar`, `EmoteSprite`, `Collider`, `Notification` | |
| `npc_state.py` | FSM NPC (Idle/Walk/Run/Jump/Fly/Stunned/Attacking/Talk/Dead) | |
| `particles.py` | System cząstek (liście, deszcz, wiatr) | |
| `rich_text.py` | `RichPanel` — sformatowany tekst z animowanymi emoji (tagi `[bold]`, `[link]`, `:emoji:`) | |
| `nine_patch.py` | Skalowalne panele UI (9-patch) | |
| `opengl_shader.py` | Wrapper zengl do shaderów post-process | patrz [`shaders/AGENTS.md`](./shaders/AGENTS.md) |
| `camera.py` | Viewport + zoom (steruje `map_view.zoom`) | |
| `transition.py` | Efekty przejść (`Transition`, `TransitionCircle`) | |
| `second_order_dynamics.py` | Gładkie animacje (Second Order Dynamics) — POC | |
| `enums.py` | Typy wyliczeniowe (Race, Attitude, ItemType, …) | |
| `main.py` | Entry point + CLI (Click na desktopie) | |

## 🔑 KRYTYCZNE: różnice desktop ↔ web

`IS_WEB` zdefiniowane w `settings.py:84`. Najważniejsze rozgałęzienia:

| Obszar | Desktop | Web | Lokalizacja |
|---|---|---|---|
| Config | `config_pydantic.py` (Pydantic) | `config.py` (dataclass) | `if IS_WEB:` w `characters.py:48`, `objects.py:19`, `ui.py:54` |
| Shadery | dostępne (gdy `USE_SHADERS`) | wyłączone (wydajność) | `USE_SHADERS=False` `settings.py:92` |
| Filtr dzień-noc (alpha) | tak | **nie** | `scene.py:1515` `if USE_ALPHA_FILTER and not IS_WEB:` |
| Logowanie | `print` | `platform.console.log` | `game.py` |
| Asyncio | stdlib | `pygbag.aio` | `main.py` |
| Wyjście z gry | zamyka okno | zostaje w przeglądarce | `state.py` |
| Screenshoty | zapis na dysk | download w przeglądarce | `game.py` |
| Gamepad | XBOX/Steam Deck | `WEB_CONTROL_NAMES` | `settings.py`, `game.py` |

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
Wysyła **prawdziwe zdarzenia klawiszy** (`pygame.event.post`), więc działa i w menu
(pygame_menu), i w scenie. Nie nadaje się do szybkich scen walki (rozdzielczość = klatki).

**Włączenie** (zmienna środowiskowa): `MOM_AGENT_CONTROL=1 ./run.sh`
(flaga `USE_AGENT_CONTROL` w `settings.py`, czyta `os.environ`).

**Sterowanie** (z innego terminala, gdy gra działa):
```bash
python project/agent_ctrl.py down accept            # w menu: zaznacz i uruchom (Play)
python project/agent_ctrl.py up:30 right:15 attack  # ruch + atak (':N' = liczba klatek)
python project/agent_ctrl.py screenshot             # zrzut → screenshots/agent/
python project/agent_ctrl.py exit                   # zamknij grę
# albo bezpośrednio: echo "up:30 screenshot" > agent_input.txt
```
Komendy = klucze z `ACTIONS` (`settings.py`) + specjalne `screenshot`/`exit`. Zrzuty trafiają
do `screenshots/agent/` (zapisywany `self.screen`).

**Wpięcie w kod (minimalne, 4 miejsca w `game.py`):** instancja w `__init__` (gdy flaga),
`agent_ctrl.apply(self)` po `get_inputs()` w `run()`, `agent_ctrl.capture(self.screen)`
po `flip()`. Cała logika w `project/agent_ctrl.py`. Ograniczenie: przy `USE_SHADERS=True`
finalny obraz idzie przez GL i `self.screen` może nie zawierać klatki — testuj z shaderami off.

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
- Type hints wymagane (mypy strict). Nie modyfikuj vendored libów (`pygame_menu`, `sftext`, `animation`).
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
