"""Kolizje w klatce: gracz vs ściany i NPC-e, broń vs NPC-e i destruktible,
skrzynia/NPC w zasięgu, ślizg NPC-ów po ścianach.

Moduł systemu wg B01 (D1): bezstanowa funkcja operująca na przekazanej scenie.
Świadomie JEDNA funkcja ``resolve`` bez podfunkcji per pętla - to hot path
wołany co klatkę (patrz benchmark ``scripts/bench_scene.py``), a rozbicie na
metody kosztowałoby więcej niż daje na czytelności.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import audio
from config_model.config import AttitudeEnum
from maze_generator.maze_utils import TILE_SIZE, clear_maze_cache
from objects import NotificationTypeEnum
from particles import ParticleDestructible

from settings import (
    _,
    CHEST_OPEN_DISTANCE,
    DESTRUCTIBLE_MIN_DAMAGE,
    FRIENDLY_WAKE_DISTANCE,
    entity_name,
)

if TYPE_CHECKING:
    from scene.scene import Scene


def resolve(scene: "Scene") -> None:
    """Rozwiąż wszystkie kolizje tej klatki (kolejność jak w dawnym ``Scene.update``)."""
    player = scene.player

    # check if the Player's feet are colliding with wall
    # Player must have a rect called feet, slide and move_back methods,
    # otherwise this will fail
    if player.feet.collidelist(scene.walls) > -1:
        # slide along wall or do a step_back
        player.slide(scene.walls)

    # check if the Player is colliding with an NPC
    if not player.is_flying:
        # sleepers are indoors and not drawn - walking through where they stood
        # is correct; bumping into an invisible body is not
        awake_NPCs = scene.awake_NPCs()
        # collision with body of NPC
        collided_index = player.feet.collidelist(awake_NPCs)  # type: ignore[type-var]
        if collided_index > -1 and not player.is_stunned:
            oponent = awake_NPCs[collided_index]
            # if player.mask.overlap(
            #     oponent.mask,
            #     (oponent.rect.x - player.rect.x, oponent.rect.y - player.rect.y)
            # ):

            # engage fight with enemy or push back friendly NPC
            player.encounter(oponent)
            # Ślizg TYLKO wtedy, gdy zderzenie dalej trwa. `encounter` rozsuwa
            # postacie (`push_apart`), a `slide` zaczyna od skasowania ruchu w osi
            # X - więc wołany bezwarunkowo zabierałby graczowi pół kroku nawet
            # wtedy, gdy droga jest już wolna.
            if player.feet.collidelist(awake_NPCs) > -1:  # type: ignore[type-var]
                # slide along wall or do a step_back
                player.slide(awake_NPCs)

        # collision of weapon with other NPC and destructibles
        if player.is_attacking and player.selected_weapon:
            # check collision with NPCs
            collided_index = player.selected_weapon.rect.collidelist(awake_NPCs)  # type: ignore[type-var]
            # collided with weapon rect
            if collided_index > -1:
                oponent = awake_NPCs[collided_index]
                # weapon rect is big, check if it collides with the mask of weapon
                if player.selected_weapon.mask.overlap(
                    oponent.mask,
                    (oponent.rect.x - player.selected_weapon.rect.x,  # type: ignore[union-attr]
                     oponent.rect.y - player.selected_weapon.rect.y)  # type: ignore[union-attr]
                ):
                    # deal damage with weapon to enemy or nothing if friendly NPC
                    player.hit(oponent)

            # check collision with destructibles
            collided_index = player.selected_weapon.rect.collidelist(
                scene.destructibles)  # type: ignore[type-var]

            if collided_index > -1:
                destructible = scene.destructibles[collided_index]
                # weapon rect is big, check if it collides with the mask of weapon
                if player.selected_weapon.mask.overlap(
                    destructible.mask,
                    (destructible.rect.x - player.selected_weapon.rect.x,  # type: ignore[union-attr]
                     destructible.rect.y - player.selected_weapon.rect.y)  # type: ignore[union-attr]
                ):
                    # too weak a weapon bounces off: tell the player *why* nothing
                    # happened, otherwise a destructible obstacle is indistinguishable
                    # from plain scenery.
                    min_damage = DESTRUCTIBLE_MIN_DAMAGE.get(destructible.type, 0)
                    if (player.selected_weapon.model.damage or 0) < min_damage:
                        # once per swing, not once per frame of the swing - the
                        # collision holds for the whole attack animation
                        if scene._weak_hit_notified_at != player.attack_time:
                            scene._weak_hit_notified_at = player.attack_time
                            scene.add_notification(
                                _("notify.weapon_too_weak",
                                  name=entity_name(player.selected_weapon.model)),
                                NotificationTypeEnum.warning)
                    else:
                        # make the tile walkable
                        x = int(destructible.rect.x // TILE_SIZE)
                        y = int(destructible.rect.y // TILE_SIZE)

                        scene.path_finding_grid[y][x] = destructible.step_cost
                        # unfortunately, the whole A* paths cache need to be recalculated
                        clear_maze_cache()
                        # destroy wall rect
                        wall = destructible.wall
                        scene.walls.remove(wall)
                        scene.destroyed_walls.append((wall.x, wall.y))
                        # trigger destruction particle system
                        rect = scene.map_view.translate_rect(destructible.rect)
                        particle = ParticleDestructible(scene.game.canvas, scene.group,
                                                        scene.camera, rect, destructible.type,
                                                        rng=scene._particle_rng())
                        particle.add()
                        scene.particles.append(particle)
                        # destroy object
                        destructible.kill()
                        scene.destructibles.remove(destructible)
                        audio.play_sfx("wall_smash")

    colliders = scene.walls
    # if player.is_flying:
    #     colliders = scene.walls
    # else:
    #     colliders = scene.walls + [player]

    player.chest_in_range = None
    for chest in scene.chests:
        # if player.feet.colliderect(chest.rect):
        distance_from_player = (chest.rect.center - player.pos).magnitude_squared()
        # chest_model = scene.game.conf.chests[chest]
        if distance_from_player < CHEST_OPEN_DISTANCE**2 and chest.model.is_closed:
            player.chest_in_range = chest
            break

    # Rozmówca jest przeliczany od zera co klatkę - z jednym wyjątkiem: gdy rozmowa
    # WŁAŚNIE się zaczęła. Wyzwalacz z mapy (`characters/player.check_scene_exit`)
    # odpala się w `group.update`, czyli PRZED tym miejscem, a rozmówcą bywa postać
    # spoza zasięgu (bramka przy wyjściu, głos zza kadru) - wyzerowanie `npc_met`
    # zabrałoby `GameUI` jedyny uchwyt do zdjęcia `is_talking` przy zamknięciu panelu
    # i rozmówca zostałby „zajęty" na zawsze. Od następnej klatki panel jest modalny,
    # więc `resolve` i tak tu nie dolatuje.
    talking = player.is_talking
    if not talking:
        player.npc_met = None
    for npc in scene.NPCs:
        if npc.is_asleep:
            # a shop that is not there cannot be walked into or traded with
            continue
        if not talking:
            npc.npc_met = None
        if npc.feet.collidelist(colliders) > -1:
            # npc.move_back(dt)
            npc.slide(colliders)

        distance_from_player = (npc.pos - player.pos).magnitude_squared()
        # enable talk to npc when player is near
        if npc.model.attitude == AttitudeEnum.friendly:
            if distance_from_player < FRIENDLY_WAKE_DISTANCE**2:
                npc.health_bar.show()

                if (npc.has_dialog and npc.dialog is not None) or (npc.model.is_merchant):
                    if not talking:
                        player.npc_met = npc
                        npc.npc_met = player
                    break
            else:
                npc.health_bar.hide()
