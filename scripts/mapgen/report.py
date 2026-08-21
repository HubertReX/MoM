#!/usr/bin/env python3
"""Kolorowa tabela wyników dla narzędzi mapowych.

Ten sam wzorzec, co `validate_world.report_table`: `rich.Table` z kolorami, a gdy
`rich` jest niedostępny - zwykły `print` wiersz po wierszu. Degradacja jest tu
istotna, nie ozdobna: raport nigdy nie ma prawa wywalić skryptu w CI ani na
gołym interpreterze, bo wtedy zamiast diagnozy dostajemy traceback.

Kolumna `waga` mówi o SKUTKU dla gry, nie o trudności poprawki:

    error  gra tego nie wczyta, `validate-world` nie przejdzie albo NPC nie powstanie
    warn   działa, ale gorzej - cisza zamiast muzyki, surowy klucz, monotonia
    info   potwierdzenie, że coś zostało obsłużone (nie ma nic do zrobienia)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

ERROR, WARN, INFO, OK = "error", "warn", "info", "ok"

_COLORS: dict[str, str] = {ERROR: "red", WARN: "yellow", INFO: "cyan", OK: "green"}
_LABELS: dict[str, str] = {ERROR: "ERROR", WARN: "WARN", INFO: "INFO", OK: "OK"}
_ORDER: dict[str, int] = {ERROR: 0, WARN: 1, OK: 2, INFO: 3}


@dataclass
class Row:
    """Jedna linia raportu. `where` to współrzędne w kaflach, gdy problem ma miejsce."""

    level: str = INFO
    source: str = ""
    key: str = ""
    message: str = ""
    where: tuple[int, int] | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "source": self.source,
            "key": self.key,
            "message": self.message,
            "where": list(self.where) if self.where else None,
            **({"data": self.data} if self.data else {}),
        }


def sort_rows(rows: Iterable[Row]) -> list[Row]:
    """Najpierw błędy, potem po źródle - lista poprawek ma się czytać z góry na dół."""
    return sorted(rows, key=lambda r: (_ORDER.get(r.level, 9), r.source, r.key, r.message))


def counts(rows: Iterable[Row]) -> dict[str, int]:
    tally = {ERROR: 0, WARN: 0, INFO: 0, OK: 0}
    for row in rows:
        tally[row.level] = tally.get(row.level, 0) + 1
    return tally


def summary_line(rows: Iterable[Row]) -> str:
    tally = counts(rows)
    parts = [f"{tally[ERROR]} errors", f"{tally[WARN]} warnings"]
    if tally[INFO]:
        parts.append(f"{tally[INFO]} info")
    return ", ".join(parts)


def report(rows: Iterable[Row], title: str = "", summary: str = "",
           show_key: bool = True) -> None:
    rows = sort_rows(rows)
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        _plain(rows, title, summary)
        return

    console = Console()
    if not rows:
        if title:
            console.print(f"[bold]{title}[/bold]")
        console.print(f"[green]{summary or 'nic do zgłoszenia'}[/green]")
        return

    table = Table(title=title or None, header_style="bold", show_lines=False)
    table.add_column("Waga", no_wrap=True)
    table.add_column("Źródło", no_wrap=True, style="cyan")
    if show_key:
        table.add_column("Klucz", no_wrap=True, style="magenta")
    table.add_column("Miejsce", no_wrap=True, style="dim")
    table.add_column("Co jest / co dopisać")

    for row in rows:
        colour = _COLORS.get(row.level, "white")
        label = _LABELS.get(row.level, row.level.upper())
        where = f"{row.where[0]},{row.where[1]}" if row.where else ""
        cells = [f"[{colour}]{label}[/{colour}]", row.source]
        if show_key:
            cells.append(row.key)
        cells.extend([where, row.message])
        table.add_row(*cells)

    console.print(table)
    console.print(summary or summary_line(rows))


def _plain(rows: list[Row], title: str, summary: str) -> None:
    if title:
        print(title)
    for row in rows:
        where = f" ({row.where[0]},{row.where[1]})" if row.where else ""
        key = f"  {row.key}" if row.key else ""
        print(f"{_LABELS.get(row.level, row.level).upper():5}  {row.source}{key}{where}  {row.message}")
    print(summary or summary_line(rows))
