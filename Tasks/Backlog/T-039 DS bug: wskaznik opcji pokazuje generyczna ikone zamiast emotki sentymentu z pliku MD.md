---
id: T-039
title: DS bug: wskaznik opcji pokazuje generyczna ikone zamiast emotki sentymentu z pliku MD
status: needs-you
owner: human
priority: p2
type: bug
agent: opencode
created: 2026-07-06
updated: 2026-07-06
tags:
  - task
state: review
---
# T-039 - DS bug: wskaznik opcji pokazuje generyczną ikonę zamiast emotki sentymentu

## 🎯 Goal / Outcome

- [x] Przy każdej opcji renderuje się emotka sentymentu z pliku MD (`:blessed:` 😇, `:angry:` 😡, `:wondering:` 🧠, `:neutral:` 😐, `:offended:` 😢, `:blink:` 😉) jako sprite z emote-sheet
- [x] Zachowana mechanika odkrywania wagi (D10 / [[T-035 DS: Sentyment w rozgrywce - odkrywanie, bramkowanie opcji, mnoznik cen]]): dla nieodkrytego sentymentu `?`, po odkryciu liczba `+N`/`-N` - ale emotka jest zawsze widoczna
- [x] Doprecyzować układ kolumny: emotka + (waga lub `?`), zamiast obecnego pustego/generycznego pudełka

## 🧭 Context

- **Kontekst wspólny:** [[DS-epic-brief]] (emote `EMOTE_SHEET_DEFINITION` w `project/settings.py:688`, `SENTIMENT_EMOJI_TO_EMOTE`).
- Zgłoszone przez użytkownika: "po prawej w każdej opcji widzę taką samą generyczną ikonę klawisza, a powinna być emotka z oryginalnego pliku MD".
- Każda opcja w źródle MD niesie emoji sentymentu, np. `* [001](#001) 1😇: ...` -> po imporcie `option.sentiment = "blessed"` (patrz `project/dialog/markdown_importer.py::_convert_sentiment`, `_OPTION_RE` grupa `sentiment`).
- **Root cause (potwierdzony):** `project/ui/panels/dialog.py::_build_weight_indicator()` (linie ~224-245) renderuje TYLKO wagę dyspozycji (`self.npc.known_disposition[opt.sentiment]` albo `?`) przez `self._weight_font.render(...)`. Nie rysuje sprite'a emotki `opt.sentiment` z emote-sheet - stąd "generyczne pudełko".
- Powiązane: [[T-038 DS bug: opcje dialogu renderowane plain fontem - znaczniki italic i kolory literalnie]], [[T-035 DS: Sentyment w rozgrywce - odkrywanie, bramkowanie opcji, mnoznik cen]].

## ⛓️ Constraints

- Dual-target desktop + web.
- Nie rozwalić layoutu kolumny wag (`_WEIGHT_COL = 46`, `_weight_pos`) z [[T-037 DialogPanel nie zamyka rozmowy przy opcji finalnej poza widocznym zwojem listy]] - może wymagać poszerzenia kolumny na emotkę + wagę.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [x] **Układ (zdecydowane - opcja A):** emotka sentymentu + waga **obok siebie w poziomie** w jednym rzędzie (`😇 +2` / `😇 ?`). Poszerzyć kolumnę wag.
- [x] W `_build_weight_indicator` (lub nowej metodzie) pobrać sprite emotki dla `opt.sentiment` z emote-sheet i skomponować z tekstem wagi/`?`.
- [x] Dostroić `_WEIGHT_COL` i `_weight_pos` do nowej szerokości (emotka + waga).
- [x] **Wyjustowanie:** kolumna wskaźników musi być **idealnie wyrównana** między opcjami - emotka i waga w tej samej pozycji X dla każdej opcji (stałej szerokości slot na emotkę + stały slot na wagę, prawy/lewy align konsekwentnie). Dziś generyczna ikona "pływała" i nie zawsze była jedna pod drugą dla różnych opcji - to naprawić.
- [x] Zweryfikować, że dla nieodkrytych wag emotka jest widoczna, a waga to `?`.
- [x] Test wizualny: hub Hammera 001 - 6 opcji, każda z inną emotką; sprawdzić że wskaźniki są idealnie w pionie jeden pod drugim.

