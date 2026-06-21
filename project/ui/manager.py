"""UIManager: owns a flat, z-ordered list of top-level widgets for one context.

A context is a menu screen or a scene's HUD. The manager dispatches events
topmost-first (so an open modal swallows input before the HUD sees it), updates and
draws in insertion (z) order.
"""
from __future__ import annotations

import pygame

from .widget import Widget


class UIManager:
    def __init__(self, surface: pygame.Surface) -> None:
        self.surface: pygame.Surface = surface
        self.widgets: list[Widget] = []

    #############################################################################################################
    def add(self, widget: Widget) -> Widget:
        self.widgets.append(widget)
        return widget

    def remove(self, widget: Widget) -> None:
        if widget in self.widgets:
            self.widgets.remove(widget)

    def clear(self) -> None:
        self.widgets.clear()

    def bring_to_front(self, widget: Widget) -> None:
        if widget in self.widgets:
            self.widgets.remove(widget)
            self.widgets.append(widget)

    #############################################################################################################
    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            for widget in reversed(self.widgets):
                if widget.handle_event(event):
                    break

    def update(self, dt: float) -> None:
        for widget in self.widgets:
            widget.update(dt)

    def draw(self, surface: pygame.Surface | None = None) -> None:
        target = surface if surface is not None else self.surface
        for widget in self.widgets:
            widget.draw(target)
