# E02 - stabilność `dt`: `clock.tick` vs `tick_busy_loop`

Domyka krok 1.2 i kryterium akceptacji 1 z [E02](E02-fps-cap-i-profil-web.md)
("sprawdź, czy `clock.tick` vs `clock.tick_busy_loop` robi u nas różnicę w stabilności
`dt`; domyślnie zostań przy `tick`; jeśli zmierzysz istotny jitter, opisz to liczbami
zanim zmienisz").

**Decyzja: zostajemy przy `clock.tick`.** Zmierzony jitter okazał się artefaktem
środowiska pomiarowego, nie własnością gry ani pygame. Potwierdzone pomiarem na
prawdziwej maszynie 2026-08-01 (`dt` = 16,00-18,00 ms, avg ~16,9 ms, fps ~59) - patrz
sekcja [Weryfikacja na prawdziwej maszynie](#weryfikacja-na-prawdziwej-maszynie-2026-08-01).

## Co się stało

Przy realizacji E02 pomiar headless (`SDL_VIDEODRIVER=dummy`) uruchomiony **wewnątrz
sandboxa narzędzia Bash agenta** pokazał drastyczny jitter: `clock.tick(60)` dawał
~9-10 FPS zamiast 60, podczas gdy `clock.tick_busy_loop(60)` trzymał 62,5 FPS z zerowym
odchyleniem. Wyglądało to na mocny argument za zmianą domyślnego limitera.

## Pomiary

Sonda izolowana (sam `pygame.time.Clock`, bez gry i bez okna), 180 klatek po rozgrzewce,
mac-mini M4, w sandboxie narzędzia Bash:

| Metoda | mean | median | p95 | max | stdev | FPS |
| --- | --- | --- | --- | --- | --- | --- |
| `clock.tick(60)` | 110,70 ms | 129,96 ms | 143,27 ms | 144,01 ms | 37,40 ms | ~9,0 |
| `clock.tick_busy_loop(60)` | 16,00 ms | 16,00 ms | 16,00 ms | 16,01 ms | 0,00 ms | ~62,5 |
| `time.sleep(1/60)` (kontrola) | 118,03 ms | - | - | 149,69 ms | - | ~8,5 |

Linia profilera z gry w tym samym środowisku (`MOM_PROFILE=1`, Village):

```text
profile: fps= 10.1 update: avg= 0.01ms p95= 0.02ms draw: avg= 2.35ms p95= 3.27ms flip: avg= 0.01ms p95= 0.02ms dt: min=17.00ms avg=95.00ms max=136.00ms
profile: fps=  9.7 update: avg= 0.01ms p95= 0.02ms draw: avg= 1.70ms p95= 3.29ms flip: avg= 0.01ms p95= 0.02ms dt: min=39.00ms avg=103.60ms max=127.00ms
```

## Wniosek: to sandbox, nie gra

Rozstrzyga wiersz kontrolny. **Samo `time.sleep(1/60)` trwa 118 ms zamiast 16,7 ms** -
to goły Python i syscall, bez pygame, bez SDL, bez kodu MoM. Sandbox koalescuje krótkie
sleepy do ~120 ms. `clock.tick` używa `SDL_Delay` (czyli sleepa) i dlatego obrywa;
`tick_busy_loop` kręci pętlę na CPU, sleepa nie woła i dlatego wygląda "idealnie".

To samo widać w linii profilera: `update` + `draw` + `flip` sumują się do ~2,4 ms, a `dt`
pokazuje ~95 ms. Gra liczy klatkę w 2 ms i czeka 93 ms w sleepie limitera. Gdyby to był
realny problem wydajnościowy, czas siedziałby w sekcjach, nie poza nimi.

Dlatego `tick_busy_loop` **nie** zostało wprowadzone: "naprawiałoby" nieistniejącą
usterkę kosztem stałego mielenia CPU (grzanie, bateria) u każdego gracza.

## Jak to rozpoznać następnym razem

- Objaw: niskie/rozjeżdżone FPS z przebiegu headless odpalonego przez narzędzie Bash.
- Test rozstrzygający: `time.sleep(1/60)` w pętli. Jeśli on też jest ~10x za wolny,
  środowisko jest skażone i żadna liczba taktowania z tego przebiegu nic nie znaczy.
- Sekcje profilera (`update`/`draw`/`flip`) pozostają wiarygodne - mierzą pracę, nie
  czekanie. Skażone jest tylko `dt` i FPS.
- Alternatywa niewrażliwa na problem: `scripts/bench_scene.py` (omija `Game.run` i jego
  zegar w całości).

## Weryfikacja na prawdziwej maszynie (2026-08-01)

Zmierzone poza sandboxem, w zwykłym oknie terminala: `MOM_PROFILE=1 just run`,
mac-mini M4, okno 1920x1024, Village, chodzenie i rozmowy z NPC. 22 okna agregacji,
z czego 18 to ustabilizowana rozgrywka.

| Metryka | Wynik (18 stabilnych okien) |
| --- | --- |
| `fps` | 58,8 - 60,2 |
| `dt` min | **16,00 ms w każdym oknie** |
| `dt` avg | 16,78 - 16,98 ms |
| `dt` max | 17 - 18 ms |
| `update` avg | 0,79 - 2,29 ms |
| `draw` avg | 3,02 - 4,03 ms |
| `flip` avg | 1,25 - 1,45 ms |

**Werdykt: `dt` jest wzorowo stabilne, `clock.tick` zostaje.** Rozrzut 16-18 ms to w
praktyce granica rozdzielczości pomiaru, a nie jitter: `pygame.time.Clock.tick()` zwraca
**pełne milisekundy**, więc przy budżecie 16,67 ms jedyne osiągalne wartości to 16 albo
17 (rzadziej 18). Realny jitter wyglądałby jak `min=8 max=40`, a nie jak kwantyzacja do
1 ms. `tick_busy_loop` nie miałby tu czego poprawić - kupiłby zero stabilności za cenę
stałego mielenia CPU.

Budżet klatki: `update` + `draw` + `flip` to razem ~6,4 ms z 16,7 ms, czyli **~38%
wykorzystania** przy 1920x1024. Zapas jest duży, `draw` dominuje.

### Piki: obciążenia startowe, nie jitter

Cztery okna odstają i wszystkie są wyjaśnione zdarzeniami, nie taktowaniem:

| Okno | Objaw | Przyczyna |
| --- | --- | --- |
| pierwsze | `fps=28,9`, `dt max=526 ms` | start gry, ładowanie zasobów |
| trzecie | `update p95=714 ms`, `dt max=730 ms` | jednorazowe ładowanie (mapa/dialogi) |
| przedostatnie | `update avg=16,98 ms` przy `p95=2,86 ms` | ogon stalla, patrz niżej |
| ostatnie | `dt max=624 ms`, `update p95=0,01 ms` | wyjście z gry (zapis) już z menu |

Odróżnienie pika od jitteru jest proste: przy piku `dt min` **nadal wynosi dokładnie
16,00 ms**, czyli reszta klatek w oknie jest równa. Jitter psułby też `min`.

### Dwa artefakty raportowania, o których warto wiedzieć

1. **`avg` bywa większe od `p95`** (np. `update: avg=17,90ms p95=0,01ms`). To nie błąd
   arytmetyki: jeden ekstremalny odstający pomiar (~1 s) podnosi średnią, nie ruszając
   95. percentyla. Przy stallu `p95` jest bezużyteczne - dopiero `max` per sekcja
   pokazałby, co się stało.
2. **Stall trafia do `dt` w NASTĘPNYM oknie.** `dt` jest mierzone przez `clock.tick` na
   POCZĄTKU klatki, więc zamulenie w ostatniej klatce okna N zobaczysz jako `dt max`
   dopiero w oknie N+1. Stąd para: okno z `update avg=16,98 ms` ma jeszcze czyste
   `dt max=18 ms`, a `dt max=624 ms` pojawia się linijkę później.
