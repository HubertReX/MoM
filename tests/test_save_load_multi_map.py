#!/usr/bin/env python3
"""Integration tests for multi-map state persistence in save/load.

Run from the project root:
    .venv/bin/python tests/test_save_load_multi_map.py

Covers the bug that made quest conditions unreliable across maps: on load,
``_apply_map_states`` applied only the map the player saved on and then cleared
the cache, so every *other* map's state (conversations, opened chests, dead
monsters) was written to the save file and then silently dropped. Walking back
into such a map rebuilt it from the TMX defaults.

The existing dialog-state tests only exercised a single NPC in isolation, which
is why this went unnoticed — so these tests deliberately work at the map level.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

from enums import ItemTypeEnum
from save_load.manager import SaveManager
from save_load.models import ChestState, GroundItemState, MapState, NPCDialogState, NPCState


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


class FakeGroup:
    """Stands in for the pyscroll sprite group / sprite sets."""

    def __init__(self) -> None:
        self.sprites_set: list[object] = []

    def remove(self, sprite: object) -> None:
        if sprite in self.sprites_set:
            self.sprites_set.remove(sprite)

    def add(self, sprite: object, layer: int = 0) -> None:
        self.sprites_set.append(sprite)

    def __contains__(self, sprite: object) -> bool:
        return sprite in self.sprites_set


def _make_npc(name: str, *, visited: dict[str, bool] | None = None) -> SimpleNamespace:
    """An NPC stub that records what restore_dialog_state was handed."""
    npc = SimpleNamespace(
        name=name,
        model=SimpleNamespace(has_dialog=True, attitude="friendly", health=10, money=0),
        pos=SimpleNamespace(x=0.0, y=0.0),
        is_dead=False,
        items=[],
        restored_state=None,
        killed=False,
    )
    npc.restore_dialog_state = lambda state, _npc=npc: setattr(_npc, "restored_state", state)
    npc.kill = lambda _npc=npc: setattr(_npc, "killed", True)
    return npc


def _make_chest(name: str) -> SimpleNamespace:
    """A chest stub mirroring ChestSprite: open()/close() swap the image too."""
    chest = SimpleNamespace(
        name=name,
        model=SimpleNamespace(is_closed=True, items=[]),
        image="closed",
    )

    def _open(_chest: SimpleNamespace = chest) -> None:
        _chest.model.is_closed = False
        _chest.image = "open"

    def _close(_chest: SimpleNamespace = chest) -> None:
        _chest.model.is_closed = True
        _chest.image = "closed"

    chest.open = _open
    chest.close = _close
    return chest


def _make_scene(current_map: str, npcs: list[SimpleNamespace]) -> SimpleNamespace:
    scene = SimpleNamespace(
        current_map=current_map,
        loaded_maps={},
        pending_map_states={},
        NPCs=npcs,
        chests=[],
        items=[],
        item_sprites=FakeGroup(),
        group=FakeGroup(),
        destructibles=[],
        walls=[],
        path_finding_grid=[[0, 0], [0, 0]],
        is_maze=False,
        sprites_layer=1,
        items_sheet={},
        dead_monsters=[],
        game=SimpleNamespace(conf=SimpleNamespace(items={})),
    )
    scene.store_map = lambda: scene.loaded_maps.__setitem__(scene.current_map, {})
    # mirrors Scene.note_monster_death - the durable record of a kill whose sprite
    # NPC.die() has already removed from scene.NPCs
    scene.note_monster_death = lambda name, _s=scene: (
        _s.dead_monsters.append(name) if name and name not in _s.dead_monsters else None
    )
    return scene


def _dialog_state(visited: dict[str, bool], sentiment: int = 77) -> NPCDialogState:
    return NPCDialogState(
        current_node_key="012",
        dialog_start_node_key="001",
        selected_options={"OPT_ASK": True},
        visited_nodes=visited,
        sentiment=sentiment,
        known_disposition={},
    )


def _barman_map_state() -> MapState:
    """Map 'Tavern': the player talked to the barman and opened a chest."""
    return MapState(
        name="Tavern",
        npc_states={
            "Barman": NPCState(
                name="Barman",
                attitude="friendly",
                pos_x=5.0,
                pos_y=6.0,
                health=10,
                money=3,
                is_dead=False,
                inventory=[],
                dialog_state=_dialog_state({"012": True}),
            )
        },
        chests={"TavernChest": ChestState(name="TavernChest", is_closed=False, items=["MERMAIDS_TEAR"])},
        ground_items=[],
        destroyed_walls=[],
        dead_monsters=[],
    )


def test_other_maps_are_kept_pending_not_dropped() -> None:
    """Loading a save on map A must not discard map B's state."""
    scene = _make_scene("Village", [])
    mgr = SaveManager.__new__(SaveManager)

    maps = {
        "Village": MapState(name="Village"),
        "Tavern": _barman_map_state(),
    }
    mgr._apply_map_states(scene, maps)

    assert_true("Tavern" in scene.pending_map_states, "other map held as pending")
    assert_true("Village" not in scene.pending_map_states, "current map is applied, not pending")


