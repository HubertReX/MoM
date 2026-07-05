#!/usr/bin/env python3
"""Round-trip serialisation tests for save_load/models.py.

Run from the project root:
    .venv/bin/python tests/test_save_load_models.py
"""

import json
import os
import sys
from copy import deepcopy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from enums import AttitudeEnum, ItemTypeEnum
from save_load.models import (
    ChestState,
    GameClockState,
    GroundItemState,
    ItemState,
    MapState,
    NPCState,
    PlayerState,
    SaveGame,
    SaveMetadata,
    SaveSlot,
    SaveSlotInfo,
    SAVE_VERSION,
    MAX_SLOT_NAME_LEN,
    migrate_save,
    sanitize_slot_name,
)


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {a!r}, got {b!r}"


def test_metadata_roundtrip() -> None:
    orig = SaveMetadata(version=0.1, timestamp=10.0, playtime=123.45, slot_name="Test Save")
    d = orig.to_dict()
    restored = SaveMetadata.from_dict(d)
    assert_eq(orig, restored, "SaveMetadata")


def test_item_state_roundtrip() -> None:
    orig = ItemState(
        name="sword",
        type=ItemTypeEnum.weapon,
        count=1,
        value=50,
        weight=2.5,
        damage=12,
        cooldown_time=500,
        health_impact=0,
    )
    d = orig.to_dict()
    restored = ItemState.from_dict(d)
    assert_eq(orig, restored, "ItemState")


def test_item_state_enum_as_string() -> None:
    orig = ItemState(name="gold", type=ItemTypeEnum.money)
    d = orig.to_dict()
    assert isinstance(d["type"], str), f"type is {type(d['type'])} not str"
    assert_eq(d["type"], ItemTypeEnum.money.value, "enum→str")


def test_ground_item_state_roundtrip() -> None:
    orig = GroundItemState(
        name="potion",
        type=ItemTypeEnum.consumable,
        count=1,
        value=10,
        weight=0.5,
        damage=0,
        cooldown_time=0,
        health_impact=25,
        pos_x=120.5,
        pos_y=80.0,
    )
    d = orig.to_dict()
    restored = GroundItemState.from_dict(d)
    assert_eq(orig, restored, "GroundItemState")


def test_player_state_roundtrip() -> None:
    orig = PlayerState(
        map_name="Village",
        entry_point="start",
        pos_x=320.0,
        pos_y=240.0,
        health=75,
        max_health=100,
        money=250,
        inventory=[
            ItemState(name="sword", type=ItemTypeEnum.weapon, count=1),
            ItemState(name="potion", type=ItemTypeEnum.consumable, count=3),
        ],
        selected_weapon="sword",
        selected_item_idx=0,
        is_flying=False,
        is_jumping=False,
        is_dead=False,
    )
    d = orig.to_dict()
    restored = PlayerState.from_dict(d)
    assert_eq(orig, restored, "PlayerState")


def test_npc_state_roundtrip() -> None:
    orig = NPCState(
        name="Guard",
        attitude=AttitudeEnum.friendly,
        pos_x=400.0,
        pos_y=300.0,
        health=50,
        money=0,
        is_dead=False,
        inventory=[ItemState(name="key", type=ItemTypeEnum.key, count=1)],
    )
    d = orig.to_dict()
    restored = NPCState.from_dict(d)
    assert_eq(orig, restored, "NPCState")


def test_npc_state_attitude_enum() -> None:
    for att in AttitudeEnum:
        orig = NPCState(name="npc", attitude=att)
        d = orig.to_dict()
        assert isinstance(d["attitude"], str), f"attitude is {type(d['attitude'])}"
        restored = NPCState.from_dict(d)
        assert_eq(orig, restored, f"NPCState with attitude={att}")


def test_chest_state_roundtrip() -> None:
    orig = ChestState(name="Treasure", is_closed=True, items=["gold", "gem"])
    d = orig.to_dict()
    restored = ChestState.from_dict(d)
    assert_eq(orig, restored, "ChestState")


def test_game_clock_roundtrip() -> None:
    orig = GameClockState(day=3, hour=14, minute=30, time_elapsed=5000.0)
    d = orig.to_dict()
    restored = GameClockState.from_dict(d)
    assert_eq(orig, restored, "GameClockState")


