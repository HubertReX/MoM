"""DialogPanel: NPC conversation box with selectable options.

Renders the current dialog node text plus a numbered list of available options,
filtered through the mini-DSL condition engine. Supports hybrid input:

* keyboard/gamepad up/down + accept
* digit keys 1-9
* mouse hover + click

Replaces UI.show_dialog_panel / activate_dialog_panel (legacy.py). Layout positions
are kept identical to the original so the screen looks unchanged.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from dialog.conditions import check_condition
from dialog.context_adapter import NPCConditionContext
from dialog.entities import DialogOption
from dialog.result_sink import visit_node
from result_sink_adapter import GameResultSink
from enums import NotificationTypeEnum
from settings import (
    AVATAR_SCALE,
    CHAR_NAME_COLOR,
    FONT_SIZE_LARGE,
    FONT_SIZE_SMALL,
    HEIGHT,
    MAIN_FONT,
    TILE_SIZE,
    WIDTH,
    _,
    get_msg,
    )

from .. import theme
from ..widget import Widget
from ..widgets import Label
from ..widgets.rich_text import RichText, render_rich_text_surface
from ._tooltip import Tooltip

if TYPE_CHECKING:
    from characters import NPC
    from scene import Scene

_BORDER = 24
_OPTION_PAD = 4
_OPTION_GAP = 3
_OPTION_FONT = 16
_BODY_FONT = 16
_MAX_OPTIONS = 9
_CURSOR_WIDTH = 10
_WEIGHT_COL = 80      # px reserved on the right of each option row for emote + sentiment weight
_EMOTE_SCALE = 1.8    # scale factor for sentiment emotes in the weight indicator column
_VISITED_ALPHA = 100  # alpha (0-255) for already-selected (visited) options
_OPTION_VISIBLE_COUNT = 4  # fixed number of options shown before scrolling
_BODY_LINES = 3
_SEPARATOR_H = 4
_SEPARATOR_GAP = 4
_SEPARATOR_COLOR = (84, 135, 137)  # greenish panel border colour (nine_patch_01c)
_OPTION_HIGHLIGHT_COLOR = (22, 55, 82)  # dark blue, high contrast vs turquoise text
_OPTION_HIGHLIGHT_ALPHA = 200
_OPTION_HIGHLIGHT_BORDER = 2
_VISITED_BG_ALPHA = 40     # alpha for visited-option background (subtle dim behind text)
_VISITED_BG_COLOR = (8, 12, 16)  # very dark, neutral — distinct from highlight blue
_TOOLTIP_TEMPLATE = "[h3][act]Hint[/act][/h3]\n\n[bold]%s[/bold]"


class DialogPanel(Widget):
    def __init__(self, scene: "Scene", hud: object | None = None) -> None:
        super().__init__()
        self.scene = scene
        self.game = scene.game
        self.npc: "NPC | None" = None

        bg_w, bg_h = WIDTH - 64, HEIGHT // 3
        self.bg = theme.nine_patch("nine_patch_01c.png", bg_w, bg_h)
        self.offset = (32, HEIGHT - self.bg.get_height() - 10)
        self.rect = pygame.Rect(self.offset, self.bg.get_size())

        body_text_h = _BODY_LINES * _BODY_FONT + (_BODY_LINES - 1) * 4
        self.body_rect = pygame.Rect(
            self.offset[0] + _BORDER,
            self.offset[1] + _BORDER,
            bg_w - 2 * _BORDER,
            body_text_h,
        )
        self.body = RichText("", self.body_rect, scene.icons, base_size=_BODY_FONT, line_spacing=4)

        # Options grow downward from under the separator line (which sits between
        # the node text and the first option row).
        sep_h = _OPTION_GAP + _OPTION_PAD + _SEPARATOR_H + _SEPARATOR_GAP
        self.options_top = self.body_rect.bottom + sep_h
        self.options_bottom = self.rect.bottom - _BORDER
        self._options: list[DialogOption] = []          # filtered, indexed source of truth
        self._option_surfaces: list[pygame.Surface] = []  # weight-indicator surface per option
        self.option_rects: list[pygame.Rect] = []       # parallel to _options; off-screen if not in window
        self.option_surfaces: list[pygame.Surface] = []  # parallel to _options
        self.option_weight_indicators: list[tuple[pygame.Surface, pygame.Rect]] = []
        self.selected_index = 0
        self._scroll_offset = 0                          # index of first option in the visible window
        self._visible_count = 0                          # how many options fit in the area
        self._on_final_node = False                      # a final node was reached; wait for Accept to close
        self._accept_consumed = False                    # guard against double-handling Enter in the same frame

        self.name_bg = theme.nine_patch("nine_patch_13.png", 8 * TILE_SIZE, TILE_SIZE)
        self.name_label = Label("", size=FONT_SIZE_LARGE, font_path=str(MAIN_FONT),
                                color=CHAR_NAME_COLOR, shadow=True)
        self.key_space = scene.icons["key_Space"][0]
        self.key_enter = scene.icons["key_Enter"][0]
        self.key_icon = scene.icons["key"][0]
        self.question_icon = scene.icons.get("question", [self.key_space])[0]
        self._weight_font = theme.get_font(FONT_SIZE_SMALL, font_path=str(MAIN_FONT))

        self.tooltip = Tooltip(scene.icons, _TOOLTIP_TEMPLATE, cursor_size=self.game.cursor_img.get_size())
        self._sentiment_flash_timer = 0.0

    #############################################################################################################
    def open(self, npc: "NPC | None" = None, text: str = "") -> None:
        """Configure the panel when the UI controller opens it."""
        self.set_dialog(npc, text)

    def set_dialog(self, npc: "NPC | None", text: str) -> None:
        self.npc = npc
        self.body.set_text(text)
        self.body.scroll_top()
        name = npc.model.name if npc else _("dialog.unknown_npc")
        self.name_label.set_text(name)
        self.name_label.set_pos(
            (self.offset[0] + 4 * TILE_SIZE, self.offset[1] - int(1.5 * TILE_SIZE))
        )
        # dynamiczne dopasowanie pola imienia do szerokości tekstu
        name_w = max(self.name_label.rect.width + 2 * TILE_SIZE, 8 * TILE_SIZE)
        self.name_bg = theme.nine_patch("nine_patch_13.png", name_w, TILE_SIZE)
        self.tooltip.update(None, (0, 0))
        self._sentiment_flash_timer = 0.0
        self._on_final_node = False
        self._visit_current_node()
        self._refresh_options()
        if self.npc and self.npc.dialog and self.npc.dialog.is_final:
            self.npc.apply_resume_node()
            self._on_final_node = True
        # Dead-end: opening node has no visible options and is not final →
        # treat as auto-final so the player can close the conversation.
        elif not self._options:
            self._on_final_node = True

    def _visit_current_node(self) -> None:
        """Apply the current node's side effect exactly once (first visit)."""
        if self.npc is None or self.npc.dialog is None:
            return
        sink = GameResultSink(self.scene.player, self.npc)
        visit_node(self.npc.dialog, sink)

    def _refresh_options(self) -> None:
        """Rebuild the filtered, numbered option list for the current node.

        Options are the single indexed source of truth (`self._options`); labels
        and weight surfaces are built once here, positions are assigned by
        `_layout_options` which also handles the scrollable viewport window.
        """
        self._options = []
        self.option_surfaces = []
        self._option_surfaces = []
        self.option_rects = []
        self.option_weight_indicators = []
        self.selected_index = 0
        self._scroll_offset = 0
        if self.npc is None or self.npc.dialog is None:
            self._visible_count = 0
            return

        ctx = NPCConditionContext(self.npc, self.scene.player)
        for i, opt in enumerate(self.npc.dialog.options):
            if i >= _MAX_OPTIONS:
                break
            try:
                available = check_condition(opt.condition, ctx)
            except Exception:
                available = False
            if available:
                self._options.append(opt)

        left = self.body_rect.left + _CURSOR_WIDTH
        # Reserve the weight column so long option text never runs into it.
        max_w = self.body_rect.width - _CURSOR_WIDTH - _WEIGHT_COL
        for display_idx, opt in enumerate(self._options):
            text = get_msg(self.game.conf.messages, opt.text)
            rich_text = f"{display_idx + 1}. {text}"
            surf = render_rich_text_surface(
                rich_text, max_w, self.scene.icons,
                base_size=_OPTION_FONT,
                base_color=theme.DEFAULT_TEXT_COLOR,
                shadow=False,
            )
            self.option_surfaces.append(surf)
            self._option_surfaces.append(self._build_weight_indicator(opt))

        self._layout_options()

    def _layout_options(self) -> None:
        """Position the visible slice of options below the separator.

        Options are top-aligned from the separator down; when there are more than
        ``_OPTION_VISIBLE_COUNT`` they scroll to keep the selection in view.
        The node text occupies the area above the separator.
        """
        n = len(self.option_surfaces)
        self.option_rects = [pygame.Rect(-10000, -10000, 0, 0) for _ in range(n)]
        empty = (pygame.Surface((0, 0), pygame.SRCALPHA), pygame.Rect(0, 0, 0, 0))
        self.option_weight_indicators = [empty for _ in range(n)]
        if n == 0:
            self._visible_count = 0
            return

        # Keep the selected option inside the scroll window (fixed visible count).
        self._scroll_offset = max(0, min(self._scroll_offset, n - 1))
        if self.selected_index < self._scroll_offset:
            self._scroll_offset = self.selected_index
        while self.selected_index >= self._scroll_offset + _OPTION_VISIBLE_COUNT:
            self._scroll_offset += 1
        self._visible_count = _OPTION_VISIBLE_COUNT

        start = self._scroll_offset
        end = min(n, start + self._visible_count)
        # top-align: stack downward from options_top
        y = self.options_top
        for i in range(start, end):
            surf_h = self.option_surfaces[i].get_height()
            rect = pygame.Rect(self.body_rect.left, y, self.body_rect.width, surf_h + _OPTION_PAD)
            self.option_rects[i] = rect
            self.option_weight_indicators[i] = self._weight_pos(self._option_surfaces[i], rect)
            y += surf_h + _OPTION_PAD + _OPTION_GAP

    def _build_weight_indicator(self, opt: DialogOption) -> pygame.Surface:
        """Return the sentiment-weight surface for an option (position set on layout).

        Shows the emote sprite for ``opt.sentiment`` (e.g. ``:blessed:``) followed by
        the numeric weight or ``?`` for undiscovered sentiment.
        """
        if self.npc is None:
            return pygame.Surface((0, 0), pygame.SRCALPHA)

        known = opt.sentiment in self.npc.known_disposition
        text = f"{self.npc.known_disposition[opt.sentiment]:+d}" if known else "?"
        color = theme.DEFAULT_TEXT_COLOR

        text_surf = self._weight_font.render(text, False, color)
        emote = self.scene.icons.get(opt.sentiment, [self.key_icon])[0]
        # Scale emote up for readability
        if _EMOTE_SCALE != 1.0:
            w, h = emote.get_size()
            emote = pygame.transform.scale(
                emote, (max(1, round(w * _EMOTE_SCALE)), max(1, round(h * _EMOTE_SCALE)))
            )
        # Fixed-width column so emotes align in one vertical line and the numeric
        # weights align in a second right-justified column across all options.
        total_w = _WEIGHT_COL
        total_h = max(emote.get_height(), text_surf.get_height())
        surf = pygame.Surface((total_w, total_h), pygame.SRCALPHA)
        surf.blit(emote, (0, (total_h - emote.get_height()) // 2))
        text_x = total_w - text_surf.get_width()
        surf.blit(text_surf, (text_x, (total_h - text_surf.get_height()) // 2))
        return surf

    def _weight_pos(
        self, surf: pygame.Surface, option_rect: pygame.Rect
    ) -> tuple[pygame.Surface, pygame.Rect]:
        """Right-align the (fixed-width) weight column inside an option row."""
        total_w, total_h = surf.get_size()
        x = option_rect.right - total_w - _OPTION_PAD
        y = option_rect.centery - total_h // 2
        return surf, pygame.Rect(x, y, total_w, total_h)

    def _set_index(self, index: int) -> None:
        if self._options:
            self.selected_index = index % len(self._options)
            self._layout_options()

    def select_next(self) -> None:
        self._set_index(self.selected_index + 1)

    def select_prev(self) -> None:
        self._set_index(self.selected_index - 1)

    def activate_selected(self) -> bool:
        """Choose the highlighted option and advance the dialog graph.

        Returns ``True`` if the conversation should close (final node reached).
        """
        self._accept_consumed = True
        if not self._options or not self.npc or not self.npc.dialog:
            return False
        if self.selected_index >= len(self._options):
            return False
        # `self._options` is the same indexed list the cursor/number keys act on,
        # so a selection below the visible scroll window still resolves correctly.
        opt = self._options[self.selected_index]
        is_new_selection = not opt.selected
        opt.selected = True
        self.npc.selected_options_dict[opt.key] = True
        shift = self.npc.apply_option_sentiment(opt.sentiment) if is_new_selection else 0
        if shift != 0:
            self.scene.add_notification(
                _("notify.sentiment", amount=shift),
                NotificationTypeEnum.success if shift > 0 else NotificationTypeEnum.info,
            )
            self._sentiment_flash_timer = 0.5
        self.npc.dialog = opt.next_node
        self._visit_current_node()
        if self.npc.dialog.is_final:
            # Refresh the body text/options for the final node so the player
            # sees the farewell text. The panel stays open until the player
            # presses Accept (Enter) to close it.
            self.npc.apply_resume_node()
            self._refresh_node()
            self._on_final_node = True
            return True
        self._on_final_node = False
        self._refresh_node()
        # Dead-end: advanced to a non-final node with no visible options →
        # auto-end the conversation.
        if not self._options:
            self._on_final_node = True
            return True
        return False

    @property
    def on_final_node(self) -> bool:
        """True when the dialog is at a final (farewell) node waiting for Accept."""
        return self._on_final_node

    def _refresh_node(self) -> None:
        """Update the body text after advancing to a new node."""
        if self.npc is None or self.npc.dialog is None:
            self.body.set_text("")
            return
        text = get_msg(self.game.conf.messages, self.npc.dialog.text)
        self.body.set_text(text)
        self.body.scroll_top()
        self._refresh_options()

    # scroll/close helpers used by the UI controller
    @property
    def at_bottom(self) -> bool:
        return self.body.is_scroll_bottom() and not self.option_surfaces

    def page_down(self) -> None:
        self.body.scroll_page_down()

    def scroll_top(self) -> None:
        self.body.scroll_top()

    #############################################################################################################
    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            for i, rect in enumerate(self.option_rects):
                if rect.collidepoint(event.pos):
                    self._set_index(i)
                    return True
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self.option_rects):
                if rect.collidepoint(event.pos):
                    self._set_index(i)
                    return self.activate_selected()
            return False
        if event.type == pygame.KEYDOWN:
            # Esc no longer closes the dialog; the conversation can only end by
            # reaching the final node and pressing Enter/accept.
            if event.key in (pygame.K_UP, pygame.K_DOWN):
                # Arrow keys move the option cursor — _edge("up"/"down") in
                # GameUI.update() handles actual navigation via INPUTS. We
                # consume the KEYDOWN here so it does NOT fall through to
                # self.body.handle_event() which would also scroll the NPC
                # speech text.
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                # If the UI controller already advanced the dialog from INPUTS["accept"]
                # in this frame, the same KEYDOWN event is routed here afterwards.
                # Consume it once so a single physical Enter press does not enter
                # and immediately exit the next node.
                if self._accept_consumed:
                    return True
                return self.activate_selected()
            if event.key == pygame.K_SPACE:
                # SPACE is handled by GameUI._edge("talk") which includes the
                # scroll-to-top wrap logic; do NOT handle it here as well
                # (double-handling would override scroll_top with page_down).
                return True
            if pygame.K_1 <= event.key <= pygame.K_9:
                idx = event.key - pygame.K_1
                if idx < len(self._options):
                    self._set_index(idx)
                    return self.activate_selected()
        return self.body.handle_event(event)

    def update(self, dt: float) -> None:
        self._accept_consumed = False
        self.body.update(dt)
        self.tooltip.update(self.body.link_at(pygame.mouse.get_pos()), pygame.mouse.get_pos())

        if self._sentiment_flash_timer > 0.0:
            self._sentiment_flash_timer = max(0.0, self._sentiment_flash_timer - dt)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        a_off = TILE_SIZE * AVATAR_SCALE
        npc_rise = TILE_SIZE * 3  # extra upward shift so the panel doesn't obscure the portrait
        npc_inset = TILE_SIZE * 10  # NPC face shifted right toward center
        p_inset = TILE_SIZE * 5     # player face stays near right edge
        if self.npc is not None:
            surface.blit(
                self.npc.avatar,
                (self.offset[0] + npc_inset, self.offset[1] + 4 - a_off - npc_rise),
            )
            surface.blit(
                self.scene.player.avatar,
                (
                    self.offset[0] + self.bg.get_width() - a_off - p_inset,
                    self.offset[1] + 4 - a_off,
                ),
            )

        surface.blit(self.bg, self.offset)
        self.body.draw(surface)

        # Draw only the visible scroll window of options.
        start = self._scroll_offset
        end = min(len(self.option_surfaces), start + self._visible_count)

        # 1. Draw dimmed background for visited options (always, regardless of cursor).
        for i in range(start, end):
                if self._options[i].selected:
                    rect = self.option_rects[i]
                    pygame.draw.rect(surface, (*_VISITED_BG_COLOR, _VISITED_BG_ALPHA), rect, border_radius=3)

        # 2. Highlight the active option (on top of visited background, if any).
        if start <= self.selected_index < end:
            rect = self.option_rects[self.selected_index]
            pygame.draw.rect(surface, (*_OPTION_HIGHLIGHT_COLOR, _OPTION_HIGHLIGHT_ALPHA), rect, border_radius=3)
            pygame.draw.rect(surface, _OPTION_HIGHLIGHT_COLOR, rect, width=_OPTION_HIGHLIGHT_BORDER, border_radius=3)

        # 3. Draw option text — dimmed for visited, full opacity otherwise.
        for i in range(start, end):
            rect = self.option_rects[i]
            blit_pos = (rect.left + _CURSOR_WIDTH, rect.top)
            surf = self.option_surfaces[i]
            if self._options[i].selected:
                surf.set_alpha(_VISITED_ALPHA)
            else:
                surf.set_alpha(255)
            surface.blit(surf, blit_pos)
            indicator, wpos = self.option_weight_indicators[i]
            surface.blit(indicator, wpos)

        self._draw_scroll_hints(surface, start, end, len(self.option_surfaces))

        # Separator line between the NPC speech and the options.
        sep_y = self.body_rect.bottom + _OPTION_GAP + _OPTION_PAD + _SEPARATOR_H // 2
        sep_rect = pygame.Rect(self.body_rect.left, sep_y - _SEPARATOR_H // 2, self.body_rect.width, _SEPARATOR_H)
        pygame.draw.rect(surface, _SEPARATOR_COLOR, sep_rect)

        # Name plate (dynamic width) centred under the name label.
        name_x = self.name_label.rect.centerx - self.name_bg.get_width() // 2
        surface.blit(self.name_bg, (name_x, self.offset[1] - 3 * TILE_SIZE))
        self.name_label.draw(surface)
        self._draw_sentiment_indicator(surface)

        if self.body.max_scroll > 0:
            surface.blit(self.key_space, (self.offset[0] + self.bg.get_width() - 15, self.offset[1] + 40))
        key_enter_x = self.offset[0] + self.bg.get_width() - 15
        key_enter_y = (self.options_top + self.options_bottom) // 2 - self.key_enter.get_height() // 2
        surface.blit(self.key_enter, (key_enter_x, key_enter_y))
        self.tooltip.draw(surface)

    def _draw_scroll_hints(self, surface: pygame.Surface, start: int, end: int, n: int) -> None:
        """Draw small up/down triangles when options extend past the visible window."""
        if n <= self._visible_count:
            return
        x = self.body_rect.right - 6
        color = CHAR_NAME_COLOR
        if start > 0:
            top = self.options_top
            pygame.draw.polygon(surface, color, [(x - 5, top + 6), (x + 1, top + 6), (x - 2, top)])
        if end < n:
            bot = self.options_bottom
            pygame.draw.polygon(surface, color, [(x - 5, bot - 6), (x + 1, bot - 6), (x - 2, bot)])

    def _draw_sentiment_indicator(self, surface: pygame.Surface) -> None:
        """Draw a small sentiment bar above the NPC name (only when known)."""
        if self.npc is None:
            return

        sentiment = max(0, min(100, self.npc.sentiment))
        bar_w, bar_h = 80, 8
        x = self.offset[0] + 4 * TILE_SIZE
        y = self.offset[1] - int(2.2 * TILE_SIZE)
        pygame.draw.rect(surface, (40, 40, 40), (x, y, bar_w, bar_h), border_radius=2)
        fill_w = int(bar_w * sentiment / 100)
        if fill_w > 0:
            # Red -> yellow -> green as sentiment grows.
            if sentiment < 50:
                color = (255, int(255 * sentiment / 50), 0)
            else:
                color = (int(255 * (100 - sentiment) / 50), 255, 0)
            pygame.draw.rect(surface, color, (x, y, fill_w, bar_h), border_radius=2)
            
        border_color = CHAR_NAME_COLOR
        if self._sentiment_flash_timer > 0.0:
            if int(self._sentiment_flash_timer * 10) % 2 == 0:
                border_color = (255, 255, 255)
                # Draw a slightly inflated border for flash emphasis
                pygame.draw.rect(surface, border_color, (x - 1, y - 1, bar_w + 2, bar_h + 2), width=1, border_radius=2)
        pygame.draw.rect(surface, border_color, (x, y, bar_w, bar_h), width=1, border_radius=2)
