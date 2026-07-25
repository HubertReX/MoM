# A04 - tryb deterministyczny testów (seed świata i cząstek, parametr godziny startu)

Priorytet: **P1** (Faza 1). Rozmiar: S. Zależności: brak; wzmacnia A01-A03.

## Kontekst i problem

Scenariusze agentowe działają na "żywej" grze: epizody pogody (liście/deszcz) startują
w losowych momentach z losowymi parametrami, NPC-e wędrują random-walkiem, seed świata
jest losowy przy każdej nowej grze. Skutki: screenshoty nieporównywalne między
uruchomieniami, NPC potrafi wejść w kadr, epizod deszczu zmienia obraz w trakcie
scenariusza.

Decyzje autora (2026-07-25):

- **Cząstek NIE wyłączamy** - testowalibyśmy inną grę niż realna, a scenariusz może
  chcieć sprawdzić właśnie emiter. Zamiast tego losowość cząstek/pogody ma być
  **zaseedowana**.
- **Godziny startu NIE wymuszamy globalnie** - gra normalnie zaczyna o 9 i scenariusze
  mają widzieć rutyny NPC takie jak gracz. Godzina startu to **opcjonalny parametr
  scenariusza**, do testów wymagających konkretnej pory (noc, zamknięty sklep).

Fundament w kodzie: `project/world_rng.py` (seedowana losowość świata:
`day_rng(world_seed, day, name)`), `WeatherDirector` + `EMITTER_SCHEDULES`
(`project/particles.py`, `settings.py`), `INITIAL_HOUR` (settings.py:391).

## Cel

`MOM_TEST_DETERMINISTIC=1`: dwa uruchomienia tego samego scenariusza dają ten sam
przebieg świata - te same epizody pogody w tych samych momentach, ten sam seed świata,
powtarzalne makro-ruchy NPC. Cząstki działają normalnie, tylko przewidywalnie.
Osobno: `MOM_TEST_START_HOUR=<0-23>` wymusza godzinę startu (niezależnie od trybu).

## Pliki do zmiany

- `project/settings.py` - odczyt zmiennych + `TEST_WORLD_SEED`, nadpisanie `INITIAL_HOUR`
- `project/particles.py` - wstrzykiwalny generator losowy w `WeatherDirector`
  i emiterach (zamiast globalnego `random`)
- `project/scene.py` / `project/characters.py` - seedowanie pozostałych źródeł losowości
- `tests/automate_display_test.py` - runner ustawia `MOM_TEST_DETERMINISTIC=1` domyślnie
  (opt-out `MOM_TEST_LIVE_WORLD=1`); pole `start_hour` w scenariuszu → env dla procesu gry
- `project/AGENTS.md` - dokumentacja obu zmiennych

## Krok 1: flagi w settings.py

Obok istniejącego odczytu `MOM_AGENT_CONTROL` dodaj:

```python
TEST_DETERMINISTIC = os.environ.get("MOM_TEST_DETERMINISTIC") == "1"
TEST_WORLD_SEED: int | None = 12345 if TEST_DETERMINISTIC else None

_start_hour = os.environ.get("MOM_TEST_START_HOUR")
if _start_hour is not None:
    INITIAL_HOUR = max(0, min(23, int(_start_hour)))   # niezależne od TEST_DETERMINISTIC
```

`USE_PARTICLES` zostaje bez zmian (cząstki włączone). Uwaga na pułapkę importu
by-value: `scene.py` robi `from settings import INITIAL_HOUR` - nadpisanie musi
nastąpić w treści settings.py (jak wyżej), wtedy import łapie już nową wartość.

## Krok 2: seedowana losowość cząstek i pogody

W `project/particles.py`:

1. `WeatherDirector` dostaje w konstruktorze parametr `rng: random.Random | None = None`;
   wewnętrznie `self.rng = rng or random.Random()`. WSZYSTKIE decyzje losowe reżysera
   (wybór emitera wg wag, długość epizodu `active_min/max`, przerwa `gap_min/max`)
   przechodzą z modułowego `random.*` na `self.rng.*`.
2. Emitery (`ParticleImageBased` i podklasy) analogicznie: parametr `rng`, wszystkie
   `random.uniform/randint/choice` w spawnie cząstek → `self.rng.*`. Reżyser przekazuje
   swój `rng` do emiterów, które tworzy/startuje (jeden wspólny generator wystarczy).
3. `Scene.load_particles` tworzy reżysera z
   `rng=random.Random(settings.TEST_WORLD_SEED) if settings.TEST_WORLD_SEED is not None
   else None`.

