---
id: T-012
title: quick_load nie zamyka otwartego LoadPanel w testach
status: in-progress
owner: ai
priority: p2
type: bug
agent: opencode
created: 2026-06-30
updated: 2026-06-30
tags:
  - task
---

# T-012 — quick_load nie zamyka otwartego LoadPanel w testach


## 🎯 Goal / Outcome

Umożliwić zamknięcie `LoadPanel` z poziomu scenariuszy testowych. W scenariuszach `Corrupt Save Handling` i `Empty Slot Load` drugie `quick_load` powinno zamknąć panel (zgodnie z założeniem testów), ale zrzuty ekranu pokazują `Load Game` nadal otwarty.

- [ ] Drugie `quick_load` w scenariuszu `Empty Slot Load` zamyka pusty panel load.
- [ ] Drugie `quick_load` w scenariuszu `Corrupt Save Handling` zamyka panel load po pokazaniu pustej listy.
- [ ] Screenshot po zamknięciu nie zawiera panelu `Load Game`.

## 🧭 Context

- Problem wykryty podczas weryfikacji T-008 (`Save-load test scenarios`).
- W `game.py` `quick_load` toggluje `LoadPanel` przez `state.ui.toggle(_LP)`.
- W `tests/scenarios.json` scenariusze zakładają, że ponowne `quick_load` zamknie otwarty panel:
  - `Empty Slot Load`: `quick_load` (otwarcie), `screenshot`, `quick_load` (zamknięcie), `screenshot`.
  - `Corrupt Save Handling`: `quick_load` (otwarcie), `screenshot`, `quick_load` (zamknięcie), `screenshot`.
- Obecnie ostatni screenshot w obu scenariuszach pokazuje nadal otwarty panel.

## ⛓️ Constraints

- Jeśli to błąd w grze: naprawić `quick_load` / `LoadPanel` tak, aby toggle działał niezawodnie przy szybkich komendach.
- Jeśli to błąd w testach: zmienić sposób zamykania panelu (np. `escape` lub dłuższa pauza).
- Nie psuć działających scenariuszy save/load.

## 🪜 Plan / Subtasks

- [ ] Sprawdzić, czy `quick_load` jako akcja ciągła/przytrzymywana nie powoduje wielokrotnego otwarcia/zamknięcia panelu w jednej klatce.
- [ ] Sprawdzić, czy `agent_ctrl.py` poprawnie kolejkuje `quick_load` jako pojedynczy impuls.
- [ ] Jeśli to problem testowy: zmienić `quick_load` na `escape` lub dodać pauzę przed drugim `quick_load`.
- [ ] Jeśli to problem gry: naprawić toggle w `LoadPanel` / `GameUI`.
- [ ] Uruchomić oba scenariusze i zweryfikować zrzuty ekranu.

## ✅ Definition of Done

- [ ] Scenariusze `Corrupt Save Handling` i `Empty Slot Load` kończą się z zamkniętym panelem load.
- [ ] Zmiany udokumentowane w tasku (`moab log`).
- [ ] Commit zmian wykonany.

## 📓 Agent Log

- 2026-06-30 opencode: claimed, starting


## 🙋 Needs-You / Questions

