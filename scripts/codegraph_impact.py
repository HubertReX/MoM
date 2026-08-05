#!/usr/bin/env python3
"""Measure how a tool adoption (CodeGraph) changed Claude Code's work profile.

Reads the raw Claude Code session transcripts (`~/.claude/projects/<slug>/*.jsonl`)
for this repo and compares two eras split by `--cutoff`. Written for the CodeGraph
before/after benchmark (`doc/codegraph-benchmark-baseline-2026-07-20.md` and
`doc/codegraph-wplyw-2026-08-05.md`), but the split date is a parameter, so it works
for any "did installing X change anything" question.

Three things it does that a naive `grep tool_use | wc -l` does not:

1. Single-label Bash classification over *segments*. A command like
   `MOM_DEBUG=1 rtk proxy rg "foo" project/ | head -20` is one search, not one
   "other" and one "readcmd". The baseline doc classified on the first word and
   dumped 16% into a catch-all, which is why its published percentages do not
   match this script's - see the methodology note in the follow-up doc.

2. Normalisation per edit. Raw counts track how much work happened, not how
   efficiently. `search/edit` and `nav/edit` survive sessions of different size;
   percentage-of-Bash does not (when runtime work grows, the search share falls
   without any navigation actually improving).

3. Repeated-symbol detection from the search PATTERN only. Extracting identifiers
   from the whole command line picks up path fragments (`Projects`, `hubertnafalski`)
   and saturates the metric at ~100% in both eras, making it useless. Only the
   pattern argument counts - flags, globs and paths are stripped.

Usage:
    .venv/bin/python scripts/codegraph_impact.py                    # full report
    .venv/bin/python scripts/codegraph_impact.py --cutoff 2026-07-21
    .venv/bin/python scripts/codegraph_impact.py --min-size 1.7     # large sessions only
    .venv/bin/python scripts/codegraph_impact.py --per-session      # add the session table
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shell_parse import segments as split_segments  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
# Claude Code stores transcripts under a slug built from the absolute project path.
TRANSCRIPTS = Path.home() / ".claude" / "projects" / str(REPO).replace("/", "-")

SEARCH_CMDS = {"rg", "grep", "ugrep", "ag"}
READ_CMDS = {"cat", "bat", "sed", "awk", "head", "tail", "jq", "less"}
RUN_CMDS = {"python", "python3", "pytest", "just", "uv", "npm", "npx", "node", "make"}
LS_CMDS = {"ls", "tree", "wc", "du", "eza", "stat", "file"}
VCS_CMDS = {"git", "gh", "yadm"}
FIND_CMDS = {"find", "fd"}

SYMBOL_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
# Words that appear in search patterns without being the symbol under investigation.
SYMBOL_NOISE = {
    "grep", "ugrep", "true", "false", "none", "self", "class", "import", "from",
    "return", "print", "type", "path", "file", "test", "null", "def",
}
# rg/grep flags that consume the following argument (so it is not the pattern).
FLAGS_WITH_ARG = {"-g", "--glob", "-t", "--type", "-A", "-B", "-C", "-m", "--max-count"}
PATTERN_FLAGS = {"-e", "--regexp"}

REPEAT_THRESHOLD = 3   # "searched the same symbol N+ times" / "re-read the same file N+ times"
MIN_SEARCHES = 10      # sessions below this are too short for the repeat metric to mean anything


@dataclass
class Session:
    """Tool-use metrics for one transcript."""

    name: str
    start: datetime
    size: int
    tools: Counter = field(default_factory=Counter)
    bash_cat: Counter = field(default_factory=Counter)
    bash_total: int = 0
    tokens: Counter = field(default_factory=Counter)
    turns: int = 0
    cg_queries: list[str] = field(default_factory=list)
    search_patterns: list[str] = field(default_factory=list)
    read_files: Counter = field(default_factory=Counter)

    @property
    def edits(self) -> int:
        return self.tools["Edit"] + self.tools["Write"]

    @property
    def searches(self) -> int:
        return self.bash_cat["search"] + self.tools["Grep"]

    @property
    def navigation(self) -> int:
        """Actions spent locating code rather than changing it."""
        return self.searches + self.bash_cat["find"] + self.bash_cat["readcmd"] + self.tools["Read"]

    @property
    def repeated_symbols(self) -> dict[str, int]:
        counts: Counter = Counter()
        for pattern in self.search_patterns:
            # Count each symbol once per pattern, so `rg "foo|foo_bar"` is not double-billed.
            for sym in {m for m in SYMBOL_RE.findall(pattern) if m.lower() not in SYMBOL_NOISE}:
                counts[sym] += 1
        return {s: c for s, c in counts.items() if c >= REPEAT_THRESHOLD}

    @property
    def reread_files(self) -> dict[str, int]:
        return {p: c for p, c in self.read_files.items() if c >= REPEAT_THRESHOLD}


def classify(command: str) -> str:
    """Assign one category to a whole Bash command, by priority across its segments."""
    segments = split_segments(command)
    if not segments:
        return "other"
    heads = {Path(seg[0]).name for seg in segments}
    first = Path(segments[0][0]).name
    # Priority order, deliberately search-first: a command is counted as navigation if it
    # searches anywhere in the pipeline. `python -c "..." | grep foo` is therefore a search,
    # not a run. That is the conservative choice for this benchmark - it inflates the
    # "before" search count as much as the "after" one, so it cannot manufacture an
    # improvement. Changing this order changes every published percentage.
    if "codegraph" in heads:
        return "codegraph"
    if heads & SEARCH_CMDS:
        return "search"
    if first == "cd":
        return "cd"
    if heads & FIND_CMDS:
        return "find"
    if first in READ_CMDS:
        return "readcmd"
    if heads & RUN_CMDS:
        return "run"
    if first in LS_CMDS:
        return "ls"
    if first in VCS_CMDS:
        return "git"
    return "other"


def extract_patterns(command: str) -> list[str]:
    """Pull the search pattern out of each rg/grep segment, skipping flags and paths."""
    patterns: list[str] = []
    for tokens in split_segments(command):
        if Path(tokens[0]).name not in SEARCH_CMDS:
            continue
        i = 1
        while i < len(tokens):
            token = tokens[i]
            if token.startswith("-"):
                if token in PATTERN_FLAGS and i + 1 < len(tokens):
                    patterns.append(tokens[i + 1])
                    i += 2
                    continue
                i += 2 if token in FLAGS_WITH_ARG else 1
                continue
            patterns.append(token)  # first non-flag argument is the pattern
            break
    return patterns


def parse(path: Path) -> Session | None:
    start: datetime | None = None
    session = Session(name=path.name, start=datetime.min.replace(tzinfo=timezone.utc),
                      size=path.stat().st_size)
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue  # transcripts can end mid-write while a session is live
            stamp = entry.get("timestamp")
            if stamp and start is None:
                try:
                    start = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                except ValueError:
                    pass
            message = entry.get("message") or {}
            usage = message.get("usage") or {}
            if usage and entry.get("type") == "assistant":
                session.turns += 1
                session.tokens["in"] += usage.get("input_tokens") or 0
                session.tokens["out"] += usage.get("output_tokens") or 0
                session.tokens["cache_read"] += usage.get("cache_read_input_tokens") or 0
                session.tokens["cache_write"] += usage.get("cache_creation_input_tokens") or 0
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = block.get("name", "?")
                params = block.get("input") or {}
                session.tools[name] += 1
                if name == "Bash":
                    session.bash_total += 1
                    command = params.get("command", "") or ""
                    category = classify(command)
                    session.bash_cat[category] += 1
                    if category == "search":
                        session.search_patterns.extend(extract_patterns(command))
                    elif category == "codegraph" and "explore" in command:
                        session.cg_queries.append(command[:160])
                elif "codegraph" in name.lower():
                    session.cg_queries.append(
                        str(params.get("query") or params.get("question") or params)[:160])
                elif name == "Grep":
                    session.search_patterns.append(str(params.get("pattern", "")))
                elif name == "Read":
                    if target := params.get("file_path"):
                        session.read_files[target] += 1
    if start is None or session.bash_total + session.tools["Read"] == 0:
        return None
    session.start = start
    return session


def ratios(group: list[Session]) -> dict[str, float]:
    edits = max(sum(s.edits for s in group), 1)
    turns = max(sum(s.turns for s in group), 1)
    return {
        "search/edit": sum(s.searches for s in group) / edits,
        "Read/edit": sum(s.tools["Read"] for s in group) / edits,
        "nav/edit": sum(s.navigation for s in group) / edits,
        "calls/turn": sum(sum(s.tools.values()) for s in group) / turns,
        "cache_read/turn": sum(s.tokens["cache_read"] for s in group) / turns,
        "out/turn": sum(s.tokens["out"] for s in group) / turns,
    }


def print_group(label: str, group: list[Session]) -> None:
    if not group:
        print(f"\n### {label}: brak sesji")
        return
    bash_total = sum(s.bash_total for s in group)
    categories: Counter = Counter()
    tools: Counter = Counter()
    for s in group:
        categories.update(s.bash_cat)
        tools.update(s.tools)
    print(f"\n### {label}  ({len(group)} sesji, {sum(s.size for s in group) / 1e6:.1f} MB, "
          f"{group[0].start:%Y-%m-%d} .. {max(s.start for s in group):%Y-%m-%d})")
    print(f"  Bash {bash_total}:", "  ".join(
        f"{k} {v} ({100 * v / max(bash_total, 1):.1f}%)" for k, v in categories.most_common()))
    print(f"  Read {tools['Read']}  Edit {tools['Edit']}  Write {tools['Write']}  "
          f"Grep {tools['Grep']}  Glob {tools['Glob']}")
    r = ratios(group)
    print(f"  search/edit {r['search/edit']:.2f}   Read/edit {r['Read/edit']:.2f}   "
          f"nav/edit {r['nav/edit']:.2f}   calls/tura {r['calls/turn']:.2f}   "
          f"cache_read/tura {r['cache_read/turn'] / 1e3:.0f}k   out/tura {r['out/turn']:.0f}")
    print(f"  mediany/sesja: Bash {median([s.bash_total for s in group]):.0f}  "
          f"search {median([s.searches for s in group]):.0f}  "
          f"Read {median([s.tools['Read'] for s in group]):.0f}  "
          f"Edit {median([s.edits for s in group]):.0f}")
    queries = sum(len(s.cg_queries) for s in group)
    users = sum(1 for s in group if s.cg_queries)
    print(f"  codegraph: {queries} zapytan w {users}/{len(group)} sesjach")
    # Repeat metric only over sessions long enough to have a meaningful denominator.
    long = [s for s in group if len(s.search_patterns) >= MIN_SEARCHES]
    if long:
        worst = sum(max(s.repeated_symbols.values(), default=0) for s in long) / len(long)
        patterns = max(sum(len(s.search_patterns) for s in long), 1)
        excess = sum(sum(c - 1 for c in s.repeated_symbols.values()) for s in long)
        print(f"  powtorki (n={len(long)} sesji >= {MIN_SEARCHES} wyszukiwan): "
              f"szukajace >= {REPEAT_THRESHOLD}x tego samego symbolu "
              f"{sum(1 for s in long if s.repeated_symbols)}/{len(long)}, "
              f"srednia max-krotnosc {worst:.1f}x, nadmiar/wzorzec {excess / patterns:.2f}")
        print(f"  czytajace >= {REPEAT_THRESHOLD}x ten sam plik: "
              f"{sum(1 for s in long if s.reread_files)}/{len(long)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cutoff", default="2026-07-21",
                    help="ISO date splitting 'before' from 'after' (default: CodeGraph install)")
    ap.add_argument("--min-size", type=float, default=0.0,
                    help="only sessions of at least N MB (controls for the size confound)")
    ap.add_argument("--transcripts", type=Path, default=TRANSCRIPTS)
    ap.add_argument("--per-session", action="store_true", help="print the per-session table")
    ap.add_argument("--queries", action="store_true", help="print every codegraph query made")
    args = ap.parse_args()

    cutoff = datetime.fromisoformat(args.cutoff).replace(tzinfo=timezone.utc)
    if not args.transcripts.is_dir():
        raise SystemExit(f"brak katalogu transkryptow: {args.transcripts}")

    sessions = [s for s in (parse(p) for p in sorted(args.transcripts.glob("*.jsonl"))) if s]
    sessions = [s for s in sessions if s.size >= args.min_size * 1e6]
    sessions.sort(key=lambda s: s.start)
    if not sessions:
        raise SystemExit("brak sesji po filtrach")

    before = [s for s in sessions if s.start < cutoff]
    after = [s for s in sessions if s.start >= cutoff]
    with_cg = [s for s in after if s.cg_queries]
    without_cg = [s for s in after if not s.cg_queries]

    filt = f", sesje >= {args.min_size} MB" if args.min_size else ""
    print(f"Transkrypty: {args.transcripts}\nCezura: {cutoff:%Y-%m-%d}{filt}")
    print_group("PRZED", before)
    print_group("PO", after)
    # The within-era split is the stronger evidence: it holds model, harness and
    # project phase constant. Pair it with --min-size, because larger sessions have
    # a naturally better nav/edit ratio regardless of tooling.
    print_group("PO - sesje UZYWAJACE codegraph", with_cg)
    print_group("PO - sesje BEZ codegraph", without_cg)

    if args.per_session:
        print("\n### Per sesja")
        print(f"{'data':<11} {'MB':>5} {'Bash':>5} {'srch':>5} {'Read':>5} {'Edit':>5} "
              f"{'CG':>4} {'s/e':>5} {'r/e':>5}")
        for s in sessions:
            e = max(s.edits, 1)
            print(f"{s.start.astimezone():%m-%d %H:%M} {s.size / 1e6:5.1f} {s.bash_total:5d} "
                  f"{s.searches:5d} {s.tools['Read']:5d} {s.edits:5d} {len(s.cg_queries):4d} "
                  f"{s.searches / e:5.2f} {s.tools['Read'] / e:5.2f}")

    if args.queries:
        print("\n### Zapytania codegraph")
        for s in after:
            for q in s.cg_queries:
                print(f"  [{s.start.astimezone():%m-%d %H:%M}] {q}")


if __name__ == "__main__":
    main()
