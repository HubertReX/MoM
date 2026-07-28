#!/usr/bin/env python3
"""Guard against the desktop (Pydantic) / web (dataclass) config model drifting apart.

Run from the project root:
    .venv/bin/python tests/test_config_web_codegen.py

Two independent guards live here:

- Parity: loads the real `config.json` through *both* models and compares every
  field of every entity, section by section. This is the test that actually
  catches a wrong `.get("key", ...)` in `config.py` - see G01 audit finding.
- Freshness (added in step 3): `scripts/gen_web_config.py` must reproduce the
  on-disk `config.py` byte for byte, otherwise `config.py` has drifted from the
  Pydantic model it is generated from.
"""

import difflib
import os
import sys
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
PROJECT_DIR = ROOT / "project"
SCRIPTS_DIR = ROOT / "scripts"

sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from config_model import config as config_web  # noqa: E402
from config_model import config_pydantic  # noqa: E402
import gen_web_config  # noqa: E402

CONFIG_JSON = PROJECT_DIR / "config_model" / "config.json"
CONFIG_PY = PROJECT_DIR / "config_model" / "config.py"

# section name in config.json -> pydantic model class (source of the field list)
SECTIONS: dict[str, type] = {
    "characters": config_pydantic.Character,
    "items": config_pydantic.Item,
    "chests": config_pydantic.Chest,
    "maze_configs": config_pydantic.MazeLevelProperties,
}


def _collect_parity_diffs() -> list[str]:
    desktop_cfg = config_pydantic.load_config(CONFIG_JSON)
    web_cfg = config_web.load_config(CONFIG_JSON)

    diffs: list[str] = []
    for section, model in SECTIONS.items():
        desktop_section: dict[Any, Any] = getattr(desktop_cfg, section)
        web_section: dict[Any, Any] = getattr(web_cfg, section)

        desktop_keys = set(desktop_section.keys())
        web_keys = set(web_section.keys())
        if desktop_keys != web_keys:
            diffs.append(
                f"{section}: key sets differ - desktop only={sorted(desktop_keys - web_keys)} "
                f"web only={sorted(web_keys - desktop_keys)}"
            )

        for key in sorted(desktop_keys & web_keys, key=str):
            desktop_entity = desktop_section[key]
            web_entity = web_section[key]
            for field_name in model.model_fields:
                desktop_value = getattr(desktop_entity, field_name)
                web_value = getattr(web_entity, field_name)
                if desktop_value != web_value:
                    diffs.append(
                        f"{section}.{key}.{field_name}: desktop={desktop_value!r} web={web_value!r}"
                    )

    return diffs


def test_config_parity() -> None:
    diffs = _collect_parity_diffs()
    assert not diffs, "config.py (web) drifted from config_pydantic.py (desktop):\n" + "\n".join(diffs)


def test_web_config_is_fresh() -> None:
    generated = gen_web_config.generate_source()
    on_disk = CONFIG_PY.read_text(encoding="utf-8")
    if generated != on_disk:
        diff = "\n".join(
            difflib.unified_diff(
                on_disk.splitlines(), generated.splitlines(),
                fromfile="config.py (on disk)", tofile="config.py (generated now)",
                lineterm="",
            )
        )
        raise AssertionError(
            "config.py (web) is stale - it does not match what the generator "
            "produces right now. uruchom: just gen-web-config\n" + diff
        )


def test_web_config_has_no_desktop_model_references() -> None:
    on_disk = CONFIG_PY.read_text(encoding="utf-8")
    assert "pydantic" not in on_disk.lower(), (
        "config.py (web) references the desktop validation library - this is the "
        "one thing that breaks the web build immediately (pygbag/WASM can't import it)"
    )


if __name__ == "__main__":
    tests = [
        ("config parity (desktop vs web)", test_config_parity),
        ("web config is fresh", test_web_config_is_fresh),
        ("web config has no desktop-model references", test_web_config_has_no_desktop_model_references),
    ]
    failures = 0
    for name, func in tests:
        try:
            func()
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            failures += 1

    print(f"\n{'-' * 40}")
    total = len(tests)
    passed = total - failures
    if failures:
        print(f"  FAILED  {failures}/{total} tests")
        sys.exit(1)
    else:
        print(f"  PASSED  {passed}/{total} tests")
