---
id: T-006
title: Save-Load manager engine — SaveManager class, desktop file backend, web localStorage backend, slot CRUD
status: archive
owner: human
priority: p1
type: feature
agent: opencode
created: 2026-06-28
updated: 2026-06-28
tags:
  - task
state: review
---

# T-006 — Save-Load manager engine — SaveManager class, desktop file backend, web localStorage backend, slot CRUD

## 🎯 Goal / Outcome

`SaveManager` — centralna klasa orchestratora save/load. Odpowiada za:

1. **Serializacja stanu gry → SaveGame** — odczytuje Player, Scene (loaded_maps), NPC, chesty, game clock, buduje `SaveGame` (używając modeli z T-005)
2. **Deserializacja SaveGame → stan gry** — aplikuje zapisany stan: odtwarza Player (pozycja, health, money, inventory, flagi), przywraca per-map state (chesty, ground items, NPC, destroyed walls, maze), ustawia game clock, ładuje właściwą mapę
3. **Persistence backends** — abstrakcja `SaveBackend` z dwiema implementacjami:
   - `FileSaveBackend` — desktop: JSON w `platformdirs.user_data_dir("mom")/saves/` (lub `~/.local/share/mom/saves/`), obsługa `pathlib`
   - `LocalStorageSaveBackend` — web: `window.localStorage` pod kluczami `MoM.save_0`, `MoM.save_1`, ... z mechanizmem `JSON.stringify`/`JSON.parse`
4. **Slot management** — CRUD dla N slotów (np. 10): lista zapisów (tylko `SaveSlotInfo` bez pełnych danych), zapis do slota, odczyt, nadpisywanie, usuwanie
5. **Error handling** — corrupt save detection (JSON parse fail, version mismatch), graceful fallback (log + return None), czytelne komunikaty

**WAŻNE:** Ten task implementuje logikę, NIE UI ani hotkeys — to jest T-007.

### Kluczowe wyzwania implementacyjne

- **Problem współdzielonych config-ów:** `game.conf.characters[name]` jest modyfikowany in-place. SaveManager musi snapshotować per-instance wartości z `NPC.model` (health, money), a przy loadzie tworzyć shadow copy dla każdego NPC zamiast mutować config
- **Player jest tworzony w `Scene.__init__` i NIE cache'owany w `loaded_maps`** — przy loadzie trzeba zniszczyć obecny Scene, stworzyć nowy z odpowiednią mapą, a potem nadpisać Player stanem z save'a
- **Maze stan:** przechowaj seed (do regeneracji layoutu) + listę dead_monsters + stan chestów. Nie snapshotuj całej siatki labiryntu
- **loaded_maps:** przy loadzie cache jest czyszczony i odbudowywany z danych save'a; na desktopie można próbować cache'ować więcej, na webie lepiej zawsze odtwarzać z save'a

## 🧭 Context

- T-005 (data model) jest prerequisite — jego modele są używane przez SaveManager
- `game.py` — `Game` klasa, jej atrybuty (`self.scene`, `self.conf`, `self.clock`), miejsce do wstrzyknięcia SaveManagera jako `self.save_manager`
- `characters.py` — Player(`pos, current_map, model.health, model.money, items, selected_weapon, selected_item_idx, is_flying`)
- `scene.py` — Scene(`current_map, entry_point, loaded_maps, day, hour, minute, chests, items (ground), NPCs, walls (destructibles)`)
- `scene.py:712-734` — `store_map()` / `restore_map()` — wzór snapshotowania per-map
- `game.py:968` — `get_local_storage()` — PoC localStorage (działa, ale nieużywany)
- `platformdirs` — desktopowa biblioteka do XDG paths, już może być w zależnościach; sprawdź `requirements*.txt`
- Wzorzec dual import (web vs pydantic): `characters.py:48-50` — tutaj niepotrzebny, bo persistence backend jest wybierany runtime przez `if IS_WEB`

### Powiązane pliki

- T-005: `project/save_load/models.py` — modele danych (prerequisite)
- `project/game.py` — Game class, miejsce na SaveManager
- `project/scene.py` — Scene, loaded_maps, store_map/restore_map, chests, ground items
- `project/characters.py` — Player, NPC, inventory
- `project/settings.py` — IS_WEB, SAVE_DIR (stała), MAX_SAVE_SLOTS
- `project/objects.py` — ItemSprite, ChestSprite, DestructibleSprite

## ⛓️ Constraints

