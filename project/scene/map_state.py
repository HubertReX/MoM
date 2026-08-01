"""Stan map: lista właściwości per-mapa, cache ``loaded_maps`` i przejścia między mapami.

Moduł systemu wg B01 (D1): bezstanowe funkcje operujące na przekazanej scenie.

Kontrakt K1: ``MAP_PROPERTIES`` to dokładnie ta lista nazw atrybutów, którą
zapis gry przechowuje per mapa - kolejność i zawartość są częścią formatu save
(``Scene.properties`` dostaje jej kopię w ``__init__``). Nie zmieniać bez migracji.
"""
from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING, Any

from maze_generator.maze_utils import clear_maze_cache

import audio
import settings
from settings import _, MOM_PROFILE, QUICK_SAVE_SLOT
from objects import NotificationTypeEnum

from scene import map_loader, world_clock

if TYPE_CHECKING:
    from scene.scene import Scene


#: Atrybuty ``Scene`` trzymane osobno dla każdej mapy (kontrakt K1 - format save).
MAP_PROPERTIES: list[str] = [
    "is_maze",
    "maze_stats",
    "maze_cols",
    "maze_rows",
    # a maze level is reproduced from its seed alone, so both the seed and
    # the grid it produced belong to the per-map cache
    "maze_seed",
    "maze",
    # where this map's exit leads back to - per map, like everything else here
    "return_map",
    "return_entry_point",
    "waypoints",
    # named destinations for daily routines - per map, like `waypoints`
    "places",
    "items",
    "zones",
    "exits",
    "chests",
    "walls",
    # both are per-map: `destructibles` used to leak across maps (walls were
    # restored from the cache, the destructible sprites were not), and
    # `destroyed_walls` is what the save reads to know which bushes/rocks
    # the player already smashed on a map they are not standing on
    "destructibles",
    "destroyed_walls",
    # per-map for the same reason as `destroyed_walls`: a killed monster
    # leaves nothing behind on the map to read the fact off
    "dead_monsters",
    "label_sprites",
    "shadow_sprites",
    "obstacles_sprites",
    "exit_sprites",
    "item_sprites",
    "animations",
    "NPCs",
    "loaded_NPCs",
    "outdoor",
    "layers",
    "path_finding_grid",
    "entry_points",
    "map_view",
    "sprites_layer",
    "group",
    "particles",
    "weather",
]


def store_map(scene: "Scene") -> None:
    map: dict[str, Any] = {}
    for property in scene.properties:
        # if hasattr(scene, property):
        map[property] = getattr(scene, property)
    scene.loaded_maps[scene.current_map] = map


def restore_map(scene: "Scene") -> None:
    map = scene.loaded_maps[scene.current_map]
    for property in map:
        setattr(scene, property, map[property])

    # check from which scene we came here
    if len(scene.game.states) > 0:
        scene.prev_state = scene.game.states[-1]

    clear_maze_cache()

    scene.set_camera_on_player()
    scene.group.center(scene.camera.target)
    # scene.group.center(scene.player.pos)


class _MapChangeProfile:
    """Rozbicie kosztu `go_to_map` na podkroki - budowane tylko pod `MOM_PROFILE`.

    Zmiana mapy to jedna bardzo droga klatka, więc w zwykłym oknie profilera ginie
    jako pojedynczy odstający pomiar w `update` (podnosi `avg`, nie rusza `p95`).
    Ta linia mówi wprost, który podkrok zjadł czas. Kilka `perf_counter` raz na
    przejście, więc koszt jest bez znaczenia - ale i tak siedzi za flagą.
    """

    def __init__(self) -> None:
        self._t0 = perf_counter()
        self._last = self._t0
        self._parts: list[str] = []

    def mark(self, label: str) -> None:
        now = perf_counter()
        self._parts.append(f"{label}={(now - self._last) * 1000:.1f}ms")
        self._last = now

    def line(self, target: str, cached: bool) -> str:
        total = (perf_counter() - self._t0) * 1000
        kind = "cached" if cached else "first_load"
        return (f"profile: map_change -> {target} ({kind}) total={total:6.1f}ms "
                + " ".join(self._parts))


