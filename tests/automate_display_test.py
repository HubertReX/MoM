#!/usr/bin/env python3
"""Agent-driven UI/smoke test runner.

Two backends share one scenarios schema:

- **Desktop** (default): subprocess `MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy ... project/main.py`;
  komendy zapisywane do ``agent_input.txt``; screenshoty przez ``pygame.image.save``.
- **Web** (``--web``): subprocess `python -m pygbag ... project` + Playwright Chromium;
  komendy wstrzykiwane do ``window.localStorage['MoM.agent_input']``;
  screenshoty przez ``page.screenshot()``; save assertions czytane z localStorage.

Usage:
    # desktop (default) - jak dotychczas
    .venv/bin/python3 tests/automate_display_test.py "Save and Load Basic"
    .venv/bin/python3 tests/automate_display_test.py            # wszystkie desktop-owe
    # lub przez Just:  just test "Save and Load Basic"  |  just test

    # web (wymaga Playwright + chromium: patrz requirements-dev)
    .venv/bin/python3 tests/automate_display_test.py --web "Save and Load Basic"
    .venv/bin/python3 tests/automate_display_test.py --web      # wszystkie web-owe
    # lub przez Just:  just test-web "Save and Load Basic"  |  just test-web

Opcje CLI (patrz też ``--help``):
    scenario            nazwa scenariusza; pomiń, by uruchomić wszystkie dla backendu
    --web               użyj backendu web (pygbag + Playwright) zamiast desktop
    --url URL           web: nadpisz URL pygbag (domyślnie http://127.0.0.1:8001/)
    --timeout S         web: ile sekund czekać na boot gry po pojawieniu się canvasu
                        (domyślnie INIT_WAIT_WEB=12s); podbij na wolnym CI/sprzęcie
    --pygbag-timeout S  web: ile sekund czekać na build + serve pygbag (domyślnie 90s)

Scenarios selection:
    Scenariusze z polem ``platform`` w ``scenarios.json`` są filtrowane per backend:
    ``"desktop"``, ``"web"`` lub lista ``["desktop", "web"]``. Brak pola = dotyczy obu.

Assertions (per scenario, opcjonalne):
    file_exists          desktop: plik ``<save_dir>/save_N.mom`` istnieje (min_size opcjonalny);
                         web: tłumaczone na obecność klucza ``MoM.save_N`` w localStorage.
    localstorage_exists  web: klucz ``key`` (np. ``MoM.save_0``) obecny w localStorage.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, List

# --- Configuration & Constants ---
TEST_CONFIG = {
    "INIT_WAIT": 5.0,
    "INIT_WAIT_WEB": 12.0,  # pygbag boot + WASM load są wolniejsze
    "PYGBAG_BOOT_TIMEOUT": 90.0,  # ile czekać na wystartowanie serwera pygbag (build + serve)
    "TRANSITION_WAIT": 0.2,
    "SCREENSHOT_BUFFER": 0.1,
    "GAME_CMD": "MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python3 project/main.py",
    "PYGBAG_CMD": [
        sys.executable, "-m", "pygbag",
        "--ume_block", "0",
        "--template", "utils/black.tmpl",
        "--icon", "project/assets/icon.png",
        "--no_opt",
        "--bind", "127.0.0.1",
        "--port", "8001",
        "project",
    ],
    "WEB_URL": "http://127.0.0.1:8001/",
    "INPUT_FILE": os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent_input.txt"),
    "STATUS_FILE": os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent_status.txt"),
    "SCENARIOS_FILE": os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios.json"),
    "WALK_TIMEOUT": 30.0,   # max seconds to wait for a walk_to_* to reach its target
}

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_SCREENSHOT_DIR = REPO_ROOT / "screenshots" / "agent"

# localStorage klucze zapisów w trybie web (muszą zgadzać się z `LocalStorageSaveBackend._STORAGE_PREFIX`)
WEB_SAVE_KEY_PREFIX = "MoM.save_"
WEB_INPUT_KEY = "MoM.agent_input"
WEB_AGENT_FLAG = "MoM.agent_control"

# Nazewnictwo screenshotów: agent_{run_ts}_{scenario_slug}_{NN}_{action_slug}.png
#   - run_ts        : jeden znacznik czasu na cały przebieg jednego scenariusza (grupuje pliki)
#   - scenario_slug : krótki slug scenariusza z pola "slug" w scenarios.json
#   - NN            : licznik screenshotów w obrębie scenariusza (2 cyfry)
#   - action_slug   : slug etykiety akcji, która zleciła screenshot
# Desktop generuje tę nazwę w grze (project/agent_ctrl.py); web — w runnerze. Oba MUSZĄ
# produkować identyczny format, żeby runner mógł przewidzieć ścieżkę na potrzeby asercji.
SS_PREFIX_ENV = "MOM_AGENT_SS_PREFIX"  # desktop: prefix "{run_ts}_{scenario_slug}" przekazany do gry

# --- ss-reviewer (analiza screenshotów przez subagenta z vision) ---
# Kolejność prób: najpierw tani model z vision (mimo-v2.5), potem fallback Gemini.
# Gdy żaden model nie zwróci werdyktu -> asercja twardo pada (decyzja usera: hard-fail).
SS_REVIEW_AGENT = "ss-reviewer"
SS_REVIEW_MODELS: list[str | None] = ["opencode-go/mimo-v2.5", "google/gemini-3.1-flash-lite"]
SS_REVIEW_TIMEOUT = 60.0
SS_REVIEW_SKIP_ENV = "MOM_SKIP_SS_REVIEW"  # ustaw =1, by pominąć (szybka iteracja)


def get_timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")


def slugify(text: str, max_len: int = 48) -> str:
    """Zamień etykietę na bezpieczny slug do nazwy pliku (snake_case, [a-z0-9_])."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:max_len] or "shot"


