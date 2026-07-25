"""Obsługa akcji gracza: cały blok ``INPUTS`` z dawnego ``Scene.update``.

Moduł systemu wg B01 (D1/D4): bezstanowa funkcja ``handle(scene)`` wołana raz
na klatkę, po kolizjach. Mechanizm wejścia bez zmian - ``INPUTS`` to ten sam
współdzielony słownik z ``settings``, konsumowany przez ustawienie klucza na
``False`` po obsłużeniu.

Globale ``SHOW_DEBUG_INFO`` / ``USE_ALPHA_FILTER`` nadal MUSZĄ być przestawiane
w module ``scene.scene`` (kontrakt K9: ``help.py`` i ``characters.py`` czytają je
przez ``scene.<flaga>``, a ``Scene.draw`` przez własną globalną). Docelowo
przeprowadzka do ``scene/debug_overlay.py`` - krok 9 planu.
"""
from __future__ import annotations

import contextlib
from typing import Any, TYPE_CHECKING

from maze_generator.maze_utils import _TIMEIT_CACHE
from objects import ItemSprite, NotificationTypeEnum
from rich import print
from ui.panels.trade import TradePanel

from scene import world_clock
from settings import _, INPUTS, USE_AGENT_CONTROL, entity_name

if TYPE_CHECKING:
    from scene.scene import Scene


