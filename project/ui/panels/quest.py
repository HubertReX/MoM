"""QuestPanel: the quest journal, toggled with J (decision D14).

Built to the mock in section 6 of ``doc/_attachements/quest-system-ssis-2026-07-16.html``
— its coordinates, sizes and palette are the spec, not a suggestion.

Two columns: threads on the left, details of the selected one on the right.
Nothing here decides *what* the player may know: **locked steps stay visible**
(the ``○`` rows). Pacing the story is the author's job — if a step title gives
too much away it gets rewritten, it does not get hidden. The panel has no idea
what the writer intended and should not pretend otherwise.

i18n split (D3): panel furniture (WĄTKI, KROKI, NAGRODA) is UI text and comes from
the TOML via ``_()``; quest titles and descriptions are *content* and come from
``config.json["messages"]`` via ``get_msg()``. The two never mix.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from quest.engine import is_unlocked, quest_progress
from quest.entities import CompletionMode, QuestDef
from quest.graph import children_of
from quest.rewards import format_reward_label
from settings import (
    FONT_SIZE_LARGE,
    FONT_SIZE_MEDIUM,
    FONT_SIZE_SMALL,
    FONT_SIZE_TINY,
    _,
    entity_name,
    get_msg,
)

from .. import theme
from ..widget import Widget

if TYPE_CHECKING:
    from scene import Scene

    from .hud import HUD

# --- geometry, straight from the mock ---------------------------------------
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 90, 60, 1100, 600
_HEADER_Y = 88
_RULE_Y = 128
_SPLIT_X = 470
_FOOTER_Y = 628
_LEFT_X = 118
_RIGHT_X = 500
_RIGHT_EDGE = 1160
_ROW_H = 30
_STEP_INDENT = 42
_LIST_TOP = 168
_LIST_BOTTOM = _FOOTER_Y - 8

# --- palette, straight from the mock ----------------------------------------
_GOLD = (255, 215, 0)
_TITLE = (255, 252, 103)
_DONE = (110, 207, 104)
_ACTIVE = (0, 197, 199)
_LOCKED = (90, 90, 86)
_MUTED = (138, 138, 134)
_LABEL = (107, 107, 102)
_WHITE = (255, 255, 255)
_RULE = (68, 68, 68)
_BAR_BG = (51, 51, 51)
_MANUAL = (232, 146, 12)

_FILTERS = ("active", "done", "all")


@dataclass(slots=True)
class _Row:
    """One line in the left column."""

    key: str
    depth: int  # 0 = thread head, 1 = step
    is_thread: bool


class QuestPanel(Widget):
    def __init__(self, scene: "Scene", hud: "HUD") -> None:
        super().__init__()
        self.scene = scene
        self.hud = hud
        self.bg = theme.nine_patch("nine_patch_04.png", PANEL_W, PANEL_H)
        self.rect = self.bg.get_rect(topleft=(PANEL_X, PANEL_Y))
        self.filter_idx = 0
        self.selected = 0
        # Threads start expanded: the journal's job is to show the work, and a
        # panel that opens on a list of closed folders answers no question.
        self.collapsed: set[str] = set()
        self._rows: list[_Row] = []

    # --- data ---------------------------------------------------------------

    @property
    def _defs(self) -> dict[str, QuestDef]:
        return self.scene.quests.defs

    def _done(self, key: str) -> bool:
        return self.scene.quest_state.is_done(key)

    def _unlocked(self, key: str) -> bool:
        return is_unlocked(self._defs, self.scene.quest_state, key)

    def _thread_matches_filter(self, key: str) -> bool:
        mode = _FILTERS[self.filter_idx]
        if mode == "all":
            return True
        if mode == "done":
            return self._done(key)
        # "active": what the player can work on now. A thread counts as active
        # while any part of it is still open, so a finished step does not hide
        # the rest of its chain.
        if self._done(key):
            return False
        return self._unlocked(key)

    def _rebuild(self) -> None:
        """Flatten the quest graph into the visible list of rows."""
        defs = self._defs
        rows: list[_Row] = []
        for key, quest in defs.items():
            if quest.parent is not None:
                continue  # steps are emitted under their thread
            if not self._thread_matches_filter(key):
                continue
            children = children_of(defs, key)
            rows.append(_Row(key, 0, bool(children)))
            if children and key not in self.collapsed:
                rows.extend(_Row(child, 1, False) for child in children)
        self._rows = rows
        self.selected = max(0, min(self.selected, len(rows) - 1))

    def open(self) -> None:
        self.selected = 0
        self._rebuild()

    # --- input --------------------------------------------------------------

    def select_next(self) -> None:
        if self._rows:
            self.selected = (self.selected + 1) % len(self._rows)

    def select_prev(self) -> None:
        if self._rows:
            self.selected = (self.selected - 1) % len(self._rows)

    def next_filter(self) -> None:
        self.filter_idx = (self.filter_idx + 1) % len(_FILTERS)
        self.selected = 0
        self._rebuild()

    def prev_filter(self) -> None:
        self.filter_idx = (self.filter_idx - 1) % len(_FILTERS)
        self.selected = 0
        self._rebuild()

    def toggle_expand(self) -> None:
        row = self._current_row()
        if row is None or not row.is_thread:
            return
        if row.key in self.collapsed:
            self.collapsed.discard(row.key)
        else:
            self.collapsed.add(row.key)
        self._rebuild()

    def _current_row(self) -> _Row | None:
        if not self._rows or not 0 <= self.selected < len(self._rows):
            return None
        return self._rows[self.selected]

    # --- drawing ------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        # rebuilt every frame: quests complete while the panel is open (the sweep
        # runs regardless), and a stale list would quietly lie about the state
        self._rebuild()

        surface.blit(self.bg, self.rect.topleft)
        pygame.draw.rect(surface, _GOLD, self.rect, width=3, border_radius=6)
        self._draw_header(surface)
        pygame.draw.line(surface, _RULE, (PANEL_X, _RULE_Y), (PANEL_X + PANEL_W, _RULE_Y), 2)
        pygame.draw.line(surface, _RULE, (_SPLIT_X, _RULE_Y), (_SPLIT_X, _FOOTER_Y), 2)
        self._draw_list(surface)
        self._draw_details(surface)
        pygame.draw.line(surface, _RULE, (PANEL_X, _FOOTER_Y), (PANEL_X + PANEL_W, _FOOTER_Y), 2)
        self._text(surface, _("quest.hints"), (_LEFT_X, _FOOTER_Y + 10), FONT_SIZE_SMALL, _MUTED)

    def _draw_header(self, surface: pygame.Surface) -> None:
        title = _("quest.journal")
        self._text(surface, title, (_LEFT_X, _HEADER_Y), FONT_SIZE_LARGE, _TITLE)

        # Filters first: they are right-aligned as a block (so the last one cannot
        # fall off the panel) and everything else in the header has to fit in
        # whatever room they leave.
        font = self._font(FONT_SIZE_SMALL)
        labels = [_(f"quest.filter_{name}") for name in _FILTERS]
        gap = 26
        total_w = sum(font.size(text)[0] for text in labels) + gap * (len(labels) - 1)
        filters_x = PANEL_X + PANEL_W - 28 - total_w

        total = len(self._defs)
        done = sum(1 for key in self._defs if self._done(key))
        # measured, not a fixed offset: the mock was drawn in a proportional font
        # and MoM renders in a wide pixel one, where a hardcoded x puts the count
        # straight through the title
        counter_x = _LEFT_X + self._font(FONT_SIZE_LARGE).size(title)[0] + 24
        # tiny, not small: the mock sized this for a proportional font, and in MoM's
        # wider pixel font the sentence gets chopped to "4 uko..." at small
        self._text(
            surface,
            self._truncate(
                _("quest.counter", total=total, done=done),
                filters_x - counter_x - 20,
                FONT_SIZE_TINY,
            ),
            (counter_x, _HEADER_Y + 14),
            FONT_SIZE_TINY,
            _MUTED,
        )

        x = filters_x
        for idx, label in enumerate(labels):
            active = idx == self.filter_idx
            self._text(surface, label, (x, _HEADER_Y + 8), FONT_SIZE_SMALL, _TITLE if active else _MUTED)
            width = font.size(label)[0]
            if active:
                pygame.draw.line(surface, _GOLD, (x, _HEADER_Y + 28), (x + width, _HEADER_Y + 28), 2)
            x += width + gap

    def _draw_list(self, surface: pygame.Surface) -> None:
        self._text(surface, _("quest.threads"), (_LEFT_X, _LIST_TOP - 26), FONT_SIZE_TINY, _LABEL)

        y = _LIST_TOP
        for idx, row in enumerate(self._rows):
            if y + _ROW_H > _LIST_BOTTOM:
                break  # the list is taller than the panel; the rest is off-view
            if idx == self.selected:
                # left column only: a band across the whole panel would underline
                # the details pane too, which belongs to this row rather than
                # being another choice in the list
                width = _SPLIT_X - PANEL_X - 8
                highlight = pygame.Surface((width, _ROW_H), pygame.SRCALPHA)
                highlight.fill((*_GOLD, 36))
                surface.blit(highlight, (PANEL_X + 4, y))
                pygame.draw.rect(surface, _GOLD, (PANEL_X + 4, y, 3, _ROW_H))

            quest = self._defs[row.key]
            indent = _STEP_INDENT if row.depth else 0
            colour = self._state_colour(row.key)

            if row.is_thread:
                self._draw_caret(
                    surface, _LEFT_X + indent, y + 6,
                    row.key not in self.collapsed, _DONE if self._done(row.key) else _ACTIVE,
                )
            else:
                self._draw_marker(surface, _LEFT_X + indent, y + 6, row.key)

            badge = self._thread_badge(row.key, quest) if row.is_thread else ""
            name_x = _LEFT_X + indent + 24
            # reserve room for the badge, or a long title runs under it and on
            # past the divider into the details pane
            name_room = _SPLIT_X - 16 - name_x - (self._font(FONT_SIZE_TINY).size(badge)[0] + 8 if badge else 0)
            name = self._truncate(get_msg(self._messages, quest.name), name_room, FONT_SIZE_SMALL)
            self._text(
                surface, name, (name_x, y + 6), FONT_SIZE_SMALL,
                _TITLE if idx == self.selected else colour,
            )

            if badge:
                colour = _MANUAL if quest.completion is CompletionMode.manual else _ACTIVE
                self._text(surface, badge, (_SPLIT_X - 20, y + 9), FONT_SIZE_TINY, colour, align="right")
            y += _ROW_H

    def _thread_badge(self, key: str, quest: QuestDef) -> str:
        """A thread's progress ('2/3'), or its 'manual' tag — shown right of the title."""
        if quest.completion is CompletionMode.manual:
            return _("quest.manual")
        progress = self._progress(key)
        return f"{progress[0]}/{progress[1]}" if progress else ""

    def _draw_details(self, surface: pygame.Surface) -> None:
        row = self._current_row()
        self._text(surface, _("quest.details"), (_RIGHT_X, _LIST_TOP - 26), FONT_SIZE_TINY, _LABEL)
        if row is None:
            self._text(surface, _("quest.empty"), (_RIGHT_X, _LIST_TOP + 20), FONT_SIZE_SMALL, _MUTED)
            return

        quest = self._defs[row.key]
        y = _LIST_TOP - 6
        title = self._truncate(get_msg(self._messages, quest.name), _RIGHT_EDGE - _RIGHT_X, FONT_SIZE_MEDIUM)
        self._text(surface, title, (_RIGHT_X, y), FONT_SIZE_MEDIUM, _TITLE)

        y += 34
        description = get_msg(self._messages, quest.description)
        for line in self._wrap(description, _RIGHT_EDGE - _RIGHT_X, FONT_SIZE_SMALL):
            self._text(surface, line, (_RIGHT_X, y), FONT_SIZE_SMALL, _WHITE)
            y += 24

        children = children_of(self._defs, row.key)
        if children:
            y = self._draw_steps(surface, row.key, children, y + 26)

        self._draw_rewards(surface, quest, y + 26)

    def _draw_steps(self, surface: pygame.Surface, key: str, children: list[str], y: int) -> int:
        self._text(surface, _("quest.steps"), (_RIGHT_X, y), FONT_SIZE_TINY, _LABEL)
        progress = self._progress(key)
        if progress:
            current, total = progress
            self._text(
                surface, f"{current} / {total}", (_RIGHT_EDGE, y), FONT_SIZE_SMALL, _ACTIVE, align="right"
            )
            bar_y = y + 20
            pygame.draw.rect(surface, _BAR_BG, (_RIGHT_X, bar_y, 660, 8), border_radius=4)
            if total:
                filled = int(660 * current / total)
                if filled:
                    pygame.draw.rect(surface, _ACTIVE, (_RIGHT_X, bar_y, filled, 8), border_radius=4)
            y = bar_y + 26

        for child in children:
            self._draw_marker(surface, _RIGHT_X, y, child)
            name = self._truncate(
                get_msg(self._messages, self._defs[child].name), _RIGHT_EDGE - _RIGHT_X - 24, FONT_SIZE_SMALL
            )
            self._text(surface, name, (_RIGHT_X + 24, y), FONT_SIZE_SMALL, self._state_colour(child))
            y += 28
        return y

    def _draw_rewards(self, surface: pygame.Surface, quest: QuestDef, y: int) -> None:
        if not quest.rewards:
            return
        self._text(surface, _("quest.reward"), (_RIGHT_X, y), FONT_SIZE_TINY, _LABEL)
        y += 16

        x = _RIGHT_X
        font = self._font(FONT_SIZE_SMALL)
        for reward in quest.rewards:
            label = format_reward_label([reward], self._item_name)
            if not label:
                continue
            width = font.size(label)[0] + 32
            if x + width > _RIGHT_EDGE:
                x, y = _RIGHT_X, y + 38
            chip = pygame.Surface((width, 30), pygame.SRCALPHA)
            chip.fill((*_GOLD, 30))
            surface.blit(chip, (x, y))
            pygame.draw.rect(surface, _GOLD, (x, y, width, 30), width=1, border_radius=4)
            self._text(surface, label, (x + 16, y + 6), FONT_SIZE_SMALL, _TITLE)
            x += width + 12

    # --- helpers ------------------------------------------------------------

    @property
    def _messages(self) -> dict[str, dict[str, str]]:
        return getattr(self.scene.game.conf, "messages", None) or {}

    def _item_name(self, item_key: str) -> str:
        items = getattr(self.scene.game.conf, "items", None) or {}
        model = items.get(item_key)
        return entity_name(model) if model is not None else item_key

    def _progress(self, key: str) -> tuple[int, int] | None:
        return quest_progress(self._defs, self.scene.quest_state, self.scene.quests.ctx, key)

    def _state(self, key: str) -> str:
        """``done`` / ``active`` / ``locked`` — the mock's three-state legend."""
        if self._done(key):
            return "done"
        if self._unlocked(key):
            return "active"
        return "locked"

    def _state_colour(self, key: str) -> tuple[int, int, int]:
        return {"done": _DONE, "active": _ACTIVE, "locked": _LOCKED}[self._state(key)]

    def _draw_marker(self, surface: pygame.Surface, x: int, y: int, key: str) -> None:
        """Draw the ✔ / ● / ○ marker as shapes, not glyphs.

        The mock asks for ``✔ ● ○``, but MoM renders in a pixel font that has no
        such glyphs — asking for them draws tofu boxes. Shapes give the same
        legend, at any size, in any font.
        """
        state = self._state(key)
        colour = self._state_colour(key)
        cx, cy = x + 7, y + 8

        if state == "done":
            pygame.draw.lines(surface, colour, False, [(x + 1, cy), (x + 5, cy + 5), (x + 13, cy - 6)], 2)
        elif state == "active":
            pygame.draw.circle(surface, colour, (cx, cy), 5)
        else:
            pygame.draw.circle(surface, colour, (cx, cy), 5, width=1)

    def _draw_caret(self, surface: pygame.Surface, x: int, y: int, expanded: bool, colour) -> None:  # type: ignore[no-untyped-def]
        """▾ / ▸ for a thread head — again shapes, for the same reason."""
        cx, cy = x + 7, y + 8
        points = (
            [(cx - 5, cy - 3), (cx + 5, cy - 3), (cx, cy + 4)]
            if expanded
            else [(cx - 3, cy - 5), (cx + 4, cy), (cx - 3, cy + 5)]
        )
        pygame.draw.polygon(surface, colour, points)

    def _font(self, size: int) -> pygame.font.Font:
        return self.scene.game.fonts[size]

    def _text(
        self,
        surface: pygame.Surface,
        text: str,
        pos: tuple[int, int],
        size: int,
        colour: tuple[int, int, int],
        align: str = "left",
    ) -> None:
        self.hud.draw_text(
            surface, text, pos, font=self._font(size), color=colour,
            align="right" if align == "right" else "left",  # type: ignore[arg-type]
        )

    def _truncate(self, text: str, width: int, size: int) -> str:
        """Cut ``text`` to ``width`` with an ellipsis.

        Quest titles are authored prose of no fixed length; without this a long one
        runs straight through the divider and into the details pane.
        """
        font = self._font(size)
        if width <= 0 or font.size(text)[0] <= width:
            return text
        while text and font.size(f"{text}...")[0] > width:
            text = text[:-1]
        return f"{text.rstrip()}..."

    def _wrap(self, text: str, width: int, size: int) -> list[str]:
        """Greedy word wrap; quest descriptions are prose and vary in length."""
        font = self._font(size)
        lines: list[str] = []
        current = ""
        for word in text.split():
            candidate = f"{current} {word}".strip()
            if current and font.size(candidate)[0] > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines[:4]  # the details pane has room for four; the rest is in the log
