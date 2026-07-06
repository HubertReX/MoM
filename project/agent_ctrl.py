#!/usr/bin/env python3
"""
agent_ctrl — zewnętrzne sterowanie grą + screenshoty dla agentów AI (tryb debug).

Mechanizm: gra (gdy włączona flaga) raz na klatkę czyta komendy i **wysyła prawdziwe
zdarzenia klawiszy** (`pygame.event.post`) tak, jakby ktoś naciskał klawiaturę.
Na żądanie zapisuje zrzut ekranu. Dzięki temu agent może uruchomić grę, "naciskać"
klawisze i oglądać stan gry na screenshotach.

Ponieważ wysyłane są realne zdarzenia klawiszy, działa to **zarówno w menu**
(pygame_menu czyta zdarzenia) **jak i w scenie** (gra buduje z nich słownik INPUTS).

Dwa backendy transportu komend:

- **Desktop**: komendy czytane z pliku `agent_input.txt` na dysku (echo > file).
- **Web** (pygbag/WASM): komendy czytane z `window.localStorage` pod kluczem
  `MoM.agent_input` — runner Playwright wrzuca je przez `page.evaluate(...)`.
  W trybie web zrzuty ekranu są delegowane do runnera (`page.screenshot()`),
  bo `pygame.image.save` w pygbag bufuje do bucket-fs niewidocznego dla hosta.

Tryb **opt-in** — domyślnie nieaktywny, więc normalna rozgrywka pozostaje nietknięta.
Nie nadaje się do szybkich scen walki (rozdzielczość czasowa = pojedyncze klatki/komendy),
ale wystarcza do debugowania.

## Włączenie
### Desktop
Ustaw zmienną środowiskową przed startem gry:

    MOM_AGENT_CONTROL=1 just run

### Web (pygbag)
Runner (`tests/automate_display_test.py --web`) ustawia flagę w `window.localStorage`
przed przeładowaniem strony:

    window.localStorage.setItem("MoM.agent_control", "1")

## Wysyłanie komend (z innego terminala / procesu, gdy gra działa)

### Desktop (plik)
    python project/agent_ctrl.py down accept          # w menu: zejdź i zatwierdź
    python project/agent_ctrl.py up:30 right:15 attack screenshot
    # lub bezpośrednio do pliku:
    echo "up:30 right:15 attack screenshot" > agent_input.txt

### Web (localStorage, robione przez runner Playwright)
    page.evaluate("localStorage.setItem('MoM.agent_input', 'down accept')")
    # screenshoty: page.screenshot(path=...) — runner, NIE gra

## Format komendy
`<action>[:frames]` rozdzielone spacją lub nową linią:
- `action` — dowolny klucz z `ACTIONS` (settings.py), np.: left, right, up, down, run,
  jump, attack, talk, open, pick_up, drop, inventory, next_item, prev_item,
  item_1..item_6, use_item, menu, accept, quit, zoom_in, zoom_out, reload, next_day.
- `frames` — ile klatek przytrzymać klawisz (domyślnie 1; dla ruchu sensowne 10–60).
  W MENU długość przytrzymania nie ma znaczenia (jeden KEYDOWN = jeden ruch kursora);
  w SCENIE dłuższe przytrzymanie = dalszy ruch postaci.
- komendy specjalne: `screenshot` (zrzut ekranu), `exit` (zamknięcie procesu gry),
  `debug_map_change` (debugowa zmiana mapy - wywołuje auto-save),
  `debug_text_input` (pokaż panel demo widgetu TextInput),
  `debug_set_maze` (wymuś is_maze=True na bieżącej scenie - test zakazu zapisu w lochu),
  `type:<tekst>` (wpisz tekst do pola z fokusem - jedno słowo, bez spacji; wysyła
  realne zdarzenia TEXTINPUT, np. `type:Abc123`),
  `backspace` (skasuj znak przed kursorem w polu tekstowym - wysyła KEYDOWN Backspace).

## Nawigacja po menu głównym (przydatne dla agenta)
    accept            # uruchom zaznaczoną pozycję (Play jest domyślnie zaznaczone)
    down / up         # zmień zaznaczenie
"""
import os
import time

