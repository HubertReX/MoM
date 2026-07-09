"""Settings panel: resolution, fullscreen, language selector.

Replaces the placeholder "Settings" splash screen in the main menu.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pygame
import settings as _settings
from settings import HEIGHT, INPUTS, IS_WEB, MENU_FONT, WIDTH, _

from save_load.display_settings import save_display_settings

from .. import theme
from ..manager import UIManager
from ..widget import Widget
from ..widgets import Button

if TYPE_CHECKING:
    pass

_PAD = 40
_GAP = 20
_TITLE_SIZE = 48
_BUTTON_SIZE = 28
_LINE_SIZE = 16


# Import settings module for mutable state


class SettingsPanel(Widget):
    """Menu-style panel with resolution, fullscreen and language buttons."""

    def __init__(
        self,
        *,
        anchor: str = "midleft",
        pos: tuple[int, int] = (60, HEIGHT // 2),
        back_callback: Callable[[], object] | None = None,
        apply_callback: Callable[[], object] | None = None,
    ) -> None:
        self._back_callback = back_callback
        self._apply_callback = apply_callback
        super().__init__()
        self.index: int = 0  # current selection index
        self._button_types: list[str] = []
        self._buttons: list[Button] = []

        self._title_surf = theme.menu_font(_TITLE_SIZE).render(_("settings.title"), False, theme.NAME)
        self._rebuild_buttons()

        # Calculate panel size
        buttons_h = sum(b.rect.height + _GAP for b in self._buttons) + _GAP
        content_w = max(b.rect.width for b in self._buttons) + 2 * _PAD
        width = content_w + 2 * _PAD
        height = buttons_h + 2 * _PAD
        if self._title_surf:
            height += self._title_surf.get_height() + _GAP

        self.rect = pygame.Rect(0, 0, width, height)
        setattr(self.rect, anchor, pos)
        self._bg = theme.nine_patch("nine_patch_06b.png", width, height)

        # Layout buttons as children
        y = self.rect.top + _PAD
        if self._title_surf:
            y += self._title_surf.get_height() + _GAP
        for btn in self._buttons:
            btn.rect.left = self.rect.left + _PAD
            btn.rect.y = y
            self.add(btn)
            y += btn.rect.height + _GAP

        self._sync_selection()

    def _rebuild_buttons(self) -> None:
        """Recreate all buttons and child widgets after state change."""
        # Clear existing children
        self.children.clear()
        self._button_types.clear()
        self._buttons.clear()

        # Build resolution buttons
        for i, (xt, yt) in enumerate(_settings.DISPLAY_RES_OPTIONS):
            w = xt * _settings.TILE_SIZE
            h = yt * _settings.TILE_SIZE
            label = _("settings.resolution", w=w, h=h)
            self._buttons.append(Button(label, None, size=_BUTTON_SIZE))
            self._button_types.append("resolution")

        # Fullscreen button (desktop only)
        if not IS_WEB:
            state = _("settings.fullscreen_on") if _settings._IS_FULLSCREEN else _("settings.fullscreen_off")
            label = _("settings.fullscreen", state=state)
            self._buttons.append(Button(label, None, size=_BUTTON_SIZE))
            self._button_types.append("fullscreen")

        # Language toggle
        self._buttons.append(Button(_("settings.language", lang=_settings.LANG), None, size=_BUTTON_SIZE))
        self._button_types.append("language")

        self._buttons.append(Button(_("settings.back"), None, size=_BUTTON_SIZE))
        self._button_types.append("back")

        # Re-layout buttons as children
        buttons_h = sum(b.rect.height + _GAP for b in self._buttons) + _GAP
        content_w = max(b.rect.width for b in self._buttons) + 2 * _PAD
        width = content_w + 2 * _PAD
        height = buttons_h + 2 * _PAD
        if self._title_surf:
            height += self._title_surf.get_height() + _GAP

        self.rect.width = width
        self.rect.height = height
        self._bg = theme.nine_patch("nine_patch_06b.png", width, height)

        y = self.rect.top + _PAD
        if self._title_surf:
            y += self._title_surf.get_height() + _GAP
        for btn in self._buttons:
            btn.rect.center = (self.rect.centerx, y + btn.rect.height // 2)
            self.add(btn)
            y += btn.rect.height + _GAP

        self._sync_selection()

    def _sync_selection(self) -> None:
        n = len(self._buttons)
        self.index = self.index % n if n > 0 else 0
        for i, btn in enumerate(self._buttons):
            btn.selected = i == self.index

    def set_index(self, index: int) -> None:
        self.index = index
        self._sync_selection()

    def select_next(self) -> None:
        self.set_index(self.index + 1)

    def select_prev(self) -> None:
        self.set_index(self.index - 1)

    def render(self) -> pygame.Surface:
        surf = self._bg.copy()
        if self._title_surf is not None:
            rect = self._title_surf.get_rect(midtop=(surf.get_width() // 2, _PAD // 2))
            surf.blit(self._title_surf, rect)
        return surf

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            for i, child in enumerate(self.children):
                if child.rect.collidepoint(event.pos):
                    self.set_index(i)
                    break
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, child in enumerate(self.children):
                if child.rect.collidepoint(event.pos):
                    self.set_index(i)
                    self.activate()
                    return True
        return False

    def activate(self) -> None:
        bt = self._button_types[self.index]
        if bt == "resolution":
            idx = self.index
            _settings.set_display(idx)
            if self._apply_callback is not None:
                self._apply_callback()
            self._rebuild_buttons()
            save_display_settings()
        elif bt == "fullscreen":
            _settings._IS_FULLSCREEN = not _settings._IS_FULLSCREEN
            if self._apply_callback is not None:
                self._apply_callback()
            self._rebuild_buttons()
            save_display_settings()
        elif bt == "language":
            _settings.LANG = "EN" if _settings.LANG == "PL" else "PL"
            _settings.reload_ui_strings()
            self._rebuild_buttons()
            save_display_settings()
        elif bt == "back":
            if self._back_callback is not None:
                self._back_callback()


class SettingsMenu:
    """Settings menu backed by SettingsPanel."""

    def __init__(self, game: object, name: str = "Settings", bg_image: pygame.Surface | None = None) -> None:
        from ..panels.main_menu import MenuScreen

        screen_class = type(
            "SettingsMenu",
            (MenuScreen,),
            {
                "build_panel": lambda self: SettingsPanel(
                    anchor="midleft",
                    pos=(60, HEIGHT // 2),
                    back_callback=lambda: self.on_quit(),
                    apply_callback=lambda: self.game.set_display(),
                ),
            },
        )
        self._screen = screen_class(game, name, bg_image)

    def enter_state(self) -> None:
        self._screen.enter_state()

    def exit_state(self) -> None:
        self._screen.exit_state()

    def update(self, dt: float, events: list) -> None:
        self._screen.update(dt, events)

    def draw(self, screen: pygame.Surface, dt: float) -> None:
        self._screen.draw(screen, dt)

    @property
    def game(self) -> object:  # noqa: ANN003
        return self._screen.game

    @property
    def manager(self) -> UIManager:
        return self._screen.manager
