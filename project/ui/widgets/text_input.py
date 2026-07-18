"""TextInput: a focusable single-line text field for the UI toolkit.

A retained-mode :class:`Widget` that lets the player type text from the keyboard:
click to focus, a blinking caret, character insertion via ``pygame.TEXTINPUT`` and
editing/navigation via ``pygame.KEYDOWN`` (backspace/delete, arrows, home/end, enter,
ctrl+v paste). It is heavily parameterised so the same widget can back a character
name, a save-slot name, a password field or a numeric field.

Styling mirrors :class:`Label` / :class:`Button`: the pixel font from
``theme.get_font`` with a drop shadow, and every colour pulled from ``theme`` so the
field sits visually with the rest of the UI.

Character insertion is driven by ``pygame.TEXTINPUT`` (SDL's text-input event), which
handles keyboard layouts / IME correctly and works both on desktop and in pygbag
(SDL's emscripten backend emits ``TEXTINPUT``). Synthetic key events posted by
``agent_ctrl`` do *not* generate ``TEXTINPUT`` on their own, so the agent test harness
posts ``TEXTINPUT`` events directly (see the ``type:`` command in ``agent_ctrl``).
"""
from __future__ import annotations

import string
from enum import Enum
from typing import Callable

import pygame

from settings import FONT_SIZE_MEDIUM, MAIN_FONT, PANEL_BG_COLOR

from ..theme import NAME, TEXT, get_font
from ..widget import Widget

# characters accepted by the LATIN class in addition to A-Z / a-z (useful for names)
_LATIN_EXTRA = " -'"
# glyph used to mask characters in password mode (plain ASCII, guaranteed by the font)
_PASSWORD_MASK = "*"


#######################################################################################################################
# MARK: CharSet


class CharSet(Enum):
    """Classes of characters a :class:`TextInput` will accept.

    ``LATIN`` is an *explicit* whitelist of ASCII letters (plus space/hyphen/apostrophe
    for names). This is deliberate: the pixel font renders some non-Latin glyphs, but
    the game standardises on the Latin alphabet, so the filter must not depend on the
    font's glyph coverage. Add a new class here (or pass ``predicate=`` to the widget)
    to extend the set.
    """

    ANY = "any"
    ALPHANUMERIC = "alphanumeric"
    ALPHA = "alpha"
    LATIN = "latin"
    DIGITS = "digits"

    def allows(self, ch: str) -> bool:
        """Return ``True`` if the single character ``ch`` is accepted by this class."""
        if not ch or ch < " ":  # reject control characters regardless of class
            return False
        if self is CharSet.ANY:
            return ch.isprintable()
        if self is CharSet.DIGITS:
            return ch in string.digits
        if self is CharSet.LATIN:
            return ch in string.ascii_letters or ch in _LATIN_EXTRA
        if self is CharSet.ALPHA:
            return ch.isalpha()
        if self is CharSet.ALPHANUMERIC:
            return ch.isalnum()
        return False


#######################################################################################################################
# MARK: helpers


def _dim(color: pygame._common.ColorValue, factor: float) -> tuple[int, int, int]:
    """Return ``color`` scaled towards black by ``factor`` (kept opaque)."""
    c = pygame.Color(color)
    return (int(c.r * factor), int(c.g * factor), int(c.b * factor))


#######################################################################################################################
# MARK: TextInput