def handle(scene: "Scene") -> None:
    """Obsłuż wszystkie akcje gracza z tej klatki (kolejność jak w dawnym ``update``)."""
    player = scene.player

    # Esc opens the main menu *on top of* the running scene (not exit_state, which
    # would discard the game). The menu offers Continue (resume unchanged), so the
    # player can return to the exact game state.
    if INPUTS["quit"]:
        if not scene.ui.is_open(TradePanel):
            for fun, val in _TIMEIT_CACHE.items():
                cnt, time = val
                print(f"{fun};{cnt};{time:.10f};{time / cnt:.10f}")
            from ui.panels.main_menu import MainMenuScreen
            bg = getattr(scene.game, "menu_bg_image", None)
            MainMenuScreen(scene.game, "MainMenu", bg).enter_state()
            scene.game.reset_inputs()
        INPUTS["quit"] = False

    if INPUTS["debug"]:
        # flaga żyje w module scene.scene (K9) - patrz docstring modułu
        from scene import scene as scene_module
        scene_module.SHOW_DEBUG_INFO = not scene_module.SHOW_DEBUG_INFO
        INPUTS["debug"] = False

    if INPUTS["alpha"]:
        from scene import scene as scene_module
        scene_module.USE_ALPHA_FILTER = not scene_module.USE_ALPHA_FILTER
        INPUTS["alpha"] = False

    if INPUTS["next_day"]:
        # Debug-only, and deliberately so: left ungated this key is a free
        # merchant refill on demand, which makes any economy observation - mine
        # or the player's - meaningless. Gated on the *runtime* overlay flag
        # (` / Z) rather than `IS_DEBUG_MODE`, which is a hardcoded False that
        # nothing ever sets; SHOW_DEBUG_INFO is also exactly what the help panel
        # already uses to decide whether to advertise this key, so the two now
        # agree. `USE_AGENT_CONTROL` keeps it available to the agent-driven
        # tests, which skip a day on purpose and run without the overlay.
        from scene import scene as scene_module
        if scene_module.SHOW_DEBUG_INFO or USE_AGENT_CONTROL:
            # Advance the counter too. Firing the day turn while `scene.day` sat
            # still made the key lie in the other direction: merchants restocked
            # on a day that, as far as anything reading the clock was concerned,
            # had never happened.
            world_clock.next_day(scene)
        INPUTS["next_day"] = False

    if INPUTS["intro"]:
        scene.start_intro()
        INPUTS["intro"] = False

    # help (H / F1) is handled in GameUI.update: it is a modal panel now, so it
    # must be toggled before the scene freezes, not here.

    if INPUTS["show_ui"]:
        scene.display_ui_flag = not scene.display_ui_flag
        INPUTS["show_ui"] = False

    if INPUTS["use_item"]:
        if not player.is_talking:
            player.use_item()
        INPUTS["use_item"] = False

    for idx in range(1, player.max_items + 1):
        if INPUTS[f"item_{idx}"]:
            # tradable_items: list[ItemSprite] = []
            items: list[ItemSprite] = []
            # gracz albo kupiec, po którego ekwipunku właśnie chodzi hotbar;
            # wspólny typ to NPC, ale import characters tutaj zrobiłby cykl
            npc: Any = player
            if not player.is_talking:
                npc = player
                items = npc.items
            else:
                if player.npc_met and player.npc_met.model.is_merchant:
                    if scene.ui.is_buying:
                        npc = player.npc_met
                        items = npc.items
                    else:
                        npc = player
                        items = player.get_tradable_items()

            if idx - 1 < len(items):
                # selected_item = items[idx - 1]
                # npc.selected_item_idx = idx - 1
                npc.selected_item_idx = idx - 1  # npc.items.index(selected_item)
            INPUTS[f"item_{idx}"] = False

    if INPUTS["next_item"]:
        if not player.is_talking:
            player.select_next_item()
        else:
            if player.npc_met and player.npc_met.model.is_merchant:
                if scene.ui.is_buying:
                    player.npc_met.select_next_item()
                else:
                    filtered_items = player.get_tradable_items()
                    player.select_next_item(filtered_items)
        INPUTS["next_item"] = False

    if INPUTS["prev_item"]:
        if not player.is_talking:
            player.select_prev_item()
        else:
            if player.npc_met and player.npc_met.model.is_merchant:
                if scene.ui.is_buying:
                    player.npc_met.select_prev_item()
                else:
                    filtered_items = player.get_tradable_items()
                    player.select_prev_item(filtered_items)
        INPUTS["prev_item"] = False

    if INPUTS["drop"]:
        # drop item from inventory to ground
        if len(player.items) > 0 and not player.is_attacking and not \
                player.is_stunned and not player.is_talking:
            if item := player.drop_item():
                scene.items.append(item)
                scene.item_sprites.add(item)
                scene.group.add(item, layer=scene.sprites_layer - 1)
                # inventory changed: has_item()/item_count() conditions may flip
                scene.quests.on_event("item_dropped")

                # print(f"Dropped '[item]{item.name}[/item]' [[magenta]{item.model.type}[/magenta]]")
                scene.add_notification(
                    _("notify.dropped", name=entity_name(item.model)), NotificationTypeEnum.info)
            else:
                print("[red]ERROR![/red] No item to drop!")
        INPUTS["drop"] = False

    if INPUTS["pick_up"]:
        if not player.is_flying and not player.is_attacking and not player.is_stunned and \
                not player.is_talking:
            items = scene.item_sprites.sprites()
            collided_index = player.feet.collidelist(items)   # type: ignore[type-var]
            if collided_index > -1:
                item = items[collided_index]
                if player.pick_up(item):
                    scene.add_notification(_("notify.picked_up", name=entity_name(item.model)), NotificationTypeEnum.success)
                    with contextlib.suppress(KeyError):
                        # if scene.group.has(item):
                        scene.group.remove(item)
                        if item in scene.items:
                            scene.items.remove(item)
                        if item in scene.item_sprites:
                            scene.item_sprites.remove(item)
                    # inventory changed: has_item()/item_count() conditions may flip
                    scene.quests.on_event("item_picked_up")
                # else:
                #     print(f"You can't pick up '{item.model.name}' - it's too heavy.")
        INPUTS["pick_up"] = False

    if INPUTS["run"]:
        # toggle between run and walk
        if player.speed == player.speed_run:
            player.speed = player.speed_walk
        else:
            player.speed = player.speed_run
        INPUTS["run"] = False

    if INPUTS["jump"]:
        # player.is_jumping = not player.is_jumping
        if not player.is_flying and not player.is_attacking and \
            not player.is_stunned and not player.is_jumping and \
                not player.is_talking:
            player.is_jumping = True
            player.jump()
            # when airborn move one layer above so it's not colliding with obstacles on the ground
            scene.group.change_layer(player, scene.sprites_layer + 1)

        INPUTS["jump"] = False

    if INPUTS["fly"]:
        # toggle flying mode
        if not player.is_jumping and not player.is_attacking and not player.is_stunned and \
                not player.is_talking:
            player.is_flying = not player.is_flying
            if player.is_flying:
                # when airborn move one layer above so it's not colliding with obstacles on the ground
                scene.group.change_layer(player, scene.sprites_layer + 1)
            else:
                scene.group.change_layer(player, scene.sprites_layer)

        INPUTS["fly"] = False

    if INPUTS["menu"]:
        # next_scene = None #  scene # Scene(scene.game, "grasslands", "start")
        # AboutMenuScreen(scene.game, next_scene).enter_state()
        from ui.panels.main_menu import MainMenuScreen
        bg = getattr(scene.game, "menu_bg_image", None)
        MainMenuScreen(scene.game, "MainMenu", bg).enter_state()
        # scene.game.reset_inputs()
        INPUTS["menu"] = False

    # live reload map (R) - irreversible reset of the current map, so confirm first
    if INPUTS["reload"]:
        from ui.panels.main_menu import ConfirmMenuScreen
        ConfirmMenuScreen(
            scene.game,
            _("scene.reload_confirm"),
            scene._confirm_reload_map,
        ).enter_state()
        scene.game.reset_inputs()
        INPUTS["reload"] = False

    # camera zoom in/out
    if INPUTS["zoom_in"]:
        scene.camera.zoom += 0.25
        # scene.map_view.zoom = scene.camera.zoom
        INPUTS["zoom_in"] = False

    if INPUTS["zoom_out"]:
        scene.camera.zoom -= 0.25
        scene.camera.zoom = max(scene.camera.zoom, 0.25)
        # scene.map_view.zoom = scene.camera.zoom
        INPUTS["zoom_out"] = False