def parse_review_verdict(text: str) -> str | None:
    """Wyciągnij PASS/FAIL z odpowiedzi ss-reviewera (kilka wariantów formatu)."""
    for pattern in (
        r"RESULT:\s*(PASS|FAIL)",
        r"\*\*Result\*\*:\s*(PASS|FAIL)",
        r"\bResult\b[:\s]+(PASS|FAIL)",
    ):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return None


def _timeout_cmd(cmd: list[str], timeout: int = 60) -> list[str]:
    """Wrap cmd with gtimeout (GNU coreutils, macOS) or timeout (Linux), if available."""
    exe = shutil.which("gtimeout") or shutil.which("timeout")
    if exe:
        return [exe, str(timeout), *cmd]
    return cmd


def review_screenshot(path: Path, expect: str, expected_state: str | None) -> tuple[str | None, str]:
    """Poproś subagenta ss-reviewer o werdykt PASS/FAIL dla screenshotu.

    Zwraca ``(verdict, detail)`` gdzie verdict to 'PASS'/'FAIL'/None (żaden model nie dał werdyktu).
    Próbuje kolejno modeli z ``SS_REVIEW_MODELS``; pierwszy zwracający czytelny werdykt wygrywa.

    UWAGA: ścieżka screenshotu jest przekazywana inline w prompcie, a nie przez ``-f``.
    ``-f`` wymaga modelu z vision (``attachment: true``, ``modalities.input: ["text","image"]``),
    a nie każdy model go ma. Modele użyte w ``SS_REVIEW_MODELS`` (mimo-v2.5, Gemini)
    mają vision, ale inne modele (deepseek-v4, glm) — nie. Przekazując ścieżkę inline,
    model bez vision może przynajmniej odpowiedzieć że nie widzi obrazka, zamiast błędu.
    """
    prompt = (
        "You are validating an automated test screenshot from the game "
        '"Misadventures of Malachi" (MoM). '
        f"Expected game state: {expected_state or 'described below'}. "
        f"Expectation to verify: {expect} "
        f"Screenshot file path: {path} "
        "Analyze the screenshot located at the given path and produce your structured report. "
        "Then, on the FINAL line, output exactly 'RESULT: PASS' if the screenshot "
        "matches the expectation, or 'RESULT: FAIL' if it does not."
    )
    # MOM_SS_REVIEW_MODEL wymusza jeden konkretny model (pomija dead primary).
    forced = os.environ.get("MOM_SS_REVIEW_MODEL")
    models: list[str | None] = [forced] if forced else SS_REVIEW_MODELS
    last_detail = "no model attempted"
    for model in models:
        label = model or "agent-default"
        cmd = ["opencode", "run", "--pure", prompt, "--agent", SS_REVIEW_AGENT]
        if model:
            cmd += ["--model", model]
        cmd = _timeout_cmd(cmd, int(SS_REVIEW_TIMEOUT))
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=SS_REVIEW_TIMEOUT + 10.0, cwd=str(REPO_ROOT),
            )
        except subprocess.TimeoutExpired:
            last_detail = f"{label}: timed out after {SS_REVIEW_TIMEOUT:.0f}s"
            print(f"[ss-review] {last_detail}")
            continue
        except FileNotFoundError:
            return None, "opencode CLI not found on PATH"
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        verdict = parse_review_verdict(out)
        if verdict:
            # dołącz krótki kontekst z raportu (ostatnie niepuste linie) do detalu
            tail = " ".join(
                ln.strip() for ln in out.strip().splitlines()[-4:] if ln.strip()
            )
            print(f"[ss-review] {label} -> {verdict}")
            return verdict, f"[{label}] {tail}"
        last_detail = f"{label}: no verdict (rc={proc.returncode})"
        print(f"[ss-review] {last_detail}")
    return None, last_detail