class TextInput(Widget):
    def __init__(
        self,
        pos: tuple[int, int] = (0, 0),
        *,
        width: int = 240,
        max_length: int | None = None,
        charset: CharSet = CharSet.ANY,
        predicate: Callable[[str], bool] | None = None,
        password: bool = False,
        placeholder: str = "",
        size: int = FONT_SIZE_MEDIUM,
        color: pygame._common.ColorValue = TEXT,
        font_path: str = str(MAIN_FONT),
        anchor: str = "topleft",
        on_change: Callable[[str], None] | None = None,
        on_submit: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self._text = ""
        self._caret = 0
        self._focused = False
        self._blink_timer = 0.0
        self._blink_on = True

        self._max_length = max_length
        self._charset = charset
        self._predicate = predicate
        self._password = password
        self._placeholder = placeholder
        self._size = size
        self._color = color
        self._font_path = font_path
        self._anchor = anchor
        self._on_change = on_change
        self._on_submit = on_submit

        # padding + fixed height derived from the font so it lines up with Label/Button
        self._pad = (8, 6)
        line_h = self.font.get_height()
        self.rect.size = (width, line_h + 2 * self._pad[1])
        setattr(self.rect, anchor, pos)

    #############################################################################################################
    # MARK: public API

    @property
    def font(self) -> pygame.font.Font:
        return get_font(self._size, font_path=self._font_path)

    @property
    def value(self) -> str:
        """The real text entered (never masked, even in password mode)."""
        return self._text

    @property
    def focused(self) -> bool:
        return self._focused

    def set_focus(self, value: bool) -> None:
        if value == self._focused:
            return
        self._focused = value
        if value:
            self._set_text_input(True)
            self._blink_on = True
            self._blink_timer = 0.0
        else:
            self._set_text_input(False)
        self.mark_dirty()

    @staticmethod
    def _set_text_input(active: bool) -> None:
        """Toggle SDL text input, guarded for backends (pygbag) that may lack it."""
        try:
            if active:
                pygame.key.start_text_input()
            else:
                pygame.key.stop_text_input()
        except (AttributeError, pygame.error):
            pass

    def set_text(self, text: str) -> None:
        text = "".join(c for c in str(text) if self._accepts(c))
        if self._max_length is not None:
            text = text[: self._max_length]
        if text != self._text:
            self._text = text
            self._caret = len(text)
            self._emit_change()
            self.mark_dirty()

    def clear(self) -> None:
        self.set_text("")

    #############################################################################################################
    # MARK: editing helpers

    def _accepts(self, ch: str) -> bool:
        if self._predicate is not None:
            return self._predicate(ch)
        return self._charset.allows(ch)

    def _emit_change(self) -> None:
        if self._on_change is not None:
            self._on_change(self._text)

    def _insert(self, chars: str) -> None:
        changed = False
        for ch in chars:
            if not self._accepts(ch):
                continue
            if self._max_length is not None and len(self._text) >= self._max_length:
                break
            self._text = self._text[: self._caret] + ch + self._text[self._caret:]
            self._caret += 1
            changed = True
        if changed:
            self._show_caret()
            self._emit_change()
            self.mark_dirty()

    def _backspace(self) -> None:
        if self._caret > 0:
            self._text = self._text[: self._caret - 1] + self._text[self._caret:]
            self._caret -= 1
            self._show_caret()
            self._emit_change()
            self.mark_dirty()

    def _delete(self) -> None:
        if self._caret < len(self._text):
            self._text = self._text[: self._caret] + self._text[self._caret + 1:]
            self._show_caret()
            self._emit_change()
            self.mark_dirty()

    def _move_caret(self, to: int) -> None:
        to = max(0, min(len(self._text), to))
        if to != self._caret:
            self._caret = to
            self._show_caret()
            self.mark_dirty()

    def _show_caret(self) -> None:
        """Reset the blink so the caret is solid right after an edit/move."""
        self._blink_on = True
        self._blink_timer = 0.0

    def _paste(self) -> None:
        try:
            raw = pygame.scrap.get(pygame.SCRAP_TEXT)  # type: ignore[attr-defined]
        except (pygame.error, AttributeError, NotImplementedError):
            return
        if not raw:
            return
        text = raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else str(raw)
        self._insert(text.replace("\x00", "").replace("\n", " ").replace("\r", ""))

    #############################################################################################################
    # MARK: events

    def _on_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            inside = self.rect.collidepoint(event.pos)
            self.set_focus(inside)
            return inside

        if not self._focused:
            return False

        if event.type == pygame.TEXTINPUT:
            self._insert(event.text)
            return True

        if event.type == pygame.KEYDOWN:
            return self._on_keydown(event)

        return False

    def _on_keydown(self, event: pygame.event.Event) -> bool:
        key = event.key
        if key == pygame.K_BACKSPACE:
            self._backspace()
        elif key == pygame.K_DELETE:
            self._delete()
        elif key == pygame.K_LEFT:
            self._move_caret(self._caret - 1)
        elif key == pygame.K_RIGHT:
            self._move_caret(self._caret + 1)
        elif key == pygame.K_HOME:
            self._move_caret(0)
        elif key == pygame.K_END:
            self._move_caret(len(self._text))
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if self._on_submit is not None:
                self._on_submit(self._text)
        elif key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
            self._paste()
        elif key == pygame.K_ESCAPE:
            self.set_focus(False)
            return False  # let the containing panel also react to Escape
        else:
            # printable characters arrive via TEXTINPUT, not here; swallow the rest
            # so keystrokes don't leak to widgets/state behind a focused field.
            return True
        return True

    #############################################################################################################
    # MARK: update / render

    def update(self, dt: float) -> None:
        super().update(dt)
        if not self._focused:
            return
        self._blink_timer += dt
        if self._blink_timer >= 0.5:
            self._blink_timer -= 0.5
            self._blink_on = not self._blink_on
            self.mark_dirty()

    def _display_text(self) -> str:
        return _PASSWORD_MASK * len(self._text) if self._password else self._text

    def render(self) -> pygame.Surface:
        surf = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        border = NAME if self._focused else _dim(TEXT, 0.45)

        pygame.draw.rect(surf, PANEL_BG_COLOR, surf.get_rect())
        pygame.draw.rect(surf, border, surf.get_rect(), width=2)

        font = self.font
        px, py = self._pad
        display = self._display_text()

        if not display and not self._focused and self._placeholder:
            ph = font.render(self._placeholder, False, _dim(TEXT, 0.5))
            surf.blit(ph, (px, py))
            return surf

        # drop shadow (mirrors Label) then the text itself
        if display:
            shadow = font.render(display, False, _dim(self._color, 0.25))
            surf.blit(shadow, (px + 2, py + 2))
            text_surf = font.render(display, False, self._color)
            surf.blit(text_surf, (px, py))

        if self._focused and self._blink_on:
            caret_x = px + font.size(display[: self._caret])[0]
            pygame.draw.rect(surf, NAME, (caret_x, py, 2, font.get_height()))

        return surf
