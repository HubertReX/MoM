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

import settings
from animation.transitions import AnimationTransition
from objects import ItemSprite, InventorySlot, Notification, NotificationTypeEnum
from settings import (
    ACTIONS,
    FONT_COLOR,
    FONT_SIZE_LARGE,
    FONT_SIZE_MEDIUM,
    FONT_SIZE_SMALL,
    INVENTORY_ITEM_SCALE,
    INVENTORY_ITEM_WIDTH,
    IS_WEB,
    ITEMS_SHEET_DEFINITION,
    MAX_HOTBAR_ITEMS,
    PANEL_BG_COLOR,
    TILE_SIZE,
    UI_BORDER_COLOR_ACTIVE,
    UI_BORDER_WIDTH,
    UI_COOL_OFF_COLOR,
    _,
)

from .. import keycap, layout, theme
from ..widget import Widget
from ..widgets.panel import Panel

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

# Shared distance from the screen edge to the *visible* edge of every anchored HUD
# element (stats, weapon, hotbar, action prompts, toasts). One token so the corners
# stay on a clean grid, a sliver of map still showing around each.
HUD_EDGE = TILE_SIZE

# The weapon panel's nine-patch is drawn this many px *outside* its logical box on
# every side (weapon_s = box + 2x this, blitted at box - this). So its visible edge
# is this much closer to the screen than the box coordinate suggests; the box has to
# be pushed in by the same amount for the visible frame to land on HUD_EDGE.
_WEAPON_FRAME_OVERHANG = 12

# vertical gap between two stacked toasts
_NOTIFICATION_GAP = 8
# text inset inside a toast box. pad_y has to clear the nine-patch frame art
# (~12px), or the last line of a tall toast sits under the bottom border.
_NOTIFICATION_PAD_X = 20
_NOTIFICATION_PAD_Y = 20


def hotbar_topleft(slots: int) -> tuple[int, int]:
    """Where a hotbar of ``slots`` slots starts, so it stays centred.

    Recomputed rather than cached: a quest can widen the hero's hotbar mid-game
    (decision D11), and a bar laid out once at construction would stay centred on
    the old width and drift off to the left.
    """
    return (
        settings.WIDTH // 2 - (INVENTORY_ITEM_WIDTH * slots // 2),
        settings.HEIGHT - INVENTORY_ITEM_WIDTH - TILE_SIZE,
    )


