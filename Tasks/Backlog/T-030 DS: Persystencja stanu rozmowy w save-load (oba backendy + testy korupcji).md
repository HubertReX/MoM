---
id: T-030
title: DS: Persystencja stanu rozmowy w save-load (oba backendy + testy korupcji)
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

# T-030 - DS: Persystencja stanu rozmowy

## 🎯 Goal / Outcome

- [ ] Pełny stan rozmowy per-NPC w save/load (D5): kursor (bieżący węzeł), `selected_options_dict`, `sentiment`, `visited`, `selected`
- [ ] Działa na obu backendach (desktop plik + web localStorage); testy korupcji przechodzą
- [ ] Reload w połowie rozmowy wznawia kursor, wybory, sentyment i naliczone efekty

## 🧭 Context

- Decyzja **D5** (pełny stan per-NPC) - `../doc/dialog-migration-plan.html`.
- MoM: `project/save_load/`, `project/config_model/`, testy `tests/test_save_load_backends.py`, `tests/test_save_load_corrupt.py`, `tests/test_save_load_models.py`.
- Zależy od: [[T-023 DS: Model NPC i pola sentymentu (dialog_key, sentiment, disposition)]], [[T-033 DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)]], [[T-034 DS: Efekty wezlow - adapter ResultSink (zloto, itemy, HP, sentyment)]].
- Odblokowuje: [[T-028 DS: Migracja pozostalych postaci + web smoke-test + testy wizualne]].

## ⛓️ Constraints

- Dual-target: oba backendy save (bez Pydantic na web).
- Nie łamać istniejących testów korupcji save.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [ ] Dodać stan rozmowy do modelu save (dataclass) dla obu backendów.
- [ ] Serializacja/deserializacja kursora (referencja węzła po kluczu).
- [ ] Rozszerzyć testy save/load + korupcji o stan rozmowy.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

## 🙋 Needs-You / Questions
