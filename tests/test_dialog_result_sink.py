#!/usr/bin/env python3
"""Unit tests for dialog result sink application (T-034).

Run from the project root:
    .venv/bin/python tests/test_dialog_result_sink.py

Pure logic (no pygame / SDL needed).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))

from dialog import (
    DialogNode,
    NodeVisitResult,
    NodeVisitResultCategory,
    apply_result,
    visit_node
    )
from enums import NotificationTypeEnum
from result_sink_adapter import GameResultSink


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


@dataclass
class _FakeNotification:
    message: str = ""
    create_time: float = 0.0


# ---------------------------------------------------------------------------
# Fake sink that records every call for dispatch testing
# ---------------------------------------------------------------------------


class FakeSink:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def add_money(self, amount: int) -> None:
        self.calls.append(("add_money", amount))

    def remove_money(self, amount: int) -> None:
        self.calls.append(("remove_money", amount))

    def add_items(self, item_keys: list[str]) -> None:
        self.calls.append(("add_items", list(item_keys)))

    def remove_items(self, item_keys: list[str]) -> None:
        self.calls.append(("remove_items", list(item_keys)))

    def restore_health(self, amount: int) -> None:
        self.calls.append(("restore_health", amount))

    def lose_health(self, amount: int) -> None:
        self.calls.append(("lose_health", amount))

    def shift_sentiment(self, amount: int, emote_key: str = "") -> None:
        self.calls.append(("shift_sentiment", amount))


# ---------------------------------------------------------------------------
# Tests for apply_result dispatch
# ---------------------------------------------------------------------------


def test_apply_result_dispatches_money_received() -> None:
    sink = FakeSink()
    result = NodeVisitResult(
        key="R", category=NodeVisitResultCategory.MONEY_RECEIVED, money=42
    )
    apply_result(result, sink)
    assert_eq(sink.calls, [("add_money", 42)])


def test_apply_result_dispatches_money_returned() -> None:
    sink = FakeSink()
    result = NodeVisitResult(
        key="R", category=NodeVisitResultCategory.MONEY_RETURNED, money=7
    )
    apply_result(result, sink)
    assert_eq(sink.calls, [("remove_money", 7)])


def test_apply_result_dispatches_items_received() -> None:
    sink = FakeSink()
    result = NodeVisitResult(
        key="R",
        category=NodeVisitResultCategory.ITEMS_RECEIVED,
        items=["GOLDEN_KEY", "POTION"],
    )
    apply_result(result, sink)
    assert_eq(sink.calls, [("add_items", ["GOLDEN_KEY", "POTION"])])


def test_apply_result_dispatches_items_returned() -> None:
    sink = FakeSink()
    result = NodeVisitResult(
        key="R",
        category=NodeVisitResultCategory.ITEMS_RETURNED,
        items=["MERMAIDS_TEAR"],
    )
    apply_result(result, sink)
    assert_eq(sink.calls, [("remove_items", ["MERMAIDS_TEAR"])])


def test_apply_result_dispatches_health_restored() -> None:
    sink = FakeSink()
    result = NodeVisitResult(
        key="R", category=NodeVisitResultCategory.HEALTH_RESTORED, health=15
    )
    apply_result(result, sink)
    assert_eq(sink.calls, [("restore_health", 15)])


def test_apply_result_dispatches_health_lost() -> None:
    sink = FakeSink()
    result = NodeVisitResult(
        key="R", category=NodeVisitResultCategory.HEALTH_LOST, health=5
    )
    apply_result(result, sink)
    assert_eq(sink.calls, [("lose_health", 5)])


def test_apply_result_dispatches_sentiment_shift() -> None:
    sink = FakeSink()
    result = NodeVisitResult(
        key="R", category=NodeVisitResultCategory.SENTIMENT_SHIFT, value=-10
    )
    apply_result(result, sink)
    assert_eq(sink.calls, [("shift_sentiment", -10)])


# ---------------------------------------------------------------------------
# Tests for visit_node idempotency
# ---------------------------------------------------------------------------


def test_visit_node_applies_effect_only_on_first_visit() -> None:
    sink = FakeSink()
    result = NodeVisitResult(
        key="R", category=NodeVisitResultCategory.MONEY_RECEIVED, money=5
    )
    node = DialogNode(key="N", text="msg", result=result)

    first = visit_node(node, sink)
    assert_eq(first, True, "first visit should apply")
    assert_eq(node.visited, True, "node should be marked visited")
    assert_eq(sink.calls, [("add_money", 5)])

    second = visit_node(node, sink)
    assert_eq(second, False, "second visit should not apply")
    assert_eq(sink.calls, [("add_money", 5)], "no extra sink calls")


def test_visit_node_without_result_still_marks_visited() -> None:
    sink = FakeSink()
    node = DialogNode(key="N", text="msg")
    assert_eq(visit_node(node, sink), True)
    assert_eq(node.visited, True)
    assert_eq(sink.calls, [])
    assert_eq(visit_node(node, sink), False)


# ---------------------------------------------------------------------------
# Tests for GameResultSink with lightweight mocks
# ---------------------------------------------------------------------------


@dataclass
class _FakeItemModel:
    weight: float = 1.0
    count: int = 1
    name_EN: str = "Sword"
    name_PL: str = "Miecz"


@dataclass
class _FakeItem:
    name: str
    model: _FakeItemModel


@dataclass
class _FakePlayerModel:
    money: int = 0
    health: int = 20
    max_health: int = 30


@dataclass
class _FakeScene:
    created: list[tuple[str, int, int, dict[str, bool]]] = field(default_factory=list)
    notifications: list[_FakeNotification] = field(default_factory=list)

    def create_item(
        self, name: str, x: int, y: int, show: bool = True
    ) -> _FakeItem:
        self.created.append((name, x, y, {"show": show}))
        return _FakeItem(name, _FakeItemModel())

    def add_notification(
        self, text: str, type: NotificationTypeEnum = NotificationTypeEnum.info,
        emote_key: str = "",
    ) -> None:
        self.notifications.append(_FakeNotification(message=text))


@dataclass
class _FakePlayer:
    model: _FakePlayerModel
    items: list[_FakeItem] = field(default_factory=list)
    total_items_weight: float = 0.0
    selected_item_idx: int = -1
    scene: _FakeScene = field(default_factory=_FakeScene)

    def pick_up(self, item: _FakeItem) -> bool:
        for owned in self.items:
            if owned.name == item.name:
                owned.model.count += 1
                self.total_items_weight += item.model.weight
                return True
        self.items.append(item)
        self.total_items_weight += item.model.weight
        if self.selected_item_idx < 0:
            self.selected_item_idx = 0
        return True


@dataclass
class _FakeNPC:
    sentiment: int = 50


def test_game_sink_money() -> None:
    player = _FakePlayer(_FakePlayerModel(money=100))
    npc = _FakeNPC()
    sink = GameResultSink(player, npc)  # type: ignore[arg-type]

    sink.add_money(50)
    assert_eq(player.model.money, 150)

    sink.remove_money(30)
    assert_eq(player.model.money, 120)

    sink.remove_money(500)
    assert_eq(player.model.money, 0)


def test_game_sink_items() -> None:
    player = _FakePlayer(_FakePlayerModel())
    npc = _FakeNPC()
    sink = GameResultSink(player, npc)  # type: ignore[arg-type]

    sink.add_items(["SWORD", "SHIELD"])
    assert_eq(len(player.items), 2)
    assert_eq(player.total_items_weight, 2.0)
    assert_eq(player.items[0].name, "SWORD")

    sink.add_items(["SWORD"])
    assert_eq(len(player.items), 2)
    assert_eq(player.items[0].model.count, 2)
    assert_eq(player.total_items_weight, 3.0)

    sink.remove_items(["SWORD"])
    assert_eq(player.items[0].model.count, 1)
    assert_eq(player.total_items_weight, 2.0)

    sink.remove_items(["SHIELD"])
    assert_eq(len(player.items), 1)
    assert_eq(player.selected_item_idx, 0)


def test_game_sink_health() -> None:
    player = _FakePlayer(_FakePlayerModel(health=20, max_health=30))
    npc = _FakeNPC()
    sink = GameResultSink(player, npc)  # type: ignore[arg-type]

    sink.restore_health(15)
    assert_eq(player.model.health, 30)

    sink.lose_health(5)
    assert_eq(player.model.health, 25)

    sink.lose_health(100)
    assert_eq(player.model.health, 0)


def test_game_sink_sentiment_clamps() -> None:
    player = _FakePlayer(_FakePlayerModel())
    npc = _FakeNPC(sentiment=50)
    sink = GameResultSink(player, npc)  # type: ignore[arg-type]

    sink.shift_sentiment(30)
    assert_eq(npc.sentiment, 80)

    sink.shift_sentiment(30)
    assert_eq(npc.sentiment, 100)

    sink.shift_sentiment(-200)
    assert_eq(npc.sentiment, 0)


def test_game_sink_visit_node_only_once() -> None:
    player = _FakePlayer(_FakePlayerModel(money=0))
    npc = _FakeNPC()
    sink = GameResultSink(player, npc)  # type: ignore[arg-type]
    result = NodeVisitResult(
        key="R", category=NodeVisitResultCategory.MONEY_RECEIVED, money=10
    )
    node = DialogNode(key="N", text="msg", result=result)

    assert_eq(visit_node(node, sink), True)
    assert_eq(player.model.money, 10)
    assert_eq(visit_node(node, sink), False)
    assert_eq(player.model.money, 10)


if __name__ == "__main__":
    test_apply_result_dispatches_money_received()
    test_apply_result_dispatches_money_returned()
    test_apply_result_dispatches_items_received()
    test_apply_result_dispatches_items_returned()
    test_apply_result_dispatches_health_restored()
    test_apply_result_dispatches_health_lost()
    test_apply_result_dispatches_sentiment_shift()
    test_visit_node_applies_effect_only_on_first_visit()
    test_visit_node_without_result_still_marks_visited()
    test_game_sink_money()
    test_game_sink_items()
    test_game_sink_health()
    test_game_sink_sentiment_clamps()
    test_game_sink_visit_node_only_once()
    print("All result-sink tests passed.")
