#!/usr/bin/env python3
"""Zamek na skrzyni i na drzwiach - jeden kształt w dwóch miejscach (H01/D8).

Nie dwa mechanizmy, tylko jeden: skrzynia czyta ``requires_item`` /
``consumes_key`` z `chests.csv`, drzwi te same dwie WŁASNOŚCI z obiektu Tiled,
i obie strony wołają `scene.player_actions.unlock`. Gdyby to były dwie ścieżki,
rozjechałyby się przy pierwszej poprawce - a klucz jednorazowy zużyty przy
skrzyni i niezużyty przy drzwiach to błąd, którego gracz nie zgłosi, tylko
zapamięta jako „ta gra jest dziwna".

Co tu jest pilnowane:

- **pusty ``requires_item`` = brak zamka** - to stan wszystkich dzisiejszych
  skrzyń i drzwi, więc musi być darmowy i cichy,
- **odmowa nazywa brakujący przedmiot** - dokładnie jak `notify.weapon_too_weak`
  przy za słabej broni; „nic się nie stało" jest nieodróżnialne od scenerii,
- **klucz znika PO otwarciu, nie przy podejściu** - inaczej samo dotknięcie
  zamkniętych drzwi zjadałoby go bez skutku.

Bez ekranu: `unlock` dostaje atrapę sceny.

Uruchamianie z katalogu projektu:
    .venv/bin/python tests/test_locks_and_keys.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from scene.player_actions import unlock


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}\n  expected: {b!r}\n  actual:   {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


class FakeItem:
    def __init__(self, name: str) -> None:
        self.name = name


class FakePlayer:
    def __init__(self, *items: str) -> None:
        self.items = [FakeItem(name) for name in items]

    def drop_item(self, show: bool = True, item: object = None) -> object:
        assert_eq(show, False, "klucz ma zniknąć z ekwipunku, a nie wylądować na ziemi")
        self.items.remove(item)          # type: ignore[arg-type]
        return item


class FakeConf:
    items = {"golden_key": type("M", (), {"name_PL": "Złoty klucz", "name_EN": "Golden key"})()}


class FakeGame:
    conf = FakeConf()


class FakeScene:
    def __init__(self, *items: str) -> None:
        self.player = FakePlayer(*items)
        self.game = FakeGame()
        self.notifications: list[str] = []

    def add_notification(self, message: str, kind: object = None) -> None:
        self.notifications.append(message)


# ---------------------------------------------------------------------------
# Brak zamka
# ---------------------------------------------------------------------------

def test_no_lock_opens_and_says_nothing() -> None:
    """Stan wszystkich dzisiejszych skrzyń i drzwi - musi być darmowy."""
    scene = FakeScene()

    assert_eq(unlock(scene, "", False), True)              # type: ignore[arg-type]
    assert_eq(scene.notifications, [])


def test_no_lock_never_eats_an_item() -> None:
    scene = FakeScene("golden_key")

    unlock(scene, "", True)                                # type: ignore[arg-type]

    assert_eq(len(scene.player.items), 1, "brak zamka zjadł przedmiot")


# ---------------------------------------------------------------------------
# Odmowa
# ---------------------------------------------------------------------------

def test_a_missing_key_refuses() -> None:
    scene = FakeScene()

    assert_eq(unlock(scene, "golden_key", False), False)    # type: ignore[arg-type]


def test_the_refusal_names_the_item_the_player_lacks() -> None:
    """„Nic się nie stało" jest nieodróżnialne od zwykłej scenerii."""
    scene = FakeScene()

    unlock(scene, "golden_key", False)                      # type: ignore[arg-type]

    assert_eq(len(scene.notifications), 1, "odmowa była cicha")
    assert_true("klucz" in scene.notifications[0].lower(),
                f"komunikat nie nazywa przedmiotu: {scene.notifications[0]}")


def test_an_unknown_item_key_still_produces_a_message() -> None:
    """Reguła 19 walidatora to łapie, ale runtime i tak nie ma prawa milczeć."""
    scene = FakeScene()

    unlock(scene, "nie_ma_takiego", False)                   # type: ignore[arg-type]

    assert_eq(len(scene.notifications), 1)
    assert_true("nie_ma_takiego" in scene.notifications[0], scene.notifications[0])


# ---------------------------------------------------------------------------
# Otwarcie
# ---------------------------------------------------------------------------

def test_holding_the_key_opens() -> None:
    scene = FakeScene("golden_key")

    assert_eq(unlock(scene, "golden_key", False), True)      # type: ignore[arg-type]
    assert_eq(scene.notifications, [], "udane otwarcie nie potrzebuje toasta")


def test_a_reusable_key_stays_in_the_bag() -> None:
    scene = FakeScene("golden_key")

    unlock(scene, "golden_key", False)                       # type: ignore[arg-type]

    assert_true(any(item.name == "golden_key" for item in scene.player.items),
                "klucz wielorazowy zniknął")


