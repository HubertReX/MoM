# Cykl dobowy NPC + odnawianie zasobów handlarzy

Dokument decyzyjny z tabelami opcji: [cykl-dobowy-npc.html](_attachements/cykl-dobowy-npc.html)

Wersja 4: obsada rutyn przeniesiona z sekcji `[assign]` w `routines.toml` do kolumny `routine` w `characters.csv`.

## Kontekst

Dziś każdy NPC ma jedną statyczną łamaną z warstwy `waypoints` w Tiled (kluczowaną nazwą NPC, `scene.py:424`), po której chodzi w kółko bez końca. Doba trwa 96 sekund realnych, a jedyne co dzieje się na jej przełomie to `Scene.update_next_day()` (`scene.py:1446`) wołające `restock_items()` na każdym handlarzu.

Ten mechanizm jest zepsuty w trzech miejscach naraz:

1. **`sell_all_bought_items()` (`characters.py:298`) tylko dodaje pieniądze** - wartość wszystkiego, co gracz sprzedał, wpada do sakiewki handlarza i nigdy z niej nie wychodzi. Sakiewka rośnie w nieskończoność.
2. **`npc.model` to współdzielony obiekt configu** (`game.conf.characters[model_name]`), więc `model.money` jest globalne. Dotyczy to również gracza - `pick_up()` robi `self.model.money += value` na tym samym obiekcie. Dwa NPC-e z tym samym `model_name` dzielą jedną sakiewkę, a nowa gra po starej dziedziczy stan.
3. **Limit fizycznie nigdy się nie aktywuje** - patrz pomiar poniżej.

Cel: cykl życia postaci sterowany danymi, nie kodem, z czystym rozdziałem Tiled / konfiguracja / kod. Odnawianie handlarzy jest konsumentem tego samego haka przełomu dnia.

### Pomiar ekonomii

| Wielkość | Wartość |
|---|---|
| Udźwig gracza | 15 kg, 6 slotów |
| Najlepsza gęstość klejnotu (`gem_small_orange`) | 60 zł/kg |
| Maksymalny łup w klejnotach | ~900 zł |
| Sakiewka JOHNY'ego | 3000 zł |

Sakiewka jest 3,3x za bogata, żeby cokolwiek dławić - gracz fizycznie nie jest w stanie jej wyczerpać. Dlatego plan skupia się na architekturze, a liczby zostają w CSV jako domena autora.

Obserwacja poboczna, poza zakresem zadania: klejnoty "big" są per kilogram gorsze od "small" w każdym kolorze, więc gracz optymalizujący zł/kg zostawia duże klejnoty na podłodze.

### Nie-cele, świadomie

- Brak symulacji potrzeb (głód, energia, nastrój) i relacji między NPC-ami. To nie ma być The Sims.
- Brak dynamicznych drzwi i wnętrz budynków.
- Brak kolejkowania i budżetowania A* dla systemu, który jeszcze nie istnieje.
- Brak strojenia liczb balansowych.

## Trójpodział odpowiedzialności

| Warstwa | Odpowiada za | Nośnik | Kto edytuje |
|---|---|---|---|
| Tiled | *Gdzie* - nazwane punkty na mapie i trasy | warstwa obiektów `places` (same nazwy) + istniejąca `waypoints` | edytor map |
| Postacie | *Czyje jest które miejsce i czyj jest który rytm* - destynacje i rutyna per postać | kolumny `home`, `work`, `social`, `hobby`, `routine` w `characters.csv` | istniejący pipeline CSV |
| Rutyny | *Kiedy i co* - rytm dnia wspólny dla wielu postaci | `project/config_model/routines.toml` | ręcznie, w edytorze tekstu |
| Kod | *Jak* - generyczny wykonawca, zero logiki per-NPC | `project/npc_schedule.py` | Python |

Test poprawności podziału:

- "kowal ma chodzić na obiad o 12 zamiast o 13" - jedna liczba w TOML-u
- "nowe miejsce w wiosce" - jeden nazwany obiekt w Tiled
- "ten NPC ma pracować gdzie indziej" - jedna komórka w `characters.csv`
- "cała wioska ma wstawać godzinę wcześniej" - jedna liczba w TOML-u
- "ten NPC ma żyć rytmem farmera" - jedna komórka w `characters.csv`

Jeśli któreś wymaga Pythona, podział jest zły.

### Format konfiguracji: TOML

Nie YAML. `settings.py:5-7` już importuje `tomllib` z fallbackiem na `tomli` dla weba, `tomli==2.2.1` jest w `requirements.txt`, a `load_ui_strings()` (`settings.py:130`) to gotowy wzorzec ładowania do skopiowania. PyYAML byłby nową zależnością doinstalowywaną także w pygbag. TOML spełnia zasadę "JSON tylko maszynowo generowany" i nie kosztuje nic.

Rutyny nie idą do `characters.csv` - zagnieżdżona lista slotów nie mieści się w płaskiej kolumnie, a CSV jest generatorem `config.json`.

## Model danych

### Gdzie wiąże się "które miejsce należy do której postaci"

W wersji 2 miejsca miały w Tiled własności `tag` i `owner`. To nie działa, bo **ta sama karczma jest miejscem pracy barmana i miejscem odpoczynku wszystkich pozostałych**. Rola miejsca nie jest własnością obiektu na mapie - jest relacją między postacią a miejscem, a własność obiektu potrafi wyrazić tylko jedną odpowiedź.

Rozwiązanie: **destynacje w `characters.csv`, obiekty w Tiled tylko nazwane.**

| Kolumna | Znaczenie | Przykład |
|---|---|---|
| `home` | gdzie śpi | BARMAN: `tavern`, JOHNY: `house_3` |
| `work` | gdzie pracuje | BARMAN: `tavern`, JOHNY: `market_stall_1`, FARMER: `field_north` |
| `social` | gdzie spędza przerwę | JOHNY: `tavern`, FARMER: `well` |
| `hobby` | miejsce charakterystyczne dla postaci | JOHNY: `pier`, KOWAL: `shrine` |
| `routine` | którym rytmem dnia żyje | JOHNY: `townsfolk`, FARMER: `farmer` |

Karczma rozwiązana: BARMAN ma `work = tavern`, JOHNY ma `social = tavern`. Jeden obiekt w Tiled, dwie różne role, zero duplikatów. Rutyna mówi tylko "o 13:00 idź do swojego `social`" i nie wie, czym to jest dla konkretnej postaci.

Jedna postać ma najwyżej jedno miejsce danego typu. Lista typów jest zamknięta.

#### Kolumna `routine` zamiast sekcji `[assign]` (zmiana planu)

Pierwotnie przypisanie rutyny do postaci siedziało w `routines.toml`, w sekcji `[assign]` kluczowanej nazwą obiektu ze `spawn_points`. Zostało przeniesione do kolumny `routine` w `characters.csv`, obok czterech destynacji, z którymi rutyna i tak współpracuje. Powód jest ten sam, dla którego destynacje nie siedzą w Tiled: **całe "kto, co, gdzie" jednej postaci ma się czytać z jednego wiersza.** Przy `[assign]` odpowiedź na "dokąd chodzi kowal i kiedy" wymagała skakania między dwoma plikami i porównywania dwóch różnych przestrzeni nazw.

