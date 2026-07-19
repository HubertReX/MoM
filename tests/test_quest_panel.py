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
    # the *real* game font, not pygame's default: MoM renders in a pixel font that
    # is markedly wider, and every width decision in this panel (truncation, the
    # column contract) is meaningless when measured against something else
    from settings import MAIN_FONT

    fonts = {size: pygame.font.Font(MAIN_FONT, size) for size in (8, 10, 14, 16, 24)}
    scene = SimpleNamespace(
        quest_state=state,
        quests=SimpleNamespace(defs=defs, ctx=ctx),
        game=SimpleNamespace(conf=SimpleNamespace(messages={}, items={}), fonts=fonts),
        # RichText resolves its own font through theme.get_font, but it still wants
        # somewhere to look icons up; the titles under test carry none
        items_sheet={},
    )
    hud = SimpleNamespace(draw_text=lambda *a, **k: None, icons={})
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
    panel._rich_cache = {}
    from ui.widgets.scroll_view import ScrollView
    panel._details_scroll = ScrollView()
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


_WHITE = (255, 255, 255)


def _relative_luminance(colour: tuple[int, int, int]) -> float:
    return sum(w * c / 255 for w, c in zip((0.2126, 0.7152, 0.0722), colour))


def _contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = _relative_luminance(a) + 0.05, _relative_luminance(b) + 0.05
    return max(la, lb) / min(la, lb)


def test_the_empty_progress_track_is_visible_on_the_panel() -> None:
    """A 0/N bar must still read as a bar - every umbrella starts empty.

    An all_subquests thread opens at 0/N, so if the empty track sinks into the
    panel, a fresh thread looks like it has no progress bar at all (reported for
    Q03_S00). At (51,51,51) the track sat at 1.68:1 against the olive panel, below
    the 3:1 floor for UI elements; this pins it above.
    """
    import pygame

    from ui import theme
    from ui.panels.quest import PANEL_H, PANEL_W, PANEL_X, _RIGHT_X

    pygame.init()
    pygame.display.set_mode((64, 64))
    bg = theme.nine_patch("nine_patch_04.png", PANEL_W, PANEL_H)
    # where the bar actually sits: inside the right pane, mid panel
    panel_here = bg.get_at((_RIGHT_X - PANEL_X + 100, 300))[:3]

    # The old quest-local _BAR_BG track token was folded into the theme palette as
    # theme.BAR_BG (== INK, 17,17,17) in the 2026-07-19 refactor. That dark, chunky
    # frame is what makes an empty (0/N) bar still read as a bar — this pins its
    # contrast against the olive panel above the 3:1 UI floor.
    ratio = _contrast(theme.BAR_BG, panel_here)
    assert_true(ratio >= 3.0, f"empty track vs panel is {ratio:.2f}:1, needs >= 3:1")


def test_the_reference_step_title_fits_without_truncation() -> None:
    """The agreed contract for how wide the thread column has to be.

    "Gdzie znaleźć tę osobę?" must render whole. Authors keep titles short from
    their side; this keeps the column from being narrowed from ours. Measured at
    the real x a step title starts from, in the real font, on the path the panel
    really draws titles with.
    """
    from ui.panels.quest import _LEFT_X, _SPLIT_X, _STEP_INDENT

    panel = _panel()
    title = "Gdzie znaleźć tę osobę?"
    step_x = _LEFT_X + _STEP_INDENT + 24
    room = _SPLIT_X - 16 - step_x

    assert_eq(panel._fit_line(title, room, 14, _WHITE), title, "the reference title is not cut")


def test_titles_are_truncated_to_their_column() -> None:
    """A long title must not run through the divider into the details pane."""
    panel = _panel()
    long_title = "Znajdź kogoś kto wie coś więcej o klątwach i innych nieszczęściach"

    cut = panel._fit_line(long_title, 200, 14, _WHITE)

    assert_true(cut.endswith("..."), f"ellipsised: {cut!r}")
    assert_true(len(cut) < len(long_title), "actually shorter")
    assert_true(panel._build_rich(cut, 10_000, 14, _WHITE).content_width <= 200, "fits the room")
    # a title that already fits is left alone
    assert_eq(panel._fit_line("Krótki", 200, 14, _WHITE), "Krótki", "short titles untouched")


def test_a_tagged_title_is_cut_without_breaking_its_markup() -> None:
    """The reason titles no longer go through the plain-text truncate.

    An author writes `[char]Kowal Kłamca[/char]`; cutting the rendered string
    would either strand an opening tag or leave the ellipsis outside the styling.
    The tag survives, and the panel prints a name rather than a tag.
    """
    panel = _panel()
    tagged = "[char]Kowal Kłamca Zamaszysty[/char] kuje i kłamie"

    cut = panel._fit_line(tagged, 200, 14, _WHITE)

    assert_true("[char]" in cut, f"opening tag kept: {cut!r}")
    assert_true(cut.endswith("[/char]"), f"and closed again: {cut!r}")
    assert_true("..." in cut, "the ellipsis sits inside the styling")
    # what matters in the end: the drawn line fits, tags costing nothing
    assert_true(panel._build_rich(cut, 10_000, 14, _WHITE).content_width <= 200, "fits the room")


def test_the_result_section_is_gated_on_finishing() -> None:
    """WYNIK is the answer, so showing it early would spoil the step that earns it.

    Q-12: the `**Sukces**:` prose reaches the player here and in the completion
    toast; before that it was imported and localized and shown nowhere.
    """
    panel = _panel(done={Q00})
    panel.filter_idx = 2
    panel._rebuild()

    assert_true(panel._done(Q00), "the opening quest is finished")
    assert_true(not panel._done(Q01_S00), "the curse thread is not")

    drawn: list[str] = []
    panel._label = lambda surface, text, pos: drawn.append(text)  # type: ignore[assignment]
    panel._draw_result = lambda *a, **k: drawn.append("RESULT-BODY") or 0  # type: ignore[assignment]

    surface = pygame.Surface((1280, 720))
    panel.selected = [r.key for r in panel._rows].index(Q00)
    panel._draw_details(surface)
    assert_true("RESULT-BODY" in drawn, "a finished quest shows its outcome")

    drawn.clear()
    panel.selected = [r.key for r in panel._rows].index(Q01_S00)
    panel._draw_details(surface)
    assert_true("RESULT-BODY" not in drawn, "an unfinished one keeps its ending to itself")


def test_a_tagged_title_renders_as_text_not_markup() -> None:
    """`draw_text` would print "[char]Kowal[/char]" literally - the bug this fixes."""
    panel = _panel()

    surface = panel._rich_line("[char]Kowal[/char]", 400, 14, _WHITE)
    plain = panel._rich_line("Kowal", 400, 14, _WHITE)

    # the tagged one is recoloured, not longer: a literal tag would be far wider
    assert_eq(surface.get_width(), plain.get_width(), "tags take no room, they style")


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
        test_the_empty_progress_track_is_visible_on_the_panel,
        test_the_reference_step_title_fits_without_truncation,
        test_titles_are_truncated_to_their_column,
        test_a_tagged_title_is_cut_without_breaking_its_markup,
        test_a_tagged_title_renders_as_text_not_markup,
        test_the_result_section_is_gated_on_finishing,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} quest panel tests passed.")


if __name__ == "__main__":
    main()
