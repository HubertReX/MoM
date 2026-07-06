#!/usr/bin/env python3
"""Unit tests for NPC sentiment / dialog model fields (T-023 / T-035).

Pure logic (no pygame / SDL). Verifies that both config backends
(Pydantic desktop and dataclass web) expose the new Character fields
(dialog_key, disposition as a per-sentiment dict) and that Config carries
the optional dialogs section used to build DialogNode graphs at NPC load time.

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


_CUSTOM_DISPOSITION: dict[str, int] = {
    "blessed": 15,
    "blink": 5,
    "wondering": 2,
    "neutral": 0,
    "human": 0,
    "offended": -5,
    "angry": -15,
}


def test_pydantic_character_has_new_fields() -> None:
    from config_model.config_pydantic import Character

    npc = Character(
        name="TestNpc",
        sprite="Villager1",
        race="humanoid",
        attitude="friendly",
        dialog_key="TEST_DIALOG",
        disposition=dict(_CUSTOM_DISPOSITION),
    )
    assert_eq(npc.dialog_key, "TEST_DIALOG", "dialog_key stored")
    assert_eq(npc.disposition, _CUSTOM_DISPOSITION, "disposition stored")


def test_pydantic_character_defaults() -> None:
    from config_model.config_pydantic import Character
    from settings import DEFAULT_DISPOSITION_WEIGHTS

    npc = Character(
        name="TestNpc",
        sprite="Villager1",
        race="humanoid",
        attitude="friendly",
    )
    assert npc.dialog_key is None
    assert_eq(npc.disposition, DEFAULT_DISPOSITION_WEIGHTS, "disposition default")


def test_web_character_has_new_fields() -> None:
    from config_model.config import Character

    npc = Character.from_dict(
        {
            "name": "TestNpc",
            "sprite": "Villager1",
            "race": "humanoid",
            "attitude": "friendly",
            "dialog_key": "TEST_DIALOG",
            "disposition": _CUSTOM_DISPOSITION,
        }
    )
    assert_eq(npc.dialog_key, "TEST_DIALOG", "web dialog_key stored")
    assert_eq(npc.disposition, _CUSTOM_DISPOSITION, "web disposition stored")


def test_web_character_defaults() -> None:
    from config_model.config import Character
    from settings import DEFAULT_DISPOSITION_WEIGHTS

    npc = Character.from_dict(
        {
            "name": "TestNpc",
            "sprite": "Villager1",
            "race": "humanoid",
            "attitude": "friendly",
        }
    )
    assert npc.dialog_key is None
    assert_eq(npc.disposition, DEFAULT_DISPOSITION_WEIGHTS, "web disposition default")


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


def test_npc_apply_option_sentiment_clamps() -> None:
    """Choosing an option shifts NPC sentiment by its disposition weight (T-035)."""
    from characters import NPC
    from dialog.entities import DialogNode, DialogOption

    npc = NPC.__new__(NPC)
    npc.sentiment = 50
    npc.disposition = {"blessed": 25, "angry": -60}
    npc.known_disposition = {}

    assert_eq(npc.apply_option_sentiment("blessed"), 25, "blessed shift returned")
    assert_eq(npc.sentiment, 75, "sentiment increased")
    assert_eq(npc.known_disposition, {"blessed": 25}, "blessed weight discovered")

    # clamp at 100
    assert_eq(npc.apply_option_sentiment("blessed"), 25, "blessed shift returned again")
    assert_eq(npc.sentiment, 100, "sentiment clamped to 100")

    # negative shift clamped at 0
    npc.sentiment = 10
    assert_eq(npc.apply_option_sentiment("angry"), -60, "angry shift returned")
    assert_eq(npc.sentiment, 0, "sentiment clamped to 0")
    assert "angry" in npc.known_disposition, "angry weight discovered"


def test_npc_apply_unknown_sentiment_defaults_to_zero() -> None:
    """Unknown sentiment keys apply no shift but are still marked discovered."""
    from characters import NPC

    npc = NPC.__new__(NPC)
    npc.sentiment = 50
    npc.disposition = {"neutral": 0}
    npc.known_disposition = {}

    assert_eq(npc.apply_option_sentiment("custom"), 0, "unknown shift is 0")
    assert_eq(npc.sentiment, 50, "sentiment unchanged")
    assert_eq(npc.known_disposition, {"custom": 0}, "unknown weight discovered as 0")


def test_trade_price_multipliers() -> None:
    """Sentiment-based trade multipliers scale around neutral (50)."""
    from settings import get_buy_price_multiplier, get_sell_price_multiplier

    assert_eq(get_buy_price_multiplier(50), 1.0, "neutral buy multiplier")
    assert_eq(get_sell_price_multiplier(50), 1.0, "neutral sell multiplier")
    assert_true(get_buy_price_multiplier(100) < 1.0, "high sentiment buy discount")
    assert_true(get_sell_price_multiplier(100) > 1.0, "high sentiment sell premium")
    assert_true(get_buy_price_multiplier(0) > 1.0, "low sentiment buy penalty")
    assert_true(get_sell_price_multiplier(0) < 1.0, "low sentiment sell penalty")


def main() -> None:
    tests = [
        test_pydantic_character_has_new_fields,
        test_pydantic_character_defaults,
        test_web_character_has_new_fields,
        test_web_character_defaults,
        test_web_config_carries_dialogs,
        test_npc_apply_option_sentiment_clamps,
        test_npc_apply_unknown_sentiment_defaults_to_zero,
        test_trade_price_multipliers,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} NPC sentiment tests passed.")


if __name__ == "__main__":
    main()
