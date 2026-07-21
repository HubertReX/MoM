"""Shared HUD/keycap icon atlas.

The icon dict (emote sheet + HUD sheet + the generated ``key_*`` caps) used to be
built per :class:`Scene`, which meant panels shown *outside* a scene - the main
menu's Save/Load screens - had no icons at all and fell back to plain-text
shortcut hints. That fallback was the only reason the main-menu Load modal looked
different from the in-game one.

Now there is exactly one atlas, built lazily on first use and reused by every
scene and every menu, so a panel renders identically wherever it is opened.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from settings import (
    EMOTE_SHEET_DEFINITION,
    EMOTE_SHEET_FILE,
    FONT_COLOR,
    FONT_SIZE_SMALL,
    FONT_SIZE_TINY,
    HUD_SHEET_DEFINITION,
    HUD_SHEET_FILE,
)

if TYPE_CHECKING:
    from game import Game

    Icons = dict[str, list[pygame.Surface]]

_icons: "Icons | None" = None


def get_icons(game: "Game") -> "Icons":
    """Return the shared icon atlas, building it on first call."""
    global _icons
    if _icons is None:
        _icons = _build(game)
    return _icons


def _import_sheet(
    sheet_path: str,
    sheet_definition: dict[str, list[tuple[int, int]]],
    width: int,
    height: int,
    scale: int = 1,
) -> "Icons":
    """Load a sprite sheet and cut it into named frame lists."""
    result: "Icons" = {}
    img = pygame.image.load(sheet_path).convert_alpha()
    if scale != 1:
        img = pygame.transform.scale_by(img, scale)
    img_rect = img.get_rect()

    for key, definition in sheet_definition.items():
        anim = []
        for x, y in definition:
            rec = pygame.Rect(x * width * scale, y * height * scale, width * scale, height * scale)
            if rec.colliderect(img_rect):
                anim.append(img.subsurface(rec))
            else:
                print(f"[red]ERROR![/] coordinate {x}x{y} not inside sprite sheet for '{key}' animation")
        if anim:
            result[key] = anim
    return result


def _build(game: "Game") -> "Icons":
    icons = _import_sheet(str(EMOTE_SHEET_FILE), EMOTE_SHEET_DEFINITION, width=14, height=13)
    icons.update(_import_sheet(str(HUD_SHEET_FILE), HUD_SHEET_DEFINITION, width=16, height=16, scale=2))
    _generate_key_caps(icons, game)
    return icons


def _generate_key_caps(icons: "Icons", game: "Game") -> None:
    small_font = game.fonts[FONT_SIZE_SMALL]
    tiny_font = game.fonts[FONT_SIZE_TINY]

    # Lico pustego `key` (i wszystkich kafli arkusza) jest już przyciemnione
    # w samym sprite'cie HUD.png, więc biały glif ma kontrast bez mnożenia w kodzie.
    center = icons["key"][0].get_rect().center

    def _cap(text: str, font: pygame.font.Font, dy: int) -> pygame.Surface:
        text_surf = font.render(text, False, FONT_COLOR)
        bg = icons["key"][0].copy()
        bg.blit(text_surf, text_surf.get_rect(center=center).move(0, dy))
        return bg

    for letter in range(ord("A"), ord("Z") + 1):
        icons[f"key_{chr(letter)}"] = [_cap(chr(letter), small_font, -1)]

    for digit in range(0, 10):
        icons[f"key_{digit}"] = [_cap(str(digit), tiny_font, -2)]

    for fn in range(1, 13):
        icons[f"key_F{fn}"] = [_cap(f"F{fn}", tiny_font, -2)]

    for sign in "<>`[]+-,.":
        icons[f"key_{sign}"] = [_cap(sign, small_font, -1)]

    # arrow keys (key_up/down/left/right) come from the HUD sheet directly
    # (HUD_SHEET_DEFINITION, rows 2) - hand-drawn arrows on dark keycaps, no
    # code-side placeholder needed anymore.
