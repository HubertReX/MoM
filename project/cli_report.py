"""One table for every authoring CLI (`just import-*`, `just validate-world`).

The authoring commands are read by a human in a terminal, one after another in
the same cascade (`import-dialogs` -> `import-entities` -> `validate-world`).
When each of them invents its own line format the output stops being a report
and becomes a wall: absolute paths repeated on every line, warnings from three
programs interleaved, and no way to tell at a glance what is an error and what
is a note. So they all draw the same three-column table - severity, where, what
- and say the rest in one summary line underneath.

`rich` is optional on purpose: the information is the point, the colour is not,
so a bare environment gets plain lines instead of a crash.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

ERROR = "ERROR"
WARN = "WARN"


@dataclass(slots=True)
class Diagnostic:
    """One problem, collected rather than printed where it is found.

    Collecting is what makes the table possible: a list can be sorted (errors
    first), counted, and drawn after the run, while a `print` deep inside a
    parser lands in the middle of whatever else is writing to the terminal.
    """

    severity: str  # ERROR or WARN
    source: str  # where the author has to go: a key, or `PL/Postacie/Kuba.md:16`
    message: str  # what is wrong, without the path prefix - that is `source`


def rel(path: str | Path) -> str:
    """The path as the author knows it: relative to the current directory.

    Every row of a table carries the same absolute prefix, which says nothing
    and pushes the part that matters off the right edge of the screen.
    """
    try:
        shown = os.path.relpath(Path(path), Path.cwd())
    except ValueError:  # different drive on Windows
        return str(path)
    # A path outside the repo reads better absolute than as a stack of `../`
    return str(path) if shown.startswith("..") else shown


def report_table(title: str, diagnostics: Sequence[Diagnostic], *, stderr: bool = True) -> None:
    """Draw the collected diagnostics as one table. Nothing to say = nothing printed.

    Goes to stderr by default so a `--json` stdout stays machine-readable.
    """
    if not diagnostics:
        return

    # errors first, then by source, so the fix list reads top to bottom
    # casing is the caller's business, not the reader's: `error`/`ERROR` sort
    # and colour the same and both print as ERROR
    rows = sorted(
        diagnostics, key=lambda d: (d.severity.upper() != ERROR, d.source, d.message)
    )
    stream = sys.stderr if stderr else sys.stdout

    try:
        from rich.console import Console
        from rich.markup import escape
        from rich.table import Table
    except ImportError:
        for diagnostic in rows:
            print(
                f"{diagnostic.severity.upper():7} {diagnostic.source}  {diagnostic.message}",
                file=stream,
            )
        return

    console = Console(stderr=stderr)
    table = Table(title=title, header_style="bold", show_lines=False)
    table.add_column("Severity", no_wrap=True)
    table.add_column("Source", style="cyan", no_wrap=True)
    table.add_column("Problem")
    for diagnostic in rows:
        severity = diagnostic.severity.upper()
        colour = "red" if severity == ERROR else "yellow"
        # escaped: a message quotes author text (`[[#trade-end]]`, `[char]`),
        # which rich would otherwise read as its own markup
        table.add_row(
            f"[{colour}]{severity}[/{colour}]",
            escape(diagnostic.source),
            escape(diagnostic.message),
        )
    console.print(table)