def go_to_map(scene: "Scene") -> None:
    if not scene.new_scene:
        return

    prof = _MapChangeProfile() if MOM_PROFILE else None

    # cancel the leaving map's armed spawn timers so they don't keep firing for
    # emitters that are about to be swapped out (each map keeps its own director)
    if scene.weather:
        scene.weather.stop_all()
    if prof:
        prof.mark("weather_stop")

    scene.return_map = scene.current_map
    scene.return_entry_point = scene.new_scene.return_entry_point

    scene.current_map = scene.new_scene.to_map
    # print(f"{scene.entry_point=} {scene.new_scene.entry_point}")
    scene.entry_point = scene.new_scene.entry_point
    scene.is_maze = scene.new_scene.is_maze
    scene.maze_cols = scene.new_scene.maze_cols
    scene.maze_rows = scene.new_scene.maze_rows
    # The seed belongs to the level we are leaving. Clearing it lets
    # `_resolve_maze_seed` decide for the level we are entering: reproduce the
    # one waiting in `pending_map_states`, or roll a fresh one. A cached level
    # gets its seed back from `restore_map` (it is in `properties`).
    scene.maze_seed = None

    cached = scene.current_map in scene.loaded_maps
    if not cached:
        reset_sprite_groups(scene)
        scene.player.shadow = scene.player.create_shadow()
        scene.player.emote = scene.player.create_emote()
        scene.player.health_bar = scene.player.create_health_bar()
        if prof:
            prof.mark("reset+player")
        scene.load_map()
        if prof:
            prof.mark("load_map")
    else:
        reset_sprite_groups(scene)

        restore_map(scene)
        map_loader.set_entry_point(scene)
        if prof:
            prof.mark("restore_map")

        scene.player.shadow = scene.player.create_shadow()
        scene.player.emote = scene.player.create_emote()
        scene.player.health_bar = scene.player.create_health_bar()

        scene.game.unregister_custom_events()
        map_loader.populate_sprite_groups(scene)
        if prof:
            prof.mark("populate_groups")

    if settings.USE_PARTICLES:
        scene.start_particles()
    if prof:
        prof.mark("particles")

    play_map_music(scene)
    if scene.is_maze:
        # zejście do lochu ma być słyszalne osobno od podmiany muzyki
        audio.play_sfx("maze_door")
    if prof:
        prof.mark("audio")

    # Quest event: arriving somewhere can satisfy a quest. Nothing uses
    # location conditions yet (`at_location()` is still hypothetical - see
    # Q01_S07 in the plan), but the hook is where it will need to be, and
    # firing it now keeps the sweep quiet when it lands.
    scene.quests.on_event("map_change")
    if prof:
        prof.mark("quests")

    # Autosave only when entering a maze (entry point into a dungeon). Regular
    # room-to-room transitions are not autosaved. The toast lets the player know
    # the quick save slot was silently overwritten.
    if (scene.is_maze
            and hasattr(scene.game, "save_manager")
            and scene.game.save_manager.save(QUICK_SAVE_SLOT)):
        scene.add_notification(_("notify.autosaved_quick"), NotificationTypeEnum.info)

    scene.transition.exiting = False

    if prof:
        prof.mark("autosave")
        scene.game.log(prof.line(scene.current_map, cached))


def play_map_music(scene: "Scene") -> None:
    """Podłóż muzykę pasującą do mapy, na której właśnie stoimy.

    Labirynt gra swój klucz `maze` niezależnie od nazwy wygenerowanej mapy - to
    ta sama jaskinia, choćby poziom nazywał się inaczej. Mapa bez wpisu w
    `audio.toml` to cisza, nie błąd (patrz nagłówek manifestu).
    """
    audio.play_music("maze" if scene.is_maze else scene.current_map)


def reload_map(scene: "Scene") -> None:
    scene.game.time_elapsed = 0.0
    world_clock.reset(scene)
    scene.display_ui_flag = True
    scene.cutscene_framing = 0.0

    # shadow = scene.player.shadow
    reset_sprite_groups(scene)
    # scene.map_view.reload()
    scene.player.reset()
    # stop the old director's timers before load_map() rebuilds the emitters
    if scene.weather:
        scene.weather.stop_all()
    scene.load_map()
    if settings.USE_PARTICLES:
        scene.start_particles()
    play_map_music(scene)


def reset_sprite_groups(scene: "Scene") -> None:
    scene.label_sprites.empty()
    scene.exit_sprites.empty()
    scene.item_sprites.empty()
    scene.obstacles_sprites.empty()
    scene.shadow_sprites.empty()
    scene.group.empty()
