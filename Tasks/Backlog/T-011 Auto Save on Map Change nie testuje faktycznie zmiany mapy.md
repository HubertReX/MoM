---
id: T-011
title: Auto Save on Map Change nie testuje faktycznie zmiany mapy
status: ready
owner: ai
priority: p2
type: bug
agent:
created: 2026-06-30
updated: 2026-06-30
tags:
  - task
---

# T-011 — Auto Save on Map Change nie testuje faktycznie zmiany mapy


## 🎯 Goal / Outcome

Uzupełnić scenariusz `Auto Save on Map Change` w `tests/scenarios.json` tak, aby faktycznie testował automatyczny zapis przy zmianie mapy. Obecnie scenariusz kończy się po starcie gry i jednym zrzucie ekranu, więc nie sprawdza, czy auto-save został utworzony.

- [ ] Scenariusz powoduje zmianę mapy (np. wejście do budynku, przejście do Maze).
- [ ] Po zmianie mapy scenariusz weryfikuje obecność auto-save (np. przez `debug_settings`, komendę pomocniczą lub asercję na pliku `.mom`).
- [ ] Screenshot dokumentuje nową mapę i/lub panel load z auto-save.

## 🧭 Context

- Wykonano testy automatyczne jako część weryfikacji T-008.
- Obecny scenariusz w `tests/scenarios.json`:
  ```json
  { "label": "Start New Game", "commands": ["accept"], "wait": 3.0 },
  { "label": "Scene loaded - auto-save triggered", "commands": ["screenshot"] }
  ```
- W grze auto-save jest wywoływany w `Scene.go_to_map()` (zgodnie z notatką T-007), więc test musi zmienić mapę, aby go aktywować.
- Można wykorzystać istniejące komendy `agent_ctrl.py` lub dodać komendę debugową do teleportacji/zmiany mapy.

## ⛓️ Constraints

- Scenariusz musi być deterministyczny i działać z `SDL_VIDEODRIVER=dummy`.
- Nie psuć innych scenariuszy.
- Minimalna ingerencja w kod gry - preferowana zmiana `tests/scenarios.json` i ewentualnie drobna komenda w `agent_ctrl.py`.

## 🪜 Plan / Subtasks

- [ ] Znaleźć sposób na deterministyczną zmianę mapy z poziomu agenta (np. dojście do warp point lub komenda debugowa).
- [ ] Rozszerzyć scenariusz `Auto Save on Map Change` o kroki zmiany mapy i weryfikacji auto-save.
- [ ] Uruchomić scenariusz pojedynczo i potwierdzić, że plik auto-save pojawia się w `~/Library/Application Support/mom/saves/` (lub odpowiedniku).

## ✅ Definition of Done

- [ ] Scenariusz `Auto Save on Map Change` zmienia mapę i weryfikuje auto-save.
- [ ] Test przechodzi pojedynczo i nie crashuje gry.
- [ ] Zmiany udokumentowane w tasku (`moab log`).
- [ ] Commit zmian wykonany.

## 📓 Agent Log

- 2026-06-30 opencode: claimed, starting
- 2026-06-30 opencode: claimed, starting
- 2026-06-30 20:41 opencode: claimed, starting
- 2026-06-30 20:42 user: moved to ready
- 2026-06-30 20:43 opencode: claimed, starting
- 2026-06-30 20:52 user: moved to ready
- 2026-06-30 21:20 opencode: claimed, starting
- 2026-06-30 21:23 user: watcher ze starej sesji zclaimował, cofnięte do Ready


## 🙋 Needs-You / Questions

