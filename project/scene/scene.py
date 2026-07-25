import random
from typing import Any, cast
from rich import print
import game
import pygame
import pyscroll
import pyscroll.data
from animation import animator
from camera import Camera
from maze_generator.maze import Maze
from maze_generator.maze_utils import (
    MARGIN,
    SUBTILE_COLS,
    SUBTILE_ROWS,
    TILE_SIZE,
    clear_maze_cache,
    get_gid_from_tmx_id,
    nearest_walkable,
    timeit
)
from objects import (ChestSprite, Collider, DestructibleSprite, ItemSprite, Notification, NotificationTypeEnum)
from particles import ParticleSystem, WeatherDirector
from pyscroll.group import PyscrollGroup
from pytmx import TiledMap
from config_model.config import RaceEnum
from quest.entities import QuestState
from quest.runtime import QuestRuntime
import settings
from settings import (
    _,
    # ACTIONS,
    # BG_COLOR,
    # CIRCLE_GRADIENT,
    BG_COLOR,
    CIRCLE_RADIUS,
    CUTSCENE_BG_COLOR,
    DAY_FILTER,
    FILTER_SCALE,
    FONT_SIZE_MEDIUM,
    FULL_WHITE_COLOR,
    GEMS_SHEET_DEFINITION,
    GEMS_SHEET_FILE,
    INVENTORY_ITEM_SCALE,
    IS_WEB,
    ITEMS_DIR,
    ITEMS_SHEET_DEFINITION,
    ITEMS_SHEET_FILE,
    MAX_HOTBAR_ITEMS,
    MONSTER_WAKE_DISTANCE,
    NIGHT_FILTER,
    NOTIFICATION_DURATION,
    NOTIFICATION_STAGGER,
    # PANEL_BG_COLOR,
    EMITTER_SCHEDULES,
    PARTICLES,
    QUICK_SAVE_SLOT,
    ROUTINES_FILE,
    SHADERS_NAMES,
    SHOW_DEBUG_INFO,
    SHOW_UI,
    TEXT_ROW_SPACING,
    TRANSPARENT_COLOR,
    USE_ALPHA_FILTER,
    USE_PARTICLES,
    USE_SHADERS,
    WAYPOINTS_LINE_COLOR,
    ZOOM_LEVEL,
    ZOOM_WIDE,
    # ColorValue,
    Point,
    to_vector,
    tuple_to_vector,
    # to_vector,
    # tuple_to_vector,
    vec,
    vec3,
    vector_to_tuple
)
from scene import collisions, map_loader, player_actions, world_clock
from state import State
from transition import Transition, TransitionCircle
from ui import icons as ui_icons
from ui.game_ui import GameUI
from ui.panels.hud import NOTIFICATION_TYPE_ICONS
from npc_schedule import (
    Routines,
    current_slot,
    destinations_of,
    load_routines,
    resolve_at,
    roster_origin_map,
    routine_roster_keys,
    slot_jitter,
    slot_target_map,
    step_logical_map,
)

#: `current_map` value for a routine NPC that has walked through the door and is
#: between two maps (or is travelling off-screen). It matches no map name, so the
#: presence filter keeps it off both rosters until the arrival timer lands it.
_NOWHERE = "\x00transit"

#: Safety arrival time (game-minutes) for a *visible* departure, in case the
#: character never reaches its door - a blocked path, mostly. Normally the arrival
#: is (re)set to `transit_minutes` from the moment it walks through the door, so
#: this large value is only a floor that stops a stuck traveller vanishing forever.
_DEPARTURE_FALLBACK_MIN = 240
from world_rng import new_world_seed


################################################################################################################
# MARK: Scene


