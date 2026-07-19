"""Beveled capsule bar — scrollbar thumb and progress fill in one component.

Reference art: ``assets/NinjaAdventure/HUD/scrollbar.png`` (8×16). Every colour in
that sprite is already a ``theme`` token, so the bar is built **procedurally** — that
lets it stretch to any length, run vertical OR horizontal, and take an arbitrary fill
colour (the dialog sentiment bar needs red→green, which a baked gold sprite could
never do).

**Chunky pixel-art scaling (the nine-patch method).** The bar is modelled in the
asset's *native* 8-px grid (the exact cap profile below), then **integer-scaled with
nearest-neighbour** (`pygame.transform.scale`) so every native pixel becomes a clean
``k×k`` block and the rounded ends keep their blocky proportions. This is the same
principle as ``nine_patch.py``: draw small, upscale linearly, never anti-alias — no
fine 1-px features that betray the upscaled pixel-art. ``k`` is derived from the
requested cross size (``k = round(cross / 8)``, min 2), so a bar is always at least
2× the native art.

Native anatomy (cross = 8 columns, matching the sprite)::

      col:  0 1 2 3 4 5 6 7
    frame:  I I . . . . I I     I = INK frame (2 px), rounded caps at both main ends
    track:  I I R R R R I I     R = RULE empty groove (interior 4 px)
     fill:  I I d F F l I I     d = dark bevel edge · F = fill body · l = light edge

The fill is a rounded capsule inside the track (rounded both ends), so a scrollbar
thumb and a progress fill share one model. Default bevel ``(WARN, TITLE)`` on
``fill=GOLD`` reproduces the sprite 1:1; ``bevel=None`` derives the two edges from
``fill`` (dark = fill×0.6, light = fill blended toward white) so the colour-changing
bars stay one component instead of a family of sprites.
"""
from __future__ import annotations

import pygame

from .. import theme

_NATIVE_CROSS = 8       # native columns, matching scrollbar.png width
_MIN_SCALE = 2          # never draw below 2× native — that is what "chunky" means
_MIN_THUMB_NATIVE = 3   # a scrollbar thumb is at least this many native rows long
_TRANSPARENT = (0, 0, 0, 0)


def _shade(color: "tuple[int, ...]", factor: float) -> "tuple[int, int, int]":
    """Darken (factor<1) or lighten toward white (factor>1) an RGB(A) colour."""
    r, g, b = color[0], color[1], color[2]
    if factor <= 1.0:
        return (int(r * factor), int(g * factor), int(b * factor))
    t = factor - 1.0
    return (int(r + (255 - r) * t), int(g + (255 - g) * t), int(b + (255 - b) * t))


def _edges(
    fill: "tuple[int, int, int]",
    bevel: "tuple[tuple[int, int, int], tuple[int, int, int]] | None",
) -> "tuple[tuple[int, int, int], tuple[int, int, int]]":
    return bevel if bevel is not None else (_shade(fill, 0.6), _shade(fill, 1.4))


def _cell(
    ci: int, mi: int, native_main: int,
    seg_start: int, seg_len: int,
    fill: "tuple[int, int, int]", dark: "tuple[int, int, int]", light: "tuple[int, int, int]",
) -> "tuple[int, int, int] | tuple[int, int, int, int] | None":
    """Colour of native cell (cross ``ci`` 0..7, main ``mi``) — see the anatomy above.

    Returns ``None`` for the transparent area outside the rounded pill outline.
    """
    d = min(mi, native_main - 1 - mi)   # distance from the nearest main-axis tip
    # Rounded frame cap: inset the INK outline near each end (blocky stair-step).
    frame_inset = 3 if d == 0 else 2 if d == 1 else 1 if d == 2 else 0
    left, right = frame_inset, _NATIVE_CROSS - 1 - frame_inset
    if ci < left or ci > right:
        return None
    if frame_inset > 0:                 # whole cap row is solid frame
        return theme.INK
    if ci in (0, 1, 6, 7):              # frame side columns
        return theme.INK
    # interior columns 2..5, themselves rounded one row in from the frame cap
    interior_cols = (3, 4) if d == 3 else (2, 3, 4, 5)
    if ci not in interior_cols:
        return theme.INK
    # inside the groove: track unless this row is within the fill segment
    in_fill = seg_len > 0 and seg_start <= mi < seg_start + seg_len
    if not in_fill:
        return theme.RULE
    rounded_end = mi in (seg_start, seg_start + seg_len - 1)
    fill_cols = (3, 4) if (rounded_end or d == 3) else (2, 3, 4, 5)
    if ci not in fill_cols:
        return theme.RULE               # track shows at the fill's rounded corner
    if ci == 2:
        return dark
    if ci == 5:
        return light
    return fill


