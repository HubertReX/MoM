#!/usr/bin/env python3
"""Tests for the merchant day turn: purse regeneration and the stock re-roll.

The purse used to only ever grow - `sell_all_bought_items` credited the merchant
the full value of everything the player had sold it, so the limit could never
bite. It is now a plain linear refill towards a ceiling, and the goods bought
from the player are discarded rather than resold.

The N-safety property is the one worth pinning down: `apply_days(3)` after a
three-day trip has to land exactly where three separate dawns would.

Run from the project root:
    .venv/bin/python tests/test_merchant_economy.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"


class _FakeModel:
    def __init__(self, money: int, money_cap: int = 0, money_regen_pct: float = 0.25) -> None:
        self.money = money
        self.money_cap = money_cap
        self.money_regen_pct = money_regen_pct
        self.items = ["gem_small_blue", "gem_small_orange"]
        self.max_carry_weight = 15.0


class _FakeConf:
    def __init__(self, base_money: int) -> None:
        # the pristine config row, never written to - it is the purse baseline
        self.characters = {"JOHNY": _FakeModel(base_money)}


class _FakeGame:
    def __init__(self, base_money: int) -> None:
        self.conf = _FakeConf(base_money)


class _FakeItemModel:
    def __init__(self, weight: float) -> None:
        from enums import ItemTypeEnum

        self.type = ItemTypeEnum.gem
        self.value = 60
        self.weight = weight
        self.count = 1


class _FakeItem:
    def __init__(self, name: str, weight: float = 1.0) -> None:
        self.name = name
        self.model = _FakeItemModel(weight)


class _FakeScene:
    def create_item(self, item_name: str, x: int, y: int, show: bool = True) -> _FakeItem:
        return _FakeItem(item_name)

    def add_notification(self, *args: object, **kwargs: object) -> None:
        pass


def _merchant(money: int, money_cap: int = 0, money_regen_pct: float = 0.25, base_money: int = 3000):
    """A bare NPC with just the attributes the day-turn methods touch."""
    from characters import NPC

    npc = NPC.__new__(NPC)
    npc.game = _FakeGame(base_money)
    npc.scene = _FakeScene()
    npc.config_key = "JOHNY"
    npc.model = _FakeModel(money, money_cap, money_regen_pct)
    npc.name = "JOHNY"
    npc.items = []
    npc.total_items_weight = 0.0
    npc.max_items = 6
    npc.selected_item_idx = -1
    return npc


# ---------------------------------------------------------------------------
# Purse ceiling
# ---------------------------------------------------------------------------

def test_unset_cap_falls_back_to_the_config_money() -> None:
    """`money_cap` is optional: an empty CSV cell means 'the money you start with'."""
    npc = _merchant(money=0, money_cap=0, base_money=3000)

    assert npc.money_cap == 3000, f"expected the config baseline, got {npc.money_cap}"


def test_explicit_cap_wins_over_the_config_money() -> None:
    npc = _merchant(money=0, money_cap=500, base_money=3000)

    assert npc.money_cap == 500, f"explicit cap ignored, got {npc.money_cap}"


def test_cap_is_read_from_config_not_from_the_live_purse() -> None:
    """`model` is this NPC's own deep copy, so a drained purse must not lower the cap."""
    npc = _merchant(money=3000, money_cap=0, base_money=3000)
    npc.model.money = 0

    assert npc.money_cap == 3000, f"cap followed the live purse, got {npc.money_cap}"


# ---------------------------------------------------------------------------
# Regeneration
# ---------------------------------------------------------------------------

def test_empty_purse_refills_in_four_days_at_25_percent() -> None:
    npc = _merchant(money=0, base_money=3000)
    seen = [npc.model.money]
    for _ in range(5):
        npc.regenerate_money(1)
        seen.append(npc.model.money)

    assert seen == [0, 750, 1500, 2250, 3000, 3000], f"regeneration curve off: {seen}"


def test_regeneration_never_exceeds_the_cap() -> None:
    npc = _merchant(money=2900, base_money=3000)
    npc.regenerate_money(1)

    assert npc.model.money == 3000, f"purse overflowed the cap: {npc.model.money}"


