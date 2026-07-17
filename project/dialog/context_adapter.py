"""Adapter connecting the dialog condition mini-DSL to live game data.

The DSL engine (``dialog.conditions``) is intentionally isolated from the game.
This module provides the bridge: a per-NPC :class:`DialogConditionContext` backed
by that NPC's conversation state, the hero's inventory, and shared node-visit
state, plus :func:`find_visited_node` — the world-level lookup quests need too
(see ``quest/context_adapter.py``).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dialog.conditions import DialogConditionContext

if TYPE_CHECKING:
    from characters import NPC, Player


def node_visited(npc: Any, node_key: str) -> bool:
    """Was ``node_key`` visited in this (live) NPC's dialog graph?"""
    nodes = getattr(npc, "dialog_nodes", None)
    if nodes and node_key in nodes:
        return bool(nodes[node_key].visited)
    return False


def find_visited_node(scene: Any, npc_key: str, node_key: str) -> bool:
    """Was ``node_key`` visited in ``npc_key``'s dialog — wherever that NPC lives?

    A quest may ask about a conversation that happened on a map the player is no
    longer standing on, so this deliberately looks past the current map. There
    are three places the answer can hide, in order of freshness:

    1. NPCs on the current map (``scene.loaded_NPCs``);
    2. NPCs on maps entered earlier this session, whose objects are still cached
       in ``scene.loaded_maps``;
    3. maps restored from a save but not re-entered since, which have no NPC
       objects at all — only the state held in ``scene.pending_map_states``.

    Falling through all three means the player has never been able to meet that
    NPC, so ``False`` is the truthful answer rather than a silent failure.
    """
    for other in getattr(scene, "loaded_NPCs", {}).values():
        if getattr(other, "config_key", None) == npc_key:
            return node_visited(other, node_key)

    for cached in (getattr(scene, "loaded_maps", None) or {}).values():
        for other in cached.get("NPCs", None) or []:
            if getattr(other, "config_key", None) == npc_key:
                return node_visited(other, node_key)

    for map_state in (getattr(scene, "pending_map_states", None) or {}).values():
        for npc_state in map_state.npc_states.values():
            if npc_state.config_key == npc_key:
                dialog_state = npc_state.dialog_state
                return bool(dialog_state and dialog_state.visited_nodes.get(node_key, False))

    return False


def count_items(player: Any, item_key: str) -> int:
    """How many of ``item_key`` the hero holds, counting stack sizes."""
    return sum(
        int(getattr(item.model, "count", 1))
        for item in player.items
        if item.name == item_key
    )


def scene_quest_done(scene: Any, quest_key: str) -> bool:
    """Is ``quest_key`` complete, per the scene's quest state?

    The quest state is attached to the Scene by the quest runtime (Q-07). Until
    that lands there is nothing to ask, and no quest is done.
    """
    state = getattr(scene, "quest_state", None)
    if state is None:
        return False
    return bool(state.is_done(quest_key))


class NPCConditionContext(DialogConditionContext):
    """ConditionContext for a single conversation.

    ``selected()`` reads the current NPC's ``selected_options_dict``.
    ``visited()`` checks the current NPC by default, or looks the world over when
    a second argument names another NPC.
    ``has_item()`` / ``item_count()`` ask the player hero.
    ``sentiment`` returns the current NPC's sentiment.
    """

    __slots__ = ("npc", "player")

    def __init__(self, npc: "NPC", player: "Player") -> None:
        self.npc = npc
        self.player = player

    def selected(self, option_key: str) -> bool:
        return self.npc.selected_options_dict.get(option_key, False)

    def visited(self, node_key: str, npc: str | None = None) -> bool:
        if npc is None or npc == self.npc.config_key:
            return node_visited(self.npc, node_key)
        # cross-NPC query by config_key (UPPER_SNAKE, matches dialog graph key)
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
