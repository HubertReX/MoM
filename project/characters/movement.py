"""Ruch postaci: sterowanie, A*, waypointy, fizyka i kierunki animacji.

Moduł systemu wg B01/D6: bezstanowe funkcje przyjmujące ``npc`` jawnie - cały
stan (``pos``/``vel``/``acc``/``waypoints``/``target``) zostaje atrybutem
:class:`characters.npc.NPC` (kontrakt K1 save/load), a klasa ma tylko cienkie
delegaty o niezmienionych nazwach (kontrakt K3: ``npc.find_path()`` itd. wołają
testy i ``agent_ctrl``). Wywołania wewnątrz modułu idą przez ``npc.<metoda>()``,
więc podmiana metody na instancji w teście nadal działa.
"""
from typing import Any, TYPE_CHECKING

import pygame
import random
from pygame.math import Vector2 as vec
from rich import print

from enums import AttitudeEnum, RaceEnum
from maze_generator.maze_utils import a_star_cached, nearest_walkable
from settings import (
    ANIMAL_REACTION_COOLDOWN,
    ANIMAL_REACTION_DURATION,
    ANIMAL_REACTION_EMOTES,
    ANIMAL_REACTION_RADIUS_TILES,
    MAX_NO_ATTEMPTS_TO_FIND_RANDOM_POS,
    MONSTER_WAKE_DISTANCE,
    NPC_MAX_REST_TIME,
    NPC_MIN_REST_TIME,
    NPC_RANDOM_WALK_DISTANCE,
    PLAYER_CONFIG_KEY,
    Point,
    RECALCULATE_PATH_DISTANCE,
    SHOULD_NPC_REST_PROBABILITY,
    TILE_SIZE,
    WANDER_PAUSE,
    WAYPOINT_ARRIVE_RADIUS_SQ,
    resolve_emote,
)

if TYPE_CHECKING:
    from characters.npc import NPC


def get_direction_360(npc: "NPC") -> str:
    if npc.npc_met and npc.is_talking:
        direction = npc.npc_met.pos - npc.pos
        angle = vec(0, -1).angle_to(direction)
    else:
        angle = vec(0, -1).angle_to(npc.vel)
    angle = (angle + 360) % 360

    dir: str
    match npc.sprite_sheet_type:
        case "2x1":
            dir = npc.get_direction_RL(angle)
        case "2x2":
            dir = npc.get_direction_RDL(angle)
        case "3x3":
            dir = npc.get_direction_RDLU(angle)
        case "4x7":
            dir = npc.get_direction_RDLU(angle)
        case _:
            dir = "down"

    return dir


###############################################################################################################
def get_direction_RL(npc: "NPC", angle: float) -> str:
    return "right" if angle < 180.0 else "left"


###############################################################################################################
def get_direction_RDL(npc: "NPC", angle: float) -> str:
    if 0.0 <= angle < 135.0:
        return "right"
    elif 135.0 <= angle < 225.0:
        return "down"
    else:
        return "left"


###############################################################################################################
def get_direction_RDLU(npc: "NPC", angle: float) -> str:
    if 45.0 <= angle < 135.0:
        return "right"
    elif 135.0 <= angle < 225.0:
        return "down"
    elif 225.0 <= angle < 315.0:
        return "left"
    else:
        return "up"


###############################################################################################################
def wander_step(npc: "NPC") -> None:
    """Drift to another spot near the anchor, after a pause.

    The pause is the whole point - without it the character re-rolls a
    destination the instant it arrives and skates around without ever looking
    like it stopped anywhere.
    """
    if npc._wander_anchor is None or npc.game.time_elapsed < npc._wander_next_time:
        return
    radius = npc.scene.routines.defaults.wander_radius
    npc.target = npc.get_random_safe_pos(npc._wander_anchor, range=radius, check_allowed_zones=False)
    npc.find_path()
    npc._wander_next_time = npc.game.time_elapsed + WANDER_PAUSE


###############################################################################################################
def movement(npc: "NPC") -> None:
    if npc.is_stunned or npc.is_talking:
        return

    # After the `is_talking` guard on purpose: a slot boundary crossed mid
    # dialog is applied when the panel closes, not during it. Otherwise the
    # merchant walks off in the middle of a transaction and TradePanel is left
    # holding a reference to somebody who is no longer there.
    npc.update_schedule()

    if npc.model.race == RaceEnum.monster:
        npc.movement_monster()
    # elif npc.model.attitude == AttitudeEnum.afraid:
    elif npc.model.race == RaceEnum.animal:
        npc.movement_animal()

    npc.follow_waypoints()


