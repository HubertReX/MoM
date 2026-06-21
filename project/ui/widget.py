"""Base retained-mode widget.

A ``Widget`` owns a ``rect`` (absolute position on the target surface) and a cached
render surface. ``render()`` is only called when the widget is marked dirty, so a
static widget costs a single blit per frame instead of re-allocating surfaces.

Widgets form a tree: a parent draws itself, then its children. Event handling walks
children topmost-first and stops at the first consumer.
"""
from __future__ import annotations

import pygame


class Widget:
    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int] | None = None,
        *,
        visible: bool = True,
        enabled: bool = True,
    ) -> None:
        self.rect: pygame.Rect = pygame.Rect(rect) if rect is not None else pygame.Rect(0, 0, 0, 0)
        self.visible: bool = visible
        self.enabled: bool = enabled
        self.parent: Widget | None = None
        self.children: list[Widget] = []
        self._dirty: bool = True
        self._cache: pygame.Surface | None = None

    #############################################################################################################
    def add(self, child: Widget) -> Widget:
        """Attach a child widget and return it (for fluent construction)."""
        child.parent = self
        self.children.append(child)
        return child

    def remove(self, child: Widget) -> None:
        if child in self.children:
            child.parent = None
            self.children.remove(child)

    #############################################################################################################
    def mark_dirty(self) -> None:
        """Force this widget to re-render on the next draw."""
        self._dirty = True

    def set_visible(self, value: bool) -> None:
        self.visible = value

    #############################################################################################################
    def render(self) -> pygame.Surface | None:
        """Produce the widget's own surface (size of ``self.rect``).

        Override in subclasses. Returning ``None`` means "nothing of my own to draw"
        (e.g. a pure container) and only children are drawn.
        """
        return None

    def _ensure_cache(self) -> pygame.Surface | None:
        if self._dirty or self._cache is None:
            self._cache = self.render()
            self._dirty = False
        return self._cache

    #############################################################################################################
    def draw(self, surface: pygame.Surface) -> None:
        """Blit this widget's cached surface, then draw children."""
        if not self.visible:
            return
        own = self._ensure_cache()
        if own is not None:
            surface.blit(own, self.rect.topleft)
        for child in self.children:
            child.draw(surface)

    #############################################################################################################
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return ``True`` if the event was consumed.

        Default behaviour: offer the event to children (topmost first), then to
        ``self`` via :meth:`_on_event`.
        """
        if not (self.visible and self.enabled):
            return False
        for child in reversed(self.children):
            if child.handle_event(event):
                return True
        return self._on_event(event)

    def _on_event(self, event: pygame.event.Event) -> bool:
        return False

    #############################################################################################################
    def update(self, dt: float) -> None:
        """Per-frame logic hook (animations, hover). Override as needed."""
        for child in self.children:
            child.update(dt)
