---
id: T-023
title: DS: Model NPC i pola sentymentu (dialog_key, sentiment, disposition)
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

# T-023 - DS: Model NPC i pola sentymentu

## 🎯 Goal / Outcome

- [ ] Model NPC MoM rozszerzony o pola: `dialog_key`, `dialog` (kursor w grafie), `selected_options_dict`, `sentiment` (0-100), `disposition`, `known_disposition`
- [ ] Pola działają w obu trybach (desktop + web, bez Pydantic)

## 🧭 Context

- Źródło: RPG `character.py` (pola dopięte do postaci).
- MoM: `project/characters.py` (klasa `NPC`, `load_dialogs:290`), `project/config_model/`.
- Decyzje **D2** (dataclassy) i **D10** (zakres pól sentymentu) - `../doc/dialog-migration-plan.html`.
- Zależy od: [[T-029 DS: Encje dialogu i budowa grafu (DialogNode, Option, Result + init_dialog)]].
- Odblokowuje: [[T-024 DS: Pipeline importu Markdown do config (parser + walidacja + konwersja znacznikow)]], [[T-034 DS: Efekty wezlow - adapter ResultSink (zloto, itemy, HP, sentyment)]], [[T-030 DS: Persystencja stanu rozmowy w save-load (oba backendy + testy korupcji)]], [[T-035 DS: Sentyment w rozgrywce - odkrywanie, bramkowanie opcji, mnoznik cen]].

## ⛓️ Constraints

- Dual-target desktop + web (bez Pydantic na web).
- Nie psuć istniejącego `NPC.dialogs: str` dopóki nowa ścieżka nie zastąpi starej.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [ ] Dodać pola do modelu NPC (dataclass / config).
- [ ] Inicjalizacja `dialog` z `START_NODE` przy ładowaniu (odpowiednik `load_character_dialogs`).
- [ ] `disposition` per postać z danych configu.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

## 🙋 Needs-You / Questions
