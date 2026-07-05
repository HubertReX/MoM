---
id: T-024
title: DS: Pipeline importu Markdown do config (parser + walidacja + konwersja znacznikow)
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

# T-024 - DS: Pipeline importu Markdown do config

## 🎯 Goal / Outcome

- [ ] Import Markdown -> config: rozbiór linii opcji jednym regexem z nazwanymi grupami (koniec z rozbiorem pozycyjnym)
- [ ] Walidacja grafu po parsowaniu: wiszące referencje, istnienie START, zgodność anchor <-> target, węzły-sieroty; błąd przerywa import z `plik:linia`
- [ ] Konwersja znaczników (D3): `[reverse]->[shadow]`, `[red]->[error]`, `[blue]->[item]`, `[yellow]->[char]`, `[key]->:key_X:`, `[symbol]/[e]->:name:`; emoji: `😇->:blessed:`, `😢->:offended:`, `😐->:neutral:`, `😡->:angry:`, `🧠->:wondering:`, `😉->:blink:`, `🤖->:human:`
- [ ] i18n: teksty do `messages[lang][key]`, węzły trzymają tylko klucze (D7)
- [ ] Postać `Hammer Hoaxheart` przechodzi pełny import bez błędów

## 🧭 Context

- **Kontekst wspólny (przeczytaj najpierw):** [[DS-epic-brief]] - lokalizacje repo (RPG i MoM), mapa źródeł RPG↔MoM, decyzje D1-D11.
- Źródło: RPG `import_dialog_from_md.py`, dialogi `RPG/dialogs/PL` i `RPG/dialogs/EN`.
- Decyzje **D6** (porządny parser + walidacja), **D3** (konwersja znaczników/emoji), **D7** (i18n messages), **D11** (Markdown źródłem prawdy) - `../doc/dialog-migration-plan.html`.
- Walidacja nazw itemów względem `project/config_model/items.csv`.
- Zależy od: [[T-029 DS: Encje dialogu i budowa grafu (DialogNode, Option, Result + init_dialog)]], [[T-023 DS: Model NPC i pola sentymentu (dialog_key, sentiment, disposition)]].
- Odblokowuje: [[T-033 DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)]], [[T-028 DS: Migracja pozostalych postaci + web smoke-test + testy wizualne]].

## ⛓️ Constraints

- Config generowany jest artefaktem maszynowym (JSON OK - nikt nie edytuje ręcznie); źródłem prawdy jest Markdown.
- Import to narzędzie build-time (nie musi działać na web).
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [ ] Regex opcji z nazwanymi grupami (target/anchor/order/sentiment/condition/text).
- [ ] Walidator grafu z raportem `plik:linia`.
- [ ] Tabela konwersji znaczników + emoji (D3).
- [ ] Generacja `messages[lang][key]` + sekcji `character_dialogs`.
- [ ] Import Hammera jako smoke-test.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

## 🙋 Needs-You / Questions
