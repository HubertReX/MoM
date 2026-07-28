# B02 - polityka wersji save + mechanizm migracji

Priorytet: **P2** (Faza 2). Rozmiar: M.
Zależności: B01 (refactor rdzenia) - zrealizowane; A02 (asercje `ui_state`) - zrealizowane.
Powiązanie: **H02** (śmierć gracza → od razu ekran wczytania) stoi na ścieżce, którą to
zadanie naprawia - patrz krok 5.

## Decyzje projektowe (zatwierdzone 2026-07-28)

1. **Jeden numer wersji.** Wersja zapisu = wersja gry. Gracz zna numer wersji gry i widzi
   go w "O grze"; osobnego numeru schematu nigdy by nie zobaczył. Nie rozdzielamy.
2. **`VERSION` staje się stringiem `"MAJOR.MINOR"`** i jest porównywana przez wyliczony
   kod całkowity (`"0.3"` → `3`, `"1.3"` → `103`). Koniec z `float` w porównaniach wersji.
3. **Alfa kasuje, 1.0 migruje.** Dopóki gra jest przed premierą, zapisy ze starszych
   wersji są odrzucane (nikt nie traci nic bolesnego, a migracje formatu, który wciąż się
   rusza, to czysty koszt). Mechanizm ma być jednak **zbudowany i przetestowany teraz**,
   żeby po 1.0 włączyć go zmianą jednej stałej.
4. **Zapisu nie do odczytania nigdy nie kasujemy sami.** Slot zostaje na liście, jest
   wyszarzony, ma podany powód, a gracz może go usunąć (`D`) albo nadpisać. Odmowa
   wczytania nigdy nie rusza stanu gry.
5. **Numer wersji zapisu jest widoczny w panelu zapisu/odczytu** - przy każdym slocie,
   nie tylko przy niezgodnym.

## Kontekst i problem

Save ma wersję, ale nie ma **polityki** wersjonowania ani działającego mechanizmu.
Pięć konkretnych skutków:

### 1. Wersja jest `float` i nie da się jej sensownie porównywać

`settings.py:37` `VERSION = 0.3`, `save_load/models.py:20` `SAVE_VERSION: float = VERSION`,
`SaveMetadata.version: float` (`:99`). Porównania zmiennoprzecinkowe (`0.1 + 0.2 != 0.3`),
brak porządku po `0.9` (czy `0.10` jest starsze, czy nowsze?), brak możliwości
zaadresowania kroku migracji. `float` nie jest typem wersji.

### 2. Mechanizm migracji jest martwym kodem

`models.py:523-560` definiuje `_MIGRATIONS`, dekorator `_register_migration`, funkcję
`migrate_save()` i placeholder `migrate_v0_to_v1()`. Z tego:

- `_MIGRATIONS` jest **puste** - `migrate_v0_to_v1` nigdy nie została zarejestrowana
  dekoratorem,
- `migrate_save()` **nie jest wołana z żadnej ścieżki ładowania** (jedyne wystąpienie
  poza `models.py` to `tests/test_save_load_models.py:356`, gdzie testuje sama siebie
  na no-opie),
- `models.py:546` `for target_version, func in sorted(_MIGRATIONS)` sortuje krotki
  `(float, function)`. Przy dwóch migracjach o tej samej wersji Python porówna funkcje
  i rzuci `TypeError: '<' not supported between instances of 'function' and 'function'`.
  Bomba z lontem - odpali się przy pierwszej realnej migracji, nie teraz.

### 3. Ładowanie odrzuca wszystko, co nie jest równe, i nie rozróżnia powodów

`save_load/manager.py:92-94`:

```python
if save.metadata.version != SAVE_VERSION:
    print(f"[save] version mismatch: ...")
    return False
```

Twarde `!=` na floatach: "zapis z przyszłości" i "zapis do zmigrowania" są tym samym
przypadkiem, a wołający dostaje tylko `False`, więc nie ma jak powiedzieć graczowi,
co się właściwie stało.

### 4. Odmowa jest niewidoczna dla gracza (i wywala grę na ekranie śmierci)

- `ui/panels/save_load.py:739-745` - `LoadPanel._do_load` pokazuje notyfikację
  **tylko przy sukcesie**. Nieudane wczytanie = nic się nie dzieje na ekranie. Komunikat
  idzie na `print`, czyli do terminala (na web: do konsoli JS).
