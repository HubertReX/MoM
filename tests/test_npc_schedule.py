#!/usr/bin/env python3
"""Tests for daily routines: which slot is in force, and where it points.

The whole module is a pure function of its arguments, which is the point - the
schedule can be pinned down completely without a display, a map or a save.

Two properties matter more than the rest:

- **Order in the file is meaningless.** Execution order comes from `from`, so a
  step can be inserted in the middle of routines.toml without disturbing anything.
- **Missing data is never an exception.** An empty CSV cell, a place Tiled does
  not have yet, a typo in a prefix - all of them mean "this character has no
  destination right now", so a half-mapped village stays playable.

Run from the project root:
    .venv/bin/python tests/test_npc_schedule.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from npc_schedule import (
    Destination,
    Routine,
    Slot,
    current_slot,
    destinations_of,
    load_routines,
    parse_routines,
    parse_time,
    resolve_at,
    slot_jitter,
)

# The townsfolk rhythm, written here in a deliberately scrambled order.
_TOWNSFOLK = {
    "routine": {
        "townsfolk": {
            "slot": [
                {"from": "20:00", "at": "type:home", "activity": "sleep"},
                {"from": "08:00", "at": "type:work", "activity": "stand"},
                {"from": "13:00", "at": "type:social", "activity": "wander"},
                {"from": "06:30", "at": "type:home", "activity": "idle"},
            ]
        }
    },
    "assign": {"Johny": "townsfolk"},
}


def _routine(*pairs: tuple[str, str]) -> Routine:
    return Routine(
        key="test",
        slots=tuple(sorted(
            (Slot(parse_time(t), at, "stand") for t, at in pairs),
            key=lambda s: s.from_minutes,
        )),
    )


def _at(hour: int, minute: int = 0) -> int:
    return hour * 60 + minute


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def test_time_parsing() -> None:
    assert parse_time("00:00") == 0
    assert parse_time("06:30") == 390
    assert parse_time("23:59") == 1439


def test_slots_are_sorted_regardless_of_file_order() -> None:
    """Reordering routines.toml must not change behaviour."""
    parsed = parse_routines(_TOWNSFOLK)
    starts = [s.from_minutes for s in parsed.routines["townsfolk"].slots]

    assert starts == sorted(starts), f"slots not sorted: {starts}"
    assert starts[0] == _at(6, 30), "earliest step is not first"


def test_a_broken_slot_is_skipped_not_fatal() -> None:
    """One typo in the file must not take the other steps down with it."""
    warnings: list[str] = []
    parsed = parse_routines(
        {"routine": {"r": {"slot": [
            {"from": "08:00", "at": "type:work", "activity": "stand"},
            {"from": "25:00", "at": "type:work", "activity": "stand"},   # bad hour
            {"from": "09:00", "at": "type:work", "activity": "dancing"},  # bad activity
            {"at": "type:work"},                                          # no `from`
        ]}}},
        warn=warnings.append,
    )

    assert len(parsed.routines["r"].slots) == 1, "good step lost with the bad ones"
    assert len(warnings) == 3, f"expected three complaints, got {warnings}"


def test_assign_pointing_at_an_unknown_routine_warns() -> None:
    warnings: list[str] = []
    parse_routines({"routine": {}, "assign": {"Johny": "nope"}}, warn=warnings.append)

    assert any("nope" in w for w in warnings), f"silent bad assignment: {warnings}"


def test_missing_file_yields_empty_routines() -> None:
    """A content problem may never stop the game from starting."""
    warnings: list[str] = []
    parsed = load_routines("/nonexistent/routines.toml", warn=warnings.append)

    assert parsed.routines == {}
    assert parsed.assign == {}
    assert warnings, "missing file should at least complain"


def test_the_shipped_file_parses() -> None:
    from settings import ROUTINES_FILE

    warnings: list[str] = []
    parsed = load_routines(ROUTINES_FILE, warn=warnings.append)

    assert not warnings, f"routines.toml has problems: {warnings}"
    assert "townsfolk" in parsed.routines
    for spawn_name, key in parsed.assign.items():
        assert key in parsed.routines, f"{spawn_name} assigned to missing routine {key}"


# ---------------------------------------------------------------------------
# Which slot is in force
# ---------------------------------------------------------------------------

def test_slot_boundaries() -> None:
    routine = _routine(("06:30", "type:home"), ("08:00", "type:work"), ("20:00", "type:home"))

    assert current_slot(routine, _at(6, 30)).at == "type:home", "boundary belongs to the step it starts"
    assert current_slot(routine, _at(7, 59)).at == "type:home"
    assert current_slot(routine, _at(8, 0)).at == "type:work"
    assert current_slot(routine, _at(19, 59)).at == "type:work"
    assert current_slot(routine, _at(20, 0)).at == "type:home"


def test_night_wraps_past_midnight() -> None:
    """Before the first step of the day, the one in force is yesterday's last."""
    routine = _routine(("06:30", "type:home"), ("20:00", "type:sleep"))

    assert current_slot(routine, _at(23, 0)).at == "type:sleep"
    assert current_slot(routine, _at(0, 1)).at == "type:sleep", "midnight lost the evening step"
    assert current_slot(routine, _at(6, 29)).at == "type:sleep"


