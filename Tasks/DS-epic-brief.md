---
tags:
  - epic
  - dialog-system
---

# DS - Brief epica "Dialog System"

Wspólny kontekst dla wszystkich zadań `DS:` (przeniesienie logiki dialogów z RPG do MoM).
**Agencie: przeczytaj to najpierw.** Zadania linkują tu przez `[[DS-epic-brief]]` zamiast powtarzać kontekst.

## Lokalizacje repozytoriów

- **MoM (target, tu pracujesz):** to repo. `github.com/HubertReX/MoM`. Silnik: Pygame-CE, dual-target desktop + web (pygbag/WASM).
- **RPG (source, oddzielne repo):** `/Users/hubertnafalski/Projects/RPG` na maszynach roboczych, `github.com/HubertReX/RPG`. Stamtąd przenosimy logikę dialogów (tekstowy prototyp, rich/Textual). Jeśli katalog nie istnieje - sklonuj z GitHuba.

## Mapa źródeł: RPG (skąd) -> MoM (dokąd)

Referencje `plik:linia` w zadaniach dotyczą repo **RPG**, chyba że ścieżka zaczyna się od `project/` (wtedy MoM).

| Rola | RPG (source) | MoM (target) |
| --- | --- | --- |
| Encje grafu | `dialog_node.py` (kanoniczna: 7 kategorii, `slots=True`) | nowy moduł w `project/` (np. `project/dialog/`) |
| Budowa grafu | `main.py:1108-1224` (`load_character_dialogs`, `init_dialog`, opcje DEBUG) | odpowiednik w MoM |
| Runtime rozmowy | `main.py:2700-2811` (`action_talk`, `process_result`, filtr opcji, sentyment) | `project/ui/panels/dialog.py` + stan `Talk` w `project/npc_state.py` |
| Warunki opcji | `dialog_loc.py:19` (`check_condition`, `eval`), `import_dialog_from_md.py:parse_condition` | nowy silnik mini-DSL (D1) |
| Parser autorstwa | `import_dialog_from_md.py` (`parse_markdown`, `parse_result`, `convert_nodes`) | nowy parser + walidacja (D6) |
| Pola postaci | `character.py` (`dialog`, `sentiment`, `disposition`, `known_disposition`, `selected_options_dict`) | `project/characters.py` (NPC, `load_dialogs:290`, otwarcie panelu `:1316`) |
| Dialogi autorskie | `dialogs/PL/char-*.md`, `dialogs/EN/char-*.md` | pozostają w Markdown jako źródło (D11) |
| Config wynikowy | `config.json` (`character_dialogs` + `messages`) | `project/config_model/` (config + `items.csv`, `characters.csv`) |
| Render znaczników | rich (`[reverse]`, `[italic]`, ...) | `project/ui/widgets/rich_text.py`, tagi w `project/settings.py:238` (`STYLE_TAGS_DICT`), emote `:key:` w `project/settings.py:688` (`EMOTE_SHEET_DEFINITION`) |
| Efekty | `main.py:process_result` | Inventory / hero / HP; adapter `ResultSink` (D8) |
| Handel | `trade_spread` | `project/ui/panels/trade.py` |
| Zapis stanu | (w obiekcie) | `project/save_load/`, testy `tests/test_save_load_*.py` |

## Decyzje projektowe (digest D1-D11)

Pełne uzasadnienie i opcje: `../doc/dialog-migration-plan.html` (sekcja 7 "Decyzje"). Skrót:

- **D1 - warunki:** mini-DSL. `ast.parse(mode="eval")` + własny walker po whiteliście węzłów (`BoolOp`/`UnaryOp`/`Compare`/`Call`-whitelist/`Name`/`Constant`); NIGDY `eval`/`exec`. Predykaty: `selected`, `visited`, `has_item`, `sentiment`.
- **D2 - encje:** dataclassy `slots=True` (web bez Pydantic). Graf jako dicty walidowane przy imporcie.
- **D3 - znaczniki:** konwersja jednorazowa przy imporcie. `[reverse]->[shadow]`, `[red]->[error]`, `[blue]->[item]`, `[yellow]->[char]`, `[key]->:key_X:`, `[symbol]/[e]->:name:`. Emoji: `😇->:blessed:`, `😢->:offended:`, `😐->:neutral:`, `😡->:angry:`, `🧠->:wondering:`, `😉->:blink:`, `🤖->:human:`.
- **D4 - sterowanie:** hybryda - kursor gora/dol + Enter, skróty 1-9, mysz.
- **D5 - zapis:** pełny stan rozmowy per-NPC (kursor, `selected_options_dict`, `sentiment`, `visited`, `selected`).
- **D6 - parser:** jeden regex z nazwanymi grupami + walidacja grafu z `plik:linia`. JSON tylko generowany maszynowo (nie edytowany ręcznie).
- **D7 - i18n:** `messages[lang][key]`, węzły trzymają tylko klucze; potrzebny `get_msg()` w MoM.
- **D8 - efekty:** adapter `ResultSink` (Protocol), silnik bez importów z gry. Nazwy itemów muszą zgadzać się z `items.csv`.
- **D9 - DEBUG:** opcje DEBUG gated `IS_DEBUG_MODE` (szybki test drzew).
- **D10 - sentyment:** pełny. Odkrywanie `known_disposition` (waga po pierwszym użyciu, UI `?`), bramkowanie opcji `sentiment >= N`, handel = jeden mnożnik cen. Feedback zmiany = backlog ([[T-036 DS: Feedback zmiany sentymentu - floating plus-minus N (later)]]).
- **D11 - źródło prawdy:** Markdown; `config.json` generowany.

## Zasady projektu istotne dla DS

- **Dual-target:** każda zmiana działa na desktopie i web (web bez Pydantic, wyłączone shadery). Wykrywanie: `project/settings.py` `IS_WEB`.
- **Type hints wymagane** (mypy `disallow_untyped_defs`).
- **Złota reguła konfiguracji:** do ręcznej edycji nigdy JSON - preferuj YAML/TOML. JSON tylko jako artefakt generowany.
- Podglądy do D3: `doc/img/mom-emote-sheet.png`, `doc/img/mom-richtext-tags.png` (regeneracja: `just gen-dialog-docs`).

## Kolejność realizacji (zależności)

```
T-029 (encje)
 ├─> T-032 (mini-DSL warunki)
 └─> T-023 (model NPC)
        └─> T-024 (pipeline import)
               └─> T-033 (UI DialogPanel)
                      ├─> T-034 (efekty ResultSink)
                      │      └─> T-030 (persystencja)
                      └─> T-035 (sentyment gameplay)  [wymaga tez T-032]
T-028 (migracja postaci + web smoke-test)  - po T-024/033/034/030
T-036 (feedback zmiany sentymentu)         - later, po T-035
```
