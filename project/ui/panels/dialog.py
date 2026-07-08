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

from typing import TYPE_CHECKING, Any

import pygame
from dialog.conditions import check_condition
from dialog.context_adapter import NPCConditionContext
from dialog.entities import DialogOption
from dialog.result_sink import visit_node
from result_sink_adapter import GameResultSink
from settings import (
    AVATAR_SCALE,
    CHAR_NAME_COLOR,
    FONT_SIZE_LARGE,
    FONT_SIZE_MEDIUM,
    FONT_SIZE_SMALL,
    HEIGHT,
    MAIN_FONT,
    TILE_SIZE,
    WIDTH,
    get_msg
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
_OPTION_FONT = 14
_BODY_FONT = 14
_MAX_OPTIONS = 9
_CURSOR_WIDTH = 10
_WEIGHT_COL = 60      # px reserved on the right of each option row for emote + sentiment weight
_VISITED_ALPHA = 100  # alpha (0-255) for already-selected (visited) options
_OPTION_VISIBLE_COUNT = 4  # fixed number of options shown before scrolling
_OPTION_ROW_H = _OPTION_FONT + _OPTION_PAD  # approx rendered option row height
_OPTION_AREA_H = _OPTION_VISIBLE_COUNT * (_OPTION_ROW_H + _OPTION_GAP) + _OPTION_GAP
_SEPARATOR_H = 2
_SEPARATOR_MARGIN = 8  # extra empty space above the separator (raises the line)
_SEPARATOR_COLOR = (84, 135, 137)  # greenish panel border colour (nine_patch_01c)
_OPTION_HIGHLIGHT_COLOR = (22, 55, 82)  # dark blue, high contrast vs turquoise text
_OPTION_HIGHLIGHT_ALPHA = 200
_OPTION_HIGHLIGHT_BORDER = 2
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

        self.body_rect = pygame.Rect(
            self.offset[0] + _BORDER,
            self.offset[1] + _BORDER,
            bg_w - 2 * _BORDER,
            bg_h - 2 * _BORDER - _SEPARATOR_H - _OPTION_AREA_H - _SEPARATOR_MARGIN,
        )
        self.options_bottom = self.rect.bottom - _BORDER
        self.options_top = self.options_bottom - _OPTION_AREA_H
        self.body = RichText("", self.body_rect, scene.icons, base_size=_BODY_FONT)

        # Options grow downward from just under the *actual* node text (dynamic,
        # not a fixed body ratio); body_rect is the max region the text may use.
        self.options_top = self.body_rect.bottom + _OPTION_GAP
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
        self.key_icon = scene.icons["key"][0]
        self.question_icon = scene.icons.get("question", [self.key_space])[0]
        self._weight_font = theme.get_font(FONT_SIZE_SMALL, font_path=str(MAIN_FONT))

        self.tooltip = Tooltip(scene.icons, _TOOLTIP_TEMPLATE, cursor_size=self.game.cursor_img.get_size())
        self._feedback_font = theme.get_font(FONT_SIZE_MEDIUM, font_path=str(MAIN_FONT))
        self._floating_texts: list[dict[str, Any]] = []
        self._sentiment_flash_timer = 0.0

    #############################################################################################################
    def open(self, npc: "NPC | None" = None, text: str = "") -> None:
        """Configure the panel when the UI controller opens it."""
        self.set_dialog(npc, text)

    def set_dialog(self, npc: "NPC | None", text: str) -> None:
        self.npc = npc
        self.body.set_text(text)
        self.body.scroll_top()
        name = npc.model.name if npc else "????"
        self.name_label.set_text(name)
        self.name_label.set_pos(
            (self.offset[0] + 4 * TILE_SIZE, self.offset[1] - int(1.5 * TILE_SIZE))
        )
        # dynamiczne dopasowanie pola imienia do szerokości tekstu
        name_w = max(self.name_label.rect.width + 2 * TILE_SIZE, 8 * TILE_SIZE)
        self.name_bg = theme.nine_patch("nine_patch_13.png", name_w, TILE_SIZE)
        self.tooltip.update(None, (0, 0))
        self._floating_texts.clear()
        self._sentiment_flash_timer = 0.0
        self._on_final_node = False
        self._visit_current_node()
        self._refresh_options()
        # Dead-end: opening node has no visible options and is not final →
        # treat as auto-final so the player can close the conversation.
        if not self._options and self.npc and self.npc.dialog and not self.npc.dialog.is_final:
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
        """Position the visible slice of options in the fixed bottom area.

        Options are always bottom-aligned in a fixed area sized for
        ``_OPTION_VISIBLE_COUNT`` rows; when there are more options they scroll to
        keep the selection in view. The node text occupies the area above the
        separator, independent of option count.
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
        # bottom-align: start from options_bottom and stack upward
        y = self.options_bottom
        for i in range(end - 1, start - 1, -1):
            surf_h = self.option_surfaces[i].get_height()
            y -= surf_h + _OPTION_PAD
            rect = pygame.Rect(self.body_rect.left, y, self.body_rect.width, surf_h + _OPTION_PAD)
            self.option_rects[i] = rect
            self.option_weight_indicators[i] = self._weight_pos(self._option_surfaces[i], rect)
            y -= _OPTION_GAP

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
        opt.selected = True
        self.npc.selected_options_dict[opt.key] = True
        shift = self.npc.apply_option_sentiment(opt.sentiment)
        if shift != 0:
            bar_w = 80
            x_pos = self.offset[0] + 4 * TILE_SIZE + bar_w // 2
            y_pos = self.offset[1] - int(2.2 * TILE_SIZE) - 6
            text = f"{shift:+d}"
            color = (50, 220, 50) if shift > 0 else (220, 50, 50)
            self._floating_texts.append({
                "text": text,
                "x": float(x_pos),
                "y": float(y_pos),
                "color": color,
                "age": 0.0,
                "lifetime": 1.2,
            })
            self._sentiment_flash_timer = 0.5
        self.npc.dialog = opt.next_node
        self._visit_current_node()
        if self.npc.dialog.is_final:
            # Refresh the body text/options for the final node so the player
            # sees the farewell text. The panel stays open until the player
            # presses Accept (Enter) to close it.
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
                # SPACE only scrolls the NPC speech; it never selects an option.
                self.page_down()
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

        # Update floating texts
        for ft in list(self._floating_texts):
            ft["age"] += dt
            ft["y"] -= 30.0 * dt  # Floats upwards
            if ft["age"] >= ft["lifetime"]:
                self._floating_texts.remove(ft)

        # Update flash timer
        if self._sentiment_flash_timer > 0.0:
            self._sentiment_flash_timer = max(0.0, self._sentiment_flash_timer - dt)

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        avatar_off = TILE_SIZE * AVATAR_SCALE
        avatar_inset = TILE_SIZE * 5  # bring faces toward the centre
        if self.npc is not None:
            surface.blit(self.npc.avatar, (self.offset[0] + avatar_inset, self.offset[1] + 4 - avatar_off))
            surface.blit(
                self.scene.player.avatar,
                (self.offset[0] + self.bg.get_width() - avatar_off - avatar_inset, self.offset[1] + 4 - avatar_off),
            )

        surface.blit(self.bg, self.offset)
        self.body.draw(surface)

        # Draw only the visible scroll window of options.
        start = self._scroll_offset
        end = min(len(self.option_surfaces), start + self._visible_count)

        # Highlight the active option (only when it is inside the window).
        if start <= self.selected_index < end:
            rect = self.option_rects[self.selected_index]
            pygame.draw.rect(surface, (*_OPTION_HIGHLIGHT_COLOR, _OPTION_HIGHLIGHT_ALPHA), rect, border_radius=3)
            pygame.draw.rect(surface, _OPTION_HIGHLIGHT_COLOR, rect, width=_OPTION_HIGHLIGHT_BORDER, border_radius=3)

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

        # Separator line between the NPC speech and the options (panel border colour).
        sep_y = self.body_rect.bottom + _OPTION_GAP + _SEPARATOR_H // 2
        pygame.draw.line(
            surface, _SEPARATOR_COLOR,
            (self.body_rect.left, sep_y), (self.body_rect.right, sep_y),
            _SEPARATOR_H,
        )

        # Name plate (dynamic width) centred under the name label.
        name_x = self.name_label.rect.centerx - self.name_bg.get_width() // 2
        surface.blit(self.name_bg, (name_x, self.offset[1] - 3 * TILE_SIZE))
        self.name_label.draw(surface)
        self._draw_sentiment_indicator(surface)

        # Draw floating texts
        for ft in self._floating_texts:
            txt_surf = self._feedback_font.render(ft["text"], True, ft["color"])
            alpha = int(max(0, min(255, 255 * (1.0 - ft["age"] / ft["lifetime"]))))
            txt_surf.set_alpha(alpha)
            rect = txt_surf.get_rect(center=(int(ft["x"]), int(ft["y"])))
            surface.blit(txt_surf, rect)

        surface.blit(self.key_space, (self.offset[0] + self.bg.get_width() - 15, self.offset[1] + 40))
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
