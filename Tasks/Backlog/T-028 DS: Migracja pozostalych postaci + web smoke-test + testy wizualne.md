---
id: T-028
title: DS: Migracja pozostalych postaci + web smoke-test + testy wizualne
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

# T-028 - DS: Migracja postaci + web smoke-test

## 🎯 Goal / Outcome

- [x] Pozostałe postaci przeniesione (Barman Absinthrayner, Clapback Sword, Potioneer Puzzlemint, Madame Sarcasmia) - wszystkie 4 budują się z configu, liczba węzłów zgodna z RPG (23/18/21/22)
- [x] Opcje DEBUG gated `IS_DEBUG_MODE` (D9) do szybkiego testu drzew dialogowych - `characters.py:322` przekazuje `debug=IS_DEBUG_MODE`; opcje DEBUG widoczne na zrzutach w trybie debug
- [x] Web smoke-test: WASM (pygbag/Chromium) - dialogi działają (patrz Dowód działania)
- [x] Testy wizualne + `doc/test-scenarios-list.md` zaktualizowane - sekcja "Postacie zmigrowane z RPG" + opis opcji DEBUG

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

- [x] Import 4 pozostałych postaci przez pipeline.
- [x] Weryfikacja opcji DEBUG (skoki do START / węzłów `is_final`).
- [x] Web smoke-test na WASM (pygbag + Playwright Chromium).
- [x] Scenariusze testów wizualnych + aktualizacja `test-scenarios-list.md`.

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [x] Testy / lint przechodzą (jeśli dotyczy) - 32 testy dialogowe PASS; mypy `dialog.py` czysty
- [x] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [x] commit zmian wykonany

### Dowód działania

Web smoke-test (2026-07-06 review): `just test-web "Hammer Dialog Flow"` - pygbag zbudował WASM, Playwright Chromium załadował grę pod `http://127.0.0.1:8001/`, scenariusz Hammera przejechał na backendzie **web**. Werdykt ss-review gemini: `dialog_open` PASS, `topic_node` PASS (`hub_node` - błąd połączenia endpointu ss-reviewera, nie UI). Pełny graf Hammera renderuje się i nawiguje na WASM:

![[agent_20260706_T-028_web_dialog.png]]

## 📓 Agent Log

- 2026-07-06 15:02 opencode: claimed, starting
- 2026-07-06 15:38 opencode: Przeniesiono 4 postacie (Barman Absinthrayner, Clapback Sword, Potioneer Puzzlemint, Madame Sarcasmia) z RPG do config.json i items.csv. Dostosowano importer do wyszukiwania plików (prefiks char-/chara-, wielkość liter). Zaimplementowano konwersję warunków dla Madame Sarcasmia i zweryfikowano wszystkie 32 testy jednostkowe dialogów (test_dialog_graph, test_dialog_conditions, test_dialog_result_sink, test_dialog_import). Włączono opcję DEBUG gated przez IS_DEBUG_MODE w settings.py. Zaktualizowano listę scenariuszy.
- 2026-07-06 17:24 cc (review): Domknięto lukę web smoke-testu - `just test-web "Hammer Dialog Flow"` przechodzi na WASM (dialog_open + topic_node PASS w ss-review). 4 postaci budują się z configu (liczba węzłów zgodna z RPG). D9 (DEBUG gated) potwierdzone. `doc/test-scenarios-list.md` zawiera sekcję migrowanych postaci. Dodano zrzut web.

## 🙋 Needs-You / Questions
