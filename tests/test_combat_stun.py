#!/usr/bin/env python3
"""Ogłuszenie zawsze wygasa, a wpadnięcie na kogoś rozsuwa, a nie blokuje.

Zastany błąd, dla którego powstał ten plik: podczas walki gracz potrafił zostać
sparaliżowany na dobre - stał nałożony na wroga, migał, nie zadawał i nie
przyjmował obrażeń, a jedynym wyjściem było zamknięcie gry. Przyczyna: `is_stunned`
zdejmowało **zdarzenie z timera**, a wszystkie akcje jednej postaci dzielą jeden
`custom_event_id`. `pygame.time.set_timer` kluczuje timery typem zdarzenia, więc
wpadnięcie w trakcie ogłuszenia na przechodzące zwierzę uzbrajało akcję `pushed`,
kasowało czekające `stunned` - a obsługa `pushed` flagi nie zdejmuje. `Player.movement`
wychodzi natychmiast, gdy `is_stunned`, więc gracz tracił sterowanie do końca sesji.

Testy pilnują więc kontraktu, a nie ścieżki zdarzeń: **ogłuszenie ma wygasnąć z
zegara**, cokolwiek stanie się z timerami. Drugi zestaw dotyczy „odbicia": wpadnięcie
na zwierzę ma je odsunąć, bo `slide` w ostateczności cofa wchodzącego do `prev_pos`,
czyli z powrotem w to samo zderzenie - i mały kotek potrafił zablokować gracza.

Uruchamianie z katalogu projektu:
    .venv/bin/python tests/test_combat_stun.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame                                                    # noqa: E402
from pygame.math import Vector2 as vec                           # noqa: E402

from characters import combat                                    # noqa: E402
from enums import AttitudeEnum                                   # noqa: E402
from settings import NPC_PUSH_DISTANCE, PUSHED_TIME, STUNNED_TIME, TILE_SIZE   # noqa: E402

pygame.init()


class FakeHealthBar:
    def __init__(self) -> None:
        self.visible = False

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False


class FakeEmote:
    def __init__(self) -> None:
        self.emotes: list[str] = []

    def set_temporary_emote(self, name: str, duration: float) -> None:
        self.emotes.append(name)


class FakeGroup:
    def remove(self, *args: object) -> None:
        pass


class FakeScene:
    def __init__(self, walls: list[pygame.Rect] | None = None) -> None:
        self.walls = walls or []
        self.group = FakeGroup()


class FakeGame:
    def __init__(self) -> None:
        self.time_elapsed = 0.0


class FakeModel:
    def __init__(self, attitude: AttitudeEnum, health: int = 10, damage: int = 3) -> None:
        self.attitude = attitude
        self.health = health
        self.max_health = 10
        self.damage = damage


class FakeNpc:
    """Tyle z `NPC`, ile czytają funkcje z `characters/combat.py`."""

    def __init__(self, scene: FakeScene, game: FakeGame, pos: tuple[float, float],
                 attitude: AttitudeEnum = AttitudeEnum.friendly) -> None:
        self.scene = scene
        self.game = game
        self.model = FakeModel(attitude)
        self.pos = vec(pos)
        self.prev_pos = vec(pos)
        self.feet = pygame.Rect(0, 0, TILE_SIZE // 2, TILE_SIZE // 2)
        self.feet.midbottom = (int(self.pos.x), int(self.pos.y))
        self.health_bar = FakeHealthBar()
        self.emote = FakeEmote()
        self.is_stunned = False
        self.is_dead = False
        self.is_attacking = False
        self.can_switch_weapon = True
        self.selected_weapon = None
        self.weapon_cooldown = 0.0
        self.switch_cooldown = 0.0
        self.stun_cooldown = 0.0
        self.health_bar_cooldown = 0.0
        self.config_key = "NPC"
        self.deaths = 0

    def adjust_rect(self) -> None:
        self.feet.midbottom = (int(self.pos.x), int(self.pos.y))

    def die(self, drop_items: bool = True) -> None:
        self.deaths += 1
        self.is_dead = True


def _pair(walls: list[pygame.Rect] | None = None,
          attitude: AttitudeEnum = AttitudeEnum.friendly) -> tuple[FakeNpc, FakeNpc, FakeGame]:
    game = FakeGame()
    scene = FakeScene(walls)
    walker = FakeNpc(scene, game, (100.0, 100.0))
    other = FakeNpc(scene, game, (104.0, 100.0), attitude)
    return walker, other, game


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}\n  expected: {b!r}\n  actual:   {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


# ---------------------------------------------------------------------------
# Ogłuszenie wygasa z zegara
# ---------------------------------------------------------------------------

def test_a_stun_wears_off_by_the_clock() -> None:
    npc, _other, game = _pair()

    combat.stun(npc)
    assert_true(npc.is_stunned, "ogłuszenie nie weszło")

    game.time_elapsed = STUNNED_TIME / 1000.0 / 2
    combat.check_cooldown(npc)
    assert_true(npc.is_stunned, "ogłuszenie zeszło za wcześnie")

    game.time_elapsed = STUNNED_TIME / 1000.0 + 0.01
    combat.check_cooldown(npc)
    assert_true(not npc.is_stunned, "ogłuszenie nie zeszło po czasie")
    assert_true(not npc.health_bar.visible, "pasek życia został na ekranie")


def test_a_bump_during_a_stun_does_not_freeze_the_hero_forever() -> None:
    """Regresja właściwego błędu: kot przechodzący obok ogłuszonego gracza.

    Kiedyś zderzenie uzbrajało zdarzenie `pushed`, które kasowało czekające
    `stunned` - i `is_stunned` zostawało włączone do końca sesji.
    """
    npc, cat, game = _pair()
    combat.stun(npc)

    game.time_elapsed = 0.1
    combat.encounter(npc, cat)              # wpadnięcie na zwierzę w trakcie ogłuszenia

    game.time_elapsed = STUNNED_TIME / 1000.0 + 0.01
    combat.check_cooldown(npc)

    assert_true(not npc.is_stunned, "gracz został sparaliżowany na zawsze")


def test_a_clock_reset_does_not_freeze_a_character() -> None:
    """`game.time_elapsed` wraca do zera przy `reload_map` i wczytaniu zapisu.

    Termin z odległej przyszłości znaczy wtedy „zegar poszedł od nowa", a nie
    „jeszcze chwila" - inaczej postać stałaby zamrożona kilka minut.
    """
    npc, _other, game = _pair()
    game.time_elapsed = 500.0
    combat.stun(npc)

    game.time_elapsed = 0.0                 # przeładowanie mapy
    combat.check_cooldown(npc)

    assert_true(not npc.is_stunned, "cofnięty zegar zostawił postać ogłuszoną")


def test_ending_a_stun_twice_kills_only_once() -> None:
    """`end_stun` woła i odliczanie, i zaległe zdarzenie z timera."""
    npc, _other, _game = _pair()
    npc.model.health = 0
    combat.stun(npc)

    combat.end_stun(npc)
    combat.end_stun(npc)

    assert_eq(npc.deaths, 1, "śmierć poszła dwa razy")


def test_dying_a_second_time_is_a_no_op() -> None:
    """`die()` musi być jednorazowe.

    Drugie wejście gra dzwon śmierci jeszcze raz, a u gracza dodatkowo zdejmuje ze
    stosu dopiero co postawiony ekran śmierci i stawia następny. Test woła PRAWDZIWE
    `combat.die` na oznaczonym trupie: bez strażnika funkcja poszłaby dalej i wywróciła
    się na pierwszym polu sceny, którego atrapa nie ma.
    """
    npc, _other, _game = _pair()
    npc.is_dead = True
    npc.health_bar.visible = True

    combat.die(npc)                       # ma po prostu wyjść

    assert_true(npc.health_bar.visible, "drugie `die()` ruszyło stan postaci")


def test_a_dead_character_is_not_stunned() -> None:
    npc, _other, _game = _pair()
    npc.is_dead = True

    combat.stun(npc)

    assert_true(not npc.is_stunned, "trup nie ma prawa być ogłuszony")


# ---------------------------------------------------------------------------
# Odbicie zamiast blokady
# ---------------------------------------------------------------------------

def test_bumping_into_an_animal_pushes_it_away() -> None:
    walker, cat, _game = _pair()
    walker.prev_pos = vec(96.0, 100.0)      # szedł w prawo, na kota
    before = cat.pos.copy()

    combat.push_apart(walker, cat)

    assert_true(cat.pos.x > before.x, f"kot nie został odsunięty: {cat.pos}")
    assert_eq(round(cat.pos.distance_to(before)), NPC_PUSH_DISTANCE)
    assert_eq(walker.pos, vec(100.0, 100.0), "wchodzący nie miał się ruszyć")


def test_an_animal_with_its_back_to_a_wall_pushes_the_walker_instead() -> None:
    """Gdy nie ma dokąd odsunąć drugiego, cofa się wchodzący - nikt nie utyka."""
    wall = pygame.Rect(104, 84, TILE_SIZE, TILE_SIZE)
    walker, cat, _game = _pair(walls=[wall])
    walker.prev_pos = vec(96.0, 100.0)

    combat.push_apart(walker, cat)

    assert_eq(cat.pos, vec(104.0, 100.0), "kot został wepchnięty w ścianę")
    assert_true(walker.pos.x < 100.0, f"wchodzący się nie cofnął: {walker.pos}")


def test_perfectly_overlapping_characters_still_separate() -> None:
    """Zerowy wektor nie może dać `normalize()` po pustym - i nikt nie może utknąć."""
    walker, other, _game = _pair()
    other.pos = vec(walker.pos)
    other.prev_pos = vec(walker.pos)
    walker.prev_pos = vec(100.0, 96.0)      # szedł w dół

    combat.push_apart(walker, other)

    assert_true(walker.pos != other.pos, "postacie zostały jedna w drugiej")


def test_a_friendly_encounter_shows_the_health_bar_for_a_while() -> None:
    walker, cat, game = _pair()
    walker.prev_pos = vec(96.0, 100.0)

    combat.encounter(walker, cat)
    assert_true(cat.health_bar.visible, "pasek życia się nie pokazał")
    assert_eq(cat.emote.emotes, ["shocked_anim"])

    game.time_elapsed = PUSHED_TIME / 1000.0 + 0.01
    combat.check_cooldown(cat)
    assert_true(not cat.health_bar.visible, "pasek życia został na zawsze")


def test_an_enemy_encounter_stuns_both_sides() -> None:
    walker, monster, game = _pair(attitude=AttitudeEnum.enemy)

    combat.encounter(walker, monster)

    assert_true(walker.is_stunned and monster.is_stunned, "starcie nie ogłuszyło obu")
    game.time_elapsed = STUNNED_TIME / 1000.0 + 0.01
    combat.check_cooldown(walker)
    combat.check_cooldown(monster)
    assert_true(not walker.is_stunned and not monster.is_stunned, "ogłuszenie nie zeszło")


if __name__ == "__main__":
    tests = [
        ("ogłuszenie wygasa z zegara", test_a_stun_wears_off_by_the_clock),
        ("zderzenie w trakcie ogłuszenia nie zamraża na zawsze",
         test_a_bump_during_a_stun_does_not_freeze_the_hero_forever),
        ("cofnięty zegar nie zamraża postaci", test_a_clock_reset_does_not_freeze_a_character),
        ("podwójne zdjęcie ogłuszenia zabija raz", test_ending_a_stun_twice_kills_only_once),
        ("drugie `die()` nic nie robi", test_dying_a_second_time_is_a_no_op),
        ("trup nie jest ogłuszany", test_a_dead_character_is_not_stunned),
        ("wpadnięcie na zwierzę je odsuwa", test_bumping_into_an_animal_pushes_it_away),
        ("zwierzę pod ścianą odsuwa wchodzącego",
         test_an_animal_with_its_back_to_a_wall_pushes_the_walker_instead),
        ("idealne nałożenie też się rozsuwa", test_perfectly_overlapping_characters_still_separate),
        ("zderzenie pokazuje pasek życia na chwilę",
         test_a_friendly_encounter_shows_the_health_bar_for_a_while),
        ("starcie z wrogiem ogłusza obu", test_an_enemy_encounter_stuns_both_sides),
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
