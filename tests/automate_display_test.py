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
    "SCENARIOS_FILE": os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios.json"),
}

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_SCREENSHOT_DIR = REPO_ROOT / "screenshots" / "agent"

# localStorage klucze zapisów w trybie web (muszą zgadzać się z `LocalStorageSaveBackend._STORAGE_PREFIX`)
WEB_SAVE_KEY_PREFIX = "MoM.save_"
WEB_INPUT_KEY = "MoM.agent_input"
WEB_AGENT_FLAG = "MoM.agent_control"


def get_timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")


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
    def __init__(self, label: str, commands: List[str], wait: float = TEST_CONFIG["TRANSITION_WAIT"]):
        self.label = label
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
    ):
        self.name = name
        self.actions = actions
        self.assertions = assertions or []
        self.cleanup_saves = cleanup_saves or []
        self.platform_spec = platform_spec
        self.setup_saves = setup_saves or []

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

    def start_game(self) -> None: ...
    def execute_action(self, action: TestAction) -> None: ...
    def check_assertion(self, assertion: dict[str, Any]) -> List[str]: ...
    def cleanup_saves_before(self, scenario: TestScenario) -> None: ...
    def setup_saves(self, saves: List[dict[str, Any]]) -> None: ...
    def cleanup(self) -> None: ...
    def next_screenshot_counter(self) -> int:
        self.counter += 1
        return self.counter

    def take_screenshot(self, label: str) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = AGENT_SCREENSHOT_DIR / f"agent_{ts}_{self.next_screenshot_counter():04d}.png"
        AGENT_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self._save_screenshot(path)
        print(f"[{get_timestamp()}] screenshot -> {path}")

    def _save_screenshot(self, path: Path) -> None:
        raise NotImplementedError


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
        self.game_proc = subprocess.Popen(
            TEST_CONFIG["GAME_CMD"], shell=True, preexec_fn=os.setsid
        )
        time.sleep(TEST_CONFIG["INIT_WAIT"])
        print(f"[{get_timestamp()}] Game Init Delta: {time.perf_counter() - start_time:.4f}s")

    def execute_action(self, action: TestAction) -> None:
        print(f"[{get_timestamp()}] {action.label}")
        start = time.perf_counter()
        cmd = f'echo "{" ".join(action.commands)}" > {TEST_CONFIG["INPUT_FILE"]}'
        subprocess.run(cmd, shell=True)
        end = time.perf_counter()
        print(f"[{get_timestamp()}] Done. Delta: {end - start:.4f}s")
        if action.wait > 0:
            time.sleep(action.wait)

    def check_assertion(self, assertion: dict[str, Any]) -> List[str]:
        a_type = assertion.get("type")
        if a_type != "file_exists":
            return [f"unknown assertion type: {a_type}"]
        path = resolve_assertion_path(assertion["path"])
        if not path.exists():
            return [f"{path} does not exist"]
        min_size = assertion.get("min_size")
        if min_size is not None and path.stat().st_size < min_size:
            return [f"{path} size {path.stat().st_size} < {min_size}"]
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
        print(f"[{get_timestamp()}] {action.label}")
        start = time.perf_counter()
        ctrl, wants_shot = action.split_screenshot()
        self._send_commands(ctrl)
        end = time.perf_counter()
        print(f"[{get_timestamp()}] Sent {len(ctrl)} cmds. Delta: {end - start:.4f}s")
        if action.wait > 0:
            time.sleep(action.wait)
        if wants_shot:
            self.take_screenshot(action.label)

    def check_assertion(self, assertion: dict[str, Any]) -> List[str]:
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
        return [f"unknown assertion type: {a_type}"]

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
                a["label"],
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
        ))
    return scenarios


def run_scenarios(scenarios: List[TestScenario], runner: RunnerBase) -> int:
    failures = 0
    for scenario in scenarios:
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