"""Main menu and About screens, built on the toolkit (replaces menus.py + pygame_menu).

A :class:`MenuPanel` is a bordered box with an optional title, optional static text
lines, and a vertical list of selectable buttons. :class:`MenuScreen` is the ``State``
that owns one panel and drives selection from the game's action inputs (so keyboard and
gamepad both work via the same ``INPUTS`` abstraction).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pygame
from objects import NotificationTypeEnum
from settings import VERSION, HEIGHT, INPUTS, IS_WEB, MENU_FONT, WIDTH, LANG, _
from state import State

from .. import theme
from ..manager import UIManager
from ..widget import Widget
from ..widgets import Button, Label

if TYPE_CHECKING:
    import game

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
        title_key: str | None = None,
        lines: list[str] | None = None,
        line_keys: list[str | tuple[str, dict[str, object]]] | None = None,
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
        self._i18n_keys: list[str] = [key for key, _ in options]  # type: ignore[misc]
        self._title_key: str | None = title_key
        self._title_size: int = title_size
        self._line_keys: list[str | tuple[str, dict[str, object]]] = line_keys or []
        self._line_size: int = line_size
        self._bg_file: str = bg_file

        self.buttons: list[Button] = [
            Button(_(key), cb, size=button_size)
            for key, cb in options  # type: ignore[arg-type]
        ]
        if lines is not None:
            self.line_labels: list[Label] = [
                Label(text, size=line_size, font_path=str(MENU_FONT)) for text in lines
            ]
            self._lines_are_keys = False
        else:
            self.line_labels = [
                Label(_(spec if isinstance(spec, str) else spec[0], **(spec[1] if isinstance(spec, tuple) else {})),
                      size=line_size, font_path=str(MENU_FONT))
                for spec in (line_keys or [])
            ]
            self._lines_are_keys = True

        title_text = title
        if title_text is None and title_key is not None:
            title_text = _(title_key)
        self._title_surf = theme.menu_font(title_size).render(title_text, False, theme.NAME) if title_text else None

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
    def _relayout(self) -> None:
        title_h = (self._title_surf.get_height() + _GAP) if self._title_surf else 0
        lines_h = sum(lbl.rect.height + 4 for lbl in self.line_labels)
        buttons_h = sum(b.rect.height + _GAP for b in self.buttons)
        content_w = max(
            [b.rect.width for b in self.buttons] + [lbl.rect.width for lbl in self.line_labels]
        )
        width = content_w + 2 * _PAD
        height = title_h + lines_h + buttons_h + 2 * _PAD
        old_center = self.rect.center
        self.rect.size = (width, height)
        self.rect.center = old_center
        self._bg = theme.nine_patch(self._bg_file, width, height)
        self.children.clear()
        self._layout_children()
        self.mark_dirty()

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

    def rebuild_i18n(self) -> None:
        """Re-apply _() to all button labels, title and lines after language change."""
        for btn, key in zip(self.buttons, self._i18n_keys):
            btn.set_text(_(key))
        if self._title_key is not None:
            self._title_surf = theme.menu_font(self._title_size).render(
                _(self._title_key), False, theme.NAME
            )
        if self._lines_are_keys:
            for i, line_spec in enumerate(self._line_keys):
                if isinstance(line_spec, tuple):
                    key, kw = line_spec
                    text = _(key, **kw)
                else:
                    text = _(line_spec)
                if i < len(self.line_labels):
                    self.line_labels[i].set_text(text)
        self._relayout()

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
    def __init__(self, game: game.Game, name: str, bg_image: pygame.Surface | None = None) -> None:
        super().__init__(game)
        self.name = name
        self.bg_image = bg_image
        self.manager = UIManager(game.HUD)
        self.panel = self.build_panel()
        self.manager.add(self.panel)
        self._held: dict[str, bool] = {}
        self._last_lang: str = LANG

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

        # Rebuild button labels if language changed at runtime
        if LANG != self._last_lang:
            self._last_lang = LANG
            self.panel.rebuild_i18n()

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
# MARK: LoadMenuScreen helpers


class _LoadUIManagerProxy:
    """Minimal ``scene.ui`` stand-in so :class:`LoadPanel` can close itself in a menu."""

    def __init__(self, manager: UIManager) -> None:
        self._manager = manager

    def close(self, panel_type: type) -> None:
        for widget in list(self._manager.widgets):
            if isinstance(widget, panel_type):
                assert isinstance(widget, Widget)
                self._manager.remove(widget)
                widget.visible = False
                break


class _LoadSceneProxy:
    """Minimal ``scene`` stand-in for :class:`LoadPanel` when no real Scene exists yet."""

    def __init__(self, game: game.Game, manager: UIManager) -> None:
        self.game = game
        self.ui = _LoadUIManagerProxy(manager)

    def add_notification(self, text: str, notification_type: NotificationTypeEnum) -> None:
        # Notifications are not shown over the main menu; loading will switch to the game.
        pass


class LoadMenuScreen(State):
    """Menu state that hosts the existing LoadPanel without creating a Scene first."""

    def __init__(self, game: game.Game, bg_image: pygame.Surface | None = None) -> None:
        super().__init__(game)
        self.bg_image = bg_image
        self.manager = UIManager(game.HUD)
        self._scene_proxy = _LoadSceneProxy(game, self.manager)
        from ui.panels.save_load import LoadPanel

        self._load_panel = LoadPanel(self._scene_proxy, None, on_load=self._on_load)  # type: ignore[arg-type]
        self.manager.add(self._load_panel)
        self._load_panel.open()

    def _on_load(self, slot_idx: int) -> None:
        # SaveManager.load pushed a new Scene on top. Collapse the stack to
        # [MainMenuScreen, Scene] so the game resumes but Esc still returns to the main
        # menu. Previously we kept only the Scene, leaving a stack of length 1, so Esc
        # in the loaded game quit the whole game instead of showing the menu.
        if not self.game.states:
            return
        new_scene = self.game.states[-1]
        menu = next((s for s in self.game.states if type(s).__name__ == "MainMenuScreen"), None)
        if menu is not None and menu is not new_scene:
            self.game.states[:] = [menu, new_scene]
        else:
            self.game.states[:] = [new_scene]

    def _on_cancel(self) -> None:
        # the LoadPanel consumed the Esc *pygame event*, but INPUTS["quit"] is still set;
        # clear it so the MainMenuScreen underneath doesn't read it next frame and quit.
        self.game.reset_inputs()
        self.exit_state()

    def update(self, dt: float, events: list[pygame.event.Event]) -> None:
        self.manager.handle_events(events)
        self.manager.update(dt)
        if self._load_panel not in self.manager.widgets:
            self._on_cancel()

    def draw(self, screen: pygame.Surface, dt: float) -> None:
        screen.fill((85, 99, 77))
        if self.bg_image:
            screen.blit(self.bg_image, (0, 0))
        self.manager.draw(screen)


#######################################################################################################################
# MARK: MainMenuScreen


class MainMenuScreen(MenuScreen):
    def _is_game_in_progress(self) -> bool:
        import scene

        return any(isinstance(state, scene.Scene) for state in self.game.states)

    def build_panel(self) -> MenuPanel:
        import scene
        import splash_screen
        from ui.panels.display_settings import SettingsMenu

        options: list[tuple[str, object]] = []

        if self._is_game_in_progress():
            options.append(("menu.continue", self._continue_game))

        if self._has_saved_games():
            options.append(("menu.load", lambda: self._open_load_panel()))
        options.extend([
            ("menu.new_game", lambda: scene.Scene(self.game, "Village", "start").enter_state()),
            ("menu.settings", lambda: SettingsMenu(self.game, _("menu.settings"), self.bg_image).enter_state()),
            ("menu.about", lambda: AboutMenuScreen(self.game, "AboutMenu", self.bg_image).enter_state()),
        ])
        if not IS_WEB:
            options.append(("menu.quit", self._quit_game))
        return MenuPanel(options, bg_file="nine_patch_06b.png", anchor="midleft", pos=(60, HEIGHT // 2))

    def _has_saved_games(self) -> bool:
        slots = self.game.save_manager.list_slots()
        return any(slot is not None and slot.is_occupied for slot in slots)

    def _continue_game(self) -> None:
        self.exit_state()

    def _open_load_panel(self) -> None:
        LoadMenuScreen(self.game, self.bg_image).enter_state()

    def _quit_game(self) -> None:
        self.game.is_running = False
        self.exit_state()

    def on_quit(self) -> None:
        if not IS_WEB:
            self._quit_game()


#######################################################################################################################
# MARK: ConfirmMenuScreen


class ConfirmMenuScreen(MenuScreen):
    """Generic Yes/No confirmation shown on top of the current state.

    Pushed as a state, so the state underneath is frozen while it is up. ``Yes`` pops
    the dialog and runs ``on_confirm``; ``No``/Esc just pops it. Used e.g. for the
    irreversible in-game map reload (R).
    """

    def __init__(
        self,
        game: game.Game,
        message: str,
        on_confirm: Callable[[], None],
        bg_image: pygame.Surface | None = None,
    ) -> None:
        self._message = message
        self._on_confirm = on_confirm
        super().__init__(game, "Confirm", bg_image)
        # default the selection to "No" - this guards destructive actions from a stray Enter
        self.panel.set_index(1)

    def build_panel(self) -> MenuPanel:
        # message goes in `lines` (not `title`) because MenuPanel sizes its width to the
        # lines/buttons - a long title would overflow the panel background.
        return MenuPanel(
            [("menu.yes", self._on_yes), ("menu.no", self._on_no)],
            title_key="menu.confirm",
            lines=[self._message],
            bg_file="nine_patch_12b.png",
            anchor="center",
            pos=(WIDTH // 2, HEIGHT // 2),
            line_size=20,
        )

    def _on_yes(self) -> None:
        self.exit_state()
        self._on_confirm()

    def _on_no(self) -> None:
        self.exit_state()


#######################################################################################################################
# MARK: AboutMenuScreen


class AboutMenuScreen(MenuScreen):
    def build_panel(self) -> MenuPanel:
        return MenuPanel(
            [("menu.back", self.on_quit)],
            title_key="menu.about",
            line_keys=[
                ("menu.about_version", {"version": VERSION}),
                "menu.about_author",
                "menu.about_www",
            ],
            bg_file="nine_patch_12b.png",
            anchor="midleft",
            pos=(60, HEIGHT // 2),
        )
