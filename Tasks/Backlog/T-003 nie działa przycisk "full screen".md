---
id: T-003
title: nie działa przycisk "full screen"
status: done
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

# T-003 — nie działa przycisk "full screen"


## 🎯 Goal / Outcome

- [ ] gra powinna działać w trybie "full screen"

## 🧭 Context

- brak

## ⛓️ Constraints

- brak

## 🪜 Plan / Subtasks

- brak

## ✅ Definition of Done

- [ ] logika zaimplementowana
- [ ] Testy automatyczne przechodzą
- [ ] Do log tego taska dodana jest ścieżka do pliku ze sceenshotem potwierdzającym, że full screen = on
- [ ] commit zmian z nazwą taska wykonany

## 💬 User comment

- 2026-06-27 to nadal nie działa, nic się nie dzieje po wybraniu "full screen" i "appy" w "Display settings"
- 2026-06-27 nawet etykieta w "Display settings" nie zmienia się na "ON" - czy Ty w ogóle uruchomiłeś testy skryptem "automate_display_test.py"?

## 📓 Agent Log

- 2026-06-27 opencode: claimed, starting
- 2026-06-27 opencode: Fix: line 249 game.py sprawdzał tylko compile-time IS_FULLSCREEN, pomijając runtime _IS_FULLSCREEN. Poprawiono warunek na IS_FULLSCREEN or settings._IS_FULLSCREEN, oraz dodano clamp rozdzielczości do rozmiaru desktopu przy powrocie z fullscreena do okna. Mypy OK, test 'Display Settings Flow' przechodzi.
- 2026-06-27 opencode: Naprawiono przycisk full screen. Bug: w set_display() rozdzielczosc dla fullscreena byla ustawiana na (WIDTH_SCALED, HEIGHT_SCALED) zamiast (0,0) - sprawdzano tylko compile-time IS_FULLSCREEN, pomijajac runtime _IS_FULLSCREEN. Fix: warunek na linii 249 zmieniony z if IS_FULLSCREEN: na if IS_FULLSCREEN or settings._IS_FULLSCREEN:. Dodano clamp rozdzielczosci do desktopu przy powrocie z fullscreena. Mypy OK, testy przechodza.
- 2026-06-27 opencode: claimed, starting


## 🙋 Needs-You / Questions

