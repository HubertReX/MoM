---
id: T-042
title: DS: oznaczanie odwiedzonych linii dialogowych (nowe bold, odwiedzone bez bold)
status: needs-you
owner: human
priority: p3
type: feature
agent: opencode
created: 2026-07-06
updated: 2026-07-06
tags:
  - task
state: review
---
# T-042 - DS: wizualne oznaczanie odwiedzonych linii dialogowych

## 🎯 Goal / Outcome

- [ ] Opcje wcześniej wybrane przez gracza są wizualnie odróżnione od nieodwiedzonych (np. nowe = pogrubione / jaśniejsze, odwiedzone = zwykłe / przygaszone, albo inne tło)
- [ ] Stan "odwiedzona" utrzymuje się między otwarciami rozmowy i po save/load (korzysta z istniejącego `selected_options_dict` / `opt.selected`)
- [ ] Oznaczenie działa dla wszystkich ścieżek wyboru (kursor, 1-9, mysz)

## 🧭 Context

- **Kontekst wspólny:** [[DS-epic-brief]] (D5 - pełny stan rozmowy per-NPC zawiera `selected_options_dict`, `selected`, `visited`).
- Zgłoszone przez użytkownika: "raz wykorzystane linie dialogowe powinny być jakoś oznaczone (nowe bold, odwiedzone bez bold, albo inne tło)".
- Stan już istnieje: `project/ui/panels/dialog.py::activate_selected()` (linie ~278-281) ustawia `opt.selected = True` i `self.npc.selected_options_dict[opt.key] = True`. Persystencja stanu rozmowy dowieziona w [[T-030 DS: Persystencja stanu rozmowy w save-load (oba backendy + testy korupcji)]].
- Render opcji: `_refresh_options()` buduje etykiety; tu trzeba dołożyć wariant stylu wg `opt.selected` (lub obecności klucza w `selected_options_dict`).
- Powiązane: [[T-038 DS bug: opcje dialogu renderowane plain fontem - znaczniki italic i kolory literalnie]] (jeśli opcje przejdą na RichText, styl odwiedzenia najłatwiej zrobić tagiem/kolorem tam).

## ⛓️ Constraints

- Dual-target desktop + web.
- Nie kolidować z podświetleniem aktualnie zaznaczonej opcji (kursor) ani z kolumną wag.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [x] **Wizualizacja (zdecydowane - opcja B):** odwiedzone opcje **przygaszone** (niższa alpha = 100/255), nowe w pełnej jasności. Bez zmiany grubości fontu (layoutowo stabilne) i bez zmiany tła (brak kolizji z boxem kursora).
- [x] W `_refresh_options()` odczytać `opt.selected` i zastosować `surf.set_alpha(_VISITED_ALPHA)` dla odwiedzonych.
- [x] Zweryfikować utrzymanie po save/load i po ponownym wejściu w dialog - `restore_dialog_state()` (characters.py:370-373) przywraca `opt.selected` z `selected_options_dict` dla każdej opcji.
- [x] Test wizualny: wejść, wybrać kilka opcji (001→002→007→001), wrócić do huba - odwiedzone wyróżnione.

## ✅ Definition of Done

- [x] Kryteria z Goal spełnione - odwiedzone opcje są przygaszone (alpha 100/255), nowe w pełnej jasności
- [x] zmiany udokumentowane w tasku (`moab log`)
- [x] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcie potwierdzające prawidłowe działanie
- [x] Testy / lint przechodzą (mypy, isort clean)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane (nie dotyczy - zmiana lokalna w `dialog.py`)
- [x] commit zmian wykonany (`0d1b29b`)

![[agent_20260707_T-042_dimmed_option.png]]

## 📓 Agent Log

- 2026-07-06 cc (review): utworzony na życzenie użytkownika. Stan `selected`/`selected_options_dict` już istnieje - brakuje tylko wizualizacji w panelu.
- 2026-07-07 decyzja (autor): **opcja B** - odwiedzone przygaszone (kolor/alpha), nowe pełna jasność. Bez bold (layout) i bez tła (kolizja z kursorem).
- 2026-07-07 opencode: implementacja - dodano stałą `_VISITED_ALPHA = 100` i warunek `if opt.selected: surf.set_alpha(_VISITED_ALPHA)` w `_refresh_options()`. Test Hammer Dialog Flow (przechodzi), test wizualny (flow 001→002→007→001) potwierdza przygaszenie opcji 1 na hubie. Screenshot: [[agent_20260707_T-042_dimmed_option.png|hub z przygaszoną opcją 1]].
- 2026-07-07 17:39 opencode: claimed, starting
- 2026-07-07 17:48 opencode: implementacja: dodano _VISITED_ALPHA=100 i set_alpha() dla opt.selected w _refresh_options(). Hammer Dialog Flow przechodzi. Test wizualny potwierdza dzialanie - screenshot w _attachments.
- 2026-07-07 17:49 opencode: Zrealizowano: dodano _VISITED_ALPHA=100 i surf.set_alpha() dla opt.selected w _refresh_options(). Hammer Dialog Flow przechodzi. Test wizualny: dialog nawigacja 001->002->007->001 - opcja 1 przygaszona po powrocie do huba. Screenshot w _attachments. mypy/isort clean.

## 🙋 Needs-You / Questions

- (brak - wszystko rozstrzygnięte)
