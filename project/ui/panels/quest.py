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
    ITEMS_SHEET_DEFINITION,
    PANEL_BG_COLOR,
    FONT_SIZE_MEDIUM,
    FONT_SIZE_SMALL,
    FONT_SIZE_TINY,
    _,
    entity_name,
    get_msg,
)

from .. import theme
from ..text.markup import cut_markup, strip_tags
from ..widget import Widget

if TYPE_CHECKING:
    from scene import Scene

    from .hud import HUD

# --- geometry, straight from the mock ---------------------------------------
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 90, 60, 1100, 600
# The nine-patch draws its own frame; rules and text stop short of it instead of
# running onto the border.
_INNER_PAD = 22
_INNER_LEFT = PANEL_X + _INNER_PAD
_INNER_RIGHT = PANEL_X + PANEL_W - _INNER_PAD
_HEADER_Y = 88
_RULE_Y = 128
# Wider than the mock's 470, and measured rather than guessed: a step title starts
# at _LEFT_X + _STEP_INDENT + 24 = 184, and "Gdzie znaleźć tę osobę?" is 322px in
# the pixel font, so the divider has to sit at 522 for it to fit whole. 560 gives
# that some headroom (and happens to fit "Spotkaj się z Sarkażmijką" too). The
# details pane pays for it and can afford to: it was mostly empty space.
_SPLIT_X = 560
_FOOTER_Y = 612
_LEFT_X = 118
# derived, so moving the divider cannot leave the right column behind
_RIGHT_X = _SPLIT_X + 30
_RIGHT_EDGE = 1160
_RIGHT_W = _RIGHT_EDGE - _RIGHT_X
_ROW_H = 30
_STEP_INDENT = 42
# `:golden_coin:` and friends are item sprites, not emotes, so markup has to be
# told they are drawable here - see _reward_icons.
_ITEM_EMOJIS = frozenset(ITEMS_SHEET_DEFINITION)
# RichText leads at the font's own height (14px at FONT_SIZE_SMALL), which sets
# prose solid; the mock's rhythm is 24px per line, so the difference is padding.
_LINE_SPACING = 10
_LIST_TOP = 168
_LIST_BOTTOM = _FOOTER_Y - 8

