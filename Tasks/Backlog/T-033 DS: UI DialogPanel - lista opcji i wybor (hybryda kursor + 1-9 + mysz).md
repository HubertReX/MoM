---
id: T-033
title: DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)
status: needs-you
owner: human
priority: p2
type: feature
agent: opencode
created: 2026-07-05
updated: 2026-07-05
tags:
  - task
state: review
---

# T-033 - DS: UI DialogPanel (opcje i wybor)

## 🎯 Goal / Outcome

- [x] `DialogPanel` renderuje tekst węzła oraz numerowaną listę dostępnych opcji (po filtrze warunków)
- [x] Sterowanie hybrydowe (D4): kursor gora/dol + Enter, skróty 1-9, mysz; podświetlenie aktywnej opcji
- [x] Przejścia między węzłami (`next_node`); wpięcie w stan `Talk`
- [x] Można pogadać z jedną postacią (Hammer) tam i z powrotem - potwierdzone wizualnie (patrz Dowód działania). Uwaga: znaleziono edge-case przy zamykaniu na `is_final` (opcja "goodbye" spoza widocznego zwoju + wstrzyknięte opcje DEBUG przesuwają indeksy) - zgłoszone jako osobny finding, patrz Needs-You.

## 🧭 Context

- **Kontekst wspólny (przeczytaj najpierw):** [[DS-epic-brief]] - lokalizacje repo (RPG i MoM), mapa źródeł RPG↔MoM, decyzje D1-D11.
- MoM: `project/ui/panels/dialog.py` (dziś tylko statyczny tekst), `project/ui/widgets/rich_text.py`, `project/npc_state.py` (stan `Talk`), `project/characters.py:1316` (otwarcie panelu).
- Decyzja **D4** (hybryda sterowania) - `../doc/dialog-migration-plan.html`. Render znaczników po konwersji z D3.
- Zależy od: [[T-029 DS: Encje dialogu i budowa grafu (DialogNode, Option, Result + init_dialog)]], [[T-024 DS: Pipeline importu Markdown do config (parser + walidacja + konwersja znacznikow)]].
- Odblokowuje: [[T-034 DS: Efekty wezlow - adapter ResultSink (zloto, itemy, HP, sentyment)]], [[T-030 DS: Persystencja stanu rozmowy w save-load (oba backendy + testy korupcji)]], [[T-035 DS: Sentyment w rozgrywce - odkrywanie, bramkowanie opcji, mnoznik cen]], [[T-028 DS: Migracja pozostalych postaci + web smoke-test + testy wizualne]].

## ⛓️ Constraints

- Real-time (pętla klatek) - bez blokowania na input, w przeciwieństwie do turowego RPG.
- Dual-target desktop + web; sterowanie działa też padem (spójne z menu MoM).
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [x] Render listy opcji + kursor/podświetlenie.
- [x] Obsługa wejścia: kursor+Enter, 1-9, mysz.
- [x] Filtr `available_options` (warunki z [[T-032 DS: Silnik warunkow - mini-DSL (AST-whitelist + predykaty)]]).
- [x] Integracja ze stanem `Talk` i zamknięcie na `is_final` (edge-case zamknięcia - patrz Needs-You).

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione (z zastrzeżeniem edge-case zamknięcia `is_final` - patrz Needs-You)
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [x] Testy / lint przechodzą (jeśli dotyczy) - testy dialogowe 4/19/8 PASS, mypy `dialog.py` czysty
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane - nie zweryfikowane
- [x] commit zmian wykonany

### Dowód działania

Test wizualny `Hammer Dialog Flow` (desktop) na **pełnym imporcie Hammer Hoaxheart** (12 węzłów z RPG, nie stub). Ścieżka 000 -> 001 -> 003, opcje renderują się z numeracją i wskaźnikami wagi sentymentu (`?`), portret postaci, przejścia między węzłami działają. Werdykt ss-review gemini-3.1-flash-lite: `dialog_open` PASS, `topic_node` PASS (`hub_node` - błąd połączenia endpointu ss-reviewera, nie UI).

Węzeł startowy 000 (powitanie + opcje):

![[agent_20260706_T-033_dialog_open_real_hammer.png]]

Po dwóch wyborach - węzeł 003 (graf przechodzi między węzłami):

![[agent_20260706_T-033_node_advance.png]]

## 📓 Agent Log

- 2026-07-06 08:12 opencode: claimed, starting
- 2026-07-06 10:23 opencode: Implemented DialogPanel with hybrid input, Hammer dialog graph, and Hammer Dialog Flow scenario. Desktop agent tests pass; screenshot_review sometimes fails due to local LLM endpoint connectivity, not UI.
- 2026-07-06 17:10 cc (review): Zweryfikowano wizualnie na pełnym imporcie Hammera (po podmianie stuba). Scenariusz `Hammer Dialog Flow` przepisany pod realny graf (000->001->003, klawisze `item_1`/`item_2`, asercje pod prawdziwą treść). Dodano dowody. Znaleziono edge-case zamknięcia na `is_final`.

## 🙋 Needs-You / Questions

- **Edge-case zamknięcia dialogu na `is_final`:** wybór opcji "goodbye" prowadzącej do węzła finalnego (990) nie zamyka panelu, gdy opcja jest poza widocznym zwojem listy. Dodatkowo w trybie `IS_DEBUG_MODE` wstrzyknięte opcje DEBUG przesuwają indeksy opcji. Nawigacja tam-i-z-powrotem między węzłami działa; problem dotyczy tylko finalnego zamknięcia via opcja spoza viewportu. Sugerowany osobny task (bug): przewijanie listy opcji do zaznaczonej pozycji + spójne indeksowanie przy opcjach DEBUG.
