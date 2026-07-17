"""Adapter connecting the quest condition mini-DSL to live game data (Q-02).

The quest counterpart of ``dialog/context_adapter.py``. The difference that
drives the whole design: a dialog condition is evaluated *during a conversation*
and therefore has a current NPC, while a quest ``test`` is evaluated by the quest
engine and has none. So :class:`QuestConditionContext` implements only the
world-level half of the bridge (:class:`~dialog.conditions.ConditionContext`) —
``selected()`` and ``sentiment`` are not merely unimplemented here, they are
rejected at validation time by ``ConditionScope.quest``.

Deliberately not exported from ``quest/__init__.py``: that package is the pure,
game-free data model, and this module reaches into the live Scene.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dialog.conditions import ConditionContext
from dialog.context_adapter import count_items, find_visited_node, scene_quest_done

if TYPE_CHECKING:
    from scene import Scene


class QuestConditionContext(ConditionContext):
    """ConditionContext for evaluating a quest's ``test`` / ``progress``.

    Backed by the Scene rather than by any one NPC, because a quest asks about
    the world: conversations had anywhere, items held, quests finished.
    """

    __slots__ = ("scene",)

    def __init__(self, scene: "Scene") -> None:
        self.scene = scene

    def visited(self, node_key: str, npc: str | None = None) -> bool:
        if npc is None:
            # `ConditionScope.quest` forces the 2-arg form at validation time, so
            # this is unreachable from authored content. If it ever fires, some
            # caller validated with the wrong scope — say so instead of
            # answering False and letting a quest hang forever.
            raise ValueError(
                f"quest condition used visited({node_key!r}) without an NPC; "
                f"a quest has no current character (validate with ConditionScope.quest)"
            )
        return find_visited_node(self.scene, npc, node_key)

    def has_item(self, item_key: str) -> bool:
        return any(item.name == item_key for item in self.scene.player.items)

    def item_count(self, item_key: str) -> int:
        return count_items(self.scene.player, item_key)

    def quest_done(self, quest_key: str) -> bool:
        return scene_quest_done(self.scene, quest_key)


__all__ = ["QuestConditionContext"]
