# B02 - polityka wersji save + minimalna migracja

Priorytet: **P2** (Faza 2). Rozmiar: M.
Zależności: B01 (refactor rdzenia) - zrealizowane; A02 (asercje `ui_state`) - zrealizowane.
Powiązanie: **H02** (śmierć gracza → od razu ekran wczytania) stoi na ścieżce, którą to
zadanie naprawia - patrz krok 4.

## Kontekst i problem

Save ma wersję, ale nie ma **polityki** wersjonowania. Cztery konkretne skutki:

### 1. Wersja save = wersja gry

`save_load/models.py:20`:

```python
SAVE_VERSION: float = VERSION      # VERSION = 0.3, settings.py:37
```

Numer schematu zapisu jest przyspawany do numeru wersji gry. Podbicie `VERSION` na 0.4
z jakiegokolwiek powodu - nowa treść, nowa mechanika, wydanie na itch.io -
**unieważnia wszystkie istniejące zapisy**, choć format się nie zmienił. Odwrotnie też
boli: realna zmiana formatu bez podbicia `VERSION` przechodzi niezauważona.

Komentarz `settings.py:35-36` pokazuje, że to już się zdarzyło raz naprawdę:
*"0.2: sentiment keys renamed (...) - older saves are incompatible and rejected on load
with a terminal message"*.

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

### 3. Ładowanie odrzuca wszystko, co nie jest równe

`save_load/manager.py:92-94`:

```python
if save.metadata.version != SAVE_VERSION:
    print(f"[save] version mismatch: ...")
    return False
```

Twarde `!=`: starszy zapis, który migracja umiałaby podnieść, leci do kosza tak samo
jak zapis z przyszłości.

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
  pod spodem - **twardy soft-lock**. Ta sama ścieżka jest w `DeathScreen._on_load_slot`
  (`:795-799`).
- `list_slots()` (`backends.py:82-94`, `:134-146`) pokazuje niekompatybilny slot jak
  każdy inny - z nazwą, datą i czasem gry. Nic w UI nie mówi, że go nie da się wczytać.

### Co już jest gotowe do wykorzystania

`scripts/save_fixtures.py:104-111` ma `corrupt_save_version()` (zapis z `version: 9999`),
a runner obsługuje go po obu stronach - desktop `tests/automate_display_test.py:983-984`,
web `:1349-1350`. **Żaden scenariusz go nie używa.** Fixture czeka gotowy.

## Cel

- Wersja **schematu zapisu** odklejona od wersji gry, jako `int`.
- Spisana polityka: kiedy się podbija, a kiedy nie, i co się dzieje przy ładowaniu
  starszego / nowszego zapisu.
- Migracja działa naprawdę: jest wołana z jedynego wspólnego punktu i ma pierwszy,
  prawdziwy wpis, dzięki któremu **dzisiejsze zapisy gracza przeżywają tę zmianę**.
- Odmowa wczytania jest widoczna w grze i nigdzie nie zwija stanu gry.

## Polityka wersji (treść do spisania)

To jest deliverable tekstowy zadania - trafia do docstringa sekcji wersjonowania
w `save_load/models.py` i w skrócie do `project/AGENTS.md` (sekcja "Persystencja stanu").
Nie robimy osobnego dokumentu HTML - to reguła inżynierska, nie decyzja projektowa.

**Numer schematu** `SAVE_SCHEMA_VERSION: int` opisuje **układ pliku zapisu**, nie wydanie
gry. Wersja gry jedzie osobno, jako pole informacyjne.

**Kiedy NIE podbijamy** (to jest domyślny przypadek): dodanie pola z wartością domyślną,
którą `from_dict` wstawi starym zapisom. Tak powstały `NPCState.config_key`,
`NPCState.runtime`, `SaveGame.world_seed` i `PlayerState.damage` - każde z komentarzem
"saves written before this existed still load". Ta praktyka jest dobra i zostaje.

**Kiedy podbijamy + piszemy migrację**: zmiana nazwy pola, usunięcie pola, zmiana
znaczenia wartości przy tej samej nazwie (jak przemianowanie kluczy sentymentu w 0.2),
zmiana typu, której `int()`/`str()` nie połknie.

**Reguły ładowania:**

| Wersja w pliku | Zachowanie |
|---|---|
| `== SAVE_SCHEMA_VERSION` | ładuj |
| `< SAVE_SCHEMA_VERSION` | przepuść przez migracje po kolei, potem ładuj |
| `> SAVE_SCHEMA_VERSION` | **odmów** z widocznym komunikatem - nie da się znać przyszłości |
| brak łańcucha migracji do danej wersji | odmów z widocznym komunikatem |