def test_map_state_roundtrip() -> None:
    orig = MapState(
        name="Dungeon",
        chests={"treasure": ChestState(name="Treasure", is_closed=False, items=["gem"])},
        ground_items=[
            GroundItemState(name="coin", type=ItemTypeEnum.money, count=5, pos_x=64.0, pos_y=128.0),
        ],
        destroyed_walls=[(5, 10), (6, 10)],
        maze_seed=42,
        maze_level=1,
        dead_monsters=["Goblin1", "Goblin2"],
    )
    d = orig.to_dict()
    restored = MapState.from_dict(d)
    assert_eq(orig, restored, "MapState")


def test_map_state_no_maze() -> None:
    orig = MapState(
        name="Village",
        maze_seed=None,
        maze_level=None,
    )
    d = orig.to_dict()
    restored = MapState.from_dict(d)
    assert_eq(orig, restored, "MapState (no maze)")


def test_save_game_roundtrip() -> None:
    orig = SaveGame(
        metadata=SaveMetadata(version=0.1, timestamp=1000.0, playtime=3600.0, slot_name="Adventure 1"),
        player=PlayerState(
            map_name="Village",
            pos_x=100.0,
            pos_y=200.0,
            health=80,
            max_health=100,
            money=50,
        ),
        clock=GameClockState(day=2, hour=10, minute=15, time_elapsed=2000.0),
        maps={
            "Village": MapState(name="Village"),
            "Dungeon": MapState(
                name="Dungeon",
                chests={"chest1": ChestState(name="chest1", is_closed=True)},
                destroyed_walls=[(3, 4)],
                dead_monsters=["Rat"],
            ),
        },
    )
    d = orig.to_dict()
    restored = SaveGame.from_dict(d)
    assert_eq(orig, restored, "SaveGame")


def test_save_slot_roundtrip() -> None:
    save = SaveGame(metadata=SaveMetadata(slot_name="Test"))
    orig = SaveSlot(slot_id="slot_00", save_data=save, is_occupied=True)
    d = orig.to_dict()
    restored = SaveSlot.from_dict(d)
    assert_eq(orig, restored, "SaveSlot")


def test_save_slot_empty() -> None:
    orig = SaveSlot(slot_id="slot_01", save_data=None, is_occupied=False)
    d = orig.to_dict()
    restored = SaveSlot.from_dict(d)
    assert_eq(orig, restored, "SaveSlot (empty)")


def test_save_slot_info_roundtrip() -> None:
    meta = SaveMetadata(version=0.1, timestamp=500.0, playtime=100.0, slot_name="Quick Save")
    orig = SaveSlotInfo(slot_id="slot_00", is_occupied=True, metadata=meta)
    d = orig.to_dict()
    restored = SaveSlotInfo.from_dict(d)
    assert_eq(orig, restored, "SaveSlotInfo")


def test_save_slot_info_empty() -> None:
    orig = SaveSlotInfo(slot_id="slot_02", is_occupied=False, metadata=None)
    d = orig.to_dict()
    restored = SaveSlotInfo.from_dict(d)
    assert_eq(orig, restored, "SaveSlotInfo (empty)")


def test_sanitize_slot_name_basic() -> None:
    assert_eq("Hero", sanitize_slot_name("Hero"), "plain name unchanged")
    assert_eq("A B 12", sanitize_slot_name("A B 12"), "letters digits spaces kept")


def test_sanitize_slot_name_strips_and_clamps() -> None:
    assert_eq("Hero", sanitize_slot_name("   Hero   "), "surrounding whitespace stripped")
    long = "A" * 40
    assert len(sanitize_slot_name(long)) == MAX_SLOT_NAME_LEN, "clamped to MAX_SLOT_NAME_LEN"


def test_sanitize_slot_name_removes_control_chars() -> None:
    # newlines / tabs / carriage returns / other control chars must be dropped
    dirty = "He\nll\to\r\x00Slot\x1b"
    cleaned = sanitize_slot_name(dirty)
    assert "\n" not in cleaned and "\t" not in cleaned and "\r" not in cleaned, "no control chars"
    assert "\x00" not in cleaned and "\x1b" not in cleaned, "no null/escape chars"
    assert_eq("HelloSlot", cleaned, "control chars removed, rest intact")


def test_sanitize_slot_name_survives_json_roundtrip() -> None:
    # a name with quotes/backslashes/newlines must still produce a loadable save
    meta = SaveMetadata(slot_name=sanitize_slot_name('bad"name\\\n' + "x" * 50))
    slot = SaveSlot(slot_id="0", save_data=SaveGame(metadata=meta), is_occupied=True)
    raw = json.dumps(slot.to_dict())  # must not raise
    restored = SaveSlot.from_dict(json.loads(raw))
    assert restored.save_data is not None
    name = restored.save_data.metadata.slot_name
    assert len(name) <= MAX_SLOT_NAME_LEN, "sanitized length survives round-trip"
    assert "\n" not in name, "no newline survived into the save"


