"""ModalPanel: full-width info/tutorial box (welcome message, etc.).

Replaces UI.show_modal_panel (legacy.py).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from settings import HEIGHT, WIDTH

from .. import theme
from ..widget import Widget
from ..widgets.rich_text import RichText
from ._tooltip import Tooltip

if TYPE_CHECKING:
    from scene import Scene

_BORDER = 24
_TOOLTIP_TEMPLATE = "[h3][act]This is a tooltip[/act][/h3]\n\n[bold]%s[/bold]"


class ModalPanel(Widget):
    def __init__(self, scene: "Scene", hud: object | None = None, text: str = "") -> None:
        super().__init__()
        self.scene = scene
        self.game = scene.game

        bg_w, bg_h = WIDTH - 200, HEIGHT - 100
        self.bg = theme.nine_patch("nine_patch_03c.png", bg_w, bg_h)
        self.offset = (100, 50)
        self.rect = pygame.Rect(self.offset, self.bg.get_size())

        text_rect = (self.offset[0] + _BORDER, self.offset[1] + _BORDER, bg_w - 2 * _BORDER, bg_h - 2 * _BORDER)
        self.body = RichText(text, text_rect, scene.icons, base_size=20)

        self.tooltip = Tooltip(scene.icons, _TOOLTIP_TEMPLATE, cursor_size=self.game.cursor_img.get_size())

    #############################################################################################################
    def open(self, text: str | None = None) -> None:
        if text is not None:
            self.set_text(text)

    def set_text(self, text: str) -> None:
        self.body.set_text(text)
        self.body.scroll_top()
        self.tooltip.update(None, (0, 0))

    @property
    def at_bottom(self) -> bool:
        return self.body.is_scroll_bottom()

    def page_down(self) -> None:
        self.body.scroll_page_down()

    def scroll_top(self) -> None:
        self.body.scroll_top()

    #############################################################################################################
    def handle_event(self, event: pygame.event.Event) -> bool:
        return self.body.handle_event(event)

    def update(self, dt: float) -> None:
        self.body.update(dt)
        self.tooltip.update(self.body.link_at(pygame.mouse.get_pos()), pygame.mouse.get_pos())

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        surface.blit(self.bg, self.offset)
        self.body.draw(surface)
        self.tooltip.draw(surface)