## Pliki do zmiany

- `project/save_load/models.py` - `SAVE_SCHEMA_VERSION`, `SaveMetadata`, sekcja migracji,
  wpięcie `migrate_save` w `SaveSlot.from_dict`
- `project/save_load/manager.py` - warunek z linii 92 (tylko "z przyszłości" odrzuca)
- `project/ui/panels/save_load.py` - notyfikacja przy nieudanym wczytaniu, oznaczenie
  niekompatybilnego slotu, naprawa `DeadState._on_load_slot` i `DeathScreen._on_load_slot`
- `project/assets/locale/PL.toml` i `EN.toml` - nowe klucze w sekcji `[save]`
- `scripts/save_fixtures.py` - `minimal_save_dict` pod nowy schemat
- `tests/test_save_load_models.py` - testy polityki i migracji
- `tests/scenarios.json` - nowy scenariusz `Incompatible Save Rejected`
- `project/AGENTS.md` - sekcja "Persystencja stanu" (~linia 576)

## Kroki

### Krok 1 - rozdzielenie wersji schematu od wersji gry

W `models.py`:

```python
SAVE_SCHEMA_VERSION: int = 1     # układ pliku zapisu, NIE wersja gry
```

`SaveMetadata` dostaje `version: int = SAVE_SCHEMA_VERSION` oraz nowe, czysto
informacyjne pole `game_version: float = VERSION` (do diagnostyki i do pokazania
w UI/logu; **nigdy nie bramkuje ładowania**). Zauważ, że dodanie `game_version`
jest samo w sobie przykładem "pole z domyślną = bez podbicia schematu".

`SaveMetadata.from_dict` musi znieść surową wartość zmiennoprzecinkową ze starego pliku,
gdyby ktoś zawołał je z pominięciem migracji (robią tak testy):
`int(float(data.get("version", SAVE_SCHEMA_VERSION)))` - `0.3` czyta się wtedy jako
schemat `0`, co jest dokładnie prawdą.

Zostaw alias `SAVE_VERSION = SAVE_SCHEMA_VERSION` **tylko jeśli** grep pokaże importy,
których nie chcesz ruszać w tym kroku; docelowo ma zniknąć (dziś importuje go
`manager.py:14` i `tests/test_save_load_models.py:32`).

### Krok 2 - migracja działa naprawdę

- Napraw sortowanie: `sorted(_MIGRATIONS, key=lambda pair: pair[0])` (`models.py:546`).
- Zarejestruj pierwszą **prawdziwą** migrację `0 → 1`, o takiej semantyce:
  - `version >= 0.3` (stary schemat "numer gry", układ identyczny z dzisiejszym)
    → podnieś do `1`, nic w danych nie zmieniaj. **To jest ta migracja, dzięki której
    dzisiejsze zapisy gracza działają dalej po tej zmianie.**
  - `version < 0.3` (0.1 / 0.2 - przemianowane klucze sentymentu, `settings.py:35`)
    → migracja się nie udaje; zapis zostaje odrzucony jako niekompatybilny.
- `migrate_save()` musi zwracać informację o niepowodzeniu, a nie po cichu oddawać
  niezmigrowane dane - inaczej odrzucenie zależy od tego, czy ktoś dalej sprawdzi wersję.
  Zwróć `tuple[dict, bool]` albo rzucaj wyjątek własnego typu; wybierz jedno i trzymaj
  się tego w obu ścieżkach (`SaveSlot.from_dict`, `manager.load`).
- Usuń placeholder `migrate_v0_to_v1` albo zamień go w tę prawdziwą migrację - nie
  zostawiaj obu.

**Punkt wpięcia: `SaveSlot.from_dict` (`models.py:483-490`).** To jedyne miejsce, przez
które przechodzą oba backendy (`backends.py:57` plik, `:113` localStorage) **i** podgląd
listy slotów. Migruj surowy `save_data` **przed** `SaveGame.from_dict`. Nie wpinaj tego
w `manager.load()` - tam jest już zdeserializowany obiekt, a lista slotów w UI ominęłaby
migrację i pokazywała stare metadane.

### Krok 3 - reguły odmowy zamiast twardego `!=`

