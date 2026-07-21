#!/usr/bin/env python3
"""Tests for save_load/backends.py.

Run from the project root:
    .venv/bin/python tests/test_save_load_backends.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from save_load.backends import FileSaveBackend
from save_load.manager import SaveManager
from save_load.models import SaveGame, SaveMetadata, SaveSlot, SaveSlotInfo
from settings import MAX_SAVE_SLOTS, SAVE_FILE_EXT


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {a!r}, got {b!r}"


def test_file_backend_write_read() -> None:
    with tempfile.TemporaryDirectory() as td:
        backend = FileSaveBackend()
        backend.save_dir = Path(td)

        game = SaveGame(metadata=SaveMetadata(slot_name="Test", playtime=100.0))
        slot = SaveSlot(slot_id="0", save_data=game, is_occupied=True)
        assert backend.write_slot(slot), "write"
        path = backend._slot_path(0)
        assert path.exists(), "file exists"

        restored = backend.read_slot(0)
        assert restored is not None, "read"
        assert restored.is_occupied
        assert restored.save_data is not None
        assert_eq(restored.save_data.metadata.slot_name, "Test", "slot_name")
        assert_eq(restored.save_data.metadata.playtime, 100.0, "playtime")


def test_file_backend_read_empty() -> None:
    with tempfile.TemporaryDirectory() as td:
        backend = FileSaveBackend()
        backend.save_dir = Path(td)
        assert backend.read_slot(0) is None, "empty slot"


def test_file_backend_delete() -> None:
    with tempfile.TemporaryDirectory() as td:
        backend = FileSaveBackend()
        backend.save_dir = Path(td)

        slot = SaveSlot(slot_id="0", save_data=SaveGame(), is_occupied=True)
        backend.write_slot(slot)
        assert backend._slot_path(0).exists(), "written"
        assert backend.delete_slot(0), "deleted"
        assert not backend._slot_path(0).exists(), "file gone"
        assert not backend.delete_slot(0), "already gone"


def test_file_backend_list_slots() -> None:
    with tempfile.TemporaryDirectory() as td:
        backend = FileSaveBackend()
        backend.save_dir = Path(td)

        slots = backend.list_slots()
        assert_eq(len(slots), MAX_SAVE_SLOTS, "slot count")
        assert all(s is None for s in slots), "all empty"

        slot = SaveSlot(slot_id="0", save_data=SaveGame(metadata=SaveMetadata(slot_name="A")), is_occupied=True)
        backend.write_slot(slot)
        slots = backend.list_slots()
        assert slots[0] is not None, "slot 0 occupied"
        assert slots[0].is_occupied
        assert_eq(slots[0].metadata.slot_name, "A", "slot 0 name")
        assert all(s is None for i, s in enumerate(slots) if i != 0), "others empty"


def test_file_backend_corrupt_save() -> None:
    with tempfile.TemporaryDirectory() as td:
        backend = FileSaveBackend()
        backend.save_dir = Path(td)

        path = backend._slot_path(0)
        path.write_text("not valid json", encoding="utf-8")
        result = backend.read_slot(0)
        assert result is None, "corrupt file returns None"


def test_file_backend_overwrite() -> None:
    with tempfile.TemporaryDirectory() as td:
        backend = FileSaveBackend()
        backend.save_dir = Path(td)

        s1 = SaveSlot(slot_id="0", save_data=SaveGame(metadata=SaveMetadata(slot_name="First")), is_occupied=True)
        backend.write_slot(s1)
        s2 = SaveSlot(slot_id="0", save_data=SaveGame(metadata=SaveMetadata(slot_name="Second")), is_occupied=True)
        backend.write_slot(s2)
        restored = backend.read_slot(0)
        assert restored is not None
        assert_eq(restored.save_data.metadata.slot_name, "Second", "overwritten")


def test_file_backend_slot_basename() -> None:
    backend = FileSaveBackend()
    path = backend._slot_path(2)
    assert_eq(path.name, f"save_2{SAVE_FILE_EXT}", "filename")


def test_file_backend_list_with_mixed() -> None:
    with tempfile.TemporaryDirectory() as td:
        backend = FileSaveBackend()
        backend.save_dir = Path(td)

        backend.write_slot(SaveSlot(slot_id="0", save_data=SaveGame(metadata=SaveMetadata(slot_name="S1")), is_occupied=True))
        backend.write_slot(SaveSlot(slot_id="2", save_data=SaveGame(metadata=SaveMetadata(slot_name="S3")), is_occupied=True))

        infos = backend.list_slots()
        assert infos[0] is not None and infos[0].metadata.slot_name == "S1"
        assert infos[1] is None, "slot 1 empty"
        assert infos[2] is not None and infos[2].metadata.slot_name == "S3"
        assert infos[3] is None, "slot 3 empty"

        for i in range(4, MAX_SAVE_SLOTS):
            assert infos[i] is None, f"slot {i} empty"


def _manager_with_backend(backend: FileSaveBackend) -> SaveManager:
    """Build a SaveManager without a Game, wired to a specific backend (for unit tests)."""
    mgr = SaveManager.__new__(SaveManager)
    mgr.backend = backend
    return mgr


def test_manager_rename_slot() -> None:
    with tempfile.TemporaryDirectory() as td:
        backend = FileSaveBackend()
        backend.save_dir = Path(td)
        backend.write_slot(
            SaveSlot(slot_id="0", save_data=SaveGame(metadata=SaveMetadata(slot_name="Old")), is_occupied=True)
        )
        mgr = _manager_with_backend(backend)

        assert mgr.rename_slot(0, "New Name"), "rename occupied slot succeeds"
        restored = backend.read_slot(0)
        assert restored is not None and restored.save_data is not None
        assert_eq(restored.save_data.metadata.slot_name, "New Name", "renamed")


def test_manager_rename_sanitizes() -> None:
    with tempfile.TemporaryDirectory() as td:
        backend = FileSaveBackend()
        backend.save_dir = Path(td)
        backend.write_slot(SaveSlot(slot_id="0", save_data=SaveGame(), is_occupied=True))
        mgr = _manager_with_backend(backend)

        assert mgr.rename_slot(0, "  bad\nname\t" + "z" * 40), "rename with dirty name"
        restored = backend.read_slot(0)
        assert restored is not None and restored.save_data is not None
        name = restored.save_data.metadata.slot_name
        assert "\n" not in name and "\t" not in name, "control chars stripped"
        assert len(name) <= 20, "clamped to 20 chars"


def test_manager_rename_empty_slot_fails() -> None:
    with tempfile.TemporaryDirectory() as td:
        backend = FileSaveBackend()
        backend.save_dir = Path(td)
        mgr = _manager_with_backend(backend)
        assert not mgr.rename_slot(0, "Nope"), "rename of empty slot returns False"
        assert not mgr.rename_slot(-1, "Bad"), "out-of-range index returns False"


def test_every_save_dir_resolver_agrees() -> None:
    """The three independent copies of "where do saves live" must not drift.

    `FileSaveBackend`, the agent runner's `get_save_dir()` and the fixture helper
    each compute the path themselves. When the fixture helper alone ignored
    `XDG_DATA_HOME` it planted corrupt saves where the game never looked - the
    corrupt-save scenario passed while testing nothing - and the runner's sandbox
    could not contain it, so real saves were still reachable.
    """
    import importlib

    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    sys.path.insert(0, str(here.parent / "scripts"))
    import save_fixtures
    import automate_display_test as runner

    with tempfile.TemporaryDirectory() as td:
        old = os.environ.get("XDG_DATA_HOME")
        os.environ["XDG_DATA_HOME"] = td
        try:
            importlib.reload(save_fixtures)
            expected = Path(td) / "mom" / "saves"
            assert_eq(save_fixtures._get_save_dir(), expected, "fixture helper honours XDG_DATA_HOME")
            assert_eq(runner.get_save_dir(), expected, "test runner honours XDG_DATA_HOME")
            assert_eq(FileSaveBackend().save_dir, expected, "the game backend honours XDG_DATA_HOME")
        finally:
            if old is None:
                os.environ.pop("XDG_DATA_HOME", None)
            else:
                os.environ["XDG_DATA_HOME"] = old


def test_the_agent_runner_sandboxes_game_data() -> None:
    """`isolate_game_data()` must move the save dir off the developer's real one."""
    import automate_display_test as runner

    old = os.environ.get("XDG_DATA_HOME")
    try:
        os.environ.pop("XDG_DATA_HOME", None)
        real = runner.get_save_dir()
        runner.isolate_game_data()
        sandboxed = runner.get_save_dir()
        assert sandboxed != real, "the runner must not write to the real save dir"
        assert runner.SANDBOX_DIR in sandboxed.parents, \
            f"sandboxed save dir {sandboxed} is not under {runner.SANDBOX_DIR}"
    finally:
        if old is None:
            os.environ.pop("XDG_DATA_HOME", None)
        else:
            os.environ["XDG_DATA_HOME"] = old


if __name__ == "__main__":
    tests = [
        ("write and read", test_file_backend_write_read),
        ("read empty slot", test_file_backend_read_empty),
        ("delete slot", test_file_backend_delete),
        ("list slots", test_file_backend_list_slots),
        ("corrupt save", test_file_backend_corrupt_save),
        ("overwrite slot", test_file_backend_overwrite),
        ("slot filename", test_file_backend_slot_basename),
        ("list mixed", test_file_backend_list_with_mixed),
        ("manager rename slot", test_manager_rename_slot),
        ("manager rename sanitizes", test_manager_rename_sanitizes),
        ("manager rename empty fails", test_manager_rename_empty_slot_fails),
        ("save dir resolvers agree", test_every_save_dir_resolver_agrees),
        ("agent runner sandboxes game data", test_the_agent_runner_sandboxes_game_data),
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
