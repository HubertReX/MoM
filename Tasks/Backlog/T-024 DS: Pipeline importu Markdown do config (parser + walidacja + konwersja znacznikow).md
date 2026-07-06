---
id: T-024
title: DS: Pipeline importu Markdown do config (parser + walidacja + konwersja znacznikow)
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

# T-024 - DS: Pipeline importu Markdown do config

## 🎯 Goal / Outcome

- [x] Import Markdown -> config: rozbiór linii opcji jednym regexem z nazwanymi grupami (koniec z rozbiorem pozycyjnym)
- [x] Walidacja grafu po parsowaniu: wiszące referencje, istnienie START, zgodność anchor <-> target, węzły-sieroty; błąd przerywa import z `plik:linia`
- [x] Konwersja znaczników (D3): `[reverse]->[shadow]`, `[red]->[error]`, `[blue]->[item]`, `[yellow]->[char]`, `[key]->:key_X:`, `[symbol]/[e]->:name:`; emoji: `😇->:blessed:`, `😢->:offended:`, `😐->:neutral:`, `😡->:angry:`, `🧠->:wondering:`, `😉->:blink:`, `🤖->:human:`
- [x] i18n: teksty do `messages[lang][key]`, węzły trzymają tylko klucze (D7)
- [x] Postać `Hammer Hoaxheart` przechodzi pełny import bez błędów (12 węzłów; od 2026-07-06 pełny import trafił też do `config.json` - wcześniej grywalny NPC używał 4-węzłowego stuba, patrz Agent Log)

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

- [x] Regex opcji z nazwanymi grupami (target/anchor/order/sentiment/condition/text).
- [x] Walidator grafu z raportem `plik:linia`.
- [x] Tabela konwersji znaczników + emoji (D3).
- [x] Generacja `messages[lang][key]` + sekcji `character_dialogs`.
- [x] Import Hammera jako smoke-test.

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania - narzędzie build-time (bez UI); dowód = testy + wygenerowany config (patrz niżej)
- [x] Testy / lint przechodzą (jeśli dotyczy)
- [x] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [x] commit zmian wykonany

### Dowód działania

Narzędzie build-time (parser Markdown->config, bez UI do zrzutu). Dowód:

- `tests/test_dialog_import.py` - 8/8 PASS (regex opcji, walidacja grafu, konwersja D3, i18n D7, mini-DSL).
- Wszystkie 5 postaci (`HAMMER_HOAXHEART`, `BARMAN_ABSINTHRAYNER`, `CLAPBACK_SWORD`, `POTIONEER_PUZZLEMINT`, `MADAME_SARCASMIA`) buduje się przez `init_dialog` z wygenerowanego `config.json`; wszystkie referencje komunikatów rozwiązują się w EN i PL.
- Wizualne potwierdzenie renderu Hammera w grze: patrz [[T-033 DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)]].

## 📓 Agent Log

- 2026-07-06 07:50 opencode: claimed, starting
- 2026-07-06 08:07 opencode: Implemented dialog/markdown_importer.py: named-group regex option parser, graph validation with file:line errors, D3 tag/emoji conversion, D7 i18n messages, mini-DSL condition conversion. Added tests/test_dialog_import.py with Hammer Hoaxheart smoke-test plus Barman/Potioneer coverage. All dialog tests, mypy and isort pass. Updated project/AGENTS.md.
- 2026-07-06 08:11 opencode: Implemented and tested. Import pipeline parses Markdown with named-group regex, validates graph with file:line errors, converts D3 tags/emoji, generates D7 i18n messages, and rewrites conditions to mini-DSL. Hammer Hoaxheart passes smoke-test. All dialog tests + mypy + isort pass. Ready for review.
- 2026-07-06 17:05 cc (review): Import był udowodniony w testach, ale wynik nigdy nie trafił do `config.json` - grywalny NPC "Hammer" używał 4-węzłowego ręcznego stuba (`START/SELL/MORE/END`). Wygenerowano pełny import (`markdown_importer.py "Hammer Hoaxheart"`, 12 węzłów, 40 komunikatów EN/PL), podmieniono stub w `config.json` na `HAMMER_HOAXHEART`, zaktualizowano `characters.Hammer.dialog_key`, usunięto osierocone klucze stuba. Wszystkie 5 grafów buduje się, referencje komunikatów rozwiązują się w EN i PL. Uwaga jakości źródła: RPG `EN/char-Hammer_Hoaxheart.md` (jak i inni migrowani) zawiera polski tekst - import wierny, ale EN=PL (zastany problem danych RPG, poza zakresem).

## 🙋 Needs-You / Questions
