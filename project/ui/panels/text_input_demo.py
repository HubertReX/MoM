"""TextInputDemoState: a throwaway state that showcases the TextInput widget.

Pushed on the state stack by the agent-control command ``debug_text_input`` (see
``agent_ctrl``). It lays out several :class:`TextInput` fields with different
configurations - free text, digits-only, password, Latin-only - so the widget can be
verified manually and by the automated agent test harness (``TextInput Basic``
scenario). ``up`` / ``down`` cycle focus between fields; every other event is routed to
the focused field. ``Escape`` closes the state.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from settings import HEIGHT, WIDTH, _

from .. import theme
from ..widgets import CharSet, Label, TextInput

if TYPE_CHECKING:
    from game import Game

from state import State as _State

_FIELD_WIDTH = 320
_ROW_H = 64


class TextInputDemoState(_State):
    def __init__(self, game: "Game") -> None:
        super().__init__(game)
        self.name = "TextInputDemoState"

        bg_w, bg_h = 620, 420
        self._bg = theme.nine_patch("nine_patch_04.png", bg_w, bg_h)
        self._bg_rect = self._bg.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        self._title_surf = theme.menu_font(40).render(_("text_demo.title"), False, theme.NAME)

        # (label, kwargs) for each demonstrated configuration
        specs = [
            (_("text_demo.field_any"), dict(charset=CharSet.ANY, placeholder=_("text_demo.ph_any"))),
            (_("text_demo.field_digits"), dict(charset=CharSet.DIGITS, max_length=6, placeholder=_("text_demo.ph_digits"))),
            (_("text_demo.field_password"), dict(password=True, placeholder=_("text_demo.ph_password"))),
            (_("text_demo.field_latin"), dict(charset=CharSet.LATIN, placeholder=_("text_demo.ph_latin"))),
        ]
        self._labels: list[Label] = []
        self._fields: list[TextInput] = []
        x_label = self._bg_rect.left + 30
        x_field = self._bg_rect.left + 190
        y = self._bg_rect.top + 90
        for text, kwargs in specs:
            self._labels.append(Label(text, (x_label, y + 6)))
            self._fields.append(TextInput((x_field, y), width=_FIELD_WIDTH, **kwargs))  # type: ignore[arg-type]
            y += _ROW_H

        self._focus_idx = 0
        self._fields[0].set_focus(True)

    #############################################################################################################
    def _cycle_focus(self, delta: int) -> None:
        self._fields[self._focus_idx].set_focus(False)
        self._focus_idx = (self._focus_idx + delta) % len(self._fields)
        self._fields[self._focus_idx].set_focus(True)

    #############################################################################################################
    def update(self, dt: float, events: list[pygame.event.Event]) -> None:
        for field in self._fields:
            field.update(dt)

        for event in events:
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_TAB):
                self._cycle_focus(-1 if event.key == pygame.K_UP else 1)
                continue
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._fields[self._focus_idx].set_focus(False)
                self.exit_state()
                return
            self._fields[self._focus_idx].handle_event(event)

    #############################################################################################################
    def draw(self, screen: pygame.Surface, dt: float) -> None:
        screen.fill((0, 0, 0))
        screen.blit(self._bg, self._bg_rect.topleft)
        tr = self._title_surf.get_rect(midtop=(self._bg_rect.centerx, self._bg_rect.top + 24))
        screen.blit(self._title_surf, tr)

        for label, field in zip(self._labels, self._fields):
            label.draw(screen)
            field.draw(screen)
