---
id: T-029
title: DS: Encje dialogu i budowa grafu (DialogNode, Option, Result + init_dialog)
status: in-progress
owner: ai
priority: p2
type: feature
agent: cc
created: 2026-07-05
updated: 2026-07-05
tags:
  - task
---

# T-029 - DS: Encje dialogu i budowa grafu

## 🎯 Goal / Outcome

- [ ] `DialogNode`, `DialogOption`, `NodeVisitResult` (+ `NodeVisitResultCategory`, 7 kategorii) przeniesione do `project/` jako dataclassy `slots=True`, bez zależności od pygame
- [ ] `init_dialog()` buduje graf postaci z dictów configu (odpowiednik `RPG main.py:1157`), rozwiązuje referencje `next_node`
- [ ] test jednostkowy: załadowanie przykładowego grafu i przejście ścieżki w pamięci

## 🧭 Context

- **Kontekst wspólny (przeczytaj najpierw):** [[DS-epic-brief]] - lokalizacje repo (RPG i MoM), mapa źródeł RPG↔MoM, decyzje D1-D11.
- Fundament epica **Dialog System** - brak zależności wejściowych.
- Źródło: RPG `dialog_node.py` (wersja kanoniczna, 7 kategorii, `slots=True`), `RPG main.py:1157-1224` (budowa grafu).
- Decyzja **D2** (dataclassy `slots`) - `../doc/dialog-migration-plan.html`.
- Odblokowuje: [[T-032 DS: Silnik warunkow - mini-DSL (AST-whitelist + predykaty)]], [[T-023 DS: Model NPC i pola sentymentu (dialog_key, sentiment, disposition)]], [[T-024 DS: Pipeline importu Markdown do config (parser + walidacja + konwersja znacznikow)]].

## ⛓️ Constraints

- Dual-target: musi działać na desktopie i web (bez Pydantic na web).
- Zero importów `pygame` w tym module (czysta logika, testowalna w izolacji).
- Type hints wymagane (mypy).

## 🪜 Plan / Subtasks

- [ ] Zaadaptować dataclassy do `project/` (np. `project/dialog/`).
- [ ] `init_dialog()` z rozwiązywaniem referencji `next_node` i sekcji configu (DIALOG_NODES/OPTIONS/NODES_OPTIONS/NODE_RESULTS/START_NODE).
- [ ] Test jednostkowy przejścia grafu (ścieżka + końcowy węzeł `is_final`).

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

- 2026-07-06 07:16 cc: claimed, starting

## 🙋 Needs-You / Questions
