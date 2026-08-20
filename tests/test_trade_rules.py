#!/usr/bin/env python3
"""Unit tests for the trade rules: what a shop refuses, and what a deal moves.

Covers the two guards (`inventory.can_buy` / `inventory.can_sell`) and the
transaction that follows them, with the awkward cases the shop actually hits:
an empty pack, a purse one coin short, a load one gram too heavy, a full
hotbar, and a merchant that only deals in one item type.

Two of these are worth naming, because they are the ones that bit before:

* while *selling*, `selected_item_idx` indexes the **filtered** (tradable)
  list, not `npc.items` - a gem-only merchant looking at a hero carrying
  [sword, gem] must price and hand over the gem, not the sword;
* the slot check is "is there a free slot **or** do I already stock this",
  so a full hotbar still stacks a known item.

No display is needed: the guards are plain functions over an NPC's attributes,
so both sides are raised with `NPC.__new__` and given only the fields the trade
code touches (same trick as `test_merchant_economy.py`).

Run from the project root:
    .venv/bin/python tests/test_trade_rules.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import inspect

from characters import NPC
from enums import ItemTypeEnum
from settings import (
    PLAYER_CONFIG_KEY,
    get_buy_price_multiplier,
    get_sell_price_multiplier,
)

# sentiment 50 is the neutral middle: both multipliers are exactly 1.0 there, so
# every test that is not *about* sentiment can read prices straight off `value`
NEUTRAL = 50
GRUDGE = 0


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def assert_false(cond: bool, msg: str = "") -> None:
    assert not cond, msg


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeItemModel:
    def __init__(self, name: str, value: int, weight: float, item_type: ItemTypeEnum) -> None:
        self.name_EN = name
        self.name_PL = name
        self.type = item_type
        self.value = value
        self.weight = weight
        self.count = 1


class _FakeItem:
    """Stand-in for `ItemSprite`: trade only ever reads `.name` and `.model`."""

    def __init__(self, name: str, value: int = 10, weight: float = 1.0,
                 item_type: ItemTypeEnum = ItemTypeEnum.consumable) -> None:
        self.name = name
        self.model = _FakeItemModel(name, value, weight, item_type)


class _FakeCharModel:
    def __init__(self, money: int, max_carry_weight: float,
                 tradeable_items_types: list[ItemTypeEnum] | None = None) -> None:
        self.money = money
        self.max_carry_weight = max_carry_weight
        self.tradeable_items_types = tradeable_items_types or []
        self.name_EN = "Somebody"
        self.name_PL = "Ktoś"


class _FakeScene:
    """Records notifications so a test can assert *why* a deal was refused."""

    def __init__(self) -> None:
        self.notifications: list[str] = []

    def add_notification(self, text: str, kind: object = None) -> None:
        self.notifications.append(text)

    def create_item(self, item_name: str, x: int, y: int, show: bool = True) -> _FakeItem:
        # only reached when splitting a stack; the split keeps the original's kind
        return _FakeItem(item_name)


def _character(money: int = 1000, max_carry_weight: float = 30.0, max_items: int = 6,
               items: list[_FakeItem] | None = None, sentiment: int = NEUTRAL,
               tradeable_items_types: list[ItemTypeEnum] | None = None,
               config_key: str = "MERCHANT") -> NPC:
    """A bare NPC carrying only what the trade guards read."""
    npc = NPC.__new__(NPC)
    npc.scene = _FakeScene()  # type: ignore[assignment]
    npc.config_key = config_key
    npc.name = config_key
    npc.model = _FakeCharModel(money, max_carry_weight, tradeable_items_types)  # type: ignore[assignment]
    npc.items = items or []  # type: ignore[assignment]
    npc.total_items_weight = sum(item.model.weight for item in npc.items)
    npc.max_items = max_items
    npc.selected_item_idx = 0 if npc.items else -1
    npc.selected_weapon = None
    npc.sentiment = sentiment
    npc.npc_met = None
    npc.pos = (0.0, 0.0)  # type: ignore[assignment]
    return npc


def _shop(player_items: list[_FakeItem] | None = None,
          stock: list[_FakeItem] | None = None,
          player_money: int = 1000, merchant_money: int = 1000,
          player_max_weight: float = 30.0, merchant_max_weight: float = 30.0,
          player_slots: int = 6, merchant_slots: int = 6,
          sentiment: int = NEUTRAL,
          tradeable_items_types: list[ItemTypeEnum] | None = None) -> tuple[NPC, NPC]:
    """A hero standing in front of an open shop. Returns (player, merchant)."""
    merchant = _character(money=merchant_money, max_carry_weight=merchant_max_weight,
                          max_items=merchant_slots, items=stock, sentiment=sentiment,
                          tradeable_items_types=tradeable_items_types)
    player = _character(money=player_money, max_carry_weight=player_max_weight,
                        max_items=player_slots, items=player_items,
                        config_key=PLAYER_CONFIG_KEY)
    player.npc_met = merchant  # type: ignore[assignment]
    return player, merchant


def _buy(player: NPC, merchant: NPC) -> _FakeItem | None:
    """The purchase exactly as `GameUI` runs it once `can_buy` said yes."""
    item = merchant.drop_item(show=False)
    if not item:
        return None
    price = int(round(item.model.value * get_buy_price_multiplier(merchant.sentiment)))
    player.model.money -= price
    merchant.model.money += price
    player.pick_up(item)  # type: ignore[arg-type]
    return item  # type: ignore[return-value]


def _sell(player: NPC, merchant: NPC) -> _FakeItem | None:
    """The sale as `GameUI` runs it: the cursor indexes the *tradable* list."""
    tradable = player.get_tradable_items()
    if not 0 <= player.selected_item_idx < len(tradable):
        return None
    item = player.drop_item(show=False, item=tradable[player.selected_item_idx])
    if not item:
        return None
    price = int(round(item.model.value * get_sell_price_multiplier(merchant.sentiment)))
    player.model.money += price
    merchant.model.money -= price
    merchant.pick_up(item)  # type: ignore[arg-type]
    return item  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# A merchant that deals in one item type only
# ---------------------------------------------------------------------------


def test_an_unrestricted_merchant_takes_the_whole_pack() -> None:
    sword = _FakeItem("sword", item_type=ItemTypeEnum.weapon)
    fish = _FakeItem("fish", item_type=ItemTypeEnum.consumable)
    player, _ = _shop(player_items=[sword, fish])

    names = [item.name for item in player.get_tradable_items()]
    assert_eq(names, ["sword", "fish"], "an empty type list means 'anything'")


def test_a_restricted_merchant_filters_the_pack_to_its_type() -> None:
    sword = _FakeItem("sword", item_type=ItemTypeEnum.weapon)
    fish = _FakeItem("fish", item_type=ItemTypeEnum.consumable)
    gem = _FakeItem("gem", item_type=ItemTypeEnum.gem)
    player, _ = _shop(player_items=[sword, fish, gem],
                      tradeable_items_types=[ItemTypeEnum.gem])

    names = [item.name for item in player.get_tradable_items()]
    assert_eq(names, ["gem"], "the shelf shows only what the merchant deals in")


def test_a_pack_with_nothing_of_the_right_type_cannot_sell() -> None:
    """Carrying plenty is not the same as carrying something *this* shop wants."""
    player, _ = _shop(player_items=[_FakeItem("sword", item_type=ItemTypeEnum.weapon)],
                      tradeable_items_types=[ItemTypeEnum.gem])

    assert_false(player.can_sell(), "a gem-only merchant must refuse a sword")


# ---------------------------------------------------------------------------
# Buying: the guards
# ---------------------------------------------------------------------------


def test_cannot_buy_without_a_merchant() -> None:
    player = _character(config_key=PLAYER_CONFIG_KEY)

    assert_false(player.can_buy(), "no shop is open")


def test_cannot_buy_from_an_empty_stock() -> None:
    """A merchant the player has already cleaned out is a valid, quiet no."""
    player, merchant = _shop(stock=[])

    assert_false(player.can_buy(), "there is nothing on the shelf")
    assert_eq(merchant.items, [], "and nothing appeared out of thin air")


def test_cannot_buy_with_the_cursor_parked_outside_the_stock() -> None:
    player, merchant = _shop(stock=[_FakeItem("fish")])
    merchant.selected_item_idx = -1

    assert_false(player.can_buy(), "nothing is selected")


def test_one_coin_short_is_still_short() -> None:
    player, _ = _shop(stock=[_FakeItem("fish", value=18)], player_money=17)

    assert_false(player.can_buy(), "17 does not buy an 18-coin fish")


def test_exactly_enough_money_still_buys() -> None:
    """The boundary the guard is written on: `money < price` refuses, `==` does not."""
    player, merchant = _shop(stock=[_FakeItem("fish", value=18)], player_money=18)

    assert_true(player.can_buy(), "the last coin must be spendable")
    _buy(player, merchant)
    assert_eq(player.model.money, 0, "the purse is emptied exactly")


def test_a_grudge_can_price_the_player_out() -> None:
    """Sentiment is part of affordability, not just flavour: 0 sentiment is 1.5x."""
    liked, liked_merchant = _shop(stock=[_FakeItem("fish", value=100)], player_money=100,
                                  sentiment=NEUTRAL)
    disliked, _ = _shop(stock=[_FakeItem("fish", value=100)], player_money=100,
                        sentiment=GRUDGE)

    assert_true(liked.can_buy(), "at neutral sentiment 100 coins buy a 100-coin fish")
    assert_false(disliked.can_buy(), "the same fish costs 150 from someone who dislikes you")
    _buy(liked, liked_merchant)
    assert_eq(liked_merchant.model.money, 1100, "the merchant is paid what the player lost")


def test_cannot_buy_what_you_cannot_carry() -> None:
    player, _ = _shop(stock=[_FakeItem("anvil", weight=5.0)],
                      player_items=[_FakeItem("rock", weight=6.0)],
                      player_max_weight=10.0)

    assert_false(player.can_buy(), "6.0 + 5.0 is over the 10.0 limit")


def test_a_load_that_lands_exactly_on_the_limit_is_allowed() -> None:
    """`max_carry_weight < total + weight` refuses - so filling it to the gram is fine."""
    player, _ = _shop(stock=[_FakeItem("anvil", weight=4.0)],
                      player_items=[_FakeItem("rock", weight=6.0)],
                      player_max_weight=10.0)

    assert_true(player.can_buy(), "exactly at the limit is not over it")


def test_a_full_pack_still_stacks_something_you_already_carry() -> None:
    """Slots are per item *kind*: a second fish rides in the fish slot."""
    pack = [_FakeItem(f"junk_{i}") for i in range(5)] + [_FakeItem("fish")]
    player, _ = _shop(player_items=pack, stock=[_FakeItem("fish")], player_slots=6)

    assert_eq(len(player.items), player.max_items, "the pack is genuinely full")
    assert_true(player.can_buy(), "a known item stacks instead of needing a slot")


def test_a_full_pack_refuses_a_kind_you_do_not_carry() -> None:
    pack = [_FakeItem(f"junk_{i}") for i in range(6)]
    player, _ = _shop(player_items=pack, stock=[_FakeItem("fish")], player_slots=6)

    assert_false(player.can_buy(), "there is no slot for a new kind")


def test_the_refusal_says_which_wall_was_hit() -> None:
    """Three different noes, three different notifications - the player has to know."""
    broke, _ = _shop(stock=[_FakeItem("fish", value=50)], player_money=10)
    broke.can_buy()
    heavy, _ = _shop(stock=[_FakeItem("anvil", weight=50.0)], player_max_weight=1.0)
    heavy.can_buy()
    full, _ = _shop(player_items=[_FakeItem(f"junk_{i}") for i in range(6)],
                    stock=[_FakeItem("fish")], player_slots=6)
    full.can_buy()

    reasons = [broke.scene.notifications, heavy.scene.notifications, full.scene.notifications]
    assert_true(all(len(r) == 1 for r in reasons), f"one message per refusal: {reasons}")
    assert_eq(len({r[0] for r in reasons}), 3, f"the three walls read differently: {reasons}")


# ---------------------------------------------------------------------------
# Selling: the guards
# ---------------------------------------------------------------------------


def test_cannot_sell_an_empty_pack() -> None:
    player, _ = _shop(player_items=[])

    assert_false(player.can_sell(), "nothing to offer")


def test_a_merchant_without_the_coin_refuses() -> None:
    player, _ = _shop(player_items=[_FakeItem("gem", value=600)], merchant_money=100)

    assert_false(player.can_sell(), "the shop cannot pay 600 out of a 100-coin purse")


def test_a_merchant_can_spend_its_very_last_coin() -> None:
    player, merchant = _shop(player_items=[_FakeItem("gem", value=100)], merchant_money=100)

    assert_true(player.can_sell(), "an exact-change sale is still a sale")
    _sell(player, merchant)
    assert_eq(merchant.model.money, 0, "the shop purse is emptied exactly")


def test_a_merchant_at_its_carry_limit_refuses() -> None:
    """The merchant's own `max_carry_weight` is a shop-closing condition too."""
    player, _ = _shop(player_items=[_FakeItem("anvil", weight=5.0)],
                      stock=[_FakeItem("rock", weight=9.0)],
                      merchant_max_weight=10.0)

    assert_false(player.can_sell(), "9.0 + 5.0 is over the merchant's 10.0 limit")


