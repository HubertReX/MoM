#!/usr/bin/env python3
"""PreToolUse hook: nudge toward codegraph_explore on the first symbol grep of a session.

Why this exists: the "use CodeGraph before grepping" rule lived in CLAUDE.md and was
followed in 12 of 28 sessions (see doc/codegraph-wplyw-2026-08-05.md). A prompt-level
rule is a suggestion; a hook always runs.

Deliberately a REMINDER, not a block. It never denies the command and never modifies it -
it only injects one line of context, at most once per session. Grep is the right tool for
plenty of things (strings in CSV, patterns in logs, "which file mentions X"), so blocking
would cost more than it saves. The goal is to change where a *code* investigation starts.

Fires only when all of these hold:
  - the command actually runs rg/grep (not merely mentions it)
  - the search pattern looks like a Python symbol - snake_case, CamelCase, or `def`/`class`
  - the search is not scoped to non-Python files (-t md, --glob '*.json', a doc/ path, ...)
  - the repo has a CodeGraph index (.codegraph/), so the advice is actionable
  - nothing has fired yet in this session

Any unexpected input is a silent no-op: a hook that breaks a tool call is worse than a
hook that misses one.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shell_parse import segments  # noqa: E402

SEARCH_CMDS = {"rg", "grep", "ugrep", "ag"}
FLAGS_WITH_ARG = {"-g", "--glob", "-t", "--type", "-A", "-B", "-C", "-m", "--max-count",
                  "-f", "--file", "--iglob"}
PATTERN_FLAGS = {"-e", "--regexp"}

# If the search is aimed at these, it is not a code-navigation question.
NON_PYTHON_HINTS = re.compile(
    r"(-t\s*(md|markdown|json|csv|toml|yaml|yml|html|js|ts)\b"
    r"|--type[= ](md|markdown|json|csv|toml|yaml|yml|html|js|ts)\b"
    r"|--i?glob[= ]?['\"]?\*?\.(md|json|csv|toml|yaml|yml|html|txt|log|jsonl)"
    r"|\.(md|json|csv|toml|yaml|yml|html|txt|log|jsonl)\b)")
# Regex metacharacters that carry no identifier information.
REGEX_NOISE = re.compile(r"[\\^$()\[\]{}?*+]|\\b|\\s|\\w|\\d")
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DEF_OR_CLASS = re.compile(r"\b(def|class)\s+[A-Za-z_]")
MIN_SYMBOL_LEN = 4


def search_patterns(command):
    """Return the pattern argument of every rg/grep segment (flags and paths excluded)."""
    found = []
    for tokens in segments(command):
        if Path(tokens[0]).name not in SEARCH_CMDS:
            continue
        i = 1
        while i < len(tokens):
            token = tokens[i]
            if token.startswith("-"):
                if token in PATTERN_FLAGS and i + 1 < len(tokens):
                    found.append(tokens[i + 1])
                    i += 2
                    continue
                i += 2 if token in FLAGS_WITH_ARG else 1
                continue
            found.append(token)  # first non-flag argument is the pattern
            break
    return found


def looks_like_python_symbol(pattern):
    """True when the pattern is plausibly a function/class/attribute name.

    Requires snake_case, CamelCase, or an explicit `def`/`class` prefix. A bare lowercase
    word ("error", "color") does not qualify - those are usually string searches, and
    firing on them would train the reader to ignore this hook.
    """
    if DEF_OR_CLASS.search(pattern):
        return True
    cleaned = REGEX_NOISE.sub(" ", pattern)
    for token in re.split(r"[|\s,]+", cleaned):
        token = token.strip(".:'\"")
        if len(token) < MIN_SYMBOL_LEN or not IDENTIFIER.match(token):
            continue
        if "_" in token.strip("_"):
            return True
        if re.search(r"[a-z][A-Z]", token):  # CamelCase / mixedCase
            return True
    return False


def already_fired(session_id):
    """One nudge per session. Repeating it every grep would be noise, not a signal."""
    if not session_id:
        return False
    marker = Path(tempfile.gettempdir()) / "claude-codegraph-hook" / f"{session_id}"
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        # O_EXCL makes create-or-fail atomic, so parallel tool calls cannot both fire.
        os.close(os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        return False
    except FileExistsError:
        return True
    except OSError:
        return False


REMINDER = (
    "Wyszukujesz symbol Pythona przez grep. To repo ma indeks CodeGraph - "
    "`codegraph_explore` zwraca zrodlo tego symbolu, jego wywolania i blast radius "
    "w jednym wywolaniu, zamiast serii grepow i Readow. Rozwaz zaczecie stamtad. "
    "Grep zostaje wlasciwym narzedziem do stringow, CSV, logow i pytan "
    "\"ktory plik wspomina X\" - to przypomnienie pojawia sie raz na sesje."
)


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    if payload.get("tool_name") != "Bash":
        return
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not command or NON_PYTHON_HINTS.search(command):
        return
    if not any(looks_like_python_symbol(p) for p in search_patterns(command)):
        return
    # Only advise what the project can actually do.
    if not (Path.cwd() / ".codegraph").is_dir():
        return
    if already_fired(payload.get("session_id")):
        return
    json.dump({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": REMINDER,
        },
        "suppressOutput": True,
    }, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - a hook must never break the tool call
        pass
