---
id: T-028
title: DS: Migracja pozostalych postaci + web smoke-test + testy wizualne
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

# T-028 - DS: Migracja postaci + web smoke-test

## 🎯 Goal / Outcome

- [ ] Pozostałe postaci przeniesione (Barman Absinthrayner, Clapback Sword, Potioneer Puzzlemint, Madame Sarcasmia)
- [ ] Opcje DEBUG gated `IS_DEBUG_MODE` (D9) do szybkiego testu drzew dialogowych
- [ ] Web smoke-test: `just serve-web` (WASM, bez Pydantic/shaderów) - dialogi działają
- [ ] Testy wizualne + `doc/test-scenarios-list.md` zaktualizowane

## 🧭 Context

- **Kontekst wspólny (przeczytaj najpierw):** [[DS-epic-brief]] - lokalizacje repo (RPG i MoM), mapa źródeł RPG↔MoM, decyzje D1-D11.
- Decyzja **D9** (opcje DEBUG gated) - `../doc/dialog-migration-plan.html`.
- MoM: `tests/automate_display_test.py`, `tests/scenarios.json`, `doc/test-scenarios-list.md`.
- Źródło dialogów: `RPG/dialogs/PL`, `RPG/dialogs/EN`.
- Zależy od: [[T-024 DS: Pipeline importu Markdown do config (parser + walidacja + konwersja znacznikow)]], [[T-033 DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)]], [[T-034 DS: Efekty wezlow - adapter ResultSink (zloto, itemy, HP, sentyment)]], [[T-030 DS: Persystencja stanu rozmowy w save-load (oba backendy + testy korupcji)]].

## ⛓️ Constraints

- Każda postać musi działać w obu trybach (desktop + web).
- Testowanie drzew to praca żmudna - wykorzystać opcje DEBUG (D9) i testy wizualne.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [ ] Import 4 pozostałych postaci przez pipeline.
- [ ] Weryfikacja opcji DEBUG (skoki do START / węzłów `is_final`).
- [ ] Web smoke-test na `just serve-web`.
- [ ] Scenariusze testów wizualnych + aktualizacja `test-scenarios-list.md`.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

## 🙋 Needs-You / Questions
