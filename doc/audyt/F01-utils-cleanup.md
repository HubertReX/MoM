# F01 - cleanup `utils/`: zależności produkcyjne do `scripts/`, ignore w CodeGraph

Priorytet: **P1** (Faza 1). Rozmiar: S. Zależności: brak.

## Kontekst i problem

Katalog `utils/` to z założenia piaskownica eksperymentów (root `AGENTS.md`: "Śmietnik
skryptów/eksperymentów - pomijać"). W praktyce produkcja zależy od niego w 4 miejscach:

1. `utils/black.tmpl` - szablon pygbag używany przez: `justfile` (`serve-web`,
   `build-itchio`), `.github/workflows/pygbag.yml`, `.github/workflows/itch_io.yml`,
   `tests/automate_display_test.py:72` (web runner)
2. `utils/find_bad_png.py` - recepty `fix-bad-png` i `find-bad-png` w justfile
3. `utils/fix_bad_png.py` - wariant windows recepty `fix-bad-png`
4. CodeGraph indeksuje cały `utils/` - 197 z 352 plików indeksu to piaskownica
   (w tym `utils/zengl_examples/`), przez co eksploracja kodu przez agentów zwraca szum

Zasada docelowa (ustalona z autorem): wszystkie używane skrypty w `scripts/`.

## Kroki

1. Przenieś (git mv, zachowaj historię):
   - `utils/black.tmpl` → `scripts/pygbag/black.tmpl`
   - `utils/find_bad_png.py` → `scripts/find_bad_png.py`
   - `utils/fix_bad_png.py` → `scripts/fix_bad_png.py`
2. Zaktualizuj WSZYSTKIE referencje (wyszukaj `grep -rn "utils/black\|utils/find_bad\|utils\\\\fix_bad\|utils/fix_bad" justfile tests .github`):
   - `justfile`: `serve-web` (unix+windows), `build-itchio`, `fix-bad-png` (unix+windows),
     `find-bad-png`
   - `tests/automate_display_test.py` linia z `--template`
   - `.github/workflows/pygbag.yml` i `itch_io.yml` (parametr `--template`)
3. CodeGraph - wyklucz `utils/` z indeksu:
   - sprawdź, czy CodeGraph wspiera plik ignore (szukaj: `codegraph init --help`,
     `codegraph index --help`, dokumentacja `codegraph --help`; sprawdź też czy respektuje
     `.gitignore` i czy istnieje wsparcie np. `.codegraphignore`)
   - jeśli wsparcie istnieje: skonfiguruj ignorowanie `utils/`, `screenshots/`,
     `references/` i przebuduj indeks (`codegraph index`); potwierdź przez
     `codegraph files --filter utils` (ma zwrócić 0 plików)
   - jeśli wsparcia brak: NIE kombinuj (żadnych symlinków ani przenoszenia utils poza
     repo) - odnotuj w raporcie zadania "CodeGraph nie wspiera ignore - do zgłoszenia
     upstream" i zakończ ten krok
4. Root `AGENTS.md`: w tabeli "Co gdzie jest" przy `utils/` dopisz, że od teraz nic
   produkcyjnego nie może z niego korzystać (szablon pygbag i narzędzia PNG są w
   `scripts/`).

## Kryteria akceptacji

1. `rg -n "utils/" justfile tests/ .github/ scripts/ project/` nie zwraca żadnych
   referencji do plików w `utils/` (poza ewentualnymi komentarzami historycznymi).
2. `just serve-web` startuje i serwuje grę (przerwij po zobaczeniu "serving on ...";
   pełny boot web niepotrzebny).
3. `just build-itchio` buduje `build/web.zip` bez błędu o brakującym szablonie.
4. `just find-bad-png` działa (może zwrócić pustą listę - chodzi o brak błędu ścieżki).
5. Workflowy CI: zmiany w yml są spójne (uruchomić ich nie możesz - `workflow_dispatch`;
   sprawdź ścieżki dwukrotnie, literówka = zepsuty deploy).
6. `just test-unit` przechodzi.
7. Jeśli krok 3 się powiódł: `codegraph files --filter utils` zwraca 0 plików, a
   `codegraph explore "Scene update"` nie zwraca wyników z `utils/`.

## Pułapki

- W `justfile` są warianty `[unix]` i `[windows]` tych samych recept - zaktualizuj OBA.
- `black.tmpl` to szablon HTML pygbag - żadnych zmian treści, tylko przeniesienie.
- Nie usuwaj niczego innego z `utils/` - piaskownica zostaje nietknięta (decyzja autora).
- Nie dodawaj `utils/` do `.gitignore` - katalog jest wersjonowany celowo.

## Po zakończeniu

- odhacz F01 w `doc/audyt/audyt.md`
- commit: `F01: produkcyjne pliki z utils/ do scripts/ (pygbag template, narzędzia PNG)`
