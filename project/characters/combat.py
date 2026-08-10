"""Walka i śmierć postaci: starcia, obrażenia, ogłuszenie, cooldowny.

Moduł systemu wg B01/D6: bezstanowe funkcje przyjmujące ``npc`` jawnie - stan
(``model.health``, ``is_stunned``, ``is_attacking``, ``is_dead``) zostaje
atrybutem :class:`characters.npc.NPC` (kontrakt K1 save/load), a klasa ma tylko
cienkie delegaty o niezmienionych nazwach (kontrakt K3). Wywołania wewnątrz
modułu idą przez ``npc.<metoda>()``, więc podmiana metody na instancji w teście
nadal działa.
"""
from typing import TYPE_CHECKING

import pygame
from pygame.math import Vector2 as vec
from rich import print

import audio
from enums import AttitudeEnum, NPCEventActionEnum
from objects import NotificationTypeEnum
from settings import PLAYER_CONFIG_KEY, PUSHED_TIME, STUNNED_TIME

if TYPE_CHECKING:
    from characters.npc import NPC


def die(npc: "NPC", drop_items: bool = True) -> None:
    # `drop_items=False` to wyjście NPC-a z mapy, nie śmierć - nie ozwucza się.
    # Rozpisane na dwa `play_sfx`, a nie warunek w argumencie: walidator
    # `check_audio_manifest` czyta literały z nawiasu wywołania, więc każdy napis
    # w argumencie wyglądałby dla niego jak klucz eventu.
    if drop_items:
        if npc.config_key == PLAYER_CONFIG_KEY:
            audio.play_sfx("player_die")
        else:
            audio.play_sfx("monster_die")
    npc.scene.NPCs = [other for other in npc.scene.NPCs if other != npc]
    npc.shadow.kill()
    npc.health_bar.kill()
    npc.emote.kill()
    npc.bark.kill()

    # drop items and money on the ground
    if npc.config_key != PLAYER_CONFIG_KEY and drop_items:
        npc.is_dead = True
        # The line above is the only thing that makes this a *death* - an NPC
        # leaving the map via an exit also calls die(), but with drop_items=False.
        # Record it here so the save still knows about the kill after this sprite
        # is gone from scene.NPCs (see Scene.dead_monsters).
        npc.scene.note_monster_death(npc.name)

        for item in npc.items:
            npc.selected_item_idx = len(npc.items) - 1
            if npc.drop_item():
                item.rect.center = npc.get_random_safe_pos(
                    npc.pos, check_allowed_zones=False)  # type: ignore[assignment]
                npc.scene.items.append(item)
                npc.scene.item_sprites.add(item)
                npc.scene.group.add(item, layer=npc.scene.sprites_layer - 1)

        if npc.model.money >  0:
            pos: vec = npc.get_random_safe_pos(npc.pos, check_allowed_zones=False)  # type: ignore[assignment]
            item = npc.scene.create_item("golden_coin", int(pos[0]), int(pos[1]))
            item.model.value = npc.model.money
            npc.scene.items.append(item)
            npc.scene.item_sprites.add(item)
            npc.scene.group.add(item, layer=npc.scene.sprites_layer - 1)

    if npc.config_key == PLAYER_CONFIG_KEY and npc.model.health <= 0:
        npc.is_dead = True
        npc.scene.exit_state()
        from ui.panels.save_load import DeadState
        DeadState(npc.game).enter_state()

    npc.kill()


###############################################################################################################
def check_cooldown(npc: "NPC") -> None:
    if npc.is_attacking and npc.game.time_elapsed > npc.weapon_cooldown:
        npc.is_attacking = False
        npc.scene.group.remove(npc.selected_weapon)

    if not npc.can_switch_weapon and npc.game.time_elapsed > npc.switch_cooldown:
        npc.can_switch_weapon = True


###############################################################################################################
def process_custom_event(npc: "NPC", **kwargs: str) -> None:
    # if npc.config_key == PLAYER_CONFIG_KEY:
    #     print(kwargs["action"])

    action = kwargs.get("action", "")
    if action == NPCEventActionEnum.pushed:
        # pushed state is invalidated
        # show health bar
        npc.health_bar.hide()
    elif action ==  NPCEventActionEnum.stunned:
        # stunned state is invalidated
        # show health bar
        npc.health_bar.hide()
        npc.is_stunned = False
        if npc.model.health == 0:
            npc.die()

    elif action ==  NPCEventActionEnum.attacking:
        # attack cool off end
        npc.is_attacking = False
        npc.scene.group.remove(npc.selected_weapon)
    elif action ==  NPCEventActionEnum.switching_weapon:
        # switching weapon cool off end
        npc.can_switch_weapon = True
    else:
        print(f"unknown action '{action}' for npc '{npc.name}'")
        npc.scene.add_notification(
            f"unknown action '[act]{action}[/act]' for npc '[char]{npc.name}[/char]'", NotificationTypeEnum.debug)


