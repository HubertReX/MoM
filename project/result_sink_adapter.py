"""Concrete ResultSink adapter backed by live MoM game objects.

This is the game-side half of decision D8: the dialog engine defines the
``ResultSink`` Protocol, and this module implements it using the hero's
inventory, health, money and the current NPC's sentiment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from enums import NotificationTypeEnum
from dialog.result_sink import ResultSink
from settings import _, MAX_HOTBAR_ITEMS_LIMIT, entity_name

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

    # --- quest rewards (Q-05) ------------------------------------------------

    def raise_max_health(self, amount: int) -> None:
        """Raise max health, and current health with it.

        Decided in Q-05: the hero feels the reward straight away, and a battered
        hero (50/80 -> 70/100) gains capacity without being healed for free.
        """
        amount = max(0, amount)
        self.player.model.max_health += amount
        self.player.model.health = min(
            self.player.model.max_health, self.player.model.health + amount
        )

    def raise_damage(self, amount: int) -> None:
        self.player.model.damage += max(0, amount)

    def raise_max_items(self, amount: int) -> None:
        """Widen the hero's hotbar, up to the number of slots the UI can drive.

        The ceiling is not cosmetic: each slot needs a `key_<n>` icon and an
        INPUTS["item_<n>"] binding, and those stop at MAX_HOTBAR_ITEMS_LIMIT.
        Going past it would draw a slot nobody can select.
        """
        self.player.max_items = min(
            MAX_HOTBAR_ITEMS_LIMIT, self.player.max_items + max(0, amount)
        )

    def shift_sentiment_of(self, npc_key: str, amount: int) -> None:
        """Shift a named NPC's sentiment, wherever that NPC currently is.

        A quest has no current NPC, so the reward names one. The NPC may well be
        on another map (or on none at all yet), which is why this searches the
        same three tiers as `find_visited_node` rather than only the live scene.
        """
        scene = self.player.scene
        for npc in getattr(scene, "loaded_NPCs", {}).values():
            if getattr(npc, "config_key", None) == npc_key:
                npc.sentiment = max(0, min(100, npc.sentiment + amount))
                return

        for cached in (getattr(scene, "loaded_maps", None) or {}).values():
            for npc in cached.get("NPCs", None) or []:
                if getattr(npc, "config_key", None) == npc_key:
                    npc.sentiment = max(0, min(100, npc.sentiment + amount))
                    return

        for map_state in (getattr(scene, "pending_map_states", None) or {}).values():
            for npc_state in map_state.npc_states.values():
                if npc_state.config_key == npc_key and npc_state.dialog_state is not None:
                    npc_state.dialog_state.sentiment = max(
                        0, min(100, npc_state.dialog_state.sentiment + amount)
                    )
                    return

        # Never met, never loaded: the NPC will be built from config with its
        # default sentiment, and this shift has nowhere to land. Say so — silently
        # dropping a reward is the bug this epic keeps deleting.
        print(f"[quest] sentiment reward for unknown/unloaded NPC {npc_key!r} was not applied")

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