def get_save_dir() -> Path:
    """Return the same save directory used by FileSaveBackend."""
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "mom" / "saves"
    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return home / "Library" / "Application Support" / "mom" / "saves"
    elif system == "Linux":
        return home / ".local" / "share" / "mom" / "saves"
    return home / "AppData" / "Local" / "mom" / "saves"


def resolve_assertion_path(path: str) -> Path:
    """Resolve assertion paths, expanding <save_dir> and user home."""
    path = path.replace("<save_dir>", str(get_save_dir()))
    return Path(path).expanduser()


def delete_save_slot(slot_idx: int) -> None:
    path = get_save_dir() / f"save_{slot_idx}.mom"
    try:
        if path.exists():
            path.unlink()
    except OSError as e:
        print(f"[warn] could not delete {path}: {e}")


def clear_all_saves() -> None:
    save_dir = get_save_dir()
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[warn] could not create save dir {save_dir}: {e}")
        return
    for path in save_dir.glob("save_*.mom"):
        try:
            path.unlink()
            print(f"[cleanup] deleted {path}")
        except OSError as e:
            print(f"[warn] could not delete {path}: {e}")


# ============================================================================
# Scenarios
# ============================================================================
class TestAction:
    def __init__(self, slug: str, commands: List[str], wait: float = TEST_CONFIG["TRANSITION_WAIT"]):
        # slug: krótka nazwa snake_case akcji - używana w logach, w nazwie pliku
        # screenshotu (action_slug) oraz jako `target` asercji screenshot_review.
        self.slug = slugify(slug)
        self.commands = commands
        self.wait = wait

    def split_screenshot(self) -> tuple[List[str], bool]:
        """Oddziel screenshot od komend sterujących. Zwraca (control_commands, wants_screenshot)."""
        ctrl = [c for c in self.commands if c not in ("screenshot", "shot")]
        wants_shot = len(ctrl) != len(self.commands)
        return ctrl, wants_shot


class TestScenario:
    def __init__(
        self,
        name: str,
        actions: List[TestAction],
        assertions: List[dict[str, Any]] | None = None,
        cleanup_saves: List[int] | None = None,
        platform_spec: str | List[str] | None = None,
        setup_saves: List[dict[str, Any]] | None = None,
        slug: str | None = None,
    ):
        self.name = name
        self.actions = actions
        self.assertions = assertions or []
        self.cleanup_saves = cleanup_saves or []
        self.platform_spec = platform_spec
        self.setup_saves = setup_saves or []
        # slug do nazw plików screenshotów; fallback = slug z nazwy scenariusza
        self.slug = slug or slugify(name)

    def supports(self, backend: str) -> bool:
        if not self.platform_spec:
            return True
        if isinstance(self.platform_spec, list):
            return backend in self.platform_spec
        return self.platform_spec == backend

    def run(self, runner: "RunnerBase") -> None:
        print(f"\n>>> Starting Scenario: {self.name}")
        for action in self.actions:
            runner.execute_action(action)
        print(f">>> Scenario {self.name} Complete.")
        self._run_assertions(runner)

    def _run_assertions(self, runner: "RunnerBase") -> None:
        if not self.assertions:
            return
        failures: List[str] = []
        for assertion in self.assertions:
            failures.extend(runner.check_assertion(assertion))
        if failures:
            raise AssertionError("; ".join(failures))
        print(f">>> Assertions passed for {self.name}")


