---
id: T-017
title: DeathScreen i DeadState pokazują wybór slotu do wczytania
status: in-progress
owner: ai
priority: p2
type: feature
agent: opencode
created: 2026-07-01
updated: 2026-07-01
tags:
  - task
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

## 📓 Agent Log

- 2026-07-01 16:56 user: moved to ready
- 2026-07-01 17:37 opencode: claimed, starting
- 2026-07-01 17:47 opencode: Implemented slot selection in DeathScreen and DeadState using reusable _LoadSlotSelector. Updated 'Death then Load' scenario to use double accept for load confirmation. Tests pass: Death then Load, Save and Load Basic; mypy/isort clean.


## 🙋 Needs-You / Questions

