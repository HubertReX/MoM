"""Daily routines: what an NPC should be doing at a given hour, and where.

This module is a *provider of goals*, not a second controller. It answers "which
slot is active" and "what world position does that slot point at", and stops
there. Actually walking is left to the movement code that already exists
(`NPC.find_path` / `NPC.follow_waypoints`). Two systems writing `npc.vel` is how
you get an NPC vibrating in a doorway.

Everything here is a pure function of its arguments - no pygame, no scene, no
globals - which is why the whole thing is unit-testable without a display.

The three-way split the routines rest on:

- **Tiled** says *where*: named objects on the `places` layer, nothing else on
  them. No `tag`, no `owner`.
- **characters.csv** says *whose is which*: the `home`/`work`/`social`/`hobby`
  columns name a place per character.
- **routines.toml** says *when and what*: the rhythm, shared by many characters.

The reason the role of a place lives on the character and not on the map object:
the same tavern is the barman's `work` and everybody else's `social`. A property
on the map object can only give one of those two answers. Ownership of a place is
a *relation*, so it is stored on the side that can hold several of them.

Incomplete data is a normal state, not an error. A character with an empty `work`
cell simply has no destination for that step, `resolve_at` returns ``None``, and
the caller leaves it where it stands. The village can be mapped one place at a
time.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - web build
    import tomli as tomllib  # type: ignore[no-redef]

from world_rng import stable_hash

MINUTES_PER_DAY = 24 * 60

#: Destination types a character can own, one each. Closed on purpose: a routine
#: written against `type:work` has to mean the same thing for every character.
DESTINATION_TYPES = ("home", "work", "social", "hobby")

#: What a slot can ask a character to do. Anything else in the file is a typo.
ACTIVITIES = ("sleep", "stand", "wander", "patrol", "idle")


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Slot:
    """One step of a routine: from this time, be *there*, doing *that*."""

    from_minutes: int
    at: str
    activity: str


@dataclass(frozen=True)
class Routine:
    key: str
    #: Sorted by `from_minutes`. Order in the file is irrelevant by design, so a
    #: step can be inserted in the middle without disturbing anything.
    slots: tuple[Slot, ...]


@dataclass(frozen=True)
class Defaults:
    wander_radius: int = 3
    slot_jitter_minutes: int = 20


@dataclass(frozen=True)
class Routines:
    """Everything routines.toml holds, parsed."""

    defaults: Defaults
    routines: Mapping[str, Routine]
    #: Tiled spawn-point name -> routine key.
    assign: Mapping[str, str]

    def for_character(self, spawn_name: str) -> Routine | None:
        key = self.assign.get(spawn_name, "")
        return self.routines.get(key) if key else None


@dataclass(frozen=True)
class Destination:
    """Where a slot points. `kind` decides how the caller should use it.

    - ``"place"``: a single named point; walk to it and stay.
    - ``"route"``: a named polyline from the `waypoints` layer; walk it in a loop.
    """

    kind: str
    name: str


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_time(text: str) -> int:
    """``"06:30"`` -> minutes since midnight."""
    hours, _, minutes = str(text).partition(":")
    value = int(hours) * 60 + int(minutes or 0)
    if not 0 <= value < MINUTES_PER_DAY:
        raise ValueError(f"time out of range: {text!r}")
    return value


def parse_routines(data: dict[str, Any], *, warn: Any = None) -> Routines:
    """Build the parsed form from an already-loaded TOML document.

    Split out from `load_routines` so tests can feed a literal dict, and so a
    malformed step is reported rather than silently dropped.
    """
    raw_defaults = data.get("defaults") or {}
    defaults = Defaults(
        wander_radius=int(raw_defaults.get("wander_radius", 3)),
        slot_jitter_minutes=int(raw_defaults.get("slot_jitter_minutes", 20)),
    )

    routines: dict[str, Routine] = {}
    for key, body in (data.get("routine") or {}).items():
        slots: list[Slot] = []
        for index, raw in enumerate(body.get("slot") or []):
            try:
                slot = Slot(
                    from_minutes=parse_time(raw["from"]),
                    at=str(raw["at"]),
                    activity=str(raw.get("activity", "stand")),
                )
            except (KeyError, ValueError) as exc:
                _warn(warn, f"routine '{key}' slot #{index}: {exc}; skipped")
                continue
            if slot.activity not in ACTIVITIES:
                _warn(warn, f"routine '{key}' slot #{index}: unknown activity '{slot.activity}'; skipped")
                continue
            slots.append(slot)
        # Sorted here, once, so every consumer can rely on it. The file's own
        # order carries no meaning - that is what makes reordering it safe.
        routines[key] = Routine(key=key, slots=tuple(sorted(slots, key=lambda s: s.from_minutes)))

    assign = {str(k): str(v) for k, v in (data.get("assign") or {}).items()}
    for spawn_name, routine_key in assign.items():
        if routine_key not in routines:
            _warn(warn, f"[assign] '{spawn_name}' points at unknown routine '{routine_key}'")

    return Routines(defaults=defaults, routines=routines, assign=assign)


def load_routines(path: str | Path, *, warn: Any = None) -> Routines:
    """Read routines.toml. A missing or broken file yields empty routines.

    Empty is a working state: no character gets a routine and everybody keeps the
    behaviour they had before this system existed. Content problems must never be
    able to stop the game from starting.
    """
    try:
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        _warn(warn, f"routines file not found: {path}")
        return Routines(defaults=Defaults(), routines={}, assign={})
    except tomllib.TOMLDecodeError as exc:
        _warn(warn, f"routines file {path} is not valid TOML: {exc}")
        return Routines(defaults=Defaults(), routines={}, assign={})
    return parse_routines(data, warn=warn)


def _warn(warn: Any, message: str) -> None:
    if warn is not None:
        warn(f"[routines] {message}")


# ---------------------------------------------------------------------------
# Which slot is active
# ---------------------------------------------------------------------------


def slot_jitter(name: str, max_minutes: int) -> int:
    """A per-character offset in ``[-max, +max]``, stable across runs.

    Without it the whole village turns on its heel at exactly 08:00, which reads
    as clockwork rather than as life - and every route gets recomputed on the same
    frame. Derived from the name so it survives a save/load; see world_rng for why
    the builtin `hash()` will not do.
    """
    if max_minutes <= 0:
        return 0
    span = 2 * max_minutes + 1
    return stable_hash(name) % span - max_minutes


def current_slot(routine: Routine, minutes_of_day: int, jitter: int = 0) -> Slot | None:
    """The slot in force at `minutes_of_day`, or ``None`` for an empty routine.

    Wrapping past midnight falls out of the rule "the last slot that has started":
    when nothing has started yet today, the one in force is the last of the
    previous day. That is how the guard's 02:00 step stays active until 06:00 and
    the evening step covers 23:00.

    `jitter` shifts this character's boundaries; shifting the query by the same
    amount in the other direction is the same thing and keeps the slots shared.
    """
    if not routine.slots:
        return None

    minutes = (minutes_of_day - jitter) % MINUTES_PER_DAY
    active = routine.slots[-1]  # yesterday's last, until today's first starts
    for slot in routine.slots:
        if slot.from_minutes <= minutes:
            active = slot
        else:
            break
    return active


# ---------------------------------------------------------------------------
# Where the slot points
# ---------------------------------------------------------------------------


def resolve_at(at: str, destinations: Mapping[str, str], known_places: Iterable[str],
               known_routes: Iterable[str], *, warn: Any = None) -> Destination | None:
    """Turn a slot's `at` into a concrete named target, or ``None``.

    ``None`` means "no destination for this character right now" and the caller is
    expected to leave the character where it is. Every way of failing lands here:
    an empty CSV cell, a place that Tiled does not have (yet), a typo in the
    prefix. None of them may raise - a half-mapped village has to be playable.
    """
    prefix, _, value = at.partition(":")
    if not value:
        _warn(warn, f"malformed `at` (expected 'type:x', 'location:x' or 'route:x'): {at!r}")
        return None

    if prefix == "type":
        if value not in DESTINATION_TYPES:
            _warn(warn, f"unknown destination type '{value}' (have: {', '.join(DESTINATION_TYPES)})")
            return None
        place = (destinations.get(value) or "").strip()
        if not place:
            return None  # empty CSV cell - normal, character stays put
        if place not in known_places:
            _warn(warn, f"'{value}' points at place '{place}', which the map does not define")
            return None
        return Destination("place", place)

    if prefix == "location":
        if value not in known_places:
            _warn(warn, f"location '{value}' is not on the map's `places` layer")
            return None
        return Destination("place", value)

    if prefix == "route":
        if value not in known_routes:
            _warn(warn, f"route '{value}' is not on the map's `waypoints` layer")
            return None
        return Destination("route", value)

    _warn(warn, f"unknown `at` prefix '{prefix}' in {at!r}")
    return None


def destinations_of(model: Any) -> dict[str, str]:
    """Pull the four destination columns off a character config model.

    Works for both mirrors of the model (dataclass on web, pydantic on desktop)
    because it only ever reads attributes.
    """
    return {name: str(getattr(model, name, "") or "") for name in DESTINATION_TYPES}
