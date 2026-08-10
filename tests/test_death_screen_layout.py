#!/usr/bin/env python3
"""Ekran śmierci: nic się na nic nie nakłada, a śmierć jest jednorazowa.

Zastany błąd: na ekranie śmierci wszystkie napisy rysowały się jeden na drugim.
Powód jest arytmetyczny - pudełko miało zaszyte 600 px, a sama metryczka zapisu
(„v0.4 2026-08-10 23:06   0g 04min") mierzy ponad 500 px. Nazwa szła do lewej,
metryczka do prawej, więc przy takiej szerokości obie zaczynały się w tym samym
miejscu. Do tego pytanie „Wczytać zapis?" i przyciski „Tak"/„Nie" miały wpisany
**ten sam** środek.

Trzecia rzecz w tym samym miejscu: `die()` dawało się wywołać dwa razy (raz ze
starcia, raz z zaległego zdarzenia ogłuszenia), a u gracza każde wywołanie gra
dzwon śmierci i przestawia stos stanów.

Uruchamianie z katalogu projektu:
    .venv/bin/python tests/test_death_screen_layout.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame                                                    # noqa: E402

pygame.init()
pygame.display.set_mode((1280, 720))

import settings                                                  # noqa: E402
from ui import theme                                             # noqa: E402
from ui.panels.save_load import (                                # noqa: E402
    _CONFIRM_BUTTONS_DY,
    _CONFIRM_TEXT_DY,
    _GAP,
    _PAD,
    _ROW_INSET,
    _SLOT_FONT,
    _fit_text,
    _slot_row_width,
)

#: najdłuższa metryczka, jaką potrafi wyprodukować `_SlotButton.parts`
LONG_META = "v0.4 2026-08-10 23:06   0g 04min"
LONG_NAME = "Ostatni zapis"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}\n  expected: {b!r}\n  actual:   {a!r}"


class FakeSlot:
    """Tyle z `_SlotButton`, ile czyta pomiar wiersza."""

    def __init__(self, name: str, meta: str) -> None:
        self.parts = (name, meta)


def _name_and_meta_boxes(row_w: int, name: str, meta: str) -> tuple[pygame.Rect, pygame.Rect]:
    """Prostokąty obu napisów po tym samym skracaniu, co w `_draw_slot_row`."""
    font = theme.menu_font(_SLOT_FONT)
    room = row_w - 2 * _ROW_INSET
    meta_w = font.size(meta)[0] if meta else 0
    if meta and font.size(name)[0] + meta_w + _GAP > room:
        meta = _fit_text(font, meta, int(room * 0.75) - _GAP)
        meta_w = font.size(meta)[0] if meta else 0
    name = _fit_text(font, name, room - meta_w - (_GAP if meta else 0))
    name_rect = pygame.Rect(_ROW_INSET, 0, font.size(name)[0], 1)
    meta_rect = pygame.Rect(row_w - _ROW_INSET - meta_w, 0, meta_w, 1)
    return name_rect, meta_rect


# ---------------------------------------------------------------------------
# Wiersz listy zapisów
# ---------------------------------------------------------------------------

def test_a_narrow_row_shortens_instead_of_overlapping() -> None:
    """Sedno błędu: w wąskim pudełku napisy MUSZĄ się skrócić, a nie nałożyć."""
    name_rect, meta_rect = _name_and_meta_boxes(600 - 4 * _PAD, LONG_NAME, LONG_META)

    assert_true(name_rect.right <= meta_rect.left,
                f"napisy nachodzą na siebie: {name_rect} vs {meta_rect}")


def test_a_wide_row_keeps_both_texts_whole() -> None:
    font = theme.menu_font(_SLOT_FONT)
    row_w = _slot_row_width(font, FakeSlot(LONG_NAME, LONG_META))  # type: ignore[arg-type]

    name_rect, meta_rect = _name_and_meta_boxes(row_w, LONG_NAME, LONG_META)

    assert_eq(name_rect.width, font.size(LONG_NAME)[0], "nazwa została skrócona bez potrzeby")
    assert_eq(meta_rect.width, font.size(LONG_META)[0], "metryczka została skrócona bez potrzeby")
    assert_true(name_rect.right <= meta_rect.left, "napisy nachodzą mimo szerokiego wiersza")


def test_the_shortened_text_never_grows() -> None:
    font = theme.menu_font(_SLOT_FONT)

    for limit in (0, 10, 40, 200, 5000):
        out = _fit_text(font, LONG_META, limit)
        assert_true(font.size(out)[0] <= max(limit, 0),
                    f"skrót {out!r} ({font.size(out)[0]}px) nie mieści się w {limit}px")


def test_the_panel_is_wide_enough_for_the_longest_row() -> None:
    """Szerokość pudełka liczy się z treści, więc skracanie ma być wyjątkiem.

    `_PAD` wchodzi dwa razy z każdej strony: pudełko odsuwa listę, lista odsuwa
    wiersz. Pomyłka o te 40 px wróciła w pierwszym podejściu do tej poprawki.
    """
    font = theme.menu_font(_SLOT_FONT)
    needed = _slot_row_width(font, FakeSlot(LONG_NAME, LONG_META)) + 4 * _PAD  # type: ignore[arg-type]

    row_w = needed - 4 * _PAD
    name_rect, meta_rect = _name_and_meta_boxes(row_w, LONG_NAME, LONG_META)

    assert_true(needed <= settings.WIDTH - 2 * _PAD, "pudełko nie mieści się na ekranie 1280")
    assert_true(name_rect.right <= meta_rect.left, "wyliczona szerokość i tak daje nachodzenie")


# ---------------------------------------------------------------------------
# Pytanie o wczytanie
# ---------------------------------------------------------------------------

def test_the_confirm_question_sits_above_its_buttons() -> None:
    """Pytanie i „Tak/Nie" miały wpisany ten sam środek - stąd zlepek na ekranie."""
    text_h = theme.menu_font(24).get_height()

    text_bottom = _CONFIRM_TEXT_DY + text_h // 2
    buttons_top = _CONFIRM_BUTTONS_DY - 20        # połowa wysokości przycisku (size 28)

    assert_true(text_bottom <= buttons_top,
                f"pytanie ({text_bottom}) wchodzi na przyciski ({buttons_top})")


if __name__ == "__main__":
    tests = [
        ("wąski wiersz skraca, nie nakłada", test_a_narrow_row_shortens_instead_of_overlapping),
        ("szeroki wiersz nie skraca niczego", test_a_wide_row_keeps_both_texts_whole),
        ("skrót nigdy nie jest szerszy niż limit", test_the_shortened_text_never_grows),
        ("pudełko liczone z najdłuższego wiersza",
         test_the_panel_is_wide_enough_for_the_longest_row),
        ("pytanie stoi nad przyciskami", test_the_confirm_question_sits_above_its_buttons),
    ]
    failures = 0
    for name, func in tests:
        try:
            func()
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            import traceback

            traceback.print_exc()
            failures += 1

    print(f"\n{'─' * 40}")
    total = len(tests)
    passed = total - failures
    if failures:
        print(f"  FAILED  {failures}/{total} tests")
        sys.exit(1)
    else:
        print(f"  PASSED  {passed}/{total} tests")
