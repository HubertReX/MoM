#!/usr/bin/env python3
"""B01: referencyjny save sprzed refactoru + kontrola wczytania (kontrakt K1).

Dwa podpolecenia:

    create   zbuduj grę headless, wejdź pierwszym wyjściem labiryntowym z Village
             (autosave slotu 0 - ta sama ścieżka co w grze) i odłóż plik do
             `.test-data/b01-fixture/save_0.mom`. Uruchamiane RAZ, na kodzie
             SPRZED refactoru (B01 krok 0).
    check    podłóż fixture do sandboxa save'ów, wczytaj przez SaveManager.load(0)
             i przekrokuj 60 klatek update/draw. Uruchamiane po KAŻDYM kroku B01,
             który dotyka atrybutów sceny/NPC (bramka nr 6 planu).

Użycie (z katalogu repo):

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python3 scripts/b01_fixture.py create
    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python3 scripts/b01_fixture.py check

Fixture zawiera scenę labiryntu (odtwarzaną z samego seeda!) + stan Village
w pending_map_states - to najbogatszy pojedynczy save, jaki gra umie zrobić,
więc łamie się najgłośniej, gdy refactor ruszy kontrakt save/load.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / ".test-data" / "b01-fixture"
FIXTURE_FILE = FIXTURE_DIR / "save_0.mom"

# Środowisko PRZED importem settings - jak w bench_scene.py.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("XDG_DATA_HOME", str(REPO_ROOT / ".test-data"))
os.environ.setdefault("MOM_TEST_DETERMINISTIC", "1")

sys.path.insert(0, str(REPO_ROOT / "project"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DT = 1.0 / 60.0


def _boot_scene():
    from game import Game
    from scene import Scene

    game = Game("run")
    scene = Scene(game, "Village", "start")
    scene.enter_state()
    # kilka klatek, żeby świat się ustabilizował (grupy, kamera, rutyny)
    for _ in range(30):
        game.time_elapsed += DT
        scene.update(DT, [])
        scene.draw(game.canvas, DT)
    return game, scene


def create() -> None:
    from save_fixtures import get_save_path

    game, scene = _boot_scene()
    from scene import map_registry
    maze_exit = next(e for e in scene.exits
                     if map_registry.is_maze_map(game.conf, e.to_map))
    scene.new_scene = maze_exit
    scene.go_to_map()  # wejście do labiryntu = autosave slotu 0 (ścieżka z gry)

    save_path = get_save_path(0)
    if not save_path.exists():
        sys.exit(f"[fixture] BŁĄD: autosave nie powstał ({save_path})")
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(save_path, FIXTURE_FILE)
    print(f"[fixture] zapisano {FIXTURE_FILE} ({FIXTURE_FILE.stat().st_size} B), "
          f"mapa: {scene.current_map}, maze_seed: {scene.maze_seed}")


def check() -> None:
    from save_fixtures import get_save_path

    if not FIXTURE_FILE.exists():
        sys.exit(f"[fixture] BŁĄD: brak {FIXTURE_FILE} - najpierw `create` (na kodzie sprzed refactoru)")

    save_path = get_save_path(0)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURE_FILE, save_path)

    game, _ = _boot_scene()
    if not game.save_manager.load(0):
        sys.exit("[fixture] BŁĄD: SaveManager.load(0) zwrócił False")

    from scene import Scene
    top = game.states[-1]
    ok = (isinstance(top, Scene)
          and top.is_maze
          and top.current_map.startswith("Maze")
          and "Village" in (set(top.loaded_maps) | set(top.pending_map_states))
          and top.player.model.health > 0)
    if not ok:
        sys.exit(f"[fixture] BŁĄD: stan po load niezgodny (top={type(top).__name__}, "
                 f"map={getattr(top, 'current_map', None)}, is_maze={getattr(top, 'is_maze', None)})")

    for _ in range(60):
        game.time_elapsed += DT
        top.update(DT, [])
        top.draw(game.canvas, DT)
    print(f"[fixture] OK: {top.current_map} (maze_seed {top.maze_seed}), "
          f"NPCs: {len(top.NPCs)}, HP: {top.player.model.health}, 60 klatek bez błędu")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("create", "check"):
        sys.exit(__doc__)
    create() if sys.argv[1] == "create" else check()
