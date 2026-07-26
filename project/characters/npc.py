"""Klasa ``NPC`` - postać niezależna (bazowa dla :class:`characters.Player`).

Rdzeń dawnego ``characters.py``; w kroku 10 refactoru B01 plik został
przeniesiony do pakietu ``characters/`` bez zmian w metodach (klasa ``Player``
poszła do ``characters/player.py``). Szczegóły: doc/refactor-rdzenia-B01.md.
"""
# from dataclasses import dataclass
import copy
import os
import random
from enum import Enum, auto
from typing import Any, TYPE_CHECKING
from rich import print

if TYPE_CHECKING:
    from save_load.models import NPCDialogState

import pygame
import settings
from pygame.math import Vector2 as vec
from settings import (
    IDLE_EMOTE_DURATION,
    ANIMATION_SPEED,
    _,
    IS_WEB,
    entity_name,
    get_buy_price_multiplier,
    get_sell_price_multiplier,
    MAX_HOTBAR_ITEMS,
    STEP_COST_WALL,
    TILE_SIZE,
    Point,
    tuple_to_vector,
    vector_to_tuple,
)
from enums import ItemTypeEnum, RaceEnum, NPCEventActionEnum
if IS_WEB:
    from config_model.config import Character
else:
    from config_model.config_pydantic import Character  # type: ignore[assignment]

from dialog.entities import DialogNode
from dialog.graph import get_start_node, init_dialog

import game
import npc_state
from npc_runtime import NpcRuntime
from npc_schedule import Destination, Slot, current_slot, destinations_of, resolve_at, slot_jitter
import scene
from characters import animation, combat, movement
from scene import debug_overlay
import splash_screen
from objects import ChestSprite, EmoteSprite, HealthBar, ItemSprite, Shadow


