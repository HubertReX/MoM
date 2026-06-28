---
id: T-005
title: Core save data model — SaveGame, SaveSlot, per-state dataclasses
status: ready
owner: ai
priority: p1
type: feature
agent:
created: 2026-06-28
updated: 2026-06-28
tags:
  - task
---

# T-005 — Core save data model — SaveGame, SaveSlot, per-state dataclasses

## 🎯 Goal / Outcome

Typed data model dla całego systemu save/load jako czyste `dataclasses` (działają na web i desktop — brak zależności od Pydantic). Struktury danych do serializacji JSON:

- `SaveMetadata` — wersja, timestamp, playtime, nazwa slota
- `PlayerState` — pozycja, mapa, health, money, inventory (lista `ItemState`), selected_weapon, selected_item_idx, flagi
- `ItemState` — nazwa, typ, count, value, weight, damage, cooldown_time
- `NPCState` — nazwa, pozycja, health, money, is_dead, inventory (lista `ItemState`)
- `ChestState` — id, is_closed, items (lista stringów)
- `MapState` — nazwa, chesty, ground_items (lista ItemState + pozycja), destroyed_walls (lista grid_pos), maze_seed, maze_level, dead_monsters (lista stringów)
- `GameClockState` — day, hour, minute, time_elapsed
- `SaveGame` — agregat: metadata + player + clock + maps (dict[str, MapState])
- `SaveSlot` — metadata + save_data (ścieżka/klucz + czy zajęty)
- `SaveSlotInfo` — podgląd slota (metadata bez pełnych danych gry) do szybkiego wyświetlania w UI

Walidacja wersji (zgodność `VERSION` z `settings.py`). Wszystkie dataclass → dict → JSON i z powrotem.

## 🧭 Context

- Obecny system NIE MA save/load (tylko RAM cache `loaded_maps` w `scene.py`)
- **Dual-target:** desktop + web (pygbag/WASM). Pydantic nie działa na web, więc save data model używa stdlib `dataclasses` — jedna implementacja dla obu platform
- Istniejący proof-of-concept localStorage: `game.py:968` (`get_local_storage`)
- Problem współdzielonych referencji: `game.conf.characters[name]` modyfikowany in-place. Save musi snapshotować per-instance wartości z `NPC.model`
- Stan gry do serializacji: szczegółowo zanalizowany (patrz `project/AGENTS.md` sekcja "Persystencja stanu")
- Plik: `project/config_model/AGENTS.md` — wzór dualnego modułu, choć tu wystarczy jeden (`dataclasses`)
- `settings.py:19` — `VERSION = 0.1` do walidacji kompatybilności

### Powiązane pliki

- `project/characters.py` — Player, NPC, inventory
- `project/scene.py` — Scene, loaded_maps, store_map/restore_map
- `project/objects.py` — ItemSprite, ChestSprite
- `project/settings.py` — VERSION, IS_WEB, MAX_HOTBAR_ITEMS
- `project/npc_state.py` — FSM stanów NPC (do pominięcia przy serializacji)
- `project/enums.py` — ItemTypeEnum, AttitudeEnum (do serializacji jako string)

## ⛓️ Constraints

- **Żadnych zależności zewnętrznych** — tylko `dataclasses` + `json` + `typing` ze stdlib
- Jedna implementacja dla web i desktop (nie ma dual-modułu dla save data)
- Wersjonowanie schematu: `metadata.version` + funkcja `migrate_save()` dla przyszłych zmian
- Type hints wymagane (mypy strict)
- Zachowaj stałe z `settings.py` zamiast hardcodingu
- Wszystkie enumy serializowane jako string (np. `"weapon"`), nie int

## 🪜 Plan / Subtasks

- [ ] Stwórz `project/save_load/models.py` — wszystkie dataclass modele (SaveMetadata, PlayerState, ItemState, NPCState, ChestState, MapState, GameClockState, SaveGame, SaveSlot, SaveSlotInfo)
- [ ] Zaimplementuj konwersję `to_dict()` / `from_dict()` dla każdej dataclass (albo użyj `dataclasses.asdict` + własny `from_dict` z walidacją typów)
- [ ] Obsługa enumów: serializacja `ItemTypeEnum` ↔ str, `AttitudeEnum` ↔ str
- [ ] Wersjonowanie: `SaveMetadata.version` + `migrate_v0_to_v1()` placeholder
- [ ] Testy jednostkowe: round-trip serializacji (dataclass → dict → JSON → dict → dataclass) dla każdego modelu
- [ ] Sprawdź typy z mypy

## ✅ Definition of Done

- [ ] Wszystkie dataclass modele z `project/save_load/models.py` są zdefiniowane i typowane
- [ ] Round-trip serializacji działa dla każdego modelu (utwórz → asdict → json → from_dict → porównaj)
- [ ] Enumy serializują się jako string i poprawnie deserializują
- [ ] `SaveGame` agreguje wszystkie pod-stany
- [ ] Testy jednostkowe przechodzą
- [ ] mypy nie zgłasza błędów w nowym kodzie
- [ ] Kompatybilność web: import działa w pygbag (brak Pydantic, brak zależności zewnętrznych)

## 📓 Agent Log

## 🙋 Needs-You / Questions
