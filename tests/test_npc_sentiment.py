#!/usr/bin/env python3
"""Unit tests for NPC sentiment / dialog model fields (T-023).

Pure logic (no pygame / SDL). Verifies that both config backends
(Pydantic desktop and dataclass web) expose the new Character fields
(dialog_key, disposition) and that Config carries the optional dialogs
section used to build DialogNode graphs at NPC load time.

Run from the project root:
    .venv/bin/python tests/test_npc_sentiment.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


def test_pydantic_character_has_new_fields() -> None:
    from config_model.config_pydantic import Character

    npc = Character(
        name="TestNpc",
        sprite="Villager1",
        race="humanoid",
        attitude="friendly",
        dialog_key="TEST_DIALOG",
        disposition=75,
    )
    assert_eq(npc.dialog_key, "TEST_DIALOG", "dialog_key stored")
    assert_eq(npc.disposition, 75, "disposition stored")


def test_pydantic_character_defaults() -> None:
    from config_model.config_pydantic import Character

    npc = Character(
        name="TestNpc",
        sprite="Villager1",
        race="humanoid",
        attitude="friendly",
    )
    assert npc.dialog_key is None
    assert_eq(npc.disposition, 50, "disposition default")


def test_web_character_has_new_fields() -> None:
    from config_model.config import Character

    npc = Character.from_dict(
        {
            "name": "TestNpc",
            "sprite": "Villager1",
            "race": "humanoid",
            "attitude": "friendly",
            "dialog_key": "TEST_DIALOG",
            "disposition": 75,
        }
    )
    assert_eq(npc.dialog_key, "TEST_DIALOG", "web dialog_key stored")
    assert_eq(npc.disposition, 75, "web disposition stored")


def test_web_character_defaults() -> None:
    from config_model.config import Character

    npc = Character.from_dict(
        {
            "name": "TestNpc",
            "sprite": "Villager1",
            "race": "humanoid",
            "attitude": "friendly",
        }
    )
    assert npc.dialog_key is None
    assert_eq(npc.disposition, 50, "web disposition default")


def test_web_config_carries_dialogs() -> None:
    from config_model.config import Config

    cfg = Config.build(
        {
            "characters": {},
            "chests": {},
            "items": {},
            "maze_configs": {},
            "dialogs": {"TEST_DIALOG": {"START_NODE": "N"}},
        }
    )
    assert_true("TEST_DIALOG" in cfg.dialogs, "dialogs section loaded")


def main() -> None:
    tests = [
        test_pydantic_character_has_new_fields,
        test_pydantic_character_defaults,
        test_web_character_has_new_fields,
        test_web_character_defaults,
        test_web_config_carries_dialogs,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} NPC sentiment tests passed.")


if __name__ == "__main__":
    main()
