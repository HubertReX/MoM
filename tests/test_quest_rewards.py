#!/usr/bin/env python3
"""Unit tests for quest/rewards.py — apply them all, label them (Q-05).

Run from the project root:
    .venv/bin/python tests/test_quest_rewards.py

The headline test is `test_every_reward_is_applied`: SSiS's `apply_quest_bonus`
had a stray `break` and paid out only the first non-zero reward, and its label
function had the same bug — so the label agreed with the payout precisely
because both were wrong.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from quest.entities import CompletionMode, QuestDef, QuestReward, QuestRewardCategory
from quest.graph import init_quests
from quest.rewards import apply_quest_rewards, format_reward_label, success_text


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


class SpySink:
    """Records every call the rewards make."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def add_money(self, amount: int) -> None:
        self.calls.append(("add_money", amount))

    def add_items(self, item_keys: list[str]) -> None:
        self.calls.append(("add_items", list(item_keys)))

    def restore_health(self, amount: int) -> None:
        self.calls.append(("restore_health", amount))

    def raise_max_health(self, amount: int) -> None:
        self.calls.append(("raise_max_health", amount))

    def raise_damage(self, amount: int) -> None:
        self.calls.append(("raise_damage", amount))

    def raise_max_items(self, amount: int) -> None:
        self.calls.append(("raise_max_items", amount))

    def shift_sentiment_of(self, npc_key: str, amount: int) -> None:
        self.calls.append(("shift_sentiment_of", (npc_key, amount)))

    # unused by quests, present so the Protocol is satisfied
    def remove_money(self, amount: int) -> None: ...
    def remove_items(self, item_keys: list[str]) -> None: ...
    def lose_health(self, amount: int) -> None: ...
    def shift_sentiment(self, amount: int, emote_key: str = "") -> None: ...


def _quest(*rewards: QuestReward) -> QuestDef:
    return QuestDef("Q_X", "n", "d", "s", CompletionMode.manual, rewards=list(rewards))


def test_every_reward_is_applied() -> None:
    """Pułapka 1: a list of three rewards pays out three times, not once."""
    quest = _quest(
        QuestReward(QuestRewardCategory.money, 100),
        QuestReward(QuestRewardCategory.max_health, 20),
        QuestReward(QuestRewardCategory.items, items=["MERMAIDS_TEAR"]),
    )
    sink = SpySink()

    apply_quest_rewards(quest, sink)

    assert_eq(
        sink.calls,
        [
            ("add_money", 100),
            ("raise_max_health", 20),
            ("add_items", ["MERMAIDS_TEAR"]),
        ],
        "all three rewards applied, in order",
    )


def test_every_category_reaches_its_sink_method() -> None:
    quest = _quest(
        QuestReward(QuestRewardCategory.money, 10),
        QuestReward(QuestRewardCategory.health, 5),
        QuestReward(QuestRewardCategory.max_health, 20),
        QuestReward(QuestRewardCategory.damage, 5),
        QuestReward(QuestRewardCategory.max_items, 1),
        QuestReward(QuestRewardCategory.sentiment, 10, target="BARMAN_ABSINTHRAYNER"),
        QuestReward(QuestRewardCategory.items, items=["A", "B"]),
    )
    sink = SpySink()

    apply_quest_rewards(quest, sink)

    assert_eq(
        [name for name, _ in sink.calls],
        [
            "add_money", "restore_health", "raise_max_health", "raise_damage",
            "raise_max_items", "shift_sentiment_of", "add_items",
        ],
        "every category has a handler",
    )
    assert_eq(sink.calls[5][1], ("BARMAN_ABSINTHRAYNER", 10), "sentiment carries its target")


def test_no_rewards_is_quiet() -> None:
    sink = SpySink()
    apply_quest_rewards(_quest(), sink)
    assert_eq(sink.calls, [], "a quest with no rewards touches nothing")


def test_reward_label() -> None:
    """Labels are RichText markup, not plain text.

    The numbers carry ``[num]`` so they pop in the panel's reward chips, and money
    uses the ``:golden_coin:`` sprite rather than 💰 — measured: the emoji is not
    in MoM's pixel font and renders as a tofu box.
    """
    label = format_reward_label(
        [
            QuestReward(QuestRewardCategory.money, 50),
            QuestReward(QuestRewardCategory.max_health, 20),
        ]
    )
    assert_eq(
        label,
        "[num]+50[/num] :golden_coin: · [num]+20[/num] max HP",
        "both rewards, numbers tagged, separated by a middle dot",
    )
    assert_true("💰" not in label, "no emoji: it would render as tofu in the game font")

    assert_eq(format_reward_label([]), "", "no rewards -> empty label, no dangling separator")


def test_reward_label_names_items() -> None:
    rewards = [QuestReward(QuestRewardCategory.items, items=["MERMAIDS_TEAR"])]

    assert_eq(format_reward_label(rewards), "MERMAIDS_TEAR", "raw key without a resolver")
    assert_eq(
        format_reward_label(rewards, lambda key: "Łza syrenki"),
        "Łza syrenki",
        "resolver gives the display name",
    )


def test_success_text_appends_the_label() -> None:
    """D3=A: the author writes prose, the engine adds the numbers."""
    prose = "Wiesz już, kto, gdzie i jak."
    rewards = [QuestReward(QuestRewardCategory.max_health, 10)]

    assert_true(prose in success_text(prose, rewards), "prose kept verbatim")
    assert_true("[num]+10[/num] max HP" in success_text(prose, rewards), "label appended")
    # no rewards -> the prose is the whole line, with no trailing whitespace games
    assert_eq(success_text(prose, []), prose, "rewardless quest reads as plain prose")
    # the prose carries no placeholder, so rebalancing never touches a translation
    assert_true("{value}" not in prose, "success text has no placeholder by design")


def _expect_value_error(fn, msg: str) -> None:  # type: ignore[no-untyped-def]
    try:
        fn()
    except ValueError:
        return
    raise AssertionError(f"expected ValueError: {msg}")


def test_sentiment_reward_must_name_an_npc() -> None:
    """A quest has no current NPC, so a targetless sentiment reward is a no-op."""
    quests = {
        "Q_X": {
            "name": "n", "description": "d", "success": "s", "completion": "manual",
            "rewards": [{"category": "sentiment", "value": 10}],
        }
    }
    _expect_value_error(lambda: init_quests(quests), "sentiment without a target")  # type: ignore[arg-type]

    # ...and with a target it builds fine
    quests["Q_X"]["rewards"][0]["target"] = "BARMAN_ABSINTHRAYNER"  # type: ignore[index]
    defs = init_quests(quests)  # type: ignore[arg-type]
    assert_eq(defs["Q_X"].rewards[0].target, "BARMAN_ABSINTHRAYNER", "target kept")


def test_only_sentiment_takes_a_target() -> None:
    quests = {
        "Q_X": {
            "name": "n", "description": "d", "success": "s", "completion": "manual",
            "rewards": [{"category": "money", "value": 10, "target": "BARMAN_ABSINTHRAYNER"}],
        }
    }
    _expect_value_error(lambda: init_quests(quests), "money reward with a target")  # type: ignore[arg-type]


def main() -> None:
    tests = [
        test_every_reward_is_applied,
        test_every_category_reaches_its_sink_method,
        test_no_rewards_is_quiet,
        test_reward_label,
        test_reward_label_names_items,
        test_success_text_appends_the_label,
        test_sentiment_reward_must_name_an_npc,
        test_only_sentiment_takes_a_target,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} quest reward tests passed.")


if __name__ == "__main__":
    main()
