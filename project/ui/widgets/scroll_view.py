"""ScrollView: a clipped, vertically-scrollable content region with an
auto-hiding scrollbar — one component for every panel that can overflow.

The quest details pane, a long help column, a wall of dialogue prose: all the
same shape — content that may be taller than the box it lives in. Instead of each
panel re-deriving a clip rect, a scroll offset, clamping and a scrollbar (help.py
did it by hand, quest.py had none and let rewards run off the frame), they share
this one widget.

**Immediate mode, matching the panels' drawing style.** You give it a viewport
rect and a ``render(top_y, width)`` callback that draws the content with its top
at ``top_y`` and its left at ``viewport.left``, wrapped to ``width``, and returns
the absolute y where it stopped. The view handles:

- **clipping** — content never spills past the viewport (that was the bug: a
  reward chip drawing onto the panel border);
- **the scroll offset** and clamping it to ``[0, max_scroll]``;
- **the shared beveled scrollbar** (``widgets/bar.py``), drawn *only when the
  content overflows* — a box that fits shows no bar.

**No reflow oscillation.** The scrollbar column is reserved out of ``width``
*always* (a fixed gutter), not only while the bar shows. Narrowing the content
just as the bar appears would change wrapping, which could flip overflow back
off, which hides the bar, which widens the content again… a one-pixel-boundary
flicker loop. A permanent gutter costs a few pixels of width and is rock-steady;
the design system prizes not-breaking over squeezing the last column.

Content height is measured *this* frame (the callback returns its bottom), so the
scrollbar decision has no one-frame lag; input clamps against the last measured
height, which self-corrects on the next draw.
"""
from __future__ import annotations

from collections.abc import Callable

import pygame

from . import bar

# 16 is a multiple of 8, so bar.py scales the native 8-col art at k=2 (thinner
# reads as fragile 1px detail — see the design-system "chunky" rule).
_SCROLLBAR_W = 16
_GAP = 8            # empty gutter between the content and the scrollbar column
_STEP = 30          # one key-press / wheel-notch, ~one quest row (_ROW_H)


class ScrollView:
    """A vertically scrollable viewport. One instance per scrollable region;
    keep it on the panel and call :meth:`draw` each frame."""

    def __init__(self, *, scrollbar_w: int = _SCROLLBAR_W, gap: int = _GAP,
                 step: int = _STEP) -> None:
        self.scroll = 0
        self._scrollbar_w = scrollbar_w
        self._gap = gap
        self._step = step
        # measured on the last draw pass, so input can clamp before the next one
        self._content_h = 0
        self._viewport_h = 0

    # --- state --------------------------------------------------------------

    @property
    def max_scroll(self) -> int:
        return max(0, self._content_h - self._viewport_h)

    @property
    def overflows(self) -> bool:
        return self._content_h > self._viewport_h

    def reset(self) -> None:
        """Snap back to the top — call when the content changes (e.g. a panel's
        ``open()``, or a new item selected)."""
        self.scroll = 0

    # --- input --------------------------------------------------------------

    def scroll_by(self, dy: int) -> None:
        self.scroll = max(0, min(self.scroll + dy, self.max_scroll))

    def scroll_up(self) -> None:
        self.scroll_by(-self._step)

    def scroll_down(self) -> None:
        self.scroll_by(self._step)

    def page_or_top(self, viewport_h: int | None = None) -> None:
        """Page down, wrapping back to the top once the end is in view.

        Mirrors the dialogue speech scroll (SPACE): one key both advances and
        resets, so a single button reads the whole thing without a second key.
        """
        height = viewport_h if viewport_h is not None else self._viewport_h
        if self.scroll >= self.max_scroll:
            self.scroll = 0
        else:
            self.scroll_by(max(1, height - self._step))

    def handle_wheel(self, events: "list[pygame.event.Event]") -> None:
        """Mouse-wheel scrolling (deliberately not a documented shortcut, as in
        help.py). Safe to call every frame; no-op without a wheel event."""
        for ev in events:
            if ev.type == pygame.MOUSEWHEEL:
                if ev.y > 0:
                    self.scroll_up()
                elif ev.y < 0:
                    self.scroll_down()

    # --- drawing ------------------------------------------------------------

    def draw(
        self,
        surface: pygame.Surface,
        viewport: "pygame.Rect | tuple[int, int, int, int]",
        render: "Callable[[int, int], int]",
    ) -> None:
        """Draw scrollable content clipped to ``viewport``.

        ``render(top_y, width)`` draws content with its top at ``top_y`` and its
        left at ``viewport.left``, wrapped to ``width`` (already narrowed to leave
        the scrollbar gutter), and returns the absolute y where it finished. The
        delta from ``top_y`` is the content height.
        """
        viewport = pygame.Rect(viewport)
        self._viewport_h = viewport.height
        # clamp against the height measured last frame (0 on the first pass → no-op)
        self.scroll = max(0, min(self.scroll, self.max_scroll))
        width = max(1, viewport.width - self._scrollbar_w - self._gap)

        old_clip = surface.get_clip()
        clip = viewport if old_clip is None else old_clip.clip(viewport)
        surface.set_clip(clip)
        top_y = viewport.top - self.scroll
        bottom = render(top_y, width)
        surface.set_clip(old_clip)

        self._content_h = max(0, bottom - top_y)
        if self.overflows:
            self._draw_scrollbar(surface, viewport)

    def _draw_scrollbar(self, surface: pygame.Surface, viewport: pygame.Rect) -> None:
        """Shared beveled capsule scrollbar (``widgets/bar.py``) at the right edge."""
        x = viewport.right - self._scrollbar_w
        max_scroll = self.max_scroll
        bar.draw_scrollbar(
            surface, (x, viewport.top, self._scrollbar_w, viewport.height),
            frac_visible=viewport.height / self._content_h,
            frac_pos=self.scroll / max_scroll if max_scroll else 0.0,
        )
