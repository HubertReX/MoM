#!/usr/bin/env python3
"""Round-trip serialisation tests for save_load/models.py.

Run from the project root:
    .venv/bin/python tests/test_save_load_models.py
"""

import json
import os
import sys
from copy import deepcopy
from typing import Any

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
    NPCDialogState,
    NPCState,
    PlayerState,
    SaveGame,
    SaveMetadata,
    SaveSlot,
    SaveSlotInfo,
    CURRENT_SAVE_CODE,
    MAX_SLOT_NAME_LEN,
    migrate_save,
    sanitize_slot_name,
    save_compatibility,
    version_code,
)
import save_load.models as models_mod
from enums import SaveCompatEnum
import settings
from settings import VERSION


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {a!r}, got {b!r}"


def test_metadata_roundtrip() -> None:
    orig = SaveMetadata(version="0.1", timestamp=10.0, playtime=123.45, slot_name="Test Save")
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


def test_npc_dialog_state_roundtrip() -> None:
    orig = NPCDialogState(
        current_node_key="NODE_002",
        selected_options={"OPT_A": True, "OPT_B": True},
        visited_nodes={"NODE_001": True, "NODE_002": True},
        sentiment=73,
    )
    d = orig.to_dict()
    restored = NPCDialogState.from_dict(d)
    assert_eq(orig, restored, "NPCDialogState")


def test_npc_state_with_dialog_state_roundtrip() -> None:
    dialog_state = NPCDialogState(
        current_node_key="NODE_003",
        selected_options={"OPT_1": True},
        visited_nodes={"NODE_001": True, "NODE_002": True, "NODE_003": True},
        sentiment=42,
    )
    orig = NPCState(
        name="Merchant",
        attitude=AttitudeEnum.friendly,
        pos_x=100.0,
        pos_y=200.0,
        health=80,
        dialog_state=dialog_state,
    )
    d = orig.to_dict()
    restored = NPCState.from_dict(d)
    assert_eq(orig, restored, "NPCState with dialog_state")


def test_npc_state_dialog_json_roundtrip() -> None:
    """Dialog state must survive the full JSON serialization used by backends."""
    dialog_state = NPCDialogState(
        current_node_key="NODE_002",
        selected_options={"OPT_A": True},
        visited_nodes={"NODE_001": True, "NODE_002": True},
        sentiment=88,
    )
    orig = NPCState(name="Hammer", attitude=AttitudeEnum.friendly, dialog_state=dialog_state)
    json_str = json.dumps(orig.to_dict())
    restored = NPCState.from_dict(json.loads(json_str))
    assert restored.dialog_state is not None
    assert_eq(restored.dialog_state.current_node_key, "NODE_002")
    assert_eq(restored.dialog_state.selected_options, {"OPT_A": True})
    assert_eq(restored.dialog_state.visited_nodes, {"NODE_001": True, "NODE_002": True})
    assert_eq(restored.dialog_state.sentiment, 88)


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
        metadata=SaveMetadata(version="0.1", timestamp=1000.0, playtime=3600.0, slot_name="Adventure 1"),
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
    meta = SaveMetadata(version="0.1", timestamp=500.0, playtime=100.0, slot_name="Quick Save")
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
        metadata=SaveMetadata(version="0.1", timestamp=99.0, playtime=5.0, slot_name="JSON Test"),
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
        "metadata": {"version": VERSION, "timestamp": 0.0, "playtime": 0.0, "slot_name": ""},
    }
    result = migrate_save(data)
    assert_eq(data, result, "migrate_save noop")


# ---------------------------------------------------------------------------
# Versioning policy (B02)
# ---------------------------------------------------------------------------


def _slot_dict(version: Any) -> dict[str, Any]:
    """A save slot as it looks on disk, with a chosen ``metadata.version``."""
    return {
        "slot_id": "1",
        "is_occupied": True,
        "save_data": {
            "metadata": {"version": version, "timestamp": 0.0, "playtime": 0.0, "slot_name": "S"},
            "player": {"map_name": "Village"},
            "clock": {"day": 1, "hour": 12, "minute": 0},
            "maps": {},
        },
    }


