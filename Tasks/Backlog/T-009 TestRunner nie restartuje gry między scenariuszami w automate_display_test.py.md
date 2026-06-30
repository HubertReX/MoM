---
id: T-009
title: TestRunner nie restartuje gry między scenariuszami w automate_display_test.py
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

# T-009 — TestRunner nie restartuje gry między scenariuszami w automate_display_test.py


## 🎯 Goal / Outcome

Naprawić `tests/automate_display_test.py` tak, aby każdy scenariusz był wykonywany na żywej instancji gry. Obecnie `TestRunner.start_game()` uruchamia grę tylko raz, a `cleanup()` zabija proces po każdym scenariuszu. Kolejne scenariusze wysyłają komendy do martwego procesu, co powoduje, że pełny przebieg (`python3 tests/automate_display_test.py` bez argumentu) daje fałszywe wyniki.

- [ ] `TestRunner` restartuje grę przed każdym scenariuszem (lub nie zabija jej między scenariuszami w sposób, który uniemożliwia kontynuację).
- [ ] Pełny przebieg wszystkich scenariuszy generuje zrzuty ekranu dla każdej akcji `screenshot`.
- [ ] Po każdym scenariuszu stan gry jest resetowany (brak wpływu kolejnych scenariuszy na poprzednie).

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

- [ ] Zmienić `TestRunner.run_scenario()` tak, aby uruchamiało grę przed scenariuszem (lub przenieść `start_game()` do wewnątrz pętli scenariuszy).
- [ ] Upewnić się, że `cleanup()` czeka na zakończenie procesu przed uruchomieniem nowej instancji.
- [ ] Zweryfikować, że pełny przebieg generuje wszystkie screenshoty i żadna gra nie zostaje w tle.

## ✅ Definition of Done

- [ ] Pełny przebieg `python3 tests/automate_display_test.py` wykonuje każdy scenariusz na żywej grze.
- [ ] Liczba plików w `screenshots/agent/` odpowiada liczbie akcji `screenshot` we wszystkich scenariuszach.
- [ ] Brak wiszących procesów Python/pygame po zakończeniu testu.
- [ ] Zmiany udokumentowane w tasku (`moab log`).
- [ ] Commit zmian wykonany.

## 📓 Agent Log


## 🙋 Needs-You / Questions

