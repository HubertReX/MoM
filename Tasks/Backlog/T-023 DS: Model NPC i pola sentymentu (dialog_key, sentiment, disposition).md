---
id: T-023
title: DS: Model NPC i pola sentymentu (dialog_key, sentiment, disposition)
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
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania - zadanie czysto-modelowe (pola danych, bez UI); dowodem jest wyjście testów (patrz niżej)
- [x] Testy / lint przechodzą (jeśli dotyczy)
- [x] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [x] commit zmian wykonany

### Dowód działania

Zadanie modelowe (pola NPC/Character, bez UI do zrzutu). Dowód = testy jednostkowe i wpięcie w grę:

- `tests/test_npc_sentiment.py` - 8/8 PASS (pola sentymentu, dyspozycje, mnożniki cen).
- Wszystkie 5 postaci ma `dialog_key` rozwiązujący się do istniejącego grafu dialogu (weryfikacja podczas review epica).
- mypy na zmienionych plikach czysty.

## 📓 Agent Log

- 2026-07-06 07:40 opencode: claimed, starting
- 2026-07-06 07:47 opencode: Dodano pola dialog_key/disposition do Character (Pydantic+dataclass), sekcję dialogs do Config, rozszerzono NPC o dialog, selected_options_dict, sentiment, disposition, known_disposition; load_dialogs inicjalizuje graf z START_NODE; dodano test_npc_sentiment.py; zaktualizowano AGENTS.md i config_schema.json
- 2026-07-06 07:48 opencode: Zaimplementowano T-023. Modele postaci rozszerzone o dialog_key/disposition (Pydantic i dataclass web), Config o sekcję dialogs, NPC o dialog (kursor DialogNode), selected_options_dict, sentiment, disposition, known_disposition. load_dialogs buduje graf i ustawia START_NODE. Zaktualizowano config_schema.json, AGENTS.md, dodano tests/test_npc_sentiment.py. Testy: test_dialog_graph.py, test_dialog_conditions.py, test_npc_sentiment.py przechodzą; mypy na zmienionych plikach czyste. Gra ładuje się w dummy driverze bez regresji.

## 🙋 Needs-You / Questions
