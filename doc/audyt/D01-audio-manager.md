# D01 - AudioManager: muzyka per mapa, SFX eventów, głośność, web-safe

Priorytet: **P1** (Faza 3). Rozmiar: L. Zależności: brak twardych; po B01 (rdzeń jest
już pakietami `scene/` i `characters/`, więc hooki wpinasz w moduły, nie w monolit).

## Kontekst i problem

W grze **nie ma dźwięku w ogóle**: `grep -r mixer project/` = zero trafień, w
`project/assets/` nie ma ani jednego pliku audio. To największy odczuwalny brak w
pierwszej minucie gry (audyt, rozdz. 9): cisza przy uderzeniu, podniesieniu przedmiotu,
otwarciu panelu.

Co już jest i czego NIE trzeba budować:

- `project/save_load/display_settings.py` - persystencja ustawień gracza
  (desktop `<data_dir>/mom/settings.json`, web localStorage) z dwoma backendami.
  Głośności dopisujesz do istniejącego modelu `DisplaySettings`.
- `project/ui/panels/display_settings.py` - `SettingsPanel` z wierszem
  „rozdzielczość" cyklowanym strzałkami (`_cycle_resolution`, `on_left`/`on_right`).
  Wiersze głośności robisz **dokładnie tym samym wzorcem**, nie nowym widżetem.
- `project/config_model/routines.toml` - wzorzec ręcznie edytowanego TOML-a z
  komentarzem-instrukcją na górze pliku. `audio.toml` ma wyglądać tak samo.
- `scripts/validate_world.py` - lista `CHECKS` z funkcjami `check_*(world) ->
  list[Violation]`. Dopisujesz jedną funkcję, nie nowy skrypt.

## Decyzje autora (2026-07-28) - wiążące

1. **Assety pochodzą z `~/Projects/RPG/sounds/`** (poprzednia gra autora): 8 utworów
   w `music/` i 34 pliki w `sfx/`, wszystkie mp3, licencja Pixabay
   (`sounds/music/sources.txt`, `sounds/sfx/sfx.txt` - **przenieś oba pliki źródeł
   razem z assetami**, licencje muszą jechać z plikami). Łącznie 60 MB - w tej postaci
   NIE wchodzą do repo; patrz krok 2 (konwersja + budżet).
2. **Mapowanie mapa→muzyka i event→SFX mieszka w `project/config_model/audio.toml`**
   (jeden plik, ręcznie edytowany, walidowany przez `just validate-world`). Zgodnie ze
   złotą zasadą projektu: żadnego JSON-a do ręcznej edycji, żadnego CSV do struktury
   klucz-wartość.

## Cel

`project/audio.py` - jedno wejście do dźwięku dla całej gry:

- muzyka per mapa (Village, VillageHouse, LOST_CORK_TAVERN, JacobsChamber, labirynt,
  menu główne, ekran śmierci), z crossfade przy zmianie mapy i BEZ restartu utworu,
  gdy nowa mapa gra to samo;
- `audio.play_sfx("<event>")` wołane z kilkunastu miejsc w kodzie;
- trzy głośności (master / muzyka / SFX) w ustawieniach, zapisywane między sesjami;
- **działa na desktopie i na web**, a gdy mikser jest niedostępny (testy z
  `SDL_AUDIODRIVER=dummy`, CI, brak karty) - wszystkie wywołania są ciche no-opami
  i gra działa normalnie.

## Pliki do zmiany

- **nowy** `project/audio.py` - manager + moduł-fasada
- **nowy** `project/config_model/audio.toml` - manifest (muzyka per mapa, SFX per event)
- **nowe** `project/assets/audio/music/*.ogg`, `project/assets/audio/sfx/*.ogg`
  + `project/assets/audio/SOURCES.md` (licencje z RPG)
- `project/settings.py` - ścieżki (`AUDIO_DIR`, `MUSIC_DIR`, `SFX_DIR`), domyślne
  głośności, flaga `USE_AUDIO`
- `project/game.py` - inicjalizacja miksera i managera; wyciszenie przy pauzie
- `project/scene/map_state.py` - muzyka przy `go_to_map` / `reload_map`
- `project/characters/combat.py`, `characters/inventory.py`, `project/objects.py`,
  `project/ui/panels/*.py`, `project/quest/…` (przez `result_sink_adapter.py`) - wołania
  `play_sfx` w punktach z tabeli eventów
