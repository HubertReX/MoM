---
id: T-032
title: DS: Silnik warunkow - mini-DSL (AST-whitelist + predykaty)
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

# T-032 - DS: Silnik warunkow (mini-DSL)

## 🎯 Goal / Outcome

- [x] `check_condition()` parsuje warunek `ast.parse(mode="eval")` i interpretuje własnym walkerem WYŁĄCZNIE whitelistę węzłów (`BoolOp`, `UnaryOp`, `Compare`, `Call` do whitelisty, `Name`, `Constant`) - nigdy `eval`/`exec`
- [x] predykaty jako jedyny most do danych: `selected(opt)`, `visited(node)`, `visited(NPC, node)`, `has_item(key)`, `sentiment` + porównania
- [x] realne warunki z RPG (Bob, Potioneer) dają poprawny bool; błędny warunek = czytelny błąd, nie cichy fałsz

## 🧭 Context

- **Kontekst wspólny (przeczytaj najpierw):** [[DS-epic-brief]] - lokalizacje repo (RPG i MoM), mapa źródeł RPG↔MoM, decyzje D1-D11.
- Decyzja **D1** (mini-DSL AST-whitelist zamiast `eval`) - `../doc/dialog-migration-plan.html`.
- Źródło warunków do przetestowania: RPG `import_dialog_from_md.py:parse_condition`, `dialog_loc.py:check_condition`.
- Zależy od: [[T-029 DS: Encje dialogu i budowa grafu (DialogNode, Option, Result + init_dialog)]].
- Odblokowuje bramkowanie: [[T-035 DS: Sentyment w rozgrywce - odkrywanie, bramkowanie opcji, mnoznik cen]].

## ⛓️ Constraints

- Web-safe: `ast` to czysty Python, działa w pygbag. Brak `eval`/`exec`.
- Kontekst ewaluacji tylko whitelist (character, hero, config, inne NPC) - bez dostępu do builtins.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [x] Parser `ast.parse(mode="eval")` + walker po dozwolonych węzłach.
- [x] Rejestr predykatów (`selected`/`visited`/`has_item`/`sentiment`).
- [x] Walidacja warunku przy imporcie (nieznana nazwa/funkcja = błąd).
- [x] Testy na realnych warunkach z RPG.

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [x] Testy / lint przechodzą (jeśli dotyczy)
- [x] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [x] commit zmian wykonany

Dowód działania - 19/19 testów jednostkowych mini-DSL (predykaty, kompozycja bool/unary/compare, realne warunki RPG Bob/Potioneer/sentyment/cross-NPC, odrzucanie `eval`-podatnych konstrukcji):

![[agent_20260706_T-032_conditions_tests.png]]

## 📓 Agent Log

- 2026-07-06 07:29 cc: claimed, starting
- 2026-07-06 07:34 cc: Implementacja mini-DSL warunków (D1). Nowy moduł project/dialog/conditions.py: check_condition()/validate_condition() na ast.parse(mode=eval) + własny walker po whiteliście (BoolOp/UnaryOp/Compare/Call-predykaty/Name/Constant), zero eval/exec, zero builtins/atrybutów/subscriptów. Predykaty jako jedyny most: selected(opt), visited(node), visited(npc,node), has_item(key), sentiment. ConditionContext jako Protocol. Walidacja wpięta w graph._build_options (błędny warunek = ValueError przy imporcie, nie cichy False). Testy: tests/test_dialog_conditions.py (19/19) z realnymi warunkami RPG (Bob, Potioneer quest-items, sentiment gate, cross-NPC visited) + odrzucanie eval-podatnych. mypy + isort czyste; regresja test_dialog_graph 4/4.

## 🙋 Needs-You / Questions
