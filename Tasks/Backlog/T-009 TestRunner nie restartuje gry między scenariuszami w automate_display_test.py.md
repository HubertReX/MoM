---
id: T-009
title: TestRunner nie restartuje gry między scenariuszami w automate_display_test.py
status: done
owner: human
priority: p1
type: bug
agent:
created: 2026-06-30
updated: 2026-06-30
tags:
  - task
state: review
---

# T-009 — TestRunner nie restartuje gry między scenariuszami w automate_display_test.py


## 🎯 Goal / Outcome

Naprawić `tests/automate_display_test.py` tak, aby każdy scenariusz był wykonywany na żywej instancji gry. Obecnie `TestRunner.start_game()` uruchamia grę tylko raz, a `cleanup()` zabija proces po każdym scenariuszu. Kolejne scenariusze wysyłają komendy do martwego procesu, co powoduje, że pełny przebieg (`python3 tests/automate_display_test.py` bez argumentu) daje fałszywe wyniki.

- [x] `TestRunner` restartuje grę przed każdym scenariuszem (lub nie zabija jej między scenariuszami w sposób, który uniemożliwia kontynuację).
- [x] Pełny przebieg wszystkich scenariuszy generuje zrzuty ekranu dla każdej akcji `screenshot`.
- [x] Po każdym scenariuszu stan gry jest resetowany (brak wpływu kolejnych scenariuszy na poprzednie).

## 🧭 Context

- Wykonano testy automatyczne z `tests/scenarios.json` jako część weryfikacji T-005-T-008.
- Przy uruchomieniu pojedynczego scenariusza (`python3 tests/automate_display_test.py "Nazwa"`) gra startuje i działa poprawnie.
- Przy uruchomieniu wszystkich scenariuszy naraz (`python3 tests/automate_display_test.py`) `cleanup()` w `run_scenario()` wysyła `SIGTERM` do grupy procesów, ale gra nie jest uruchamiana ponownie przed kolejnym scenariuszem.
- W katalogu `screenshots/agent/` po pełnym przebiegu pojawia się tylko 5 zrzutów zamiast kilkudziesięciu.

## ⛓️ Constraints

- Zachować możliwość uruchamiania pojedynczych scenariuszy przez argument wiersza poleceń.
- Nie psuć istniejących scenariuszy save/load.
- Desktop-only (`SDL_VIDEODRIVER=dummy`).

## 🪜 Plan / Subtasks

- [x] Zmienić `TestRunner.run_scenario()` tak, aby uruchamiało grę przed scenariuszem (lub przenieść `start_game()` do wewnątrz pętli scenariuszy).
- [x] Upewnić się, że `cleanup()` czeka na zakończenie procesu przed uruchomieniem nowej instancji.
- [x] Zweryfikować, że pełny przebieg generuje wszystkie screenshoty i żadna gra nie zostaje w tle.

## ✅ Definition of Done

- [x] Pełny przebieg `python3 tests/automate_display_test.py` wykonuje każdy scenariusz na żywej grze.
- [x] Liczba plików w `screenshots/agent/` odpowiada liczbie akcji `screenshot` we wszystkich scenariuszach.
- [x] Brak wiszących procesów Python/pygame po zakończeniu testu.
- [x] Zmiany udokumentowane w tasku (`moab log`).
- [x] Commit zmian wykonany.

## 📓 Agent Log

- 2026-06-30 opencode: claimed, starting
- 2026-06-30 opencode: moved `start_game()` into `run_scenario()`; added `cleanup()` wait for process termination and input-file clear; verified single + full run (28 screenshots, no hanging processes)
- 2026-07-01 09:49 user: moved to done


## 🙋 Needs-You / Questions

