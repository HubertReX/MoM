#!/usr/bin/env python3
"""Unit tests for quest/runtime.py — events, sweep, rewards (Q-07).

Run from the project root:
    .venv/bin/python tests/test_quest_runtime.py

The sweep is a safety net, not a mechanism (decision D12=C). These tests pin both
halves of that: it must catch a change no event reported, and it must *say so*.
A net that quietly does the mechanism's job hides every missing hook forever.
"""

from __future__ import annotations

import io
import contextlib
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
sys.path.insert(0, os.path.dirname(__file__))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from quest.entities import QuestState
from quest.runtime import SWEEP_INTERVAL, QuestRuntime, quest_config
from test_quest_entities import SAMPLE

Q00 = "Q00_S00_WHAT_IS_GOING_ON"


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


class SpySink:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def add_money(self, amount: int) -> None:
        self.calls.append(("add_money", amount))

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        def record(*args: object) -> None:
            self.calls.append((name, args))
        return record


def _runtime(visits: dict[str, set[str]] | None = None) -> tuple[QuestRuntime, SpySink]:
    """A runtime over the real 8-quest graph, with a stub scene."""
    sink = SpySink()
    toasts: list[tuple[str, object]] = []
    scene = SimpleNamespace(
        game=SimpleNamespace(conf=SimpleNamespace(quests=SAMPLE, messages={}, items={})),
        quest_state=QuestState(),
        loaded_NPCs={},
        loaded_maps={},
        pending_map_states={},
        player=SimpleNamespace(items=[]),
        toasts=toasts,
    )
    scene.add_notification = lambda text, type=None, emote_key="": toasts.append((text, type))
    runtime = QuestRuntime(scene, sink_factory=lambda: sink)

    if visits:
        runtime.ctx = SimpleNamespace(  # type: ignore[assignment]
            visited=lambda node, npc=None: node in (visits or {}).get(npc, set()),
            has_item=lambda key: False,
            item_count=lambda key: 0,
            quest_done=lambda key: scene.quest_state.is_done(key),
        )
    return runtime, sink


def _capture(fn, *args) -> str:  # type: ignore[no-untyped-def]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


def test_event_completes_a_quest() -> None:
    runtime, _ = _runtime({"CLAPBACK_SWORD": {"015"}})

    result = runtime.on_event("DialogPanel_closed")

    assert_eq(result.newly_done, [Q00], "the event did the work")
    assert_true(runtime.scene.quest_state.is_done(Q00), "state updated")


def test_sweep_is_quiet_when_events_did_the_work() -> None:
    """The DoD of Q-07: correct wiring produces no warnings."""
    runtime, _ = _runtime({"CLAPBACK_SWORD": {"015"}})
    runtime.on_event("DialogPanel_closed")

    output = _capture(runtime.update, SWEEP_INTERVAL + 0.1)

    assert_eq(output, "", "a sweep with nothing left to do says nothing")


def test_sweep_catches_and_reports_a_missing_event() -> None:
    """The net must complain, not just cope."""
    runtime, _ = _runtime({"CLAPBACK_SWORD": {"015"}})
    # world changed, nobody fired an event

    output = _capture(runtime.update, SWEEP_INTERVAL + 0.1)

    assert_true(runtime.scene.quest_state.is_done(Q00), "the sweep still completed it")
    assert_true("sweep" in output, "the warning names the sweep")
    assert_true(Q00 in output, "the warning names what fired, so the hook is findable")
    assert_true("missing" in output, "the warning says what is wrong")


def test_sweep_only_runs_on_its_interval() -> None:
    runtime, _ = _runtime({"CLAPBACK_SWORD": {"015"}})

    runtime.update(SWEEP_INTERVAL / 3)
    assert_true(not runtime.scene.quest_state.is_done(Q00), "not swept yet")

    runtime.update(SWEEP_INTERVAL)
    assert_true(runtime.scene.quest_state.is_done(Q00), "swept once the interval passed")


def test_rewards_are_applied_once_on_completion() -> None:
    runtime, sink = _runtime({"CLAPBACK_SWORD": {"015"}})

    runtime.on_event("DialogPanel_closed")
    assert_eq(sink.calls, [("add_money", 50)], "Q00's reward paid out")

    # a second event must not pay again: the quest is already done
    runtime.on_event("DialogPanel_closed")
    assert_eq(sink.calls, [("add_money", 50)], "paid exactly once")