# ============================================================================
# Runner base + Desktop runner
# ============================================================================
class RunnerBase:
    backend = "desktop"

    def __init__(self) -> None:
        self.counter = 0
        self.run_ts = ""            # jeden znacznik czasu na przebieg jednego scenariusza
        self.scenario_slug = ""
        self.screenshots: List[dict[str, Any]] = []  # {slug, label, path} w kolejności zrobienia

    def start_game(self) -> None: ...
    def execute_action(self, action: TestAction) -> None: ...
    def check_assertion(self, assertion: dict[str, Any]) -> List[str]: ...
    def cleanup_saves_before(self, scenario: TestScenario) -> None: ...
    def setup_saves(self, saves: List[dict[str, Any]]) -> None: ...
    def cleanup(self) -> None: ...

    # ---------------------------------------------------------------- scenariusz
    def begin_scenario(self, scenario: TestScenario) -> None:
        """Zamroź jeden znacznik czasu + slug scenariusza; wyzeruj licznik i historię."""
        self.counter = 0
        self.run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.scenario_slug = scenario.slug
        self.screenshots = []

    def screenshot_prefix(self) -> str:
        return f"{self.run_ts}_{self.scenario_slug}"

    def record_screenshot(self, action_slug: str) -> Path:
        """Policz przewidywaną ścieżkę screenshotu i zapamiętaj ją (dla asercji).

        Nazwa MUSI być identyczna z tą, którą generuje gra na desktopie
        (project/agent_ctrl.py) — patrz komentarz przy SS_PREFIX_ENV.
        """
        self.counter += 1
        slug = slugify(action_slug)
        name = f"agent_{self.run_ts}_{self.scenario_slug}_{self.counter:02d}_{slug}.png"
        path = AGENT_SCREENSHOT_DIR / name
        AGENT_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self.screenshots.append({"slug": slug, "path": path})
        return path

    def take_screenshot(self, action_slug: str) -> None:
        """Web: policz ścieżkę i zapisz zrzut (desktop zapisuje gra, nie runner)."""
        path = self.record_screenshot(action_slug)
        self._save_screenshot(path)
        print(f"[{get_timestamp()}] screenshot -> {path}")

    def _save_screenshot(self, path: Path) -> None:
        raise NotImplementedError

    # ---------------------------------------------------------------- asercje wspólne
    def find_screenshot(self, target: str | None) -> dict[str, Any] | None:
        """Znajdź zapamiętany screenshot po slugu akcji; brak target => ostatni."""
        if not self.screenshots:
            return None
        if not target:
            return self.screenshots[-1]
        wanted = slugify(target)
        for shot in reversed(self.screenshots):
            if shot["slug"] == wanted:
                return shot
        return None

    def check_common_assertion(self, assertion: dict[str, Any]) -> List[str] | None:
        """Asercje wspólne dla obu backendów. Zwraca None gdy typ nieobsługiwany tutaj."""
        a_type = assertion.get("type")
        if a_type == "screenshot_review":
            return self._assert_screenshot_review(assertion)
        if a_type == "screenshot_min_size":
            return self._assert_screenshot_min_size(assertion)
        if a_type == "process_alive":
            return self._assert_process_alive(assertion)
        return None

    def _assert_screenshot_review(self, assertion: dict[str, Any]) -> List[str]:
        if os.environ.get(SS_REVIEW_SKIP_ENV):
            print(f"[ss-review] skipped ({SS_REVIEW_SKIP_ENV} set)")
            return []
        target = assertion.get("target")
        shot = self.find_screenshot(target)
        if shot is None:
            avail = [s["slug"] for s in self.screenshots]
            return [f"screenshot_review: no screenshot for target={target!r} (have: {avail})"]
        path = Path(shot["path"])
        if not path.exists():
            return [f"screenshot_review: screenshot file missing: {path}"]
        expect = assertion.get("expect", "")
        expected_state = assertion.get("expected_state")
        verdict, detail = review_screenshot(path, expect, expected_state)
        if verdict == "PASS":
            return []
        if verdict == "FAIL":
            return [f"screenshot_review[{shot['slug']}] FAIL: {detail}"]
        # hard-fail (decyzja usera): żaden model nie dał werdyktu
        return [f"screenshot_review[{shot['slug']}] no verdict from any model: {detail}"]

    def _assert_screenshot_min_size(self, assertion: dict[str, Any]) -> List[str]:
        target = assertion.get("target")
        shot = self.find_screenshot(target)
        if shot is None:
            return [f"screenshot_min_size: no screenshot for target={target!r}"]
        path = Path(shot["path"])
        if not path.exists():
            return [f"screenshot_min_size: file missing: {path}"]
        min_size = int(assertion.get("min_size", 1000))
        size = path.stat().st_size
        if size < min_size:
            return [f"screenshot_min_size[{shot['slug']}]: {size} bytes < {min_size} (blank frame?)"]
        return []

    def _assert_process_alive(self, assertion: dict[str, Any]) -> List[str]:
        """Domyślnie no-op; DesktopRunner nadpisuje realną kontrolą procesu."""
        return []


