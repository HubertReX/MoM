"""Rich-text styling and markup parsing."""
from __future__ import annotations

from .markup import Token, parse, strip_tags
from .style import Style

__all__ = ["Token", "parse", "strip_tags", "Style"]
