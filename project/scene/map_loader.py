"""Ładowanie mapy: TMX/labirynt, warstwy, koszty kroku, NPC-e, grupy sprite'ów.

Moduł systemu wg B01 (D1): bezstanowe funkcje operujące na przekazanej scenie -
cały stan zostaje atrybutami ``Scene`` (kontrakt K1 save/load). Jedyny punkt
lokalnego importu ``characters`` w pakiecie scene mieszka tutaj (cykl
scene ↔ characters rozwiązany jawnie - patrz doc/refactor-rdzenia-B01.md).
"""
from __future__ import annotations

import copy
import random
from typing import TYPE_CHECKING, cast

import pygame
import pyscroll
import pyscroll.data
from maze_generator.hunt_and_kill_maze import HuntAndKillMaze
from maze_generator.maze_utils import (
    EMPTY_CELL,
    IMAGE_DIRECTION_TO_CHEST,
    MARGIN,
    SUBTILE_COLS,
    SUBTILE_ROWS,
    TILE_SIZE,
    X_CENTER,
    Y_CENTER,
    analyze_maze,
    build_tileset_map_from_maze,
    clear_maze_cache,
    find_dead_ends,
    find_tiles_with_cross_way,
)
from objects import ChestSprite, Collider, DestructibleSprite, ItemSprite, NotificationTypeEnum
from pyscroll.group import PyscrollGroup
from pytmx import TiledMap, TiledObjectGroup, TiledTileLayer
from pytmx.util_pygame import load_pygame
from rich import print

import settings
from settings import _, to_point, tuple_to_vector, vec

from scene import fog_of_war

if TYPE_CHECKING:
    from scene.scene import Scene


def create_item(scene: "Scene", name: str, x: int, y: int, show: bool = True) -> ItemSprite:
    group = scene.item_sprites if show else None
    return ItemSprite(
        group,
        (x, y),
        name,  # tile.item_name,
        image=scene.items_sheet[name],
        model=copy.copy(scene.game.conf.items[name])
    )


#############################################################################################################

# def load_items_def(scene: "Scene") -> None:
#     items_map = load_pygame(str(ITEMS_DIR / "Items.tmx"))
#     items_layer = cast(TiledTileLayer, items_map.get_layer_by_name("Items"))

#     scene.items_defs = {}
#     for x, y, tile in items_layer.tiles():
#         gid = items_layer.data[y][x]
#         # skip item defs that don't have item_name property set
#         if gid not in items_map.tile_properties:
#             continue

#         name = items_map.tile_properties[gid]["item_name"]
#         if name in scene.game.conf.items:
#             scene.items_defs[name] = tile
#         else:
#             if name:
#                 print(f"[red]ERROR![/] '{name}' item has no definition in '[b][u]config.json[/u][/b]'")

#############################################################################################################