`routines.toml` trzyma teraz **same rutyny** - jest katalogiem rytmów, a nie obsadą.

Cena, świadoma: klucz nie jest już nazwą egzemplarza ze `spawn_points`, tylko nazwą modelu, więc **wszystkie kopie tego samego modelu na mapie żyją jednym rytmem**. Dziś to nic nie kosztuje (każdy model humanoidalny stoi w jednym egzemplarzu), a gdyby kiedyś było trzeba, `NpcRuntime.routine_key` jest polem per instancja i zapisywanym - da się je nadpisać po spawnie, bez wracania do drugiego pliku obsady.

Walidacja przeniosła się razem z danymi: `parse_routines` nie ma już czego sprawdzać w `[assign]` (zostaje tylko ostrzeżenie, gdy stara sekcja została w pliku - inaczej wyglądałaby na działającą), a nieznany klucz z CSV wyłapuje `Scene.load_NPCs` przy spawnie: ostrzeżenie i degradacja do "brak rutyny". Sam fakt, że oba pliki łączy goły string, pilnuje test `test_every_routine_named_in_characters_csv_exists`.

### Warstwa `places` w Tiled

Skoro role przeniosły się do CSV, warstwa upraszcza się do **nazwanych punktów** - żadnych custom properties, żadnego `tag`, żadnego `owner`.

| Element | Rola |
|---|---|
| nazwa obiektu | jedyne, co niesie obiekt: `tavern`, `well`, `market_stall_1`, `house_3`, `field_north`. Musi być unikalna w obrębie mapy |
| pozycja | gdzie NPC ma dojść; dla `sleep` to próg, na którym następuje zanik |
| `radius` (opcjonalne) | jedyna dopuszczona własność - nadpisuje `wander_radius` z `[defaults]` dla tego miejsca |

Istniejąca warstwa `waypoints` zostaje bez zmian i zyskuje drugie życie jako trasa dla aktywności `patrol`.

### Trzy warianty `at`

| Zapis | Rozwiązanie | Do czego |
|---|---|---|
| `at = "type:work"` | kolumna `work` postaci -> nazwa obiektu -> pozycja | domyślny sposób; to on czyni rutynę uniwersalną |
| `at = "location:well"` | wprost nazwa obiektu z warstwy `places` | furtka na wyjątki i miejsca wspólne dla wszystkich |
| `at = "route:patrol_north"` | nazwana łamana z warstwy `waypoints` | patrole; jedyny wariant, w którym celem jest trasa, nie punkt |

Fallback: gdy `type:X` nie jest zdefiniowane dla postaci (pusta komórka), NPC zostaje tam, gdzie jest - krok degraduje się do `idle` w bieżącym miejscu, plus ostrzeżenie w trybie debug. Niekompletne dane nigdy nie wywalają gry, a brak domów dla wszystkich nie blokuje wdrożenia.

### `routines.toml`

Kroki rutyny to zwięzła tablica tabel `[[routine.X.slot]]`. Wariant z nazwanymi krokami (`morning`, `lunch`) dawał czytelną etykietę, ale wymagał pełnego `[routine.townsfolk.slots.morning]` w każdym nagłówku - etykieta nie jest warta tego prefiksu. To, czym krok jest, i tak widać z pól `from` i `at` tuż pod nim.

Naturalny odruch, czyli `[[routine.townsfolk.slots]]` a pod nim `[[morning]]`, parsuje się bez błędu, ale buduje złą strukturę. Sprawdzone pod `tomllib`:

```text
{'routine': {'townsfolk': {'slots': [{}]}},
 'morning': [{'from': '06:30'}]}
```

`[[morning]]` to nagłówek bezwzględny, nie zagnieżdżony - ląduje na najwyższym poziomie dokumentu, odłączony od rutyny, a `slots` zostaje pustą listą. TOML nie ma zagnieżdżania przez wcięcie, ścieżkę zawsze pisze się w nagłówku w całości.

**Kolejność kroków bierze się z pola `from`, nie z kolejności w pliku.** Przestawienie bloków czy dopisanie kroku w środku nigdy niczego nie psuje. Sortowanie po `from` obsługuje też noc przechodzącą przez północ - u strażnika krok o 02:00 jest aktywny do 06:00, a o 23:00 aktywny jest krok wieczorny.

```toml
# Rutyny NPC. Ten plik trzyma SAME rutyny - kto ktora ma, mowi kolumna
# `routine` w characters.csv.
#
# `at` ma trzy warianty:
#   type:<typ>       -> kolumna `home`/`work`/`social`/`hobby` w characters.csv
#                       wskazuje nazwe obiektu z warstwy `places` w Tiled.
#                       To on czyni rutyne uniwersalna - kazda postac idzie
#                       "do swojego" miejsca danego typu.
#   location:<nazwa> -> wprost nazwa obiektu z warstwy `places` (wyjatki,
#                       miejsca wspolne dla wszystkich)
#   route:<nazwa>    -> nazwana lamana z istniejacej warstwy `waypoints`
#
# Kolejnosc wykonania bierze sie z pola `from`, nie z kolejnosci w pliku.

[defaults]
wander_radius       = 3     # promien mikro-wedrowki, w kaflach
slot_jitter_minutes = 20    # +/- , deterministycznie z hasha nazwy NPC


# =====================================================================
#  townsfolk - kupiec, kowal, barman: dom, praca, przerwa, praca, dom
# =====================================================================

[[routine.townsfolk.slot]]
from     = "06:30"
at       = "type:home"
activity = "idle"

[[routine.townsfolk.slot]]
from     = "08:00"
at       = "type:work"
activity = "stand"

[[routine.townsfolk.slot]]
from     = "13:00"
at       = "type:social"
activity = "wander"

[[routine.townsfolk.slot]]
from     = "14:00"
at       = "type:work"
activity = "stand"

[[routine.townsfolk.slot]]
from     = "18:30"
at       = "type:hobby"
activity = "wander"

[[routine.townsfolk.slot]]
from     = "20:00"
at       = "type:home"
activity = "sleep"


# =====================================================================
#  farmer - wstaje przed switem, dluga praca w polu, wczesniej spi
# =====================================================================

[[routine.farmer.slot]]
from     = "04:30"
at       = "type:work"
activity = "stand"

[[routine.farmer.slot]]
from     = "11:00"
at       = "location:well"      # wspolna studnia, nie "swoja" - stad location:
activity = "idle"

[[routine.farmer.slot]]
from     = "12:00"
at       = "type:work"
activity = "stand"

[[routine.farmer.slot]]
from     = "18:00"
at       = "type:social"
activity = "wander"

[[routine.farmer.slot]]
from     = "21:00"
at       = "type:home"
activity = "sleep"


# =====================================================================
#  guard - patrol dzienny, patrol wieczorny, krotka noc
# =====================================================================

[[routine.guard.slot]]
from     = "06:00"
at       = "route:patrol_north"
activity = "patrol"

[[routine.guard.slot]]
from     = "18:00"
at       = "route:patrol_south"
activity = "patrol"

[[routine.guard.slot]]
from     = "02:00"
at       = "type:home"
activity = "sleep"
```

Zmiany względem wersji 2:

