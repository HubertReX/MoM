---
id: T-015
title: Continue w menu głównym tylko przy trwającej grze
status: archive
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

# T-015 — Continue w menu głównym tylko przy trwającej grze


## 🎯 Goal / Outcome


- [x] Przycisk "Continue" w menu głównym jest widoczny tylko wtedy, gdy gra została już rozpoczęta w bieżącej sesji (jest aktywna scena na stanie gry).
- [x] "Continue" nie wczytuje żadnego zapisu z dysku - po prostu wraca do aktualnie trwającej gry.
- [x] Gdy nie ma trwającej gry, "Continue" nie pojawia się w menu (zamiast niego widać tylko Load / New Game / Settings / About / Quit).

## 🧭 Context


- Obecnie "Continue" w `project/ui/panels/main_menu.py` szuka ostatniego zajętego slotu i wywołuje `sm.load(last_idx)`.
- Użytkownik chce, aby "Continue" kontynuował bieżącą sesję, a wczytywanie zapisu było domeną "Load".
- Trzeba rozróżnić stan: "w menu po uruchomieniu gry" vs "w menu podczas pauzy w trakcie rozgrywki".

## ⛓️ Constraints


- Nie psuć menu głównego ani pauzy.
- Zachować kompatybilność desktop + web.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [x] Dodać wykrywanie, czy gra jest w toku (np. czy na stosie stanów `game.states` znajduje się `Scene`, a nie tylko menu).
- [x] Zmienić logikę budowania menu: "Continue" tylko gdy gra trwa.
- [x] Zmienić akcję "Continue" na powrót do gry (np. `exit_state()` menu lub wznowienie z pauzy), bez wywoływania `save_manager.load()`.
- [x] Upewnić się, że "Load" nadal działa niezależnie.

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [ ] commit zmian wykonany
- [x] Testy / lint przechodzą (jeśli dotyczy)

## 📓 Agent Log

- 2026-07-01 16:56 user: moved to ready
- 2026-07-01 16:56 opencode: claimed, starting
- 2026-07-01 17:03 opencode: Zmieniono logikę Continue: widoczne tylko gdy gra trwa, wraca do sceny przez exit_state(). Lint/isort/mypy OK, testy automatyczne PASS.
- 2026-07-01 17:05 opencode: Zrealizowano T-015. Zmiany: project/ui/panels/main_menu.py - Continue widoczne tylko gdy na stosie stanów jest Scene, akcja wraca do gry przez exit_state(). Load zawsze widoczne. Dodano type hints. Testy: mypy/isort/py_compile PASS, 'Save and Load Basic' PASS, ręczny test wizualny z agent_ctrl PASS (3 screenshoty: menu bez Continue, menu z Continue, powrót do gry).
- 2026-07-01 18:44 opencode: REVIEW OK (human): mypy clean; _is_game_in_progress (Scene on stack) + _continue_game=exit_state; kod spojny z main_menu. Uwaga bookkeeping: zmiany zostaly commitowane w ramieniu commita T-016 (efd6d94) - DoD 'commit wykonany' odznaczony omylkowo, faktycznie commit jest. Przeniesione do Done.


## 🙋 Needs-You / Questions

