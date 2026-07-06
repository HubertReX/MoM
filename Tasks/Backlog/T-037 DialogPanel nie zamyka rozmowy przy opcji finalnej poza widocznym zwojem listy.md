---
id: T-037
title: DialogPanel nie zamyka rozmowy przy opcji finalnej poza widocznym zwojem listy
status: needs-you
owner: human
priority: p2
type: bug
agent: cc
created: 2026-07-06
updated: 2026-07-06
tags:
  - task
state: review
---

# T-037 - DialogPanel nie zamyka rozmowy przy opcji finalnej poza widocznym zwojem listy

## 🎯 Goal / Outcome

- [x] Wybór opcji prowadzącej do węzła `is_final` zamyka panel rozmowy niezależnie od ścieżki wejścia (accept/talk, klawisz `1-9`, mysz) - naprawiono flagą `_pending_close` + centralne domknięcie w `game_ui`
- [x] Lista opcji przewija się tak, aby zaznaczona kursorem opcja była zawsze widoczna; opcje mieszczą się w ramce (font 18->14, dynamiczna wysokość tekstu, rezerwa kolumny wag, wskaźniki `▲/▼`)
- [x] Indeksowanie opcji spójne (`self._options` = jedno źródło prawdy dla kursora, `1-9`, myszy i `activate_selected`), także przy wstrzykniętych opcjach DEBUG

## 🧭 Context

- **Kontekst wspólny:** [[DS-epic-brief]].
- Znalezione podczas review [[T-033 DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)]] na pełnym imporcie Hammera (węzeł-hub 001 ma 6 realnych opcji, a opcja "goodbye" prowadząca do finalnego 990 jest ostatnia).
- Repro: rozmowa z Hammerem -> dojść do węzła 001 -> wybrać ostatnią opcję ("Żegnam", `next_node=990`, `is_final`). Panel nie zamyka się, gdy ta opcja renderuje się poniżej widocznego obszaru panelu.
- Kod: `project/ui/panels/dialog.py` - `_refresh_options` (buduje wszystkie etykiety bez clipowania viewportu), `activate_selected` (linie ~218-253, zwraca `True` gdy `next_node.is_final`), obsługa klawiszy `1-9` (linie ~315-319, `idx < len(option_labels)`), `select_next`/`_set_index`.
- Powiązane: opcje DEBUG gated `IS_DEBUG_MODE` (D9) - w trybie DEBUG węzeł ma dodatkowe opcje, co przesuwa indeksy widoczne w scenariuszach testowych (`tests/scenarios.json` -> `Hammer Dialog Flow`).

## ⛓️ Constraints

- Dual-target desktop + web.
- Nie zepsuć istniejącej hybrydy sterowania D4 (kursor + Enter, 1-9, mysz).
- Type hints wymagane (mypy).

## 🪜 Plan / Subtasks

- [x] Dodać przewijanie/scroll-offset listy opcji tak, aby zaznaczona pozycja była zawsze w viewporcie panelu (`_layout_options` + `_draw_scroll_hints`).
- [x] Zweryfikować, że `activate_selected` zamyka rozmowę dla opcji spoza aktualnie widocznego zwoju - root-cause: `game_ui` ignorował zwrot `handle_event` przy klawiszach `1-9`/myszy; naprawiono centralnym `consume_close`.
- [x] Ustalić spójne indeksowanie opcji z/bez opcji DEBUG (`self._options` - jedna lista).
- [x] Rozszerzyć/odblokować krok "reach is_final -> dialog_closed" w scenariuszu `Hammer Dialog Flow`.
- [x] Dodatkowo (finding z review): naprawić overflow opcji (nie mieściły się w panelu) - font 14 + dynamiczna wysokość tekstu + rezerwa kolumny wag.

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione
- [x] zmiany udokumentowa w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [x] Testy / lint przechodzą (jeśli dotyczy) - 8 zestawów testów dialog/save-load PASS; mypy `dialog.py`/`game_ui.py` bez nowych błędów
- [x] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane - nie dotyczy (fix UI, bez nowych konwencji)
- [x] commit zmian wykonany

### Dowód działania

Test wizualny `Hammer Dialog Flow` po fixie - **wszystkie 3 asercje ss-review PASS** (gemini-3.1-flash-lite).

Hub 001: wszystkie 6 opcji mieści się w ramce, każda z wskaźnikiem wagi w osobnej kolumnie, `▼` sygnalizuje opcje DEBUG poza oknem:

![[agent_20260706_T-037_options_fit.png]]

Po wyborze opcji finalnej (`item_6` -> węzeł 990 `is_final`) panel **zamyka się** i wraca rozgrywka:

![[agent_20260706_T-037_closed_on_final.png]]

## 📓 Agent Log

- 2026-07-06 17:1x cc: utworzony podczas review epica DS (finding z T-033). Repro i wskazówki do kodu opisane w Context.
- 2026-07-06 17:40 cc: claimed, starting
- 2026-07-06 17:53 cc: Naprawiono w `dialog.py` + `game_ui.py`. Dźwignie overflow: font opcji 18->14, dynamiczna wysokość tekstu węzła (mierzona z `RichText.content_surface`, zamiast sztywnych 55%), rezerwa kolumny wag (`_WEIGHT_COL`), przewijanie viewportu (`_layout_options`, `_scroll_offset`, `_visible_count`) + wskaźniki `▲/▼`. Root-cause niezamykania: `game_ui` ignorował zwrot `handle_event` dla klawiszy `1-9`/myszy - dodano flagę `DialogPanel._pending_close` + `consume_close()` i jedno centralne domknięcie w `game_ui.update` (działa dla accept/talk/1-9/mysz). Zunifikowano źródło opcji (`self._options`). Weryfikacja wizualna: hub 6 opcji mieści się, zamknięcie na `is_final` działa - 3/3 ss-review PASS.
- 2026-07-06 17:56 cc: Fix overflow opcji (font 14 + dynamiczna wysokosc tekstu + rezerwa kolumny wag + przewijanie) oraz zamykanie na is_final (flaga _pending_close + centralne domkniecie w game_ui, dziala dla 1-9/myszy). Weryfikacja wizualna: 3/3 ss-review PASS. Test: just test 'Hammer Dialog Flow'.

## 🙋 Needs-You / Questions
