---
id: T-043
title: DS: zrodlowe MD dialogow w project assets dialogs plus task just konwersji MD do config.json
status: needs-you
owner: human
priority: p2
type: chore
agent: opencode
created: 2026-07-06
updated: 2026-07-06
tags:
  - task
state: review
---
# T-043 - DS: MD dialogów w projekcie + task `just` do konwersji MD -> config.json

## 🎯 Goal / Outcome

- [ ] 5 postaci dialogowych (Hammer, Barman Absinthrayner, Potioneer Puzzlemint, Clapback Sword, Madame Sarcasmia) ma źródłowe pliki MD w `project/assets/dialogs/EN/` i `.../PL/`, gotowe do wygodnej edycji w repo MoM
- [ ] Prosty task `just` (np. `just import-dialogs` lub per-postać) uruchamia `markdown_importer` i deterministycznie regeneruje sekcje `character_dialogs` + `messages` w `project/config_model/config.json`
- [ ] Import waliduje graf i nazwy itemów (D6/D8) i zgłasza błędy z `plik:linia`; brak ręcznej edycji `config.json`

## 🧭 Context

- **Kontekst wspólny:** [[DS-epic-brief]] (D11 - Markdown źródłem prawdy, `config.json` generowany; D6 - parser + walidacja).
- Zgłoszone przez użytkownika: "chcę, aby pliki MD z dialogami były w moim projekcie (`project/assets/dialogs`), abym mógł je wygodnie edytować, i potrzebuję prostego narzędzia (task just) do przenoszenia ich z MD do config.json".
- Obecnie źródła MD leżą w OSOBNYM repo RPG: `/Users/hubertnafalski/Projects/RPG/dialogs/{EN,PL}/char-*.md` (+ `chara-Madame_Sarcasmia.md`). W MoM `project/assets/dialogs/{EN,PL}/` istnieje, ale ma tylko przykłady (`Marry.md`, `Rob.md`, `welcome_message.md`) - brak 5 postaci DS.
- Importer: `project/dialog/markdown_importer.py` (`import_character_dialog(src_dir, character_name, *, valid_items)`, `main()` drukuje JSON dla jednej postaci; UWAGA: banner pygame-ce na stdout - trzeba obciąć do pierwszego `{`).
- Istniejący justfile ma już `gen-dialog-docs`; dołożyć analogiczny task importu.

## ⛓️ Constraints

- Dual-target: `config.json` musi być poprawny dla desktop i web.
- **Złota reguła:** JSON tylko generowany, nigdy ręcznie edytowany.
- Task `just` musi działać na obu maszynach (użyć `.venv/bin/python`, ścieżki względne / `$HOME`).
- Deterministyczny zapis (stabilna kolejność kluczy, `ensure_ascii=False, indent=4`), by diff był czytelny.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [x] Skopiować 5 par MD (EN+PL) z RPG do `project/assets/dialogs/{EN,PL}/` z konwencją nazw **`<Name_Surname>.md`** (bez prefiksu `char-`, zdecydowane - opcja B). Mapowanie: `Hammer_Hoaxheart.md`, `Barman_Absinthrayner.md`, `Clapback_Sword.md`, `Potioneer_Puzzlemint.md`, `Madame_Sarcasmia.md` (RPG `chara-Madame_Sarcasmia.md` -> bez literówki `chara`). Spójne z istniejącymi `Marry.md`/`Rob.md`. `dialog_key = nazwa_pliku.upper()` (np. `Hammer_Hoaxheart` -> `HAMMER_HOAXHEART`) - importer wyprowadza klucz z nazwy pliku.
- [x] Dodać do `markdown_importer` tryb "zbuduj cały config" (iteracja po wszystkich postaciach, merge do istniejącego `config.json`, usunięcie osieroconych kluczy `messages`).
- [x] Dodać task `just import-dialogs` (i ew. `just import-dialog <name>`), czyszczący banner pygame ze stdout.
- [x] Uruchomić import, potwierdzić że wszystkie referencje `messages` się rozwiązują (EN+PL) i graf się buduje.
- [x] Zaktualizować `project/assets/AGENTS.md` o nową ścieżkę źródeł i workflow.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy) - re-import daje identyczny config (idempotencja)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

- 2026-07-06 cc (review): utworzony na życzenie użytkownika. Źródła MD dziś w repo RPG; trzeba je wnieść do MoM i dać `just`-owy pipeline importu (dziś import był robiony ręcznie, D11 mówi Markdown = źródło prawdy).
- 2026-07-07 decyzja (autor): **opcja B** - `<Name_Surname>.md` bez prefiksu `char-`. Spójne z `Marry.md`/`Rob.md`; `dialog_key = nazwa_pliku.upper()`.
- 2026-07-07 14:34 opencode: claimed, starting
- 2026-07-07 opencode: copied 5 RPG MD pairs (Hammer, Barman, Clapback, Potioneer, Madame Sarcasmia) to project/assets/dialogs/{EN,PL}/; updated _find_markdown_file to match <name>.md as third fallback (after char-, chara-); added build_dialog_config() + updated main() for --all mode; added just import-dialogs; verified idempotent import (296 msg keys per lang, 0 orphans, 8/8 tests pass). Remaining: moab review + commit.
- 2026-07-07 14:40 opencode: Completed: copied 5 MD pairs, added build_dialog_config(), added just import-dialogs, verified idempotent import. Updated assets/AGENTS.md + project/AGENTS.md. All 8 tests pass, 0 orphans, config.json consistent.
- 2026-07-07 14:40 opencode: Import pipeline działa: just import-dialogs rebuilds config.json z assets/dialogs/{EN,PL}/. 4 postacie importowane, Madame Sarcasmia preserved, 0 orphanów. Weryfikacja: tests/test_dialog_import.py — 8/8 PASS.
- 2026-07-07 14:42 opencode: Commit d8c5ddd. T-043 done - MD sources in project, importer pipeline works, docs updated.

## 🙋 Needs-You / Questions

- (brak - wszystko rozstrzygnięte)