- Rutyna `farmer` **przywrócona** - ma inny rytm, nie tylko inne miejsce pracy: wstaje o 04:30, ma jedną długą przerwę w południe zamiast dwóch i kładzie się o 21:00. Scalenie jej z `townsfolk` w v2 było błędem.
- `at` **rozszerzone** o jawne prefiksy `type:` / `location:` / `route:`. Bez nich nie było widać, czy chodzi o typ destynacji, czy o konkretny obiekt.
- `tag` i `owner` w Tiled **usunięte** - zastąpione kolumnami w `characters.csv`.
- `fade_duration` usunięte już w v2 - nie robiło nic, a jako stała renderowania należy do `settings.py`.
- Sekcja `[assign]` **usunięta** - obsada przeniesiona do kolumny `routine` w `characters.csv` (patrz wyżej).

### Aktywności

Pięć wartości, nic więcej. Każda mapuje się na kod, który już istnieje - żadna nie wymaga nowego systemu ruchu.

| Aktywność | Zachowanie | Co reużywa |
|---|---|---|
| `sleep` | dojście do progu miejsca, zanik, wypisanie z aktualizacji do rana | istniejące grupy sprite'ów |
| `stand` | stanie w miejscu; dla handlarza to godziny otwarcia | `Idle` / `Bored` z `npc_state.py` |
| `wander` | losowy spacer w promieniu wokół miejsca | `get_random_safe_pos()`, `characters.py:597` |
| `patrol` | podążanie nazwaną łamaną | `follow_waypoints()` |
| `idle` | stanie + emotka | `EmoteSprite` |

Status: **wszystkie pięć zrobione** (kroki 6-7). `update_schedule()` rozpadło się na dwie części, bo to dwa różne rytmy: `_begin_slot()` odpala raz, na granicy slotu (rozwiązuje destynację, woła A* - drogo i rzadko), a `_continue_slot()` co klatkę, żeby zauważyć *dotarcie* (tanie, bo wychodzi natychmiast, gdy postać jeszcze idzie).

Jak każda z nich wyszła:

- **`sleep`** - zasypianie to opuszczenie `scene.group`: koniec rysowania, animacji, fizyki i szukania drogi. Robi to `Scene.update_sleepers()`, **nie** sama postać: sprite wypisujący się z grupy, po której właśnie leci `update()`, to rodzaj rzeczy, która działa do czasu. Postać wyraża tylko chęć (`wants_to_sleep`), scena zamienia ją w fakt. Śpiący **zostaje** w `scene.NPCs`, bo z tej listy budowany jest zapis (`_build_map_states`) - wypisanie go stamtąd gubiłoby sakiewkę handlarza na noc. Dwie pętle, które wpadałyby na niewidzialne ciało (kolizja gracza i "kto jest blisko, żeby pogadać"), pomijają śpiących jawnie. Śpiący nie dostaje własnego update'u, więc nigdy by się nie obudził - dlatego `update_sleepers()` odpytuje mu harmonogram.
- **`patrol`** - `route:` oddaje nazwaną łamaną prosto do starej pętli waypointów. `target` zostaje zerem, bo to dokładnie ta flaga, która każe `follow_waypoints()` zawinąć na początek zamiast się zatrzymać. Zero nowego kodu ruchu, dokładnie jak zakładał plan.
- **`wander`** - kluczowa jest **pauza** (`WANDER_PAUSE`, 3 s) i to, że dryf liczy się od **kotwicy** (miejsca ze slotu), nie od poprzedniego kroku. Bez pauzy postać przelosowuje cel w tej samej klatce, w której dotarła, i ślizga się po okolicy zamiast w niej stać. Bez kotwicy dostajemy błądzenie losowe, które po kilku minutach wyprowadza postać z wioski.
- **`idle`** - jedna emotka na dotarcie, nie co klatkę.
- **`stand`** - bez zmian, działało od kroku 5.

### Parametry żywości

Dwa do dodania, trzeci już istnieje:

1. **`slot_jitter_minutes`** - każdy NPC przesuwa granice slotów o deterministyczny offset z hasha nazwy. Nic nie jest zsynchronizowane, wioska nie przeskakuje o 8:00. Około 80% wrażenia życia za ~5 linii, a przy okazji rozkłada w czasie przeliczanie tras.
2. **`wander_radius`** - postać dryfuje po swoim miejscu zamiast stać jak słup.
3. **Zróżnicowana prędkość** - już istnieje (`speed = random.choice([speed_walk, speed_run])`, `characters.py:205`).

## Architektura kodu

### `NpcRuntime` - fundament

Status: **zrobione** (commit `404d274`). Zrealizowane jako wariant hybrydowy, po tym jak przy implementacji wyszły dwie rzeczy nieznane w chwili pisania planu.

Co wyszło w trakcie:

- Bug dotyczy nie tylko `money`, ale też **`health`** - wszystkie potwory tego samego typu czerpały z jednej puli. Objawem nie było "giną naraz" (bo `oponent.die()` jest celowo zakomentowane, a śmierć następuje po wygaśnięciu ogłuszenia, którego timer jest per instancja), tylko drugi potwór ginący od jednego ciosu.
- **Przedmioty i skrzynie już kopiują swój config per instancja** - `copy.copy` w `scene.py:372`, `copy.deepcopy` w `scene.py:667`. NPC był jedynym, który tego nie robił, więc naprawa poszła istniejącym wzorcem, a nie nowym.

Co powstało:

- `NPC.__init__` robi `copy.deepcopy(game.conf.characters[model_name])`. Głęboka, bo `Character` niesie listy (`items`, `allowed_zones`) i słownik (`disposition`), a na desktopie jest modelem pydantic. Naprawia przy okazji złoto gracza, bo `Player` dziedziczy po `NPC`.
- `project/npc_runtime.py` - `NpcRuntime` na stan, który celowo **nie** trafia do modelu configu, bo ten jest zdefiniowany dwa razy (`config.py` dla weba, `config_pydantic.py` dla desktopu) i każde nowe pole trzeba by dublować. Na razie `routine_key` i `stock`.
- `NPCState` dostaje pole `runtime` z wartością domyślną, więc stare zapisy się wczytują. Zapis i odczyt przez `deepcopy`, żeby snapshot nie był aliasem żywego obiektu.
- Usunięta płytka kopia modelu w `_apply_npc_states` - łatała objaw tylko przy wczytywaniu.

Czego świadomie **nie** zrobiono: przenoszenia `health`, `max_health`, `money` i `damage` do `NpcRuntime`. To 78 odwołań w 9 plikach, w tym kod walki i zapisu, przy zerowym zysku zachowania - kopia już daje każdej postaci własne wartości. Config zostaje nietknięty, więc `conf.characters[k].money` jest gotową wartością bazową dla regeneracji sakiewki.

Skutek dla rozgrywki: liczba ciosów potrzebnych do zabicia drugiego i kolejnych potworów tego samego typu **wraca do wartości ze zdrowia w CSV**. To nie regresja, tylko powrót do zamierzonych liczb.

Szczegóły z dowodem empirycznym: [wspoldzielony-config-npc.html](_attachements/wspoldzielony-config-npc.html)

### `npc_schedule.py` - dostawca celu, nie drugi kontroler

Status: **zrobione**, krok 5 w wariancie "kod bez mapy" - wszystko gotowe, czeka na punkty w Tiled i uzupełnione kolumny w CSV. Do tego czasu nic się nie zmienia w zachowaniu: każdy krok rutyny rozwiązuje się do "brak destynacji", a NPC zostaje przy swojej starej łamanej.

