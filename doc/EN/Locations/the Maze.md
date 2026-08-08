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

==TODO== - the file name is a **working proposal**, same as for [[Jacob's Chamber]].

The maze as a location has no `.tmx` file - every level is generated procedurally
from the `assets/MazeTileset/MazeTileset_Ninja.tmx` template. Levels carry their own
keys `MAZE_01`, `MAZE_02`, `MAZE_03`, `MAZE_04` (D16); how many there are is decided
by the row count in `project/config_model/maze_configs.csv` - that file sets the depth
of the dungeon, because the generator stops placing stairs down past the last level.

This is a **separate location** from [[Caverns of Confusion]] - those are the Act 1
caves, whose map does not exist yet.

In stage 3 the player will see the name from here on the HUD instead of the
`MAZE_01` key. Worth deciding along the way: should levels be numbered on screen
("the Maze - level 2"), or should they all read the same.