- `ui/panels/save_load.py:874-878` - `DeadState._on_load_slot` **ignoruje wynik**:

  ```python
  self.game.save_manager.load(slot_idx)
  # SaveManager.load pushed a new Scene; discard this DeadState.
  if self.game.states:
      self.game.states[:] = [self.game.states[-1]]
  ```

  Gdy `load()` zwróci `False`, żadna nowa `Scene` nie została wepchnięta na stos, więc
  `states[-1]` to **sam `DeadState`**. Stos zwija się do ekranu śmierci bez żadnej sceny
  pod spodem - **twardy soft-lock**.
- `DeathScreen._on_load_slot` (`:795-799`) jest gorszy: woła `self._close_state()`
  **przed** `load()`, więc przy nieudanym wczytaniu panel i `DeadState` już nie żyją,
  a nowej sceny nie ma.
- `game.py:1019-1026` (F9 quick load) - gdy `load()` zwróci `False`, **nie ma gałęzi
  `else`**: gracz naciska F9 i nie dzieje się absolutnie nic.
- `list_slots()` (`backends.py:82-94`, `:134-146`) pokazuje niekompatybilny slot jak
  każdy inny - z nazwą, datą i czasem gry. Nic w UI nie mówi, że go nie da się wczytać.

### 5. Migracja nie ma gdzie się wpiąć bez utraty danych

`SaveGame.from_dict` jest tolerancyjny (`data.get(klucz, domyślna)`), więc stary zapis
z **przemianowanym** kluczem nie wybucha - po cichu ląduje na wartościach domyślnych.
To znaczy, że migracja musi zadziałać na **surowym dictcie**, zanim cokolwiek go
zdeserializuje. Wpięcie jej po deserializacji jest bezużyteczne.

### Co już jest gotowe do wykorzystania

`scripts/save_fixtures.py:104-111` ma `corrupt_save_version()` (zapis z `version: 9999`),
a runner obsługuje go po obu stronach - desktop `tests/automate_display_test.py:983-984`,
web `:1349-1350`. **Żaden scenariusz go nie używa.** Fixture czeka gotowy.

## Cel

- Wersja gry jako string `"MAJOR.MINOR"` z wyliczanym kodem `int` - jedno źródło prawdy
  dla gry i dla zapisu.
- Spisana polityka: co znaczy podbicie wersji dla zapisów, kiedy trzeba napisać migrację,
  a kiedy nie, i co dokładnie dzieje się przy zapisie starszym / nowszym / nieczytelnym.
- Mechanizm migracji **działa i jest przetestowany**, ale w alfie łańcuch jest pusty;
  włączenie go po 1.0 to zmiana jednej stałej.
- Odmowa wczytania jest widoczna w grze, ma podany powód i nigdzie nie zwija stanu gry.
- Wersja zapisu widoczna przy każdym slocie w panelu zapisu/odczytu.

## Model wersjonowania (treść polityki do spisania)

To jest deliverable tekstowy zadania - trafia do docstringa sekcji wersjonowania
w `save_load/models.py` i w skrócie do `project/AGENTS.md` (sekcja "Persystencja stanu").
Nie robimy osobnego dokumentu HTML - to reguła inżynierska, nie decyzja projektowa.

### Numer wersji

`VERSION: str = "0.3"` w `settings.py`, format `MAJOR.MINOR`. **Nie ma poziomu patch
w kontrakcie zapisu** - jeśli poprawka musiałaby zmienić format, podbija się `MINOR`.

`version_code("1.3") == 103` (`MAJOR * 100 + MINOR`, `MINOR` w zakresie 0-99). Kod jest
tym, co się porównuje i czym adresuje się migracje. Kod ujemny = wersja nieczytelna.

Stare pliki mają `version` jako `float` (`0.3`). `version_code` przyjmuje `str | float |
int` i normalizuje przez `str()`, więc `0.3` → `"0.3"` → `3`, czyli **dzisiejsze zapisy
mają dokładnie ten sam kod co bieżąca wersja gry i wczytują się bez migracji**. To jest
też powód, dla którego przechodzimy na string teraz: `0.10` i `0.1` to ten sam `float`.

### Dwie stałe sterujące

```python
CURRENT_SAVE_CODE: int = version_code(VERSION)   # 3
MIN_SUPPORTED_SAVE_CODE: int = CURRENT_SAVE_CODE  # alfa: tylko bieżąca wersja
```