def test_json_roundtrip() -> None:
    """Full JSON round-trip: model → dict → json → dict → model."""
    orig = SaveGame(
        metadata=SaveMetadata(version=0.1, timestamp=99.0, playtime=5.0, slot_name="JSON Test"),
        player=PlayerState(
            map_name="Dungeon",
            pos_x=50.0,
            pos_y=75.0,
            health=100,
            max_health=100,
            money=999,
            inventory=[ItemState(name="sword", type=ItemTypeEnum.weapon, value=100)],
            selected_weapon="sword",
            selected_item_idx=0,
        ),
        clock=GameClockState(day=1, hour=9, minute=0, time_elapsed=0.0),
        maps={
            "Dungeon": MapState(
                name="Dungeon",
                destroyed_walls=[(1, 1)],
                dead_monsters=["Slime"],
            ),
        },
    )
    json_str = json.dumps(orig.to_dict(), indent=2)
    parsed = json.loads(json_str)
    restored = SaveGame.from_dict(parsed)
    assert_eq(orig, restored, "JSON round-trip")


def test_migrate_save_noop() -> None:
    """migrate_save on current version should be a no-op."""
    data = {
        "metadata": {"version": SAVE_VERSION, "timestamp": 0.0, "playtime": 0.0, "slot_name": ""},
    }
    result = migrate_save(data)
    assert_eq(data, result, "migrate_save noop")


def test_empty_defaults() -> None:
    """All models should construct with no args."""
    models = [
        SaveMetadata(),
        ItemState(),
        GroundItemState(),
        PlayerState(),
        NPCState(),
        ChestState(),
        GameClockState(),
        MapState(),
        SaveGame(),
        SaveSlot(),
        SaveSlotInfo(),
    ]
    for m in models:
        d = m.to_dict()
        restored = type(m).from_dict(d)  # type: ignore[attr-defined]
        assert_eq(m, restored, f"empty {type(m).__name__}")
    print(f"  OK — {len(models)} empty models round-tripped")


def test_deep_copy_independence() -> None:
    """to_dict returns independent dicts; from_dict returns independent models."""
    orig = PlayerState(inventory=[ItemState(name="ring", type=ItemTypeEnum.gem)])
    d = orig.to_dict()
    d["inventory"].append({"name": "extra"})  # mutate dict
    assert len(orig.inventory) == 1, "to_dict shared reference"


if __name__ == "__main__":
    tests = [
        ("empty defaults", test_empty_defaults),
        ("metadata round-trip", test_metadata_roundtrip),
        ("item state round-trip", test_item_state_roundtrip),
        ("item enum as string", test_item_state_enum_as_string),
        ("ground item round-trip", test_ground_item_state_roundtrip),
        ("player state round-trip", test_player_state_roundtrip),
        ("npc state round-trip", test_npc_state_roundtrip),
        ("npc attitude enum", test_npc_state_attitude_enum),
        ("chest state round-trip", test_chest_state_roundtrip),
        ("game clock round-trip", test_game_clock_roundtrip),
        ("map state round-trip", test_map_state_roundtrip),
        ("map state no maze", test_map_state_no_maze),
        ("save game round-trip", test_save_game_roundtrip),
        ("save slot round-trip", test_save_slot_roundtrip),
        ("save slot empty", test_save_slot_empty),
        ("save slot info round-trip", test_save_slot_info_roundtrip),
        ("save slot info empty", test_save_slot_info_empty),
        ("sanitize slot name basic", test_sanitize_slot_name_basic),
        ("sanitize slot name strip/clamp", test_sanitize_slot_name_strips_and_clamps),
        ("sanitize slot name control chars", test_sanitize_slot_name_removes_control_chars),
        ("sanitize slot name JSON safe", test_sanitize_slot_name_survives_json_roundtrip),
        ("JSON round-trip", test_json_roundtrip),
        ("migrate save noop", test_migrate_save_noop),
        ("deep copy independence", test_deep_copy_independence),
    ]
    failures = 0
    for name, func in tests:
        try:
            func()
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failures += 1

    print(f"\n{'─' * 40}")
    total = len(tests)
    passed = total - failures
    if failures:
        print(f"  FAILED  {failures}/{total} tests")
        sys.exit(1)
    else:
        print(f"  PASSED  {passed}/{total} tests")