- `project/save_load/display_settings.py` - pola `volume_master/music/sfx`
- `project/ui/panels/display_settings.py` - trzy wiersze głośności
- `project/assets/locale/PL.toml` + `EN.toml` - etykiety ustawień
- `scripts/validate_world.py` - `check_audio_manifest`
- **nowy** `tests/test_audio.py`
- `project/AGENTS.md` + `pygbag.ini` (jeśli okaże się, że coś trzeba wykluczyć)

## Krok 0 (NAJPIERW, przed konwersją i przed kodem): sonda web

Nie buduj całego systemu, żeby na końcu odkryć, że web nie gra. Zrób najmniejszą
możliwą próbę:

1. Skopiuj **jeden** krótki plik ogg do `project/assets/audio/`, dopisz w
   `project/main.py`/`game.py` tymczasowe `pygame.mixer.init()` +
   `mixer.music.load(...)` + `play(-1)` pod flagą.
2. `just serve-web`, otwórz z `#debug`, sprawdź w konsoli: czy `mixer.init()` przechodzi,
   czy `music.play()` gra od razu, czy dopiero po kliknięciu/klawiszu.
3. Zapisz wynik (3-5 zdań + ewentualny błąd z konsoli) w pliku zadania niżej, w sekcji
   „Wynik sondy web", i **dopiero potem** projektuj resztę.

To determinuje dwie rzeczy: czy zostajemy przy ogg, i czy potrzebny jest „start
dźwięku przy pierwszym wejściu gracza" (patrz pułapki - `--ume_block 0` w recepturach
`serve-web`/`build-itchio` wyłącza pygbagowy ekran „kliknij, aby zacząć", a przeglądarki
blokują autoplay bez gestu użytkownika).

## Krok 1: manifest `audio.toml`

Format (nagłówek pliku = komentarz-instrukcja, jak w `routines.toml`):

```toml
# Mapowanie dźwięków. Klucze muzyki to nazwy map (plik .tmx bez rozszerzenia)
# + trzy konteksty specjalne: main_menu, death, maze.
# Klucze SFX to nazwy eventów wołane z kodu przez audio.play_sfx("<klucz>").
# Plik jest walidowany przez `just validate-world`: nieistniejący plik audio,
# nieznana mapa i nieużywany/nieznany event to twarde błędy.

[music]
main_menu        = "this-is-epic.ogg"
fight            = "to-the-death.ogg"
# Shire
Village          = "best-adventure-ever.ogg"
# misterious
VillageHouse     = "deep-in-the-dell.ogg"
# magic, harry potter style
LOST_CORK_TAVERN = "let-the-mystery-unfold.ogg"
# a bit spooky, more misterious
JacobsChamber    = "scary-spooky-ambient.ogg"
# spooky cave, slow, water drops
maze             = "caves-of-dawn.ogg"
death            = "tubular-bell-of-death.ogg"

[music.settings]
fade_ms   = 500     # crossfade przy zmianie mapy
volume    = 0.6     # mnożnik utworu względem suwaka muzyki

[sfx]
player_hit     = "male_hurt7.ogg"
monster_hit    = "punch-2.ogg"
monster_die    = "body-fall.ogg"
player_die     = "tubular-bell-of-death.ogg"
item_pick_up   = "item.ogg"
item_equip     = "item-equip.ogg"
# cut to only frist 2 seconds
item_drop      = "cardboard-box-drop.ogg"
coins          = "coins27.ogg"
sentiment_up   = "game-level-complete.ogg"
sentiment_down = "failfarefailure-drum-sound-effect.ogg"
# all toasts with negative effect: can't pickup, can't buy or sell, can't smash rock
toast_fail     = "failfarefailure-drum-sound-effect.ogg"
chest_open     = "game-level-complete.ogg"
quest_done     = "success-fanfare-trumpets.ogg"
# what does level done even mean?
level_done     = "level-passed.ogg"
# cut to only frist 2 seconds
panel_open     = "backpack.ogg"
menu_move      = "item-equip.ogg"
save_done      = "game-bonus.ogg"
maze_door      = "stairwellwalk.ogg"
wall_smash     = "punch-2.ogg"
# cut out only first sample
dailog_hero    = "voicepack.ogg"
# cut out only second sample
dailog_char    = "voicepack.ogg"
```

Zasady:

- **klucz muzyki = nazwa mapy** z `project/assets/NinjaAdventure/maps/*.tmx` (dziś:
  Village, VillageHouse, LOST_CORK_TAVERN, JacobsChamber) albo jeden z trzech
  kontekstów `main_menu` / `maze` / `death`. Brak wpisu dla mapy = **cisza**, nie błąd
  (nowa mapa nie może wywalić gry).
- **klucz SFX = nazwa eventu**, nie nazwa pliku. Kod nigdy nie zna nazw plików.
- Powyższa lista eventów jest propozycją minimalną - dobierz nazwy do realnych punktów
  w kodzie (krok 4), ale **nie rozdmuchuj**: kilkanaście eventów, każdy z realnym
  wywołaniem. Event bez wywołania = błąd walidatora.

## Krok 2: konwersja assetów i budżet rozmiaru

`~/Projects/RPG/sounds` to 60 MB mp3 - paczka web musi zostać mała (pygbag pakuje
`project/assets/` w całości; dziś sam `config.json` to 204 KB).

**Budżet: całe `project/assets/audio/` ≤ 10 MB.** Z tego muzyka ≤ 1,5 MB na utwór.

1. Wybierz **maksymalnie 8 utworów** (mapy + menu + labirynt + śmierć) i
   **maksymalnie 20 SFX-ów** z tabeli eventów. Reszty nie kopiuj.
2. Konwersja (ffmpeg jest w brew; jeśli go nie ma - zapytaj autora, nie instaluj sam):
   - muzyka: `ffmpeg -i in.mp3 -c:a libvorbis -q:a 1 -ac 1 -ar 44100 out.ogg`
     (mono, ~64-80 kbps; jeśli utwór wypada > 1,5 MB napisz ostrzeżenie w podsumowaniu)
   - SFX: `ffmpeg -i in.mp3 -c:a libvorbis -q:a 2 -ac 1 -ar 22050 out.ogg`
     + przytnij ciszę na końcu (`-af silenceremove`); cel ≤ 60 KB na plik
3. Nazwy plików: małe litery, myślniki, **bez losowych numerów Pixabaya**
   (`male_hurt7-48124.mp3` → `male_hurt7.ogg`).
4. `project/assets/audio/SOURCES.md`: przenieś treść `sources.txt` i `sfx.txt` z RPG,
   dopisz mapowanie stara-nazwa → nowa-nazwa (żeby dało się wrócić do oryginału).
5. Po konwersji zmierz i zapisz w commicie: rozmiar katalogu audio oraz rozmiar paczki
   web przed/po (`just build-itchio` → `web.zip`).

## Krok 3: `project/audio.py`

Kształt (zgodny z B01: system to moduł z funkcjami, stan w jednym obiekcie):

```python
class AudioManager:
    def __init__(self, manifest_path: Path) -> None: ...
    @property
    def available(self) -> bool: ...          # mikser wstał i manifest się wczytał
    def play_music(self, key: str) -> None: ...   # nazwa mapy albo kontekst
    def stop_music(self, fade_ms: int | None = None) -> None: ...
    def play_sfx(self, key: str) -> None: ...
    def set_volumes(self, master: float, music: float, sfx: float) -> None: ...

# fasada modułowa - to woła reszta kodu, bez przekazywania referencji do gry
def init(manifest_path: Path) -> AudioManager: ...
def play_music(key: str) -> None: ...
def play_sfx(key: str) -> None: ...
```

Wymagania:

- `init()` woła `pygame.mixer.init()` w `try/except Exception`. **Każdy** wyjątek =
  `available = False`, jedna linia logu, dalej wszystko jest no-opem. Gra bez karty
  dźwiękowej, testy z `SDL_AUDIODRIVER=dummy` i CI mają działać identycznie jak dziś.
- Wczytanie manifestu przy starcie; `mixer.Sound` **ładowane leniwie** przy pierwszym
  użyciu i cache'owane (nie ładuj 16 plików w `__init__` - to koszt startu na web).
- `play_music(key)`: gdy `key` gra już teraz - **nic nie rób** (bez restartu utworu przy
  wracaniu do tej samej mapy). Zmiana = `fadeout(fade_ms)` + `load` + `play(-1)`.
- Nieznany klucz SFX = jedna linia ostrzeżenia w logu i no-op (nigdy wyjątek w runtime;
  od łapania literówek jest walidator).
- Zero importów z `scene`/`characters`/`game` (moduł ma być importowalny w teście
  jednostkowym bez SDL-a).