`MIN_SUPPORTED_SAVE_CODE` to **najstarszy kod zapisu, który potrafimy dociągnąć do dziś**.

- **Przed 1.0 (teraz):** równa się `CURRENT_SAVE_CODE` i jest podbijana razem z `VERSION`
  przy każdym wydaniu. Skutek: starsze zapisy są odrzucane z czytelnym komunikatem.
  Pozycja na liście kontrolnej wydania (patrz niżej).
- **Od 1.0:** zamraża się na `100` i już nie rośnie. Od tego momentu każda zmiana formatu
  musi przyjechać z migracją.

### Rejestr migracji

Migracja jest kluczowana **wersją, w której zmienił się format**, nie każdym wydaniem:

```python
@_register_migration("1.4")           # format zmienił się w 1.4
def _to_1_4(data: dict) -> dict: ...  # przerabia dowolny układ sprzed 1.4 na układ 1.4
```

`migrate_save` bierze wszystkie migracje o kodzie `> kod_zapisu` i `<= CURRENT_SAVE_CODE`,
stosuje rosnąco, po czym stempluje `metadata.version` bieżącą wersją.

**Kluczowa konsekwencja tego kształtu:** wydanie, które nie zmienia formatu (nowa mapa,
nowy quest, poprawka balansu), **nie wymaga żadnego wpisu** - łańcuch jest pusty, zapis
przechodzi i dostaje nowy stempel. To jest to, co czyni sprzężenie wersji gry z wersją
zapisu utrzymywalnym; bez tego każde wydanie wymagałoby migracji-tożsamości.

### Kiedy trzeba napisać migrację (od 1.0)

**Nie trzeba** (przypadek domyślny): dodanie pola z wartością domyślną, którą `from_dict`
wstawi starym zapisom. Tak powstały `NPCState.config_key`, `NPCState.runtime`,
`SaveGame.world_seed` i `PlayerState.damage` - każde z komentarzem "saves written before
this existed still load". Ta praktyka jest dobra i zostaje.

**Trzeba**: zmiana nazwy pola, usunięcie pola, zmiana znaczenia wartości przy tej samej
nazwie (jak przemianowanie kluczy sentymentu w 0.2 - `settings.py:35`), zmiana typu,
której `int()`/`str()` nie połknie.

### Reguły ładowania

| Kod zapisu | Stan | Zachowanie |
|---|---|---|
| `== CURRENT_SAVE_CODE` | `ok` | ładuj |
| `>= MIN_SUPPORTED` i `< CURRENT` | `ok` | przepuść przez łańcuch migracji, ostempluj, ładuj |
| `> CURRENT_SAVE_CODE` | `from_future` | odmów: "zapis z nowszej wersji gry" |
| `< MIN_SUPPORTED` | `too_old` | odmów: "zapis ze starszej, nieobsługiwanej wersji" |
| nie da się sparsować | `unreadable` | odmów: jak `too_old`, komunikat bez numeru |

### Postępowanie z zapisem, którego nie da się wczytać

- Slot **zostaje** na liście - nigdy nie kasujemy cudzych danych automatycznie.
- Rysowany na szaro; w kolumnie meta zamiast daty i czasu gry idzie numer wersji
  + powód (`v0.2  za stara wersja` / `v1.3  nowsza wersja gry`).
- Próba wczytania: notyfikacja `error` z powodem, **zero zmian w stanie gry**
  (panel zostaje otwarty, ekran śmierci zostaje ekranem śmierci).
- Gracz może go usunąć (`D`) albo **nadpisać** z panelu zapisu - nadpisanie działa
  normalnie, z istniejącym potwierdzeniem. To jest jego droga wyjścia i nie ruszamy jej.
- F9 na niezgodnym szybkim zapisie: komunikat z powodem zamiast dzisiejszej ciszy.

### Lista kontrolna wydania (do `AGENTS.md`)

Przy podbiciu `VERSION`:

1. czy zmienił się format zapisu? jeśli tak i jesteśmy po 1.0 - napisz migrację
   kluczowaną nową wersją,
2. przed 1.0: podbij `MIN_SUPPORTED_SAVE_CODE` razem z `VERSION`,
3. zaktualizuj domyślną wersję w `scripts/save_fixtures.py` (pilnuje tego test, patrz krok 6).

## Pliki do zmiany