class DesktopRunner(RunnerBase):
    backend = "desktop"

    def __init__(self) -> None:
        super().__init__()
        self.game_proc: subprocess.Popen | None = None

    def _clear_input_file(self) -> None:
        try:
            with open(TEST_CONFIG["INPUT_FILE"], "w") as f:
                f.write("")
        except FileNotFoundError:
            pass

    def start_game(self) -> None:
        print(f"[{get_timestamp()}] Starting game (desktop)...")
        start_time = time.perf_counter()
        self._clear_input_file()
        # Prefix nazw screenshotów przekazany do gry — patrz SS_PREFIX_ENV.
        env = dict(os.environ)
        env[SS_PREFIX_ENV] = self.screenshot_prefix()
        self.game_proc = subprocess.Popen(
            TEST_CONFIG["GAME_CMD"], shell=True, preexec_fn=os.setsid, env=env
        )
        time.sleep(TEST_CONFIG["INIT_WAIT"])
        print(f"[{get_timestamp()}] Game Init Delta: {time.perf_counter() - start_time:.4f}s")

    def execute_action(self, action: TestAction) -> None:
        print(f"[{get_timestamp()}] {action.slug}")
        start = time.perf_counter()
        ctrl, wants_shot = action.split_screenshot()
        tokens = list(ctrl)
        if wants_shot:
            # Osadź slug akcji w komendzie: gra użyje go w nazwie pliku.
            tokens.append(f"screenshot:{action.slug}")
        walk_cmd = next((t for t in tokens if t.startswith("walk_to")), None)
        if walk_cmd is not None:
            self._reset_walk_status()
        cmd = f'echo "{" ".join(tokens)}" > {TEST_CONFIG["INPUT_FILE"]}'
        print(f"[RUNNER SEND] {cmd}")
        subprocess.run(cmd, shell=True)
        if walk_cmd is not None:
            # Deterministic: block until the game reports the walk finished (or failed),
            # instead of guessing a fixed sleep. Poll the status file the game writes.
            outcome = self._wait_for_walk()
            print(f"[{get_timestamp()}] walk '{walk_cmd}' -> {outcome}")
        if wants_shot:
            # Przewidź ścieżkę, którą zapisze gra (ten sam format nazwy), na potrzeby asercji.
            self.record_screenshot(action.slug)
        end = time.perf_counter()
        print(f"[{get_timestamp()}] Done. Delta: {end - start:.4f}s")
        if action.wait > 0:
            time.sleep(action.wait)

    def _reset_walk_status(self) -> None:
        try:
            with open(TEST_CONFIG["STATUS_FILE"], "w") as f:
                f.write("walking")
        except OSError:
            pass

    def _wait_for_walk(self) -> str:
        """Poll the game's status file until the walk is no longer in progress.

        Returns the terminal status: ``arrived`` / ``no_path`` / ``not_found`` /
        ``timeout``. Deterministic replacement for a fixed sleep after walk_to_*.
        """
        deadline = time.perf_counter() + TEST_CONFIG["WALK_TIMEOUT"]
        while time.perf_counter() < deadline:
            try:
                with open(TEST_CONFIG["STATUS_FILE"]) as f:
                    status = f.read().strip()
            except OSError:
                status = ""
            if status and status != "walking":
                return status
            time.sleep(0.1)
        return "timeout"

    def check_assertion(self, assertion: dict[str, Any]) -> List[str]:
        common = self.check_common_assertion(assertion)
        if common is not None:
            return common
        a_type = assertion.get("type")
        if a_type == "file_exists":
            path = resolve_assertion_path(assertion["path"])
            if not path.exists():
                return [f"{path} does not exist"]
            min_size = assertion.get("min_size")
            if min_size is not None and path.stat().st_size < min_size:
                return [f"{path} size {path.stat().st_size} < {min_size}"]
            return []
        if a_type == "save_absent":
            path = resolve_assertion_path(assertion["path"])
            if path.exists():
                return [f"{path} exists but should be absent"]
            return []
        return [f"unknown assertion type: {a_type}"]

    def _assert_process_alive(self, assertion: dict[str, Any]) -> List[str]:
        if self.game_proc is None or self.game_proc.poll() is not None:
            return ["process_alive: game process exited unexpectedly (crash or unwanted quit)"]
        return []

    def cleanup_saves_before(self, scenario: TestScenario) -> None:
        clear_all_saves()
        for slot_idx in scenario.cleanup_saves:
            delete_save_slot(slot_idx)

    def setup_saves(self, saves: List[dict[str, Any]]) -> None:
        from test_save_load_corrupt import (
            corrupt_save, corrupt_save_version, create_minimal_save,
        )
        for spec in saves:
            slot = int(spec["slot"])
            kind = spec.get("type", "minimal")
            if kind == "corrupt":
                corrupt_save(slot)
            elif kind == "corrupt_version":
                corrupt_save_version(slot)
            else:
                create_minimal_save(slot)

    def cleanup(self) -> None:
        if self.game_proc:
            print(f"[{get_timestamp()}] Cleaning up...")
            try:
                os.killpg(os.getpgid(self.game_proc.pid), 15)
                try:
                    self.game_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(self.game_proc.pid), 9)
                    self.game_proc.wait(timeout=5)
            except Exception:
                pass
            print(f"[{get_timestamp()}] Game stopped.")
            self.game_proc = None

    def _save_screenshot(self, path: Path) -> None:
        # screenshot zapisuje gra przez agent_ctrl.capture(); ten runner nic nie robi
        pass


