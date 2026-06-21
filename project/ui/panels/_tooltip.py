"""Link tooltip shared by dialog and modal panels.

A tooltip is built once per distinct link string (cached) and positioned next to the
mouse, clamped to the screen. Replaces RichPanel's second sftext instance.
"""
from __future__ import annotations

import pygame

from settings import HEIGHT, WIDTH

from ..theme import DEFAULT_TEXT_COLOR
from ..widgets.rich_text import RichText

_PAD = 12


class Tooltip:
    def __init__(
        self,
        icons: dict[str, list[pygame.Surface]],
        template: str,
        *,
        max_width: int = 360,
        cursor_size: tuple[int, int] = (0, 0),
    ) -> None:
        self.icons = icons
        self.template = template
        self.max_width = max_width
        self.cursor_size = cursor_size
        self._cache: dict[str, pygame.Surface] = {}
        self.surface: pygame.Surface | None = None
        self.rect: pygame.Rect | None = None

    #############################################################################################################
    def update(self, link: str | None, mouse_pos: tuple[int, int]) -> None:
        if not link:
            self.surface = None
            return
        surf = self._cache.get(link)
        if surf is None:
            surf = self._build(link)
            self._cache[link] = surf
        self.surface = surf
        x = mouse_pos[0] + self.cursor_size[0] // 2
        y = mouse_pos[1] + self.cursor_size[1]
        x = min(x, WIDTH - surf.get_width())
        y = min(y, HEIGHT - surf.get_height())
        self.rect = pygame.Rect(x, y, *surf.get_size())

    def draw(self, surface: pygame.Surface) -> None:
        if self.surface is not None and self.rect is not None:
            surface.blit(self.surface, self.rect)

    #############################################################################################################
    def _build(self, link: str) -> pygame.Surface:
        text = self.template % link
        rt = RichText(text, (0, 0, self.max_width, 4000), self.icons, base_size=14, show_scrollbar=False)
        content = rt.content_surface
        assert content is not None
        bg = pygame.Surface((content.get_width() + 2 * _PAD, content.get_height() + 2 * _PAD), pygame.SRCALPHA)
        bg.fill((30, 30, 30, 220))
        pygame.draw.rect(bg, DEFAULT_TEXT_COLOR, bg.get_rect(), 2)
        bg.blit(content, (_PAD, _PAD))
        return bg
