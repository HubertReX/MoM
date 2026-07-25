"""Label: a single run of plain text with an optional drop shadow or outline.

Replaces ``UI.display_text`` (ui.py). The rendered text is cached; it only re-renders
when :meth:`set_text` (or another setter) actually changes something.
"""
from __future__ import annotations

import pygame

from settings import FONT_SIZE_MEDIUM, MAIN_FONT, PANEL_BG_COLOR

from ..theme import TEXT, get_font
from ..widget import Widget


class Label(Widget):
    def __init__(
        self,
        text: str,
        pos: tuple[int, int] = (0, 0),
        *,
        size: int = FONT_SIZE_MEDIUM,
        color: pygame._common.ColorValue = TEXT,
        font_path: str = str(MAIN_FONT),
        bold: bool = False,
        italic: bool = False,
        shadow: bool = True,
        outline_color: pygame._common.ColorValue | None = PANEL_BG_COLOR,
        anchor: str = "topleft",
        name: str = "",
    ) -> None:
        super().__init__()
        # human-readable id in layout-violation reports (see ui/layout.py)
        self.name = name
        self._text = str(text)
        self._size = size
        self._color = color
        self._font_path = font_path
        self._bold = bold
        self._italic = italic
        self._shadow = shadow
        self._outline_color = outline_color
        self._anchor = anchor
        self._pos = pos
        self._relayout()

    #############################################################################################################
    @property
    def font(self) -> pygame.font.Font:
        return get_font(self._size, font_path=self._font_path, bold=self._bold, italic=self._italic)

    def set_text(self, text: str) -> None:
        text = str(text)
        if text != self._text:
            self._text = text
            self._relayout()

    def set_color(self, color: pygame._common.ColorValue) -> None:
        if color != self._color:
            self._color = color
            self.mark_dirty()

    def set_pos(self, pos: tuple[int, int], anchor: str | None = None) -> None:
        self._pos = pos
        if anchor is not None:
            self._anchor = anchor
        self._reanchor()

    #############################################################################################################
    def _relayout(self) -> None:
        """Recompute size (text changed) then re-anchor and mark dirty."""
        w, h = self.font.size(self._text)
        # outline grows the surface by 1px on each side; drop shadow by the offset
        pad = 3 if (self._outline_color and not self._shadow) else 2
        self.rect.size = (w + 2 * pad, h + 2 * pad)
        self._pad = pad
        self._reanchor()
        self.mark_dirty()

    def _reanchor(self) -> None:
        setattr(self.rect, self._anchor, self._pos)

    def _check_clipped(self, text_surf: pygame.Surface) -> None:
        """Report ``clipped`` when the rendered text does not fit the widget's rect.

        ``_relayout`` sizes the rect to the text, so this can only fire when a caller
        has overwritten ``rect.size`` afterwards (a fixed-width slot, a panel forcing
        a column width). That is exactly the case worth catching: the surface is
        allocated at ``rect.size``, so the excess is silently cut off, never wrapped.
        """
        needed_w = text_surf.get_width() + 2 * self._pad
        needed_h = text_surf.get_height() + 2 * self._pad
        if needed_w <= self.rect.width and needed_h <= self.rect.height:
            return
        from ..layout import report_violation
        label = self.name or f"'{self._text[:24]}'"
        report_violation(
            f"Label({label})", "clipped",
            f"text needs {needed_w}x{needed_h}px, rect is {self.rect.width}x{self.rect.height}px",
        )

    #############################################################################################################
    def render(self) -> pygame.Surface:
        surf = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        font = self.font
        pad = self._pad
        text_surf = font.render(self._text, False, self._color)
        self._check_clipped(text_surf)

        if self._outline_color:
            border_surf = font.render(self._text, False, self._outline_color)
            if self._shadow:
                surf.blit(border_surf, (pad + 2, pad + 2))
            else:
                for dx, dy in ((-pad, 0), (pad, 0), (0, -pad), (0, pad),
                               (-pad, -pad), (pad, -pad), (-pad, pad), (pad, pad)):
                    surf.blit(border_surf, (pad + dx, pad + dy))

        surf.blit(text_surf, (pad, pad))
        return surf