# --- palette — shared tokens from theme (single source of truth) ------------
# Local aliases keep the call sites unchanged; values live in theme.py.
_GOLD = theme.GOLD
_TITLE = theme.TITLE
_DONE = theme.DONE
_ACTIVE = theme.ACCENT_CYAN
# One grey for every muted thing (labels, counter, locked rows, hints).
_GREY = theme.GREY
_WHITE = theme.WHITE
_RULE = theme.RULE
# Empty progress track: near-black clears the 3:1 UI floor against the olive panel.
_BAR_BG = theme.BAR_BG
_MANUAL = theme.WARN

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
        # (markup, width, size, colour) -> surface. Keyed on all four because the
        # same title is drawn narrow in the list and wide in the details pane, and
        # baking it is not free: fitting one to a column costs a handful of probes.
        self._rich_cache: dict[tuple[str, int, int, tuple[int, ...]], pygame.Surface] = {}

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

        # the nine-patch already frames the panel; a second gold rect on top of it
        # only fights with the border art
        surface.blit(self.bg, self.rect.topleft)
        self._draw_header(surface)
        # rules stop at the inner edge instead of running out onto the frame
        pygame.draw.line(surface, _RULE, (_INNER_LEFT, _RULE_Y), (_INNER_RIGHT, _RULE_Y), 2)
        pygame.draw.line(surface, _RULE, (_SPLIT_X, _RULE_Y + 2), (_SPLIT_X, _FOOTER_Y - 2), 2)
        self._draw_list(surface)
        self._draw_details(surface)
        pygame.draw.line(surface, _RULE, (_INNER_LEFT, _FOOTER_Y), (_INNER_RIGHT, _FOOTER_Y), 2)
        self._text(surface, _("quest.hints"), (_LEFT_X, _FOOTER_Y + 10), FONT_SIZE_SMALL, _GREY, shadow=True)

    def _draw_header(self, surface: pygame.Surface) -> None:
        title = _("quest.journal")
        self._text(surface, title, (_LEFT_X, _HEADER_Y), FONT_SIZE_LARGE, _TITLE, shadow=True)

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
            _GREY,
            shadow=True,
        )

        x = filters_x
        for idx, label in enumerate(labels):
            active = idx == self.filter_idx
            self._text(
                surface, label, (x, _HEADER_Y + 8), FONT_SIZE_SMALL,
                _TITLE if active else _GREY, shadow=True,
            )
            width = font.size(label)[0]
            if active:
                pygame.draw.line(surface, _GOLD, (x, _HEADER_Y + 28), (x + width, _HEADER_Y + 28), 2)
            x += width + gap

    def _draw_list(self, surface: pygame.Surface) -> None:
        self._label(surface, _("quest.threads"), (_LEFT_X, _LIST_TOP - 26))

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
            name = self._rich_line(
                get_msg(self._messages, quest.name), name_room, FONT_SIZE_SMALL,
                _TITLE if idx == self.selected else colour,
            )
            surface.blit(name, (name_x, y + 6))

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
        self._label(surface, _("quest.details"), (_RIGHT_X, _LIST_TOP - 26))
        if row is None:
            self._text(surface, _("quest.empty"), (_RIGHT_X, _LIST_TOP + 20), FONT_SIZE_SMALL, _GREY)
            return

        quest = self._defs[row.key]
        y = _LIST_TOP - 6
        title = self._rich_line(get_msg(self._messages, quest.name), _RIGHT_W, FONT_SIZE_MEDIUM, _TITLE)
        surface.blit(title, (_RIGHT_X, y))

        y += 34
        description = self._rich_block(
            get_msg(self._messages, quest.description), _RIGHT_W, FONT_SIZE_SMALL, _WHITE
        )
        surface.blit(description, (_RIGHT_X, y))
        y += description.get_height()

        if self._done(row.key):
            y = self._draw_result(surface, quest, y + 26)

        children = children_of(self._defs, row.key)
        if children:
            y = self._draw_steps(surface, row.key, children, y + 26)

        self._draw_rewards(surface, quest, y + 26)

    def _draw_result(self, surface: pygame.Surface, quest: QuestDef, y: int) -> int:
        """The author's prose for how the quest ended — for finished quests only.

        Gated on `done` because the prose *is* the answer: "Kiedyś wołali na nią
        Mariolka" told up front would spoil the step that earns it. The journal is
        a record of what happened, not a hint sheet.

        This is where `**Sukces**:` finally reaches the player. It was imported,
        stored in config.json and localized all along, and nothing ever showed it.
        """
        self._label(surface, _("quest.result"), (_RIGHT_X, y))
        y += 22
        prose = self._rich_block(
            get_msg(self._messages, quest.success), _RIGHT_W, FONT_SIZE_SMALL, _DONE, max_lines=4
        )
        surface.blit(prose, (_RIGHT_X, y))
        return y + prose.get_height()

    def _draw_steps(self, surface: pygame.Surface, key: str, children: list[str], y: int) -> int:
        self._label(surface, _("quest.steps"), (_RIGHT_X, y))
        progress = self._progress(key)
        if progress:
            current, total = progress
            self._text(
                surface, f"{current} / {total}", (_RIGHT_EDGE, y), FONT_SIZE_SMALL, _ACTIVE, align="right"
            )
            bar_y = y + 20
            pygame.draw.rect(surface, _BAR_BG, (_RIGHT_X, bar_y, _RIGHT_W, 8), border_radius=4)
            if total:
                filled = int(_RIGHT_W * current / total)
                if filled:
                    pygame.draw.rect(surface, _ACTIVE, (_RIGHT_X, bar_y, filled, 8), border_radius=4)
            y = bar_y + 26
        else:
            # A `manual` umbrella has no progress bar - completing its steps does not
            # complete it, so a bar would be a lie. Skipping the bar must not also
            # skip its vertical space, or the first step lands on the KROKI label.
            y += 24

        for child in children:
            self._draw_marker(surface, _RIGHT_X, y, child)
            name = self._rich_line(
                get_msg(self._messages, self._defs[child].name), _RIGHT_W - 24,
                FONT_SIZE_SMALL, self._state_colour(child),
            )
            surface.blit(name, (_RIGHT_X + 24, y))
            y += 28
        return y

    def _draw_rewards(self, surface: pygame.Surface, quest: QuestDef, y: int) -> None:
        if not quest.rewards:
            return
        self._label(surface, _("quest.reward"), (_RIGHT_X, y))
        y += 18

        x = _RIGHT_X
        for reward in quest.rewards:
            label = format_reward_label([reward], self._item_name)
            if not label:
                continue
            # a chip sizes to its label rather than the other way round, so the
            # only cap is the pane it has to stay inside
            text = self._rich_line(label, _RIGHT_W - 32, FONT_SIZE_SMALL, _TITLE)
            width = text.get_width() + 32
            if x + width > _RIGHT_EDGE:
                x, y = _RIGHT_X, y + 38
            chip = pygame.Surface((width, 30), pygame.SRCALPHA)
            chip.fill((*_GOLD, 30))
            surface.blit(chip, (x, y))
            pygame.draw.rect(surface, _GOLD, (x, y, width, 30), width=1, border_radius=4)
            surface.blit(text, (x + 16, y + (30 - text.get_height()) // 2))
            x += width + 12

    def _reward_icons(self) -> dict[str, list[pygame.Surface]]:
        """Emote/HUD icons plus the item sprites, for the reward chips.

        Items go in first so the emote sheet wins the one name they share
        (``heart``) and every existing ``:heart:`` keeps the look it has.
        """
        return {**self.scene.items_sheet, **self.hud.icons}

    def _build_rich(  # type: ignore[no-untyped-def]
        self, markup: str, width: int, size: int, colour: tuple[int, ...], *, line_spacing: int = 0
    ):
        """A RichText over ``markup``, with the panel's icons and whitelist.

        ``base_color`` matters: without it an untagged run (the unit in "max HP")
        falls back to RichText's own default and stops matching what it sits in.
        """
        from ..widgets.rich_text import RichText

        return RichText(markup, (0, 0, max(1, width), max(size * 4, 64)), self._reward_icons(),
                        base_size=size, base_color=colour, show_scrollbar=False,
                        line_spacing=line_spacing, extra_emojis=_ITEM_EMOJIS)

    def _fit_line(self, markup: str, max_width: int, size: int, colour: tuple[int, ...]) -> str:
        """``markup`` cut to ``max_width``, tags intact.

        Binary search over how many *characters* survive, measured with RichText
        itself. Deliberately not arithmetic on font widths: ``[bold]`` changes the
        advance, so a hand-rolled sum would quietly disagree with what is drawn —
        and the whole point of this is that the drawn line fits.

        ~6 probes, only for a title that actually overflows, and the result is
        cached by the caller.
        """
        if self._build_rich(markup, 10_000, size, colour).content_width <= max_width:
            return markup

        low, high = 0, len(strip_tags(markup))
        best = cut_markup(markup, 0)
        while low <= high:
            mid = (low + high) // 2
            candidate = cut_markup(markup, mid)
            if self._build_rich(candidate, 10_000, size, colour).content_width <= max_width:
                best, low = candidate, mid + 1
            else:
                high = mid - 1
        return best

    def _rich_line(
        self, markup: str, max_width: int, size: int, colour: tuple[int, ...]
    ) -> pygame.Surface:
        """One line of styled text, ellipsised to ``max_width``. Cached.

        Titles and prose are author markup — ``[char]Zielarka[/char]`` — which
        plain ``draw_text`` would print tag and all. Reward labels additionally
        carry an inline sprite: ``💰`` and friends are not in MoM's pixel font
        (measured; every one renders the same tofu box), so the coin has to be the
        real thing, and it lives in the *items* sheet rather than the emote sheet.
        """
        key = (markup, max_width, size, tuple(colour))
        surf = self._rich_cache.get(key)
        if surf is None:
            rt = self._build_rich(self._fit_line(markup, max_width, size, colour),
                                  10_000, size, colour)
            full = rt.render_static()
            width = max(1, min(rt.content_width, full.get_width()))
            surf = full.subsurface((0, 0, width, full.get_height())).copy()
            self._rich_cache[key] = surf
        return surf

    def _rich_block(
        self, markup: str, width: int, size: int, colour: tuple[int, ...], *, max_lines: int = 6
    ) -> pygame.Surface:
        """Word-wrapped styled text, ``width`` wide, at most ``max_lines`` tall. Cached.

        RichText wraps on its own, so the panel does its own wrapping nowhere —
        and unlike a plain-text wrap, it breaks what is actually drawn rather than
        the untagged string behind it.

        The cap is what stops a long description from pushing KROKI and NAGRODA
        off the bottom of the panel; the pane has no scrollbar to fall back on.
        """
        key = (markup, width, size, tuple(colour))
        surf = self._rich_cache.get(key)
        if surf is None:
            rt = self._build_rich(markup, width, size, colour, line_spacing=_LINE_SPACING)
            surf = rt.render_static()
            # cut on a line boundary, using the heights RichText actually laid out.
            # Deriving them from the font slices the last line through its glyphs:
            # a line is as tall as its tallest item, and a shadow makes that more
            # than the font's own height.
            kept = rt.line_heights[:max_lines]
            ceiling = sum(kept) + _LINE_SPACING * max(0, len(kept) - 1)
            if surf.get_height() > ceiling:
                surf = surf.subsurface((0, 0, surf.get_width(), ceiling)).copy()
            self._rich_cache[key] = surf
        return surf

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
        return {"done": _DONE, "active": _ACTIVE, "locked": _GREY}[self._state(key)]

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
            pygame.draw.circle(surface, colour, (cx, cy), 5, width=2)

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
        *,
        shadow: bool = False,
    ) -> None:
        """Draw a line of plain text.

        ``shadow`` is off by default: it earns its keep on the furniture (header,
        section labels, footer) where it separates chrome from content, but under
        a paragraph of prose it just thickens every glyph and costs legibility.
        """
        self.hud.draw_text(
            surface, text, pos, font=self._font(size), color=colour,
            align="right" if align == "right" else "left",  # type: ignore[arg-type]
            border=PANEL_BG_COLOR if shadow else None,  # type: ignore[arg-type]
        )

    def _label(self, surface: pygame.Surface, text: str, pos: tuple[int, int]) -> None:
        """A section heading (WĄTKI / SZCZEGÓŁY / KROKI / NAGRODA) — chrome, so shadowed."""
        self._text(surface, text, pos, FONT_SIZE_TINY, _GREY, shadow=True)

    def _truncate(self, text: str, width: int, size: int) -> str:
        """Cut plain ``text`` to ``width`` with an ellipsis.

        For UI chrome only — the counter in the header, whose wording comes from
        the locale and carries no tags. Anything the *author* wrote goes through
        :meth:`_rich_line`, which cuts without breaking the markup.
        """
        font = self._font(size)
        if width <= 0 or font.size(text)[0] <= width:
            return text
        while text and font.size(f"{text}...")[0] > width:
            text = text[:-1]
        return f"{text.rstrip()}..."