def test_three_days_at_once_equals_three_single_days() -> None:
    """The N-safety property: returning from a trip is one call, not a loop."""
    at_once = _merchant(money=0, base_money=3000)
    at_once.regenerate_money(3)

    stepwise = _merchant(money=0, base_money=3000)
    for _ in range(3):
        stepwise.regenerate_money(1)

    assert at_once.model.money == stepwise.model.money, (
        f"apply_days(3)={at_once.model.money} != 3x apply_days(1)={stepwise.model.money}"
    )


def test_many_days_at_once_still_stops_at_the_cap() -> None:
    npc = _merchant(money=0, base_money=3000)
    npc.regenerate_money(100)

    assert npc.model.money == 3000, f"long absence overflowed the cap: {npc.model.money}"


def test_zero_regen_pct_leaves_the_purse_alone() -> None:
    """A merchant whose CSV row sets 0% simply never recovers."""
    npc = _merchant(money=120, money_regen_pct=0.0, base_money=3000)
    npc.regenerate_money(5)

    assert npc.model.money == 120, f"purse moved with 0% regen: {npc.model.money}"


# ---------------------------------------------------------------------------
# Stock re-roll
# ---------------------------------------------------------------------------

def test_restock_drops_goods_bought_from_the_player() -> None:
    """Otherwise the player's junk silts up `max_carry_weight` for good."""
    npc = _merchant(money=1000)
    npc.items = [_FakeItem("gem_small_blue"), _FakeItem("rusty_junk"), _FakeItem("dead_fish")]

    npc.restock_items()

    names = sorted(item.name for item in npc.items)
    assert names == ["gem_small_blue", "gem_small_orange"], f"stock not reset to config: {names}"


def test_restock_does_not_pay_the_merchant() -> None:
    """The old `sell_all_bought_items` credited the value of every bought item here."""
    npc = _merchant(money=1000)
    npc.items = [_FakeItem("gem_small_blue"), _FakeItem("rusty_junk")]

    npc.restock_items()

    assert npc.model.money == 1000, f"restock moved the purse: {npc.model.money}"


def test_restock_resets_the_carried_weight() -> None:
    """`total_items_weight` is a running total - clearing `items` must zero it too.

    It did not, so every dawn stacked another stock's worth on the tally; after a
    few days the merchant was nominally over `max_carry_weight` while holding two
    gems, and stopped buying permanently.
    """
    npc = _merchant(money=1000)
    npc.items = [_FakeItem("gem_small_blue", weight=2.0)]
    npc.total_items_weight = 2.0

    for _ in range(10):
        npc.restock_items()

    assert npc.total_items_weight == 2.0, (
        f"carried weight accumulated across dawns: {npc.total_items_weight}"
    )


if __name__ == "__main__":
    tests = [
        ("unset cap falls back to config money", test_unset_cap_falls_back_to_the_config_money),
        ("explicit cap wins", test_explicit_cap_wins_over_the_config_money),
        ("cap read from config, not live purse", test_cap_is_read_from_config_not_from_the_live_purse),
        ("empty purse refills in four days", test_empty_purse_refills_in_four_days_at_25_percent),
        ("regeneration never exceeds the cap", test_regeneration_never_exceeds_the_cap),
        ("three days at once == three single days", test_three_days_at_once_equals_three_single_days),
        ("long absence stops at the cap", test_many_days_at_once_still_stops_at_the_cap),
        ("zero regen leaves the purse alone", test_zero_regen_pct_leaves_the_purse_alone),
        ("restock drops the player's goods", test_restock_drops_goods_bought_from_the_player),
        ("restock does not pay the merchant", test_restock_does_not_pay_the_merchant),
        ("restock resets the carried weight", test_restock_resets_the_carried_weight),
    ]
    failures = 0
    for name, func in tests:
        try:
            func()
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            import traceback

            traceback.print_exc()
            failures += 1

    print(f"\n{'─' * 40}")
    total = len(tests)
    passed = total - failures
    if failures:
        print(f"  FAILED  {failures}/{total} tests")
        sys.exit(1)
    else:
        print(f"  PASSED  {passed}/{total} tests")
