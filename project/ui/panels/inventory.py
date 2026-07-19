"""InventoryPanel: the player's inventory overlay (toggled with I).

Shows the selected item's stats over a bordered panel. The hotbar itself is still drawn
by the HUD on top (matching the original draw order). ``draw_item_details`` and
``build_inventory_bg`` are shared with the trade panel.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pygame

import settings
from settings import _, entity_name

from .. import theme
from ..widget import Widget

if TYPE_CHECKING:
    from scene import Scene

    from .hud import HUD

_DIVIDER = theme.DIVIDER


def build_inventory_bg() -> pygame.Surface:
    """Inventory background (800x320) with the two divider lines drawn once."""
    bg = theme.nine_patch("nine_patch_04.png", 800, 320).copy()
    pygame.draw.line(bg, _DIVIDER, (bg.get_width() // 2, 70), (bg.get_width() // 2, 160), 4)
    pygame.draw.line(bg, _DIVIDER, (40, 180), (bg.get_width() - 40, 180), 4)
    return bg


def draw_item_details(hud: "HUD", surface: pygame.Surface, props_top_left: tuple[int, int],
                      props_top_middle: tuple[int, int], item_model: Any,
                      price: int | None = None, *, panel_w: int = 0) -> None:
    from settings import IS_WEB
    if IS_WEB:
        from config_model.config import ItemTypeEnum
    else:
        from config_model.config_pydantic import ItemTypeEnum  # type: ignore[assignment]

    value_label = _("inv.price") if price is not None else _("inv.value")
    value_text = f"{price:4d}" if price is not None else f"{item_model.value:4d}"
    left_col_cx = props_top_left[0] + panel_w // 2 if panel_w else 0
    left_properties = [
        {"icon_name": "", "label": "", "value": entity_name(item_model)},
        {"icon_name": "pan_balance", "label": _("inv.weight"), "value": f"{item_model.weight:4.2f}"},
        {"icon_name": "golden_coin", "label": value_label, "value": value_text},
        {"icon_name": "abacus2", "label": _("inv.amount"), "value": f"{item_model.count:4d}"},
    ]
    for row, prop in enumerate(left_properties):
        hud.draw_icon_label_value(surface, props_top_left, row, prop,
                                  name_center_x=left_col_cx if row == 0 else None)

    right_properties: list[dict[str, str]] = [
        {"icon_name": "", "label": "", "value": ""},
        {"icon_name": "red_question", "label": _("inv.type"), "value": _(f"item_type.{item_model.type.value}")},
    ]
    if item_model.type == ItemTypeEnum.weapon:
        right_properties.append({"icon_name": "big_heart", "label": _("inv.damage"), "value": f"{-item_model.damage:4d}"})
        right_properties.append({"icon_name": "hourglass", "label": _("inv.cooldown"),
                                 "value": f"{item_model.cooldown_time:4.2f}"})
    if item_model.type == ItemTypeEnum.consumable:
        right_properties.append({"icon_name": "big_heart", "label": _("inv.health"),
                                 "value": f"{item_model.health_impact:+4d}"})
    for row, prop in enumerate(right_properties):
        hud.draw_icon_label_value(surface, props_top_middle, row, prop)


class InventoryPanel(Widget):
    def __init__(self, scene: "Scene", hud: "HUD") -> None:
        super().__init__()
        self.scene = scene
        self.hud = hud
        self.bg = build_inventory_bg()
        self._reposition()

    def _reposition(self) -> None:
        """Center horizontally and anchor near the bottom of the current viewport."""
        self.rect = self.bg.get_rect(
            topleft=(settings.WIDTH // 2 - self.bg.get_width() // 2, settings.HEIGHT - 320))

    def open(self) -> None:
        # Re-fit to the current viewport: the panel is cached by the UI, so the
        # resolution may have changed since it was built.
        self._reposition()

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        player = self.scene.player
        surface.blit(self.bg, self.rect.topleft)
        if player.selected_item_idx < 0:
            return
        item_model = player.items[player.selected_item_idx].model
        draw_item_details(self.hud, surface, self.rect.topleft, self.rect.midtop, item_model,
                          panel_w=self.bg.get_width())
        surface.blit(self.hud.icons["key_I"][0], (self.rect.left + self.rect.width - 8, self.rect.top + 40))