Poprawka do planu: **FSM z `npc_state.py` nie jest kontrolerem ruchu.** To maszyna stanów *animacji* - `get_new_state()` czyta `character.vel` i flagi, żeby wybrać klatki. Ruchem steruje `NPC.movement()` -> `find_path()` (A*) -> `follow_waypoints()`. Harmonogram wpina się więc w `movement()`, a nie w FSM, ale zasada z planu zostaje spełniona: `update_schedule()` ustawia najwyżej `self.target` i woła istniejący pathfinder, nigdy nie dotyka `vel`.

Detale, które wyszły w implementacji:

- **Obsada jest kluczowana nazwą modelu z `characters.csv`** (kolumna `routine`), więc kopie tego samego modelu dzielą rytm - patrz "Kolumna `routine` zamiast sekcji `[assign]`" wyżej. Pierwsza implementacja kluczowała ją nazwą obiektu ze `spawn_points`; przeniesienie do CSV to świadoma wymiana tej granulacji na czytelność jednego wiersza.
- **Plan zakładał nieistniejące postacie.** Na `Village.tmx` nie ma `KOWAL`, `BARMAN`, `FARMER` ani `STRAZNIK`; są `Johny`, `Bart`, `Marry`, `Rob`, `Robin`, `HAMMER_HOAXHEART` (kowal), `BARMAN_ABSINTHRAYNER` i reszta dialogowych. Kolumna `routine` obsadza na start tylko czwórkę, która **i tak dziś stoi w miejscu** (Johny i Bart mają łamane odłożone w Tiled jako `Johny_BCKP` / `Bart_BCKP`), żeby włączenie rutyn nie zabrało ruchu nikomu, kto dziś chodzi. `farmer` i `guard` zostają szablonami bez obsady.
- **`update_schedule()` działa tylko na granicy slotu.** Przeliczanie trasy co klatkę restartowałoby A* w kółko i NPC nigdy by nie dotarł. Zapamiętany ostatni slot + jitter per postać rozkładają te przeliczenia w czasie.
- **Aktywności poza `stand` na razie nic nie robią** - `route:` (patrol) i reszta kończą na "zostaw postać w spokoju". To uczciwsze niż udawanie, że działają.

Harmonogram nie steruje ruchem. Ustawia `npc.goal = (place, activity)`, a istniejący FSM z `npc_state.py` decyduje jak tam dotrzeć. Dwa systemy piszące do `npc.vel` to gwarantowany bug "NPC drga w drzwiach".

- `Talk` jest stanem pochłaniającym - zmiana slotu w trakcie dialogu jest kolejkowana i stosowana po zamknięciu panelu. Inaczej handlarz odchodzi w środku transakcji, a `TradePanel` zostaje z wiszącą referencją (`trade.py:120`).
- Godziny otwarcia sprawdzane tylko przy otwarciu panelu, nigdy co klatkę.

### Hak przełomu dnia

`Scene.update_next_day()` przechodzi na `apply_days(n)`. Powrót z wyprawy trwającej trzy doby ma zadziałać jednym wywołaniem, więc każdy krok dzienny musi być funkcją stanu i liczby dni, a nie pętlą po dniach.

Losowanie musi być zaziarnione: `Random(hash((save_seed, day, npc_name)))`. Inaczej gracz przeładowuje zapis, aż handlarz będzie miał to, czego szuka. To także warunek konieczny zapowiadania popytu na jutro (opcja N1).

Status: **zrobione**, krok 3. `project/world_rng.py` (`stable_hash`, `day_rng`, `new_world_seed`) plus `Scene.world_seed` i `Scene.day_rng(name, day_offset)`. Seed jest losowany raz na nową grę i wędruje w zapisie (`SaveGame.world_seed`); stare zapisy dostają 0 - kiepski seed, ale **stały**, bo losowanie świeżego przy każdym wczytaniu byłoby dokładnie tą dziurą, którą to zamyka.

Poprawka do planu: **`hash()` z planu nie działa.** Python soli hashowanie stringów per proces (`PYTHONHASHSEED`), więc `hash((4242, 3, "JOHNY"))` daje inną liczbę po każdym starcie gry - roll byłby stabilny w obrębie sesji i przelosowywalny przez restart, czyli ta sama dziura, tylko wolniejsza. Zweryfikowane empirycznie, dwa procesy: `-8392815750115326562` vs `-2251698939627118296`. Stąd `zlib.crc32` po bajtach UTF-8, przypięte testem odpalającym dwa podprocesy z różnym `PYTHONHASHSEED`.

Uwaga o zakresie: to na razie **sam szkielet, bez konsumenta**. W przełomie dnia nie ma dziś nic losowego (`restock_items()` odtwarza listę z configu), więc `day_rng` czeka na pulę asortymentu i na popyt z N1. Zbudowane teraz, bo plan słusznie stawia je przed krokami 4-7 - dorabianie ziarna po fakcie oznaczałoby unieważnienie zapisów.