#################################################################################################################
# MARK: NPC
# @dataclass(slots=True)
class NPC(pygame.sprite.Sprite):
    def __init__(
            self,
            game: game.Game,
            scene: scene.Scene,
            shadow_group: pygame.sprite.Group,
            label_group: pygame.sprite.Group,
            pos: tuple[int, int],
            name: str,
            emotes: dict[str, list[pygame.Surface]],
            waypoints: tuple[Point, ...] = (),
            model_name: str = "",
    ):

        self.name = name
        if not model_name:
            model_name = self.name
        super(NPC, self).__init__()
        self.game = game
        self.scene = scene
        # Deep copy, not a reference: `game.conf.characters[...]` is one object
        # shared by the whole process, and this class writes into it (`model.health`
        # in hit/encounter, `model.money` in pick_up and trading). Without the copy
        # every snake in the maze drew from a single pool of health - kill one and
        # the next died to a single blow - and the player's gold survived into a new
        # game. Items and chests already copy their config per instance
        # (`Scene.create_item`, chest spawning); NPCs were the one that did not.
        # deepcopy, not copy: `Character` carries lists (`items`, `allowed_zones`)
        # and a dict (`disposition`), and on desktop it is a pydantic model.
        self.model: Character = copy.deepcopy(game.conf.characters[model_name])
        # Mutable state that is deliberately *not* in the config model - see
        # npc_runtime.NpcRuntime for why it lives outside it.
        self.runtime: NpcRuntime = NpcRuntime()
        self.current_map = self.scene.current_map
        # The map this character belongs to - where it spawned. It is the anchor a
        # daily routine walks it away from and back to, the map its state is saved
        # under, and the default map for any destination written without a `map:`
        # prefix. `logical_map` starts here too; the schedule moves it from here.
        self.origin_map = self.current_map
        self.runtime.logical_map = self.current_map
        self.has_dialog: bool = False
        # How many item slots this character has. Used to be the module constant
        # MAX_HOTBAR_ITEMS everywhere; it is a per-character field now because a
        # quest can reward the hero extra slots (decision D11). MAX_HOTBAR_ITEMS
        # stays as the starting value, MAX_HOTBAR_ITEMS_LIMIT as the ceiling
        # (bounded by the number of hotbar keys and key icons that exist).
        self.max_items: int = MAX_HOTBAR_ITEMS

        # dialog-system state (T-023): `dialog` is the live cursor into the
        # DialogNode graph built from config.json.
        self.config_key: str = model_name
        self.dialog: DialogNode | None = None
        self.dialog_nodes: dict[str, DialogNode] | None = None
        self.selected_options_dict: dict[str, bool] = {}
        self.dialog_start_node: DialogNode | None = None
        # base sentiment comes from the character's `friendly` (0..1) config field
        self.sentiment: int = round(self.model.friendly * 100)
        self.disposition: dict[str, int] = dict(self.model.disposition)
        self.known_disposition: dict[str, int] = {}

        # Daily routine bookkeeping. `_schedule_slot` remembers which slot was last
        # acted on, so the schedule is consulted every frame but only *does*
        # anything on a boundary - retargeting every frame would restart the A*
        # path continuously and the NPC would never actually get anywhere.
        self._schedule_slot: Slot | None = None
        self._schedule_jitter: int | None = None
        self._schedule_destination: Destination | None = None
        # Anchor for `wander`: the place the character drifts *around*, kept apart
        # from `target`, which is wherever the current little stroll is heading.
        self._wander_anchor: vec | None = None
        self._wander_next_time: float = 0.0
        self._idle_emoted: bool = False
        # Which map this character just walked in from, set on the frame a cross-map
        # transit completes and consumed by the presence reconciler to pick the
        # doorway it should appear at. Transient - never saved, never trusted stale.
        self._arrived_from: str | None = None
        # True once a departing character has reached (walked through) the door on the
        # map it is leaving: it then goes invisible even though the arrival timer -
        # which alone decides when it turns up on the far side - has not fired yet.
        # Off-screen departures set it immediately (no walk to show).
        self._transit_gone: bool = False
        # A routine character created by the roster (its spawn map was not loaded
        # yet) sits at the (0,0) placeholder until it is first settled on a real
        # map. A visitor gets a real position the moment it materialises, but a
        # character whose *home* map is a non-hub map is never a visitor there, so
        # `_settle_routine_npcs` has to notice this flag and drop it at its slot
        # destination instead of leaving it stuck in the wall at (0,0).
        self._roster_unplaced: bool = False
        # `wants_to_sleep` is the character's own opinion; `is_asleep` is the world
        # acting on it. They are separate because taking a sprite out of the draw
        # group from inside that group's own update pass is asking for trouble -
        # `Scene.update_sleepers` reconciles the two once a frame, from outside.
        self.wants_to_sleep: bool = False
        self.is_asleep: bool = False

        self.load_dialogs()

        self.shadow_group = shadow_group
        self.label_group = label_group
        self.pos: vec = vec(pos[0], pos[1])
        self.prev_pos: vec = self.pos.copy()

        self.shadow = self.create_shadow()
        self.health_bar = self.create_health_bar()
        # hide health bar at start (negative value makes it transparent)
        self.health_bar.hide()
        self.items: list[ItemSprite] = []
        self.selected_weapon: ItemSprite | None = None
        self.selected_item_idx: int = -1
        self.total_items_weight: float = 0.0
        self.animations: dict[str, list[pygame.surface.Surface]] = {}

        self.sprite_sheet_type: str = ""
        self.masks: dict[str, list[pygame.mask.Mask]] = {}
        self.animation_speed: float = ANIMATION_SPEED
        self.frame_index: float = 0.0
        self.avatar: pygame.surface.Surface
        # image/mask przypisuje animation.load_sprites - deklaracja tutaj dla mypy
        self.image: pygame.surface.Surface
        self.mask: pygame.mask.Mask
        # sprite sheet -> klatki animacji, maski, avatar i pierwsza klatka
        animation.load_sprites(self)

        self.emote: EmoteSprite = EmoteSprite(label_group, pos, emotes)

        self.tileset_coord: Point = self.get_tileset_coord()
        self.rect: pygame.FRect = self.image.get_frect(midbottom = self.pos)
        # hit box size is half the TILE_SIZE, bottom, centered
        self.feet = pygame.Rect(0, 0, self.rect.width // 2, TILE_SIZE // 2)
        self.feet.midbottom = (int(self.pos.x), int(self.pos.y))
        # individual steps to follow (mainly a center of a given tile, but pixel accurate)
        # provided by A* path finding
        self.waypoints: tuple[Point, ...] = waypoints
        self.waypoints_cnt: int = len(waypoints)
        self.current_waypoint_no: int = 0
        # list of targets to follow
        self.target: vec = vec(0, 0)
        self.targets: list[vec] = []

        # NPC met in the game
        self.npc_met: NPC | None = None
        # Chest object near player
        self.chest_in_range: ChestSprite | None = None

        # is in attacking state
        self.is_attacking: bool = False
        # game time (time_elapsed) when last attack was made
        self.attack_time: float  = 0.0
        # how long to wait before next attack (in mili seconds)
        self.attack_cooldown: int = 200
        # double check cooldown since events fail
        self.weapon_cooldown: float = 0.0
        # prevent tight pathfind retry loop when A* fails
        self.next_pathfind_time: float = 0.0

        self.can_switch_weapon: bool = True
        # how long to wait before next weapon switch (in mili seconds)
        self.switch_duration_cooldown: int = 400
        # double check cooldown since events fail
        self.switch_cooldown: float = 0.0
        # rest duration
        self.end_rest_time: float = -1.0

        # basic planar (N,E, S, W) physics
        # speed in pixels per second
        self.speed_walk: int = self.model.speed_walk
        self.speed_run: int = self.model.speed_run
        self.speed: int = random.choice([self.speed_walk, self.speed_run])
        if self.model.race in [RaceEnum.animal, RaceEnum.monster]:
            self.speed = self.speed_walk

        # movement inertia
        self.force: int = 2000
        self.friction: int = -12
        self.acc: vec = vec(0, 0)
        self.vel: vec = vec(0, 0)

        # jump/fly physics
        self.up_force: int = 3200
        self.up_friction: int = -1
        self.up_acc: float = 0.0
        self.up_vel: float = 0.0

        self.jumping_offset: int = 0
        # flags set by key strokes - not real NPC states
        self.is_dead = False
        self.is_flying = False
        self.is_jumping = False
        self.is_stunned = False
        self.is_talking = False

        # general purpose custom event, action is defined by the payload passed to event
        self.custom_event_id: int  = pygame.event.custom_type()
        self.register_custom_event()

        # actual NPC state, mainly to determine type of animation and speed
        self.state: npc_state.NPC_State = npc_state.Idle()
        self.state.enter_time = self.scene.game.time_elapsed

        self.load_items()

    #############################################################################################################
    def select_next_item(self, filtered_items: list[ItemSprite] | None = None) -> None:
        if not filtered_items:
            filtered_items = self.items

        if len(filtered_items) > 0:
            if self.selected_item_idx < len(filtered_items):
                selected_item = filtered_items[self.selected_item_idx]
            else:
                selected_item = filtered_items[0]
            new_idx = filtered_items.index(selected_item) + 1
            self.selected_item_idx = 0 if new_idx >= len(filtered_items) else new_idx

    #############################################################################################################
    def select_prev_item(self, filtered_items: list[ItemSprite] | None = None) -> None:
        if not filtered_items:
            filtered_items = self.items

        if len(filtered_items) > 0:
            if self.selected_item_idx < len(filtered_items):
                selected_item = filtered_items[self.selected_item_idx]
            else:
                selected_item = filtered_items[0]
            new_idx = filtered_items.index(selected_item) - 1
            self.selected_item_idx = len(filtered_items) - 1 if new_idx < 0 else new_idx

    #############################################################################################################

    def register_custom_event(self) -> None:
        self.game.register_custom_event(self.custom_event_id, self.process_custom_event)

    #############################################################################################################

    def set_sprite_sheet_type(self, sprite_file_name: str) -> tuple[int, dict[str, list[tuple[int, int]]]]:
        return animation.set_sprite_sheet_type(self, sprite_file_name)

    #############################################################################################################

    def __hash__(self) -> int:
        return hash(self.name)

    #############################################################################################################

    def load_items(self) -> None:
        for item_name in self.model.items:
            item = self.scene.create_item(item_name, 0, 0, show=False)
            self.pick_up(item)

    #############################################################################################################

    @property
    def money_cap(self) -> int:
        """Ceiling the purse regenerates up to.

        `self.model` is this character's own deep copy, so `model.money` is the
        *live* purse and cannot serve as the baseline. The pristine config can:
        an unset `money_cap` means "whatever the CSV row starts you with".
        """
        cap = self.model.money_cap
        if cap > 0:
            return cap
        return self.game.conf.characters[self.config_key].money

    #############################################################################################################

    def regenerate_money(self, days: int = 1) -> None:
        """Refill the purse by a flat share of its ceiling per elapsed day.

        Linear growth with a ceiling has a closed form, which is what keeps this
        N-safe: coming back from a three-day trip is one call, not a loop over
        days. (A percentage compounded from the current amount would not be.)

        Emptying a merchant is therefore felt for a few days - at the default 25%
        a purse drained to zero needs four dawns to come back - which is the
        gentle nudge towards selling gradually, or to somebody else.
        """
        cap = self.money_cap
        per_day = round(cap * self.model.money_regen_pct)
        self.model.money = min(cap, self.model.money + days * per_day)

    #############################################################################################################

    def restock_items(self) -> None:
        """Dawn re-roll of the stock: back to the list from the config, nothing else.

        Whatever the player sold here is gone rather than resold. Keeping it would
        silt up `max_carry_weight` with the player's junk across sessions until the
        merchant permanently stopped buying.

        The money side of the day turn is `regenerate_money`, deliberately *not*
        the value of those items: the old `sell_all_bought_items` credited the
        merchant the full value of everything it had ever bought, so the purse only
        ever grew and the limit could never bite.
        """
        self.items = []
        # `total_items_weight` is a running total maintained by pick_up/drop_item, so
        # dropping the item list on the floor without zeroing it left every dawn's
        # stock weighing on top of the previous one - after a few days the merchant
        # was over `max_carry_weight` while visibly holding two gems, and refused to
        # buy anything ever again.
        self.total_items_weight = 0.0
        self.load_items()

    #############################################################################################################

    def load_dialogs(self) -> None:
        # dialog graph path (T-023): if the character config points at a
        # config_key, build the DialogNode graph and set the cursor to START_NODE.
        if self.model.has_dialog:
            dialog_config: dict[str, Any] = self.game.conf.dialogs.get(self.config_key, {})
            if dialog_config:
                from settings import IS_DEBUG_MODE
                nodes = init_dialog(dialog_config, debug=IS_DEBUG_MODE)
                self.dialog_nodes = nodes
                self.dialog = get_start_node(dialog_config, nodes)
                self.dialog_start_node = self.dialog
                self.has_dialog = True

    #############################################################################################################

    def apply_option_sentiment(self, option_sentiment: str) -> int:
        """Apply a dialog option's sentiment shift and reveal its weight.

        Returns the actual shift applied (after clamping).  The weight is
        recorded in ``known_disposition`` so future options with the same
        sentiment show their value instead of ``?``.
        """
        weight = self.disposition.get(option_sentiment, 0)
        self.sentiment = max(0, min(100, self.sentiment + weight))
        self.known_disposition[option_sentiment] = weight
        return weight

    def restore_dialog_state(self, dialog_state: "NPCDialogState") -> None:
        """Restore the conversation state from a save snapshot.

        Rebuilds the dialog graph if necessary, then applies the saved cursor,
        selected options, visited nodes, sentiment and discovered disposition.
        """
        if not self.model.has_dialog:
            return
        if self.dialog_nodes is None:
            self.load_dialogs()
        if self.dialog_nodes is None:
            return

        self.selected_options_dict = dict(dialog_state.selected_options)
        self.sentiment = dialog_state.sentiment
        self.known_disposition = dict(dialog_state.known_disposition)

        current_key = dialog_state.current_node_key
        if current_key and current_key in self.dialog_nodes:
            self.dialog = self.dialog_nodes[current_key]
        elif self.dialog is None:
            # Fallback to the graph entry node if the saved cursor is missing.
            dialog_config = self.game.conf.dialogs.get(self.config_key, {})
            if dialog_config:
                self.dialog = get_start_node(dialog_config, self.dialog_nodes)

        # Restore dialog_start_node (next conversation start, may differ from START_NODE)
        start_key = dialog_state.dialog_start_node_key
        if start_key and start_key in self.dialog_nodes:
            self.dialog_start_node = self.dialog_nodes[start_key]
        elif self.dialog_start_node is None:
            dialog_config = self.game.conf.dialogs.get(self.config_key, {})
            if dialog_config:
                self.dialog_start_node = get_start_node(dialog_config, self.dialog_nodes)

        for key, node in self.dialog_nodes.items():
            node.visited = dialog_state.visited_nodes.get(key, False)

        selected_options = dialog_state.selected_options
        for node in self.dialog_nodes.values():
            for opt in node.options:
                opt.selected = selected_options.get(opt.key, False)

    def reset_dialog(self) -> None:
        """Reset the dialog cursor to the start node for the next conversation."""
        if self.dialog_start_node is not None:
            self.dialog = self.dialog_start_node

    def apply_resume_node(self) -> None:
        """If the current dialog node has a resume_node, update dialog_start_node
        so the next conversation begins there instead of the original START_NODE.
        """
        if self.dialog is not None and self.dialog.resume_node and self.dialog_nodes:
            resume_key = self.dialog.resume_node
            if resume_key in self.dialog_nodes:
                self.dialog_start_node = self.dialog_nodes[resume_key]

    #############################################################################################################
    def generate_masks(self) -> None:
        animation.generate_masks(self)

    #############################################################################################################

    def create_health_bar(self) -> HealthBar:
        return HealthBar(self.name,
                         self.model,
                         self.game.render_text,
                         self.label_group,
                         vector_to_tuple(self.pos)
                         )

    #############################################################################################################
    def create_shadow(self) -> Shadow:
        empty: bool = False
        # TODO: add proper handling of shadows hiding when NPC is in water
        if "Fish" in self.model.name_EN:
            empty = True
        return Shadow(self.shadow_group, (0, 0), (TILE_SIZE - 2, 6), empty)

    #############################################################################################################
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name})"

    #############################################################################################################
    def get_tileset_coord(self, pos: vec | None = None, offset_y: int = -4) -> Point:
        """
        map position in world coordinates to tileset grid
        """
        if not pos:
            pos = self.pos

        # shift up by 4 pixels since perceived location is different than actual Sprite position on screen
        return Point(int(pos.x // TILE_SIZE), int((pos.y + offset_y) // TILE_SIZE))

    #############################################################################################################
    # MARK: animate
    def animate(self, state: str, dt: float, loop: bool = True) -> None:
        animation.animate(self, state, dt, loop)

    #############################################################################################################
    def get_direction_360(self) -> str:
        return movement.get_direction_360(self)

    #############################################################################################################

    def get_direction_RL(self, angle: float) -> str:
        return movement.get_direction_RL(self, angle)

    #############################################################################################################

    def get_direction_RDL(self, angle: float) -> str:
        return movement.get_direction_RDL(self, angle)

    #############################################################################################################

    def get_direction_RDLU(self, angle: float) -> str:
        return movement.get_direction_RDLU(self, angle)

    #############################################################################################################
    # MARK: schedule
    def update_schedule(self) -> None:
        """Point this character at whatever its routine says it should be doing.

        A goal provider, not a controller: the most it does is set `self.target`
        and ask the existing pathfinder for a route. Nothing here writes `vel`.

        Split in two on purpose. Crossing a slot boundary is rare and expensive
        (it resolves a destination and runs A*), so `_begin_slot` fires once, on
        the boundary. What the character does *after* it gets there - drift around
        a well, go to bed - has to be checked while it stands there, so
        `_continue_slot` runs every frame and is cheap when there is nothing to do.

        Every way of having no destination - no routine, no place named in the
        CSV, no such object on the map - ends the same way: the character is left
        exactly as it was, still walking its old Tiled polyline if it had one.
        That is what lets the village be mapped one place at a time.
        """
        routine_key = self.runtime.routine_key
        if not routine_key:
            return
        routine = self.scene.routines.routines.get(routine_key)
        if routine is None:
            return

        if self._schedule_jitter is None:
            self._schedule_jitter = slot_jitter(self.name, self.scene.routines.defaults.slot_jitter_minutes)

        minutes = self.scene.hour * 60 + self.scene.minute
        slot = current_slot(routine, minutes, self._schedule_jitter)
        if slot is None:
            return
        if slot != self._schedule_slot:
            self._schedule_slot = slot
            self._begin_slot(slot)
        self._continue_slot(slot)

    #############################################################################################################
    @property
    def is_travelling(self) -> bool:
        """On its way somewhere - either a path to walk or a target to reach."""
        return self.waypoints_cnt > 0 or self.target != vec(0, 0)

    #############################################################################################################
    def _begin_slot(self, slot: Slot) -> None:
        """React to a slot boundary: work out where to go, and start going."""
        # A new slot always ends the night, even before the character has walked
        # anywhere - waking up is not something it can be too far away to do.
        self.wants_to_sleep = False
        self._wander_anchor = None
        self._wander_next_time = 0.0
        self._idle_emoted = False

        destination = resolve_at(
            slot.at,
            destinations_of(self.model),
            self.scene.places,
            self.scene.waypoints,
            origin_map=self.origin_map,
            current_map=self.scene.current_map,
            # live read of the runtime flag from scene/debug_overlay.py, like
            # `debug()` below - a `from settings import` copy would never see
            # the ` / Z toggle
            warn=print if debug_overlay.SHOW_DEBUG_INFO else None,
        )
        self._schedule_destination = destination
        if destination is None:
            return

        if destination.map and destination.map != self.scene.current_map:
            # Target is on another map, resolved by name only - its pixels are not
            # loaded. Moving the character across maps is the cross-map tick's job
            # (Scene.update_routine_npcs); here there is nothing physical to do.
            return

        if destination.kind == "route":
            # `patrol`: hand the named polyline straight to the legacy waypoint
            # loop. `target` stays zero, which is exactly the flag that makes
            # `follow_waypoints` wrap around to the start instead of stopping - the
            # same mechanism the Tiled `waypoints` layer has always used.
            route = self.scene.waypoints.get(destination.name, ())
            if route:
                self.target = vec(0, 0)
                self.waypoints = route
                self.waypoints_cnt = len(route)
                self.current_waypoint_no = 0
            return

        place = vec(self.scene.places[destination.name])
        self._wander_anchor = place
        self.target = place
        self.find_path()

    #############################################################################################################
    def _continue_slot(self, slot: Slot) -> None:
        """What the character does once it has arrived. Cheap while it walks."""
        if self._schedule_destination is None or self.is_travelling:
            return

        if slot.activity == "sleep":
            # Only an opinion; `Scene.update_sleepers` is what takes the sprite out
            # of the world, and it is also what keeps consulting the schedule
            # afterwards - a sleeping character gets no update of its own, so it
            # could never wake itself.
            self.wants_to_sleep = True
        elif slot.activity == "wander":
            self._wander_step()
        elif slot.activity == "idle" and not self._idle_emoted:
            self._idle_emoted = True
            self.emote.set_temporary_emote("dots_anim", IDLE_EMOTE_DURATION)
        # `stand` and `patrol` need nothing here: one is standing still, and the
        # other never stops travelling, so it never reaches this line.

    #############################################################################################################
    def _wander_step(self) -> None:
        movement.wander_step(self)

    #############################################################################################################
    # MARK: movement
    def movement(self) -> None:
        movement.movement(self)

    #############################################################################################################
    def movement_animal(self) -> None:
        movement.movement_animal(self)

    #############################################################################################################

    def get_random_safe_pos(
        self,
        start_pos: vec,
        range: float = 1.0,
        check_exits: bool = True,
        check_allowed_zones: bool = True,
        allow_start_pos: bool = True,
    ) -> vec:
        return movement.get_random_safe_pos(
            self, start_pos, range, check_exits, check_allowed_zones, allow_start_pos)

    #############################################################################################################
    def check_waypoints_in_exit(self) -> None:
        movement.check_waypoints_in_exit(self)

    #############################################################################################################

    def check_pos_is_exit(self, target_vec: vec) -> bool:
        return movement.check_pos_is_exit(self, target_vec)

    #############################################################################################################

    def movement_monster(self) -> None:
        movement.movement_monster(self)

    #############################################################################################################
    def follow_waypoints(self) -> None:
        movement.follow_waypoints(self)

    #############################################################################################################
    def clear_waypoints(self) -> None:
        movement.clear_waypoints(self)

    #############################################################################################################
    def find_path(self) -> None:
        movement.find_path(self)

    def generate_waypoints_from_path(self, path: list[tuple[int, int]], start: tuple[int, int]) -> None:
        movement.generate_waypoints_from_path(self, path, start)

    #############################################################################################################
    def jump(self) -> None:
        movement.jump(self)

    #############################################################################################################
    # MARK: physics
    def physics(self, dt: float) -> None:
        movement.physics(self, dt)

    #############################################################################################################
    def change_state(self) -> None:
        if new_state := self.state.enter_state(self):
            new_state.enter_time = self.scene.game.time_elapsed
            # print(self.model.name_EN, new_state)
            self.state = new_state

    #############################################################################################################
    def set_entry_point(self, entry_point: str, default: vec) -> bool:
        return movement.set_entry_point(self, entry_point, default)

    #############################################################################################################
    def check_scene_exit(self) -> None:
        movement.check_scene_exit(self)

    #############################################################################################################

    def get_random_pos(self, x_tiles: float = 1.0, y_tiles: float = 1.0) -> vec:
        return movement.get_random_pos(self, x_tiles, y_tiles)

    #############################################################################################################
    def die(self, drop_items: bool = True) -> None:
        combat.die(self, drop_items)

    #############################################################################################################
    def update(self, dt: float) -> None:
        self.state.update(dt, self)
        self.change_state()

    #############################################################################################################

    def check_cooldown(self) -> None:
        combat.check_cooldown(self)

    #############################################################################################################

    def slide(self, colliders: list[Any]) -> None:
        movement.slide(self, colliders)

    #############################################################################################################
    # MARK: process_custom_event
    def process_custom_event(self, **kwargs: str) -> None:
        combat.process_custom_event(self, **kwargs)

    #############################################################################################################
    # MARK: encounter

    def encounter(self, oponent: "NPC") -> None:
        combat.encounter(self, oponent)

    #############################################################################################################
    # MARK: hit
    def hit(self, oponent: "NPC") -> None:
        combat.hit(self, oponent)

    #############################################################################################################
    def set_event_timer(self, npc: "NPC", action: NPCEventActionEnum, interval: int, repeat: int) -> None:
        combat.set_event_timer(self, npc, action, interval, repeat)

    #############################################################################################################
    def set_emote(self, emote: str) -> None:
        if self.has_dialog and str(self.state) in ["Idle", "Bored", "Walk", "Run"]:
            self.emote.set_emote("dots_anim")
        elif self.model.is_merchant and str(self.state) in ["Idle", "Bored", "Walk", "Run"]:
            self.emote.set_emote("$_anim")
        else:
            self.emote.set_emote(emote)

    #############################################################################################################
    def reset(self) -> None:
        self.shadow = self.create_shadow()
        self.emote = self.create_emote()
        self.health_bar = self.create_health_bar()
        self.is_attacking = False
        self.is_dead = False
        self.is_flying = False
        self.is_jumping = False
        self.is_stunned = False
        self.is_talking = False
        self.items = []
        self.selected_item_idx = -1
        self.load_items()
        self.model.health = self.model.max_health

    #############################################################################################################
    def create_emote(self) -> EmoteSprite:
        return EmoteSprite(self.scene.label_sprites, vector_to_tuple(self.pos), self.scene.icons)
    #############################################################################################################

    def move_back(self) -> None:
        movement.move_back(self)

    #############################################################################################################
    def adjust_rect(self) -> None:
        animation.adjust_rect(self)

    #############################################################################################################
    def debug(self, msgs: list[str]) -> None:
        if debug_overlay.SHOW_DEBUG_INFO:
            for i, msg in enumerate(msgs):
                self.game.render_text(msg, (0, settings.HEIGHT - 25 - i * 25))

    #############################################################################################################
    def pick_up(self, item: ItemSprite) -> bool:
        result: bool = False

        if item.model.type == ItemTypeEnum.money:
            self.model.money += item.model.value
            # self.items.append(item)
            result = True
        else:
            found = False
            for idx, owned_item in enumerate(self.items):
                if owned_item.name == item.name:
                    found = True
                    break

            if self.total_items_weight + item.model.weight <= self.model.max_carry_weight:
                if found:
                    self.total_items_weight += item.model.weight

                    # increase amount if already owned
                    self.items[idx].model.count += 1

                    result = True
                else:
                    # check if there are free slots
                    if len(self.items) < self.max_items:
                        # add new item if not owned
                        self.total_items_weight += item.model.weight

                        self.items.append(item)

                        # if it's the first owned item, set it as selected
                        if self.selected_item_idx < 0:
                            self.selected_item_idx = 0

                        result = True
                    else:
                        print(
                            f"\n[red]ERROR:[/] {self.name} All '[num]{self.max_items}[/num]'"
                            " items slots are taken!\n")
                        self.scene.add_notification(
                            _("notify.all_slots_taken", n=self.max_items),
                            scene.NotificationTypeEnum.failure)
            else:
                print(
                    f"\n[red]ERROR:[/] {self.name} Max carry weight "
                    f"'[num]{self.model.max_carry_weight:4.2f}[/num]' exceeded!\n")
                self.scene.add_notification(
                    _("notify.max_weight_exceeded", w=f"{self.model.max_carry_weight:4.2f}"),
                    scene.NotificationTypeEnum.failure)

        return result

    #############################################################################################################
    def get_tradable_items(self) -> list[ItemSprite]:
        items = self.items

        if self.npc_met:
            tradeable_items_types = self.npc_met.model.tradeable_items_types
            if tradeable_items_types:
                items = [item for item in items if item.model.type in tradeable_items_types]

        return items

    #############################################################################################################
    def can_buy(self) -> bool:
        if (
            not self.npc_met or not self.npc_met.items or self.npc_met.selected_item_idx < 0
        ):
            return False

        selected_item = self.npc_met.items[self.npc_met.selected_item_idx]
        price = int(round(selected_item.model.value * get_buy_price_multiplier(self.npc_met.sentiment)))

        if self.model.money < price:
            self.scene.add_notification(
                _("notify.cant_buy_money", name=entity_name(selected_item.model)),
                scene.NotificationTypeEnum.failure)
            return False

        if self.model.max_carry_weight < self.total_items_weight + selected_item.model.weight:
            self.scene.add_notification(
                _("notify.cant_buy_weight", name=entity_name(selected_item.model)),
                scene.NotificationTypeEnum.failure)
            return False

        found = False
        for owned_item in self.items:
            if owned_item.name == selected_item.name:
                found = True
                break

        if not found and len(self.items) == self.max_items:
            self.scene.add_notification(
                _("notify.cant_buy_slots", name=entity_name(selected_item.model)),
                scene.NotificationTypeEnum.failure)
            return False

        return True

    #############################################################################################################
    def can_sell(self) -> bool:
        # selected_item_idx indexes the *filtered* (tradable) list while selling, not
        # self.items - a type-restricted merchant (e.g. gems only) filters the player's
        # inventory, so validate against the same list the sell action uses.
        tradable = self.get_tradable_items()
        if (
            not tradable or self.selected_item_idx < 0 or self.selected_item_idx > len(
                tradable) - 1 or not self.npc_met
        ):
            return False

        selected_item = tradable[self.selected_item_idx]
        price = int(round(selected_item.model.value * get_sell_price_multiplier(self.npc_met.sentiment)))

        if self.npc_met.model.money < price:
            self.scene.add_notification(
                _("notify.merchant_cant_buy_money", name=entity_name(selected_item.model)),
                scene.NotificationTypeEnum.failure)
            return False

        if self.npc_met.model.max_carry_weight < self.npc_met.total_items_weight + selected_item.model.weight:
            self.scene.add_notification(
                _("notify.merchant_cant_buy_weight", name=entity_name(selected_item.model)),
                scene.NotificationTypeEnum.failure)
            return False

        found = False
        for owned_item in self.npc_met.items:
            if owned_item.name == selected_item.name:
                found = True
                break

        if not found and len(self.npc_met.items) == self.npc_met.max_items:
            self.scene.add_notification(
                _("notify.merchant_cant_buy_slots", name=entity_name(selected_item.model)),
                scene.NotificationTypeEnum.failure)
            return False

        return True

    #############################################################################################################
    def drop_item(self, show: bool = True, item: "ItemSprite | None" = None) -> "ItemSprite | None":
        if item is None:
            if (
                not self.items or self.selected_item_idx < 0 or self.selected_item_idx > len(self.items) - 1
            ):
                return None
            item = self.items[self.selected_item_idx]
        selected_item = item
        self.total_items_weight -= selected_item.model.weight  # * selected_item.model.count

        if selected_item.model.count > 1:
            org_item = selected_item
            org_item.model.count -= 1

            # selected_item = copy.copy(org_item)
            selected_item = self.scene.create_item(org_item.name, int(self.pos[0]), int(self.pos[1]), show=show)
            # selected_item.rect = org_item.rect.copy()
            # selected_item.model = copy.copy(org_item.model)
            # selected_item.model.count = 1
        else:
            # are we dropping currently selected weapon
            if selected_item.model.type == ItemTypeEnum.weapon and self.selected_weapon and \
                    self.selected_weapon.name == selected_item.name:
                self.selected_weapon = None

            self.items.remove(selected_item)

            if show:
                self.scene.item_sprites.add(selected_item)
                selected_item.rect.center = self.pos  # type: ignore[assignment]

            if self.selected_item_idx >= len(self.items):
                self.selected_item_idx -= 1
        # item = self.items.pop(-1)

        return selected_item