def test_guard_night_step_stays_active_until_morning() -> None:
    """The plan's example: a 02:00 step is in force until the 06:00 one starts."""
    guard = _routine(("06:00", "route:patrol_north"), ("18:00", "route:patrol_south"), ("02:00", "type:home"))

    assert current_slot(guard, _at(2, 0)).at == "type:home"
    assert current_slot(guard, _at(5, 59)).at == "type:home"
    assert current_slot(guard, _at(6, 0)).at == "route:patrol_north"
    assert current_slot(guard, _at(23, 0)).at == "route:patrol_south", "evening step lost"
    assert current_slot(guard, _at(1, 0)).at == "route:patrol_south", "after midnight, still evening"


def test_empty_routine_has_no_slot() -> None:
    assert current_slot(Routine(key="empty", slots=()), _at(12)) is None


# ---------------------------------------------------------------------------
# Jitter
# ---------------------------------------------------------------------------

def test_jitter_is_deterministic_and_bounded() -> None:
    for name in ("Johny", "Bart", "BARMAN_ABSINTHRAYNER"):
        first = slot_jitter(name, 20)
        assert first == slot_jitter(name, 20), f"{name}: jitter is not stable"
        assert -20 <= first <= 20, f"{name}: jitter out of range: {first}"


def test_jitter_differs_between_characters() -> None:
    """If everybody got the same offset the village would still move in lockstep."""
    offsets = {slot_jitter(n, 20) for n in ("Johny", "Bart", "Marry", "Rob", "Robin")}

    assert len(offsets) > 1, f"whole village shares one offset: {offsets}"


def test_zero_jitter_is_off() -> None:
    assert slot_jitter("Johny", 0) == 0


def test_jitter_shifts_the_boundary() -> None:
    """A character with +30 starts work at 08:30, not 08:00."""
    routine = _routine(("06:30", "type:home"), ("08:00", "type:work"))

    assert current_slot(routine, _at(8, 10), jitter=30).at == "type:home", "boundary did not move"
    assert current_slot(routine, _at(8, 40), jitter=30).at == "type:work"


# ---------------------------------------------------------------------------
# Resolving `at`
# ---------------------------------------------------------------------------

_PLACES = ("tavern", "well", "market_stall_1", "house_3")
_ROUTES = ("patrol_north", "intro")
_JOHNY = {"home": "house_3", "work": "market_stall_1", "social": "tavern", "hobby": ""}


def test_type_goes_through_the_characters_own_column() -> None:
    assert resolve_at("type:work", _JOHNY, _PLACES, _ROUTES) == Destination("place", "market_stall_1")


