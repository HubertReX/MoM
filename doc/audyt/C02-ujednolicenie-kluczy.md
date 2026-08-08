# C02 - stopniowe ujednolicenie kluczy encji (Tiled ↔ config)

Priorytet: **P3** (Faza 4). Rozmiar: M → **L** (po uwagach autora z rev. 2). Zależności: **miękka** -
korzysta z walidatora z [C01](C01-validate-world.md) i z bramki zgodności zapisu z
[B02](B02-polityka-wersji-save.md).

Status: **rev. 3 - D1-D19 zamknięte decyzjami autora. Etap 1 zrobiony** (2026-08-08).
Otwarty jest tylko drobiazg w D13 (zestaw kolumn `maps.csv`). Następny w kolejce: etap 2.

## Wymagania autora (wiążące, ustalone 2026-08-08)

- **W1** - klucz identyfikuje encję wszędzie jednakowo. `LOST_CORK_TAVERN` to **klucz**
  używany przy projektowaniu fabuły, dialogów, questów i postaci w Obsidian - nie
  stylizacja. Dotyczy to również **map**.
- **W2** - w interfejsie gry widać nazwy przyjazne, zależne od języka (PL „Tawerna
  Brakująca Klepka", EN „the Lost Cork Tavern"). Klucz nigdy nie trafia na ekran gracza.
- **W3** - `VillageHouse.tmx` zostaje jako zaczątek osobnego domu w wiosce; przenosimy
  poza `maps/`, żeby walidator i pakowanie web go nie liczyły.
- **W4** - stare zapisy odrzucamy jawnie (D9 = A), bez kodu migracji.
- **W5** - trzy nieużywane utwory zostają na mapy Aktu 1; dokładamy samą regułę
  walidatora (O4).

## Uwagi autora do rev. 2 (wiążące, 2026-08-08 wieczorem)

- **W6** - w kluczach skrzyń lokalizacja idzie **na przód**, nie na koniec:
  `SmallChest_VillageHouse` → `LOST_CORK_TAVERN_SMALL_CHEST` (zmienia D8).
- **W7** - mapa `Village` to tak naprawdę **`BLUNDERHAVEN`** i ta zmiana idzie w ramach C02.
- **W8** - właściwości labiryntu (`is_maze`, `maze_cols`, `maze_rows`) wychodzą z obiektu
  `Maze` w warstwie `interactions` do pliku CSV; `entry_point` → `destination_entry_point`;
  `is_maze` najlepiej niech zniknie zupełnie, bo to cecha mapy, nie drzwi.
- **W9** - `model_name` mieszka w `CharacterTileset.tsx`, nie na obiektach mapy; cztery
  wyjątki w `Village.tmx` do usunięcia po upewnieniu się, że tileset ma dobre wartości.
- **W10** - `Element.tsx` i `FloorDetail.tsx` przenieść do `maps/tilesets/` razem
  z odwołaniami w plikach `.tmx`.
- **W11** - mapy niezgodne z konwencją (`JacobsChamber`, labirynt) dostają parę plików
  `.md` (PL + EN) w `doc/`, do edycji i tłumaczenia w Obsidian; stamtąd nazwy trafiają do
  sekcji `[map]` w plikach locale.
- **W12** - wpis w `AGENTS.md` nie daje gwarancji, że skrypt rename'ujący nadąży za grą.
  Potrzebny bezpieczny (nie psujący) test jednostkowy, który musi przejść na CI.
- **W13** - model węża to `SNAKE`, a nie `SNAKE_01`; tabela zmian w rev. 2 odwracała też
  numerację zwierząt - to była pomyłka dokumentu, nie zamysł.

Dokument decyzyjny (diagramy, tabele opcji, dokładna lista zmian, ściąga projektanta):
[C02-klucze-encji-2026-08-08.html](../_attachements/C02-klucze-encji-2026-08-08.html)
(podgląd: `docserve start doc/_attachements/C02-klucze-encji-2026-08-08.html`).

## Kontekst

Klucze encji żyją w **dwunastu przestrzeniach nazw**. C01 dał walidator, który pilnuje,
czy odwołania *wskazują na coś istniejącego* - ale nie pilnuje, czy *nazwy trzymają
jakąkolwiek konwencję*. Efekt: w warstwie `spawn_points` stoją obok siebie
`BARMAN_ABSINTHRAYNER`, `Johny`, `FishRed01` i `Dog_orange`, a autor przy każdej nowej
postaci zgaduje, która forma jest ta właściwa.

