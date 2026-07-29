# H02 - dzienny autosave o 6:00 (śmierć gracza: druga połowa zadania jest już zrobiona)

Priorytet: **P2** (Faza 3). Rozmiar: S. Zależności: brak (B02 zamknięte).

## Kontekst i problem

Znaleziska G-1 / D-9: śmierć = pełny reset ekwipunku do stanu z configu + respawn
w wiosce. **Decyzja autora (2026-07-25): kary nie zmiękczamy** - realne ryzyko śmierci
jest w labiryncie, a przed wejściem do niego gra już autosave'uje. Zamiast tego gracz
ma dostać dwie rzeczy: świeży punkt powrotu i szybką drogę do niego.

**Połowa tego zadania powstała przy B02** (2026-07-28):

- `DeathScreen` (`project/ui/panels/save_load.py:798`) pokazuje po śmierci listę
  zapisanych slotów do wczytania, z widoczną odmową wczytania (niezgodna wersja =
  komunikat na panelu, nie cichy print do konsoli) i bez niszczenia stanu gry.
- Autosave przy wejściu do labiryntu działa (`project/scene/map_state.py:152-157`,
  slot `QUICK_SAVE_SLOT` + toast `notify.autosaved_quick`).

**Zostaje:** dzienny autosave, żeby gracz spędzający liczne godziny na powierzchni (questy,
handel, dialogi) też miał świeży punkt powrotu.

## Decyzja autora (2026-07-28) - wiążąca

