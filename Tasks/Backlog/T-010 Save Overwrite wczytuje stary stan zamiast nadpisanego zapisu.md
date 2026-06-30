---
id: T-010
title: Save Overwrite wczytuje stary stan zamiast nadpisanego zapisu
status: needs-you
owner: human
priority: p1
type: bug
agent: opencode
created: 2026-06-30
updated: 2026-06-30
tags:
  - task
state: review
---

# T-010 — Save Overwrite wczytuje stary stan zamiast nadpisanego zapisu


## 🎯 Goal / Outcome

Naprawić błąd w systemie save/load, polegający na tym, że po nadpisaniu zapisu i jego wczytaniu gra przywraca stan pośredni, a nie ostatnio zapisany. Scenariusz `Save Overwrite` powinien po `quick_save` (pierwszym), ruchu gracza, `quick_save` (nadpisaniu) i wczytaniu pokazywać pozycję i czas z momentu nadpisania.

- [x] `SaveManager.save(0)` nadpisuje istniejący slot nowym stanem.
- [x] `SaveManager.load(0)` wczytuje dokładnie ten sam stan, który został zapisany w ostatnim overwrite.
- [x] Po wczytaniu pozycja gracza i czas gry zgadzają się z zawartością pliku `.mom`.

## 🧭 Context

- Problem wykryty podczas weryfikacji T-008 (`Save-load test scenarios`).
- Scenariusz `Save Overwrite` w `tests/scenarios.json`:
  1. `quick_save` (slot 0) - stan A, czas ~9:04.
  2. `right:30` - gracz się przesuwa.
  3. `quick_save` (nadpisanie slotu 0) - stan B, czas ~9:11-9:12.
  4. `quick_load` + dwa razy `accept` - wczytanie slotu 0.
  5. Screenshot pokazuje czas ~9:05 i pozycję pośrednią, a nie stan B.
- Plik `save_0.mom` po scenariuszu zawiera timestamp odpowiadający nadpisaniu i godzinę 9:11, więc zapis przebiega poprawnie. Błąd jest prawdopodobnie w `SaveManager.load()` lub w przejściu ze starym `Scene` z otwartym `LoadPanel`.

## ⛓️ Constraints

- Nie psuć działających scenariuszy `Save and Load Basic`, `Quick Save and Load`, `Death then Load`, `UI Flow - Full Save Load`.
- Zachować kompatybilność desktop + web.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [x] Zweryfikować, czy `LoadPanel` przy otwarciu nie zaznacza innego slotu niż 0.
- [x] Sprawdzić, czy `_apply_save_game` w `SaveManager` poprawnie zamyka stary stan i odtwarza nowy (pozycja, czas, kamera).
- [x] Sprawdzić, czy `Scene.__init__` nie nadpisuje czasu/pozycji po `_apply_game_clock` / `_apply_player_state`.
- [x] Naprawić przyczynę i przeprowadzić scenariusz `Save Overwrite` kilka razy, aby potwierdzić powtarzalność.

## ✅ Definition of Done

- [x] Scenariusz `Save Overwrite` po wczytaniu pokazuje stan z ostatniego nadpisania (czas ~9:11 i przesuniętą pozycję).
- [x] Plik `save_0.mom` po scenariuszu zawiera spójne dane z wczytanym stanem.
- [x] Zmiany udokumentowane w tasku (`moab log`).
- [x] Commit zmian wykonany.

## 📓 Agent Log

- 2026-06-30 opencode: claimed, starting
- 2026-06-30 opencode: claimed, starting
- 2026-06-30 20:40 opencode: claimed, starting
- 2026-06-30 20:41 user: moved to ready
- 2026-06-30 20:42 opencode: claimed, starting
- 2026-06-30 20:43 user: moved to ready
- 2026-06-30 20:52 opencode: claimed, starting
- 2026-06-30 21:07 opencode: Znaleziono przyczynę: _apply_game_clock resetował scene.minute_f do 0.0, więc kolejna klatka Scene.update nadpisywała scene.minute wartością int(minute_f) zamiast zapisanego czasu. Dodatkowo game.time_elapsed nie był przywracany z zapisu. Naprawiono: minute_f = float(clock.minute) oraz game.time_elapsed = clock.time_elapsed. Przetestowano scenariusze Save Overwrite, Save and Load Basic, Quick Save and Load, Death then Load, UI Flow - Full Save Load oraz testy jednostkowe save_load.
- 2026-06-30 21:12 opencode: Naprawiono błąd w SaveManager._apply_game_clock: scene.minute_f jest teraz ustawiane na zapisaną minutę (zamiast 0.0), a game.time_elapsed jest przywracane z zapisu. Dzięki temu po overwrite + load gra pokazuje czas i pozycję z momentu nadpisania. Przetestowano scenariusze Save Overwrite, Save and Load Basic, Quick Save and Load, Death then Load, UI Flow - Full Save Load oraz testy jednostkowe save_load (28/28 passed). Zmiany gotowe do commita.


## 🙋 Needs-You / Questions