def _blit_bar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    vertical: bool,
    frac_visible: float | None,
    frac_pos: float,
    fraction: float,
    fill: "tuple[int, int, int]",
    bevel: "tuple[tuple[int, int, int], tuple[int, int, int]] | None",
) -> None:
    cross = rect.width if vertical else rect.height
    main = rect.height if vertical else rect.width
    k = max(_MIN_SCALE, round(cross / _NATIVE_CROSS))
    native_main = max(7, round(main / k))
    interior = native_main - 6            # rows 3 .. native_main-4 hold track/fill

    if frac_visible is not None:          # scrollbar thumb
        thumb = max(_MIN_THUMB_NATIVE, round(interior * max(0.0, min(1.0, frac_visible))))
        thumb = min(thumb, interior)
        seg_start = 3 + round((interior - thumb) * max(0.0, min(1.0, frac_pos)))
        seg_len = thumb
    else:                                 # progress fill from the start
        seg_len = min(interior, round(interior * max(0.0, min(1.0, fraction))))
        seg_start = 3

    dark, light = _edges(fill, bevel)
    native = pygame.Surface((_NATIVE_CROSS, native_main), pygame.SRCALPHA)
    native.fill(_TRANSPARENT)
    for mi in range(native_main):
        for ci in range(_NATIVE_CROSS):
            c = _cell(ci, mi, native_main, seg_start, seg_len, fill, dark, light)
            if c is not None:
                native.set_at((ci, mi), c)

    scaled = pygame.transform.scale(native, (_NATIVE_CROSS * k, native_main * k))
    if not vertical:
        # transpose vertical→horizontal: fill-start (top) → left, dark edge → top
        scaled = pygame.transform.rotate(pygame.transform.flip(scaled, True, False), 90)
    # centre on the cross axis, align to the start of the main axis
    if vertical:
        pos = (rect.x + (rect.width - scaled.get_width()) // 2, rect.y)
    else:
        pos = (rect.x, rect.y + (rect.height - scaled.get_height()) // 2)
    surface.blit(scaled, pos)


def draw_scrollbar(
    surface: pygame.Surface,
    rect: "pygame.Rect | tuple[int, int, int, int]",
    *,
    frac_visible: float,
    frac_pos: float,
    vertical: bool = True,
    fill: "tuple[int, int, int]" = theme.GOLD,
    bevel: "tuple[tuple[int, int, int], tuple[int, int, int]] | None" = (theme.WARN, theme.TITLE),
) -> None:
    """Capsule track with a beveled thumb.

    ``frac_visible`` = viewport / content (the thumb's share of the track);
    ``frac_pos`` = scroll / max_scroll (0 at top/left, 1 at bottom/right).
    """
    _blit_bar(surface, pygame.Rect(rect), vertical, frac_visible, frac_pos, 0.0, fill, bevel)


def draw_progress(
    surface: pygame.Surface,
    rect: "pygame.Rect | tuple[int, int, int, int]",
    fraction: float,
    *,
    vertical: bool = False,
    fill: "tuple[int, int, int]" = theme.ACCENT_CYAN,
    bevel: "tuple[tuple[int, int, int], tuple[int, int, int]] | None" = None,
) -> None:
    """Capsule track with a beveled fill from the start up to ``fraction`` (0..1).

    ``bevel`` defaults to edges derived from ``fill`` — the colour-changing bars
    (e.g. dialog sentiment) rely on this so one component covers every hue.
    """
    _blit_bar(surface, pygame.Rect(rect), vertical, None, 0.0, fraction, fill, bevel)
