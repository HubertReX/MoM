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

- [x] `DialogNode`, `DialogOption`, `NodeVisitResult` (+ `NodeVisitResultCategory`, 7 kategorii) przeniesione do `project/` jako dataclassy `slots=True`, bez zależności od pygame
- [x] `init_dialog()` buduje graf postaci z dictów configu (odpowiednik `RPG main.py:1157`), rozwiązuje referencje `next_node`
- [x] test jednostkowy: załadowanie przykładowego grafu i przejście ścieżki w pamięci

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

- [x] Zaadaptować dataclassy do `project/` (np. `project/dialog/`).
- [x] `init_dialog()` z rozwiązywaniem referencji `next_node` i sekcji configu (DIALOG_NODES/OPTIONS/NODES_OPTIONS/NODE_RESULTS/START_NODE).
- [x] Test jednostkowy przejścia grafu (ścieżka + końcowy węzeł `is_final`).

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [x] Testy / lint przechodzą (jeśli dotyczy) - 4/4 testy + mypy czysto
- [x] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane - nie dotyczy (moduł fundamentowy, bez nowych konwencji)
- [x] commit zmian wykonany

### Dowód działania

Moduł czysto-logiczny (headless, bez pygame), więc dowodem jest wyjście testu jednostkowego + mypy:

![[T-029-test-run.png]]

## 📓 Agent Log

- 2026-07-06 07:16 cc: claimed, starting
- 2026-07-06 07:2x cc: dodano `project/dialog/` (entities.py: dataclassy `slots=True` `DialogNode`/`DialogOption`/`NodeVisitResult`/`NodeVisitResultCategory` bez pygame; graph.py: `init_dialog()` + `get_start_node()` z rozwiązywaniem referencji `next_node`/`result`/opcji i walidacją dangling refs; opcje DEBUG gated flagą `debug`). Test `tests/test_dialog_graph.py` (build, przejście ścieżki do węzła `is_final`, opcje DEBUG, błędy walidacji) - 4/4 PASS, mypy clean.
- 2026-07-06 07:21 cc: Zaimplementowano project/dialog/ (entities + init_dialog) + test_dialog_graph.py 4/4 PASS, mypy clean

## 🙋 Needs-You / Questions
