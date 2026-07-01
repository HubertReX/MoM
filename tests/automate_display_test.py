#!/usr/bin/env python3
import platform
import subprocess
import time
import os
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List

# --- Configuration & Constants ---
TEST_CONFIG = {
    "INIT_WAIT": 5.0,
    "TRANSITION_WAIT": 0.2,
    "SCREENSHOT_BUFFER": 0.1,
    "GAME_CMD": "MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python3 project/main.py",
    "INPUT_FILE": os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent_input.txt"),
    "SCENARIOS_FILE": os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios.json")
}

def get_timestamp():
    return datetime. now().strftime("%H:%M:%S.%f")


def get_save_dir() -> Path:
    """Return the same save directory used by FileSaveBackend."""
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
    """Delete a single save slot file if it exists."""
    path = get_save_dir() / f"save_{slot_idx}.mom"
    try:
        if path.exists():
            path.unlink()
    except OSError as e:
        print(f"[warn] could not delete {path}: {e}")

class TestAction:
    def __init__(self, label: str, commands: List[str], wait: float = TEST_CONFIG["TRANSITION_WAIT"]):
        self.label = label
        self.commands = commands
        self.wait = wait

    def execute(self):
        print(f"[{get_timestamp()}] {self.label}")
        start = time.perf_counter()
        cmd = f'echo "{ " ".join(self.commands) }" > {TEST_CONFIG["INPUT_FILE"]}'
        subprocess.run(cmd, shell=True)
        end = time.perf_counter()
        print(f"[{get_timestamp()}] Done. Delta: {end - start:.4f}s")
        if self.wait > 0:
            time.sleep(self.wait)

class TestScenario:
    def __init__(
        self,
        name: str,
        actions: List[TestAction],
        assertions: List[dict[str, Any]] | None = None,
        cleanup_saves: List[int] | None = None,
    ):
        self.name = name
        self.actions = actions
        self.assertions = assertions or []
        self.cleanup_saves = cleanup_saves or []

    def _run_assertions(self) -> None:
        """Validate optional file assertions after the scenario finishes."""
        if not self.assertions:
            return
        failures: List[str] = []
        for assertion in self.assertions:
            a_type = assertion.get("type")
            if a_type == "file_exists":
                path = resolve_assertion_path(assertion["path"])
                if not path.exists():
                    failures.append(f"{path} does not exist")
                    continue
                min_size = assertion.get("min_size")
                if min_size is not None:
                    size = path.stat().st_size
                    if size < min_size:
                        failures.append(f"{path} size {size} < {min_size}")
            else:
                failures.append(f"unknown assertion type: {a_type}")
        if failures:
            raise AssertionError("; ".join(failures))
        print(f">>> Assertions passed for {self.name}")

    def run(self):
        print(f"\n>>> Starting Scenario: {self.name}")
        for action in self.actions:
            action.execute()
        print(f">>> Scenario {self.name} Complete.")
        self._run_assertions()

class TestRunner:
    def __init__(self):
        self.game_proc: subprocess.Popen | None = None

    def _clear_input_file(self) -> None:
        """Wyczyść plik wejściowy, aby stara gra nie wykonała poprzednich komend."""
        try:
            with open(TEST_CONFIG["INPUT_FILE"], "w") as f:
                f.write("")
        except FileNotFoundError:
            pass

    def start_game(self) -> None:
        print(f"[{get_timestamp()}] Starting game...")
        start_time = time.perf_counter()
        self._clear_input_file()
        self.game_proc = subprocess.Popen(
            TEST_CONFIG["GAME_CMD"], shell=True, preexec_fn=os.setsid
        )
        time.sleep(TEST_CONFIG["INIT_WAIT"])
        print(f"[{get_timestamp()}] Game Init Delta: {time.perf_counter() - start_time:.4f}s")

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

    def load_scenarios(self) -> List[TestScenario]:
        with open(TEST_CONFIG["SCENARIOS_FILE"], "r") as f:
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
            ))
        return scenarios

    def run_scenario(self, scenario: TestScenario) -> None:
        for slot_idx in scenario.cleanup_saves:
            delete_save_slot(slot_idx)
        self.start_game()
        try:
            scenario.run()
        except AssertionError as e:
            print(f"Test failed: {e}")
            raise
        except Exception as e:
            print(f"Test failed: {e}")
        finally:
            self.cleanup()

if __name__ == "__main__":
    runner = TestRunner()
    scenarios = runner.load_scenarios()

    if len(sys.argv) > 1:
        target_name = sys.argv[1]
        selected = [s for s in scenarios if s.name == target_name]
        if not selected:
            print(f"Error: Scenario '{target_name}' not found in {TEST_CONFIG['SCENARIOS_FILE']}")
            sys.exit(1)
        for s in selected:
            runner.run_scenario(s)
    else:
        for s in scenarios:
            runner.run_scenario(s)
