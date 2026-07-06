---
id: T-037
title: DialogPanel nie zamyka rozmowy przy opcji finalnej poza widocznym zwojem listy
status: ready
owner: ai
priority: p2
type: bug
agent:
created: 2026-07-06
updated: 2026-07-06
tags:
  - task
---

# T-037 - DialogPanel nie zamyka rozmowy przy opcji finalnej poza widocznym zwojem listy

## 🎯 Goal / Outcome

- [ ] Wybór opcji prowadzącej do węzła `is_final` zamyka panel rozmowy niezależnie od tego, czy opcja jest w widocznej części listy, czy poniżej zwoju
- [ ] Lista opcji przewija się tak, aby zaznaczona kursorem opcja była zawsze widoczna (kursor gora/dol nie "gubi" się poza panelem)
- [ ] Indeksowanie opcji jest spójne przy włączonym `IS_DEBUG_MODE` (wstrzyknięte opcje DEBUG nie rozjeżdżają numeracji `1-9` ani wyboru kursorem)

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

- [ ] Dodać przewijanie/scroll-offset listy opcji tak, aby zaznaczona pozycja była zawsze w viewporcie panelu.
- [ ] Zweryfikować, że `activate_selected` zamyka rozmowę dla opcji spoza aktualnie widocznego zwoju (bug reprodukowany na węźle 001 Hammera).
- [ ] Ustalić spójne indeksowanie opcji z/bez opcji DEBUG (numeracja 1-9 i wybór kursorem odnoszą się do tej samej listy).
- [ ] Rozszerzyć/odblokować krok "reach is_final -> dialog_closed" w scenariuszu `Hammer Dialog Flow`.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

- 2026-07-06 17:1x cc: utworzony podczas review epica DS (finding z T-033). Repro i wskazówki do kodu opisane w Context.

## 🙋 Needs-You / Questions
