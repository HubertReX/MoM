---
id: T-010
title: Save Overwrite wczytuje stary stan zamiast nadpisanego zapisu
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

# T-010 — Save Overwrite wczytuje stary stan zamiast nadpisanego zapisu


## 🎯 Goal / Outcome

Naprawić błąd w systemie save/load, polegający na tym, że po nadpisaniu zapisu i jego wczytaniu gra przywraca stan pośredni, a nie ostatnio zapisany. Scenariusz `Save Overwrite` powinien po `quick_save` (pierwszym), ruchu gracza, `quick_save` (nadpisaniu) i wczytaniu pokazywać pozycję i czas z momentu nadpisania.

- [ ] `SaveManager.save(0)` nadpisuje istniejący slot nowym stanem.
- [ ] `SaveManager.load(0)` wczytuje dokładnie ten sam stan, który został zapisany w ostatnim overwrite.
- [ ] Po wczytaniu pozycja gracza i czas gry zgadzają się z zawartością pliku `.mom`.

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

- [ ] Zweryfikować, czy `LoadPanel` przy otwarciu nie zaznacza innego slotu niż 0.
- [ ] Sprawdzić, czy `_apply_save_game` w `SaveManager` poprawnie zamyka stary stan i odtwarza nowy (pozycja, czas, kamera).
- [ ] Sprawdzić, czy `Scene.__init__` nie nadpisuje czasu/pozycji po `_apply_game_clock` / `_apply_player_state`.
- [ ] Naprawić przyczynę i przeprowadzić scenariusz `Save Overwrite` kilka razy, aby potwierdzić powtarzalność.

## ✅ Definition of Done

- [ ] Scenariusz `Save Overwrite` po wczytaniu pokazuje stan z ostatniego nadpisania (czas ~9:11 i przesuniętą pozycję).
- [ ] Plik `save_0.mom` po scenariuszu zawiera spójne dane z wczytanym stanem.
- [ ] Zmiany udokumentowane w tasku (`moab log`).
- [ ] Commit zmian wykonany.

## 📓 Agent Log

- 2026-06-30 opencode: claimed, starting


## 🙋 Needs-You / Questions