import pygame

try:
    # dostępne, gdy moduł działa wewnątrz gry (sys.path zawiera 'project')
    from settings import ACTIONS
except ImportError:
    ACTIONS = {}

# domyślny czas przytrzymania klawiszy ciągłych (ruch), gdy nie podano ':frames'
DEFAULT_HOLD_FRAMES = 12
# akcje "ciągłe" (przytrzymywane), reszta traktowana jako jednorazowy impuls
CONTINUOUS_ACTIONS = {"left", "right", "up", "down", "run", "fly"}

# klucz localStorage dla komend agenta w trybie web
WEB_INPUT_KEY = "MoM.agent_input"


class AgentController:
    """Czyta komendy (z pliku lub localStorage) i wysyła zdarzenia klawiszy do gry.

    ``web_mode=True`` => komendy czytane z ``window.localStorage[WEB_INPUT_KEY]``;
    w tym trybie ``capture()`` jest no-opem, bo zrzuty ekranu wykonuje runner
    Playwright przez ``page.screenshot()`` (zapis po stronie hosta).
    """

    def __init__(self, input_file, screenshot_dir, log=print, web_mode: bool = False):
        self.input_file = str(input_file)
        self.screenshot_dir = str(screenshot_dir)
        self.log = log
        self.web_mode = web_mode
        if not web_mode:
            try:
                os.makedirs(self.screenshot_dir, exist_ok=True)
            except OSError as e:
                self.log(f"[agent_ctrl] cannot create screenshot dir: {e}")

        self._held: dict[str, int] = {}    # akcja -> pozostała liczba klatek przytrzymania
        self._keys: dict[str, int] = {}    # akcja -> kod klawisza pygame (do KEYUP)
        self._screenshot_pending = False
        self._screenshot_label = ""     # slug etykiety akcji z komendy `screenshot:<slug>`
        self._counter = 0
        self._exit_requested = False
        self._death_pending = False
        self._load_last_pending = False
        self._map_change_pending = False
        self._type_pending: str = ""          # tekst do "wpisania" (posted TEXTINPUT)
        self._text_demo_pending = False       # żądanie pokazania panelu demo TextInput
        self._set_maze_pending = False        # wymuś tryb maze na bieżącej scenie (test zakazu zapisu)
        if not web_mode:
            self._write_file("")           # wyczyść stary plik na starcie

    # ---------------------------------------------------------------- wysyłanie
    @staticmethod
    def send(commands, input_file) -> None:
        """Zapisz komendy do pliku wejściowego (używane przez CLI / inne skrypty)."""
        text = " ".join(commands) if isinstance(commands, (list, tuple)) else str(commands)
        with open(str(input_file), "w") as f:
            f.write(text)

    # ----------------------------------------------------------------- pomocnicze
    @staticmethod
    def _key_for(action: str):
        keys = ACTIONS.get(action, {}).get("keys", [])
        return keys[0] if keys else None

    def _write_file(self, text: str) -> None:
        try:
            with open(self.input_file, "w") as f:
                f.write(text)
        except OSError:
            pass

    # ----------------------------------------------------------------- odczyt
    def poll(self) -> None:
        """Odczytaj komendy (plik na desktop, localStorage na web) i zakolejkuj je."""
        if self.web_mode:
            self._poll_localstorage()
        else:
            self._poll_file()

    def _poll_file(self) -> None:
        try:
            with open(self.input_file, "r") as f:
                raw = f.read().strip()
        except (FileNotFoundError, OSError):
            return
        if not raw:
            return
        self.log(f"[agent_ctrl] poll raw={raw!r}")
        self._write_file("")  # konsumuj zawartość
        for token in raw.split():
            self._enqueue(token)

    def _poll_localstorage(self) -> None:
        try:
            from platform import window  # type: ignore[attr-defined]
        except ImportError:
            return
        try:
            raw = window.localStorage.getItem(WEB_INPUT_KEY)
        except Exception:
            return
        if not raw:
            return
        try:
            window.localStorage.removeItem(WEB_INPUT_KEY)  # konsumuj
        except Exception:
            pass
        for token in raw.split():
            self._enqueue(token)

    def _enqueue(self, token: str) -> None:
        action, _, frames_str = token.partition(":")
        action = action.strip()
        if not action:
            return
        if action in ("screenshot", "shot"):
            self._screenshot_pending = True
            # `screenshot:<slug>` — slug etykiety akcji (po ':') trafia do nazwy pliku.
            self._screenshot_label = frames_str.strip()
            return
        if action in ("exit", "quit_game"):
            self._exit_requested = True
            return
        if action == "debug_settings":
            import settings
            self.log(
                f"[DEBUG] Fullscreen: {settings._IS_FULLSCREEN}, "
                f"Res Index: {settings._DISPLAY_RES_INDEX}, "
                f"WIDTH={settings.WIDTH}, HEIGHT={settings.HEIGHT}, "
                f"WIDTH_SCALED={settings.WIDTH_SCALED}, HEIGHT_SCALED={settings.HEIGHT_SCALED}"
            )
            return

        if action == "debug_death_screen":
            self._death_pending = True
            return

        if action == "debug_load_last_save":
            self._load_last_pending = True
            return

        if action == "debug_map_change":
            self._map_change_pending = True
            return

        if action == "debug_text_input":
            self._text_demo_pending = True
            return

        if action == "debug_set_maze":
            # wymuś is_maze=True na bieżącej scenie, żeby przetestować zakaz zapisu (F5) w lochu
            self._set_maze_pending = True
            return

        if action == "type":
            # `type:<tekst>` — wpisz tekst do pola z fokusem (bez spacji; jedno słowo).
            # frames_str zawiera wszystko po pierwszym ':' (patrz partition wyżej).
            self._type_pending += frames_str
            return

        if action == "backspace":
            # wyślij realne KEYDOWN Backspace (pola tekstowe kasują znak przed kursorem)
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, mod=0))
            return

        key = self._key_for(action)
        if key is None:
            self.log(f"[agent_ctrl] unknown action: {action!r} (ignored)")
            return

        frames_str = frames_str.strip()
        if frames_str.isdigit():
            frames = max(1, int(frames_str))
        else:
            frames = DEFAULT_HOLD_FRAMES if action in CONTINUOUS_ACTIONS else 1

        # wyślij KEYDOWN tylko gdy klawisz nie jest już "wciśnięty" przez agenta
        self.log(f"[agent_ctrl] queue action={action} frames={frames} key={key}")
        if action not in self._held:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
        self._held[action] = max(self._held.get(action, 0), frames)
        self._keys[action] = key

    # ------------------------------------------------------------- pętla gry
    def apply(self, game) -> None:
        """Woła raz na klatkę PO get_inputs(). Odlicza przytrzymania i czyta komendy."""
        # 1) odlicz istniejące przytrzymania; po wygaśnięciu wyślij KEYUP
        for action in list(self._held.keys()):
            self._held[action] -= 1
            if self._held[action] <= 0:
                pygame.event.post(pygame.event.Event(pygame.KEYUP, key=self._keys[action]))
                del self._held[action]
                del self._keys[action]

        # 2) wczytaj nowe komendy (wyśle KEYDOWN, ustawi przytrzymania)
        self.poll()

        # wpisywanie tekstu: wyślij realne zdarzenia TEXTINPUT (jeden na znak).
        # Syntetyczne KEYDOWN NIE generują TEXTINPUT, więc pola tekstowe (TextInput)
        # muszą dostać te zdarzenia wprost — tak samo odbierze je gra przez event.get().
        if self._type_pending:
            for ch in self._type_pending:
                pygame.event.post(pygame.event.Event(pygame.TEXTINPUT, text=ch))
            self._type_pending = ""

        if self._text_demo_pending and game.states:
            self._text_demo_pending = False
            from ui.panels.text_input_demo import TextInputDemoState
            TextInputDemoState(game).enter_state()

        if self._set_maze_pending and game.states:
            self._set_maze_pending = False
            state = game.states[-1]
            if hasattr(state, "is_maze"):
                state.is_maze = True
                self.log("[agent_ctrl] debug_set_maze -> current scene is_maze=True")

        if self._exit_requested:
            game.is_running = False
            self._exit_requested = False

        if self._death_pending and game.states:
            self._death_pending = False
            from ui.panels.save_load import DeadState as _DS
            _DS(game).enter_state()

        if self._load_last_pending and game.save_manager:
            self._load_last_pending = False
            slots = game.save_manager.list_slots()
            last_idx = -1
            for i, s in enumerate(slots):
                if s is not None and s.is_occupied:
                    last_idx = i
            if last_idx >= 0:
                game.save_manager.load(last_idx)

        if self._map_change_pending:
            self._map_change_pending = False
            state = game.states[-1] if game.states else None
            if state is not None and hasattr(state, "exits") and state.exits:
                # prefer non-maze exits for fast, deterministic loads
                exit = next(
                    (e for e in state.exits if not getattr(e, "is_maze", False)),
                    state.exits[0],
                )
                state.new_scene = exit
                state.go_to_map()
                self.log(f"[agent_ctrl] debug_map_change -> {exit.to_map}")
            else:
                self.log("[agent_ctrl] debug_map_change: no scene/exits available")

    # ------------------------------------------------------------- screenshot
    def capture(self, surface) -> "str | None":
        """Zapisz bieżącą powierzchnię, jeśli zlecono komendę 'screenshot'.

        W ``web_mode`` to jest no-op: zrzuty ekranu robi runner Playwright po
        stronie hosta (``page.screenshot()``), ponieważ pygbag bucket-fs nie jest
        widoczny dla procesu testowego. Flaga ``_screenshot_pending`` jest jednak
        konsumowana, żeby runner mógł wysłać komendę 'screenshot' bez skutków.
        """
        if not self._screenshot_pending or surface is None:
            return None
        self._screenshot_pending = False
        label = self._screenshot_label
        self._screenshot_label = ""
        self._counter += 1
        if self.web_mode:
            self.log(f"[agent_ctrl] screenshot #{self._counter} (delegated to web runner)")
            return None
        # Nazwa spójna z runnerem: agent_{run_ts}_{scenario_slug}_{NN}_{action_slug}.png
        # Prefix "{run_ts}_{scenario_slug}" przychodzi z runnera przez env MOM_AGENT_SS_PREFIX.
        # Bez prefixu (ręczne uruchomienie) — stary format wstecznie kompatybilny.
        prefix = os.environ.get("MOM_AGENT_SS_PREFIX")
        if prefix:
            slug = label or "shot"
            filename = f"agent_{prefix}_{self._counter:02d}_{slug}.png"
        else:
            time_str = time.strftime("%Y%m%d_%H%M%S")
            filename = f"agent_{time_str}_{self._counter:04d}.png"
        path = os.path.join(self.screenshot_dir, filename)
        try:
            pygame.image.save(surface, path)
            self.log(f"[agent_ctrl] screenshot -> {path}")
            return path
        except (pygame.error, OSError) as e:
            self.log(f"[agent_ctrl] screenshot failed: {e}")
            return None


# ----------------------------------------------------------------------- CLI
if __name__ == "__main__":
    import sys

    try:
        from settings import AGENT_INPUT_FILE
        input_file = AGENT_INPUT_FILE
    except ImportError:
        # uruchomione spoza gry (np. python project/agent_ctrl.py ...)
        input_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "agent_input.txt")

    if len(sys.argv) < 2:
        print("Usage: python project/agent_ctrl.py <action[:frames]> [more...]")
        print("  e.g. python project/agent_ctrl.py down accept")
        print("       python project/agent_ctrl.py up:30 right:15 attack screenshot")
    print("  special: screenshot, exit, debug_map_change")
    sys.exit(1)

    AgentController.send(sys.argv[1:], input_file)
    print(f"sent: {' '.join(sys.argv[1:])}  ->  {input_file}")