###############################################################################################################
def animal_reaction(npc: "NPC") -> None:
    """Zwierzę zauważa gracza, który podszedł blisko (H01/W7).

    Rozszerzenie mechanizmu, który już był, a nie nowy: potrącone zwierzę wpada
    w `Stunned` i pokazuje `shocked_anim` (`npc_state.get_new_state`). Tyle że
    zderzenie jest rzadkie, a podejście blisko - ciągłe, więc wieś była martwa
    dokładnie tam, gdzie najłatwiej ją ożywić.

    Emoji wybiera zasiany generator postaci (A04), a cooldown pilnuje, żeby
    zwierzę nie migało za każdym razem, gdy gracz przestąpi z nogi na nogę.
    Onomatopeje ("Muuu", "Ko-ko") to TREŚĆ i idą pulą barków - tędy leci sam obrazek.
    """
    if npc.is_stunned or npc.is_dead:
        # potrącone zwierzę ma już swoją, mocniejszą reakcję - nie nadpisujemy jej
        return
    now = npc.game.time_elapsed
    if now < npc._animal_reaction_time:
        return
    radius = ANIMAL_REACTION_RADIUS_TILES * TILE_SIZE
    if (npc.pos - npc.scene.player.pos).magnitude_squared() > radius ** 2:
        return
    npc._animal_reaction_time = now + ANIMAL_REACTION_COOLDOWN
    emote = npc._routine_emote_rng().choice(list(ANIMAL_REACTION_EMOTES))
    npc.emote.set_temporary_emote(resolve_emote(emote), ANIMAL_REACTION_DURATION)


###############################################################################################################
def movement_animal(npc: "NPC") -> None:
    animal_reaction(npc)
    # distance_from_player = (npc.pos - npc.scene.player.pos).magnitude_squared()
    distance_from_target = (npc.pos - npc.target).magnitude_squared()

    if npc.waypoints_cnt == 0 or distance_from_target < 4**2:
        should_rest: bool = random.randint(0, 100) < SHOULD_NPC_REST_PROBABILITY
        if npc.end_rest_time < 0.0 and should_rest:
            npc.target = vec(0, 0)
            npc.waypoints = ()
            npc.waypoints_cnt = 0
            npc.speed = 0

            delta = NPC_MAX_REST_TIME - NPC_MIN_REST_TIME
            npc.end_rest_time = npc.game.time_elapsed + NPC_MIN_REST_TIME + random.random() * delta
            # print(f"({npc.game.time_elapsed:4.1f}) [yellow]{npc.name}[/] "
            #       f"will rest for {(npc.end_rest_time - npc.game.time_elapsed):4.1f} sec ")
        else:
            if npc.game.time_elapsed > npc.end_rest_time:
                # print(f"({npc.game.time_elapsed:4.1f}) [yellow]{npc.name}[/] will no longer rest")
                npc.end_rest_time = -1.0
                npc.speed = npc.speed_walk
                # current_way_point_vec.distance_squared_to(npc_pos) <= 2.0

                target_vec = npc.get_random_safe_pos(npc.pos, range=NPC_RANDOM_WALK_DISTANCE)

                # verify A* reachability before committing (cache makes 2nd call in find_path free)
                npc_tile = (npc.tileset_coord.y, npc.tileset_coord.x)
                target_tile = npc.get_tileset_coord(target_vec)
                reachable = a_star_cached(start=npc_tile, goal=(target_tile.y, target_tile.x), grid=npc.scene.path_finding_grid)
                if not reachable:
                    npc.target = vec(0, 0)
                    npc.end_rest_time = npc.game.time_elapsed + 1.0
                    return

                npc.target = target_vec
                npc.find_path()
                npc.check_waypoints_in_exit()
                if npc.waypoints_cnt == 0:
                    npc.target = vec(0, 0)
                    npc.end_rest_time = npc.game.time_elapsed + 1.0


