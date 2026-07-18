"""Shared keycap rendering (design-system A).

One place builds the hotkey component: the hotbar sprite ``hud.icons["key_*"]``
scaled evenly from the native 32px (default 0.5 → 16px for HUD; panels may use
larger scales like 0.75 → 24px for readability). Single-char keys get a crisp
fresh glyph on the scaled key; multi-char / mouse / arrow keys reuse their
baked sprite art.

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
              scale: float = 0.5) -> "pygame.Surface | None":
    """Return a keycap surface for ``token``, or ``None`` if it has no sprite.

    *scale* multiplies the native 32px sprite (0.5 → 16px, 0.75 → 24px).
    """
    ck = (token, glyph_color, id(glyph_font), scale)
    if ck in _cache:
        return _cache[ck]
    cap = _make_cap(icons, token, glyph_font, glyph_color, scale)
    _cache[ck] = cap
    return cap


def _scaled(sprite_list, scale: float = 0.5) -> "pygame.Surface | None":
    return pygame.transform.scale_by(sprite_list[0], scale) if sprite_list else None


def _make_cap(icons, token, glyph_font, glyph_color, scale: float = 0.5):
    arrow = _ARROW_DIR.get(token)
    if arrow is not None:                       # ← ↑ → ↓ (placeholder or hand art)
        return _scaled(icons.get(f"key_{arrow}"), scale)
    if token in _MOUSE:                          # LMB / RMB
        return _scaled(icons.get(_MOUSE[token]), scale)
    if len(token) == 1:                          # single glyph — fresh, crisp label
        key = icons.get("key")
        if not key:
            return None
        cap = pygame.transform.scale_by(key[0], scale).copy()
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


def measure(icons, glyph_font, text_font, text: str,
            glyph_color=(255, 255, 255), *, scale: float = 0.5) -> int:
    """Total pixel width of the rendered hint row (for right alignment)."""
    w = 0
    for kind, val in _parts(text):
        if kind == "key":
            cap = build_cap(icons, val, glyph_font, glyph_color, scale=scale)
            w += cap.get_width() if cap else text_font.size(val)[0]
        else:
            w += text_font.size(val)[0]
    return w


def render_hint(surface, icons, glyph_font, text_font, text, pos, text_color,
                *, align="left", glyph_color=(255, 255, 255), shadow_color=None,
                scale: float = 0.5) -> None:
    """Draw an inline hint row mixing keycaps (``{TOKEN}``) and text.

    Text parts get an optional +2 drop shadow (chrome model); keycaps never do
    (they are sprites). Unknown tokens fall back to plain text so nothing vanishes.
    """
    x, y = pos
    if align == "right":
        x -= measure(icons, glyph_font, text_font, text, glyph_color, scale=scale)
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
        if shadow_color is not None:
            sh = text_font.render(val, False, shadow_color)
            surface.blit(sh, (x + 2, y + (line_h - sh.get_height()) // 2 + 2))
        glyph = text_font.render(val, False, text_color)
        surface.blit(glyph, (x, y + (line_h - glyph.get_height()) // 2))
        x += glyph.get_width()
