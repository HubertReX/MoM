#!/usr/bin/env python3
"""Integration tests for quest-state persistence in save/load (Q-06).

Run from the project root:
    .venv/bin/python tests/test_save_load_quest_state.py

Decision D13: progress lives in the savegame, never in config.json. config.json is
a generated artifact — `just import-quests` rewrites it wholesale — so anything
stored there would be erased by the next content edit.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from quest.entities import QuestState
from save_load.manager import SaveManager
from save_load.models import SaveGame

Q00 = "Q00_S00_WHAT_IS_GOING_ON"
Q01 = "Q01_S01_LEARN_ABOUT_CURSE"


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def _manager(known_quests: dict[str, object] | None = None) -> SaveManager:
    mgr = SaveManager.__new__(SaveManager)
    mgr.game = SimpleNamespace(conf=SimpleNamespace(quests=known_quests or {}))
    return mgr


def test_save_game_roundtrips_quest_progress() -> None:
    state = QuestState()
    state.mark_done(Q00)

    save = SaveGame(quests=state.to_dict())
    restored = SaveGame.from_dict(json.loads(json.dumps(save.to_dict())))

    assert_eq(restored.quests, {Q00: {"done": True}}, "flat, readable shape in the save")
    assert_true(QuestState.from_dict(restored.quests).is_done(Q00), "progress survives JSON")


def test_build_captures_scene_progress() -> None:
    state = QuestState()
    state.mark_done(Q00)
    scene = SimpleNamespace(quest_state=state)

    assert_eq(_manager()._build_quest_state(scene), {Q00: {"done": True}}, "captured from the scene")

    # a scene with no quest state at all (older code path) must not crash the save
    assert_eq(_manager()._build_quest_state(SimpleNamespace()), {}, "no quest state -> empty")


def test_apply_restores_progress_to_the_scene() -> None:
    scene = SimpleNamespace()
    mgr = _manager({Q00: {}, Q01: {}})

    mgr._apply_quest_state(scene, {Q00: {"done": True}, Q01: {"done": False}})

    assert_true(scene.quest_state.is_done(Q00), "done quest restored")
    assert_true(not scene.quest_state.is_done(Q01), "unfinished quest restored")


def test_unknown_quest_keys_are_dropped_not_fatal() -> None:
    """Content was renamed under the save: warn, drop, keep playing."""
    scene = SimpleNamespace()
    mgr = _manager({Q00: {}})

    mgr._apply_quest_state(scene, {Q00: {"done": True}, "Q99_DELETED_QUEST": {"done": True}})

    assert_true(scene.quest_state.is_done(Q00), "known progress kept")
    assert_true("Q99_DELETED_QUEST" not in scene.quest_state.entries, "unknown key dropped")


def test_quest_defined_but_absent_from_save_is_not_done() -> None:
    """New content added after the save was written simply starts unfinished."""
    scene = SimpleNamespace()
    mgr = _manager({Q00: {}, "Q_BRAND_NEW": {}})

    mgr._apply_quest_state(scene, {Q00: {"done": True}})

    assert_true(scene.quest_state.is_done(Q00), "old progress kept")
    assert_true(not scene.quest_state.is_done("Q_BRAND_NEW"), "new quest starts not done")


def test_corrupt_quest_state_degrades_instead_of_crashing() -> None:
    scene = SimpleNamespace()
    mgr = _manager({Q00: {}})

    for junk in ({Q00: "yes"}, {Q00: None}, {Q00: []}):
        mgr._apply_quest_state(scene, junk)  # type: ignore[arg-type]
        assert_true(not scene.quest_state.is_done(Q00), f"junk entry {junk!r} -> not done")

    # a whole-section corruption is survivable too
    assert_eq(SaveGame.from_dict({"quests": "garbage"}).quests, {}, "non-dict section -> empty")
    assert_eq(SaveGame.from_dict({}).quests, {}, "save written before quests existed")


def test_reimporting_content_does_not_lose_progress() -> None:
    """The DoD of D13, end to end: `just import-quests` must not touch the save.

    Rewrites config.json exactly the way the importer does (wholesale) and checks
    the save is untouched — this is the SSiS failure being designed out, where the
    config *was* the savegame.
    """
    from quest.markdown_importer import build_quest_config

    pl = """---
aliases:
  - Q00
---

## S00_WHAT_IS_GOING_ON

**Tytuł**: O co tu chodzi?

Miecz gada.

**Completion**: test
**Test**: visited("CLAPBACK_SWORD", "015")
**Sukces**: To klątwa.
"""
    en = pl.replace("**Tytuł**: O co tu chodzi?", "**Title**: What is going on?").replace(
        "Miecz gada.", "The sword talks."
    ).replace("**Sukces**: To klątwa.", "**Success**: It is a curse.").replace(
        '**Completion**: test\n**Test**: visited("CLAPBACK_SWORD", "015")\n', ""
    )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "PL/Misje").mkdir(parents=True)
        (root / "EN/Quests").mkdir(parents=True)
        (root / "PL/Misje/a.md").write_text(pl, encoding="utf-8")
        (root / "EN/Quests/a.md").write_text(en, encoding="utf-8")

        config_path = root / "config.json"
        config_path.write_text(json.dumps({"messages": {"PL": {}, "EN": {}}}), encoding="utf-8")

        # the player has finished Q00 and their progress is in the save, not the config
        save_path = root / "save.json"
        state = QuestState()
        state.mark_done(Q00)
        save_path.write_text(json.dumps(SaveGame(quests=state.to_dict()).to_dict()), encoding="utf-8")
        before = save_path.read_text(encoding="utf-8")

        # author edits the prose and re-imports
        (root / "PL/Misje/a.md").write_text(
            pl.replace("Miecz gada.", "Miecz gada i nie przestaje."), encoding="utf-8"
        )
        rc = build_quest_config(src_dir=root, config_path=config_path, chain_keys=["Q00"])
        assert_eq(rc, 0, "re-import succeeded")

        assert_eq(save_path.read_text(encoding="utf-8"), before, "save is byte-identical")
        reloaded = SaveGame.from_dict(json.loads(save_path.read_text(encoding="utf-8")))
        assert_true(QuestState.from_dict(reloaded.quests).is_done(Q00), "progress survives re-import")

        # and the config really did change (otherwise the test proves nothing)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert_true(
            "nie przestaje" in config["messages"]["PL"][f"M_QUEST_{Q00}_DESCRIPTION"],
            "config.json was actually rewritten",
        )
        assert_true("quests" in config and Q00 in config["quests"], "quest redefined in config")
        assert_true(
            "done" not in json.dumps(config["quests"][Q00]),
            "config.json holds no progress — that is what the save is for (D13)",
        )


def main() -> None:
    tests = [
        test_save_game_roundtrips_quest_progress,
        test_build_captures_scene_progress,
        test_apply_restores_progress_to_the_scene,
        test_unknown_quest_keys_are_dropped_not_fatal,
        test_quest_defined_but_absent_from_save_is_not_done,
        test_corrupt_quest_state_degrades_instead_of_crashing,
        test_reimporting_content_does_not_lose_progress,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} quest-state persistence tests passed.")


if __name__ == "__main__":
    main()