- **DEPENDENCY:** Wymaga ukończonego T-005 — importuje `SaveGame`, `PlayerState`, `NPCState`, `MapState`, `ChestState`, `GameClockState`, `SaveSlotInfo` z `project/save_load/models.py`
- **Web:** `platformdirs` NIE działa w pygbag — `FileSaveBackend` deskop only, z `if IS_WEB:` guard
- **Web:** localStorage jest synchroniczny (limit ~5-10MB na domenę) — nie używać IndexedDB na razie
- **Desktop:** użyj `platformdirs.user_data_dir("mom", ensure_exists=True)` dla standardowej ścieżki XDG; ew. fallback `~/Library/Application Support/mom/saves/` na macOS
- Nie modyfikować configu (`game.conf`) podczas loadu — snapshotować per-instance wartości
- SaveManager jako atrybut `Game` (nie singleton), tworzony w `Game.__init__`
- type hints wymagane (mypy strict)

## 🪜 Plan / Subtasks

- [ ] Dodaj stałe do `settings.py`: `MAX_SAVE_SLOTS = 10`, `SAVE_FILE_EXT = ".mom"`
- [ ] Stwórz `project/save_load/manager.py` — klasa `SaveManager`:
  - [ ] `__init__(game)` — zapamiętuje referencję do `Game`
  - [ ] `save(slot_idx: int) -> bool` — zbiera stan, buduje `SaveGame`, woła backend
  - [ ] `load(slot_idx: int) -> bool` — czyta `SaveGame`, aplikuje stan gry
  - [ ] `list_slots() -> list[SaveSlotInfo | None]` — szybki podgląd (bez pełnych danych)
  - [ ] `delete_slot(slot_idx: int) -> bool` — usuwa zapis
  - [ ] `_build_save_game() -> SaveGame` — snapshotuje cały stan gry
  - [ ] `_apply_save_game(save: SaveGame)` — odtwarza stan gry z save'a
  - [ ] `_build_player_state() -> PlayerState` — snapshot gracza
  - [ ] `_build_map_states() -> dict[str, MapState]` — snapshot per-map z `loaded_maps`
  - [ ] `_apply_player_state(state: PlayerState)` — odtwarza gracza
  - [ ] `_apply_map_states(maps: dict[str, MapState])` — odtwarza per-map cache
  - [ ] `_apply_game_clock(clock: GameClockState)` — ustawia czas
- [ ] Stwórz `project/save_load/backends.py`:
  - [ ] Abstrakcja `SaveBackend` (protocol/ABC)
  - [ ] `FileSaveBackend` — desktop: pathlib, json.dump/load
  - [ ] `LocalStorageSaveBackend` — web: window.localStorage, json.dumps/loads
  - [ ] Backend wybierany w `SaveManager.__init__` przez `if IS_WEB: ... else: ...`
- [ ] `SaveManager._create_backend() -> SaveBackend` — fabryka
- [ ] Wpięcie w `Game.__init__`: `self.save_manager = SaveManager(self)`
- [ ] Error handling: corrupt save → log + return None, version mismatch → log + return None
- [ ] Testy jednostkowe: mockowanie backendu, save → load → verify state match
- [ ] mypy

## ✅ Definition of Done

- [ ] `SaveManager` zapisuje pełny stan gry do wybranego slota (JSON)
- [ ] `SaveManager` odtwarza stan gry z zapisu: player (pos, health, money, inventory, flags), wszystkie mapy z cache (chesty, ground items, NPC, destroyed walls), game clock
- [ ] Na desktopie plik `.mom` pojawia się w `~/.local/share/mom/saves/` (lub odpowiedniku)
- [ ] Na webie save ląduje w `localStorage` pod `MoM.save_N`
- [ ] `list_slots()` zwraca poprawne podglądy (wolne/zajęte sloty z timestampem)
- [ ] Uszkodzony save nie crashuje gry (log + return None)
- [ ] Wersjonowanie: niekompatybilna wersja save'a = odrzucona z logiem
- [ ] Testy jednostkowe przechodzą
- [ ] mypy nie zgłasza błędów

## 📓 Agent Log

- 2026-06-28 opencode: claimed, starting
- 2026-06-28 opencode: Zaimplementowano SaveManager (manager.py + backends.py), dodano npc_states do MapState, wpięto w Game.__init__. 28 testów pass, mypy clean.
- 2026-06-28 opencode: Pełna implementacja SaveManager z backends.py, wpięcie w game.py, rozszerzenie models.py o npc_states. 28 testów pass, mypy clean. Desktop: ~/.local/share/mom/saves/*.mom, Web: localStorage MoM.save_N. Wersjonowanie, corrupt save handling, CRUD slotów.

## 🙋 Needs-You / Questions