def test_the_same_place_can_be_two_roles() -> None:
    """The tavern is the barman's `work` and Johny's `social` - one Tiled object."""
    barman = {"home": "tavern", "work": "tavern", "social": "", "hobby": ""}

    assert resolve_at("type:work", barman, _PLACES, _ROUTES).name == "tavern"
    assert resolve_at("type:social", _JOHNY, _PLACES, _ROUTES).name == "tavern"


def test_location_names_a_place_directly() -> None:
    assert resolve_at("location:well", _JOHNY, _PLACES, _ROUTES) == Destination("place", "well")


def test_route_names_a_polyline() -> None:
    assert resolve_at("route:patrol_north", _JOHNY, _PLACES, _ROUTES) == Destination("route", "patrol_north")


def test_empty_column_is_not_an_error() -> None:
    """The main reason the village can be mapped one place at a time."""
    warnings: list[str] = []

    assert resolve_at("type:hobby", _JOHNY, _PLACES, _ROUTES, warn=warnings.append) is None
    assert not warnings, f"an empty cell is normal, not worth a warning: {warnings}"


def test_place_the_map_does_not_have_warns_but_does_not_raise() -> None:
    warnings: list[str] = []
    lost = {"home": "atlantis", "work": "", "social": "", "hobby": ""}

    assert resolve_at("type:home", lost, _PLACES, _ROUTES, warn=warnings.append) is None
    assert any("atlantis" in w for w in warnings), f"silent missing place: {warnings}"


def test_bad_prefixes_and_types_are_survivable() -> None:
    for bad in ("type:garden", "nonsense:tavern", "tavern", "location:atlantis", "route:nope", ""):
        assert resolve_at(bad, _JOHNY, _PLACES, _ROUTES) is None, f"{bad!r} should not resolve"


def test_destinations_come_off_both_model_mirrors() -> None:
    """Web dataclass and desktop pydantic must expose the same four columns."""
    from config_model.config import Character as WebCharacter
    from config_model.config_pydantic import Character as DesktopCharacter

    payload = {
        "name_EN": "Johny", "name_PL": "Jas", "sprite": "Villager1",
        "race": "humanoid", "attitude": "friendly",
        "home": "house_3", "work": "market_stall_1", "social": "tavern",
    }
    expected = {"home": "house_3", "work": "market_stall_1", "social": "tavern", "hobby": ""}

    assert destinations_of(WebCharacter.from_dict(payload)) == expected
    assert destinations_of(DesktopCharacter(**payload)) == expected


# ---------------------------------------------------------------------------
# NPC.update_schedule - the seam between the pure schedule and the movement code
# ---------------------------------------------------------------------------

from pygame.math import Vector2 as pvec


class _FakeScene:
    """Just enough scene for `update_schedule`: a clock, a map and the routines."""

    def __init__(self, routines, hour: int = 9, minute: int = 0) -> None:
        self.routines = routines
        self.hour = hour
        self.minute = minute
        self.places = {"market_stall_1": (100, 200), "house_3": (300, 400), "well": (150, 150)}
        self.waypoints = {"patrol_north": ((1, 1), (2, 2), (3, 3))}


class _FakeEmote:
    def __init__(self) -> None:
        self.emotes: list[str] = []

    def set_temporary_emote(self, emote: str, duration: float) -> None:
        self.emotes.append(emote)


class _FakeGame:
    time_elapsed = 0.0


