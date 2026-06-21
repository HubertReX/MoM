"""Central UI theme: cached fonts, colours, nine-patch backgrounds and shared constants.

All UI widgets pull fonts and palette entries from here so that nothing is
re-loaded or re-scaled per frame. Fonts are cached by ``(path, size, bold, italic,
underline)`` because the rich-text renderer needs arbitrary sizes (not only the five
sizes the game pre-creates in ``game.fonts``).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pygame

from nine_patch import NinePatch
from settings import (
    CHAR_NAME_COLOR,
    FONT_COLOR,
    HUD_DIR,
    MAIN_FONT,
    MENU_FONT,
    PANEL_BG_COLOR,
    STYLE_TAGS_DICT,
    UI_BORDER_COLOR,
)

# default rich-text colours (mirror RichPanel defaults so dialogs look unchanged)
DEFAULT_TEXT_COLOR: tuple[int, int, int] = (0, 197, 199)
DEFAULT_SHADOW_COLOR: tuple[int, int, int] = (130, 32, 32)
DEFAULT_SHADOW_OFFSET: tuple[int, int] = (4, 4)


#######################################################################################################################
# MARK: Fonts


@lru_cache(maxsize=256)
def get_font(
    size: int,
    *,
    font_path: str = str(MAIN_FONT),
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
) -> pygame.font.Font:
    """Return a cached ``pygame.font.Font``.

    bold/italic/underline are baked into the cached instance, so callers must not
    mutate the returned font's style flags.
    """
    font = pygame.font.Font(font_path, size)
    font.set_bold(bold)
    font.set_italic(italic)
    font.set_underline(underline)
    return font


def menu_font(size: int) -> pygame.font.Font:
    """Cached menu font (munro)."""
    return get_font(size, font_path=str(MENU_FONT))


def measure(text: str, size: int, *, bold: bool = False, italic: bool = False) -> tuple[int, int]:
    """Measure a single run of text without rendering it."""
    return get_font(size, bold=bold, italic=italic).size(text)


#######################################################################################################################
# MARK: Nine-patch backgrounds


@lru_cache(maxsize=64)
def nine_patch(file: str, width: int, height: int, *, scale: int = 4, border: int = 6) -> pygame.Surface:
    """Return a cached nine-patch surface scaled to ``width`` x ``height``.

    Caching on (file, width, height, scale, border) means each distinct panel size is
    only ever scaled once for the whole process.
    """
    return NinePatch(file=file, scale=scale, border=border).get_scaled_to(width, height)


@lru_cache(maxsize=16)
def menu_border(file: str, scale: int) -> pygame.Surface:
    """Cached raw (unscaled-to-size) nine-patch image used for menu/dialog borders."""
    return NinePatch(file=file, scale=scale).image


#######################################################################################################################
# MARK: Palette

# re-export common colours so widgets import them from one place
PANEL_BG: tuple[int, int, int, int] = PANEL_BG_COLOR
BORDER: tuple[int, int, int, int] = UI_BORDER_COLOR
TEXT: tuple[int, int, int, int] = FONT_COLOR
NAME: tuple[int, int, int] = CHAR_NAME_COLOR

__all__ = [
    "get_font",
    "menu_font",
    "measure",
    "nine_patch",
    "menu_border",
    "DEFAULT_TEXT_COLOR",
    "DEFAULT_SHADOW_COLOR",
    "DEFAULT_SHADOW_OFFSET",
    "PANEL_BG",
    "BORDER",
    "TEXT",
    "NAME",
    "STYLE_TAGS_DICT",
    "HUD_DIR",
]
