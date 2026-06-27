---
id: T-004
title: zmiana ustawień wyświetlania bez potwierdzania
status: done
owner: human
priority: p1
type: feature
agent: opencode
created: 2026-06-27
updated: 2026-06-27
tags:
  - task
state: review
---

# T-004 — zmiana ustawień wyświetlania bez potwierdzania


## 🎯 Goal / Outcome


- [x] po wybraniu rozdzielczości i naciśnięciu enter, zmiana od razu jest zastosowana
- [x] po zmianie trybu full screen on/off zmiana od razu jest zastosowana
- [x] przycisk "Apply (restarts game)" jest usuwanięty z "Display Settings"

## 🧭 Context


- `project/ui/panels/display_settings.py`

## ⛓️ Constraints

- brak

## 🪜 Plan / Subtasks

- brak

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] Testy / lint przechodzą (jeśli dotyczy)

## 📓 Agent Log

- 2026-06-27 opencode: claimed, starting
- 2026-06-27 opencode: Usunięto przycisk 'Apply (restarts game)', resolution i fullscreen zmiany są teraz aplikowane natychmiast po naciśnięciu Enter
- 2026-06-27 opencode: Zmiany w project/ui/panels/display_settings.py:\n- activate() dla 'resolution': po set_display(idx) woła apply_callback → game.set_display()\n- activate() dla 'fullscreen': po toggle woła apply_callback → game.set_display()\n- Usunięto 'apply' button i jego case z activate()\n- mypy/isort OK


## 🙋 Needs-You / Questions

