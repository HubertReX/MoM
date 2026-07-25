# A02 - agent_ctrl: `debug_ui_state` + asercje stanu w runnerze

Priorytet: **P0** (Faza 1). Rozmiar: M. Zależności: brak (niezależne od A01).

## Kontekst i problem

Weryfikacja wizualna (ss-review) jest niedeterministyczna z natury (LLM-vision). Tymczasem
większość faktów, które testy chcą sprawdzić ("panel dialogu jest otwarty", "gracz jest na
mapie Village", "HP = 100"), gra ZNA i może je po prostu zrzucić do pliku. Runner powinien
asertować fakty z runtime, a vision zostawić tylko do ocen estetycznych.

Częściowo już to działa: `agent_ctrl` zapisuje stan spaceru do `agent_status.txt`
(idle|walking|arrived|no_path|not_found - patrz `project/agent_ctrl.py`, `_write_status`),
a scenariusze mają asercje plikowe (`file_exists`, `localstorage_exists`).

## Cel

Nowa komenda agenta `debug_ui_state` zapisująca JSON ze stanem gry oraz nowy typ asercji
`ui_state` w `tests/scenarios.json`, którym runner porównuje wybrane pola.

## Pliki do zmiany

- `project/agent_ctrl.py` - nowa komenda w interpreterze (`apply()`, obok `debug_settings`,
  `debug_death_screen` itd.)
- `project/settings.py` - stała `AGENT_UI_STATE_FILE` (obok `AGENT_STATUS_FILE`)
- `tests/automate_display_test.py` - obsługa asercji `ui_state`
- `tests/scenarios.json` - użycie w 2-3 scenariuszach jako wzorzec
- `project/AGENTS.md` - dopisanie komendy do listy komend agenta

## Krok 1: komenda `debug_ui_state`

W `agent_ctrl.apply(game)` dodaj obsługę tokenu `debug_ui_state`. Zbierz słownik i zapisz
do `AGENT_UI_STATE_FILE` (`agent_ui_state.json` w katalogu repo; na web - klucz
`MoM.agent_ui_state` w localStorage, symetrycznie do `agent_status`):

```python
state = game.states[-1]
scene = getattr(game, "save_manager", None) and game.save_manager.current_scene()
info: dict[str, Any] = {
    "top_state": type(state).__name__,          # "Scene", "MainMenuScreen", ...
    "map": getattr(scene, "current_map", None),
    "is_maze": getattr(scene, "is_maze", None),
    "hour": getattr(scene, "hour", None),
    "open_panels": [],
    "player": None,
    "dialog": None,
}
if scene is not None:
    ui = scene.ui
    info["open_panels"] = [type(p).__name__ for p in ui._open]
    p = scene.player
    info["player"] = {
        "hp": p.model.health, "money": p.model.money,
        "pos": [round(p.pos.x), round(p.pos.y)],
        "items": sorted(i.name for i in p.items),
    }
    npc = p.npc_met
    if npc is not None and npc.dialog is not None:
        info["dialog"] = {"npc": npc.dialog_key or npc.name,
                          "node": npc.dialog.key,
                          "sentiment": npc.sentiment}
```

Zapisuj przez `json.dump(..., ensure_ascii=False)`. Każde wywołanie NADPISUJE plik.
Uwaga: dostęp do `ui._open` jest prywatny - dodaj w `GameUI` publiczną własność
`open_panel_names` zwracającą listę nazw klas i użyj jej (nie sięgaj po `_open` z zewnątrz).

## Krok 2: asercja `ui_state` w runnerze

W `tests/automate_display_test.py`, obok obsługi `file_exists`, dodaj typ:

```json
{"type": "ui_state", "expect": {"top_state": "Scene", "map": "Village",
                                 "open_panels_contains": ["DialogPanel"],
                                 "player.hp_min": 1}}
```

Semantyka porównania (zaimplementuj dokładnie te cztery rodzaje, nic więcej):

- klucz zwykły (`top_state`, `map`, `is_maze`...) - równość z wartością z JSON-a
- `open_panels_contains` - każdy element listy musi występować w `open_panels`
- `<ścieżka>.hp_min` / `_max` - porównanie liczbowe pola po ścieżce z kropką
- brak pliku stanu = FAIL z czytelnym komunikatem ("scenario must call debug_ui_state first")

Scenariusz musi wysłać `debug_ui_state` jako akcję przed asercją - dopisz to do 2-3
scenariuszy (np. "Hammer Dialog Flow": po otwarciu dialogu `debug_ui_state`, potem asercja
`open_panels_contains: ["DialogPanel"]` i `dialog.npc`).

Na web: asercja czyta klucz `MoM.agent_ui_state` przez `page.evaluate` (wzorzec:
istniejąca obsługa `localstorage_exists`).

## Kryteria akceptacji

1. `MOM_SKIP_SS_REVIEW=1 MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
   .venv/bin/python3 tests/automate_display_test.py "Hammer Dialog Flow"` przechodzi
   z nowymi asercjami `ui_state`.
2. Celowo zepsuta asercja (np. `map: "Nieistniejąca"`) daje FAIL z komunikatem
   pokazującym wartość oczekiwaną i faktyczną.
3. Wariant web: `just test-web "<scenariusz z ui_state>"` przechodzi (jeśli scenariusz
   jest oznaczony jako web-kompatybilny).
4. `just test-unit` przechodzi w całości.
5. Plik `agent_ui_state.json` jest w `.gitignore` (obok `agent_input.txt`).

## Pułapki

- `game.states[-1]` to może być menu, nie Scene - wszystkie pola sceny muszą być
  odporne na `None` (stąd `getattr(..., None)`).
- Komenda musi działać także gdy gra jest w menu (zwróci `top_state: "MainMenuScreen"`,
  reszta null) - to legalny wynik, nie błąd.
- Nie loguj całego JSON-a do stdout gry (szum); wystarczy `[agent] ui_state saved`.
- Zapis pliku w web-mode nie istnieje - użyj localStorage (patrz jak robi to
  `_write_status` i mechanizm komend web w `agent_ctrl.py`).

## Po zakończeniu

- dopisz `debug_ui_state` do listy komend w `project/AGENTS.md` (sekcja agent_ctrl)
- odhacz A02 w `doc/audyt/audyt.md`
- commit: `A02: agent_ctrl - debug_ui_state + asercje ui_state w runnerze`
