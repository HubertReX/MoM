"""Ekwipunek i handel: sloty, waga, ceny, podnoszenie i upuszczanie przedmiotów.

Moduł systemu wg B01/D6: bezstanowe funkcje przyjmujące ``npc`` jawnie - stan
(``items``, ``selected_item_idx``, ``total_items_weight``, ``model.money``)
zostaje atrybutem :class:`characters.npc.NPC` (kontrakt K1 save/load), a klasa
ma tylko cienkie delegaty o niezmienionych nazwach (kontrakt K3; ``money_cap``
zostaje property).
"""
from typing import TYPE_CHECKING

from rich import print

import audio
import scene
from enums import ItemTypeEnum
from objects import ItemSprite
from settings import (
    PLAYER_CONFIG_KEY,
    _,
    entity_name,
    get_buy_price_multiplier,
    get_sell_price_multiplier,
)

if TYPE_CHECKING:
    from characters.npc import NPC


###############################################################################################################
def select_next_item(npc: "NPC", filtered_items: list[ItemSprite] | None = None) -> None:
    if not filtered_items:
        filtered_items = npc.items

    if len(filtered_items) > 0:
        if npc.selected_item_idx < len(filtered_items):
            selected_item = filtered_items[npc.selected_item_idx]
        else:
            selected_item = filtered_items[0]
        new_idx = filtered_items.index(selected_item) + 1
        npc.selected_item_idx = 0 if new_idx >= len(filtered_items) else new_idx


###############################################################################################################
def select_prev_item(npc: "NPC", filtered_items: list[ItemSprite] | None = None) -> None:
    if not filtered_items:
        filtered_items = npc.items

    if len(filtered_items) > 0:
        if npc.selected_item_idx < len(filtered_items):
            selected_item = filtered_items[npc.selected_item_idx]
        else:
            selected_item = filtered_items[0]
        new_idx = filtered_items.index(selected_item) - 1
        npc.selected_item_idx = len(filtered_items) - 1 if new_idx < 0 else new_idx


###############################################################################################################
def load_items(npc: "NPC") -> None:
    for item_name in npc.model.items:
        item = npc.scene.create_item(item_name, 0, 0, show=False)
        npc.pick_up(item)


###############################################################################################################
def money_cap(npc: "NPC") -> int:
    """Ceiling the purse regenerates up to.

    `npc.model` is this character's own deep copy, so `model.money` is the
    *live* purse and cannot serve as the baseline. The pristine config can:
    an unset `money_cap` means "whatever the CSV row starts you with".
    """
    cap = npc.model.money_cap
    if cap > 0:
        return cap
    return npc.game.conf.characters[npc.config_key].money


###############################################################################################################
def regenerate_money(npc: "NPC", days: int = 1) -> None:
    """Refill the purse by a flat share of its ceiling per elapsed day.

    Linear growth with a ceiling has a closed form, which is what keeps this
    N-safe: coming back from a three-day trip is one call, not a loop over
    days. (A percentage compounded from the current amount would not be.)

    Emptying a merchant is therefore felt for a few days - at the default 25%
    a purse drained to zero needs four dawns to come back - which is the
    gentle nudge towards selling gradually, or to somebody else.
    """
    cap = npc.money_cap
    per_day = round(cap * npc.model.money_regen_pct)
    npc.model.money = min(cap, npc.model.money + days * per_day)


###############################################################################################################
def restock_items(npc: "NPC") -> None:
    """Dawn re-roll of the stock: back to the list from the config, nothing else.

    Whatever the player sold here is gone rather than resold. Keeping it would
    silt up `max_carry_weight` with the player's junk across sessions until the
    merchant permanently stopped buying.

    The money side of the day turn is `regenerate_money`, deliberately *not*
    the value of those items: the old `sell_all_bought_items` credited the
    merchant the full value of everything it had ever bought, so the purse only
    ever grew and the limit could never bite.
    """
    npc.items = []
    # `total_items_weight` is a running total maintained by pick_up/drop_item, so
    # dropping the item list on the floor without zeroing it left every dawn's
    # stock weighing on top of the previous one - after a few days the merchant
    # was over `max_carry_weight` while visibly holding two gems, and refused to
    # buy anything ever again.
    npc.total_items_weight = 0.0
    npc.load_items()


###############################################################################################################
def pick_up(npc: "NPC", item: ItemSprite) -> bool:
    result: bool = False

    if item.model.type == ItemTypeEnum.money:
        npc.model.money += item.model.value
        # npc.items.append(item)
        result = True
    else:
        found = False
        for idx, owned_item in enumerate(npc.items):
            if owned_item.name == item.name:
                found = True
                break

        if npc.total_items_weight + item.model.weight <= npc.model.max_carry_weight:
            if found:
                npc.total_items_weight += item.model.weight

                # increase amount if already owned
                npc.items[idx].model.count += 1

                result = True
            else:
                # check if there are free slots
                if len(npc.items) < npc.max_items:
                    # add new item if not owned
                    npc.total_items_weight += item.model.weight

                    npc.items.append(item)

                    # if it's the first owned item, set it as selected
                    if npc.selected_item_idx < 0:
                        npc.selected_item_idx = 0

                    result = True
                else:
                    print(
                        f"\n[red]ERROR:[/] {npc.name} All '[num]{npc.max_items}[/num]'"
                        " items slots are taken!\n")
                    npc.scene.add_notification(
                        _("notify.all_slots_taken", n=npc.max_items),
                        scene.NotificationTypeEnum.failure)
        else:
            print(
                f"\n[red]ERROR:[/] {npc.name} Max carry weight "
                f"'[num]{npc.model.max_carry_weight:4.2f}[/num]' exceeded!\n")
            npc.scene.add_notification(
                _("notify.max_weight_exceeded", w=f"{npc.model.max_carry_weight:4.2f}"),
                scene.NotificationTypeEnum.failure)

    # tylko bohater - kupiec chowający sprzedany przedmiot nie brzęczy graczowi w ucho
    if result and npc.config_key == PLAYER_CONFIG_KEY:
        audio.play_sfx("coins" if item.model.type == ItemTypeEnum.money else "item_pick_up")

    return result