# ============================================================================
# Web runner (Playwright + pygbag)
# ============================================================================
class WebRunner(RunnerBase):
    backend = "web"

    def __init__(
        self,
        url: str | None = None,
        init_wait: float | None = None,
        pygbag_timeout: float | None = None,
    ) -> None:
        super().__init__()
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Playwright nie zainstalowany. Uruchom:\n"
                "  rtk uv pip install playwright && rtk .venv/bin/playwright install chromium"
            ) from e
        self._sync_playwright = sync_playwright
        self.pygbag_proc: subprocess.Popen | None = None
        self.url = url or TEST_CONFIG["WEB_URL"]
        # boot wait po pojawieniu się canvasu (asset load + MainMenuScreen); konfigurowalne przez --timeout
        self.init_wait = init_wait if init_wait is not None else TEST_CONFIG["INIT_WAIT_WEB"]
        self.pygbag_timeout = pygbag_timeout if pygbag_timeout is not None else TEST_CONFIG["PYGBAG_BOOT_TIMEOUT"]
        self.pw = None
        self.browser = None
        self.page = None
        # saves do wstrzyknięcia po pierwszym goto(), przed reloadem ze stroną z grą
        self._pending_setup_saves: List[dict[str, Any]] = []

    def _wait_for_pygbag_url(self, proc: subprocess.Popen, timeout: float | None = None) -> str:
        if timeout is None:
            timeout = self.pygbag_timeout
        """Sprawdź gotowość pygbag: (a) szukaj URL w stdout, (b) HTTP poll na self.url."""
        url_re = re.compile(r"http://[\w\.-]+:\d+/?")
        deadline = time.perf_counter() + timeout
        assert proc.stdout is not None
        poll_interval = 0.5
        while time.perf_counter() < deadline:
            line = proc.stdout.readline()
            if line:
                text = line.rstrip() if isinstance(line, str) else line.decode("utf-8", errors="replace").rstrip()
                if text:
                    print(f"[pygbag] {text}")
                m = url_re.search(text)
                if m:
                    return m.group(0)
            if proc.poll() is not None:
                raise RuntimeError("pygbag exited unexpectedly")
            # równolegle HTTP poll na znanym URL
            if self._http_up(self.url):
                return self.url
            time.sleep(poll_interval)
        raise RuntimeError(f"pygbag nie wystartował w {timeout}s (URL={self.url})")

    @staticmethod
    def _http_up(url: str) -> bool:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def start_game(self) -> None:
        print(f"[{get_timestamp()}] Starting pygbag (web)...")
        env = dict(os.environ)
        self.pygbag_proc = subprocess.Popen(
            TEST_CONFIG["PYGBAG_CMD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT),
            env=env,
            text=True,
            bufsize=1,
            # własna sesja/grupa procesów: cleanup() robi os.killpg na tej grupie,
            # bez tego SIGTERM trafiłby też w sam runner (współdzielona grupa) -> exit 143/144
            start_new_session=True,
        )
        try:
            url = self._wait_for_pygbag_url(self.pygbag_proc)
        except Exception:
            self.cleanup()
            raise
        self.url = url
        print(f"[{get_timestamp()}] pygbag ready: {url}")

        self.pw = self._sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=True)
        self.page = self.browser.new_page(viewport={"width": 1280, "height": 720})

        # Najpierw basic load, ustaw flagę agenta, potem RELOAD - gra czyta flagę w __init__.
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # ustawienie agent_control + clear ewentualnych poprzednich komend/save
        self.page.evaluate(
            "([k,v]) => localStorage.setItem(k, v)",
            [WEB_AGENT_FLAG, "1"],
        )
        self.page.evaluate(
            "() => localStorage.removeItem('" + WEB_INPUT_KEY + "')"
        )
        # wstrzyknij ewentualne saves (corrupt/minimal) zadeklarowane przez scenario.
        # Robione TU (po first goto, przed reloadem), bo gra czyta localStorage w __init__.
        self._inject_setup_saves()
        print(f"[{get_timestamp()}] localStorage[MoM.agent_control]=1; reloading...")
        self.page.reload(wait_until="domcontentloaded", timeout=30000)

        # czekaj aż gra zacznie rysować canvas (pygbag generuje <canvas>)
        try:
            self.page.wait_for_selector("canvas", timeout=30000)
        except Exception as e:
            print(f"[warn] canvas not found within 30s: {e}")
        # daj grze czas na pełny boot (asset load, MainMenuScreen)
        time.sleep(self.init_wait)
        print(f"[{get_timestamp()}] Web game ready")

    def _send_commands(self, commands: List[str]) -> None:
        if not commands:
            return
        text = " ".join(commands)
        # escape for JS string literal
        escaped = text.replace("\\", "\\\\").replace("'", "\\'")
        self.page.evaluate(
            "([k,v]) => localStorage.setItem(k, v)",
            [WEB_INPUT_KEY, text],
        )

    def execute_action(self, action: TestAction) -> None:
        print(f"[{get_timestamp()}] {action.slug}")
        start = time.perf_counter()
        ctrl, wants_shot = action.split_screenshot()
        self._send_commands(ctrl)
        end = time.perf_counter()
        print(f"[{get_timestamp()}] Sent {len(ctrl)} cmds. Delta: {end - start:.4f}s")
        if action.wait > 0:
            time.sleep(action.wait)
        if wants_shot:
            self.take_screenshot(action.slug)

    def check_assertion(self, assertion: dict[str, Any]) -> List[str]:
        common = self.check_common_assertion(assertion)
        if common is not None:
            return common
        a_type = assertion.get("type")
        if a_type == "file_exists":
            # Translator: assertion z desktopa -> sprawdź localStorage zamiast pliku.
            # Format ścieżki: <save_dir>/save_N.mom -> wyciągnij N.
            m = re.search(r"save_(\d+)\.mom$", assertion["path"])
            if not m:
                return [
                    f"web: nie wyciągnąłem slotu z paths '{assertion['path']}'"
                    f" (use type 'localstorage_exists' jawnie)"
                ]
            slot = int(m.group(1))
            return self._check_localstorage_slot(slot, assertion.get("min_size"))
        elif a_type == "localstorage_exists":
            m = re.search(r"save_(\d+)", assertion.get("key", ""))
            if m:
                slot = int(m.group(1))
                return self._check_localstorage_slot(slot, assertion.get("min_size"))
            return [f"localstorage_exists: brak slotu w 'key' ({assertion.get('key')})"]
        elif a_type == "save_absent":
            m = re.search(r"save_(\d+)", assertion.get("path", ""))
            if not m:
                return [f"save_absent: brak slotu w 'path' ({assertion.get('path')})"]
            slot = int(m.group(1))
            key = f"{WEB_SAVE_KEY_PREFIX}{slot}"
            raw = self.page.evaluate("([k]) => localStorage.getItem(k)", [key])
            if raw:
                return [f"{key} present in localStorage but should be absent"]
            return []
        return [f"unknown assertion type: {a_type}"]

    def _assert_process_alive(self, assertion: dict[str, Any]) -> List[str]:
        # web: gra żyje, jeśli strona nadal odpowiada na evaluate (nie ma crashu WASM)
        if self.page is None:
            return ["process_alive: no page (web game not running)"]
        try:
            self.page.evaluate("() => 1")
        except Exception as e:
            return [f"process_alive: web page unresponsive ({e})"]
        return []

    def _check_localstorage_slot(self, slot: int, min_size: Any) -> List[str]:
        key = f"{WEB_SAVE_KEY_PREFIX}{slot}"
        raw = self.page.evaluate(
            "([k]) => localStorage.getItem(k)",
            [key],
        )
        if not raw:
            return [f"{key} not present in localStorage"]
        if min_size is not None:
            size = len(raw)
            if size < min_size:
                return [f"{key} size {size} < {min_size}"]
        return []

    def cleanup_saves_before(self, scenario: TestScenario) -> None:
        # w web mode saveBackend jest localStorage -> czyścimy jeśli runner jest już w górze,
        # w przeciwnym razie clear nastąpi po starcie gry (reload czyści w _runner harmonogram).
        # Tutaj wykonujemy pomiędzy scenariuszami, gdy pygbag jest jeszcze aktywny z poprzedniego.
        if self.page is not None:
            self.page.evaluate(
                "() => {"
                f" for (let i=0;i<10;i++) localStorage.removeItem('{WEB_SAVE_KEY_PREFIX}'+i);"
                " }"
            )
            self.page.evaluate(f"() => localStorage.removeItem('{WEB_INPUT_KEY}')")
            print(f"[cleanup] cleared localStorage save slots")

    def setup_saves(self, saves: List[dict[str, Any]]) -> None:
        # w web nie jesteśmy jeszcze po pierwszym goto - zapamiętaj na później.
        self._pending_setup_saves = list(saves)

    def _inject_setup_saves(self) -> None:
        if not self._pending_setup_saves or self.page is None:
            return
        from test_save_load_corrupt import minimal_save_dict, corrupt_save_text
        for spec in self._pending_setup_saves:
            slot = int(spec["slot"])
            kind = spec.get("type", "minimal")
            key = f"{WEB_SAVE_KEY_PREFIX}{slot}"
            if kind == "corrupt":
                payload = corrupt_save_text()
            elif kind == "corrupt_version":
                payload = json.dumps(minimal_save_dict(slot, version=9999))
            else:
                payload = json.dumps(minimal_save_dict(slot))
            self.page.evaluate(
                "([k,v]) => localStorage.setItem(k, v)",
                [key, payload],
            )
            print(f"[setup] localStorage['{key}'] = {kind}")
        self._pending_setup_saves = []

    def cleanup(self) -> None:
        if self.page:
            try:
                self.page.close()
            except Exception:
                pass
            self.page = None
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
            self.browser = None
        if self.pw:
            try:
                self.pw.stop()
            except Exception:
                pass
            self.pw = None
        if self.pygbag_proc:
            print(f"[{get_timestamp()}] Stopping pygbag...")
            try:
                os.killpg(os.getpgid(self.pygbag_proc.pid), 15)
                try:
                    self.pygbag_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(self.pygbag_proc.pid), 9)
                    self.pygbag_proc.wait(timeout=5)
            except Exception:
                try:
                    self.pygbag_proc.kill()
                except Exception:
                    pass
            print(f"[{get_timestamp()}] pygbag stopped.")
            self.pygbag_proc = None

    def _save_screenshot(self, path: Path) -> None:
        assert self.page is not None
        self.page.screenshot(path=str(path), full_page=False)
        # daj chwilę buffer po capture, żeby kolejna akcja nie złapała intermediate frame
        time.sleep(TEST_CONFIG["SCREENSHOT_BUFFER"])


