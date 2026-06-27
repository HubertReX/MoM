---
id: T-002
title: ekran nie przesuwa się na środek po zmianie rozdzielczości
status: needs-you
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

# T-002 — ekran nie przesuwa się na środek po zmianie rozdzielczości


## 🎯 Goal / Outcome


- [ ] po zmianie rozdzielczości gry okno jest wyśrodkowane
- [ ] jeżeli rozdzielczość gry jest większa od rozdzielczości ekranu to okno jest dosunięte do lewego górnego rogu

## 🧭 Context


- brak

## ⛓️ Constraints

- nie zmieniaj innych części gry

## 🪜 Plan / Subtasks

- brak

## ✅ Definition of Done

- brak

## 📓 Agent Log

- 2026-06-27 opencode: claimed, starting
- 2026-06-27 opencode: Added window centering in game.py:set_display() via pygame._sdl2.video.Window. Centered if window fits desktop, top-left (0,0) if larger. Guarded with not IS_WEB.
- 2026-06-27 opencode: Fixed window positioning after resolution change: (1) window is centered on desktop via pygame._sdl2.video.Window.position, (2) if game resolution exceeds desktop, window goes to (0,0). Guarded by not IS_WEB. isort + mypy pass.


## 🙋 Needs-You / Questions

