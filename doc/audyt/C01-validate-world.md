# C01 - `just validate-world`: walidator spójności encji cross-source

Priorytet: **P0** (Faza 1). Rozmiar: M. Zależności: brak.

## Kontekst i problem

Klucze encji żyją w ośmiu przestrzeniach nazw (pełna tabela: rozdz. 5 raportu
`doc/_attachements/audyt-architektury-2026-07-25.html`): config.json, characters.csv,
frontmatter vaultu, mapy Tiled (name/model_name/places/waypoints), routines.toml,
klucze przedmiotów w warunkach DSL, sprite'y, locale. Walidację mają dziś tylko dialogi,
questy i locale. Mapy Tiled NIE są sprawdzane wcale: literówka w `model_name` obiektu
spawn, w nazwie miejsca w kolumnie `home` albo w nazwie rutyny = cichy `print` w runtime
albo brak NPC, wykrywane ręcznie podczas grania. Przy 10x większej liczbie map i postaci
to będzie stały koszt.

## Cel

Jeden skrypt `scripts/validate_world.py` + recepta `just validate-world`: czyta wszystkie
źródła, raportuje rozjazdy czytelną tabelą (rich), zwraca exit code != 0 przy błędach.
Bez naprawiania czegokolwiek - tylko diagnoza.

## Pliki do zmiany

- `scripts/validate_world.py` - nowy skrypt (jedyny plik z logiką)
- `justfile` - recepta `validate-world` (unix + windows, wzorzec: `validate-locale`)
- `AGENTS.md` (root) - wzmianka w sekcji narzędzi
- `.github/workflows/unit_tests.yml` - krok walidacji po testach (opcjonalnie, patrz krok 5)

## Krok 1: wczytanie źródeł (bez pygame!)

Skrypt NIE może importować pygame ani modułów gry wymagających SDL. Czytaj surowe pliki:

- `project/config_model/config.json` - `json.load`; sekcje characters, items, chests,
  maze_configs, dialogs, quests
- `project/config_model/characters.csv` (separator `;`) - kolumny key, sprite, home, work,
  social, hobby, routine, items
- `project/config_model/items.csv`, `chests.csv` - klucze
- `project/config_model/routines.toml` - `tomllib`; nazwy rutyn i kroki `at`
  (warianty `type:`, `location:`, `route:`)
- mapy `.tmx` - `xml.etree.ElementTree` (NIE pytmx - ciągnie pygame). Interesują tylko
  warstwy obiektów: `<objectgroup name="spawn_points|places|waypoints|entry_points">`;
  z obiektów czytaj `name` oraz property `model_name`
  (`<properties><property name="model_name" value="..."/>`). Listę map weź z katalogu
  `project/assets/NinjaAdventure/maps/*.tmx` + `project/assets/map/*.tmx`; pomiń
  `project/assets/MazeTileset/` (labirynty proceduralne) - zakoduj te ścieżki jako stałe
  z komentarzem.
- sprite'y: katalogi `project/assets/NinjaAdventure/Actor/Characters/<Sprite>/`
  (zweryfikuj dokładną ścieżkę w repo przed implementacją: `ls project/assets/NinjaAdventure`)

## Krok 2: reguły walidacji

Zaimplementuj jako listę funkcji `check_*` zwracających listę naruszeń
`(severity, source_file, message)`; severity: `ERROR` albo `WARN`.

1. ERROR `spawn.model_name` z mapy nie istnieje w `config.characters`
2. ERROR wartość `home/work/social/hobby` w characters.csv wskazuje miejsce
   (`mapa:miejsce` albo `miejsce`) nieistniejące w warstwie `places` żadnej mapy
   (format `Mapa:nazwa` = konkretna mapa; sama nazwa = dowolna mapa)
3. ERROR `routine` z characters.csv nie istnieje w routines.toml
4. ERROR krok rutyny `at = "route:<nazwa>"` wskazuje nieistniejącą krzywą `waypoints`;
   `at = "location:<nazwa>"` - nieistniejące miejsce `places`
5. ERROR `sprite` postaci bez katalogu assetów
6. ERROR przedmiot w `items` postaci / skrzyni / nagrodzie questa / warunku `has_item()`
   nie istnieje w `config.items` (warunki wyciągnij regexem `has_item\("([^"]+)"\)`
   z sekcji dialogs i quests configu)
7. ERROR `dialog_key` postaci bez sekcji w `config.dialogs`
8. WARN postać w config.characters bez żadnego spawn point na żadnej mapie
   (legalne dla potworów labiryntu - te są w maze_configs; wyklucz je)
