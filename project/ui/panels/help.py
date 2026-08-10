"""HelpPanel: the controls/keybindings reference, toggled with H or F1.

Built to the mock in ``doc/_attachements/help-panel-2026-07-18.html`` — its columns,
grouping and palette are the spec.

Unlike the old right-edge scrolling strip (``HUD.show_help``), this is a centered
**modal** panel: while it is up the world is frozen (it is listed in ``GameUI._MODAL``
and ``_BLOCKING``), so the player can read it without a monster walking in.

Three concerns shape the content:

- **Grouping by purpose**, not by key order — Ruch / Interakcja / Ekwipunek / Mysz /
  System / W oknach / Debug.
- **Debug section is dev-only**: it renders only when the runtime debug overlay is on
  (``scene.SHOW_DEBUG_INFO`` — the *scene module* global that ``/Z toggles, read live
  exactly as ``characters.py`` does, not a stale import).
- **Web hides only what web cannot do**: the whole Debug section (the debug overlay is
  desktop only). Save/load/screenshot (F5/F9/F6) all work on web, so they stay visible;
  the ``web_hidden`` mechanism remains for any future desktop-only row.

i18n (D3): every string here is UI furniture and comes from the TOML ``[help]`` section
via ``_()``. Keycaps are the shared hotbar sprite (``hud.icons["key_*"]``) at native
32px, so a hotkey looks identical here and on the HUD (design-system A).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

import settings
from settings import (
    FONT_SIZE_LARGE,
    FONT_SIZE_SMALL,
    FONT_SIZE_TINY,
    IS_WEB,
    PANEL_BG_COLOR,
    _,
)

from .. import keycap, layout, theme
from ..widget import Widget
from ..widgets.scroll_view import ScrollView

if TYPE_CHECKING:
    from scene import Scene

    from .hud import HUD

# --- geometry ----------------------------------------------------------------
# Two columns, not the mock's three: MoM's pixel font is far wider than the mock's
# web font (the longest description, "Rozmawiaj / otwórz / atakuj", is 378px), so a
# third column would clip every description.
#
# NOTHING here is a fixed box any more. The design size below is a MAXIMUM: the panel
# is clamped to the viewport (at 1024x720 the old fixed 1120px panel hung ~48px off
# BOTH screen edges), and the column widths are MEASURED from the real fonts, per
# language. That is the design-system meta-rule — a width that depends on a font metric
# must be derived from it, never guessed — and it is why the Polish "Rozmawiaj / otwórz
# / atakuj" used to silently spill out of its 341px slot into the column gap.
_DESIGN_W, _DESIGN_H = 1152, 680
_MIN_MARGIN = 16        # the panel never touches the viewport edge
_PAD = 28
# scrollbar on the right edge of the panel — shared beveled capsule component
# (widgets/bar.py): INK frame + RULE track + gold beveled thumb, CHUNKY (non-AA) ends.
_SCROLLBAR_W = 32
_COL_GAP = 48           # minimum gutter between the two columns
_DESC_MARGIN = 8        # breathing room after the longest description in a column

# Everything below is (re)computed by _recompute_geometry() — on construction, on
# open() and after a resolution change — because it depends on the viewport size AND
# on the current language's text metrics. Declared here first for module visibility.
PANEL_W = PANEL_H = PANEL_X = PANEL_Y = 0
_SCROLLBAR_X = _INNER_LEFT = _INNER_RIGHT = 0
_HEADER_Y = _RULE_Y = _CONTENT_TOP = 0
_FOOTER_Y = _FOOTER_TEXT_Y = _CONTENT_BOTTOM = _CONTENT_H = 0
_KEY_COL_W = 0          # key icons slot before a row's description starts
_COLUMN_COUNT = 2       # 1 when the viewport is too narrow for two columns
_COL_X: tuple[int, int] = (0, 0)
_ROW_H = 36
# group title (SMALL 14px) + its rows: the shared section-label rhythm — content sits
# 14px (label height) + theme.SECTION_LABEL_GAP (18) below the label, same as quest.py.
# Keep in sync with the label font if it changes (there it is derived; here it is a
# layout constant used to advance _draw_column, so it is spelled out).
_TITLE_H = 14 + theme.SECTION_LABEL_GAP
_GROUP_GAP = 10
_CAP_GAP = 3
_SEP_GAP = 5

# --- palette — shared tokens from theme (single source of truth) ------------
_TITLE_COL = theme.TITLE
_GREY = theme.GREY
_WHITE = theme.WHITE
# fresh glyph rendered onto the scaled key for single-char caps
_CAP_TEXT = theme.WHITE
_RULE = theme.RULE
_ORANGE = theme.WARN

# A key is drawn as a hotbar keycap sprite via ``keycap.build_cap`` (the same component
# the HUD hotbar and action buttons use). Separators are NOT keys:
#   "/"  -> "or" separator, drawn as a larger grey glyph (proportional to 32px caps);
#   "–"  -> range separator (e.g. hotbar 1–6), drawn as a short grey dash line.
# The ASCII "-" stays a real keycap (the zoom-out key), so it must not be a separator.
_TEXT_SEP = ("/",)
_RANGE_SEP = ("–",)
_RANGE_DASH_W = 12       # the range dash is drawn as a rect, not a glyph


@dataclass(frozen=True)
class _Row:
    keys: tuple[str, ...]  # cap labels / arrow markers / separators
    desc: str              # i18n key
    web_hidden: bool = False


@dataclass(frozen=True)
class _Group:
    title: str             # i18n key
    rows: tuple[_Row, ...]
    debug: bool = False


def _row(keys: tuple[str, ...], desc: str, *, web_hidden: bool = False) -> _Row:
    return _Row(keys, desc, web_hidden)


# Two columns. Each key is a display label rendered as a keycap chip (see _draw_cap);
# "/" and "-" are separators, and ↑↓←→ become triangle chips. Left column = what the
# player does; right column = system, in-window and dev keys. Row counts are balanced
# so the taller (debug-on) column still fits without scroll.
_COLUMNS: tuple[tuple[_Group, ...], ...] = (
    (  # left column — player actions
        _Group("help.grp_move", (
            _row(("W", "A", "S", "D"), "help.move"),
            _row(("Shift",), "help.run"),
            _row(("Space",), "help.jump"),
            _row(("+", "/", "-"), "help.zoom"),
        )),
        _Group("help.grp_interact", (
            _row(("Space",), "help.interact"),
            _row(("E",), "help.pick_toggle"),
            _row(("X",), "help.drop"),
            _row(("F",), "help.use_buy_sell"),
        )),
        _Group("help.grp_items", (
            _row(("I",), "help.inventory"),
            _row(("J",), "help.quest_log"),
            _row(("T",), "help.track_quest"),
            _row(("1", "–", "6"), "help.hotbar"),
            _row((",", "/", "."), "help.cycle"),
        )),
        _Group("help.grp_mouse", (
            _row(("LMB",), "help.go_to"),
            _row(("RMB",), "help.stop"),
        )),
    ),
    (  # right column — system, in-window navigation, dev tools
        _Group("help.grp_system", (
            _row(("H", "/", "F1"), "help.this_help"),
            _row(("F2",), "help.menu"),
            _row(("Esc", "/", "Q"), "help.main_menu"),
            _row(("F5",), "help.quick_save"),
            _row(("F9",), "help.quick_load"),
            _row(("F6",), "help.screenshot"),
        )),
        _Group("help.grp_windows", (
            _row(("↑", "/", "↓"), "help.win_select"),
            _row(("Space",), "help.win_scroll"),
            _row(("Enter",), "help.win_accept"),
            _row(("←", "/", "→"), "help.win_filter"),
            _row(("Esc", "/", "Q"), "help.win_close"),
        )),
        _Group("help.grp_debug", (
            _row(("`", "/", "Z"), "help.dbg_overlay"),
            _row(("B",), "help.dbg_alpha"),
            _row(("N",), "help.dbg_next_day"),
            _row(("F3",), "help.dbg_ui"),
            _row(("F4",), "help.dbg_intro"),
            _row(("F7",), "help.dbg_demo"),
            _row(("R",), "help.dbg_reload"),
            _row(("Alt",), "help.dbg_fly"),
        ), debug=True),
    ),
)


#######################################################################################
# MARK: measured layout


def _keys_width(keys: tuple[str, ...]) -> int:
    """Width a row's key icons occupy — mirrors ``_draw_keys``' advance, exactly.

    Kept next to it on purpose: the moment the two disagree, the key column is sized
    from a number that no longer describes what is drawn.
    """
    sep_font = theme.get_font(FONT_SIZE_LARGE)
    width = 0
    for token in keys:
        if token in _TEXT_SEP:
            width += sep_font.size(token)[0] + 2 * _SEP_GAP
        elif token in _RANGE_SEP:
            width += _RANGE_DASH_W + 2 * _SEP_GAP
        else:
            width += keycap.BASE_PX + _CAP_GAP
    return width


def _measure_columns() -> "tuple[int, tuple[int, int]]":
    """``(key column width, width each column needs)`` for the CURRENT language.

    Measured over every row, debug rows included, so toggling the debug overlay can
    never reshuffle the layout.
    """
    key_col = max(_keys_width(row.keys)
                  for column in _COLUMNS for group in column for row in group.rows)
    needs = tuple(
        key_col + _DESC_MARGIN + max(theme.measure(_(row.desc), FONT_SIZE_SMALL)[0]
                                     for group in column for row in group.rows)
        for column in _COLUMNS
    )
    return key_col + _CAP_GAP, (needs[0], needs[1])


def _recompute_geometry() -> None:
    """Fit the panel to the current viewport and language (WIDTH/HEIGHT/LANG)."""
    global PANEL_W, PANEL_H, PANEL_X, PANEL_Y, _SCROLLBAR_X, _INNER_LEFT, _INNER_RIGHT
    global _HEADER_Y, _RULE_Y, _CONTENT_TOP, _FOOTER_Y, _FOOTER_TEXT_Y
    global _CONTENT_BOTTOM, _CONTENT_H, _KEY_COL_W, _COLUMN_COUNT, _COL_X
    PANEL_W = min(_DESIGN_W, settings.WIDTH - 2 * _MIN_MARGIN)
    PANEL_H = min(_DESIGN_H, settings.HEIGHT - 2 * _MIN_MARGIN)
    PANEL_X = (settings.WIDTH - PANEL_W) // 2
    PANEL_Y = (settings.HEIGHT - PANEL_H) // 2
    _SCROLLBAR_X = PANEL_X + PANEL_W - _PAD - _SCROLLBAR_W - 4
    _INNER_LEFT = PANEL_X + _PAD
    _INNER_RIGHT = PANEL_X + PANEL_W - _PAD - _SCROLLBAR_W - 8
    _HEADER_Y = PANEL_Y + 22
    _RULE_Y = PANEL_Y + 72
    _CONTENT_TOP = PANEL_Y + 82
    # footer strip (shortcuts) mirrors the quest panel: a rule + a hint row at the bottom
    _FOOTER_Y = PANEL_Y + PANEL_H - _PAD - 44
    _FOOTER_TEXT_Y = _FOOTER_Y + 8
    _CONTENT_BOTTOM = _FOOTER_Y - 10
    _CONTENT_H = _CONTENT_BOTTOM - _CONTENT_TOP

    inner = _INNER_RIGHT - _INNER_LEFT
    _KEY_COL_W, needs = _measure_columns()
    if needs[0] + needs[1] + _COL_GAP <= inner:
        # Content-sized columns: the left one starts at the inner edge, the right one
        # ENDS at it, so the slack becomes gutter instead of overflow.
        _COLUMN_COUNT = 2
        _COL_X = (_INNER_LEFT, _INNER_RIGHT - needs[1])
    else:
        # Too narrow for two columns (e.g. 1024px wide with the Polish strings): stack
        # them into one scrollable column rather than let the descriptions spill.
        _COLUMN_COUNT = 1
        _COL_X = (_INNER_LEFT, _INNER_LEFT)
    widest = max(needs)
    if widest > inner:
        # Not even one column fits — a real layout bug, and the A03 registry is where
        # it gets reported. This code never clamps or truncates to hide it.
        layout.report_violation(
            "HelpPanel(columns)", "h-overflow",
            f"widest row needs {widest}px, the panel's inner width is {inner}px "
            f"(viewport {settings.WIDTH}x{settings.HEIGHT})",
        )


class HelpPanel(Widget):
    def __init__(self, scene: "Scene", hud: "HUD") -> None:
        super().__init__()
        self.scene = scene
        self.hud = hud
        _recompute_geometry()
        self.bg = theme.nine_patch("nine_patch_04.png", PANEL_W, PANEL_H)
        self.rect = self.bg.get_rect(topleft=(PANEL_X, PANEL_Y))
        # Shared scroll component (widgets/scroll_view.py): clips the columns,
        # tracks the offset and draws the scrollbar only when they overflow. Step
        # is one row so a key-press moves the list by exactly one line.
        self._scroll = ScrollView(step=_ROW_H)

    # --- lifecycle ----------------------------------------------------------

    def open(self) -> None:
        # Refit to the current viewport and language: both the resolution and LANG
        # may have changed since this panel was constructed, and the panel SIZE now
        # depends on them - so the nine-patch has to be rebuilt too, not just moved
        # (theme.nine_patch is cached per size, so a repeat open costs nothing).
        _recompute_geometry()
        self.bg = theme.nine_patch("nine_patch_04.png", PANEL_W, PANEL_H)
        self.rect = self.bg.get_rect(topleft=(PANEL_X, PANEL_Y))
        self._scroll.reset()

    def scroll_up(self) -> None:
        self._scroll.scroll_up()

    def scroll_down(self) -> None:
        self._scroll.scroll_down()

    # --- debug gate ---------------------------------------------------------

    @staticmethod
    def _debug_on() -> bool:
        """Live read of the runtime debug flag.

        ``` ``/``Z`` rebind ``debug_overlay.SHOW_DEBUG_INFO`` (the runtime flag of
        the scene package, B01 krok 9); a ``from settings import`` copy would go
        stale. Local import avoids the game_ui → help → scene import cycle at load
        time.
        """
        from scene import debug_overlay
        return bool(debug_overlay.SHOW_DEBUG_INFO)

    def _visible_groups(self, groups: tuple[_Group, ...]) -> list[tuple[_Group, list[_Row]]]:
        out: list[tuple[_Group, list[_Row]]] = []
        debug_on = self._debug_on()
        for group in groups:
            if group.debug and not debug_on:
                continue
            rows = [r for r in group.rows if not (r.web_hidden and IS_WEB)]
            if rows:
                out.append((group, rows))
        return out

    # --- drawing ------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        surface.blit(self.bg, self.rect.topleft)
        self._draw_header(surface)
        pygame.draw.line(surface, _RULE, (_INNER_LEFT, _RULE_Y), (_INNER_RIGHT, _RULE_Y), 2)

        columns = [self._visible_groups(groups) for groups in _COLUMNS]
        # The viewport spans the columns and reaches the scrollbar's right edge, so
        # ScrollView drops the bar exactly where the panel used to (_SCROLLBAR_X).
        # The columns' own x/width already exclude the scrollbar, so ScrollView's
        # width param is unused here — the two-column layout is fixed, not fluid.
        viewport = pygame.Rect(
            _INNER_LEFT, _CONTENT_TOP, _SCROLLBAR_X + _SCROLLBAR_W - _INNER_LEFT, _CONTENT_H
        )
        self._scroll.draw(
            surface, viewport,
            lambda top_y, width: self._render_columns(surface, columns, top_y),
        )
        self._draw_footer(surface)

    def _render_columns(
        self, surface: pygame.Surface,
        columns: list[list[tuple[_Group, list[_Row]]]], top_y: int,
    ) -> int:
        """Draw the columns from ``top_y``; return the bottom y the ScrollView needs.

        In the narrow (one-column) layout the second column is stacked UNDER the first
        instead of beside it - the extra height is legal, ScrollView scrolls it.
        """
        if _COLUMN_COUNT == 1:
            bottom = top_y
            for visible in columns:
                bottom = self._draw_column(surface, _COL_X[0], visible, bottom)
            return bottom
        bottom = top_y
        for col_idx, visible in enumerate(columns):
            bottom = max(bottom, self._draw_column(surface, _COL_X[col_idx], visible, top_y))
        return bottom

    def _draw_header(self, surface: pygame.Surface) -> None:
        self._text(surface, _("help.title"), (_INNER_LEFT, _HEADER_Y), FONT_SIZE_LARGE,
                   _TITLE_COL, shadow=True)

    def _draw_footer(self, surface: pygame.Surface) -> None:
        """Footer shortcuts strip (design-system: panel shortcuts live in the footer).

        Left: close hints. Right: scroll hints, only while the list overflows.
        """
        pygame.draw.line(surface, _RULE, (_INNER_LEFT, _FOOTER_Y), (_INNER_RIGHT, _FOOTER_Y), 2)
        text_font = self._font(FONT_SIZE_SMALL)
        sep_font = self._font(FONT_SIZE_LARGE)  # bigger "/" so it isn't dwarfed by 32px caps
        keycap.render_hint(
            surface, self.hud.icons, text_font, text_font,
            _("help.close_hint"), (_INNER_LEFT, _FOOTER_TEXT_Y), _GREY,
            glyph_color=_CAP_TEXT, shadow_color=PANEL_BG_COLOR, sep_font=sep_font,
        )
        if self._scroll.overflows:
            keycap.render_hint(
                surface, self.hud.icons, text_font, text_font,
                _("help.scroll_hint"), (_INNER_RIGHT, _FOOTER_TEXT_Y), _GREY,
                align="right", glyph_color=_CAP_TEXT, shadow_color=PANEL_BG_COLOR, sep_font=sep_font,
            )

    def _draw_column(self, surface: pygame.Surface, x: int,
                     visible: list[tuple[_Group, list[_Row]]], y: int) -> int:
        """Draw one column from ``y`` down; return the y where it finished (the
        ScrollView derives content height, hence overflow, from it)."""
        for group, rows in visible:
            colour = _ORANGE if group.debug else _GREY
            self._text(surface, _(group.title), (x, y), FONT_SIZE_SMALL, colour, shadow=True)
            y += _TITLE_H
            for row in rows:
                self._draw_keys(surface, row.keys, x, y)
                self._text(surface, _(row.desc), (x + _KEY_COL_W, y + 5), FONT_SIZE_SMALL, _WHITE)
                y += _ROW_H
            y += _GROUP_GAP
        return y

    def _draw_keys(self, surface: pygame.Surface, keys: tuple[str, ...], x: int, y: int) -> None:
        cx = x
        sep_font = self._font(FONT_SIZE_LARGE)  # "/" proportional to the 32px caps
        for token in keys:
            if token in _TEXT_SEP:
                gy = y + (_ROW_H - sep_font.get_height()) // 2
                self._text(surface, token, (cx + _SEP_GAP, gy), FONT_SIZE_LARGE, _GREY)
                cx += sep_font.size(token)[0] + 2 * _SEP_GAP
            elif token in _RANGE_SEP:
                # a range (1–6), not a key: a short horizontal grey dash
                dy = y + _ROW_H // 2
                pygame.draw.rect(surface, _GREY, (cx + _SEP_GAP, dy - 1, _RANGE_DASH_W, 2))
                cx += _RANGE_DASH_W + 2 * _SEP_GAP
            else:
                cx += self._draw_cap(surface, token, cx, y) + _CAP_GAP

    def _draw_cap(self, surface: pygame.Surface, token: str, x: int, y: int) -> int:
        """Draw one keycap sprite; return its width so the caller can advance.

        Uses the hotbar keycap sprite (hud.icons["key_*"]) at native 32px - the
        design-system minimum for a readable keycap. Single-char keys get a crisp
        fresh glyph on the key; multi-char / mouse / arrow keys reuse baked art.
        """
        cap = keycap.build_cap(self.hud.icons, token, self._font(FONT_SIZE_SMALL), _CAP_TEXT,
                               scale=1.0)
        if cap is None:  # unknown token — fall back to plain text so nothing vanishes
            glyph = self._font(FONT_SIZE_SMALL).render(token, False, _CAP_TEXT)
            surface.blit(glyph, (x, y + 5))
            return glyph.get_width()
        surface.blit(cap, (x, y + (_ROW_H - cap.get_height()) // 2))
        return cap.get_width()

    # --- helpers ------------------------------------------------------------

    def _font(self, size: int) -> pygame.font.Font:
        return self.scene.game.fonts[size]

    def _text(self, surface: pygame.Surface, text: str, pos: tuple[int, int], size: int,
              colour: tuple[int, int, int], align: str = "left", *, shadow: bool = False) -> None:
        """Draw a line of plain text.

        ``shadow`` off by default (QuestPanel model): it earns its keep on the
        furniture (header, section titles) where it separates chrome from content,
        but under a description or a keycap glyph it only thickens every pixel.
        """
        self.hud.draw_text(
            surface, text, pos, font=self._font(size), color=colour,
            align="right" if align == "right" else "left",  # type: ignore[arg-type]
            border=PANEL_BG_COLOR if shadow else None,  # type: ignore[arg-type]
        )
