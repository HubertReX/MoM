"""Reżyser rutyn: harmonogram NPC-ów na wszystkich mapach (v5).

Moduł systemu wg B01 (D1): bezstanowe funkcje operujące na przekazanej scenie -
tick logicznej mapy i tranzytów, materializacja/dematerializacja postaci na
aktualnej mapie, sen, roster rutyn i rozwiązywanie miejsc ze slotów.

Publiczne nazwy (``update_sleepers``, ``awake_NPCs``, ``update_routine_npcs``,
``reconcile_routine_presence``, ``exit_to``, ``load_routine_roster``) zostają na
``Scene`` jako delegaty - to sondy testów i API agenta (kontrakt K3).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pygame
from maze_generator.maze_utils import TILE_SIZE, nearest_walkable
from npc_schedule import (
    current_slot,
    destinations_of,
    resolve_at,
    roster_origin_map,
    routine_roster_keys,
    slot_jitter,
    slot_target_map,
    step_logical_map,
)
from rich import print

from scene import world_clock
from settings import vec

if TYPE_CHECKING:
    from scene.scene import Scene

#: `current_map` value for a routine NPC that has walked through the door and is
#: between two maps (or is travelling off-screen). It matches no map name, so the
#: presence filter keeps it off both rosters until the arrival timer lands it.
_NOWHERE = "\x00transit"

#: Safety arrival time (game-minutes) for a *visible* departure, in case the
#: character never reaches its door - a blocked path, mostly. Normally the arrival
#: is (re)set to `transit_minutes` from the moment it walks through the door, so
#: this large value is only a floor that stops a stuck traveller vanishing forever.
_DEPARTURE_FALLBACK_MIN = 240


def update_sleepers(scene: "Scene") -> None:
    """Take characters whose routine put them to bed out of the world, and back.

    Done here, once a frame, rather than by the character itself: falling
    asleep means leaving `scene.group`, and a sprite removing itself from the
    very group whose `update()` is running is the kind of thing that works
    until it doesn't. The character only ever states an intention
    (`wants_to_sleep`); this turns it into fact.

    Leaving the group is what makes sleeping cheap - no animation, no physics,
    no pathfinding, and nothing drawn. But the character stays in `scene.NPCs`,
    because that list is what the save file is built from (`_build_map_states`)
    and a sleeping merchant must not lose its purse overnight. The two loops
    that would otherwise bump into an invisible body skip sleepers explicitly.

    A sleeping character gets no update of its own, so it could never notice
    the morning. Consulting its schedule from here is what wakes it.
    """
    for npc in scene.NPCs:
        if npc.is_asleep:
            npc.update_schedule()

        if npc.wants_to_sleep and not npc.is_asleep:
            npc.is_asleep = True
            scene.group.remove(npc, npc.shadow, npc.health_bar, npc.emote)
        elif not npc.wants_to_sleep and npc.is_asleep:
            npc.is_asleep = False
            scene.group.add(npc, layer=scene.sprites_layer)
            scene.group.add(npc.shadow, layer=scene.sprites_layer - 2)
            scene.group.add(npc.health_bar, layer=scene.sprites_layer + 1)
            scene.group.add(npc.emote, layer=scene.sprites_layer + 1)


def awake_NPCs(scene: "Scene") -> list[Any]:
    """`scene.NPCs` minus the ones currently indoors asleep.

    Used for collision and for "who is close enough to talk to": a character
    that is not drawn must not be bumped into or traded with either.
    """
    return [npc for npc in scene.NPCs if not npc.is_asleep]


def update_routine_npcs(scene: "Scene") -> None:
    """Tick the daily schedule for every routine NPC, on any map (v5).

    The half of the schedule that has to run even for characters the player is
    not looking at: it moves each one's *logical* map as its routine crosses
    between buildings, arming and completing the transit timer. It touches no
    sprites and runs no pathfinding - materialising a character on the player's
    map is the presence reconciler's job. Cheap by construction (a slot lookup
    and some string work per NPC), so sweeping the whole roster every frame is
    fine.

    With no cross-map destinations in the data yet, every `slot_target_map`
    returns the character's own map, so nothing here changes state - the system
    is inert until the CSV names a place on another map.
    """
    defaults = scene.routines.defaults
    now_abs = world_clock.abs_minutes(scene)
    minutes = scene.hour * 60 + scene.minute
    for npc in scene.loaded_NPCs.values():
        routine_key = npc.runtime.routine_key
        if not routine_key or npc.is_dead:
            continue
        routine = scene.routines.routines.get(routine_key)
        if routine is None:
            continue
        if npc._schedule_jitter is None:
            npc._schedule_jitter = slot_jitter(npc.name, defaults.slot_jitter_minutes)

        slot = current_slot(routine, minutes, npc._schedule_jitter)
        target_map = None
        if slot is not None:
            target_map = slot_target_map(slot.at, destinations_of(npc.model), npc.origin_map)

        rt = npc.runtime
        was_transit = bool(rt.transit_to_map)
        prev_logical = rt.logical_map or npc.origin_map
        new_logical, new_to_map, new_arrive = step_logical_map(
            prev_logical,
            rt.transit_to_map,
            rt.transit_arrive_min,
            target_map,
            now_abs,
            defaults.transit_minutes,
        )
        if new_logical != prev_logical:
            # A transit just landed the character on a new map. Remember where it
            # came from so the reconciler can walk it in through the right door,
            # and clear the "gone through the door" flag for the next trip.
            npc._arrived_from = prev_logical
            npc._transit_gone = False
        rt.logical_map, rt.transit_to_map, rt.transit_arrive_min = new_logical, new_to_map, new_arrive

        if new_to_map and not was_transit:
            # A cross-map trip just started. On the player's map, send it walking
            # to the door so it visibly heads out (the doorway is a wall, but this
            # is a *target* - find_path snaps the goal to the nearest walkable tile,
            # i.e. walks it up to the threshold); it vanishes on reaching the door.
            # Off the player's map there is no walk to show, so it is gone at once.
            door = exit_to(scene, new_to_map) if npc in scene.NPCs else None
            if door is not None:
                npc._transit_gone = False
                npc.target = vec(door)
                npc.find_path()
                # It is leaving, not doing its slot activity - drop the schedule
                # destination so `_continue_slot` does not wander/idle it.
                npc._schedule_destination = None
                # Arrival is re-timed from when it walks through the door; until
                # then hold it off with a large floor so a short transit_minutes
                # does not flip the map (and dematerialise it) mid-walk.
                rt.transit_arrive_min = now_abs + _DEPARTURE_FALLBACK_MIN
            else:
                # Off the player's map (or no door to walk to): straight through,
                # appears on the far side after the normal short transit.
                npc._transit_gone = True

    reconcile_presence(scene)


def physical_map(npc: "Any") -> str:
    """Which map a routine NPC is physically on right now.

    While a transit is armed, `logical_map` stays the *source* map until the
    timer completes, so a departing character stays present there - walking to
    the door - instead of blinking off the instant the trip is armed (which read
    as vanishing on the spot). Once it reaches the door (`_transit_gone`, set by
    the reconciler) it goes to `_NOWHERE`: through the door, not yet arrived. The
    timer alone decides when `logical_map` flips to the destination and it turns
    up at the far door.
    """
    rt = npc.runtime
    if rt.transit_to_map and getattr(npc, "_transit_gone", False):
        return _NOWHERE
    return rt.logical_map or npc.origin_map


def reconcile_presence(scene: "Scene") -> None:
    """Add / remove routine NPCs from the live map as the schedule moves them (v5).

    Runs every frame after `update_routine_npcs`. It is the counterpart to
    `settle` (which handles a whole map load at once): here a
    single character crosses a boundary while the player stands still, so only
    the ones whose physical map just started or stopped matching the loaded map
    change. Mirrors `update_sleepers` - the sprite plumbing is the same.
    """
    for npc in scene.loaded_NPCs.values():
        if not npc.runtime.routine_key or npc.is_dead:
            continue
        # A character walking out reaches the threshold and goes through it: the
        # frame it stops travelling (the door path is spent) it is gone from the
        # map it was leaving, and its arrival on the far side is timed from *now* -
        # so it turns up there shortly after, however long the walk to the door took.
        if (npc.runtime.transit_to_map and not npc._transit_gone
                and npc in scene.NPCs and not npc.is_travelling):
            npc._transit_gone = True
            npc.runtime.transit_arrive_min = min(
                npc.runtime.transit_arrive_min,
                world_clock.abs_minutes(scene) + scene.routines.defaults.transit_minutes,
            )
        physical = physical_map(npc)
        should_be_here = physical == scene.current_map
        present = npc in scene.NPCs
        if should_be_here and not present:
            npc.current_map = scene.current_map
            materialize(scene, npc)
        elif present and not should_be_here:
            npc.current_map = physical
            dematerialize(scene, npc)


def settle(scene: "Scene") -> None:
    """Place every routine NPC on the map it is logically on, before drawing it.

    Called once from `map_loader.populate_sprite_groups`, i.e. whenever a map is (re)built.
    A visitor - a character whose home is elsewhere - is dropped straight at its
    current destination, which is the accepted "already sitting at the table
    when the player walks in" teleport. The same drop applies to a character
    whose home *is* this map but which the roster created at the (0,0)
    placeholder (its spawn map had not been loaded when it was instantiated) -
    without it the character would be frozen in the wall at (0,0), since A*
    cannot step off a blocked start tile. Its own residents that spawned from a
    real point keep the position they had. Characters mid-transit are parked off
    the map on the sentinel.
    """
    for npc in scene.loaded_NPCs.values():
        if not npc.runtime.routine_key:
            continue
        physical = physical_map(npc)
        npc.current_map = physical
        if physical != scene.current_map:
            continue
        if npc.origin_map != scene.current_map or npc._roster_unplaced:
            place = slot_place(scene, npc)
            if place is not None:
                npc.pos = vec(place)
                npc.prev_pos = npc.pos.copy()
                npc.adjust_rect()
                # Anchored on a real map now - keep this position on re-entry
                # instead of being teleported to the slot place every time.
                npc._roster_unplaced = False


def slot_place(scene: "Scene", npc: "Any") -> "vec | None":
    """Walkable pixel of the NPC's current slot destination on *this* map, or None.

    Only resolves a `place` that lands on the loaded map (a route or a target on
    another map is not a spot to stand at). Snapped off any wall the marker sits
    on, the same way `find_path` does it.
    """
    routine = scene.routines.routines.get(npc.runtime.routine_key)
    if routine is None:
        return None
    minutes = scene.hour * 60 + scene.minute
    slot = current_slot(routine, minutes, npc._schedule_jitter or 0)
    if slot is None:
        return None
    dest = resolve_at(
        slot.at, destinations_of(npc.model), scene.places, scene.waypoints,
        origin_map=npc.origin_map, current_map=scene.current_map,
    )
    if dest is None or dest.kind != "place" or dest.map != scene.current_map:
        return None
    if dest.name not in scene.places:
        return None
    return walkable_pixel(scene, scene.places[dest.name])


def walkable_pixel(scene: "Scene", pixel: "vec") -> "vec":
    """Nearest tile centre A* can stand on to `pixel` - so a teleport never lands in a wall.

    Tolerates being called from `map_loader.populate_sprite_groups` before `load_step_cost`
    has (re)built the grid: with no grid to consult it just returns the raw
    marker, which authors place on something sensible anyway.
    """
    grid = getattr(scene, "path_finding_grid", None)
    if grid:
        goal = (int(pixel.y // TILE_SIZE), int(pixel.x // TILE_SIZE))
        walkable = nearest_walkable(grid, goal)
        if walkable:
            row, col = walkable
            return vec(col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2)
    return vec(pixel)


def exit_to(scene: "Scene", map_name: str) -> "vec | None":
    """The doorway on *this* map that leads to `map_name`. The exit collider sits
    on the threshold, so its own position is exactly the door - but that tile is
    a wall (you walk *into* it to leave), so it is only the anchor for finding the
    walkable landing beside it, never a spot to stand on. See `_arrival_pos`."""
    for exit in scene.exits:
        if getattr(exit, "to_map", "") == map_name:
            return vec(exit.rect.midbottom)
    return None


def arrival_pos(scene: "Scene", source_map: str) -> "vec | None":
    """Walkable spot an NPC coming from `source_map` should appear at.

    The doorway collider is a wall, so an NPC dropped on it is stuck - A* cannot
    step off a blocked tile, so it never leaves the threshold. The walkable
    landing is the `entry_points` object beside that door: the very spot the
    player lands on when walking through it (here `VillageHouseDoor`). Pick the
    entry point nearest the exit that leads back to `source_map` - door and its
    entry point are the same threshold - and snap it onto free ground for safety.
    Falls back to snapping the doorway itself if the map has no entry points.
    """
    door = exit_to(scene, source_map)
    if door is None:
        return None
    nearest: "vec | None" = None
    nearest_d2: float | None = None
    for pos in scene.entry_points.values():
        d2 = (vec(pos) - door).length_squared()
        if nearest_d2 is None or d2 < nearest_d2:
            nearest, nearest_d2 = vec(pos), d2
    return walkable_pixel(scene, nearest if nearest is not None else door)


def materialize(scene: "Scene", npc: "Any") -> None:
    """Bring a routine NPC onto the live map: position it, then wire its sprites.

    Positioning has two shapes. If it just arrived through a door (`_arrived_from`
    set, and that door exists on this map) it appears at the threshold and walks
    to its destination - the visible "comes in and crosses the room" case. Any
    other way of becoming present drops it at the destination directly.
    """
    door = arrival_pos(scene, npc._arrived_from) if npc._arrived_from else None
    place = slot_place(scene, npc)
    if door is not None:
        npc.pos = vec(door)
        npc.prev_pos = npc.pos.copy()
        npc.adjust_rect()
        if place is not None:
            npc._wander_anchor = vec(place)
            npc.target = vec(place)
            npc.find_path()
    elif place is not None:
        npc.pos = vec(place)
        npc.prev_pos = npc.pos.copy()
        npc.adjust_rect()
    npc._arrived_from = None

    # A fresh slot is due the moment it lands, so the activity (stand, wander,
    # sleep) starts without waiting for the next boundary.
    npc._schedule_slot = None

    scene.NPCs.append(npc)
    scene.shadow_sprites.add(npc.shadow)
    scene.label_sprites.add(npc.health_bar)
    scene.label_sprites.add(npc.emote)
    npc.register_custom_event()
    scene.group.add(npc, layer=scene.sprites_layer)
    scene.group.add(npc.shadow, layer=scene.sprites_layer - 2)
    scene.group.add(npc.health_bar, layer=scene.sprites_layer + 1)
    scene.group.add(npc.emote, layer=scene.sprites_layer + 1)


def dematerialize(scene: "Scene", npc: "Any") -> None:
    """Take a routine NPC off the live map when the schedule moves it elsewhere.

    The mirror of `materialize`: drop it from the draw group and the
    active list, but leave it in `loaded_NPCs` so its schedule keeps ticking and
    it can come back. `is_asleep` is cleared - a character walking out of the map
    is by definition awake, and leaving the flag set would strand it invisible if
    it were mid-sleep.
    """
    if npc in scene.NPCs:
        scene.NPCs.remove(npc)
    scene.group.remove(npc, npc.shadow, npc.health_bar, npc.emote)
    scene.shadow_sprites.remove(npc.shadow)
    scene.label_sprites.remove(npc.health_bar, npc.emote)
    npc.is_asleep = False
    npc.wants_to_sleep = False


def load_roster(scene: "Scene") -> None:
    """Instantiate every routine character that has no NPC yet (v5).

    The general fix for "an NPC only exists after its spawn map is loaded":
    after the hub map is up, create an object for each `characters.csv` row that
    follows a routine and was not already spawned here, so the off-map schedule
    tick covers the whole cast regardless of which map their `spawn_point` is on.
    Dedup is free - `routine_roster_keys` skips anyone already in `loaded_NPCs`.

    Their sprites go into throwaway groups, not the live ones, so an off-map
    character never leaves a stray shadow or emote on the hub; the reconciler
    re-homes them into the real groups when it materialises the character.
    """
    from characters import NPC

    hub = scene.current_map
    # Dedup by config key, not object name: a spawn_point named "Johny" carries
    # model_name "JOHNY", so `loaded_NPCs` is keyed "Johny" while the roster walks
    # config keys ("JOHNY"). Comparing the two names missed the match and built a
    # duplicate that stood at the destination while the original walked to it.
    present = {getattr(npc, "config_key", "") or npc.name for npc in scene.loaded_NPCs.values()}
    for key in routine_roster_keys(scene.game.conf.characters, present):
        model = scene.game.conf.characters[key]
        routine_key = str(getattr(model, "routine", "") or "").strip()
        if routine_key not in scene.routines.routines:
            print(f"[routines] roster '{key}' wants unknown routine '{routine_key}'")
            continue
        detached_shadow: pygame.sprite.Group = pygame.sprite.Group()
        detached_label: pygame.sprite.Group = pygame.sprite.Group()
        npc = NPC(
            scene.game, scene, detached_shadow, detached_label,
            (0, 0), key, scene.icons, (), model_name=key,
        )
        origin = roster_origin_map(model, hub)
        npc.origin_map = origin
        npc.current_map = origin
        npc.runtime.routine_key = routine_key
        npc.runtime.logical_map = origin
        # Created at the (0,0) placeholder - `settle` gives it a
        # real position the first time its map is loaded.
        npc._roster_unplaced = True
        scene.loaded_NPCs[key] = npc
