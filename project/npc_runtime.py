"""Per-instance mutable state for a character - the half that is *not* config.

`Character` (config_model) describes what a character *is*: sprite, race, base
health, starting money, walking speed. Those come from `characters.csv`, are the
same for every instance of that character, and never change while the game runs.

This module holds the other half: what happens to *this one* character during
play. It lives here rather than in `Character` for two reasons.

**The config model is mirrored.** It is defined twice - `config_model/config.py`
(dataclass, used on web) and `config_model/config_pydantic.py` (pydantic, used on
desktop), selected in `game.py`. Every field added to one has to be added to the
other, and forgetting produces a crash that only happens on web, with a traceback
only visible in the browser console. Runtime state has no business paying that
tax, so it is defined once, here.

**Config is the pristine baseline.** `game.conf.characters[key]` is never written
to, which makes it a free source of "what was this originally" - the merchant's
purse ceiling for the daily regeneration is just the `money` its CSV row declares.
Keeping runtime values out of it is what preserves that.

Note that `health` and `money` are *not* here: they live on the character's own
deep copy of `Character` (see `NPC.__init__`), which is the pattern items and
chests already use (`Scene.create_item`, chest spawning). Splitting them out would
mean rewriting ~78 call sites across combat, UI and save/load for no behavioural
gain - the deep copy already gives every character its own values.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NpcRuntime:
    """Mutable per-instance state that is not part of the character's config."""

    #: Key of the daily routine this character follows, from `routines.toml`.
    #: Empty means "no routine" - the character keeps its legacy waypoint loop.
    routine_key: str = ""

    #: Item keys the character currently offers for sale. Merchants re-roll this
    #: at dawn; everyone else leaves it empty.
    stock: list[str] = field(default_factory=list)

    #: Which map the character is *logically* on, which the daily schedule drives
    #: and which need not be the map the player is looking at. Empty on a fresh
    #: object or an old save means "wherever it spawned" - the reconciler treats it
    #: as `origin_map`. This is the field that lets a routine walk an NPC from the
    #: village into the tavern (a separate Tiled map) and back.
    logical_map: str = ""

    #: Cross-map transit: while walking between two maps the character is on
    #: neither's active roster. `transit_to_map` is where it is headed (empty =
    #: not in transit) and `transit_arrive_min` is the absolute game-minute it
    #: arrives. The arrival time is fixed at the slot boundary, *not* when the
    #: sprite reaches the door - so the player leaving the source map mid-walk
    #: never loses track of when the character shows up on the far side.
    transit_to_map: str = ""
    transit_arrive_min: int = 0

    # No `to_dict`: this is nested inside `NPCState`, whose `_to_dict` runs
    # `dataclasses.asdict` recursively and picks these fields up on its own.

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> NpcRuntime:
        """Rebuild from a save file, tolerating saves written before this existed."""
        if not data:
            return cls()
        return cls(
            routine_key=str(data.get("routine_key", "")),
            stock=[str(item) for item in data.get("stock", [])],
            logical_map=str(data.get("logical_map", "")),
            transit_to_map=str(data.get("transit_to_map", "")),
            transit_arrive_min=int(data.get("transit_arrive_min", 0) or 0),
        )
