---
id: T-007
title: Save-Load UI panels and game integration — SavePanel, LoadPanel, hotkeys F5-F9, auto-save, death screen load
status: ready
owner: ai
priority: p2
type: feature
agent:
created: 2026-06-28
updated: 2026-06-28
tags:
  - task
---

# T-007 — Save-Load UI panels and game integration — SavePanel, LoadPanel, hotkeys F5-F9, auto-save, death screen load

## 🎯 Goal / Outcome

UI i integracja systemu save/load z grą:

1. **SavePanel** — panel UI (wzorem istniejących paneli: InventoryPanel, DialogPanel) do wyboru slota zapisu. Wyświetla sloty (zajęte z timestampem/mapą, wolne jako puste). Po wybraniu pustego = zapis; po wybraniu zajętego = dialog overwrite confirmation
2. **LoadPanel** — panel UI do wyboru slota wczytywania. Pokazuje tylko zajęte sloty. Po wybraniu = dialog load confirmation („stracisz niezapisany postęp")
3. **Hotkeys** — F5 = szybki zapis do ostatniego/domyślnego slota; F9 = otwiera LoadPanel (lub szybki load jeśli trzymany)
4. **Auto-save** — automatyczny zapis przy zmianie mapy (w `Scene.transition_to_map`) oraz na timerze co N minut gry
5. **Integracja z death screen** — po śmierci gracza (`characters.py:811`), zamiast immediate respawn: pokaż panel z opcją "Load last save" lub "Restart from checkpoint"
6. **Game menu** — opcje "Save" i "Load" w main menu / pause menu
7. **Overwrite confirmation** — modal "Are you sure? This will overwrite your existing save." z opcjami Yes/No (wzór `ConfirmationModal` lub `Modal`)
8. **Load confirmation** — modal "Loading will lose unsaved progress. Continue?" z Yes/No
9. **Save feedback** — krótka notyfikacja "Game saved" po udanym zapisie (użyć istniejącego `Notification` systemu z `objects.py` lub HUD)

### UX flow

**Zapis:**
- Gra → Pause/Inventory → "Save" → SavePanel (sloty 1-10) → klik slot → jeśli zajęty: "Overwrite?" → Yes → zapis + notyfikacja
- Lub: F5 → szybki zapis do ostatniego slota (lub pierwszego wolnego) → notyfikacja

**Wczytywanie:**
- Gra → Pause/Inventory → "Load" → LoadPanel (zajęte sloty) → klik slot → "Load? (stracisz postęp)" → Yes → load + przejście na mapę
- Lub: F9 → LoadPanel
- LoadPanel w Main Menu: "Continue" opcja (pokazuje ostatni save) + "Load" (lista slotów)

**Śmierć:**
- Death → modal "You died!" z opcjami: "Load last save" / "Restart (respawn in village)" (dotychczasowe zachowanie)

## 🧭 Context

- T-005 (data model) i T-006 (SaveManager engine) są prerequisite
- Własny toolkit UI: `project/ui/` — retained-mode, czysty pygame-ce. Wzór implementacji paneli: `ui/panels/inventory.py`, `ui/panels/trade.py`, `ui/panels/dialog.py`
- Panel API: `ui.open(PanelType, **kw)`, `ui.close(PanelType)`, `ui.is_open(PanelType)`
- `PanelType` enum w `project/enums.py` — trzeba dodać `SAVE` i `LOAD`
- `Scene.ui` to `GameUI` — kontroler paneli
- `GameUI` w `project/ui/game_ui.py`
- `Modal` panel: `ui/panels/modal.py` — do confirmation dialogów
- `Notification` system: `project/objects.py:653` (`Notification` klasa), używany w HUD
- `characters.py:811` — śmierć gracza, obecny flow: `exit_state()` → splash "GAME OVER"
- `scene.py` — `transition_to_map()` miejsce na auto-save hook
- `game.py` — obsługa klawiszy (ACTIONS mapping), miejsce na hotkeys F5/F9
- `main_menu.py` — `ui/panels/main_menu.py`, miejsce na "Continue"/"Load" opcje

### Istniejące wzory UI do naśladowania

- InventoryPanel: `ui/panels/inventory.py` — lista slotów, nawigacja strzałkami/wheel, klik
- Modal: `ui/panels/modal.py` — proste dialogi Yes/No z callbackami (użyć do overwrite/load confirmation)
- RichText scroll: `ui/widgets/` — jeśli potrzeba
- Panel layout: `3-column` (slot numer, thumbnail, info label)

## ⛓️ Constraints

- **DEPENDENCY:** Wymaga ukończonego T-005 (modele danych: `SaveSlotInfo`) i T-006 (silnik: `SaveManager.save()`, `SaveManager.load()`, `SaveManager.list_slots()`)
- **Web:** działa — UI toolkit jest czystym pygame-ce, kompatybilny z pygbag
- **Web:** F5/F9 muszą działać (pygbag nie przechwytuje F5 w przeglądarce? Sprawdzić; ewentualnie inny klawisz na web. Jeśli F5 jest zablokowane przez przeglądarkę → dodać alternatywny klawisz)
- Użyj istniejących komponentów UI (Widget, Label, Button, Image, RichText, Modal)
- Nie twórz nowego toolkitu — rozszerz istniejący PanelType
- Hotkeys definiuj w `settings.py` w słowniku `ACTIONS` jak reszta sterowania (wzór: `actions.py` lub `ACTIONS` dict)
- Wszystkie stringi UI powinny iść przez system lokalizacji (assets dialogs pattern) — przynajmniej przygotuj stałe

## 🪜 Plan / Subtasks

- [ ] Dodaj `PanelType.SAVE` i `PanelType.LOAD` do enuma w `project/enums.py`
- [ ] Dodaj akcje klawiszy do `settings.py`: `ACTION_QUICK_SAVE`, `ACTION_QUICK_LOAD` z domyślnymi F5/F9 (ew. alternatywa na web)
- [ ] Stwórz `project/ui/panels/save_load.py`:
  - [ ] `SavePanel` — lista slotów, wybór, overwrite confirmation modal
  - [ ] `LoadPanel` — lista zajętych slotów, load confirmation modal
  - [ ] `render_slot_widget(slot_idx, slot_info: SaveSlotInfo | None) -> Widget` — komponent slotu z timestampem, mapą, numerem
- [ ] Dodaj "Save / Load" do GameUI: `game_ui.py` obsługa nowych paneli
- [ ] Dodaj opcje do Pause menu i Main Menu:
  - [ ] Main Menu: "Continue" (jeśli jest save) + "Load"
  - [ ] Pause/Inventory: "Save" + "Load" przyciski
- [ ] Auto-save w `Scene.transition_to_map()` → `game.save_manager.save(auto_save_slot_idx)`
- [ ] Quick save/load hotkeys w `game.py` (`get_inputs()` lub `run()`):
  - [ ] F5 → `save_manager.save(last_used_slot or 0)` + notyfikacja "Game saved"
  - [ ] F9 → otwiera LoadPanel (lub jeśli przytrzymany → load ostatniego slota)
- [ ] Death screen integracja (`characters.py:811` lub `game.py`):
  - [ ] Po śmierci: zamiast immediate respawn, pokaż modal z opcjami "Load last save" / "Restart"
  - [ ] "Restart" = obecne zachowanie (respawn w wiosce)
  - [ ] "Load last save" = wczytaj ostatni ręczny zapis
- [ ] Notyfikacja "Game saved" po udanym zapisie (przez istniejący system Notification/Toast)
- [ ] Testy manualne: save na różnych mapach, load, quick save/load, auto-save, death → load
- [ ] mypy

## ✅ Definition of Done

- [ ] SavePanel działa: wybór slota, zapis, overwrite confirmation
- [ ] LoadPanel działa: wybór slota, load confirmation, wczytanie stanu gry
- [ ] F5 szybki zapis + notyfikacja "Game saved"
- [ ] F9 otwiera LoadPanel (lub szybki load przy przytrzymaniu)
- [ ] Auto-save przy zmianie mapy
- [ ] Po śmierci gracza: opcja "Load last save" zamiast natychmiastowego respawnu
- [ ] Opcje "Save"/"Load" dostępne w pauzie/main menu
- [ ] "Continue" w Main Menu wczytuje ostatni save
- [ ] Wszystkie confirmation dialogi działają (overwrite, load)
- [ ] Działa na desktop (`./run.sh`) i web (`./serve_web.sh`)
- [ ] mypy nie zgłasza błędów

## 📓 Agent Log

## 🙋 Needs-You / Questions
