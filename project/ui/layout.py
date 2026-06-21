"""Anchoring/layout helpers.

The HUD positions panels relative to screen corners and edges. ``anchor_rect`` turns
an anchor name plus a reference rect into an absolute rect, so panel code reads as
"put this 200x36 box at the screen's bottom-right with a 16px margin" instead of
hand-computed ``WIDTH - ... - ...`` arithmetic.
"""
from __future__ import annotations

import pygame

from settings import HEIGHT, WIDTH

# valid pygame.Rect anchor attribute names
ANCHORS = (
    "topleft", "midtop", "topright",
    "midleft", "center", "midright",
    "bottomleft", "midbottom", "bottomright",
)


#############################################################################################################
def screen_rect() -> pygame.Rect:
    return pygame.Rect(0, 0, WIDTH, HEIGHT)


def anchor_rect(
    size: tuple[int, int],
    anchor: str = "topleft",
    ref: pygame.Rect | None = None,
    offset: tuple[int, int] = (0, 0),
) -> pygame.Rect:
    """Position a rect of ``size`` so its ``anchor`` point sits on ``ref``'s same-named
    point, shifted by ``offset``.

    Args:
        size: (width, height) of the new rect.
        anchor: one of :data:`ANCHORS`.
        ref: reference rect (defaults to the whole screen).
        offset: (dx, dy) applied after anchoring.
    """
    if anchor not in ANCHORS:
        raise ValueError(f"unknown anchor {anchor!r}; expected one of {ANCHORS}")
    ref = ref if ref is not None else screen_rect()
    rect = pygame.Rect((0, 0), size)
    setattr(rect, anchor, getattr(ref, anchor))
    rect.move_ip(offset)
    return rect