def _migrate_with(entries: list[tuple[str, Any]], min_supported: int,
                  data: dict[str, Any]) -> dict[str, Any]:
    """Run ``migrate_save`` against a temporary migration registry.

    The shipped registry is empty on purpose (nothing is migrated before 1.0), so the
    mechanism can only be exercised on stand-ins. ``min_supported`` is patched too -
    in alpha it equals the current code, which would refuse every older save before a
    migration got the chance to run.
    """
    saved_migrations = list(models_mod._MIGRATIONS)
    saved_min = models_mod.MIN_SUPPORTED_SAVE_CODE
    models_mod._MIGRATIONS.clear()
    models_mod.MIN_SUPPORTED_SAVE_CODE = min_supported
    try:
        for version, func in entries:
            models_mod._register_migration(version)(func)
        return migrate_save(data)
    finally:
        models_mod._MIGRATIONS[:] = saved_migrations
        models_mod.MIN_SUPPORTED_SAVE_CODE = saved_min


def test_version_code_basics() -> None:
    assert_eq(3, version_code("0.3"), "0.3")
    assert_eq(103, version_code("1.3"), "1.3")
    assert_eq(100, version_code("1.0"), "1.0")
    assert_eq(102, version_code("1.2.5"), "patch level is ignored")
    assert_eq(999900, version_code("9999"), "missing MINOR means 0")
    for junk in ("abc", "", "1.x", None, "-1.2", "0.100"):
        assert_eq(-1, version_code(junk), f"junk {junk!r}")


def test_version_code_monotonic() -> None:
    """The property a float version never had: 0.9 < 0.10 < 1.0."""
    assert version_code("0.9") < version_code("0.10") < version_code("1.0"), \
        "version codes must sort like versions, not like floats"


def test_legacy_float_version_reads_as_same_code() -> None:
    """Saves written so far store ``version`` as a float (0.3).

    It has to normalise to the string "0.3" - the same code the game writes - or the
    change to string versions would kill every existing save. Floats only ever
    appeared up to 0.3, so the ambiguity between 0.1 and 0.10 cannot bite here.
    """
    assert_eq(version_code("0.3"), version_code(0.3), "float vs string 0.3")
    slot = SaveSlot.from_dict(_slot_dict(0.3))
    assert slot.save_data is not None, "legacy save must still deserialize"
    assert_eq("0.3", slot.save_data.metadata.version, "normalised version")
    assert_eq("", slot.save_data.metadata.migrated_from, "nothing to migrate")


def test_save_compatibility_rules() -> None:
    assert_eq(SaveCompatEnum.ok, save_compatibility(VERSION), "current version")
    assert_eq(SaveCompatEnum.from_future, save_compatibility("9999"), "from the future")
    assert_eq(SaveCompatEnum.too_old, save_compatibility("0.1"), "pre-0.3 is unsupported")
    assert_eq(SaveCompatEnum.unreadable, save_compatibility("nonsense"), "garbage version")
    assert_eq(SaveCompatEnum.unreadable, save_compatibility(None), "missing version value")


def test_missing_version_key_means_current() -> None:
    """A save with no ``version`` key at all is read as the current version.

    Deliberate: ``SaveMetadata.from_dict`` has always defaulted that way, and the only
    dicts without the key are hand-made ones (fixtures, tests), never player saves.
    """
    meta = SaveMetadata.from_dict({"timestamp": 1.0})
    assert_eq(VERSION, meta.version, "defaulted version")
    assert_eq(SaveCompatEnum.ok, save_compatibility(meta.version), "and it loads")


def test_field_with_default_needs_no_migration() -> None:
    """The reason the schema almost never has to move: additive changes just load."""
    data = SaveGame().to_dict()
    del data["world_seed"]
    del data["player"]["damage"]
    restored = SaveGame.from_dict(data)
    assert_eq(0, restored.world_seed, "world_seed default")
    assert_eq(SaveGame().player.damage, restored.player.damage, "player.damage default")


def test_migration_chain_applies_in_order() -> None:
    """Only migrations newer than the save run, oldest first, and it is re-stamped."""
    trace: list[str] = []

    def to_0_2(data: dict[str, Any]) -> dict[str, Any]:
        trace.append("0.2")
        return data

    def to_0_3(data: dict[str, Any]) -> dict[str, Any]:
        trace.append("0.3")
        return data

    result = _migrate_with([("0.3", to_0_3), ("0.2", to_0_2)], 0, _slot_dict("0.1")["save_data"])
    assert_eq(["0.2", "0.3"], trace, "migrations run oldest first")
    assert_eq(VERSION, result["metadata"]["version"], "re-stamped to the current version")
    assert_eq("0.1", result["metadata"]["migrated_from"], "origin recorded")


