# E01 - filtr nocy: jedna ścieżka kodu na desktop i web (bez shaderów)

Priorytet: **P1** (Faza 3). Rozmiar: M. Zależności: A04 (`MOM_TEST_START_HOUR` -
scenariusz nocny), benchmark z B01 (`scripts/bench_scene.py`).
Zadanie **nie** obejmuje mgły wojny w labiryncie - to osobna pozycja
[E03](E03-fog-of-war-labirynt.md) (plan na przyszłość, po tym zadaniu).

## Kontekst i problem

Cykl dobowy istnieje i wygląda dobrze **tylko na desktopie**. W `project/scene/scene.py`
(sekcja `draw`, ok. linii 642) stoi:

```python
if USE_ALPHA_FILTER and not IS_WEB:
    night_filter.apply_time_of_day_filter(self, screen)
```

Na web noc **nie istnieje** - świat jest tak samo jasny o 3:00 jak o 12:00. To
rozjazd dwóch platform w rzeczy, która jest w MoM mechaniką klimatu (a docelowo
i gameplayu: nocne questy, zamknięte sklepy).

Drugi problem to koszt (znalezisko D-7): `night_filter.apply_time_of_day_filter`
robi w KAŻDEJ klatce nocy:

- `pygame.transform.scale_by(scene.b_and_w_circle, scale)` **osobno dla każdego NPC**
  i gracza (plus dwa światła „intro"), bez cache;
- `pygame.transform.scale(scene.filter_surf, (WIDTH, HEIGHT))` na pełny ekran.

Na desktopie jest zapas (cała klatka ~1,7 ms), ale to dokładnie ten wzorzec, który
na WASM kosztuje wielokrotnie więcej - dlatego włączenie go na web bez optymalizacji
byłoby strzałem w stopę.

## Decyzja kierunkowa (audyt, potwierdzona)

Najpierw **tani fallback bez shaderów, jedna ścieżka kodu desktop+web**. Shadery
(`USE_SHADERS`, `shaders/OpenGL3.0_ES`) zostają osobnym eksperymentem o niskim
priorytecie; nawet gdyby kiedyś ruszyły, ta ścieżka pozostaje dla słabszych maszyn.

## Cel

1. Ten sam kod filtra działa na desktopie i na web - warunek `not IS_WEB` znika.
2. Koszt filtra zmierzony liczbami przed/po (desktop: benchmark; web: licznik klatki).
3. Gdy budżet klatki na web okaże się za ciasny - degradacja jakości (grubszy
   `FILTER_SCALE`), **nie** wyłączanie mechaniki na jednej platformie.

## Pliki do zmiany

- `project/scene/night_filter.py` - cache i brak realokacji (rdzeń zadania)
- `project/scene/scene.py` - zdjęcie `not IS_WEB`; `filter_surf` / `b_and_w_circle`
  (linie ~225-231 i ~494 przy zmianie rozdzielczości)
- `project/settings.py` - ewentualny `FILTER_SCALE` zależny od platformy (dopiero po
  pomiarze!)
- `scripts/bench_scene.py` - pomiar `draw` w scenerii nocnej (dziś mierzy dzień)
- `tests/scenarios.json` - scenariusz nocny (`start_hour`) dla desktop i web
- `project/AGENTS.md` - opis filtra po zmianie

## Krok 1: pomiar PRZED (bez tego nie zaczynaj)

1. Desktop: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python3
   scripts/bench_scene.py` - zanotuj `update`/`draw`. Następnie dopisz do skryptu tryb
   nocny (wymuś `scene.hour = 22` przed pętlą pomiarową) i zanotuj `draw` w nocy.
   Różnica dzień/noc = realny koszt filtra.
2. Web: `just serve-web`, otwórz z `#debug`, przejdź na noc (`MOM_TEST_START_HOUR=22`
   przez `MoM.env` albo klawisz przeskoku doby) i zanotuj FPS z licznika debug -
   **z filtrem włączonym na próbę** (jedna linia zakomentowana lokalnie, bez commita).
   To jest liczba, którą optymalizujesz.

Zapisz oba pomiary w sekcji „Pomiary" na końcu tego pliku.

## Krok 2: cache w `night_filter.py`

1. **Cache skalowanego koła świateł.** Zamiast `transform.scale_by` per NPC per klatka:
   słownik `{klucz_skali: Surface}` trzymany na scenie (albo modułowo, kluczowany też
   rozmiarem `b_and_w_circle`). Klucz = skala zaokrąglona do np. 0,05 - zoom zmienia się
   płynnie, ale różnica pół procenta jest niewidoczna, a cache bez zaokrąglenia nigdy
   nie trafia.
