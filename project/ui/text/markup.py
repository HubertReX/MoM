"""Markup parser: BBCode-like tags + inline emoji into styled tokens.

Tag -> style mappings are derived from ``STYLE_TAGS_DICT`` in settings.py (the same
table the old sftext path used), so existing dialog files render identically without
edits. Supported, nestable tags: h1/h2/h3, shadow, dark, light, bold|b, italic|i,
underline|u, big, small, left|right|center, the colour tags (act, char, item, loc,
num, quest, text, error) and ``[link URL]...[/link]``. ``:name:`` becomes an inline
image when ``name`` is a known emoji.

``[/]`` closes the innermost open tag, so ``[char]Kowal[/]`` needs no repetition
of the name. ``[/name]`` still works and still closes that specific tag.
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
# Named groups, not positions: this pattern has grown a branch before, and every
# time it does, `m.group(4)` silently starts meaning something else.
_TOKEN_RE = re.compile(
    r"\[(?P<slash>/?)(?P<name>" + "|".join(re.escape(n) for n in _TAG_NAMES) + r")"
    r"(?: (?P<arg>[^\]]*))?\]"
    r"|(?P<close_last>\[/\])"  # bare closer: pops whatever tag is innermost
    r"|:(?P<emoji>[\w$]+):"    # emoji names may contain '$' (e.g. :$_anim:)
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


def parse(
    text: str, base: Style | None = None, *, extra_emojis: frozenset[str] = frozenset()
) -> list[Token]:
    """Parse markup ``text`` into a flat list of styled tokens.

    ``extra_emojis`` widens the set of ``:name:`` markers that become images -
    the emote sheet is speech bubbles, so a caller wanting item sprites inline
    (a coin next to a reward) has to say so. Opt-in per call site, because a name
    that becomes an image token but has no frames renders as *nothing*: whoever
    widens the set has to supply the matching icons.
    """
    base = base or Style()
    known_emojis = _EMOJIS | extra_emojis
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

        emoji = m.group("emoji")
        if emoji is not None:
            if emoji in known_emojis:
                tokens.append(Token("image", emoji, current()))
            else:
                _emit_text(tokens, m.group(0), current())  # unknown -> literal
            continue

        # `[/]` closes whatever is innermost, so `[h3][char]X[/][/]` reads left to
        # right without naming anything twice.
        if m.group("close_last") is not None:
            if stack:
                stack.pop()
            else:
                # `\[` escapes the bracket for rich: without it rich reads our own
                # error text as *its* markup and raises MarkupError, so a typo in a
                # dialog blew up in the handler meant to report it.
                print(r"[red]ERROR[/] markup: closing tag \[/] without matching open tag")
            continue

        slash, name, arg = m.group("slash"), m.group("name"), m.group("arg")
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
                print(rf"[red]ERROR[/] markup: closing tag \[/{name}] without matching open tag")

    if pos < len(text):
        _emit_text(tokens, text[pos:], current())
    return tokens


def strip_tags(text: str) -> str:
    """Return ``text`` with all tags and emoji markers removed (for measuring)."""
    return _TOKEN_RE.sub("", text)


def cut_markup(markup: str, n_chars: int, ellipsis: str = "...") -> str:
    """Keep the first ``n_chars`` characters of *text*, then close and ellipsise.

    Tags cost nothing and are copied through; only rendered characters count. Any
    tag still open at the cut is closed, innermost first, so the result is valid
    markup and the ellipsis inherits the styling of the text it replaces::

        cut_markup("[char]Kowal Kłamca[/char] kuje", 8) -> "[char]Kowal Kł...[/char]"

    Truncating the *plain* text and re-tagging it is not an option: a cut can land
    inside a tag, and the ellipsis has to end up inside the styling rather than
    dangling after a stray ``[/char]``.

    Emoji markers are atomic and free - a title is text, and charging them would
    only make the caller's search over ``n_chars`` lumpy.
    """
    out: list[str] = []
    stack: list[str] = []
    used = 0
    pos = 0
    truncated = False

    def take(text: str) -> bool:
        """Append what fits; True when the budget ran out mid-text."""
        nonlocal used
        room = n_chars - used
        chunk = text[:max(0, room)]
        out.append(chunk)
        used += len(chunk)
        return len(chunk) < len(text)

    for m in _TOKEN_RE.finditer(markup):
        if m.start() > pos and take(markup[pos:m.start()]):
            truncated = True
            break
        pos = m.end()

        if m.group("emoji") is not None:
            out.append(m.group(0))
            continue

        if m.group("close_last") is not None:
            if stack:
                stack.pop()
            out.append(m.group(0))
            continue

        name = m.group("name")
        if m.group("slash"):
            for i in range(len(stack) - 1, -1, -1):
                if stack[i] == name:
                    del stack[i]
                    break
        else:
            stack.append(name)
        out.append(m.group(0))
    else:
        if pos < len(markup) and take(markup[pos:]):
            truncated = True

    if truncated:
        out.append(ellipsis)
    out.extend(f"[/{name}]" for name in reversed(stack))
    return "".join(out)
