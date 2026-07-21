#!/usr/bin/env python3
"""Save-file fixtures for the agent test suite - NOT a test file itself.

Used by `tests/automate_display_test.py` to plant a corrupt / minimal save before
a scenario runs, and usable by hand as a CLI (see `__main__` at the bottom).

Lives in `scripts/` rather than `tests/` for two reasons: it is a helper script
(the repo keeps those together), and under its old `test_*.py` name any runner
globbing the test dir collected it and reported a file "passing" that defines no
tests and asserts nothing.

Functions:
- corrupt_save(slot_idx) — overwrite a save file with invalid JSON
- corrupt_save_version(slot_idx) — overwrite with valid JSON but wrong version
- create_dummy_save(slot_idx) — create a minimal valid save for testing
- delete_save(slot_idx) — remove a specific save file
- clear_all_saves() — remove all save files
- get_save_path(slot_idx) — get the full path to a save slot file
- corrupt_save_text() — invalid JSON string for corrupt slots (desktop + web)
- minimal_save_dict(slot_idx, version=1) — dict of a minimal valid save
"""

from __future__ import annotations

import json
import os
import platform as _platform
from pathlib import Path

SAVE_FILE_EXT = ".mom"
MAX_SAVE_SLOTS = 10


def corrupt_save_text() -> str:
    """Invalid-JSON payload used for corrupt save slots (desktop file or web localStorage)."""
    return "this is not valid json {{{"


def minimal_save_dict(slot_idx: int, version: int = 1) -> dict:
    """Minimal valid save dict (deskop .mom content or web localStorage value)."""
    return {
        "slot_id": str(slot_idx),
        "is_occupied": True,
        "save_data": {
            "metadata": {
                "version": version,
                "timestamp": 0.0,
                "playtime": 0.0,
                "slot_name": f"Slot {slot_idx + 1}",
            },
            "player": {
                "name": "Player",
                "health": 100,
                "max_health": 100,
                "pos_x": 0.0,
                "pos_y": 0.0,
                "current_map": "Village",
                "entry_point": "start",
                "money": 0,
                "items": [],
                "is_dead": False,
            },
            "clock": {"hour": 12, "minute": 0, "day": 1, "total_seconds": 43200.0},
            "maps": {},
        },
    }


def _get_save_dir() -> Path:
    """Where the game keeps its saves - must match ``FileSaveBackend`` exactly.

    ``XDG_DATA_HOME`` wins over the per-OS default, like it does in the backend
    and in the test runner. Without that branch this module wrote to the macOS
    default while the game read the XDG path: fixtures landed somewhere the game
    never looked (so corrupt-save scenarios silently tested nothing), and the
    runner's sandbox could not contain them.
    """
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "mom" / "saves"
    system = _platform.system()
    if system == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "mom" / "saves"
    elif system == "Linux":
        base = Path.home() / ".local" / "share" / "mom" / "saves"
    else:
        base = Path.home() / "AppData" / "Local" / "mom" / "saves"
    return base


def get_save_path(slot_idx: int) -> Path:
    return _get_save_dir() / f"save_{slot_idx}{SAVE_FILE_EXT}"


def corrupt_save(slot_idx: int) -> Path:
    """Overwrite save file with invalid JSON (corrupt)."""
    path = get_save_path(slot_idx)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(corrupt_save_text(), encoding="utf-8")
    print(f"[corrupt] wrote invalid JSON -> {path}")
    return path


def corrupt_save_version(slot_idx: int) -> Path:
    """Write valid JSON but with an unknown SAVE_VERSION to test migration handling."""
    path = get_save_path(slot_idx)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = minimal_save_dict(slot_idx, version=9999)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[corrupt] wrote bad-version JSON -> {path}")
    return path


def create_minimal_save(slot_idx: int) -> Path:
    """Create a minimal valid save file for testing load flows."""
    path = get_save_path(slot_idx)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = minimal_save_dict(slot_idx)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[save] wrote minimal save -> {path}")
    return path


def delete_save(slot_idx: int) -> bool:
    path = get_save_path(slot_idx)
    if path.exists():
        path.unlink()
        print(f"[save] deleted -> {path}")
        return True
    return False


def clear_all_saves() -> None:
    save_dir = _get_save_dir()
    for i in range(MAX_SAVE_SLOTS):
        path = save_dir / f"save_{i}{SAVE_FILE_EXT}"
        if path.exists():
            path.unlink()
            print(f"[save] cleaned up -> {path}")


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "corrupt":
        idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        corrupt_save(idx)
    elif cmd == "corrupt_version":
        idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        corrupt_save_version(idx)
    elif cmd == "create":
        idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        create_minimal_save(idx)
    elif cmd == "delete":
        idx = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        delete_save(idx)
    elif cmd == "clear":
        clear_all_saves()
    else:
        print(f"Usage: {sys.argv[0]} <corrupt|corrupt_version|create|delete|clear> [slot_idx]")
        print("  corrupt <N>       — write invalid JSON to save slot N")
        print("  corrupt_version   — write valid JSON with version=9999")
        print("  create <N>        — write minimal valid save to slot N")
        print("  delete <N>        — delete save slot N")
        print("  clear             — delete all save files")