# ============================================================================
# Orchestration
# ============================================================================
def load_scenarios(path: str) -> List[TestScenario]:
    with open(path, "r") as f:
        data = json.load(f)
    scenarios = []
    for s in data:
        actions = [
            TestAction(
                a.get("slug") or a.get("label", ""),
                a["commands"],
                a.get("wait", TEST_CONFIG["TRANSITION_WAIT"]),
            )
            for a in s["actions"]
        ]
        scenarios.append(TestScenario(
            s["name"],
            actions,
            assertions=s.get("assertions"),
            cleanup_saves=s.get("cleanup_saves"),
            platform_spec=s.get("platform"),
            setup_saves=s.get("setup_saves"),
            slug=s.get("slug"),
        ))
    return scenarios


def run_scenarios(scenarios: List[TestScenario], runner: RunnerBase) -> int:
    failures = 0
    for scenario in scenarios:
        runner.begin_scenario(scenario)
        runner.cleanup_saves_before(scenario)
        if scenario.setup_saves:
            runner.setup_saves(scenario.setup_saves)
        runner.start_game()
        try:
            scenario.run(runner)
        except AssertionError as e:
            print(f"Test failed: {e}")
            failures += 1
        except Exception as e:
            print(f"Test failed: {e}")
            failures += 1
        finally:
            runner.cleanup()
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent-driven UI test runner")
    parser.add_argument("--web", action="store_true", help="use pygbag + Playwright web backend")
    parser.add_argument("--url", default=None, help="override pygbag URL (web mode)")
    parser.add_argument(
        "--timeout", type=float, default=None,
        help="web mode: seconds to wait for the game to boot after the canvas appears "
             f"(default {TEST_CONFIG['INIT_WAIT_WEB']}); bump on slow CI/hardware",
    )
    parser.add_argument(
        "--pygbag-timeout", type=float, default=None,
        help="web mode: seconds to wait for the pygbag server to build + serve "
             f"(default {TEST_CONFIG['PYGBAG_BOOT_TIMEOUT']})",
    )
    parser.add_argument("scenario", nargs="?", default=None, help="scenario name; omit to run all")
    args = parser.parse_args()

    scenarios = load_scenarios(TEST_CONFIG["SCENARIOS_FILE"])
    backend = "web" if args.web else "desktop"
    selected = [s for s in scenarios if s.supports(backend)]
    if args.scenario:
        target_name = args.scenario
        selected = [s for s in selected if s.name == target_name]
        if not selected:
            avail = [s.name for s in scenarios if s.supports(backend)]
            print(f"Error: scenario '{target_name}' not available for backend '{backend}'.")
            print(f"Available: {avail}")
            return 2

    runner: RunnerBase
    if args.web:
        runner = WebRunner(
            url=args.url,
            init_wait=args.timeout,
            pygbag_timeout=args.pygbag_timeout,
        )
    else:
        runner = DesktopRunner()

    print(f"Backend: {backend}; scenarios: {[s.name for s in selected]}")
    failures = run_scenarios(selected, runner)
    if failures:
        print(f"\n{failures} scenario(s) failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())