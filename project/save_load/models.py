"""Save data models — pure dataclasses (no Pydantic).

Works on both desktop and pygbag/WASM.

Serialization: dataclass → dict (JSON-safe) → JSON → dict → dataclass round-trip.
All enums serialized as strings.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, cast

from enums import AttitudeEnum, ItemTypeEnum, SaveCompatEnum
from npc_runtime import NpcRuntime
from settings import MAX_HOTBAR_ITEMS, VERSION


# ---------------------------------------------------------------------------
# Save versioning policy
# ---------------------------------------------------------------------------
#
# ONE version number. The version of a save IS the version of the game
# (``settings.VERSION``, "MAJOR.MINOR"). There is no separate schema number: the
# player knows the game version and would never see a schema one.
#
# Comparisons never touch the string or a float - they go through
# ``version_code()``: "0.3" -> 3, "1.3" -> 103 (MAJOR * 100 + MINOR, MINOR in 0..99).
# There is deliberately NO patch level in the save contract: if a fix would change
# the format, it bumps MINOR. Old files store ``version`` as a float (0.3); the code
# reads it through ``str()``, so 0.3 -> "0.3" -> 3 and pre-existing saves keep working.
#
# Two constants steer everything:
#
#   CURRENT_SAVE_CODE       - the version the game writes.
#   MIN_SUPPORTED_SAVE_CODE - the OLDEST save code that can still be brought forward.
#
# Before 1.0 (now) MIN_SUPPORTED_SAVE_CODE equals CURRENT_SAVE_CODE and is bumped
# together with VERSION on every release: older saves are refused with a visible
# message, and the game carries no migrations at all (the format is still moving and
# nobody's progress is at stake yet). From 1.0 on it freezes at 100 and never moves
# again; from that point every format change ships with a migration.
#
# A migration is keyed by the version in which THE FORMAT CHANGED, not by every
# release - see ``_register_migration``. A release that does not touch the format
# needs no entry: the chain is simply empty, the save passes and is re-stamped. That
# is what makes one shared version number affordable.
#
# When a migration is needed (from 1.0 on):
#   NO  - adding a field with a default that ``from_dict`` fills in for old saves.
#         This is the normal case (NPCState.config_key, SaveGame.world_seed, ...).
#   YES - renaming a field, removing one, changing the meaning of a value under the
#         same name (like the 0.2 sentiment keys), or a type change ``int()``/``str()``
#         will not swallow.
#
# Load rules (implemented once, in ``save_compatibility``):
#
#   == CURRENT                      -> load
#   >= MIN_SUPPORTED and < CURRENT  -> run the migration chain, re-stamp, load
#   >  CURRENT                      -> refuse: save from a newer version of the game
#   <  MIN_SUPPORTED                -> refuse: save from an older, unsupported version
#   unparsable                      -> refuse
#
# A save that cannot be read is never deleted by the game. Its slot stays on the
# list, greyed out, showing its version and the reason; the player can delete or
# overwrite it. Refusing a load never touches the game state.


def version_code(value: str | float | int | None) -> int:
    """``"0.3"`` -> 3, ``"1.3"`` -> 103, ``0.3`` (legacy float) -> 3, garbage -> -1.

    ``MAJOR * 100 + MINOR``. A third component (patch) is ignored - it is not part of
    the save contract. Never raises: this runs while drawing every slot row, and an
    exception on an unreadable version would take the panel down instead of greying
    out one row.
    """
    if value is None:
        return -1
    parts = str(value).strip().split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return -1
    if major < 0 or not (0 <= minor <= 99):
        # MINOR is capped at 99 because codes would otherwise collide: "0.100" and
        # "1.0" both map to 100. Bump MAJOR before MINOR would reach 100.
        return -1
    return major * 100 + minor


CURRENT_SAVE_CODE: int = version_code(VERSION)

# Alpha: only the current version loads. Bump together with VERSION on every release,
# then freeze at 100 (= "1.0") when 1.0 ships - see the policy note above.
MIN_SUPPORTED_SAVE_CODE: int = CURRENT_SAVE_CODE


def save_compatibility(version: str | float | int | None) -> SaveCompatEnum:
    """Can a save written under ``version`` be loaded by this build?

    The single place where that question is answered - used both by
    ``SaveManager.load`` (the decision) and by the save/load panel (drawing the row).
    """
    code = version_code(version)
    if code < 0:
        return SaveCompatEnum.unreadable
    if code > CURRENT_SAVE_CODE:
        return SaveCompatEnum.from_future
    if code < MIN_SUPPORTED_SAVE_CODE:
        return SaveCompatEnum.too_old
    return SaveCompatEnum.ok


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert a dataclass to a JSON-safe dict.

    ``dataclasses.asdict`` recursively processes nested dataclasses and
    containers.  This wrapper handles:
    - enum members → their ``.value`` string
    - ``tuple`` → ``list``
    """
    return cast("dict[str, Any]", _json_safe(asdict(obj, dict_factory=_enum_dict_factory)))


