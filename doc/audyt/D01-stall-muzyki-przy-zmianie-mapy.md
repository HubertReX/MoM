# D01 - zamrożenie ~0,7 s przy każdej zmianie mapy (naprawione)

Znalezisko zgłoszone przez gracza: przy każdym przejściu między mapami (wejście do
Tawerny, zejście do labiryntu) obraz zatrzymywał się na ułamek sekundy. Objaw pojawił
się po dodaniu dźwięków ([D01](D01-audio-manager.md)) i ta intuicja okazała się trafna.

**Status: naprawione.** Koszt przejścia mapy spadł z **805 ms do 76 ms**, a sam krok
audio z **694 ms do 2,8 ms**.

## Przyczyna

`AudioManager._start_current()` (`project/audio.py`) robił:

```python
pygame.mixer.music.fadeout(self._fade_ms)   # fade_ms = 500 (audio.toml)
pygame.mixer.music.load(str(path))
pygame.mixer.music.set_volume(...)
pygame.mixer.music.play(-1)
```

Pułapka nie leży tam, gdzie by się wydawało:

- `music.fadeout()` **nie blokuje** (wbrew starszej dokumentacji pygame) - mierzone 0,0 ms
  w pygame-ce 2.5.1 / SDL_mixer 2.8.0;
- `music.load()` **też nie blokuje**, gdy muzyka gra normalnie - 0,8 ms;
- ale `music.load()` wywołane **w trakcie trwającego fade'u czeka, aż fade się skończy**
  - zmierzone **723 ms** przy `fade_ms = 500`.

Cała ta ścieżka biegnie synchronicznie wewnątrz `map_state.go_to_map()`, czyli w środku
klatki gry. Efekt: pętla stała ~0,7 s, ekran zamarzał.

| Sekwencja | `load` | Razem |
| --- | --- | --- |
| `fadeout(500)` → `load` → `play(-1)` (przed) | 723,1 ms | ~725 ms |
| `load` → `play(-1, fade_ms=500)` (po) | 0,8 ms | **1,5 ms** |

## Naprawa

Usunięty blokujący `fadeout` przed `load`; płynne wejście utworu realizuje teraz
nieblokujący parametr `fade_ms` w `play()`.

**Kompromis:** stary utwór jest ucinany, a nie wyciszany - `pygame.mixer.music` ma jeden
strumień i prawdziwego crossfade'u i tak nie umiał (poprzedni kod robił fade-out, a
potem twardy start, tyle że kosztem zamrożenia gry). Gdyby kiedyś zależało nam na
wyciszeniu starego utworu, trzeba by odroczyć podmianę o kilka klatek, sterując nią z
pętli gry - `AudioManager` nie ma dziś haka per-klatkę, więc to osobne zadanie, nie
poprawka jednej linii.

## Dlaczego testy tego nie łapały

1. **Stub miksera w `tests/test_audio.py` nie przyjmował `fade_ms`.** Po zmianie na
   `play(-1, fade_ms=...)` stub rzucał `TypeError`, `AudioManager` łapał to jako "padł
   mikser" i po cichu wyłączał muzykę - test przechodził dalej, mylnie. Stub musi
   odzwierciedlać sygnaturę prawdziwego API, inaczej testuje coś innego niż produkcja.
2. **Test asercjonował błędne zachowanie:** `assert mixer.music.fadeouts >= 1`
   ("a map change must fade the old track out") utrwalał dokładnie tę linię, która
   powodowała zamrożenie. Zastąpiony przez `fadeouts == 0` + sprawdzenie, że każdy utwór
   dostaje fade-in.
3. **Sterownik `dummy` nie odtwarza tej patologii** - fade kończy się natychmiast, więc
   `load` nie ma na co czekać. Cały headless CI był ślepy na ten błąd z definicji;
   znaleziony dopiero pomiarem na sterowniku `coreaudio`.

## Jak to zostało znalezione

Profiler klatki (`MOM_PROFILE=1`, [E02](E02-fps-cap-i-profil-web.md)) pokazywał stall
tylko pośrednio - jako `update: avg=26.79ms p95=0.91ms` (jeden odstający pomiar podnosił
średnią, nie ruszając percentyla) i `dt max=659ms` **okno później**. Dwie zmiany zrobiły
z tego diagnozę zamiast zagadki:

- `max` per sekcja w linii `profile:` - stall przestał być niewidoczny między `avg` a `p95`;
- osobna linia `profile: map_change -> <mapa> (first_load|cached) total=... <podkroki>`
  w `go_to_map`, która wskazuje winny podkrok wprost.

Ta druga od razu pokazała `audio=694.5ms` przy `load_map=93.6ms` - czyli że problemem nie
jest wcale ładowanie mapy.

```text
przed:  map_change -> Maze_01 (first_load) total= 805.1ms  load_map=93.6ms audio=694.5ms
po:     map_change -> Maze_01 (first_load) total=  76.3ms  load_map=69.9ms audio=  2.8ms
```

## Co zostaje jako możliwe następne kroki

- `load_map` = ~70 ms przy pierwszym wejściu na mapę. To już nie jest zamrożenie
  rzucające się w oczy, ale przy 60 FPS to nadal ~4 zgubione klatki. Preload sąsiednich
  map albo rozbicie ładowania na kilka klatek to osobny, znacznie większy temat.
- Wyciszanie starego utworu (patrz "Kompromis" wyżej).
