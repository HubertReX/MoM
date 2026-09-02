"""API agenta testowego: deterministyczna nawigacja i otwieranie dialogów.

Moduł systemu wg B01 (D1): bezstanowe funkcje operujące na przekazanej scenie.
``Scene`` zachowuje delegaty ``agent_*`` - to kontrakt K3, wołany przez
``agent_ctrl.py`` i scenariusze testowe.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from maze_generator.maze_utils import TILE_SIZE

from settings import vec

if TYPE_CHECKING:
    from scene.scene import Scene


def find_entity(scene: "Scene", key: str) -> "Any | None":
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

    for name, npc in scene.loaded_NPCs.items():
        if name.lower() == k or name.lower().startswith(k) or _matches(npc):
            return npc
    # flattened rather than a tuple of the two lists: `list` is invariant, so
    # `(scene.items, scene.chests)` joins to plain `object` and stops being iterable
    # as far as the type checker is concerned
    for ent in [*scene.items, *scene.chests]:
        if _matches(ent):
            return ent
    return None


def walk_target(scene: "Scene", key: str) -> "vec | None":
    """Walkable world point next to entity ``key`` that the player can reach.

    Returns the centre of a walkable tile adjacent (8-neighbourhood) to the
    entity and reachable from the player via A*, or ``None`` if the entity is
    unknown or has no reachable adjacent tile ("brak ścieżki").
    """
    ent = find_entity(scene, key)
    if ent is None:
        return None
    return point_near(scene, getattr(ent, "pos", None))


def point_near(scene: "Scene", pos: "vec | None") -> "vec | None":
    """Walkable, player-reachable world point next to world ``pos`` (or ``pos``
    itself if already free). ``None`` when nothing adjacent is reachable."""
    if pos is None:
        return None
    from maze_generator.maze_utils import a_star_cached

    grid = scene.path_finding_grid
    rows, cols = len(grid), len(grid[0]) if grid else 0
    p_tile = scene.player.get_tileset_coord()
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


def walk_player_to(scene: "Scene", point: "vec") -> bool:
    """Send the player walking to ``point`` via the normal A* path. Returns
    ``True`` if a path was found (movement started), ``False`` otherwise."""
    scene.player.target = vec(point.x, point.y)
    scene.player.find_path()
    started = scene.player.waypoints_cnt > 0 or scene.player.target == vec(0, 0)
    if not started:
        scene.player.target = vec(0, 0)
    return started


def player_arrived(scene: "Scene") -> bool:
    """True when the player is no longer walking a queued path."""
    return scene.player.target == vec(0, 0) and scene.player.waypoints_cnt == 0


def open_dialog(scene: "Scene", key: str) -> bool:
    """Deterministically open ``key``'s dialog — no walking to a wandering NPC.

    NPCs random-walk, so ``walk_to_char`` + ``talk`` races the target. For a
    repeatable dialog screenshot this snaps the player next to the NPC and opens
    the panel through the game's own talk path (``npc_met`` + ``ui.open``).
    Returns ``True`` if a dialog panel was opened.

    The actual opening lives in ``scene/dialog_triggers.fire`` — the same call the
    map triggers use, so there is one way to start a conversation outside the
    SPACE path, not two that can drift apart.
    """
    from scene import dialog_triggers

    npc = find_entity(scene, key)
    if npc is None or getattr(npc, "dialog", None) is None:
        return False
    return dialog_triggers.fire(scene, npc)
