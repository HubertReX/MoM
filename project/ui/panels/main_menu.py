"""Main menu and About screens, built on the toolkit (replaces menus.py + pygame_menu).

A :class:`MenuPanel` is a bordered box with an optional title, optional static text
lines, and a vertical list of selectable buttons. :class:`MenuScreen` is the ``State``
that owns one panel and drives selection from the game's action inputs (so keyboard and
gamepad both work via the same ``INPUTS`` abstraction).
"""

from __future__ import annotations

import pygame

from settings import HEIGHT, INPUTS, IS_WEB, MENU_FONT, WIDTH
from state import State

from .. import theme
from ..manager import UIManager
from ..widget import Widget
from ..widgets import Button, Label

_PAD = 28
_GAP = 14
# menu uses the munro font at the sizes the original pygame_menu theme used
_TITLE_SIZE = 48
_BUTTON_SIZE = 36
_LINE_SIZE = 16


#######################################################################################################################
# MARK: MenuPanel


class MenuPanel(Widget):
    def __init__(
        self,
        options: list[tuple[str, object]],
        *,
        title: str | None = None,
        lines: list[str] | None = None,
        bg_file: str = "nine_patch_06b.png",
        anchor: str = "midleft",
        pos: tuple[int, int] = (60, HEIGHT // 2),
        title_size: int = _TITLE_SIZE,
        button_size: int = _BUTTON_SIZE,
        line_size: int = _LINE_SIZE,
        min_width: int = WIDTH // 5,
    ) -> None:
        super().__init__()
        self.index: int = 0

        self.buttons: list[Button] = [
            Button(label, cb, size=button_size)
            for label, cb in options  # type: ignore[arg-type]
        ]
        self.line_labels: list[Label] = [
            Label(text, size=line_size, font_path=str(MENU_FONT)) for text in (lines or [])
        ]

        self._title_surf = theme.menu_font(title_size).render(title, False, theme.NAME) if title else None

        title_h = (self._title_surf.get_height() + _GAP) if self._title_surf else 0
        lines_h = sum(lbl.rect.height + 4 for lbl in self.line_labels)
        buttons_h = sum(b.rect.height + _GAP for b in self.buttons)
        content_w = max(
            [b.rect.width for b in self.buttons] + [lbl.rect.width for lbl in self.line_labels] + [min_width]
        )
        width = content_w + 2 * _PAD
        height = title_h + lines_h + buttons_h + 2 * _PAD

        self.rect = pygame.Rect(0, 0, width, height)
        setattr(self.rect, anchor, pos)
        self._bg = theme.nine_patch(bg_file, width, height)

        self._layout_children()
        self._sync_selection()

    #############################################################################################################
    def _layout_children(self) -> None:
        y = self.rect.top + _PAD
        if self._title_surf:
            y += self._title_surf.get_height() + _GAP
        for lbl in self.line_labels:
            lbl.set_pos((self.rect.left + _PAD, y))
            self.add(lbl)
            y += lbl.rect.height + 4
        for btn in self.buttons:
            btn.rect.center = (self.rect.centerx, y + btn.rect.height // 2)
            self.add(btn)
            y += btn.rect.height + _GAP

    def _sync_selection(self) -> None:
        for i, btn in enumerate(self.buttons):
            btn.selected = i == self.index

    #############################################################################################################
    def set_index(self, index: int) -> None:
        if self.buttons:
            self.index = index % len(self.buttons)
            self._sync_selection()

    def select_next(self) -> None:
        self.set_index(self.index + 1)

    def select_prev(self) -> None:
        self.set_index(self.index - 1)

    def activate(self) -> None:
        if self.buttons:
            self.buttons[self.index].activate()

    #############################################################################################################
    def render(self) -> pygame.Surface:
        surf = self._bg.copy()
        if self._title_surf is not None:
            rect = self._title_surf.get_rect(midtop=(surf.get_width() // 2, _PAD // 2))
            surf.blit(self._title_surf, rect)
        return surf

    def handle_event(self, event: pygame.event.Event) -> bool:
        # the panel owns selection, so it does not delegate to button children
        if event.type == pygame.MOUSEMOTION:
            for i, btn in enumerate(self.buttons):
                if btn.rect.collidepoint(event.pos):
                    self.set_index(i)
                    break
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, btn in enumerate(self.buttons):
                if btn.rect.collidepoint(event.pos):
                    self.set_index(i)
                    self.activate()
                    return True
        return False


#######################################################################################################################
# MARK: MenuScreen


class MenuScreen(State):
    def __init__(self, game, name: str, bg_image: pygame.Surface | None = None) -> None:  # noqa: ANN001
        super().__init__(game)
        self.name = name
        self.bg_image = bg_image
        self.manager = UIManager(game.HUD)
        self.panel = self.build_panel()
        self.manager.add(self.panel)
        self._held: dict[str, bool] = {}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.name}"

    #############################################################################################################
    def build_panel(self) -> MenuPanel:
        raise NotImplementedError("Subclasses must implement build_panel()")

    def on_quit(self) -> None:
        self.game.reset_inputs()
        self.exit_state()

    #############################################################################################################
    def _edge(self, action: str) -> bool:
        """Rising-edge detector so a held key/stick moves the selection only once."""
        value = bool(INPUTS[action])
        fired = value and not self._held.get(action, False)
        self._held[action] = value
        return fired

    def update(self, dt: float, events: list[pygame.event.Event]) -> None:
        self.manager.handle_events(events)

        if self._edge("up"):
            self.panel.select_prev()
        if self._edge("down"):
            self.panel.select_next()
        if self._edge("select") or self._edge("accept"):
            self.game.reset_inputs()
            self.panel.activate()
            return
        if self._edge("quit"):
            self.on_quit()

    def draw(self, screen: pygame.Surface, dt: float) -> None:
        screen.fill((85, 99, 77))
        if self.bg_image:
            screen.blit(self.bg_image, (0, 0))
        self.manager.draw(screen)


#######################################################################################################################
# MARK: MainMenuScreen


class MainMenuScreen(MenuScreen):
    def build_panel(self) -> MenuPanel:
        import scene
        import splash_screen
        from ui.panels.display_settings import DisplaySettingsScreen

        options: list[tuple[str, object]] = [
            ("Play", lambda: scene.Scene(self.game, "Village", "start").enter_state()),
            ("Settings", lambda: DisplaySettingsScreen(self.game, "DisplaySettings", self.bg_image).enter_state()),
            ("About", lambda: AboutMenuScreen(self.game, "AboutMenu", self.bg_image).enter_state()),
        ]
        if not IS_WEB:
            options.append(("Quit", self._quit_game))
        return MenuPanel(options, bg_file="nine_patch_06b.png", anchor="midleft", pos=(60, HEIGHT // 2))

    def _quit_game(self) -> None:
        self.game.is_running = False
        self.exit_state()

    def on_quit(self) -> None:
        if not IS_WEB:
            self._quit_game()


#######################################################################################################################
# MARK: AboutMenuScreen


class AboutMenuScreen(MenuScreen):
    def build_panel(self) -> MenuPanel:
        from settings import ABOUT

        return MenuPanel(
            [("Back", self.on_quit)],
            title="About",
            lines=list(ABOUT),
            bg_file="nine_patch_12b.png",
            anchor="midleft",
            pos=(60, HEIGHT // 2),
        )
