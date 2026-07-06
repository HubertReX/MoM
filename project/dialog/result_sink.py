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

    def shift_sentiment(self, amount: int) -> None:
        """Shift the current NPC's sentiment toward the hero."""
        ...


def apply_result(result: NodeVisitResult, sink: ResultSink) -> None:
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
        sink.shift_sentiment(result.value)
    else:
        # unreachable unless a new category is added without a handler
        raise ValueError(f"unhandled NodeVisitResultCategory: {category!r}")


def visit_node(node: DialogNode, sink: ResultSink) -> bool:
    """Mark ``node`` visited and apply its side effect exactly once.

    Returns ``True`` when this call actually applied the result (first visit),
    ``False`` when the node was already visited.
    """
    if node.visited:
        return False
    node.visited = True
    if node.result is not None:
        apply_result(node.result, sink)
    return True


__all__ = [
    "ResultSink",
    "apply_result",
    "visit_node",
]