- `project/settings.py` - `VERSION` jako `str`
- `project/save_load/models.py` - `version_code`, `CURRENT_SAVE_CODE`,
  `MIN_SUPPORTED_SAVE_CODE`, `save_compatibility`, przepisany rejestr migracji,
  `SaveMetadata.version: str` + `migrated_from`, wpięcie `migrate_save`
  w `SaveSlot.from_dict`
- `project/enums.py` - `SaveCompatEnum`
- `project/save_load/manager.py` - bramka w `load()` oparta o `save_compatibility`,
  `slot_compatibility()` dla UI
- `project/ui/panels/save_load.py` - wersja w kolumnie meta, oznaczenie niezgodnego slotu,
  notyfikacja przy nieudanym wczytaniu, naprawa `DeadState._on_load_slot`
  i `DeathScreen._on_load_slot`
- `project/game.py` - gałąź `else` dla F9 quick load (`:1019-1026`)
- `project/assets/locale/PL.toml` i `EN.toml` - nowe klucze w sekcji `[save]`
- `scripts/save_fixtures.py` - `minimal_save_dict` na stringową wersję + nowy fixture
  `old_save_version`
- `tests/automate_display_test.py` - obsługa typu `old_version` w `setup_saves`
  (desktop `:983`, web `:1349`)
- `tests/test_save_load_models.py` - testy polityki, migracji i zgodności fixture'ów
- `tests/scenarios.json` - scenariusze `Future Save Rejected` i `Old Save Rejected`
- `project/AGENTS.md` - sekcja "Persystencja stanu" (~linia 576) + lista kontrolna wydania

## Kroki

### Krok 1 - wersja jako string + kod porównawczy

- `settings.py:37`: `VERSION: str = "0.3"`. Sprawdź `ui/panels/main_menu.py:597`
  (`("menu.about_ver", {"version": VERSION})`) - dla stringa renderuje się identycznie,
  ale zweryfikuj na ekranie.
- `models.py`: `version_code(value: str | float | int) -> int`. Parsowanie: `str(value)`,
  split po `.`, pierwszy człon = major, drugi (jeśli jest) = minor, trzeci **ignorowany**.
  Wszystko, czego nie da się sparsować na inty → `-1`. Bez wyjątków - to funkcja czysta,
  wołana z pętli listującej sloty.
- `CURRENT_SAVE_CODE` i `MIN_SUPPORTED_SAVE_CODE` jak w sekcji polityki.
- `SaveMetadata.version: str = VERSION`; `from_dict` normalizuje przez
  `str(data.get("version", VERSION))` (stary `float` 0.3 → `"0.3"`).
- `SaveMetadata.migrated_from: str = ""` - informacyjne, ustawiane tylko przez migrację,
  puste w świeżym zapisie. Samo w sobie jest przykładem "pole z domyślną = bez migracji".
- Usuń `SAVE_VERSION`. Importują go `manager.py:14` i `tests/test_save_load_models.py:32` -
  oba i tak przepisujemy. Aliasu nie zostawiamy.

### Krok 2 - `save_compatibility` jako jedyna bramka

W `enums.py`:

```python
class SaveCompatEnum(StrEnum):
    ok = auto()
    too_old = auto()
    from_future = auto()
    unreadable = auto()
```

W `models.py` funkcja czysta `save_compatibility(version: str | float | int) ->
SaveCompatEnum` realizująca tabelę reguł ładowania. Używają jej **oba** miejsca:
`manager.load()` (decyzja) i UI (rysowanie wiersza). Żadnej innej logiki porównywania
wersji nigdzie w kodzie.

### Krok 3 - migracja działa naprawdę

- `_MIGRATIONS: list[tuple[int, MigrationFn]]`, dekorator przyjmuje **string wersji**
  i zapisuje `version_code` tej wersji.
- Napraw sortowanie: `sorted(_MIGRATIONS, key=lambda pair: pair[0])` - dwie migracje pod
  tym samym kodem nie mogą wywalić porównania funkcji.
- `migrate_save(data: dict) -> dict` - **nigdy nie rzuca i nigdy nie loguje w pętli**.
  Gdy `save_compatibility != ok`, zwraca dane **nietknięte** (z oryginalnym `version`).
  Gdy `ok`: stosuje pasujące migracje rosnąco, ustawia `metadata.migrated_from` na
  oryginalną wersję (tylko gdy kod się różnił) i `metadata.version` na `VERSION`.
  Sygnałem powodzenia jest stempel wersji, nie zwracana flaga - dzięki temu bramka
  z kroku 2 zostaje jedynym miejscem decyzji.
