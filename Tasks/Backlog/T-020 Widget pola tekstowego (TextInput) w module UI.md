---
id: T-020
title: Widget pola tekstowego (TextInput) w module UI
status: in-progress
owner: ai
priority: p2
type: feature
agent: cc
created: 2026-07-05
updated: 2026-07-05
tags:
  - task
---

# T-020 — Widget pola tekstowego (TextInput) w module UI

Nowy widget `TextInput` w toolkicie UI (`project/ui/widgets/`) pozwalający graczowi wprowadzać tekst z klawiatury: fokus, kursor (caret), obsługa `KEYDOWN` / `TEXTINPUT`, backspace/delete, ruch kursora strzałkami, wklejanie. Widget ma być mocno konfigurowalny parametrami, żeby dało się go użyć do różnych celów (nazwa postaci, nazwa slotu zapisu, hasło, pole numeryczne itp.).

## 🎯 Goal / Outcome

- [ ] Widget `TextInput(Widget)` w `project/ui/widgets/text_input.py`, wyeksportowany w `project/ui/widgets/__init__.py`
- [ ] Renderuje wprowadzony tekst czcionką pixel-art (`MAIN_FONT`) z migającym kursorem, spójny wizualnie z `Label` / `Button` (drop shadow / outline, `theme.get_font`)
- [ ] Fokus: klik myszą ustawia fokus; widget przechwytuje zdarzenia klawiatury tylko gdy ma fokus (zwraca `True` z `handle_event`, żeby nie przeciekały dalej)
- [ ] **Maksymalna długość** (`max_length: int | None`) - po jej osiągnięciu kolejne znaki są ignorowane
- [ ] **Klasy dopuszczalnych znaków** (`charset`) - min. warianty: `ANY`, `ALPHANUMERIC`, `DIGITS` (tylko cyfry), `LATIN` (tylko litery alfabetu łacińskiego, bez znaków diakrytycznych - patrz Constraints), opcjonalnie `ALPHA`; znaki spoza klasy są odrzucane przy wpisywaniu
- [ ] **Tryb hasła** (`password: bool`) - wpisane znaki wyświetlane jako maska (np. `*` / `•`), a `value` nadal zwraca prawdziwy tekst
- [ ] **Ograniczenie do liter łacińskich** jako oddzielna, jawna opcja (bo obecna czcionka pixel-art nie ma glifów spoza łacińskiego) - patrz Constraints
- [ ] `value` (getter zwracający aktualny tekst) + callbacki `on_change` i `on_submit` (Enter)
- [ ] Placeholder (`placeholder: str`) wyświetlany przygaszonym kolorem, gdy pole puste i bez fokusu
- [ ] Działa na desktop (`./run.sh`) i web (`./serve_web.sh`, pygbag)

## 🧭 Context

- Własny toolkit UI: `project/ui/` - retained-mode, czysty pygame-ce. Bazowa klasa: `project/ui/widget.py` (`Widget`: `rect`, `handle_event` → `_on_event`, `render`, `mark_dirty`, `update(dt)`, drzewo `children`)
- Istniejące widgety do naśladowania (wzór stylu i API): `project/ui/widgets/label.py`, `button.py`, `image.py`, `rich_text.py`; eksport w `project/ui/widgets/__init__.py`
- **Czcionka i rozmiary:** `project/settings.py:469-483` - aktywna czcionka to `font_pixel` (`MAIN_FONT = FONTS_PATH/"font_pixel.ttf"`), rozmiary `FONT_SIZE_TINY/SMALL/MEDIUM/LARGE/HUGE`. Fonty pobierać przez `project/ui/theme.py:get_font(size, font_path=..., bold=, italic=)`; kolory z `theme` (`TEXT`, `NAME`, `PANEL_BG_COLOR`)
- **Obsługa zdarzeń:** `Button._on_event` (`button.py:81`) pokazuje wzór myszy (`MOUSEMOTION` / `MOUSEBUTTONDOWN`). Dla tekstu potrzebne dodatkowo `pygame.KEYDOWN` (sterowanie: backspace, delete, strzałki, home/end, enter, ctrl+v) oraz `pygame.TEXTINPUT` (właściwe znaki - obsługuje IME/układy klawiatury lepiej niż `event.unicode`)
- Panele używające widgetów: `project/ui/panels/` (np. `main_menu.py`, `save_load.py`, `modal.py`) - to potencjalni konsumenci `TextInput` (nazwa postaci, nazwa slotu). Nie trzeba ich teraz podłączać, ale API ma to umożliwiać
- `GameUI` / manager: `project/ui/game_ui.py`, `project/ui/manager.py` - kontroler paneli (kontekst, jak widgety trafiają na ekran)
- **Testy agentowe:** `tests/automate_display_test.py` (runner desktop + web) czyta deklaratywne scenariusze z `tests/scenarios.json` (`name` + lista `actions` z `commands` typu `down`/`accept`/`screenshot`). Komendy agenta obsługuje `project/agent_ctrl.py` (`MOM_AGENT_CONTROL=1`, wejście przez `agent_input.txt` / localStorage na web). Obecnie **brak komendy „wpisz tekst"** - żeby przetestować `TextInput`, trzeba dodać komendę wprowadzania znaków (np. `type:<tekst>`) do `agent_ctrl.py`, tak by scenariusz mógł wpisać wartość do pola