def _npc(routine_key: str, destinations: dict, scene: "_FakeScene", name: str = "Johny"):
    from characters import NPC

    npc = NPC.__new__(NPC)
    npc.name = name
    npc.scene = scene
    npc.game = _FakeGame()
    npc.emote = _FakeEmote()
    npc.runtime = type("R", (), {"routine_key": routine_key})()
    npc.model = type("M", (), destinations)()
    npc._schedule_slot = None
    npc._schedule_jitter = 0          # pin the jitter so the clock reads literally
    npc._schedule_destination = None
    npc._wander_anchor = None
    npc._wander_next_time = 0.0
    npc._idle_emoted = False
    npc.wants_to_sleep = False
    npc.is_asleep = False
    npc.target = pvec(0, 0)
    npc.waypoints = ()
    npc.waypoints_cnt = 0
    npc.current_waypoint_no = 0
    npc.paths_found = 0

    def find_path() -> None:
        npc.paths_found += 1
        npc.waypoints_cnt = 3          # a path was found, so it is now travelling

    npc.find_path = find_path

    def arrive() -> None:
        """Pretend the walk finished, exactly as `clear_waypoints` leaves things."""
        npc.waypoints = ()
        npc.waypoints_cnt = 0
        npc.target = pvec(0, 0)

    npc.arrive = arrive
    return npc


_STANDING = {
    "routine": {"townsfolk": {"slot": [
        {"from": "08:00", "at": "type:work", "activity": "stand"},
        {"from": "20:00", "at": "type:home", "activity": "sleep"},
    ]}},
    "assign": {"Johny": "townsfolk"},
}
_DESTS = {"home": "house_3", "work": "market_stall_1", "social": "", "hobby": ""}


def test_no_routine_is_a_no_op() -> None:
    """Everyone without an assignment must be left exactly as they were."""
    scene = _FakeScene(parse_routines(_STANDING))
    npc = _npc("", _DESTS, scene)

    npc.update_schedule()

    assert npc.paths_found == 0, "routine-less NPC was retargeted"
    assert npc.target == pvec(0, 0)


def test_a_resolvable_slot_sets_the_target_once() -> None:
    """Retargeting every frame would restart A* forever and it would never arrive."""
    scene = _FakeScene(parse_routines(_STANDING), hour=9)
    npc = _npc("townsfolk", _DESTS, scene)

    for _ in range(10):
        npc.update_schedule()

    assert npc.paths_found == 1, f"path recomputed {npc.paths_found} times in one slot"
    assert tuple(npc.target) == (100, 200), f"wrong destination: {npc.target}"


def test_crossing_a_boundary_retargets() -> None:
    scene = _FakeScene(parse_routines(_STANDING), hour=9)
    npc = _npc("townsfolk", _DESTS, scene)
    npc.update_schedule()

    scene.hour = 21          # evening step: go home
    npc.update_schedule()

    assert npc.paths_found == 2, "boundary did not retarget"
    assert tuple(npc.target) == (300, 400), f"did not go home: {npc.target}"


def test_an_unmapped_village_leaves_everyone_alone() -> None:
    """No `places` layer yet: the NPC keeps whatever it was doing, no exception."""
    scene = _FakeScene(parse_routines(_STANDING), hour=9)
    scene.places = {}
    npc = _npc("townsfolk", _DESTS, scene)

    npc.update_schedule()

    assert npc.paths_found == 0, "NPC was sent to a place the map does not have"
    assert npc.target == pvec(0, 0)


def test_empty_destination_column_leaves_the_npc_alone() -> None:
    scene = _FakeScene(parse_routines(_STANDING), hour=9)
    npc = _npc("townsfolk", {"home": "", "work": "", "social": "", "hobby": ""}, scene)

    npc.update_schedule()

    assert npc.paths_found == 0
    assert npc.target == pvec(0, 0)


# ---------------------------------------------------------------------------
# sleep
# ---------------------------------------------------------------------------

def test_sleep_is_only_requested_after_arriving() -> None:
    """Vanishing halfway down the street would look like a bug, because it is one."""
    scene = _FakeScene(parse_routines(_STANDING), hour=21)
    npc = _npc("townsfolk", _DESTS, scene)

    npc.update_schedule()
    assert not npc.wants_to_sleep, "went to bed while still walking home"

    npc.arrive()
    npc.update_schedule()
    assert npc.wants_to_sleep, "arrived home and stayed up"


