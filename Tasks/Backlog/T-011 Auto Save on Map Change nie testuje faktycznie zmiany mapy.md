---
id: T-011
title: Auto Save on Map Change nie testuje faktycznie zmiany mapy
status: archive
owner: human
priority: p2
type: bug
agent:
created: 2026-06-30
updated: 2026-06-30
tags:
  - task
state: review
---

# T-011 — Auto Save on Map Change nie testuje faktycznie zmiany mapy


## 🎯 Goal / Outcome

Uzupełnić scenariusz `Auto Save on Map Change` w `tests/scenarios.json` tak, aby faktycznie testował automatyczny zapis przy zmianie mapy. Obecnie scenariusz kończy się po starcie gry i jednym zrzucie ekranu, więc nie sprawdza, czy auto-save został utworzony.

- [x] Scenariusz powoduje zmianę mapy (np. wejście do budynku, przejście do Maze).
- [x] Po zmianie mapy scenariusz weryfikuje obecność auto-save (np. przez `debug_settings`, komendę pomocniczą lub asercję na pliku `.mom`).
- [x] Screenshot dokumentuje nową mapę i/lub panel load z auto-save.

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

- [x] Znaleźć sposób na deterministyczną zmianę mapy z poziomu agenta (np. dojście do warp point lub komenda debugowa).
- [x] Rozszerzyć scenariusz `Auto Save on Map Change` o kroki zmiany mapy i weryfikacji auto-save.
- [x] Uruchomić scenariusz pojedynczo i potwierdzić, że plik auto-save pojawia się w `~/Library/Application Support/mom/saves/` (lub odpowiedniku).

## ✅ Definition of Done

- [x] Scenariusz `Auto Save on Map Change` zmienia mapę i weryfikuje auto-save.
- [x] Test przechodzi pojedynczo i nie crashuje gry.
- [x] Zmiany udokumentowane w tasku (`moab log`).
- [x] Commit zmian wykonany.

## 📓 Agent Log

- 2026-06-30 opencode: claimed, starting
- 2026-06-30 opencode: claimed, starting
- 2026-06-30 20:41 opencode: claimed, starting
- 2026-06-30 20:42 user: moved to ready
- 2026-06-30 20:43 opencode: claimed, starting
- 2026-06-30 20:52 user: moved to ready
- 2026-06-30 21:20 opencode: claimed, starting
- 2026-06-30 21:23 user: watcher ze starej sesji zclaimował, cofnięte do Ready
- 2026-06-30 21:29 opencode: claimed, starting
- 2026-06-30 21:35 user: moved to ready
- 2026-06-30 21:37 opencode: claimed, starting
- 2026-06-30 21:41 opencode: Rozszerzono runnera testów o opcjonalne asercje plikowe oraz cleanup slotów save. Scenariusz Auto Save on Map Change czyści slot 0, zmienia mapę przez debug_map_change i aseryuje obecność <save_dir>/save_0.mom. Test przechodzi pojedynczo.
- 2026-06-30 21:42 opencode: Scenariusz Auto Save on Map Change rozszerzony o cleanup slotu 0, zmianę mapy (debug_map_change) oraz asercję plikową <save_dir>/save_0.mom. Runner testów obsługuje teraz opcjonalne assertions i cleanup_saves. Test przechodzi pojedynczo. Pozostałe scenariusze (Save and Load Basic, Empty Slot Load) nie uległy regresji.
- 2026-07-01 19:01 user: moved to done


## 🙋 Needs-You / Questions