To zadanie jest w połowie robotą projektanta gry, nie programisty: jego głównym
produktem jest **ściąga „gdzie używam jakiego klucza"**, a rename'y są tylko po to,
żeby ta ściąga była prawdziwa.

## Ustalenia z analizy (rev. 2: O1-O5, rev. 3: O6-O9)

- **O1 - zmiana nazwy obiektu Tiled kasuje jego stan z zapisu.** Zapis kluczuje NPC-e
  i skrzynie po nazwie obiektu, nie po kluczu configu: `manager.py:337`
  (`npc_states[npc.name]`), `:696` (`chest_map`), `:755` (`dead_monsters`). Bramka
  `save_compatibility` z B02 tego **nie złapie**, bo format zapisu się nie zmienia -
  zapis wczyta się „poprawnie", a przemianowany obiekt dostanie stan domyślny.
- **O2 - rename `VillageHouse` → `LOST_CORK_TAVERN` stoi w połowie.** Zostały: martwy
  `VillageHouse.tmx` (12×10 kafli, nieosiągalny z żadnej warstwy `interactions`), klucz
  `VillageHouse` w `audio.toml`, skrzynia `SmallChest_VillageHouse` stojąca w tawernie
  i punkt wejścia `VillageHouseDoor`. Muzyka w tawernie **gra poprawnie**
  (`LOST_CORK_TAVERN` ma własny wpis) - szkoda polega na tym, że martwy `.tmx`
  uwiarygodnia martwy klucz, więc `check_audio_manifest` go przepuszcza.
- **O3 - rename NIE zerwie rozpoznawania modelu.** Wszystkie 34 obiekty `spawn_points`
  biorą `model_name` z kafla tilesetu (31) albo z własności na obiekcie (3). **Ani
  jeden** nie polega na fallbacku „nazwa obiektu = klucz configu"
  (`validate_world.py:_resolve_model_name`, wariant 3). Nazwa obiektu jest dziś czystą
  etykietą instancji.
- **O4 - 4,78 MB z 9,97 MB katalogu `assets/audio/` to balast.** Trzy utwory nie mają
  wpisu w manifeście w ogóle, `deep-in-the-dell` ma wpis tylko dla martwej mapy,
  `failfare` jest zakomentowany. Przyczyna niewidoczności: `check_audio_manifest` sprawdza
  SFX-y w obie strony, a muzykę **tylko w jedną**. Decyzja W5: utwory zostają, dokładamy
  regułę „plik muzyki bez wpisu = WARN".
- **O5 - HUD wyświetla surowy klucz mapy.** `hud.py:233-237` bierze `scene.current_map`
  i jedyne, co z nim robi, to zamiana `Maze_01` → `Maze 1`. Gracz stojący w tawernie
  czyta na ekranie `LOST_CORK_TAVERN`, a nazw map nie ma dziś w żadnym pliku locale.
- **O6 - kod rozpoznaje gracza po nazwie wyświetlanej, nie po kluczu.** `combat.py:31`,
  `:41`, `:66` i `objects.py:207` sprawdzają `npc.model.name_EN == "Player"`. `name_EN`
  to kolumna z napisem dla gracza - dokładnie ta warstwa, którą W2 każe tłumaczyć. Polskie
  „Gracz" w `characters.csv` po cichu wyłączy walkę i śmierć gracza. To ten sam błąd co O5,
  odbity w lustrze: tam klucz udaje napis, tu napis udaje klucz.
- **O7 - `maze_cols` i `maze_rows` na obiekcie `Maze` są martwe.** `go_to_map` przepisuje
  je z wyjścia na scenę (`map_state.py:150-151`), po czym `load_tileset_map` natychmiast
  nadpisuje je wartościami z `maze_configs.csv` (`map_loader.py:474-475`) - i dopiero te
  wchodzą do `HuntAndKillMaze(...)`. Ścieżka „mapa z cache" bierze zapisane. Mapa mówi
  `10×7`, `maze_configs.csv` dla poziomu 1 mówi `9×6` - wygrywa CSV. Nie trzeba ich nigdzie
  przenosić: trzeba je skasować.