`manager.py:92` ma odrzucać **wyłącznie** dwa przypadki: zapis z przyszłości
(`version > SAVE_SCHEMA_VERSION`) i zapis, którego migracja nie objęła. Starsze,
zmigrowane zapisy przechodzą normalnie. `load()` dalej zwraca `bool`, ale wołający musi
umieć odróżnić "pusty slot" od "niekompatybilny" - dodaj metodę pomocniczą
(np. `SaveManager.slot_compatibility(slot_idx)`) albo pole z powodem ostatniej porażki.
UI z kroku 4 tego potrzebuje.

### Krok 4 - widoczna odmowa i koniec soft-locka

- **Nowe klucze locale** w `[save]` (PL i EN, obie muszą mieć te same klucze -
  `just validate-locale` to sprawdza):
  `load_failed` ("Nie udało się wczytać zapisu"), `incompatible` ("Niezgodna wersja zapisu").
- `LoadPanel._do_load` (`:739`) - `else` z notyfikacją `NotificationTypeEnum.error`
  (sprawdź dostępne warianty w `enums.py`). Z menu głównego notyfikacje też działają -
  `_PanelSceneProxy.add_notification` (`ui/panels/main_menu.py:369-372`) przekazuje je
  do żywej sceny.
- `DeadState._on_load_slot` (`:874`) i `DeathScreen._on_load_slot` (`:795`) -
  **sprawdź wynik `load()`**. Przy `False` nie ruszaj `game.states`, zostań na ekranie
  śmierci i pokaż komunikat. To jest naprawa soft-locka, nie kosmetyka.
- **Oznaczenie slotu na liście.** `_SlotButton.parts` (`:91-108`) zwraca `(name, meta)`;
  `_draw_slot_row` (`:111-126`) rysuje nazwę do lewej, meta do prawej. Dla
  niekompatybilnego slotu podmień **meta** na `_("save.incompatible")` i rysuj nazwę
  kolorem `theme.GREY`. Nie dokładaj trzeciego elementu do wiersza - istniejący układ
  dwukolumnowy jest odporny na przepełnienie (A03, `just test-unit layout_checks`),
  a nowy element trzeba by przez te self-checki przepychać.
  `SaveSlotInfo.metadata.version` jest tu dostępne bez czytania całego zapisu.

### Krok 5 - testy

**Jednostkowe** (`tests/test_save_load_models.py`, pamiętaj o dopisaniu funkcji
do listy `tests = [...]` na dole pliku - runner wywala plik, w którym `test_*` tam nie ma):

- zapis z `version: 0.3` (dzisiejszy format) → po migracji `version == 1`, dane
  identyczne pole po polu;
- zapis z `version: 0.2` → migracja odmawia;
- zapis z `version: 9999` → odrzucony jako "z przyszłości";
- zapis bez klucza `version` → traktowany jak schemat 0;
- **własność "pole z domyślną nie wymaga podbicia"**: weź `SaveGame().to_dict()`, usuń
  z niego `world_seed` i `player.damage`, przepuść przez `from_dict` - musi wyjść obiekt
  z wartościami domyślnymi, bez migracji;
- dwie migracje zarejestrowane pod **tą samą** wersją → `migrate_save` nie rzuca
  `TypeError` (regresja na `sorted`, punkt 2 kontekstu).

**Scenariusz agentowy** `Incompatible Save Rejected` w `tests/scenarios.json`
(`platform: ["desktop", "web"]`):

- `setup_saves: [{"slot": 1, "type": "corrupt_version"}]` - slot 1, nie 0 (slot 0 jest
  zarezerwowany dla F5/F9 i tylko do odczytu z poziomu gracza, `settings.py:296-299`);
- akcje: start gry → menu → panel wczytywania → wybór slotu → potwierdzenie →
  `screenshot`. Sekwencję klawiszy skopiuj ze scenariusza `Load from Main Menu`, nie
  wymyślaj od zera;
- asercje: `process_alive`; `ui_state` potwierdzające, że gra **nie** weszła do
  wczytanego świata (panel/menu dalej na wierzchu); `no_layout_violations`;
  `screenshot_review` z oczekiwaniem "widoczny komunikat o niezgodnej wersji zapisu,
  gra nie wczytała się i nie zawiesiła".

## Kryteria akceptacji

1. `just test-unit` w całości zielony, z nowymi testami z kroku 5.
2. `just mypy` = `Success: no issues found`.
3. `just validate-locale` zielony (klucze PL i EN symetryczne).
4. **Zapis sprzed zmiany wczytuje się po zmianie.** Przed pierwszym commitem tego zadania:
   uruchom grę, zapisz do slotu 2, skopiuj plik `<data_dir>/mom/saves/save_2.mom` poza
   katalog. Po zmianie: wgraj go z powrotem, wczytaj z menu - gra ma wstać w tym samym
   miejscu, a `metadata.version` w pliku po ponownym zapisie ma być `1`.
