#!/usr/bin/env python3
"""Unit tests for the deterministic test mode (A04).

Run from the project root:
    .venv/bin/python tests/test_deterministic_mode.py

Two properties are pinned here. First, that a seeded WeatherDirector replays the same
schedule - same emitter, same episode lengths, same gaps - because that is what makes
screenshots comparable between runs. Second, that the environment variables are read
where they have to be read: settings resolves them at import time, so each check runs
in a FRESH subprocess (reloading the module would not reproduce the real ordering).
"""

from __future__ import annotations

import os
import subprocess
import sys

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(REPO_ROOT, "project"))
sys.path.insert(0, os.path.dirname(__file__))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"


def assert_eq(a: object, b: object, msg: str = "") -> None:
    if a != b:
        raise AssertionError(f"{msg}\n  expected: {b!r}\n  actual:   {a!r}")


#############################################################################################################
# MARK: seeded weather
def _director_trace(seed: int, steps: int = 60) -> list[tuple[str, str | None, float]]:
    """Drive a WeatherDirector for ``steps`` ticks and record every decision it makes.

    Systems are stubs: the director only ever calls start()/stop() on them, so the real
    pygame emitters (and a display) are not needed here.
    """
    import random

    # settings FIRST: particles.py and settings.py import each other, and entering the
    # cycle from the particles side leaves settings half-built (PARTICLES registry)
    from settings import EmitterSchedule
    from particles import WeatherDirector

    class _StubSystem:
        def __init__(self) -> None:
            self.running = False

        def start(self) -> None:
            self.running = True

        def stop(self) -> None:
            self.running = False

    schedules = {
        "leafs": EmitterSchedule(group="sky", weight=1.0),
        "rain": EmitterSchedule(group="sky", weight=2.0),
    }
    systems = {name: _StubSystem() for name in schedules}
    director = WeatherDirector(systems, schedules, rng=random.Random(seed))  # type: ignore[arg-type]

    trace: list[tuple[str, str | None, float]] = []
    for _ in range(steps):
        before = dict(director._active)
        director.update(5.0)  # 5s per tick: long enough to cross episode boundaries
        for group, active in director._active.items():
            if active != before[group]:
                trace.append((group, active, round(director._timer[group], 6)))
    return trace


def test_the_same_seed_replays_the_same_weather_schedule() -> None:
    first = _director_trace(42)
    second = _director_trace(42)
    assert len(first) >= 5, f"the trace is too short to prove anything: {first}"
    assert_eq(first, second, "a seeded WeatherDirector must replay its decisions exactly")


def test_a_different_seed_gives_a_different_schedule() -> None:
    """Guard against the check above passing because nothing random happens at all."""
    a = _director_trace(42)
    b = _director_trace(2026)
    if a == b:
        raise AssertionError("two different seeds produced an identical schedule - "
                             "the rng is probably not being used")


#############################################################################################################
# MARK: environment variables (fresh subprocess - settings reads them at import time)
def _settings_value(expr: str, env_extra: dict[str, str]) -> str:
    env = dict(os.environ)
    env.update(env_extra)
    env.setdefault("SDL_VIDEODRIVER", "dummy")
    env.setdefault("SDL_AUDIODRIVER", "dummy")
    proc = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, 'project');"
         f"import settings; print({expr})"],
        capture_output=True, text=True, cwd=os.path.abspath(REPO_ROOT), env=env,
    )
    if proc.returncode != 0:
        raise AssertionError(f"settings import failed:\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout.strip().splitlines()[-1]


def test_the_flag_turns_on_the_fixed_world_seed() -> None:
    assert_eq(_settings_value("settings.TEST_WORLD_SEED", {"MOM_TEST_DETERMINISTIC": "1"}),
              "12345", "MOM_TEST_DETERMINISTIC=1 must pin the world seed")


def test_without_the_flag_the_world_seed_stays_random() -> None:
    env = {k: v for k, v in os.environ.items() if k != "MOM_TEST_DETERMINISTIC"}
    os.environ.pop("MOM_TEST_DETERMINISTIC", None)
    assert_eq(_settings_value("settings.TEST_WORLD_SEED", {}), "None",
              "without the flag the seed must stay unset (random per playthrough)")
    del env


def test_start_hour_can_be_forced() -> None:
    assert_eq(_settings_value("settings.INITIAL_HOUR", {"MOM_TEST_START_HOUR": "21"}),
              "21", "MOM_TEST_START_HOUR must override the start hour")


def test_start_hour_is_independent_of_the_deterministic_flag() -> None:
    """The two knobs are deliberately separate: a scenario may want night-time without
    a seeded world, and a seeded world must still start at the normal hour."""
    assert_eq(_settings_value("settings.INITIAL_HOUR", {"MOM_TEST_DETERMINISTIC": "1"}),
              "9", "the deterministic flag alone must not move the clock")


def test_the_start_hour_is_clamped_to_a_real_hour() -> None:
    assert_eq(_settings_value("settings.INITIAL_HOUR", {"MOM_TEST_START_HOUR": "99"}), "23")
    assert_eq(_settings_value("settings.INITIAL_HOUR", {"MOM_TEST_START_HOUR": "-5"}), "0")


def test_a_nonsense_start_hour_is_ignored_not_fatal() -> None:
    assert_eq(_settings_value("settings.INITIAL_HOUR", {"MOM_TEST_START_HOUR": "poludnie"}),
              "9", "a malformed value must fall back to the default, not crash the game")


def test_the_default_start_hour_is_nine() -> None:
    assert_eq(_settings_value("settings.INITIAL_HOUR", {}), "9")


def main() -> None:
    tests = [
        test_the_same_seed_replays_the_same_weather_schedule,
        test_a_different_seed_gives_a_different_schedule,
        test_the_flag_turns_on_the_fixed_world_seed,
        test_without_the_flag_the_world_seed_stays_random,
        test_start_hour_can_be_forced,
        test_start_hour_is_independent_of_the_deterministic_flag,
        test_the_start_hour_is_clamped_to_a_real_hour,
        test_a_nonsense_start_hour_is_ignored_not_fatal,
        test_the_default_start_hour_is_nine,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} deterministic-mode tests passed.")


if __name__ == "__main__":
    main()
