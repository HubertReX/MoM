#!/usr/bin/env python3
"""Unit tests for `ui/widgets/panel.Panel` - pudełko liczone z treści.

Run from the project root:
    .venv/bin/python tests/test_panel_autosize.py

Powód istnienia tego pliku jest konkretny: nazwa lokacji „Tawerna Brakująca klepka"
zawijała się do dwóch linii w pudełku, którego wysokość była zaszyta na jedną
(`_location_panel_h = 76`), więc druga linia wchodziła na ramkę. To ta sama klasa
błędu, która wcześniej rozjechała panel pomocy i kolumny questów - i jedyny sposób,
żeby nie wróciła, to **żeby rozmiaru pudełka nie dało się wpisać z palca**.

Testy pilnują trzech rzeczy:

1. Pudełko rośnie razem z treścią - w obu wymiarach, i mierzy się to na wysokości,
   bo to ją najłatwiej zapomnieć.
2. Treść zawsze mieści się w obszarze wewnętrznym, cokolwiek jej podasz - łącznie
   z ramką nine-patcha, która zjada pierwsze `border * scale` pikseli z każdej strony.
3. `render_tight` nie ucina wyśrodkowanego tekstu. Pierwsza wersja poprawki
   przycinała gotowy surface do `content_width` od x=0 - przy `[center]` odcinało to
   końcówkę napisu i „Tawerna Brakująca klepka" traciła „klepka".
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

pygame.init()
pygame.display.set_mode((320, 240))

import settings                                          # noqa: E402
from ui import layout                                    # noqa: E402
from ui.widgets.panel import Panel                       # noqa: E402
from ui.widgets.rich_text import render_tight            # noqa: E402


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def _content(w: int, h: int) -> pygame.Surface:
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((255, 0, 0, 255))
    return surf


def _screen() -> pygame.Surface:
    return pygame.Surface((settings.WIDTH, settings.HEIGHT), pygame.SRCALPHA)


###############################################################################################################
# 1. Pudełko wynika z treści
###############################################################################################################

def test_the_box_grows_with_the_content_in_both_directions() -> None:
    panel = Panel(pad=(40, 32), name="probe")
    one_line = panel.box_size((200, 40))
    two_lines = panel.box_size((200, 80))
    assert_eq(two_lines[0], one_line[0], "szerokość bez zmian przy tej samej treści")
    assert_eq(two_lines[1] - one_line[1], 40, "wysokość rośnie dokładnie o przyrost treści")


def test_the_box_is_the_content_plus_padding_on_every_side() -> None:
    panel = Panel(pad=(40, 32), name="probe")
    assert_eq(panel.box_size((200, 40)), (200 + 80, 40 + 64), "padding liczony obustronnie")


def test_padding_can_never_be_thinner_than_the_painted_frame() -> None:
    """Ramka nine-patcha to obrazek, nie miejsce na tekst - pod nią nic nie wchodzi."""
    panel = Panel(scale=4, border=6, pad=(2, 2), name="probe")
    assert_eq(panel.pad, (24, 24), "za mały padding podniesiony do grubości ramki")


def test_min_size_is_a_floor_not_a_ceiling() -> None:
    """`min_size` wyrównuje wygląd drobiazgów, ale nie ma prawa ściskać treści."""
    panel = Panel(pad=(30, 30), min_size=(300, 100), name="probe")
    assert_eq(panel.box_size((10, 10)), (300, 100), "mała treść dostaje minimum")
    big = panel.box_size((400, 400))
    assert_eq(big, (460, 460), "duża treść przebija minimum, a nie jest do niego docinana")


###############################################################################################################
# 2. Treść zawsze mieści się w pudełku
###############################################################################################################

def test_drawing_any_content_size_reports_no_violation() -> None:
    layout.reset_violations()
    panel = Panel(pad=(40, 32), name="probe")
    surface = _screen()
    for size in ((100, 30), (400, 120), (700, 260), (12, 8)):
        panel.draw(surface, _content(*size), anchor="midtop")
    assert_eq(layout.violations(), [], "pudełko liczone z treści nie może jej nie mieścić")


def test_the_content_sits_fully_inside_the_inner_area() -> None:
    layout.reset_violations()
    panel = Panel(pad=(40, 32), name="probe")
    surface = _screen()
    content = _content(300, 90)
    rect = panel.draw(surface, content, anchor="midtop")
    inner = rect.inflate(-2 * panel.pad[0], -2 * panel.pad[1])
    assert_true(inner.contains(content.get_rect(center=rect.center)),
                f"treść {content.get_size()} nie mieści się w {tuple(inner)}")
    assert_eq(layout.violations(), [], "i nic nie zgłoszono")


def test_a_box_wider_than_the_screen_is_reported_not_clamped() -> None:
    """Rejestr layoutu ma krzyczeć, a nie po cichu docinać (zasada z ui/AGENTS.md)."""
    layout.reset_violations()
    panel = Panel(pad=(40, 32), name="too-wide")
    panel.draw(_screen(), _content(settings.WIDTH + 200, 40), anchor="midtop")
    kinds = [v.split(":")[0].split()[-1] for v in layout.violations()]
    assert_true(any("h-overflow" in v for v in layout.violations()),
                f"brak zgłoszenia h-overflow: {layout.violations()} ({kinds})")
    layout.reset_violations()


def test_max_content_size_is_the_wrap_budget_for_a_given_box() -> None:
    panel = Panel(pad=(40, 32), name="probe")
    assert_eq(panel.max_content_size((400, 200)), (400 - 80, 200 - 64),
              "budżet treści = budżet pudełka minus padding")


###############################################################################################################
# 3. Treść nie może być przycięta przy składaniu
###############################################################################################################

def test_render_tight_keeps_centred_text_whole() -> None:
    """Regresja: przycinanie do `content_width` od x=0 zjadało koniec wyśrodkowanej linii."""
    from ui.widgets.rich_text import RichText
    text = "[center]Tawerna Brakująca klepka[/center]"
    # ile pikseli napis zajmuje, gdy nikt go nie dotyka
    loose = RichText(text, (0, 0, 1000, 400), {}, base_size=32,
                     show_scrollbar=False).render_static().get_bounding_rect()
    tight = render_tight(text, 1000, {}, base_size=32, show_scrollbar=False)
    painted = tight.get_bounding_rect()
    assert_eq(painted.width, loose.width, "napis stracił piksele przy dopasowaniu szerokości")
    assert_true(tight.get_width() - painted.width <= 12,
                f"surface szerszy od napisu o {tight.get_width() - painted.width}px - "
                f"pudełko byłoby za szerokie")


def test_render_tight_is_no_wider_than_the_wrap_budget() -> None:
    long_text = "[center]" + " ".join(["Blunderhaven"] * 20) + "[/center]"
    surf = render_tight(long_text, 300, {}, base_size=32, show_scrollbar=False)
    assert_true(surf.get_width() <= 300,
                f"zawinięcie zignorowane: {surf.get_width()}px przy budżecie 300px")
    assert_true(surf.get_height() > 40, "długi tekst ma zająć więcej niż jedną linię")


def test_a_longer_name_produces_a_taller_box() -> None:
    """Dokładnie ten przypadek, który zgłosił autor - dwie linie w pudełku na jedną."""
    panel = Panel(pad=(40, 32), name="probe")
    budget = 300
    short = render_tight("[center]Maze[/center]", budget, {}, base_size=32, show_scrollbar=False)
    long = render_tight("[center]Tawerna Brakująca klepka[/center]", budget, {},
                        base_size=32, show_scrollbar=False)
    assert_true(long.get_height() > short.get_height(), "długa nazwa musi się zawinąć")
    assert_true(panel.box_size(long.get_size())[1] > panel.box_size(short.get_size())[1],
                "pudełko dłuższej nazwy musi być wyższe")


def main() -> None:
    tests = [
        test_the_box_grows_with_the_content_in_both_directions,
        test_the_box_is_the_content_plus_padding_on_every_side,
        test_padding_can_never_be_thinner_than_the_painted_frame,
        test_min_size_is_a_floor_not_a_ceiling,
        test_drawing_any_content_size_reports_no_violation,
        test_the_content_sits_fully_inside_the_inner_area,
        test_a_box_wider_than_the_screen_is_reported_not_clamped,
        test_max_content_size_is_the_wrap_budget_for_a_given_box,
        test_render_tight_keeps_centred_text_whole,
        test_render_tight_is_no_wider_than_the_wrap_budget,
        test_a_longer_name_produces_a_taller_box,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} panel auto-size tests passed.")
    layout.reset_violations()


if __name__ == "__main__":
    main()