- Głośność efektywna: `master * kanał` (osobno muzyka, osobno SFX), zakres 0.0-1.0.

## Krok 4: hooki w grze

| Event | Miejsce w kodzie |
| --- | --- |
| `player_hit`, `monster_hit` | `project/characters/combat.py` (`hit`) |
| `monster_die`, `player_die` | `project/characters/combat.py` (`die`) |
| `item_pick_up`, `item_drop` | `project/characters/inventory.py` |
| `coins` | `project/result_sink_adapter.py` (`add_money`) + handel w `ui/panels/trade.py` |
| `chest_open` | `project/objects.py` (skrzynie) |
| `quest_done` | `project/quest/…` przez `result_sink_adapter.py` |
| `panel_open`, `menu_move` | `project/ui/panels/*.py` (wspólne miejsce w `ui/manager.py`, jeśli istnieje - lepsze niż 8 osobnych wywołań) |
| `save_done` | `project/save_load/manager.py` (udany zapis) |
| `wall_smash` | ścieżka `DESTRUCTIBLE_MIN_DAMAGE` |
| muzyka mapy | `project/scene/map_state.py` (`go_to_map`, `reload_map`) - obok istniejącego hooka `quests.on_event("map_change")` |
| muzyka menu / śmierci | `project/ui/panels/main_menu.py`, `ui/panels/save_load.py` (`DeathScreen`) |

Labirynt: klucz `maze` ma pierwszeństwo przed nazwą mapy, gdy `scene.is_maze`.

## Krok 5: głośność w ustawieniach

1. `DisplaySettings` (dataclass w `save_load/display_settings.py`): trzy pola float
   0.0-1.0, domyślnie `1.0 / 0.7 / 0.8`. **Wczytanie musi tolerować brak pól** (stary
   `settings.json` gracza) - jak dziś reszta pól.
2. `SettingsPanel`: trzy wiersze cyklowane strzałkami dokładnie jak rozdzielczość
   (`_button_types` dostaje `volume_master` / `volume_music` / `volume_sfx`), krok 10%,
   etykieta `"Muzyka: 70%"` z locale. Zmiana natychmiast woła `audio.set_volumes(...)`
   (gracz ma słyszeć efekt) i zapisuje przez istniejący storage.
3. Klucze locale w PL.toml i EN.toml - `just validate-locale` musi przechodzić.

## Krok 6: walidator

`check_audio_manifest(world)` w `scripts/validate_world.py`, dopisany do `CHECKS`:

- każdy plik z `[music]` i `[sfx]` istnieje na dysku;
- każdy klucz muzyki to istniejąca mapa albo jeden z `main_menu` / `maze` / `death`;
- każdy klucz SFX jest realnie wołany w kodzie (grep po `play_sfx("<klucz>")` w
  `project/`) - event bez wywołania to martwy wpis;
- każde `play_sfx("x")` w kodzie ma wpis w manifeście (odwrotny kierunek - to łapie
  literówkę w wywołaniu).

## Kryteria akceptacji

1. `tests/test_audio.py` (samodzielny skrypt z listą `tests = [...]`, jak reszta):
   parsowanie manifestu, nieznany klucz SFX = no-op bez wyjątku, tryb „mikser
   niedostępny" (zasymuluj wyjątek z `mixer.init`) = wszystkie metody no-op,
   `play_music` tym samym kluczem drugi raz nie przeładowuje utworu.
2. `just test-unit` w całości zielone; `just mypy` = 0; `just validate-world` = 0
   naruszeń; `just validate-locale` zielone.
3. Desktop: `just run` - muzyka gra na Village, zmienia się przy wejściu do
   VillageHouse i do labiryntu, wraca bez restartu przy powrocie na tę samą mapę;
   suwaki w ustawieniach działają na żywo i przeżywają restart gry.
4. Web: `just serve-web` - muzyka gra (po ewentualnym geście użytkownika z kroku 0),
   SFX-y grają, brak błędów w konsoli JS. `MOM_SKIP_SS_REVIEW=1 just test-smoke`
   zielone (6 scenariuszy).
5. Rozmiar: `project/assets/audio/` ≤ 10 MB; w opisie commita podany rozmiar `web.zip`
   przed i po.
6. Testy agentowe (desktop) nie regresują - dźwięk nie może zmieniać taktowania
   scenariuszy ani generować wyjątków przy `SDL_AUDIODRIVER=dummy`.

