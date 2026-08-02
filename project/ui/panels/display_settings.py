"""Settings panel: resolution, fullscreen, language selector.

Replaces the placeholder "Settings" splash screen in the main menu.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import audio
import pygame
import settings as _settings
from settings import INPUTS, IS_WEB, MENU_FONT, _

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

#: Wiersze głośności: tag wiersza -> (atrybut runtime w `settings`, klucz locale).
#: Kolejność z tabeli jest kolejnością na ekranie.
_VOLUME_TYPES: tuple[str, ...] = ("volume_master", "volume_music", "volume_sfx")
_VOLUME_FIELDS: dict[str, tuple[str, str]] = {
    "volume_master": ("_VOLUME_MASTER", "settings.volume_master"),
    "volume_music": ("_VOLUME_MUSIC", "settings.volume_music"),
    "volume_sfx": ("_VOLUME_SFX", "settings.volume_sfx"),
}

#: E03: nazwa algorytmu mgły -> klucz locale opisujący go w wierszu ustawień.
#: Kolejność w `settings.FOG_ALGORITHM_OPTIONS` jest kolejnością cyklowania.
_FOG_LABELS: dict[str, str] = {
    "off": "settings.fog_off",
    "raycast": "settings.fog_raycast",
    "shadowcast": "settings.fog_shadowcast",
}


# Import settings module for mutable state


class SettingsPanel(Widget):
    """Menu-style panel with resolution, fullscreen and language buttons."""

    def __init__(
        self,
        *,
        anchor: str = "midleft",
        pos: tuple[int, int] | None = None,
        back_callback: Callable[[], object] | None = None,
        apply_callback: Callable[[], object] | None = None,
    ) -> None:
        # viewport-relative default resolved at call time (settings.HEIGHT is mutable)
        if pos is None:
            pos = (60, _settings.HEIGHT // 2)
        self._back_callback = back_callback
        self._apply_callback = apply_callback
        super().__init__()
        self.index: int = 0  # current selection index
        self._anchor: str = anchor
        self._button_types: list[str] = []
        self._buttons: list[Button] = []

        self._render_title()

        self._build_buttons()
        width, height = self._compute_size()
        self.rect = pygame.Rect(0, 0, width, height)
        setattr(self.rect, anchor, pos)
        self._bg = theme.nine_patch("nine_patch_06b.png", width, height)
        self._layout_children()
        self._sync_selection()

    def _render_title(self) -> None:
        """(Re)render the panel title in the current language."""
        self._title_surf = theme.menu_font(_TITLE_SIZE).render(_("settings.title"), False, theme.NAME)

    def _build_buttons(self) -> None:
        """(Re)create the Button widgets and their type tags from current settings."""
        self._button_types.clear()
        self._buttons.clear()

        # Single resolution row - cycled left/right instead of one button per option
        self._buttons.append(Button(self._resolution_label(), None, size=_BUTTON_SIZE))
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

        # Volume rows - same cycled-by-arrows widget as the resolution row above
        for volume_type in _VOLUME_TYPES:
            self._buttons.append(Button(self._volume_label(volume_type), None, size=_BUTTON_SIZE))
            self._button_types.append(volume_type)

        # Fog of war algorithm (E03) - cycled like the rows above
        self._buttons.append(Button(self._fog_label(), None, size=_BUTTON_SIZE))
        self._button_types.append("fog")

        self._buttons.append(Button(_("settings.back"), None, size=_BUTTON_SIZE))
        self._button_types.append("back")

    def _resolution_label(self) -> str:
        """Label for the resolution cycler at the current display index."""
        idx = _settings._DISPLAY_RES_INDEX % len(_settings.DISPLAY_RES_OPTIONS)
        xt, yt = _settings.DISPLAY_RES_OPTIONS[idx]
        return _("settings.resolution", w=xt * _settings.TILE_SIZE, h=yt * _settings.TILE_SIZE)

    def _volume_label(self, volume_type: str) -> str:
        attr, key = _VOLUME_FIELDS[volume_type]
        return _(key, value=int(round(getattr(_settings, attr) * 100)))

    def _fog_label(self) -> str:
        """Label for the fog-of-war cycler at the current algorithm."""
        key = _FOG_LABELS.get(_settings.FOG_ALGORITHM, _FOG_LABELS["off"])
        return _("settings.fog", value=_(key))

    def _cycle_fog(self, step: int) -> None:
        """Switch the fog-of-war algorithm (wrapping) and persist it at once.

        Takes effect on the next frame drawn in a maze - the scene reads
        ``settings.FOG_ALGORITHM`` live (K6), so there is nothing to rebuild and
        nothing to restart. Discovery already made is kept: the mask is repainted
        from the same bitset whatever the algorithm.
        """
        options = _settings.FOG_ALGORITHM_OPTIONS
        try:
            idx = options.index(_settings.FOG_ALGORITHM)
        except ValueError:
            idx = 0
        _settings.FOG_ALGORITHM = options[(idx + step) % len(options)]
        audio.play_sfx("menu_move")
        self._rebuild_buttons()
        save_display_settings()

    def _cycle_volume(self, volume_type: str, step: int) -> None:
        """Move one volume by ``VOLUME_STEP``, clamped to 0-100% (no wrap).

        Wrapping would jump a muted game to full blast on one extra keypress, so
        unlike the resolution cycler this one stops at both ends. The change is
        audible immediately (``audio.set_volumes``) and persisted at once, like
        every other row here.
        """
        attr, _key = _VOLUME_FIELDS[volume_type]
        value = getattr(_settings, attr) + step * _settings.VOLUME_STEP
        # zaokrąglenie do kroku: dodawanie 0.1 w floatach dryfuje (0.7000000000000001)
        value = round(max(0.0, min(1.0, value)) / _settings.VOLUME_STEP) * _settings.VOLUME_STEP
        setattr(_settings, attr, value)
        audio.set_volumes(_settings._VOLUME_MASTER, _settings._VOLUME_MUSIC, _settings._VOLUME_SFX)
        # dźwięk próbki: gracz ma usłyszeć, co właśnie ustawił
        audio.play_sfx("menu_move")
        self._rebuild_buttons()
        save_display_settings()

    def _cycle_resolution(self, step: int) -> None:
        """Move the resolution selection by *step* (wrapping) and apply it."""
        n = len(_settings.DISPLAY_RES_OPTIONS)
        new_idx = (_settings._DISPLAY_RES_INDEX + step) % n
        _settings.set_display(new_idx)
        if self._apply_callback is not None:
            self._apply_callback()
        self._rebuild_buttons()
        save_display_settings()

    def _compute_size(self) -> tuple[int, int]:
        buttons_h = sum(b.rect.height + _GAP for b in self._buttons) + _GAP
        content_w = max(b.rect.width for b in self._buttons) + 2 * _PAD
        width = content_w + 2 * _PAD
        height = buttons_h + 2 * _PAD
        if self._title_surf:
            height += self._title_surf.get_height() + _GAP
        return width, height

    def _layout_children(self) -> None:
        """Position all buttons (centered) as children, top-to-bottom under the title."""
        self.children.clear()
        y = self.rect.top + _PAD
        if self._title_surf:
            y += self._title_surf.get_height() + _GAP
        for btn in self._buttons:
            btn.rect.center = (self.rect.centerx, y + btn.rect.height // 2)
            self.add(btn)
            y += btn.rect.height + _GAP

    def _rebuild_buttons(self) -> None:
        """Recreate all buttons and re-layout after a state change (resolution, etc.).

        Preserves the panel's anchor point so resizing the box does not make it drift -
        setting ``rect.width``/``rect.height`` directly pins the top-left corner, which
        moves a ``midleft``-anchored panel off its position.
        """
        self._render_title()
        self._build_buttons()
        width, height = self._compute_size()
        anchor_pos = getattr(self.rect, self._anchor)
        self.rect.size = (width, height)
        setattr(self.rect, self._anchor, anchor_pos)
        self._bg = theme.nine_patch("nine_patch_06b.png", width, height)
        self._layout_children()
        self._sync_selection()
        self.mark_dirty()

    def rebuild_i18n(self) -> None:
        """Re-apply translations to the title and every button after a language change.

        Called by :class:`MenuScreen` when it detects a runtime language switch (matching
        the same hook on :class:`MenuPanel`), so the settings screen refreshes even when
        the toggle happens elsewhere.
        """
        self._rebuild_buttons()

    def _sync_selection(self) -> None:
        n = len(self._buttons)
        self.index = self.index % n if n > 0 else 0
        for i, btn in enumerate(self._buttons):
            btn.selected = i == self.index

    def set_index(self, index: int) -> None:
        previous = self.index
        self.index = index
        self._sync_selection()
        # dopiero po `_sync_selection` - ono normalizuje indeks modulo liczbę wierszy
        if self.index != previous:
            audio.play_sfx("menu_move")

    def select_next(self) -> None:
        self.set_index(self.index + 1)

    def select_prev(self) -> None:
        self.set_index(self.index - 1)

    def on_left(self) -> None:
        """Left input: step the selected cycler (resolution / volume) back."""
        self._step_selected(-1)

    def on_right(self) -> None:
        """Right input: step the selected cycler (resolution / volume) forward."""
        self._step_selected(1)

    def _step_selected(self, step: int) -> None:
        button_type = self._button_types[self.index]
        if button_type == "resolution":
            self._cycle_resolution(step)
        elif button_type in _VOLUME_FIELDS:
            self._cycle_volume(button_type, step)
        elif button_type == "fog":
            self._cycle_fog(step)

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
                    # On a cycled row (resolution, volumes), a click on the left half
                    # steps back and the right half steps forward (matching the
                    # "< ... >" arrows in the label).
                    if (self._button_types[i] in ("resolution", "fog")
                            or self._button_types[i] in _VOLUME_FIELDS):
                        self._step_selected(-1 if event.pos[0] < child.rect.centerx else 1)
                    else:
                        self.activate()
                    return True
        return False

    def activate(self) -> None:
        bt = self._button_types[self.index]
        if bt == "resolution":
            # Keyboard/gamepad accept cycles forward; left/right give both directions.
            self._cycle_resolution(1)
        elif bt in _VOLUME_FIELDS:
            self._cycle_volume(bt, 1)
        elif bt == "fog":
            self._cycle_fog(1)
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
                    pos=(60, _settings.HEIGHT // 2),
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