def load_map(scene: "Scene") -> None:
    # MARK: load_map

    tileset_map = load_tileset_map(scene)

    # setup level geometry with simple pygame rectangles, loaded from pytmx
    scene.layers = []
    for layer in tileset_map.layers:
        scene.layers.append(layer.name)

    scene.outdoor = tileset_map.properties.get("outdoor", False)

    load_walls(scene, cast(TiledTileLayer, tileset_map.get_layer_by_name("walls")))

    # mgła wojny (E03) - po `load_walls`, bo czyta gotową `path_finding_grid`
    # (żywo, więc zniszczona ściana od razu zmienia geometrię widzenia) oraz
    # warstwę `floor` (kafle bez podłogi to wnętrza bloków ścian)
    fog_of_war.build(scene, tileset_map)

    load_items(scene, cast(TiledTileLayer, tileset_map.get_layer_by_name("items")))

    load_interactions(scene, cast(TiledTileLayer, tileset_map.get_layer_by_name("interactions")))

    if "zones" in scene.layers:
        load_zones(scene, cast(TiledTileLayer, tileset_map.get_layer_by_name("zones")))

    scene.waypoints = {}
    # layer of invisible objects consisting of points that layout a list waypoints to follow by NPCs
    if "waypoints" in scene.layers:
        for obj in cast(TiledObjectGroup, tileset_map.get_layer_by_name("waypoints")):
            scene.waypoints[obj.name] = tuple(to_point(point) for point in obj.points)

    scene.places = {}
    # Named points a daily routine can send an NPC to (`places` layer in Tiled).
    # The objects carry nothing but a name - which place is whose is decided in
    # characters.csv, because the same tavern is the barman's `work` and
    # everybody else's `social`, and a property on the object could only say
    # one of those. A map without this layer is fine: every routine step then
    # resolves to "no destination" and nobody moves differently than before.
    if "places" in scene.layers:
        for obj in cast(TiledObjectGroup, tileset_map.get_layer_by_name("places")):
            rect = pygame.Rect(obj.x, obj.y, obj.width, obj.height)
            scene.places[obj.name] = vec(rect.midbottom)

    scene.entry_points = {}
    # layer of invisible objects being single points on map where NPCs show up coming from linked map
    if "entry_points" in scene.layers:
        for obj in cast(TiledObjectGroup, tileset_map.get_layer_by_name("entry_points")):
            rect = pygame.Rect(obj.x, obj.y, obj.width, obj.height)
            scene.entry_points[obj.name] = vec(rect.midbottom)

    # load NPCs only once
    if scene.current_map not in scene.loaded_maps:
        load_NPCs(scene, cast(TiledObjectGroup, tileset_map.get_layer_by_name("spawn_points")))

    clear_maze_cache()

    # create new renderer (camera)
    scene.map_view = pyscroll.BufferedRenderer(
        data = pyscroll.data.TiledMapData(tileset_map),
        size = scene.game.canvas.get_size(),
        # camera stops at map borders (no black area around), player blocked to be stopped separately
        clamp_camera = True,
    )

    # TODO fix zoom
    # scene.map_view.zoom = scene.camera.zoom

    set_entry_point(scene)

    # Pyscroll supports layered rendering.
    # Our map has several 'under' layers and 'over' layers in relations to Sprites.
    # Sprites (NPCs) are always drawn over the tiles of the layer they are on.
    scene.sprites_layer = scene.layers.index("sprites")

    scene.group = PyscrollGroup(map_layer=scene.map_view, default_layer=scene.sprites_layer)

    # main SpritesGroup holding whole tiled map with all layers and NPCs
    populate_sprite_groups(scene)

    load_step_cost(scene, tileset_map)

    # Build the routine roster once, after the hub map is fully up (its step-cost
    # grid is needed to place anyone). This instantiates any routine character
    # not spawned from a map yet, so the off-map schedule tick covers the whole
    # cast; the reconcile then materialises any of them that belong right here.
    if not scene._roster_loaded and not scene.is_maze:
        scene._roster_loaded = True
        scene.load_routine_roster()
        scene.reconcile_routine_presence()

    # scene.group.center(scene.player.pos)
    scene.set_camera_on_player()
    scene.group.center(scene.camera.target)

    scene.load_particles(tileset_map)

    # mark map as loaded
    if scene.current_map not in scene.loaded_maps:
        # A map entered for the first time after loading a save has just been
        # rebuilt from its TMX defaults, so it knows nothing about the chests
        # the player opened, the monsters they killed or the conversations
        # they had here. Re-apply the saved state now, before the map is
        # cached, or that progress is silently rolled back.
        if hasattr(scene.game, "save_manager"):
            scene.game.save_manager.apply_pending_map_state(scene)
        scene.store_map()

#############################################################################################################

def populate_sprite_groups(scene: "Scene") -> None:
    # Put routine NPCs on the map they are logically on before the filter below
    # reads `current_map`, and drop visitors at their destination. No-op on the
    # very first load (nobody has a routine-driven cross-map position yet).
    scene._settle_routine_npcs()

    for item in scene.items:
        if item not in scene.item_sprites:
            scene.item_sprites.add(item)

    for exit in scene.exits:
        if exit not in scene.exit_sprites:
            scene.exit_sprites.add(exit)

    for chest in scene.chests:
        if chest not in scene.obstacles_sprites:
            scene.obstacles_sprites.add(chest)

    for destructible in scene.destructibles:
        if destructible not in scene.obstacles_sprites:
            scene.obstacles_sprites.add(destructible)

    # add all NPCs from current map to the group
    scene.NPCs = []
    for npc in scene.loaded_NPCs.values():
        if npc.current_map == scene.current_map and not npc.is_dead:
            scene.NPCs.append(npc)
            scene.shadow_sprites.add(npc.shadow)
            scene.label_sprites.add(npc.health_bar)
            scene.label_sprites.add(npc.emote)
            npc.register_custom_event()

    scene.group.add(scene.shadow_sprites,    layer=scene.sprites_layer - 2)
    scene.group.add(scene.item_sprites,      layer=scene.sprites_layer - 1)
    scene.group.add(scene.label_sprites,     layer=scene.sprites_layer + 1)

    scene.group.add(scene.obstacles_sprites, layer=scene.sprites_layer - 1)

    # add Player to the group
    scene.group.add(scene.player, layer=scene.sprites_layer)

    scene.group.add(scene.NPCs, layer=scene.sprites_layer)

