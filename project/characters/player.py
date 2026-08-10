"""Klasa ``Player`` - postać gracza (podklasa :class:`NPC`).

Wydzielona z ``characters.py`` w kroku 10 refactoru B01 (przeniesienie bez
zmian w metodach). Kontrakt K4: ``from characters import NPC, Player`` działa
jak przed podziałem na pakiet. Decyzja D2: dziedziczenie ``Player(NPC)``
zostaje, podział jest tylko na pliki.
"""
from rich import print

import pygame
from pygame.math import Vector2 as vec
from settings import (
    INVENTORY_ITEM_SCALE,
    INPUTS,
    JOY_MOVE_MULTIPLIER,
    MOM_DEBUG_TALK,
    TILE_SIZE,
    _,
    entity_name,
    get_buy_price_multiplier,
    get_msg,
    get_sell_price_multiplier,
    Point,
)
from enums import ItemTypeEnum, NPCEventActionEnum

import audio
import game
import scene
from characters.npc import NPC
from objects import HealthBarUI, NotificationTypeEnum
from scene import player_actions
from ui.panels.dialog import DialogPanel
from ui.panels.trade import TradePanel


#################################################################################################################
# MARK: Player


# @dataclass(slots=True, unsafe_hash=True)
# @dataclass(slots=True, frozen=True)
class Player(NPC):
    def __init__(
            self,
            game: game.Game,
            scene: scene.Scene,
            shadow_group: pygame.sprite.Group,
            label_group: pygame.sprite.Group,
            pos: tuple[int, int],
            name: str,
            emotes: dict[str, list[pygame.Surface]],
            model_name: str = "",
    ):
        self.name = name
        if not model_name:
            model_name = self.name

        super(Player, self).__init__(game, scene, shadow_group, label_group, pos, name, emotes, model_name=model_name)
        # give player some super powers
        self.speed_run  = int(self.speed_run * 1.7)
        self.speed_walk = int(self.speed_walk * 1.4)
        self.speed = self.speed_run
        self.health_bar_ui = self.create_health_bar_ui(label_group, pos, INVENTORY_ITEM_SCALE)
        #: Nazwa zamkniętych drzwi, o których gracz już usłyszał (H01/D8). Kolizja
        #: z progiem trzyma się przez wiele klatek, więc bez tego komunikat
        #: „brakuje klucza" leciałby co klatkę. Czyszczone, gdy gracz zejdzie
        #: z progu - następne podejście znów ma prawo do komunikatu.
        self._locked_door_told: str = ""
        # label_group.remove(self.health_bar)
    #############################################################################################################

    def __hash__(self) -> int:
        return hash(self.name)

    #############################################################################################################

    def create_health_bar_ui(
        self,
        label_group: pygame.sprite.Group,
        pos: tuple[int, int],
        scale: int = 1
    ) -> HealthBarUI:
        # self.wrong: bool = True
        return HealthBarUI(self.model, label_group, pos, scale)

    #############################################################################################################
    def movement(self) -> None:
        global INPUTS
        if self.is_stunned or self.is_attacking:
            return

        if INPUTS["open"]:
            if self.chest_in_range and self.chest_in_range.model.is_closed and not self.is_talking:
                chest = self.chest_in_range
                # Zamek (H01/D8): odmowa nazywa brakujący klucz i NIE otwiera
                # skrzyni. Ta sama funkcja obsługuje drzwi - jeden kształt zamka
                # w dwóch miejscach, nie dwa mechanizmy.
                if not player_actions.unlock(
                    self.scene,
                    getattr(chest.model, "requires_item", "") or "",
                    bool(getattr(chest.model, "consumes_key", False)),
                ):
                    INPUTS["open"] = False
                    return
                chest.open()
                audio.play_sfx("chest_open")
                self.scene.add_notification(_("notify.chest_opened"), NotificationTypeEnum.success)
                for item_name in chest.model.items:
                    # print(f"[light_green] '{item_name}' item from chest")
                    chest_pos = vec(self.chest_in_range.rect.centerx, self.chest_in_range.rect.centery)
                    pos: vec = self.get_random_safe_pos(
                        chest_pos, range=1.5, check_allowed_zones=False, allow_start_pos=False)
                    rect = pygame.Rect(0, 0, TILE_SIZE, TILE_SIZE)
                    rect.center = pos  # type: ignore[assignment]
                    item = self.scene.create_item(item_name, rect.left, rect.top)
                    self.scene.items.append(item)
                    self.scene.group.add(item, layer=self.scene.sprites_layer - 1)
            INPUTS["open"] = False
        elif INPUTS["talk"]:
            if MOM_DEBUG_TALK:
                self.game.log(
                    f"[DEBUG talk] npc_met={getattr(self.npc_met, 'name', None)}, "
                    f"has_dialog={getattr(self.npc_met, 'has_dialog', None) if self.npc_met else None}, "
                    f"is_talking={self.is_talking}, "
                    f"dialog={getattr(self.npc_met, 'dialog', None) is not None if self.npc_met else None}")
            if self.npc_met and (self.npc_met.has_dialog or self.npc_met.model.is_merchant) and not self.is_talking:
                # dialog or trading?
                if self.npc_met.has_dialog and self.npc_met.dialog is not None:
                    text = get_msg(self.game.conf.messages, self.npc_met.dialog.text)
                    self.scene.ui.open(DialogPanel, npc=self.npc_met, text=text)
                    if MOM_DEBUG_TALK:
                        self.game.log(f"[DEBUG talk] opened DialogPanel for {self.npc_met.name} "
                                      f"at node {self.npc_met.dialog.key}")
                else:
                    # since trader might accept only selected types of items
                    # selected item index needs to be initiated again
                    filtered_items = self.get_tradable_items()
                    if len(filtered_items) > 0:

                        selected_item = self.items[self.selected_item_idx]
                        if selected_item not in filtered_items:
                            self.selected_item_idx = 0
                        else:
                            self.selected_item_idx = filtered_items.index(selected_item)

                        self.scene.ui.open(TradePanel)
                self.is_talking = True
                self.npc_met.is_talking = True
            INPUTS["talk"] = False

        if INPUTS["end_trade"]:
            if self.scene.ui.is_open(TradePanel):
                self.scene.ui.close(TradePanel)
                # since trader might might accepted only selected types of items
                # selected item index needs to be initiated again
                filtered_items = self.get_tradable_items()
                selected_item = filtered_items[self.selected_item_idx]
                self.selected_item_idx = self.items.index(selected_item)

                self.is_talking = False
                if self.npc_met:
                    self.npc_met.is_talking = False
                INPUTS["quit"] = False
            INPUTS["end_trade"] = False

        if INPUTS["toggle"]:
            if self.scene.ui.is_open(TradePanel):
                self.scene.ui.toggle_trade_side()
            INPUTS["toggle"] = False

        if INPUTS["buy"]:
            if self.scene.ui.is_open(TradePanel) and self.npc_met and self.scene.ui.is_buying:
                if self.can_buy():
                    item_to_buy = self.npc_met.drop_item(show=False)
                    if item_to_buy:
                        price = int(round(item_to_buy.model.value * get_buy_price_multiplier(self.npc_met.sentiment)))
                        self.model.money -= price
                        self.npc_met.model.money += price
                        self.pick_up(item_to_buy)
                        audio.play_sfx("coins")
                        self.scene.add_notification(
                            _("notify.bought", name=entity_name(item_to_buy.model), price=price),
                            NotificationTypeEnum.info)
            INPUTS["buy"] = False

        if INPUTS["sell"]:
            if self.scene.ui.is_open(TradePanel) and self.npc_met and not self.scene.ui.is_buying:
                if self.can_sell():
                    item_to_sell = self.drop_item(show=False)
                    if item_to_sell:
                        price = int(round(item_to_sell.model.value * get_sell_price_multiplier(self.npc_met.sentiment)))
                        self.model.money += price
                        self.npc_met.model.money -= price
                        self.npc_met.pick_up(item_to_sell)
                        audio.play_sfx("coins")
                        self.scene.add_notification(
                            _("notify.sold", name=entity_name(item_to_sell.model), price=price),
                            NotificationTypeEnum.info)
            INPUTS["sell"] = False

        # prevent player from moving and attacking while talking
        if self.is_talking:
            return

        if not self.target == vec(0, 0):
            self.follow_waypoints()

        # or not self.target == vec(0, 0):
        if INPUTS["left_click"]:
            target = vec(pygame.mouse.get_pos())
            mx, my = self.scene.map_view.get_center_offset()
            # convert screen position to world position
            x = target.x // self.scene.map_view._real_ratio_x - mx
            y = target.y // self.scene.map_view._real_ratio_y - my
            rect = pygame.Rect(x, y, 2, 2)
            fix_exit_target = False
            skip = False
            exit_sprites = list(self.scene.exit_sprites)
            if rect.collidelist(exit_sprites) > -1:
                fix_exit_target = True
                y += TILE_SIZE
            else:
                cell_x = int(x // TILE_SIZE)
                cell_y = int(y // TILE_SIZE)
                walk_cost = self.scene.path_finding_grid[cell_y][cell_x]
                if walk_cost > 0:
                    print("[yellow]INFO[/] destination unreachable")
                    self.scene.add_notification(_("notify.destination_unreachable"),
                                                NotificationTypeEnum.failure)
                    skip = True

            if not skip:
                self.target = vec(x, y + 8)
                self.find_path()

                if fix_exit_target:
                    exit_target = Point(int(x), int(y - TILE_SIZE))
                    waypoints_l = list(self.waypoints)
                    self.waypoints = tuple(waypoints_l + [exit_target])
                    self.waypoints_cnt = len(waypoints_l)

            INPUTS["left_click"] = False

            self.follow_waypoints()
            # target = vec(pygame.mouse.get_pos())
            # mx, my = self.scene.map_view.get_center_offset()
            # x = target.x // self.scene.map_view._real_ratio_x - mx
            # y = target.y // self.scene.map_view._real_ratio_x - my
            # self.target = vec(x // TILE_SIZE, y // TILE_SIZE)
            # INPUTS["left_click"] = False

        if INPUTS["right_click"]:
            self.target = vec(0, 0)
            self.waypoints_cnt = 0
            self.waypoints = ()
            INPUTS["right_click"] = False

        if INPUTS["attack"]:
            if not self.is_attacking and self.selected_weapon:

                self.is_attacking = True
                self.attack_time = self.game.time_elapsed
                self.scene.group.add(self.selected_weapon, layer=self.scene.sprites_layer - 1)
                weapon_cooldown = int(self.selected_weapon.model.cooldown_time * 1000.0) if self.selected_weapon else 0
                self.weapon_cooldown = self.game.time_elapsed + (weapon_cooldown + self.attack_cooldown) / 1000.0

                self.set_event_timer(
                    self,
                    NPCEventActionEnum.attacking,
                    self.attack_cooldown + weapon_cooldown,
                    1)
            INPUTS["attack"] = False

        if INPUTS["left"]:
            multiplier = INPUTS["left_value"] * JOY_MOVE_MULTIPLIER if self.game.is_joystick_in_use else 1.0
            self.acc.x = -self.force * multiplier
            self.target = vec(0, 0)
        elif INPUTS["right"]:
            multiplier = INPUTS["right_value"] * JOY_MOVE_MULTIPLIER if self.game.is_joystick_in_use else 1.0
            self.acc.x = self.force * multiplier
            self.target = vec(0, 0)
        else:
            if self.target == vec(0, 0):
                self.acc.x = 0

        if INPUTS["up"]:
            multiplier = INPUTS["up_value"] * JOY_MOVE_MULTIPLIER if self.game.is_joystick_in_use else 1.0
            # print(multiplier)
            self.acc.y = -self.force * multiplier
            self.target = vec(0, 0)
        elif INPUTS["down"]:
            multiplier = INPUTS["down_value"] * JOY_MOVE_MULTIPLIER if self.game.is_joystick_in_use else 1.0
            # print(multiplier)
            self.acc.y = self.force * multiplier
            self.target = vec(0, 0)
        else:
            if self.target == vec(0, 0):
                self.acc.y = 0

    #############################################################################################################
    def check_scene_exit(self) -> None:
        if self.scene.transition.exiting:
            return

        for exit in self.scene.exit_sprites:
            if self.feet.colliderect(exit.rect):
                # Zamknięte drzwi (H01/D8): odmowa z nazwą brakującego klucza,
                # ta sama funkcja co przy skrzyni. Komunikat RAZ na podejście,
                # nie co klatkę - kolizja trzyma się tak długo, jak długo gracz
                # stoi na progu (ten sam problem i to samo lekarstwo, co przy
                # `notify.weapon_too_weak` w `scene/collisions.py`).
                if exit.requires_item:
                    already_told = self._locked_door_told == exit.name
                    if not player_actions.unlock(self.scene, exit.requires_item,
                                                 exit.consumes_key, quiet=already_told):
                        self._locked_door_told = exit.name
                        break
                self._locked_door_told = ""
                self.scene.new_scene = exit
                self.scene.transition.exiting = True
                break
        else:
            # gracz zszedł z progu - następne podejście znów ma prawo do komunikatu
            self._locked_door_told = ""
                # self.scene.go_to_scene()

    #############################################################################################################
    def use_item(self) -> None:
        if (
            not self.items or self.selected_item_idx < 0 or self.selected_item_idx > len(self.items) - 1
        ):
            return None

        item = self.items[self.selected_item_idx]
        if item.model.type == ItemTypeEnum.consumable:
            # actual delta after clamping: eating at full health (or the nominal
            # impact overshooting max_health) heals less than the label promises,
            # so the toast reports what really changed, not item.health_impact
            health_before = self.model.health
            self.model.health += item.model.health_impact
            self.model.health = max(0, min(self.model.health, self.model.max_health))
            actual_change = self.model.health - health_before
            if actual_change > 0:
                self.scene.add_notification(
                    _("notify.health", amount=actual_change), NotificationTypeEnum.success)
            elif actual_change < 0:
                self.scene.add_notification(
                    _("notify.health", amount=actual_change), NotificationTypeEnum.failure)
            else:
                self.scene.add_notification(
                    _("notify.health_no_change"), NotificationTypeEnum.info)
            item.model.count -= 1
            self.total_items_weight -= item.model.weight
            if item.model.count <= 0:
                self.items.remove(item)
                if self.selected_item_idx >= len(self.items):
                    self.selected_item_idx -= 1
        elif item.model.type == ItemTypeEnum.weapon:
            if self.can_switch_weapon and not self.is_attacking and not self.is_stunned:
                audio.play_sfx("item_equip")
                self.can_switch_weapon = False
                self.switch_cooldown = self.game.time_elapsed + (self.switch_duration_cooldown / 1000.0)
                self.set_event_timer(self, NPCEventActionEnum.switching_weapon, self.switch_duration_cooldown, 1)

                if self.selected_weapon:
                    if self.selected_weapon.name == item.name:
                        # self.scene.group.remove(self.selected_weapon)
                        self.selected_weapon = None
                    else:
                        # self.scene.group.remove(self.selected_weapon)
                        self.selected_weapon = item
                        # self.scene.group.add(self.selected_weapon)
                else:
                    self.selected_weapon = item
                    # self.scene.group.add(self.selected_weapon)
