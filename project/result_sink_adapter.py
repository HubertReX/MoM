"""Concrete ResultSink adapter backed by live MoM game objects.

This is the game-side half of decision D8: the dialog engine defines the
``ResultSink`` Protocol, and this module implements it using the hero's
inventory, health, money and the current NPC's sentiment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from enums import NotificationTypeEnum
from dialog.result_sink import ResultSink
from settings import _, entity_name

if TYPE_CHECKING:
    from characters import NPC, Player


# Delay (seconds) between consecutive dialog-result notifications so
# multi-item transfers animate in one at a time instead of stacking.
_ITEM_NOTIFY_DELAY = 0.5


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
        scene = self.player.scene
        for i, key in enumerate(item_keys):
            item = scene.create_item(key, 0, 0, show=False)
            self.player.pick_up(item)
            scene.add_notification(
                _("notify.received_item", name=entity_name(item.model)),
                NotificationTypeEnum.success,
            )
            scene.notifications[-1].create_time += i * _ITEM_NOTIFY_DELAY

    def remove_items(self, item_keys: list[str]) -> None:
        scene = self.player.scene
        names: list[str] = []
        for key in item_keys:
            name = self._remove_one_item(key)
            if name:
                names.append(name)
        for i, name in enumerate(names):
            scene.add_notification(
                _("notify.given_item", name=name),
                NotificationTypeEnum.info,
            )
            scene.notifications[-1].create_time += i * _ITEM_NOTIFY_DELAY

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

    def shift_sentiment(self, amount: int, emote_key: str = "") -> None:
        self.npc.sentiment = max(0, min(100, self.npc.sentiment + amount))
        if amount != 0:
            self.player.scene.add_notification(
                _("notify.sentiment", amount=amount),
                NotificationTypeEnum.success if amount > 0 else NotificationTypeEnum.info,
                emote_key=emote_key,
            )

    def _remove_one_item(self, key: str) -> str | None:
        """Drop one stack-count of ``key`` from the hero's inventory.

        Returns the display name of the removed item (or ``None`` if not found).
        """
        for idx, item in enumerate(self.player.items):
            if item.name == key:
                display_name = entity_name(item.model)
                self.player.total_items_weight -= item.model.weight
                if item.model.count > 1:
                    item.model.count -= 1
                else:
                    self.player.items.pop(idx)
                    if self.player.selected_item_idx >= len(self.player.items):
                        self.player.selected_item_idx = max(
                            0, len(self.player.items) - 1
                        )
                return display_name
        return None
