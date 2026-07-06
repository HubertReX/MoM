"""Adapter connecting the dialog condition mini-DSL to live game data.

The DSL engine (``dialog.conditions``) is intentionally isolated from the game.
This module provides the bridge: a per-NPC :class:`ConditionContext` backed by
that NPC's conversation state, the hero's inventory, and shared node-visit
state stored on the Scene.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from dialog.conditions import ConditionContext

if TYPE_CHECKING:
    from characters import NPC, Player


class NPCConditionContext(ConditionContext):
    """ConditionContext for a single conversation.

    ``selected()`` reads the current NPC's ``selected_options_dict``.
    ``visited()`` checks the current NPC by default, or another NPC's visited
    nodes when a second argument is given (quest-state sharing).
    ``has_item()`` asks the player hero.
    ``sentiment`` returns the current NPC's sentiment.
    """

    __slots__ = ("npc", "player")

    def __init__(self, npc: "NPC", player: "Player") -> None:
        self.npc = npc
        self.player = player

    def selected(self, option_key: str) -> bool:
        return self.npc.selected_options_dict.get(option_key, False)

    def visited(self, node_key: str, npc: str | None = None) -> bool:
        if npc is None or npc == self.npc.name:
            target = self.npc.dialog
            return target is not None and target.key == node_key
        # cross-NPC query: walk the Scene's loaded NPCs
        for other in self.player.scene.loaded_NPCs.values():
            if other.name == npc:
                return other.dialog is not None and other.dialog.key == node_key
        return False

    def has_item(self, item_key: str) -> bool:
        return any(item.model.name == item_key for item in self.player.items)

    @property
    def sentiment(self) -> int:
        return self.npc.sentiment
