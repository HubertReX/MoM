---
id: T-039
title: DS bug: wskaznik opcji pokazuje generyczna ikone zamiast emotki sentymentu z pliku MD
status: backlog
owner: human
priority: p2
type: bug
agent:
created: 2026-07-06
updated: 2026-07-06
tags:
  - task
---
# T-039 - DS bug: wskaznik opcji pokazuje generyczną ikonę zamiast emotki sentymentu

## 🎯 Goal / Outcome

- [ ] Przy każdej opcji renderuje się emotka sentymentu z pliku MD (`:blessed:` 😇, `:angry:` 😡, `:wondering:` 🧠, `:neutral:` 😐, `:offended:` 😢, `:blink:` 😉) jako sprite z emote-sheet
- [ ] Zachowana mechanika odkrywania wagi (D10 / [[T-035 DS: Sentyment w rozgrywce - odkrywanie, bramkowanie opcji, mnoznik cen]]): dla nieodkrytego sentymentu `?`, po odkryciu liczba `+N`/`-N` - ale emotka jest zawsze widoczna
- [ ] Doprecyzować układ kolumny: emotka + (waga lub `?`), zamiast obecnego pustego/generycznego pudełka

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

- [ ] **Układ (zdecydowane - opcja A):** emotka sentymentu + waga **obok siebie w poziomie** w jednym rzędzie (`😇 +2` / `😇 ?`). Poszerzyć kolumnę wag.
- [ ] W `_build_weight_indicator` (lub nowej metodzie) pobrać sprite emotki dla `opt.sentiment` z emote-sheet i skomponować z tekstem wagi/`?`.
- [ ] Dostroić `_WEIGHT_COL` i `_weight_pos` do nowej szerokości (emotka + waga).
- [ ] **Wyjustowanie:** kolumna wskaźników musi być **idealnie wyrównana** między opcjami - emotka i waga w tej samej pozycji X dla każdej opcji (stałej szerokości slot na emotkę + stały slot na wagę, prawy/lewy align konsekwentnie). Dziś generyczna ikona "pływała" i nie zawsze była jedna pod drugą dla różnych opcji - to naprawić.
- [ ] Zweryfikować, że dla nieodkrytych wag emotka jest widoczna, a waga to `?`.
- [ ] Test wizualny: hub Hammera 001 - 6 opcji, każda z inną emotką; sprawdzić że wskaźniki są idealnie w pionie jeden pod drugim.

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

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

- 2026-07-06 cc (review): utworzony podczas weryfikacji epica DS. Root cause: `_build_weight_indicator` rysuje tylko wagę, nie sprite emotki `opt.sentiment`.
- 2026-07-07 decyzja (autor): układ **opcja A** - emotka + waga obok siebie w poziomie. Dodatkowy wymóg: idealne wyjustowanie kolumny wskaźników (dziś ikony "pływały", nie były w pionie).

## 🙋 Needs-You / Questions

- (brak - wszystko rozstrzygnięte)
