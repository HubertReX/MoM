"""DialogPanel: NPC conversation box (avatars, name, scrollable rich text, link tooltip).

Replaces UI.show_dialog_panel / activate_dialog_panel (legacy.py). Layout positions are
kept identical to the original so the screen looks unchanged.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from settings import AVATAR_SCALE, CHAR_NAME_COLOR, FONT_SIZE_LARGE, HEIGHT, MAIN_FONT, TILE_SIZE, WIDTH

from .. import theme
from ..widget import Widget
from ..widgets import Label
from ..widgets.rich_text import RichText
from ._tooltip import Tooltip

if TYPE_CHECKING:
    from characters import NPC
    from scene import Scene

_BORDER = 24
_TOOLTIP_TEMPLATE = "[h3][act]Hint[/act][/h3]\n\n[bold]%s[/bold]"


class DialogPanel(Widget):
    def __init__(self, scene: "Scene", hud: object | None = None) -> None:
        super().__init__()
        self.scene = scene
        self.game = scene.game
        self.npc: "NPC | None" = None

        bg_w, bg_h = WIDTH - 200, HEIGHT // 3
        self.bg = theme.nine_patch("nine_patch_01c.png", bg_w, bg_h)
        self.offset = (100, HEIGHT - self.bg.get_height() - 10)
        self.rect = pygame.Rect(self.offset, self.bg.get_size())

        text_rect = (self.offset[0] + _BORDER, self.offset[1] + _BORDER, bg_w - 2 * _BORDER, bg_h - 2 * _BORDER)
        self.body = RichText("", text_rect, scene.icons, base_size=20)

        self.name_bg = theme.nine_patch("nine_patch_13.png", 26 * TILE_SIZE, TILE_SIZE)
        self.name_label = Label("", size=FONT_SIZE_LARGE, font_path=str(MAIN_FONT),
                                color=CHAR_NAME_COLOR, shadow=True)
        self.key_space = scene.icons["key_Space"][0]

        self.tooltip = Tooltip(scene.icons, _TOOLTIP_TEMPLATE, cursor_size=self.game.cursor_img.get_size())

    #############################################################################################################
    def open(self, npc: "NPC | None" = None, text: str = "") -> None:
        """Configure the panel when the UI controller opens it."""
        self.set_dialog(npc, text)

    def set_dialog(self, npc: "NPC | None", text: str) -> None:
        self.npc = npc
        self.body.set_text(text)
        self.body.scroll_top()
        name = npc.model.name if npc else "????"
        self.name_label.set_text(name)
        self.name_label.set_pos(
            (self.offset[0] + 4 * TILE_SIZE, self.offset[1] - int(1.5 * TILE_SIZE))
        )
        self.tooltip.update(None, (0, 0))

    # scroll/close helpers used by the UI controller
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
        avatar_off = TILE_SIZE * AVATAR_SCALE
        if self.npc is not None:
            surface.blit(self.npc.avatar, (self.offset[0], self.offset[1] + 4 - avatar_off))
            surface.blit(
                self.scene.player.avatar,
                (self.offset[0] + self.bg.get_width() - avatar_off, self.offset[1] + 4 - avatar_off),
            )

        surface.blit(self.bg, self.offset)
        self.body.draw(surface)

        surface.blit(self.name_bg, (self.offset[0] + 3 * TILE_SIZE, self.offset[1] - 3 * TILE_SIZE))
        self.name_label.draw(surface)

        surface.blit(self.key_space, (self.offset[0] + self.bg.get_width() - 15, self.offset[1] + 40))
        self.tooltip.draw(surface)