Uwaga: spawn napędzają timery pygame (`set_timer`) - momenty klatek nie są idealnie
równe między uruchomieniami, więc identyczność co do piksela NIE jest celem. Celem jest
powtarzalność sekwencji decyzji (ten sam emiter, te same długości epizodów, ta sama
kolejność parametrów cząstek).

## Krok 3: pozostałe źródła losowości

1. Seed świata: tam gdzie nowa gra woła `new_world_seed()` - jeśli
   `settings.TEST_WORLD_SEED` ustawione, użyj go.
2. Random-walk NPC i inne użycia globalnego `random` w `characters.py`/`scene.py`:
   pod flagą `TEST_DETERMINISTIC` zrób raz `random.seed(TEST_WORLD_SEED)` na starcie gry
   (np. w `Game.__init__`). To eliminuje makro-różnice; pełna powtarzalność
   klatka-w-klatkę nie jest wymagana.
3. Labirynty już są deterministyczne per seed (`maze_rng`) - nie ruszaj.

## Krok 4: runner i pole `start_hour`

1. W `tests/automate_display_test.py`, w miejscu budowania env procesu gry (tam gdzie
   `XDG_DATA_HOME`), dodaj `MOM_TEST_DETERMINISTIC=1`, chyba że użytkownik ustawił
   `MOM_TEST_LIVE_WORLD=1`. Zaloguj wybrany tryb jedną linią.
2. Scenariusz w `scenarios.json` może mieć opcjonalne pole `"start_hour": 21` -
   runner przekazuje je jako `MOM_TEST_START_HOUR` w env TEGO scenariusza (pamiętaj:
   runner odpala osobną instancję gry per scenariusz, więc env jest per scenariusz).
   Brak pola = brak zmiennej = gra startuje o normalnej porze (9:00) i rutyny NPC
   wyglądają jak u gracza.

## Kryteria akceptacji

1. Test jednostkowy `tests/test_deterministic_mode.py` (samodzielny skrypt, lista
   `tests = [...]`):
   - dwa `WeatherDirector` z `rng=random.Random(42)` produkują identyczną sekwencję
     decyzji (zbierz np. 20 pierwszych wyborów emitera + długości epizodów, porównaj);
   - z env `MOM_TEST_DETERMINISTIC=1` (świeży subprocess!) `settings.TEST_WORLD_SEED == 12345`;
     bez env - `None`;
   - z env `MOM_TEST_START_HOUR=21` - `settings.INITIAL_HOUR == 21`; bez env - 9.
2. Dwa kolejne uruchomienia `MOM_SKIP_SS_REVIEW=1 just test-agent "Save and Load Basic"`
   dają ten sam przebieg pogody (porównaj logi/screenshoty: deszcz albo jest na obu,
   albo na żadnym, w tych samych krokach scenariusza).
3. `MOM_TEST_LIVE_WORLD=1` przywraca w pełni losowe zachowanie.
4. Zwykłe `just run` (bez env) - bez żadnych zmian zachowania (cząstki losowe, seed
   losowy, start 9:00).
5. `just test-unit` przechodzi w całości.

## Pułapki

- Env trzeba ustawiać PRZED pierwszym importem settings - w testach dowodowych używaj
  świeżego subprocessu, nie przeładowania modułu.
- Nie zamrażaj zegara gry (dt) - scenariusze polegają na upływie czasu (waity).
  Deterministyczna ma być LOSOWOŚĆ, nie czas.
- Nie wyłączaj rutyn NPC - są deterministyczne względem godziny; scenariusze dialogowe
  używają `talk_to_char`, które zamraża NPC.
- `random.seed()` globalne wołaj wyłącznie pod flagą - nigdy w trybie produkcyjnym.
- `WeatherDirector` jest częścią stanu mapy (`store_map`/`restore_map`) - `rng` musi
  przetrwać snapshot (jest zwykłym atrybutem, przetrwa; nie serializuj go do save'ów).
- Memory `headless-scene-stepping-verification`: `scene.py` importuje `INITIAL_HOUR`
  by-value - narzędzia patchują `scene.INITIAL_HOUR`; Twoja zmiana w settings działa
  wcześniej (przy imporcie), więc nie koliduje, ale nie przenoś odczytu w inne miejsce.

## Po zakończeniu

- dopisz obie zmienne do `project/AGENTS.md` (sekcja testów agentowych)
- odhacz A04 w `doc/audyt/audyt.md`
- commit: `A04: MOM_TEST_DETERMINISTIC (seed świata+pogody) i MOM_TEST_START_HOUR`
