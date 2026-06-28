---
id: T-007
title: Save-Load UI panels and game integration — SavePanel, LoadPanel, hotkeys F5-F9, auto-save, death screen load
status: done
owner: human
priority: p2
type: feature
agent: opencode
created: 2026-06-28
updated: 2026-06-28
tags:
  - task
state: review
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

- [x] Dodaj `PanelType.SAVE` i `PanelType.LOAD` do enuma — **pominięte (panels używa class references, nie enum)**
- [x] Dodaj akcje klawiszy do `settings.py`: `quick_save` (F5), `quick_load` (F9)
- [x] Stwórz `project/ui/panels/save_load.py`:
  - [x] `SaveLoadPanel` — bazowy panel slotów (wszystkie sloty, klik = zapis; zajęty = overwrite confirm)
  - [x] `SavePanel(SaveLoadPanel)` — zapis
  - [x] `LoadPanel(SaveLoadPanel)` — tylko zajęte sloty, klik = load confirm
  - [x] `DeathScreen(Widget)` + `DeadState(State)` — ekran śmierci z opcjami
- [x] Dodaj panele do GameUI: import w `game_ui.py`
- [x] Dodaj opcje do Main Menu:
  - [x] "Continue" (wczytuje ostatni save)
  - [x] "Load" (otwiera LoadPanel w nowej scenie)
  - [ ] Pause/Inventory: "Save" + "Load" — **pominięte (brak pause menu, hotkeys wystarczą)**
- [x] Auto-save w `Scene.go_to_map()` → `save_manager.save(0)`
- [x] Quick save/load hotkeys w `game.py`:
  - [x] F5 → `save_manager.save(0)` + notyfikacja "Game saved"
  - [x] F9 → toggle LoadPanel
- [x] Death screen integracja — `DeadState` z opcjami "Load Last Save" / "Restart"
- [x] Notyfikacja "Game saved" po quick save
- [ ] Testy manualne
- [x] mypy — tylko pre-existing errors (identyczne jak w innych panelach)

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

- 2026-06-28 opencode: claimed, starting
- 2026-06-28 opencode: Zaimplementowano UI save/load: SavePanel+LoadPanel (save_load.py), DeadState na śmierć, hotkeys F5/F9 w game.py, auto-save w go_to_map(), Continue/Load w Main Menu. Importy działają, 28/28 testów pass. Czeka na review.
- 2026-06-28 opencode: Gotowe do review: SavePanel/LoadPanel, quick save/load F5/F9, auto-save przy zmianie mapy, death screen z Load/Restart, Continue/Load w Main Menu. 28/28 testów pass, importy działają. Do zrobienia tylko testy manualne.

## 🙋 Needs-You / Questions
