---
id: T-013
title: Po wczytaniu gry nie wyświetlają się ikony w inventory
status: ready
owner: ai
priority: p1
type: bug
agent:
created: 2026-06-30
updated: 2026-06-30
tags:
  - task
---

# T-013 — Po wczytaniu gry nie wyświetlają się ikony w inventory


## 🎯 Goal / Outcome

Naprawić rendering ikon przedmiotów w inventory po wczytaniu gry. Obecnie po `SaveManager.load()` sloty inventory są zajęte i logika gry działa (liczby przedmiotów są widoczne, można ich używać), ale obrazki/ikony przedmiotów nie renderują się.

- [ ] Po wczytaniu zapisu inventory pokazuje ikony wszystkich przywróconych przedmiotów.
- [ ] Ikony są spójne z tymi z nowej gry (przed zapisem).
- [ ] Problem nie występuje na desktopie ani w przeglądarce.

## 🧭 Context

- Problem wykryty podczas weryfikacji T-008 (`Save-load test scenarios`).
- Na screenshotach ze scenariuszy `Save and Load Basic` i `Quick Save and Load` widać, że po loadzie inventory ma puste sloty (brak obrazków), mimo że liczby przedmiotów są widoczne.
- Prawdopodobna przyczyna: w `SaveManager._apply_player_state()` tworzone są `ItemSprite` z tymczasowym obrazkiem `pygame.Surface((1, 1))` zamiast prawdziwej grafiki z `scene.items_sheet`.
- Kod:
  ```python
  sprite = ItemSprite(
      None, (0, 0), item_s.name, model,
      image=[pygame.Surface((1, 1))],
  )
  ```
- W przeciwieństwie do `_apply_ground_items`, które używa `scene.items_sheet`, `_apply_player_state` nie przypisuje prawidłowego `image`.

## ⛓️ Constraints

- Nie psuć działającej logiki inventory (przedmioty są używalne).
- Zachować kompatybilność desktop + web.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [ ] Sprawdzić, w jaki sposób `InventoryPanel` / `HUD` renderuje ikony przedmiotów gracza.
- [ ] Porównać tworzenie `ItemSprite` w `_apply_player_state` z `_apply_ground_items`.
- [ ] Naprawić przypisanie obrazka w `_apply_player_state` (użyć `scene.items_sheet` lub innego źródła grafik).
- [ ] Uruchomić scenariusze `Save and Load Basic` / `UI Flow - Full Save Load` i zweryfikować screenshoty.

## ✅ Definition of Done

- [ ] Po loadzie inventory wyświetla pełne ikony przedmiotów.
- [ ] Screenshoty ze scenariuszy save/load pokazują poprawne inventory.
- [ ] Zmiany udokumentowane w tasku (`moab log`).
- [ ] Commit zmian wykonany.

## 📓 Agent Log


## 🙋 Needs-You / Questions

