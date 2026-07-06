---
id: T-035
title: DS: Sentyment w rozgrywce - odkrywanie, bramkowanie opcji, mnoznik cen
status: in-progress
owner: ai
priority: p2
type: feature
agent: opencode
created: 2026-07-05
updated: 2026-07-05
tags:
  - task
---

# T-035 - DS: Sentyment w rozgrywce

## 🎯 Goal / Outcome

- [ ] Mechanika odkrywania `known_disposition`: waga emoji ujawniana dopiero po pierwszym użyciu; UI pokazuje `?` dla nieodkrytych
- [ ] Bramkowanie opcji/zakończeń progiem sentymentu (predykat `sentiment >= N` z mini-DSL)
- [ ] Handel: jeden współczynnik sentymentu mnożący wszystkie ceny u kupca
- [ ] UI: ikona `:key:` + liczba przy opcji oraz prosty wskaźnik poziomu NPC
- [ ] Balans wag `disposition` per postać (iteracyjnie)

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

- [ ] Naliczanie sentymentu przy wyborze opcji + clamp 0-100.
- [ ] `known_disposition` (ujawnianie wag) + UI `?`.
- [ ] Bramkowanie przez predykat `sentiment >= N`.
- [ ] Mnożnik cen sentymentu w handlu.
- [ ] Wskaźnik poziomu NPC w panelu rozmowy.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

- 2026-07-06 14:30 opencode: claimed, starting

## 🙋 Needs-You / Questions