#############################################################################################################

def load_step_cost(scene: "Scene", tileset_map: TiledMap) -> None:
    for x, y, surf in tileset_map.layers[0].tiles():
        # get step cost for all walkable tiles
        #  100 => wall (not walkable)
        #    0 => initial value for ground (a free space to walk)
        # -100 => road, pavement - low cost
        # -150 => grass, dirt - moderate cost
        # -200 => long grass, corn field - high cost
        # -300 => water - very high cost
        # stored as negative number to distinguish from walls (positive numbers == 100)
        # this is used in A*
        if scene.path_finding_grid[y][x] == 0:
            # check the 'under' layers one by one - the top most cost prevails
            tile_0_gid = tileset_map.get_tile_properties(x, y, 0)
            tile_1_gid = tileset_map.get_tile_properties(x, y, 1)
            # base step cost
            step_cost = -settings.STEP_COST_GROUND
            if tile_0_gid and "step_cost" in tile_0_gid:
                step_cost = tile_0_gid["step_cost"]
            if tile_1_gid and "step_cost" in tile_1_gid:
                step_cost = tile_1_gid["step_cost"]
            scene.path_finding_grid[y][x] = -step_cost

#############################################################################################################

def load_interactions(scene: "Scene", exits_layer: TiledTileLayer) -> None:
    scene.exits = []
    scene.chests = []
    # how many chests of each config template we have built on this map so far.
    # A chest's save key is `<template>#<n>`, so the count is what makes the key
    # unique when one template is reused - which is the normal case in a maze,
    # where every small chest comes from the same template. Keying by the bare
    # template name silently collapsed them all into a single save entry.
    template_counts: dict[str, int] = {}

    def _chest_name(model_name: str) -> str:
        idx = template_counts.get(model_name, 0)
        template_counts[model_name] = idx + 1
        return f"{model_name}#{idx}"

    if "interactions" in scene.layers:
        for obj in exits_layer:
            if getattr(obj, "obj_type", "") == "exit":
                exit = Collider(
                    scene.exit_sprites,
                    (obj.x, obj.y),
                    (obj.width, obj.height),
                    obj.name,
                    obj.to_map,
                    obj.entry_point,
                    obj.is_maze,
                    getattr(obj, "maze_cols", 0),
                    getattr(obj, "maze_rows", 0),
                    getattr(obj, "return_entry_point", ""),
                )
                scene.exits.append(exit)
            elif getattr(obj, "obj_type", "") == "chest":
                if scene.is_maze and scene.maze is not None and obj.name == "SmallChest_Maze":
                    maze = scene.maze
                    # maze_configs = scene.game.conf.maze_configs
                    # level = scene.maze_stats["current_map_level"]
                    # level_properties = maze_configs.get(level, maze_configs[len(maze_configs)])

                    # generate list of maze locations to put small chests
                    # use only cells with one way out
                    candidates = find_dead_ends(maze)

                    # skip start (too easy) and end (big chest will be there)
                    start = scene.maze_stats["start"]
                    if start in candidates:
                        candidates.remove(start)

                    end = scene.maze_stats["end"]
                    if end in candidates:
                        candidates.remove(end)

                    # generate small chests
                    level_properties = scene.maze_stats["level_properties"]
                    # maze_rng, not random: the positions have to come back
                    # identical when this level is rebuilt from its seed
                    for x, y in scene.maze_rng.sample(candidates, level_properties.small_chest_count):
                        # blocked from walking (wall)
                        scene.path_finding_grid[y][x] = settings.STEP_COST_WALL

                        # recalculate grid position to map coordinates
                        image_index = maze.cell_rows[y][x].image_index
                        offset = IMAGE_DIRECTION_TO_CHEST[image_index]
                        x = (MARGIN + x * SUBTILE_COLS + offset[0]) * TILE_SIZE
                        y = (MARGIN + y * SUBTILE_ROWS + offset[1]) * TILE_SIZE

                        rect = pygame.Rect(x, y, TILE_SIZE, TILE_SIZE)
                        scene.walls.append(rect)

                        model_name = level_properties.small_chest_template
                        # deep, not shallow: a shallow copy shares the `items`
                        # list with the config object, and ChestSprite mutates
                        # it in place via generate_random_items() - see the big
                        # chest below for the full story
                        chest = ChestSprite(scene.obstacles_sprites,
                                            (x, y),
                                            copy.deepcopy(scene.game.conf.chests[model_name]),
                                            scene.items_sheet,
                                            name=_chest_name(model_name),
                                            rng=scene.maze_rng,
                                            )
                        scene.chests.append(chest)
                else:
                    rect = pygame.Rect(obj.x, obj.y, obj.width, obj.height)
                    scene.walls.append(rect)

                    # blocked from walking (wall)
                    scene.path_finding_grid[int(obj.y // TILE_SIZE)][int(obj.x // TILE_SIZE)] = settings.STEP_COST_WALL

                    if scene.is_maze:
                        level_properties = scene.maze_stats["level_properties"]
                        model_name = level_properties.big_chest_template
                    else:
                        model_name = obj.name

                    # deepcopy, not copy: `Chest` is a pydantic model on desktop
                    # and a slots dataclass on web, and a shallow copy of either
                    # shares the `items` list with the entry in `game.conf`.
                    # ChestSprite.generate_random_items() appends to that list in
                    # place, so every maze chest built from the same template both
                    # saw the same rolled loot and permanently polluted the config
                    # for the rest of the process.
                    chest = ChestSprite(scene.obstacles_sprites,
                                        (obj.x, obj.y),
                                        copy.deepcopy(scene.game.conf.chests[model_name]),
                                        scene.items_sheet,
                                        name=_chest_name(model_name),
                                        rng=scene.maze_rng if scene.is_maze else None,
                                        )
                    scene.chests.append(chest)

#############################################################################################################

def load_zones(scene: "Scene", zones_layer: TiledTileLayer) -> None:
    scene.zones = {}
    if "zones" in scene.layers:
        for obj in zones_layer:
            if obj.name not in scene.zones:
                scene.zones[obj.name] = []
            zone = pygame.Rect(obj.x, obj.y, obj.width, obj.height)
            scene.zones[obj.name].append(zone)

    # print("[light_green]Zones")
    # for zone_name in scene.zones:
    #     print(f"[magenta]{zone_name}[/]", scene.zones[zone_name])

#############################################################################################################

def load_items(scene: "Scene", items_layer: TiledTileLayer) -> None:
    scene.items = []
    scene.item_sprites.empty()
    if "items" in scene.layers:

        for x, y, tile in items_layer.tiles():
            gid = items_layer.data[y][x]
            name = items_layer.parent.tile_properties[gid]["item_name"]

            item = create_item(scene, name, x * TILE_SIZE, y * TILE_SIZE)
            scene.items.append(item)
        items_layer.visible = False

#############################################################################################################

def load_walls(scene: "Scene", walls_layer: TiledTileLayer) -> None:
    scene.walls = []
    scene.destructibles = []
    scene.destroyed_walls = []
    if "walls" in scene.layers:
        walls_width = walls_layer.width
        walls_height = walls_layer.height
        # path finding uses only grid build of tiles and not world coordinates in pixels
        # 0   => ground (later zeros will be replaced with negative numbers representing actual cost)
        # 100 => wall (not walkable)
        scene.path_finding_grid = [[0 for _ in range(walls_width)] for _ in range(walls_height)]

        for x, y, sprite in walls_layer.tiles():
            # if gid:
            wall = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            scene.walls.append(wall)
            # blocked from walking (wall)
            prev_step_cost = scene.path_finding_grid[y][x]
            scene.path_finding_grid[y][x] = settings.STEP_COST_WALL

            gid = walls_layer.data[y][x]
            obj = walls_layer.parent.tile_properties.get(gid, {})

            if obj.get("destructible", 0):
                type = obj.get("destruct_type", "")
                destructible = DestructibleSprite(
                    scene.obstacles_sprites,
                    (x * TILE_SIZE, y * TILE_SIZE),
                    sprite,
                    wall,
                    prev_step_cost,
                    type,
                )
                scene.destructibles.append(destructible)
                walls_layer.data[y][x] = EMPTY_CELL

#############################################################################################################

def _resolve_maze_seed(scene: "Scene") -> int:
    """Seed for the maze level about to be generated.

    Three ways in, in priority order: a seed already on the scene (this scene
    was built from a save and starts inside the maze), a seed waiting in
    `pending_map_states` (the player is walking back into a level they saved
    on), or a fresh roll for a level nobody has seen yet.
    """
    if scene.maze_seed is not None:
        return scene.maze_seed

    pending = (scene.pending_map_states or {}).get(scene.current_map)
    pending_seed = getattr(pending, "maze_seed", None) if pending is not None else None
    if pending_seed is not None:
        return int(pending_seed)

    return random.randint(0, 2**31 - 1)

#############################################################################################################

def load_tileset_map(scene: "Scene") -> TiledMap:
    if scene.is_maze:
        # check from which scene we came here
        if len(scene.game.states) > 0:
            scene.prev_state = scene.game.states[-1]

        if scene.current_map not in scene.loaded_maps:
            # get maze properties based on maze level
            # if level higher than maze_configs count, use highest
            maze_configs = scene.game.conf.maze_configs
            level = int(scene.current_map.split("_")[1])
            max_level = len(maze_configs)
            level_properties = maze_configs.get(level, maze_configs[max_level])
            scene.maze_cols = level_properties.maze_cols
            scene.maze_rows = level_properties.maze_rows
            # A saved maze level is reproduced, not re-rolled: `scene.maze_seed`
            # is already set when this scene was built from a save, or when the
            # player walks back into a level whose seed is waiting in
            # `pending_map_states`. Otherwise this level is new - roll a seed
            # now and keep it, so the save can bring this exact maze back.
            scene.maze_seed = _resolve_maze_seed(scene)
            scene.maze_rng = random.Random(scene.maze_seed)
            # generate new maze
            scene.maze = HuntAndKillMaze(scene.maze_cols, scene.maze_rows)
            scene.maze.generate(scene.maze_rng)
            scene.maze_stats = analyze_maze(scene.maze)
            scene.maze_stats["level_properties"] = level_properties
            scene.maze_stats["current_map_level"] = level
            scene.maze_stats["max_level"] = max_level

        # tileset_map: TiledMap = load_pygame(str(settings.MAZE_DIR / "MazeTileset_clean.tmx"))
        tileset_map: TiledMap = load_pygame(str(settings.MAZE_DIR / "MazeTileset_Ninja.tmx"))
        # combine tileset clean template with maze grid into final map
        build_tileset_map_from_maze(
            tileset_map,
            scene.maze,
            scene.maze_stats,
            scene.current_map,
            to_map = scene.return_map,
            entry_point = scene.return_entry_point,
            rng = scene.maze_rng,
        )
    else:
        # load data from pytmx
        tileset_map = load_pygame(str(settings.MAPS_DIR / f"{scene.current_map}.tmx"))

    return tileset_map

#############################################################################################################

def set_entry_point(scene: "Scene") -> None:
    default = tuple_to_vector(scene.map_view.map_rect.center)
    result = scene.player.set_entry_point(scene.entry_point, default)
    scene.camera.target = scene.player.pos

    if not result:
        print("\n[red]ERROR![/] no entry point found!\n")
        scene.add_notification(_("scene.error_no_entry"),
                               NotificationTypeEnum.debug)

#############################################################################################################

def load_NPCs(scene: "Scene", spawn_points: TiledObjectGroup) -> None:

    # layer of invisible objects being single points determining where NPCs will spawn
    if "spawn_points" in scene.layers:
        # jedyny lokalny import characters w pakiecie scene (cykl scene <-> characters)
        from characters import NPC
        for obj in spawn_points:
            if obj.name not in scene.loaded_NPCs:
                rect = pygame.Rect(obj.x, obj.y, obj.width, obj.height)
                # list of waypoints attached by NPCs name
                waypoint = scene.waypoints.get(obj.name, ())
                npc = NPC(
                    scene.game,
                    scene,
                    scene.shadow_sprites,
                    scene.label_sprites,
                    # (obj.x, obj.y),
                    rect.midbottom,
                    obj.name,
                    scene.icons,
                    waypoint,
                    model_name=obj.model_name,
                )
                # The rhythm comes off the character's own row in characters.csv,
                # next to the destinations it works with, so "who does what and
                # where" is answerable from one line. Empty means "no routine" -
                # the legacy waypoint loop. `npc.model` is this NPC's own copy,
                # so a routine can still be swapped per instance at runtime.
                routine_key = getattr(npc.model, "routine", "")
                if routine_key and routine_key not in scene.routines.routines:
                    print(f"[routines] '{obj.name}' wants unknown routine '{routine_key}'")
                    routine_key = ""
                npc.runtime.routine_key = routine_key
                scene.loaded_NPCs[obj.name] = npc

    if scene.is_maze and scene.current_map not in scene.loaded_maps:
        # collect positions for possible monster placement
        # all T-shaped tiles and 4-way crossing
        candidates = find_tiles_with_cross_way(scene.maze)
        # all map corner and map center
        candidates.append((0,                     0))
        candidates.append((scene.maze_cols  - 1,  scene.maze_rows  - 1))
        candidates.append((scene.maze_cols  - 1,  0))
        candidates.append((0,                     scene.maze_rows  - 1))
        candidates.append((scene.maze_cols  // 2, scene.maze_rows  // 2))

        # prevent from adding regular monter in the start position
        player_pos = scene.maze_stats["start"]
        if player_pos in candidates:
            candidates.remove(player_pos)

        # prevent from adding regular monster in the end (stairs down to next level) position
        # boss monster will be place there
        end = scene.maze_stats["end"]
        if end in candidates:
            candidates.remove(end)

        id: int = 0
        level_properties = scene.maze_stats["level_properties"]

        # add regular monsters
        # get a `monsters_count` number of randomly selected positions from candidates list
        # maze_rng, not random: both the positions and the model picked for each
        # monster must be reproduced when the level is rebuilt from its seed,
        # otherwise the saved health/position of "Bat_003" lands on a monster
        # that is now a different creature standing somewhere else
        for x_r, y_r in scene.maze_rng.sample(candidates, level_properties.monsters_count):
            id += 1
            npc_model_name: str = scene.maze_rng.choice(level_properties.monsters_list)
            add_NPC_at_grid_pos(scene, id, x_r, y_r, npc_model_name)

        # add boss monster at the end of the longest path (stairs down to next level)
        id += 1
        add_NPC_at_grid_pos(scene, id, end[0], end[1], level_properties.boss_monster)

#############################################################################################################

def add_NPC_at_grid_pos(scene: "Scene", id: int, x: int, y: int, model_name: str) -> None:
    # jedyny lokalny import characters w pakiecie scene (cykl scene <-> characters)
    from characters import NPC

    # Unique across the whole scene, not just this level: `loaded_NPCs` is one
    # dict shared by every map, so without the map prefix the third bat on
    # Maze_01 and the third bat on Maze_02 were both "Bat_003" - the second
    # level's spawn was silently dropped, and a save could not tell the two
    # apart either.
    name = f"{scene.current_map}_{model_name}_{id:03}"
    # recalculate grid position to word coordinates
    pos = ((MARGIN + X_CENTER + x * SUBTILE_COLS) * TILE_SIZE,
           (MARGIN + Y_CENTER + y * SUBTILE_ROWS) * TILE_SIZE)

    npc = NPC(
        scene.game,
        scene,
        scene.shadow_sprites,
        scene.label_sprites,
        pos,
        name,
        scene.icons,
        (),
        model_name=model_name,
    )

    scene.loaded_NPCs[name] = npc