###############################################################################################################
def get_tradable_items(npc: "NPC") -> list[ItemSprite]:
    items = npc.items

    if npc.npc_met:
        tradeable_items_types = npc.npc_met.model.tradeable_items_types
        if tradeable_items_types:
            items = [item for item in items if item.model.type in tradeable_items_types]

    return items


###############################################################################################################
def can_buy(npc: "NPC") -> bool:
    if (
        not npc.npc_met or not npc.npc_met.items or npc.npc_met.selected_item_idx < 0
    ):
        return False

    selected_item = npc.npc_met.items[npc.npc_met.selected_item_idx]
    price = int(round(selected_item.model.value * get_buy_price_multiplier(npc.npc_met.sentiment)))

    if npc.model.money < price:
        npc.scene.add_notification(
            _("notify.cant_buy_money", name=entity_name(selected_item.model)),
            scene.NotificationTypeEnum.failure)
        return False

    if npc.model.max_carry_weight < npc.total_items_weight + selected_item.model.weight:
        npc.scene.add_notification(
            _("notify.cant_buy_weight", name=entity_name(selected_item.model)),
            scene.NotificationTypeEnum.failure)
        return False

    found = False
    for owned_item in npc.items:
        if owned_item.name == selected_item.name:
            found = True
            break

    if not found and len(npc.items) == npc.max_items:
        npc.scene.add_notification(
            _("notify.cant_buy_slots", name=entity_name(selected_item.model)),
            scene.NotificationTypeEnum.failure)
        return False

    return True


###############################################################################################################
def can_sell(npc: "NPC") -> bool:
    # selected_item_idx indexes the *filtered* (tradable) list while selling, not
    # npc.items - a type-restricted merchant (e.g. gems only) filters the player's
    # inventory, so validate against the same list the sell action uses.
    tradable = npc.get_tradable_items()
    if (
        not tradable or npc.selected_item_idx < 0 or npc.selected_item_idx > len(
            tradable) - 1 or not npc.npc_met
    ):
        return False

    selected_item = tradable[npc.selected_item_idx]
    price = int(round(selected_item.model.value * get_sell_price_multiplier(npc.npc_met.sentiment)))

    if npc.npc_met.model.money < price:
        npc.scene.add_notification(
            _("notify.merchant_cant_buy_money", name=entity_name(selected_item.model)),
            scene.NotificationTypeEnum.failure)
        return False

    if npc.npc_met.model.max_carry_weight < npc.npc_met.total_items_weight + selected_item.model.weight:
        npc.scene.add_notification(
            _("notify.merchant_cant_buy_weight", name=entity_name(selected_item.model)),
            scene.NotificationTypeEnum.failure)
        return False

    found = False
    for owned_item in npc.npc_met.items:
        if owned_item.name == selected_item.name:
            found = True
            break

    if not found and len(npc.npc_met.items) == npc.npc_met.max_items:
        npc.scene.add_notification(
            _("notify.merchant_cant_buy_slots", name=entity_name(selected_item.model)),
            scene.NotificationTypeEnum.failure)
        return False

    return True


###############################################################################################################
def drop_item(npc: "NPC", show: bool = True, item: "ItemSprite | None" = None) -> "ItemSprite | None":
    if item is None:
        if (
            not npc.items or npc.selected_item_idx < 0 or npc.selected_item_idx > len(npc.items) - 1
        ):
            return None
        item = npc.items[npc.selected_item_idx]
    selected_item = item
    npc.total_items_weight -= selected_item.model.weight  # * selected_item.model.count

    if selected_item.model.count > 1:
        org_item = selected_item
        org_item.model.count -= 1

        # selected_item = copy.copy(org_item)
        selected_item = npc.scene.create_item(org_item.name, int(npc.pos[0]), int(npc.pos[1]), show=show)
        # selected_item.rect = org_item.rect.copy()
        # selected_item.model = copy.copy(org_item.model)
        # selected_item.model.count = 1
    else:
        # are we dropping currently selected weapon
        if selected_item.model.type == ItemTypeEnum.weapon and npc.selected_weapon and \
                npc.selected_weapon.name == selected_item.name:
            npc.selected_weapon = None

        npc.items.remove(selected_item)

        if show:
            npc.scene.item_sprites.add(selected_item)
            selected_item.rect.center = npc.pos  # type: ignore[assignment]

        if npc.selected_item_idx >= len(npc.items):
            npc.selected_item_idx -= 1
    # item = npc.items.pop(-1)

    # `show=False` to transfer w handlu albo łup wypadający z trupa, nie rzut
    # gracza o ziemię - te ścieżki mają własne dźwięki
    if show and npc.config_key == PLAYER_CONFIG_KEY:
        audio.play_sfx("item_drop")

    return selected_item