class Scene(State):
    def __init__(
            self,
            game: game.Game,
            map_name: str,
            entry_point: str,
            is_maze: bool = False,
            maze_cols: int = 0,
            maze_rows: int = 0,
            maze_seed: int | None = None,
            return_map: str = "",
            return_entry_point: str = "",
    ) -> None:

        super().__init__(game)
        self.properties: list[str] = [
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

        self.notifications: list[Notification] = []
        self.game.time_elapsed = 0.0
        self.current_map = map_name
        self.loaded_maps: dict[str, Any] = {}
        # Saved state for maps the player visited before saving but has not
        # re-entered since loading. Their NPCs/chests do not exist yet, so the
        # state cannot be applied at load time; `load_map` applies each entry
        # when its map is actually built. Deliberately NOT in `self.properties`:
        # this is global, not per-map, and must survive `store_map`/`restore_map`.
        self.pending_map_states: dict[str, Any] = {}
        # Quest progress (decision D13). Global, not per-map, so it stays out of
        # `self.properties`. A new game starts with nothing done; loading a save
        # replaces this wholesale (see SaveManager._apply_quest_state).
        self.quest_state: QuestState = QuestState()
        self.entry_point = entry_point
        self.new_scene: Collider | None = None
        self.is_maze = is_maze
        self.maze_stats: dict[str, Any] = {}
        self.maze_cols = maze_cols
        self.maze_rows = maze_rows
        # Seed of the current maze level, and the generator driven by it. Every
        # random decision that shapes a maze - the grid, the decors, where the
        # chests and monsters stand, which monster model each one gets - is drawn
        # from `maze_rng`, so the save file needs to store nothing but this int to
        # bring the whole level back. `None` means "not generated yet"; a value
        # handed to the constructor means "reproduce this one" (loading a save).
        self.maze_seed: int | None = maze_seed
        self.maze_rng: random.Random = random.Random(maze_seed)
        self.maze: Maze | None = None
        # Where the exit of a level-1 maze leads back to. Normally filled in by
        # `go_to_map` when the player walks in; passed to the constructor when a
        # save drops the player straight into a dungeon. Without it,
        # `build_tileset_map_from_maze` raised AttributeError on a directly
        # constructed maze scene.
        self.return_map: str = return_map
        self.return_entry_point: str = return_entry_point
        self.waypoints: dict[str, tuple[Point, ...]] = {}
        # Named points from the `places` layer - the destinations a daily routine
        # can name. Per-map, like `waypoints`, hence in `self.properties`.
        self.places: dict[str, vec] = {}
        # Parsed routines.toml. Global (the rhythm of a day is not per-map) and
        # read once per scene; an unreadable file yields empty routines and the
        # game behaves exactly as it did before routines existed.
        self.routines: Routines = load_routines(ROUTINES_FILE, warn=print)
        # roster rutyn budowany raz, przy pierwszej mapie hubowej (map_loader.load_map)
        self._roster_loaded: bool = False
        self.items: list[ItemSprite] = []
        # self.items_defs: dict[str, pygame.Surface] = {}
        self.exits: list[Collider] = []
        self.zones: dict[str, list[pygame.Rect]] = {}
        self.chests: list[ChestSprite] = []
        self.destructibles: list[DestructibleSprite] = []
        self.walls: list[pygame.Rect] = []
        # top-left pixel coords of every destructible destroyed on the current map.
        # Recorded as it happens rather than diffed against a snapshot of `walls`
        # taken at save time - the snapshot was captured lazily on the first save,
        # so everything destroyed before that first save was invisible to it.
        self.destroyed_walls: list[tuple[int, int]] = []
        # `Player.attack_time` of the swing that already raised a "weapon too weak"
        # toast, so one bounced-off hit does not spam a toast per frame
        self._weak_hit_notified_at: float = -1.0
        # Names of monsters killed on the current map. Needed for the same reason as
        # `destroyed_walls`: `NPC.die()` drops the sprite from `self.NPCs`, so once it
        # is gone nothing on the map says it ever existed. Without this list a save
        # made after a load would report an empty kill list and resurrect everything.
        self.dead_monsters: list[str] = []

        self.label_sprites: pygame.sprite.Group = pygame.sprite.Group()
        self.shadow_sprites: pygame.sprite.Group = pygame.sprite.Group()
        self.obstacles_sprites: pygame.sprite.Group = pygame.sprite.Group()
        self.exit_sprites: pygame.sprite.Group = pygame.sprite.Group()
        self.item_sprites: pygame.sprite.Group = pygame.sprite.Group()
        self.animations: pygame.sprite.Group = pygame.sprite.Group()

        # self.transition = Transition(self)
        self.transition = TransitionCircle(self)

        # one shared atlas for the whole run (see ui/icons.py) - menus need the same
        # keycaps as the scene, and rebuilding it per scene only duplicated surfaces
        self.icons: dict[str, list[pygame.Surface]] = ui_icons.get_icons(self.game)
        # self.import_emote_sheet(str(EMOTE_SHEET_FILE))
        self.items_sheet: dict[str, list[pygame.Surface]] = self.import_sheet(
            str(ITEMS_SHEET_FILE), ITEMS_SHEET_DEFINITION, width=16, height=16)

        self.items_sheet.update(self.import_sheet(
            str(GEMS_SHEET_FILE), GEMS_SHEET_DEFINITION, width=16, height=16))

        # moved here to avoid circular imports
        from characters import Player
        self.player: Player = Player(
            self.game,
            self,
            self.shadow_sprites,
            self.label_sprites,
            (settings.WIDTH // 2, settings.HEIGHT // 2),
            name="Malachi",
            model_name="Player",
            emotes=self.icons,
        )
        # moved here to avoid circular imports
        from characters import NPC

        self.NPCs: list[NPC] = []
        self.loaded_NPCs: dict[str, NPC] = {}
        # pyscroll renderer (camera)
        self.map_view: pyscroll.BufferedRenderer
        # view target for camera
        self.camera = Camera(self)
        # self.camera.target = vec(1 * TILE_SIZE, 1 * TILE_SIZE)
        # self.camera.zoom   = ZOOM_LEVEL
        # self.map_view.zoom = self.camera.zoom

        # percentage of black bars shown during cutscene
        self.cutscene_framing: float = 0.0
        # it's high noon
        self.day: int = settings.INITIAL_DAY
        self.hour: int = settings.INITIAL_HOUR
        self.minute: int = 0
        self.minute_f: float = 0.0
        # Identity of this playthrough, rolled once and then carried in the save.
        # Everything the world re-rolls by itself draws from `day_rng(name)`, which
        # is derived from this plus the day - see world_rng.py for why that is not
        # optional. Global, not per-map, so it stays out of `self.properties`.
        self.world_seed: int = new_world_seed()
        # are we outdoors? shell there be night and day cycle?
        self.outdoor: bool = False
        self.filter_surf = pygame.Surface((settings.WIDTH // FILTER_SCALE, settings.HEIGHT // FILTER_SCALE),
                                          pygame.SRCALPHA)  # .convert(self.game.canvas)

        self.b_and_w_circle = pygame.Surface((2 * CIRCLE_RADIUS, 2 * CIRCLE_RADIUS),
                                             pygame.SRCALPHA)  # .convert(self.game.canvas)
        self.b_and_w_circle.fill(FULL_WHITE_COLOR)
        pygame.draw.circle(self.b_and_w_circle, DAY_FILTER, (CIRCLE_RADIUS, CIRCLE_RADIUS), CIRCLE_RADIUS)
        # self.day_filter = pygame.Surface((2 * CIRCLE_RADIUS, 2 * CIRCLE_RADIUS), pygame.SRCALPHA)
        # self.day_filter.fill(DAY_FILTER)
        self.layers: list[str] = []
        self.path_finding_grid: list[list[int]] = []
        self.entry_points: dict[str, vec] = {}
        self.sprites_layer: int = 0
        self.group: PyscrollGroup
        self.particles: list[ParticleSystem] = []
        # weather scheduler (episodic emitters); built per-map in load_particles()
        self.weather: WeatherDirector | None = None
        # self.circle_gradient: pygame.Surface = (CIRCLE_GRADIENT).convert_alpha()
        self.ui = GameUI(self)
        self.display_ui_flag: bool = SHOW_UI
        # Quest runtime (Q-07). Construction only reads config and keeps a Scene
        # reference, so it is safe here, before the map exists; nothing is
        # evaluated until the first event or sweep.
        self.quests = QuestRuntime(self)
        # self.load_items_def()
        self.load_map()
        if USE_PARTICLES:
            self.start_particles()
        # self.start_particles()
        # self.set_camera_on_player()

    #############################################################################################################

    def note_monster_death(self, name: str) -> None:
        """Record a kill on the current map, called from :meth:`NPC.die`.

        The sprite is gone by the time a save runs, so this list is the only
        durable evidence of it - see ``self.dead_monsters``.
        """
        if name and name not in self.dead_monsters:
            self.dead_monsters.append(name)

    #############################################################################################################

    def add_notification(self, text: str, type: NotificationTypeEnum = NotificationTypeEnum.info,
                         emote_key: str = "") -> None:
        # message is raw markup; the HUD renders and caches it via the new RichText engine.
        # A supplied emote (the chosen dialog option's sentiment) leads the message inline,
        # at the text's own height — replacing the generic type icon. It is NOT also drawn as
        # a separate overlay (that produced a second, mis-aligned copy of the emote).
        icon = emote_key or NOTIFICATION_TYPE_ICONS[type]
        message = f":{icon}: {text}"
        now = self.game.time_elapsed

        # Queue rather than pile up: several toasts raised in one frame used to
        # share a single window, and the player got ~5 s to read all of them.
        # Each new one waits out the previous one's head start; because the
        # lifetime runs from show_time, waiting costs it nothing.
        last_shown = max((n.show_time for n in self.notifications), default=now - NOTIFICATION_STAGGER)
        show_time = max(now, last_shown + NOTIFICATION_STAGGER)

        # emote_key baked into the message above; no separate overlay (field kept empty)
        notification = Notification(type, message, "", 0, 0, now, "", show_time)
        self.notifications.append(notification)

    #############################################################################################################
    def visible_notifications(self) -> list[Notification]:
        """The ones whose turn has come. The rest are queued, not lost."""
        return [n for n in self.notifications if n.show_time <= self.game.time_elapsed]

    #############################################################################################################
    def remove_old_notifications(self) -> None:
        # a queued toast has not been seen yet, so it cannot be old
        self.notifications = [n for n in self.notifications
                              if n.show_time + NOTIFICATION_DURATION > self.game.time_elapsed]

    #############################################################################################################
    def create_item(self, name: str, x: int, y: int, show: bool = True) -> ItemSprite:
        # delegat do systemu map_loader (B01 krok 2) - patrz doc/refactor-rdzenia-B01.md
        return map_loader.create_item(self, name, x, y, show)

    #############################################################################################################

    def load_map(self) -> None:
        # delegat do systemu map_loader (B01 krok 2)
        map_loader.load_map(self)

    #############################################################################################################

    def _particle_rng(self) -> "random.Random | None":
        """Seeded generator for particles/weather, or ``None`` for the live world.

        Under ``MOM_TEST_DETERMINISTIC=1`` every emitter and the director draw from a
        generator seeded with ``settings.TEST_WORLD_SEED``, so two runs of a scenario
        produce the same sequence of weather decisions. Particles are NOT switched off:
        a test would then be looking at a different game than the player's, and a
        scenario may want to check the emitter itself.
        """
        if settings.TEST_WORLD_SEED is None:
            return None
        return random.Random(settings.TEST_WORLD_SEED)

    def load_particles(self, tileset_map: TiledMap) -> None:
        map_particles = tileset_map.properties.get("particles", "").replace(" ", "").strip().lower().split(",")
        # string with coma separated names of particle systems active in this map
        self.particles = []
        # name -> system, used to hand the schedulable emitters to the WeatherDirector
        weather_systems: dict[str, ParticleSystem] = {}
        # init particle systems relevant for this scene
        for particle in map_particles:
            if particle in PARTICLES:
                particle_class = PARTICLES[particle]
                system = particle_class(self.game.canvas, self.group, self.camera,
                                        rng=self._particle_rng())
                self.particles.append(system)
                weather_systems[particle] = system

        # WeatherDirector turns the map's allowed emitters into random, mutually-exclusive
        # episodes (see EMITTER_SCHEDULES); only emitters with a schedule are scheduled
        self.weather = WeatherDirector(weather_systems, EMITTER_SCHEDULES, rng=self._particle_rng())

    #############################################################################################################

    def start_particles(self) -> None:
        for particle in self.particles:
            # self.game.unregister_custom_event()
            self.game.register_custom_event(particle.custom_event_id, particle.add)

    #############################################################################################################
    def on_suspend(self) -> None:
        # a menu/dialog is now on top: Scene.draw() (which ages particles via emit)
        # stops running, so disarm the weather emitters. Otherwise their spawn timers
        # keep firing (get_inputs runs every frame) and pile up a backlog that bursts
        # all at once when we return to the scene.
        if self.weather:
            self.weather.pause()

    #############################################################################################################
    def on_resume(self) -> None:
        # re-arm the weather emitters once the scene is active again - but not while a
        # hard pause (P / focus loss) is still in effect (that path re-arms on unpause)
        if self.weather and not self.game.is_paused:
            self.weather.resume()

    #############################################################################################################

    def store_map(self) -> None:
        map: dict[str, Any] = {}
        for property in self.properties:
            # if hasattr(self, property):
            map[property] = getattr(self, property)
        self.loaded_maps[self.current_map] = map

    #############################################################################################################

    def restore_map(self) -> None:
        map = self.loaded_maps[self.current_map]
        for property in map:
            setattr(self, property, map[property])

        # check from which scene we came here
        if len(self.game.states) > 0:
            self.prev_state = self.game.states[-1]

        clear_maze_cache()

        self.set_camera_on_player()
        self.group.center(self.camera.target)
        # self.group.center(self.player.pos)

    #############################################################################################################
    # MARK: agent test helpers (deterministic navigation)

    def agent_find_entity(self, key: str) -> "Any | None":
        """Return the NPC / item / chest whose key matches ``key`` (case-insensitive).

        Deterministic-test helper. Matches on the map-object name (``loaded_NPCs``
        key / sprite ``name``) or the entity's bilingual display name, and accepts a
        prefix so ``barman`` finds ``Barman_Absyntnent``. NPCs are searched first,
        then items, then chests.
        """
        k = key.strip().lower()

        def _matches(ent: "Any") -> bool:
            names = [str(getattr(ent, "name", "")).lower()]
            model = getattr(ent, "model", None)
            if model is not None:
                names += [str(getattr(model, "name_EN", "")).lower(),
                          str(getattr(model, "name_PL", "")).lower()]
            names = [n for n in names if n]
            return any(n == k or n.startswith(k) or k in n for n in names)

        for name, npc in self.loaded_NPCs.items():
            if name.lower() == k or name.lower().startswith(k) or _matches(npc):
                return npc
        # flattened rather than a tuple of the two lists: `list` is invariant, so
        # `(self.items, self.chests)` joins to plain `object` and stops being iterable
        # as far as the type checker is concerned
        for ent in [*self.items, *self.chests]:
            if _matches(ent):
                return ent
        return None

    def agent_walk_target(self, key: str) -> "vec | None":
        """Walkable world point next to entity ``key`` that the player can reach.

        Returns the centre of a walkable tile adjacent (8-neighbourhood) to the
        entity and reachable from the player via A*, or ``None`` if the entity is
        unknown or has no reachable adjacent tile ("brak ścieżki").
        """
        ent = self.agent_find_entity(key)
        if ent is None:
            return None
        return self.agent_point_near(getattr(ent, "pos", None))

    def agent_point_near(self, pos: "vec | None") -> "vec | None":
        """Walkable, player-reachable world point next to world ``pos`` (or ``pos``
        itself if already free). ``None`` when nothing adjacent is reachable."""
        if pos is None:
            return None
        from maze_generator.maze_utils import a_star_cached

        grid = self.path_finding_grid
        rows, cols = len(grid), len(grid[0]) if grid else 0
        p_tile = self.player.get_tileset_coord()
        start = (p_tile.y, p_tile.x)
        col0 = int(pos.x // TILE_SIZE)
        row0 = int(pos.y // TILE_SIZE)
        # try the entity's own tile first, then the 8 neighbours (nearest first)
        offsets = [(0, 0), (0, -1), (0, 1), (-1, 0), (1, 0),
                   (-1, -1), (-1, 1), (1, -1), (1, 1)]
        for dr, dc in offsets:
            r, c = row0 + dr, col0 + dc
            if not (0 <= r < rows and 0 <= c < cols):
                continue
            if grid[r][c] > 0:                      # wall / not walkable
                continue
            if (r, c) != start and not a_star_cached(start=start, goal=(r, c), grid=grid):
                continue                            # unreachable from the player
            return vec(c * TILE_SIZE + TILE_SIZE // 2, r * TILE_SIZE + TILE_SIZE // 2)
        return None

    def agent_walk_player_to(self, point: "vec") -> bool:
        """Send the player walking to ``point`` via the normal A* path. Returns
        ``True`` if a path was found (movement started), ``False`` otherwise."""
        self.player.target = vec(point.x, point.y)
        self.player.find_path()
        started = self.player.waypoints_cnt > 0 or self.player.target == vec(0, 0)
        if not started:
            self.player.target = vec(0, 0)
        return started

    def agent_player_arrived(self) -> bool:
        """True when the player is no longer walking a queued path."""
        return self.player.target == vec(0, 0) and self.player.waypoints_cnt == 0

    def agent_open_dialog(self, key: str) -> bool:
        """Deterministically open ``key``'s dialog — no walking to a wandering NPC.

        NPCs random-walk, so ``walk_to_char`` + ``talk`` races the target. For a
        repeatable dialog screenshot this snaps the player next to the NPC and opens
        the panel through the game's own talk path (``npc_met`` + ``ui.open``).
        Returns ``True`` if a dialog panel was opened.
        """
        from settings import get_msg
        from ui.panels.dialog import DialogPanel

        npc = self.agent_find_entity(key)
        if npc is None or not getattr(npc, "has_dialog", False) or getattr(npc, "dialog", None) is None:
            return False
        # freeze the NPC where it stands so it can't wander off; do NOT move the
        # player (snapping onto item piles triggers auto-pickup churn).
        npc.target = vec(0, 0)
        npc.waypoints = ()
        npc.waypoints_cnt = 0
        self.player.npc_met = npc
        npc.npc_met = self.player
        text = get_msg(self.game.conf.messages, npc.dialog.text)
        self.ui.open(DialogPanel, npc=npc, text=text)
        self.player.is_talking = True
        npc.is_talking = True
        return True

    #############################################################################################################

    @staticmethod
    def import_sheet(
        sheet_path: str,
        sheet_definition: dict[str, list[tuple[int, int]]],
        width: int, height: int,
        scale: int = 1,
    ) -> dict[str, list[pygame.Surface]]:
        """
        Load sprite sheet and cut it into animation names and frames using EMOTE_SHEET_DEFINITION dict.
        """
        result: dict[str, list[pygame.Surface]] = {}
        img = pygame.image.load(sheet_path).convert_alpha()
        if scale != 1:
            img = pygame.transform.scale_by(img, scale)
        img_rect = img.get_rect()

        for key, definition in sheet_definition.items():
            anim = []
            for coord in definition:
                x, y = coord
                rec = pygame.Rect(x * width * scale, y * height * scale, width * scale, height * scale)
                if rec.colliderect(img_rect):
                    img_part = img.subsurface(rec)
                    anim.append(img_part)
                else:
                    print(
                        f"[red]ERROR![/] coordinate {x}x{y} "
                        f"not inside sprite sheet for '{key}' animation")
                    # self.add_notification(
                    #     f"[error]ERROR[/error]:red_exclamation: {self.current_map}: coordinate {
                    #         x}x{y} not inside sprite sheet for '{key}' animation",
                    #     NotificationTypeEnum.debug)
                    continue
            if anim:
                result[key] = anim

        return result

    #############################################################################################################

    def __repr__(self) -> str:
        # MARK: __repr__
        return f"{self.__class__.__name__}: {self.current_map}"

    #############################################################################################################
    def start_intro(self) -> None:
        # MARK: start_intro

        self.set_camera_free()
        # in_out_quad out_sine # in_out_elastic - anticipate and overshoot
        # in_out_back - anticipate # in_out_bounce - well, bouncy
        CAMERA_TRANSITION = "out_sine"

        waypoints = self.waypoints["intro"]

        self.intro_cutscene = {
            "steps": [
                # ########## INITIAL SETUP #######################
                {
                    "name": "step_01",
                    "description": "move camera the big tree",
                    "type": "animation",
                    "target": self.camera.target,
                    "args": {"x": waypoints[0].x,  "y": waypoints[0].y},
                    "duration": 0.1,
                    "transition": CAMERA_TRANSITION,
                    "from": "<root>",
                    "trigger": "<begin>"
                },
                {
                    "name": "step_01a",
                    "description": "night time",
                    "type": "animation",
                    "target": self,
                    "args": {"hour": 3},
                    "round_values": True,
                    "duration": 0.1,
                    "transition": "linear",
                    "from": "step_01",
                    "trigger": "on finish"
                },
                {
                    "name": "step_01b",
                    "description": "hide UI",
                    "type": "animation",
                    "target": self,
                    "args": {"display_ui_flag": 0},
                    "round_values": True,
                    "duration": 0.1,
                    "transition": "linear",
                    "from": "step_01",
                    "trigger": "on finish"
                },
                {
                    "name": "step_02",
                    "description": "show cutscene bars",
                    "type": "animation",
                    "target": self,
                    "args": {"cutscene_framing": 1.00},
                    "duration": 2.0,
                    "transition": "linear",
                    "from": "step_01",
                    "trigger": "on finish"
                },
                {
                    "name": "step_03",
                    "description": "camera zoom out",
                    "type": "animation",
                    "target": self.camera,
                    "args": {"zoom": ZOOM_WIDE},
                    "duration": 2.0,
                    "transition": "linear",
                    "from": "step_01",
                    "trigger": "on finish"
                },
                # ################# START #################
                {
                    "name": "step_04",
                    "description": "move camera to waypoint 1",
                    "type": "animation",
                    "target": self.camera.target,
                    "args": {"x": waypoints[1].x,  "y": waypoints[1].y},
                    "duration": 2.0,
                    "transition": CAMERA_TRANSITION,
                    "from": "step_03",
                    "trigger": "on finish"
                },
                {
                    "name": "step_05",
                    "description": "move camera to waypoint 3",
                    "type": "animation",
                    "target": self.camera.target,
                    "args": {"x": waypoints[3].x,  "y": waypoints[3].y},
                    "duration": 2.5,
                    "transition": CAMERA_TRANSITION,
                    "from": "step_04",
                    "trigger": "on finish"
                },
                {
                    "name": "step_05a",
                    "description": "move camera to waypoint 7",
                    "type": "animation",
                    "target": self.camera.target,
                    "args": {"x": waypoints[7].x,  "y": waypoints[7].y},
                    "duration": 2.5,
                    "transition": CAMERA_TRANSITION,
                    "from": "step_05",
                    "trigger": "on finish"
                },
                {
                    "name": "step_05b",
                    "description": "move camera to waypoint 10 (house)",
                    "type": "animation",
                    "target": self.camera.target,
                    "args": {"x": waypoints[10].x,  "y": waypoints[10].y},
                    "duration": 2.5,
                    "transition": CAMERA_TRANSITION,
                    "from": "step_05a",
                    "trigger": "on finish"
                },
                {
                    "name": "step_06",
                    "description": "camera zoom in on village house",
                    "type": "animation",
                    "target": self.camera,
                    "args": {"zoom": ZOOM_LEVEL},
                    "duration": 3.0,
                    "transition": "linear",
                    "from": "step_05b",
                    "trigger": "on finish"
                },
                {
                    "name": "step_07",
                    "description": "steady take",
                    "type": "animation",
                    "target": self.camera.target,
                    "args": {"x": self.camera.target.x,  "y": self.camera.target.y},
                    "duration": 1.0,
                    "transition": CAMERA_TRANSITION,
                    "from": "step_06",
                    "trigger": "on finish"
                },
                # ############# CLEAN UP ############################
                {
                    "name": "step_08",
                    "description": "move camera back to player pos",
                    "type": "animation",
                    "target": self.camera.target,
                    "args": {"x": self.player.pos.x,  "y": self.player.pos.y},
                    "duration": 1.0,
                    "transition": CAMERA_TRANSITION,
                    "from": "step_07",
                    "trigger": "on finish"
                },
                {
                    "name": "step_08a",
                    "description": "day time",
                    "type": "animation",
                    "target": self,
                    "args": {"hour": 12},
                    "round_values": True,
                    "duration": .250,
                    "transition": "linear",
                    "from": "step_07",
                    "trigger": "on finish"
                },
                {
                    "name": "step_09",
                    "description": "revert camera target to the player",
                    "type": "task",
                    "target": self.set_camera_on_player,
                    "args": {},
                    "interval": 0.1,
                    "times": 1,
                    "from": "step_08",
                    "trigger": "on finish"
                },
                {
                    "name": "step_10",
                    "description": "hide cutscene framing",
                    "type": "animation",
                    "target": self,
                    "args": {"cutscene_framing": 0.0},
                    "duration": 1.0,
                    "transition": "out_cubic",
                    "from": "step_08",
                    "trigger": "on finish"
                },
                {
                    "name": "step_11",
                    "description": "show UI",
                    "type": "animation",
                    "target": self,
                    "args": {"display_ui_flag": 1},
                    "round_values": True,
                    "duration": 0.1,
                    "transition": "linear",
                    "from": "step_10",
                    "trigger": "on finish"
                },
            ]
        }
        animator(self.intro_cutscene, self.animations)

    #############################################################################################################
    def set_camera_on_player(self) -> None:
        self.camera.target = self.player.pos
        self.camera.zoom = ZOOM_LEVEL
        self.group.center(self.camera.target)
        # TODO fix zoom
        # self.map_view.zoom = self.camera.zoom

    #############################################################################################################
    def set_camera_free(self) -> None:
        # release reference to self.player.pos by coping only value
        self.camera.target = self.camera.target.copy()

    #############################################################################################################
    # def go_to_scene(self) -> None:
    #     if not self.new_scene:
    #         return

    #     self.transition.exiting = False
    #     new_scene = Scene(
    #         self.game,
    #         self.new_scene.to_map,
    #         self.new_scene.entry_point,
    #         self.new_scene.is_maze,
    #         self.new_scene.maze_cols,
    #         self.new_scene.maze_rows
    #     )
    #     self.exit_state(quit=False)
    #     new_scene.enter_state()

    #############################################################################################################
    def on_resize(self) -> None:
        """Re-fit viewport-sized surfaces after a display resolution change.

        The pyscroll viewport and the day/night filter surface are created once at
        the canvas size; when the resolution changes while this scene is loaded (e.g.
        via the in-game settings menu), returning to it must show the full new
        viewport, not a stale smaller one.
        """
        self.map_view.set_size(self.game.canvas.get_size())
        self.filter_surf = pygame.Surface(
            (settings.WIDTH // FILTER_SCALE, settings.HEIGHT // FILTER_SCALE),
            pygame.SRCALPHA,
        )

    def go_to_map(self) -> None:
        if not self.new_scene:
            return

        # cancel the leaving map's armed spawn timers so they don't keep firing for
        # emitters that are about to be swapped out (each map keeps its own director)
        if self.weather:
            self.weather.stop_all()

        self.return_map = self.current_map
        self.return_entry_point = self.new_scene.return_entry_point

        self.current_map = self.new_scene.to_map
        # print(f"{self.entry_point=} {self.new_scene.entry_point}")
        self.entry_point = self.new_scene.entry_point
        self.is_maze = self.new_scene.is_maze
        self.maze_cols = self.new_scene.maze_cols
        self.maze_rows = self.new_scene.maze_rows
        # The seed belongs to the level we are leaving. Clearing it lets
        # `_resolve_maze_seed` decide for the level we are entering: reproduce the
        # one waiting in `pending_map_states`, or roll a fresh one. A cached level
        # gets its seed back from `restore_map` (it is in `properties`).
        self.maze_seed = None

        if self.current_map not in self.loaded_maps:
            self.reset_sprite_groups()
            self.player.shadow = self.player.create_shadow()
            self.player.emote = self.player.create_emote()
            self.player.health_bar = self.player.create_health_bar()
            self.load_map()
        else:
            self.reset_sprite_groups()

            self.restore_map()
            map_loader.set_entry_point(self)

            self.player.shadow = self.player.create_shadow()
            self.player.emote = self.player.create_emote()
            self.player.health_bar = self.player.create_health_bar()

            self.game.unregister_custom_events()
            map_loader.populate_sprite_groups(self)

        if USE_PARTICLES:
            self.start_particles()

        # Quest event: arriving somewhere can satisfy a quest. Nothing uses
        # location conditions yet (`at_location()` is still hypothetical - see
        # Q01_S07 in the plan), but the hook is where it will need to be, and
        # firing it now keeps the sweep quiet when it lands.
        self.quests.on_event("map_change")

        # Autosave only when entering a maze (entry point into a dungeon). Regular
        # room-to-room transitions are not autosaved. The toast lets the player know
        # the quick save slot was silently overwritten.
        if (self.is_maze
                and hasattr(self.game, "save_manager")
                and self.game.save_manager.save(QUICK_SAVE_SLOT)):
            self.add_notification(_("notify.autosaved_quick"), NotificationTypeEnum.info)

        self.transition.exiting = False

    #############################################################################################################
    def update_sleepers(self) -> None:
        """Take characters whose routine put them to bed out of the world, and back.

        Done here, once a frame, rather than by the character itself: falling
        asleep means leaving `self.group`, and a sprite removing itself from the
        very group whose `update()` is running is the kind of thing that works
        until it doesn't. The character only ever states an intention
        (`wants_to_sleep`); this turns it into fact.

        Leaving the group is what makes sleeping cheap - no animation, no physics,
        no pathfinding, and nothing drawn. But the character stays in `self.NPCs`,
        because that list is what the save file is built from (`_build_map_states`)
        and a sleeping merchant must not lose its purse overnight. The two loops
        that would otherwise bump into an invisible body skip sleepers explicitly.

        A sleeping character gets no update of its own, so it could never notice
        the morning. Consulting its schedule from here is what wakes it.
        """
        for npc in self.NPCs:
            if npc.is_asleep:
                npc.update_schedule()

            if npc.wants_to_sleep and not npc.is_asleep:
                npc.is_asleep = True
                self.group.remove(npc, npc.shadow, npc.health_bar, npc.emote)
            elif not npc.wants_to_sleep and npc.is_asleep:
                npc.is_asleep = False
                self.group.add(npc, layer=self.sprites_layer)
                self.group.add(npc.shadow, layer=self.sprites_layer - 2)
                self.group.add(npc.health_bar, layer=self.sprites_layer + 1)
                self.group.add(npc.emote, layer=self.sprites_layer + 1)

    #############################################################################################################
    def awake_NPCs(self) -> list[Any]:
        """`self.NPCs` minus the ones currently indoors asleep.

        Used for collision and for "who is close enough to talk to": a character
        that is not drawn must not be bumped into or traded with either.
        """
        return [npc for npc in self.NPCs if not npc.is_asleep]

    #############################################################################################################
    def abs_minutes(self) -> int:
        # delegat do systemu world_clock (B01 krok 3)
        return world_clock.abs_minutes(self)

    #############################################################################################################
    def update_routine_npcs(self) -> None:
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
        defaults = self.routines.defaults
        now_abs = self.abs_minutes()
        minutes = self.hour * 60 + self.minute
        for npc in self.loaded_NPCs.values():
            routine_key = npc.runtime.routine_key
            if not routine_key or npc.is_dead:
                continue
            routine = self.routines.routines.get(routine_key)
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
                door = self.exit_to(new_to_map) if npc in self.NPCs else None
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

        self.reconcile_routine_presence()

    #############################################################################################################
    @staticmethod
    def _routine_physical_map(npc: "Any") -> str:
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

    #############################################################################################################
    def reconcile_routine_presence(self) -> None:
        """Add / remove routine NPCs from the live map as the schedule moves them (v5).

        Runs every frame after `update_routine_npcs`. It is the counterpart to
        `_settle_routine_npcs` (which handles a whole map load at once): here a
        single character crosses a boundary while the player stands still, so only
        the ones whose physical map just started or stopped matching the loaded map
        change. Mirrors `update_sleepers` - the sprite plumbing is the same.
        """
        for npc in self.loaded_NPCs.values():
            if not npc.runtime.routine_key or npc.is_dead:
                continue
            # A character walking out reaches the threshold and goes through it: the
            # frame it stops travelling (the door path is spent) it is gone from the
            # map it was leaving, and its arrival on the far side is timed from *now* -
            # so it turns up there shortly after, however long the walk to the door took.
            if (npc.runtime.transit_to_map and not npc._transit_gone
                    and npc in self.NPCs and not npc.is_travelling):
                npc._transit_gone = True
                npc.runtime.transit_arrive_min = min(
                    npc.runtime.transit_arrive_min,
                    self.abs_minutes() + self.routines.defaults.transit_minutes,
                )
            physical = self._routine_physical_map(npc)
            should_be_here = physical == self.current_map
            present = npc in self.NPCs
            if should_be_here and not present:
                npc.current_map = self.current_map
                self._materialize_routine_npc(npc)
            elif present and not should_be_here:
                npc.current_map = physical
                self._dematerialize_routine_npc(npc)

    #############################################################################################################
    def _settle_routine_npcs(self) -> None:
        """Place every routine NPC on the map it is logically on, before drawing it.

        Called once from `populate_sprite_groups`, i.e. whenever a map is (re)built.
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
        for npc in self.loaded_NPCs.values():
            if not npc.runtime.routine_key:
                continue
            physical = self._routine_physical_map(npc)
            npc.current_map = physical
            if physical != self.current_map:
                continue
            if npc.origin_map != self.current_map or npc._roster_unplaced:
                place = self._slot_place(npc)
                if place is not None:
                    npc.pos = vec(place)
                    npc.prev_pos = npc.pos.copy()
                    npc.adjust_rect()
                    # Anchored on a real map now - keep this position on re-entry
                    # instead of being teleported to the slot place every time.
                    npc._roster_unplaced = False

    #############################################################################################################
    def _slot_place(self, npc: "Any") -> "vec | None":
        """Walkable pixel of the NPC's current slot destination on *this* map, or None.

        Only resolves a `place` that lands on the loaded map (a route or a target on
        another map is not a spot to stand at). Snapped off any wall the marker sits
        on, the same way `find_path` does it.
        """
        routine = self.routines.routines.get(npc.runtime.routine_key)
        if routine is None:
            return None
        minutes = self.hour * 60 + self.minute
        slot = current_slot(routine, minutes, npc._schedule_jitter or 0)
        if slot is None:
            return None
        dest = resolve_at(
            slot.at, destinations_of(npc.model), self.places, self.waypoints,
            origin_map=npc.origin_map, current_map=self.current_map,
        )
        if dest is None or dest.kind != "place" or dest.map != self.current_map:
            return None
        if dest.name not in self.places:
            return None
        return self._walkable_pixel(self.places[dest.name])

    #############################################################################################################
    def _walkable_pixel(self, pixel: "vec") -> "vec":
        """Nearest tile centre A* can stand on to `pixel` - so a teleport never lands in a wall.

        Tolerates being called from `populate_sprite_groups` before `load_step_cost`
        has (re)built the grid: with no grid to consult it just returns the raw
        marker, which authors place on something sensible anyway.
        """
        grid = getattr(self, "path_finding_grid", None)
        if grid:
            goal = (int(pixel.y // TILE_SIZE), int(pixel.x // TILE_SIZE))
            walkable = nearest_walkable(grid, goal)
            if walkable:
                row, col = walkable
                return vec(col * TILE_SIZE + TILE_SIZE // 2, row * TILE_SIZE + TILE_SIZE // 2)
        return vec(pixel)

    #############################################################################################################
    def exit_to(self, map_name: str) -> "vec | None":
        """The doorway on *this* map that leads to `map_name`. The exit collider sits
        on the threshold, so its own position is exactly the door - but that tile is
        a wall (you walk *into* it to leave), so it is only the anchor for finding the
        walkable landing beside it, never a spot to stand on. See `_arrival_pos`."""
        for exit in self.exits:
            if getattr(exit, "to_map", "") == map_name:
                return vec(exit.rect.midbottom)
        return None

    #############################################################################################################
    def _arrival_pos(self, source_map: str) -> "vec | None":
        """Walkable spot an NPC coming from `source_map` should appear at.

        The doorway collider is a wall, so an NPC dropped on it is stuck - A* cannot
        step off a blocked tile, so it never leaves the threshold. The walkable
        landing is the `entry_points` object beside that door: the very spot the
        player lands on when walking through it (here `VillageHouseDoor`). Pick the
        entry point nearest the exit that leads back to `source_map` - door and its
        entry point are the same threshold - and snap it onto free ground for safety.
        Falls back to snapping the doorway itself if the map has no entry points.
        """
        door = self.exit_to(source_map)
        if door is None:
            return None
        nearest: "vec | None" = None
        nearest_d2: float | None = None
        for pos in self.entry_points.values():
            d2 = (vec(pos) - door).length_squared()
            if nearest_d2 is None or d2 < nearest_d2:
                nearest, nearest_d2 = vec(pos), d2
        return self._walkable_pixel(nearest if nearest is not None else door)

    #############################################################################################################
    def _materialize_routine_npc(self, npc: "Any") -> None:
        """Bring a routine NPC onto the live map: position it, then wire its sprites.

        Positioning has two shapes. If it just arrived through a door (`_arrived_from`
        set, and that door exists on this map) it appears at the threshold and walks
        to its destination - the visible "comes in and crosses the room" case. Any
        other way of becoming present drops it at the destination directly.
        """
        door = self._arrival_pos(npc._arrived_from) if npc._arrived_from else None
        place = self._slot_place(npc)
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

        self.NPCs.append(npc)
        self.shadow_sprites.add(npc.shadow)
        self.label_sprites.add(npc.health_bar)
        self.label_sprites.add(npc.emote)
        npc.register_custom_event()
        self.group.add(npc, layer=self.sprites_layer)
        self.group.add(npc.shadow, layer=self.sprites_layer - 2)
        self.group.add(npc.health_bar, layer=self.sprites_layer + 1)
        self.group.add(npc.emote, layer=self.sprites_layer + 1)

    #############################################################################################################
    def _dematerialize_routine_npc(self, npc: "Any") -> None:
        """Take a routine NPC off the live map when the schedule moves it elsewhere.

        The mirror of `_materialize_routine_npc`: drop it from the draw group and the
        active list, but leave it in `loaded_NPCs` so its schedule keeps ticking and
        it can come back. `is_asleep` is cleared - a character walking out of the map
        is by definition awake, and leaving the flag set would strand it invisible if
        it were mid-sleep.
        """
        if npc in self.NPCs:
            self.NPCs.remove(npc)
        self.group.remove(npc, npc.shadow, npc.health_bar, npc.emote)
        self.shadow_sprites.remove(npc.shadow)
        self.label_sprites.remove(npc.health_bar, npc.emote)
        npc.is_asleep = False
        npc.wants_to_sleep = False

    #############################################################################################################
    def load_routine_roster(self) -> None:
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

        hub = self.current_map
        # Dedup by config key, not object name: a spawn_point named "Johny" carries
        # model_name "JOHNY", so `loaded_NPCs` is keyed "Johny" while the roster walks
        # config keys ("JOHNY"). Comparing the two names missed the match and built a
        # duplicate that stood at the destination while the original walked to it.
        present = {getattr(npc, "config_key", "") or npc.name for npc in self.loaded_NPCs.values()}
        for key in routine_roster_keys(self.game.conf.characters, present):
            model = self.game.conf.characters[key]
            routine_key = str(getattr(model, "routine", "") or "").strip()
            if routine_key not in self.routines.routines:
                print(f"[routines] roster '{key}' wants unknown routine '{routine_key}'")
                continue
            detached_shadow: pygame.sprite.Group = pygame.sprite.Group()
            detached_label: pygame.sprite.Group = pygame.sprite.Group()
            npc = NPC(
                self.game, self, detached_shadow, detached_label,
                (0, 0), key, self.icons, (), model_name=key,
            )
            origin = roster_origin_map(model, hub)
            npc.origin_map = origin
            npc.current_map = origin
            npc.runtime.routine_key = routine_key
            npc.runtime.logical_map = origin
            # Created at the (0,0) placeholder - `_settle_routine_npcs` gives it a
            # real position the first time its map is loaded.
            npc._roster_unplaced = True
            self.loaded_NPCs[key] = npc

    #############################################################################################################
    def day_rng(self, name: str = "", day_offset: int = 0) -> random.Random:
        # delegat do systemu world_clock (B01 krok 3)
        return world_clock.day_rng(self, name, day_offset)

    #############################################################################################################
    def apply_days(self, days: int = 1) -> None:
        # delegat do systemu world_clock (B01 krok 3)
        world_clock.apply_days(self, days)

    #############################################################################################################
    # @timeit
    def update(self, dt: float, events: list[pygame.event.EventType]) -> None:
        # MARK: update
        self.remove_old_notifications()
        # Quest safety net (D12=C). Events do the real work; this only catches a
        # hook we failed to wire, and complains when it has to.
        self.quests.update(dt)

        # sample this before ui.update() so that on the frame a modal panel closes
        # itself (e.g. Esc in QuestPanel) we still freeze this frame - that keeps the
        # closing keypress from also leaking to the scene (Esc would open the menu).
        modal_open = self.ui.is_modal_open()

        if self.display_ui_flag:
            self.ui.update(self.game.time_elapsed, events)

        # while a modal panel is open the world is frozen and input goes only to
        # the panel; clear INPUTS so nothing queued fires when the panel closes.
        if modal_open:
            # Dialog/Trade freeze the world, but keep the animated emotes above
            # characters running so the scene doesn't look completely static.
            for npc in self.NPCs:
                if npc.emote:
                    npc.emote.animate(dt)
            if self.player.emote:
                self.player.emote.animate(dt)
            self.game.reset_inputs()
            return

        self.group.update(dt)
        # after group.update, so nobody is mutating the group mid-pass
        self.update_sleepers()
        # cross-map schedule: moves off-screen routine NPCs between maps (v5).
        # Runs after the modal-open early return above, so a dialog/trade freezes
        # the clock and no transit arms mid-conversation (the P8 "Talk absorbs a
        # slot change" guarantee falls out of the existing freeze).
        self.update_routine_npcs()
        self.animations.update(dt)
        self.transition.update(dt)

        # advance weather episodes (start/stop emitters); global master switch gates it
        if USE_PARTICLES and self.weather:
            self.weather.update(dt)

        # zegar świata (B01 krok 3): upływ minut, przełom doby i upkeep dnia
        world_clock.tick(self, dt)

        # kolizje klatki (B01 krok 4): ściany, NPC-e, broń, destruktible,
        # skrzynia i NPC w zasięgu rozmowy
        collisions.resolve(self)

        # akcje gracza (B01 krok 5): cały blok INPUTS
        player_actions.handle(self)

    # TODO Rename this here and in `update`
    def _confirm_reload_map(self) -> None:
        """Called from the reload confirmation dialog (Yes) - actually reset the map."""
        self.reload_map()
        self.ui.reset()

    def reload_map(self) -> None:
        self.game.time_elapsed = 0.0
        world_clock.reset(self)
        self.display_ui_flag = True
        self.cutscene_framing = 0.0

        # shadow = self.player.shadow
        self.reset_sprite_groups()
        # self.map_view.reload()
        self.player.reset()
        # stop the old director's timers before load_map() rebuilds the emitters
        if self.weather:
            self.weather.stop_all()
        self.load_map()
        if USE_PARTICLES:
            self.start_particles()

    def reset_sprite_groups(self) -> None:
        self.label_sprites.empty()
        self.exit_sprites.empty()
        self.item_sprites.empty()
        self.obstacles_sprites.empty()
        self.shadow_sprites.empty()
        self.group.empty()

    #############################################################################################################
    # @timeit
    def draw(self, screen: pygame.Surface, dt: float) -> None:
        # MARK: draw
        # center map on player
        # self.group.center(self.player.pos)
        # self.map_view.center(self.camera.target)
        # self.map_view.zoom = self.camera.zoom
        self.group.center(self.camera.target)

        self.group.draw(screen)

        for particle in self.particles:
            particle.emit(dt)

        self.transition.draw(screen)

        # alpha filter demo
        if USE_ALPHA_FILTER and not IS_WEB:
            self.apply_time_of_day_filter(screen)
            # self.apply_alpha_filter(screen)

        # draw black bars at the top and bottom when during cutscene
        if self.cutscene_framing:
            self.apply_cutscene_framing(screen, self.cutscene_framing)

        if SHOW_DEBUG_INFO:
            self.show_debug()
            self.debug([f"FPS: {self.game.fps: 7.1f} M: {self.current_map}",])

        if self.display_ui_flag:
            self.ui.draw(self.game.time_elapsed)

    #############################################################################################################

    def apply_time_of_day_filter(self, screen: pygame.Surface) -> None:
        # MARK: apply_time_of_day_filter
        # do not apply night and day filter indoors
        if not self.outdoor and not self.is_maze:
            return

        filter = list(BG_COLOR)
        hour: float = self.hour + (self.minute / 60)

        if self.is_maze:
            filter = list(NIGHT_FILTER)
        else:
            if hour < 6 or hour >= 20:
                filter = list(NIGHT_FILTER)
            elif 6 <= hour < 9:
                weight = (hour - 6) / (9 - 6)
                for i in range(4):
                    filter[i] = pygame.math.lerp(NIGHT_FILTER[i], DAY_FILTER[i], weight)  # type: ignore[call-overload]
            elif 9 <= hour < 17:
                filter = list(DAY_FILTER)
            elif 17 <= hour < 20:
                weight = (hour - 17) / (20 - 17)
                for i in range(4):
                    filter[i] = pygame.math.lerp(DAY_FILTER[i], NIGHT_FILTER[i], weight)  # type: ignore[call-overload]

        self.filter_surf.fill(filter)

        if (hour > 17 or hour < 9) or self.is_maze:
            scale = (self.camera.zoom / ZOOM_LEVEL)
            for npc in self.NPCs + [self.player]:
                pos = self.map_view.translate_point(npc.pos + vec(0, -8))
                pos_vec = (tuple_to_vector(pos) / FILTER_SCALE) - vec(CIRCLE_RADIUS, CIRCLE_RADIUS) * scale
                self.filter_surf.blit(
                    # self.b_and_w_circle,
                    pygame.transform.scale_by(self.b_and_w_circle, scale),
                    pos_vec,
                    special_flags=pygame.BLEND_RGBA_MIN)

            if "intro" in self.waypoints:
                scale = 2 * (self.camera.zoom / ZOOM_LEVEL)
                village_pos = to_vector(self.waypoints["intro"][0])
                pos = self.map_view.translate_point(village_pos + vec(0, 0))
                pos_vec = (tuple_to_vector(pos) / FILTER_SCALE) - vec(CIRCLE_RADIUS, CIRCLE_RADIUS) * scale
                self.filter_surf.blit(
                    pygame.transform.scale_by(self.b_and_w_circle, scale),
                    pos_vec,
                    special_flags=pygame.BLEND_RGBA_MIN)

                village_pos = to_vector(self.waypoints["intro"][-1])
                pos = self.map_view.translate_point(village_pos)
                pos_vec = (tuple_to_vector(pos) / FILTER_SCALE) - vec(CIRCLE_RADIUS, CIRCLE_RADIUS) * scale
                self.filter_surf.blit(
                    pygame.transform.scale_by(self.b_and_w_circle, scale),
                    pos_vec,
                    special_flags=pygame.BLEND_RGBA_MIN)

        screen.blit(pygame.transform.scale(self.filter_surf, (settings.WIDTH, settings.HEIGHT)))  # FILTER_SCALE
        # print(screen.get_bitsize(), self.filter_surf.get_bitsize())
        # pygame.transform.scale(self.filter_surf, (WIDTH, HEIGHT), screen)  # FILTER_SCALE

    #############################################################################################################

    def get_lights(self) -> tuple[list[vec3], float]:
        # return list of light source coordinates with sizes and day/night ratio as float
        # in range [0.0, 1.0] (0.0 ==> day)
        light_sources: list[vec3] = []
        ratio: float = 0.0

        # indoors it's always day except mazes
        # no light sources
        if not self.outdoor and not self.is_maze:
            ratio = 0.0
        else:
            # in maze it's always night
            if self.is_maze:
                ratio = 1.0
            else:
                hour: float = self.hour + (self.minute / 60)
                if hour < 6.00 or hour >= 20.00:
                    ratio = 1.0
                elif 6.00 <= hour < 9.00:
                    ratio = 1.0 - ((hour - 6.00) / (9.00 - 6.00))
                    # for i in range(4):
                    #     filter[i] = pygame.math.lerp(NIGHT_FILTER[i], DAY_FILTER[i], weight)
                elif 9.00 <= hour < 17.00:
                    ratio = 0.0
                else:
                    ratio = (hour - 17.00) / (20.00 - 17.00)
            # if it's not full day add light sources
            if ratio > 0.0:
                for npc in self.NPCs + [self.player]:
                    pos = self.map_view.translate_point(npc.pos + vec(0, -8))
                    # pos_list = scene.map_view.translate_point(npc.pos + vec(0, -8))
                    light = vec3(pos[0], settings.HEIGHT - pos[1], 64.0)
                    light_sources.append(light)
                    # pygame.draw.circle(filter_surf, DAY_FILTER, pos, 196)
                if "intro" in self.waypoints:
                    self.get_light_from_intro(light_sources)
                    # pygame.draw.circle(filter_surf, DAY_FILTER, pos, 256)

        return (light_sources, ratio)

    #############################################################################################################
    def get_light_from_intro(self, light_sources: list[vec3]) -> None:
        village_pos = self.waypoints["intro"][0].as_vector
        pos = self.map_view.translate_point(village_pos + vec(0, 0))
        light = vec3(pos[0], settings.HEIGHT - pos[1], 64.0)
        light_sources.append(light)

        village_pos = self.waypoints["intro"][-1].as_vector
        pos = self.map_view.translate_point(village_pos + vec(0, 0))
        light = vec3(pos[0], settings.HEIGHT - pos[1], 64.0)
        light_sources.append(light)

    #############################################################################################################
    def apply_alpha_filter(self, screen: pygame.Surface) -> None:
        # MARK: apply_alpha_filter
        h = settings.HEIGHT // 2
        self.game.render_text(_("scene.day_label"),   (0, int(h - FONT_SIZE_MEDIUM * TEXT_ROW_SPACING)))
        self.game.render_text(_("scene.night_label"), (0, int(h +                    TEXT_ROW_SPACING)))

        # sunny, warm yellow light during daytime
        half_screen = pygame.Surface((settings.WIDTH, h), pygame.SRCALPHA)
        half_screen.fill(DAY_FILTER)
        screen.blit(half_screen, (0, 0))

        # cold, dark and bluish light at night
        half_screen.fill(NIGHT_FILTER)
        screen.blit(half_screen, (0, h))

    #############################################################################################################

    def apply_cutscene_framing(self, screen: pygame.Surface, percentage: float) -> None:
        # MARK: apply_cutscene_framing
        if percentage <= 0.001:
            return

        surface_h = settings.HEIGHT // 2
        framing_h = int(settings.HEIGHT * 0.1)
        framing_offset = int(framing_h * percentage)
        half_screen = pygame.Surface((settings.WIDTH, surface_h), pygame.SRCALPHA)
        half_screen.fill(CUTSCENE_BG_COLOR)
        # blit a black rect at the top of the screen
        screen.blit(half_screen, (0, -surface_h + framing_offset))
        # blit a black rect at the bottom of the screen
        screen.blit(half_screen, (0, settings.HEIGHT - framing_offset))

    #############################################################################################################
    def show_debug(self) -> None:
        # MARK: show_debug
        # prepare shader info

        # shader_index = SHADERS_NAMES.index(self.game.shader.shader_name)
        # shader_index = max(shader_index, 0)
        # shader_name = SHADERS_NAMES[shader_index] if USE_SHADERS else "n/a"
        # prepare debug messages displayed in upper left corner
        # msgs = [
        #     f"FPS: {self.game.fps: 5.1f} Shader: {shader_name}",
        #     # f"Eye: x:{self.camera.target.x:6.2f} y:{self.camera.target.y:6.2f}",
        #     f"Time: {self.hour}:{self.minute:02}",
        #     # f"vel: {self.player.vel.x: 6.1f} {self.player.vel.y: 6.1f}",
        #     # f"x  : {self.player.pos.x: 3.0f}   y : {self.player.pos.y: 3.0f}",
        #     # f"g x:  {self.player.tileset_coord.x: 3.0f} g y : {self.player.tileset_coord.y: 3.0f}",
        #     # f"up_vel: {self.player.up_vel: 3.1f} up_acc{self.player.up_acc: 3.1f}",
        #     # f"t x:  {self.player.target.x: 3.0f} t y : {self.player.target.y: 3.0f}",
        #     # f"offset: {self.player.jumping_offset: 6.1f}",
        #     # f"col: {self.player.rect.collidelist(self.walls):06.02f}",
        #     # f"bored={self.player.state.enter_time: 5.1f} time_elapsed={self.game.time_elapsed: 5.1f}",
        # ]
        # self.debug(msgs)

        if self.is_maze:
            current_map_level: int = int(self.current_map.split("_")[1])
            if current_map_level == 1:
                path = self.maze_stats["longest_N_wall_path"]
            else:
                path = self.maze_stats["longest_dead_end_path"]
            self.mark_maze_sub_grid(path[0], "red")
            self.mark_maze_sub_grid(path[-1], "blue")
            for step in path[1:-1]:
                self.mark_maze_sub_grid(step, "green")
            pass

        # display npc (and players) debug messages
        for npc in self.NPCs + [self.player]:
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
                    from_p = self.map_view.translate_point(vec(prev_point.x, prev_point.y))
                    to_p = self.map_view.translate_point(vec(point.x, point.y))
                    pygame.draw.line(self.game.canvas, WAYPOINTS_LINE_COLOR, from_p, to_p, width=2)
                    prev_point = point

            pos = self.map_view.translate_point(npc.pos)
            self.game.render_texts(texts, pos, font_size=FONT_SIZE_MEDIUM, centred=True)

            # render red square indicating hitbox
            rect = self.map_view.translate_rect(npc.feet)
            pygame.draw.rect(self.game.canvas, "red", rect, width=2)

        # # draw walls (colliders)
        # for y, row in enumerate(self.path_finding_grid):
        #     for x, tile in enumerate(row):
        #         if tile > 0:
        #             rect_w = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        #             rect_s = self.map_view.translate_rect(rect_w)
        #             img = pygame.Surface(rect_s.size, pygame.SRCALPHA)
        #             pygame.draw.rect(img, (0,0,200,64), img.get_rect())
        #             self.game.canvas.blit(img, rect_s)

    def mark_maze_sub_grid(self, start: tuple[int, int], color: str) -> None:
        # MARGIN = 3
        # MARGIN_X = 3
        # MARGIN_Y = 3
        # SUBTILE_GRID = 6

        left = MARGIN * TILE_SIZE + start[0] * SUBTILE_COLS * TILE_SIZE
        top  = MARGIN * TILE_SIZE + start[1] * SUBTILE_ROWS * TILE_SIZE
        rect = self.map_view.translate_rect((left, top, SUBTILE_COLS * TILE_SIZE, SUBTILE_ROWS * TILE_SIZE))
        pygame.draw.rect(self.game.canvas, color, rect, width=4)