2. **Bufor pełnoekranowy.** `pygame.transform.scale(filter_surf, (WIDTH, HEIGHT))`
   alokuje nową powierzchnię co klatkę - użyj wariantu z docelową powierzchnią
   (`pygame.transform.scale(src, size, dest_surface)`), trzymanej na scenie i
   przebudowywanej **tylko** przy zmianie rozdzielczości.
3. **Wczesne wyjście.** Gdy `ratio == 0` (pełny dzień, 9:00-17:00 poza labiryntem)
   filtr ma kosztować zero - dziś i tak wypełnia i skaluje powierzchnię.
4. Nie zmieniaj wyglądu: te same kolory (`DAY_FILTER`/`NIGHT_FILTER`), ta sama
   interpolacja świtu/zmierzchu, ten sam `BLEND_RGBA_MIN`.

## Krok 3: włączenie na web

1. Zdejmij `and not IS_WEB` w `scene.py`.
2. Zmierz na web ponownie (jak w kroku 1). Jeśli spadek FPS jest nie do przyjęcia,
   **degraduj jakość, nie mechanikę**: `FILTER_SCALE = 16` na web (mniejsza powierzchnia
   filtra = 4x mniej pikseli), ewentualnie ogranicz światła do gracza + NPC w kadrze.
   Każdą taką decyzję zapisz w komentarzu przy kodzie z liczbą, która ją uzasadnia.
3. Jeżeli po degradacji nadal nie mieści się w budżecie - **STOP i zapytaj autora**
   (opcje: cieńszy efekt, filtr tylko w labiryncie, powrót do wyłączenia na web).
   Nie zostawiaj cichego rozjazdu platform.

## Krok 4: scenariusz testowy nocy

W `tests/scenarios.json` dodaj scenariusz z `"start_hour": 22`:
wejście do gry → zrzut ekranu na Village nocą → `ui_state` potwierdzający mapę i
godzinę. Ma działać w zestawie desktop i web. `ui_quality_checks` dla ss-review:
„scena jest wyraźnie ciemniejsza niż w dzień, wokół postaci widać rozjaśnienie,
UI (HUD, ramki) pozostaje czytelne".

## Kryteria akceptacji

1. `just test-unit` zielone; `just mypy` = 0.
2. Benchmark desktop: `draw` w nocy **nie gorszy niż przed zmianą** (cel: wyraźnie
   lepszy); `draw` w dzień bez regresji. Liczby przed/po w opisie commita.
3. Web: filtr nocy widoczny w grze, FPS zmierzony i zapisany; `MOM_SKIP_SS_REVIEW=1
   just test-smoke` zielone.
4. Nowy scenariusz nocny przechodzi na desktopie i na web (ze ss-review).
5. Wygląd nocy na desktopie bez regresji - porównanie zrzutów przed/po
   **i finalna weryfikacja autora na realnym ekranie** (memory
   `headless-screenshot-not-faithful`: zmiany pipeline'u renderowania nie są w pełni
   wierne w headless).
6. Brak gałęzi `IS_WEB` w `night_filter.py` i w wywołaniu filtra - to jest sedno zadania.

## Pułapki

- `filter_surf` jest tworzony w dwóch miejscach (`scene.py` ~225 i ~494 przy zmianie
  rozdzielczości) - każdy nowy bufor musi być przebudowany w OBU.
- `ZOOM_LEVEL` i `camera.zoom`: skala kół zależy od zoomu, więc klucz cache musi go
  obejmować; inaczej po zoomie zobaczysz koła w złym rozmiarze.
- Ścieżka shaderowa (`USE_SHADERS = True`) czyta `get_lights` - nie zmieniaj jego
  kontraktu (delegat `Scene.get_lights`, kontrakt K3 z B01).
- Wnętrza (`not outdoor and not is_maze`) mają nadal nie mieć filtra; labirynt ma noc
  zawsze - to zachowanie zostaje.
- Nie ruszaj `apply_cutscene_framing` ani `apply_alpha_filter` (demo) - to sąsiedzi
  w pliku, nie zakres zadania.
- Web-runner to singleton (memory `web-test-singleton-run-hygiene`): przed
  `just test-web`/`test-smoke` sprawdź `pgrep -f automate_display_test` i `lsof -ti :8001`.

## Po zakończeniu

- zaktualizuj sekcję o filtrze dnia/nocy w `project/AGENTS.md` (cache, brak gałęzi web,
  zmierzony koszt)
- odhacz E01 w `doc/audyt/audyt.md`
- commit: `E01: filtr nocy na desktop i web - cache świateł i bufora, jedna ścieżka kodu`

## Pomiary (wypełnia agent)

| Pomiar | Przed | Po |
| --- | --- | --- |
| desktop `draw` dzień (ms) | | |
| desktop `draw` noc (ms) | | |
| web FPS noc | | |