Klawisz `next_day` zabramkowany, ale na `SHOW_DEBUG_INFO`, **nie** na `IS_DEBUG_MODE` - ta druga to zahardkodowane `False` w `settings.py:318`, którego nic nigdy nie ustawia, więc dosłowne wykonanie planu zabiłoby klawisz także we własnym playteście. `SHOW_DEBUG_INFO` jest przełączalne w locie (`` ` `` / `Z`) i jest dokładnie tym, czym panel pomocy już teraz bramkuje wiersz "N" - czyli pomoc przestaje kłamać. Do tego `USE_AGENT_CONTROL`, żeby testy agentowe dalej mogły przeskoczyć dobę. Przy okazji klawisz podbija teraz `self.day`; wcześniej odpalał przełom dnia na dobie, która - dla wszystkiego, co czyta zegar - nigdy się nie wydarzyła.

### Odnawianie sakiewki: regeneracja do limitu

Status: **zrobione**, krok 2. `Scene.update_next_day()` to teraz `Scene.apply_days(n)`, a po stronie NPC są dwie metody: `regenerate_money(days)` i przepisane `restock_items()`. `sell_all_bought_items()` usunięte w całości - to ono było źródłem nieskończonego wzrostu sakiewki.

Co wyszło przy implementacji, a nie było w planie:

- **`restock_items()` nie zerowało `total_items_weight`.** Lista `items` szła do kosza, ale bieżąca waga jest osobnym licznikiem prowadzonym przez `pick_up()` / `drop_item()`, więc każdy świt dokładał kolejny komplet towaru do sumy. Po kilku dobach handlarz miał nominalnie ponad `max_carry_weight` trzymając dwa klejnoty - i przestawał kupować na stałe. To dokładnie ten sam objaw, przed którym plan chronił wyrzucaniem skupionego towaru, tylko drugą drogą. Naprawione, przypięte testem.
- **`money_cap` = 0 znaczy "użyj `money` z CSV".** Dzięki temu krok 2 nie czeka na regenerację `characters.csv` (krok 4) - dopóki kolumna jest pusta, sufitem jest kwota startowa z configu, czyli 3000 zł dla JOHNY'ego. Sufit czyta się z `game.conf.characters[config_key].money`, bo `self.model` to własna kopia postaci i jej `money` jest stanem bieżącym, nie bazą.

```text
money = min(money_cap, money + n_dni * round(money_cap * money_regen_pct))
```

Regeneracja liniowa z sufitem jest domknięta wzorem, więc pozostaje N-bezpieczna - powrót po trzech dobach to jedno wywołanie, nie pętla. (Procent składany od aktualnego stanu nie miałby tej własności.)

Przykład dla JOHNY'ego, `money_cap` 3000, regeneracja 25% czyli 750/dobę, po opróżnieniu sakiewki do zera:

| Dzień | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Sakiewka | 0 | 750 | 1500 | 2250 | 3000 |

Pełna odbudowa zajmuje cztery doby. To jest ten delikatny nacisk na sukcesywne zdobywanie i sprzedawanie - gracz, który opróżni handlarza, ma powód, żeby przez kilka dni sprzedawać komuś innemu albo mniej naraz.

Parametry w CSV: `money_cap`, `money_regen_pct` (domyślnie 0,25). Stan bieżący `money` żyje w `NpcRuntime` i w zapisie, nie w configu.

Dodatkowo: przelosowanie asortymentu o świcie **wymazuje towar skupiony od gracza**. Bez tego `max_carry_weight` handlarza zapycha się złomem gracza między sesjami i handlarz na stałe przestaje kupować.

### Sprzedaż: bez zmian mechaniki

Handel jest i zostaje **po jednej sztuce** na naciśnięcie klawisza (`characters.py:1494-1518` woła `drop_item()`, cena liczona dla jednego przedmiotu).

To jest dobra wiadomość: handel po 1 sztuce plus skończona sakiewka *już strukturalnie jest* stopniową sprzedażą. Gracz klika, patrzy jak sakiewka topnieje, i w pewnym momencie kolejne kliknięcie nie przechodzi. Nie trzeba żadnej nowej mechaniki - trzeba tylko, żeby sakiewka faktycznie się kończyła i żeby gracz widział dlaczego.

| Element | Stan | Do zrobienia |
|---|---|---|
| Sakiewka handlarza w panelu | `_draw_merchant_stats` (`trade.py:131`) już rysuje pieniądze i wagę | gotowe |
| Powód odmowy | trzy osobne powiadomienia: pieniądze, waga, sloty (`characters.py:1302-1341`) | gotowe |
| Sufit sakiewki widoczny | `_draw_merchant_stats` pokazuje `money/money_cap`, na wzór wiersza z wagą | gotowe |

## Brakujące kolumny w `characters.csv`

Zgłoszone jako sprawa poboczna, ale wiązanie destynacji i tak wymaga dopisania kolumn do tego pliku, więc trafia do planu.

**Nie brakuje kodu - plik jest po prostu nieaktualny.** `import_entities.py` jest symetryczny: `_export_csv` zbiera nazwy kolumn ze wszystkich encji w sekcji (`for v in section.values(): for k in v`), więc pole obecne u choćby jednej postaci trafia do nagłówka. `characters.csv` ma dziś 17 kolumn, a ponowny eksport wygeneruje 24.

| Kolumna | Typ | Kto ją dziś ma w `config.json` |
|---|---|---|
| `money` | int | 12 postaci: Player, JOHNY, FRED, BART, ROB, ROBIN, MARRY, HAMMER_HOAXHEART, BARMAN_ABSINTHRAYNER, CLAPBACK_SWORD, POTIONEER_PUZZLEMINT, MADAME_SARCASMIA |
| `items` | lista | Player, JOHNY, BART, SNAKE_01, MADAME_SARCASMIA |
| `is_merchant` | bool | JOHNY, BART |
| `tradeable_items_types` | lista | JOHNY |
| `max_carry_weight` | float | JOHNY, BART |
| `allowed_zones` | lista | 11 zwierząt: FISH_RED, DOG_ORANGE, DOG_PURPLE, CHICKEN_*, PIG, COW, HORSE, FROG |
| `max_health` | int | nie zgłoszone, ale też brakuje |

Jak to zrobić:

```bash
just import-entities --export
```

Status: **zrobione**, krok 4. `characters.csv` ma teraz 31 kolumn zamiast 17 (7 brakujących + `money_cap`, `money_regen_pct` + 4 destynacje + `routine`). `chests.csv` przy okazji odzyskał `random_items` i `items`, a `maze_configs.csv` listy po przecinku zamiast JSON-a.

Dwie rzeczy trzeba było naprawić w eksporterze, bo bez nich krok się nie domykał:

- **Eksport widział tylko pola, które ktoś już ma w `config.json`.** `_export_csv` zbierało nazwy kolumn z danych, więc pole dodane do modelu z wartością domyślną (czyli takie, którego nikt jeszcze nie ustawił - dokładnie sześć nowych) nigdy nie dostałoby kolumny, a kolumna dopisana ręcznie zniknęłaby przy następnym eksporcie. Teraz nagłówek to suma "co jest w danych" i "co deklaruje model" (`Character.model_fields`), więc nowe pole modelu jest jeden eksport od bycia edytowalnym. Import bez zmian - dalej czyta te kolumny, które plik akurat niesie.
- **Kolejność kolumn brała się z kolejności wstawiania w `config.json`, czyli z przypadku.** W `items.csv` wylądowałoby `key;type;value;weight;...`, z nazwami gdzieś w środku wiersza - w pliku edytowanym ręcznie nie da się wtedy powiedzieć, czego dotyczy linijka, bez liczenia średników. `LEADING_COLUMNS = ("key", "name_EN", "name_PL")` przypina tożsamość na przód; reszta zachowuje dotychczasową kolejność.

Uwaga na przyszłość, poza zakresem: **zacommitowany `config.json` nie jest w formacie, który produkuje którykolwiek importer.** W repo jest wcięcie 2-spacjowe ze zwartymi tablicami, a `import_entities.py`, `dialog/markdown_importer.py` i `quest/markdown_importer.py` piszą `indent=4`. Pierwszy lepszy `just import-*` przeformatuje cały plik - 4000 linii diffu przy zerowej zmianie treści. Tutaj przywróciłem plik po weryfikacji round-tripu, żeby nie wciągać tego do commita, ale to wybuchnie przy następnym imporcie dialogów.

Round-trip zweryfikowany: `--export` a potem import daje `config.json` semantycznie identyczny (`a == b` po `json.load`). Eksport wypisuje pustą komórkę dla pola, którego postać nie ma, a import pomija puste komórki (`if raw == "": continue`), więc model użyje wartości domyślnej - puste zostaje puste. Mimo to pierwszy przebieg przepisuje cały plik (kolejność kolumn, sortowanie kluczy, formatowanie list), więc diff będzie duży.

#### Kolumny listowe: przecinek zamiast JSON-a

Dziś `_export_csv` zapisuje listy jako JSON w komórce (`["water","shore"]`). To jedyne miejsce, gdzie JSON wraca tylnymi drzwiami do pliku edytowanego ręcznie, i jest nieprzyjemne w edycji. Zmiana: listy zapisywane jako wartości rozdzielone przecinkiem.

| Kolumna | Dziś | Po zmianie |
|---|---|---|
| `allowed_zones` | `["water","shore"]` | `water,shore` |
| `tradeable_items_types` | `["gem"]` | `gem` |
| `items` | `["life_pot","life_pot","fish"]` | `life_pot,life_pot,fish` |

Separator kolumn to średnik, więc przecinek jest wolny i nie trzeba niczego cytować. Po stronie odczytu `parse_value` przyjmuje oba zapisy: najpierw próba JSON (żeby istniejące komórki dalej działały), a gdy to nie jest lista - podział po przecinku z obcięciem białych znaków. Pusta komórka nadal oznacza "nie nadpisuj".

Recepta `import-entities` dostaje przelot argumentów, więc eksport to `just import-entities --export` - bez mnożenia recept.

Do tego samego pliku dochodzą cztery kolumny destynacji: `home`, `work`, `social`, `hobby`, oraz piąta - `routine` - z kluczem rutyny. Trzeba je dodać także do modelu postaci (`config.py` i `config_pydantic.py`) z domyślną wartością pustego stringa, żeby importer je rozpoznał.

## Pliki

Nowe:

- `project/world_rng.py` - zaziarnione losowanie świata (zrobione)
- `project/config_model/routines.toml`
- `project/npc_schedule.py`
- warstwa obiektów `places` w mapie Tiled - nazwane punkty

Modyfikowane:

- `project/characters.py` - `NpcRuntime`, `goal`, przepisanie `restock_items` / `sell_all_bought_items`
- `project/npc_state.py` - `Talk` pochłaniający, konsumpcja `npc.goal`
- `project/scene.py` - wczytanie warstwy `places` (obok `waypoints`, ~`:424`), `update_next_day` -> `apply_days(n)`, gating klawisza debug za `IS_DEBUG_MODE`
- `project/save_load/models.py` + `manager.py` - nowe pola `NPCState`, domyślne wartości dla starych zapisów
- `project/ui/panels/trade.py` - sakiewka jako `bieżąca / sufit`
- `project/config_model/config.py` + `config_pydantic.py` - `money_cap`, `money_regen_pct`, pula asortymentu, cztery kolumny destynacji + `routine`
- `project/config_model/characters.csv` - regeneracja przez `--export` (7 brakujących kolumn) + 4 kolumny destynacji + `routine`
- `project/config_model/import_entities.py` - listy po przecinku, odczyt tolerujący też stary JSON
- `Justfile` - przelot argumentów w `import-entities`

## Kolejność budowy

1. ~~`NpcRuntime` + rozdzielenie od configu + pola w zapisie.~~ **Zrobione**, commit `404d274`.
2. ~~Regeneracja sakiewki + sakiewka jako `bieżąca / sufit` w panelu.~~ **Zrobione**, plus naprawa niezerowanej wagi w `restock_items` i testy `tests/test_merchant_economy.py`.
3. ~~Zaziarnione losowanie + gating klawisza `next_day`.~~ **Zrobione**: `world_rng.py`, `Scene.world_seed` w zapisie, bramka na `SHOW_DEBUG_INFO` (nie `IS_DEBUG_MODE` - patrz wyżej), testy `tests/test_world_rng.py`.
4. ~~Regeneracja `characters.csv` przez `--export` + cztery kolumny destynacji w modelu postaci.~~ **Zrobione**: 17 -> 31 kolumn (z `routine`), plus dwie naprawy eksportera (kolumny z modelu, tożsamość na przód).
5. ~~`routines.toml` + `npc_schedule.py` + warstwa `places`, na razie z jedną aktywnością `stand`.~~ **Kod zrobiony**; brakuje danych: punktów na warstwie `places` w Tiled i czterech kolumn destynacji w `characters.csv` (tabelka poniżej). Do tego czasu system jest bezczynny i nic nie psuje.
6. ~~`sleep` z zanikiem na progu.~~ **Zrobione.**
7. ~~`wander` / `patrol` / `idle` + jitter kroków.~~ **Zrobione** (jitter wszedł już w kroku 5).

Punkty 1-3 to ekonomia, 4-7 to cykl dobowy. Obie połówki są niezależne, byle `NpcRuntime` był pierwszy.

## Do zrobienia ręcznie: punkty w Tiled i kolumny w CSV

Kod kroku 5 jest kompletny, ale bezczynny, dopóki nie ma danych. Dwie rzeczy, obie po stronie autora.

### 1. Warstwa obiektów `places` w `Village.tmx`

Nowa warstwa obiektów o nazwie **`places`**, obok istniejących `waypoints` / `spawn_points` / `entry_points`. Same nazwane punkty - **żadnych custom properties**. Nazwa musi być unikalna w obrębie mapy. Scena czyta `rect.midbottom`, więc zwykły Point działa.

| Nazwa obiektu | Gdzie postawić | Komu służy |
|---|---|---|
| `tavern` | wnętrze/próg karczmy | praca BARMANA, przerwa reszty |
| `market_stall_1` | stragan Johny'ego | praca Johny'ego |
| `market_stall_2` | stragan Barta | praca Barta |
| `smithy` | kuźnia | praca HAMMER_HOAXHEART |
| `well` | studnia na środku wioski | wspólna, używana przez `location:well` |
| `house_johny` | próg domu Johny'ego | jego `home` |
| `house_bart` | próg domu Barta | jego `home` |
| `house_barman` | próg domu barmana (albo sama karczma) | jego `home` |
| `house_smith` | próg domu kowala | jego `home` |
| `pier` | pomost nad wodą | `hobby` - miejsce charakterystyczne |
| `shrine` | kapliczka | `hobby` |

Minimum, żeby zobaczyć efekt: `market_stall_1` i `house_johny`. Reszta może dojść później - brakujące miejsce nie jest błędem, tylko krokiem "zostań gdzie jesteś".

### 2. Kolumny destynacji i rutyny w `characters.csv`

Pięć nowych kolumn jest już w pliku. Cztery destynacje wypełnia się **nazwami obiektów z warstwy `places`**, a `routine` - kluczem sekcji `[routine.*]` z `routines.toml`. Wiersz jest kluczowany nazwą modelu, więc kopie tego samego modelu dostają ten sam rytm.

| Wiersz w `characters.csv` | `home` | `work` | `social` | `hobby` | `routine` |
|---|---|---|---|---|---|
| `JOHNY` | `house_johny` | `market_stall_1` | `tavern` | `pier` | `townsfolk` |
| `BART` | `house_bart` | `market_stall_2` | `tavern` | `well` | `townsfolk` |
| `BARMAN_ABSINTHRAYNER` | `house_barman` | `tavern` | `well` | `shrine` | `townsfolk` |
| `HAMMER_HOAXHEART` | `house_smith` | `smithy` | `tavern` | `shrine` | `townsfolk` |

Karczma rozwiązana tak, jak chciał plan: BARMAN ma ją jako `work`, wszyscy pozostali jako `social`. Jeden obiekt w Tiled, dwie role, zero duplikatów.

Po wypełnieniu: `just import-entities` (CSV -> config.json). Puste komórki nie nadpisują niczego, więc można wypełniać po jednej.

### Dwa bugi wykryte po postawieniu punktów

Obserwacje z pierwszego przejścia z prawdziwą mapą, obie naprawione.

**Dygotanie po dotarciu - prawdziwa przyczyna siedzi w integratorze fizyki.** Pierwsza naprawa (okno dotarcia, niżej) była potrzebna, ale nie ta. `physics()` robiło:

```python
self.acc.x += self.vel.x * self.friction
self.vel.x += self.acc.x * dt
```

`acc` jest polem obiektu, więc przeżywa klatkę - a to znaczy, że tarcie wpadało z powrotem samo w siebie. Dopóki jakiś kontroler nadpisywał `acc` co klatkę, było nieszkodliwe (stąd marsz zawsze wyglądał dobrze). W momencie, w którym nikt już `acc` nie pisał - postać dotarła, `clear_waypoints()` wyzerowało `acc`, a `follow_waypoints()` zaczęło wychodzić od razu na `waypoints_cnt <= 0` - te dwie linijki domykały się w pętlę:

```text
acc' = acc + f*v
v'   = v + acc'*dt
```

To jest oscylator harmoniczny o module wartości własnej **dokładnie 1,0**, czyli bez tłumienia - nigdy nie wygasa. Okres 13,9 klatki (0,23 s przy 60 FPS), amplituda ~2,4 px. Zmierzone, nie oszacowane. Gracz był odporny przez przypadek: jego obsługa wejścia przypisuje `self.acc.x = 0` w klatkach bez wciśniętego klawisza, co rozrywa pętlę.

Naprawa: `acc` to siła *na tę klatkę*. Tarcie liczone na kopii, a `acc` zerowane na końcu `physics()` - każdy kontroler i tak pisze je w `movement()` tuż przed. Po zmianie moduły wartości własnych to 0,8 i 0, czyli tłumienie: postać dojeżdża 3 px za cel i **staje**, rozrzut 0,000 px przez 10 sekund.

**Zbyt wąskie okno dotarcia (osobna sprawa, też naprawiona).** Sterowanie w `follow_waypoints()` jest bang-bang: `force = 2000` przykładane w pełni w stronę punktu niezależnie od odległości. Okno dotarcia było stałe i wynosiło `distance² <= 2.0`, czyli promień ~1,41 px. Krok jednej klatki to `1.5 * vel * dt`, co przy `speed_run = 40` i 60 FPS daje 1,0 px, a przy spadku do 40 FPS - 1,5 px. Postać, która nie trafi *do wnętrza* okna, przelatuje nad nim, dostaje pełną siłę z powrotem i drga w nieskończoność. Stąd pozorna losowość: zależało od klatkażu, od `step_cost` terenu i od tego, czy dana postać wylosowała przy spawnie `speed_walk` czy `speed_run` (`characters.py:226`). Zwierzęta mają domyślne `speed_run = 40`, więc łapały to samo. Naprawa: okno nie może być węższe niż jeden krok klatki - `max(WAYPOINT_ARRIVE_RADIUS_SQ, step²)`, gdzie `step` to `pos - prev_pos`, czyli dosłownie przebyty dystans z poprzedniej klatki (`physics()` próbkuje `prev_pos` przed ruchem). Samo się skaluje i dla wolnych postaci zostaje ciasne.

**Nikt nie szedł na noc do domu - i to nie `sleep` był winny.** Pomiar na `Village.tmx`: **pięć z jedenastu** postawionych miejsc siedzi na kaflach ściany - `tavern` i wszystkie cztery `house_*`. A* nie wchodzi na kafel z `grid[r][c] > 0`, więc `a_star` zwracał `None`, a gałąź `else` w `find_path()` czyści łamaną i zeruje prędkość, czyli **zamraża postać w miejscu**. To ten sam objaw co obserwacja "jak nie zdąży dojść, to się zatrzymuje" - o 13:00 cała czwórka szła do `tavern`, dostawała "Path not found" i stawała. Naprawa: `nearest_walkable()` w `maze_utils.py` dosuwa cel do najbliższego przejezdnego kafla, pierścieniami. To nie jest obejście błędu autora - marker *zawsze* ląduje na tym, co oznacza (drzwi, stragan, karczma), a "podejdź pod drzwi" jest tym, o co chodziło. Po naprawie wszystkie 11 miejsc jest osiągalnych ze spawnu Johny'ego.

### 3. Co wtedy zobaczysz

Johny i Bart zaczną chodzić między straganem a domem wg zegara (`` ` `` pokazuje godzinę). Granice slotów są rozjechane o jitter z hasha nazwy, więc nie ruszą jednocześnie. Aktywności inne niż `stand` jeszcze nic nie robią - postać po prostu dochodzi na miejsce i staje.

