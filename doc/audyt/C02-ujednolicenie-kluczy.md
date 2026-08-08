# C02 - stopniowe ujednolicenie kluczy encji (Tiled ↔ config)

Priorytet: **P3** (Faza 4). Rozmiar: M. Zależności: **miękka** - korzysta z walidatora
z [C01](C01-validate-world.md) i z bramki zgodności zapisu z [B02](B02-polityka-wersji-save.md).

Status: **czeka na akceptację decyzji D1-D11**. Kod zaczyna się dopiero po niej.

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
| D5 | Nazwy map | `CamelCase` nazwa własna (`LostCorkTavern`) - **decyzja bardziej autora niż architekta** |
| D6 | `interactions` / `entry_points` | nowa reguła ERROR w C01 |
| D7 | Martwy `VillageHouse.tmx` | usunąć + reguły „mapa bez muzyki", „mapa nieosiągalna", „plik muzyki bez wpisu" jako WARN |
| D8 | Klucze skrzyń | opisują zawartość, nie mapę (`SMALL_CHEST_TAVERN`) |
| D9 | Stare zapisy | podbić wersję → **jawna odmowa** zamiast cichej utraty stanu |
| D10 | Sposób wykonania | skrypt `just rename-entity <stara> <nowa>` zmieniający wszystkie źródła naraz |
| D11 | Zakres podejścia | trzy osobne commity (naprawa → walidator → rename'y) |

**Dlaczego D1 = klucz configu, a nie „klucz małymi literami" z pierwotnej propozycji
audytu:** wariant „małymi" renamuje wszystkie 34 obiekty, w tym **6 postaci z dialogami**,
czyli dokładnie te, których stan w zapisie ma wartość (sentyment, przebieg rozmowy).
Wariant rekomendowany renamuje 27 obiektów, z czego **wszystkie 20 zmienianych postaci ma
`has_dialog=false` i nie ma grafu rozmowy** - ich stan w zapisie to pozycja i flaga
„zabity". Podział wychodzi idealnie czysty i to on rozstrzyga decyzję.

## Etap 1: dokończenie rename'u tawerny (D7, D8)

Sprzątanie po niedokończonej zmianie - idzie pierwsze i osobnym commitem.

Pliki:

- `project/assets/NinjaAdventure/maps/VillageHouse.tmx` - usunąć (lub przenieść poza
  `maps/`, jeśli autor wybierze D7=B)
- `project/config_model/audio.toml` - usunąć martwy wpis `VillageHouse`
- `project/config_model/chests.csv` + `config.json` - klucze skrzyń wg D8
- `project/assets/NinjaAdventure/maps/LOST_CORK_TAVERN.tmx` - nazwa obiektu skrzyni

Kryterium: `just validate-world` nie zgłasza nowych błędów, a muzyka w tawernie gra jak
dotąd. **Weryfikacja u autora** - sterownik `dummy` nie odtwarza dźwięku, więc headless
tego nie sprawdzi.

Osobna decyzja autora (O4): co zrobić z 4,78 MB nieużywanego audio. Nie blokuje etapu.

## Etap 2: nowe reguły walidatora - PRZED rename'ami (D1, D3, D6, D7)

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
jest siatką bezpieczeństwa dla etapu 3, więc musi powstać wcześniej.

## Etap 3: rename'y (D1, D2, D3, D4, D5, D9, D10)

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
- 10 komórek miejsc w `characters.csv` + 2 cele `location:` dostają prefiks mapy
- mapa `LOST_CORK_TAVERN` → `LostCorkTavern` wraz z odwołaniami (audio, prefiksy miejsc,
  `interactions`, `entry_point`)
- podbicie wersji zapisu (D9), żeby stare zapisy zostały jawnie odrzucone

## Kryteria akceptacji

- `just validate-world` - 0 błędów, ostrzeżenia tylko znane (dziś 5)
- `just test-unit` - komplet zielony (dziś 499 testów w 36 plikach)
- scenariusz agentowy z przewinięciem doby: `BART` i `JOHNY` docierają do
  `market_stall_*`, barman do `bar` (rutyny przeżyły rename)
- nowy zapis wczytuje się w komplecie; **stary jest widocznie odrzucony**, nie po cichu
  okrojony
- `just test-smoke` przechodzi (złota zasada dual-target)
- muzyka w tawernie gra - **weryfikacja u autora**
- ściąga „gdzie używam jakiego klucza" trafia do `project/AGENTS.md`

## Pułapki

- **Nie zaczynaj od rename'ów.** Bez reguł walidatora z etapu 2 nie ma jak sprawdzić, czy
  27 zmian trafiło we wszystkie źródła - zostaje granie po omacku.
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