def test_morning_ends_the_night_even_before_walking_anywhere() -> None:
    """Waking is not something a character can be too far from home to do."""
    scene = _FakeScene(parse_routines(_STANDING), hour=21)
    npc = _npc("townsfolk", _DESTS, scene)
    npc.update_schedule()
    npc.arrive()
    npc.update_schedule()
    assert npc.wants_to_sleep

    scene.hour = 9
    npc.update_schedule()

    assert not npc.wants_to_sleep, "still asleep after the slot changed"


def test_a_sleeper_without_a_home_never_goes_to_bed() -> None:
    """No `home` cell means no threshold to vanish on - it just stands there."""
    scene = _FakeScene(parse_routines(_STANDING), hour=21)
    npc = _npc("townsfolk", {"home": "", "work": "market_stall_1", "social": "", "hobby": ""}, scene)

    npc.update_schedule()
    npc.arrive()
    npc.update_schedule()

    assert not npc.wants_to_sleep, "fell asleep on the spot with nowhere to sleep"


# ---------------------------------------------------------------------------
# patrol
# ---------------------------------------------------------------------------

_PATROL = {
    "routine": {"guard": {"slot": [
        {"from": "06:00", "at": "route:patrol_north", "activity": "patrol"},
    ]}},
    "assign": {"Johny": "guard"},
}


def test_patrol_hands_the_route_to_the_waypoint_loop() -> None:
    scene = _FakeScene(parse_routines(_PATROL), hour=9)
    npc = _npc("guard", _DESTS, scene)

    npc.update_schedule()

    assert npc.waypoints == ((1, 1), (2, 2), (3, 3)), f"route not loaded: {npc.waypoints}"
    assert npc.waypoints_cnt == 3
    assert npc.current_waypoint_no == 0
    assert npc.paths_found == 0, "patrol should follow the polyline, not pathfind to it"


def test_patrol_leaves_target_zero_so_the_route_loops() -> None:
    """A non-zero `target` is exactly what makes follow_waypoints stop at the end."""
    scene = _FakeScene(parse_routines(_PATROL), hour=9)
    npc = _npc("guard", _DESTS, scene)

    npc.update_schedule()

    assert npc.target == pvec(0, 0), f"patrol would stop at the last point: {npc.target}"


def test_an_unknown_route_leaves_the_npc_alone() -> None:
    scene = _FakeScene(parse_routines(_PATROL), hour=9)
    scene.waypoints = {}
    npc = _npc("guard", _DESTS, scene)

    npc.update_schedule()

    assert npc.waypoints_cnt == 0, "invented a route that is not on the map"


# ---------------------------------------------------------------------------
# wander and idle
# ---------------------------------------------------------------------------

_DRIFTING = {
    "routine": {"townsfolk": {"slot": [
        {"from": "08:00", "at": "location:well", "activity": "wander"},
        {"from": "20:00", "at": "location:well", "activity": "idle"},
    ]}},
    "assign": {"Johny": "townsfolk"},
}


def test_wander_waits_before_drifting_again() -> None:
    """Without the pause it re-rolls on arrival and skates around without stopping."""
    from settings import WANDER_PAUSE

    scene = _FakeScene(parse_routines(_DRIFTING), hour=9)
    npc = _npc("townsfolk", _DESTS, scene)
    npc.get_random_safe_pos = lambda pos, range=1.0, **kw: pvec(pos) + pvec(range, 0)

    npc.update_schedule()          # walk to the well
    npc.arrive()
    npc.update_schedule()          # first drift
    first = npc.paths_found

    for _ in range(10):            # same instant: must not re-roll
        npc.arrive()
        npc.update_schedule()
    assert npc.paths_found == first, f"drifted {npc.paths_found - first} times without pausing"

    npc.game.time_elapsed += WANDER_PAUSE + 0.1
    npc.arrive()
    npc.update_schedule()
    assert npc.paths_found == first + 1, "never drifted again after the pause"


