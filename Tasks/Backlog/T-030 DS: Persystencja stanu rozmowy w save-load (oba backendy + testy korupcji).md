---
id: T-030
title: DS: Persystencja stanu rozmowy w save-load (oba backendy + testy korupcji)
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

# T-030 - DS: Persystencja stanu rozmowy

## 🎯 Goal / Outcome

- [x] Pełny stan rozmowy per-NPC w save/load (D5): kursor (bieżący węzeł), `selected_options_dict`, `sentiment`, `visited`, `selected`
- [x] Działa na obu backendach (desktop plik + web localStorage); testy korupcji przechodzą
- [x] Reload w połowie rozmowy wznawia kursor, wybory, sentyment i naliczone efekty

## 🧭 Context

- **Kontekst wspólny (przeczytaj najpierw):** [[DS-epic-brief]] - lokalizacje repo (RPG i MoM), mapa źródeł RPG↔MoM, decyzje D1-D11.
- Decyzja **D5** (pełny stan per-NPC) - `../doc/dialog-migration-plan.html`.
- MoM: `project/save_load/`, `project/config_model/`, testy `tests/test_save_load_backends.py`, `tests/test_save_load_corrupt.py`, `tests/test_save_load_models.py`.
- Zależy od: [[T-023 DS: Model NPC i pola sentymentu (dialog_key, sentiment, disposition)]], [[T-033 DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)]], [[T-034 DS: Efekty wezlow - adapter ResultSink (zloto, itemy, HP, sentyment)]].
- Odblokowuje: [[T-028 DS: Migracja pozostalych postaci + web smoke-test + testy wizualne]].

## ⛓️ Constraints

- Dual-target: oba backendy save (bez Pydantic na web).
- Nie łamać istniejących testów korupcji save.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [x] Dodać stan rozmowy do modelu save (dataclass) dla obu backendów.
- [x] Serializacja/deserializacja kursora (referencja węzła po kluczu).
- [x] Rozszerzyć testy save/load + korupcji o stan rozmowy.

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [x] Testy / lint przechodzą (jeśli dotyczy)
- [x] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

![[agent_20260706_T-030_dialog_open_after_load.png]]

## 📓 Agent Log

- 2026-07-06 14:09 opencode: claimed, starting
- 2026-07-06 14:21 opencode: Added NPCDialogState to save_load/models.py, extended NPCState, SaveManager build/apply and NPC.restore_dialog_state. New tests: test_save_load_dialog_state.py + extended test_save_load_models.py. All save/load, dialog and mypy checks pass. Agent scenarios Save and Load Basic and Hammer Dialog Flow run without game errors (screenshot review unavailable locally).
- 2026-07-06 14:27 opencode: Implemented NPCDialogState persistence across desktop file and web localStorage backends. Added NPC.restore_dialog_state, SaveManager serialization and comprehensive tests. Added agent scenario 'Dialog Save and Load' to tests/scenarios.json. All save/load, dialog and mypy checks pass; agent scenario passes assertions.
- 2026-07-06 14:29 opencode: Updated project/AGENTS.md with dialog persistence notes. All tests and mypy still pass.

## 🙋 Needs-You / Questions
