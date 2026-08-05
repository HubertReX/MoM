#!/usr/bin/env python3
"""Split shell commands into their component commands, quote-aware.

Shared by `codegraph_impact.py` (transcript analysis) and `hook_codegraph_reminder.py`
(PreToolUse hook) so the two cannot drift apart - they must agree on what counts as a
search command and what its pattern is.

The naive approach - `re.split(r'\\||&&|;', command)` - is wrong in a way that is easy to
miss: it cuts inside quoted strings. `rg "def load_map|def load_NPCs"` becomes
`rg "def load_map` and `def load_NPCs"`, so an alternation pattern (very common when
hunting for a symbol) is silently truncated to its first branch. `shlex` with
`punctuation_chars` tokenises operators while respecting quotes, which is the fix.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

# Prefixes that wrap a real command without being one.
WRAPPERS = {"sudo", "nohup", "env", "builtin", "rtk", "proxy", "\\", "command"}
# Wrappers that swallow one argument first (`gtimeout 60 pytest`).
WRAPPERS_WITH_ARG = {"gtimeout", "timeout", "xargs", "time"}
OPERATORS = {"|", "||", "&&", ";", "&", ">", ">>", "<", "(", ")"}
DURATION = re.compile(r"[\d.]+[smh]?")


def _strip_prefixes(tokens: list[str]) -> list[str]:
    """Drop env assignments and wrapper commands until the real command is at index 0."""
    while tokens:
        head = Path(tokens[0]).name
        if ("=" in tokens[0] and not tokens[0].startswith("-")) or head in WRAPPERS:
            tokens.pop(0)
        elif head in WRAPPERS_WITH_ARG:
            tokens.pop(0)
            while tokens and (tokens[0].startswith("-") or DURATION.fullmatch(tokens[0])):
                tokens.pop(0)
        else:
            break
    return tokens


def segments(command: str) -> list[list[str]]:
    """Return one token list per command in the pipeline, prefixes stripped.

    Falls back to a whitespace split when the command does not lex (unbalanced quotes
    happen in real transcripts); the caller should treat the result as best-effort.
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = command.split()
    out: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in OPERATORS:
            if current and (stripped := _strip_prefixes(current)):
                out.append(stripped)
            current = []
        else:
            current.append(token)
    if current and (stripped := _strip_prefixes(current)):
        out.append(stripped)
    return out
