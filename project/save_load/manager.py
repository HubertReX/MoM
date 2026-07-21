from __future__ import annotations

import contextlib
import copy
import time
from typing import TYPE_CHECKING, Any, cast

from enums import ItemTypeEnum
from objects import ItemSprite
from quest.entities import QuestState
from save_load.backends import FileSaveBackend, LocalStorageSaveBackend, SaveBackend
from save_load.models import (
    SAVE_VERSION,
    ChestState,
    GameClockState,
    GroundItemState,
    ItemState,
    MapState,
    NPCDialogState,
    NPCState,
    PlayerState,
    SaveGame,
    SaveMetadata,
    SaveSlot,
    SaveSlotInfo,
    sanitize_slot_name,
)
from settings import IS_WEB, MAX_HOTBAR_ITEMS_LIMIT, MAX_SAVE_SLOTS, USE_WEB_SIMULATOR

if TYPE_CHECKING:
    from game import Game
    from scene import Scene

import pygame
from pygame.math import Vector2 as vec


def _copy_item_model(item: Any) -> Any:
    if IS_WEB or not hasattr(item, "model_copy"):
        return copy.copy(item)
    return item.model_copy(deep=False)


class SaveManager:
    def __init__(self, game: Game) -> None:
        self.game = game
        self.backend: SaveBackend = self._create_backend()

    def _create_backend(self) -> SaveBackend:
        if IS_WEB and not USE_WEB_SIMULATOR:
            return LocalStorageSaveBackend()
        return FileSaveBackend()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, slot_idx: int, slot_name: str = "") -> bool:
        if slot_idx < 0 or slot_idx >= MAX_SAVE_SLOTS:
            print(f"[save] invalid slot index {slot_idx}")
            return False

        save_game = self._build_save_game()
        if save_game is None:
            return False

        # sanitize even the caller-supplied name so no flow can write a name that
        # breaks the save JSON / slot layout (defence in depth, see sanitize_slot_name)
        clean_name = sanitize_slot_name(slot_name)
        save_game.metadata.slot_name = clean_name or f"Slot {slot_idx + 1}"
        save_game.metadata.timestamp = time.time()

        slot = SaveSlot(
            slot_id=str(slot_idx),
            is_occupied=True,
            save_data=save_game,
        )
        return self.backend.write_slot(slot)

    def load(self, slot_idx: int) -> bool:
        if slot_idx < 0 or slot_idx >= MAX_SAVE_SLOTS:
            print(f"[save] invalid slot index {slot_idx}")
            return False

        slot = self.backend.read_slot(slot_idx)
        if slot is None or not slot.is_occupied or slot.save_data is None:
            print(f"[save] slot {slot_idx} is empty")
            return False

        save = slot.save_data
        if save.metadata.version != SAVE_VERSION:
            print(f"[save] version mismatch: save={save.metadata.version}, current={SAVE_VERSION}")
            return False

        self._apply_save_game(save)
        return True

    def list_slots(self) -> list[SaveSlotInfo | None]:
        return self.backend.list_slots()

    def delete_slot(self, slot_idx: int) -> bool:
        return self.backend.delete_slot(slot_idx)

    def rename_slot(self, slot_idx: int, new_name: str) -> bool:
        """Rename an occupied slot in place, without re-saving the live game state.

        Reads the slot, sanitizes ``new_name`` (see :func:`sanitize_slot_name`),
        swaps only ``metadata.slot_name`` and writes it back through the same backend
        used everywhere else (file on desktop, localStorage on web). Returns ``False``
        for an out-of-range or empty slot.
        """
        if slot_idx < 0 or slot_idx >= MAX_SAVE_SLOTS:
            print(f"[save] invalid slot index {slot_idx}")
            return False

        slot = self.backend.read_slot(slot_idx)
        if slot is None or not slot.is_occupied or slot.save_data is None:
            print(f"[save] slot {slot_idx} is empty, cannot rename")
            return False

        slot.save_data.metadata.slot_name = sanitize_slot_name(new_name)
        return self.backend.write_slot(slot)

    def find_first_free_slot(self) -> int | None:
        """Return the first unoccupied save slot index, or None if all are full."""
        slots = self.list_slots()
        for i in range(MAX_SAVE_SLOTS):
            info = slots[i]
            if info is None or not info.is_occupied:
                return i
        return None

    def find_oldest_occupied_slot(self) -> int | None:
        """Return the occupied slot index with the oldest timestamp, or None if all empty."""
        slots = self.list_slots()
        oldest_idx: int | None = None
        oldest_ts: float | None = None
        for i in range(MAX_SAVE_SLOTS):
            info = slots[i]
            if info is None or not info.is_occupied or info.metadata is None:
                continue
            ts = info.metadata.timestamp
            if oldest_ts is None or ts < oldest_ts:
                oldest_ts = ts
                oldest_idx = i
        return oldest_idx

    def should_autosave_on_map_change(self, was_maze: bool) -> bool:
        """Whether a map change should autosave slot 0.

        A dungeon run gets exactly one autosave: the step from the overworld into
        maze level 1. Descending further, climbing back up, and walking out to the
        surface all leave it alone, so slot 0 keeps pointing at the mouth of the
        dungeon instead of following the player around inside it.

        All three excluded cases share one property - the map being *left* is a
        maze - so that is the whole rule. Ordinary overworld map changes still
        autosave, and so does the overworld -> maze-level-1 step, because there the
        map being left is not a maze.
        """
        return not was_maze

    def pick_quick_save_slot(self) -> int | None:
        """Pick a slot for quick save: first free, falling back to oldest occupied."""
        free = self.find_first_free_slot()
        if free is not None:
            return free
        return self.find_oldest_occupied_slot()

    # ------------------------------------------------------------------
    # Build save game from live state
    # ------------------------------------------------------------------

    def _build_save_game(self) -> SaveGame | None:
        game = self.game
        if not game.states:
            return None

        from scene import Scene
        current_state = game.states[-1]
        if not isinstance(current_state, Scene):
            print("[save] current state is not a Scene, cannot save")
            return None

        scene: Scene = cast("Scene", current_state)

        player_state = self._build_player_state(scene)
        map_states = self._build_map_states(scene)
        clock_state = GameClockState(
            day=scene.day,
            hour=scene.hour,
            minute=scene.minute,
            time_elapsed=game.time_elapsed,
        )

        return SaveGame(
            metadata=SaveMetadata(playtime=game.time_elapsed),
            player=player_state,
            clock=clock_state,
            maps=map_states,
            quests=self._build_quest_state(scene),
        )

    def _build_quest_state(self, scene: Scene) -> dict[str, dict[str, Any]]:
        """Capture quest progress (decision D13)."""
        state = getattr(scene, "quest_state", None)
        return state.to_dict() if state is not None else {}

    def _build_player_state(self, scene: Scene) -> PlayerState:
        player = scene.player
        inventory = [
            ItemState(
                name=item.name,
                type=item.model.type,
                count=item.model.count,
                value=item.model.value,
                weight=item.model.weight,
                damage=item.model.damage,
                cooldown_time=int(item.model.cooldown_time),
                health_impact=item.model.health_impact,
            )
            for item in player.items
        ]
        return PlayerState(
            map_name=scene.current_map,
            entry_point=scene.entry_point,
            pos_x=player.pos.x,
            pos_y=player.pos.y,
            health=player.model.health,
            max_health=player.model.max_health,
            money=player.model.money,
            damage=player.model.damage,
            max_items=player.max_items,
            inventory=inventory,
            selected_weapon=player.selected_weapon.name if player.selected_weapon else None,
            selected_item_idx=player.selected_item_idx,
            is_flying=player.is_flying,
            is_jumping=player.is_jumping,
            is_dead=player.is_dead,
        )

    def _build_map_states(self, scene: Scene) -> dict[str, MapState]:
        maps: dict[str, MapState] = {}
        current_name = scene.current_map

        for map_name in list(scene.loaded_maps.keys()):
            if map_name == current_name:
                continue
            cached = scene.loaded_maps[map_name]
            maps[map_name] = MapState(
                name=map_name,
                npc_states=self._build_npc_states_from_cache(cached),
                chests=self._build_chest_states_from_cache(cached),
                ground_items=self._build_ground_items_from_cache(cached),
                destroyed_walls=self._build_destroyed_walls_from_cache(cached),
                maze_seed=cached.get("maze_seed"),
                maze_level=(cached.get("maze_stats") or {}).get("current_map_level"),
                maze_return_map=cached.get("return_map", "") or "",
                maze_return_entry_point=cached.get("return_entry_point", "") or "",
                dead_monsters=self._build_dead_monsters_from_cache(cached),
            )

        maps[current_name] = MapState(
            name=current_name,
            npc_states=self._build_npc_states(scene),
            chests=self._build_chest_states(scene),
            ground_items=self._build_ground_items(scene),
            destroyed_walls=self._build_destroyed_walls(scene),
            maze_seed=self._build_maze_seed(scene),
            maze_level=self._build_maze_level(scene),
            maze_return_map=getattr(scene, "return_map", "") if scene.is_maze else "",
            maze_return_entry_point=getattr(scene, "return_entry_point", "") if scene.is_maze else "",
            dead_monsters=self._build_dead_monsters(scene),
        )

        # Maps restored from a save but not re-entered yet have no live objects to
        # read, so carry their state through untouched. Without this, saving (and
        # every map change autosaves) would drop the progress of every map the
        # player has not revisited since loading.
        for name, state in (getattr(scene, "pending_map_states", None) or {}).items():
            if name not in maps:
                maps[name] = state

        return maps

    def _build_npc_states(self, scene: Scene) -> dict[str, NPCState]:
        return {
            npc.name: NPCState(
                name=npc.name,
                config_key=getattr(npc, "config_key", ""),
                attitude=npc.model.attitude,
                pos_x=npc.pos.x,
                pos_y=npc.pos.y,
                health=npc.model.health,
                money=npc.model.money,
                is_dead=npc.is_dead,
                inventory=[ItemState(
                    name=item.name,
                    type=item.model.type,
                    count=item.model.count,
                    value=item.model.value,
                    weight=item.model.weight,
                    damage=item.model.damage,
                    cooldown_time=int(item.model.cooldown_time),
                    health_impact=item.model.health_impact,
                ) for item in npc.items],
                dialog_state=self._build_npc_dialog_state(npc),
            )
            for npc in scene.NPCs
        }

    def _build_npc_dialog_state(self, npc: Any) -> NPCDialogState | None:
        """Capture the conversation state for an NPC, if it has a dialog graph."""
        has_dialog = getattr(npc.model, "has_dialog", False) if hasattr(npc, "model") else False
        dialog_nodes = getattr(npc, "dialog_nodes", None)
        if not has_dialog or dialog_nodes is None:
            return None
        current_node_key = npc.dialog.key if npc.dialog else ""
        visited_nodes = {key: True for key, node in dialog_nodes.items() if node.visited}
        start_node_key = npc.dialog_start_node.key if npc.dialog_start_node else ""
        return NPCDialogState(
            current_node_key=current_node_key,
            dialog_start_node_key=start_node_key,
            selected_options=dict(getattr(npc, "selected_options_dict", {})),
            visited_nodes=visited_nodes,
            sentiment=int(getattr(npc, "sentiment", 50)),
            known_disposition=dict(getattr(npc, "known_disposition", {})),
        )

    def _build_chest_states(self, scene: Scene) -> dict[str, ChestState]:
        return {
            chest.name: ChestState(
                name=chest.name,
                is_closed=chest.model.is_closed,
                items=list(chest.model.items),
            )
            for chest in scene.chests
        }

    def _build_ground_items(self, scene: Scene) -> list[GroundItemState]:
        return [
            GroundItemState(
                name=item.name,
                type=item.model.type,
                count=item.model.count,
                value=item.model.value,
                weight=item.model.weight,
                damage=item.model.damage,
                cooldown_time=int(item.model.cooldown_time),
                health_impact=item.model.health_impact,
                pos_x=item.rect.x,
                pos_y=item.rect.y,
            )
            for item in scene.items
        ]

    def _build_destroyed_walls(self, scene: Scene) -> list[tuple[int, int]]:
        """Read the list the scene keeps as destructibles are smashed.

        This used to be a diff between ``scene.walls`` and a snapshot of the
        "original" walls - but that snapshot was taken lazily on the first save,
        i.e. *after* the player had already been smashing bushes. The first save
        of every session therefore reported zero destroyed walls, and because the
        snapshot lived on the Scene (which outlives a map change) it also mixed
        up positions between maps.
        """
        return list(getattr(scene, "destroyed_walls", None) or [])

    def _build_maze_seed(self, scene: Scene) -> int | None:
        """The seed this maze level was actually generated from.

        Used to roll a *fresh* random number here, which made the field useless:
        nothing read it back, and had anything tried, it would have rebuilt a
        different dungeon than the one the player was standing in.
        """
        if not scene.is_maze:
            return None
        return scene.maze_seed

    def _build_maze_level(self, scene: Scene) -> int | None:
        if not scene.is_maze or not hasattr(scene, "maze_stats"):
            return None
        val = scene.maze_stats.get("current_map_level")
        return val if val is None else int(val)

    def _build_dead_monsters(self, scene: Scene) -> list[str]:
        return [npc.name for npc in scene.NPCs if npc.is_dead]

    def _build_npc_states_from_cache(self, cached: dict[str, Any]) -> dict[str, NPCState]:
        result: dict[str, NPCState] = {}
        for npc in cached.get("NPCs", []):
            result[npc.name] = NPCState(
                name=npc.name,
                config_key=getattr(npc, "config_key", ""),
                attitude=npc.model.attitude,
                pos_x=npc.pos.x,
                pos_y=npc.pos.y,
                health=npc.model.health,
                money=npc.model.money,
                is_dead=npc.is_dead,
                inventory=[ItemState(name=it.name, type=it.model.type, count=it.model.count)
                           for it in npc.items],
                dialog_state=self._build_npc_dialog_state(npc),
            )
        return result

    def _build_chest_states_from_cache(self, cached: dict[str, Any]) -> dict[str, ChestState]:
        return {
            chest.name: ChestState(
                name=chest.name,
                is_closed=chest.model.is_closed,
                items=list(chest.model.items),
            )
            for chest in cached.get("chests", [])
        }

    def _build_ground_items_from_cache(self, cached: dict[str, Any]) -> list[GroundItemState]:
        return [
            GroundItemState(
                name=it.name,
                type=it.model.type,
                count=it.model.count,
                value=getattr(it.model, "value", 0),
                weight=getattr(it.model, "weight", 0.0),
                damage=getattr(it.model, "damage", 0),
                cooldown_time=int(getattr(it.model, "cooldown_time", 0)),
                health_impact=getattr(it.model, "health_impact", 0),
                pos_x=it.rect.x,
                pos_y=it.rect.y,
            )
            for it in cached.get("items", [])
        ]

    def _build_destroyed_walls_from_cache(self, cached: dict[str, Any]) -> list[tuple[int, int]]:
        """Destroyed walls of a map the player left but has visited this session.

        Hard-coded to ``[]`` before, which threw away every bush and rock smashed
        on any map other than the one being saved on.
        """
        return [(int(x), int(y)) for x, y in cached.get("destroyed_walls", [])]

    def _build_dead_monsters_from_cache(self, cached: dict[str, Any]) -> list[str]:
        dead: list[str] = []
        for npc in cached.get("NPCs", []):
            if npc.is_dead:
                dead.append(npc.name)
        return dead

    # ------------------------------------------------------------------
    # Apply save game to live state
    # ------------------------------------------------------------------

    def _apply_save_game(self, save: SaveGame) -> None:
        game = self.game
        from scene import Scene

        if game.states:
            state = game.states[-1]
            if isinstance(state, Scene):
                state.exit_state()

        # A save can put the player inside a maze (entering one autosaves slot 0),
        # and a maze level is not read from a TMX - it is regenerated. Scene builds
        # its map in __init__, so `is_maze` and the seed have to be known now; a
        # moment later is too late.
        current_map_state = save.maps.get(save.player.map_name)
        maze_seed = current_map_state.maze_seed if current_map_state else None

        new_scene = Scene(
            game,
            save.player.map_name,
            save.player.entry_point,
            is_maze=maze_seed is not None,
            maze_seed=maze_seed,
            return_map=current_map_state.maze_return_map if current_map_state else "",
            return_entry_point=current_map_state.maze_return_entry_point if current_map_state else "",
        )
        new_scene.enter_state()

        self._apply_player_state(new_scene, save.player)
        self._apply_map_states(new_scene, save.maps)
        self._apply_game_clock(new_scene, save.clock)
        self._apply_quest_state(new_scene, save.quests)

    def _apply_quest_state(self, scene: Scene, quests: dict[str, dict[str, Any]]) -> None:
        """Restore quest progress, dropping quests the content no longer defines.

        Content changes between saves: `just import-quests` can rename or delete a
        quest, and a save written before that still names it. Such a key is
        ignored with a warning rather than killing the load — but it *is* logged,
        because a key nobody defines is usually a renamed quest, i.e. progress the
        player silently lost.

        The reverse (a quest defined but absent from the save) needs no handling:
        `QuestState.is_done` reads an unknown key as not done, which is exactly
        right for content added after the save was written.
        """
        state = QuestState.from_dict(quests)

        known = set(getattr(self.game.conf, "quests", None) or {})
        if known:
            unknown = set(state.entries) - known
            for key in unknown:
                del state.entries[key]
            if unknown:
                print(f"[save] ignoring {len(unknown)} unknown quest key(s): {sorted(unknown)}")

        scene.quest_state = state

    def _apply_player_state(self, scene: Scene, state: PlayerState) -> None:
        player = scene.player
        player.pos = vec(state.pos_x, state.pos_y)
        player.prev_pos = player.pos.copy()

        player.model.health = state.health
        player.model.max_health = state.max_health
        player.model.money = state.money
        player.model.damage = state.damage
        # clamped on the way in as well as on the way out: a save hand-edited to
        # 99 slots would otherwise draw a hotbar nobody can select from
        player.max_items = max(1, min(MAX_HOTBAR_ITEMS_LIMIT, state.max_items))
        player.is_flying = state.is_flying
        player.is_jumping = state.is_jumping
        player.is_dead = state.is_dead

        player.items.clear()
        player.selected_weapon = None
        player.selected_item_idx = -1

        item_conf = scene.game.conf.items

        sheet = scene.items_sheet
        for item_s in state.inventory:
            if item_s.name not in item_conf:
                continue
            model = _copy_item_model(item_conf[item_s.name])
            model.count = item_s.count
            image = sheet[item_s.name] if item_s.name in sheet else [pygame.Surface((1, 1))]
            sprite = ItemSprite(
                None, (0, 0), item_s.name, model,
                image=image,
            )
            player.items.append(sprite)

        if state.selected_weapon:
            for item in player.items:
                if item.name == state.selected_weapon:
                    player.selected_weapon = item
                    break

        if 0 <= state.selected_item_idx < len(player.items):
            player.selected_item_idx = state.selected_item_idx

        scene.camera.target = player.pos
        scene.group.center(scene.camera.target)

    def _apply_map_states(self, scene: Scene, maps: dict[str, MapState]) -> None:
        current_name = scene.current_map

        # Only the map the player saved on exists right now — the others have no
        # NPCs, chests or sprites to apply state to yet. Hold their state until
        # the player walks back into them (see `apply_pending_map_state`), rather
        # than dropping it: that drop is what silently reset every other map's
        # progress on load.
        scene.pending_map_states = {
            name: state for name, state in maps.items() if name != current_name
        }

        if current_name not in maps:
            return

        self._apply_one_map_state(scene, maps[current_name])

        scene.loaded_maps.clear()
        scene.store_map()

    def apply_pending_map_state(self, scene: Scene) -> None:
        """Apply the saved state of a map the player has just (re-)entered.

        Called from ``Scene.load_map`` once the map is built from its TMX but
        before it is cached. A map with no pending state (never visited, or
        already restored once) is left exactly as the TMX defines it.
        """
        pending: dict[str, Any] = getattr(scene, "pending_map_states", None) or {}
        ms = pending.pop(scene.current_map, None)
        if ms is None:
            return

        self._apply_one_map_state(scene, ms)

    def _apply_one_map_state(self, scene: Scene, ms: MapState) -> None:
        """Apply ``ms`` onto a map that has just been built from its TMX.

        Single implementation on purpose: this used to be two copies, and the
        copy that handled the current map forgot to clear the ground items —
        which is exactly how the duplication bug below survived.
        """
        self._apply_chest_states(scene, ms.chests)
        self._restore_ground_items(scene, ms.ground_items)
        self._apply_destroyed_walls(scene, ms.destroyed_walls)
        self._apply_npc_states(scene, ms)
        self._apply_maze_mobs(scene, ms)

    def _restore_ground_items(self, scene: Scene, items: list[GroundItemState]) -> None:
        """Make the map's ground items exactly what the save recorded.

        The map was just rebuilt from its TMX, which respawns every item the
        level designer placed — including the ones the player already picked up.
        The save is the authority on what is actually lying around, so replace
        rather than append.

        Appending is what shipped before: every save+load added another copy of
        every TMX item (4 -> 8 -> 12 on Village, compounding per cycle), and a
        picked-up item reappeared on the ground while staying in the player's
        bag — free duplication of quest items like MERMAIDS_TEAR.
        """
        self._clear_ground_items(scene)
        self._apply_ground_items(scene, items)

    def _clear_ground_items(self, scene: Scene) -> None:
        """Drop every ground item currently on the map (sprites included)."""
        for item in list(scene.items):
            with contextlib.suppress(KeyError):
                scene.group.remove(item)
            if item in scene.item_sprites:
                scene.item_sprites.remove(item)
        scene.items = []

    def _apply_chest_states(self, scene: Scene, chests: dict[str, ChestState]) -> None:
        chest_map = {c.name: c for c in scene.chests}
        for name, cs in chests.items():
            chest = chest_map.get(name)
            if chest is None:
                continue
            chest.model.items = list(cs.items)
            # go through open()/close() rather than poking `model.is_closed`:
            # the sprite picks its image in __init__ only, so setting the flag
            # alone left a looted chest drawn shut after every load
            if cs.is_closed:
                chest.close()
            else:
                chest.open()

    def _apply_ground_items(self, scene: Scene, items: list[GroundItemState]) -> None:
        item_conf = scene.game.conf.items
        for gis in items:
            if gis.name not in item_conf:
                continue
            model = _copy_item_model(item_conf[gis.name])
            model.count = gis.count
            sheet = scene.items_sheet
            image = sheet[gis.name] if gis.name in sheet else [pygame.Surface((1, 1))]
            sprite = ItemSprite(
                scene.item_sprites, (int(gis.pos_x), int(gis.pos_y)),
                gis.name, model, image=image,
            )
            scene.items.append(sprite)
            scene.group.add(sprite, layer=scene.sprites_layer - 1)

    def _apply_destroyed_walls(self, scene: Scene, destroyed: list[tuple[int, int]]) -> None:
        destroyed_set = set(destroyed)
        # the scene tracks this list itself now, so re-seed it - otherwise the next
        # save would only report what the player smashed *after* loading
        scene.destroyed_walls = list(destroyed_set)
        remaining: list[Any] = []
        for d in scene.destructibles:
            key = (d.wall.x, d.wall.y)
            if key in destroyed_set:
                d.kill()
                scene.obstacles_sprites.remove(d)
                scene.walls = [w for w in scene.walls if w.topleft != (d.wall.x, d.wall.y)]
                tile_x, tile_y = d.wall.x // 16, d.wall.y // 16
                grid = scene.path_finding_grid
                if 0 <= tile_y < len(grid) and 0 <= tile_x < len(grid[0]):
                    cost = getattr(d, "step_cost", -100)
                    grid[tile_y][tile_x] = cost
            else:
                remaining.append(d)
        scene.destructibles = remaining

    def _apply_npc_states(self, scene: Scene, ms: MapState) -> None:
        for npc in list(scene.NPCs):
            if npc.name in ms.dead_monsters:
                npc.is_dead = True
                npc.kill()
                if npc in scene.NPCs:
                    scene.NPCs.remove(npc)
                continue

            if npc.name in ms.npc_states:
                saved = ms.npc_states[npc.name]
                npc.model = _copy_item_model(npc.model)
                npc.model.health = saved.health
                npc.model.money = saved.money
                npc.pos = vec(saved.pos_x, saved.pos_y)
                npc.is_dead = saved.is_dead
                if saved.dialog_state is not None and hasattr(npc, "restore_dialog_state"):
                    npc.restore_dialog_state(saved.dialog_state)

    def _apply_maze_mobs(self, scene: Scene, ms: MapState) -> None:
        """Nothing to do: maze monsters are rebuilt by regenerating the level.

        Seeding the level's generator with `ms.maze_seed` puts the same monsters,
        of the same models, in the same cells, under the same names - so the
        health / position / dead state in `ms` is applied by `_apply_npc_states`
        like on any hand-made map. Kept as an explicit no-op so the next reader
        does not go looking for the missing maze branch.
        """

    def _apply_game_clock(self, scene: Scene, clock: GameClockState) -> None:
        scene.day = clock.day
        scene.hour = clock.hour
        scene.minute = clock.minute
        scene.minute_f = float(clock.minute)
        scene.game.time_elapsed = clock.time_elapsed