def test_migration_skips_versions_at_or_below_the_save() -> None:
    trace: list[str] = []

    def to_0_2(data: dict[str, Any]) -> dict[str, Any]:
        trace.append("0.2")
        return data

    def to_0_3(data: dict[str, Any]) -> dict[str, Any]:
        trace.append("0.3")
        return data

    _migrate_with([("0.2", to_0_2), ("0.3", to_0_3)], 0, _slot_dict("0.2")["save_data"])
    assert_eq(["0.3"], trace, "a migration for the save's own version must not re-run")


def test_release_without_format_change_needs_no_migration() -> None:
    """An older save with an EMPTY chain still loads - it is simply re-stamped.

    This is what makes one shared game/save version number affordable: a content-only
    release does not have to register an identity migration.
    """
    result = _migrate_with([], 0, _slot_dict("0.1")["save_data"])
    assert_eq(VERSION, result["metadata"]["version"], "re-stamped")
    assert_eq("0.1", result["metadata"]["migrated_from"], "origin recorded")


def test_two_migrations_with_the_same_code_do_not_crash() -> None:
    """Regression: ``sorted`` on bare tuples compared functions and raised TypeError."""
    def first(data: dict[str, Any]) -> dict[str, Any]:
        return data

    def second(data: dict[str, Any]) -> dict[str, Any]:
        return data

    result = _migrate_with([("0.3", first), ("0.3", second)], 0, _slot_dict("0.1")["save_data"])
    assert_eq(VERSION, result["metadata"]["version"], "still migrated")


def test_incompatible_save_is_returned_untouched() -> None:
    """A save that cannot be brought forward keeps its version - that IS the refusal.

    If migrate_save re-stamped it anyway, the gate in SaveManager.load would see a
    current version and happily load a save it cannot understand.
    """
    def boom(data: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("migration must not run on an incompatible save")

    for version in ("9999", "0.1", "junk"):
        original = _slot_dict(version)["save_data"]
        before = deepcopy(original)
        result = _migrate_with([("0.3", boom)], CURRENT_SAVE_CODE, original)
        assert_eq(before, result, f"untouched for version {version}")


def test_fixture_version_matches_settings() -> None:
    """``scripts/save_fixtures.py`` cannot import settings, so it hardcodes the version.

    If a release bumps VERSION and forgets the fixture, every "minimal save" scenario
    would silently start testing a rejected save instead.
    """
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import save_fixtures

    assert_eq(VERSION, save_fixtures.CURRENT_VERSION, "fixture version")
    # Ta sama klasa rozjazdu, tylko o mapę startową (C02, D5): fixture stawiający
    # gracza na nieistniejącej mapie wczytałby się i wywalił ładowarkę.
    assert_eq(settings.START_MAP, save_fixtures.START_MAP, "fixture start map")
    assert_eq(SaveCompatEnum.ok,
              save_compatibility(save_fixtures.minimal_save_dict(1)["save_data"]["metadata"]["version"]),
              "minimal fixture must be loadable")
    assert_eq(SaveCompatEnum.from_future, save_compatibility(save_fixtures.FUTURE_VERSION), "future fixture")
    assert_eq(SaveCompatEnum.too_old, save_compatibility(save_fixtures.OLD_VERSION), "old fixture")


def test_empty_defaults() -> None:
    """All models should construct with no args."""
    models: list[Any] = [
        SaveMetadata(),
        ItemState(),
        GroundItemState(),
        PlayerState(),
        NPCDialogState(),
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
        ("npc dialog state round-trip", test_npc_dialog_state_roundtrip),
        ("npc state with dialog state round-trip", test_npc_state_with_dialog_state_roundtrip),
        ("npc state dialog JSON round-trip", test_npc_state_dialog_json_roundtrip),
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
        ("version code basics", test_version_code_basics),
        ("version code monotonic", test_version_code_monotonic),
        ("legacy float version", test_legacy_float_version_reads_as_same_code),
        ("save compatibility rules", test_save_compatibility_rules),
        ("missing version key", test_missing_version_key_means_current),
        ("field with default needs no migration", test_field_with_default_needs_no_migration),
        ("migration chain order", test_migration_chain_applies_in_order),
        ("migration skips own version", test_migration_skips_versions_at_or_below_the_save),
        ("release without format change", test_release_without_format_change_needs_no_migration),
        ("two migrations same code", test_two_migrations_with_the_same_code_do_not_crash),
        ("incompatible save untouched", test_incompatible_save_is_returned_untouched),
        ("fixture version in sync", test_fixture_version_matches_settings),
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