def test_wander_stays_around_its_anchor_not_its_last_step() -> None:
    """Drifting relative to the previous spot is a random walk out of the village."""
    scene = _FakeScene(parse_routines(_DRIFTING), hour=9)
    npc = _npc("townsfolk", _DESTS, scene)
    anchors: list[tuple[float, float]] = []
    npc.get_random_safe_pos = lambda pos, range=1.0, **kw: (anchors.append(tuple(pvec(pos))), pvec(pos))[1]

    npc.update_schedule()
    npc.arrive()
    for _ in range(3):
        npc.update_schedule()
        npc.arrive()
        npc.game.time_elapsed += 10.0

    assert anchors, "never wandered"
    assert set(anchors) == {(150.0, 150.0)}, f"anchor drifted: {set(anchors)}"


def test_idle_emotes_once_on_arrival() -> None:
    scene = _FakeScene(parse_routines(_DRIFTING), hour=21)
    npc = _npc("townsfolk", _DESTS, scene)

    npc.update_schedule()
    assert npc.emote.emotes == [], "emoted while still walking"

    npc.arrive()
    for _ in range(10):
        npc.update_schedule()

    assert len(npc.emote.emotes) == 1, f"emote repeated every frame: {npc.emote.emotes}"


# ---------------------------------------------------------------------------
# Scene.update_sleepers - turning the intention into fact
# ---------------------------------------------------------------------------


class _FakeGroup:
    def __init__(self) -> None:
        self.members: set = set()

    def add(self, *sprites, layer: int = 0) -> None:
        self.members.update(sprites)

    def remove(self, *sprites) -> None:
        self.members.difference_update(sprites)


class _Sleeper:
    """A character that only knows how to want to sleep."""

    def __init__(self, wants: bool = False) -> None:
        self.wants_to_sleep = wants
        self.is_asleep = False
        self.shadow, self.health_bar, self.emote = object(), object(), object()
        self.schedule_checks = 0

    def update_schedule(self) -> None:
        self.schedule_checks += 1

    def sprites(self) -> tuple:
        return (self, self.shadow, self.health_bar, self.emote)


def _scene_with(*npcs):
    from scene import Scene

    scene = Scene.__new__(Scene)
    scene.NPCs = list(npcs)
    scene.group = _FakeGroup()
    scene.sprites_layer = 4
    for npc in npcs:
        scene.group.add(*npc.sprites())
    return scene


def test_falling_asleep_leaves_the_draw_group() -> None:
    """Out of the group means no drawing, no animation, no physics - sleep is free."""
    npc = _Sleeper(wants=True)
    scene = _scene_with(npc)

    scene.update_sleepers()

    assert npc.is_asleep
    assert not (scene.group.members & set(npc.sprites())), "sprite still in the draw group"


def test_a_sleeper_stays_in_the_list_the_save_is_built_from() -> None:
    """`_build_map_states` iterates `scene.NPCs`; dropping a sleeper loses its purse."""
    npc = _Sleeper(wants=True)
    scene = _scene_with(npc)

    scene.update_sleepers()

    assert npc in scene.NPCs, "sleeping NPC would vanish from the save file"


def test_sleepers_are_not_collidable_or_talkable() -> None:
    awake, asleep = _Sleeper(), _Sleeper(wants=True)
    scene = _scene_with(awake, asleep)

    scene.update_sleepers()

    assert scene.awake_NPCs() == [awake], "an invisible body is still in the way"


def test_a_sleeper_still_gets_its_schedule_checked() -> None:
    """It gets no update of its own, so this is the only thing that can wake it."""
    npc = _Sleeper(wants=True)
    scene = _scene_with(npc)

    scene.update_sleepers()          # falls asleep
    before = npc.schedule_checks
    scene.update_sleepers()          # and is still consulted afterwards

    assert npc.schedule_checks > before, "asleep forever - nothing would ever wake it"


def test_waking_puts_every_sprite_back() -> None:
    npc = _Sleeper(wants=True)
    scene = _scene_with(npc)
    scene.update_sleepers()

    npc.wants_to_sleep = False
    scene.update_sleepers()

    assert not npc.is_asleep
    assert set(npc.sprites()) <= scene.group.members, "came back from bed half invisible"