## ⛓️ Constraints

- **Nie twórz nowego toolkitu** - rozszerz istniejący: `TextInput` dziedziczy po `Widget`, korzysta z `theme.get_font`, stałych z `settings.py`, wzoruje się na `Label`/`Button`
- **Web (pygbag):** musi działać. Preferuj `pygame.TEXTINPUT` + `pygame.key.start_text_input()` zamiast dłubania w `event.unicode`; sprawdź czy pygbag emituje `TEXTINPUT` - jeśli nie, fallback na `KEYDOWN.unicode`
- **Czcionka pixel-art (`font_pixel.ttf`) obsługuje tylko alfabet łaciński** (bez polskich znaków diakrytycznych i innych glifów Unicode). Dlatego:
  - filtr `LATIN` musi ograniczać do `A-Z a-z` (opcjonalnie spacja / myślnik dla nazw), odrzucając `ą ę ł …` oraz cyrylicę itp.
  - warto **zweryfikować faktyczny zakres glifów** czcionki przed implementacją (np. `pygame.font.Font(...).metrics()` zwraca `None` dla brakujących glifów) i oprzeć na tym walidację / wybór znaku maski hasła
- Klasy znaków jako `enum` (spójnie z konwencją `project/enums.py`) albo prosty typ w module widgetu - do decyzji autora, ale ma być rozszerzalne (łatwo dołożyć nową klasę / własne `predicate`)
- Wszystkie stałe kolory/rozmiary z `theme.py` / `settings.py` - żadnych hardcodowanych magicznych wartości niespójnych z resztą UI
- Trzymaj się reguł formatowania z `project/AGENTS.md` (styl kodu, mypy)

## 🪜 Plan / Subtasks

- [ ] Sprawdź zakres glifów `font_pixel.ttf` (które znaki ma / nie ma) - ustala realny zakres filtra `LATIN` i znak maski hasła
- [ ] Zdefiniuj klasy znaków (`CharSet`: `ANY`, `ALPHANUMERIC`, `ALPHA`, `LATIN`, `DIGITS`) + mapowanie na funkcję walidującą pojedynczy znak
- [ ] Zaimplementuj `TextInput(Widget)` w `project/ui/widgets/text_input.py`:
  - [ ] konstruktor z parametrami: `max_length`, `charset`, `password`, `placeholder`, `size`, `color`, `font_path`, `width`, `anchor`, `on_change`, `on_submit`
  - [ ] stan: `_text`, `_caret` (pozycja), `_focused`
  - [ ] `render()` - tło/ramka + tekst (lub maska hasła, lub placeholder) + migający kursor
  - [ ] `_on_event()` - fokus (klik), `TEXTINPUT` (wstaw znak z walidacją charset + max_length), `KEYDOWN` (backspace/delete/strzałki/home/end/enter→`on_submit`/ctrl+v)
  - [ ] `update(dt)` - miganie kursora (timer)
  - [ ] `value` getter + `set_text()` / `clear()`
- [ ] Eksportuj `TextInput` (i `CharSet`) w `project/ui/widgets/__init__.py`
- [ ] Mini-demo / panel testowy pokazujący pola: zwykłe, tylko cyfry, hasło, tylko łacińskie (do manualnej weryfikacji; może być tymczasowy panel lub wpięcie w istniejący)
- [ ] **Scenariusz testów agentowych:** dodaj komendę wprowadzania tekstu do `project/agent_ctrl.py` (np. `type:<tekst>`) i nowy scenariusz w `tests/scenarios.json` (np. „TextInput Basic") - fokus pola, wpisanie tekstu, weryfikacja filtra (odrzucenie znaku spoza klasy), backspace, maska hasła; screenshoty w punktach kontrolnych. Ma przechodzić na desktop i web przez `tests/automate_display_test.py`
- [ ] mypy bez nowych błędów; sprawdź desktop i web

## ✅ Definition of Done

- [ ] `TextInput` renderuje się i przyjmuje tekst z klawiatury (fokus po kliknięciu, migający kursor)
- [ ] `max_length` blokuje wpisywanie po przekroczeniu limitu
- [ ] Filtry `DIGITS` (tylko cyfry), `ALPHANUMERIC`, `LATIN` (tylko litery łacińskie) działają - znaki spoza klasy są odrzucane
- [ ] Tryb `password` maskuje wyświetlane znaki, a `value` zwraca prawdziwy tekst
- [ ] Backspace / delete / strzałki / home / end / enter (`on_submit`) działają
- [ ] Placeholder widoczny przy pustym polu bez fokusu
- [ ] Scenariusz testów agentowych dla `TextInput` w `tests/scenarios.json` przechodzi na desktop i web (`tests/automate_display_test.py`), z komendą wpisywania tekstu w `agent_ctrl.py`
- [ ] Działa na desktop (`./run.sh`) i web (`./serve_web.sh`)
- [ ] mypy nie zgłasza nowych błędów
- [ ] zmiany udokumentowane w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcie potwierdzające prawidłowe działanie (np. panel z kilkoma polami: cyfry, hasło, łacińskie)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

- 2026-07-05 07:10 cc: claimed, starting

## 🙋 Needs-You / Questions