def test_entering_a_map_applies_its_saved_state() -> None:
    """Walking back into a visited map restores its NPC conversation + chests."""
    # the player loads on Village...
    scene = _make_scene("Village", [])
    mgr = SaveManager.__new__(SaveManager)
    mgr._apply_map_states(scene, {"Village": MapState(name="Village"), "Tavern": _barman_map_state()})

    # ...then walks into the Tavern, which is rebuilt fresh from its TMX
    barman = _make_npc("Barman")
    chest = _make_chest("TavernChest")
    scene.current_map = "Tavern"
    scene.NPCs = [barman]
    scene.chests = [chest]

    mgr.apply_pending_map_state(scene)

    assert_true(barman.restored_state is not None, "barman got his dialog state back")
    assert_eq(barman.restored_state.visited_nodes, {"012": True}, "visited node restored")
    assert_eq(barman.restored_state.sentiment, 77, "sentiment restored")
    assert_true(not chest.model.is_closed, "chest is still open")
    # the sprite must follow the flag - setting only `model.is_closed` used to
    # leave a looted chest drawn shut after a load
    assert_eq(chest.image, "open", "open chest uses the open sprite")
    # consumed exactly once
    assert_true("Tavern" not in scene.pending_map_states, "pending entry consumed")


def test_applying_is_idempotent_and_scoped() -> None:
    """A map with no pending state keeps its TMX defaults."""
    scene = _make_scene("Village", [])
    mgr = SaveManager.__new__(SaveManager)
    mgr._apply_map_states(scene, {"Village": MapState(name="Village"), "Tavern": _barman_map_state()})

    # entering a map that was never visited before: nothing to apply
    fresh_npc = _make_npc("Blacksmith")
    scene.current_map = "Forge"
    scene.NPCs = [fresh_npc]
    mgr.apply_pending_map_state(scene)
    assert_true(fresh_npc.restored_state is None, "untouched map keeps TMX defaults")

    # entering the Tavern twice must not re-apply stale state over live progress
    barman = _make_npc("Barman")
    scene.current_map = "Tavern"
    scene.NPCs = [barman]
    mgr.apply_pending_map_state(scene)
    assert_true(barman.restored_state is not None, "first entry restores")

    barman.restored_state = None
    mgr.apply_pending_map_state(scene)
    assert_true(barman.restored_state is None, "second entry is a no-op")


def test_saving_preserves_unvisited_pending_maps() -> None:
    """The autosave on every map change must not drop maps not yet revisited.

    This is the trap in the fix: `_build_map_states` reads live objects, and a
    pending map has none — so without an explicit pass-through, walking A -> C
    would quietly erase B's progress from the new save.
    """
    scene = _make_scene("Village", [])
    mgr = SaveManager.__new__(SaveManager)
    mgr._apply_map_states(scene, {"Village": MapState(name="Village"), "Tavern": _barman_map_state()})

    # the player is on Village and saves (or walks to another map, autosaving)
    scene.loaded_maps = {}
    built = mgr._build_map_states(scene)

    assert_true("Tavern" in built, "pending map survives the save")
    assert_eq(
        built["Tavern"].npc_states["Barman"].dialog_state.visited_nodes,
        {"012": True},
        "pending map's dialog state carried through untouched",
    )
    assert_true("Village" in built, "current map still saved")


def test_live_map_wins_over_pending() -> None:
    """Once re-entered, a map is rebuilt from live objects, not the stale pending copy."""
    scene = _make_scene("Tavern", [])
    mgr = SaveManager.__new__(SaveManager)
    # a stale pending entry for the very map we are standing on
    scene.pending_map_states = {"Tavern": _barman_map_state()}

    barman = _make_npc("Barman")
    barman.dialog_nodes = None  # no graph -> no dialog state captured
    scene.NPCs = [barman]

    built = mgr._build_map_states(scene)

    # the live (current) map must not be overwritten by the pending snapshot
    assert_true(built["Tavern"].npc_states["Barman"].dialog_state is None, "live state wins")


