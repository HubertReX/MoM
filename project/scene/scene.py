import random
from typing import Any, cast
from rich import print
import game
import pygame
import pyscroll
import pyscroll.data
from camera import Camera
from maze_generator.maze import Maze
from maze_generator.maze_utils import (
    MARGIN,
    SUBTILE_COLS,
    SUBTILE_ROWS,
    TILE_SIZE,
    clear_maze_cache,
    get_gid_from_tmx_id,
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
    TRANSPARENT_COLOR,
    USE_ALPHA_FILTER,
    USE_PARTICLES,
    USE_SHADERS,
    WAYPOINTS_LINE_COLOR,
    ZOOM_LEVEL,
    # ColorValue,
    Point,
    # to_vector,
    # tuple_to_vector,
    vec,
    vec3,
    vector_to_tuple
)
from scene import (collisions, intro, map_loader, map_state, night_filter, player_actions,
                   routines_director, world_clock)
from state import State
from transition import Transition, TransitionCircle
from ui import icons as ui_icons
from ui.game_ui import GameUI
from ui.panels.hud import NOTIFICATION_TYPE_ICONS
from npc_schedule import Routines, load_routines

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
        # lista atrybutów per-mapa mieszka w scene/map_state.py (K1 - format save);
        # kopia, bo store/restore czyta ją z instancji
        self.properties: list[str] = list(map_state.MAP_PROPERTIES)

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
        # delegat do systemu map_state (B01 krok 7)
        map_state.store_map(self)

    #############################################################################################################

    def restore_map(self) -> None:
        # delegat do systemu map_state (B01 krok 7)
        map_state.restore_map(self)

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
        # delegat do systemu intro (B01 krok 8)
        intro.start_intro(self)

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
        # delegat do systemu map_state (B01 krok 7)
        map_state.go_to_map(self)

    #############################################################################################################
    def update_sleepers(self) -> None:
        # delegat do systemu routines_director (B01 krok 6)
        routines_director.update_sleepers(self)

    #############################################################################################################
    def awake_NPCs(self) -> list[Any]:
        """`self.NPCs` minus the ones currently indoors asleep."""
        # delegat do systemu routines_director (B01 krok 6)
        return routines_director.awake_NPCs(self)

    #############################################################################################################
    def abs_minutes(self) -> int:
        # delegat do systemu world_clock (B01 krok 3)
        return world_clock.abs_minutes(self)

    #############################################################################################################
    def update_routine_npcs(self) -> None:
        # delegat do systemu routines_director (B01 krok 6)
        routines_director.update_routine_npcs(self)

    #############################################################################################################
    def reconcile_routine_presence(self) -> None:
        # delegat do systemu routines_director (B01 krok 6)
        routines_director.reconcile_presence(self)

    #############################################################################################################
    def _settle_routine_npcs(self) -> None:
        # delegat do systemu routines_director (B01 krok 6)
        routines_director.settle(self)

    #############################################################################################################
    def exit_to(self, map_name: str) -> "vec | None":
        """The doorway on *this* map that leads to `map_name`."""
        # delegat do systemu routines_director (B01 krok 6)
        return routines_director.exit_to(self, map_name)

    #############################################################################################################
    def load_routine_roster(self) -> None:
        # delegat do systemu routines_director (B01 krok 6)
        routines_director.load_roster(self)

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
        # delegat do systemu map_state (B01 krok 7)
        map_state.reload_map(self)

    def reset_sprite_groups(self) -> None:
        # delegat do systemu map_state (B01 krok 7)
        map_state.reset_sprite_groups(self)

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
            night_filter.apply_time_of_day_filter(self, screen)
            # night_filter.apply_alpha_filter(self, screen)

        # draw black bars at the top and bottom when during cutscene
        if self.cutscene_framing:
            night_filter.apply_cutscene_framing(self, screen, self.cutscene_framing)

        if SHOW_DEBUG_INFO:
            self.show_debug()
            self.debug([f"FPS: {self.game.fps: 7.1f} M: {self.current_map}",])

        if self.display_ui_flag:
            self.ui.draw(self.game.time_elapsed)

    #############################################################################################################

    def get_lights(self) -> tuple[list[vec3], float]:
        # delegat do systemu night_filter (B01 krok 8) - czyta go shader w game.py
        return night_filter.get_lights(self)

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
