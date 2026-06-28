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

from typing import TYPE_CHECKING

import pygame

from settings import INPUTS

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


class GameUI:
    def __init__(self, scene: "Scene") -> None:
        self.scene = scene
        self.game = scene.game
        self.surface = self.game.HUD
        self.hud = HUD(scene)
        self._panels: dict[type, "Widget"] = {}
        self._open: list["Widget"] = []

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
                dialog = self._panel(DialogPanel)
                if dialog.at_bottom:  # type: ignore[attr-defined]
                    self.close(DialogPanel)
                    self.scene.player.is_talking = False
                    if self.scene.player.npc_met:
                        self.scene.player.npc_met.is_talking = False
                else:
                    dialog.page_down()  # type: ignore[attr-defined]
                INPUTS["talk"] = False

        # route raw events (scroll wheel / arrows) to the topmost open panel
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
