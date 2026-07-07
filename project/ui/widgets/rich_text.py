"""RichText: word-wrapped, scrollable, styled text with inline animated emoji and links.

Replaces the thorpy/sftext ``RichPanel`` text engine. The laid-out *text* is rendered
once into a cached content surface; only the (handful of) animated emoji frames and the
scroll offset change per frame, so a static dialog costs one clipped blit. Links expose
hit-test rects so a panel can show a tooltip.
"""
from __future__ import annotations

import re

import pygame

from .. import theme
from ..text.markup import Token, parse
from ..text.style import Style
from ..widget import Widget

_WORD_RE = re.compile(r"\S+|\s+")
_ANIM_FPS = 8.0


class RichText(Widget):
    def __init__(
        self,
        text: str,
        rect: pygame.Rect | tuple[int, int, int, int],
        icons: dict[str, list[pygame.Surface]],
        *,
        base_size: int = 20,
        base_color: pygame._common.ColorValue = theme.DEFAULT_TEXT_COLOR,
        show_scrollbar: bool = True,
    ) -> None:
        super().__init__(rect)
        self.icons = icons
        self.base_style = Style(size=base_size, color=tuple(base_color))  # type: ignore[arg-type]
        self.show_scrollbar = show_scrollbar

        self.scroll: int = 0
        self.max_scroll: int = 0
        self.content_width: int = 0
        self._anim_t: float = 0.0
        self.link_rects: list[tuple[pygame.Rect, str]] = []
        # (name, rect, target_height) so animated frames are scaled to match the text
        self.image_items: list[tuple[str, pygame.Rect, int]] = []
        self._scaled_icons: dict[tuple[str, int], list[pygame.Surface]] = {}
        self._content: pygame.Surface | None = None

        self._text = text
        self.tokens: list[Token] = parse(text, self.base_style)
        self._bake()

    #############################################################################################################
    # MARK: text / layout

    def set_text(self, text: str) -> None:
        if text == self._text:
            return
        self._text = text
        self.tokens = parse(text, self.base_style)
        self.scroll = 0
        self._bake()

    @property
    def content_surface(self) -> pygame.Surface | None:
        """The full (unclipped) laid-out text surface; height == total content height."""
        return self._content

    def _default_line_height(self) -> int:
        return theme.get_font(self.base_style.size).get_height()

    def _icon_frames(self, name: str, target_h: int) -> list[pygame.Surface]:
        """Return the emoji frames scaled to ``target_h`` so inline icons match text size."""
        key = (name, target_h)
        frames = self._scaled_icons.get(key)
        if frames is None:
            src = self.icons.get(name, [])
            frames = []
            for frame in src:
                w, h = frame.get_size()
                scale = target_h / h if h else 1.0
                frames.append(pygame.transform.scale(frame, (max(1, round(w * scale)), target_h)))
            self._scaled_icons[key] = frames
        return frames

    def _render_word(self, word: str, style: Style, font: pygame.font.Font) -> pygame.Surface:
        base = font.render(word, False, style.color)
        if not style.shadow:
            return base
        ox, oy = style.shadow_offset
        surf = pygame.Surface((base.get_width() + ox, base.get_height() + oy), pygame.SRCALPHA)
        surf.blit(font.render(word, False, style.shadow_color), (ox, oy))
        surf.blit(base, (0, 0))
        return surf

    def _layout(self) -> list[dict]:
        width = self.rect.width
        lines: list[dict] = []
        items: list[dict] = []
        x = 0
        line_h = 0
        align: str | None = None
        pending_space = 0

        def flush() -> None:
            nonlocal items, x, line_h, align, pending_space
            lines.append({
                "align": align or "left",
                "items": items,
                "width": x,
                "height": line_h or self._default_line_height(),
            })
            items, x, line_h, align, pending_space = [], 0, 0, None, 0

        for tok in self.tokens:
            if align is None:
                align = tok.style.align

            if tok.kind == "newline":
                flush()
                continue

            if tok.kind == "image":
                target_h = theme.get_font(tok.style.size).get_height()
                frames = self._icon_frames(tok.value, target_h)
                if not frames:
                    continue
                w, h = frames[0].get_size()
                if items and x + pending_space + w > width:
                    flush()
                    align = tok.style.align
                if items:
                    x += pending_space
                pending_space = 0
                items.append({"kind": "image", "name": tok.value, "x": x, "w": w, "h": h,
                              "th": target_h, "link": tok.style.link})
                x += w
                line_h = max(line_h, h)
                continue

            # text
            font = theme.get_font(tok.style.size, bold=tok.style.bold,
                                  italic=tok.style.italic, underline=tok.style.underline)
            space_w = font.size(" ")[0]
            for seg in _WORD_RE.findall(tok.value):
                if seg.isspace():
                    pending_space += space_w * len(seg)
                    continue
                surf = self._render_word(seg, tok.style, font)
                w, h = surf.get_size()
                if items and x + pending_space + w > width:
                    flush()
                    align = tok.style.align
                if items:
                    x += pending_space
                pending_space = 0
                items.append({"kind": "text", "surf": surf, "x": x, "w": w, "h": h, "link": tok.style.link})
                x += w
                line_h = max(line_h, h)

        if items:
            flush()
        return lines

    def _bake(self) -> None:
        lines = self._layout()
        width = self.rect.width
        total_h = sum(line["height"] for line in lines) or self._default_line_height()

        content = pygame.Surface((width, total_h), pygame.SRCALPHA)
        self.link_rects = []
        self.image_items = []

        y = 0
        for line in lines:
            if line["align"] == "center":
                ox = max(0, (width - line["width"]) // 2)
            elif line["align"] == "right":
                ox = max(0, width - line["width"])
            else:
                ox = 0
            for it in line["items"]:
                ix = ox + it["x"]
                rect = pygame.Rect(ix, y, it["w"], it["h"])
                if it["kind"] == "text":
                    content.blit(it["surf"], (ix, y))
                else:
                    self.image_items.append((it["name"], rect, it["th"]))
                if it["link"]:
                    self.link_rects.append((rect, it["link"]))
            y += line["height"]

        self._content = content
        self.content_width = max((line["width"] for line in lines), default=0)
        self.max_scroll = max(0, total_h - self.rect.height)
        self.scroll = min(self.scroll, self.max_scroll)

    #############################################################################################################
    # MARK: scrolling

    def scroll_by(self, dy: int) -> None:
        self.scroll = max(0, min(self.max_scroll, self.scroll + dy))

    def scroll_top(self) -> None:
        self.scroll = 0

    def scroll_bottom(self) -> None:
        self.scroll = self.max_scroll

    def scroll_page_down(self) -> None:
        self.scroll_by(int(self.rect.height * 0.9))

    def scroll_page_up(self) -> None:
        self.scroll_by(-int(self.rect.height * 0.9))

    def is_scroll_bottom(self) -> bool:
        return self.scroll >= self.max_scroll

    #############################################################################################################
    # MARK: links

    def link_at(self, mouse_pos: tuple[int, int]) -> str | None:
        if not self.rect.collidepoint(mouse_pos):
            return None
        local = (mouse_pos[0] - self.rect.x, mouse_pos[1] - self.rect.y + self.scroll)
        for rect, url in self.link_rects:
            if rect.collidepoint(local):
                return url
        return None

    #############################################################################################################
    # MARK: events / update / draw

    def _on_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEWHEEL and self.rect.collidepoint(pygame.mouse.get_pos()):
            self.scroll_by(-event.y * 40)
            return True
        if event.type == pygame.KEYDOWN and self.max_scroll > 0:
            if event.key in (pygame.K_DOWN,):
                self.scroll_by(40); return True
            if event.key in (pygame.K_UP,):
                self.scroll_by(-40); return True
            if event.key == pygame.K_PAGEDOWN:
                self.scroll_page_down(); return True
            if event.key == pygame.K_PAGEUP:
                self.scroll_page_up(); return True
            if event.key == pygame.K_HOME:
                self.scroll_top(); return True
            if event.key == pygame.K_END:
                self.scroll_bottom(); return True
        return False

    def update(self, dt: float) -> None:
        self._anim_t += dt / 1000.0

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible or self._content is None:
            return
        view = self.rect
        prev_clip = surface.get_clip()
        surface.set_clip(view)
        # cached text, clipped to the viewport at the current scroll offset
        surface.blit(self._content, view.topleft, area=pygame.Rect(0, self.scroll, view.width, view.height))
        # animated emoji on top (scaled to match the text they sit next to)
        for name, crect, target_h in self.image_items:
            top = crect.y - self.scroll
            if top + crect.h < 0 or top > view.height:
                continue
            frames = self._icon_frames(name, target_h)
            if not frames:
                continue
            frame = frames[int(self._anim_t * _ANIM_FPS) % len(frames)]
            surface.blit(frame, (view.x + crect.x, view.y + top))
        surface.set_clip(prev_clip)

        if self.show_scrollbar and self.max_scroll > 0:
            self._draw_scrollbar(surface)

    def _draw_scrollbar(self, surface: pygame.Surface) -> None:
        view = self.rect
        track = pygame.Rect(view.right - 6, view.y, 4, view.height)
        total = view.height + self.max_scroll
        thumb_h = max(16, int(view.height * view.height / total))
        thumb_y = view.y + int((view.height - thumb_h) * (self.scroll / self.max_scroll))
        pygame.draw.rect(surface, (0, 0, 0, 90), track, border_radius=2)
        pygame.draw.rect(surface, theme.DEFAULT_TEXT_COLOR, (track.x, thumb_y, 4, thumb_h), border_radius=2)


def render_rich_text_surface(
    text: str,
    max_width: int,
    icons: dict[str, list[pygame.Surface]],
    *,
    base_size: int = 20,
    base_color: tuple[int, int, int] = theme.DEFAULT_TEXT_COLOR,
    shadow: bool = False,
) -> pygame.Surface:
    """Render styled ``text`` to a static surface, word-wrapped to ``max_width``.

    Emoji uses frame 0 only (static).  Pass ``shadow=True`` to apply a drop shadow
    on unstyled text (same effect as ``Label(shadow=True)``).
    """
    base_style = Style(size=base_size, color=base_color, shadow=shadow)
    tokens = parse(text, base_style)

    def _render_word(word: str, style: Style, font: pygame.font.Font) -> pygame.Surface:
        base = font.render(word, False, style.color)
        if not style.shadow:
            return base
        ox, oy = style.shadow_offset
        surf = pygame.Surface((base.get_width() + ox, base.get_height() + oy), pygame.SRCALPHA)
        surf.blit(font.render(word, False, style.shadow_color), (ox, oy))
        surf.blit(base, (0, 0))
        return surf

    # --- layout (word-wrap) ---
    lines: list[dict] = []
    items: list[dict] = []
    x = 0
    line_h = 0
    pending_space = 0

    def flush() -> None:
        nonlocal items, x, line_h, pending_space
        lines.append({
            "items": items,
            "width": x,
            "height": line_h or base_style.size,
        })
        items, x, line_h, pending_space = [], 0, 0, 0

    for tok in tokens:
        if tok.kind == "newline":
            flush()
            continue

        if tok.kind == "image":
            target_h = theme.get_font(tok.style.size).get_height()
            src = icons.get(tok.value, [])
            if not src:
                continue
            w0, h0 = src[0].get_size()
            scale = target_h / h0 if h0 else 1.0
            w = max(1, round(w0 * scale))
            if items and x + pending_space + w > max_width:
                flush()
            if items:
                x += pending_space
            pending_space = 0
            items.append({"kind": "image", "name": tok.value, "x": x, "w": w, "h": target_h})
            x += w
            line_h = max(line_h, target_h)
            continue

        font = theme.get_font(tok.style.size, bold=tok.style.bold,
                              italic=tok.style.italic)
        space_w = font.size(" ")[0]
        for seg in _WORD_RE.findall(tok.value):
            if seg.isspace():
                pending_space += space_w * len(seg)
                continue
            word_surf = _render_word(seg, tok.style, font)
            w = word_surf.get_width()
            if items and x + pending_space + w > max_width:
                flush()
            if items:
                x += pending_space
            pending_space = 0
            items.append({"kind": "text", "surf": word_surf, "x": x, "w": w,
                          "h": word_surf.get_height()})
            x += w
            line_h = max(line_h, word_surf.get_height())

    if items:
        flush()

    # --- bake ---
    total_h = sum(line["height"] for line in lines) or base_style.size
    surface = pygame.Surface((max_width, total_h), pygame.SRCALPHA)
    y = 0
    for line in lines:
        ox = 0  # left-aligned
        for it in line["items"]:
            if it["kind"] == "text":
                surface.blit(it["surf"], (ox + it["x"], y))
            else:
                src = icons.get(it["name"], [])
                if src:
                    frame = src[0]
                    w0, h0 = frame.get_size()
                    scale = it["h"] / h0 if h0 else 1.0
                    scaled = pygame.transform.scale(
                        frame, (max(1, round(w0 * scale)), it["h"]),
                    )
                    surface.blit(scaled, (ox + it["x"], y))
        y += line["height"]

    return surface
