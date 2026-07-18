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
- **Web hides what web cannot do**: the whole Debug section (debug overlay is desktop
  only anyway) and the quick save/load rows (``web_hidden``), mirroring the existing
  ``[] if IS_WEB`` gating in ``ACTIONS``.

i18n (D3): every string here is UI furniture and comes from the TOML ``[help]`` section
via ``_()``. Keycaps are the shared hotbar sprite (``hud.icons["key_*"]``) scaled
evenly to 16px, so a hotkey looks identical here and on the HUD (design-system A).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from settings import (
    FONT_SIZE_LARGE,
    FONT_SIZE_SMALL,
    FONT_SIZE_TINY,
    HEIGHT,
    IS_WEB,
    PANEL_BG_COLOR,
    WIDTH,
    _,
)

from .. import keycap, theme
from ..widget import Widget

if TYPE_CHECKING:
    from scene import Scene

    from .hud import HUD

# --- geometry (logical 1280x720) --------------------------------------------
# Two columns, not the mock's three: MoM's pixel font is far wider than the mock's
# web font (the longest description, "Rozmawiaj / otwórz / atakuj", is 378px), so a
# third column would clip every description. Two ~508px columns clear the widest
# line, and the row height is tuned so even the debug-on layout fits without scroll.
PANEL_W, PANEL_H = 1120, 680
PANEL_X, PANEL_Y = (WIDTH - PANEL_W) // 2, (HEIGHT - PANEL_H) // 2
_PAD = 28
# scrollbar on the right edge of the panel
_SCROLLBAR_W = 6
_SCROLLBAR_X = PANEL_X + PANEL_W - _PAD - _SCROLLBAR_W - 4
_INNER_LEFT = PANEL_X + _PAD
_INNER_RIGHT = PANEL_X + PANEL_W - _PAD - _SCROLLBAR_W - 8
_HEADER_Y = PANEL_Y + 22
_RULE_Y = PANEL_Y + 72
_CONTENT_TOP = PANEL_Y + 82
_CONTENT_BOTTOM = PANEL_Y + PANEL_H - _PAD
_CONTENT_H = _CONTENT_BOTTOM - _CONTENT_TOP

_COL_GAP = 48
_COL_W = (_INNER_RIGHT - _INNER_LEFT - _COL_GAP) // 2
_COL_X = (_INNER_LEFT, _INNER_LEFT + _COL_W + _COL_GAP)
# room reserved for the key icons before a row's description starts. 155 fits the
# widest row (W A S D — four 32px caps = 137px) with a small margin.
_KEY_COL_W = 155
_ROW_H = 36
_TITLE_H = 26
_GROUP_GAP = 10
_CAP_GAP = 3
_SEP_GAP = 5

# --- palette — shared tokens from theme (single source of truth) ------------
_TITLE_COL = theme.TITLE
_GOLD = theme.GOLD
_GREY = theme.GREY
_WHITE = theme.WHITE
# fresh glyph rendered onto the scaled key for single-char caps
_CAP_TEXT = theme.WHITE
_RULE = theme.RULE
_ORANGE = theme.WARN

# A key is drawn as a hotbar keycap sprite via ``keycap.build_cap`` (the same component
# the HUD hotbar and action buttons use). Only the separators stay plain text.
_SEPARATORS = ("/",)


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
            _row(("1", "-", "6"), "help.hotbar"),
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
            _row(("F5",), "help.quick_save", web_hidden=True),
            _row(("F9",), "help.quick_load", web_hidden=True),
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


