"""Beveled capsule bar — scrollbar thumb and progress fill in one component.

**The art is the source, not a reference.** ``assets/NinjaAdventure/HUD/scrollbar.png``
(8×16) is loaded once at startup and every pixel of a drawn bar comes from it: repaint
the sprite in Aseprite, restart the game, and the scrollbars change. Nothing about the
look (frame thickness, cap profile, bevel columns) is hard-coded here.

**Colours are roles, not literals.** Each colour in the sprite must be an exact
``theme`` token and stands for one role::

    INK   → frame        RULE  → track (empty groove)     GOLD  → fill body
    WARN  → dark bevel   TITLE → light bevel              alpha 0 → outside the shape

A pixel that is neither fully transparent nor an exact token is a **hard load error**
(the sprite and the palette have drifted apart — see ``load_model``). At draw time the
fill/bevel roles are re-coloured (``fill=``/``bevel=``), which is how one sprite covers
the dialog sentiment bar's red→green sweep. The defaults ``fill=GOLD`` +
``bevel=(WARN, TITLE)`` reproduce the sprite 1:1.

**Structure is parsed, not assumed.** Fully transparent rows at both ends of the sprite
are trimmed (the main axis is the stretchable one), then rows are split into a fixed
leading cap, a stretchable body row (the rows with the widest groove) and a fixed
trailing cap — the nine-patch principle from ``ui/AGENTS.md``, applied along one axis.
The sprite also *shows* its own fill states, so the interior patterns are read off it:
a fully filled row (``dark, fill, fill, light``) and the fill's rounded end row
(``track, fill, fill, track``). Rendering the shipped sprite's own state reproduces it
pixel for pixel — that is ``tests/test_bar_asset.py``.

**Chunky pixel-art scaling.** The bar is built in the sprite's *native* grid and then
**integer-scaled with nearest-neighbour**, so every native pixel becomes a clean ``k×k``
block and the rounded ends keep their blocky proportions. ``k = round(cross / sprite
width)``, min 2 — a bar is always at least 2× the native art.
"""
from __future__ import annotations

from typing import NamedTuple

import pygame
from settings import HUD_DIR, load_image

from .. import theme

_ASSET = "scrollbar.png"
_MIN_SCALE = 2          # never draw below 2× native — that is what "chunky" means
_MIN_THUMB_NATIVE = 3   # a scrollbar thumb is at least this many native rows long
_TRANSPARENT = (0, 0, 0, 0)

# Pixel roles. The sprite's palette maps onto these; everything below works in roles.
FRAME = "frame"
TRACK = "track"
FILL = "fill"
DARK = "dark"
LIGHT = "light"
_GROOVE_ROLES = (TRACK, FILL, DARK, LIGHT)   # the interior that holds track/fill
_FILL_ROLES = (FILL, DARK, LIGHT)            # "this cell is part of the fill"


class _Row(NamedTuple):
    """One native row of the sprite, reduced to its outline.

    ``frame`` / ``groove`` are column indices; every other column is transparent.
    """

    frame: tuple[int, ...]
    groove: tuple[int, ...]


class _Model(NamedTuple):
    """The sprite parsed into a stretchable bar (see the module docstring)."""

    cross: int                              # native columns = sprite width
    head: tuple[_Row, ...]                  # fixed rows before the stretchable body
    body: _Row                              # the row repeated to reach the wanted length
    tail: tuple[_Row, ...]                  # fixed rows after it
    fill_pat: dict[int, tuple[str, ...]]    # groove width → roles of a fully filled row
    end_pat: dict[int, tuple[str, ...]]     # groove width → roles at the fill's rounded end


_model: "_Model | None" = None


#######################################################################################################################
# MARK: Loading the sprite


def _token_roles() -> dict[tuple[int, int, int], str]:
    """The palette contract: which theme token means which role."""
    return {
        tuple(theme.INK[:3]): FRAME,      # type: ignore[dict-item]
        tuple(theme.RULE[:3]): TRACK,     # type: ignore[dict-item]
        tuple(theme.GOLD[:3]): FILL,      # type: ignore[dict-item]
        tuple(theme.WARN[:3]): DARK,      # type: ignore[dict-item]
        tuple(theme.TITLE[:3]): LIGHT,    # type: ignore[dict-item]
    }


def _centred(inner: "tuple[str, ...]", width: int) -> "tuple[str, ...]":
    """Centre a narrower fill pattern inside a wider groove, padding with track."""
    pad = (width - len(inner)) // 2
    return (TRACK,) * pad + inner + (TRACK,) * (width - len(inner) - pad)


def _pattern(table: "dict[int, tuple[str, ...]]", width: int) -> "tuple[str, ...]":
    """Interior roles for a groove ``width``, falling back to the next narrower one."""
    pat = table.get(width)
    if pat is not None:
        return pat
    narrower = [w for w in table if w < width]
    if narrower:
        return _centred(table[max(narrower)], width)
    return (FILL,) * width