### Zasięg marszu na slot - liczby, nie wrażenia

`GAME_TIME_SPEED = 0.25`, więc **godzina w grze to 4 sekundy realne**, a doba 96 s. Przy `speed_walk = 30` px/s postać robi 120 px na godzinę gry, czyli **8 kafli**; biegiem (40) 10 kafli.

| Trasa | Odległość | Ile godzin gry marszem |
|---|---|---|
| stragan Johny'ego -> `well` | 5 kafli | poniżej godziny |
| stragan -> `smithy` | 11 kafli | ~1,5 h |
| stragan -> `pier` | 29 kafli | ~3,5 h |
| stragan -> `house_johny` | 31 kafli | ~4 h |
| stragan -> `shrine` | 63 kafle | **~8,5 h** |

Stąd obserwacja, że do `shrine` nikt nie dochodzi: slot `hobby` trwa 18:30-20:00, czyli półtorej godziny gry - dystans dziesięć razy za duży. Trzy wyjścia, do wyboru: przybliżyć `shrine`, wydłużyć slot, albo podnieść `speed_walk` tym postaciom. Sloty i tak trzeba przemyśleć pod kątem tych liczb - `home` w 4 godziny marszu zjada połowę nocy.

## Weryfikacja

| Co | Jak |
|---|---|
| Harmonogram | Test jednostkowy `current_slot()`: granice kroków, zawijanie przez północ (krok o 02:00 aktywny do 06:00), determinizm jittera, niezależność od kolejności kroków w pliku. Bez pygame - czysta funkcja. |
| Obsada rutyn | Każdy klucz z kolumny `routine` w `characters.csv` istnieje w `routines.toml` (`test_every_routine_named_in_characters_csv_exists`) - oba pliki łączy goły string, więc literówka musi być błędem testu, nie odkryciem w grze. Nieznany klucz przy spawnie degraduje się do "brak rutyny" plus ostrzeżenie. |
| Rozwiązywanie `at` | Trzy warianty: `type:` trafia w kolumnę postaci, `location:` w obiekt mapy, `route:` w łamaną. Pusta komórka destynacji degraduje krok do `idle` w miejscu, nie wyjątek. |
| Round-trip CSV | `--export` a potem `import_entities.py` daje `config.json` identyczny semantycznie z wyjściowym (puste komórki nie nadpisują wartości domyślnych). |
| Regeneracja | `apply_days(3)` daje ten sam stan co trzykrotne `apply_days(1)`. Sakiewka nie przekracza `money_cap`. Pusta odbudowuje się w 4 doby przy 25%. |
| Asortyment | Po przelosowaniu nie zawiera towaru skupionego od gracza. |
| Zapis / odczyt | Stary plik zapisu bez nowych pól wczytuje się bez wyjątku. Dopisać do `tests/test_save_load_dialog_state.py`. |
| Ręcznie | Przez `agent_ctrl`: `talk_to_char` na handlarzu o 8:00 i o 23:00. Sprzedawać po sztuce aż do wyczerpania sakiewki i sprawdzić powiadomienie o odmowie. |
| Wizualnie | U usera. Zrzuty headless nie są wierne dla kompozycji całej klatki, więc zanik NPC o zmierzchu i panel handlu weryfikuje user na prawdziwym ekranie. |
| Wydajność | Przy `SHOW_DEBUG_INFO` sprawdzić, że o pełnej godzinie nie ma skoku czasu klatki - jitter ma to rozłożyć. |

