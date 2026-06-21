"""Lightweight retained-mode UI toolkit (pure pygame-ce, web/pygbag compatible).

Replaces the old menu/HUD/dialog stack that was glued together from pygame_menu and
thorpy/sftext. Widgets cache their rendered surface and only re-render when marked
dirty, so static UI costs one blit per frame.

Public API:
    UIManager          – per-context widget list (events/update/draw)
    Widget             – base class for custom widgets
    Label, Image, Button
    anchor_rect        – corner/edge anchoring helper
    theme              – fonts, palette, nine-patch cache
"""
from __future__ import annotations

from . import theme
from .layout import anchor_rect, screen_rect
from .manager import UIManager
from .widget import Widget
from .widgets import Button, Image, Label, RichText

__all__ = [
    "UIManager",
    "Widget",
    "Label",
    "Image",
    "Button",
    "RichText",
    "anchor_rect",
    "screen_rect",
    "theme",
]