def _read_roles(surface: pygame.Surface, path: str) -> "list[list[str | None]]":
    """Classify every pixel into a role — an unknown colour is a hard error."""
    roles = _token_roles()
    width, height = surface.get_size()
    grid: "list[list[str | None]]" = []
    for y in range(height):
        row: "list[str | None]" = []
        for x in range(width):
            r, g, b, a = surface.get_at((x, y))
            if a == 0:
                row.append(None)
                continue
            role = roles.get((r, g, b)) if a == 255 else None
            if role is None:
                raise ValueError(
                    f"{path}: pixel ({x}, {y}) is #{r:02X}{g:02X}{b:02X} alpha {a}, which is not a "
                    f"theme token. The bar sprite may only use INK (frame), RULE (track), "
                    f"GOLD (fill), WARN (dark bevel), TITLE (light bevel) — or fully transparent "
                    f"pixels. Repaint it with the palette, or add the colour to theme.py.",
                )
            row.append(role)
        grid.append(row)
    return grid


def _parse(surface: pygame.Surface, path: str) -> _Model:
    """Turn the classified pixels into a stretchable model (see the module docstring)."""
    cross = surface.get_width()
    grid = _read_roles(surface, path)
    filled_rows = [y for y, row in enumerate(grid) if any(r is not None for r in row)]
    if not filled_rows:
        raise ValueError(f"{path}: the bar sprite is fully transparent — nothing to draw.")
    top, bottom = filled_rows[0], filled_rows[-1]

    rows: list[_Row] = []
    patterns: list[tuple[str, ...]] = []
    for y in range(top, bottom + 1):
        frame = tuple(x for x in range(cross) if grid[y][x] == FRAME)
        groove = tuple(x for x in range(cross) if grid[y][x] in _GROOVE_ROLES)
        rows.append(_Row(frame, groove))
        patterns.append(tuple(str(grid[y][x]) for x in groove))

    # Interior patterns, read off the states the sprite happens to show: for each groove
    # width keep the widest fill (a fully filled row) and the narrowest one (the fill's
    # rounded end). A width the sprite only ever draws filled gets its end pattern
    # derived by centring the next narrower fill — exactly how a rounded cap looks.
    fill_pat: dict[int, tuple[str, ...]] = {}
    end_pat: dict[int, tuple[str, ...]] = {}
    for row, pat in zip(rows, patterns):
        n_fill = sum(1 for role in pat if role in _FILL_ROLES)
        if n_fill == 0:
            continue
        width = len(row.groove)
        widest = fill_pat.get(width)
        if widest is None or n_fill > sum(1 for role in widest if role in _FILL_ROLES):
            fill_pat[width] = pat
        narrowest = end_pat.get(width)
        if narrowest is None or n_fill < sum(1 for role in narrowest if role in _FILL_ROLES):
            end_pat[width] = pat
    for width, pat in list(fill_pat.items()):
        if end_pat.get(width) == pat:                       # only one state drawn at this width
            narrower = [w for w in fill_pat if w < width]
            if narrower:
                end_pat[width] = _centred(fill_pat[max(narrower)], width)

    widest_groove = max(len(row.groove) for row in rows)
    if widest_groove == 0:
        raise ValueError(f"{path}: the bar sprite has no groove — no track/fill pixels to stretch.")
    if widest_groove not in fill_pat:
        raise ValueError(
            f"{path}: no row shows the fill at its full width ({widest_groove} px). The sprite must "
            f"draw the thumb somewhere, so the bevel columns can be read from it.",
        )
    first = next(i for i, row in enumerate(rows) if len(row.groove) == widest_groove)
    last = len(rows) - 1 - next(i for i, row in enumerate(reversed(rows)) if len(row.groove) == widest_groove)
    body = rows[first]
    for i in range(first, last + 1):
        if rows[i] != body:
            raise ValueError(
                f"{path}: row {top + i} has a different outline than the stretchable body row "
                f"{top + first}. Every row between the two caps is repeated to stretch the bar, so "
                f"they must share one frame/groove profile.",
            )
    return _Model(cross, tuple(rows[:first]), body, tuple(rows[last + 1:]), fill_pat, end_pat)


def load_model() -> None:
    """Load and validate the bar sprite now.

    Called once at startup (``game.py``) so a sprite that drifted from the palette fails
    loudly with the offending pixel, instead of on the first frame that draws a scrollbar.
    Needs an initialised display (``convert_alpha``); the result is cached per module.
    """
    _get_model()


def _get_model() -> _Model:
    global _model
    if _model is None:
        path = HUD_DIR / _ASSET
        _model = _parse(load_image(path).convert_alpha(), str(path))
    return _model


#######################################################################################################################
# MARK: Drawing


def _shade(color: "tuple[int, ...]", factor: float) -> "tuple[int, int, int]":
    """Darken (factor<1) or lighten toward white (factor>1) an RGB(A) colour."""
    r, g, b = color[0], color[1], color[2]
    if factor <= 1.0:
        return (int(r * factor), int(g * factor), int(b * factor))
    t = factor - 1.0
    return (int(r + (255 - r) * t), int(g + (255 - g) * t), int(b + (255 - b) * t))


