#!/usr/bin/env python3
"""Unit tests for ui/panels/quest.py — the journal's logic (Q-08).

Run from the project root:
    .venv/bin/python tests/test_quest_panel.py

Drawing is checked by eye against the mock in section 6 of the design HTML; what
is pinned here is the behaviour underneath: which rows exist, what the filters
mean, and that a locked step stays visible.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
sys.path.insert(0, os.path.dirname(__file__))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from quest.entities import QuestState
from quest.graph import init_quests
from test_quest_entities import SAMPLE

Q00 = "Q00_S00_WHAT_IS_GOING_ON"
Q01_S00 = "Q01_S00_BREAK_THE_CURSE"
Q03_S00 = "Q03_S00_LEARN_ABOUT_CURSE"
Q03_S03 = "Q03_S03_HOW_TO_GET_THERE"


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def _panel(done: set[str] | None = None):  # type: ignore[no-untyped-def]
    """A QuestPanel over the real 8-quest graph, with stub scene + fonts."""
    pygame.init()
    pygame.display.set_mode((64, 64))
    from ui.panels.quest import QuestPanel

    defs = init_quests(SAMPLE)  # type: ignore[arg-type]
    state = QuestState()
    for key in done or ():
        state.mark_done(key)

    ctx = SimpleNamespace(
        visited=lambda node, npc=None: False,
        has_item=lambda key: False,
        item_count=lambda key: 0,
        quest_done=lambda key: state.is_done(key),
    )
    fonts = {size: pygame.font.Font(None, max(8, size)) for size in (8, 10, 14, 16, 24)}
    scene = SimpleNamespace(
        quest_state=state,
        quests=SimpleNamespace(defs=defs, ctx=ctx),
        game=SimpleNamespace(conf=SimpleNamespace(messages={}, items={}), fonts=fonts),
    )
    hud = SimpleNamespace(draw_text=lambda *a, **k: None)
    panel = QuestPanel.__new__(QuestPanel)
    # skip __init__: it builds a nine-patch that needs the real asset pipeline
    from ui.widget import Widget

    Widget.__init__(panel)
    panel.scene = scene
    panel.hud = hud
    panel.filter_idx = 0
    panel.selected = 0
    panel.collapsed = set()
    panel._rows = []
    return panel


def test_rows_nest_steps_under_their_thread() -> None:
    panel = _panel()
    panel.filter_idx = 2  # all
    panel._rebuild()

    keys = [r.key for r in panel._rows]
    assert_eq(len(keys), 8, f"every quest has a row: {keys}")

    # a step is never a top-level row; it sits under its thread
    idx_thread = keys.index(Q03_S00)
    assert_eq(keys[idx_thread + 1: idx_thread + 4],
              ["Q03_S01_WHO_HAS_MORE_KNOWLEDGE", "Q03_S02_WHERE_TO_FIND_THIS_PERSON", Q03_S03],
              "the thread's steps follow it, in order")
    assert_true(all(r.depth == 1 for r in panel._rows[idx_thread + 1: idx_thread + 4]), "steps are indented")
    assert_true(panel._rows[idx_thread].is_thread, "the umbrella is marked as a thread")


def test_locked_steps_stay_visible() -> None:
    """Settled in the design: the panel hides nothing.

    Pacing the story is the author's job — a step that gives too much away gets
    rewritten, it does not get hidden. The panel does not know the writer's intent
    and must not pretend to.
    """
    panel = _panel()
    panel.filter_idx = 2
    panel._rebuild()

    # nothing is done, so every step of the curse thread is locked...
    assert_eq(panel._state(Q00), "active", "the opening quest is available")
    assert_eq(panel._state(Q01_S00), "locked", "the curse thread is gated")
    # ...and yet they all have rows
    assert_true(Q03_S03 in [r.key for r in panel._rows], "a locked step is still listed")


def test_markers_follow_the_three_state_legend() -> None:
    panel = _panel(done={Q00})
    assert_eq(panel._state(Q00), "done", "✔")
    assert_eq(panel._state(Q01_S00), "active", "● — unlocked by Q00")
    assert_eq(panel._state(Q03_S00), "locked", "○ — still waiting on Q01_S01")


def test_filters() -> None:
    panel = _panel(done={Q00})

    panel.filter_idx = 0  # active
    panel._rebuild()
    keys = [r.key for r in panel._rows]
    assert_true(Q00 not in keys, "a finished quest is not something to work on")
    assert_true(Q01_S00 in keys, "the open thread is active")

    panel.filter_idx = 1  # done
    panel._rebuild()
    assert_eq([r.key for r in panel._rows], [Q00], "only what is finished")

    panel.filter_idx = 2  # all
    panel._rebuild()
    assert_eq(len(panel._rows), 8, "everything, locked included")


def test_filter_cycling_wraps_and_resets_selection() -> None:
    panel = _panel()
    panel.selected = 3

    panel.next_filter()
    assert_eq(panel.filter_idx, 1, "moved on")
    assert_eq(panel.selected, 0, "selection resets: row 3 of the old list means nothing here")

    panel.next_filter()
    panel.next_filter()
    assert_eq(panel.filter_idx, 0, "wraps around")

    panel.prev_filter()
    assert_eq(panel.filter_idx, 2, "wraps backwards too")


def test_collapsing_a_thread_hides_its_steps() -> None:
    panel = _panel()
    panel.filter_idx = 2
    panel._rebuild()
    before = len(panel._rows)

    panel.selected = [r.key for r in panel._rows].index(Q03_S00)
    panel.toggle_expand()
    assert_eq(len(panel._rows), before - 3, "the thread's three steps folded away")
    assert_true(Q03_S00 in [r.key for r in panel._rows], "the thread itself stays")

    panel.toggle_expand()
    assert_eq(len(panel._rows), before, "and unfold again")


def test_collapsing_a_step_does_nothing() -> None:
    panel = _panel()
    panel.filter_idx = 2
    panel._rebuild()
    panel.selected = [r.key for r in panel._rows].index(Q03_S03)
    before = len(panel._rows)

    panel.toggle_expand()

    assert_eq(len(panel._rows), before, "a leaf has nothing to fold")


def test_selection_wraps_and_survives_an_empty_list() -> None:
    panel = _panel()
    panel.filter_idx = 2
    panel._rebuild()

    panel.selected = len(panel._rows) - 1
    panel.select_next()
    assert_eq(panel.selected, 0, "wraps to the top")
    panel.select_prev()
    assert_eq(panel.selected, len(panel._rows) - 1, "and back to the bottom")

    # the "done" filter is empty on a fresh game: navigation must not explode
    panel.filter_idx = 1
    panel._rebuild()
    assert_eq(panel._rows, [], "nothing finished yet")
    panel.select_next()
    panel.select_prev()
    panel.toggle_expand()
    assert_true(panel._current_row() is None, "no row, no crash")


def test_titles_are_truncated_to_their_column() -> None:
    """A long title must not run through the divider into the details pane."""
    panel = _panel()
    long_title = "Znajdź kogoś kto wie coś więcej o klątwach i innych nieszczęściach"

    cut = panel._truncate(long_title, 200, 14)

    assert_true(cut.endswith("..."), f"ellipsised: {cut!r}")
    assert_true(len(cut) < len(long_title), "actually shorter")
    assert_true(panel._font(14).size(cut)[0] <= 200, "and it fits the room given")
    # a title that already fits is left alone
    assert_eq(panel._truncate("Krótki", 200, 14), "Krótki", "short titles untouched")


def main() -> None:
    tests = [
        test_rows_nest_steps_under_their_thread,
        test_locked_steps_stay_visible,
        test_markers_follow_the_three_state_legend,
        test_filters,
        test_filter_cycling_wraps_and_resets_selection,
        test_collapsing_a_thread_hides_its_steps,
        test_collapsing_a_step_does_nothing,
        test_selection_wraps_and_survives_an_empty_list,
        test_titles_are_truncated_to_their_column,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} quest panel tests passed.")


if __name__ == "__main__":
    main()
