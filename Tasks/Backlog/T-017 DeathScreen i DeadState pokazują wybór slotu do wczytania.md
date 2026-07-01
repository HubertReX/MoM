---
id: T-017
title: DeathScreen i DeadState pokazują wybór slotu do wczytania
status: backlog
owner: human
priority: p2
type: feature
agent:
created: 2026-07-01
updated: 2026-07-01
tags:
  - task
---

# T-017 — DeathScreen i DeadState pokazują wybór slotu do wczytania


## 🎯 Goal / Outcome


- [ ] Ekran śmierci (`DeathScreen`) pokazuje menu wyboru slotu do wczytania zamiast przycisku "Load Last Save".
- [ ] Stan śmierci (`DeadState`) pokazuje to samo menu wyboru slotu.
- [ ] Wybranie slotu wczytuje grę i zamyka ekran śmierci.

## 🧭 Context


- Obecnie zarówno `DeathScreen` jak i `DeadState` w `project/ui/panels/save_load.py` mają przycisk "Load Last Save", który wczytuje ostatni zajęty slot.
- Użytkownik chce mieć możliwość wyboru konkretnego slotu, podobnie jak w menu Load.
- Oba ekrany istnieją w kodzie - prawdopodobnie jeden jest aktywnie używany, drugi to legacy. Trzeba to zweryfikować.

## ⛓️ Constraints


- Nie psuć istniejącego flow respawnu / restartu.
- Zachować kompatybilność desktop + web.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [ ] Sprawdzić, który ekran śmierci jest faktycznie używany (`DeathScreen` czy `DeadState`).
- [ ] Zastąpić przycisk "Load Last Save" w obu ekranach śmierci panelem wyboru slotu (można wykorzystać istniejący `LoadPanel` lub dedykowany widżet).
- [ ] Upewnić się, że po wczytaniu ekran śmierci znika poprawnie.
- [ ] Przetestować: śmierć, wybór slotu, wczytanie gry.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] commit zmian wykonany
- [ ] Testy / lint przechodzą (jeśli dotyczy)

## 📓 Agent Log


## 🙋 Needs-You / Questions