def _enum_dict_factory(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Dict factory that converts enums to their string values."""
    result: dict[str, Any] = {}
    for k, v in pairs:
        if isinstance(v, (ItemTypeEnum, AttitudeEnum)):
            result[k] = v.value
        else:
            result[k] = v
    return result


def _json_safe(obj: Any) -> Any:
    """Recursively convert remaining non-JSON-safe types."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def _enum_val(v: str | None, enum_cls: Any) -> Any:
    """Convert a string back to an enum member, or return a default."""
    if v is None:
        return next(iter(enum_cls))
    return enum_cls(v)


# ---------------------------------------------------------------------------
# Slot name sanitization
# ---------------------------------------------------------------------------

# Maximum length of a user-visible save-slot name. Kept short enough that a full-length
# name (left-aligned) does not collide with the right-aligned timestamp+playtime in a
# save/load slot row (see ui/panels/save_load.py _draw_slot_row and the panel width).
MAX_SLOT_NAME_LEN: int = 16


def sanitize_slot_name(name: str) -> str:
    """Normalize a user-supplied save-slot name so it can never corrupt the save file.

    Strips control / non-printable characters (newlines, tabs, carriage returns, etc.),
    trims surrounding whitespace and clamps the result to ``MAX_SLOT_NAME_LEN``
    characters. ``json.dumps`` (used by the backends) already escapes quotes and
    backslashes, so this is the *last line of defence*: it keeps the name safe no
    matter what the UI character filter allows, so widening that filter later can
    never break a save's JSON or the slot-list layout.
    """
    cleaned = "".join(ch for ch in str(name) if ch.isprintable())
    return cleaned.strip()[:MAX_SLOT_NAME_LEN]


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


@dataclass
class SaveMetadata:
    """Header stored with every save."""

    version: str = VERSION
    timestamp: float = field(default_factory=time.time)
    playtime: float = 0.0
    slot_name: str = ""
    # Set by ``migrate_save`` to the version the file was written under, when it
    # actually had to be brought forward; empty in a freshly written save. Purely
    # informational (diagnostics, UI) - it never gates loading. Itself an example of
    # "a field with a default needs no migration".
    migrated_from: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SaveMetadata:
        # ``str()`` and not ``float()``: files written before 0.4 store a float, and
        # 0.3 has to read back as "0.3" so ``version_code`` sees the same code the
        # game currently writes.
        return cls(
            version=str(data.get("version", VERSION)),
            timestamp=float(data.get("timestamp", 0.0)),
            playtime=float(data.get("playtime", 0.0)),
            slot_name=str(data.get("slot_name", "")),
            migrated_from=str(data.get("migrated_from", "")),
        )


# ---------------------------------------------------------------------------
# Item state
# ---------------------------------------------------------------------------


@dataclass
class ItemState:
    """Savable snapshot of an inventory item."""

    name: str = ""
    type: ItemTypeEnum = ItemTypeEnum.consumable
    count: int = 1
    value: int = 0
    weight: float = 0.0
    damage: int = 0
    cooldown_time: int = 0
    health_impact: int = 0

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ItemState:
        return cls(
            name=str(data.get("name", "")),
            type=_enum_val(data.get("type"), ItemTypeEnum),
            count=int(data.get("count", 1)),
            value=int(data.get("value", 0)),
            weight=float(data.get("weight", 0.0)),
            damage=int(data.get("damage", 0)),
            cooldown_time=int(data.get("cooldown_time", 0)),
            health_impact=int(data.get("health_impact", 0)),
        )


@dataclass
class GroundItemState:
    """Item lying on the ground (ItemState + position)."""

    name: str = ""
    type: ItemTypeEnum = ItemTypeEnum.consumable
    count: int = 1
    value: int = 0
    weight: float = 0.0
    damage: int = 0
    cooldown_time: int = 0
    health_impact: int = 0
    pos_x: float = 0.0
    pos_y: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GroundItemState:
        return cls(
            name=str(data.get("name", "")),
            type=_enum_val(data.get("type"), ItemTypeEnum),
            count=int(data.get("count", 1)),
            value=int(data.get("value", 0)),
            weight=float(data.get("weight", 0.0)),
            damage=int(data.get("damage", 0)),
            cooldown_time=int(data.get("cooldown_time", 0)),
            health_impact=int(data.get("health_impact", 0)),
            pos_x=float(data.get("pos_x", 0.0)),
            pos_y=float(data.get("pos_y", 0.0)),
        )


# ---------------------------------------------------------------------------
# Entity states
# ---------------------------------------------------------------------------


@dataclass
class PlayerState:
    """Snapshot of the player character."""

    map_name: str = ""
    entry_point: str = ""
    pos_x: float = 0.0
    pos_y: float = 0.0
    health: int = 100
    max_health: int = 100
    money: int = 0
    # Quest-granted stats have to persist, or the reward evaporates on load.
    # `damage` rides along for the same reason (D11 maps the SSiS `hp` bonus onto
    # it). Defaults keep saves written before Q-05 loading fine.
    damage: int = 10
    max_items: int = MAX_HOTBAR_ITEMS
    inventory: list[ItemState] = field(default_factory=list)
    selected_weapon: str | None = None
    selected_item_idx: int = -1
    is_flying: bool = False
    is_jumping: bool = False
    is_dead: bool = False

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlayerState:
        return cls(
            map_name=str(data.get("map_name", "")),
            entry_point=str(data.get("entry_point", "")),
            pos_x=float(data.get("pos_x", 0.0)),
            pos_y=float(data.get("pos_y", 0.0)),
            health=int(data.get("health", 100)),
            max_health=int(data.get("max_health", 100)),
            money=int(data.get("money", 0)),
            damage=int(data.get("damage", 10)),
            max_items=int(data.get("max_items", MAX_HOTBAR_ITEMS)),
            inventory=[ItemState.from_dict(i) for i in data.get("inventory", [])],
            selected_weapon=data.get("selected_weapon"),
            selected_item_idx=int(data.get("selected_item_idx", -1)),
            is_flying=bool(data.get("is_flying", False)),
            is_jumping=bool(data.get("is_jumping", False)),
            is_dead=bool(data.get("is_dead", False)),
        )


@dataclass
class NPCDialogState:
    """Snapshot of a single NPC's dialog graph state.

    Maps to the live NPC fields as follows:
    - ``current_node_key``   -> ``NPC.dialog.key`` (cursor into the graph)
    - ``dialog_start_node_key`` -> ``NPC.dialog_start_node.key`` (next conversation start)
    - ``selected_options``   -> ``NPC.selected_options_dict``
    - ``visited_nodes``      -> ``DialogNode.visited`` flags on the rebuilt graph
    - ``sentiment``          -> ``NPC.sentiment``
    - ``known_disposition``  -> ``NPC.known_disposition``
    """

    current_node_key: str = ""
    dialog_start_node_key: str = ""
    selected_options: dict[str, bool] = field(default_factory=dict)
    visited_nodes: dict[str, bool] = field(default_factory=dict)
    sentiment: int = 50
    known_disposition: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NPCDialogState:
        return cls(
            current_node_key=str(data.get("current_node_key", "")),
            dialog_start_node_key=str(data.get("dialog_start_node_key", "")),
            selected_options={str(k): bool(v) for k, v in data.get("selected_options", {}).items()},
            visited_nodes={str(k): bool(v) for k, v in data.get("visited_nodes", {}).items()},
            sentiment=int(data.get("sentiment", 50)),
            known_disposition={str(k): int(v) for k, v in data.get("known_disposition", {}).items()},
        )


@dataclass
class NPCState:
    """Snapshot of a single NPC's mutable state.

    ``name`` is the TMX object name (unique per map); ``config_key`` is the
    character's key in ``config.json`` — the same key dialog and quest
    conditions use in ``visited("BARMAN_ABSINTHRAYNER", "012")``. Both are kept
    because a saved map that has not been re-entered yet has no live NPC objects
    to ask, and a condition can only look it up by ``config_key``.

    ``config_key`` defaults to ``""`` so saves written before it existed still
    load (those NPCs simply resolve once their map is re-entered).
    """

    name: str = ""
    config_key: str = ""
    attitude: AttitudeEnum = AttitudeEnum.friendly
    pos_x: float = 0.0
    pos_y: float = 0.0
    health: int = 100
    money: int = 0
    is_dead: bool = False
    inventory: list[ItemState] = field(default_factory=list)
    dialog_state: NPCDialogState | None = None
    #: Per-instance state kept outside the config model - see `npc_runtime`.
    #: Defaults to a blank runtime so saves written before it existed still load.
    runtime: NpcRuntime = field(default_factory=NpcRuntime)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NPCState:
        dialog_state_raw = data.get("dialog_state")
        return cls(
            name=str(data.get("name", "")),
            config_key=str(data.get("config_key", "")),
            attitude=_enum_val(data.get("attitude"), AttitudeEnum),
            pos_x=float(data.get("pos_x", 0.0)),
            pos_y=float(data.get("pos_y", 0.0)),
            health=int(data.get("health", 100)),
            money=int(data.get("money", 0)),
            is_dead=bool(data.get("is_dead", False)),
            inventory=[ItemState.from_dict(i) for i in data.get("inventory", [])],
            dialog_state=NPCDialogState.from_dict(dialog_state_raw) if dialog_state_raw else None,
            runtime=NpcRuntime.from_dict(data.get("runtime")),
        )


@dataclass
class ChestState:
    """Snapshot of a chest's mutable state."""

    name: str = ""
    is_closed: bool = True
    items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChestState:
        return cls(
            name=str(data.get("name", "")),
            is_closed=bool(data.get("is_closed", True)),
            items=list(data.get("items", [])),
        )


# ---------------------------------------------------------------------------
# Game clock
# ---------------------------------------------------------------------------


@dataclass
class GameClockState:
    """Snapshot of the in-game day/night clock."""

    day: int = 1
    hour: int = 9
    minute: int = 0
    time_elapsed: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameClockState:
        return cls(
            day=int(data.get("day", 1)),
            hour=int(data.get("hour", 9)),
            minute=int(data.get("minute", 0)),
            time_elapsed=float(data.get("time_elapsed", 0.0)),
        )


# ---------------------------------------------------------------------------
# Map state
# ---------------------------------------------------------------------------


@dataclass
class MapState:
    """Snapshot of everything mutable on a single map."""

    name: str = ""
    chests: dict[str, ChestState] = field(default_factory=dict)
    ground_items: list[GroundItemState] = field(default_factory=list)
    npc_states: dict[str, NPCState] = field(default_factory=dict)
    destroyed_walls: list[tuple[int, int]] = field(default_factory=list)
    # A maze level is not stored tile by tile - it is regenerated from this seed.
    # Everything random about it (grid, decors, chest and monster placement, which
    # monster model each spawn gets, chest loot) is drawn from a generator seeded
    # with it, so the level comes back identical and the state below - who is dead,
    # who is hurt, which chest is open - lands on the right entities.
    # ``None`` means this map is an ordinary TMX map.
    maze_seed: int | None = None
    maze_level: int | None = None
    # Where a level-1 maze exit leads. Not derivable after a load: levels 2+ compute
    # it from the level number, but level 1 returns to whichever overworld map the
    # player came in from.
    maze_return_map: str = ""
    maze_return_entry_point: str = ""
    dead_monsters: list[str] = field(default_factory=list)
    # E03: fog of war. The maze level itself is still regenerated from the seed -
    # this is the first maze data that is really remembered, because "which
    # corridors the player has already walked" cannot be derived from anything.
    # One bit per map tile, base64-encoded (78x60 tiles = 780 B for the biggest
    # level). ``fog_w``/``fog_h`` are the grid it was recorded on: a mismatch
    # means the level was generated differently, and the fog is dropped rather
    # than smeared over the wrong tiles.
    # A field with a default, so an older save loads with an empty fog and needs
    # NO migration and NO version bump (policy in B02 - and before 1.0 a bump
    # would refuse every existing save instead).
    fog_discovered: str = ""
    fog_w: int = 0
    fog_h: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = _to_dict(self)
        d["destroyed_walls"] = [list(w) for w in self.destroyed_walls]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MapState:
        raw_npc = data.get("npc_states", {})
        return cls(
            name=str(data.get("name", "")),
            chests={k: ChestState.from_dict(v) for k, v in data.get("chests", {}).items()},
            ground_items=[GroundItemState.from_dict(i) for i in data.get("ground_items", [])],
            npc_states={k: NPCState.from_dict(v) for k, v in raw_npc.items()},
            destroyed_walls=[tuple(w) for w in data.get("destroyed_walls", [])],
            maze_seed=int(data["maze_seed"]) if data.get("maze_seed") is not None else None,
            maze_level=int(data["maze_level"]) if data.get("maze_level") is not None else None,
            maze_return_map=str(data.get("maze_return_map", "")),
            maze_return_entry_point=str(data.get("maze_return_entry_point", "")),
            dead_monsters=list(data.get("dead_monsters", [])),
            fog_discovered=str(data.get("fog_discovered", "")),
            fog_w=int(data.get("fog_w", 0) or 0),
            fog_h=int(data.get("fog_h", 0) or 0),
        )


# ---------------------------------------------------------------------------
# Save aggregate
# ---------------------------------------------------------------------------


@dataclass
class SaveGame:
    """Top-level save — everything needed to restore game state."""

    metadata: SaveMetadata = field(default_factory=SaveMetadata)
    player: PlayerState = field(default_factory=PlayerState)
    clock: GameClockState = field(default_factory=GameClockState)
    maps: dict[str, MapState] = field(default_factory=dict)
    # Quest progress (decision D13): ``{quest_key: {"done": bool}}``, the
    # serialized form of ``quest.entities.QuestState``. It lives here rather than
    # in config.json because config.json is a generated artifact — `just
    # import-quests` rewrites it, and progress must survive that. Stored flat
    # (not as a nested QuestState) so the save file stays readable.
    quests: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Identity of the playthrough. Everything the world re-rolls on its own (a
    # merchant's stock at dawn, what it will pay extra for) is derived from this
    # plus the day, so the answer for a given day is fixed and reloading in front
    # of a stall cannot re-roll it - see world_rng.py. Saves written before this
    # existed default to 0, which is a poorer seed but still a *stable* one; the
    # alternative, rolling a fresh seed on every load, is the hole itself.
    world_seed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return _to_dict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SaveGame:
        raw_quests = data.get("quests")
        return cls(
            metadata=SaveMetadata.from_dict(data.get("metadata", {})),
            player=PlayerState.from_dict(data.get("player", {})),
            clock=GameClockState.from_dict(data.get("clock", {})),
            maps={k: MapState.from_dict(v) for k, v in data.get("maps", {}).items()},
            quests=raw_quests if isinstance(raw_quests, dict) else {},
            world_seed=int(data.get("world_seed", 0)),
        )


# ---------------------------------------------------------------------------
# Slot types
# ---------------------------------------------------------------------------


@dataclass
class SaveSlot:
    """A single save slot — may be occupied or empty."""

    slot_id: str = ""
    save_data: SaveGame | None = None
    is_occupied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "is_occupied": self.is_occupied,
            "save_data": self.save_data.to_dict() if self.save_data else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SaveSlot:
        save_data_raw = data.get("save_data")
        if save_data_raw:
            # Migrate the RAW dict, before anything deserializes it. ``SaveGame.from_dict``
            # is tolerant (``data.get(key, default)``), so a renamed key would silently
            # land on its default and there would be nothing left for a migration to fix.
            # This is also the single point both backends *and* ``list_slots()`` go
            # through - hence ``migrate_save`` must stay cheap and silent.
            save_data_raw = migrate_save(save_data_raw)
        return cls(
            slot_id=str(data.get("slot_id", "")),
            is_occupied=bool(data.get("is_occupied", False)),
            save_data=SaveGame.from_dict(save_data_raw) if save_data_raw else None,
        )


@dataclass
class SaveSlotInfo:
    """Lightweight slot preview for the UI (no full save data)."""

    slot_id: str = ""
    is_occupied: bool = False
    metadata: SaveMetadata | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "is_occupied": self.is_occupied,
            "metadata": self.metadata.to_dict() if self.metadata else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SaveSlotInfo:
        meta_raw = data.get("metadata")
        return cls(
            slot_id=str(data.get("slot_id", "")),
            is_occupied=bool(data.get("is_occupied", False)),
            metadata=SaveMetadata.from_dict(meta_raw) if meta_raw else None,
        )


# ---------------------------------------------------------------------------
# Versioning / migration
# ---------------------------------------------------------------------------


MigrationFn = Callable[[dict[str, Any]], dict[str, Any]]

# Deliberately EMPTY before 1.0: older saves are refused rather than migrated (see the
# policy note at the top of this module). The mechanism is exercised by the unit tests,
# which register their own migrations - a placeholder migration living here would be
# exactly the dead code this module used to carry.
_MIGRATIONS: list[tuple[int, MigrationFn]] = []


def _register_migration(version: str) -> Callable[[MigrationFn], MigrationFn]:
    """Register a migration keyed by the version in which THE FORMAT CHANGED.

    ``@_register_migration("1.4")`` means "run this on any save written before 1.4, to
    turn it into the 1.4 layout". A release that does not change the format needs no
    entry at all: the chain comes out empty, the save passes and is simply re-stamped.
    That is what makes one shared game/save version number affordable.
    """
    code = version_code(version)

    def wrapper(func: MigrationFn) -> MigrationFn:
        _MIGRATIONS.append((code, func))
        return func

    return wrapper


def migrate_save(data: dict[str, Any]) -> dict[str, Any]:
    """Bring a raw save dict forward to the current version, if that is possible.

    Never raises and never logs: it runs for all 10 slots every time the save/load
    panel opens (through ``SaveSlot.from_dict``).

    A save that cannot be brought forward is returned **untouched**, with its original
    ``metadata.version`` - the stamp is the success signal, and the single decision
    point stays ``save_compatibility`` in ``SaveManager.load``. There is no second
    "did it work" flag to keep in sync.
    """
    meta = data.get("metadata")
    raw_version = meta.get("version", VERSION) if isinstance(meta, dict) else VERSION
    if save_compatibility(raw_version) is not SaveCompatEnum.ok:
        return data

    code = version_code(raw_version)
    for target_code, func in sorted(_MIGRATIONS, key=lambda pair: pair[0]):
        # ``key=`` is not cosmetic: sorting bare tuples compares the functions
        # whenever two migrations share a code, and functions are not orderable.
        if code < target_code <= CURRENT_SAVE_CODE:
            data = func(data)

    if code != CURRENT_SAVE_CODE:
        migrated_meta = cast("dict[str, Any]", data.setdefault("metadata", {}))
        migrated_meta["migrated_from"] = str(raw_version)
        migrated_meta["version"] = VERSION

    return data