class HelpPanel(Widget):
    def __init__(self, scene: "Scene", hud: "HUD") -> None:
        super().__init__()
        self.scene = scene
        self.hud = hud
        self.bg = theme.nine_patch("nine_patch_04.png", PANEL_W, PANEL_H)
        self.rect = self.bg.get_rect(topleft=(PANEL_X, PANEL_Y))
        self.scroll: int = 0
        self._max_scroll: int = 0

    # --- lifecycle ----------------------------------------------------------

    def open(self) -> None:
        self.scroll = 0

    def scroll_up(self) -> None:
        self.scroll = max(0, self.scroll - _ROW_H)

    def scroll_down(self) -> None:
        self.scroll = min(self._max_scroll, self.scroll + _ROW_H)

    # --- debug gate ---------------------------------------------------------

    @staticmethod
    def _debug_on() -> bool:
        """Live read of the runtime debug flag.

        ``` ``/``Z`` rebind ``scene.SHOW_DEBUG_INFO`` (the *scene module* global);
        a ``from settings import`` copy would go stale. Local import avoids the
        game_ui → help → scene import cycle at load time.
        """
        import scene as scene_module
        return bool(scene_module.SHOW_DEBUG_INFO)

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

    @staticmethod
    def _column_height(visible: list[tuple[_Group, list[_Row]]]) -> int:
        return sum(_TITLE_H + len(rows) * _ROW_H + _GROUP_GAP for _g, rows in visible)

    # --- drawing ------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        surface.blit(self.bg, self.rect.topleft)
        self._draw_header(surface)
        pygame.draw.line(surface, _RULE, (_INNER_LEFT, _RULE_Y), (_INNER_RIGHT, _RULE_Y), 2)

        columns = [self._visible_groups(groups) for groups in _COLUMNS]
        self._max_scroll = max(0, max(self._column_height(c) for c in columns) - _CONTENT_H)
        self.scroll = max(0, min(self.scroll, self._max_scroll))

        old_clip = surface.get_clip()
        surface.set_clip(pygame.Rect(_INNER_LEFT, _CONTENT_TOP, _INNER_RIGHT - _INNER_LEFT, _CONTENT_H))
        for col_idx, visible in enumerate(columns):
            self._draw_column(surface, _COL_X[col_idx], visible)
        surface.set_clip(old_clip)

        if self._max_scroll > 0:
            self._draw_scrollbar(surface)

    def _draw_header(self, surface: pygame.Surface) -> None:
        self._text(surface, _("help.title"), (_INNER_LEFT, _HEADER_Y), FONT_SIZE_LARGE,
                   _TITLE_COL, shadow=True)
        keycap.render_hint(
            surface, self.hud.icons, self._font(FONT_SIZE_SMALL), self._font(FONT_SIZE_SMALL),
            _("help.close_hint"), (_INNER_RIGHT, _HEADER_Y + 10), _GREY,
            align="right", glyph_color=_CAP_TEXT, shadow_color=PANEL_BG_COLOR,
            scale=1.0,
        )

    def _draw_column(self, surface: pygame.Surface, x: int,
                     visible: list[tuple[_Group, list[_Row]]]) -> None:
        y = _CONTENT_TOP - self.scroll
        for group, rows in visible:
            colour = _ORANGE if group.debug else _GREY
            self._text(surface, _(group.title), (x, y), FONT_SIZE_TINY, colour, shadow=True)
            y += _TITLE_H
            for row in rows:
                self._draw_keys(surface, row.keys, x, y)
                self._text(surface, _(row.desc), (x + _KEY_COL_W, y + 5), FONT_SIZE_SMALL, _WHITE)
                y += _ROW_H
            y += _GROUP_GAP

    def _draw_keys(self, surface: pygame.Surface, keys: tuple[str, ...], x: int, y: int) -> None:
        cx = x
        font = self._font(FONT_SIZE_SMALL)
        for token in keys:
            if token in _SEPARATORS:
                self._text(surface, token, (cx + _SEP_GAP, y + 5), FONT_SIZE_SMALL, _GREY)
                cx += font.size(token)[0] + 2 * _SEP_GAP
            else:
                cx += self._draw_cap(surface, token, cx, y) + _CAP_GAP

    def _draw_cap(self, surface: pygame.Surface, token: str, x: int, y: int) -> int:
        """Draw one keycap sprite; return its width so the caller can advance.

        Uses the hotbar keycap sprite (hud.icons["key_*"]) scaled evenly to
        24px — larger than the HUD hotbar's 16px for panel readability.
        Single-char keys get a crisp fresh glyph on the scaled key; multi-char /
        mouse / arrow keys reuse their baked sprite art.
        """
        cap = keycap.build_cap(self.hud.icons, token, self._font(FONT_SIZE_SMALL), _CAP_TEXT,
                               scale=1.0)
        if cap is None:  # unknown token — fall back to plain text so nothing vanishes
            glyph = self._font(FONT_SIZE_SMALL).render(token, False, _CAP_TEXT)
            surface.blit(glyph, (x, y + 5))
            return glyph.get_width()
        surface.blit(cap, (x, y + (_ROW_H - cap.get_height()) // 2))
        return cap.get_width()

    # --- scrollbar -----------------------------------------------------------

    def _draw_scrollbar(self, surface: pygame.Surface) -> None:
        """Thin vertical scrollbar on the right edge of the panel."""
        track_h = _CONTENT_H
        total_h = track_h + self._max_scroll
        thumb_h = max(20, int(track_h * track_h / total_h))
        thumb_y = _CONTENT_TOP + int((track_h - thumb_h) * self.scroll / self._max_scroll)
        # track
        pygame.draw.rect(surface, _GREY, (_SCROLLBAR_X, _CONTENT_TOP, _SCROLLBAR_W, track_h))
        # thumb
        pygame.draw.rect(surface, _GOLD, (_SCROLLBAR_X, thumb_y, _SCROLLBAR_W, thumb_h))

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
