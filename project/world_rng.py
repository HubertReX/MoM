"""Seeded randomness for anything the world re-rolls on its own.

Every random decision a day turn makes - which goods a merchant puts out at
dawn, which of them it will pay extra for - has to be a *function* of the save,
the day and whose decision it is. Not a draw from the global generator.

The reason is reload-scumming. A merchant whose stock is rolled from
`random.random()` hands the player a slot machine: save in front of the stall,
sleep, look, reload, look again, until the gems they need show up. Derive the
roll from `(world_seed, day, name)` instead and the answer for a given day is
fixed - reloading yields the same stall, so there is nothing to farm.

The same property buys the day-ahead demand preview for free: ask for `day + 1`
and you get tomorrow's answer today, without storing anything.

**Do not use the builtin `hash()` here.** Python salts string hashing per
process (PYTHONHASHSEED), so `hash(("JOHNY", 3))` differs between launches -
the roll would be stable within one session and re-rollable by restarting the
game, which is the exact hole this module exists to close. `zlib.crc32` over
UTF-8 bytes is stable across processes, machines and Python versions.
"""
from __future__ import annotations

import random
from zlib import crc32


def stable_hash(*parts: object) -> int:
    """A hash that survives a process restart, unlike the builtin `hash()`."""
    joined = "\x1f".join(str(part) for part in parts)
    return crc32(joined.encode("utf-8"))


def day_rng(world_seed: int, day: int, name: str = "") -> random.Random:
    """Generator for one actor's decisions on one day.

    `name` separates actors that roll on the same day, so two merchants do not
    put out identical stock; leave it empty for a roll that belongs to the world
    rather than to somebody in it.
    """
    return random.Random(stable_hash(world_seed, day, name))


def new_world_seed() -> int:
    """Roll the seed for a fresh game. Stored in the save from then on."""
    return random.randrange(2 ** 31)
