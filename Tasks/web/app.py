#!/usr/bin/env python3
"""MOAB web — a FastAPI board editor over the same board.md + notes.

A 3rd face for MOAB (next to Obsidian+Kanban and the static board-designer.html),
for remote / no-Obsidian use. Reads are parsed directly from board.md; every
mutation calls the `moab` CLI (single source of truth — same validation + sync
the agents use). Note bodies are editable; frontmatter stays managed by `moab sync`.

Run:  ./run.sh [PORT]  (sets up a uv venv, serves on 0.0.0.0 on [PORT] default = 8770)
"""

from __future__ import annotations
import importlib.util, importlib.machinery, subprocess, sys, re, os, signal, threading
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

WEB = Path(__file__).resolve().parent
BASE = WEB.parent  # the Tasks/ vault
MOAB = BASE / "bin" / "moab"

# import the moab module (file has no .py extension) to reuse its parsing regexes
_loader = importlib.machinery.SourceFileLoader("moab", str(MOAB))
_spec = importlib.util.spec_from_loader("moab", _loader)
moab = importlib.util.module_from_spec(_spec)
_loader.exec_module(moab)

app = FastAPI(title="MOAB web")

# serve attachments (images, etc.) referenced in task notes
app.mount("/attachments", StaticFiles(directory=str(BASE / "_attachments")), name="attachments")

# ---- model discovery (lazy, cached) ----
_MODELS_LOCK = threading.Lock()
_MODELS: list[str] | None = None
_MODELS_ERROR: str | None = None


def _discover_models() -> list[str]:
    """Ask opencode for the full provider/model list. Falls back to opencode-go defaults."""
    try:
        p = subprocess.run(
            ["opencode", "models"],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        lines = (p.stdout + "\n" + p.stderr).splitlines()
        models = [ln.strip() for ln in lines if "/" in ln.strip() and not ln.strip().startswith("[")]
        if models:
            return sorted(set(models))
    except subprocess.TimeoutExpired:
        return _fallback_models()
    except Exception:
        pass
    return _fallback_models()


def _fallback_models() -> list[str]:
    return sorted({
        "opencode-go/deepseek-v4-flash",
        "opencode-go/deepseek-v4-pro",
        "opencode-go/glm-5.1",
        "opencode-go/glm-5.2",
        "opencode-go/kimi-k2.6",
        "opencode-go/kimi-k2.7-code",
        "opencode-go/mimo-v2.5",
        "opencode-go/mimo-v2.5-pro",
        "opencode-go/minimax-m2.7",
        "opencode-go/minimax-m3",
        "opencode-go/qwen3.6-plus",
        "opencode-go/qwen3.7-max",
        "opencode-go/qwen3.7-plus",
    })


def get_models() -> list[str]:
    global _MODELS, _MODELS_ERROR
    if _MODELS is None:
        with _MODELS_LOCK:
            if _MODELS is None:
                try:
                    _MODELS = _discover_models()
                except Exception as e:
                    _MODELS_ERROR = str(e)
                    _MODELS = _fallback_models()
    return _MODELS


# ---- watcher state ----
class WatcherState:
    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.agent: str | None = None
        self.model: str | None = None
        self.interval: int = 10
        self.limit: int = 1

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        if self.proc is None:
            return
        try:
            if self.proc.poll() is None:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        finally:
            self.proc = None


WATCHER = WatcherState()


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


@app.get("/api/models")
def api_models():
    return {"models": get_models()}


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
    model: str | None = None


@app.post("/api/claim")
def api_claim(c: Claim):
    args = ["claim", c.id, "--agent", c.agent]
    if c.model:
        args += ["--model", c.model]
    return {"output": run_moab(args)}


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


class Archive(BaseModel):
    id: str


@app.post("/api/archive")
def api_archive(a: Archive):
    return {"output": run_moab(["archive", a.id])}


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


# ---- watcher control ----
class WatchStart(BaseModel):
    agent: str
    model: str | None = None
    interval: int = Field(default=10, ge=1)
    limit: int = Field(default=1, ge=1)


@app.post("/api/watch/start")
def api_watch_start(s: WatchStart):
    if WATCHER.is_running():
        raise HTTPException(409, "watcher already running")
    if s.agent not in moab.AGENT:
        raise HTTPException(400, f"unknown agent '{s.agent}'")
    cmd = [
        sys.executable, str(MOAB), "watch",
        "--agent", s.agent,
        "--interval", str(s.interval),
        "--limit", str(s.limit),
        "--dir", str(BASE),
    ]
    if s.model:
        cmd += ["--model", s.model]
    try:
        WATCHER.proc = subprocess.Popen(
            cmd,
            cwd=str(BASE.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        WATCHER.agent = s.agent
        WATCHER.model = s.model
        WATCHER.interval = s.interval
        WATCHER.limit = s.limit
        return {"ok": True, "pid": WATCHER.proc.pid}
    except Exception as e:
        raise HTTPException(500, f"failed to start watcher: {e}")


@app.post("/api/watch/stop")
def api_watch_stop():
    WATCHER.stop()
    return {"ok": True}


@app.get("/api/watch/status")
def api_watch_status():
    return {
        "running": WATCHER.is_running(),
        "agent": WATCHER.agent,
        "model": WATCHER.model,
        "interval": WATCHER.interval,
        "limit": WATCHER.limit,
    }


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
