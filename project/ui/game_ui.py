"""GameUI: per-Scene UI controller (HUD + panels) with a clean open/close API.

Replaces the monolithic legacy ``UI`` class and its loose boolean flags. Panels are
addressed by type:

    ui.open(DialogPanel, npc=npc, text=npc.dialogs)
    ui.open(TradePanel)
    ui.toggle(InventoryPanel)
    ui.close(DialogPanel)
    ui.is_open(TradePanel) -> bool

The HUD is always drawn. Open panels form a small z-ordered stack; the gameplay HUD
overlay (weapon/hotbar/help) is hidden while a blocking panel (dialog/trade) is open.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pygame

from settings import (
    INPUTS,
    MAX_HOTBAR_ITEMS,
    _,
    entity_name,
    get_buy_price_multiplier,
    get_sell_price_multiplier,
)
from objects import NotificationTypeEnum

from .panels.dialog import DialogPanel
from .panels.hud import HUD
from .panels.inventory import InventoryPanel
from .panels.modal import ModalPanel
from .panels.save_load import LoadPanel, SavePanel
from .panels.trade import TradePanel

if TYPE_CHECKING:
    from scene import Scene

    from .widget import Widget

# panels that hide the gameplay HUD overlay (weapon/hotbar/help) while open
_BLOCKING = (DialogPanel, TradePanel)
# panels that fully freeze the world while open: input must go to the panel only,
# not to the scene underneath (otherwise e.g. R renames a slot *and* reloads the map)
_MODAL = (DialogPanel, TradePanel, LoadPanel, SavePanel)


class GameUI:
    def __init__(self, scene: "Scene") -> None:
        self.scene = scene
        self.game = scene.game
        self.surface = self.game.HUD
        self.hud = HUD(scene)
        self._panels: dict[type, "Widget"] = {}
        self._open: list["Widget"] = []
        # rising-edge detector for held gamepad/keyboard inputs while DialogPanel is open
        self._dialog_held: dict[str, bool] = {}

    #############################################################################################################
    # MARK: panel registry / open-close API

    def _panel(self, panel_type: type) -> "Widget":
        panel = self._panels.get(panel_type)
        if panel is None:
            panel = panel_type(self.scene, self.hud)
            self._panels[panel_type] = panel
        return panel

    def open(self, panel_type: type, **kwargs) -> "Widget":
        panel = self._panel(panel_type)
        panel.open(**kwargs)  # type: ignore[attr-defined]
        panel.visible = True
        if panel not in self._open:
            self._open.append(panel)
        return panel

    def close(self, panel_type: type) -> None:
        panel = self._panels.get(panel_type)
        if panel is not None:
            panel.visible = False
            if panel in self._open:
                self._open.remove(panel)

    def toggle(self, panel_type: type) -> None:
        if self.is_open(panel_type):
            self.close(panel_type)
        else:
            self.open(panel_type)

    def is_open(self, panel_type: type) -> bool:
        panel = self._panels.get(panel_type)
        return panel is not None and panel in self._open

    def is_modal_open(self) -> bool:
        """True if a panel that should freeze the scene (Save/Load) is open."""
        return any(isinstance(p, _MODAL) for p in self._open)

    def reset(self) -> None:
        for panel in self._open:
            panel.visible = False
        self._open.clear()

    #############################################################################################################
    # MARK: convenience proxies used by scene/characters

    @property
    def is_buying(self) -> bool:
        return self._panel(TradePanel).is_buying  # type: ignore[attr-defined]

    def toggle_trade_side(self) -> None:
        self._panel(TradePanel).toggle_side()  # type: ignore[attr-defined]

    @property
    def show_help_info(self) -> bool:
        return self.hud.show_help_info

    @show_help_info.setter
    def show_help_info(self, value: bool) -> None:
        self.hud.show_help_info = value

    #############################################################################################################
    def _edge(self, action: str) -> bool:
        """Rising-edge detector so a held key/stick moves the selection only once."""
        value = bool(INPUTS[action])
        fired = value and not self._dialog_held.get(action, False)
        self._dialog_held[action] = value
        return fired

    #############################################################################################################
    # MARK: per-frame update

    def update(self, time_elapsed: float, events: list[pygame.event.Event]) -> None:
        if INPUTS["inventory"]:
            self.toggle(InventoryPanel)
            INPUTS["inventory"] = False

        if INPUTS["talk"]:
            if self.is_open(ModalPanel):
                modal = self._panel(ModalPanel)
                if modal.at_bottom:  # type: ignore[attr-defined]
                    self.close(ModalPanel)
                else:
                    modal.page_down()  # type: ignore[attr-defined]
                INPUTS["talk"] = False

        if self.is_open(DialogPanel):
            dialog = cast(DialogPanel, self._panel(DialogPanel))
            if self._edge("up"):
                dialog.select_prev()
            if self._edge("down"):
                dialog.select_next()
            if self._edge("accept"):
                if dialog.on_final_node:
                    # Final node reached: Accept closes the farewell text.
                    self.close(DialogPanel)
                    self.scene.player.is_talking = False
                    if self.scene.player.npc_met:
                        self.scene.player.npc_met.is_talking = False
                        self.scene.player.npc_met.reset_dialog()
                else:
                    dialog.activate_selected()
                # raw key events also call activate_selected; clear accept
                # so the same press is not handled twice this frame.
                INPUTS["accept"] = False
            if self._edge("talk"):
                # SPACE (talk) scrolls the NPC speech; at the bottom it wraps to top.
                if not dialog.body.is_scroll_bottom():
                    dialog.page_down()
                else:
                    dialog.scroll_top()
                INPUTS["talk"] = False

        if self.is_open(TradePanel):
            if INPUTS["end_trade"]:
                self.close(TradePanel)
                self.scene.player.is_talking = False
                if self.scene.player.npc_met:
                    self.scene.player.npc_met.is_talking = False
                INPUTS["end_trade"] = False
            if INPUTS["toggle"]:
                self.toggle_trade_side()
                INPUTS["toggle"] = False
            if INPUTS["buy"]:
                player = self.scene.player
                if player.npc_met and self.is_buying:
                    if player.can_buy():
                        item_to_buy = player.npc_met.drop_item(show=False)
                        if item_to_buy:
                            price = int(round(
                                item_to_buy.model.value * get_buy_price_multiplier(player.npc_met.sentiment)))
                            player.model.money -= price
                            player.npc_met.model.money += price
                            player.pick_up(item_to_buy)
                            self.scene.add_notification(
                                _("notify.bought", name=entity_name(item_to_buy.model), price=price),
                                NotificationTypeEnum.info)
                INPUTS["buy"] = False
            if INPUTS["sell"]:
                player = self.scene.player
                if player.npc_met and not self.is_buying:
                    if player.can_sell():
                        filtered = player.get_tradable_items()
                        if 0 <= player.selected_item_idx < len(filtered):
                            item_to_sell = player.drop_item(show=False, item=filtered[player.selected_item_idx])
                        else:
                            item_to_sell = None
                        if item_to_sell:
                            price = int(round(
                                item_to_sell.model.value * get_sell_price_multiplier(player.npc_met.sentiment)))
                            player.model.money += price
                            player.npc_met.model.money -= price
                            player.npc_met.pick_up(item_to_sell)
                            self.scene.add_notification(
                                _("notify.sold", name=entity_name(item_to_sell.model), price=price),
                                NotificationTypeEnum.info)
                INPUTS["sell"] = False

            # item selection during trade
            for idx in range(1, MAX_HOTBAR_ITEMS + 1):
                if INPUTS[f"item_{idx}"]:
                    player = self.scene.player
                    if self.is_buying and player.npc_met and player.npc_met.model.is_merchant:
                        npc = player.npc_met
                        items = npc.items
                    else:
                        npc = player
                        items = npc.get_tradable_items()
                    if idx - 1 < len(items):
                        npc.selected_item_idx = idx - 1
                    INPUTS[f"item_{idx}"] = False

            if INPUTS["next_item"]:
                player = self.scene.player
                if self.is_buying and player.npc_met and player.npc_met.model.is_merchant:
                    player.npc_met.select_next_item()
                else:
                    filtered = player.get_tradable_items()
                    player.select_next_item(filtered)
                INPUTS["next_item"] = False

            if INPUTS["prev_item"]:
                player = self.scene.player
                if self.is_buying and player.npc_met and player.npc_met.model.is_merchant:
                    player.npc_met.select_prev_item()
                else:
                    filtered = player.get_tradable_items()
                    player.select_prev_item(filtered)
                INPUTS["prev_item"] = False

        # route raw events to HUD first (e.g. help panel scroll), then to the topmost open panel
        for event in events:
            self.hud.handle_event(event)
        if self._open:
            top = self._open[-1]
            for event in events:
                top.handle_event(event)

        for panel in self._open:
            panel.update(time_elapsed)

    #############################################################################################################
    # MARK: draw

    def draw(self, time_elapsed: float | None = None) -> None:
        surface = self.surface
        blocking = any(isinstance(p, _BLOCKING) for p in self._open)

        # inventory background sits *under* the hotbar (original draw order)
        if self.is_open(InventoryPanel):
            self._panel(InventoryPanel).draw(surface)

        self.hud.draw_gameplay(surface, enabled=not blocking)

        # modal / dialog / trade render above the gameplay overlay
        for panel in self._open:
            if isinstance(panel, InventoryPanel):
                continue
            panel.draw(surface)

        # notifications + stats always on top
        self.hud.draw_overlay(surface)
