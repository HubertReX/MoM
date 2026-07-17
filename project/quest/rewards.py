"""Quest rewards: apply them all, and label them (Q-05).

Two jobs, both shaped by SSiS bugs:

- :func:`apply_quest_rewards` loops over **every** reward. SSiS's
  ``apply_quest_bonus`` had a stray ``break`` and paid out only the first
  non-zero one; the commented-out loop underneath it showed the intent. Two
  quests were silently short-changed by it (``02_game_mechanics`` and
  ``Q01_S07``). A list is a list.
- :func:`format_reward_label` builds the "+50 💰 · +20 max HP" tail the engine
  appends to a quest's ``success`` text (decision D3=A). The author writes plain
  prose with no ``{value}`` placeholder, so the numbers can change without
  touching translations. SSiS's ``get_quest_bonus_label()`` had the *same*
  ``break`` bug — the label agreed with the payout precisely because both were
  wrong.
"""

from __future__ import annotations

from typing import Callable

from quest.entities import QuestDef, QuestReward, QuestRewardCategory
from dialog.result_sink import ResultSink
from settings import _

# Resolves an item key to its localized display name, e.g. entity_name(model).
ItemNameResolver = Callable[[str], str]


def apply_quest_rewards(quest: QuestDef, sink: ResultSink) -> None:
    """Apply every reward of ``quest``, in order.

    Call once per completion — the caller drives this from
    ``QuestCheckResult.newly_done``, and a quest only ever appears there once
    because :func:`quest.engine.check_quests` marks it done first (the same
    "apply exactly once" shape as ``dialog.result_sink.visit_node``).
    """
    for reward in quest.rewards:
        apply_reward(reward, sink)


def apply_reward(reward: QuestReward, sink: ResultSink) -> None:
    """Dispatch one reward to the sink."""
    category = reward.category

    if category is QuestRewardCategory.money:
        sink.add_money(reward.value)
    elif category is QuestRewardCategory.items:
        sink.add_items(reward.items)
    elif category is QuestRewardCategory.health:
        sink.restore_health(reward.value)
    elif category is QuestRewardCategory.max_health:
        sink.raise_max_health(reward.value)
    elif category is QuestRewardCategory.damage:
        sink.raise_damage(reward.value)
    elif category is QuestRewardCategory.max_items:
        sink.raise_max_items(reward.value)
    elif category is QuestRewardCategory.sentiment:
        if not reward.target:
            # init_quests rejects this; reaching it means hand-built defs
            raise ValueError("sentiment reward has no target NPC")
        sink.shift_sentiment_of(reward.target, reward.value)
    else:
        # unreachable unless a category is added without a handler
        raise ValueError(f"unhandled QuestRewardCategory: {category!r}")


# Locale key per category. Item rewards are named individually instead.
_LABEL_KEYS: dict[QuestRewardCategory, str] = {
    QuestRewardCategory.money: "quest.reward_money",
    QuestRewardCategory.health: "quest.reward_health",
    QuestRewardCategory.max_health: "quest.reward_max_health",
    QuestRewardCategory.damage: "quest.reward_damage",
    QuestRewardCategory.max_items: "quest.reward_max_items",
    QuestRewardCategory.sentiment: "quest.reward_sentiment",
}

_LABEL_SEPARATOR = " · "


def format_reward_label(
    rewards: list[QuestReward], item_name: ItemNameResolver | None = None
) -> str:
    """Render rewards as a single line, e.g. ``+50 💰 · +20 max HP``.

    Empty for a quest with no rewards, so the caller can append it
    unconditionally without producing a trailing separator.

    Args:
        rewards: the quest's rewards, in order.
        item_name: optional ``(item_key) -> str`` resolver for item rewards. The
            raw key is used when it is not supplied, which keeps this function
            usable from tests without the whole config.
    """
    parts: list[str] = []
    for reward in rewards:
        if reward.category is QuestRewardCategory.items:
            parts.extend(item_name(key) if item_name else key for key in reward.items)
            continue
        key = _LABEL_KEYS.get(reward.category)
        if key is None:
            continue
        parts.append(_(key, value=reward.value))
    return _LABEL_SEPARATOR.join(parts)


def success_text(
    success: str, rewards: list[QuestReward], item_name: ItemNameResolver | None = None
) -> str:
    """A quest's completion line with its reward label appended (D3=A).

    ``success`` is finished prose and carries no placeholder; the numbers live in
    the rewards, so rebalancing them never touches a translation.
    """
    label = format_reward_label(rewards, item_name)
    return f"{success}  {label}" if label else success


__all__ = [
    "apply_quest_rewards",
    "apply_reward",
    "format_reward_label",
    "success_text",
]
