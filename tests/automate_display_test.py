#!/usr/bin/env python3
import subprocess
import time
import os
import json
import sys
from datetime import datetime
from typing import List

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
    def __init__(self, name: str, actions: List[TestAction]):
        self.name = name
        self.actions = actions

    def run(self):
        print(f"\n>>> Starting Scenario: {self.name}")
        for action in self.actions:
            action.execute()
        print(f">>> Scenario {self.name} Complete.")

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
            actions = [TestAction(a["label"], a["commands"]) for a in s["actions"]]
            scenarios.append(TestScenario(s["name"], actions))
        return scenarios

    def run_scenario(self, scenario: TestScenario) -> None:
        self.start_game()
        try:
            scenario.run()
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