## Pułapki

- **`--ume_block 0`** w recepturach `serve-web` i `build-itchio` wyłącza pygbagowy ekran
  startowy. Bez gestu użytkownika przeglądarka może zablokować autoplay - wtedy
  rozwiązaniem jest start muzyki przy pierwszym realnym wejściu gracza (klawisz/klik),
  a nie zmiana `--ume_block` (to zmiana zachowania całego buildu - jeśli uznasz, że
  jest potrzebna, ZAPYTAJ autora).
- `pygame.mixer.music` to **jeden** strumień - nie da się grać dwóch utworów naraz;
  crossfade robisz przez `fadeout` + `load` + `play`.
- Kanały SFX są ograniczone (domyślnie 8). Przy młócce w labiryncie ustaw
  `mixer.set_num_channels(...)` i pozwól nowym dźwiękom wypierać stare - lepiej urwany
  SFX niż zjedzony klawisz.
- `mixer.init()` **przed** `pygame.init()` bywa kapryśny; wołaj po `pygame.init()`
  w `Game.__init__` (linia ~137), ale **przed** pierwszym `load_map`.
- Testy jednostkowe ustawiają `SDL_AUDIODRIVER=dummy` przed importem pygame -
  nie licz na to, że to zawsze zadziała: ścieżka „mikser niedostępny" ma być
  przetestowana jawnie.
- Nie dokładaj audio do save'ów - to ustawienie gracza, nie stan świata
  (`display_settings.py`, nie `save_load/models.py`; patrz B02 i bramka wersji zapisu).
- `git` i duże pliki binarne: konwertuj do docelowego rozmiaru **przed** pierwszym
  commitem; mp3 z RPG nie mają trafić do historii repo nawet przejściowo.
- Memory projektu `headless-screenshot-not-faithful` - dźwięku i tak nie widać na
  zrzucie; weryfikacja słuchowa jest po stronie autora.

## Po zakończeniu

- opisz system w `project/AGENTS.md` (nowa sekcja „Audio": manifest, eventy, tryb
  no-op, budżet rozmiaru) i dopisz `audio.toml` do opisu pipeline'u treści
- odhacz D01 w `doc/audyt/audyt.md`
- commit: `D01: AudioManager - muzyka per mapa z audio.toml, SFX eventów, głośność w ustawieniach`

## Wynik sondy web (krok 0, 2026-07-29)

Sonda: tymczasowe `mixer.init()` + `music.load/play(-1)` + `mixer.Sound(...).play()`
w `Game.__init__`/`Game.loop` (kod usunięty po sondzie), pygbag na `127.0.0.1:8001`,
headless chromium przez Playwrighta, zrzut konsoli JS.

1. `pygame.mixer.init()` **przechodzi** na pygbag: `get_init() == (48000, -16, 2)`.
   Zostajemy przy **ogg vorbis** - i `mixer.music`, i `mixer.Sound` wczytują ogg bez
   problemu (`Sound.get_length()` zwraca poprawną długość).
2. Autoplay jest **zablokowany bez gestu użytkownika**. Konsola:
   `Cannot play before user interaction, will retry` + nieprzechwycone
   `NotAllowedError: play() failed because the user didn't interact with the document
   first`. Pygbagowe „will retry" **nie działa** - po 40 s i po kliknięciu utwór dalej
   stał na `get_pos() == 0`.
3. Po geście użytkownika trzeba **ponowić `music.play(-1)` z kodu** - wtedy gra
   (`get_pos()` rośnie 2993 → 28480 ms). SFX (`mixer.Sound.play()`) po geście też gra.
4. `mixer.music.get_busy()` na web zwraca **`False` mimo grającego utworu** (na desktopie
   działa normalnie). Nie wolno na nim opierać logiki „co teraz gra" - manager trzyma
   własny stan (`_current_key`), a `get_busy()` nie jest używane nigdzie.

Wniosek dla implementacji (bez zmiany `--ume_block`, zgodnie z pułapkami):
`AudioManager` ma bramkę `_unlocked`. Na web startuje `False` i **nic nie jest wołane
do miksera** (żadnego `play`) - dzięki temu w konsoli nie ma `NotAllowedError`. Pierwsze
realne wejście gracza (`KEYDOWN` / `MOUSEBUTTONDOWN` / przycisk pada) woła
`audio.unlock()`, które odpala odłożony utwór. Na desktopie `_unlocked` startuje `True`.
