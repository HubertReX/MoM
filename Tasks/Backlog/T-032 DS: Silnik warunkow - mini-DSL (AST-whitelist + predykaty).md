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

- [ ] `check_condition()` parsuje warunek `ast.parse(mode="eval")` i interpretuje własnym walkerem WYŁĄCZNIE whitelistę węzłów (`BoolOp`, `UnaryOp`, `Compare`, `Call` do whitelisty, `Name`, `Constant`) - nigdy `eval`/`exec`
- [ ] predykaty jako jedyny most do danych: `selected(opt)`, `visited(node)`, `visited(NPC, node)`, `has_item(key)`, `sentiment` + porównania
- [ ] realne warunki z RPG (Bob, Potioneer) dają poprawny bool; błędny warunek = czytelny błąd, nie cichy fałsz

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

- [ ] Parser `ast.parse(mode="eval")` + walker po dozwolonych węzłach.
- [ ] Rejestr predykatów (`selected`/`visited`/`has_item`/`sentiment`).
- [ ] Walidacja warunku przy imporcie (nieznana nazwa/funkcja = błąd).
- [ ] Testy na realnych warunkach z RPG.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

- 2026-07-06 07:29 cc: claimed, starting

## 🙋 Needs-You / Questions