def test_a_merchant_with_full_slots_still_takes_more_of_what_it_stocks() -> None:
    stock = [_FakeItem(f"stock_{i}") for i in range(5)] + [_FakeItem("fish")]
    player, merchant = _shop(player_items=[_FakeItem("fish")], stock=stock, merchant_slots=6)

    assert_eq(len(merchant.items), merchant.max_items, "the shop is genuinely full")
    assert_true(player.can_sell(), "a fish stacks onto the shop's own fish")


def test_a_merchant_with_full_slots_refuses_a_new_kind() -> None:
    stock = [_FakeItem(f"stock_{i}") for i in range(6)]
    player, _ = _shop(player_items=[_FakeItem("fish")], stock=stock, merchant_slots=6)

    assert_false(player.can_sell(), "no shelf space for a kind the shop does not stock")


def test_selling_is_judged_on_the_filtered_item_not_the_hotbar_slot() -> None:
    """The cursor indexes the tradable list, so slot 0 is the gem, not the sword.

    Judging `items[0]` instead would price a 300-coin sword against a 50-coin
    purse and refuse a sale the shop can easily afford.
    """
    sword = _FakeItem("sword", value=300, item_type=ItemTypeEnum.weapon)
    gem = _FakeItem("gem", value=10, item_type=ItemTypeEnum.gem)
    player, _ = _shop(player_items=[sword, gem], merchant_money=50,
                      tradeable_items_types=[ItemTypeEnum.gem])
    player.selected_item_idx = 0

    assert_true(player.can_sell(), "the gem is what is on offer, and it costs 10")


