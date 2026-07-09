"""Button: clickable / selectable text item used by menus.

Handles its own mouse hover + click. Keyboard/gamepad navigation is driven by the
containing menu, which sets :attr:`selected` and calls :meth:`activate`.
"""
from __future__ import annotations

from typing import Callable

import pygame

from settings import FONT_SIZE_LARGE, MENU_FONT

from ..theme import NAME, TEXT, get_font
from ..widget import Widget


class Button(Widget):
    def __init__(
        self,
        text: str,
        callback: Callable[[], object] | None = None,
        pos: tuple[int, int] = (0, 0),
        *,
        size: int = FONT_SIZE_LARGE,
        width: int | None = None,
        height: int | None = None,
        color: pygame._common.ColorValue = TEXT,
        selected_color: pygame._common.ColorValue = NAME,
        font_path: str = str(MENU_FONT),
        background: pygame.Surface | None = None,
        padding: tuple[int, int] = (16, 8),
        anchor: str = "topleft",
    ) -> None:
        super().__init__()
        self._text = str(text)
        self._callback = callback
        self._size = size
        self._color = color
        self._selected_color = selected_color
        self._font_path = font_path
        self._background = background
        self._padding = padding
        self._anchor = anchor
        self._selected = False

        font = get_font(size, font_path=font_path)
        tw, th = font.size(self._text)
        self.rect.size = (width or tw + 2 * padding[0], height or th + 2 * padding[1])
        setattr(self.rect, anchor, pos)

    #############################################################################################################
    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        if value != self._selected:
            self._selected = value
            self.mark_dirty()

    def set_text(self, text: str) -> None:
        if text != self._text:
            self._text = str(text)
            font = get_font(self._size, font_path=self._font_path)
            tw, th = font.size(self._text)
            self.rect.size = (tw + 2 * self._padding[0], th + 2 * self._padding[1])
            self.mark_dirty()

    def activate(self) -> None:
        if self.enabled and self._callback is not None:
            self._callback()

    #############################################################################################################
    def render(self) -> pygame.Surface:
        surf = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        if self._background is not None:
            surf.blit(pygame.transform.scale(self._background, self.rect.size), (0, 0))

        font = get_font(self._size, font_path=self._font_path)
        color = self._selected_color if self._selected else self._color
        text_surf = font.render(self._text, False, color)
        text_rect = text_surf.get_rect(center=(self.rect.width // 2, self.rect.height // 2))
        surf.blit(text_surf, text_rect)
        return surf

    #############################################################################################################
    def _on_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.selected = self.rect.collidepoint(event.pos)
            return False  # motion never consumes
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.activate()
                return True
        return False
