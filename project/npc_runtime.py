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
        )