###############################################################################################################
def get_random_safe_pos(
    npc: "NPC",
    start_pos: vec,
    range: float = 1.0,
    check_exits: bool = True,
    check_allowed_zones: bool = True,
    allow_start_pos: bool = True,
) -> vec:

    repeat = True
    repeat_cnt: int = 0
    new_rect = pygame.FRect(0.0, 0.0, TILE_SIZE, TILE_SIZE)  # npc.rect.copy()

    while repeat:
        repeat_cnt += 1
        target_vec = start_pos + npc.get_random_pos(range, range)
        new_rect.center = target_vec  # type: ignore[assignment]

        if repeat_cnt > MAX_NO_ATTEMPTS_TO_FIND_RANDOM_POS:
            print(
                f"[red]ERROR![/] in [magenta]get_random_safe_pos[/] can't find safe pos for [blue]{npc.name}[/]"
                f" from {start_pos}!")
            return target_vec

        # check if new position is within rect around start position
        if not allow_start_pos:
            start_rect = pygame.FRect(0, 0, TILE_SIZE, TILE_SIZE)
            start_rect.center = start_pos  # type: ignore[assignment]
            if start_rect.collidepoint(target_vec):
                print("[yellow]Warning[/] same position not allowed")
                continue

        # check if new pos is not on exit
        if check_exits:
            if npc.check_pos_is_exit(target_vec):
                continue

        # check if new pos is inside one of allowed zones
        if check_allowed_zones:
            if len(npc.model.allowed_zones) > 0:
                matched_any_zone: bool = False
                for zone_name in npc.model.allowed_zones:
                    allowed_zones = npc.scene.zones[zone_name]
                    for zone in allowed_zones:
                        if zone.contains(new_rect):
                            matched_any_zone = True
                            # print(f"[magenta]Zone: {zone_name}[/] matched for [blue]{npc.name}[/]!")
                            break
                    if matched_any_zone:
                        break
                if not matched_any_zone:
                    # zone_names = ", ".join(npc.model.allowed_zones)
                    # print(f"[red]ERROR![/] [blue]{npc.name}[/] outside of zones ({zone_names})!")
                    continue

        # check if new position is in map bounds
        target_grid = npc.get_tileset_coord(target_vec, offset_y=0)
        # target_grid.x -= 1
        # target_grid.y -= 1
        grid = npc.scene.path_finding_grid
        if target_grid.y < 0 or target_grid.y >= len(grid) or \
                target_grid.x < 0 or target_grid.x >= len(grid[0]):
            continue

        # check if new position is not on a wall
        value = grid[target_grid.y][target_grid.x]
        if value < 0:
            repeat = False

    return target_vec


###############################################################################################################
def check_waypoints_in_exit(npc: "NPC") -> None:
    # check if waypoints are inside one of the exits
    new_waypoints: list[Point] = []
    for waypoint in npc.waypoints:
        if npc.check_pos_is_exit(waypoint.as_vector):
            break
        new_waypoints.append(waypoint)

    # accept only waypoints that are before the on in exit
    npc.waypoints = tuple(new_waypoints)
    npc.waypoints_cnt = len(new_waypoints)
    if npc.current_waypoint_no > npc.waypoints_cnt - 1:
        npc.current_waypoint_no = 0


###############################################################################################################
def check_pos_is_exit(npc: "NPC", target_vec: vec) -> bool:
    for exit in npc.scene.exit_sprites:
        if exit.rect.collidepoint(target_vec):
            return True

    return False


###############################################################################################################
def movement_monster(npc: "NPC") -> None:
    distance_from_player = (npc.pos - npc.scene.player.pos).magnitude_squared()
    # activate monsters in maze when player is near
    # no designated waypoints, distance from player in range, is enemy
    if npc.waypoints_cnt == 0 and distance_from_player < MONSTER_WAKE_DISTANCE**2:
        if npc.game.time_elapsed < npc.next_pathfind_time:
            return
        npc.target = npc.scene.player.pos.copy()
        npc.speed = npc.speed_run
        npc.emote.set_temporary_emote("red_exclamation_anim", 4.0)
        npc.find_path()
        if npc.waypoints_cnt == 0:
            npc.target = vec(0, 0)
            npc.next_pathfind_time = npc.game.time_elapsed + 0.5
        # if character has a set target (and needs to follow it) or there are no waypoints to follow any more
    elif npc.target != vec(0, 0):  # or npc.waypoints_cnt == 0:
        # if (no more waypoints or the player has moved) and (character is a monster chasing player)
        # not npc.target == npc.scene.player.pos)
        distance_player_moved = (npc.target - npc.scene.player.pos).magnitude_squared()

        # if (npc.waypoints_cnt == 0 or not npc.target == npc.scene.player.pos) and \
        #     npc.model.attitude == AttitudeEnum.enemy.value:
        if (distance_player_moved > RECALCULATE_PATH_DISTANCE ** 2) \
                and npc.model.attitude == AttitudeEnum.enemy:
            if npc.game.time_elapsed < npc.next_pathfind_time:
                return
            npc.target = npc.scene.player.pos.copy()
            npc.find_path()
            if npc.waypoints_cnt == 0:
                npc.target = vec(0, 0)
                npc.next_pathfind_time = npc.game.time_elapsed + 0.5


