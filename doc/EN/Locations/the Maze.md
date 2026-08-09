---
aliases:
  - MAZE
alternative:
PL: "[[Labirynt]]"
inspirations:
  - 
characters:
---
# Info

The maze as a location does not have its own `.tmx` file - each level is generated procedurally from the `assets/MazeTileset/MazeTileset_Ninja.tmx` template. The levels have their own keys: `MAZE_01`, `MAZE_02`, `MAZE_03`, `MAZE_04`.

Their total number is determined by the number of rows in `project/config_model/maze_configs.csv` - this file defines the dungeon depth, as the generator does not place downstairs below the final level.

The entrance to the maze is located in the village of [[Blunderhaven]].