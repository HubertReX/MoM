#!/usr/bin/env python3
"""
agent_ctrl — zewnętrzne sterowanie grą + screenshoty dla agentów AI (tryb debug).

Mechanizm plikowy: gra (gdy włączona flaga) raz na klatkę czyta komendy z pliku
`agent_input.txt` i **wysyła prawdziwe zdarzenia klawiszy** (`pygame.event.post`) tak,
jakby ktoś naciskał klawiaturę. Na żądanie zapisuje zrzut ekranu. Dzięki temu agent może
uruchomić grę, "naciskać" klawisze i oglądać stan gry na screenshotach.

Ponieważ wysyłane są realne zdarzenia klawiszy, działa to **zarówno w menu**
(pygame_menu czyta zdarzenia) **jak i w scenie** (gra buduje z nich słownik INPUTS).

Tryb wyłącznie **desktop** (operacje na plikach) i **opt-in** — domyślnie nieaktywny,
więc normalna rozgrywka pozostaje nietknięta. Nie nadaje się do szybkich scen walki
(rozdzielczość czasowa = pojedyncze klatki/komendy), ale wystarcza do debugowania.

## Włączenie
Ustaw zmienną środowiskową przed startem gry:

    MOM_AGENT_CONTROL=1 ./run.sh

## Wysyłanie komend (z innego terminala / procesu, gdy gra działa)

    python project/agent_ctrl.py down accept          # w menu: zejdź i zatwierdź
    python project/agent_ctrl.py up:30 right:15 attack screenshot
    # lub bezpośrednio do pliku:
    echo "up:30 right:15 attack screenshot" > agent_input.txt

## Format komendy
`<action>[:frames]` rozdzielone spacją lub nową linią:
- `action` — dowolny klucz z `ACTIONS` (settings.py), np.: left, right, up, down, run,
  jump, attack, talk, open, pick_up, drop, inventory, next_item, prev_item,
  item_1..item_6, use_item, menu, accept, quit, zoom_in, zoom_out, reload, next_day.
- `frames` — ile klatek przytrzymać klawisz (domyślnie 1; dla ruchu sensowne 10–60).
  W MENU długość przytrzymania nie ma znaczenia (jeden KEYDOWN = jeden ruch kursora);
  w SCENIE dłuższe przytrzymanie = dalszy ruch postaci.
- komendy specjalne: `screenshot` (zrzut ekranu), `exit` (zamknięcie procesu gry),
  `debug_map_change` (debugowa zmiana mapy - wywołuje auto-save).

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


class AgentController:
    """Czyta komendy z pliku i wysyła odpowiadające im zdarzenia klawiszy do gry."""

    def __init__(self, input_file, screenshot_dir, log=print):
        self.input_file = str(input_file)
        self.screenshot_dir = str(screenshot_dir)
        self.log = log
        try:
            os.makedirs(self.screenshot_dir, exist_ok=True)
        except OSError as e:
            self.log(f"[agent_ctrl] cannot create screenshot dir: {e}")

        self._held: dict[str, int] = {}    # akcja -> pozostała liczba klatek przytrzymania
        self._keys: dict[str, int] = {}    # akcja -> kod klawisza pygame (do KEYUP)
        self._screenshot_pending = False
        self._counter = 0
        self._exit_requested = False
        self._death_pending = False
        self._load_last_pending = False
        self._map_change_pending = False
        self._write_file("")               # wyczyść stary plik na starcie

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
        """Odczytaj plik wejściowy, wyczyść go i zakolejkuj komendy."""
        try:
            with open(self.input_file, "r") as f:
                raw = f.read().strip()
        except (FileNotFoundError, OSError):
            return
        if not raw:
            return
        self._write_file("")  # konsumuj zawartość
        for token in raw.split():
            self._enqueue(token)

    def _enqueue(self, token: str) -> None:
        action, _, frames_str = token.partition(":")
        action = action.strip()
        if not action:
            return
        if action in ("screenshot", "shot"):
            self._screenshot_pending = True
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
        """Zapisz bieżącą powierzchnię, jeśli zlecono komendę 'screenshot'."""
        if not self._screenshot_pending or surface is None:
            return None
        self._screenshot_pending = False
        self._counter += 1
        time_str = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.screenshot_dir, f"agent_{time_str}_{self._counter:04d}.png")
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
