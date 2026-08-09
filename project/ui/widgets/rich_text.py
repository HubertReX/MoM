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
_ICON_SCALE = 1.35        # inline icons are sized ~1.35x font height (then snapped, see below)
_SCROLLBAR_W = 32         # beveled capsule scrollbar (widgets/bar.py) at the right edge


def _icon_factor(src_h: int, target_h: int) -> int:
    """Nearest whole scale factor for a pixel-art icon (min 1).

    Fractional upscaling of a low-res icon duplicates some rows/cols and not
    others, so the icon looks distorted. An integer factor maps every source
    pixel to a clean k x k block. See the design-system doc (skalowanie ikon).
    """
    if src_h <= 0:
        return 1
    return max(1, round(target_h / src_h))


def render_tight(
    text: str,
    max_width: int,
    icons: "dict[str, list[pygame.Surface]]",
    **kwargs: object,
) -> pygame.Surface:
    """Surface przycięta do **realnej** szerokości tekstu, zawiniętego do ``max_width``.

    Do panelu, którego rozmiar ma wynikać z treści (`widgets/panel.Panel`): dostajesz
    powierzchnię tak szeroką, jak najdłuższa linia, więc pudełko nie jest szerokie na
    cały limit zawijania.

    Dwa przebiegi, nie przycinanie gotowego surface'a. Przycinanie działa tylko dla
    tekstu do lewej: przy ``[center]`` każda linia jest wyśrodkowana w **rect'cie**,
    więc `subsurface((0, 0, content_width, h))` ucinał końcówkę („Tawerna Brakująca
    klepka" traciła „klepka"). Drugi przebieg układa tekst od razu w docelowej
    szerokości, więc centrowanie wychodzi na tym, co widać.
    """
    probe = RichText(text, (0, 0, max_width, 1 << 16), icons, **kwargs)  # type: ignore[arg-type]
    width = max(1, min(probe.content_width, max_width))
    if width == max_width:
        return probe.render_static()
    return RichText(text, (0, 0, width, 1 << 16), icons, **kwargs).render_static()  # type: ignore[arg-type]


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
        line_spacing: int = 0,
        extra_emojis: frozenset[str] = frozenset(),
        icon_scale: float = _ICON_SCALE,
        name: str = "",
    ) -> None:
        super().__init__(rect)
        self.icons = icons
        # human-readable id in layout-violation reports (see ui/layout.py); worth
        # setting for any RichText that is actually drawn on screen
        self.name = name
        # Inline-icon height as a multiple of the font height, before the integer
        # snap. The default (~1.35x) reads as "a touch larger than the text". Dense
        # chips/toasts at a small font want the icon a *whole* step bigger so a 16px
        # coin snaps to a crisp 32px (factor 2) instead of rounding back to 1 - see
        # the design-system rule on integer icon scaling.
        self._icon_scale = icon_scale
        # Names beyond the emote sheet that ``:name:`` may reference. Whatever is
        # listed here must exist in ``icons`` - an image token with no frames
        # draws nothing at all, which is worse than the literal text it replaced.
        self.extra_emojis = extra_emojis
        self.base_style = Style(size=base_size, color=tuple(base_color))  # type: ignore[arg-type]
        self.show_scrollbar = show_scrollbar
        self.line_spacing = line_spacing

        self.scroll: int = 0
        self.max_scroll: int = 0
        self.content_width: int = 0
        self.line_heights: list[int] = []
        self._anim_t: float = 0.0
        self.link_rects: list[tuple[pygame.Rect, str]] = []
        # (name, rect, target_height) so animated frames are scaled to match the text
        self.image_items: list[tuple[str, pygame.Rect, int]] = []
        self._scaled_icons: dict[tuple[str, int], list[pygame.Surface]] = {}
        self._content: pygame.Surface | None = None
        # (kind, detail) measured in _bake(), reported from draw() - see _report_layout()
        self._layout_issues: list[tuple[str, str]] = []

        self._text = text
        self.tokens: list[Token] = parse(text, self.base_style, extra_emojis=self.extra_emojis)
        self._bake()

    #############################################################################################################
    # MARK: text / layout

    def set_text(self, text: str) -> None:
        if text == self._text:
            return
        self._text = text
        self.tokens = parse(text, self.base_style, extra_emojis=self.extra_emojis)
        self.scroll = 0
        self._bake()

    @property
    def content_surface(self) -> pygame.Surface | None:
        """The full (unclipped) laid-out **text** surface; height == total content height.

        Text only - inline icons are not in here. :meth:`draw` blits them on top
        each frame so they can animate. A caller that takes this surface and
        blits it itself gets no icons at all; it wants :meth:`render_static`.
        """
        return self._content

    def render_static(self) -> pygame.Surface:
        """Text *and* icons baked into one surface, for callers that cache and blit.

        ``content_surface`` carries no icons, which is invisible until you look:
        the layout still reserves their width, so the text spaces itself out
        around an icon that never arrives. Reward chips and toasts both cached
        ``content_surface`` and had been dropping every icon silently.

        Animated icons freeze on their first frame - the price of a cached
        surface, and the reason this is a separate method rather than the default.
        """
        assert self._content is not None
        # an icon is nudged up to sit centred against the text, so it can start
        # above y=0 and would be clipped away by a naive blit
        top = min([r.y for _, r, _ in self.image_items] + [0])
        bottom = max([r.bottom for _, r, _ in self.image_items] + [self._content.get_height()])

        surf = pygame.Surface((self._content.get_width(), bottom - top), pygame.SRCALPHA)
        surf.blit(self._content, (0, -top))
        for name, crect, target_h in self.image_items:
            frames = self._icon_frames(name, target_h)
            if frames:
                surf.blit(frames[0], (crect.x, crect.y - top))
        return surf

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
                _w, h = frame.get_size()
                frames.append(pygame.transform.scale_by(frame, _icon_factor(h, target_h)))
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
                font_h = theme.get_font(tok.style.size).get_height()
                target_h = round(font_h * self._icon_scale)
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
                adj = (h - font_h) // 2  # upward offset to vertically center the icon over text
                items.append({"kind": "image", "name": tok.value, "x": x, "w": w, "h": h,
                              "th": target_h, "link": tok.style.link, "adj": adj})
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
        n_lines = len(lines)
        total_h = (
            sum(line["height"] for line in lines) + self.line_spacing * max(0, n_lines - 1)
        ) or self._default_line_height()

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
                    adj = it.get("adj", 0)
                    rect = pygame.Rect(ix, y - adj, it["w"], it["h"])
                    self.image_items.append((it["name"], rect, it["th"]))
                if it["link"]:
                    self.link_rects.append((rect, it["link"]))
            y += line["height"] + self.line_spacing

        self._content = content
        # per-line heights, so a caller capping at N lines can cut on a boundary.
        # A line is as tall as its tallest item, which is not the font's height:
        # a shadow or an inline icon makes it taller, and guessing from the font
        # slices the last line through the middle of its glyphs.
        self.line_heights = [int(line["height"]) for line in lines]
        self.content_width = max((line["width"] for line in lines), default=0)
        self.max_scroll = max(0, total_h - self.rect.height)
        self.scroll = min(self.scroll, self.max_scroll)
        self._measure_layout(total_h)

    #############################################################################################################
    # MARK: layout self-checks

    def _measure_layout(self, total_h: int) -> None:
        """Record (do not yet report) how the baked content fits its rect.

        Word wrap keeps lines inside ``rect.width``, so a too-wide line means a single
        unbreakable item - a long word or an inline icon - that no wrap can save; that
        one really does paint over the frame. Height is only a violation when nothing
        can scroll: with a scrollbar, more content than viewport is the *designed*
        behaviour, not a bug.

        Measured here (once per layout) but reported from :meth:`draw`, because a
        RichText built purely to measure text - ``render_static`` callers like the HUD
        toasts or the quest panel's ``_fit_line`` binary search - is never drawn and
        must not raise alarms about intermediate candidates.
        """
        issues: list[tuple[str, str]] = []
        if self.content_width > self.rect.width:
            issues.append((
                "h-overflow",
                f"longest line {self.content_width}px > {self.rect.width}px available "
                f"(unbreakable word or inline icon)",
            ))
        if total_h > self.rect.height and not self.show_scrollbar:
            issues.append((
                "v-overflow",
                f"content {total_h}px tall > {self.rect.height}px available, no scrollbar",
            ))
        self._layout_issues = issues

    def _report_layout(self) -> None:
        if not self._layout_issues:
            return
        from ..layout import report_violation
        label = self.name or f"'{self._text[:24]}'"
        for kind, detail in self._layout_issues:
            report_violation(f"{type(self).__name__}({label})", kind, detail)

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
        self._report_layout()
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
        from . import bar  # local import: bar imports theme, avoid load-order churn
        view = self.rect
        total = view.height + self.max_scroll
        bar.draw_scrollbar(
            surface, (view.right - _SCROLLBAR_W - 2, view.y, _SCROLLBAR_W, view.height),
            frac_visible=view.height / total,
            frac_pos=self.scroll / self.max_scroll,
        )


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
            target_h = round(theme.get_font(tok.style.size).get_height() * _ICON_SCALE)
            src = icons.get(tok.value, [])
            if not src:
                continue
            w0, h0 = src[0].get_size()
            k = _icon_factor(h0, target_h)  # integer scale: keep pixel-art crisp
            w, h = w0 * k, h0 * k
            if items and x + pending_space + w > max_width:
                flush()
            if items:
                x += pending_space
            pending_space = 0
            font_h = theme.get_font(tok.style.size).get_height()
            adj = (h - font_h) // 2
            items.append({"kind": "image", "name": tok.value, "x": x, "w": w, "h": h, "adj": adj})
            x += w
            line_h = max(line_h, h)
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
                    _w0, h0 = frame.get_size()
                    scaled = pygame.transform.scale_by(frame, _icon_factor(h0, it["h"]))
                    adj = it.get("adj", 0)
                    surface.blit(scaled, (ox + it["x"], y - adj))
        y += line["height"]

    return surface
