---
id: T-008
title: Save-load test scenarios — agent tests for save, load, corrupt data, edge cases
status: ready
owner: ai
priority: p2
type: feature
agent:
created: 2026-06-28
updated: 2026-06-28
tags:
  - task
---

# T-008 — Save-load test scenarios — agent tests for save, load, corrupt data, edge cases

## 🎯 Goal / Outcome

Scenariusze testowe dla systemu save/load, odpalane przez istniejący framework agent testing (`tests/scenarios.json` + `tests/automate_display_test.py`). Pokrycie:

1. **Save basic** — zapis gry na różnych mapach (Village, Maze, Inn), zweryfikuj że plik/klucz localStorage istnieje
2. **Load basic** — wczytaj zapis, zweryfikuj pozycję gracza, health, money, inventory (przez zrzut ekranu lub debug settings)
3. **Quick save/load** — F5 (quick save) → zmiana mapy → F9 (quick load) → wróć do poprzedniej mapy
4. **Save overwrite** — zapisz w slocie 1 → zmień stan gry → zapisz ponownie w slocie 1 (confirm overwrite) → wczytaj → zweryfikuj że to drugi stan
5. **Death → Load** — gracz umiera → wybierz "Load last save" → gra wraca do stanu sprzed śmierci
6. **Auto-save on map change** — zmień mapę → sprawdź że auto-save istnieje
7. **Corrupt save handling** — ręcznie zepsuj plik save'a (wstaw nie-JSON lub złą wersję) → próba loadu → gra nie crashuje, pokazuje błąd
8. **Empty slot load** — próba wczytania pustego slota → gra nie crashuje, pokazuje info
9. **Multi-slot** — zapisz w 3 różnych slotach → wczytaj każdy → zweryfikuj że stany są różne
10. **UI flow** — otwórz SavePanel → wybierz slot → overwrite confirm → notyfikacja "Game saved" → otwórz LoadPanel → wybierz slot → load confirm → gra wczytana

Wykorzystaj istniejący `agent_ctrl.py` do symulacji klawiszy i `screenshot` do weryfikacji wizualnej.

## 🧭 Context

- T-005, T-006, T-007 są prerequisite (system musi działać, żeby testować)
- Istniejący framework testowy: `tests/scenarios.json`, `tests/automate_display_test.py` — komendy przez `agent_input.txt`, zrzuty ekranu do `screenshots/agent/`
- Agent uruchamia grę z `MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy ./run.sh` (desktop, headless-ish)
- `agent_ctrl.py` — symulacja klawiszy, screenshot, exit
- `project/agent_ctrl.py` — dokumentacja komend: `up`, `down`, `accept`, `screenshot`, `exit`
- Wzór istniejących testów: `tests/scenarios.json` zawiera listy `TestAction` z nazwą akcji, komendą i pauzą
- Do testów save/load potrzebne będą też bezpośrednie operacje na plikach save (dla corrupt-data test) — można je dodać jako osobny skrypt

## ⛓️ Constraints

- **DEPENDENCY:** Wymaga ukończonych T-005, T-006 i T-007 — testuje działający system save/load z UI, hotkeys i auto-save
- Testy działają TYLKO na desktopie (`SDL_VIDEODRIVER=dummy`). Save/load na web można testować tylko w przeglądarce (poza zakresem tego taska)
- Scenariusze muszą być deterministyczne — pauzy (`TRANSITION_WAIT`) między akcjami
- Do weryfikacji stanu gry: użyj `screenshot` (wizualnie) + debug settings przez `agent_ctrl.py debug_settings` (jeśli istnieje) lub `print` do logów
- Test corrupt-data: skrypt Python, który przed uruchomieniem gry podmienia plik save na zepsuty JSON
- Nie psuj istniejących testów — dodaj nowe scenariusze obok starych
- Nie testuj na web — tylko desktop (`SDL_VIDEODRIVER=dummy`)

## 🪜 Plan / Subtasks

- [ ] Przeczytaj istniejące testy: `tests/scenarios.json` i `tests/automate_display_test.py` — zrozum format
- [ ] Dodaj nowe scenariusze w `tests/scenarios.json`:
  - [ ] `Save and Load Basic` — wejdź w menu → Save → slot 1 → ok → zmień mapę → Load → slot 1 → screenshot
  - [ ] `Quick Save and Load` — F5 → zmiana mapy → F9 → screenshot (ta sama pozycja?)
  - [ ] `Death then Load` — idź do walki → giń → "Load last save" → screenshot
  - [ ] `Save Overwrite` — save slot 1 → pickup item → save slot 1 (overwrite) → load → sprawdź item w inventory (przez trade/drop)
  - [ ] `Auto-save` — zmień mapę → sprawdź że plik auto-save istnieje (assert przez skrypt zewnętrzny)
  - [ ] `Corrupt Save` — skrypt podmienia save na `{"corrupt": true}` → próba loadu → screenshot z komunikatem błędu (nie crash)
  - [ ] `Empty Slot Load` — otwórz LoadPanel → wybierz pusty slot → screenshot z info (nie crash)
- [ ] Stwórz `tests/test_save_load_corrupt.py` — helper do symulowania corrupt save (przed uruchomieniem gry podmienia plik)
- [ ] Zweryfikuj że wszystkie scenariusze przechodzą:
  ```bash
  python3 tests/automate_display_test.py "Save and Load Basic"
  python3 tests/automate_display_test.py "Quick Save and Load"
  # ... etc
  ```
- [ ] Dokumentacja: krótka instrukcja w `tests/README.md` (lub w komentarzu w `scenarios.json`) jak odpalić testy save/load

## ✅ Definition of Done

- [ ] Minimum 5 scenariuszy save/load w `tests/scenarios.json`
- [ ] Każdy scenariusz można odpalić przez `python3 tests/automate_display_test.py "Nazwa Scenariusza"`
- [ ] Scenariusze przechodzą (gra nie crashuje, zrzuty ekranu wyglądają sensownie)
- [ ] Corrupt save test: gra nie crashuje, pokazuje komunikat
- [ ] Empty slot test: gra nie crashuje, pokazuje informację
- [ ] Scenariusze są deterministyczne (takie same pauzy, sekwencje klawiszy)
- [ ] Wszystkie zrzuty ekranu lądują w `screenshots/agent/` z opisowymi nazwami

## 📓 Agent Log

## 🙋 Needs-You / Questions
