"""Animacja postaci: sprite sheety, klatki, maski i ustawianie prostokątów.

Moduł systemu wg B01/D6: bezstanowe funkcje przyjmujące ``npc`` jawnie - klatki
(``animations``/``masks``/``frame_index``/``image``) zostają atrybutami
:class:`characters.npc.NPC`, a klasa ma tylko cienkie delegaty o niezmienionych
nazwach (kontrakt K3). ``load_sprites`` jest wołane z ``NPC.__init__`` - same
deklaracje atrybutów (dla mypy) zostają w ``__init__``.
"""
from typing import TYPE_CHECKING

import math

import pygame
from pygame.math import Vector2 as vec
from rich import print

from animation.transitions import AnimationTransition
from settings import (
    AVATAR_SCALE,
    CHARACTERS_DIR,
    PLAYER_CONFIG_KEY,
    SPRITE_SHEET_DEFINITION_4x7,
    SPRITE_SHEET_DEFINITIONS,
    STUNNED_COLOR,
    TILE_SIZE,
    WEAPON_DIRECTION_OFFSET,
    WEAPON_DIRECTION_OFFSET_FROM,
    import_sprite_sheet,
    lerp_vectors,
)

if TYPE_CHECKING:
    from characters.npc import NPC


def load_sprites(npc: "NPC") -> None:
    """Wczytaj sprite sheet postaci: klatki animacji, maski, avatar, pierwsza klatka."""
    tile_height = 16

    sprite_file_name = str(CHARACTERS_DIR / npc.model.sprite / "SpriteSheet.png")
    tile_width, sheet = npc.set_sprite_sheet_type(sprite_file_name)

    npc.animations = import_sprite_sheet(
        sprite_file_name,
        tile_width,
        tile_height,
        sprite_sheet_definition=sheet,
    )
    npc.avatar = pygame.image.load(str(CHARACTERS_DIR / npc.model.sprite / "Faceset.png")).convert_alpha()
    # Player avatar will be shown on the right side of the screen
    # and need to be flipped to face left
    if npc.config_key != PLAYER_CONFIG_KEY:
        npc.avatar = pygame.transform.flip(npc.avatar, True, False)

    npc.avatar = pygame.transform.scale(npc.avatar, (TILE_SIZE * AVATAR_SCALE, TILE_SIZE * AVATAR_SCALE))

    npc.generate_masks()
    npc.image = npc.animations["idle_down"][int(npc.frame_index)]
    npc.mask = npc.masks["idle_down"][int(npc.frame_index)]


###############################################################################################################
def set_sprite_sheet_type(npc: "NPC", sprite_file_name: str) -> tuple[int, dict[str, list[tuple[int, int]]]]:
    width = pygame.image.load(sprite_file_name).get_width()
    if width in SPRITE_SHEET_DEFINITIONS:
        sheet = SPRITE_SHEET_DEFINITIONS[width]["sheet"]
        tile_width = SPRITE_SHEET_DEFINITIONS[width]["tile_width"]
        npc.sprite_sheet_type = SPRITE_SHEET_DEFINITIONS[width]["type"]
    else:
        print(f"[red]ERROR![/] Unknown sprite sheet definitions width {width} for NPC {npc.name}")
        sheet = SPRITE_SHEET_DEFINITION_4x7
        npc.sprite_sheet_type = "4x7"
    return tile_width, sheet


###############################################################################################################
def generate_masks(npc: "NPC") -> None:
    # _mask = pygame.mask.from_surface(npc.image)
    for key, animation in npc.animations.items():
        masks = [pygame.mask.from_surface(frame) for frame in animation]
        npc.masks[key] = masks


###############################################################################################################
def animate(npc: "NPC", state: str, dt: float, loop: bool = True) -> None:
    npc.frame_index += dt

    if npc.frame_index >= len(npc.animations[state]):
        npc.frame_index = 0.0 if loop else len(npc.animations[state]) - 1.0

    npc.image = npc.animations[state][int(npc.frame_index)].copy()
    npc.mask = npc.masks[state][int(npc.frame_index)].copy()

    npc.emote.animate(dt)
    if npc.is_stunned:
        # npc.emote.set_emote("shocked_anim")
        red_filter = pygame.Surface(npc.image.get_size(), pygame.SRCALPHA)
        red_filter.fill(STUNNED_COLOR)
        # npc.image.blit(red_filter, (0, 0))
        # red_filter.blit(npc.image, (0, 0))
        # npc.image = red_filter

        value = math.sin(npc.game.time_elapsed * 200.0)
        value = 255 if value >= 0 else 0
        npc.image.set_alpha(value)
        if npc.selected_weapon and npc.selected_weapon.image:
            npc.selected_weapon.image.set_alpha(value)
    else:
        npc.image.set_alpha(255)
        if npc.selected_weapon and npc.selected_weapon.image:
            npc.selected_weapon.image.set_alpha(255)


###############################################################################################################
def adjust_rect(npc: "NPC") -> None:
    npc.tileset_coord = npc.get_tileset_coord()
    # display sprite n pixels above position so the shadow doesn't stick out from the bottom
    npc.rect.midbottom = npc.pos + vec(0,  -npc.jumping_offset - 3)  # type: ignore[union-attr, assignment]
    # 'hitbox' for collisions
    npc.feet.midbottom = vec(npc.pos[0], npc.pos[1])  # type: ignore[assignment]
    # shadow
    npc.shadow.rect.midbottom =  vec(npc.pos[0], npc.pos[1])  # type: ignore[assignment]
    npc.health_bar.rect.midtop =  vec(npc.pos[0], npc.pos[1])  # type: ignore[assignment]

    # if npc.emote:
    npc.emote.rect.midbottom = npc.rect.midtop
    # Bark siada NAD emote, nie zamiast niego: to dwa niezależne kanały ambientu
    # (H01/W2), a imię postaci jest pod nią, więc żaden z trzech napisów nie
    # zasłania pozostałych.
    npc.bark.rect.midbottom = npc.emote.rect.midtop

    if npc.selected_weapon and npc.is_attacking:
        direction = npc.get_direction_360()
        # how far between start attack time and weapon cooldown are we
        factor: float = max(0, npc.weapon_cooldown - npc.game.time_elapsed) / \
            (npc.weapon_cooldown - npc.attack_time)
        weapon_offset_from = WEAPON_DIRECTION_OFFSET_FROM[direction]
        weapon_offset_to = WEAPON_DIRECTION_OFFSET[direction]
        # smooth out the move using a transition function
        # shift by 0.5 to the weapon is moved away the farthest
        # in the middle of the transition
        # in_out_quad in_out_expo in_out_elastic in_out_back
        factor = AnimationTransition.in_out_elastic(1.0 - abs(factor - 0.5) * 2.0)
        offset = lerp_vectors(weapon_offset_from, weapon_offset_to, factor)
        npc.selected_weapon.rect.center = vec(npc.pos[0], npc.pos[1]) + offset   # type: ignore[assignment]
        npc.selected_weapon.image = npc.selected_weapon.image_directions[direction].copy()
        npc.selected_weapon.mask = npc.selected_weapon.masks[direction]