5. `MOM_SKIP_SS_REVIEW=1 just test-agent "Incompatible Save Rejected"` zielony;
   ten sam scenariusz na web: `MOM_SKIP_SS_REVIEW=1 just test-web "Incompatible Save Rejected"`.
6. `MOM_SKIP_SS_REVIEW=1 just test-smoke` zielony (6 scenariuszy) - w tym
   `Save and Load Basic` i `Auto Save on Maze Entry`, czyli happy path zapisu.
7. `MOM_SKIP_SS_REVIEW=1 just test-agent "Death then Load"` zielony (happy path ekranu
   śmierci nie drgnął).
8. **Ręczna weryfikacja soft-locka:** `.venv/bin/python scripts/save_fixtures.py
   corrupt_version 1`, `just run`, zgiń, spróbuj wczytać slot 1 → ekran śmierci zostaje,
   widać komunikat, `Restart` dalej działa. Przed naprawą ta sama ścieżka zostawia pustą
   grę bez sceny.
9. Panel wczytywania pokazuje niekompatybilny slot jako wyszarzony z komunikatem zamiast
   daty - zweryfikuj na realnym ekranie (zrzuty headless nie są wierne dla pełnej
   kompozycji, patrz notatka pamięci `headless-screenshot-not-faithful`).
10. Polityka spisana w docstringu `save_load/models.py` i streszczona
    w `project/AGENTS.md`.

## Pułapki

- **Nie podbijaj `SAVE_SCHEMA_VERSION` w tym zadaniu.** Startujemy od `1` i to jest
  wartość docelowa po migracji `0 → 1`. Zadanie ma zbudować mechanizm, nie użyć go.
- **Migracja w `SaveSlot.from_dict` dotyka też `list_slots()`**, które czyta wszystkie
  10 slotów przy każdym otwarciu panelu. Trzymaj ją tanią - to czysta operacja na dictach,
  bez I/O i bez logowania w pętli (10 printów przy każdym otwarciu panelu to szum, który
  utopi realne komunikaty w logu scenariuszy).
- **`float` w starych plikach.** `0.1 + 0.2 != 0.3` - nie porównuj wersji z pliku przez
  `==` do literału zmiennoprzecinkowego. Progi przez `<` / `>=` albo najpierw
  normalizacja do int.
- **`save_fixtures.minimal_save_dict` ma `version: int = 1`** (`:39`) - pod dzisiejszym
  schematem `0.3` to zapis "z przyszłości" i nikt tego nie zauważył, bo żaden scenariusz
  nie używa typu `minimal`. Po tej zmianie `1` staje się poprawną wartością; sprawdź, czy
  to nie zamienia przypadkiem fixture'u testowego w zapis, który **da się** wczytać, gdy
  scenariusz oczekiwał czegoś innego.
- **`corrupt_version` używa `9999`** (`save_fixtures.py:108`) - zostaw, to jest wprost
  przypadek "z przyszłości", którego potrzebuje nowy scenariusz.
- **`corrupt_save` (nieprawidłowy JSON) to inna ścieżka** - backend łapie wyjątek
  i zwraca `None` (`backends.py:58-60`), więc slot w ogóle nie istnieje dla UI. Nie zlewaj
  jej z niekompatybilną wersją; scenariusz `Corrupt Save Handling` ma dalej przechodzić
  bez zmian.
- **Web ma osobny magazyn.** `localStorage` przeżywa reload i zamknięcie strony;
  przy ręcznym testowaniu na web czyść klucze `MoM.save_*` między próbami, inaczej
  testujesz zapis z poprzedniego przebiegu (patrz notatka `web-test-singleton-run-hygiene`).
- **Dual-target:** żadnego pydantic w `save_load/` - moduł jest wspólny dla desktopu
  i web (docstring `models.py:1-7`) i to się nie zmienia.
- Web-flaki najpierw powtórz 2x, dopiero potem oglądaj `screenshots/agent/`.

## Po zakończeniu

- odhacz B02 w `doc/audyt/audyt.md`
- commit: `B02: wersja schematu save odklejona od wersji gry + działająca migracja`
  (naprawa soft-locka ekranu śmierci warta osobnego commita z opisem objawu)
- jeśli realizujesz później **H02** (śmierć → od razu ekran wczytania), ta ścieżka jest
  już bezpieczna - odnotuj to w pliku zadania H02, gdy będzie powstawał
