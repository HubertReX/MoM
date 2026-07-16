"""Build the quest definitions from config dicts.

Mirror of :func:`dialog.graph.init_dialog`: a *pure* function (no pygame, no
game object) turning the ``config.json["quests"]`` section into a resolved
``{key: QuestDef}`` map, failing loudly on anything malformed.

The input section is ``{quest_key: {...}}``::

    {
        "Q03_S00_LEARN_ABOUT_CURSE": {
            "name": "M_QUEST_Q03_S00_LEARN_ABOUT_CURSE_NAME",
            "description": "M_QUEST_Q03_S00_LEARN_ABOUT_CURSE_DESCRIPTION",
            "success": "M_QUEST_Q03_S00_LEARN_ABOUT_CURSE_SUCCESS",
            "completion": "all_subquests",
            "requires": ["Q01_S01_LEARN_ABOUT_CURSE"],
            "rewards": [{"category": "money", "value": 50}]
        }
    }

Validation here is **structural only** — dangling ``requires`` / ``parent``,
and the ``completion`` contradictions that made SSiS quests silently
uncompletable. Two checks live elsewhere on purpose:

- mini-DSL ``test`` expressions are validated at *import* time (Q-04), once
  ``quest_done()`` exists in the whitelist (Q-02);
- acyclicity of the ``requires`` graph is the engine's concern (Q-03).
"""

from __future__ import annotations

from typing import Any

from quest.entities import (
    CompletionMode,
    QuestDef,
    QuestReward,
    QuestRewardCategory,
)


def init_quests(quests: dict[str, Any]) -> dict[str, QuestDef]:
    """Build the ``{key: QuestDef}`` map from the config ``quests`` section.

    Raises:
        ValueError: on an unknown field value, a dangling ``requires`` /
            ``parent`` reference, or a ``completion`` mode the quest cannot
            possibly satisfy. The message always names the offending quest.
    """
    defs = {key: _build_quest(key, data) for key, data in quests.items()}
    _validate_references(defs)
    return defs


def children_of(defs: dict[str, QuestDef], key: str) -> list[str]:
    """Keys of the subquests parented to ``key``, in definition order."""
    return [child.key for child in defs.values() if child.parent == key]


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _build_quest(key: str, data: dict[str, Any]) -> QuestDef:
    if not isinstance(data, dict):
        raise ValueError(f"quest {key!r} must be an object, got {type(data).__name__}")

    for required_field in ("name", "description", "success", "completion"):
        if required_field not in data:
            raise ValueError(f"quest {key!r} is missing {required_field!r}")

    try:
        completion = CompletionMode(data["completion"])
    except ValueError as error:
        modes = ", ".join(mode.value for mode in CompletionMode)
        raise ValueError(
            f"quest {key!r} has unknown completion {data['completion']!r} (expected one of: {modes})"
        ) from error

    return QuestDef(
        key,
        data["name"],
        data["description"],
        data["success"],
        completion,
        test=data.get("test"),
        progress=data.get("progress"),
        progress_total=data.get("progress_total", 0),
        requires=list(data.get("requires", [])),
        parent=data.get("parent"),
        rewards=[_build_reward(key, r) for r in data.get("rewards", [])],
    )


def _build_reward(quest_key: str, data: dict[str, Any]) -> QuestReward:
    if not isinstance(data, dict) or "category" not in data:
        raise ValueError(f"quest {quest_key!r} has a reward without a 'category'")

    try:
        category = QuestRewardCategory(data["category"])
    except ValueError as error:
        categories = ", ".join(c.value for c in QuestRewardCategory)
        raise ValueError(
            f"quest {quest_key!r} has unknown reward category {data['category']!r} "
            f"(expected one of: {categories})"
        ) from error

    reward = QuestReward(
        category,
        value=data.get("value", 0),
        items=list(data.get("items", [])),
    )

    # An items reward with no items (or a numeric reward with no amount) is the
    # SSiS "zero reward" shape that the stray `break` used to skip over. It is
    # never intentional, so it fails here rather than paying out nothing.
    if category is QuestRewardCategory.items:
        if not reward.items:
            raise ValueError(f"quest {quest_key!r} has an 'items' reward with no items")
    elif reward.value == 0:
        raise ValueError(
            f"quest {quest_key!r} has a {category.value!r} reward with no value"
        )

    return reward


# ---------------------------------------------------------------------------
# Cross-quest validation
# ---------------------------------------------------------------------------


def _validate_references(defs: dict[str, QuestDef]) -> None:
    for key, quest in defs.items():
        _validate_links(key, quest, defs)
        _validate_completion(key, quest, defs)
        _validate_progress(key, quest)


def _validate_links(key: str, quest: QuestDef, defs: dict[str, QuestDef]) -> None:
    for req in quest.requires:
        if req == key:
            raise ValueError(f"quest {key!r} requires itself")
        if req not in defs:
            raise ValueError(f"quest {key!r} requires unknown quest {req!r}")

    if len(set(quest.requires)) != len(quest.requires):
        raise ValueError(f"quest {key!r} lists a duplicate in 'requires'")

    if quest.parent is not None:
        if quest.parent == key:
            raise ValueError(f"quest {key!r} is its own parent")
        if quest.parent not in defs:
            raise ValueError(f"quest {key!r} has unknown parent {quest.parent!r}")


def _validate_completion(key: str, quest: QuestDef, defs: dict[str, QuestDef]) -> None:
    """Reject every ``completion`` mode the quest could not possibly satisfy.

    This is the check that would have caught ``Q01_S07`` in SSiS: an umbrella
    with no subquests, or a ``test`` quest with nothing to test, can only ever
    read as "in progress" — forever, silently, taking its whole chain with it.
    """
    if quest.completion is CompletionMode.all_subquests:
        if not children_of(defs, key):
            raise ValueError(
                f"quest {key!r} has completion 'all_subquests' but no subquest "
                f"names it as 'parent' — it could never complete"
            )
    elif quest.completion is CompletionMode.test:
        if not quest.test:
            raise ValueError(
                f"quest {key!r} has completion 'test' but no 'test' condition"
            )
    elif quest.completion is CompletionMode.manual:
        if quest.test:
            raise ValueError(
                f"quest {key!r} has completion 'manual' but also a 'test' condition "
                f"({quest.test!r}) — the test would never run"
            )


def _validate_progress(key: str, quest: QuestDef) -> None:
    """``progress`` and ``progress_total`` are a pair: both or neither.

    An umbrella's progress is counted from its subquests by the engine, so it
    needs neither field.
    """
    if quest.progress and quest.progress_total <= 0:
        raise ValueError(
            f"quest {key!r} has a 'progress' expression but progress_total="
            f"{quest.progress_total} (expected a positive total)"
        )
    if quest.progress_total > 0 and not quest.progress:
        raise ValueError(
            f"quest {key!r} has progress_total={quest.progress_total} but no "
            f"'progress' expression"
        )


__all__ = [
    "init_quests",
    "children_of",
]