## 🎨 Jawne mapowanie sentyment -> emote (ustalone 2026-07-05, epic §6b)

Emotka renderowana przy opcji wg `opt.sentiment` (sprite z `EMOTE_SHEET_DEFINITION`, `SENTIMENT_EMOJI_TO_EMOTE`):

| RPG unicode | Znaczenie | Emote MoM (`:key:`) |
| --- | --- | --- |
| 😇 | kind (miły) | `:blessed:` |
| 😢 | weak (współczucie/smutek) | `:offended:` |
| 😐 | neutral | `:neutral:` |
| 😡 | angry | `:angry:` |
| 🧠 | smart (spryt) | `:wondering:` |
| 😉 | funny (żart) | `:blink:` |
| 🤖 | technical (opcja systemowa) | `:human:` |

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [x] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

![[agent_20260707_T-039_hub_node.png|Hammer dialog hub node - 6 opcji z emote sentymentu (blessed, angry, wondering, blink, neutral, offended) + waga/?]]

Screenshot z testu `Hammer Dialog Flow` — panel dialogowy Hammera z 6 opcjami, każda z emote sentymentu z emote-sheet zamiast poprzedniej generycznej ikony klawisza. Waga pokazuje `?` (nieodkryty sentyment) lub wartość liczbową obok emotki.

Zmiany w `project/ui/panels/dialog.py`:
- `_build_weight_indicator()`: zastąpiono `self.key_icon` (generyczna ikona klawisza) sprite'em `self.scene.icons[opt.sentiment][0]` z emote-sheet (np. `:blessed:`, `:angry:`). Fallback do `key_icon` dla nieznanych kluczy.
- `_WEIGHT_COL`: zwiększono z 46→60px dla wygodnego pomieszczenia emotki (14px) + wagi tekstowej.

Testy: `test_dialog_graph`, `test_dialog_conditions`, `test_dialog_result_sink` — wszystkie przechodzą. mypy clean. Scenariusz `Hammer Dialog Flow` OK (`dialog_open` ss-review PASS).

## 📓 Agent Log

- 2026-07-06 cc (review): utworzony podczas weryfikacji epica DS. Root cause: `_build_weight_indicator` rysuje tylko wagę, nie sprite emotki `opt.sentiment`.
- 2026-07-07 decyzja (autor): układ **opcja A** - emotka + waga obok siebie w poziomie. Dodatkowy wymóg: idealne wyjustowanie kolumny wskaźników (dziś ikony "pływały", nie były w pionie).
- 2026-07-07 17:10 opencode: claimed, starting
- 2026-07-07 17:30 opencode: fix applied — `_build_weight_indicator` now renders `scene.icons[opt.sentiment][0]` emote sprite instead of generic `key_icon`. `_WEIGHT_COL` bumped 46→60. Tests pass (dialog unit + Hammer Dialog Flow scenario). Screenshot shows hub node with 6 distinct sentiment emotes.
- 2026-07-07 17:30 opencode: fix applied: _build_weight_indicator now renders scene.icons[opt.sentiment][0] emote sprite instead of generic key_icon. _WEIGHT_COL bumped 46->60. Unit tests + Hammer Dialog Flow scenario pass.
- 2026-07-07 17:30 opencode: fix applied: _build_weight_indicator renders emote sprite (scene.icons[opt.sentiment][0]) instead of generic key_icon per option. _WEIGHT_COL 46->60. Unit tests (graph, conditions, result_sink) pass. Hammer Dialog Flow scenario passes (dialog_open ss-review PASS). Screenshot in _attachments/.

## 🙋 Needs-You / Questions

- (brak - wszystko rozstrzygnięte)
