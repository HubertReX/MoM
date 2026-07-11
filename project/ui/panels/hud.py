"""HUD: always-on gameplay overlay (stats, hotbar, weapon, help/actions, notifications).

Ported from the legacy UI display_* methods. Differences that matter:
  * every nine-patch background is fetched from the cached theme registry (no per-frame
    NinePatch scaling);
  * notifications render their rich text once and cache it by message string (the old
    code rebuilt an sftext object every frame for every visible notification);
  * the empty throw-away SRCALPHA surfaces the old selection_box/box created each frame
    are gone.

Drawing helpers (draw_text, draw_hotbar, draw_icon_value, draw_icon_label_value) are
reused by the inventory and trade panels.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import pygame

from animation.transitions import AnimationTransition
from objects import ItemSprite, InventorySlot, Notification, NotificationTypeEnum
from settings import (
    ACTIONS,
    FONT_COLOR,
    FONT_SIZE_MEDIUM,
    FONT_SIZE_SMALL,
    HEIGHT,
    INVENTORY_ITEM_SCALE,
    INVENTORY_ITEM_WIDTH,
    IS_WEB,
    MAX_HOTBAR_ITEMS,
    PANEL_BG_COLOR,
    SHOW_HELP_INFO,
    TILE_SIZE,
    UI_BORDER_COLOR_ACTIVE,
    UI_BORDER_WIDTH,
    UI_COOL_OFF_COLOR,
    WIDTH,
    _,
)

from .. import theme
from ..widget import Widget

if TYPE_CHECKING:
    from characters import NPC, Player
    from scene import Scene

if IS_WEB:
    from config_model.config import ItemTypeEnum
else:
    from config_model.config_pydantic import ItemTypeEnum  # type: ignore[assignment]


NOTIFICATION_TYPE_ICONS: dict[str, str] = {
    NotificationTypeEnum.debug.value:   "human",
    NotificationTypeEnum.info.value:    "dots_anim",
    NotificationTypeEnum.warning.value: "exclamation",
    NotificationTypeEnum.error.value:   "red_exclamation_anim",
    NotificationTypeEnum.success.value: "blessed_anim",
    NotificationTypeEnum.failure.value: "shocked_anim",
}


class HUD(Widget):
    def __init__(self, scene: "Scene") -> None:
        super().__init__()
        self.scene = scene
        self.game = scene.game
        self.icons = scene.icons
        self.font: pygame.font.Font = self.game.fonts[FONT_SIZE_MEDIUM]
        self.tiny_font: pygame.font.Font = self.game.fonts[FONT_SIZE_SMALL]
        self.show_help_info: bool = SHOW_HELP_INFO

        self.inventory_slot = InventorySlot(
            None,
            (WIDTH // 2 - (INVENTORY_ITEM_WIDTH * MAX_HOTBAR_ITEMS // 2),
             HEIGHT - INVENTORY_ITEM_WIDTH - TILE_SIZE),
            INVENTORY_ITEM_SCALE,
        )

        weapon_s = 24 + TILE_SIZE * 8
        self.weapon_bg = theme.nine_patch("nine_patch_04.png", weapon_s, weapon_s)
        self.stats_bg = theme.nine_patch("nine_patch_04.png", 300, 190)
        self.available_action_bg = theme.nine_patch("panel_brown.png", 216, 36, border=3)

        show_actions = [action for action in ACTIONS.values() if action["show"]]
        help_h = int((len(show_actions) + 2) * FONT_SIZE_MEDIUM * 2.1)
        self.help_bg = theme.nine_patch("nine_patch_04.png", 400, help_h)

        self.help_scroll: int = 0
        self.help_max_scroll: int = 0
        self.help_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)

        # cache: notification message string -> pre-rendered rich-text surface
        self._notification_cache: dict[str, pygame.Surface] = {}

    #############################################################################################################
    # MARK: text helper

    def draw_text(
        self,
        surface: pygame.Surface,
        text: str,
        pos: tuple[int, int],
        *,
        font: pygame.font.Font | None = None,
        align: Literal["left", "centred", "right"] = "left",
        color: pygame._common.ColorValue | None = None,
        shadow: bool = True,
        border: pygame._common.ColorValue = PANEL_BG_COLOR,
    ) -> None:
        font = font or self.font
        color = FONT_COLOR if color is None else color
        text_surf = font.render(str(text), False, color)
        if align == "left":
            text_rect = text_surf.get_rect(topleft=pos)
        elif align == "centred":
            text_rect = text_surf.get_rect(center=pos)
        else:
            text_rect = text_surf.get_rect(topright=pos)

        if border:
            border_surf = font.render(str(text), False, border)
            offset = 2 if shadow else 3
            surface.blit(border_surf, (text_rect.x + offset, text_rect.y + offset))
            if not shadow:
                for dx, dy in ((-offset, 0), (offset, 0), (0, -offset), (0, offset), (-offset, -offset)):
                    surface.blit(border_surf, (text_rect.x + dx, text_rect.y + dy))

        surface.blit(text_surf, text_rect)

    #############################################################################################################
    # MARK: stats

    def draw_icon_value(self, surface: pygame.Surface, top_left: tuple[int, int], row: int,
                        property: dict[str, str]) -> None:
        left_margin, top_margin, row_height = 30, 40, 35
        icon_offset = -TILE_SIZE // 2
        if property["icon_name"]:
            if property["icon_name"] in self.scene.items_sheet:
                item_sprite = self.scene.items_sheet[property["icon_name"]][0]
            else:
                item_sprite = self.scene.icons[property["icon_name"]][0]
            icon = pygame.transform.scale_by(item_sprite, 2)
            surface.blit(icon, (top_left[0] + left_margin, top_left[1] + top_margin + icon_offset + row_height * row))
        if property["value"]:
            self.draw_text(surface, property["value"], color=(0, 197, 199),
                           pos=(top_left[0] + 3 * TILE_SIZE + left_margin, top_left[1] + top_margin + row_height * row))

    def draw_icon_label_value(self, surface: pygame.Surface, top_left: tuple[int, int], row: int,
                              property: dict[str, str], *,
                              name_center_x: int | None = None) -> None:
        left_margin, top_margin, row_height = 30, 40, 35
        icon_offset = -TILE_SIZE // 2
        if property["icon_name"]:
            if property["icon_name"] in self.scene.items_sheet:
                item_sprite = self.scene.items_sheet[property["icon_name"]][0]
            else:
                item_sprite = self.scene.icons[property["icon_name"]][0]
            icon = pygame.transform.scale_by(item_sprite, 2)
            surface.blit(icon, (top_left[0] + left_margin, top_left[1] + top_margin + icon_offset + row_height * row))
        if property["label"]:
            self.draw_text(surface, property["label"], color=(255, 255, 255),
                           pos=(top_left[0] + 3 * TILE_SIZE + left_margin, top_left[1] + top_margin + row_height * row))
        if property["value"]:
            if name_center_x is not None and not property["icon_name"] and not property["label"]:
                self.draw_text(surface, property["value"], color=(0, 197, 199), align="centred",
                               pos=(name_center_x, top_left[1] + top_margin + row_height * row))
            else:
                self.draw_text(surface, property["value"], color=(0, 197, 199), align="right",
                               pos=(top_left[0] + 20 * TILE_SIZE + left_margin,
                                    top_left[1] + top_margin + row_height * row))

    def show_stats_panel(self, surface: pygame.Surface, player: "Player") -> None:
        top_left = (TILE_SIZE, TILE_SIZE)
        surface.blit(self.stats_bg, top_left)
        left_margin, top_margin = 30, 40
        properties = [
            {"icon_name": "big_heart", "value": ""},
            {"icon_name": "pan_balance",
             "value": f"{player.total_items_weight:4.2f}/{player.model.max_carry_weight:4.2f}"},
            {"icon_name": "hourglass", "value": _("hud.datetime", day=self.scene.day, hour=self.scene.hour, min=self.scene.minute)},
            {"icon_name": "golden_coin", "value": f"{player.model.money}"},
        ]
        for row, prop in enumerate(properties):
            self.draw_icon_value(surface, top_left, row, prop)

        hb = player.health_bar_ui
        hb.set_bar(player.model.health / player.model.max_health,
                   (4 * TILE_SIZE + left_margin, TILE_SIZE + top_margin - 8))
        surface.blit(hb.image, hb.rect)

    #############################################################################################################
    # MARK: hotbar

    def draw_hotbar(self, surface: pygame.Surface, npc: "NPC", top_left: tuple[int, int],
                    show_shortcuts: bool, *, tradable: bool = False) -> None:
        items = npc.get_tradable_items() if tradable else npc.items
        for i in range(MAX_HOTBAR_ITEMS):
            item_model = items[i].model if i < len(items) else None
            if npc.selected_weapon and npc.selected_weapon.model == item_model:
                image = self.inventory_slot.image_selected
            else:
                image = self.inventory_slot.image
            surface.blit(image, (top_left[0] + i * INVENTORY_ITEM_WIDTH, top_left[1]))

            if i < len(items):
                if i == npc.selected_item_idx and show_shortcuts:
                    surface.blit(self.inventory_slot.image_selector,
                                 (top_left[0] + i * INVENTORY_ITEM_WIDTH, top_left[1]))
                item: ItemSprite = items[i]
                if item.model.type == ItemTypeEnum.weapon:
                    image = item.image_directions["up"]
                else:
                    image = item.image or pygame.Surface((TILE_SIZE, TILE_SIZE))
                image = pygame.transform.scale_by(image, INVENTORY_ITEM_SCALE)
                surface.blit(image, (10 + top_left[0] + i * INVENTORY_ITEM_WIDTH, 12 + top_left[1]))
                self.draw_text(surface, str(item.model.count),
                               (12 + top_left[0] + i * INVENTORY_ITEM_WIDTH, 16 + top_left[1]), font=self.tiny_font)

            if show_shortcuts and i <= len(items) - 1:
                surface.blit(self.icons[f"key_{i + 1}"][0],
                             (top_left[0] + 2 + i * INVENTORY_ITEM_WIDTH + INVENTORY_ITEM_WIDTH // 4,
                              top_left[1] - 22))

        if show_shortcuts:
            h = 24
            surface.blit(self.icons["key_<"][0], (top_left[0] - 24, top_left[1] + h))
            surface.blit(self.icons["key_>"][0],
                         (top_left[0] + MAX_HOTBAR_ITEMS * INVENTORY_ITEM_WIDTH - 16, top_left[1] + h))

    #############################################################################################################
    # MARK: weapon

    def selection_box(self, surface: pygame.Surface, left: int, top: int, has_switched: bool,
                      cooldown: int = 100) -> pygame.Rect:
        item_box_size = TILE_SIZE * 8
        c = 1 - max(0, cooldown / 100)
        h = int(item_box_size * c)
        bg_cool_off_rect = pygame.Rect(left, top + item_box_size - h, item_box_size, h)
        bg_rect = pygame.Rect(left, top, item_box_size, item_box_size)
        surface.blit(self.weapon_bg, bg_rect.move(-12, -12).topleft)
        pygame.draw.rect(surface, UI_COOL_OFF_COLOR, bg_cool_off_rect)
        if has_switched:
            pygame.draw.rect(surface, UI_BORDER_COLOR_ACTIVE, bg_rect, UI_BORDER_WIDTH)
        return bg_rect

    def show_weapon_panel(self, surface: pygame.Surface, weapon: "ItemSprite | None",
                          has_switched: bool, elapsed_time: float) -> None:
        player = self.scene.player
        if player.is_attacking:
            now = elapsed_time - player.attack_time
            weapon_cooldown = player.selected_weapon.model.cooldown_time if player.selected_weapon else 0.0
            limit = (player.attack_cooldown / 1000.0) + weapon_cooldown
            cooldown = min(100, int(now / limit * 100))
        else:
            cooldown = 100
        bg_rect = self.selection_box(surface, TILE_SIZE, HEIGHT - (TILE_SIZE * 9), has_switched, cooldown)
        if weapon:
            weapon_surf = pygame.transform.scale(weapon.image_directions["up"], (TILE_SIZE * 7, TILE_SIZE * 7))
            surface.blit(weapon_surf, weapon_surf.get_rect(center=bg_rect.center))
            if cooldown == 100:
                surface.blit(self.icons["key_Space"][0], bg_rect.move(4, 18).topright)

    #############################################################################################################
    # MARK: help / actions

    def show_help(self, surface: pygame.Surface) -> None:
        if not self.show_help_info:
            return
        show_actions = [action for action in ACTIONS.values() if action["show"]]
        row_spacing = 2.2
        row_height = int(FONT_SIZE_MEDIUM * row_spacing)
        content_w = 400
        panel_x = WIDTH - content_w - 16
        content_h = (len(show_actions) + 1) * row_height
        max_h = HEIGHT - TILE_SIZE
        visible_h = min(content_h, max_h)
        self.help_max_scroll = max(0, content_h - visible_h)
        self.help_scroll = max(0, min(self.help_scroll, self.help_max_scroll))
        rect = pygame.Rect(panel_x, TILE_SIZE // 2, content_w, visible_h)
        self.help_rect = rect

        old_clip = surface.get_clip()
        surface.set_clip(rect)
        surface.blit(self.help_bg, rect.topleft, area=pygame.Rect(0, self.help_scroll,
                      content_w, visible_h))
        for i, action in enumerate(show_actions, start=1):
            y = 2 + int(i * row_height) - self.help_scroll
            self.draw_text(surface, _(action['msg']),
                           (panel_x + 50, y), shadow=True)
            surface.blit(self.icons[action['show'][0]][0],
                         (panel_x + 16, -6 + int(i * row_height) - self.help_scroll))
        surface.set_clip(old_clip)

    def _on_event(self, event: pygame.event.Event) -> bool:
        if not self.show_help_info:
            return False
        if event.type == pygame.MOUSEWHEEL and self.help_rect.collidepoint(pygame.mouse.get_pos()):
            self.help_scroll = max(0, min(self.help_max_scroll, self.help_scroll - event.y * 40))
            return True
        return False

    def show_action(self, surface: pygame.Surface, action: str, row: int, label: str = "") -> None:
        row_spacing = row * 48
        label = label or _(ACTIONS[action]["msg"])
        icon = self.icons[ACTIONS[action]["show"][0]][0]
        label_w, _h = self.font.size(label)
        surface.blit(self.available_action_bg, (WIDTH - TILE_SIZE - 216, HEIGHT - (2 * TILE_SIZE) - 16 - row_spacing))
        surface.blit(icon, (WIDTH - (2 * TILE_SIZE) - 32, HEIGHT - (2 * TILE_SIZE) - 14 - row_spacing))
        self.draw_text(surface, label, (WIDTH - TILE_SIZE - label_w - 56, HEIGHT - (2 * TILE_SIZE) - 7 - row_spacing))

    def show_available_actions(self, surface: pygame.Surface) -> None:
        if not self.show_help_info:
            self.show_action(surface, "help", 0)
        player: Player = self.scene.player
        if not player.is_flying and not player.is_attacking and not player.is_stunned:
            items = self.scene.item_sprites.sprites()
            if player.feet.collidelist(items) > -1:  # type: ignore[type-var]
                self.show_action(surface, "pick_up", 1)
        if player.selected_item_idx >= 0:
            self.show_action(surface, "drop", 2)
            item: ItemSprite = player.items[player.selected_item_idx]
            label = ""
            if item.model.type == ItemTypeEnum.consumable:
                label = _("action.consume")
            elif item.model.type == ItemTypeEnum.weapon:
                if player.selected_weapon and player.selected_weapon.name == item.name:
                    label = _("action.disarm")
                else:
                    label = _("action.equip")
            self.show_action(surface, "use_item", 3, label=label)
        if player.chest_in_range:
            self.show_action(surface, "open", 4, label=_("action.open_chest"))
        elif player.npc_met:
            if player.npc_met.has_dialog:
                self.show_action(surface, "talk", 4)
            elif player.npc_met.model.is_merchant:
                self.show_action(surface, "trade", 4)

    #############################################################################################################
    # MARK: notifications

    def _notification_surface(self, notification: Notification) -> pygame.Surface:
        """Render (and cache) a notification's rich text once, cropped tight to its content."""
        surf = self._notification_cache.get(notification.message)
        if surf is None:
            from ..widgets.rich_text import RichText
            rt = RichText(notification.message, (0, 0, WIDTH - 300, 400), self.icons,
                          base_size=14, show_scrollbar=False)
            full = rt.content_surface
            assert full is not None
            w = max(1, min(rt.content_width, full.get_width()))
            surf = full.subsurface((0, 0, w, full.get_height())).copy()
            self._notification_cache[notification.message] = surf
        return surf

    def show_notification(self, surface: pygame.Surface, notification: Notification, row: int) -> None:
        row_spacing = row * 50
        time_elapsed = self.game.time_elapsed - notification.create_time

        y_bottom = HEIGHT - TILE_SIZE
        y_stop = 230 + row_spacing
        factor = AnimationTransition.in_out_expo(min(1.0, time_elapsed / 1.0))
        y = int(y_bottom + (y_stop - y_bottom) * factor)

        text_surf = self._notification_surface(notification)
        tw, th = text_surf.get_size()

        # Sentiment emote drawn separately to the left of the text.
        emote_surf: pygame.Surface | None = None
        emote_w = 0
        if notification.emote_key:
            frames = self.icons.get(notification.emote_key, [])
            if frames:
                font_h = theme.get_font(14).get_height()
                target_h = round(font_h * 1.35)
                src = frames[0]
                sw, sh = src.get_size()
                s = target_h / sh if sh else 1.0
                emote_surf = pygame.transform.scale(src, (max(1, round(sw * s)), target_h))
                emote_w = emote_surf.get_width() + 4  # 4px gap

        total_w = tw + emote_w
        pad_x, pad_y = 20, 10
        bg = theme.nine_patch("nine_patch_04c.png", total_w + 2 * pad_x, th + 2 * pad_y, border=3)
        surface.blit(bg, (TILE_SIZE, y))
        # Centre the text+emote block inside the panel (both axes), then shift
        # down 3px so it doesn't ride up into the border.
        text_x = TILE_SIZE + (bg.get_width() - total_w) // 2 + (emote_w - 8 if emote_w else 0)
        text_y = y + (bg.get_height() - th) // 2 + 3
        surface.blit(text_surf, (text_x, text_y))

        if emote_surf is not None:
            emote_x = text_x - emote_w + 24
            emote_y = text_y + (th - emote_surf.get_height()) // 2 - 3
            surface.blit(emote_surf, (emote_x, emote_y))

    #############################################################################################################
    # MARK: compose
    #
    # Drawn in two parts so the UI controller can layer panels between them, matching the
    # original order: gameplay overlay (weapon/hotbar/help) under modal/dialog/trade, then
    # the always-on overlay (notifications + stats) on top of everything.

    def draw_gameplay(self, surface: pygame.Surface, enabled: bool = True) -> None:
        if not enabled:
            return
        player: Player = self.scene.player
        self.show_weapon_panel(surface, player.selected_weapon, not player.can_switch_weapon,
                               self.game.time_elapsed)
        self.draw_hotbar(surface, player, self.inventory_slot.rect.topleft, show_shortcuts=True)
        if self.show_help_info:
            self.show_help(surface)
        else:
            self.show_available_actions(surface)

    def draw_overlay(self, surface: pygame.Surface) -> None:
        for row, notification in enumerate(self.scene.notifications):
            self.show_notification(surface, notification, row)
        self.show_stats_panel(surface, self.scene.player)
