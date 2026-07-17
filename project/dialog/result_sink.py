"""ResultSink adapter for dialog node side effects (decision D8).

The 7 categories of :class:`NodeVisitResult` are applied to live game systems
through a small :class:`ResultSink` Protocol.  The dialog engine itself stays
pure and game-agnostic; MoM supplies a concrete sink implementation.

This module is web-safe (no pygame, no Pydantic) and tested in isolation.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from dialog.entities import DialogNode, NodeVisitResult, NodeVisitResultCategory


@runtime_checkable
class ResultSink(Protocol):
    """Bridge from a dialog node's side effect to live game state."""

    def add_money(self, amount: int) -> None:
        """Give money to the hero."""
        ...

    def remove_money(self, amount: int) -> None:
        """Take money from the hero."""
        ...

    def add_items(self, item_keys: list[str]) -> None:
        """Add items to the hero's inventory."""
        ...

    def remove_items(self, item_keys: list[str]) -> None:
        """Remove items from the hero's inventory."""
        ...

    def restore_health(self, amount: int) -> None:
        """Heal the hero."""
        ...

    def lose_health(self, amount: int) -> None:
        """Damage the hero."""
        ...

    def shift_sentiment(self, amount: int, emote_key: str = "") -> None:
        """Shift the current NPC's sentiment toward the hero."""
        ...

    # --- quest rewards (Q-05) ------------------------------------------------
    # Dialogs never needed these; quest rewards do (decision D11, which remapped
    # the SSiS stats onto ones MoM actually has). They live on the shared
    # Protocol so a dialog node could grant them too, should the story want it.

    def raise_max_health(self, amount: int) -> None:
        """Raise the hero's maximum health."""
        ...

    def raise_damage(self, amount: int) -> None:
        """Raise the hero's damage."""
        ...

    def raise_max_items(self, amount: int) -> None:
        """Raise the number of item slots the hero can carry."""
        ...

    def shift_sentiment_of(self, npc_key: str, amount: int) -> None:
        """Shift a *named* NPC's sentiment, wherever that NPC currently is.

        The targeted twin of :meth:`shift_sentiment`. A quest is evaluated by the
        engine rather than during a conversation, so it has no current NPC and
        must say who it means.
        """
        ...


def apply_result(result: NodeVisitResult, sink: ResultSink, emote_key: str = "") -> None:
    """Dispatch ``result`` to ``sink`` based on its category.

    The numeric fields inside :class:`NodeVisitResult` are expected to be
    non-negative; the category determines the sign of the change.
    """
    category = result.category
    if category is NodeVisitResultCategory.MONEY_RECEIVED:
        sink.add_money(result.money)
    elif category is NodeVisitResultCategory.MONEY_RETURNED:
        sink.remove_money(result.money)
    elif category is NodeVisitResultCategory.ITEMS_RECEIVED:
        sink.add_items(result.items)
    elif category is NodeVisitResultCategory.ITEMS_RETURNED:
        sink.remove_items(result.items)
    elif category is NodeVisitResultCategory.HEALTH_RESTORED:
        sink.restore_health(result.health)
    elif category is NodeVisitResultCategory.HEALTH_LOST:
        sink.lose_health(result.health)
    elif category is NodeVisitResultCategory.SENTIMENT_SHIFT:
        sink.shift_sentiment(result.value, emote_key)
    else:
        # unreachable unless a new category is added without a handler
        raise ValueError(f"unhandled NodeVisitResultCategory: {category!r}")


def visit_node(node: DialogNode, sink: ResultSink, emote_key: str = "") -> bool:
    """Mark ``node`` visited and apply its side effect exactly once.

    Returns ``True`` when this call actually applied the result (first visit),
    ``False`` when the node was already visited.
    """
    if node.visited:
        return False
    node.visited = True
    if node.result is not None:
        apply_result(node.result, sink, emote_key)
    return True


__all__ = [
    "ResultSink",
    "apply_result",
    "visit_node",
]
