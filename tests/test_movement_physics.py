#!/usr/bin/env python3
"""Tests for the movement integrator: a character that stops must stay stopped.

`physics()` used to fold friction back into `self.acc`, a member that survives the
frame:

    acc += vel * friction
    vel += acc * dt

While some controller overwrote `acc` every frame that was harmless, which is why
walking always looked fine. The moment nobody wrote it any more - the character
arrived, `clear_waypoints` zeroed `acc`, and `follow_waypoints` started returning
early on `waypoints_cnt <= 0` - those two lines closed into a loop that is a
harmonic oscillator with |eigenvalue| exactly 1.0. Undamped: it never decays.
Period 13.9 frames, amplitude ~2.4 px. On screen: a character shivering between
two positions on the spot, forever, at every destination.

The player never showed it because its input code assigns `self.acc.x = 0` on
frames with no key held, which happens to break the loop.

Run from the project root:
    .venv/bin/python tests/test_movement_physics.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
from pygame.math import Vector2 as vec

DT = 1 / 60


class _FakeScene:
    # one big open field; `physics` only reads it to look up the step cost
    path_finding_grid = [[-100] * 8 for _ in range(8)]


def _character(vel: tuple[float, float] = (30.0, 0.0), speed: int = 30):
    """A bare NPC carrying only what `physics()` touches."""
    from characters import NPC

    npc = NPC.__new__(NPC)
    npc.scene = _FakeScene()
    npc.is_stunned = False
    npc.is_attacking = False
    npc.is_flying = False
    npc.is_jumping = False
    npc.jumping_offset = 0
    npc.pos = vec(64.0, 64.0)
    npc.prev_pos = npc.pos.copy()
    npc.acc = vec(0, 0)
    npc.vel = vec(*vel)
    npc.friction = -12
    npc.speed = speed
    # int components: the real one indexes `path_finding_grid` directly
    npc.tileset_coord = type("Coord", (), {"x": 4, "y": 4})()
    npc.adjust_rect = lambda: None
    return npc


def _run(npc, frames: int, steering: vec | None = None) -> list[float]:
    xs = []
    for _ in range(frames):
        if steering is not None:
            npc.acc.update(steering)      # a controller still pushing, as movement() would
        npc.physics(DT)
        xs.append(npc.pos.x)
    return xs


def test_a_character_left_alone_comes_to_rest() -> None:
    """The regression itself: no steering, so it must coast to a stop and stay."""
    npc = _character()

    _run(npc, 60)                          # one second to settle
    late = _run(npc, 60)                   # the second after that must be still

    spread = max(late) - min(late)
    assert spread < 0.01, f"character never settles - shivers over {spread:.3f} px"


def test_the_oscillation_is_gone_not_merely_slower() -> None:
    """Undamped means "forever", so a long run is the honest check."""
    npc = _character()

    _run(npc, 60)
    late = _run(npc, 600)                  # ten more seconds

    spread = max(late) - min(late)
    assert spread < 0.01, f"still moving after 10 s - spread {spread:.3f} px"


def test_velocity_decays_towards_zero() -> None:
    npc = _character()

    _run(npc, 120)

    assert npc.vel.length() < 0.01, f"velocity survived: {npc.vel.length():.4f}"


def test_the_stop_is_close_to_where_it_arrived() -> None:
    """Coasting is fine; sliding half a tile past the destination is not."""
    npc = _character()
    start_x = npc.pos.x

    _run(npc, 120)

    drift = npc.pos.x - start_x
    assert 0 < drift < 8, f"coasted {drift:.2f} px past the target (a tile is 16)"


def test_steering_still_moves_the_character() -> None:
    """The fix must not cost the ability to walk."""
    npc = _character(vel=(0.0, 0.0))
    start_x = npc.pos.x

    _run(npc, 60, steering=vec(2000, 0))

    assert npc.pos.x - start_x > 20, f"barely moved in a second: {npc.pos.x - start_x:.2f} px"
    assert npc.vel.x > 25, f"never reached walking speed: {npc.vel.x:.2f}"


def test_steering_reaches_the_speed_cap_and_holds_it() -> None:
    """Terminal velocity must still be the character's `speed`, not something new."""
    npc = _character(vel=(0.0, 0.0), speed=30)

    _run(npc, 120, steering=vec(2000, 0))

    assert abs(npc.vel.x - 30) < 0.5, f"speed cap drifted: {npc.vel.x:.3f}"


def test_releasing_the_controls_stops_the_character() -> None:
    """Walk, then let go: it must glide to a halt, not oscillate around it."""
    npc = _character(vel=(0.0, 0.0))

    _run(npc, 60, steering=vec(2000, 0))   # walking
    _run(npc, 60)                          # let go
    late = _run(npc, 120)

    spread = max(late) - min(late)
    assert spread < 0.01, f"shivers after release - spread {spread:.3f} px"


def test_acc_is_consumed_each_frame() -> None:
    """The mechanism, pinned directly: a force applies once, not until overwritten."""
    npc = _character(vel=(0.0, 0.0))
    npc.acc.update(vec(2000, 0))

    npc.physics(DT)

    assert npc.acc == vec(0, 0), f"steering force survived the frame: {npc.acc}"


if __name__ == "__main__":
    pygame.init()
    tests = [
        ("character left alone comes to rest", test_a_character_left_alone_comes_to_rest),
        ("oscillation gone, not merely slower", test_the_oscillation_is_gone_not_merely_slower),
        ("velocity decays to zero", test_velocity_decays_towards_zero),
        ("stops close to where it arrived", test_the_stop_is_close_to_where_it_arrived),
        ("steering still moves the character", test_steering_still_moves_the_character),
        ("steering holds the speed cap", test_steering_reaches_the_speed_cap_and_holds_it),
        ("releasing the controls stops it", test_releasing_the_controls_stops_the_character),
        ("acc is consumed each frame", test_acc_is_consumed_each_frame),
    ]
    failures = 0
    for name, func in tests:
        try:
            func()
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            import traceback

            traceback.print_exc()
            failures += 1

    print(f"\n{'─' * 40}")
    total = len(tests)
    passed = total - failures
    if failures:
        print(f"  FAILED  {failures}/{total} tests")
        sys.exit(1)
    else:
        print(f"  PASSED  {passed}/{total} tests")
