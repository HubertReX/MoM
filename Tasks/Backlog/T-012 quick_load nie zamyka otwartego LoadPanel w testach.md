---
id: T-012
title: quick_load nie zamyka otwartego LoadPanel w testach
status: archive
owner: human
priority: p2
type: bug
agent: opencode
created: 2026-06-30
updated: 2026-06-30
tags:
  - task
state: review
---

# T-012 — quick_load nie zamyka otwartego LoadPanel w testach


## 🎯 Goal / Outcome

Umożliwić zamknięcie `LoadPanel` z poziomu scenariuszy testowych. W scenariuszach `Corrupt Save Handling` i `Empty Slot Load` drugie `quick_load` powinno zamknąć panel (zgodnie z założeniem testów), ale zrzuty ekranu pokazują `Load Game` nadal otwarty.

- [x] Drugie `quick_load` w scenariuszu `Empty Slot Load` zamyka pusty panel load.
- [x] Drugie `quick_load` w scenariuszu `Corrupt Save Handling` zamyka panel load po pokazaniu pustej listy.
- [x] Screenshot po zamknięciu nie zawiera panelu `Load Game`.

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

- [x] Sprawdzić, czy `quick_load` jako akcja ciągła/przytrzymywana nie powoduje wielokrotnego otwarcia/zamknięcia panelu w jednej klatce.
- [x] Sprawdzić, czy `agent_ctrl.py` poprawnie kolejkuje `quick_load` jako pojedynczy impuls.
- [x] Jeśli to problem testowy: zmienić `quick_load` na `escape` lub dodać pauzę przed drugim `quick_load`.
- [x] Jeśli to problem gry: naprawić toggle w `LoadPanel` / `GameUI`.
- [x] Uruchomić oba scenariusze i zweryfikować zrzuty ekranu.

## ✅ Definition of Done

- [x] Scenariusze `Corrupt Save Handling` i `Empty Slot Load` kończą się z zamkniętym panelem load.
- [x] Zmiany udokumentowane w tasku (`moab log`).
- [ ] Commit zmian wykonany.

## 📓 Agent Log

- 2026-06-30 opencode: claimed, starting
- 2026-06-30 opencode: Zatrzymano wiszącą sesję T-012 i cofnięto do Ready
- 2026-06-30 19:25 opencode: claimed, starting
- 2026-06-30 20:17 user: moved to ready
- 2026-06-30 20:40 user: moved to needs-you
- 2026-06-30 20:42 user: moved to ready
- 2026-06-30 20:44 user: moved to needs-you
- 2026-06-30 20:44 user: moved to ready
- 2026-06-30 21:15 opencode: claimed, starting
- 2026-06-30 21:19 user: moved to ready
- 2026-06-30 21:23 opencode: claimed, starting
- 2026-06-30 21:29 user: moved to ready
- 2026-06-30 21:35 opencode: claimed, starting
- 2026-06-30 21:36 user: moved to ready
- 2026-06-30 21:43 user: moved to backlog
- 2026-06-30 21:43 user: moved to ready
- 2026-06-30 21:43 opencode: claimed, starting
- 2026-06-30 21:51 opencode: Rozdzielono komendy quick_load i screenshot na osobne akcje w tests/scenarios.json dla scenariuszy Empty Slot Load i Corrupt Save Handling. Dzieki temu screenshot jest robiony po zarejestrowaniu toggle przez gre, a nie w tej samej klatce co KEYDOWN. Przetestowano pojedynczo: Empty Slot Load, Corrupt Save Handling, Auto Save on Map Change oraz Save and Load Basic - we wszystkich ostatni screenshot pokazuje zamkniety panel Load Game.
- 2026-06-30 21:51 opencode: Do weryfikacji: scenariusze Empty Slot Load i Corrupt Save Handling. Ostatni screenshot w obu powinien pokazywac zamkniety panel Load Game. Zmiana polega na rozdzieleniu komend quick_load i screenshot na osobne akcje w tests/scenarios.json.


## 🙋 Needs-You / Questions