- Usuń placeholder `migrate_v0_to_v1`. **W alfie `_MIGRATIONS` zostaje puste** -
  mechanizm jest zbudowany i przetestowany (patrz krok 6: testy rejestrują własne
  migracje lokalnie), ale gra nie wozi ze sobą ani jednej.

**Punkt wpięcia: `SaveSlot.from_dict` (`models.py:483-490`), na surowym dictcie, przed
`SaveGame.from_dict`.** To jedyne miejsce, przez które przechodzą oba backendy
(`backends.py:57` plik, `:113` localStorage) **i** `list_slots()`. Wpięcie po
deserializacji jest bezużyteczne - `from_dict` już zgubiłby przemianowane klucze
na wartościach domyślnych (kontekst, punkt 5).

### Krok 4 - reguły odmowy zamiast twardego `!=`

- `manager.py:92` - warunek na `save_compatibility(save.metadata.version)`.
  Zapamiętaj powód ostatniej porażki (np. `self.last_load_error: SaveCompatEnum | None`),
  żeby wołający miał co pokazać.
- `SaveManager.slot_compatibility(slot_idx) -> SaveCompatEnum | None` (None = pusty slot)
  dla UI, licząca z `SaveSlotInfo.metadata.version` - bez czytania całego zapisu.
- Uwaga na kolejność: `migrate_save` w `from_dict` już podniosło `metadata.version`
  zmigrowanego zapisu do bieżącej wersji, więc bramka w `load()` widzi `ok`.
  Zapis, którego nie dało się zmigrować, ma wersję nietkniętą i leci na `too_old`
  / `from_future`. To jest cała mechanika - nie dokładaj drugiego sprawdzenia.

### Krok 5 - widoczna odmowa i koniec soft-locka

- **Nowe klucze locale** w `[save]` (PL i EN muszą mieć te same klucze -
  `just validate-locale` to sprawdza):
  `load_failed` ("Nie udało się wczytać zapisu"), `too_old` ("Zapis ze starszej wersji gry"),
  `from_future` ("Zapis z nowszej wersji gry"), `unreadable` ("Nieczytelna wersja zapisu"),
  `version_short` (`"v{v}"` - prefiks w wierszu slotu).
- `LoadPanel._do_load` (`:739`) - `else` z notyfikacją `NotificationTypeEnum.error`
  i tekstem dobranym po `SaveCompatEnum`. Z menu głównego notyfikacje też działają -
  `_PanelSceneProxy.add_notification` (`ui/panels/main_menu.py:369-372`) przekazuje je
  do żywej sceny.
- `DeadState._on_load_slot` (`:874`) - **sprawdź wynik `load()`**. Przy `False` nie ruszaj
  `game.states`, zostań na ekranie śmierci, pokaż komunikat.
- `DeathScreen._on_load_slot` (`:795`) - **przesuń `self._close_state()` za udany
  `load()`**. Dziś zamyka panel zanim wie, czy jest dokąd wracać.
- `game.py:1019-1026` (F9) - dodaj `else` z powodem z `last_load_error`; przy niezgodnym
  slocie 0 gracz ma zobaczyć komunikat, nie ciszę.
- `agent_ctrl.py:499` (`load_last`) - wynik możesz zignorować, ale wypisz powód na `print`,
  żeby scenariusze agentowe miały ślad w logu.

### Krok 6 - wersja i stan slotu w panelu

`_SlotButton.parts` (`:91-108`) zwraca `(name, meta)`, `_draw_slot_row` (`:111-126`) rysuje
nazwę do lewej, meta do prawej. Zmiany **tylko w tych dwóch miejscach**, dalej dwie
kolumny - trzeci element trzeba by przepychać przez self-checki layoutu
(A03, `just test-unit layout_checks`), a układ dwukolumnowy jest odporny na przepełnienie.

- slot zgodny: `meta = f"v{wersja}  {data}  {czas_gry}"`,
- slot niezgodny: `meta = f"v{wersja}  {powód}"`, nazwa rysowana kolorem `theme.GREY`
  zamiast `theme.WHITE`.