def _palette(
    fill: "tuple[int, int, int]",
    bevel: "tuple[tuple[int, int, int], tuple[int, int, int]] | None",
) -> "dict[str, tuple[int, int, int]]":
    """Role → colour for one draw call (this is the colour swap on the loaded sprite)."""
    dark, light = bevel if bevel is not None else (_shade(fill, 0.6), _shade(fill, 1.4))
    return {FRAME: theme.INK, TRACK: theme.RULE, FILL: fill, DARK: dark, LIGHT: light}


def _native(
    model: _Model, native_main: int, seg_start: int, seg_len: int,
    colour: "dict[str, tuple[int, int, int]]",
) -> pygame.Surface:
    """Build the bar in the sprite's native grid: caps verbatim, body row repeated."""
    surface = pygame.Surface((model.cross, native_main), pygame.SRCALPHA)
    surface.fill(_TRANSPARENT)
    body_rows = native_main - len(model.head) - len(model.tail)
    rows = list(model.head) + [model.body] * body_rows + list(model.tail)
    groove_index = 0
    for mi, row in enumerate(rows):
        for x in row.frame:
            surface.set_at((x, mi), colour[FRAME])
        if not row.groove:
            continue
        width = len(row.groove)
        if seg_len > 0 and seg_start <= groove_index < seg_start + seg_len:
            rounded_end = groove_index in (seg_start, seg_start + seg_len - 1)
            pat = _pattern(model.end_pat if rounded_end else model.fill_pat, width)
        else:
            pat = (TRACK,) * width
        for x, role in zip(row.groove, pat):
            surface.set_at((x, mi), colour[role])
        groove_index += 1
    return surface


def _blit_bar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    vertical: bool,
    frac_visible: "float | None",
    frac_pos: float,
    fraction: float,
    fill: "tuple[int, int, int]",
    bevel: "tuple[tuple[int, int, int], tuple[int, int, int]] | None",
) -> None:
    model = _get_model()
    cross = rect.width if vertical else rect.height
    main = rect.height if vertical else rect.width
    k = max(_MIN_SCALE, round(cross / model.cross))
    caps = len(model.head) + len(model.tail)
    native_main = max(caps + 1, round(main / k))

    # groove rows = the ones that can hold track/fill (cap rows may have a narrow groove too)
    groove_rows = sum(1 for row in model.head + model.tail if row.groove) + (native_main - caps)
    if frac_visible is not None:          # scrollbar thumb
        thumb = max(_MIN_THUMB_NATIVE, round(groove_rows * max(0.0, min(1.0, frac_visible))))
        seg_len = min(thumb, groove_rows)
        seg_start = round((groove_rows - seg_len) * max(0.0, min(1.0, frac_pos)))
    else:                                 # progress fill from the start
        seg_len = min(groove_rows, round(groove_rows * max(0.0, min(1.0, fraction))))
        seg_start = 0

    native = _native(model, native_main, seg_start, seg_len, _palette(fill, bevel))
    scaled = pygame.transform.scale(native, (model.cross * k, native_main * k))
    if not vertical:
        # transpose vertical→horizontal: fill-start (top) → left, dark edge → top
        scaled = pygame.transform.rotate(pygame.transform.flip(scaled, True, False), 90)
    # centre on the cross axis, align to the start of the main axis
    if vertical:
        pos = (rect.x + (rect.width - scaled.get_width()) // 2, rect.y)
    else:
        pos = (rect.x, rect.y + (rect.height - scaled.get_height()) // 2)
    surface.blit(scaled, pos)


def draw_scrollbar(
    surface: pygame.Surface,
    rect: "pygame.Rect | tuple[int, int, int, int]",
    *,
    frac_visible: float,
    frac_pos: float,
    vertical: bool = True,
    fill: "tuple[int, int, int]" = theme.GOLD,
    bevel: "tuple[tuple[int, int, int], tuple[int, int, int]] | None" = (theme.WARN, theme.TITLE),
) -> None:
    """Capsule track with a beveled thumb.

    ``frac_visible`` = viewport / content (the thumb's share of the track);
    ``frac_pos`` = scroll / max_scroll (0 at top/left, 1 at bottom/right).
    """
    _blit_bar(surface, pygame.Rect(rect), vertical, frac_visible, frac_pos, 0.0, fill, bevel)


def draw_progress(
    surface: pygame.Surface,
    rect: "pygame.Rect | tuple[int, int, int, int]",
    fraction: float,
    *,
    vertical: bool = False,
    fill: "tuple[int, int, int]" = theme.ACCENT_CYAN,
    bevel: "tuple[tuple[int, int, int], tuple[int, int, int]] | None" = None,
) -> None:
    """Capsule track with a beveled fill from the start up to ``fraction`` (0..1).

    ``bevel`` defaults to edges derived from ``fill`` — the colour-changing bars
    (e.g. dialog sentiment) rely on this so one component covers every hue.
    """
    _blit_bar(surface, pygame.Rect(rect), vertical, None, 0.0, fraction, fill, bevel)
