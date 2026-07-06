---
id: T-034
title: DS: Efekty wezlow - adapter ResultSink (zloto, itemy, HP, sentyment)
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

# T-034 - DS: Efekty wezlow (adapter ResultSink)

## 🎯 Goal / Outcome

- [x] Adapter `ResultSink` (Protocol) mapujący 7 kategorii `NodeVisitResult` na systemy MoM: złoto, `Inventory`, HP gracza, sentyment NPC
- [x] Silnik dialogu bez importów z gry; gra dostarcza konkretny sink (odwrócona zależność)
- [x] Flaga `visited` chroni przed dublem - efekt liczony raz przy pierwszej wizycie węzła
- [x] Test: węzeł z `MONEY+` / `ITEMS+` zmienia stan gracza dokładnie jednokrotnie

## 🧭 Context

- **Kontekst wspólny (przeczytaj najpierw):** [[DS-epic-brief]] - lokalizacje repo (RPG i MoM), mapa źródeł RPG↔MoM, decyzje D1-D11.
- Decyzja **D8** (cienki adapter) - `../doc/dialog-migration-plan.html`. Źródło: RPG `main.py:process_result`.
- MoM: `Inventory`, hero/health, klucze itemów z `project/config_model/items.csv`.
- Zależy od: [[T-029 DS: Encje dialogu i budowa grafu (DialogNode, Option, Result + init_dialog)]], [[T-023 DS: Model NPC i pola sentymentu (dialog_key, sentiment, disposition)]], [[T-033 DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)]].
- Odblokowuje: [[T-030 DS: Persystencja stanu rozmowy w save-load (oba backendy + testy korupcji)]], [[T-035 DS: Sentyment w rozgrywce - odkrywanie, bramkowanie opcji, mnoznik cen]].

## ⛓️ Constraints

- Nazwy itemów w efektach muszą zgadzać się z kluczami `items.csv` (walidacja przy imporcie - łączy się z pipeline).
- Dual-target desktop + web.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [x] `ResultSink` (Protocol) + `apply_result()` (match po kategorii).
- [x] Konkretny `GameSink` spięty z Inventory/hero/HP/sentyment.
- [x] Ochrona `visited` przed podwójnym naliczeniem.
- [x] Test jednokrotności efektu.

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania - zobacz `![[agent_20260706_T-034_tests_passed.png]]`
- [x] Testy / lint przechodzą (jeśli dotyczy)
- [x] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

![[agent_20260706_T-034_tests_passed.png]]

## 📓 Agent Log

- 2026-07-06 10:23 opencode: claimed, starting
- 2026-07-06 13:12 opencode: implemented `ResultSink` Protocol, `GameResultSink`, visited-once guard, tests; dialog/graph/conditions/import + new result-sink tests pass; mypy clean; updated `project/AGENTS.md`
- 2026-07-06 13:14 opencode: Implemented ResultSink Protocol, GameResultSink, visited-once guard, and tests. All dialog tests + mypy pass. Ready for review.
- 2026-07-06 13:15 opencode: Ready for review. Changes: project/dialog/result_sink.py (ResultSink Protocol + apply_result + visit_node), project/result_sink_adapter.py (GameResultSink), project/dialog/__init__.py (exports), project/ui/panels/dialog.py (_visit_current_node wiring), project/AGENTS.md (docs), tests/test_dialog_result_sink.py. Tests: test_dialog_result_sink.py + graph + conditions + import all pass; mypy clean. See attached screenshot in Definition of Done.

## 🙋 Needs-You / Questions