def test_a_single_use_key_is_consumed() -> None:
    scene = FakeScene("golden_key")

    unlock(scene, "golden_key", True)                        # type: ignore[arg-type]

    assert_eq(scene.player.items, [], "klucz jednorazowy został w ekwipunku")


def test_only_the_matching_key_is_consumed() -> None:
    scene = FakeScene("silver_key", "golden_key", "life_pot")

    unlock(scene, "golden_key", True)                        # type: ignore[arg-type]

    assert_eq(sorted(item.name for item in scene.player.items), ["life_pot", "silver_key"])


# ---------------------------------------------------------------------------
# Tryb "tylko zapytaj"
# ---------------------------------------------------------------------------

def test_quiet_neither_speaks_nor_consumes() -> None:
    """Podpowiedź na HUD-zie PYTA o zamek - nie wolno jej zjeść klucza."""
    scene = FakeScene("golden_key")

    assert_eq(unlock(scene, "golden_key", True, quiet=True), True)   # type: ignore[arg-type]
    assert_eq(len(scene.player.items), 1, "zapytanie zjadło klucz")
    assert_eq(scene.notifications, [])


def test_quiet_still_answers_no() -> None:
    scene = FakeScene()

    assert_eq(unlock(scene, "golden_key", False, quiet=True), False)  # type: ignore[arg-type]
    assert_eq(scene.notifications, [], "cichy tryb jednak zagadał")


# ---------------------------------------------------------------------------
# Dane
# ---------------------------------------------------------------------------

def test_both_key_items_exist_and_are_of_type_key() -> None:
    """`golden_key` i `silver_key` leżały w items.csv nic nie robiąc - to ich pierwsza rola."""
    import csv
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "project/config_model/items.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = {row["key"]: row for row in csv.DictReader(handle, delimiter=";")}

    for key in ("golden_key", "silver_key"):
        assert_true(key in rows, f"brakuje przedmiotu '{key}'")
        assert_eq(rows[key]["type"], "key", f"'{key}' nie jest typu key")


def test_the_chest_csv_carries_both_lock_columns() -> None:
    """Bez kolumn w CSV pola z modelu nigdy by się nie wypełniły."""
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "project/config_model/chests.csv"
    header = path.read_text(encoding="utf-8").splitlines()[0].split(";")

    assert_true("requires_item" in header, f"brak kolumny requires_item: {header}")
    assert_true("consumes_key" in header, f"brak kolumny consumes_key: {header}")


def test_the_web_config_mirror_has_the_lock_fields() -> None:
    """Złota zasada dual-target: pominięty `just gen-web-config` wywala się DOPIERO na web."""
    from config_model.config import Chest

    fields = Chest.__dataclass_fields__

    assert_true("requires_item" in fields, "web config nie ma requires_item - uruchom gen-web-config")
    assert_true("consumes_key" in fields, "web config nie ma consumes_key - uruchom gen-web-config")


def test_a_door_collider_defaults_to_unlocked() -> None:
    """Wszystkie dzisiejsze drzwi nie mają własności zamka - i mają działać jak dotąd."""
    import pygame
    from objects import Collider

    pygame.init()
    pygame.display.set_mode((64, 64))
    door = Collider(pygame.sprite.Group(), (0, 0), (16, 16), "Door", "MAP", "entry")

    assert_eq(door.requires_item, "")
    assert_eq(door.consumes_key, False)


if __name__ == "__main__":
    tests = [
        ("brak zamka otwiera i milczy", test_no_lock_opens_and_says_nothing),
        ("brak zamka nie je przedmiotu", test_no_lock_never_eats_an_item),
        ("brak klucza = odmowa", test_a_missing_key_refuses),
        ("odmowa nazywa przedmiot", test_the_refusal_names_the_item_the_player_lacks),
        ("nieznany klucz też ma komunikat", test_an_unknown_item_key_still_produces_a_message),
        ("klucz w ręku otwiera", test_holding_the_key_opens),
        ("klucz wielorazowy zostaje", test_a_reusable_key_stays_in_the_bag),
        ("klucz jednorazowy znika", test_a_single_use_key_is_consumed),
        ("znika tylko pasujący klucz", test_only_the_matching_key_is_consumed),
        ("quiet nie gada i nie je", test_quiet_neither_speaks_nor_consumes),
        ("quiet nadal odpowiada nie", test_quiet_still_answers_no),
        ("oba klucze istnieją i są typu key", test_both_key_items_exist_and_are_of_type_key),
        ("chests.csv ma obie kolumny", test_the_chest_csv_carries_both_lock_columns),
        ("web config ma pola zamka", test_the_web_config_mirror_has_the_lock_fields),
        ("drzwi domyślnie otwarte", test_a_door_collider_defaults_to_unlocked),
    ]
    failures = 0
    for name, func in tests:
        try:
            func()
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            import traceback

            traceback.print_exc()
            failures += 1

    print(f"\n{'─' * 40}")
    total = len(tests)
    passed = total - failures
    if failures:
        print(f"  FAILED  {failures}/{total} tests")
        sys.exit(1)
    else:
        print(f"  PASSED  {passed}/{total} tests")
