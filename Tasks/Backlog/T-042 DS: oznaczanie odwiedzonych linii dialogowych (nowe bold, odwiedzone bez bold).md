---
id: T-042
title: DS: oznaczanie odwiedzonych linii dialogowych (nowe bold, odwiedzone bez bold)
status: backlog
owner: human
priority: p3
type: feature
agent:
created: 2026-07-06
updated: 2026-07-06
tags:
  - task
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

- [ ] **Wizualizacja (zdecydowane - opcja B):** odwiedzone opcje **przygaszone** (przyciemniony kolor / niższa alpha), nowe w pełnej jasności. Bez zmiany grubości fontu (layoutowo stabilne, nie rusza wyjustowania z [[T-039 DS bug: wskaznik opcji pokazuje generyczna ikone zamiast emotki sentymentu z pliku MD]]) i bez zmiany tła (kolizja z boxem kursora).
- [ ] W `_refresh_options`/`draw` odczytać `opt.selected` (lub `npc.selected_options_dict`) i zastosować przygaszenie (kolor/alpha) dla odwiedzonych.
- [ ] Zweryfikować utrzymanie po save/load i po ponownym wejściu w dialog.
- [ ] Test wizualny: wejść, wybrać kilka opcji, wrócić do huba - odwiedzone wyróżnione.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

- 2026-07-06 cc (review): utworzony na życzenie użytkownika. Stan `selected`/`selected_options_dict` już istnieje - brakuje tylko wizualizacji w panelu.
- 2026-07-07 decyzja (autor): **opcja B** - odwiedzone przygaszone (kolor/alpha), nowe pełna jasność. Bez bold (layout) i bez tła (kolizja z kursorem).

## 🙋 Needs-You / Questions

- (brak - wszystko rozstrzygnięte)