def _real_sprite_scene(current_map: str) -> SimpleNamespace:
    """A scene stub with real pygame groups, so ItemSprites can actually be built."""
    pygame.init()
    pygame.display.set_mode((64, 64))
    item_conf = {
        "MERMAIDS_TEAR": SimpleNamespace(
            type=ItemTypeEnum.gem, count=1, value=50, weight=1.0, damage=0,
            cooldown_time=1.0, health_impact=0, in_use=False,
        )
    }
    scene = SimpleNamespace(
        current_map=current_map,
        loaded_maps={},
        pending_map_states={},
        NPCs=[],
        chests=[],
        items=[],
        item_sprites=pygame.sprite.Group(),
        group=pygame.sprite.LayeredUpdates(),
        destructibles=[],
        walls=[],
        path_finding_grid=[[0, 0], [0, 0]],
        is_maze=False,
        sprites_layer=1,
        items_sheet={},
        game=SimpleNamespace(conf=SimpleNamespace(items=item_conf)),
    )
    scene.store_map = lambda: scene.loaded_maps.__setitem__(scene.current_map, {})
    return scene


def _spawn_tmx_item(scene: SimpleNamespace, name: str) -> object:
    """Stand in for `Scene.load_items` respawning a TMX-placed ground item."""
    from objects import ItemSprite

    model = SimpleNamespace(
        type=ItemTypeEnum.gem, count=1, value=50, weight=1.0, damage=0,
        cooldown_time=1.0, health_impact=0, in_use=False,
    )
    sprite = ItemSprite(scene.item_sprites, (32, 32), name, model)
    scene.items.append(sprite)
    scene.group.add(sprite, layer=scene.sprites_layer - 1)
    return sprite


def test_ground_items_are_replaced_not_appended() -> None:
    """Loading must not stack a second copy of every TMX item onto the map.

    Verified against the real game before fixing: Village went 4 -> 8 -> 12 -> 16
    ground items over repeated save/load cycles, and a picked-up MERMAIDS_TEAR
    came back onto the ground while staying in the player's bag.
    """
    scene = _real_sprite_scene("Village")
    mgr = SaveManager.__new__(SaveManager)

    # the map was just rebuilt from its TMX: the item is on the ground again
    _spawn_tmx_item(scene, "MERMAIDS_TEAR")
    assert_eq(len(scene.items), 1, "TMX respawned the item")

    # ...but the save says it is still lying there exactly once
    ms = MapState(
        name="Village",
        ground_items=[GroundItemState(name="MERMAIDS_TEAR", type=ItemTypeEnum.gem, count=1,
                                      pos_x=32, pos_y=32)],
    )
    mgr._apply_one_map_state(scene, ms)

    assert_eq(len(scene.items), 1, "exactly one copy after restore, not two")
    assert_eq(len(scene.item_sprites.sprites()), 1, "sprite groups agree")


def test_picked_up_item_stays_picked_up() -> None:
    """The save is the authority: an item the player took must not respawn."""
    scene = _real_sprite_scene("Village")
    mgr = SaveManager.__new__(SaveManager)

    _spawn_tmx_item(scene, "MERMAIDS_TEAR")  # TMX puts it back...

    # ...but the save recorded an empty ground: the player had picked it up
    mgr._apply_one_map_state(scene, MapState(name="Village", ground_items=[]))

    assert_eq(len(scene.items), 0, "picked-up item does not come back")
    assert_eq(len(scene.item_sprites.sprites()), 0, "and its sprite is gone too")


def test_first_save_records_already_destroyed_walls() -> None:
    """A bush smashed before the very first save must land in that save.

    The old implementation diffed `scene.walls` against a snapshot it took
    lazily on the first `_build_destroyed_walls` call - i.e. after the player
    had already been smashing things - so the first save of every session
    always reported an empty list and every bush/rock came back on load.
    """
    scene = _make_scene("Village", [])
    mgr = SaveManager.__new__(SaveManager)

    # player smashed two destructibles, then saves for the first time
    scene.destroyed_walls = [(32, 48), (64, 48)]

    assert_eq(mgr._build_destroyed_walls(scene), [(32, 48), (64, 48)],
              "first save reports what was already destroyed")


def test_destroyed_walls_of_other_maps_survive_a_save() -> None:
    """Bushes smashed on a map the player has left are not thrown away."""
    scene = _make_scene("Village", [])
    mgr = SaveManager.__new__(SaveManager)
    scene.destroyed_walls = []
    scene.loaded_maps = {"Tavern": {"destroyed_walls": [(16, 16)], "NPCs": [], "chests": [], "items": []}}

    maps = mgr._build_map_states(scene)

    assert_eq(maps["Tavern"].destroyed_walls, [(16, 16)],
              "the cached map keeps its destroyed walls")