def test_a_stale_cursor_cannot_sell() -> None:
    """`selected_item_idx` outlives the item it pointed at (dropped, sold, filtered)."""
    player, _ = _shop(player_items=[_FakeItem("gem", item_type=ItemTypeEnum.gem)],
                      tradeable_items_types=[ItemTypeEnum.gem])
    player.selected_item_idx = 4

    assert_false(player.can_sell(), "an out-of-range cursor is a no, not an IndexError")


# ---------------------------------------------------------------------------
# The deal itself
# ---------------------------------------------------------------------------


def test_buying_moves_the_coin_the_weight_and_the_goods() -> None:
    player, merchant = _shop(stock=[_FakeItem("fish", value=18, weight=1.0)],
                             player_money=100, merchant_money=200)

    assert_true(player.can_buy(), "the deal is legal")
    _buy(player, merchant)

    assert_eq(player.model.money, 82, "the player paid 18")
    assert_eq(merchant.model.money, 218, "the merchant was paid 18")
    assert_eq([item.name for item in player.items], ["fish"], "the fish changed hands")
    assert_eq(merchant.items, [], "and left the shelf")
    assert_eq(player.total_items_weight, 1.0, "the player carries its weight now")
    assert_eq(merchant.total_items_weight, 0.0, "the merchant does not")


