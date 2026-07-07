---
id: T-040
title: DS bug: strzalki przesuwaja wybor opcji o 2 pozycje (podwojna obsluga KEYDOWN)
status: needs-you
owner: human
priority: p1
type: bug
agent: opencode
created: 2026-07-06
updated: 2026-07-06
tags:
  - task
state: review
---
# T-040 - DS bug: strzałki przesuwają wybór opcji o 2 pozycje

## 🎯 Goal / Outcome

- [ ] Naciśnięcie strzałki góra/dół (lub W/S) przesuwa zaznaczenie o dokładnie 1 pozycję
- [ ] Zachowana obsługa wszystkich ścieżek sterowania (D4): kursor + Enter, skróty 1-9, mysz - żadna nie działa podwójnie
- [ ] Brak regresji w domykaniu na `is_final` z [[T-037 DialogPanel nie zamyka rozmowy przy opcji finalnej poza widocznym zwojem listy]]

## 🧭 Context

- **Kontekst wspólny:** [[DS-epic-brief]] (D4 - hybryda sterowania).
- Zgłoszone przez użytkownika: "przy wyborze linii dialogowej strzałkami wybór przesuwa się o 2 pozycje na raz zamiast o jedną".
- **Root cause (potwierdzony w kodzie):** ten sam event KEYDOWN strzałki jest obsługiwany DWA razy w jednej klatce:
  1. `project/ui/game_ui.py::update()` (linie ~142-145): `if self._edge("up"): dialog.select_prev()` oraz `if self._edge("down"): dialog.select_next()` - rising-edge z `INPUTS`.
  2. `project/ui/game_ui.py::update()` (linie ~153-157): pętla `for event in events: top.handle_event(event)` routuje surowy KEYDOWN do `DialogPanel.handle_event`, które w `dialog.py:349-355` **też** woła `select_prev()`/`select_next()` dla `K_UP/K_w` i `K_DOWN/K_s`.
- Uwaga: dla `accept`/`talk` już jest ochrona przed podwójną obsługą (`game_ui` ustawia `INPUTS["accept"]=False` po `activate_selected`, linie 146-151). Dla `up`/`down` analogicznej ochrony brak - stąd podwójny ruch.

## ⛓️ Constraints

- Dual-target desktop + web.
- Rozwiązać spójnie z istniejącym wzorcem `accept`/`talk` (jedna ścieżka obsługi, nie dwie).
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [x] Wybrano: zachować `_edge()` w `game_ui` (obsługuje keyboard + gamepad przez INPUTS), usunąć K_UP/K_DOWN/K_w/K_s z `DialogPanel.handle_event()`. Decyzja: gamepad nie generuje KEYDOWN — tylko INPUTS, więc `handle_event` nie może być jedynym źródłem dla strzałek.
- [x] Gamepad/held-key: `_edge()` i `_dialog_held` nietknięte. Sterowanie gamepadem nadal idzie przez INPUTS → `_edge("up"/"down")` → `dialog.select_prev/next`.
- [x] Test wizualny (Hammer Dialog Flow — PASS) + jednostkowe (3 × dialog test — wszystkie PASS).

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowane w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane zdjęcia potwierdzające prawidłowe działania

Dialog otwarty (Hammer, węzeł 000):
![[agent_20260707_093030_hammer_dialog_flow_02_dialog_open.png]]

Węzeł hub po wybraniu opcji 1:
![[agent_20260707_093030_hammer_dialog_flow_03_hub_node.png]]

- [x] Testy / lint przechodzą:
  - `mypy` — Success: no issues found
  - `test_dialog_graph.py` — 4/4 PASS
  - `test_dialog_conditions.py` — 19/19 PASS
  - `test_dialog_result_sink.py` — All passed
  - `automate_display_test.py "Hammer Dialog Flow"` — PASS (all assertions passed)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane (nie potrzeba)
- [ ] commit zmian wykonany

## 📓 Agent Log

- 2026-07-06 cc (review): utworzony podczas weryfikacji epica DS. Root cause: podwójna obsługa KEYDOWN strzałek (`_edge` w game_ui + `handle_event` w dialog.py).
- 2026-07-07 09:28 opencode: claimed, starting
- 2026-07-07 09:32 opencode: Fix: removed duplicate K_UP/K_DOWN/K_w/K_s handling from DialogPanel.handle_event(). Arrow navigation now only goes through _edge(up/down) in game_ui.py (single source of truth). Gamepad support preserved via INPUTS dict -> _edge. All unit tests (dialog graph, conditions, result sink) and Hammer Dialog Flow scenario pass. Screenshots: dialog_open, hub_node. Ready for review.
- 2026-07-07 09:32 opencode: Fix zaimplementowany i zweryfikowany. Zmiana: usunięcie K_UP/K_DOWN/K_w/K_s z DialogPanel.handle_event() — strzałki obsługiwane wyłącznie przez _edge(up/down) w game_ui.py (to samo źródło co gamepad przez INPUTS). Testy: mypy, 3x dialog unit test, Hammer Dialog Flow (PASS, 4 screenshoty). Commit f28f087.

## 🙋 Needs-You / Questions
