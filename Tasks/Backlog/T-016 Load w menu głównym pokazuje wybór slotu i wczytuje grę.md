---
id: T-016
title: Load w menu głównym pokazuje wybór slotu i wczytuje grę
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

# T-016 — Load w menu głównym pokazuje wybór slotu i wczytuje grę


## 🎯 Goal / Outcome


- [ ] Przycisk "Load" w menu głównym otwiera menu wyboru slotu zapisu (tak jak obecny LoadPanel).
- [ ] Wybranie slotu wczytuje stan gry z tego slotu.
- [ ] Po wczytaniu menu główne znika i gracz od razu gra (bez tworzenia pośredniej pustej sceny w tle).

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

- [ ] Zmienić `_open_load_panel` w `project/ui/panels/main_menu.py` tak, aby nie tworzyć uprzednio nowej sceny Village.
- [ ] Upewnić się, że po wczytaniu stanu z save menu główne jest zdejmowane ze stosu (`exit_state()`).
- [ ] Obsłużyć sytuację, gdy nie ma żadnych zapisów (np. nie pokazywać "Load" w menu lub pokazać panel z informacją o braku zapisów).
- [ ] Przetestować ręcznie: zapis, wyjście do menu, Load, powrót do gry.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] commit zmian wykonany
- [ ] Testy / lint przechodzą (jeśli dotyczy)

## 📓 Agent Log


## 🙋 Needs-You / Questions