## Opcjonalne, na koniec

Obie rzeczy poniżej są zaprojektowane tak, żeby cała reszta działała bez nich. Żadna nie jest zależnością niczego z listy powyżej.

### N1 - popyt dzienny z zapowiedzią na jutro

Każdy handlarz ma na dany dzień 2-3 towary, za które płaci więcej. Gracz dowiaduje się o tym dzień wcześniej, więc może zaplanować, po co schodzi do labiryntu. To zamienia losowanie w plan do wykonania.

**Problem:** handlarze nie prowadzą dialogów - `JOHNY` i `BART` mają `has_dialog: false`, więc nie ma gdzie umieścić zdania "jutro będę chciał bursztyny".

| Nośnik | Jak | Koszt | Ocena |
|---|---|---|---|
| Panel handlu | `_draw_merchant_stats` (`trade.py:131`) już rysuje wiersze ikona + wartość i już potrafi wypisać listę typów towaru (`trade.trades_only`). Dokładasz dwie sekcje tą samą metodą | reużywa `draw_icon_value`, zero nowych paneli i dialogów | zalecane |
| Tablica ogłoszeń w wiosce | nowy obiekt interaktywny w Tiled, panel z popytem wszystkich handlarzy | nowy typ obiektu, nowy panel, obsługa interakcji | później |
| Nadanie handlarzom dialogów | `has_dialog: true` + graf z węzłem czytającym popyt | trzeba napisać i utrzymywać treść w dwóch językach | odrzucone |

