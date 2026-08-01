#!/usr/bin/env python3
"""Unit tests for the asset-driven bar widget (U01).

Run from the project root:
    .venv/bin/python tests/test_bar_asset.py

What is pinned here is the contract that makes ``scrollbar.png`` the *source* of the
scrollbar look rather than a reference picture:

- the shipped sprite reproduces itself pixel for pixel when rendered in its own state
  (same scale, same thumb) - so a repaint in Aseprite really is what you see in game;
- a colour that is not a ``theme`` token is a hard, readable load error (the sprite and
  the palette must not drift apart silently);
- the frame/track roles survive a colour swap, and the fill role takes the requested
  colour - which is what lets one sprite serve the red→green sentiment bar.
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

from settings import HUD_DIR, load_image
from ui import theme
from ui.widgets import bar

SPRITE = HUD_DIR / "scrollbar.png"


def assert_eq(a: object, b: object, msg: str = "") -> None:
    if a != b:
        raise AssertionError(f"{msg}\n  expected: {b!r}\n  actual:   {a!r}")


def assert_true(cond: bool, msg: str = "") -> None:
    if not cond:
        raise AssertionError(msg)


def _sprite() -> pygame.Surface:
    return load_image(SPRITE).convert_alpha()


def _pixels(surface: pygame.Surface) -> list[tuple[int, ...]]:
    return [tuple(surface.get_at((x, y))) for y in range(surface.get_height())
            for x in range(surface.get_width())]


def _trimmed(surface: pygame.Surface) -> pygame.Surface:
    """The sprite without its fully transparent leading/trailing rows.

    The main axis is the stretchable one, so those rows are canvas padding, not art -
    the model drops them and a drawn bar spans its whole rect.
    """
    rows = [y for y in range(surface.get_height())
            if any(surface.get_at((x, y))[3] for x in range(surface.get_width()))]
    return surface.subsurface((0, rows[0], surface.get_width(), rows[-1] - rows[0] + 1)).copy()


def _draw(width: int = 32, height: int = 96, **kwargs: object) -> pygame.Surface:
    """Draw a vertical bar filling a transparent canvas of exactly its own size."""
    canvas = pygame.Surface((width, height), pygame.SRCALPHA)
    bar.draw_scrollbar(canvas, (0, 0, width, height), **kwargs)  # type: ignore[arg-type]
    return canvas


#############################################################################################################
def test_the_sprite_is_parsed_into_caps_and_a_stretchable_body() -> None:
    """The 8x16 sprite: 2 transparent rows trimmed, then cap + groove cap, body, mirror."""
    model = bar._get_model()
    assert_eq(model.cross, _sprite().get_width(), "native cross must be the sprite width")
    assert_true(len(model.head) > 0 and len(model.tail) > 0, "the sprite must have both caps")
    assert_true(len(model.body.groove) > len(model.head[0].groove),
                "the body row must be the one with the widest groove")
    assert_true(bar.DARK in model.fill_pat[len(model.body.groove)],
                "the filled body row must carry a dark bevel column read off the sprite")
    assert_true(bar.LIGHT in model.fill_pat[len(model.body.groove)],
                "the filled body row must carry a light bevel column read off the sprite")


def test_the_sprite_reproduces_itself_pixel_for_pixel() -> None:
    """The whole point of U01: what is painted in the asset is what the game draws.

    The shipped sprite shows a thumb parked at the top filling 7 of the 10 groove rows,
    so rendering that exact state at native scale must give back the sprite itself.
    """
    art = _trimmed(_sprite())
    # native scale: cross = sprite width x _MIN_SCALE would double it, so ask for the
    # scale-1 model directly and compare the un-scaled native surface.
    model = bar._get_model()
    groove_rows = sum(1 for row in model.head + model.tail if row.groove) + \
        (art.get_height() - len(model.head) - len(model.tail))
    native = bar._native(
        model, art.get_height(), 0, groove_rows - 3,
        bar._palette(theme.GOLD, (theme.WARN, theme.TITLE)),
    )
    assert_eq(_pixels(native), _pixels(art),
              "rendering the sprite's own state must give back the sprite")


def test_an_off_palette_pixel_is_a_readable_load_error() -> None:
    """Acceptance criterion 1: a colour outside the palette fails loudly, with the pixel."""
    broken = _sprite().copy()
    broken.set_at((3, 5), (255, 0, 255, 255))     # magenta - not a theme token
    try:
        bar._parse(broken, str(SPRITE))
    except ValueError as exc:
        assert_true("(3, 5)" in str(exc), f"the message must name the pixel: {exc}")
        assert_true("#FF00FF" in str(exc), f"the message must name the colour: {exc}")
        return
    raise AssertionError("an off-palette pixel must raise ValueError")


def test_repainting_the_frame_with_another_token_changes_the_drawn_bar() -> None:
    """Acceptance criterion 1, second half: a frame pixel repainted in another palette
    token is visible in the game (here: the drawn bar stops matching the shipped one)."""
    before = _draw(frac_visible=0.5, frac_pos=0.0)
    original = bar._model
    try:
        repainted = _sprite().copy()
        for y in range(repainted.get_height()):                 # whole left frame column
            if repainted.get_at((1, y))[3]:
                repainted.set_at((1, y), (*theme.RULE, 255))
        bar._model = bar._parse(repainted, str(SPRITE))
        after = _draw(frac_visible=0.5, frac_pos=0.0)
    finally:
        bar._model = original
    assert_true(_pixels(before) != _pixels(after), "an edited sprite must change the drawn bar")


def test_the_fill_colour_is_swapped_and_the_frame_is_not() -> None:
    """Colour swap: the fill role takes the requested colour, chrome roles stay tokens."""
    gold = _draw(frac_visible=1.0, frac_pos=0.0)
    cyan = _draw(frac_visible=1.0, frac_pos=0.0, fill=theme.ACCENT_CYAN, bevel=None)
    present = {tuple(px[:3]) for px in _pixels(gold) if px[3]}
    swapped = {tuple(px[:3]) for px in _pixels(cyan) if px[3]}
    assert_true(theme.GOLD in present, "the default bar must use GOLD as its fill")
    assert_true(theme.GOLD not in swapped, "fill=ACCENT_CYAN must replace every GOLD pixel")
    assert_true(theme.ACCENT_CYAN in swapped, "the requested fill colour must appear")
    assert_true(theme.INK in present and theme.INK in swapped, "the frame stays INK either way")


def test_the_sentiment_bar_works_across_the_whole_range() -> None:
    """Acceptance criterion 3: a dynamic colour + derived bevel over the full 0-100 sweep."""
    canvas = pygame.Surface((200, 56), pygame.SRCALPHA)
    seen: set[int] = set()
    for value in range(0, 101):
        fraction = value / 100
        colour = (int(255 * (1 - fraction)), int(255 * fraction), 60)
        canvas.fill((0, 0, 0, 0))
        bar.draw_progress(canvas, (0, 8, 180, 32), fraction, fill=colour)
        seen.add(sum(1 for px in _pixels(canvas) if px[:3] == colour and px[3]))
    assert_true(len(seen) > 10, f"the fill length must follow the fraction, got {len(seen)} lengths")


def test_a_horizontal_bar_is_the_transposed_vertical_one() -> None:
    """The sprite is drawn vertically; horizontal bars reuse it via flip+rotate."""
    vertical = _draw(frac_visible=0.4, frac_pos=0.5)
    canvas = pygame.Surface((96, 32), pygame.SRCALPHA)
    bar.draw_scrollbar(canvas, (0, 0, 96, 32), frac_visible=0.4, frac_pos=0.5, vertical=False)
    rotated = pygame.transform.rotate(pygame.transform.flip(vertical, True, False), 90)
    assert_eq(_pixels(canvas), _pixels(rotated), "horizontal must be the transposed vertical bar")


def test_public_geometry_is_unchanged() -> None:
    """Panels pass multiples of 8 (min 32 = 4x native) as the cross size; the bar fills it."""
    for cross, expected_k in ((32, 4), (40, 5), (48, 6), (64, 8)):
        canvas = pygame.Surface((cross, 120), pygame.SRCALPHA)
        bar.draw_scrollbar(canvas, (0, 0, cross, 120), frac_visible=0.5, frac_pos=0.0)
        painted = [x for x in range(cross)
                   for y in range(120) if canvas.get_at((x, y))[3]]
        assert_true(bool(painted), f"a {cross}px bar must draw something")
        model = bar._get_model()
        k = max(bar._MIN_SCALE, round(cross / model.cross))
        assert_eq(k, expected_k, f"scale for cross={cross}")
        # the drawn capsule is centred on the cross axis
        left, right = min(painted), max(painted)
        assert_eq(left, cross - 1 - right, f"the capsule must be centred for cross={cross}")


def main() -> None:
    tests = [
        test_the_sprite_is_parsed_into_caps_and_a_stretchable_body,
        test_the_sprite_reproduces_itself_pixel_for_pixel,
        test_an_off_palette_pixel_is_a_readable_load_error,
        test_repainting_the_frame_with_another_token_changes_the_drawn_bar,
        test_the_fill_colour_is_swapped_and_the_frame_is_not,
        test_the_sentiment_bar_works_across_the_whole_range,
        test_a_horizontal_bar_is_the_transposed_vertical_one,
        test_public_geometry_is_unchanged,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} bar asset tests passed.")


if __name__ == "__main__":
    main()
