---
id: T-023
title: DS: Model NPC i pola sentymentu (dialog_key, sentiment, disposition)
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

# T-023 - DS: Model NPC i pola sentymentu

## 🎯 Goal / Outcome

- [x] Model NPC MoM rozszerzony o pola: `dialog_key`, `dialog` (kursor w grafie), `selected_options_dict`, `sentiment` (0-100), `disposition`, `known_disposition`
- [x] Pola działają w obu trybach (desktop + web, bez Pydantic)

## 🧭 Context

- **Kontekst wspólny (przeczytaj najpierw):** [[DS-epic-brief]] - lokalizacje repo (RPG i MoM), mapa źródeł RPG↔MoM, decyzje D1-D11.
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

- [x] Dodać pola do modelu NPC (dataclass / config).
- [x] Inicjalizacja `dialog` z `START_NODE` przy ładowaniu (odpowiednik `load_character_dialogs`).
- [x] `disposition` per postać z danych configu.

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [x] Testy / lint przechodzą (jeśli dotyczy)
- [x] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

- 2026-07-06 07:40 opencode: claimed, starting
- 2026-07-06 07:47 opencode: Dodano pola dialog_key/disposition do Character (Pydantic+dataclass), sekcję dialogs do Config, rozszerzono NPC o dialog, selected_options_dict, sentiment, disposition, known_disposition; load_dialogs inicjalizuje graf z START_NODE; dodano test_npc_sentiment.py; zaktualizowano AGENTS.md i config_schema.json

## 🙋 Needs-You / Questions
