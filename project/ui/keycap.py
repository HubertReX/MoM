"""Shared keycap rendering (design-system A).

One place builds the hotkey component: the hotbar sprite ``hud.icons["key_*"]``
rendered at the native 32px (the design-system minimum - keycaps scaled down to
16px were unreadable, so ``scale`` defaults to 1.0 and stays 1.0 everywhere).
Single-char keys get a crisp fresh glyph on the key; multi-char / mouse / arrow
keys reuse their baked sprite art.

``render_hint`` draws an inline row mixing keycaps and text from a ``{TOKEN}``
markup string (e.g. ``"{W}/{S} wybór   ·   {Enter} rozwiń"``) - used by the help
header and quest footer so their nav hints show the same keycaps as everything else.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    Icons = dict[str, list[pygame.Surface]]

# ↑↓←→ and mouse tokens map to their dedicated sprites; everything else is key_<token>.
_ARROW_DIR = {"↑": "up", "↓": "down", "←": "left", "→": "right"}
_MOUSE = {"LMB": "mouse_LMB", "RMB": "mouse_RMB"}
_BASE_PX = 32          # native sprite size before scaling
_MARKUP = re.compile(r"\{([^}]+)\}")

# cache keyed by (token, glyph_color, font id, scale) — fonts live for the whole run
_cache: dict[tuple, "pygame.Surface | None"] = {}


def build_cap(icons, token: str, glyph_font: pygame.font.Font,
              glyph_color: tuple[int, int, int], *,
              scale: float = 1.0) -> "pygame.Surface | None":
    """Return a keycap surface for ``token``, or ``None`` if it has no sprite.

    *scale* multiplies the native 32px sprite; keep it at 1.0 (32px) - the
    design-system minimum for a readable keycap.
    """
    ck = (token, glyph_color, id(glyph_font), scale)
    if ck in _cache:
        return _cache[ck]
    cap = _make_cap(icons, token, glyph_font, glyph_color, scale)
    _cache[ck] = cap
    return cap


def _scaled(sprite_list, scale: float = 1.0) -> "pygame.Surface | None":
    if not sprite_list:
        return None
    return sprite_list[0] if scale == 1.0 else pygame.transform.scale_by(sprite_list[0], scale)


def _make_cap(icons, token, glyph_font, glyph_color, scale: float = 1.0):
    arrow = _ARROW_DIR.get(token)
    if arrow is not None:                       # ← ↑ → ↓ (placeholder or hand art)
        return _scaled(icons.get(f"key_{arrow}"), scale)
    if token in _MOUSE:                          # LMB / RMB
        return _scaled(icons.get(_MOUSE[token]), scale)
    if len(token) == 1:                          # single glyph — fresh, crisp label
        key = icons.get("key")
        if not key:
            return None
        cap = key[0].copy() if scale == 1.0 else pygame.transform.scale_by(key[0], scale)
        glyph = glyph_font.render(token, False, glyph_color)
        cap.blit(glyph, glyph.get_rect(center=cap.get_rect().center).move(0, -1))
        return cap
    return _scaled(icons.get(f"key_{token}"), scale)  # Esc / Shift / Enter / F1..


def _parts(text: str) -> list[tuple[str, str]]:
    """Split ``{H} / {F1} close`` into alternating ('key', 'H') / ('text', ' / ') parts."""
    out: list[tuple[str, str]] = []
    i = 0
    for m in _MARKUP.finditer(text):
        if m.start() > i:
            out.append(("text", text[i:m.start()]))
        out.append(("key", m.group(1)))
        i = m.end()
    if i < len(text):
        out.append(("text", text[i:]))
    return out


# Pure-separator text parts (between two keycaps) render at ``sep_font`` when one is
# given, so a thin " / " is not dwarfed by the 32px caps around it.
_SEP_CHARS = set("/-·")


def _part_font(val: str, text_font, sep_font):
    """The font a text part is drawn with: the bigger separator font for a part
    that is only separator punctuation, otherwise the normal text font."""
    if sep_font is not None and val.strip() and all(c in _SEP_CHARS for c in val.strip()):
        return sep_font
    return text_font


def measure(icons, glyph_font, text_font, text: str,
            glyph_color=(255, 255, 255), *, scale: float = 1.0, sep_font=None) -> int:
    """Total pixel width of the rendered hint row (for right alignment)."""
    w = 0
    for kind, val in _parts(text):
        if kind == "key":
            cap = build_cap(icons, val, glyph_font, glyph_color, scale=scale)
            w += cap.get_width() if cap else text_font.size(val)[0]
        else:
            w += _part_font(val, text_font, sep_font).size(val)[0]
    return w


def render_hint(surface, icons, glyph_font, text_font, text, pos, text_color,
                *, align="left", glyph_color=(255, 255, 255), shadow_color=None,
                scale: float = 1.0, sep_font=None) -> None:
    """Draw an inline hint row mixing keycaps (``{TOKEN}``) and text.

    Text parts get an optional +2 drop shadow (chrome model); keycaps never do
    (they are sprites). Unknown tokens fall back to plain text so nothing vanishes.
    A pure-separator part ("/", "-", "·") is drawn with ``sep_font`` when given, so
    it stays proportional to the 32px caps around it.
    """
    x, y = pos
    if align == "right":
        x -= measure(icons, glyph_font, text_font, text, glyph_color, scale=scale, sep_font=sep_font)
    cap_px = round(_BASE_PX * scale)
    line_h = max(text_font.get_height(), cap_px)
    for kind, val in _parts(text):
        if kind == "key":
            cap = build_cap(icons, val, glyph_font, glyph_color, scale=scale)
            if cap is not None:
                surface.blit(cap, (x, y + (line_h - cap.get_height()) // 2))
                x += cap.get_width()
                continue
            # unknown token — render its name as text
        part_font = _part_font(val, text_font, sep_font)
        if shadow_color is not None:
            sh = part_font.render(val, False, shadow_color)
            surface.blit(sh, (x + 2, y + (line_h - sh.get_height()) // 2 + 2))
        glyph = part_font.render(val, False, text_color)
        surface.blit(glyph, (x, y + (line_h - glyph.get_height()) // 2))
        x += glyph.get_width()
