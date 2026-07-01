---
id: T-014
title: F5 quick save zapisuje w nowym slocie
status: done
owner: human
priority: p2
type: feature
agent: opencode
created: 2026-07-01
updated: 2026-07-01
tags:
  - task
state: review
---

# T-014 — F5 quick save zapisuje w nowym slocie


## 🎯 Goal / Outcome


- [x] Klawisz F5 (quick save) zapisuje grę w pierwszym wolnym slocie zamiast zawsze nadpisywać slot 0.
- [x] Wielokrotne naciśnięcia F5 tworzą kolejne, niezależne zapisy.
- [x] Gracz dostaje powiadomienie z numerem użytego slotu (np. "Game saved in slot 3").

## 🧭 Context


- Obecnie `quick_save` w `project/game.py` wywołuje `self.save_manager.save(0)`, więc F5 zawsze zapisuje w tym samym slocie.
- MAX_SAVE_SLOTS = 10 (`project/settings.py`).
- Logika wyszukiwania wolnego slotu powinna być podobna do tej używanej przy ręcznym zapisie z panelu Save.

## ⛓️ Constraints


- Nie psuć istniejącego systemu save/load.
- Zachować kompatybilność desktop + web.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [x] Zmienić obsługę `quick_save` w `project/game.py`, aby szukała pierwszego wolnego slotu (lub najstarszego, jeśli wszystkie zajęte - do ustalenia).
- [x] Zaktualizować tekst powiadomienia "Game saved" o numer slotu.
- [x] Przejrzeć i ewentualnie zaktualizować scenariusze testowe save/load.
- [x] Przetestować ręcznie: kilka F5, potem F9 + wybranie różnych slotów.

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] commit zmian wykonany
- [x] Testy / lint przechodzą (jeśli dotyczy)

## 📓 Agent Log

- 2026-07-01 08:14 user: moved to ready
- 2026-07-01 08:14 opencode: claimed, starting
- 2026-07-01 08:19 opencode: Zaimplementowano quick_save w pierwszym wolnym slocie (fallback na najstarszy zajęty). Dodano powiadomienie z numerem slotu. Zaktualizowano scenariusz testowy Save Overwrite -> Multiple Quick Saves. Przeprowadzono testy: Save and Load Basic, Multiple Quick Saves, UI Flow - Full Save Load, Quick Save and Load, Death then Load, Auto Save on Map Change. mypy przechodzi.
- 2026-07-01 08:23 opencode: Zaimplementowano T-014. F5 zapisuje w pierwszym wolnym slocie, a gdy wszystkie zajęte - nadpisuje najstarszy. Powiadomienie pokazuje numer slotu (np. 'Game saved in slot 1'). Zaktualizowano scenariusz 'Save Overwrite' na 'Multiple Quick Saves'. Testy: Save and Load Basic, Multiple Quick Saves, UI Flow - Full Save Load, Quick Save and Load, Death then Load, Auto Save on Map Change. mypy clean. Commit: 66e71d6.
- 2026-07-01 18:44 opencode: REVIEW OK (human): mypy clean; 'Multiple Quick Saves' PASS clean; pick_quick_save_slot logic poprawna (first free -> oldest occupied). Przeniesione do Done.


## 🙋 Needs-You / Questions

