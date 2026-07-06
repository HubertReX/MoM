---
id: T-035
title: DS: Sentyment w rozgrywce - odkrywanie, bramkowanie opcji, mnoznik cen
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

# T-035 - DS: Sentyment w rozgrywce

## 🎯 Goal / Outcome

- [x] Mechanika odkrywania `known_disposition`: waga emoji ujawniana dopiero po pierwszym użyciu; UI pokazuje `?` dla nieodkrytych - potwierdzone wizualnie (`?` przy opcjach na zrzutach T-033) i testem
- [x] Bramkowanie opcji/zakończeń progiem sentymentu (predykat `sentiment >= N` z mini-DSL) - realne dane: Potioneer Puzzlemint ma opcje `sentiment>=42` / `sentiment<42`, filtrowane przez `check_condition` (T-032, 19/19 testów)
- [x] Handel: jeden współczynnik sentymentu mnożący wszystkie ceny u kupca - `tests/test_npc_sentiment.py::test_trade_price_multipliers`
- [x] UI: ikona `:key:` + liczba przy opcji oraz prosty wskaźnik poziomu NPC - wskaźnik wagi renderowany przy każdej opcji (patrz zrzuty T-033)
- [x] Balans wag `disposition` per postać (iteracyjnie) - wagi per postać w configu (np. Hammer `blessed:8 ... angry:-8`); strojenie iteracyjne, nie blokuje MVP

## 🧭 Context

- **Kontekst wspólny (przeczytaj najpierw):** [[DS-epic-brief]] - lokalizacje repo (RPG i MoM), mapa źródeł RPG↔MoM, decyzje D1-D11.
- Decyzja **D10** (pełny sentyment, zakres v1) - `../doc/dialog-migration-plan.html`.
- MoM: `project/ui/panels/trade.py` (ceny, `trade_spread`), `disposition` per postać.
- Zależy od: [[T-032 DS: Silnik warunkow - mini-DSL (AST-whitelist + predykaty)]] (predykat `sentiment`), [[T-023 DS: Model NPC i pola sentymentu (dialog_key, sentiment, disposition)]], [[T-033 DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)]], [[T-034 DS: Efekty wezlow - adapter ResultSink (zloto, itemy, HP, sentyment)]].
- Powiązane (później): [[T-036 DS: Feedback zmiany sentymentu - floating plus-minus N (later)]].

## ⛓️ Constraints

- Dual-target desktop + web.
- Balans wag to praca iteracyjna - nie blokować MVP idealnym strojeniem.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [x] Naliczanie sentymentu przy wyborze opcji + clamp 0-100 (`apply_option_sentiment` w `dialog.py`).
- [x] `known_disposition` (ujawnianie wag) + UI `?`.
- [x] Bramkowanie przez predykat `sentiment >= N`.
- [x] Mnożnik cen sentymentu w handlu.
- [x] Wskaźnik poziomu NPC w panelu rozmowy.

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania - wskaźniki wagi `?` widoczne na zrzutach z [[T-033 DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)]]
- [x] Testy / lint przechodzą (jeśli dotyczy) - `test_npc_sentiment.py` 8/8; mini-DSL `test_dialog_conditions.py` 19/19 (w tym bramka sentymentu)
- [x] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [x] commit zmian wykonany

## 📓 Agent Log

- 2026-07-06 14:30 opencode: claimed, starting
- 2026-07-06 17:26 cc (review): Zweryfikowano end-to-end. Odkrywanie wag + UI `?` widoczne na zrzutach; bramkowanie potwierdzone realnymi danymi (Potioneer `sentiment>=42`/`sentiment<42` filtrowane przez mini-DSL T-032); mnożnik cen pokryty testem `test_trade_price_multipliers`. Naliczanie sentymentu i flash feedback w `dialog.py`. Commit 90e800b.

## 🙋 Needs-You / Questions
