---
id: T-021
title: Panel zarządzania slotami zapisu w menu głównym (edycja nazwy, usuwanie)
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

# T-021 — Panel zarządzania slotami zapisu w menu głównym (edycja nazwy, usuwanie)

**Rozszerzenie istniejącego `LoadPanel`** (`project/ui/panels/save_load.py`) o zarządzanie slotami z zapisaną grą: **zmiana nazwy** slotu (z użyciem widgetu `TextInput` z T-020) oraz **usuwanie** slotu z potwierdzeniem. Nie tworzymy osobnego panelu - dokładamy akcje do panelu, który już wyświetla listę slotów. To jednocześnie pierwszy realny konsument `TextInput` - służy jako test integracyjny tego widgetu w prawdziwym UI. Przy okazji popraw błąd polegający na tym, że po wczytaniu gry z LoadPanel, gra prawidłowo się wznawia, ale naciśnięcie Esc zamiast pokazać MainMenu wychodzi z gry.

## 🎯 Goal / Outcome

- [ ] `LoadPanel` (`save_load.py`) rozszerzony o akcje na zaznaczonym slocie: „Rename" i „Delete" (np. dodatkowe klawisze/przyciski przy zaznaczonym slocie). Dostępne tam, gdzie `LoadPanel` już działa - w tym w menu głównym
- [ ] **Edycja nazwy** zaznaczonego slotu: pole `TextInput` (z T-020) prefill aktualną nazwą, limit **20 znaków**, dozwolone **litery łacińskie, cyfry i spacje**; zapis nowej nazwy do metadanych slotu
- [ ] **Usuwanie** zaznaczonego slotu z modalem potwierdzenia („Na pewno usunąć zapis? Tej operacji nie można cofnąć") - Yes/No, wzór `modal.py`
- [ ] **Sanityzacja nazwy przy zapisie** (patrz Constraints) - nazwa jest normalizowana zanim trafi do pliku save (JSON), niezależnie od filtra w UI
- [ ] Zmiany (nazwa/usunięcie) od razu widoczne na liście i trwałe (desktop: plik na dysku, web: localStorage)
- [ ] Anulowanie edycji nazwy (Esc) nie zmienia zapisanej nazwy
- [ ] Działa na desktop (`./run.sh`) i web (`./serve_web.sh`)

## 🧭 Context

- **Silnik save/load już to wspiera częściowo:**
  - `project/save_load/backends.py` - każdy backend ma `delete_slot(slot_idx)` (desktop plikowy + web localStorage). Usuwanie jest gotowe na poziomie backendu
  - `project/save_load/manager.py:95` - `SaveManager.delete_slot(slot_idx)` (publiczne API)
  - `project/save_load/manager.py:55` - `SaveManager.save(slot_idx, slot_name="")` przyjmuje nazwę slotu
  - `project/save_load/models.py:77` - `SaveMetadata.slot_name: str` - pole nazwy już istnieje w modelu
  - `SaveManager.list_slots()` → `list[SaveSlotInfo | None]` - dane do wyświetlenia listy
  - **Brakuje** metody „rename" (zmiana samej nazwy bez ponownego zapisu całego stanu) - trzeba dodać np. `SaveManager.rename_slot(slot_idx, new_name)` (odczyt slotu → podmiana `metadata.slot_name` → zapis), albo cienką operację na backendzie
- **Panel do rozszerzenia:** `project/ui/panels/save_load.py` (`LoadPanel` / `SaveLoadPanel`) - layout listy slotów, nawigacja, klik. Tu dokładamy akcje Rename/Delete na zaznaczonym slocie
- **UI menu głównego:** `project/ui/panels/main_menu.py` - `LoadMenuScreen` + proxy (`_LoadUIManagerProxy`, `_LoadSceneProxy`) pokazują, jak `LoadPanel` działa w menu bez realnej sceny. Rozszerzony `LoadPanel` automatycznie dostanie nowe akcje w tym kontekście - zweryfikuj, że proxy obsłużą modal usunięcia i `TextInput`
- **Modal potwierdzenia:** `project/ui/panels/modal.py` - dialog Yes/No z callbackami (do potwierdzenia usunięcia)
- **Sanityzacja/serializacja save:** plik zapisu to JSON - patrz `project/save_load/models.py` (`to_dict`/`from_dict`, `SaveMetadata.slot_name`) i ścieżka zapisu w `backends.py` (`write_slot`). Normalizację nazwy najlepiej umieścić przy ustawianiu `slot_name` (w `rename_slot` / `save`), żeby żaden przepływ jej nie ominął

## ⛓️ Constraints

- **DEPENDENCY: wymaga widgetu `TextInput` z [[T-020 Widget pola tekstowego (TextInput) w module UI]].** Edycja nazwy slotu korzysta z `TextInput` (fokus, `max_length=20`, znaki: litery łacińskie + cyfry + spacja). Ten task zaczynać dopiero po ukończeniu (lub przynajmniej dostępności `TextInput` w `project/ui/widgets/`). To jednocześnie pierwszy realny test integracyjny `TextInput`
- **Rozszerz `LoadPanel`, nie twórz nowego panelu.** Użyj istniejących komponentów: `Widget`, `LoadPanel`/`SaveLoadPanel`, `Modal`, `TextInput`
- **Nazwa slotu:** maks. **20 znaków**, dozwolone **litery łacińskie, cyfry i spacje**. W `TextInput` może to wymagać charsetu „litery+cyfry+spacja" (w T-020 przewidziano rozszerzalny charset / własny predicate - użyj go, nie dokładaj diakrytyków)
- **Sanityzacja nazwy przy zapisie (obrona w głąb, wymóg na przyszłość):** niezależnie od filtra w UI, przy zapisie nazwy do metadanych (`rename_slot` / `save`, ustawienie `SaveMetadata.slot_name`) nazwa musi być **znormalizowana**, tak by nigdy nie zepsuła formatu pliku save (JSON) ani layoutu:
  - przytnij do 20 znaków (`[:20]`)
  - usuń znaki sterujące / niedrukowalne oraz znaki nowej linii i tabulacje (`\n`, `\r`, `\t`), `strip()` białych znaków z brzegów
  - serializacja przez `json.dumps` (już używana) escapuje cudzysłowy/backslashe - **nie** buduj JSON ręcznie ze sklejania stringów
  - dzięki temu ewentualne późniejsze rozszerzenie listy dopuszczalnych znaków w UI nie może uszkodzić pliku save - sanityzacja przy zapisie jest ostatnią linią obrony
- **Nie duplikuj logiki save/load** - operacje na slotach wyłącznie przez `SaveManager` (`delete_slot`, nowa `rename_slot`), nie grzeb bezpośrednio w plikach/localStorage z poziomu UI
- **Web (pygbag):** usuwanie i zmiana nazwy muszą działać także na backendzie localStorage
- Trzymaj się reguł z `project/AGENTS.md` (styl, mypy)

## 🪜 Plan / Subtasks

- [ ] Dodaj funkcję sanityzacji nazwy slotu (przytnij do 20, usuń znaki sterujące/nowe linie/tab, `strip()`) i wywołaj ją przy każdym ustawieniu `slot_name`
- [ ] Dodaj `SaveManager.rename_slot(slot_idx, new_name)` (odczyt → sanityzacja → zmiana `metadata.slot_name` → zapis); zastosuj tę samą sanityzację w `save(slot_idx, slot_name=...)`
- [ ] Rozszerz `LoadPanel`/`SaveLoadPanel` (`save_load.py`) o akcje „Rename" / „Delete" na zaznaczonym slocie (klawisze/przyciski)
- [ ] Zweryfikuj, że rozszerzony `LoadPanel` działa w menu głównym (`LoadMenuScreen` + proxy) - modal usunięcia i `TextInput` obsłużone także tam
- [ ] Edycja nazwy: otwarcie `TextInput` (prefill aktualną nazwą, `max_length=20`, litery łacińskie + cyfry + spacja), zatwierdzenie (Enter) → `rename_slot`, Esc → anuluj
- [ ] Usuwanie: `Modal` Yes/No → `delete_slot` → odświeżenie listy
- [ ] Odświeżanie listy po każdej operacji (nazwa/usunięcie)
- [ ] Scenariusz testów agentowych w `tests/scenarios.json` (np. „Manage Saves"): wejście do `LoadPanel`, zmiana nazwy slotu (użycie komendy wpisywania tekstu dodanej w T-020), usunięcie slotu z potwierdzeniem; screenshoty w punktach kontrolnych; desktop + web
- [ ] Test/asercja sanityzacji: nazwa z niedozwolonym znakiem / za długa / ze znakiem sterującym zapisuje się jako poprawny JSON, plik nadal się wczytuje (rozważ dołożenie do `tests/test_save_load_*.py`)
- [ ] mypy bez nowych błędów; sprawdź desktop i web

## ✅ Definition of Done

- [ ] Rozszerzony `LoadPanel` ma akcje „Rename" i „Delete" na zaznaczonym slocie (działają też w menu głównym)
- [ ] Zmiana nazwy slotu przez `TextInput` (maks. 20 znaków, litery łacińskie + cyfry + spacja) działa i jest trwała (desktop + web)
- [ ] Usuwanie slotu z potwierdzeniem działa i jest trwałe (desktop + web)
- [ ] Sanityzacja nazwy przy zapisie: nawet nazwa ze znakami sterującymi / za długa nie psuje pliku save (JSON), plik nadal się wczytuje
- [ ] Anulowanie edycji nazwy (Esc) nie zmienia zapisu; puste sloty nie mają akcji rename/delete
- [ ] Lista odświeża się po każdej operacji
- [ ] Scenariusz testów agentowych „Manage Saves" przechodzi na desktop i web (`tests/automate_display_test.py`)
- [ ] mypy nie zgłasza nowych błędów
- [ ] zmiany udokumentowane w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcie potwierdzające prawidłowe działanie (panel z edycją nazwy i/lub potwierdzeniem usunięcia)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

- 2026-07-05 07:57 cc: claimed, starting

## 🙋 Needs-You / Questions

- Ustalone (2026-07-05): nazwa slotu maks. 20 znaków; dozwolone litery łacińskie, cyfry i spacje. Sanityzacja przy zapisie jako obrona na wypadek przyszłego rozszerzenia listy znaków (patrz Constraints).

