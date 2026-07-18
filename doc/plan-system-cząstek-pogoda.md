# System cząstek: epizodyczna pogoda z grupami wykluczającymi

Status: **wdrożone** (commit `87d8a88`, gałąź `docs/design-system-ui`, 2026-07-18).

## Kontekst

System cząstek istniał w kodzie, ale był martwy: `USE_PARTICLES = False` blokowało
rejestrację handlerów `add`, a gdyby go włączyć - emitery spawnowały **cały czas**,
a liście i deszcz leciały **równocześnie**. Cel: przeprojektować sterowanie tak, aby
emitery pojawiały się **sporadycznie (epizodami)**, żeby liście i deszcz **nigdy nie
grały naraz**, a przyszłe emitery mogły działać **równolegle** - z parametrami trzymanymi
wygodnie w jednym miejscu.

Decyzje projektowe (ustalone z autorem):

- Konfiguracja jako **dataclass w `settings.py`** (obok rejestru `PARTICLES`).
- **Globalne** definicje emiterów + istniejąca **allow-lista per mapa** z `.tmx`
  (property `particles="..."`).
- **Nazwane grupy** wykluczające (jeden aktywny epizod na grupę; różne grupy = równolegle).

## Model

- Każdy emiter ma harmonogram: `group` (grupa wykluczająca), `weight` (szansa w grupie),
  `active_min/max` (długość epizodu w s), `gap_min/max` (przerwa między epizodami w s).
- Grupa = jeden aktywny emiter naraz. `leafs` i `rain` w grupie `"sky"` → nigdy razem.
  Przyszły równoległy emiter (np. `fog`, `fireflies`) w innej grupie → własny, niezależny cykl.
- **`WeatherDirector`** trzyma stan per grupa (idle/active + odliczanie). Na koniec idle:
  losuje emiter po wadze i włącza na `random(active_min, active_max)`. Na koniec active:
  wyłącza emiter, wchodzi w idle na `random(gap_min, gap_max)`.
- Prymityw włącz/wyłącz: `pygame.time.set_timer(Event(id), interval)` startuje spawn,
  `set_timer(Event(id), 0)` zatrzymuje. Wyłączony emiter przestaje dodawać cząstki;
  istniejące dograją i znikną przez `emit()`.

## Co zostało zrobione

### `project/settings.py`

- Dodano `@dataclass(frozen=True) EmitterSchedule(group, weight, active_min/max, gap_min/max)`
  oraz rejestr `EMITTER_SCHEDULES` (leafs, rain - oba w grupie `"sky"`) obok `PARTICLES`.
- `USE_PARTICLES` przełączone na `True` (globalny wyłącznik).

### `project/particles.py`

- Timer wyjęty z `ParticleImageBased.__init__` → jawne `start()` / `stop()`
  (`set_timer(..., 0)` gasi). `ParticleSystem` (ABC) dostał abstrakcyjne `start()`/`stop()`,
  zaimplementowane w `ParticleLeafs`, `ParticleRain`, `ParticleDestructible`
  (destructible = no-op, bo jednorazowy).
- Nowa klasa **`WeatherDirector`** - epizody per grupa, wybór ważony, wzajemne wykluczanie
  w grupie, `stop_all()`.
- Sprzątanie: usunięta martwa `pygame.mouse.get_pos()` z `ParticleLeafs.add()` /
  `ParticleRain.add()` (spawn_rect ma priorytet); zdjęte `@cache`/`@staticmethod`
  z `x_oscillation` (zwykła metoda); usunięte martwe importy `cache`, `Any`.

### `project/scene.py`

- `load_particles()` buduje mapę `{nazwa: system}` i tworzy `self.weather = WeatherDirector(...)`
  z emiterów dozwolonych na mapie i mających wpis w `EMITTER_SCHEDULES`.
- Tick `self.weather.update(dt)` w `Scene.update()` (ścieżka nie-zamrożona, obok
  `self.group.update`), pod flagą `USE_PARTICLES`.
- `"weather"` dodane do stanu mapy (`store_map`/`restore_map`), a `go_to_map()` /
  `reload_map()` wołają `weather.stop_all()` przed przebudową, żeby nie przeciekały timery.

### `project/AGENTS.md`

- Nowa sekcja "System cząstek i pogoda" (architektura, grupy, `EMITTER_SCHEDULES`,
  allow-lista per mapa, wyjątek `ParticleDestructible`, pułapka z memoizacją `time_elapsed`).

## Uwagi

- `ParticleDestructible` (rozpad krzaków/kamieni) działa **poza** reżyserem i flagą pogody:
  `scene.py` woła `add()` bezpośrednio przy zniszczeniu; `start()/stop()` to no-opy.
- Tylko `Village.tmx` ma dziś `particles="leafs,rain"`; reszta `n/a`. Nowy emiter =
  wpis w `PARTICLES` (klasa) + wpis w `EMITTER_SCHEDULES` (harmonogram) + nazwa w property
  `particles` danej `.tmx`.
- Strojenie: obecnie epizody 8-25 s, przerwy 30-120 s (`EMITTER_SCHEDULES`).

## Weryfikacja

Dwutorowa, obie przeszły:

- **Test jednostkowy (headless)** reżysera z atrapami emiterów: liście+deszcz jednocześnie
  = **0 klatek**; epizodyczność ~42% czasu z przerwami; równoległość między grupami
  (fog obok pogody nieba); `stop_all()` gasi wszystko.
- **Zrzut w grze (headless, `SDL_VIDEODRIVER=dummy`, sterowanie agentem)** na mapie Village
  z `USE_PARTICLES=True`: realnie widoczne **opadające liście** przez cały epizod
  (t08→t20), **bez jednoczesnego deszczu**.
