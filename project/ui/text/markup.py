"""Markup parser: BBCode-like tags + inline emoji into styled tokens.

Tag -> style mappings are derived from ``STYLE_TAGS_DICT`` in settings.py (the same
table the old sftext path used), so existing dialog files render identically without
edits. Supported, nestable tags: h1/h2/h3, shadow, dark, light, bold|b, italic|i,
underline|u, big, small, left|right|center, the colour tags (act, char, item, loc,
num, quest, text, error) and ``[link URL]...[/link]``. ``:name:`` becomes an inline
image when ``name`` is a known emoji.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from rich import print

from settings import EMOTE_SHEET_DEFINITION, STYLE_TAGS_DICT

from .style import Style


@dataclass
class Token:
    kind: str        # "text" | "image" | "newline"
    value: str       # text content, emoji name, or "" for newline
    style: Style


#######################################################################################################################
# MARK: tag table (derived from STYLE_TAGS_DICT)

_FIELD_RE = re.compile(r"\{(\w+) ([^}]+)\}")


def _parse_color(value: str) -> tuple[int, ...]:
    return tuple(int(n) for n in value.strip().strip("()").split(","))


def _translate(sftext_value: str) -> dict[str, object]:
    """Translate an sftext-format style string into Style-field overrides."""
    mutation: dict[str, object] = {}
    for key, val in _FIELD_RE.findall(sftext_value):
        val = val.strip()
        if key == "align":
            mutation["align"] = val
        elif key == "size":
            mutation["size"] = int(val)
        elif key == "cast_shadow":
            mutation["shadow"] = val == "True"
        elif key == "shadow_color":
            mutation["shadow_color"] = _parse_color(val)
        elif key == "color":
            mutation["color"] = _parse_color(val)
        elif key == "bold":
            mutation["bold"] = val == "True"
        elif key == "italic":
            mutation["italic"] = val == "True"
        elif key == "underline":
            mutation["underline"] = val == "True"
        # "link" is handled per-instance (URL comes from the tag argument)
    return mutation


def _build_tag_styles() -> dict[str, dict[str, object]]:
    table: dict[str, dict[str, object]] = {}
    for key, value in STYLE_TAGS_DICT.items():
        name = "link" if key.startswith("link") else key
        table[name] = _translate(value)
    table.setdefault("link", {"underline": True})
    return table


TAG_STYLES: dict[str, dict[str, object]] = _build_tag_styles()
_EMOJIS: frozenset[str] = frozenset(EMOTE_SHEET_DEFINITION)

# longer names first so "[bold]" is not shadowed by "[b]"
_TAG_NAMES = sorted(TAG_STYLES.keys(), key=len, reverse=True)
_TOKEN_RE = re.compile(
    r"\[(/?)(" + "|".join(re.escape(n) for n in _TAG_NAMES) + r")(?: ([^\]]*))?\]"
    r"|:([\w$]+):"  # emoji names may contain '$' (e.g. :$_anim:)
)


#######################################################################################################################
# MARK: parse


def _emit_text(tokens: list[Token], text: str, style: Style) -> None:
    parts = text.split("\n")
    for i, part in enumerate(parts):
        if i > 0:
            tokens.append(Token("newline", "", style))
        if part:
            tokens.append(Token("text", part, style))


def parse(text: str, base: Style | None = None) -> list[Token]:
    """Parse markup ``text`` into a flat list of styled tokens."""
    base = base or Style()
    tokens: list[Token] = []
    stack: list[tuple[str, dict[str, object]]] = []

    def current() -> Style:
        s = base.copy()
        for _, mutation in stack:
            s = s.apply(mutation)
        return s

    pos = 0
    for m in _TOKEN_RE.finditer(text):
        if m.start() > pos:
            _emit_text(tokens, text[pos:m.start()], current())
        pos = m.end()

        emoji = m.group(4)
        if emoji is not None:
            if emoji in _EMOJIS:
                tokens.append(Token("image", emoji, current()))
            else:
                _emit_text(tokens, m.group(0), current())  # unknown -> literal
            continue

        slash, name, arg = m.group(1), m.group(2), m.group(3)
        if not slash:
            mutation = dict(TAG_STYLES.get(name, {}))
            if name == "link":
                mutation["link"] = (arg or "").strip() or None
            stack.append((name, mutation))
        else:
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == name:
                    del stack[i]
                    break
            else:
                print(f"[red]ERROR[/] markup: closing tag [/{name}] without matching open tag")

    if pos < len(text):
        _emit_text(tokens, text[pos:], current())
    return tokens


def strip_tags(text: str) -> str:
    """Return ``text`` with all tags and emoji markers removed (for measuring)."""
    return _TOKEN_RE.sub("", text)
