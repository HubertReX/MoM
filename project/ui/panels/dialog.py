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
from settings import (
    AVATAR_SCALE,
    CHAR_NAME_COLOR,
    FONT_SIZE_LARGE,
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
from ..widgets.rich_text import RichText
from ._tooltip import Tooltip

if TYPE_CHECKING:
    from characters import NPC
    from scene import Scene

_BORDER = 24
_OPTION_PAD = 6
_OPTION_GAP = 4
_MAX_OPTIONS = 9
_CURSOR_WIDTH = 10
_BODY_RATIO = 0.55
_TOOLTIP_TEMPLATE = "[h3][act]Hint[/act][/h3]\n\n[bold]%s[/bold]"


class DialogPanel(Widget):
    def __init__(self, scene: "Scene", hud: object | None = None) -> None:
        super().__init__()
        self.scene = scene
        self.game = scene.game
        self.npc: "NPC | None" = None

        bg_w, bg_h = WIDTH - 200, HEIGHT // 3
        self.bg = theme.nine_patch("nine_patch_01c.png", bg_w, bg_h)
        self.offset = (100, HEIGHT - self.bg.get_height() - 10)
        self.rect = pygame.Rect(self.offset, self.bg.get_size())

        body_h = int(bg_h * _BODY_RATIO)
        self.body_rect = pygame.Rect(
            self.offset[0] + _BORDER,
            self.offset[1] + _BORDER,
            bg_w - 2 * _BORDER,
            body_h,
        )
        self.body = RichText("", self.body_rect, scene.icons, base_size=20)

        self.options_top = self.body_rect.bottom + _OPTION_GAP
        self.option_rects: list[pygame.Rect] = []
        self.option_labels: list[Label] = []
        self.option_weight_indicators: list[tuple[pygame.Surface, pygame.Rect]] = []
        self.selected_index = 0

        self.name_bg = theme.nine_patch("nine_patch_13.png", 26 * TILE_SIZE, TILE_SIZE)
        self.name_label = Label("", size=FONT_SIZE_LARGE, font_path=str(MAIN_FONT),
                                color=CHAR_NAME_COLOR, shadow=True)
        self.key_space = scene.icons["key_Space"][0]
        self.key_icon = scene.icons["key"][0]
        self.question_icon = scene.icons.get("question", [self.key_space])[0]
        self._weight_font = theme.get_font(FONT_SIZE_SMALL, font_path=str(MAIN_FONT))

        self.tooltip = Tooltip(scene.icons, _TOOLTIP_TEMPLATE, cursor_size=self.game.cursor_img.get_size())

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
        self.tooltip.update(None, (0, 0))
        self._visit_current_node()
        self._refresh_options()

    def _visit_current_node(self) -> None:
        """Apply the current node's side effect exactly once (first visit)."""
        if self.npc is None or self.npc.dialog is None:
            return
        sink = GameResultSink(self.scene.player, self.npc)
        visit_node(self.npc.dialog, sink)

    def _refresh_options(self) -> None:
        """Rebuild the filtered, numbered option list for the current node."""
        self.option_labels = []
        self.option_rects = []
        self.option_weight_indicators = []
        self.selected_index = 0
        if self.npc is None or self.npc.dialog is None:
            return

        node = self.npc.dialog
        ctx = NPCConditionContext(self.npc, self.scene.player)
        available: list[tuple[int, DialogOption]] = []
        for i, opt in enumerate(node.options):
            if i >= _MAX_OPTIONS:
                break
            try:
                visible = check_condition(opt.condition, ctx)
            except Exception:
                visible = False
            if visible:
                available.append((i, opt))

        # Preserve the previous selection when the list changes, if possible.
        old_index = self.selected_index
        y = self.options_top
        left = self.body_rect.left + _CURSOR_WIDTH
        max_w = self.body_rect.width - _CURSOR_WIDTH
        for display_idx, (_orig_idx, opt) in enumerate(available):
            text_key = opt.text
            text = get_msg(self.game.conf.messages, text_key)
            label = Label(
                f"{display_idx + 1}. {text}",
                size=18,
                font_path=str(MAIN_FONT),
                color=theme.DEFAULT_TEXT_COLOR,
                shadow=True,
            )
            label.rect.topleft = (left, y)
            label.rect.width = min(label.rect.width, max_w)
            self.option_labels.append(label)
            option_rect = pygame.Rect(
                self.body_rect.left, y, self.body_rect.width, label.rect.height + _OPTION_PAD
            )
            self.option_rects.append(option_rect)
            self.option_weight_indicators.append(
                self._build_weight_indicator(opt, option_rect)
            )
            y += label.rect.height + _OPTION_PAD + _OPTION_GAP

        if self.option_labels and old_index < len(self.option_labels):
            self.selected_index = old_index

    def _build_weight_indicator(
        self, opt: DialogOption, option_rect: pygame.Rect
    ) -> tuple[pygame.Surface, pygame.Rect]:
        """Return a cached surface + blit position for the option's sentiment weight.

        The weight is shown as a small key icon followed by the numeric value.
        Undiscovered weights (not yet selected for this NPC) render a ``?`` icon.
        """
        if self.npc is None:
            return (pygame.Surface((0, 0), pygame.SRCALPHA), pygame.Rect(0, 0, 0, 0))

        known = opt.sentiment in self.npc.known_disposition
        if known:
            weight = self.npc.known_disposition[opt.sentiment]
            text = f"{weight:+d}"
            color = theme.DEFAULT_TEXT_COLOR
        else:
            text = "?"
            color = theme.DEFAULT_TEXT_COLOR

        text_surf = self._weight_font.render(text, False, color)
        icon = self.key_icon
        spacing = 2
        total_w = icon.get_width() + spacing + text_surf.get_width()
        total_h = max(icon.get_height(), text_surf.get_height())
        surf = pygame.Surface((total_w, total_h), pygame.SRCALPHA)
        surf.blit(icon, (0, 0))
        surf.blit(text_surf, (icon.get_width() + spacing, (total_h - text_surf.get_height()) // 2))

        # Right-align inside the option rect with a small margin.
        x = option_rect.right - total_w - _OPTION_PAD
        y = option_rect.centery - total_h // 2
        return surf, pygame.Rect(x, y, total_w, total_h)

    def _set_index(self, index: int) -> None:
        if self.option_labels:
            self.selected_index = index % len(self.option_labels)

    def select_next(self) -> None:
        self._set_index(self.selected_index + 1)

    def select_prev(self) -> None:
        self._set_index(self.selected_index - 1)

    def activate_selected(self) -> bool:
        """Choose the highlighted option and advance the dialog graph.

        Returns ``True`` if the conversation should close (final node reached).
        """
        if not self.option_labels or not self.npc or not self.npc.dialog:
            return False
        # Find the original DialogOption that corresponds to the visible label.
        visible = self._visible_options()
        if self.selected_index >= len(visible):
            return False
        opt = visible[self.selected_index]
        opt.selected = True
        self.npc.selected_options_dict[opt.key] = True
        self.npc.apply_option_sentiment(opt.sentiment)
        self.npc.dialog = opt.next_node
        self._visit_current_node()
        if self.npc.dialog.is_final:
            return True
        self._refresh_node()
        return False

    def _visible_options(self) -> list[DialogOption]:
        """Return the currently visible DialogOption objects in display order."""
        if self.npc is None or self.npc.dialog is None:
            return []
        ctx = NPCConditionContext(self.npc, self.scene.player)
        visible: list[DialogOption] = []
        for i, opt in enumerate(self.npc.dialog.options):
            if i >= _MAX_OPTIONS:
                break
            try:
                if check_condition(opt.condition, ctx):
                    visible.append(opt)
            except Exception:
                pass
        return visible

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
        return self.body.is_scroll_bottom() and not self.option_labels

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
            if event.key in (pygame.K_UP, pygame.K_w):
                self.select_prev()
                return True
            if event.key in (pygame.K_DOWN, pygame.K_s):
                self.select_next()
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return self.activate_selected()
            if pygame.K_1 <= event.key <= pygame.K_9:
                idx = event.key - pygame.K_1
                if idx < len(self.option_labels):
                    self._set_index(idx)
                    return self.activate_selected()
        return self.body.handle_event(event)

    def update(self, dt: float) -> None:
        self.body.update(dt)
        self.tooltip.update(self.body.link_at(pygame.mouse.get_pos()), pygame.mouse.get_pos())

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        avatar_off = TILE_SIZE * AVATAR_SCALE
        if self.npc is not None:
            surface.blit(self.npc.avatar, (self.offset[0], self.offset[1] + 4 - avatar_off))
            surface.blit(
                self.scene.player.avatar,
                (self.offset[0] + self.bg.get_width() - avatar_off, self.offset[1] + 4 - avatar_off),
            )

        surface.blit(self.bg, self.offset)
        self.body.draw(surface)

        # Highlight the active option.
        if self.option_rects:
            rect = self.option_rects[self.selected_index]
            pygame.draw.rect(surface, (*CHAR_NAME_COLOR, 80), rect.inflate(-2, -2), border_radius=3)
            pygame.draw.rect(surface, CHAR_NAME_COLOR, rect.inflate(-2, -2), width=1, border_radius=3)

        for label in self.option_labels:
            label.draw(surface)

        for indicator, pos in self.option_weight_indicators:
            surface.blit(indicator, pos)

        surface.blit(self.name_bg, (self.offset[0] + 3 * TILE_SIZE, self.offset[1] - 3 * TILE_SIZE))
        self.name_label.draw(surface)
        self._draw_sentiment_indicator(surface)

        surface.blit(self.key_space, (self.offset[0] + self.bg.get_width() - 15, self.offset[1] + 40))
        self.tooltip.draw(surface)

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
        pygame.draw.rect(surface, CHAR_NAME_COLOR, (x, y, bar_w, bar_h), width=1, border_radius=2)
