#!/usr/bin/env python3
"""Run the plain-Python unit tests in `tests/` and summarise them.

These tests do not use pytest (it is not a dependency). Each `tests/test_*.py`
is a standalone script whose `main()` calls a hand-written list of test
functions and exits non-zero on failure. This runner just executes each file in
a subprocess and aggregates the results.

It also enforces the one invariant that hand-written list has: **every**
`test_*` function a file defines must appear in it. Nothing else catches a test
that was written but never added to the list - it would simply never run, and
the file would still exit 0. That check is why this runner parses the sources
instead of only shelling out.

Usage:

    python scripts/run_unit_tests.py            # everything
    python scripts/run_unit_tests.py save_load  # only files matching a substring
    python scripts/run_unit_tests.py -v         # stream each file's own output
"""

from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "tests"
PROJECT_DIR = ROOT / "project"

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def _colour(text: str, code: str) -> str:
    return text if os.environ.get("NO_COLOR") else f"{code}{text}{RESET}"


def collect_test_files(pattern: str = "") -> list[Path]:
    files = sorted(p for p in TESTS_DIR.glob("test_*.py") if p.is_file())
    if pattern:
        files = [p for p in files if pattern in p.name]
    return files


def defined_and_registered(path: Path) -> tuple[set[str], set[str]]:
    """Return (test functions defined, those referenced somewhere in the file).

    A test is "registered" when its name is used as a value anywhere - listed in
    the runner's ``tests = [...]``, or named as a string. Definitions do not
    count as uses, so a function nobody references stands out.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in defined:
            used.add(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in defined:
            used.add(node.value)
    return defined, used


def run_file(path: Path, verbose: bool) -> tuple[bool, str]:
    env = {
        **os.environ,
        # the tests import from `project/` directly, and must never open a window
        "PYTHONPATH": str(PROJECT_DIR) + os.pathsep + os.environ.get("PYTHONPATH", ""),
        "PYGAME_HIDE_SUPPORT_PROMPT": "1",
        "SDL_VIDEODRIVER": "dummy",
        "SDL_AUDIODRIVER": "dummy",
    }
    proc = subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT, env=env, capture_output=True, text=True,
    )
    output = proc.stdout + proc.stderr
    if verbose:
        print(output.rstrip())
    return proc.returncode == 0, output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pattern", nargs="?", default="",
                        help="only run test files whose name contains this substring")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="stream each test file's own output")
    args = parser.parse_args()

    files = collect_test_files(args.pattern)
    if not files:
        print(f"no test files match {args.pattern!r} in {TESTS_DIR}")
        return 1

    failed: list[str] = []
    unregistered: list[str] = []
    total_tests = 0

    for path in files:
        defined, used = defined_and_registered(path)
        missing = sorted(defined - used)
        total_tests += len(defined)

        ok, output = run_file(path, args.verbose)
        if ok and not missing:
            mark, name_col = _colour("PASS", GREEN), DIM
        elif ok:
            mark, name_col = _colour("WARN", YELLOW), YELLOW
        else:
            mark, name_col = _colour("FAIL", RED), RED
        print(f"  {mark}  {_colour(path.name, name_col)}  ({len(defined)} tests)")

        if not ok:
            failed.append(path.name)
            if not args.verbose:
                for line in output.rstrip().splitlines()[-15:]:
                    print(f"        {line}")
        for m in missing:
            unregistered.append(f"{path.name}::{m}")
            print(f"        {_colour('not in the runner list:', YELLOW)} {m}")

    print()
    print("─" * 60)
    print(f"  {len(files)} files, {total_tests} tests")
    if unregistered:
        print(_colour(f"  {len(unregistered)} test(s) defined but never run "
                      f"- add them to their file's `tests = [...]` list", YELLOW))
    if failed:
        print(_colour(f"  FAILED  {len(failed)}/{len(files)} files: {', '.join(failed)}", RED))
        return 1
    if unregistered:
        return 1
    print(_colour(f"  PASSED  {len(files)}/{len(files)} files", GREEN))
    return 0


if __name__ == "__main__":
    sys.exit(main())
