# C02 - stopniowe ujednolicenie kluczy encji (Tiled ↔ config)

Priorytet: **P3** (Faza 4). Rozmiar: M. Zależności: **miękka** - korzysta z walidatora
z [C01](C01-validate-world.md) i z bramki zgodności zapisu z [B02](B02-polityka-wersji-save.md).

Status: **D1-D11 z decyzjami autora z 2026-08-08; D12 (warstwa nazw wyświetlanych) do
rozstrzygnięcia**. Kod zaczyna się po domknięciu D12.

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

## Trzy ustalenia z analizy 2026-08-08 (zmieniają kształt zadania)

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
- **O4 - przy okazji: 4,78 MB z 9,97 MB katalogu `assets/audio/` to balast.** Trzy utwory
  (`to-the-death`, `stranger-things`, `dreamy-rain-ambience`) nie mają wpisu w manifeście
  w ogóle, `deep-in-the-dell` ma wpis tylko dla martwej mapy, `failfare` jest
  zakomentowany. Wszystko jedzie w `web.zip`, a budżet z D01 („≤ 10 MB") jest już
  wyczerpany w 99,7%. Przyczyna niewidoczności: `check_audio_manifest` sprawdza SFX-y
  w obie strony, a muzykę **tylko w jedną** (klucz → plik, nigdy plik → klucz).
  **To nie jest robota C02** (co zrobić z trzema utworami to decyzja projektowa autora),
  ale regułę „plik muzyki bez wpisu = WARN" dokładamy przy D7.
- **O5 - HUD wyświetla surowy klucz mapy.** `hud.py:233-237` bierze `scene.current_map`
  i jedyne, co z nim robi, to zamiana `Maze_01` → `Maze 1`. Gracz stojący w tawernie
  czyta na ekranie `LOST_CORK_TAVERN`, a nazw map nie ma dziś w żadnym pliku locale.
  Warstwa wymagana przez W2 **nie istnieje** - i to ona jest teraz największą pozycją
  w C02 (decyzja D12).
- **O3 - rename NIE zerwie rozpoznawania modelu.** Wszystkie 34 obiekty `spawn_points`
  biorą `model_name` z kafla tilesetu (31) albo z własności na obiekcie (3). **Ani
  jeden** nie polega na fallbacku „nazwa obiektu = klucz configu"
  (`validate_world.py:_resolve_model_name`, wariant 3). Nazwa obiektu jest dziś czystą
  etykietą instancji.

## Decyzje do akceptacji

Pełne tabele opcji z uzasadnieniem są w dokumencie HTML. Skrót rekomendacji:

| # | Decyzja | Rekomendacja |
| --- | --- | --- |
| D1 | Konwencja nazwy instancji w `spawn_points` | = klucz configu (`FISH_RED_01`), NIE małymi literami |
| D2 | Kiedy sufiks numeryczny | tylko gdy model ma >1 kopię na mapie |
| D3 | Odwołania do miejsc | zawsze `Mapa:miejsce`, także wewnątrz jednej mapy |
| D4 | Krzywe `waypoints` | nazwa idzie za D1; wyłączanie własnością `enabled=false`, nie sufiksem `_BCKP` |
| D5 | Nazwy map | **`SCREAMING_SNAKE` (W1)**: `Village` → `VILLAGE`, `JacobsChamber` → `JACOBS_CHAMBER`, `LOST_CORK_TAVERN` bez zmian |
| D6 | `interactions` / `entry_points` | nowa reguła ERROR w C01 |
| D7 | `VillageHouse.tmx` | **przenieść do `maps/_wip/` (W3)** + reguły „mapa bez muzyki", „mapa nieosiągalna", „plik muzyki bez wpisu" jako WARN |
| D8 | Klucze skrzyń | opisują zawartość, nie mapę (`SMALL_CHEST_TAVERN`) |
| D9 | Stare zapisy | **podbić wersję → jawna odmowa (W4)**, bez kodu migracji |
| D10 | Sposób wykonania | skrypt `just rename-entity <stara> <nowa>`; **musi umieć też mapy** |
| D11 | Zakres podejścia | osobne commity per etap |
| **D12** | **Gdzie żyją nazwy wyświetlane (W2)** | **do rozstrzygnięcia** - rekomendacja: sekcja `[map]` w `locale/PL.toml` i `EN.toml` |

**D5 poszło w odwrotną stronę niż moja pierwotna rekomendacja.** Proponowałem `CamelCase`
(`LostCorkTavern`), zakładając, że nazwa mapy jest jednocześnie tym, co widzi gracz.
Przy W2 to nieprawda - nazwa mapy to czysty klucz, a gracz czyta locale. Argument
„ładniej wygląda na HUD-zie" znika, zostaje sam argument za spójnością.

**D12 - warianty:** (A) sekcja `[map]` w plikach locale - symetrię PL/EN pilnuje już
`just validate-locale`, zero nowych formatów; (B) nowy `maps.csv` z `name_PL`/`name_EN`
jak `characters.csv` - znajoma konwencja, ale wypada z zasięgu `validate-locale`;
(C) własności w `.tmx` - nazwa mieszka z mapą, ale tłumaczenia rozsypane po kilkunastu
plikach XML. Rekomendacja A: nazwa mapy to napis UI, bliżej jej do `notify.bought` niż
do `speed_walk`.

**Dlaczego D1 = klucz configu, a nie „klucz małymi literami" z pierwotnej propozycji
audytu:** wariant „małymi" renamuje wszystkie 34 obiekty, w tym **6 postaci z dialogami**,
czyli dokładnie te, których stan w zapisie ma wartość (sentyment, przebieg rozmowy).
Wariant rekomendowany renamuje 27 obiektów, z czego **wszystkie 20 zmienianych postaci ma
`has_dialog=false` i nie ma grafu rozmowy** - ich stan w zapisie to pozycja i flaga
„zabity". Podział wychodzi idealnie czysty i to on rozstrzyga decyzję.

## Etap 1: sprzątanie po rename'ie tawerny (D7, D8)

Niezależne od reszty - idzie pierwsze i osobnym commitem.

Pliki:

- `project/assets/NinjaAdventure/maps/VillageHouse.tmx` → `maps/_wip/` (W3); ładowarka
  map i `validate_world.MAP_DIRS` muszą ignorować `_wip/`, a pakowanie web go nie brać
- `project/config_model/audio.toml` - usunąć martwy wpis `VillageHouse`
- `project/config_model/chests.csv` + `config.json` - klucze skrzyń wg D8
- `project/assets/NinjaAdventure/maps/LOST_CORK_TAVERN.tmx` - nazwa obiektu skrzyni

Kryterium: `just validate-world` nie zgłasza nowych błędów, a muzyka w tawernie gra jak
dotąd. **Weryfikacja u autora** - sterownik `dummy` nie odtwarza dźwięku, więc headless
tego nie sprawdzi.

## Etap 2: warstwa nazw wyświetlanych (D12, W2) - PRZED renamem map

Nowy etap, wymuszony przez W2 i znalezisko O5. **Musi wyprzedzić etap 4**: gdyby rename
map poszedł pierwszy, gracz zobaczyłby na HUD-zie `JACOBS_CHAMBER`, czyli zmiana
pogorszyłaby stan widoczny w grze, zanim go poprawi.

- `project/assets/locale/PL.toml` i `EN.toml` - nowa sekcja `[map]` (wariant D12=A)
- `project/ui/panels/hud.py` - `_update_location_cache` czyta nazwę z locale zamiast
  wyświetlać `scene.current_map`; `_format_map_name` (hack na `Maze_01`) znika, bo
  labirynt dostaje normalny wpis w locale
- `scripts/validate_locale.py` albo `validate_world.py` - reguła „mapa bez nazwy
  wyświetlanej w PL i EN = ERROR"

Pułapka: zmiana języka w locie musi działać. Czytaj `settings.LANG` na żywo, nie przez
`from settings import LANG`, a panele odświeżaj przez `rebuild_i18n()` - ta klasa błędu
już raz w tym projekcie wystąpiła.

Kryterium: HUD pokazuje „Tawerna Brakująca Klepka" / „the Lost Cork Tavern", a
przełączenie języka w ustawieniach zmienia napis bez restartu. **Weryfikacja u autora.**

## Etap 3: nowe reguły walidatora - PRZED rename'ami (D1, D3, D6, D7)

Plik: `scripts/validate_world.py` (+ testy w `tests/`).

Nowe reguły:

1. **Konwencja nazwy instancji** (D1/D2): nazwa obiektu w `spawn_points` musi być równa
   kluczowi z `model_name`, opcjonalnie z sufiksem `_NN`. Poziom: ERROR.
2. **Drzwi donikąd** (D6): obiekt w `interactions` musi nazywać istniejącą mapę albo
   istniejący klucz skrzyni; własność `entry_point` musi wskazywać obiekt z warstwy
   `entry_points` **mapy docelowej**. Poziom: ERROR. Uwaga: walidator czyta dziś same
   nazwy obiektów (`load_map` zbiera `obj.get("name")`) - trzeba dołożyć czytanie
   własności, wzorem `_resolve_model_name`.
3. **Miejsce bez prefiksu mapy** (D3): wartość w `home`/`work`/`social`/`hobby` oraz
   `location:` w `routines.toml` musi mieć kształt `Mapa:miejsce`. Poziom: ERROR.
4. **Mapa bez muzyki**, **mapa nieosiągalna z żadnej warstwy `interactions`** oraz
   **plik w `assets/audio/music/` bez wpisu w manifeście** (D7, O4). Poziom: WARN.
   Trzecia reguła domyka asymetrię: SFX-y są dziś sprawdzane w obie strony, muzyka tylko
   w jedną (`check_audio_manifest`).

Po tym etapie `just validate-world` **świeci na czerwono** - to zamierzone. Walidator
jest siatką bezpieczeństwa dla etapu 4, więc musi powstać wcześniej.

## Etap 4: rename'y (D1, D2, D3, D4, D5, D9, D10)

Najpierw narzędzie (D10): `scripts/rename_entity.py` + recepta
`just rename-entity <stara> <nowa>`, zmieniające **wszystkie** źródła w jednym
przebiegu (`.tmx`, `.csv`, `.toml`, `config.json`) i kończące się wywołaniem
`validate_world`. To narzędzie przeżyje C02 - przyda się przy każdej zmianie nazwy w
treści Aktu 1.

Zakres (pełna tabela w dokumencie HTML):

- 27 obiektów `spawn_points` (20 zwierząt/potworów + 5 statystów humanoidalnych; 6 postaci
  z dialogami zostaje nietkniętych)
- krzywe `waypoints`: `Rob`, `Robin`, `Marry`, `Cat01` idą za nazwami instancji;
  `Bart_BCKP`/`Johny_BCKP` wracają do właściwych nazw + `enabled=false`
- `routines.toml`: `route:Rob` → `route:ROB`, `route:Robin` → `route:ROBIN`
- 10 komórek miejsc w `characters.csv` + 2 cele `location:` dostają prefiks klucza mapy
  (`VILLAGE:well`); 6 komórek z prefiksem `LOST_CORK_TAVERN:` jest już poprawnych
- mapy: `Village` → `VILLAGE`, `JacobsChamber` → `JACOBS_CHAMBER` wraz ze wszystkimi
  odwołaniami (nazwa pliku, audio, prefiksy miejsc, `interactions`, własność
  `entry_point`, punkty wejścia `JACOBS_CHAMBER_DOOR`)
- **`"Village"` jest zapisane na sztywno w kodzie** - `save_load.py` (2×), `main_menu.py`,
  `maze_utils.py`, plus skrypty i testy. Przy okazji wyciągnąć to do jednej stałej
  `settings.START_MAP` zamiast poprawiać w czterech miejscach
- podbicie wersji zapisu (D9/W4), żeby stare zapisy zostały jawnie odrzucone

## Kryteria akceptacji

- `just validate-world` - 0 błędów, ostrzeżenia tylko znane (dziś 5)
- `just test-unit` - komplet zielony (dziś 499 testów w 36 plikach)
- scenariusz agentowy z przewinięciem doby: `BART` i `JOHNY` docierają do
  `market_stall_*`, barman do `bar` (rutyny przeżyły rename)
- nowy zapis wczytuje się w komplecie; **stary jest widocznie odrzucony**, nie po cichu
  okrojony
- `just test-smoke` przechodzi (złota zasada dual-target)
- **HUD nigdy nie pokazuje klucza** - nazwa przyjazna w PL i EN, zmiana języka działa
  w locie (**weryfikacja u autora**)
- muzyka w tawernie gra po przemianowaniu map - **weryfikacja u autora**
- ściąga „gdzie używam jakiego klucza" trafia do `project/AGENTS.md`

## Pułapki

- **Nie zaczynaj od rename'ów.** Bez reguł walidatora z etapu 3 nie ma jak sprawdzić, czy
  zmiany trafiły we wszystkie źródła - zostaje granie po omacku. A bez etapu 2 rename map
  najpierw **pogorszy** to, co widzi gracz (klucz na HUD).
- **Nazwa mapy to nie tylko dana.** Siedzi w nazwie pliku `.tmx`, w zapisie
  (`PlayerState.map_name`), w kluczach muzyki, w prefiksach miejsc, w warstwie
  `interactions`, we własności `entry_point` **i w kodzie** (mapa startowa). To jedyna
  część C02 wychodząca poza dane do logiki.
- **Nazwa obiektu ≠ klucz configu w kodzie.** `NPC.name` to nazwa obiektu Tiled,
  `NPC.config_key` to klucz z `config.json` (`characters/npc.py:69` i `:105`). Dialogi i
  questy używają `config_key`; zapis używa `name`. Nie zamieniaj ich miejscami.
- **`_resolve_model_name` ma trzy warianty** i fallback na nazwę obiektu jest ostatni.
  Dziś nikt z niego nie korzysta (O3), ale jeśli ktoś doda spawn bez `model_name` na
  kaflu, rename takiego obiektu odczepi go od configu. Reguła 1 z etapu 2 to złapie.
- **Gołe nazwy miejsc są dziś dwuznaczne.** `bar`, `tables` i `badroom` istnieją
  równocześnie na `LOST_CORK_TAVERN` i na martwym `VillageHouse` - to kolejny powód, by
  etap 1 poprzedzał etap 3.
- **Nie ruszaj `CONF_ENTITIES_TO_STORE`** przy okazji. Wygląda na powiązaną listę kolumn,
  ale po usunięciu `main.py store` w B01 czytane są z niego **tylko klucze** - to martwe
  dane do sprzątnięcia osobno, nie kwestia spójności encji.

## Po zakończeniu

- ściąga do `project/AGENTS.md` (sekcja o kluczach encji) i do dokumentacji świata
- rozdział 5 raportu audytu (mapa przepływu encji) - aktualizacja konwencji
- odhaczenie C02 w [audyt.md](audyt.md)
