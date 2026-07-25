"""Anchoring/layout helpers + layout self-checks.

The HUD positions panels relative to screen corners and edges. ``anchor_rect`` turns
an anchor name plus a reference rect into an absolute rect, so panel code reads as
"put this 200x36 box at the screen's bottom-right with a 16px margin" instead of
hand-computed ``WIDTH - ... - ...`` arithmetic.

The second half of this module is the **layout violation registry**: widgets that
notice their content does not fit report it here, tests assert the registry is empty.
See "Layout self-checks" in ``project/ui/AGENTS.md``.
"""
from __future__ import annotations

import pygame

import settings

# valid pygame.Rect anchor attribute names
ANCHORS = (
    "topleft", "midtop", "topright",
    "midleft", "center", "midright",
    "bottomleft", "midbottom", "bottomright",
)


#############################################################################################################
def screen_rect() -> pygame.Rect:
    return pygame.Rect(0, 0, settings.WIDTH, settings.HEIGHT)


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


#############################################################################################################
# MARK: layout self-checks (violation registry)
#
# The most common UI bug class - "the panel is too small for the text", "the text runs
# into the frame" - is invisible to unit tests and only shows up on a screenshot, where
# an LLM reviewer may or may not catch it. But the widgets KNOW their geometry: RichText
# knows how wide its longest line came out and how tall the content is, a panel knows its
# inner rect. So the check is exact, and this registry is where the findings land.
#
# This mechanism only MEASURES and REPORTS. It never clamps, truncates or "fixes" a
# layout - a violation is a bug to fix at the source, not something to paper over here.

_violations: list[str] = []
_seen: set[str] = set()


def report_violation(widget: str, kind: str, detail: str) -> None:
    """Record a layout violation (once per ``(widget, kind)`` per session).

    Deduplication is essential: these checks sit on the draw path, so without it the
    log would grow by one line per frame. ``kind`` is a short slug used by tests -
    ``h-overflow``, ``v-overflow``, ``clipped``, ``outside-panel``.
    """
    key = f"{widget}:{kind}"
    if key in _seen:
        return
    _seen.add(key)
    msg = f"[layout] {kind} in {widget}: {detail}"
    _violations.append(msg)
    print(msg)


def violations() -> list[str]:
    """Every violation reported since the last :func:`reset_violations`."""
    return list(_violations)


def reset_violations() -> None:
    """Clear the registry.

    Called when the geometry legitimately changes underneath the widgets - a
    resolution change or ``GameUI.reset()`` - so findings from the previous layout
    are not blamed on the new one.
    """
    _violations.clear()
    _seen.clear()


def check_inside(widget: str, inner: pygame.Rect, container: pygame.Rect) -> bool:
    """Report ``outside-panel`` when ``inner`` is not fully within ``container``.

    For panels that draw sections themselves instead of delegating to a widget that
    could check itself. Returns ``True`` when the layout is fine.
    """
    if container.contains(inner):
        return True
    report_violation(
        widget, "outside-panel",
        f"content {tuple(inner)} sticks out of panel area {tuple(container)}",
    )
    return False
