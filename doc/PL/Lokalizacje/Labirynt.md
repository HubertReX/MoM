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

Labirynt jako lokacja nie ma pliku `.tmx` - każdy poziom powstaje proceduralnie z szablonu `assets/MazeTileset/MazeTileset_Ninja.tmx`. Poziomy mają własne klucze `MAZE_01`, `MAZE_02`, `MAZE_03`, `MAZE_04`; 

To ile ich jest, decyduje liczba wierszy w `project/config_model/maze_configs.csv` - to ten plik wyznacza głębokość lochu, bo generator nie stawia schodów w dół poniżej ostatniego poziomu.

Wejście do labiryntu znajduje się w wiosce [[Gafowo Kolonia]].