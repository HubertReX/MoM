---
id: T-016
title: Load w menu głównym pokazuje wybór slotu i wczytuje grę
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

# T-016 — Load w menu głównym pokazuje wybór slotu i wczytuje grę


## 🎯 Goal / Outcome


- [x] Przycisk "Load" w menu głównym otwiera menu wyboru slotu zapisu (tak jak obecny LoadPanel).
- [x] Wybranie slotu wczytuje stan gry z tego slotu.
- [x] Po wczytaniu menu główne znika i gracz od razu gra (bez tworzenia pośredniej pustej sceny w tle).

## 🧭 Context


- Obecnie "Load" w `project/ui/panels/main_menu.py` tworzy najpierw `Scene(game, "Village", "start")`, a dopiero potem otwiera `LoadPanel`.
- Powoduje to, że pod panelem wczytywania jest już nowa, pusta scena, co jest zbędne i może powodować mrugnięcie.
- LoadPanel (`project/ui/panels/save_load.py`) już potrafi wyświetlać zajęte sloty i wczytywać wybrany.

## ⛓️ Constraints


- Nie psuć istniejącego LoadPanel.
- Zachować kompatybilność desktop + web.
- Type hints wymagane.
- Pusty slot nie powinien być wybieralny do wczytania.

## 🪜 Plan / Subtasks

- [x] Zmienić `_open_load_panel` w `project/ui/panels/main_menu.py` tak, aby nie tworzyć uprzednio nowej sceny Village.
- [x] Upewnić się, że po wczytaniu stanu z save menu główne jest zdejmowane ze stosu (`exit_state()`).
- [x] Obsłużyć sytuację, gdy nie ma żadnych zapisów (np. nie pokazywać "Load" w menu lub pokazać panel z informacją o braku zapisów).
- [x] Przetestować ręcznie: zapis, wyjście do menu, Load, powrót do gry.

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [ ] commit zmian wykonany
- [x] Testy / lint przechodzą (jeśli dotyczy)

## 📓 Agent Log

- 2026-07-01 16:56 user: moved to ready
- 2026-07-01 17:06 opencode: claimed, starting
- 2026-07-01 17:34 opencode: Zaimplementowano Load z menu głównego: dodano LoadMenuScreen, który hostuje istniejący LoadPanel bez tworzenia pustej sceny Village; LoadPanel rozszerzony o opcjonalny on_load callback; menu główne znika po wczytaniu; puste sloty niewybieralne (LoadPanel filtruje); opcja Load ukryta gdy brak zapisów. Testy: 'Load from Main Menu' PASS, 'Save and Load Basic' PASS, 'UI Flow - Full Save Load' PASS, mypy/isort/py_compile clean.
- 2026-07-01 17:36 opencode: Gotowe do review. Zmiany w project/ui/panels/main_menu.py i save_load.py. Przetestowano scenariuszami 'Load from Main Menu', 'Save and Load Basic' i 'UI Flow - Full Save Load'. mypy/isort/py_compile clean.
- 2026-07-01 18:44 opencode: REVIEW OK (human): mypy clean; feature dziala - 'Load from Main Menu' PASS przy czystych savach (save_0 tworzy sie przez quick_save, load z menu, menu znika). Uwaga MINOR: scenariusz 'Load from Main Menu' ma kruche cleanup_saves:[0] - przy pozostawionych savach w slotach 1+ (np. po 'Multiple Quick Saves') asercja file_exists save_0.mom moze nie przejsc w pelnym suite. Do naprawy gdy T-009 (runner restart) bedzie gotowy - rozszerzyc cleanup_saves na wszystkie sloty. Nie bloka feature. Przeniesione do Done.


## 🙋 Needs-You / Questions