Plan wdrożenia dla wariantu "panel handlu":

1. **Model.** `NpcRuntime.demand: dict[str, int]` - klucz przedmiotu na liczbę sztuk objętych podwyżką. Nic nowego w zapisie: skoro losowanie jest zaziarnione, popyt wylicza się z `(save_seed, day, npc_name)` i nie musi być serializowany.
2. **Funkcja.** `demand_for(npc, day) -> dict[str, int]` - czysta funkcja bez stanu. Wywołana z `day` daje dziś, wywołana z `day + 1` daje zapowiedź. To jest cała magia zapowiedzi - jutro jest za darmo, bo jest deterministyczne.
3. **Cena.** W `get_sell_price_multiplier` dołożyć mnożnik popytu, dopóki nie wyczerpie się liczba sztuk na dziś. Po wyczerpaniu cena wraca do normalnej, *nie spada poniżej* - inaczej wracamy do odrzuconego nasycenia.
4. **Panel.** Dwa wiersze w `_draw_merchant_stats`, wzorowane na istniejącym bloku `trades_only`.
5. **Arytmetyka.** Cena w panelu szczegółów pokazuje składniki: `40 zł x1,2 (poszukiwane) x0,9 (nieufny) = 43 zł`. To musi powstać razem z popytem, nie po nim - bez tego popyt jest niewidzialną matematyką.

Warunek sensowności: N1 warto robić dopiero, gdy limit sakiewki realnie się aktywuje, czyli po korekcie liczb w CSV.

### N2 - nocleg u Barmana

Gracz podchodzi do Barmana w karczmie, rozmawia, a jedna z opcji dialogowych ma specjalny efekt: zabiera pieniądze (jeśli gracza stać), potem fade out / fade in i zaczyna się nowy dzień.

Trzy czwarte tego już istnieje: `BARMAN_ABSINTHRAYNER` ma dialogi, a system efektów ubocznych węzłów ma gotową kategorię `MONEY_RETURNED`, która woła `sink.remove_money()` (`dialog/result_sink.py`). Zabranie złota za nocleg nie wymaga żadnego nowego kodu ekonomicznego.

Trzy realne blokady, wykryte w kodzie:

| Blokada | Na czym polega | Rozwiązanie |
|---|---|---|
| Efekt działa tylko raz | `visit_node()` ma `if node.visited: return False` - efekt stosuje się raz na całą grę, a nocleg musi działać co noc | flaga `repeatable: bool` na `DialogNode`, domyślnie `False`; gdy ustawiona, `visit_node` stosuje efekt mimo `visited`. Jedno pole i jeden warunek, nie rusza żadnego istniejącego dialogu |
| Brak kategorii "prześpij noc" | `NodeVisitResultCategory` ma 7 wartości: pieniądze, przedmioty, zdrowie, sentyment - żadna nie przesuwa czasu | ósma wartość `TIME_ADVANCED` + metoda `sleep_until_dawn()` w protokole `ResultSink` + jedna gałąź w `apply_result`; implementacja w adapterze woła istniejące `apply_days(1)` i ustawia godzinę na 6:00 |
| DSL warunków nie widzi złota ani godziny | `NPCConditionContext` daje `selected`, `visited`, `has_item`, `item_count`, `quest_done`, `sentiment` - brak pieniędzy i zegara | dwie właściwości: `money` (z `player`, już wstrzykniętego) i `hour` (ze `scene`); wtedy warunek opcji to `money >= 20 and (hour >= 20 or hour < 6)`, czysto deklaratywnie w danych dialogu |

Przepływ:

```text
gracz rozmawia z Barmanem
  |
  +- opcja "Przenocuję" widoczna tylko gdy:
  |     money >= cena_noclegu   AND   godzina w oknie 20:00-06:00
  |     (warunek w DSL, zero kodu per-przypadek)
  |
  +- wybór opcji -> węzeł z result:
  |     MONEY_RETURNED  (cena_noclegu)  -> sink.remove_money()     [istnieje]
  |     TIME_ADVANCED                   -> sink.sleep_until_dawn() [nowe]
  |
  +- sleep_until_dawn():
        zamknij panel dialogu
        transition.fade_out()          [istnieje: project/transition.py]
        scene.apply_days(1); scene.hour = 6; scene.minute = 0
        transition.fade_in()
```

Dlaczego okno 20:00-06:00: jedno `if` w warunku opcji sprawia, że pętla "prześpij - sprzedaj - prześpij" staje się zdominowana. Po noclegu jest 6:00 i opcja znika na 14 godzin gry, a odpowiedź na "i co teraz" brzmi: labirynt, czyli gra. Opłata dokłada drugi koszt.

Zasada do wielokrotnego użytku: nie trzeba czynić degeneracyjnej taktyki niemożliwą, wystarczy uczynić ją gorszą od grania. Po dodaniu reguły antyexploitowej pytaj: "co optymalny gracz robi w oknie, które ta reguła tworzy?". Jeśli odpowiedź brzmi "stoi", reguła jest cooldownem i zawiodła.

Pliki dodatkowe dla opcjonalnych: N1 dotyka `trade.py` i `settings.py`. N2 dotyka `dialog/entities.py`, `dialog/result_sink.py`, `dialog/context_adapter.py` i `result_sink_adapter.py`.
