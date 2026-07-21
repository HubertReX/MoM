"""TradePanel: merchant trading screen (buy/sell, two hotbars, item details, actions).

Replaces UI.show_trade_panel + the trade branch of show_inventory_panel. Layout mirrors
the original. The HUD's gameplay overlay (weapon/hotbar/help) is suppressed while this is
open; the trade panel draws its own two hotbars via the HUD helpers.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

import settings
from settings import (
    CHAR_NAME_COLOR,
    FONT_SIZE_LARGE,
    INVENTORY_ITEM_WIDTH,
    MAX_HOTBAR_ITEMS,
    _,
    entity_name,
    get_buy_price_multiplier,
    get_sell_price_multiplier,
)

from .. import theme
from ..widget import Widget
from .hud import HUD_EDGE, hotbar_topleft
from .inventory import build_inventory_bg, draw_item_details

if TYPE_CHECKING:
    from characters import NPC
    from scene import Scene

    from .hud import HUD

_DIVIDER = theme.DIVIDER

# Layout inside trader_bg, all relative to the panel's own top so they track it when
# the panel moves (the details block used to be pinned to an absolute Y that only
# lined up while the panel top happened to be at y=50, and slid too low once the panel
# was raised to meet the stats panel). The details block sits just below the
# horizontal divider; its anchor is 40px above the first text row, because
# draw_icon_label_value adds that top_margin before row 0.
_TRADER_HDIV_Y = 330      # horizontal divider: hotbar (above) | item details (below)
_TRADER_DETAILS_Y = 320   # item-details anchor (relative to panel top), just under it


class TradePanel(Widget):
    def __init__(self, scene: "Scene", hud: "HUD") -> None:
        super().__init__()
        self.scene = scene
        self.game = scene.game
        self.hud = hud
        self.is_buying: bool = True

        self.inventory_bg = build_inventory_bg()
        self.trader_bg = theme.nine_patch("nine_patch_04.png", 800, 520).copy()
        w, h = self.trader_bg.get_size()
        pygame.draw.line(self.trader_bg, _DIVIDER, (w // 2, h - 140), (w // 2, h - 40), 4)
        pygame.draw.line(self.trader_bg, _DIVIDER, (40, _TRADER_HDIV_Y), (w - 40, _TRADER_HDIV_Y), 4)
        self.trader_small_bg = theme.nine_patch("nine_patch_04.png", 800, 340).copy()
        self._reposition()

    def _reposition(self) -> None:
        """Center/anchor the panels on the current viewport. Called on open() too, so
        the cached panel re-fits after a resolution change."""
        self.inventory_bg_rect = self.inventory_bg.get_rect(
            topleft=(settings.WIDTH // 2 - self.inventory_bg.get_width() // 2, settings.HEIGHT - 320)
        )
        hotbar_half = INVENTORY_ITEM_WIDTH * MAX_HOTBAR_ITEMS // 2
        # Slide the whole trade UI left just enough that the panel's right edge clears
        # the top-right stats panel (which the HUD now anchors there). Everything the
        # panel draws - avatar, name, merchant stats, and *both* hotbars - rides this
        # one center (``self._cx``), so "moje" and the merchant's slots stay
        # column-aligned (one under the other). No overlap -> no shift (wide screens).
        default_cx = settings.WIDTH // 2
        panel_right = (default_cx - hotbar_half - 48) + self.trader_bg.get_width()
        stats_left = settings.WIDTH - self.hud.stats_bg.get_width() - HUD_EDGE
        shift = max(0, panel_right - (stats_left - HUD_EDGE))
        self._cx = default_cx - shift
        left = self._cx - hotbar_half - 48
        # top edge flush with the stats panel's (both anchored at HUD_EDGE)
        top = HUD_EDGE
        self.trader_bg_rect = self.trader_bg.get_rect(topleft=(left, top))
        self.trader_small_bg_rect = self.trader_small_bg.get_rect(topleft=(left, top))

    #############################################################################################################
    def open(self) -> None:
        self._reposition()
        self.is_buying = True

    def toggle_side(self) -> None:
        self.is_buying = not self.is_buying

    #############################################################################################################
    def _draw_inventory(self, surface: pygame.Surface, npc: "NPC") -> None:
        if self.is_buying:
            background = self.trader_bg
            top_left = self.trader_bg_rect.topleft
            props_y = self.trader_bg_rect.top + _TRADER_DETAILS_Y
            props_top_left = (top_left[0], props_y)
            props_top_middle = (self.trader_bg_rect.centerx, props_y)
        else:
            background = self.inventory_bg
            top_left = (self.trader_bg_rect.left, self.inventory_bg_rect.top)
            props_top_left = top_left
            props_top_middle = (self.trader_bg_rect.centerx, self.inventory_bg_rect.top)
            surface.blit(self.trader_small_bg, self.trader_small_bg_rect.topleft)

        surface.blit(background, top_left)
        if npc.selected_item_idx < 0:
            return
        if self.is_buying:
            items = npc.items
        else:
            items = npc.get_tradable_items()
        if npc.selected_item_idx >= len(items):
            return
        item_model = items[npc.selected_item_idx].model
        merchant = self.scene.player.npc_met
        if merchant and self.is_buying:
            multiplier = get_buy_price_multiplier(merchant.sentiment)
        elif merchant:
            multiplier = get_sell_price_multiplier(merchant.sentiment)
        else:
            multiplier = 1.0
        price = int(round(item_model.value * multiplier))
        draw_item_details(self.hud, surface, props_top_left, props_top_middle, item_model, price=price,
                          panel_w=self.trader_bg.get_width())

    def _draw_merchant_stats(self, surface: pygame.Surface, npc: "NPC", top_left: tuple[int, int]) -> None:
        properties = [
            {"icon_name": "pan_balance",
             "value": f"{npc.total_items_weight:4.2f}/{npc.model.max_carry_weight:4.2f}"},
            # purse as current/ceiling, mirroring the weight row above it: the limit
            # only shapes play if the player can see how close the merchant is to it
            {"icon_name": "golden_coin", "value": f"{npc.model.money}/{npc.money_cap}"},
        ]
        tradeable = npc.model.tradeable_items_types
        if tradeable:
            properties.append({"icon_name": "red_exclamation_anim", "value": _("trade.trades_only")})
            for item_type in tradeable:
                properties.append({"icon_name": "", "value": f"        {_(f'item_type.{item_type.value}')}"})
        for row, prop in enumerate(properties):
            self.hud.draw_icon_value(surface, top_left, row, prop)

    #############################################################################################################
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        player = self.scene.player
        merchant = player.npc_met
        if not merchant or not merchant.model.is_merchant:
            return

        npc = merchant if self.is_buying else player
        self._draw_inventory(surface, npc)

        cx = self._cx
        avatar = pygame.transform.scale_by(merchant.avatar, 0.5)
        ar = avatar.get_rect()
        surface.blit(avatar, (cx - ar.width // 2, self.trader_bg_rect.top + 10))
        self.hud.draw_text(
            surface, entity_name(merchant.model),
            (cx, self.trader_bg_rect.top + 10 + ar.height - 16),
            font=self.game.fonts[FONT_SIZE_LARGE], color=CHAR_NAME_COLOR,
            border=(84, 135, 137), shadow=False, align="centred",
        )
        self._draw_merchant_stats(surface, merchant, (cx + ar.width // 2, self.trader_bg_rect.top + 10))

        # both hotbars ride the same center -> the merchant's slots and "moje" stay in
        # one vertical line; only the y differs (merchant inside the panel, player at
        # the bottom of the screen)
        def hb_x(slots: int) -> int:
            return cx - INVENTORY_ITEM_WIDTH * slots // 2

        self.hud.draw_hotbar(
            surface, merchant,
            (hb_x(merchant.max_items), self.trader_bg_rect.top + 10 + ar.height + 24),
            show_shortcuts=self.is_buying,
        )
        self.hud.draw_hotbar(
            surface, player,
            (hb_x(player.max_items), hotbar_topleft(player.max_items)[1]),
            show_shortcuts=not self.is_buying, tradable=True,
        )

        self.hud.show_action(surface, "end_trade", 0)
        if self.is_buying:
            self.hud.show_action(surface, "toggle", 1, label=_("trade.show_mine"))
            self.hud.show_action(surface, "buy", 2)
        else:
            self.hud.show_action(surface, "toggle", 1, label=_("trade.show_shop"))
            self.hud.show_action(surface, "sell", 2)