def test_loading_reseeds_the_scene_destroyed_walls() -> None:
    """After a load, saving again must still report the restored destructions."""
    scene = _make_scene("Village", [])
    mgr = SaveManager.__new__(SaveManager)

    mgr._apply_one_map_state(scene, MapState(name="Village", destroyed_walls=[(32, 48)]))

    assert_eq(mgr._build_destroyed_walls(scene), [(32, 48)],
              "a re-save keeps what the loaded save had destroyed")


def test_a_dead_monster_stays_dead_across_two_save_cycles() -> None:
    """A kill must survive load -> save -> load, not just the first load.

    `NPC.die()` drops the monster from `scene.NPCs`, so the *only* durable record
    of the kill is `MapState.dead_monsters`. `_apply_npc_states` used to consume
    that list - kill the sprite, remove it - without telling the scene, so the
    next save read the (now monster-less) live list, wrote `dead_monsters=[]`,
    and the monster came back to life. Reported from a maze: load a save, walk in
    (autosave fires), the lion is correctly gone; press F9 and it is standing
    there again, next to the chest that correctly stayed open.
    """
    lion = _make_npc("CaveLion")
    scene = _make_scene("Maze_01", [lion])
    scene.group.add(lion)
    mgr = SaveManager.__new__(SaveManager)

    # first load: the save says the lion is dead, so it is removed from the map
    mgr._apply_npc_states(scene, MapState(name="Maze_01", dead_monsters=["CaveLion"]))
    assert_true(lion not in scene.NPCs, "the dead lion is taken off the map")

    # the autosave that fires right after must still report it
    assert_eq(mgr._build_dead_monsters(scene), ["CaveLion"],
              "a re-save keeps the kill the loaded save had recorded")


def test_dead_monsters_of_other_maps_survive_a_save() -> None:
    """A kill on a map the player has walked out of is read from its cache."""
    scene = _make_scene("Village", [])
    mgr = SaveManager.__new__(SaveManager)
    scene.loaded_maps = {
        "Maze_01": {"dead_monsters": ["CaveLion"], "NPCs": [], "chests": [],
                    "items": [], "destroyed_walls": []},
    }

    maps = mgr._build_map_states(scene)

    assert_eq(maps["Maze_01"].dead_monsters, ["CaveLion"],
              "the cached map keeps its dead monsters")


