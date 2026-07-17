#!/usr/bin/env python3
"""Unit tests for the toast queue - scene.add_notification (Q-12).

Run from the project root:
    .venv/bin/python tests/test_notifications.py

Three toasts raised in one frame (a quest closing opens a thread and its first
step) used to share one NOTIFICATION_DURATION window and land on top of each
other, which is ~5 s to read all three. They queue now. What is pinned here is
that queueing costs a toast nothing: its lifetime and its slide-in both run from
the moment it appears, not from the moment it was raised.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from scene import Scene
from settings import NOTIFICATION_DURATION, NOTIFICATION_STAGGER


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


class FakeScene:
    """Just the notification machinery, borrowed from the real Scene.

    Building a Scene needs maps, sprites and a display; the queue needs a clock
    and a list. Binding the real methods keeps the test on the shipping code
    without dragging the world in.
    """

    def __init__(self) -> None:
        self.notifications: list[object] = []
        self.game = SimpleNamespace(time_elapsed=0.0)

    add_notification = Scene.add_notification
    visible_notifications = Scene.visible_notifications
    remove_old_notifications = Scene.remove_old_notifications

    def tick(self, seconds: float) -> None:
        self.game.time_elapsed += seconds
        self.remove_old_notifications()


def test_a_lone_toast_is_not_delayed() -> None:
    """Nothing to queue behind: the common case must stay instant."""
    scene = FakeScene()
    scene.add_notification("sam jeden")

    assert_eq(len(scene.visible_notifications()), 1, "shown right away")
    assert_eq(scene.notifications[0].show_time, 0.0, "no head start to wait out")  # type: ignore[attr-defined]


def test_toasts_raised_in_one_frame_appear_one_at_a_time() -> None:
    """The reported bug: three at once, ~5 s, unreadable."""
    scene = FakeScene()
    for text in ("ukończono", "nowy wątek", "nowy cel"):
        scene.add_notification(text)

    assert_eq(len(scene.notifications), 3, "all three are queued, none dropped")
    assert_eq(len(scene.visible_notifications()), 1, "only the first is on screen")

    scene.tick(NOTIFICATION_STAGGER + 0.01)
    assert_eq(len(scene.visible_notifications()), 2, "the second takes its turn")

    scene.tick(NOTIFICATION_STAGGER)
    assert_eq(len(scene.visible_notifications()), 3, "and the third")


def test_a_queued_toast_still_gets_the_full_duration() -> None:
    """The point of show_time. Expiring on create_time would rob the last one.

    With three toasts and a 1.2 s stagger, the third waits 2.4 s. If its clock
    started when it was raised it would get 2.6 s of the 5 s - less time than
    the first, for no reason the player could see.
    """
    scene = FakeScene()
    for text in ("pierwszy", "drugi", "trzeci"):
        scene.add_notification(text)
    third = scene.notifications[2]

    # walk to the moment it appears, then to just before its window closes
    scene.tick(2 * NOTIFICATION_STAGGER)
    assert_true(third in scene.visible_notifications(), "its turn came")

    scene.tick(NOTIFICATION_DURATION - 0.01)
    assert_true(third in scene.visible_notifications(), "still readable")

    scene.tick(0.02)
    assert_true(third not in scene.notifications, "and then it goes")


def test_the_sweep_counts_from_show_time_not_create_time() -> None:
    """A toast's window has to start when the player can see it.

    The second toast is raised at 0 but appears at +STAGGER, so a create_time
    sweep would bin it at DURATION while it still had STAGGER seconds of reading
    left - cutting it short by exactly as long as it politely waited.
    """
    scene = FakeScene()
    scene.add_notification("pierwszy")
    scene.add_notification("drugi")
    second = scene.notifications[1]

    # past a create_time-based expiry, short of a show_time-based one
    scene.tick(NOTIFICATION_DURATION + NOTIFICATION_STAGGER / 2)

    assert_true(second in scene.notifications, "not swept on the clock it never ran on")
    assert_true(second in scene.visible_notifications(), "and still readable")

    scene.tick(NOTIFICATION_STAGGER)
    assert_true(second not in scene.notifications, "its own window does close, though")


def test_a_later_toast_does_not_wait_for_a_finished_queue() -> None:
    """The head start is against what is still on screen, not against history."""
    scene = FakeScene()
    scene.add_notification("dawny")
    scene.tick(NOTIFICATION_DURATION + 1.0)
    assert_eq(scene.notifications, [], "the old one has expired")

    scene.add_notification("nowy")
    assert_eq(len(scene.visible_notifications()), 1, "shown immediately, nothing to queue behind")


def test_toast_padding_clears_the_frame_so_the_last_line_fits() -> None:
    """The reported bug: a tall toast's last line sat under the bottom frame.

    The box is sized to the text height plus ``_NOTIFICATION_PAD_Y`` each side, but
    the nine-patch frame art eats into that padding. If the padding is thinner than
    the frame, the top and bottom lines render under the border. Measured off the
    real asset so it tracks the art, not a guessed number.
    """
    import pygame

    from ui import theme
    from ui.panels.hud import _NOTIFICATION_PAD_Y

    pygame.init()
    pygame.display.set_mode((64, 64))
    box = theme.nine_patch("nine_patch_04c.png", 240, 160, border=3)
    w, h = box.get_size()
    mid_x = w // 2
    interior = tuple(box.get_at((mid_x, h // 2))[:3])

    top_frame = next(y for y in range(h) if tuple(box.get_at((mid_x, y))[:3]) == interior)
    bottom_frame = next(dy for dy in range(h) if tuple(box.get_at((mid_x, h - 1 - dy))[:3]) == interior)

    assert_true(
        _NOTIFICATION_PAD_Y >= top_frame,
        f"pad_y {_NOTIFICATION_PAD_Y} must clear the {top_frame}px top frame",
    )
    assert_true(
        _NOTIFICATION_PAD_Y >= bottom_frame,
        f"pad_y {_NOTIFICATION_PAD_Y} must clear the {bottom_frame}px bottom frame",
    )


def main() -> None:
    tests = [
        test_a_lone_toast_is_not_delayed,
        test_toasts_raised_in_one_frame_appear_one_at_a_time,
        test_a_queued_toast_still_gets_the_full_duration,
        test_the_sweep_counts_from_show_time_not_create_time,
        test_a_later_toast_does_not_wait_for_a_finished_queue,
        test_toast_padding_clears_the_frame_so_the_last_line_fits,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} notification tests passed.")


if __name__ == "__main__":
    main()