def test_no_quests_configured_is_a_no_op() -> None:
    scene = SimpleNamespace(
        game=SimpleNamespace(conf=SimpleNamespace(quests={})),
        quest_state=QuestState(),
        loaded_NPCs={}, loaded_maps={}, pending_map_states={},
        player=SimpleNamespace(items=[]),
    )
    runtime = QuestRuntime(scene)

    assert_true(not runtime.on_event("whatever"), "nothing to do, nothing reported")
    assert_eq(_capture(runtime.update, 99.0), "", "and the sweep stays quiet")


def test_quest_config_flattens_both_loaders() -> None:
    """Decision D4: desktop hands us Pydantic models, web hands us dicts."""
    # web shape: plain dicts, passed through untouched
    plain = {"Q_X": {"name": "n", "completion": "manual"}}
    assert_eq(quest_config(SimpleNamespace(quests=plain)), plain, "dicts pass through")

    # desktop shape: anything with model_dump gets flattened
    class FakeModel:
        def model_dump(self, mode: str = "python") -> dict[str, str]:
            return {"name": "n", "completion": "manual"}

    flattened = quest_config(SimpleNamespace(quests={"Q_X": FakeModel()}))
    assert_eq(flattened, {"Q_X": {"name": "n", "completion": "manual"}}, "models flattened")

    # a config with no quests section at all
    assert_eq(quest_config(SimpleNamespace()), {}, "missing section -> empty")
    assert_eq(quest_config(SimpleNamespace(quests=None)), {}, "None section -> empty")


def test_toast_for_a_finished_step() -> None:
    """Q-09: completing a step says so, in the quest colour."""
    runtime, _ = _runtime({"CLAPBACK_SWORD": {"015"}})
    runtime.on_event("DialogPanel_closed")

    texts = [t for t, _type in runtime.scene.toasts]
    done = [t for t in texts if "Ukończono" in t]
    assert_eq(len(done), 1, f"one completion toast, got {texts}")
    assert_true("[quest]" in done[0], "the quest name is tagged, not bare text")
    assert_true("[h3]" not in done[0], "a step is not shouted like a thread ending")


def test_toast_for_a_closed_thread_is_louder() -> None:
    """A chapter ending must not look like another tick on a list."""
    runtime, _ = _runtime(
        {
            "CLAPBACK_SWORD": {"015"},
            "BARMAN_ABSINTHRAYNER": {"012", "017"},
            "POTIONEER_PUZZLEMINT": {"014"},
            "HAMMER_HOAXHEART": {"009"},
        }
    )
    runtime.on_event("DialogPanel_closed")

    texts = [t for t, _type in runtime.scene.toasts]
    thread = [t for t in texts if "Wątek zamknięty" in t]
    assert_eq(len(thread), 1, f"exactly one thread-closed toast, got {texts}")
    assert_true("[h3]" in thread[0], "the thread ending is visually louder than a step")
    # SAMPLE's umbrella pays money + max_health + an item; all three must show,
    # because the label and the payout read the same list (the SSiS `break` bug)
    assert_true("[num]+100[/num] :golden_coin:" in thread[0], f"money in the label: {thread[0]}")
    assert_true("[num]+20[/num] max HP" in thread[0], f"max health in the label: {thread[0]}")
    assert_true("MERMAIDS_TEAR" in thread[0], f"item in the label: {thread[0]}")
    # the labels carry their own tags now; the toast must not wrap them again
    assert_true("[num][num]" not in thread[0], "no nested [num] markup")


def test_unlocked_thread_and_step_read_differently() -> None:
    """Calling a step 'a new thread' would simply be a lie to the player."""
    runtime, _ = _runtime({"CLAPBACK_SWORD": {"015"}})
    runtime.on_event("DialogPanel_closed")

    texts = [t for t, _type in runtime.scene.toasts]
    assert_true(any("Nowy wątek" in t for t in texts), f"the umbrella opened: {texts}")
    assert_true(any("Nowy cel" in t for t in texts), f"its first step is an objective: {texts}")


def test_quiet_sweep_says_nothing_to_the_player() -> None:
    runtime, _ = _runtime()
    runtime.update(SWEEP_INTERVAL + 0.1)
    assert_eq(runtime.scene.toasts, [], "nothing happened, nothing announced")


def main() -> None:
    tests = [
        test_event_completes_a_quest,
        test_sweep_is_quiet_when_events_did_the_work,
        test_sweep_catches_and_reports_a_missing_event,
        test_sweep_only_runs_on_its_interval,
        test_rewards_are_applied_once_on_completion,
        test_no_quests_configured_is_a_no_op,
        test_quest_config_flattens_both_loaders,
        test_toast_for_a_finished_step,
        test_toast_for_a_closed_thread_is_louder,
        test_unlocked_thread_and_step_read_differently,
        test_quiet_sweep_says_nothing_to_the_player,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} quest runtime tests passed.")


if __name__ == "__main__":
    main()
