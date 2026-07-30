# E02 - profil web z realnymi liczbami

Wyniki jednorazowej sesji pomiarowej dla [E02](E02-fps-cap-i-profil-web.md), zebrane
profilerem `MOM_PROFILE=1` (patrz `project/AGENTS.md`, sekcja "`FPS_CAP` i profiler
sekcji klatki").

## Środowisko pomiaru

- **Przeglądarka:** Chromium headless shell 149.0.7827.55 (Playwright, `headless=True`,
  bez GPU - ten sam backend, co używa runner testowy `tests/automate_display_test.py`).
- **Maszyna:** mac-mini, Apple M4, 32 GB RAM, macOS 26.5.1 (25F80).
- **Rozdzielczość okna:** 1280x720 (viewport Playwright).
- **Build web:** `pygbag --no_opt`, `project/build/web.zip` = **7,1 MB**.
- **Metoda:** jednorazowy skrypt Playwright (nie wchodzi do repo - throwaway), który dla
  każdego scenariusza wstrzykuje `MoM.env` (`MOM_AGENT_CONTROL=1`,
  `MOM_TEST_DETERMINISTIC=1`, `MOM_PROFILE=1`, opcjonalnie `MOM_TEST_START_HOUR`),
  przeładowuje stronę, uruchamia nową grę (`accept`), wysyła komendy scenariusza przez
  `agent_ctrl`, i zbiera linie `profile: ...` z konsoli przeglądarki (`page.on("console")`).
  Każdy scenariusz to osobny reload = osobna instancja gry (świeży seed deterministyczny).
- Wiersz w tabeli = ostatnie stabilne okno agregacji profilera (1 s) po ustabilizowaniu
  się sceny; pełne logi (12-27 linii na scenariusz) zebrane w trakcie sesji.

## Wyniki

| Scenariusz                                      | FPS       | update (ms)               | draw (ms)                 | flip (ms)            |
| ----------------------------------------------- | --------- | ------------------------- | ------------------------- | -------------------- |
| Village dzień, bez ruchu                        | 62,5      | 0,00                      | 6,51 (p95 6,60)           | 0,43 (p95 0,50)      |
| Village dzień, bieg z NPC w kadrze              | 62,5      | 2,05-2,12 (p95 2,30-2,60) | 3,24-3,73 (p95 3,30-4,70) | 0,44-0,45 (p95 0,50) |
| Village noc (filtr E01, `overlay_half`)         | 62,5-62,9 | 0,00                      | 6,55-6,60 (p95 6,60-6,70) | 0,43-0,46 (p95 0,50) |
| labirynt, walka (`debug_enter_maze` + `attack`) | 62,5-62,9 | 2,13-2,40 (p95 2,80-2,90) | 3,31-3,33 (p95 3,50-3,60) | 0,45-0,46 (p95 0,50) |
| panel questów otwarty                           | 62,5-62,9 | 2,04-2,13 (p95 2,40-2,70) | 3,27-3,74 (p95 3,40-4,80) | 0,44-0,45 (p95 0,50) |

FPS raportowany przez `pygame.time.Clock.get_fps()` kwantuje się do wielokrotności
`1000/16 ≈ 62,5` w tym środowisku (efekt `SDL_Delay`/`clock.tick(60)` w headless
Chromium, nie błąd pomiaru) - liczba mieszcząca się w budżecie 60 FPS, traktuj ją jako
"zbito limit", nie jako dokładną wartość.

## Wnioski

1. **Mieścimy się w budżecie z dużym zapasem.** Suma `update + draw + flip` w
   najgorszym zmierzonym przypadku to ~7,0 ms (Village w dzień, bez ruchu) wobec budżetu
   16,7 ms dla 60 FPS - **nie ma dziś czego optymalizować na web**, nawet bez GPU.
2. **Filtr nocy (E01) nie jest widoczny na tym profilu.** Village w dzień i w nocy mają
   niemal identyczny koszt `draw` (6,51 vs 6,55-6,60 ms), mimo że izolowany pomiar
   złożenia klatki w E01 wskazywał ~1,8 ms dla trybu `overlay_half`. To potwierdza
   zastrzeżenie już zapisane w E01: w headless Chromium bez GPU end-to-end FPS/`draw`
   nie różnicuje trybów kompozycji - różnica ginie w szumie innych kosztów klatki
   (tilemapa, sprite'y, UI). Wiążący dla porównania trybów zostaje pomiar izolowany z E01,
   nie ten profil.
3. **Ruch/walka/panel questów są TAŃSZE w `draw`, droższe w `update`, niż statyczny dzień.**
   `update` rośnie z 0,00 do ~2,0-2,4 ms (logika ruchu/AI/widgetu), a `draw` spada z ~6,5
   do ~3,3-3,7 ms. Możliwe wyjaśnienie: w bezruchu kamera stoi w miejscu i `draw` obejmuje
   więcej statycznych elementów w kadrze niż po przesunięciu się gracza w stronę krawędzi
   mapy/labiryntu - niezweryfikowane, nieistotne dla wniosku budżetowego (suma i tak niżej
   niż w bezruchu).
4. **Anomalia do zbadania osobno (nie blokuje E02):** w każdym scenariuszu, w którym
   wysłano JAKIEKOLWIEK komendy przez `agent_ctrl` (ruch, `attack`, `quest_log`), `update`
   po kilku sekundach skokowo rośnie z 0,00 do ~2,0-2,4 ms i **utrzymuje się** - efekt nie
   zależy od rodzaju komendy ani nie zanika, gdy komenda dawno przestała być
   przytrzymywana (`quest_log` to pojedyncze naciśnięcie, nie trzymanie). W scenariuszach
   bez żadnej komendy (`bez ruchu`, `noc`) `update` zostaje na 0,00 przez całą sesję.
   Wygląda na koszt uruchamiany przez sam fakt aktywności `agent_ctrl`/pierwszego
   `KEYDOWN`, nie na realny koszt gry - ale nie zdążyłem znaleźć źródła w kodzie. Warto
   zweryfikować w osobnym zadaniu, najlepiej porównując z tym samym profilem bez
   `MOM_AGENT_CONTROL` (czego nie da się zrobić przez `agent_ctrl`, więc wymaga innego
   sterowania - np. nagranej sekwencji zdarzeń).
5. **Co optymalizować następne, jeśli będzie taka potrzeba:** nic pilnego. Gdyby budżet
   kiedyś się zacieśnił (więcej NPC, cięższe mapy), pierwszy kandydat to koszt `draw` w
   bezruchu (~6,5 ms) - największa pojedyncza pozycja w każdym scenariuszu.
