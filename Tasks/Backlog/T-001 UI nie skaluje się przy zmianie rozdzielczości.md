---
id: T-001
title: T-001 UI nie skaluje się przy zmianie rozdzielczości
status: archive
owner: human
priority: p2
type: bug
agent: opencode
created: 2026-06-26
updated: 2026-06-26
tags:
  - task
state: review
---

# T-001 — UI nie skaluje się przy zmianie rozdzielczości


## 🎯 Goal / Outcome


- [ ] Kryterium 1
- [ ] Kryterium 2

## 🧭 Context


- `project/...`

## ⛓️ Constraints


-

## 🪜 Plan / Subtasks

- [ ] Krok 1
- [ ] Krok 2

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] Testy / lint przechodzą (jeśli dotyczy)

## 📓 Agent Log

- 2026-06-27 opencode: claimed, starting
- 2026-06-27 opencode: investigating codebase structure and rendering/scaling system
- 2026-06-27 opencode: Fix implemented: decoupled logical resolution (1280x720) from physical display size. SCALE is now a dynamic float calculated from physical/logical ratio. Canvas (game world + UI) stays at logical resolution and is scaled to fill the physical screen via pygame.transform.scale(). UI renders at logical resolution and scales proportionally with the canvas. Also fixed get_random_pos() in characters.py which incorrectly used display SCALE for game-world coordinates. Commit dd49ccc.
- 2026-06-27 opencode: UI scaling fix ready. See commit dd49ccc. Test by: 1) ./run.sh, 2) Settings → Display, 3) change resolution, 4) Apply — UI should scale proportionally.


## 🙋 Needs-You / Questions