###############################################################################################################
def follow_waypoints(npc: "NPC") -> None:
    if npc.waypoints_cnt <= 0:
        return

    npc_pos = npc.pos
    current_way_point_vec = npc.waypoints[npc.current_waypoint_no].as_vector
    current_way_point_vec.y += 4
    # The arrival window has to be at least as wide as one frame's travel.
    # Steering here is bang-bang - `force` is applied at full strength towards
    # the waypoint no matter how close it is - so a character that cannot land
    # *inside* the window overshoots, gets full force back, overshoots again,
    # and shivers between two positions forever instead of arriving. The fixed
    # ~1.4px window was narrower than a single step at run speed (1.5 * 40 *
    # dt), which is why it looked intermittent: it depended on the frame rate,
    # on the terrain's step cost, and on whether that character happened to
    # roll walk or run speed at spawn.
    #
    # `pos - prev_pos` is exactly last frame's displacement (physics() samples
    # prev_pos before moving), so the window measures itself and stays tight
    # for slow characters.
    step = (npc.pos - npc.prev_pos).length()
    arrive_radius_sq = max(WAYPOINT_ARRIVE_RADIUS_SQ, step * step)
    if current_way_point_vec.distance_squared_to(npc_pos) <= arrive_radius_sq:
        npc.current_waypoint_no += 1
        # if following target and reached goal do not start over again
        if npc.current_waypoint_no >= npc.waypoints_cnt:
            if npc.target != vec(0, 0):
                return npc.clear_waypoints()
            else:
                npc.current_waypoint_no = 0
            current_way_point_vec = npc.waypoints[npc.current_waypoint_no].as_vector
            current_way_point_vec.y += 4
    direction = current_way_point_vec - npc_pos
    if direction.length_squared() > 0:
        direction = direction.normalize() * npc.force
        npc.acc.x = direction.x
        npc.acc.y = direction.y
    else:
        npc.acc.x = 0
        npc.acc.y = 0


###############################################################################################################
def clear_waypoints(npc: "NPC") -> None:
    npc.target = vec(0, 0)
    npc.waypoints = ()
    npc.waypoints_cnt = 0
    npc.current_waypoint_no = 0
    npc.acc = vec(0, 0)
    # npc.vel = vec(0, 0)
    if npc.model.attitude == AttitudeEnum.enemy:
        npc.speed = npc.speed_walk

    return


###############################################################################################################
def find_path(npc: "NPC") -> None:
    start = (npc.tileset_coord.y, npc.tileset_coord.x)
    target = npc.get_tileset_coord(npc.target)
    goal = (target.y, target.x)
    # A destination is a marker, not a promise that the tile under it is floor.
    # Every named place an author puts on the map lands on something solid -
    # the tavern, a market stall, a doorway - and A* will not enter a blocked
    # tile, so the search fails outright and the branch below freezes the
    # character where it stands. Aim at the closest tile it *can* reach
    # instead; "walk up to the door" is what was meant anyway.
    if walkable := nearest_walkable(npc.scene.path_finding_grid, goal):
        goal = walkable
    # fps = f"FPS:\t{npc.game.fps: 6.1f}\t3s:\t{npc.game.avg_fps_3s: 6.1f}
    # \t10s:\t{npc.game.avg_fps_10s: 6.1f}\ttime:\t{npc.game.time_elapsed:4.1f}"
    if path := a_star_cached(start=start, goal=goal, grid=npc.scene.path_finding_grid):
        npc.generate_waypoints_from_path(path, start)
    else:
        print(f"[red]ERROR![/] Path not found for npc '{npc.name}'!")
        # npc.scene.add_notification(
        #     f"Path not found for npc '[char]{npc.name}[/char]'", NotificationTypeEnum.debug)
        npc.waypoints = ()
        npc.waypoints_cnt = 0
        npc.acc = vec(0, 0)
        npc.vel = vec(0, 0)
        npc.target = vec(0, 0)

    npc.current_waypoint_no = 0