- **O8 - sześć kafli w `CharacterTileset.tsx` ma `model_name`, które nie jest kluczem
  żadnej postaci.** Kafel 9 = `Dog1`, 10 = `Dog`, 6 = `Snake`, 21 = `Spirit`, 22 = `Slime`,
  23 = `SpiderRed`. Trzy pierwsze są dziś zamaskowane własnością na obiekcie (to właśnie te
  „niepotrzebne" własności z W9), trzy pozostałe czekają uśpione - pierwszy spawn potwora
  postawiony z tego kafla w Tiled wybuchnie `KeyError`. Usunięcie własności z obiektów
  **bez** naprawy kafli psuje grę natychmiast.
- **O9 - `ROB` i `ROBIN` stoją na tym samym kaflu** (`gid=2821`, kafel 4, sprite
  `Villager4`). Własność `model_name` na obiekcie `Robin` jest jedynym sposobem odróżnienia
  ich - po jej usunięciu Robin zaspawnuje się jako Rob. To nie jest niekonsekwencja do
  posprzątania, tylko brakujący kafel w tilesecie.

## Decyzje

Pełne tabele opcji z uzasadnieniem są w dokumencie HTML. Skrót:

| # | Decyzja | Rozstrzygnięcie |
| --- | --- | --- |
| D1 | Konwencja nazwy instancji w `spawn_points` | = klucz configu (`FISH_RED_01`) |
| D2 | Kiedy sufiks numeryczny | tylko gdy model ma >1 kopię na mapie |
| D3 | Odwołania do miejsc | zawsze `MAPA:miejsce`, także wewnątrz jednej mapy |
| D4 | Krzywe `waypoints` | nazwa idzie za D1; wyłączanie własnością `enabled=false` |
| D5 | Nazwy map | `SCREAMING_SNAKE`; `Village` → **`BLUNDERHAVEN`** (W7), `JacobsChamber` → `JACOBS_CHAMBER` |
| D6 | `interactions` / `entry_points` | nowa reguła ERROR w C01 |
| D7 | `VillageHouse.tmx` | do `maps/_wip/` (W3) + trzy reguły WARN |
| D8 | Klucze skrzyń | **prefiks lokalizacji** (W6): `LOST_CORK_TAVERN_SMALL_CHEST` |
| D9 | Stare zapisy | podbić wersję → jawna odmowa (W4), bez kodu migracji |
| D10 | Sposób wykonania | skrypt `just rename-entity <stara> <nowa>`; musi umieć też mapy |
| D11 | Zakres podejścia | osobne commity per etap |
| D12 | Nazwy wyświetlane (W2) | **przyjęte: A** - sekcja `[map]` w `locale/PL.toml` i `EN.toml` |
| **D13** | **Właściwości labiryntu (W8)** | **do akceptacji** - nowy `maps.csv`, kasata trzech własności |
| **D14** | **`model_name` tylko w tilesecie (W9)** | naprawa 6 kafli + **nowy kafel dla `ROBIN`** (wariant A) |
| **D15** | **Tilesety do `tilesets/` (W10)** | przyjęte - 7 odwołań w 6 plikach `.tmx` |
| **D16** | **Dokumenty lokacji (W11)** | przyjęte - para `.md` dla `JACOBS_CHAMBER` **i dla labiryntu** |
| **D17** | **Utrzymanie skryptu rename (W12)** | przyjęte - `tests/test_rename_entity.py` na CI |
| **D18** | **Sufiks `_01` w kluczach modeli (W13)** | przyjęte - `SNAKE`, `SPIRIT`, `SLIME`, `SPIDER` |
| **D19** | **`CAVE_LION2`** | przyjęte A - `CAVE_LION_SAND` + `CAVE_LION_GREY` + rozdzielone napisy |

### D13 - co dokładnie robimy z obiektem `Maze`

- `maze_cols`, `maze_rows` - **usunąć** z `.tmx` i z sygnatury `Collider`. Są martwe (O7),
  a prawdziwe wartości siedzą w `maze_configs.csv` per poziom - i tam jest ich miejsce, bo
  poziom 3 ma inny rozmiar niż poziom 1, a obiekt na mapie zna tylko wejście.
- `entry_point` → `destination_entry_point`. Wskazuje punkt **na mapie docelowej**, a scena
  ma osobne pole `entry_point` („gdzie stoję teraz"). Jedna nazwa na dwa pojęcia to dokładnie
  ta klasa pomyłki, którą C02 likwiduje. Pole `PlayerState.entry_point` w zapisie **zostaje** -
  tam chodzi o scenę, nie o drzwi.
- `is_maze` - usunąć z `.tmx`, wyliczać z nowego rejestru `project/config_model/maps.csv`
  (`key;kind`, gdzie `kind` to `static` albo `maze`): `is_maze = maps[to_map].kind == "maze"`.
  Ten sam plik daje walidatorowi listę legalnych kluczy map, której dziś nie ma (mapa
  „istnieje", bo istnieje plik `.tmx` - a labirynt pliku nie ma), i domyka regułę z D12.
- `to_map`, `return_entry_point`, `obj_type` - bez zmian, opisują to konkretne przejście.

**Do rozstrzygnięcia:** czy `maps.csv` ma być goły (`key;kind`), a nazwy wyświetlane mają
jechać wyłącznie przez locale (rekomendacja), czy ma też trzymać nazwy plików `.md` z `doc/`.

### D16 - konwencja dokumentów lokacji już istnieje

Siedem lokacji ma dziś parę plików PL/EN z aliasem-kluczem we frontmatterze
(`doc/EN/Locations/`, `doc/PL/Lokalizacje/`, szablony w `doc/_templates/loc_template*.md`):
`BLUNDERHAVEN`, `LOST_CORK_TAVERN`, `CAVERNS_OF_CONFUSION`, `KINGDOM_OF_KNAVESHIRE`,
`QUIRKSHIRE`, `SWAMP_OF_INCONVENIENCE`, `TANGLED_FOREST_OF_ANNOYANCE`. Brakuje dwóch:
`JACOBS_CHAMBER` i labiryntu.

**Rozstrzygnięte:** `CAVERNS_OF_CONFUSION` („Jaskinie zagmatwania") to osobna lokacja Aktu 1 -
mapy jaskini jeszcze nie ma. Labirynt dostaje więc własną parę plików `.md`, a klucze poziomów
zostają `MAZE_01`, `MAZE_02`… Do dorobienia są dwie pary: `JACOBS_CHAMBER` i labirynt.

### D18 - gdzie siedzi numer

Model traci sufiks (`SNAKE`, `SPIRIT`, `SLIME`, `SPIDER`), numer należy do instancji i pojawia się
tam, gdzie kopii jest wiele. Na `BLUNDERHAVEN` wąż jest jeden, więc instancja to `SNAKE`.
W labiryncie potworów tego rodzaju są dziesiątki - i **kod już nadaje im nazwy zgodne z docelową
konwencją**: `map_loader.py:609` buduje `<MAPA>_<MODEL>_<NNN>`, czyli prefiks mapy na przodzie,
dokładnie jak w kluczach skrzyń z W6. Sufiks `_01` w kluczu modelu produkuje dziś podwójny numer
(`Maze_01_SNAKE_01_004`); po D18 wychodzi czytelne `MAZE_01_SNAKE_004`, bez zmiany linijki w kodzie
nazywającym.

### D19 - co znaczy „nazwa opisowa"

`CAVE_LION` i `CAVE_LION2` to dwa różne modele (osobne sprite'y `CaveLion`, `CaveLion2`), a nie dwie
kopie jednego - więc numer myli tak samo jak `SNAKE_01`. Nazwa opisowa = klucz mówi, **czym** ten model
różni się od tamtego, zamiast mówić „drugi z brzegu". Konwencja już istnieje i jest kolorowa:
`DOG_ORANGE`/`DOG_PURPLE`, `CHICKEN_BLACK`/`CHICKEN_BROWN`/`CHICKEN_WHITE`, `FISH_RED`, `LION_YELLOW`.
Oba lwy różnią się właśnie kolorem: pierwszy piaskowy z tęczową grzywą, drugi ciemnoszary
z niebiesko-pomarańczową.

**Przyjęte: A** - `CAVE_LION_SAND` + `CAVE_LION_GREY`, symetrycznie jak psy.

Nazwy wyświetlane też były identyczne dla obu (`name_EN` „CaveLion", `name_PL` „Lew jaskiniowy"), więc
gracz nie odróżniłby ich w dzienniku walki nawet po rozdzieleniu kluczy. Rozdzielone i **wprowadzone
od razu**, bo są niezależne od rename'u kluczy:

| Klucz | `name_EN` | `name_PL` |
| --- | --- | --- |
| `CAVE_LION` → `CAVE_LION_SAND` | Sand Cave Lion | Piaskowy lew jaskiniowy |
| `CAVE_LION2` → `CAVE_LION_GREY` | Grey Cave Lion | Szary lew jaskiniowy |

Napisy siedzą już w `characters.csv` i w `config.json` (przez `just import-entities`; `validate-world`:
0 błędów, 5 znanych ostrzeżeń). Same klucze zmieniają się w etapie 5, jednym przebiegiem `rename-entity`.

### D17 - dlaczego test, a nie wpis w `AGENTS.md`

Obawa z W12 jest trafna: `rename_entity.py` zna listę źródeł, w których siedzą nazwy encji.
Za pół roku dojdzie `quests.csv` albo nowy katalog map i pierwszy rename po cichu zostawi
jedno źródło nietknięte. Trzy warstwy zabezpieczenia:

1. `just validate-world` na CI (**już jest**, ostatni krok `unit_tests.yml`) - pilnuje, że
   świat *po* rename'ie jest spójny.
2. **Nowe:** `tests/test_rename_entity.py` - skrypt publikuje manifest globów
   (`config_model/*.csv`, `*.toml`, `config.json`, `maps/**/*.tmx`, `locale/*.toml`), a test
   przechodzi po repo i **failuje, gdy znajdzie plik danych, którego żaden glob nie obejmuje**.
   Krzyczy w dniu, w którym ktoś doda nowy plik - a nie przy pierwszym rename'ie po nim.
3. Ta sama para w drugą stronę: na kopii świata w katalogu tymczasowym skrypt zmienia znaną
   encję, a test sprawdza, że nie została ani jedna stara nazwa.

Test jest bezpieczny: operuje na **kopii** w katalogu tymczasowym, nigdy na plikach repo,
nie uruchamia gry i nie potrzebuje ekranu (czyta surowe CSV/TOML/XML jak `validate_world.py`).
Wzór jest w repo - `tests/test_config_web_codegen.py` pilnuje w ten sposób, że `config.py`
nie rozjechał się z generatorem. Ściąga w `AGENTS.md` zostaje jako opis dla człowieka i agenta,
ale **bramką jest CI**.

## Etap 1: sprzątanie po tawernie + higiena plików (D7, D8, D14, D15) - ZROBIONE

Niezależne od reszty - poszło pierwsze i osobnym commitem.

- `maps/VillageHouse.tmx` → `maps/_wip/` (W3). Walidator i ładowarka nie wymagały ani
  jednej linijki zmiany: `MAP_DIRS` używa `glob("*.tmx")` (bez rekursji), a ładowarka
  szuka mapy po płaskiej nazwie `MAPS_DIR / f"{current_map}.tmx"`. Pakowanie web wyłącza
  nowy wpis w `pygbag.ini` (`ignoreDirs`)
- `audio.toml` - martwy wpis `VillageHouse` usunięty
- `chests.csv` + `maze_configs.csv` + `config.json` + nazwy obiektów w `interactions` -
  klucze skrzyń wg D8/W6 (2 wioskowe + 8 labiryntowych)
- `CharacterTileset.tsx` - naprawa **7** wartości `model_name` (O8) i zgranie z nimi
  atrybutu `type`; **nowy kafel 33 dla `ROBIN`** ze sprite'em `Villager4` (O9, D14=A)
- `Village.tmx` - wszystkie 4 własności `model_name` usunięte; obiekt `Robin` przepięty
  na `gid=2850`
- `Element.tsx`, `FloorDetail.tsx` → `tilesets/`; **8 odwołań w 6 plikach `.tmx`**;
  wewnątrz przenoszonych plików ścieżka do PNG skróciła się o `tilesets/`
- martwy duplikat `tilesets/TilesetFloorDetail.tsx` usunięty (ten sam PNG, zero odwołań,
  brak własności `elements` - potwierdzone przed kasatą)

### Czym wykonanie różni się od planu

- **Kafli do naprawy było 7, nie 6.** Ósmym… właściwie pierwszym: kafel 0 miał
  `model_name="GreenNinja"` (nazwa sprite'a), a klucz postaci to `Player`. Dziś nie boli,
  bo gracza spawnuje kod (`scene/scene.py:194`), ale reguła 4 z etapu 4 zapaliłaby się na
  nim. Naprawione razem z szóstką z O8 - decyzja autora.
- **Odwołań do przenoszonych tilesetów było 8, nie 7** - ósme siedzi w samym
  `VillageHouse.tmx`, którego plan nie liczył.
- **`_wip/VillageHouse.tmx` zjechał o katalog niżej, więc straciło ważność *wszystkie
  siedem* jego ścieżek względnych**, nie tylko `Element.tsx`. Poprawione na `../tilesets/…`
  i `../../items/items.tsx`, żeby plik dalej otwierał się w Tiled - W3 chce go jako zaczątek
  domu, a nie jako złom.
- **Skrzynia w `_wip` zostaje `SmallChest_VillageHouse`.** To osobny dom, nie tawerna;
  klucz dostanie, kiedy autor nazwie mapę.
- **`BigChest_Village` → `BLUNDERHAVEN_BIG_CHEST` od razu** (decyzja autora), zamiast
  przez pośrednie `VILLAGE_BIG_CHEST`. Klucz skrzyni to zwykły string - nie wymaga, żeby
  mapa już się tak nazywała, a oszczędza drugi rename w etapie 5.
- **`import_entities.py` nie umie zmienić nazwy klucza** - aktualizuje tylko wiersze, które
  już są w `config.json`, a nieznane pomija ostrzeżeniem. Klucze skrzyń trzeba było
  podmienić w `config.json` wprost, a dopiero potem puścić import. Warte zapamiętania dla
  `rename_entity.py` z etapu 5.
- **`tests/test_audio.py` był przypięty do martwego wpisu** `VillageHouse` (test zmiany
  utworu przy zmianie mapy). Przepięty na żywą parę `Village` → `LOST_CORK_TAVERN`.
- `config_model/autogenerated_config.json` trzyma stare klucze skrzyń. Zostawiony:
  to martwy artefakt po usuniętym w B01 `main.py store`, nikt go nie czyta.
- `VillageHouseDoor` (punkt wejścia na `Village`) i nazwy obiektów-szablonów
  `BigChest_Maze`/`SmallChest_Maze` w `MazeTileset_Ninja.tmx` **zostają** - te drugie są
  zaszyte w kodzie (`map_loader.py:293`, `maze_utils.py:827`), więc nie są zwykłą daną.

### Wynik

- `just validate-world` - 0 błędów, te same 5 znanych ostrzeżeń; **6 map zamiast 7**
  (`VillageHouse` wypadł z zakresu, zgodnie z W3)
- `just test-unit` - 499/499 w 36 plikach
- `just test-smoke` - 6/6 scenariuszy, w tym **Auto Save on Maze Entry**: labirynt
  generuje się po przeprowadzce tilesetów
- headless `load_pygame` na wszystkich 6 mapach + obu szablonach labiryntu przechodzi;
  `Robin` rozwiązuje się na `ROBIN`, a `Rob` na `ROB` z samego kafla, bez własności na
  obiekcie (O9 zamknięte)

**Do weryfikacji u autora** (sterownik `dummy` nie odtwarza dźwięku, a walidator nie widzi
`assets/MazeTileset/`): muzyka w tawernie i w wiosce gra jak dotąd, labirynt wygląda
poprawnie po przeprowadzce `Element.tsx`/`FloorDetail.tsx`, `Robin` stoi w wiosce jako
Robin. Uwaga: klucze skrzyń się zmieniły, więc **stare zapisy zgubią stan tych skrzyń**
(O1) - to przedsmak D9, gdzie zapisy zostaną odrzucone jawnie.

## Etap 2: rejestr map i właściwości labiryntu (D13, D16)

Czysto techniczny, bez ani jednego rename'u - odwracalny osobnym commitem.

- nowy `project/config_model/maps.csv` (`key;kind`) + model w `config_pydantic.py` i
  regeneracja web przez `just gen-web-config`
- `objects.py` (`Collider`), `scene/map_loader.py`, `scene/map_state.py` - `is_maze` liczone
  z rejestru, `maze_cols`/`maze_rows` wypadają z sygnatury
- `.tmx` - kasata trzech własności, `entry_point` → `destination_entry_point` na obiektach
  wyjść (także w obiektach syntetyzowanych w `maze_generator/maze_utils.py:817,825,839`)
- para plików `.md` (PL + EN) dla map bez dokumentu (D16) - **do edycji autora w Obsidian**

Kryterium: `just test-unit` zielony (`test_maze_reproducible.py` musi przejść bez zmian),
wejście do labiryntu i powrót działają - **weryfikacja u autora**.

## Etap 3: warstwa nazw wyświetlanych (D12, W2, O6) - PRZED renamem map

**Musi wyprzedzić etap 5**: gdyby rename map poszedł pierwszy, gracz zobaczyłby na HUD-zie
`JACOBS_CHAMBER`, czyli zmiana pogorszyłaby stan widoczny w grze, zanim go poprawi.

- `project/assets/locale/PL.toml` i `EN.toml` - nowa sekcja `[map]`, zasilona z dokumentów
  lokacji w `doc/`
- `project/ui/panels/hud.py` - `_update_location_cache` czyta nazwę z locale zamiast
  wyświetlać `scene.current_map`; `_format_map_name` (hack na `Maze_01`) znika
- `combat.py`, `objects.py` - `name_EN == "Player"` → porównanie po kluczu (O6)
- `scripts/validate_locale.py` albo `validate_world.py` - reguła „mapa bez nazwy
  wyświetlanej w PL i EN = ERROR"

Pułapka: zmiana języka w locie musi działać. Czytaj `settings.LANG` na żywo, nie przez
`from settings import LANG`, a panele odświeżaj przez `rebuild_i18n()`.

Kryterium: HUD pokazuje „Tawerna Brakująca Klepka" / „the Lost Cork Tavern", a
przełączenie języka w ustawieniach zmienia napis bez restartu. **Weryfikacja u autora.**

## Etap 4: nowe reguły walidatora - PRZED rename'ami (D1, D3, D6, D7, D13, D14)

Plik: `scripts/validate_world.py` (+ testy w `tests/`).

1. **Konwencja nazwy instancji** (D1/D2): nazwa obiektu w `spawn_points` = klucz z
   `model_name`, opcjonalnie z sufiksem `_NN`. Poziom: ERROR.
2. **Drzwi donikąd** (D6): obiekt w `interactions` musi nazywać istniejącą mapę albo
   istniejący klucz skrzyni; `destination_entry_point` musi wskazywać obiekt z warstwy
   `entry_points` **mapy docelowej**. Poziom: ERROR. Uwaga: walidator czyta dziś same nazwy
   obiektów - trzeba dołożyć czytanie własności, wzorem `_resolve_model_name`.
3. **Miejsce bez prefiksu mapy** (D3): wartość w `home`/`work`/`social`/`hobby` oraz
   `location:` w `routines.toml` musi mieć kształt `MAPA:miejsce`. Poziom: ERROR.
4. **`model_name` w tilesecie musi być kluczem istniejącej postaci** (D14, O8). Poziom:
   ERROR. Dziś walidator sprawdza tylko wartość *rozwiązaną dla obiektu na mapie*, więc
   sześć zepsutych kafli przeszło mu pod nosem.
5. **Mapa spoza `maps.csv`** i **mapa bez nazwy wyświetlanej** (D13, D12). Poziom: ERROR.
6. **Mapa bez muzyki**, **mapa nieosiągalna z żadnej warstwy `interactions`** oraz **plik
   w `assets/audio/music/` bez wpisu w manifeście** (D7, O4). Poziom: WARN.

Po tym etapie `just validate-world` **świeci na czerwono** - to zamierzone. Walidator jest
siatką bezpieczeństwa dla etapu 5, więc musi powstać wcześniej.

## Etap 5: rename'y (D1, D2, D3, D4, D5, D9, D10, D17, D18)

Najpierw narzędzie (D10): `scripts/rename_entity.py` + recepta `just rename-entity`,
zmieniające **wszystkie** źródła w jednym przebiegu (`.tmx`, `.csv`, `.toml`, `config.json`,
`locale/*.toml`) i kończące się wywołaniem `validate_world`. Razem z nim `tests/test_rename_entity.py`
(D17) - inaczej narzędzie zgnije dokładnie tak, jak przewiduje W12.

Zakres (pełna tabela w dokumencie HTML):

- 27 obiektów `spawn_points` (20 zwierząt/potworów + 5 statystów humanoidalnych; 6 postaci
  z dialogami zostaje nietkniętych). **Numer instancji idzie 1:1 ze starym numerem**
  (`FishRed01` → `FISH_RED_01`) - rev. 2 odwracała kolejność, to była pomyłka (W13)
- 4 klucze modeli tracą sufiks `_01` (D18): `SNAKE`, `SPIRIT`, `SLIME`, `SPIDER` - w
  `characters.csv`, `config.json`, kaflach tilesetu i `maze_configs.csv`. Nazwy instancji
  w labiryncie poprawiają się same (`MAZE_01_SNAKE_004` zamiast `Maze_01_SNAKE_01_004`)
- krzywe `waypoints`: `Rob`, `Robin`, `Marry`, `Cat01` idą za nazwami instancji;
  `Bart_BCKP`/`Johny_BCKP` wracają do właściwych nazw + `enabled=false`
- `routines.toml`: `route:Rob` → `route:ROB`, `route:Robin` → `route:ROBIN`
- 10 komórek miejsc w `characters.csv` + 2 cele `location:` dostają prefiks klucza mapy
  (`BLUNDERHAVEN:well`); 6 komórek z prefiksem `LOST_CORK_TAVERN:` jest już poprawnych
- mapy: `Village` → `BLUNDERHAVEN`, `JacobsChamber` → `JACOBS_CHAMBER` wraz ze wszystkimi
  odwołaniami (nazwa pliku, `maps.csv`, audio, prefiksy miejsc, `interactions`,
  `destination_entry_point`, punkty wejścia)
- **`"Village"` jest zapisane na sztywno w kodzie i skryptach** - `save_load.py` (2×),
  `main_menu.py`, `save_fixtures.py`, `b01_fixture.py`, `bench_scene.py`, `FoW-prototype.py`,
  `test_pathfinding_goal.py`. Przy okazji wyciągnąć to do stałej `settings.START_MAP`
- podbicie wersji zapisu (D9/W4), żeby stare zapisy zostały jawnie odrzucone

## Kryteria akceptacji

- `just validate-world` - 0 błędów, ostrzeżenia tylko znane (dziś 5)
- `just test-unit` - komplet zielony (dziś 499 testów w 36 plikach) + nowy `test_rename_entity.py`
- scenariusz agentowy z przewinięciem doby: `BART` i `JOHNY` docierają do `market_stall_*`,
  barman do `bar` (rutyny przeżyły rename)
- nowy zapis wczytuje się w komplecie; **stary jest widocznie odrzucony**, nie po cichu okrojony
- `just test-smoke` przechodzi (złota zasada dual-target)
- **HUD nigdy nie pokazuje klucza** - nazwa przyjazna w PL i EN, zmiana języka działa w locie
  (**weryfikacja u autora**)
- muzyka w tawernie gra po przemianowaniu map - **weryfikacja u autora**
- labirynt generuje się po przeprowadzce tilesetów i po kasacie własności - **weryfikacja u autora**
- ściąga „gdzie używam jakiego klucza" trafia do `project/AGENTS.md`

## Pułapki

- **Nie zaczynaj od rename'ów.** Bez reguł walidatora z etapu 4 nie ma jak sprawdzić, czy
  zmiany trafiły we wszystkie źródła. A bez etapu 3 rename map najpierw **pogorszy** to, co
  widzi gracz (klucz na HUD).
- **Nie usuwaj własności `model_name` z obiektów przed naprawą tilesetu.** Trzy z czterech
  maskują zepsute kafle (O8), czwarta jest jedynym odróżnieniem `ROBIN` od `ROB` (O9).
- **`MazeTileset_Ninja.tmx` jest niewidoczny dla walidatora.** Odwołania do tilesetów
  w `assets/MazeTileset/` nie są sprawdzane przez `validate_world`, a to żywy szablon
  labiryntu. Po D15 trzeba wejść do lochu ręcznie.
- **Nazwa mapy to nie tylko dana.** Siedzi w nazwie pliku `.tmx`, w zapisie
  (`PlayerState.map_name`), w kluczach muzyki, w prefiksach miejsc, w warstwie
  `interactions`, we własności wyjścia **i w kodzie** (mapa startowa).
- **Nazwa obiektu ≠ klucz configu w kodzie.** `NPC.name` to nazwa obiektu Tiled,
  `NPC.config_key` to klucz z `config.json` (`characters/npc.py:69` i `:105`). Dialogi
  i questy używają `config_key`; zapis używa `name`. Nie zamieniaj ich miejscami.
- **`entry_point` znaczy dwie różne rzeczy.** Na obiekcie wyjścia - punkt na mapie docelowej
  (po D13: `destination_entry_point`). Na scenie i w `PlayerState` - punkt, w którym gracz
  stoi teraz. To drugie zostaje bez zmian.
- **Gołe nazwy miejsc są dziś dwuznaczne.** `bar`, `tables` i `badroom` istnieją równocześnie
  na `LOST_CORK_TAVERN` i na martwym `VillageHouse` - kolejny powód, by etap 1 poprzedzał etap 4.
- **Nie ruszaj `CONF_ENTITIES_TO_STORE`** przy okazji. Po usunięciu `main.py store` w B01
  czytane są z niego tylko klucze - to martwe dane do sprzątnięcia osobno.

## Po zakończeniu

- ściąga do `project/AGENTS.md` (sekcja o kluczach encji) i do dokumentacji świata
- rozdział 5 raportu audytu (mapa przepływu encji) - aktualizacja konwencji
- odhaczenie C02 w [audyt.md](audyt.md)