###############################################################################################################
def encounter(npc: "NPC", oponent: "NPC") -> None:
    if oponent.model.attitude == AttitudeEnum.enemy:
        # deal damage
        npc.model.health -= oponent.model.damage
        if npc.selected_weapon:
            damage = npc.selected_weapon.model.damage
        else:
            damage = npc.model.damage
        oponent.model.health -= damage

        npc.model.health = max(0, npc.model.health)
        oponent.model.health = max(0, oponent.model.health)

        # w starciu obrywają obaj - liczy się ten, w którego skórze siedzi gracz
        # (rozpisane na dwie gałęzie z tego samego powodu, co w `die`)
        if npc.config_key == PLAYER_CONFIG_KEY:
            audio.play_sfx("player_hit")
        else:
            audio.play_sfx("monster_hit")

        # print(f"{npc.name}: {npc.model.health} opponent {oponent.name} {oponent.model.health}")
        if npc.model.health == 0:
            npc.die()

        # if oponent.model.health == 0:
        #     oponent.die()

        npc.is_stunned = True
        npc.set_event_timer(npc, NPCEventActionEnum.stunned, STUNNED_TIME, 1)
        npc.health_bar.show()

        oponent.is_stunned = True
        oponent.set_event_timer(oponent, NPCEventActionEnum.stunned, STUNNED_TIME, 1)
        oponent.emote.set_temporary_emote("fight_anim", 4.0)

        # show health bar (for STUNNED_TIME ms)
        # npc.health_bar.set_bar(npc.model.health / npc.model.max_health, npc.game)
        oponent.health_bar.show()

        # push the npc
        player_move = npc.pos - oponent.pos
        if not player_move == vec(0, 0):
            # npc.pos += player_move.normalize() * 8
            oponent.pos -= player_move.normalize() * 8

        # oponent_move = oponent.pos - oponent.prev_pos
        # if not oponent_move == vec(0, 0):
        #     oponent.pos += oponent_move.normalize() * TILE_SIZE
        npc.acc = vec(0, 0)
        oponent.acc = vec(0, 0)
        npc.adjust_rect()
        oponent.adjust_rect()
    else:
        # push the npc
        player_move = npc.pos - npc.prev_pos
        if player_move != vec(0, 0):
            # oponent.pos += player_move.normalize() * TILE_SIZE
            oponent.emote.set_temporary_emote("shocked_anim", 4.0)
        oponent.adjust_rect()

        npc.set_event_timer(npc,    NPCEventActionEnum.pushed, PUSHED_TIME, 1)
        oponent.set_event_timer(oponent, NPCEventActionEnum.pushed, PUSHED_TIME, 1)

        # show health bar (for PUSHED_TIME ms)
        # npc.health_bar.set_bar(npc.model.health / npc.model.max_health, npc.game)
        oponent.health_bar.show()


###############################################################################################################
def hit(npc: "NPC", oponent: "NPC") -> None:
    if oponent.model.attitude == AttitudeEnum.enemy and npc.is_attacking and npc.selected_weapon:
        # deal damage to oponent only since we hit wit weapon
        damage = npc.selected_weapon.model.damage
        oponent.model.health -= damage
        oponent.model.health = max(0, oponent.model.health)

        # trafienie bronią - obrywa tylko przeciwnik
        audio.play_sfx("monster_hit")

        # print(f"{npc.name}: {npc.model.health} opponent {oponent.name} {oponent.model.health}")
        # if oponent.model.health == 0:
        #     oponent.die()

        oponent.is_stunned = True
        oponent.set_event_timer(oponent, NPCEventActionEnum.stunned, STUNNED_TIME, 1)

        # show health bar (for STUNNED_TIME ms)
        # npc.health_bar.set_bar(npc.model.health / npc.model.max_health, npc.game)
        oponent.health_bar.show()

        # push the npc
        player_move = npc.pos - oponent.pos
        if not player_move == vec(0, 0):
            # npc.pos += player_move.normalize() * 8
            oponent.pos -= player_move.normalize() * 8

        # npc.acc = vec(0, 0)
        oponent.acc = vec(0, 0)
        # npc.adjust_rect()
        oponent.adjust_rect()
    # else:
    #     pass
        # push the npc
        # player_move = npc.pos - npc.prev_pos
        # if player_move != vec(0, 0):
        #     oponent.pos += player_move.normalize() * TILE_SIZE
        # oponent.adjust_rect()

        # npc.set_event_timer(npc,    NPCEventActionEnum.pushed, PUSHED_TIME, 1)
        # npc.set_event_timer(oponent, NPCEventActionEnum.pushed, PUSHED_TIME, 1)

        # # show health bar (for PUSHED_TIME ms)
        # npc.health_bar.set_bar(npc.model.health / npc.model.max_health, npc.game)
        # oponent.health_bar.set_bar(oponent.model.health / oponent.model.max_health, npc.game)


###############################################################################################################
def set_event_timer(npc: "NPC", target: "NPC", action: NPCEventActionEnum, interval: int, repeat: int) -> None:
    event = pygame.event.Event(target.custom_event_id, action=action)
    pygame.time.set_timer(event, interval, repeat)