- **godzina: 6:00 czasu gry** (nie północ - gracz „budzi się" po pełnej dobie postępu);
- **slot: 0 (`QUICK_SAVE_SLOT`)**, ten sam, którego używa F5/F9 i autosave labiryntu.
  Tak, to nadpisuje ręczny szybki zapis gracza - świadomy wybór: jeden zawsze świeży
  punkt powrotu jest wart więcej niż drugi slot do pilnowania. Gracz ma o tym wiedzieć
  z toastu.

## Cel

Przy przejściu zegara świata przez 6:00 gra zapisuje się do slotu 0 i pokazuje toast.
Dokładnie raz na dobę gry, także gdy czas przeskoczy przez 6:00 jednym skokiem.

## Pliki do zmiany

- `project/scene/world_clock.py` - wykrycie przekroczenia 6:00 (`tick`, `next_day`)
- `project/scene/scene.py` - wykonanie zapisu + toast (zegar zostaje bez zależności
  od `save_manager`; patrz „Pułapki")
- `project/settings.py` - stała `DAILY_AUTOSAVE_HOUR = 6` (0-23; `None` = wyłączone)
- `project/assets/locale/PL.toml` + `EN.toml` - klucz `notify.autosaved_daily`
- **nowy/rozszerzony** `tests/test_world_clock.py` - logika wykrywania przekroczenia
- `tests/scenarios.json` - scenariusz agentowy z `start_hour`
- `project/AGENTS.md` - opis reguły autosave'u

## Krok 1: wykrycie przekroczenia godziny

W `world_clock.tick` zegar rośnie minutami, a `hour` przeskakuje o 1 przy przepełnieniu
(`world_clock.py:84-91`). Wykrycie ma być oparte na **absolutnej minucie**
(`abs_minutes(scene)` - istnieje, jest monotoniczna przez północ i przez skoki dni),
a nie na porównaniu `hour == 6`:

1. Scene trzyma `last_daily_autosave_abs: int` (minuta absolutna ostatniego dziennego
   autosave'u; `-1` = jeszcze nigdy).
2. Po przesunięciu zegara policz minutę absolutną **najbliższego minionego** 6:00.
   Jeśli jest większa niż `last_daily_autosave_abs` → wyzwól autosave i zapamiętaj ją.
3. Ta konstrukcja z definicji obsługuje skok o kilka godzin/dni (sen, `next_day`,
   `apply_days`) jednym zapisem, a nie serią.

## Krok 2: wykonanie zapisu

Wyzwolenie zapisu **nie może** mieszkać w `world_clock` (moduł zegara nie zna
`save_manager` ani powiadomień - trzymaj granice z B01). Zegar zwraca informację
„przekroczono granicę doby", a `Scene.update` (albo cienka funkcja w `scene/`)
wykonuje:

```python
if (scene.game.save_manager.save(QUICK_SAVE_SLOT)):
    scene.add_notification(_("notify.autosaved_daily"), NotificationTypeEnum.info)
```

Warunki blokujące zapis (pomiń zapis, ale **zaktualizuj** znacznik, żeby nie próbować
co klatkę):

- trwa intro/cutscena (`scene.cutscene_framing` / stan intro),
- gracz jest martwy (na stosie stanów jest `DeadState`),
- `save_manager` nie istnieje (ścieżki testowe konstruujące Scene wprost - memory
  `headless-scene-stepping-verification`).

Dialog, panel handlu czy otwarty ekwipunek **nie** blokują - zapis ma być niewidoczny
dla gracza poza toastem.

## Krok 3: zapis stanu znacznika

`last_daily_autosave_abs` jest częścią stanu świata - musi trafić do zapisu
(`GameClockState` w `save_load/models.py`), inaczej wczytanie zapisu z 05:59 i przejście
przez 6:00 zrobi autosave, ale wczytanie tego samego zapisu drugi raz zrobi go
ponownie… i tak w kółko przy każdym wczytaniu. Zgodnie z polityką z
[B02](B02-polityka-wersji-save.md): **dodanie pola = zmiana formatu zapisu** - podbij
wersję gry, dopisz wpis do `save_compatibility` i migrację (stary zapis: `-1`).

Alternatywa do rozważenia, jeśli chcesz uniknąć zmiany formatu: wyprowadź znacznik
z zegara przy wczytaniu (`last = najbliższe minione 6:00`), wtedy nic nie dochodzi do
`PlayerState`/`GameClockState`. **Wybierz jedną drogę i uzasadnij ją w commicie** -
druga jest tańsza, ale gubi informację „dziś już zapisano" po wczytaniu zapisu z 6:30.

## Kryteria akceptacji

1. Test jednostkowy (samodzielny skrypt z listą `tests = [...]`):
   - tick przez 5:59 → 6:01 wyzwala dokładnie jeden autosave;
   - skok o 3 doby (`apply_days(3)` / `next_day` ×3) wyzwala **jeden** autosave;
   - dwa kolejne ticki tej samej doby po 6:00 nie wyzwalają drugiego;
   - `DAILY_AUTOSAVE_HOUR = None` wyłącza mechanizm.
2. Scenariusz agentowy (`"start_hour": 5`): poczekaj do przekroczenia 6:00 →
   `ui_state` potwierdza toast/zapis, slot 0 istnieje i ma świeży znacznik czasu.
   Zielony na desktopie i na web.
3. Po śmierci `DeathScreen` pokazuje ten slot jako wybieralny (ręczna weryfikacja
   przez `debug_death_screen` w `agent_ctrl`).
4. `just test-unit`, `just mypy` = 0, `just validate-locale`,
   `MOM_SKIP_SS_REVIEW=1 just test-smoke` - zielone.
5. Toast nie zaśmieca ekranu: jeden na dobę gry, nie na każdą klatkę o 6:00.

## Pułapki

- `GAME_TIME_SPEED` sprawia, że doba gry mija w kilka minut realnych - przy testach
  ręcznych 6:00 przychodzi szybciej, niż się spodziewasz; przy scenariuszach ustaw
  `start_hour` tuż przed granicą, zamiast czekać.
- Zapis na web idzie do localStorage i potrafi być wolniejszy - nie rób go w środku
  ciasnej pętli klatki bez potrzeby (raz na dobę gry to nie problem, ale nie „napraw"
  tego dokładaniem zapisu przy każdej zmianie godziny).
- `QUICK_SAVE_SLOT` jest w UI slotem tylko-do-odczytu (nie da się go nazwać ani
  skasować) - nie zmieniaj tej zasady.
- Nie dubluj toastu z autosave'em labiryntu: jeśli gracz wchodzi do labiryntu o 6:00,
  dopuszczalne są dwa zapisy, ale **nie** dwa identyczne komunikaty pod rząd
  (drugi zapis nadpisze pierwszy - to jest w porządku, komunikat ma być jeden).
- Memory `deterministic-dialog-testing` / `headless-screenshot-not-faithful`: toast
  weryfikuj asercją `ui_state` (A02), nie zrzutem ekranu.

## Po zakończeniu

- dopisz regułę do `project/AGENTS.md` (sekcja save/load: „autosave przy wejściu do
  labiryntu ORAZ o 6:00 czasu gry, oba do slotu 0")
- odhacz H02 w `doc/audyt/audyt.md`
- commit: `H02: dzienny autosave o 6:00 do slotu szybkiego zapisu + toast`
