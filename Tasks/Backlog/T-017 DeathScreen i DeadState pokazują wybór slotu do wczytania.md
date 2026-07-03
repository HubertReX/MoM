---
id: T-017
title: DeathScreen i DeadState pokazują wybór slotu do wczytania
status: done
owner: human
priority: p2
type: feature
agent:
created: 2026-07-01
updated: 2026-07-01
tags:
  - task
state: review
---

# T-017 — DeathScreen i DeadState pokazują wybór slotu do wczytania


## 🎯 Goal / Outcome


- [x] Ekran śmierci (`DeathScreen`) pokazuje menu wyboru slotu do wczytania zamiast przycisku "Load Last Save".
- [x] Stan śmierci (`DeadState`) pokazuje to samo menu wyboru slotu.
- [x] Wybranie slotu wczytuje grę i zamyka ekran śmierci.

## 🧭 Context


- Obecnie zarówno `DeathScreen` jak i `DeadState` w `project/ui/panels/save_load.py` mają przycisk "Load Last Save", który wczytuje ostatni zajęty slot.
- Użytkownik chce mieć możliwość wyboru konkretnego slotu, podobnie jak w menu Load.
- Oba ekrany istnieją w kodzie - prawdopodobnie jeden jest aktywnie używany, drugi to legacy. Trzeba to zweryfikować.

## ⛓️ Constraints


- Nie psuć istniejącego flow respawnu / restartu.
- Zachować kompatybilność desktop + web.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [x] Sprawdzić, który ekran śmierci jest faktycznie używany (`DeathScreen` czy `DeadState`).
- [x] Zastąpić przycisk "Load Last Save" w obu ekranach śmierci panelem wyboru slotu (można wykorzystać istniejący `LoadPanel` lub dedykowany widżet).
- [x] Upewnić się, że po wczytaniu ekran śmierci znika poprawnie.
- [x] Przetestować: śmierć, wybór slotu, wczytanie gry.

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] commit zmian wykonany
- [x] Testy / lint przechodzą (jeśli dotyczy)

Load screen:
![[agent_20260701_193144_0003.png]]

Confirmation:
![[agent_20260701_193144_0004.png]]

## 📓 Agent Log

- 2026-07-01 16:56 user: moved to ready
- 2026-07-01 17:37 opencode: claimed, starting
- 2026-07-01 17:47 opencode: Implemented slot selection in DeathScreen and DeadState using reusable _LoadSlotSelector. Updated 'Death then Load' scenario to use double accept for load confirmation. Tests pass: Death then Load, Save and Load Basic; mypy/isort clean. Evidence: [[agent_20260701_193144_0003.png]]
- 2026-07-01 17:48 opencode: DeathScreen and DeadState now display an occupied-slot selector instead of 'Load Last Save'. Keyboard/mouse navigation with confirmation dialog, restart button retained. Tests: Death then Load, Save and Load Basic pass; mypy/isort clean. Commit c4ef51f.
- 2026-07-01 18:44 opencode: REVIEW OK (human): mypy clean; 'Death then Load' PASS clean; _LoadSlotSelector reused w DeathScreen i DeadState, confirmation dialog + restart retained. Przeniesione do Done.


## 🙋 Needs-You / Questions

