#!/usr/bin/env python3
"""Unit tests for quest/entities.py + quest/graph.py (Q-01).

Run from the project root:
    .venv/bin/python tests/test_quest_entities.py

Pure logic (no pygame / SDL, no Pydantic — the web runtime has neither), but we
add ``project`` to the path the same way the dialog tests do.

The happy-path fixture is the real 8-quest graph from
``doc/quest-migration-plan.md``, so the shapes here are the shapes Q-10 will
actually author.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))

from quest import (
    CompletionMode,
    QuestDef,
    QuestReward,
    QuestRewardCategory,
    QuestState,
    children_of,
    init_quests,
)


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def _msgs(key: str) -> dict[str, str]:
    """The three i18n keys every quest carries (decision D3)."""
    return {
        "name": f"M_QUEST_{key}_NAME",
        "description": f"M_QUEST_{key}_DESCRIPTION",
        "success": f"M_QUEST_{key}_SUCCESS",
    }


# The 8 quests of the 1st iteration. Note Q01_S00 is `manual` (an umbrella that
# waits for content still owed by S06/S07) while Q03_S00 is `all_subquests`.
SAMPLE: dict[str, object] = {
    "Q00_S00_WHAT_IS_GOING_ON": {
        **_msgs("Q00_S00_WHAT_IS_GOING_ON"),
        "completion": "test",
        "test": 'visited("CLAPBACK_SWORD", "015")',
        "rewards": [{"category": "money", "value": 50}],
    },
    "Q01_S00_BREAK_THE_CURSE": {
        **_msgs("Q01_S00_BREAK_THE_CURSE"),
        "completion": "manual",
        "requires": ["Q00_S00_WHAT_IS_GOING_ON"],
    },
    "Q01_S01_LEARN_ABOUT_CURSE": {
        **_msgs("Q01_S01_LEARN_ABOUT_CURSE"),
        "completion": "test",
        "test": 'visited("BARMAN_ABSINTHRAYNER", "012")',
        "parent": "Q01_S00_BREAK_THE_CURSE",
    },
    "Q01_S05_MEET_MADAME_SARCASMIA": {
        **_msgs("Q01_S05_MEET_MADAME_SARCASMIA"),
        "completion": "test",
        "test": 'visited("MADAME_SARCASMIA", "SARCASMIA_AA_BACK_SO_SOON")',
        "parent": "Q01_S00_BREAK_THE_CURSE",
        # the edge SSiS never had — without it this quest is unreachable
        "requires": ["Q01_S01_LEARN_ABOUT_CURSE"],
    },
    "Q03_S00_LEARN_ABOUT_CURSE": {
        **_msgs("Q03_S00_LEARN_ABOUT_CURSE"),
        "completion": "all_subquests",
        "requires": ["Q01_S01_LEARN_ABOUT_CURSE"],
        "rewards": [
            {"category": "money", "value": 100},
            {"category": "max_health", "value": 20},
            {"category": "items", "items": ["MERMAIDS_TEAR"]},
        ],
    },
    "Q03_S01_WHO_HAS_MORE_KNOWLEDGE": {
        **_msgs("Q03_S01_WHO_HAS_MORE_KNOWLEDGE"),
        "completion": "test",
        "test": 'visited("POTIONEER_PUZZLEMINT","014") or visited("POTIONEER_PUZZLEMINT","017")',
        "parent": "Q03_S00_LEARN_ABOUT_CURSE",
    },
    "Q03_S02_WHERE_TO_FIND_THIS_PERSON": {
        **_msgs("Q03_S02_WHERE_TO_FIND_THIS_PERSON"),
        "completion": "test",
        "test": 'visited("HAMMER_HOAXHEART", "009")',
        "parent": "Q03_S00_LEARN_ABOUT_CURSE",
    },
    "Q03_S03_HOW_TO_GET_THERE": {
        **_msgs("Q03_S03_HOW_TO_GET_THERE"),
        "completion": "test",
        "test": 'visited("BARMAN_ABSINTHRAYNER", "017")',
        "parent": "Q03_S00_LEARN_ABOUT_CURSE",
    },
}


def test_build_shapes() -> None:
    defs = init_quests(SAMPLE)  # type: ignore[arg-type]
    assert_eq(len(defs), 8, "quest count")
    assert_true(all(isinstance(q, QuestDef) for q in defs.values()), "quest types")

    # completion coerced from string to the enum
    umbrella = defs["Q03_S00_LEARN_ABOUT_CURSE"]
    assert_eq(umbrella.completion, CompletionMode.all_subquests, "completion enum")
    assert_true(umbrella.test is None, "umbrella has no test")

    # quests carry i18n keys, never rendered text (D3)
    assert_eq(umbrella.name, "M_QUEST_Q03_S00_LEARN_ABOUT_CURSE_NAME", "name is a messages key")

    step = defs["Q00_S00_WHAT_IS_GOING_ON"]
    assert_eq(step.completion, CompletionMode.test, "test completion")
    assert_eq(step.test, 'visited("CLAPBACK_SWORD", "015")', "test condition preserved verbatim")

    # manual quest: no test, never auto-completes
    assert_eq(defs["Q01_S00_BREAK_THE_CURSE"].completion, CompletionMode.manual, "manual completion")

    # defaults for the fields most quests omit
    assert_eq(step.requires, [], "requires defaults to empty list")
    assert_true(step.parent is None, "parent defaults to None")
    assert_eq(step.progress_total, 0, "progress_total defaults to 0")


def test_rewards_are_a_list() -> None:
    """All rewards survive, in order — the SSiS `break` bug (Pułapka 1)."""
    defs = init_quests(SAMPLE)  # type: ignore[arg-type]
    rewards = defs["Q03_S00_LEARN_ABOUT_CURSE"].rewards

    assert_eq(len(rewards), 3, "all three rewards kept")
    assert_true(all(isinstance(r, QuestReward) for r in rewards), "reward types")
    assert_eq(
        [r.category for r in rewards],
        [QuestRewardCategory.money, QuestRewardCategory.max_health, QuestRewardCategory.items],
        "reward categories in order",
    )
    assert_eq(rewards[0].value, 100, "money value")
    assert_eq(rewards[2].items, ["MERMAIDS_TEAR"], "item reward keys")
    assert_eq(rewards[2].value, 0, "item reward carries no amount")


def test_children_and_links() -> None:
    defs = init_quests(SAMPLE)  # type: ignore[arg-type]

    assert_eq(
        children_of(defs, "Q03_S00_LEARN_ABOUT_CURSE"),
        [
            "Q03_S01_WHO_HAS_MORE_KNOWLEDGE",
            "Q03_S02_WHERE_TO_FIND_THIS_PERSON",
            "Q03_S03_HOW_TO_GET_THERE",
        ],
        "umbrella children in definition order",
    )
    assert_eq(len(children_of(defs, "Q01_S00_BREAK_THE_CURSE")), 2, "curse chain children")
    assert_eq(children_of(defs, "Q00_S00_WHAT_IS_GOING_ON"), [], "leaf has no children")

    # requires crosses chains (Q03 depends on a Q01 step)
    assert_eq(
        defs["Q03_S00_LEARN_ABOUT_CURSE"].requires,
        ["Q01_S01_LEARN_ABOUT_CURSE"],
        "cross-chain requires edge",
    )
    # Q01_S05 got the requires edge SSiS never gave it
    assert_eq(
        defs["Q01_S05_MEET_MADAME_SARCASMIA"].requires,
        ["Q01_S01_LEARN_ABOUT_CURSE"],
        "Q01_S05 is reachable",
    )


def test_quest_state() -> None:
    state = QuestState()
    assert_true(not state.is_done("Q00_S00_WHAT_IS_GOING_ON"), "unknown key is not done")

    state.mark_done("Q00_S00_WHAT_IS_GOING_ON")
    assert_true(state.is_done("Q00_S00_WHAT_IS_GOING_ON"), "marked done")
    assert_eq(state.done_keys(), {"Q00_S00_WHAT_IS_GOING_ON"}, "done keys")

    state.mark_done("Q00_S00_WHAT_IS_GOING_ON", False)
    assert_true(not state.is_done("Q00_S00_WHAT_IS_GOING_ON"), "un-marked")
    assert_eq(state.done_keys(), set(), "no done keys left")

    # serialised shape is exactly {key: {"done": bool}}
    state.mark_done("Q03_S01_WHO_HAS_MORE_KNOWLEDGE")
    assert_eq(
        state.to_dict()["Q03_S01_WHO_HAS_MORE_KNOWLEDGE"],
        {"done": True},
        "serialised entry shape",
    )

    # to_dict copies: mutating the dump must not reach back into the state
    dumped = state.to_dict()
    dumped["Q03_S01_WHO_HAS_MORE_KNOWLEDGE"]["done"] = False
    assert_true(state.is_done("Q03_S01_WHO_HAS_MORE_KNOWLEDGE"), "dump is a copy")


def test_quest_state_roundtrip_and_corruption() -> None:
    state = QuestState()
    state.mark_done("Q03_S01_WHO_HAS_MORE_KNOWLEDGE")
    state.mark_done("Q03_S02_WHERE_TO_FIND_THIS_PERSON", False)

    restored = QuestState.from_dict(state.to_dict())
    assert_eq(restored.to_dict(), state.to_dict(), "roundtrip is lossless")
    assert_true(restored.is_done("Q03_S01_WHO_HAS_MORE_KNOWLEDGE"), "done survives roundtrip")

    # a hand-edited / corrupted save degrades to "not done" instead of crashing
    assert_eq(QuestState.from_dict(None).entries, {}, "None -> empty state")
    assert_eq(QuestState.from_dict("garbage").entries, {}, "junk -> empty state")  # type: ignore[arg-type]
    broken = QuestState.from_dict({"Q00_S00_WHAT_IS_GOING_ON": "yes"})
    assert_true(not broken.is_done("Q00_S00_WHAT_IS_GOING_ON"), "non-dict entry -> not done")
    assert_true(not QuestState.from_dict({"Q_X": {}}).is_done("Q_X"), "entry without 'done' -> not done")

    # unknown fields in an entry are preserved (forward compatibility for Q-06)
    extra = QuestState.from_dict({"Q_X": {"done": True, "completed_at": 42}})
    assert_eq(extra.to_dict()["Q_X"]["completed_at"], 42, "unknown entry field kept")


def _expect_value_error(fn, msg: str) -> None:  # type: ignore[no-untyped-def]
    try:
        fn()
    except ValueError:
        return
    raise AssertionError(f"expected ValueError: {msg}")


def test_rejects_umbrella_without_subquests() -> None:
    """The Q01_S07 bug (Pułapka 2): an umbrella nobody parents to is a corpse.

    In SSiS this shipped as `test: "False"` with no subquests — it could never
    complete, and it silently blocked the entire curse chain behind it. This is
    the single check that decision D5 (explicit `completion`) exists to enable.
    """
    corpse = {
        "Q01_S07_STAY_SAFE": {
            **_msgs("Q01_S07_STAY_SAFE"),
            "completion": "all_subquests",
        },
    }
    _expect_value_error(lambda: init_quests(corpse), "umbrella with no subquests")  # type: ignore[arg-type]

    # ...and the same quest is fine the moment a subquest names it as parent
    revived = {
        **corpse,
        "Q01_S07_S01_FIND_SHELTER": {
            **_msgs("Q01_S07_S01_FIND_SHELTER"),
            "completion": "test",
            "test": 'visited("MADAME_SARCASMIA", "001")',
            "parent": "Q01_S07_STAY_SAFE",
        },
    }
    defs = init_quests(revived)  # type: ignore[arg-type]
    assert_eq(len(children_of(defs, "Q01_S07_STAY_SAFE")), 1, "umbrella revived by a subquest")


def test_rejects_impossible_completion() -> None:
    # completion=test with nothing to test
    _expect_value_error(
        lambda: init_quests({"Q_X": {**_msgs("Q_X"), "completion": "test"}}),  # type: ignore[arg-type]
        "test completion without a test",
    )
    # completion=test with an empty test is the same corpse, spelled differently
    _expect_value_error(
        lambda: init_quests({"Q_X": {**_msgs("Q_X"), "completion": "test", "test": ""}}),  # type: ignore[arg-type]
        "test completion with empty test",
    )
    # manual + test is a contradiction: the test would never run
    _expect_value_error(
        lambda: init_quests(
            {"Q_X": {**_msgs("Q_X"), "completion": "manual", "test": "quest_done('Q_Y')"}}  # type: ignore[arg-type]
        ),
        "manual completion with a test",
    )
    # unknown completion mode
    _expect_value_error(
        lambda: init_quests({"Q_X": {**_msgs("Q_X"), "completion": "whenever"}}),  # type: ignore[arg-type]
        "unknown completion mode",
    )


def test_rejects_dangling_links() -> None:
    base = {**_msgs("Q_X"), "completion": "manual"}

    _expect_value_error(
        lambda: init_quests({"Q_X": {**base, "requires": ["Q_MISSING"]}}),  # type: ignore[arg-type]
        "dangling requires",
    )
    _expect_value_error(
        lambda: init_quests({"Q_X": {**base, "parent": "Q_MISSING"}}),  # type: ignore[arg-type]
        "dangling parent",
    )
    _expect_value_error(
        lambda: init_quests({"Q_X": {**base, "requires": ["Q_X"]}}),  # type: ignore[arg-type]
        "self-require",
    )
    _expect_value_error(
        lambda: init_quests({"Q_X": {**base, "parent": "Q_X"}}),  # type: ignore[arg-type]
        "self-parent",
    )
    _expect_value_error(
        lambda: init_quests(
            {  # type: ignore[arg-type]
                "Q_X": {**base, "requires": ["Q_Y", "Q_Y"]},
                "Q_Y": {**_msgs("Q_Y"), "completion": "manual"},
            }
        ),
        "duplicate requires",
    )


def test_rejects_missing_fields() -> None:
    _expect_value_error(
        lambda: init_quests({"Q_X": {"completion": "manual"}}),  # type: ignore[arg-type]
        "missing name/description/success",
    )
    _expect_value_error(
        lambda: init_quests({"Q_X": {**_msgs("Q_X")}}),  # type: ignore[arg-type]
        "missing completion",
    )
    _expect_value_error(
        lambda: init_quests({"Q_X": "not an object"}),  # type: ignore[arg-type]
        "quest is not an object",
    )


def test_rejects_empty_rewards() -> None:
    """A reward that pays out nothing is never intentional (Pułapka 1)."""
    base = {**_msgs("Q_X"), "completion": "manual"}

    _expect_value_error(
        lambda: init_quests({"Q_X": {**base, "rewards": [{"category": "money", "value": 0}]}}),  # type: ignore[arg-type]
        "numeric reward with no value",
    )
    _expect_value_error(
        lambda: init_quests({"Q_X": {**base, "rewards": [{"category": "items", "items": []}]}}),  # type: ignore[arg-type]
        "items reward with no items",
    )
    _expect_value_error(
        lambda: init_quests({"Q_X": {**base, "rewards": [{"category": "agility", "value": 1}]}}),  # type: ignore[arg-type]
        "reward category dropped in D11 (agility)",
    )
    _expect_value_error(
        lambda: init_quests({"Q_X": {**base, "rewards": [{"value": 1}]}}),  # type: ignore[arg-type]
        "reward without a category",
    )


def test_progress_fields_pair_up() -> None:
    base = {**_msgs("Q_X"), "completion": "manual"}

    # both set: fine
    defs = init_quests(
        {"Q_X": {**base, "progress": 'item_count("MERMAIDS_TEAR")', "progress_total": 3}}  # type: ignore[arg-type]
    )
    assert_eq(defs["Q_X"].progress_total, 3, "progress_total kept")

    _expect_value_error(
        lambda: init_quests({"Q_X": {**base, "progress": 'item_count("X")'}}),  # type: ignore[arg-type]
        "progress without a total",
    )
    _expect_value_error(
        lambda: init_quests({"Q_X": {**base, "progress_total": 3}}),  # type: ignore[arg-type]
        "total without a progress expression",
    )


def main() -> None:
    tests = [
        test_build_shapes,
        test_rewards_are_a_list,
        test_children_and_links,
        test_quest_state,
        test_quest_state_roundtrip_and_corruption,
        test_rejects_umbrella_without_subquests,
        test_rejects_impossible_completion,
        test_rejects_dangling_links,
        test_rejects_missing_fields,
        test_rejects_empty_rewards,
        test_progress_fields_pair_up,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} quest entity tests passed.")


if __name__ == "__main__":
    main()