def test_buying_one_of_a_stack_leaves_the_rest_on_the_shelf() -> None:
    stack = _FakeItem("fish", value=18, weight=1.0)
    stack.model.count = 3
    player, merchant = _shop(stock=[stack])
    merchant.total_items_weight = 3.0

    _buy(player, merchant)

    assert_eq(merchant.items[0].model.count, 2, "two fish are still for sale")
    assert_eq(player.items[0].model.count, 1, "the player got exactly one")


def test_selling_hands_over_the_filtered_item_and_leaves_the_rest() -> None:
    """The regression this file exists for: sell the gem, keep the sword."""
    sword = _FakeItem("sword", value=300, item_type=ItemTypeEnum.weapon)
    gem = _FakeItem("gem", value=10, item_type=ItemTypeEnum.gem)
    player, merchant = _shop(player_items=[sword, gem], player_money=0, merchant_money=100,
                             tradeable_items_types=[ItemTypeEnum.gem])
    player.selected_item_idx = 0

    sold = _sell(player, merchant)

    assert_eq(sold.name if sold else None, "gem", "the gem is what left the pack")
    assert_eq([item.name for item in player.items], ["sword"], "the sword stayed")
    assert_eq(player.model.money, 10, "paid the gem's price, not the sword's")
    assert_eq(merchant.model.money, 90, "and the shop paid it")