class HUD(Widget):
    def __init__(self, scene: "Scene") -> None:
        super().__init__()
        self.scene = scene
        self.game = scene.game
        # annotated explicitly: mypy runs with follow_imports=skip, so it cannot see
        # Scene's own annotation and every panel reading hud.icons inherits an
        # "cannot determine type" error
        self.icons: dict[str, list[pygame.Surface]] = scene.icons
        self.font: pygame.font.Font = self.game.fonts[FONT_SIZE_MEDIUM]
        self.tiny_font: pygame.font.Font = self.game.fonts[FONT_SIZE_SMALL]

        self.inventory_slot = InventorySlot(
            None,
            hotbar_topleft(MAX_HOTBAR_ITEMS),
            INVENTORY_ITEM_SCALE,
        )

        weapon_s = 2 * _WEAPON_FRAME_OVERHANG + TILE_SIZE * 8
        self.weapon_bg = theme.nine_patch("nine_patch_04.png", weapon_s, weapon_s)
        self.stats_bg = theme.nine_patch("nine_patch_04.png", 300, 190)
        self.available_action_bg = theme.nine_patch("panel_brown.png", 216, 36, border=3)

        # location panel: centred at the top, same vertical band as the stats panel.
        # Rozmiar pudełka liczy `Panel` z rozmiaru napisu - nazwa lokacji zależy od
        # języka i potrafi się zawinąć do dwóch linii („Tawerna Brakująca klepka"),
        # więc żadna z tych liczb nie ma prawa być stałą.
        self._location_panel = Panel("nine_patch_04.png", pad=(40, 32), name="HUD(location)")
        self._location_display: str = ""
        self._location_key: tuple[str, int] | None = None
        self._location_rt_surf: pygame.Surface | None = None
        self._update_location_cache()
        # wskaźnik questa (H01/D7): pudełko w LEWYM GÓRNYM rogu, nad stosem toastów.
        # Osobne pudełko, nie druga linia w panelu lokacji: nazwa mapy zmienia się
        # przy przejściu, a wskaźnik przy zdarzeniu questowym - wspólny cache
        # przerysowywałby oba za każdym razem.
        #
        # Był pod nazwą lokacji, na środku u góry - i to był błąd: środek górnej
        # krawędzi ma już nazwę mapy, a razem zasłaniały centralną część ekranu,
        # czyli dokładnie to miejsce, w którym gracz patrzy na akcję. Lewa górna
        # kolumna należy do rzeczy „tekstowych" (toasty), prawa górna do statystyk,
        # środek zostaje pusty.
        self._tracker_panel = Panel("nine_patch_04.png", pad=(28, 18), name="HUD(quest_tracker)")
        self._tracker_key: tuple[str, int, int] | None = None
        self._tracker_rt_surf: pygame.Surface | None = None

        # toast: ta sama zasada, inny wygląd ramki i ciaśniejszy odstęp
        self._notification_panel = Panel("nine_patch_04c.png", border=3,
                                         pad=(_NOTIFICATION_PAD_X, _NOTIFICATION_PAD_Y),
                                         name="HUD(toast)")
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
        # top-right corner, HUD_EDGE from both edges (toasts now own the top-left)
        top_left = (settings.WIDTH - self.stats_bg.get_width() - HUD_EDGE, HUD_EDGE)
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
        # relative to top_left, not absolute: the panel is no longer pinned to (16, 16)
        hb.set_bar(player.model.health / player.model.max_health,
                   (top_left[0] + 3 * TILE_SIZE + left_margin, top_left[1] + top_margin - 8))
        surface.blit(hb.image, hb.rect)

    #############################################################################################################
    # MARK: location panel

    def _update_location_cache(self) -> None:
        """Re-render the location name text when the map - or the language - changes.

        Cache key is the *rendered* name, not the map key: `_()` reads the live
        `settings.LANG`, so a language switch changes the string and invalidates the
        surface by itself, with no extra `rebuild_i18n()` hook on this panel (C02, D12).
        A map without a `[map]` entry falls back to its key - loud enough to notice,
        and `just validate-world` fails on it anyway (rule 12).
        """
        map_name = self.scene.current_map
        display = _(f"map.{map_name}")
        if display == f"map.{map_name}":       # brak wpisu - `_()` zwraca sam klucz
            display = map_name
        # klucz cache'u to (napis, szerokość ekranu): zmiana rozdzielczości zmienia
        # limit zawijania, więc stary surface przestaje pasować do nowego pudełka
        key = (display, settings.WIDTH)
        if key == self._location_key and self._location_rt_surf is not None:
            return
        self._location_key = key
        self._location_display = display
        from ..widgets.rich_text import render_tight
        # Zawijanie na tyle, ile pudełko może mieć - nie na magicznej stałej. Pudełko
        # jest wyśrodkowane, a w tym samym pasie stoi panel statystyk (prawy górny róg),
        # więc budżet to szerokość ekranu minus DWA razy miejsce zajęte przez statystyki.
        # Nazwa, która się w to nie mieści, wchodzi w drugą linię, a `Panel` urośnie
        # wzwyż - to jest cała różnica wobec zaszytej wysokości 76 px.
        side = self.stats_bg.get_width() + 2 * HUD_EDGE
        max_w, _max_h = self._location_panel.max_content_size(
            (settings.WIDTH - 2 * side, settings.HEIGHT - 2 * HUD_EDGE))
        self._location_rt_surf = render_tight(
            f"[center][shadow]{display}[/shadow][/center]",
            max_w,
            self.icons,
            base_size=FONT_SIZE_LARGE,
            base_color=theme.TITLE,
            show_scrollbar=False,
            name="HUD(location)",
        )

    def show_location_panel(self, surface: pygame.Surface) -> None:
        """Draw the current map name centred at the top of the screen."""
        self._update_location_cache()
        if self._location_rt_surf is None:
            return
        self._location_panel.draw(surface, self._location_rt_surf,
                                  anchor="midtop", offset=(0, HUD_EDGE))

    #############################################################################################################
    # MARK: quest tracker (H01/D7)

    def _update_tracker_cache(self) -> None:
        """Przerysuj linię wskaźnika, gdy zmieni się śledzony quest albo język.

        Ta sama sztuczka, co przy nazwie lokacji: kluczem cache'u jest GOTOWY
        napis, a nie klucz questa - `_()` i `get_msg()` czytają żywy
        `settings.LANG`, więc przełączenie języka samo unieważnia surface.
        """
        quests = getattr(self.scene, "quests", None)
        name = quests.tracked_name() if quests is not None else ""
        display = _("quest.tracker", name=name) if name else ""
        # szerokość pudełka lokacji jest częścią klucza: wskaźnik stoi po jego
        # LEWEJ, więc dłuższa nazwa mapy zabiera mu miejsce i wymaga przelania
        key = (display, settings.WIDTH, self._location_box_width())
        if key == self._tracker_key:
            return
        self._tracker_key = key
        if not display:
            self._tracker_rt_surf = None
            return
        from ..widgets.rich_text import render_tight
        # Wskaźnik dzieli górny pas z DWIEMA rzeczami: pudełkiem lokacji (środek)
        # i statystykami (prawy górny róg). Węższy z dwóch budżetów wygrywa -
        # inaczej przy wąskim oknie wskaźnik wjeżdżał pod nazwę mapy i zjadał jej
        # pierwszą literę. Tekst, który się nie mieści, zawija się na kolejną
        # linię, a `Panel` rośnie wzwyż (i tyle samo zjada stos toastów).
        max_w = min(self._left_column_text_width(self._tracker_panel),
                    self._space_left_of_location(self._tracker_panel))
        self._tracker_rt_surf = render_tight(
            display,
            max_w,
            self.icons,
            base_size=FONT_SIZE_SMALL,
            base_color=theme.WHITE,
            show_scrollbar=False,
            name="HUD(quest_tracker)",
        )

    def _location_box_width(self) -> int:
        """Szerokość pudełka z nazwą lokacji (0, gdy jeszcze nie ma napisu)."""
        surf = self._location_rt_surf
        return 0 if surf is None else surf.get_width() + 2 * self._location_panel.pad[0]

    def _space_left_of_location(self, panel: Panel) -> int:
        """Ile pikseli tekstu mieści się na LEWO od wyśrodkowanego pudełka lokacji."""
        free = (settings.WIDTH - self._location_box_width()) // 2 - HUD_EDGE - _NOTIFICATION_GAP
        return max(1, free - 2 * panel.pad[0])

    def _left_column_text_width(self, panel: Panel) -> int:
        """Ile pikseli tekstu mieści się w lewej kolumnie HUD-u, przy danym pudełku.

        Lewa kolumna (wskaźnik questa + toasty) kończy się tam, gdzie zaczyna się
        panel statystyk w prawym górnym rogu - obie rzeczy dzielą ten sam pas.
        """
        stats_left = settings.WIDTH - self.stats_bg.get_width() - HUD_EDGE
        return max(1, stats_left - HUD_EDGE - 2 * panel.pad[0] - _NOTIFICATION_GAP)

    def show_quest_tracker(self, surface: pygame.Surface) -> int:
        """Jedna linia „co teraz?" w lewym górnym rogu; zwraca wysokość pudełka.

        Wynik jest przesunięciem dla stosu toastów: toasty zatrzymują się POD
        wskaźnikiem, a gdy nie ma czego śledzić (brak pudełka, nie pusta ramka),
        jadą do samej góry, tak jak przed H01.

        Nie na środku u góry: tam stoi już nazwa lokacji, a dwa pudełka jedno pod
        drugim zasłaniały środek ekranu - czyli to miejsce, w którym gracz patrzy
        na akcję.
        """
        self._update_tracker_cache()
        if self._tracker_rt_surf is None:
            return 0
        rect = self._tracker_panel.draw(surface, self._tracker_rt_surf,
                                        pos=(HUD_EDGE, HUD_EDGE))
        # Keycap J okrakiem na LEWEJ krawędzi pudełka - ten sam chwyt, co klawisze
        # w oknie dialogowym: kapsel siedzi NA ramce, więc czyta się jako „ten
        # panel ma klawisz", a nie jako kolejna ikona w treści. Wskaźnik mówi „idź
        # tam", a jedyne, czego gracz o nim nie wie, to czym go otworzyć.
        #
        # Pozycja liczona z padu panelu, nie ze zgadniętego przesunięcia: prawa
        # krawędź capa ma stanąć jeden klik siatki (4 px) PRZED treścią, więc cap
        # nigdy nie dotknie pierwszej litery, choćby pad się zmienił. Reszta capa
        # wychodzi na ramkę i poza nią - pudełko stoi HUD_EDGE od brzegu ekranu,
        # więc jest gdzie wyjść, ale nie na tyle, żeby wyjechać poza ekran.
        cap = keycap.build_cap(
            self.icons, "J", theme.get_font(FONT_SIZE_SMALL), theme.WHITE)
        if cap is not None:
            cap_right = rect.left + self._tracker_panel.pad[0] - 4
            surface.blit(cap, (cap_right - cap.get_width(),
                               rect.centery - cap.get_height() // 2))
        return rect.height

    #############################################################################################################
    # MARK: hotbar

    def draw_hotbar(self, surface: pygame.Surface, npc: "NPC", top_left: tuple[int, int],
                    show_shortcuts: bool, *, tradable: bool = False) -> None:
        items = npc.get_tradable_items() if tradable else npc.items
        # per character, not the module constant: the hero's bar can grow (D11)
        for i in range(npc.max_items):
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
                         (top_left[0] + npc.max_items * INVENTORY_ITEM_WIDTH - 16, top_left[1] + h))

    #############################################################################################################
    # MARK: weapon

    def selection_box(self, surface: pygame.Surface, left: int, top: int, has_switched: bool,
                      cooldown: int = 100) -> pygame.Rect:
        item_box_size = TILE_SIZE * 8
        c = 1 - max(0, cooldown / 100)
        h = int(item_box_size * c)
        bg_cool_off_rect = pygame.Rect(left, top + item_box_size - h, item_box_size, h)
        bg_rect = pygame.Rect(left, top, item_box_size, item_box_size)
        surface.blit(self.weapon_bg,
                     bg_rect.move(-_WEAPON_FRAME_OVERHANG, -_WEAPON_FRAME_OVERHANG).topleft)
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
        # push the box in by the frame overhang so the *visible* nine-patch edge lands
        # HUD_EDGE from the screen (clean grid with the other HUD corners), not ~4px
        item_box_size = TILE_SIZE * 8
        box_left = HUD_EDGE + _WEAPON_FRAME_OVERHANG
        box_top = settings.HEIGHT - HUD_EDGE - item_box_size - _WEAPON_FRAME_OVERHANG
        bg_rect = self.selection_box(surface, box_left, box_top, has_switched, cooldown)
        if weapon:
            weapon_surf = pygame.transform.scale(weapon.image_directions["up"], (TILE_SIZE * 7, TILE_SIZE * 7))
            surface.blit(weapon_surf, weapon_surf.get_rect(center=bg_rect.center))
            if cooldown == 100:
                surface.blit(self.icons["key_Space"][0], bg_rect.move(4, 18).topright)

    #############################################################################################################
    # MARK: available actions
    #
    # The full keybindings reference moved to HelpPanel (a centered modal that pauses
    # the world). What stays here is the small contextual prompt bottom-right — the
    # "H — help" hint plus whatever the player can do right now (pick up, talk, ...).

    def show_action(self, surface: pygame.Surface, action: str, row: int, label: str = "") -> None:
        row_spacing = row * 48
        label = label or _(ACTIONS[action]["msg"])
        icon = self.icons[ACTIONS[action]["show"][0]][0]
        # panel geometry as named edges so the keycap can align to the panel's right
        # edge (was inset ~16px, reading as misaligned)
        panel_right = settings.WIDTH - HUD_EDGE
        panel_left = panel_right - self.available_action_bg.get_width()
        # bottom row's frame sits HUD_EDGE from the bottom, matching the other corners
        bg_y = settings.HEIGHT - HUD_EDGE - self.available_action_bg.get_height() - row_spacing
        surface.blit(self.available_action_bg, (panel_left, bg_y))
        icon_x = panel_right - icon.get_width()  # keycap right edge == panel right edge
        surface.blit(icon, (icon_x, bg_y + 2))
        # label right-aligned into the gap left of the keycap
        self.draw_text(surface, label, (icon_x - 8, bg_y + 9), align="right")
        # Ten box ma stałą szerokość (216 px), bo klawisz musi stać w jednej kolumnie
        # z klawiszami sąsiednich wierszy. Dziś najdłuższy napis to PL „rozmawiaj"
        # (144 px), ale nowa akcja albo nowy język zmieści się tu tylko przypadkiem -
        # niech się o tym dowiemy z rejestru, a nie ze zrzutu ekranu (A03).
        needed = self.font.size(label)[0] + 8 + icon.get_width()
        if needed > self.available_action_bg.get_width():
            layout.report_violation(
                f"HUD(action:{action})", "h-overflow",
                f"'{label}' + klawisz to {needed}px przy pudełku "
                f"{self.available_action_bg.get_width()}px",
            )

    def show_available_actions(self, surface: pygame.Surface) -> None:
        # the "H — help" hint hides while the help panel itself is open
        # (ui.show_help_info now reports whether HelpPanel is on the stack)
        if not self.scene.ui.show_help_info:
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
            from ..widgets.rich_text import render_tight
            # Wrap so the widest toast box still clears the stats panel: toasts now
            # rest at the top-left and the stats panel owns the top-right, sharing the
            # top band. Cap = stats_left - our own left inset - box padding - a gap.
            stats_left = settings.WIDTH - self.stats_bg.get_width() - HUD_EDGE
            max_text_w = stats_left - HUD_EDGE - 2 * _NOTIFICATION_PAD_X - _NOTIFICATION_GAP
            # quest toasts carry reward labels ("[num]+50[/num] :golden_coin:"), and
            # the coin is an item sprite rather than an emote - items go in first so
            # the emote sheet keeps the one name they share (`heart`)
            surf = render_tight(notification.message, max(1, max_text_w),
                                {**self.scene.items_sheet, **self.icons},
                                base_size=14, show_scrollbar=False,
                                # bump the inline icon a whole step (16px source -> crisp
                                # 32px, factor 2): the default ~1.35x snapped a toast emote
                                # back to native size and it read as unreadably tiny
                                icon_scale=2.0,
                                extra_emojis=frozenset(ITEMS_SHEET_DEFINITION),
                                name="HUD(toast)")
            self._notification_cache[notification.message] = surf
        return surf

    def show_notification(
        self, surface: pygame.Surface, notification: Notification, stack_offset: int
    ) -> int:
        """Draw one toast, its top ``stack_offset`` px below the resting anchor.

        Returns the drawn box height so the caller can place the next toast under
        it — toasts vary in height, so the pitch has to be measured, not assumed.
        """
        # from show_time, not create_time: a queued toast would otherwise have
        # burned its slide-in while waiting and pop in fully arrived
        time_elapsed = self.game.time_elapsed - notification.show_time

        y_bottom = settings.HEIGHT - TILE_SIZE
        # rest at the very top-left now that the stats panel has vacated that corner;
        # toasts slide up from the bottom and stack downward from HUD_EDGE
        y_stop = HUD_EDGE + stack_offset
        factor = AnimationTransition.in_out_expo(min(1.0, time_elapsed / 1.0))
        y = int(y_bottom + (y_stop - y_bottom) * factor)

        # The leading emote (type icon, or the chosen option's sentiment for sentiment
        # toasts) is part of the RichText message inline — no separate overlay copy.
        # Box size comes from the text via `Panel`, so a four-line quest toast simply
        # gets a taller box instead of running out under its own frame.
        text_surf = self._notification_surface(notification)
        return self._notification_panel.draw(surface, text_surf, pos=(HUD_EDGE, y)).height

    #############################################################################################################
    # MARK: compose
    #
    # Drawn in two parts so the UI controller can layer panels between them, matching the
    # original order: gameplay overlay (weapon/hotbar) under modal/dialog/trade, then
    # the always-on overlay (notifications + stats) on top of everything. The help
    # reference is its own modal panel now, drawn by GameUI on top of this.

    def draw_gameplay(self, surface: pygame.Surface, enabled: bool = True) -> None:
        if not enabled:
            return
        player: Player = self.scene.player
        self.show_weapon_panel(surface, player.selected_weapon, not player.can_switch_weapon,
                               self.game.time_elapsed)
        # recomputed per frame: the hero's bar widens when a quest rewards slots
        self.draw_hotbar(surface, player, hotbar_topleft(player.max_items), show_shortcuts=True)
        self.show_available_actions(surface)

    def draw_overlay(self, surface: pygame.Surface, *, stats: bool = True,
                     labels: bool = True) -> None:
        # Stack by each toast's real height, not a fixed row pitch: a quest-done
        # toast can run to four lines (a wrapped [h3] headline plus success prose),
        # and a fixed 50px step let the tall one overlap the toast below it. Only
        # the *visible* ones count — a queued toast reserves no space.
        # A full-screen panel (the journal) covers the stats box; drawing it on top
        # would put the hero's HP over the quest title. Notifications stay: they are
        # transient news and the player should not miss one for having the log open.
        if stats:
            self.show_stats_panel(surface, self.scene.player)
        # Nazwa lokacji i wskaźnik questa to ETYKIETY ŚWIATA, nie stan bohatera:
        # gasną pod każdym panelem blokującym (handel, dialog, dziennik, pomoc),
        # bo rysowały się NA panelu handlu i zasłaniały jego górną krawędź.
        # Toasty zostają zawsze - to nowiny, których gracz nie ma prawa przegapić
        # przez to, że akurat ma coś otwarte.
        offset = 0
        if labels:
            # lokacja PRZED wskaźnikiem: wskaźnik liczy swoją szerokość z tego,
            # ile miejsca zostawiło mu pudełko lokacji
            self.show_location_panel(surface)
            tracker_h = self.show_quest_tracker(surface)
            if tracker_h:
                offset = tracker_h + _NOTIFICATION_GAP
        # Toasts LAST, so they land on top of the location name. Both live in the same
        # top band - toasts at the left edge, the location box centred - and a wide
        # toast reaches the centre, where the location panel used to bury it.
        for notification in self.scene.visible_notifications():
            offset += self.show_notification(surface, notification, offset) + _NOTIFICATION_GAP