###############################################################################################################
def generate_waypoints_from_path(npc: "NPC", path: list[tuple[int, int]], start: tuple[int, int]) -> None:
    waypoints = []
    path_list = list(path)
    # if first waypoint is the same map grid, than skip it
    # hack to prevent NPC jitter (coming back to center of current grid, than to next,
    # but then path is recalculated and goes back to current grid center)
    start_index = 1 if len(path_list) >= 2 and path_list[0] == start else 0
    # when following Player, stop 1 step before
    # for waypoint in path_list[start_index:-1]:
    for waypoint in path_list[start_index:]:
        y, x = waypoint
        p = Point(x * TILE_SIZE + TILE_SIZE // 2, y * TILE_SIZE + TILE_SIZE // 2)
        waypoints.append(p)
    npc.waypoints_cnt = len(waypoints)
    npc.waypoints = tuple(waypoints)


###############################################################################################################
def jump(npc: "NPC") -> None:
    npc.is_jumping = True
    npc.up_acc = npc.up_force
    # npc.up_vel = 50
    npc.jumping_offset = 1


###############################################################################################################
def physics(npc: "NPC", dt: float) -> None:
    if npc.is_stunned or npc.is_attacking:
        npc.adjust_rect()
        return

    npc.prev_pos = npc.pos.copy()

    # `acc` is the steering force *for this frame*, written by whoever drives
    # this character just before physics runs: input in `Player.movement`,
    # `follow_waypoints` for everyone else. Friction is a force too, but it
    # must be applied to a copy, never folded back into the member.
    #
    # It used to be `npc.acc.x += npc.vel.x * npc.friction`, and because
    # `acc` survives the frame, that fed friction back into itself. As long as
    # a controller kept overwriting `acc` every frame it was harmless - which
    # is why walking looked fine. The moment nobody wrote `acc` any more (the
    # character arrived, `clear_waypoints` zeroed it, `follow_waypoints` then
    # returned early on `waypoints_cnt <= 0`) the two lines became a closed
    # loop: acc' = acc + f*v, v' = v + acc'*dt. That is a harmonic oscillator
    # with |eigenvalue| == 1.0 exactly - undamped, so it never decays. Period
    # 13.9 frames (0.23 s at 60 FPS), amplitude ~2.4 px: the character
    # shivering between two positions on the spot, forever.
    #
    # The player was immune only by accident: its input code assigns
    # `npc.acc.x = 0` on the frames no key is held, which breaks the loop.
    acc_x = npc.acc.x + npc.vel.x * npc.friction
    npc.vel.x += acc_x * dt

    acc_y = npc.acc.y + npc.vel.y * npc.friction
    npc.vel.y += acc_y * dt

    if 0 <= npc.tileset_coord.y < len(npc.scene.path_finding_grid) and \
            0 <= npc.tileset_coord.x < len(npc.scene.path_finding_grid[0]):
        step_cost = abs(npc.scene.path_finding_grid[npc.tileset_coord.y][npc.tileset_coord.x]) or 1
    else:
        step_cost = 1
    speed = (npc.speed * (100 / step_cost))

    if npc.vel.magnitude() >= speed:
        if speed > 0:
            npc.vel = npc.vel.normalize() * speed

    if speed == 0:
        npc.acc = vec(0, 0)
        npc.vel = vec(0, 0)

    if npc.is_flying:
        oscillation = 1 if npc.scene.game.time_elapsed % 0.25 < 0.125 else 0
        npc.jumping_offset = TILE_SIZE + oscillation
    else:
        if not npc.is_jumping:
            npc.jumping_offset = 0

    if npc.is_jumping:
        npc.up_acc += npc.up_vel * npc.up_friction
        npc.up_vel += npc.up_acc * dt
        # + (npc.up_vel / 2) * dt
        npc.jumping_offset = int(npc.up_vel * dt)
        if npc.jumping_offset <= 0:
            npc.is_jumping = False
            npc.up_acc = 0.0
            npc.up_vel = 0.0
            npc.jumping_offset = 0

            # TODO not a good place to do it
            npc.scene.group.change_layer(npc, npc.scene.sprites_layer)

    npc.pos.x += npc.vel.x * dt + (npc.vel.x / 2) * dt
    npc.pos.y += npc.vel.y * dt + (npc.vel.y / 2) * dt

    # The steering force is spent. A controller that stops writing `acc` means
    # "I am not pushing any more", which has to leave the character coasting to
    # a stop under friction - not still leaning on last frame's force. Every
    # controller writes `acc` in `movement()`, immediately before this runs, so
    # nothing is lost by clearing it here.
    npc.acc.update(0, 0)

    npc.adjust_rect()


###############################################################################################################
def set_entry_point(npc: "NPC", entry_point: str, default: vec) -> bool:
    if entry_point in npc.scene.entry_points:
        result: bool = True
        # set first start position for the Player
        ep = npc.scene.entry_points[entry_point]
        npc.pos = vec(ep.x, ep.y)
        npc.adjust_rect()
    else:
        result = False
        # Komunikat MUSI nazywać brakujący punkt i te, które mapa zna. Bez tego
        # jedyny ślad po awarii to bohater postawiony na pozycji awaryjnej -
        # a gracz widzi tylko, że stoi w lesie i nie może się ruszyć.
        known = ", ".join(sorted(npc.scene.entry_points)) or "brak"
        print(f"\n[red]ERROR![/] [char]{npc.model.name_EN}[/] entry point "
              f"'{entry_point}' nie istnieje na mapie '{npc.scene.current_map}' "
              f"(mapa zna: {known})\n")
        npc.pos = default
        npc.adjust_rect()

    return result


###############################################################################################################
def check_scene_exit(npc: "NPC") -> None:
    # Routine NPCs move between maps through the schedule's transit system, not by
    # stepping onto an exit collider. This guard is not an optimisation: the
    # presence reconciler materialises an arriving NPC *on* the doorway, so
    # without it the character would die() on the very next frame. Everyone else
    # keeps the legacy "walk into an exit and leave" behaviour (unused today).
    if npc.runtime.routine_key:
        return

    for exit in npc.scene.exit_sprites:
        if npc.feet.colliderect(exit.rect):
            npc.current_map = exit.to_map
            # npc.set_entry_point(exit.entry_point, vec(0, 0))
            # npc.scene.NPCs.remove(npc)
            # npc.scene.group.remove(npc)
            # npc.shadow.kill()
            # npc.health_bar.kill()
            # npc.emote.kill()
            npc.die(drop_items=False)
            # TODO NPC goes to another map


###############################################################################################################
def get_random_pos(npc: "NPC", x_tiles: float = 1.0, y_tiles: float = 1.0) -> vec:
    x = -x_tiles + random.random() * 2.0 * x_tiles
    y = -y_tiles + random.random() * 2.0 * y_tiles

    return vec(x * TILE_SIZE, y * TILE_SIZE)


###############################################################################################################
def slide(npc: "NPC", colliders: list[Any]) -> None:
    move_vec = npc.pos - npc.prev_pos
    # can't move by full vector,
    # first try move ony in one axis (reset the movement along the other axis to zero)

    # slide along y axis
    npc.pos.x -= move_vec.x
    npc.adjust_rect()
    if npc.feet.collidelist(colliders) == -1:
        # looks ok, so set prev pos
        npc.prev_pos = npc.pos.copy()
        return

    # slide along x axis
    npc.pos.x += move_vec.x
    npc.pos.y -= move_vec.y
    npc.adjust_rect()
    if npc.feet.collidelist(colliders) == -1:
        # looks ok, so set prev pos
        npc.prev_pos = npc.pos.copy()
        return

    # slide is not possible, block movement
    npc.move_back()


###############################################################################################################
def move_back(npc: "NPC") -> None:
    """
    If called after an update, the sprite can move back

    """
    # npc.debug([f"{npc.rect.topleft=}", f"{npc.old_rect.topleft=}"])
    npc.pos = npc.prev_pos.copy()
    if npc.config_key == PLAYER_CONFIG_KEY:  # and npc.scene.camera.target == npc.prev_pos:
        npc.scene.camera.target = npc.pos

    npc.adjust_rect()
