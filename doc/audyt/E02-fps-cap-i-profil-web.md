# E02 - `FPS_CAP = 60` + profil wydajności web z realnymi liczbami

Priorytet: **P2** (Faza 3). Rozmiar: S. Zależności: najlepiej PO [E01](E01-filtr-nocy-desktop-i-web.md)
(profil ma mierzyć docelowy pipeline, z filtrem nocy włączonym na obu platformach).

## Kontekst i problem

Znalezisko D-6: `project/settings.py:380` ma `FPS_CAP = 0`, a pętla woła
`dt = self.clock.tick(FPS_CAP) / 1000` (`project/game.py:987`). `tick(0)` = brak limitu:

- desktop miele CPU na maksa (wiatraki, bateria) i daje **niestabilne `dt`**, przez co
  ruch, cząstki i rutyny liczą się przy zmiennym kroku;
- na web przeglądarka i tak throttluje pętlę do vsync, więc problem jest tam
  zamaskowany - i dlatego nikt go nie zauważył.

Drugi wątek: **nie mamy ani jednej liczby z realnego weba**. Benchmark
(`scripts/bench_scene.py`) mierzy headless desktop (baseline: update 0,775 ms /
draw 1,284 ms). Wszystkie rozważania o „narzucie WASM 5-20x" to szacunki. Zanim
cokolwiek zoptymalizujemy na web, trzeba zmierzyć.

## Cel

1. `FPS_CAP = 60` jako domyślne zachowanie na obu platformach, z możliwością zmiany.
2. Lekki profiler sekcji klatki (update / draw / flip), włączany flagą, logujący
   liczby także na web (konsola JS przez `#debug`).
3. Jednorazowy **profil web** zapisany jako dokument z liczbami - punkt odniesienia dla
   przyszłych optymalizacji.

## Pliki do zmiany

- `project/settings.py` - `FPS_CAP = 60` + flaga profilera
- `project/game.py` - `clock.tick`, pomiar sekcji klatki, log
- `project/scene/debug_overlay.py` - pokazanie czasów sekcji na overlayu debug (jeśli
  pasuje do istniejącego układu; nie rozbudowuj overlaya ponad jedną linię)
- **nowy** `doc/audyt/E02-profil-web-wyniki.md` - tabela pomiarów
- `project/AGENTS.md` - jak włączyć profiler

## Krok 1: FPS_CAP

1. `FPS_CAP = 60`. Zostaw możliwość podniesienia (komentarz przy stałej: 0 = bez limitu,
   do profilowania).
2. Sprawdź, czy `clock.tick` vs `clock.tick_busy_loop` robi u nas różnicę w stabilności
   `dt` (busy loop = dokładniej, ale grzeje CPU). Domyślnie zostań przy `tick`;
   jeśli zmierzysz istotny jitter `dt`, opisz to liczbami zanim zmienisz.
3. Sprawdź `RECORDING_FPS = 30` i ścieżkę nagrywania - limit klatek nie może zepsuć
   nagrywania rozgrywki.

## Krok 2: profiler sekcji klatki

Flaga `MOM_PROFILE=1` (przez `settings._ENV`, tak samo jak `MOM_TEST_DETERMINISTIC` -
na web czytana z klucza localStorage `MoM.env`, patrz A07):

- pomiar `perf_counter` wokół `update`, `draw` i `flip` w pętli `Game`;
- agregacja co 1 s: średnia i p95 per sekcja + FPS;
- jedna linia logu na sekundę przez `self.log` (na web to `platform.console.log`,
  więc liczby widać w konsoli JS z `#debug`);
- gdy flaga jest wyłączona - **zero kosztu** (żadnych `perf_counter` w gorącej pętli).

## Krok 3: profil web (dokument)

Zbierz w jednej sesji, w `doc/audyt/E02-profil-web-wyniki.md`:

| Scenariusz | FPS | update (ms) | draw (ms) | flip (ms) |
| --- | --- | --- | --- | --- |
| Village dzień, bez ruchu | | | | |
| Village dzień, bieg z NPC w kadrze | | | | |
| Village noc (filtr E01) | | | | |
| labirynt, walka | | | | |
| panel questów otwarty | | | | |

Do tego: przeglądarka i wersja, maszyna, rozdzielczość okna, rozmiar paczki web.
Na końcu 3-5 zdań wniosków: co jest najdroższe i co optymalizować **następne**
(albo: „mieścimy się, nie ma czego optymalizować" - to też jest wynik).

## Kryteria akceptacji

1. `FPS_CAP = 60` w repo; desktop trzyma ~60 FPS, `dt` stabilne (pokaż zakres `dt`
   z profilera przed/po).
2. `MOM_PROFILE=1` działa na desktopie i na web; bez flagi profiler nie liczy nic.
3. `doc/audyt/E02-profil-web-wyniki.md` wypełniony realnymi liczbami z przeglądarki.
4. `just test-unit` zielone, `just mypy` = 0, `MOM_SKIP_SS_REVIEW=1 just test-smoke`
   zielone.
5. Scenariusze agentowe nie regresują - limit klatek nie może zmienić taktowania
   waitów (w razie czego runner steruje krokami, nie zegarem ściennym; jeśli coś
   zacznie migotać, opisz to zamiast podnosić limity „na czuja").

## Pułapki

- `dt` wpływa na fizykę ruchu i cząstki - po zmianie limitu sprawdź, czy postać nie
  chodzi wolniej/szybciej niż przed (`characters/movement.py`).
- Testy agentowe biegną z `SDL_VIDEODRIVER=dummy` i potrafią lecieć szybciej niż
  60 FPS - limit spowolni je; zmierz czas `just test-smoke` przed/po (dziś 96 s) i
  podaj w commicie.
- Nagrywanie rozgrywki i zrzuty ekranu (`RECORDING_FPS`, `MOM_AGENT_SS_CANVAS`) mają
  działać po zmianie tak samo.
- Na web `clock.tick` nie jest jedynym limiterem - pętla jest asynchroniczna
  (pygbag-safe `await asyncio.sleep(0)`); nie próbuj tego „naprawiać".
- Profiler ma być tani: żadnego `statistics` na każdej klatce, tylko sumy i liczniki.

## Po zakończeniu

- dopisz do `project/AGENTS.md`: `MOM_PROFILE=1` i gdzie szukać liczb
- odhacz E02 w `doc/audyt/audyt.md`
- commit: `E02: FPS_CAP=60 + profiler sekcji klatki (MOM_PROFILE) i profil web z liczbami`
