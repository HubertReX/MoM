"""Adapter connecting the *bark* condition scope to live game data (H01/D1).

Same shape as ``dialog/context_adapter.py``, and deliberately so: the condition
engine (``dialog.conditions``) never imports the game, and every predicate
crosses into it through exactly one method here.

What makes a bark its own scope rather than a dialog one: the speaker is known
(so ``sentiment`` and one-argument ``visited()`` work), but nobody is standing in
a conversation, and the three facts that decide whether a one-liner fits are
about the world - what time it is, what the speaker is doing right now, which step
of its day that is, and which map it is on. Those are `time_of_day`, `activity`,
`at` and `on_map`.

Everything is read *live* on each call. A bark condition is checked at the moment
the hero walks up, and the clock, the routine step and the map have all moved
since the NPC was built.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dialog.conditions import BarkConditionContext
from dialog.context_adapter import count_items, find_visited_node, node_visited, scene_quest_done

if TYPE_CHECKING:
    from characters import NPC, Player


def speaker_activity(npc: Any) -> str:
    """The speaker's current routine step (``sleep``/``wander``/…), or ``""``.

    ``""`` for a character with no routine at all, and for one whose routine has
    not been evaluated yet. It is not an error: such a character simply never
    matches an ``activity(...)`` bark, exactly like the empty destination cell in
    ``routines.toml`` degrades to "stay where you are" rather than to an
    exception.
    """
    slot = getattr(npc, "_schedule_slot", None)
    return str(getattr(slot, "activity", "") or "") if slot is not None else ""


def speaker_slot_at(npc: Any) -> str:
    """Where the speaker's current routine step points, or ``""``.

    The raw ``at`` field of the step (``type:work``, ``location:Tavern``,
    ``route:Patrol``) - the same string the author wrote in ``routines.toml``,
    not a resolved position. That is the whole point: ``activity`` says *what*
    the character is doing (``stand`` covers the barman, the smith and Bart),
    while this says *which step of the day* it is.

    ``""`` for a character with no routine, exactly like `speaker_activity`.
    """
    slot = getattr(npc, "_schedule_slot", None)
    return str(getattr(slot, "at", "") or "") if slot is not None else ""


def speaker_map(npc: Any) -> str:
    """Which map the speaker is on - the *logical* one the schedule drives.

    ``runtime.logical_map`` rather than the loaded map, because those two are the
    same only by accident: a bark is only ever spoken by a materialised NPC, but
    asking the honest field keeps the predicate meaning one thing.
    """
    logical = str(getattr(getattr(npc, "runtime", None), "logical_map", "") or "")
    return logical or str(getattr(npc, "current_map", "") or "")


class NPCBarkContext(BarkConditionContext):
    """ConditionContext for one NPC's ambient one-liners.

    ``visited()`` / ``has_item()`` / ``item_count()`` / ``quest_done()`` /
    ``sentiment`` behave exactly as in a conversation (same helpers, same
    semantics), so a line moved from a dialog option into a bark keeps its
    meaning. The three world predicates are the new part.
    """

    __slots__ = ("npc", "player")

    def __init__(self, npc: "NPC", player: "Player") -> None:
        self.npc = npc
        self.player = player

    # -- shared with the dialog scope ---------------------------------------

    def visited(self, node_key: str, npc: str | None = None) -> bool:
        if npc is None or npc == self.npc.config_key:
            return node_visited(self.npc, node_key)
        return find_visited_node(self.player.scene, npc, node_key)

    def has_item(self, item_key: str) -> bool:
        return any(item.name == item_key for item in self.player.items)

    def item_count(self, item_key: str) -> int:
        return count_items(self.player, item_key)

    def quest_done(self, quest_key: str) -> bool:
        return scene_quest_done(self.player.scene, quest_key)

    @property
    def sentiment(self) -> int:
        return self.npc.sentiment

    # -- bark-only ----------------------------------------------------------

    def time_of_day(self, phase: str) -> bool:
        """Is the world clock in ``phase``? Boundaries come from ``settings.DAY_PHASES``.

        Imported here rather than at module scope so this module stays importable
        without ``scene`` (the import tests and the condition unit tests do that).
        """
        from scene.world_clock import day_phase

        scene = self.player.scene
        return day_phase(scene.hour + scene.minute / 60) == phase

    def activity(self, name: str) -> bool:
        return speaker_activity(self.npc) == name

    def at(self, spec: str) -> bool:
        return speaker_slot_at(self.npc) == spec

    def on_map(self, map_key: str) -> bool:
        return speaker_map(self.npc) == map_key
