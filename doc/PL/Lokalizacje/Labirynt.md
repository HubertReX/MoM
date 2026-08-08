---
aliases:
  - MAZE
alternative:
EN: "[[the Maze]]"
inspirations:
  - 
characters:
---
# Info

==TODO== - nazwa pliku jest **roboczą propozycją**, tak jak przy [[Komnata Jakuba]].

Labirynt jako lokacja nie ma pliku `.tmx` - każdy poziom powstaje proceduralnie
z szablonu `assets/MazeTileset/MazeTileset_Ninja.tmx`. Poziomy mają własne klucze
`MAZE_01`, `MAZE_02`, `MAZE_03`, `MAZE_04` (D16); ile ich jest, decyduje liczba
wierszy w `project/config_model/maze_configs.csv` - to ten plik wyznacza głębokość
lochu, bo generator nie stawia schodów w dół poniżej ostatniego poziomu.

To **osobna lokacja** od [[Jaskinie zagmatwania]] - tamte to jaskinie Aktu 1,
których mapy jeszcze nie ma.

W etapie 3 gracz zobaczy na HUD-zie nazwę stąd zamiast klucza `MAZE_01`. Do
rozstrzygnięcia przy okazji: czy poziomy mają być numerowane na ekranie
(„Labirynt - poziom 2"), czy wszystkie mają wyglądać tak samo.