def test_an_awake_character_is_left_alone() -> None:
    npc = _Sleeper()
    scene = _scene_with(npc)
    before = set(scene.group.members)

    scene.update_sleepers()

    assert scene.group.members == before
    assert npc.schedule_checks == 0, "awake NPCs are updated by the group, not from here"


if __name__ == "__main__":
    tests = [
        ("time parsing", test_time_parsing),
        ("slots sorted regardless of file order", test_slots_are_sorted_regardless_of_file_order),
        ("broken slot is skipped, not fatal", test_a_broken_slot_is_skipped_not_fatal),
        ("bad assignment warns", test_assign_pointing_at_an_unknown_routine_warns),
        ("missing file yields empty routines", test_missing_file_yields_empty_routines),
        ("the shipped routines.toml parses", test_the_shipped_file_parses),
        ("slot boundaries", test_slot_boundaries),
        ("night wraps past midnight", test_night_wraps_past_midnight),
        ("guard night step lasts until morning", test_guard_night_step_stays_active_until_morning),
        ("empty routine has no slot", test_empty_routine_has_no_slot),
        ("jitter deterministic and bounded", test_jitter_is_deterministic_and_bounded),
        ("jitter differs between characters", test_jitter_differs_between_characters),
        ("zero jitter is off", test_zero_jitter_is_off),
        ("jitter shifts the boundary", test_jitter_shifts_the_boundary),
        ("type: uses the character's column", test_type_goes_through_the_characters_own_column),
        ("one place, two roles", test_the_same_place_can_be_two_roles),
        ("location: names a place", test_location_names_a_place_directly),
        ("route: names a polyline", test_route_names_a_polyline),
        ("empty column is not an error", test_empty_column_is_not_an_error),
        ("missing place warns, does not raise", test_place_the_map_does_not_have_warns_but_does_not_raise),
        ("bad prefixes are survivable", test_bad_prefixes_and_types_are_survivable),
        ("destinations from both model mirrors", test_destinations_come_off_both_model_mirrors),
        ("no routine is a no-op", test_no_routine_is_a_no_op),
        ("resolvable slot sets target once", test_a_resolvable_slot_sets_the_target_once),
        ("crossing a boundary retargets", test_crossing_a_boundary_retargets),
        ("unmapped village leaves everyone alone", test_an_unmapped_village_leaves_everyone_alone),
        ("empty destination column is safe", test_empty_destination_column_leaves_the_npc_alone),
        ("sleep only after arriving", test_sleep_is_only_requested_after_arriving),
        ("morning ends the night", test_morning_ends_the_night_even_before_walking_anywhere),
        ("no home, no bed", test_a_sleeper_without_a_home_never_goes_to_bed),
        ("patrol loads the route", test_patrol_hands_the_route_to_the_waypoint_loop),
        ("patrol keeps target zero so it loops", test_patrol_leaves_target_zero_so_the_route_loops),
        ("unknown route leaves the NPC alone", test_an_unknown_route_leaves_the_npc_alone),
        ("wander pauses between drifts", test_wander_waits_before_drifting_again),
        ("wander stays around its anchor", test_wander_stays_around_its_anchor_not_its_last_step),
        ("idle emotes once on arrival", test_idle_emotes_once_on_arrival),
        ("falling asleep leaves the draw group", test_falling_asleep_leaves_the_draw_group),
        ("sleeper stays in the save list", test_a_sleeper_stays_in_the_list_the_save_is_built_from),
        ("sleepers not collidable or talkable", test_sleepers_are_not_collidable_or_talkable),
        ("sleeper still gets its schedule checked", test_a_sleeper_still_gets_its_schedule_checked),
        ("waking puts every sprite back", test_waking_puts_every_sprite_back),
        ("awake character left alone", test_an_awake_character_is_left_alone),
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
