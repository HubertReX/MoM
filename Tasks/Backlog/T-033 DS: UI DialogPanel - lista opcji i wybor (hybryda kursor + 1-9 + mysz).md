---
id: T-033
title: DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)
status: backlog
owner: human
priority: p2
type: feature
agent:
created: 2026-07-05
updated: 2026-07-05
tags:
  - task
---

# T-033 - DS: UI DialogPanel (opcje i wybor)

## 🎯 Goal / Outcome

- [ ] `DialogPanel` renderuje tekst węzła oraz numerowaną listę dostępnych opcji (po filtrze warunków)
- [ ] Sterowanie hybrydowe (D4): kursor gora/dol + Enter, skróty 1-9, mysz; podświetlenie aktywnej opcji
- [ ] Przejścia między węzłami (`next_node`); wpięcie w stan `Talk`
- [ ] Można pogadać z jedną postacią (Hammer) tam i z powrotem, aż do węzła `is_final`

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

- [ ] Render listy opcji + kursor/podświetlenie.
- [ ] Obsługa wejścia: kursor+Enter, 1-9, mysz.
- [ ] Filtr `available_options` (warunki z [[T-032 DS: Silnik warunkow - mini-DSL (AST-whitelist + predykaty)]]).
- [ ] Integracja ze stanem `Talk` i zamknięcie na `is_final`.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

## 🙋 Needs-You / Questions
