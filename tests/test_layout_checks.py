#!/usr/bin/env python3
"""Unit tests for the UI layout self-checks (A03).

Run from the project root:
    .venv/bin/python tests/test_layout_checks.py

What is pinned here is the contract the whole mechanism rests on: content that does
not fit its box is reported, content that legitimately scrolls is NOT, the registry
can be cleared, and a repeat offender is only logged once (these checks sit on the
draw path, so without deduplication the log would grow by one line per frame).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
sys.path.insert(0, os.path.dirname(__file__))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

pygame.init()
pygame.display.set_mode((320, 240))

from ui import layout
from ui.widgets.label import Label
from ui.widgets.rich_text import RichText

# One very long unbreakable word: no word wrap can make this fit, which is exactly
# what an h-overflow is. Ordinary long prose just wraps and is not a violation.
LONG_WORD = "Absyntnentokontrfaktycznieniepodwazalnymikrozarzadzanie"
LONG_PROSE = " ".join(["slowo"] * 200)


def assert_eq(a: object, b: object, msg: str = "") -> None:
    if a != b:
        raise AssertionError(f"{msg}\n  expected: {b!r}\n  actual:   {a!r}")


def assert_true(cond: bool, msg: str = "") -> None:
    if not cond:
        raise AssertionError(msg)


def _kinds() -> list[str]:
    """Violation kinds currently in the registry (order preserved)."""
    return [v.split("]", 1)[1].split(" in ", 1)[0].strip() for v in layout.violations()]


def _rich(text: str, w: int, h: int, *, show_scrollbar: bool, name: str = "probe") -> RichText:
    return RichText(text, (0, 0, w, h), {}, base_size=16,
                    show_scrollbar=show_scrollbar, name=name)


def _draw(widget: RichText) -> None:
    """Drawing is what publishes a finding - measurement-only widgets stay silent."""
    widget.draw(pygame.Surface((320, 240), pygame.SRCALPHA))


#############################################################################################################
def test_an_unbreakable_word_wider_than_the_box_is_reported() -> None:
    layout.reset_violations()
    _draw(_rich(LONG_WORD, 80, 400, show_scrollbar=False))
    assert_true("h-overflow" in _kinds(), f"expected h-overflow, got {layout.violations()}")


def test_too_much_text_without_a_scrollbar_is_reported() -> None:
    layout.reset_violations()
    _draw(_rich(LONG_PROSE, 200, 40, show_scrollbar=False))
    assert_true("v-overflow" in _kinds(), f"expected v-overflow, got {layout.violations()}")


def test_the_same_text_is_fine_when_it_can_scroll() -> None:
    """A scrollbar is the designed answer to more content than viewport, not a bug."""
    layout.reset_violations()
    _draw(_rich(LONG_PROSE, 200, 40, show_scrollbar=True))
    assert_eq(layout.violations(), [], "scrollable overflow must not be reported")


def test_text_that_fits_reports_nothing() -> None:
    layout.reset_violations()
    _draw(_rich("krotki tekst", 400, 200, show_scrollbar=False))
    assert_eq(layout.violations(), [], "content that fits must be silent")


def test_a_widget_that_is_never_drawn_stays_silent() -> None:
    """Measure-only RichText (render_static callers, the quest panel's binary search
    over how much text fits) must not raise alarms about intermediate candidates."""
    layout.reset_violations()
    _rich(LONG_WORD, 80, 400, show_scrollbar=False)  # baked, never drawn
    assert_eq(layout.violations(), [], "an unbaked/undrawn widget must not report")


def test_reset_clears_the_registry() -> None:
    layout.reset_violations()
    _draw(_rich(LONG_WORD, 80, 400, show_scrollbar=False))
    assert_true(layout.violations() != [], "precondition: something was reported")
    layout.reset_violations()
    assert_eq(layout.violations(), [], "reset_violations must empty the registry")


def test_the_same_violation_is_logged_once_not_once_per_frame() -> None:
    layout.reset_violations()
    widget = _rich(LONG_WORD, 80, 400, show_scrollbar=False, name="repeat")
    for _ in range(30):
        _draw(widget)
    assert_eq(len(layout.violations()), 1, "deduplication by (widget, kind) failed")


def test_two_different_widgets_are_reported_separately() -> None:
    layout.reset_violations()
    _draw(_rich(LONG_WORD, 80, 400, show_scrollbar=False, name="first"))
    _draw(_rich(LONG_WORD, 80, 400, show_scrollbar=False, name="second"))
    assert_eq(len(layout.violations()), 2, "deduplication must be per widget, not global")


#############################################################################################################
def test_check_inside_reports_content_sticking_out_of_a_panel() -> None:
    layout.reset_violations()
    panel = pygame.Rect(0, 0, 100, 100)
    ok = layout.check_inside("Panel(x)", pygame.Rect(50, 50, 100, 20), panel)
    assert_eq(ok, False, "check_inside must return False for content that sticks out")
    assert_true("outside-panel" in _kinds(), f"expected outside-panel, got {layout.violations()}")


def test_check_inside_is_silent_for_contained_content() -> None:
    layout.reset_violations()
    panel = pygame.Rect(0, 0, 100, 100)
    ok = layout.check_inside("Panel(x)", pygame.Rect(10, 10, 50, 20), panel)
    assert_eq(ok, True, "check_inside must return True for contained content")
    assert_eq(layout.violations(), [], "contained content must be silent")


#############################################################################################################
def test_a_label_squeezed_below_its_text_size_is_reported() -> None:
    """Label sizes itself to its text, so this only fires when a caller has forced
    a smaller rect afterwards - and then the excess really is cut off, not wrapped."""
    layout.reset_violations()
    label = Label("tekst ktory sie nie zmiesci", name="squeezed")
    label.rect.size = (10, 10)
    label.render()
    assert_true("clipped" in _kinds(), f"expected clipped, got {layout.violations()}")


def test_a_label_at_its_natural_size_reports_nothing() -> None:
    layout.reset_violations()
    Label("tekst", name="natural").render()
    assert_eq(layout.violations(), [], "a self-sized label must be silent")


def main() -> None:
    tests = [
        test_an_unbreakable_word_wider_than_the_box_is_reported,
        test_too_much_text_without_a_scrollbar_is_reported,
        test_the_same_text_is_fine_when_it_can_scroll,
        test_text_that_fits_reports_nothing,
        test_a_widget_that_is_never_drawn_stays_silent,
        test_reset_clears_the_registry,
        test_the_same_violation_is_logged_once_not_once_per_frame,
        test_two_different_widgets_are_reported_separately,
        test_check_inside_reports_content_sticking_out_of_a_panel,
        test_check_inside_is_silent_for_contained_content,
        test_a_label_squeezed_below_its_text_size_is_reported,
        test_a_label_at_its_natural_size_reports_nothing,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} layout self-check tests passed.")
    layout.reset_violations()


if __name__ == "__main__":
    main()