Jeśli `layout_checks` zgłosi przepełnienie wiersza po dołożeniu prefiksu wersji, skróć
znacznik czasu do `MM-DD HH:MM` (`_format_timestamp`, `:63`) - **nie** usuwaj wersji,
bo to jest cel tego kroku.

### Krok 7 - testy

**Jednostkowe** (`tests/test_save_load_models.py`, pamiętaj o dopisaniu funkcji
do listy `tests = [...]` na dole pliku - runner wywala plik, w którym `test_*` tam nie ma):

- `version_code`: `"0.3"` → 3, `0.3` (float ze starego pliku) → 3, `"1.3"` → 103,
  `"1.0"` → 100, `"1.2.5"` → 102 (patch ignorowany), `"abc"` / `""` / `None` → -1;
- **monotoniczność**: `version_code("0.9") < version_code("0.10") <
  version_code("1.0")` - to jest dokładnie ta własność, której `float` nie miał;
- `save_compatibility`: bieżąca wersja → `ok`, `"9999"` → `from_future`,
  `"0.1"` → `too_old`, brak klucza / śmieć → `ok` (domyślka) i `unreadable` dla śmiecia -
  **rozstrzygnij i utrwal w teście**, że brak klucza `version` znaczy "bieżąca wersja"
  (dziś `from_dict` tak robi) i że to jest świadoma decyzja;
- **dzisiejszy zapis przeżywa zmianę**: dict z `"version": 0.3` (float, jak w pliku
  na dysku) przechodzi `SaveSlot.from_dict` → `save_data` niepuste, `metadata.version ==
  "0.3"`, `migrated_from == ""`;
- **własność "pole z domyślną nie wymaga migracji"**: weź `SaveGame().to_dict()`, usuń
  `world_seed` i `player.damage`, przepuść przez `from_dict` - wychodzi obiekt
  z domyślnymi, bez migracji;
- **mechanizm migracji na atrapach** (rejestr jest w produkcji pusty, więc test musi
  go sobie zbudować i posprzątać - użyj `try/finally` na `_MIGRATIONS`):
  - dwie migracje pod różnymi kodami stosują się rosnąco i tylko te `> kod_zapisu`,
  - po migracji `metadata.version == VERSION`, a `migrated_from` trzyma oryginał,
  - dwie migracje pod **tym samym** kodem → `migrate_save` nie rzuca `TypeError`
    (regresja na `sorted`, kontekst punkt 2),
  - zapis `too_old` / `from_future` wychodzi z `migrate_save` **bajt w bajt taki sam**;
