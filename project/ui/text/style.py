"""Text style model for the rich-text renderer.

A :class:`Style` is the fully-resolved set of attributes for one run of text or one
inline image. Markup tags mutate a stack of styles; each emitted token carries an
immutable snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from ..theme import DEFAULT_SHADOW_COLOR, DEFAULT_SHADOW_OFFSET, DEFAULT_TEXT_COLOR

Color = tuple[int, int, int] | tuple[int, int, int, int]


@dataclass
class Style:
    size: int = 20
    color: Color = DEFAULT_TEXT_COLOR
    bold: bool = False
    italic: bool = False
    underline: bool = False
    shadow: bool = False                       # maps to sftext "cast_shadow"
    shadow_color: Color = DEFAULT_SHADOW_COLOR
    shadow_offset: tuple[int, int] = DEFAULT_SHADOW_OFFSET
    align: str = "left"                        # left | center | right
    link: str | None = None

    def copy(self) -> "Style":
        return replace(self)

    def apply(self, mutation: dict[str, object]) -> "Style":
        """Return a new style with ``mutation`` fields overridden."""
        return replace(self, **mutation)  # type: ignore[arg-type]
