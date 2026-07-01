---
id: T-015
title: Continue w menu głównym tylko przy trwającej grze
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

# T-015 — Continue w menu głównym tylko przy trwającej grze


## 🎯 Goal / Outcome


- [ ] Przycisk "Continue" w menu głównym jest widoczny tylko wtedy, gdy gra została już rozpoczęta w bieżącej sesji (jest aktywna scena na stanie gry).
- [ ] "Continue" nie wczytuje żadnego zapisu z dysku - po prostu wraca do aktualnie trwającej gry.
- [ ] Gdy nie ma trwającej gry, "Continue" nie pojawia się w menu (zamiast niego widać tylko Load / New Game / Settings / About / Quit).

## 🧭 Context


- Obecnie "Continue" w `project/ui/panels/main_menu.py` szuka ostatniego zajętego slotu i wywołuje `sm.load(last_idx)`.
- Użytkownik chce, aby "Continue" kontynuował bieżącą sesję, a wczytywanie zapisu było domeną "Load".
- Trzeba rozróżnić stan: "w menu po uruchomieniu gry" vs "w menu podczas pauzy w trakcie rozgrywki".

## ⛓️ Constraints


- Nie psuć menu głównego ani pauzy.
- Zachować kompatybilność desktop + web.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [ ] Dodać wykrywanie, czy gra jest w toku (np. czy na stosie stanów `game.states` znajduje się `Scene`, a nie tylko menu).
- [ ] Zmienić logikę budowania menu: "Continue" tylko gdy gra trwa.
- [ ] Zmienić akcję "Continue" na powrót do gry (np. `exit_state()` menu lub wznowienie z pauzy), bez wywoływania `save_manager.load()`.
- [ ] Upewnić się, że "Load" nadal działa niezależnie.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] commit zmian wykonany
- [ ] Testy / lint przechodzą (jeśli dotyczy)

## 📓 Agent Log


## 🙋 Needs-You / Questions

