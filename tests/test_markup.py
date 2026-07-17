#!/usr/bin/env python3
"""Unit tests for ui/text/markup.py and RichText's static render (Q-12).

Run from the project root:
    .venv/bin/python tests/test_markup.py

This parser is shared by every dialog, item and quest in the game, so a change
here can repaint text nobody was looking at. The `[/]` shorthand is the reason
this file exists; the emoji test is here because adding its branch to _TOKEN_RE
would have shifted the positional groups the parser used to read.

The last test counts pixels rather than reading strings. It has to: icons were
being dropped from every reward chip and every toast, and no assertion about the
markup *string* could ever have seen it.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from ui.text.markup import parse, strip_tags


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def _styled(markup: str) -> list[tuple[str, object]]:
    """``[(text, colour), ...]`` - the parse result, minus the noise."""
    return [(t.value, t.style.color) for t in parse(markup) if t.kind == "text"]


def test_bare_closer_matches_the_named_one() -> None:
    """`[char]Kowal[/]` is what an author reaches for; it used to print `[/]`."""
    assert_eq(_styled("[char]Kowal[/]"), _styled("[char]Kowal[/char]"), "same styling")
    assert_true("[/]" not in "".join(t.value for t in parse("[char]Kowal[/]")), "not literal text")


def test_bare_closer_pops_the_innermost_tag() -> None:
    """`[h3][char]X[/][/]` reads left to right, naming nothing twice."""
    nested = parse("[h3][char]X[/]Y[/]Z")
    text = {t.value: t.style for t in nested if t.kind == "text"}

    assert_eq(text["X"].color, parse("[char]X[/char]")[0].style.color, "X is char-coloured")
    assert_true(text["Y"].size > text["Z"].size, "Y is still inside h3, Z is outside it")
    assert_eq(text["Z"].size, parse("Z")[0].style.size, "the second [/] closed h3")


def test_the_two_closers_interleave() -> None:
    """Mixing them is legal; `[/]` just means "whatever is innermost"."""
    assert_eq(_styled("[h3][char]X[/][/h3]"), _styled("[h3][char]X[/char][/h3]"), "bare then named")
    assert_eq(_styled("[h3][char]X[/char][/]"), _styled("[h3][char]X[/char][/h3]"), "named then bare")


def test_an_unmatched_closer_warns_instead_of_raising() -> None:
    """A typo in a dialog is author error, and must read as one.

    Found while adding `[/]`: this path was broken *before* it existed. The
    warning goes through `rich.print`, which parsed the `[/char]` inside our own
    error text as *its* markup and raised MarkupError - so a stray closing tag
    anywhere in the vault blew up inside the handler written to report it.
    Both spellings are covered because both messages had the same bug.
    """
    for markup, label in (("X[/]Y", "bare"), ("X[/char]Y", "named")):
        tokens = parse(markup)  # must not raise
        assert_eq(
            "".join(t.value for t in tokens if t.kind == "text"), "XY", f"text survives ({label})"
        )


def test_strip_tags_removes_the_bare_closer() -> None:
    """strip_tags measures plain text; a stray `[/]` would inflate every width."""
    assert_eq(strip_tags("[char]Kowal[/] kuje"), "Kowal kuje", "gone")
    assert_eq(strip_tags("[num]+10[/num] max HP"), "+10 max HP", "named closer still gone")


def test_emoji_still_parses() -> None:
    """Regression on the group shift, not on emoji.

    The parser read `m.group(4)` for the emoji name. Adding the `[/]` branch
    ahead of it moves the emoji to group 5, and every `:name:` in the game would
    quietly start rendering as literal text. Named groups is the fix; this is the
    guard. `heart` is used because it is really in EMOTE_SHEET_DEFINITION - a
    name that is not would make this test pass for the wrong reason.
    """
    tokens = parse("zdrowie :heart: rośnie")

    images = [t for t in tokens if t.kind == "image"]
    assert_eq([t.value for t in images], ["heart"], "the heart is an image, not text")
    assert_true(":heart:" not in "".join(t.value for t in tokens if t.kind == "text"),
                "and its marker is consumed")


def test_an_unknown_emoji_stays_literal() -> None:
    tokens = parse("a :not_an_emoji: b")
    assert_true(":not_an_emoji:" in "".join(t.value for t in tokens if t.kind == "text"),
                "unknown names are left alone rather than eaten")


def test_link_argument_survives() -> None:
    """`[link URL]` carries an argument - the other group the shift would break."""
    tokens = parse("[link https://example.com]klik[/link]")
    linked = [t for t in tokens if t.kind == "text" and t.style.link]
    assert_eq([t.style.link for t in linked], ["https://example.com"], "URL parsed from the tag")


def test_extra_emojis_opens_the_item_sheet() -> None:
    """`:golden_coin:` is an item sprite, and the emote sheet is speech bubbles.

    Opt-in per call site on purpose: a name in this set that has no icon renders
    as *nothing*, which is worse than the literal text it replaces.
    """
    label = "[num]+50[/num] :golden_coin:"

    default = [(t.kind, t.value) for t in parse(label)]
    assert_true(("text", ":golden_coin:") in default, f"literal without opting in: {default}")

    widened = [(t.kind, t.value) for t in parse(label, extra_emojis=frozenset({"golden_coin"}))]
    assert_true(("image", "golden_coin") in widened, f"an image once opted in: {widened}")
    assert_true(("text", ":golden_coin:") not in widened, "and the marker is consumed")


def _rendered(markup: str, *, static: bool):  # type: ignore[no-untyped-def]
    """Render `markup` through the real RichText and the real sprite sheets."""
    import pygame

    pygame.init()
    pygame.display.set_mode((64, 64))
    from scene import Scene
    from settings import (
        EMOTE_SHEET_DEFINITION,
        EMOTE_SHEET_FILE,
        ITEMS_SHEET_DEFINITION,
        ITEMS_SHEET_FILE,
    )
    from ui.widgets.rich_text import RichText

    emotes = Scene.import_sheet(str(EMOTE_SHEET_FILE), EMOTE_SHEET_DEFINITION, width=14, height=13)
    items = Scene.import_sheet(str(ITEMS_SHEET_FILE), ITEMS_SHEET_DEFINITION, width=16, height=16)
    rt = RichText(markup, (0, 0, 400, 60), {**items, **emotes}, base_size=14,
                  show_scrollbar=False, extra_emojis=frozenset(ITEMS_SHEET_DEFINITION))
    surface = rt.render_static() if static else rt.content_surface
    assert surface is not None
    return pygame.mask.from_surface(surface).count()


def test_render_static_actually_draws_the_icons() -> None:
    """The bug this method exists for, and the one a string test cannot see.

    `content_surface` is text only - icons live in `image_items` and are blitted
    by `draw()` each frame. Reward chips and toasts cached `content_surface` and
    blitted it themselves, so every icon in both was silently dropped: the layout
    reserved the width, nothing filled it. Measured in painted pixels, because
    that is the only thing that would have caught it.
    """
    text_only = _rendered("[num]+50[/num] :golden_coin:", static=False)
    with_icons = _rendered("[num]+50[/num] :golden_coin:", static=True)
    bare = _rendered("[num]+50[/num]", static=True)

    assert_true(with_icons > text_only, f"the coin adds pixels: {with_icons} vs {text_only}")
    assert_eq(text_only, bare, "and content_surface had none of it - same pixels as no icon at all")


def main() -> None:
    tests = [
        test_bare_closer_matches_the_named_one,
        test_bare_closer_pops_the_innermost_tag,
        test_the_two_closers_interleave,
        test_an_unmatched_closer_warns_instead_of_raising,
        test_strip_tags_removes_the_bare_closer,
        test_emoji_still_parses,
        test_an_unknown_emoji_stays_literal,
        test_link_argument_survives,
        test_extra_emojis_opens_the_item_sheet,
        test_render_static_actually_draws_the_icons,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} markup tests passed.")


if __name__ == "__main__":
    main()
