"""GameUI: per-Scene UI controller (HUD + panels) with a clean open/close API.

Replaces the monolithic legacy ``UI`` class and its loose boolean flags. Panels are
addressed by type:

    ui.open(DialogPanel, npc=npc, text=node_text)
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
from .panels.quest import QuestPanel
from .panels.help import HelpPanel
from .panels.hud import HUD
from .panels.inventory import InventoryPanel
from .panels.modal import ModalPanel
from .panels.save_load import LoadPanel, SavePanel
from .panels.trade import TradePanel

if TYPE_CHECKING:
    from scene import Scene

    from .widget import Widget

# panels that hide the gameplay HUD overlay (weapon/hotbar/help) while open
# Closing one of these can have changed the world in a way a quest cares about:
# a conversation happened (visited nodes), or items changed hands (trade).
_QUEST_EVENT_PANELS = (DialogPanel, TradePanel)

# the hotbar is not drawn while one of these is up: it would show through the panel
_BLOCKING = (DialogPanel, TradePanel, QuestPanel, HelpPanel)
# panels that fully freeze the world while open: input must go to the panel only,
# not to the scene underneath (otherwise e.g. R renames a slot *and* reloads the map).
# The journal is here so its arrow keys drive the list instead of walking the hero
# around behind it, and so Esc closes it rather than opening the main menu. The help
# panel is here too — that is what "pause the game until it is closed" means.
_MODAL = (DialogPanel, TradePanel, LoadPanel, SavePanel, QuestPanel, HelpPanel)


class GameUI:
    def __init__(self, scene: "Scene") -> None:
        self.scene = scene
        self.game = scene.game
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
            if panel_type in _QUEST_EVENT_PANELS:
                # The main quest event (D12=C): the conversation that satisfied a
                # quest has just ended. Hooked here rather than at the call sites
                # so every way of closing counts - final node, Esc, a panel
                # closing itself - and so a quest cannot depend on which one the
                # player used.
                self.scene.quests.on_event(f"{panel_type.__name__}_closed")

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
        """Back-compat shim: the help panel is now a modal in this UI's stack."""
        return self.is_open(HelpPanel)

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

        if INPUTS["quest_log"]:
            self.toggle(QuestPanel)
            INPUTS["quest_log"] = False

        # Help (H / F1): a modal panel, so it pauses the world (see _MODAL). Handled
        # here rather than in Scene.update because a modal freezes the scene and its
        # update never reaches the old toggle — this runs before that freeze.
        if INPUTS["help"]:
            self.toggle(HelpPanel)
            INPUTS["help"] = False
        if self.is_open(HelpPanel):
            help_panel = cast(HelpPanel, self._panel(HelpPanel))
            if self._edge("up"):
                help_panel.scroll_up()
            if self._edge("down"):
                help_panel.scroll_down()
            # mouse wheel scrolls the panel too (deliberately not a documented shortcut)
            for ev in events:
                if ev.type == pygame.MOUSEWHEEL:
                    if ev.y > 0:
                        help_panel.scroll_up()
                    elif ev.y < 0:
                        help_panel.scroll_down()
            if INPUTS["quit"]:
                self.close(HelpPanel)
                INPUTS["quit"] = False

        if self.is_open(QuestPanel):
            quests = cast(QuestPanel, self._panel(QuestPanel))
            # rising edge, same as the dialog: a held key must not race the list
            if self._edge("up"):
                quests.select_prev()
            if self._edge("down"):
                quests.select_next()
            if self._edge("right"):
                quests.next_filter()
            if self._edge("left"):
                quests.prev_filter()
            if self._edge("accept"):
                quests.toggle_expand()
                INPUTS["accept"] = False
            if INPUTS["quit"]:
                self.close(QuestPanel)
                INPUTS["quit"] = False

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
                            # re-clamp selection to the (now shrunk) filtered list: drop_item
                            # adjusts selected_item_idx against the full inventory, but while
                            # selling the index refers to the tradable-only list.
                            filtered = player.get_tradable_items()
                            if not filtered:
                                player.selected_item_idx = -1
                            elif player.selected_item_idx >= len(filtered):
                                player.selected_item_idx = len(filtered) - 1
                INPUTS["sell"] = False

            # item selection during trade
            for idx in range(1, self.scene.player.max_items + 1):
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
        # Read game.HUD live: changing the resolution recreates that surface, and a
        # cached reference would leave the HUD/panels drawing onto the old, orphaned
        # surface (never blitted) — invisible HUD after a resolution change.
        surface = self.game.HUD
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

        # notifications always on top; the stats box hides behind a full-screen panel
        # (the journal or the help reference)
        self.hud.draw_overlay(surface, stats=not (self.is_open(QuestPanel) or self.is_open(HelpPanel)))
