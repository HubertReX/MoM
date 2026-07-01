---
id: T-014
title: F5 quick save zapisuje w nowym slocie
status: backlog
owner: human
priority: p2
type: feature
agent:
created: 2026-07-01
updated: 2026-07-01
tags:
  - task
---

# T-014 — F5 quick save zapisuje w nowym slocie


## 🎯 Goal / Outcome


- [ ] Klawisz F5 (quick save) zapisuje grę w pierwszym wolnym slocie zamiast zawsze nadpisywać slot 0.
- [ ] Wielokrotne naciśnięcia F5 tworzą kolejne, niezależne zapisy.
- [ ] Gracz dostaje powiadomienie z numerem użytego slotu (np. "Game saved in slot 3").

## 🧭 Context


- Obecnie `quick_save` w `project/game.py` wywołuje `self.save_manager.save(0)`, więc F5 zawsze zapisuje w tym samym slocie.
- MAX_SAVE_SLOTS = 10 (`project/settings.py`).
- Logika wyszukiwania wolnego slotu powinna być podobna do tej używanej przy ręcznym zapisie z panelu Save.

## ⛓️ Constraints


- Nie psuć istniejącego systemu save/load.
- Zachować kompatybilność desktop + web.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [ ] Zmienić obsługę `quick_save` w `project/game.py`, aby szukała pierwszego wolnego slotu (lub najstarszego, jeśli wszystkie zajęte - do ustalenia).
- [ ] Zaktualizować tekst powiadomienia "Game saved" o numer slotu.
- [ ] Przejrzeć i ewentualnie zaktualizować scenariusze testowe save/load.
- [ ] Przetestować ręcznie: kilka F5, potem F9 + wybranie różnych slotów.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] commit zmian wykonany
- [ ] Testy / lint przechodzą (jeśli dotyczy)

## 📓 Agent Log


## 🙋 Needs-You / Questions

