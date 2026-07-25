"""Cutscena intro: deklaratywny scenariusz kroków animacji kamery i czasu.

Moduł systemu wg B01 (D1): jedna funkcja ``start_intro(scene)`` budująca opis
kroków i oddająca go animatorowi. ``Scene.start_intro`` zostaje delegatem
(woła je klawisz z ``player_actions``).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from animation import animator
from settings import ZOOM_LEVEL, ZOOM_WIDE

if TYPE_CHECKING:
    from scene.scene import Scene


def start_intro(scene: "Scene") -> None:
    # MARK: start_intro

    scene.set_camera_free()
    # in_out_quad out_sine # in_out_elastic - anticipate and overshoot
    # in_out_back - anticipate # in_out_bounce - well, bouncy
    CAMERA_TRANSITION = "out_sine"

    waypoints = scene.waypoints["intro"]

    intro_cutscene = {
        "steps": [
            # ########## INITIAL SETUP #######################
            {
                "name": "step_01",
                "description": "move camera the big tree",
                "type": "animation",
                "target": scene.camera.target,
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
                "target": scene,
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
                "target": scene,
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
                "target": scene,
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
                "target": scene.camera,
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
                "target": scene.camera.target,
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
                "target": scene.camera.target,
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
                "target": scene.camera.target,
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
                "target": scene.camera.target,
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
                "target": scene.camera,
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
                "target": scene.camera.target,
                "args": {"x": scene.camera.target.x,  "y": scene.camera.target.y},
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
                "target": scene.camera.target,
                "args": {"x": scene.player.pos.x,  "y": scene.player.pos.y},
                "duration": 1.0,
                "transition": CAMERA_TRANSITION,
                "from": "step_07",
                "trigger": "on finish"
            },
            {
                "name": "step_08a",
                "description": "day time",
                "type": "animation",
                "target": scene,
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
                "target": scene.set_camera_on_player,
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
                "target": scene,
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
                "target": scene,
                "args": {"display_ui_flag": 1},
                "round_values": True,
                "duration": 0.1,
                "transition": "linear",
                "from": "step_10",
                "trigger": "on finish"
            },
        ]
    }
    animator(intro_cutscene, scene.animations)
