# E02 - stabilność `dt`: `clock.tick` vs `tick_busy_loop`

Domyka krok 1.2 i kryterium akceptacji 1 z [E02](E02-fps-cap-i-profil-web.md)
("sprawdź, czy `clock.tick` vs `clock.tick_busy_loop` robi u nas różnicę w stabilności
`dt`; domyślnie zostań przy `tick`; jeśli zmierzysz istotny jitter, opisz to liczbami
zanim zmienisz").

**Decyzja: zostajemy przy `clock.tick`.** Zmierzony jitter okazał się artefaktem
środowiska pomiarowego, nie własnością gry ani pygame.

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

## Weryfikacja na prawdziwej maszynie

Do uzupełnienia poza sandboxem, w zwykłym oknie terminala (nie przez agenta):

```bash
MOM_PROFILE=1 just run
```

Chodzenie po Village przez kilkanaście sekund, potem wklejenie kilku linii `profile:`.

- Oczekiwane przy `FPS_CAP = 60`: `dt` w okolicy `min≈16 avg≈16,7 max≈17-18 ms`,
  `fps≈60`.
- Gdyby `dt` realnie się rozjeżdżało (np. `min=8 max=40`) przy sekcjach mieszczących
  się w budżecie - dopiero wtedy wraca temat `tick_busy_loop` albo limitera hybrydowego
  (sleep do ~1 ms przed deadlinem, potem krótki busy-wait).

| Data | Maszyna | fps | dt min | dt avg | dt max | Uwagi |
| --- | --- | --- | --- | --- | --- | --- |
| _do uzupełnienia_ | | | | | | |
