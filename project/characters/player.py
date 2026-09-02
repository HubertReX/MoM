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
    get_msg,
    Point,
)
from enums import ItemTypeEnum, NPCEventActionEnum

import audio
import game
import scene
from characters.npc import NPC
from objects import HealthBarUI, NotificationTypeEnum
from scene import dialog_triggers, player_actions
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
        #: Nazwa wyjścia, którego bramkę fabularną gracz już zobaczył w tym
        #: podejściu. Ta sama choroba i to samo lekarstwo co wyżej: kolizja
        #: z progiem trzyma się wiele klatek, a dialog ma się odegrać RAZ.
        #: Warunek liczy się dalej co klatkę - patrz `check_scene_exit`.
        self._exit_dialog_told: str = ""
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

    def can_interact_with_npc(self) -> bool:
        """Is someone within reach that the hero can talk to or trade with?

        `collisions.resolve` already pins such a character to `npc_met`; this is
        the same test it used to decide, asked from the other side.
        """
        npc = self.npc_met
        return bool(npc and (npc.has_dialog or npc.model.is_merchant))

    def normalise_trade_selection(self) -> None:
        """Point `selected_item_idx` at something the merchant will actually take.

        A trader may accept only some item types, so the hotbar cursor has to be
        re-seated before the shop opens. An empty inventory (or nothing tradable)
        is fine and leaves the cursor at 0 - the player came to buy.
        """
        filtered_items = self.get_tradable_items()
        if not filtered_items or not self.items:
            self.selected_item_idx = 0
            return
        if self.selected_item_idx >= len(self.items):
            self.selected_item_idx = 0
        selected_item = self.items[self.selected_item_idx]
        if selected_item not in filtered_items:
            self.selected_item_idx = 0
        else:
            self.selected_item_idx = filtered_items.index(selected_item)

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
            npc = self.npc_met
            if npc is not None and self.can_interact_with_npc() and not self.is_talking:
                # dialog or trading?
                if npc.has_dialog and npc.dialog is not None:
                    text = get_msg(self.game.conf.messages, npc.dialog.text)
                    self.scene.ui.open(DialogPanel, npc=npc, text=text)
                    if MOM_DEBUG_TALK:
                        self.game.log(f"[DEBUG talk] opened DialogPanel for {npc.name} "
                                      f"at node {npc.dialog.key}")
                else:
                    self.normalise_trade_selection()
                    # having nothing to sell is not a reason to refuse the shop -
                    # the player may well have come to buy
                    self.scene.ui.open(TradePanel)
                self.is_talking = True
                npc.is_talking = True
            INPUTS["talk"] = False

        # Wejścia sklepu (buy/sell/toggle/end_trade) obsługuje wyłącznie
        # `GameUI.update`: przy otwartym panelu `Scene.update` zamraża świat i wraca
        # przed `group.update`, więc `Player.movement` w ogóle wtedy nie leci. Druga
        # kopia tej obsługi siedziała tutaj i zdążyła się rozjechać z żywą (wydawała
        # przedmiot spod indeksu z listy filtrowanej i sięgała po `filtered_items[i]`
        # bez zabezpieczenia) - usunięta, testy w `tests/test_trade_rules.py`.

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
            # SPACE raises `talk`, `open` and `attack` together (settings.ACTIONS),
            # and the talk branch above clears only its own flag - so a hero with a
            # weapon drawn used to swing at the merchant he was opening the shop
            # with. Standing at someone who can be talked or traded with, the
            # peaceful action wins and the swing is dropped.
            if self.can_interact_with_npc():
                pass
            elif not self.is_attacking and self.selected_weapon:

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
                # Bramka fabularna: wyjście wskazuje węzeł `-entry`, a jego warunek
                # mówi, czy wolno już stąd wyjść. Warunek sprawdzamy CO KLATKĘ, ale
                # dialog odgrywamy raz na podejście - dzięki temu rozmowa, która
                # właśnie domknęła quest, przepuszcza gracza od razu, bez schodzenia
                # z progu, a stanie na progu przy niespełnionym warunku niczego nie
                # powtarza.
                #
                # Fabuła przed kluczem: „nie jesteś gotów" jest stwierdzeniem
                # o świecie, a „nie masz klucza" o tych konkretnych drzwiach - ta
                # druga odmowa ma sens dopiero wtedy, gdy wyjść już wolno.
                if exit.dialog and dialog_triggers.should_fire(self.scene, exit.dialog):
                    if self._exit_dialog_told != exit.name:
                        self._exit_dialog_told = exit.name
                        dialog_triggers.fire_spec(self.scene, exit.dialog)
                    break
                self._exit_dialog_told = ""

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
            self._exit_dialog_told = ""
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
