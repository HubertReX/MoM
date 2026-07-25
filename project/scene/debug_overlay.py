"""Nakładka debug (` / Z): etykiety NPC, ścieżki A*, hitboxy, siatka labiryntu.

Moduł systemu wg B01 (D1/D3): tu mieszka runtime'owa flaga ``SHOW_DEBUG_INFO``.
Musi być czytana ŻYWO (``debug_overlay.SHOW_DEBUG_INFO``), nie kopiowana przez
``from ... import`` - klawisz ` / Z przestawia ją w trakcie gry, a czytają ją
``Scene.draw``, ``characters.py`` i panel pomocy (kontrakt K9).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
from maze_generator.maze_utils import MARGIN, SUBTILE_COLS, SUBTILE_ROWS, TILE_SIZE

import settings
from settings import FONT_SIZE_MEDIUM, Point, WAYPOINTS_LINE_COLOR, vec

if TYPE_CHECKING:
    from scene.scene import Scene

#: Runtime'owa flaga nakładki debug - przestawiana klawiszem ` / Z
#: (``scene/player_actions.py``), czytana żywo przez wszystkich konsumentów.
SHOW_DEBUG_INFO: bool = settings.SHOW_DEBUG_INFO


def show_debug(scene: "Scene") -> None:
    # MARK: show_debug
    # prepare shader info

    # shader_index = SHADERS_NAMES.index(scene.game.shader.shader_name)
    # shader_index = max(shader_index, 0)
    # shader_name = SHADERS_NAMES[shader_index] if USE_SHADERS else "n/a"
    # prepare debug messages displayed in upper left corner
    # msgs = [
    #     f"FPS: {scene.game.fps: 5.1f} Shader: {shader_name}",
    #     # f"Eye: x:{scene.camera.target.x:6.2f} y:{scene.camera.target.y:6.2f}",
    #     f"Time: {scene.hour}:{scene.minute:02}",
    #     # f"vel: {scene.player.vel.x: 6.1f} {scene.player.vel.y: 6.1f}",
    #     # f"x  : {scene.player.pos.x: 3.0f}   y : {scene.player.pos.y: 3.0f}",
    #     # f"g x:  {scene.player.tileset_coord.x: 3.0f} g y : {scene.player.tileset_coord.y: 3.0f}",
    #     # f"up_vel: {scene.player.up_vel: 3.1f} up_acc{scene.player.up_acc: 3.1f}",
    #     # f"t x:  {scene.player.target.x: 3.0f} t y : {scene.player.target.y: 3.0f}",
    #     # f"offset: {scene.player.jumping_offset: 6.1f}",
    #     # f"col: {scene.player.rect.collidelist(scene.walls):06.02f}",
    #     # f"bored={scene.player.state.enter_time: 5.1f} time_elapsed={scene.game.time_elapsed: 5.1f}",
    # ]
    # scene.debug(msgs)

    if scene.is_maze:
        current_map_level: int = int(scene.current_map.split("_")[1])
        if current_map_level == 1:
            path = scene.maze_stats["longest_N_wall_path"]
        else:
            path = scene.maze_stats["longest_dead_end_path"]
        mark_maze_sub_grid(scene, path[0], "red")
        mark_maze_sub_grid(scene, path[-1], "blue")
        for step in path[1:-1]:
            mark_maze_sub_grid(scene, step, "green")
        pass

    # display npc (and players) debug messages
    for npc in scene.NPCs + [scene.player]:
        # prepare text displayed under NPC
        texts = [
            npc.name,
            # f"px={npc.pos.x // 1:3} y={(npc.pos.y - 4) // 1:3}",
            f"gx={npc.tileset_coord.x:3} y={npc.tileset_coord.y:3}",
            # f"s ={npc.state} j={npc.is_flying}",
            # f"st ={npc.state} sp = {npc.speed}",
            # f"wc={npc.waypoints_cnt} wn={npc.current_waypoint_no}",
            # f"tx={npc.get_tileset_coord(npc.target).x:3} y={npc.get_tileset_coord(npc.target).y:3}",
        ]
        # draw lines connecting waypoints
        if npc.waypoints_cnt > 0:
            # curr_wp = npc.waypoints[npc.current_waypoint_no]
            # add current waypoint as text under NPC
            # texts.append(f"cw={npc.get_tileset_coord(curr_wp).x:3} {npc.get_tileset_coord(curr_wp).y:3}")
            prev_point = Point(int(npc.pos.x), int(npc.pos.y - 4))
            for point in list(npc.waypoints)[npc.current_waypoint_no:]:
                from_p = scene.map_view.translate_point(vec(prev_point.x, prev_point.y))
                to_p = scene.map_view.translate_point(vec(point.x, point.y))
                pygame.draw.line(scene.game.canvas, WAYPOINTS_LINE_COLOR, from_p, to_p, width=2)
                prev_point = point

        pos = scene.map_view.translate_point(npc.pos)
        scene.game.render_texts(texts, pos, font_size=FONT_SIZE_MEDIUM, centred=True)

        # render red square indicating hitbox
        rect = scene.map_view.translate_rect(npc.feet)
        pygame.draw.rect(scene.game.canvas, "red", rect, width=2)

    # # draw walls (colliders)
    # for y, row in enumerate(scene.path_finding_grid):
    #     for x, tile in enumerate(row):
    #         if tile > 0:
    #             rect_w = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
    #             rect_s = scene.map_view.translate_rect(rect_w)
    #             img = pygame.Surface(rect_s.size, pygame.SRCALPHA)
    #             pygame.draw.rect(img, (0,0,200,64), img.get_rect())
    #             scene.game.canvas.blit(img, rect_s)


def mark_maze_sub_grid(scene: "Scene", start: tuple[int, int], color: str) -> None:
    # MARGIN = 3
    # MARGIN_X = 3
    # MARGIN_Y = 3
    # SUBTILE_GRID = 6

    left = MARGIN * TILE_SIZE + start[0] * SUBTILE_COLS * TILE_SIZE
    top  = MARGIN * TILE_SIZE + start[1] * SUBTILE_ROWS * TILE_SIZE
    rect = scene.map_view.translate_rect((left, top, SUBTILE_COLS * TILE_SIZE, SUBTILE_ROWS * TILE_SIZE))
    pygame.draw.rect(scene.game.canvas, color, rect, width=4)