def test_dead_monsters_is_a_cached_map_property() -> None:
    """`Scene.properties` must list it, or the cache above is always empty.

    `store_map`/`restore_map` copy exactly the names in `Scene.properties`, so a
    field missing from that list silently does not survive a map change - which is
    how the kill list got lost for any map other than the live one.
    """
    import ast
    import pathlib

    source = pathlib.Path(__file__).resolve().parent.parent / "project" / "scene.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    listed: list[str] = []
    for node in ast.walk(tree):
        # `self.properties: list[str] = [...]` is an AnnAssign; plain `=` an Assign
        targets = [node.target] if isinstance(node, ast.AnnAssign) else \
                  node.targets if isinstance(node, ast.Assign) else []
        if (targets
                and any(isinstance(t, ast.Attribute) and t.attr == "properties" for t in targets)
                and isinstance(node.value, ast.List)):
            listed = [e.value for e in node.value.elts
                      if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            break

    assert_true(bool(listed), "found the Scene.properties list in scene.py")
    for field in ("dead_monsters", "destroyed_walls", "NPCs"):
        assert_true(field in listed, f"{field!r} is cached per map")


def test_a_kill_during_play_is_recorded_without_the_sprite() -> None:
    """`die()` removes the NPC, so the scene must note the name at that moment."""
    lion = _make_npc("CaveLion")
    scene = _make_scene("Maze_01", [lion])
    mgr = SaveManager.__new__(SaveManager)

    # what NPC.die() does to the scene, minus the pygame parts
    scene.NPCs = [n for n in scene.NPCs if n is not lion]
    scene.note_monster_death(lion.name)

    assert_eq(mgr._build_dead_monsters(scene), ["CaveLion"],
              "the kill is saved even though nothing on the map represents it")


def test_chests_from_one_template_do_not_collapse() -> None:
    """Several chests built from the same config template are distinct entries.

    Every small chest in a maze comes from `level_properties.small_chest_template`,
    so keying the save by the bare template name folded them all into one entry:
    the save recorded whatever the last chest happened to be, and on load exactly
    one chest got that state while the rest silently reset to their TMX defaults.
    The scene now names them `<template>#<n>`.
    """
    scene = _make_scene("Maze_01", [])
    mgr = SaveManager.__new__(SaveManager)

    looted = _make_chest("SmallChest_Maze_01#0")
    looted.open()
    untouched = _make_chest("SmallChest_Maze_01#1")
    scene.chests = [looted, untouched]

    states = mgr._build_chest_states(scene)
    assert_eq(len(states), 2, "two chests, two save entries")
    assert_true(not states["SmallChest_Maze_01#0"].is_closed, "the looted one is open")
    assert_true(states["SmallChest_Maze_01#1"].is_closed, "the other one is still shut")

    # ...and the state comes back onto the right chest
    rebuilt = [_make_chest("SmallChest_Maze_01#0"), _make_chest("SmallChest_Maze_01#1")]
    scene.chests = rebuilt
    mgr._apply_chest_states(scene, states)

    assert_eq(rebuilt[0].image, "open", "first chest restored as open")
    assert_eq(rebuilt[1].image, "closed", "second chest stayed closed")


def test_maze_seed_is_the_one_that_built_the_level() -> None:
    """The save must carry the seed in use, not a freshly rolled one.

    `_build_maze_seed` used to `random.randint(...)` at save time. Nothing read the
    field back, so it went unnoticed - but the moment anything did, it would have
    rebuilt a different dungeon than the one the player was standing in.
    """
    scene = _make_scene("Maze_01", [])
    mgr = SaveManager.__new__(SaveManager)
    scene.is_maze = True
    scene.maze_seed = 1234567

    assert_eq(mgr._build_maze_seed(scene), 1234567, "the live seed is saved verbatim")

    scene.is_maze = False
    assert_eq(mgr._build_maze_seed(scene), None, "an ordinary map has no seed")


def test_maze_level_left_behind_keeps_its_seed() -> None:
    """Walking out of a dungeon and saving must not lose the dungeon."""
    scene = _make_scene("Village", [])
    mgr = SaveManager.__new__(SaveManager)
    scene.destroyed_walls = []
    scene.loaded_maps = {
        "Maze_01": {
            "maze_seed": 777, "maze_stats": {"current_map_level": 1},
            "return_map": "Village", "return_entry_point": "Stairs",
            "destroyed_walls": [], "NPCs": [], "chests": [], "items": [],
        }
    }

    maps = mgr._build_map_states(scene)

    assert_eq(maps["Maze_01"].maze_seed, 777, "seed of the level we left")
    assert_eq(maps["Maze_01"].maze_level, 1, "and its level number")
    assert_eq(maps["Maze_01"].maze_return_map, "Village", "and where its exit leads")


def test_autosave_only_on_the_way_into_the_dungeon() -> None:
    """Slot 0 autosaves only when entering a maze.

    A maze run gets one autosave - the step in from the overworld. Ordinary
    room-to-room transitions, going deeper into the dungeon, climbing back up,
    and walking out to the surface must not trigger it, so slot 0 always points
    at the mouth of the dungeon.
    """
    mgr = SaveManager.__new__(SaveManager)

    # is_maze=True: entering a maze (overworld -> maze level 1)
    assert_true(mgr.should_autosave_on_map_change(is_maze=True),
                "entering a maze autosaves")

    # is_maze=False: ordinary room-to-room, or leaving a maze
    assert_true(not mgr.should_autosave_on_map_change(is_maze=False),
                "non-maze transitions never autosave")


def main() -> None:
    tests = [
        test_other_maps_are_kept_pending_not_dropped,
        test_entering_a_map_applies_its_saved_state,
        test_applying_is_idempotent_and_scoped,
        test_saving_preserves_unvisited_pending_maps,
        test_live_map_wins_over_pending,
        test_ground_items_are_replaced_not_appended,
        test_picked_up_item_stays_picked_up,
        test_first_save_records_already_destroyed_walls,
        test_destroyed_walls_of_other_maps_survive_a_save,
        test_loading_reseeds_the_scene_destroyed_walls,
        test_a_dead_monster_stays_dead_across_two_save_cycles,
        test_a_kill_during_play_is_recorded_without_the_sprite,
        test_dead_monsters_of_other_maps_survive_a_save,
        test_dead_monsters_is_a_cached_map_property,
        test_chests_from_one_template_do_not_collapse,
        test_maze_seed_is_the_one_that_built_the_level,
        test_maze_level_left_behind_keeps_its_seed,
        test_autosave_only_on_the_way_into_the_dungeon,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} multi-map save/load tests passed.")


if __name__ == "__main__":
    main()
