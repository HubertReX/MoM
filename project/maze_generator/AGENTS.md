# AGENTS.md — proceduralne labirynty (`project/maze_generator/`)

Generuje proceduralne labirynty (dungeony) renderowane jak zwykłe mapy Tiled.
Kontekst nadrzędny: [`../AGENTS.md`](../AGENTS.md).

## Algorytm i struktura

- **Hunt-and-Kill** — `hunt_and_kill_maze.py`: losowo drąży korytarze, potem „poluje" na
  nieodwiedzone komórki sąsiadujące z odwiedzonymi.
- **Siatka komórek** — `maze.py` (klasa `Maze`), `cell.py` (klasa `Cell` z sąsiadami N/S/E/W
  i `image_index`).
- **`mappings.py`** — mapuje `image_index` (bitmaska 0–15 kodująca otwarcia korytarza) na
  wzór kafelków 3×3 (które pola to ściana, a które przejście).

## Render i integracja

- **`maze_drawer_pyscroll.py`** + **`maze_utils.py` (34K)** — budują obiekt TiledMap z
  wygenerowanego labiryntu: przeliczają GID-y kafelków, rozmieszczają decory (beczki,
  banery, dziury), ustawiają subtile.
- Labirynt jest renderowany przez **pyscroll** identycznie jak ręcznie zrobiona mapa `.tmx`,
  więc `Scene` obsługuje go tym samym kodem co zwykłe mapy (z flagą maze).
- **Pathfinding:** `maze_utils.py` zawiera `a_star_cached` (importowane przez
  `characters.py:11`) działające na gridzie z kosztami przejścia (`STEP_COST_WALL` itd.);
  wyniki są cache'owane dla wydajności.
- `analyze_maze.py` — narzędzie do analizy trudności (ślepe uliczki, najdłuższe ścieżki).

## Powiązanie z configiem

Parametry poziomów labiryntu (potwory, boss, liczba/szablony skrzyń, wymiary `maze_cols`/`rows`)
pochodzą z `maze_configs` w `config.json` — patrz
[`../config_model/AGENTS.md`](../config_model/AGENTS.md).

## Assety labiryntu

Kafelki z paczki `MazeTileset/` — patrz [`../assets/AGENTS.md`](../assets/AGENTS.md).
Szablon czystego labiryntu: `assets/MazeTileset/MazeTileset_clean.tmx`.
