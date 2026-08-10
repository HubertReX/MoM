#!/usr/bin/env python3
"""Reżyser barków: kto się odzywa, kiedy i czym (H01, etap 2).

Czysta logika `BarkDirector` na atrapach sceny - bez ekranu, bez pygame'a poza
wektorem pozycji. To, czego pilnuje ten plik, to reguły, które w grze widać
dopiero po kilku minutach chodzenia po wsi:

- **cisza jest stanem domyślnym** - postać bez pasującej kwestii nie mówi nic,
  a nie „coś",
- **wieś nie tyka jak zegarek** - rzut kością raz na wejście w promień, cooldowny
  per postać i globalny, twardy limit dwóch barków naraz,
- **ten sam żart nie leci dwa razy pod rząd** - inaczej wychodzi z tego usterka,
  a nie żart,
- **ten sam seed daje ten sam ciąg** - bez tego każda asercja scenariusza
  agentowego jest zgadywanką (A04).

Uruchamianie z katalogu projektu:
    .venv/bin/python tests/test_barks.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import random

from pygame.math import Vector2 as vec

from characters.barks import BarkDirector
from npc_schedule import Slot
from settings import (
    BARK_COOLDOWN_GLOBAL,
    BARK_COOLDOWN_NPC,
    BARK_MAX_ON_SCREEN,
    BARK_RADIUS_TILES,
    BARK_ROUTINE_RADIUS_TILES,
    TILE_SIZE,
)


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}\n  expected: {b!r}\n  actual:   {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


# ---------------------------------------------------------------------------
# Atrapy
# ---------------------------------------------------------------------------

class FakeBark:
    """Tyle z `BarkSprite`, ile widzi reżyser."""

    def __init__(self) -> None:
        self.message_key = ""
        self.text = ""
        self.is_speaking = False

    def say(self, text: str, message_key: str = "") -> None:
        self.text = text
        self.message_key = message_key
        self.is_speaking = True

    def silence(self) -> None:
        self.message_key = ""
        self.text = ""
        self.is_speaking = False


class FakeModel:
    def __init__(self, pool: str = "") -> None:
        self.barks = pool


class FakeNpc:
    def __init__(self, key: str, pos: tuple[float, float] = (0.0, 0.0), pool: str = "") -> None:
        self.config_key = key
        self.name = key
        self.pos = vec(pos)
        self.model = FakeModel(pool)
        self.bark = FakeBark()
        self.is_dead = False
        self.is_asleep = False
        self.sentiment = 50
        self.dialog_nodes: dict[str, object] = {}
        self.runtime = type("R", (), {"logical_map": "BLUNDERHAVEN"})()
        self.current_map = "BLUNDERHAVEN"
        self._schedule_slot: Slot | None = None


class FakeConf:
    def __init__(self, barks: dict[str, list[dict[str, str]]]) -> None:
        self.barks = barks
        texts = {
            entry["msg"]: f"tekst {entry['msg']}"
            for entries in barks.values() for entry in entries
        }
        self.messages = {"PL": dict(texts), "EN": dict(texts)}


class FakePlayer:
    def __init__(self, scene: "FakeScene") -> None:
        self.pos = vec(0, 0)
        self.items: list[object] = []
        self.scene = scene


class FakeGame:
    def __init__(self, conf: FakeConf) -> None:
        self.conf = conf


class FakeScene:
    def __init__(self, npcs: list[FakeNpc], barks: dict[str, list[dict[str, str]]],
                 seed: int | None = 12345) -> None:
        self.NPCs = npcs
        self.game = FakeGame(FakeConf(barks))
        self.player = FakePlayer(self)
        self.hour = 12
        self.minute = 0
        self.quest_state = None
        self.loaded_NPCs = {npc.config_key: npc for npc in npcs}
        self._seed = seed

    def _particle_rng(self) -> "random.Random | None":
        return random.Random(self._seed) if self._seed is not None else None


def _director(npcs: list[FakeNpc], barks: dict[str, list[dict[str, str]]],
              seed: int | None = 12345) -> BarkDirector:
    return BarkDirector(FakeScene(npcs, barks, seed))       # type: ignore[arg-type]


def _entries(*keys: str) -> list[dict[str, str]]:
    return [{"msg": key, "condition": "True"} for key in keys]


NEAR = (BARK_RADIUS_TILES - 0.5) * TILE_SIZE
#: Za daleko na zaczepkę „na zbliżenie", w sam raz na barka z rutyny - jedyna
#: odległość, na której da się testować wyzwalacz z rutyny w izolacji.
NEWS_ONLY = (BARK_RADIUS_TILES + 1.0) * TILE_SIZE
FAR = (BARK_ROUTINE_RADIUS_TILES + 5) * TILE_SIZE


# ---------------------------------------------------------------------------
# Skąd biorą się kwestie
# ---------------------------------------------------------------------------

def test_own_section_and_pool_sum() -> None:
    """D2: pula nie wyklucza własnych linii, tylko je uzupełnia."""
    npc = FakeNpc("BART", pool="VILLAGERS")
    director = _director([npc], {"BART": _entries("bark.BART.001"),
                                 "VILLAGERS": _entries("bark.VILLAGERS.001")})

    assert_eq([e["msg"] for e in director.candidates_for(npc)],
              ["bark.BART.001", "bark.VILLAGERS.001"])


def test_an_empty_pool_cell_is_not_an_error() -> None:
    """Postać bez puli bierze tylko swoje - i to jest normalny stan."""
    npc = FakeNpc("BART")
    director = _director([npc], {"BART": _entries("bark.BART.001"),
                                 "VILLAGERS": _entries("bark.VILLAGERS.001")})

    assert_eq([e["msg"] for e in director.candidates_for(npc)], ["bark.BART.001"])


def test_a_character_with_nothing_to_say_stays_silent() -> None:
    npc = FakeNpc("SNAKE")
    director = _director([npc], {})

    assert_eq(director.speak(npc), False, "postać bez kwestii nie ma się odzywać")
    assert_eq(npc.bark.is_speaking, False)


def test_conditions_filter_the_candidates() -> None:
    npc = FakeNpc("BART")
    director = _director([npc], {"BART": [
        {"msg": "bark.BART.001", "condition": 'time_of_day("day")'},
        {"msg": "bark.BART.002", "condition": 'time_of_day("night")'},
    ]})

    assert_eq([e["msg"] for e in director.candidates_for(npc)], ["bark.BART.001"])


def test_a_broken_condition_silences_one_line_not_the_game() -> None:
    """Importer i reguła 20 łapią to wcześniej; tu chodzi o to, żeby nie było wyjątku."""
    npc = FakeNpc("BART")
    director = _director([npc], {"BART": [
        {"msg": "bark.BART.001", "condition": "to nie ==== warunek"},
        {"msg": "bark.BART.002", "condition": "True"},
    ]})

    assert_eq([e["msg"] for e in director.candidates_for(npc)], ["bark.BART.002"])


# ---------------------------------------------------------------------------
# Kiedy wolno mówić
# ---------------------------------------------------------------------------

def test_the_player_walking_up_can_trigger_a_bark() -> None:
    npc = FakeNpc("BART", (NEAR, 0))
    director = _director([npc], {"BART": _entries("bark.BART.001")})

    # kilka klatek: rzut kością jest jednorazowy per wejście w promień, więc
    # rozstrzyga pierwsza klatka - dlatego test ustawia szansę na pewność
    director.rng = random.Random(1)
    for _ in range(3):
        director.update(1 / 60)
        director.global_cooldown = 0.0
        if npc.bark.is_speaking:
            break
        director._in_range.clear()

    assert_true(npc.bark.is_speaking, "postać obok gracza nigdy się nie odezwała")


def test_a_distant_character_never_speaks() -> None:
    npc = FakeNpc("BART", (FAR, 0))
    director = _director([npc], {"BART": _entries("bark.BART.001")})

    for _ in range(120):
        director.update(1 / 60)
        director.global_cooldown = 0.0
        director._in_range.clear()

    assert_eq(npc.bark.is_speaking, False, "postać z drugiego końca mapy zagadała")


def test_speaking_arms_both_cooldowns() -> None:
    npc = FakeNpc("BART", (NEAR, 0))
    director = _director([npc], {"BART": _entries("bark.BART.001")})

    director.speak(npc)

    assert_eq(director.cooldowns["BART"], BARK_COOLDOWN_NPC)
    assert_eq(director.global_cooldown, BARK_COOLDOWN_GLOBAL)


def test_a_character_on_cooldown_is_skipped() -> None:
    npc = FakeNpc("BART", (NEAR, 0))
    director = _director([npc], {"BART": _entries("bark.BART.001")})
    director.cooldowns["BART"] = 30.0

    for _ in range(60):
        director.update(1 / 60)
        director.global_cooldown = 0.0
        director._in_range.clear()

    assert_eq(npc.bark.is_speaking, False, "cooldown per postać nie zadziałał")


def test_cooldowns_expire() -> None:
    director = _director([], {})
    director.cooldowns["BART"] = 0.5
    director.global_cooldown = 0.5

    for _ in range(60):
        director.update(1 / 60)

    assert_true("BART" not in director.cooldowns, "cooldown postaci nie wygasł")
    assert_eq(director.global_cooldown, 0.0)


def test_the_sleeping_and_the_dead_do_not_talk() -> None:
    """`sleep` ma własny kanał - stałe `zzz` nad głową, nie kwestię."""
    sleeper = FakeNpc("BART", (NEAR, 0))
    sleeper.is_asleep = True
    corpse = FakeNpc("SNAKE", (NEAR, 0))
    corpse.is_dead = True
    director = _director([sleeper, corpse],
                         {"BART": _entries("b.1"), "SNAKE": _entries("s.1")})

    for _ in range(120):
        director.update(1 / 60)
        director.global_cooldown = 0.0
        director._in_range.clear()

    assert_eq(director.active(), [], "śpiący albo martwy się odezwał")


def test_at_most_two_barks_at_once() -> None:
    """Trzeci przepada, nie czeka: bark jest tłem, nie wiadomością."""
    npcs = [FakeNpc(f"N{i}", (NEAR, 0)) for i in range(5)]
    director = _director(npcs, {npc.config_key: _entries(f"{npc.config_key}.001")
                                for npc in npcs})

    for _ in range(600):
        director.update(1 / 60)
        director.global_cooldown = 0.0
        director._in_range.clear()
        assert_true(len(director.active()) <= BARK_MAX_ON_SCREEN,
                    f"{len(director.active())} barków naraz")


# ---------------------------------------------------------------------------
# Wyzwalacz z rutyny (W4)
# ---------------------------------------------------------------------------

def test_a_slot_change_gives_a_character_something_to_say() -> None:
    """Postać, której właśnie zmienił się krok dnia, gada bez rzutu kością.

    Odległość celowo POZA promieniem zaczepki: inaczej test nie odróżniłby
    wyzwalacza z rutyny od zwykłego „gracz podszedł".
    """
    npc = FakeNpc("BART", (NEWS_ONLY, 0))
    npc._schedule_slot = Slot(from_minutes=480, at="type:work", activity="stand")
    director = _director([npc], {"BART": _entries("bark.BART.001")})

    director.update(1 / 60)                 # pierwszy odczyt = poznanie stanu
    assert_eq(npc.bark.is_speaking, False, "pierwszy odczyt slotu to nie zmiana")

    npc._schedule_slot = Slot(from_minutes=780, at="type:social", activity="wander")
    director.global_cooldown = 0.0
    director.update(1 / 60)

    assert_true(npc.bark.is_speaking, "zmiana kroku rutyny nie odpaliła barka")


def test_the_first_reading_of_a_slot_is_not_a_change() -> None:
    """Inaczej cała wieś zagadałaby w pierwszej klatce po wczytaniu zapisu."""
    npcs = [FakeNpc(f"N{i}", (NEWS_ONLY, 0)) for i in range(4)]
    for npc in npcs:
        npc._schedule_slot = Slot(from_minutes=480, at="type:work", activity="stand")
    director = _director(npcs, {npc.config_key: _entries(f"{npc.config_key}.001")
                                for npc in npcs})

    director.update(1 / 60)

    assert_eq(director._has_news, set(), "pierwszy odczyt zrobił z całej wsi nowinę")


def test_news_is_consumed_even_with_nothing_to_say() -> None:
    """Bez tego postać bez pasującej kwestii próbowałaby w każdej klatce."""
    npc = FakeNpc("SNAKE", (NEAR, 0))
    director = _director([npc], {})
    director._has_news.add("SNAKE")

    director.speak(npc)

    assert_true("SNAKE" not in director._has_news, "nowina się nie zużyła")


# ---------------------------------------------------------------------------
# Wybór kwestii (D5)
# ---------------------------------------------------------------------------

def test_the_same_line_never_comes_twice_in_a_row() -> None:
    npc = FakeNpc("BART", (NEAR, 0))
    director = _director([npc], {"BART": _entries("b.1", "b.2", "b.3")})

    said: list[str] = []
    for _ in range(30):
        director.cooldowns.clear()
        npc.bark.silence()
        director.speak(npc)
        said.append(npc.bark.message_key)

    repeats = [(a, b) for a, b in zip(said, said[1:]) if a == b]
    assert_eq(repeats, [], f"kwestia powtórzona pod rząd w {said}")


def test_a_single_candidate_may_repeat() -> None:
    """Przy jednej kwestii wykluczać nie ma czego - powtórzenie to jedyna treść."""
    npc = FakeNpc("BART", (NEAR, 0))
    director = _director([npc], {"BART": _entries("b.1")})

    for _ in range(3):
        director.cooldowns.clear()
        npc.bark.silence()
        assert_eq(director.speak(npc), True)
    assert_eq(npc.bark.message_key, "b.1")


def test_the_text_comes_from_the_message_table() -> None:
    npc = FakeNpc("BART", (NEAR, 0))
    director = _director([npc], {"BART": _entries("b.1")})

    director.speak(npc)

    assert_eq(npc.bark.text, "tekst b.1")


# ---------------------------------------------------------------------------
# Determinizm (A04)
# ---------------------------------------------------------------------------

def _sequence(seed: int | None) -> list[str]:
    npcs = [FakeNpc(f"N{i}", (NEAR, i * 2.0)) for i in range(4)]
    director = _director(npcs, {npc.config_key: _entries(f"{npc.config_key}.1",
                                                         f"{npc.config_key}.2")
                                for npc in npcs}, seed=seed)
    said: list[str] = []
    for frame in range(900):
        director.update(1 / 60)
        said.extend(entry["msg"] for entry in director.active()
                    if not said or said[-1] != entry["msg"])
        if frame % 30 == 0:
            director.cooldowns.clear()
            director.global_cooldown = 0.0
            director._in_range.clear()
            for npc in npcs:
                npc.bark.silence()
    return said[:10]


def test_the_same_seed_gives_the_same_sequence() -> None:
    """Bez tego każda asercja scenariusza agentowego jest zgadywanką."""
    assert_eq(_sequence(12345), _sequence(12345), "ten sam seed dał inny ciąg barków")


def test_a_different_seed_gives_a_different_sequence() -> None:
    """Kontrola przytomności: gdyby ciąg był stały, poprzedni test nic by nie znaczył."""
    assert_true(_sequence(12345) != _sequence(999), "seed nie ma wpływu na losowanie")


def test_the_live_world_is_not_seeded() -> None:
    """Poza trybem deterministycznym wieś ma być nieprzewidywalna."""
    director = _director([], {}, seed=None)

    assert_true(isinstance(director.rng, random.Random))


# ---------------------------------------------------------------------------
# Zrzut stanu (A02)
# ---------------------------------------------------------------------------

def test_active_reports_who_speaks_and_with_what() -> None:
    npc = FakeNpc("BART", (NEAR, 0))
    director = _director([npc], {"BART": _entries("b.1")})
    director.speak(npc)

    assert_eq(director.active(), [{"npc": "BART", "msg": "b.1"}])


if __name__ == "__main__":
    tests = [
        ("własna sekcja i pula sumują się", test_own_section_and_pool_sum),
        ("pusta pula nie jest błędem", test_an_empty_pool_cell_is_not_an_error),
        ("postać bez kwestii milczy", test_a_character_with_nothing_to_say_stays_silent),
        ("warunki filtrują kandydatów", test_conditions_filter_the_candidates),
        ("zły warunek wycisza jedną linię", test_a_broken_condition_silences_one_line_not_the_game),
        ("zbliżenie gracza odpala barka", test_the_player_walking_up_can_trigger_a_bark),
        ("daleka postać milczy", test_a_distant_character_never_speaks),
        ("bark uzbraja oba cooldowny", test_speaking_arms_both_cooldowns),
        ("postać na cooldownie pominięta", test_a_character_on_cooldown_is_skipped),
        ("cooldowny wygasają", test_cooldowns_expire),
        ("śpiący i martwi nie gadają", test_the_sleeping_and_the_dead_do_not_talk),
        ("najwyżej dwa barki naraz", test_at_most_two_barks_at_once),
        ("zmiana kroku rutyny odpala barka", test_a_slot_change_gives_a_character_something_to_say),
        ("pierwszy odczyt slotu to nie zmiana", test_the_first_reading_of_a_slot_is_not_a_change),
        ("nowina zużywa się bez kwestii", test_news_is_consumed_even_with_nothing_to_say),
        ("brak powtórki pod rząd", test_the_same_line_never_comes_twice_in_a_row),
        ("jedyny kandydat może się powtórzyć", test_a_single_candidate_may_repeat),
        ("tekst z tablicy wiadomości", test_the_text_comes_from_the_message_table),
        ("ten sam seed = ten sam ciąg", test_the_same_seed_gives_the_same_sequence),
        ("inny seed = inny ciąg", test_a_different_seed_gives_a_different_sequence),
        ("żywy świat nie jest zasiany", test_the_live_world_is_not_seeded),
        ("active() raportuje kto i czym", test_active_reports_who_speaks_and_with_what),
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
