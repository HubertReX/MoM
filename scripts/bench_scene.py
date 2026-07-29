#!/usr/bin/env python3
"""B01: benchmark klatki Scene headless (bramka wydajności refactoru rdzenia).

Konstruuje Game + Scene wprost (bez pętli gry i menu - patrz memory
"headless-scene-stepping") i mierzy medianę czasu `Scene.update` oraz
`Scene.draw` na mapie Village. Tryb deterministyczny wymuszony, więc dwa
uruchomienia mierzą ten sam świat.

Użycie (z katalogu repo):

    SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python3 scripts/bench_scene.py
    ... scripts/bench_scene.py --hour 22   # scena nocna (E01: koszt filtra nocy)

``--hour`` wymusza godzinę świata PO zbudowaniu sceny, więc różnica
``draw`` między ``--hour 12`` a ``--hour 22`` to czysty koszt filtra dnia/nocy
(w dzień poza 9:00-17:00 filtr i tak rysuje światła).

Baseline z audytu 2026-07-25 (mac-mini, Village, 32 NPC): update 0,41 ms,
draw 1,31 ms. Bramka B01: regresja którejkolwiek mediany > 20% = STOP kroku.
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Środowisko PRZED importem settings: headless SDL, sandbox na dane gry
# (Game tworzy SaveManager - nie wolno dotykać prawdziwych save'ów),
# deterministyczny świat (powtarzalny pomiar).
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("XDG_DATA_HOME", str(REPO_ROOT / ".test-data"))
os.environ.setdefault("MOM_TEST_DETERMINISTIC", "1")

sys.path.insert(0, str(REPO_ROOT / "project"))

WARMUP_FRAMES = 60
MEASURE_FRAMES = 500
DT = 1.0 / 60.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hour", type=int, default=None,
                        help="wymuś godzinę świata (0-23) przed pomiarem, np. 22 = noc")
    args = parser.parse_args()

    from game import Game
    from scene import Scene

    game = Game("run")
    scene = Scene(game, "Village", "start")
    scene.enter_state()

    if args.hour is not None:
        scene.hour = max(0, min(23, args.hour))
        scene.minute = 0
        scene.minute_f = 0.0

    print(f"[bench] Village, NPCs: {len(scene.NPCs)}, world_seed: {scene.world_seed}, "
          f"hour: {scene.hour}:00")

    for _ in range(WARMUP_FRAMES):
        game.time_elapsed += DT
        scene.update(DT, [])
        scene.draw(game.canvas, DT)

    update_ms: list[float] = []
    draw_ms: list[float] = []
    for _ in range(MEASURE_FRAMES):
        game.time_elapsed += DT
        t0 = time.perf_counter()
        scene.update(DT, [])
        t1 = time.perf_counter()
        scene.draw(game.canvas, DT)
        t2 = time.perf_counter()
        update_ms.append((t1 - t0) * 1000)
        draw_ms.append((t2 - t1) * 1000)

    up, dr = statistics.median(update_ms), statistics.median(draw_ms)
    print(f"[bench] frames: {MEASURE_FRAMES}")
    print(f"[bench] update median: {up:.3f} ms  (p90 {statistics.quantiles(update_ms, n=10)[8]:.3f})")
    print(f"[bench] draw   median: {dr:.3f} ms  (p90 {statistics.quantiles(draw_ms, n=10)[8]:.3f})")
    print(f"[bench] frame  median: {up + dr:.3f} ms")


if __name__ == "__main__":
    main()