- **zgodność fixture'ów**: `save_fixtures.minimal_save_dict(0)["save_data"]["metadata"]
  ["version"] == settings.VERSION` - to jest strażnik punktu 3 listy kontrolnej wydania.

**Scenariusze agentowe** w `tests/scenarios.json` (`platform: ["desktop", "web"]`):

- `Future Save Rejected` - `setup_saves: [{"slot": 1, "type": "corrupt_version"}]`,
- `Old Save Rejected` - `setup_saves: [{"slot": 1, "type": "old_version"}]`
  (nowy fixture `old_save_version`, wersja `"0.1"`; dołóż obsługę typu po obu stronach
  runnera - desktop `:983`, web `:1349`).

W obu: slot 1, nie 0 (slot 0 jest zarezerwowany dla F5/F9 i tylko do odczytu z poziomu
gracza, `settings.py:296-299`). Akcje: start gry → menu → panel wczytywania → wybór slotu
→ potwierdzenie → `screenshot`. Sekwencję klawiszy skopiuj ze scenariusza
`Load from Main Menu`, nie wymyślaj od zera. Asercje: `process_alive`; `ui_state`
potwierdzające, że gra **nie** weszła do wczytanego świata (panel/menu dalej na wierzchu);
`no_layout_violations`; `screenshot_review` z oczekiwaniem "slot wyszarzony z numerem
wersji i powodem, widoczny komunikat o odmowie, gra się nie wczytała i nie zawiesiła".

## Kryteria akceptacji

1. `just test-unit` w całości zielony, z nowymi testami z kroku 7.
2. `just mypy` = `Success: no issues found`.
3. `just validate-locale` zielony (klucze PL i EN symetryczne).
4. **Zapis sprzed zmiany wczytuje się po zmianie.** Przed pierwszym commitem tego zadania:
   uruchom grę, zapisz do slotu 2, skopiuj plik `<data_dir>/mom/saves/save_2.mom` poza
   katalog. Po zmianie: wgraj go z powrotem, wczytaj z menu - gra ma wstać w tym samym
   miejscu, a `metadata.version` w pliku po ponownym zapisie ma być stringiem `"0.3"`.
5. `MOM_SKIP_SS_REVIEW=1 just test-agent "Future Save Rejected"` i
   `... "Old Save Rejected"` zielone; te same scenariusze na web przez `just test-web`.
6. `MOM_SKIP_SS_REVIEW=1 just test-smoke` zielony (6 scenariuszy) - w tym
   `Save and Load Basic` i `Auto Save on Maze Entry`, czyli happy path zapisu.
7. `MOM_SKIP_SS_REVIEW=1 just test-agent "Death then Load"` zielony (happy path ekranu
   śmierci nie drgnął).
8. **Ręczna weryfikacja soft-locka:** `.venv/bin/python scripts/save_fixtures.py
   corrupt_version 1`, `just run`, zgiń, spróbuj wczytać slot 1 → ekran śmierci zostaje,
   widać komunikat, `Restart` dalej działa. Powtórz to samo z panelu `DeathScreen`
   (druga ścieżka, `:795`). Przed naprawą obie zostawiają grę bez sceny.
9. **Ręczna weryfikacja F9:** `save_fixtures.py corrupt_version 0`, `just run`, F9 →
   widoczny komunikat o niezgodnej wersji zamiast ciszy.
10. Panel wczytywania pokazuje numer wersji przy każdym slocie, a niezgodny slot jako
    wyszarzony z powodem zamiast daty - zweryfikuj na realnym ekranie (zrzuty headless
    nie są wierne dla pełnej kompozycji, patrz notatka `headless-screenshot-not-faithful`).
11. Polityka spisana w docstringu `save_load/models.py`, streszczona w `project/AGENTS.md`
    razem z listą kontrolną wydania.

## Pułapki

- **Nie podbijaj `VERSION` w tym zadaniu.** Zostaje `"0.3"`, tylko zmienia typ na string.
  Zadanie ma zbudować mechanizm, nie użyć go. Dzięki temu kryterium 4 jest sprawdzalne.
- **`_MIGRATIONS` zostaje puste w kodzie produkcyjnym.** Nie dopisuj "przykładowej"
  migracji ani no-opa - martwy kod migracji jest dokładnie tym, co to zadanie usuwa.
  Mechanizm dowodzi się testami z atrapami.
- **`migrate_save` biegnie w `SaveSlot.from_dict`, a więc też w `list_slots()`**, które
  czyta wszystkie 10 slotów przy każdym otwarciu panelu. Trzymaj ją tanią: czyste
  operacje na dictach, bez I/O i **bez logowania w pętli** (10 printów przy każdym
  otwarciu panelu utopi realne komunikaty w logu scenariuszy).
- **`version_code` nie może rzucać.** Wołana jest z rysowania wiersza slotu; wyjątek
  na nieczytelnej wersji wywali panel zamiast pokazać wyszarzony slot.
- **`MINOR` ma zakres 0-99.** Przy `MINOR >= 100` kody się nakładają (`0.100` = `1.0`).
  Dołóż asercję/komentarz przy `version_code` - to jest cena schematu `MAJOR*100+MINOR`
  i trzeba ją mieć spisaną, a nie odkrywać przy 0.100.
- **`corrupt_version` używa `9999`** (`save_fixtures.py:108`) - zostaw. `version_code`
  ma to znieść jako jednoczłonowy string (`"9999"` → 999900), czyli wprost "z przyszłości".
- **`corrupt_save` (nieprawidłowy JSON) to inna ścieżka** - backend łapie wyjątek
  i zwraca `None` (`backends.py:58-60`), więc slot w ogóle nie istnieje dla UI. Nie zlewaj
  jej z niezgodną wersją; scenariusz `Corrupt Save Handling` ma dalej przechodzić bez zmian.
- **Nadpisanie niezgodnego slotu musi dalej działać.** `SavePanel` nie ma prawa blokować
  zapisu do slotu, którego nie da się wczytać - to jedyna droga wyjścia gracza.
- **Web ma osobny magazyn.** `localStorage` przeżywa reload i zamknięcie strony;
  przy ręcznym testowaniu na web czyść klucze `MoM.save_*` między próbami, inaczej
  testujesz zapis z poprzedniego przebiegu (patrz notatka `web-test-singleton-run-hygiene`).
- **Dual-target:** żadnego pydantic w `save_load/` - moduł jest wspólny dla desktopu
  i web (docstring `models.py:1-7`) i to się nie zmienia.
- Web-flaki najpierw powtórz 2x, dopiero potem oglądaj `screenshots/agent/`.

## Wynik realizacji (2026-07-28)

Zrealizowane zgodnie z planem, z czterema świadomymi odchyleniami:

1. **`SaveManager.slot_compatibility()` nie powstała.** Panel trzyma już `SaveSlotInfo`
   w `_SlotButton.info`, więc liczy zgodność wprost przez `save_compatibility(...)`;
   metoda na managerze byłaby martwym kodem (a przy 10 wierszach - 10 odczytów z dysku
   na wiersz). Ścieżka F9 używa `SaveManager.last_load_error`.
2. **Odmowa w panelu idzie w stopkę panelu, nie w notyfikację sceny.** Plan zakładał
   `NotificationTypeEnum.error` przez `_PanelSceneProxy`, ale panel żyje w stanie menu,
   gdzie toasty sceny **nie są rysowane** (mówi to wprost docstring `_notify_locked`) -
   komunikat byłby równie niewidoczny co dotychczasowy `print`. Użyty jest istniejący
   mechanizm `_flash` (stopka, `_FLASH_SECONDS`), ten sam co dla `quick_slot_locked`.
3. **Panel śmierci urósł z 520 na 560 px** (`_DEATH_PANEL_H`) - po śmierci nie ma sceny,
   która mogłaby wyświetlić notyfikację, więc `DeadState` / `DeathScreen` rysują własną
   linię błędu między listą slotów a przyciskiem `Restart`. Minimalna rozdzielczość
   (1280x720) to mieści.
4. **Doszedł trzeci scenariusz agentowy `Death Load Rejected`** (odmowa wczytania
   z ekranu śmierci) - plan zostawiał tę ścieżkę tylko ręcznej weryfikacji, a to
   najdroższy z naprawianych błędów.

**Korekta opisu z sekcji "Kontekst", punkt 4.** `DeadState._on_load_slot` nie dawał
czarnego ekranu: `states[:] = [states[-1]]` przy nieudanym wczytaniu zostawiało
`DeadState` na wierzchu (widoczny, `Restart` działał), ale **po cichu** - bez żadnej
reakcji na ekranie - i kasowało wszystko, co leżało pod spodem. Prawdziwy soft-lock był
w `DeathScreen._on_load_slot`, które wołało `_close_state()` **przed** `load()`, czyli
burzyło panel i stan zanim wiedziało, czy jest dokąd wracać (klasa nie jest dziś nigdzie
instancjonowana, więc nie objawiało się to w grze). Obie ścieżki naprawione.

Stan testów: `just test-unit` 442 testy, jedyna porażka `test_quest_graph_script.py`
(`"+50 zł"` vs `"+50 złota"`) jest **wcześniejsza i niezwiązana** - `scripts/quest_graph.py`
ma `"money": "złota"` już w `HEAD`. `just mypy` czysty, `just validate-locale` czysty,
`just test-smoke` 6/6, `Death then Load` zielony, trzy nowe scenariusze zielone na
desktopie i na web.

Do zrobienia przez usera (wymaga realnego ekranu, zrzuty headless nie są wierne -
notatka `headless-screenshot-not-faithful`): kryteria 4, 8, 9 i 10.

## Po zakończeniu

- odhacz B02 w `doc/audyt/audyt.md`
- commity (osobno, bo to trzy różne rzeczy):
  1. `B02: wersja gry jako string + kod porównawczy, jedna bramka zgodności zapisu`
  2. `B02: działający mechanizm migracji zapisów (łańcuch pusty do 1.0)`
  3. `B02: koniec soft-locka po nieudanym wczytaniu z ekranu śmierci` - z opisem objawu
- jeśli realizujesz później **H02** (śmierć → od razu ekran wczytania), ta ścieżka jest
  już bezpieczna - odnotuj to w pliku zadania H02, gdy będzie powstawał
- **przy pierwszym wydaniu 1.0**: zamroź `MIN_SUPPORTED_SAVE_CODE = 100` i przestań je
  podbijać. Od tego momentu obowiązuje reguła "zmiana formatu = migracja".
