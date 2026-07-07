---
id: T-038
title: DS bug: opcje dialogu renderowane plain fontem - znaczniki italic i kolory literalnie
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
# T-038 - DS bug: opcje dialogu renderowane plain fontem (znaczniki i emotki literalnie)

## 🎯 Goal / Outcome

- [ ] Tekst opcji dialogowej przechodzi przez ten sam parser znaczników co treść węzła (RichText / `STYLE_TAGS_DICT`), więc `[italic]`, `[shadow]`, kolory (`[char]`/`[item]`/`[loc]`/`[error]`) renderują się jako styl, a nie dosłowny tekst
- [ ] Inline emotki (`:blessed:`, `:key_1:`, ...) w treści opcji renderują się jako sprite z emote-sheet, nie jako literalny `:name:`
- [ ] Prefiks numeru (`1. `, `2. `) nadal działa, kursor i clip do szerokości kolumny bez najeżdżania na kolumnę wag (`_WEIGHT_COL`)

## 🧭 Context

- **Kontekst wspólny:** [[DS-epic-brief]] (D3 - konwersja znaczników, render `project/ui/widgets/rich_text.py`, `STYLE_TAGS_DICT` w `project/settings.py:303`, emote `:key:` w `EMOTE_SHEET_DEFINITION`).
- Zgłoszone przez użytkownika na zrzucie z rozmowy z Hammerem: opcja "3. A po co tym [italic]francuskim pieskom[/italic] dobra broń?" pokazuje znaczniki `[italic]...[/italic]` dosłownie.
- **Root cause (potwierdzony w kodzie):** `project/ui/panels/dialog.py` `_refresh_options()` (linie ~165-175) buduje etykiety opcji przez `Label(f"{i}. {text}", size=_OPTION_FONT, ...)`. `Label` to zwykły render czcionki (`font.render`) - **nie parsuje** znaczników RichText ani emotek. Treść węzła (`self.body = RichText(...)`, `dialog.py:76`) parsuje je poprawnie; opcje nie.
- Import (`project/dialog/markdown_importer.py::_convert_text`) generuje poprawne znaczniki MoM (`[italic]`, `[shadow]`, `:blessed:` itd.) - dane w `config.json` są OK, problem jest wyłącznie po stronie renderu opcji.
- Powiązane: [[T-039 DS bug: wskaznik opcji pokazuje generyczna ikone zamiast emotki sentymentu z pliku MD]] (kolumna wag/emotka), [[T-033 DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)]].

## ⛓️ Constraints

- Dual-target desktop + web (web bez shaderów; RichText już działa na obu).
- Nie zepsuć layoutu z [[T-037 DialogPanel nie zamyka rozmowy przy opcji finalnej poza widocznym zwojem listy]]: font opcji 14, dynamiczna wysokość tekstu węzła, rezerwa kolumny wag, przewijanie viewportu.
- Type hints wymagane (mypy).

## 🪜 Plan / Subtasks

- [x] Zamienić `Label` opcji na wariant renderujący przez RichText (lub wspólny helper `render_rich(text)`), zachowując rozmiar `_OPTION_FONT` i shadow.
- [x] Zmierzyć szerokość/wysokość z zbakowanej powierzchni RichText (jak przy treści węzła), by clip do `max_w` i pozycjonowanie w `_layout_options()` dalej działały.
- [x] Zweryfikować wizualnie: kursywa, pogrubienie, kolor i inline emotka w opcji.
- [x] Rozważyć, czy prefiks `"N. "` ma być poza RichText (stały) czy w tym samym stringu.
  - **Decyzja:** prefiks w tym samym stringu RichText (renderuje się jako plain text, brak tagów).

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione — opcje dialogu przechodzą przez RichText parser, znaczniki `[italic]`, `[shadow]`, kolory (`[char]`/`[item]`) renderują się jako styl
- [x] Inline emotki (`:blessed:`, `:key_1:`) w treści opcji renderują się jako sprite z emote-sheet (przez `render_rich_text_surface` → `icons` z `scene.icons`)
- [x] Prefiks numeru (`1. `, `2. `) działa w tym samym stringu RichText, kursor i clip do szerokości kolumny bez najeżdżania na kolumnę wag
- [x] zmiany udokumentowane w tasku (`moab log`)
- [x] dowód działania — screenshot hub_node z 6 poprawnie wyrenderowanymi opcjami:
  ![[agent_20260707_T-038_hub_node.png]]
- [x] Testy / lint przechodzą - `Hammer Dialog Flow` (3/3 screenshot_review PASS), mypy clean
- [x] AGENTS.md aktualizacja nie jest potrzebna (zmiana wewnątrz istniejącego modułu, zgodna z opisaną architekturą)
- [ ] commit zmian wykonany (pending review)

## 📓 Agent Log

- 2026-07-06 cc (review): utworzony podczas weryfikacji epica DS. Root cause wskazany w Context (opcje przez `Label`, nie RichText).
- 2026-07-07 09:36 opencode: claimed, implementacja + testy + screenshot proof
- 2026-07-07 opencode (`render_rich_text_surface`): Dodano statyczną funkcję `render_rich_text_surface()` w `project/ui/widgets/rich_text.py` która renderuje styled text + emoji (BBCode-like tags przez `markup.parse()`, word-wrap, drop-shadow) do pojedynczej `pygame.Surface`. Reużywa tego samego `_WORD_RE` i logiki layoutu co `RichText` ale bez overheadu widgetu (scroll, rect, event handling).
- 2026-07-07 opencode (`dialog.py`): Zastąpiono `Label` dla opcji na `render_rich_text_surface()`. Zmieniono `option_labels: list[Label]` → `option_surfaces: list[pygame.Surface]`. W `_layout_options()` y-advancement używa `surf_h + _OPTION_PAD + _OPTION_GAP` zamiast stałego `per` (zapobiega overlappingowi przy zawijaniu wierszy). W `draw()` blit powierzchni zamiast `label.draw()`. Prefiks `N. ` w tym samym stringu co treść opcji (renderuje się jako plain text).
- 2026-07-07 09:47 opencode: Zaimplementowano renderowanie opcji dialogu przez RichText. Dodano funkcję render_rich_text_surface() w rich_text.py (layout+bake word-wrapped styled text na statyczną powierzchnię). W dialog.py zastąpiono Label opcji na rich-text surface, z actual-height y-advancement w layout (zapobiega overlappingowi przy zawijaniu długich opcji). Test Hammer Dialog Flow przechodzi (3 screenshot review PASS, mypy clean).
- 2026-07-07 09:47 opencode: Zaimplementowano: (1) render_rich_text_surface() w rich_text.py — statyczny render styled text + emoji do powierzchni, word-wrap, drop-shadow. (2) dialog.py: Label opcji → rich-text surface, y-advancement per actual height (fix overlapping przy zawijaniu). Test Hammer Dialog Flow: 3/3 screenshot_review PASS, mypy clean. Screenshot dowodu: _attachments/agent_20260707_T-038_hub_node.png (hub node z 6 opcjami, [italic] Hammera renderowany jako styl).

## 🙋 Needs-You / Questions