def test_a_grudging_round_trip_costs_the_player() -> None:
    """Buy at 1.5x and sell straight back at 0.5x: the spread is the whole economy."""
    player, merchant = _shop(stock=[_FakeItem("fish", value=100)], player_money=200,
                             merchant_money=200, sentiment=GRUDGE)

    _buy(player, merchant)
    assert_eq(player.model.money, 50, "the fish cost 150")
    player.selected_item_idx = 0
    _sell(player, merchant)

    assert_eq(player.model.money, 100, "selling it straight back returned only 50")
    assert_eq(merchant.model.money, 300, "the merchant kept the 100-coin spread")


def test_selling_the_last_tradable_item_empties_the_shelf() -> None:
    """After the sale there is nothing left to point at - the cursor must not dangle."""
    player, merchant = _shop(player_items=[_FakeItem("gem", item_type=ItemTypeEnum.gem),
                                           _FakeItem("sword", item_type=ItemTypeEnum.weapon)],
                             tradeable_items_types=[ItemTypeEnum.gem])
    player.selected_item_idx = 0

    _sell(player, merchant)

    assert_eq(player.get_tradable_items(), [], "the shop has nothing left to buy")
    assert_false(player.can_sell(), "and says so instead of indexing an empty list")


def test_the_sell_handler_indexes_the_filtered_list() -> None:
    """Structural pin: `can_sell` validates the tradable list, so the sale must use it.

    Reading `items[selected_item_idx]` here (what `drop_item` does by default)
    would hand over a different item than the one that was priced and approved.
    """
    from ui.game_ui import GameUI

    source = inspect.getsource(GameUI.update)
    sell_block = source[source.index('if INPUTS["sell"]:'):]
    sell_block = sell_block[:sell_block.index('INPUTS["sell"] = False')]

    assert_true("get_tradable_items()" in sell_block, "the sale re-derives the tradable list")
    assert_true("item=filtered[player.selected_item_idx]" in sell_block,
                "and hands `drop_item` that item explicitly")


# ---------------------------------------------------------------------------


def main() -> None:
    tests = [
        test_an_unrestricted_merchant_takes_the_whole_pack,
        test_a_restricted_merchant_filters_the_pack_to_its_type,
        test_a_pack_with_nothing_of_the_right_type_cannot_sell,
        test_cannot_buy_without_a_merchant,
        test_cannot_buy_from_an_empty_stock,
        test_cannot_buy_with_the_cursor_parked_outside_the_stock,
        test_one_coin_short_is_still_short,
        test_exactly_enough_money_still_buys,
        test_a_grudge_can_price_the_player_out,
        test_cannot_buy_what_you_cannot_carry,
        test_a_load_that_lands_exactly_on_the_limit_is_allowed,
        test_a_full_pack_still_stacks_something_you_already_carry,
        test_a_full_pack_refuses_a_kind_you_do_not_carry,
        test_the_refusal_says_which_wall_was_hit,
        test_cannot_sell_an_empty_pack,
        test_a_merchant_without_the_coin_refuses,
        test_a_merchant_can_spend_its_very_last_coin,
        test_a_merchant_at_its_carry_limit_refuses,
        test_a_merchant_with_full_slots_still_takes_more_of_what_it_stocks,
        test_a_merchant_with_full_slots_refuses_a_new_kind,
        test_selling_is_judged_on_the_filtered_item_not_the_hotbar_slot,
        test_a_stale_cursor_cannot_sell,
        test_buying_moves_the_coin_the_weight_and_the_goods,
        test_buying_one_of_a_stack_leaves_the_rest_on_the_shelf,
        test_selling_hands_over_the_filtered_item_and_leaves_the_rest,
        test_a_grudging_round_trip_costs_the_player,
        test_selling_the_last_tradable_item_empties_the_shelf,
        test_the_sell_handler_indexes_the_filtered_list,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL  {test.__name__}: {exc}")
            import traceback

            traceback.print_exc()
            failures += 1

    print(f"\n{'─' * 40}")
    total = len(tests)
    if failures:
        print(f"  FAILED  {failures}/{total} tests")
        sys.exit(1)
    print(f"  PASSED  {total - failures}/{total} tests")


if __name__ == "__main__":
    main()
