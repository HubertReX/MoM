"""Image widget: blits a (pre-built) surface at an anchored position."""
from __future__ import annotations

import pygame

from ..widget import Widget


class Image(Widget):
    def __init__(
        self,
        surface: pygame.Surface,
        pos: tuple[int, int] = (0, 0),
        *,
        anchor: str = "topleft",
    ) -> None:
        super().__init__()
        self._surface = surface
        self.rect = surface.get_rect()
        setattr(self.rect, anchor, pos)
        self._anchor = anchor

    def set_surface(self, surface: pygame.Surface) -> None:
        if surface is not self._surface:
            self._surface = surface
            pos = getattr(self.rect, self._anchor)
            self.rect = surface.get_rect()
            setattr(self.rect, self._anchor, pos)
            self.mark_dirty()

    def render(self) -> pygame.Surface:
        return self._surface
