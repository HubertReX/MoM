#!/usr/bin/env python3
"""MOAB web — a FastAPI board editor over the same board.md + notes.

A 3rd face for MOAB (next to Obsidian+Kanban and the static board-designer.html),
for remote / no-Obsidian use. Reads are parsed directly from board.md; every
mutation calls the `moab` CLI (single source of truth — same validation + sync
the agents use). Note bodies are editable; frontmatter stays managed by `moab sync`.

Run:  ./run.sh [PORT]  (sets up a uv venv, serves on 0.0.0.0 on [PORT] default = 8770)
"""

from __future__ import annotations
import importlib.util, importlib.machinery, subprocess, sys, re
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

WEB = Path(__file__).resolve().parent
BASE = WEB.parent  # the Tasks/ vault
MOAB = BASE / "bin" / "moab"

# import the moab module (file has no .py extension) to reuse its parsing regexes
_loader = importlib.machinery.SourceFileLoader("moab", str(MOAB))
_spec = importlib.util.spec_from_loader("moab", _loader)
moab = importlib.util.module_from_spec(_spec)
_loader.exec_module(moab)

app = FastAPI(title="MOAB web")

def get_project_name():
    try:
        return moab.get_project_name(BASE)
    except Exception:
        return "MOAB"


WORKFLOW = ["backlog", "ready", "in-progress", "needs-you", "done"]
LANE_LABEL = {
    "backlog": "🧊 Backlog",
    "ready": "🟢 Ready for AI",
    "in-progress": "🤖 In Progress",
    "needs-you": "🙋 Needs You",
    "done": "🏁 Done",
}


def run_moab(args: list[str]):
    p = subprocess.run([sys.executable, str(MOAB), *args, "--dir", str(BASE)], capture_output=True, text=True)
    if p.returncode != 0:
        raise HTTPException(400, (p.stderr or p.stdout).strip() or "moab failed")
    return p.stdout.strip()


def parse_board():
    """Return ordered lanes with full card info (tags preserved for chips)."""
    lanes = {k: [] for k in WORKFLOW}
    status = None
    for raw in (BASE / "board.md").read_text(encoding="utf-8").splitlines():
        if raw.startswith("## "):
            status, _ = moab.lane_of(raw[3:])
            continue
        if status not in lanes:
            continue
        m = moab.CARD_RE.match(raw)
        if not m:
            continue
        link = moab.LINK_RE.search(m.group(1))
        if not link:
            continue
        target = link.group(1).strip()
        tags = moab.TAG_RE.findall(m.group(1))
        due = moab.DUE_RE.search(m.group(1))
        agent = next((t for t in tags if t.lower() in moab.AGENT), "")
        lanes[status].append(
            {
                "id": target.split(" ", 1)[0],
                "target": target,
                "title": target.split(" ", 1)[1] if " " in target else target,
                "tags": [t for t in tags if t.lower() not in moab.AGENT],
                "agent": agent,
                "due": due.group(1) if due else None,
            }
        )
    return [{"key": k, "label": LANE_LABEL[k], "cards": lanes[k]} for k in WORKFLOW]


@app.get("/api/board")
def api_board():
    return {
        "lanes": parse_board(),
        "agents": sorted(moab.AGENT),
        "types": sorted(moab.TYPE),
        "prios": sorted(moab.PRIO),
        "states": sorted(moab.STATE),
        "laneOrder": [{"key": k, "label": LANE_LABEL[k]} for k in WORKFLOW],
        "projectName": get_project_name(),
    }


class NewCard(BaseModel):
    title: str
    type: str = "chore"
    prio: str = "p2"
    lane: str = "backlog"
    due: str | None = None


@app.post("/api/new")
def api_new(c: NewCard):
    args = ["new", c.title, "--type", c.type, "--prio", c.prio, "--lane", c.lane]
    if c.due:
        args += ["--due", c.due]
    return {"output": run_moab(args)}


class Move(BaseModel):
    id: str
    to: str


@app.post("/api/move")
def api_move(m: Move):
    return {"output": run_moab(["move", m.id, "--to", m.to])}


class Claim(BaseModel):
    id: str
    agent: str


@app.post("/api/claim")
def api_claim(c: Claim):
    return {"output": run_moab(["claim", c.id, "--agent", c.agent])}


class Hand(BaseModel):
    id: str
    agent: str | None = None
    note: str | None = None


def _hand(kind: str, h: Hand):
    args = [kind, h.id]
    if h.agent:
        args += ["--agent", h.agent]
    if h.note:
        args += ["--note", h.note]
    return {"output": run_moab(args)}


@app.post("/api/review")
def api_review(h: Hand):
    return _hand("review", h)


@app.post("/api/block")
def api_block(h: Hand):
    return _hand("block", h)


class Done(BaseModel):
    id: str


@app.post("/api/done")
def api_done(d: Done):
    return {"output": run_moab(["done", d.id])}


class Retag(BaseModel):
    id: str
    prio: str | None = None
    type: str | None = None
    add: str | None = None
    remove: str | None = None


@app.post("/api/retag")
def api_retag(r: Retag):
    args = ["retag", r.id]
    if r.prio:
        args += ["--prio", r.prio]
    if r.type:
        args += ["--type", r.type]
    if r.add:
        args += ["--add", r.add]
    if r.remove:
        args += ["--remove", r.remove]
    return {"output": run_moab(args)}


class Rm(BaseModel):
    id: str


@app.post("/api/rm")
def api_rm(d: Rm):
    return {"output": run_moab(["rm", d.id])}


# ---- note body editing (frontmatter stays managed by sync) ----
def split_note(text: str):
    m = re.match(r"^(---\n.*?\n---\n)(.*)$", text, re.S)
    return (m.group(1), m.group(2)) if m else ("", text)


@app.get("/api/note/{task_id}")
def api_get_note(task_id: str):
    note = moab.note_for_id(BASE, task_id)
    fm, body = split_note(note.read_text(encoding="utf-8"))
    return {"id": task_id, "frontmatter": fm, "body": body}


class NoteBody(BaseModel):
    body: str


@app.put("/api/note/{task_id}")
def api_put_note(task_id: str, n: NoteBody):
    note = moab.note_for_id(BASE, task_id)
    fm, _ = split_note(note.read_text(encoding="utf-8"))
    note.write_text(fm + n.body, encoding="utf-8")
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def index():
    return (WEB / "index.html").read_text(encoding="utf-8")