9. WARN obiekt `spawn_points` z nazwą, której nie ma w waypoints, gdy postać nie ma
   rutyny (stary system tras; sama nieobecność to tylko ostrzeżenie)
10. WARN duplikaty nazw obiektów w obrębie jednej warstwy jednej mapy

## Krok 3: raport

Użyj `rich` (jest w requirements-dev; jeśli nie - dopisz). Tabela: kolumny
Severity / Źródło / Problem, kolory: ERROR czerwony, WARN żółty. Na końcu podsumowanie
`X errors, Y warnings` i exit code: 1 gdy errors > 0, inaczej 0 (warningi nie failują).
Flaga `--strict` - warningi też failują. Flaga `--json` - wynik jako JSON na stdout
(dla przyszłej integracji).

## Krok 4: recepta just + kaskada po importach

Wzorzec `validate-locale` (justfile:274). Dodatkowo:

1. Dodaj `validate-world` do agregatu `check:` (linia `check: sourcery mypy
   validate-locale` - dopisz na końcu).
2. **Kaskada (decyzja autora):** na KOŃCU recept `import-entities`, `import-dialogs`
   i `import-quests` dopisz wywołanie `just validate-world` - błąd spójności ma
   wychodzić w momencie autorskiej edycji treści, nie w runtime. Walidator jest
   szybki (< 5 s), więc nie spowalnia pętli pracy. Recept `gen-*` / `dialog-graph` /
   `quest-graph` NIE ruszaj - to generatory diagnostyczne, czytają config, niczego
   nie psują.
3. Git pre-commit hooka NIE dodajemy (świadoma decyzja: na tym repo pracuje
   równolegle wielu agentów + rtk przechwytuje komendy - hook w tym środowisku
   generuje więcej tarcia niż wartości). Zamiast tego walidacja żyje w `just check`,
   w kaskadzie importów i w CI (krok 5).

## Krok 5: stan zero

Uruchom walidator na obecnym repo. Każde znalezione naruszenie: jeśli to oczywista
literówka - NIE naprawiaj (to nie jest zakres tego zadania), tylko zbierz wszystkie
do sekcji "Stan zero" w raporcie końcowym zadania (wklej do opisu commita i zgłoś
autorowi). Jeżeli naruszeń klasy ERROR jest dużo, NIE dodawaj kroku do CI - zgłoś
listę i zostaw decyzję autorowi; jeżeli zero - dodaj krok do unit_tests.yml.

## Kryteria akceptacji

1. `just validate-world` działa i wypisuje tabelę + podsumowanie.
2. Test mutacyjny (ręczny, bez commita): zmień w kopii `Village.tmx` jedno `model_name`
   na `XXX` - walidator zgłasza ERROR z nazwą mapy i obiektu; przywróć plik.
3. Analogicznie: nieistniejąca rutyna w characters.csv - ERROR z numerem wiersza
   lub kluczem postaci.
4. Skrypt działa bez SDL/pygame: `python3 scripts/validate_world.py` na czystym
   interpreterze bez `SDL_VIDEODRIVER` (import pygame = automatyczny FAIL zadania).
5. Czas działania < 5 s.
6. `just test-unit` przechodzi (walidator to skrypt, nie moduł gry - nic nie powinno
   być dotknięte).

## Pułapki

- characters.csv używa separatora `;`, wartości mogą być puste - puste pole = brak
  wymogu, nie błąd.
- Warstwa `places` używa formatu `Mapa:nazwa` TYLKO w CSV; na mapie obiekt nazywa się
  samą nazwą. Parsuj `:` z lewej strony raz (`split(":", 1)`).
- Nazwy plików map ≠ nazwy map w grze - Scene używa nazw bez rozszerzenia
  (`Village`, `VillageHouse`); mapuj po stem pliku.
- Potwory labiryntów (maze_configs: monsters_list, boss_monster) też muszą istnieć
  w characters (reguła 1 obejmuje je przez sprawdzenie maze_configs).
- Nie waliduj `doc/` vaultu - to robi importer dialogów/questów; nie dubluj jego pracy.

## Po zakończeniu

- wzmianka w root `AGENTS.md` + `project/config_model/AGENTS.md`
- odhacz C01 w `doc/audyt/audyt.md`; listę "stanu zero" wklej do commita
- commit: `C01: just validate-world - walidator spójności encji (mapy/CSV/config/rutyny)`
