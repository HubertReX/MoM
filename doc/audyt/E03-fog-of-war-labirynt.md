# E03 - prawdziwa mgła wojny w labiryncie (plan na przyszłość)

Priorytet: **P3** (Faza 4). Rozmiar: L. Zależności: **twarda** - najpierw
[E01](E01-filtr-nocy-desktop-i-web.md) (jedna ścieżka filtra na desktop+web z cache).
Zadanie zaczyna się od dokumentu decyzyjnego, nie od kodu.

## Kontekst

Dziś w labiryncie nie ma mgły wojny, tylko **wieczna noc**: `scene.is_maze` wymusza
`NIGHT_FILTER` i wycięcia świateł wokół postaci
(`project/scene/night_filter.py:apply_time_of_day_filter`). Efekt jest ładny, ale ma
zero pamięci - korytarz, przez który gracz właśnie przeszedł, ciemnieje dokładnie tak
samo jak ten, którego nigdy nie widział. Gracz nie buduje mapy w głowie, a labirynt
(znalezisko G-5: „powtarzalność bez haczyka") traci najtańsze źródło satysfakcji:
poczucie odkrywania.

Autor rozdzielił to od E01 świadomie (2026-07-28): **noc wszędzie - od razu; mgła
wojny - jako zaplanowana mechanika na później.**

## Cel (docelowy, po akceptacji dokumentu)

Trzy stany widoczności kafla labiryntu, a nie dwa:

1. **nieodkryty** - czarny, bez tilesetu (gracz nie wie, czy tam jest korytarz),
2. **odkryty, poza zasięgiem wzroku** - widoczny, ale przygaszony,
3. **w zasięgu wzroku** - pełna jasność (dzisiejsze wycięcie światła).

Stan odkrycia jest **per poziom labiryntu**, przeżywa wyjście na inny poziom i powrót,
i przeżywa zapis gry.

## Etap 0: dokument decyzyjny (bramka akceptacji)

Zanim powstanie kod: `doc/_attachements/fog-of-war-<data>.html` + skrót md, z tabelami
opcji per decyzja (wzór: dokument architektury B01). Musi rozstrzygnąć:

1. **Reprezentacja odkrycia.** Bitmapa `set[(x, y)]` odwiedzonych komórek vs bitset
   spakowany do stringa. Labirynt jest siatką komórek (`maze_generator/cell.py`,
   `maze.py`) - decyzja wpływa na rozmiar zapisu i koszt aktualizacji per klatka.
2. **Zasięg odkrywania.** Promień w kaflach czy widoczność wzdłuż korytarza (raycast)?
   Raycast jest ładniejszy i droższy - MoM ma być tani na web, więc rekomendacja
   powinna zaczynać się od promienia.
3. **Renderowanie trzech stanów.** Jedna powierzchnia nakładki komponowana z filtrem
   nocy (jedno `blit` więcej) czy druga warstwa? **Warunek twardy: nie wolno dołożyć
   drugiego pełnoekranowego `transform.scale` per klatka** - to dokładnie ten koszt,
   który E01 właśnie usuwa.
4. **Zapis.** `MapState` trzyma dziś tylko `maze_seed`, `maze_level`, `maze_return_map`,
   `maze_return_entry_point` (`save_load/models.py:486-518`) - poziom jest
   **regenerowany z seeda**, nie zapisywany kafel po kaflu. Mgła to pierwsze dane
   labiryntu, które trzeba zapamiętać naprawdę. Rozstrzygnij format i policz rozmiar
   (np. 60×60 komórek = 3600 bitów = 450 B na poziom; przy 4 poziomach to nic, ale
   napisz to wprost). To **zmiana formatu zapisu** - obowiązuje polityka z
   [B02](B02-polityka-wersji-save.md): podbicie wersji gry, wpis w `save_compatibility`,
   migracja kluczowana wersją zmiany formatu (stary zapis = mgła pusta, nie odmowa).
5. **Interakcja z gameplayem.** Czy mgła ma być tylko wizualna, czy dostaje
   konsekwencje (minimapa? modyfikator poziomu „gęstsza mgła" z `maze_configs.csv`,
   o którym mówi G-5)? Rekomendacja: prolog = tylko wizualna.
6. **Koszt na web.** Budżet z pomiarów E02 (`doc/audyt/E02-profil-web-wyniki.md`) -
   ile ms zostaje na mgłę.

Etap 0 kończy się **przedstawieniem dokumentu autorowi**. Bez „akceptuję" nie ruszaj kodu.

## Etap 1: implementacja (szkic - doprecyzuje dokument)

- stan odkrycia w obiekcie labiryntu (`maze_generator/maze.py`), aktualizowany przy
  ruchu gracza, nie co klatkę;
- nakładka rysowana w `scene/night_filter.py` (albo w module obok - decyzja z dokumentu),
  w tej samej powierzchni co filtr nocy;
- serializacja w `save_load/models.py` + migracja;
- scenariusz agentowy: wejście do labiryntu, przejście korytarzem, zrzut z widocznym
  podziałem na odkryte/nieodkryte;
- test jednostkowy logiki odkrywania (czysta funkcja: pozycja + promień → zbiór komórek).

## Kryteria akceptacji (etapu 1)

1. Trzy stany widoczne w grze; odkryte korytarze zostają widoczne po odejściu.
2. Stan mgły przeżywa zapis/wczytanie i przejście między poziomami; stary zapis
   wczytuje się bez błędu (mgła pusta).
3. Koszt klatki na web w labiryncie mieści się w budżecie z E02 - liczby w commicie.
4. `just test-unit`, `just mypy` = 0, `just validate-world`, `test-smoke` zielone.
5. Weryfikacja wizualna autora na realnym ekranie.

## Pułapki

- Labirynt renderuje się jak zwykła mapa Tiled (`maze_drawer_pyscroll.py`) - nie buduj
  drugiego pipeline'u renderowania „bo mgła".
- `clear_maze_cache()` leci przy każdym ładowaniu mapy i zniszczeniu ściany - stan mgły
  NIE może w nim wyparować.
- Zniszczalne ściany zmieniają topologię poziomu w trakcie - odkrycie musi być
  przypisane do komórki, nie do wyliczonej ścieżki.
- Nie zaczynaj przed E01: bez cache filtra dołożenie mgły to podwojenie najdroższej
  operacji klatki.

## Po zakończeniu

- opis mechaniki w `project/maze_generator/AGENTS.md` i `project/AGENTS.md`
- odhacz E03 w `doc/audyt/audyt.md`
- commit: `E03: mgła wojny w labiryncie - trzy stany widoczności + stan w zapisie`
