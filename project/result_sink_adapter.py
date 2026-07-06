"""Concrete ResultSink adapter backed by live MoM game objects.

This is the game-side half of decision D8: the dialog engine defines the
``ResultSink`` Protocol, and this module implements it using the hero's
inventory, health, money and the current NPC's sentiment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dialog.result_sink import ResultSink

if TYPE_CHECKING:
    from characters import NPC, Player


class GameResultSink(ResultSink):
    """Apply dialog node effects to the hero and the current NPC."""

    __slots__ = ("player", "npc")

    def __init__(self, player: "Player", npc: "NPC") -> None:
        self.player: "Player" = player
        self.npc: "NPC" = npc

    def add_money(self, amount: int) -> None:
        self.player.model.money += max(0, amount)

    def remove_money(self, amount: int) -> None:
        self.player.model.money = max(0, self.player.model.money - max(0, amount))

    def add_items(self, item_keys: list[str]) -> None:
        for key in item_keys:
            item = self.player.scene.create_item(key, 0, 0, show=False)
            self.player.pick_up(item)

    def remove_items(self, item_keys: list[str]) -> None:
        for key in item_keys:
            self._remove_one_item(key)

    def restore_health(self, amount: int) -> None:
        self.player.model.health = min(
            self.player.model.max_health,
            self.player.model.health + max(0, amount),
        )

    def lose_health(self, amount: int) -> None:
        self.player.model.health = max(
            0,
            self.player.model.health - max(0, amount),
        )

    def shift_sentiment(self, amount: int) -> None:
        self.npc.sentiment = max(0, min(100, self.npc.sentiment + amount))

    def _remove_one_item(self, key: str) -> None:
        """Drop one stack-count of ``key`` from the hero's inventory silently."""
        for idx, item in enumerate(self.player.items):
            if item.name == key:
                self.player.total_items_weight -= item.model.weight
                if item.model.count > 1:
                    item.model.count -= 1
                else:
                    self.player.items.pop(idx)
                    if self.player.selected_item_idx >= len(self.player.items):
                        self.player.selected_item_idx = max(
                            0, len(self.player.items) - 1
                        )
                break
