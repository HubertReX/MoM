from __future__ import annotations

import os
import random
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, cast

if TYPE_CHECKING:
    from second_order_dynamics import SecondOrderDynamics
    import ffmpeg
    from config_model.config_pydantic import update_config_schema

import pygame
import settings
from enums import TaskEnum
from maze_generator.maze_utils import timeit
from objects import NotificationTypeEnum
from PIL import Image
from rich import print, traceback
from settings import (  # LOGO_IMG,; ColorValue,
    ACTIONS,
    AGENT_INPUT_FILE,
    AGENT_SCREENSHOT_DIR,
    BG_COLOR,
    BLACK_COLOR,
    CONF_ENTITIES_TO_STORE,
    CONFIG_DIR,
    CONFIG_FILE,
    CUTSCENE_BG_COLOR,
    DEFAULT_SHADER,
    FONT_COLOR,
    FONT_SIZE_DEFAULT,
    FONT_SIZE_HUGE,
    FONT_SIZE_LARGE,
    FONT_SIZE_MEDIUM,
    FONT_SIZE_SMALL,
    FONT_SIZE_TINY,
    FPS_CAP,
    GAME_NAME,
    GAMEPAD_STEAM_DECK_CONTROL_NAMES,
    GAMEPAD_WEB_CONTROL_NAMES,
    GAMEPAD_XBOX_AXIS2ACTIONS,
    GAMEPAD_XBOX_BUTTON2ACTIONS,
    GAMEPAD_XBOX_CONTROL_NAMES,
    HEIGHT,
    HEIGHT_SCALED,
    HUD_DIR,
    INPUTS,
    IS_FULLSCREEN,
    IS_LINUX,
    IS_WEB,
    JOY_COOLDOWN,
    JOY_DRIFT,
    JOY_MOVE_MULTIPLIER,
    MAIN_FONT,
    MENU_FONT,
    MOUSE_CURSOR_IMG,
    PANEL_BG_COLOR,
    PROGRAM_ICON,
    RECORDING_FPS,
    SCREENSHOTS_DIR,
    SHADERS_NAMES,
    TEXT_ROW_SPACING,
    TILE_SIZE,
    TRANSPARENT_COLOR,
    UI_BORDER_COLOR,
    UI_BORDER_WIDTH,
    USE_AGENT_CONTROL,
    USE_CUSTOM_MOUSE_CURSOR,
    USE_SHADERS,
    USE_SOD,
    USE_WEB_SIMULATOR,
    WIDTH,
    WIDTH_SCALED,
    load_image,
    vec,
    vec3,
)

if USE_WEB_SIMULATOR:
    import pygbag.aio as asyncio
else:
    import asyncio

# if USE_SHADERS:
#     from opengl_shader import OpenGL_shader

if IS_WEB:
    from config_model.config import load_config
else:
    import ffmpeg
    from config_model.config_pydantic import (  # type: ignore[assignment]
        load_config,
        save_config,
        update_config_schema,
    )

if USE_SOD:
    from second_order_dynamics import SecondOrderDynamics

# 101 0017 # 106 0021 # 107 0030 no left down
seed = 107
random.seed(seed)
# np.random.seed(seed)
traceback.install(show_locals=True, width=150)

# os.environ["SDL_WINDOWS_DPI_AWARENESS"] = "permonitorv2"

#################################################################################################################


class Game:
    # MARK: Game
    def __init__(self, task: str, entities: list[str]) -> None:  # 1_004_511
        import platform

        if IS_WEB and not USE_WEB_SIMULATOR:
            self.log = platform.console.log  # type: ignore[attr-defined]
        else:
            self.log = print
        self.conf = load_config(CONFIG_FILE)

        # print(task, entities)
        if task == TaskEnum.store:
            self.store_config_to_csv(entities)
        elif task == TaskEnum.load:
            self.load_config_from_csv(entities)
        elif task == TaskEnum.update:
            update_config_schema()

        if task != TaskEnum.run:
            exit()

        pygame.init()

        # initialise the joystick module
        pygame.joystick.init()
        # https://www.codeproject.com/Articles/5298051/Improving-Performance-in-Pygame-Speed-Up-Your-Game
        # pygame.event.set_allowed([pygame.QUIT, pygame.KEYDOWN, pygame.KEYUP])

        # create empty list to store joysticks
        self.joysticks: dict[int, pygame.joystick.JoystickType] = {}
        self.is_joystick_in_use: bool = False
        self.joy_actions_cooldown: dict[str, float] = {}

        self.clock: pygame.time.Clock = pygame.time.Clock()
        # time elapsed in seconds (milliseconds as fraction) without pause time
        self.time_elapsed: float = 0.0

        self.set_display()

        self.rec_process: Any | None = None
        self.save_frame: bool = False

        self.fonts: dict[int, pygame.font.Font] = {}
        self.thin_fonts: dict[int, pygame.font.Font] = {}
        font_sizes = [FONT_SIZE_TINY, FONT_SIZE_SMALL, FONT_SIZE_MEDIUM, FONT_SIZE_LARGE, FONT_SIZE_HUGE]
        for font_size in font_sizes:
            self.fonts[font_size] = pygame.font.Font(MAIN_FONT, font_size)
            self.thin_fonts[font_size] = pygame.font.Font(MENU_FONT, font_size)

        self.font: pygame.Font = self.fonts[FONT_SIZE_DEFAULT]

        self.is_running: bool = True
        self.is_paused: bool = False

        # self.show_loading_screen()
        # if USE_SHADERS:
        #     size = self.screen.get_size()
        #     self.shader = OpenGL_shader(size, DEFAULT_SHADER)
        #     self.shader.create_pipeline()
        # self.loading_screen()

        if USE_CUSTOM_MOUSE_CURSOR:
            self.cursor_img: pygame.Surface = pygame.image.load(MOUSE_CURSOR_IMG)
            # scale_x = self.cursor_img.get_width() // TILE_SIZE
            # scale_y = self.cursor_img.get_height() // TILE_SIZE
            # self.cursor_img = pygame.transform.scale(cursor_img, (scale_x, scale_y)).convert_alpha()
            # self.cursor_img = pygame.transform.invert(self.cursor_img)
            # self.cursor_img.set_alpha(150)
            pygame.mouse.set_visible(False)

        # stacked game states (e.g. Scene, Menu)
        if TYPE_CHECKING:
            from agent_ctrl import AgentController
            from state import State
        self.states: list[State] = []
        # dict of custom events with callable functions
        # (not used for now since pygame.time.set_timer is not implemented in pygbag)
        self.custom_events: dict[int, Callable] = {}
        # moved imports here to avoid circular imports
        from ui.panels.main_menu import MainMenuScreen

        # bg_image = load_image(HUD_DIR / "main_menu_bg.png").convert_alpha()
        # bg_image = load_image(HUD_DIR / "big_tree_1600x1024.png").convert_alpha()
        bg_image = load_image(HUD_DIR / "Main_menu_bg-0001.png").convert_alpha()
        bg_image = pygame.transform.scale(bg_image, (WIDTH, HEIGHT))
        # logo_image = load_image(LOGO_IMG).convert_alpha()
        # logo_image = pygame.transform.scale_by(logo_image, 5)
        # bg_image.blit(logo_image, (WIDTH // 2, 100))
        from save_load.manager import SaveManager

        self.save_manager: SaveManager = SaveManager(self)

        start_state = MainMenuScreen(self, "MainMenu", bg_image)
        self.states.append(start_state)

        # external control & screenshots for AI agents (debug, opt-in)
        # - desktop: czytane z pliku (MOM_AGENT_CONTROL=1 env)
        # - web: czytane z window.localStorage['MoM.agent_control'] (runner Playwright)
        self.agent_ctrl: AgentController | None = None
        if USE_AGENT_CONTROL and not IS_WEB:
            from agent_ctrl import AgentController

            self.agent_ctrl = AgentController(AGENT_INPUT_FILE, AGENT_SCREENSHOT_DIR, log=self.log, web_mode=False)
            self.log("[agent_ctrl] external control ENABLED (desktop)")
        elif IS_WEB and not USE_WEB_SIMULATOR:
            web_agent_enabled = False
            try:
                from platform import window  # type: ignore[attr-defined]

                web_agent_enabled = window.localStorage.getItem("MoM.agent_control") == "1"
            except Exception:
                pass
            if web_agent_enabled:
                from agent_ctrl import AgentController

                self.agent_ctrl = AgentController(AGENT_INPUT_FILE, AGENT_SCREENSHOT_DIR, log=self.log, web_mode=True)
                self.log("[agent_ctrl] external control ENABLED (web)")

        # import scene
        # start_state = scene.Scene(self, "Village", "start")
        # start_state.enter_state()

        if USE_SOD:
            self.init_SOD()

    # #############################################################################################################
    def set_display(self) -> None:
        pygame.display.set_caption(GAME_NAME)
        program_icon = pygame.image.load(PROGRAM_ICON)
        pygame.display.set_icon(program_icon)

        # https://coderslegacy.com/python/pygame-rpg-improving-performance/
        self.flags: int = 0

        if IS_FULLSCREEN or settings._IS_FULLSCREEN:
            self.flags |= pygame.FULLSCREEN | pygame.DOUBLEBUF
        else:
            self.flags &= ~(pygame.FULLSCREEN | pygame.DOUBLEBUF)
            # hide title bar (can fit 2 more tiles vertically)
            # self.flags |= pygame.NOFRAME

        if USE_SHADERS:
            if IS_WEB:
                pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
                pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 0)
                pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_ES)
            else:
                pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
                pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
                pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
            pygame.display.gl_set_attribute(pygame.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG, True)
            # pygame.RESIZABLE , | pygame.SCALED
            self.flags = self.flags | pygame.OPENGL | pygame.DOUBLEBUF

        # final surface, after scaling up
        if IS_FULLSCREEN or settings._IS_FULLSCREEN:
            res = (0, 0)
        else:
            # Recalculate from saved display index — WIDTH_SCALED may have
            # been overwritten by the fullscreen (0,0) path above.
            _xt, _yt = settings.DISPLAY_RES_OPTIONS[settings._DISPLAY_RES_INDEX]
            res = (_xt * settings.TILE_SIZE, _yt * settings.TILE_SIZE)
            settings.WIDTH_SCALED, settings.HEIGHT_SCALED = res
            settings.SCALE = min(res[0] / settings.BASE_WIDTH, res[1] / settings.BASE_HEIGHT)
            # Clamp window size to desktop when returning from fullscreen
            if not IS_WEB:
                try:
                    _ds = pygame.display.get_desktop_sizes()
                    if _ds:
                        _dw, _dh = _ds[0]
                        if res[0] > _dw or res[1] > _dh:
                            res = (min(res[0], _dw), min(res[1], _dh))
                except Exception:
                    pass
        print(res)
        self.screen: pygame.Surface = pygame.display.set_mode(res, self.flags, vsync=0)
        # sync WIDTH_SCALED with actual screen size (important for fullscreen)
        if self.screen.get_size() != (settings.WIDTH_SCALED, settings.HEIGHT_SCALED):
            actual_w, actual_h = self.screen.get_size()
            settings.WIDTH_SCALED = actual_w
            settings.HEIGHT_SCALED = actual_h
            settings.SCALE = min(actual_w / settings.BASE_WIDTH, actual_h / settings.BASE_HEIGHT)
        if not IS_WEB:
            try:
                from pygame._sdl2.video import Window as _SDL2Win

                _sdl_win = _SDL2Win.from_display_module()
                if _sdl_win:
                    _ds = pygame.display.get_desktop_sizes()
                    if _ds:
                        _dw, _dh = _ds[0]
                        _ww, _wh = _sdl_win.size
                        if _ww <= _dw and _wh <= _dh:
                            _sdl_win.position = ((_dw - _ww) // 2, (_dh - _wh) // 2)
                        else:
                            _sdl_win.position = (0, 0)
            except Exception:
                pass
        # helper surface, before scaling up
        # , 32 .convert_alpha() # pygame.SRCALPHA
        self.canvas: pygame.Surface = pygame.Surface(
            (settings.WIDTH, settings.HEIGHT)
        )  # .convert_alpha()  # , self.flags)
        # helper surface for HUD
        self.HUD: pygame.Surface = pygame.Surface(
            (settings.WIDTH, settings.HEIGHT)
        ).convert_alpha()  # | pygame.SRCALPHA

        if not USE_SHADERS:
            # self.canvas = self.screen
            # self.HUD    = self.screen
            self.HUD = self.canvas

    # #############################################################################################################
    # def update_config_schema(self) -> None:
    #     update_schema()

    #############################################################################################################
    def store_config_to_csv(self, entities: list[str]) -> None:
        if "all" in entities:
            entities = list(CONF_ENTITIES_TO_STORE.keys())

        for entity_name in CONF_ENTITIES_TO_STORE:
            if entity_name in entities:
                file_name = CONFIG_DIR / f"{entity_name}.csv"
                print(f"[yellow]Storing[/] '{entity_name}' [yellow]to[/] '{file_name}'")
                entity_fields = CONF_ENTITIES_TO_STORE[entity_name]
                with open(file_name, "w") as f:
                    f.write(";".join(["key"] + entity_fields))
                    f.write("\n")
                    objects = getattr(self.conf, entity_name)
                    for key, object in objects.items():
                        values = [str(key)] + [str(getattr(object, field)) for field in entity_fields]
                        f.write(";".join(values))
                        f.write("\n")

    #############################################################################################################
    def load_config_from_csv(self, entities: list[str]) -> None:
        if "all" in entities:
            entities = list(CONF_ENTITIES_TO_STORE.keys())

        for entity_name in CONF_ENTITIES_TO_STORE:
            if entity_name in entities:
                file_name = CONFIG_DIR / f"{entity_name}.csv"
                print(f"[yellow]Loading[/] '{entity_name}' [yellow]from[/] '{file_name}'")
                # entity_fields = CONF_ENTITIES_TO_STORE[entity_name]
                with open(file_name, "r") as f:
                    data = f.readlines()
                objects = getattr(self.conf, entity_name)
                # skip "\n" at the end
                fields = data[0][:-1].split(";")
                for line in data[1:]:
                    # skip "\n" at the end
                    values = line[:-1].split(";")
                    key = values[0]
                    if entity_name == "maze_configs":
                        key = int(key)  # type: ignore[assignment]

                    if key in objects:
                        object = objects[key]
                        for i, value in enumerate(values[1:]):
                            # +1 to skip 'key' field
                            field: Any = getattr(object, fields[i + 1])
                            if type(field) is int:
                                setattr(object, fields[i + 1], int(value))
                            elif type(field) is float:
                                setattr(object, fields[i + 1], float(value))

        save_config(self.conf, CONFIG_DIR / "autogenerated_config.json")  # type: ignore[arg-type]

    #############################################################################################################
    def show_loading_screen(self) -> None:
        self.screen.fill(BG_COLOR)
        self.render_text(
            "Loading...",
            (WIDTH_SCALED // 2, HEIGHT_SCALED // 2),
            font_size=FONT_SIZE_HUGE,
            centred=True,
            bg_color=PANEL_BG_COLOR,
        )
        # if USE_SHADERS:
        #     self.shader.render(
        #         self.screen, self.HUD, [], 1.0, -1.0, 0.01,
        #         use_shaders=USE_SHADERS, save_frame=self.save_frame
        #     )
        pygame.display.flip()

    #############################################################################################################
    def init_SOD(self) -> None:
        # frequency, reaction speed and oscillation
        f = 0.01
        # zeta, damping factor
        z = 0.3
        # response, immediate, overshoot, anticipation
        r = -3.0
        self.sod_time = 0.01
        cursor_rect = self.cursor_img.get_frect(center=pygame.mouse.get_pos())
        pos = vec(cursor_rect.center)

        self.SOD = SecondOrderDynamics(f, z, r, x0=pos)

    #############################################################################################################
    def render_panel(self, rect: pygame.Rect, color: Any, surface: pygame.Surface | None = None) -> None:
        # MARK: render
        """
        Renders semitransparent (if `alpha` provided) rect using provided color on `game.HUD`

        Args:
            rect (pygame.Rect): Size and position of panel
            color (ColorValue): color to fill in the panel (with alpha)
            surface (pygame.Surface): surface to blit on. Defaults to None
        """
        if not surface:
            surface = self.HUD

        surf = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(surf, color, surf.get_rect())
        pygame.draw.rect(surf, UI_BORDER_COLOR, surf.get_rect(), width=UI_BORDER_WIDTH)
        surface.blit(surf, rect)

    #############################################################################################################
    def render_texts(
        self,
        texts: list[str],
        pos: tuple[int, int],
        color: Any = FONT_COLOR,
        bg_color: Any = 0,
        shadow: Any = CUTSCENE_BG_COLOR,
        font_size: int = 0,
        thin_fonts: bool = False,
        centred: bool = False,
        surface: pygame.Surface | None = None,
    ) -> None:
        """
        Blit several lines of text on surface or on `game.HUD` if surface is not provided, one under other,

        Args:
            texts (list[str]): list of strings to render
            pos (tuple[int, int]): position of first row
            color (ColorValue, optional): text color. Defaults to `FONT_COLOR`.
            bg_color (ColorValue, optional): draw background panel. Defaults to `0` == no bg.
            shadow (ColorValue, optional): draw outline of text with black color. Defaults to `CUTSCENE_BG_COLOR`.
            font_size (int, optional): font size from `FONT_SIZES_DICT` list. Defaults to `0` == `FONT_SIZE_DEFAULT`
            centred (bool, optional): shell the text be centered at `pos`. Defaults to `False`.
            surface (pygame.Surface, optional): surface to blit on, if `None` user `game.HUD`. Defaults to `None`.
        """

        for line_no, text in enumerate(texts):
            if font_size == 0:
                font_size = FONT_SIZE_SMALL
            new_pos = (pos[0], pos[1] + int(line_no * font_size * TEXT_ROW_SPACING))
            self.render_text(text, new_pos, color, bg_color, shadow, font_size, thin_fonts, centred, surface)

    #############################################################################################################
    def render_text(
        self,
        text: str,
        pos: tuple[int, int],
        color: Any = FONT_COLOR,
        bg_color: Any = 0,
        shadow: Any = CUTSCENE_BG_COLOR,
        font_size: int = 0,
        thin_fonts: bool = False,
        centred: bool = False,
        surface: pygame.Surface | None = None,
    ) -> None:
        """
        Blit line of text on `surface` or on `game.HUD` if `surface` is not provided

        Args:
            text (str): _description_
            pos (tuple[int, int]): _description_
            color (ColorValue, optional): _description_. Defaults to `FONT_COLOR`.
            bg_color (ColorValue, optional): _description_. Defaults to `0` == no bg.
            shadow (ColorValue, optional): _description_. Defaults to `CUTSCENE_BG_COLOR`.
            font_size (int, optional): _description_. Defaults to `0` == `FONT_SIZE_DEFAULT`.
            centred (bool, optional): _description_. Defaults to `False`.
            surface (pygame.Surface, optional): _description_. Defaults to `None`.
        """

        if not surface:
            surface = self.HUD

        if thin_fonts:
            font_type = self.thin_fonts
        else:
            font_type = self.fonts

        if font_type.get(font_size, False):
            selected_font = font_type[font_size]
        else:
            selected_font = self.font

        surf: pygame.surface.Surface = selected_font.render(text, False, color)
        rect: pygame.Rect = surf.get_rect(center=pos) if centred else surf.get_rect(topleft=pos)

        # alpha blend semitransparent rect in background 8 pixels bigger than rect
        # works well for single line of text
        if bg_color:
            bg_rect: pygame.Rect = rect.copy().inflate(18, 18).move(-4, -4)
            bg_surf = pygame.Surface(bg_rect.size)  # pygame.SRCALPHA
            pygame.draw.rect(bg_surf, bg_color, bg_surf.get_rect())
            surface.blit(bg_surf, bg_rect)

        # add black outline (render black text moved by offset to all 8 directions)
        if shadow:
            surf_shadow: pygame.surface.Surface = selected_font.render(text, False, shadow)
            offset = 1
            surface.blit(surf_shadow, (rect.x - offset, rect.y))
            surface.blit(surf_shadow, (rect.x + offset, rect.y))
            surface.blit(surf_shadow, (rect.x, rect.y - offset))
            surface.blit(surf_shadow, (rect.x, rect.y + offset))

            surface.blit(surf_shadow, (rect.x + offset, rect.y + offset))
            surface.blit(surf_shadow, (rect.x - offset, rect.y - offset))
            surface.blit(surf_shadow, (rect.x + offset, rect.y - offset))
            surface.blit(surf_shadow, (rect.x - offset, rect.y + offset))

        surface.blit(surf, rect)

    #############################################################################################################
    def custom_cursor(self, screen: pygame.Surface) -> None:
        """
        blit custom cursor in mouse current position if USE_CUSTOM_MOUSE_CURSOR is enabled
        """
        if not USE_CUSTOM_MOUSE_CURSOR:
            return

        cursor_rect = self.cursor_img.get_frect(center=pygame.mouse.get_pos())

        if USE_SOD:
            pos = vec(cursor_rect.center)
            if self.time_elapsed - self.sod_time > 3:
                self.sod_time = self.time_elapsed + 0.01
                self.SOD.reset(pos)

            res = self.SOD.update(
                self.time_elapsed - self.sod_time,
                pos,
            )
            res[0] = max(0, res[0])
            res[1] = max(0, res[1])

            res[0] = min(WIDTH - 8, res[0])
            res[1] = min(HEIGHT - 8, res[1])
            screen.blit(self.cursor_img, res)
        else:
            screen.blit(self.cursor_img, cursor_rect.center)

    #############################################################################################################
    def get_images(self, path: str) -> list[pygame.Surface]:
        """
        Gets a list of images from the specified path.

        Args:
            path (str): The directory path to load the images from.
            *: Additional keyword arguments, currently ignored.

        Returns:
            list[pygame.Surface]: A list of pygame.Surface objects representing the loaded images.
        """
        images = []
        for file in os.listdir(path):
            full_path = os.path.join(path, file)
            # img = pygame.image.load(full_path).convert_alpha()
            img = pygame.image.load(full_path)
            images.append(img)

        return images

    #############################################################################################################

    def add_notification_dummy(self, text: str, type: NotificationTypeEnum = NotificationTypeEnum.info) -> None:
        pass

    #############################################################################################################

    def save_screenshot(self, add_notification: Callable, data: bytes | None = None) -> bool:
        """
        save current screen to SCREENSHOT_FOLDER as PNG with timestamp in name
        """
        if not USE_SHADERS:
            INPUTS["screenshot"] = False
            self.save_frame = False

            time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = SCREENSHOTS_DIR / f"screenshot_{time_str}.png"
            os.makedirs(file_name.parent, exist_ok=True)
            pygame.image.save(self.canvas, file_name)
            if IS_WEB:
                import platform

                platform.window.download_from_browser_fs(  # type: ignore[attr-defined]
                    file_name.as_posix(), "image/png"
                )
            else:
                self.log(f"screenshot saved to file '{file_name}'")
            if ".." in str(file_name):
                short_name = str(file_name).split("..")[-1]
            else:
                short_name = str(file_name)
            add_notification(f"screenshot saved to file '[u]{short_name}[/u]'", NotificationTypeEnum.info)

            return True

        if self.save_frame and data:
            # in previous loop, frame was saved back to screen
            # so now we can store it and disable frame saving
            self.save_frame = False
            INPUTS["screenshot"] = False

            time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = SCREENSHOTS_DIR / f"screenshot_{time_str}.png"
            os.makedirs(file_name.parent, exist_ok=True)
            # pygame.image.save(self.screen, file_name)
            Image.frombuffer("RGBA", (WIDTH, HEIGHT), data, "raw", "RGBA", 0, -1).save(file_name)
            if IS_WEB:
                import platform

                platform.window.download_from_browser_fs(  # type: ignore[attr-defined]
                    file_name.as_posix(), "image/png"
                )
            else:
                self.log(f"screenshot saved to file '{file_name}'")
            if ".." in str(file_name):
                short_name = str(file_name).split("..")[-1]
            else:
                short_name = str(file_name)
            add_notification(f"screenshot saved to file '[u]{short_name}[/u]'", NotificationTypeEnum.info)

            return True
        else:
            # next frame rendered by pipeline needs to be saved back to screen
            self.save_frame = True
            return False

    #############################################################################################################

    def unregister_custom_events(self) -> None:
        self.custom_events = {}

    #############################################################################################################

    def register_custom_event(self, custom_event_id: int, handle_function: Callable) -> None:
        """
        Registers a custom event with a specific ID and associates it with a handler function.

        Args:
            custom_event_id (int): A unique integer identifier for the custom event.
            handle_function (callable): A function that will be called when the custom event is triggered.

        """

        if custom_event_id in self.custom_events:
            del self.custom_events[custom_event_id]
            # self.custom_events.pop(custom_event_id, None)

        self.custom_events[custom_event_id] = handle_function

    #############################################################################################################
    def get_inputs(self) -> list[pygame.event.EventType]:
        # MARK: get_inputs
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                self.is_running = False
                # pygame.quit()
                # sys.exit()

            # global IS_PAUSED

            if event.type in [pygame.WINDOWHIDDEN, pygame.WINDOWMINIMIZED, pygame.WINDOWFOCUSLOST]:
                self.is_paused = True
                self.log(f"{self.is_paused=}")

            elif event.type in [
                pygame.WINDOWSHOWN,
                pygame.WINDOWMAXIMIZED,
                pygame.WINDOWRESTORED,
                pygame.WINDOWFOCUSGAINED,
            ]:
                self.is_paused = False
                # print(f"{self.is_paused=}")
            elif event.type in self.custom_events:
                handler = self.custom_events[event.type]
                handler(**event.dict)
            elif event.type == pygame.KEYDOWN:
                self.is_joystick_in_use = False
                for action, definition in ACTIONS.items():
                    if event.key in definition["keys"]:
                        INPUTS[action] = True
            elif event.type == pygame.KEYUP:
                self.is_joystick_in_use = False
                for action, definition in ACTIONS.items():
                    if event.key in definition["keys"]:
                        INPUTS[action] = False

            elif event.type == pygame.MOUSEWHEEL:
                if event.y == 1:
                    INPUTS["scroll_up"] = True
                    INPUTS["zoom_in"] = True
                elif event.y == -1:
                    INPUTS["scroll_down"] = True
                    INPUTS["zoom_out"] = True

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    INPUTS["left_click"] = True
                elif event.button == 3:
                    INPUTS["right_click"] = True
                elif event.button == 4:
                    INPUTS["scroll_click"] = True

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    INPUTS["left_click"] = False
                elif event.button == 3:
                    INPUTS["right_click"] = False
                elif event.button == 4:
                    INPUTS["scroll_click"] = False

            elif event.type == pygame.JOYDEVICEADDED:
                joy = pygame.joystick.Joystick(event.device_index)
                self.joysticks[joy.get_instance_id()] = joy
                self.is_joystick_in_use = True
            elif event.type == pygame.JOYDEVICEREMOVED:
                del self.joysticks[event.instance_id]
                self.is_joystick_in_use = False

        for joystick in self.joysticks.values():
            for i in range(joystick.get_numbuttons()):
                if joystick.get_button(i):
                    self.log(f"{i} pressed")
                    self.is_joystick_in_use = True
                    break
            else:
                for i in range(joystick.get_numaxes()):
                    if joystick.get_axis(i) > JOY_DRIFT:
                        self.is_joystick_in_use = True
                        break
            break

        if self.is_joystick_in_use:
            for joystick in self.joysticks.values():
                if IS_WEB:
                    gamepad_controls = GAMEPAD_WEB_CONTROL_NAMES
                elif IS_LINUX:
                    gamepad_controls = GAMEPAD_STEAM_DECK_CONTROL_NAMES
                else:
                    gamepad_controls = GAMEPAD_XBOX_CONTROL_NAMES

                for button_name, action in GAMEPAD_XBOX_BUTTON2ACTIONS.items():
                    # print(f"{button_name=}")
                    pressed = joystick.get_button(gamepad_controls["buttons"][button_name])
                    # if pressed:
                    #     print(f"{button_name} pressed")

                    if not pressed:
                        INPUTS[action] = pressed
                    elif self.time_elapsed - self.joy_actions_cooldown.get(action, 0.0) >= JOY_COOLDOWN:
                        self.joy_actions_cooldown[action] = self.time_elapsed
                        INPUTS[action] = pressed
                        # joystick.get_button(b2a["buttons"][button_name])

                for axis_name, actions in GAMEPAD_XBOX_AXIS2ACTIONS.items():
                    value = joystick.get_axis(gamepad_controls["axis"][axis_name])
                    if abs(value) > JOY_DRIFT:
                        if value > 0.0:
                            # e.g. left/up
                            INPUTS[actions[0]] = False
                            # eg. right/down
                            INPUTS[actions[1]] = True
                            INPUTS[f"{actions[1]}_value"] = abs(value)
                        else:
                            INPUTS[actions[0]] = True
                            INPUTS[f"{actions[0]}_value"] = abs(value)
                            INPUTS[actions[1]] = False

        global USE_SHADERS
        # global IS_PAUSED
        if INPUTS["pause"]:
            # IS_PAUSED = not IS_PAUSED
            self.is_paused = not self.is_paused
            self.log(f"{self.is_paused=}")
            INPUTS["pause"] = False

        # if INPUTS["record"]:
        #     if not IS_WEB:
        #         if not self.save_frame:
        #             self.start_recording()
        #         else:
        #             self.save_recording()
        #     INPUTS["record"] = False

        if INPUTS["screenshot"] and USE_SHADERS:
            state = self.states[-1]
            add_notification = (
                state.add_notification
                if hasattr(state, "add_notification")
                else self.add_notification_dummy
            )
            INPUTS["screenshot"] = not self.save_screenshot(add_notification)

        if INPUTS["run"]:
            for joystick in self.joysticks.values():
                joystick.rumble(1, 0, 450)
                joystick.rumble(0, 1, 250)

        # if INPUTS["shaders_toggle"]:
        #     USE_SHADERS = not USE_SHADERS
        #     INPUTS["shaders_toggle"] = False

        # if INPUTS["next_shader"]:
        #     shader_index = SHADERS_NAMES.index(self.shader.shader_name)
        #     if shader_index < 0:
        #         shader_index = 0
        #     else:
        #         shader_index += 1
        #         if shader_index >= len(SHADERS_NAMES):
        #             shader_index = 0

        #     self.shader.create_pipeline(SHADERS_NAMES[shader_index])
        #     INPUTS["next_shader"] = False

        return events

    #############################################################################################################
    def reset_inputs(self) -> None:
        for key in ACTIONS.keys():
            INPUTS[key] = False

    #############################################################################################################
    def save_recording(self) -> None:
        if not self.save_frame or not self.rec_process:
            return

        self.save_frame = False
        self.log("Recording stopped")
        self.rec_process.stdin.close()
        self.log("saving recordings - this can take a while...")
        self.render_text(
            "SAVING...",
            (WIDTH_SCALED // 2, HEIGHT_SCALED // 2),
            font_size=FONT_SIZE_HUGE,
            centred=True,
            bg_color=PANEL_BG_COLOR,
        )

        # positions = [vec3(0, 0, 0)]
        # if USE_SHADERS:
        #     ratio: float = -1.0
        #     dt: float = self.clock.tick(FPS_CAP) / 1000.0
        #     self.shader.render(
        #         self.screen, self.HUD, [], 1.0, ratio, dt,
        #         use_shaders=USE_SHADERS, save_frame=self.save_frame
        #     )
        pygame.display.flip()
        self.rec_process.wait()

    #############################################################################################################
    def start_recording(self) -> None:
        self.save_frame = True

        time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = SCREENSHOTS_DIR / f"recording_{time_str}.mp4"
        self.log(f"Recording started: {file_name}")

        self.rec_process = (
            ffmpeg.input(
                "pipe:",
                format="rawvideo",
                pix_fmt="rgba",
                s=f"{WIDTH}x{HEIGHT}",
                r=FPS_CAP,
            )
            .vflip()
            .output(str(file_name), pix_fmt="rgb24", loglevel="quiet", r=RECORDING_FPS)
            .overwrite_output()
            .run_async(pipe_stdin=True)
        )

    #############################################################################################################
    def show_pause_message(self) -> None:
        self.render_text(
            "PAUSED",
            (WIDTH // 2, HEIGHT // 2),
            font_size=FONT_SIZE_HUGE,
            centred=True,
            bg_color=PANEL_BG_COLOR,
        )

    #############################################################################################################
    def postprocessing(self, dt: float) -> None:
        # shaders are used for postprocessing special effects
        # the whole Surface is used as texture on rect that fills to a full screen
        return

        ratio: float = 0.0
        if hasattr(self.states[-1], "player"):
            # if TYPE_CHECKING:
            from scene import Scene

            scene = cast(Scene, self.states[-1])
            # scene = self.states[-1]
            positions, ratio = scene.get_lights()
            scale = scene.camera.zoom
            add_notification = scene.add_notification
        else:
            add_notification = self.add_notification_dummy
            positions = []
            ratio = -1.0
            scale = 1.0

        # if SCALE != 1:
        #     HUD = pygame.transform.scale_by(self.HUD, SCALE)
        # else:
        #     HUD = self.HUD

        # render pipeline works as follows:
        # main game is rendered on game.canvas Surface
        # game.canvas is scaled to desired resolution on game.screen Surface
        # HUD/UI is rendered on game.HUD Surface
        # game.screen and game.HUD are passed to pixel shader for postprocessing effects
        # e.g.: day/night effect, color boost is applied to game.screen
        # HUD is drawn on top of it using alpha blending
        # when save_frame is True, the final image is returned as byte buffer
        # to be saved to a file (for screenshot or video recording)
        # returned image is not converted to Surface since it's a very slow process

        if USE_SHADERS:
            res = self.shader.render(
                self.screen,
                self.HUD,
                positions,
                scale,
                ratio,
                dt,
                USE_SHADERS,
                save_frame=self.save_frame,
                # USE_SHADERS
            )  # self.save_frame)

            if self.save_frame:
                if INPUTS["screenshot"]:
                    self.save_screenshot(add_notification, res)
                else:
                    if self.rec_process:
                        self.rec_process.stdin.write(res)

        return

    #############################################################################################################

    # @timeit
    async def run(self) -> None:
        # delta time since last frame in milliseconds
        dt = self.clock.tick(FPS_CAP) / 1000
        # slow down
        # dt *= 0.25
        self.fps = self.clock.get_fps()
        # print(f"FPS: {self.fps:4.2f}")
        # self.fps_data_3s.append(self.fps)
        # self.fps_data_10s.append(self.fps)
        # self.avg_fps_3s = sum(self.fps_data_3s) / len(self.fps_data_3s)
        # self.avg_fps_10s = sum(self.fps_data_10s) / len(self.fps_data_10s)
        # events = []
        events = self.get_inputs()

        # post external agent key events / handle commands (no-op unless enabled)
        if self.agent_ctrl:
            self.agent_ctrl.apply(self)

        # handle save/load hotkeys (works even when paused)
        if INPUTS.get("quick_save"):
            state = self.states[-1]
            if getattr(state, "is_maze", False):
                # saving is not allowed inside dungeons/mazes (procedural, non-persistable)
                if hasattr(state, "add_notification"):
                    state.add_notification("Cannot save in the dungeon", NotificationTypeEnum.error)  # type: ignore[attr-defined]
            else:
                slot_idx = self.save_manager.pick_quick_save_slot()
                if slot_idx is None:
                    if hasattr(state, "add_notification"):
                        state.add_notification("No free save slots", NotificationTypeEnum.error)  # type: ignore[attr-defined]
                elif self.save_manager.save(slot_idx):
                    if hasattr(state, "add_notification"):
                        state.add_notification(f"Game saved in slot {slot_idx + 1}", NotificationTypeEnum.success)  # type: ignore[attr-defined]
                else:
                    if hasattr(state, "add_notification"):
                        state.add_notification("Failed to save game", NotificationTypeEnum.error)  # type: ignore[attr-defined]
            INPUTS["quick_save"] = False
        if INPUTS.get("quick_load"):
            state = self.states[-1]
            if hasattr(state, "ui"):
                from ui.panels.save_load import LoadPanel as _LP

                state.ui.toggle(_LP)
            INPUTS["quick_load"] = False

        # first draw on separate Surface (game.canvas)
        if not self.is_paused:
            self.time_elapsed += dt
            self.states[-1].update(dt, events)
        # self.canvas.fill(BLACK_COLOR)
        if USE_SHADERS:
            self.HUD.fill(TRANSPARENT_COLOR)
        self.states[-1].draw(self.canvas, dt)
        self.custom_cursor(self.HUD)

        if self.is_paused:
            self.show_pause_message()

        if INPUTS["screenshot"] and not USE_SHADERS:
            state = self.states[-1]
            add_notification = (
                state.add_notification
                if hasattr(state, "add_notification")
                else self.add_notification_dummy
            )
            self.save_screenshot(add_notification)

        # than scale and copy on final Surface (game.screen)

        _scale = settings.SCALE
        if _scale != 1:
            scaled_w = int(WIDTH * _scale)
            scaled_h = int(HEIGHT * _scale)
            offset_x = (settings.WIDTH_SCALED - scaled_w) // 2
            offset_y = (settings.HEIGHT_SCALED - scaled_h) // 2
            self.screen.fill((0, 0, 0))
            self.screen.blit(pygame.transform.scale(self.canvas, (scaled_w, scaled_h)), (offset_x, offset_y))
        else:
            self.screen.blit(self.canvas, (0, 0))

        if USE_SHADERS:
            self.postprocessing(dt)
        # else:
        #     self.screen.blit(self.HUD, (0, 0))

        pygame.display.flip()

        # save screenshot if an external agent requested one (no-op unless enabled)
        if self.agent_ctrl:
            self.agent_ctrl.capture(self.screen)

        await asyncio.sleep(0)  # type: ignore

    def get_local_storage(self) -> None:
        if not IS_WEB or USE_WEB_SIMULATOR:
            return

        from platform import window  # type: ignore[attr-defined]

        window.localStorage.setItem("MoM.test", "test")

        result = window.localStorage.getItem("MoM.test")
        self.log(f"got from storage: {result}")

        # erase:
        keys = []
        for i in range(window.localStorage.length):
            key = window.localStorage.key(i)
            val = window.localStorage.getItem(key)
            keys.append(key)
            self.log(f"{key}, {val}")
        # while keys:
        #     window.localStorage.removeItem(keys.pop())

    async def loop(self) -> None:
        # import platform
        # print(platform.platform())  # Linux-6.1.52-valve16-1-neptune-61-x86_64-with-glibc2.37

        if IS_WEB:
            import platform

            platform.window.show_canvas(True)  # type: ignore[attr-defined]
            self.get_local_storage()

        # MARK: loop
        self.fps = 0.0
        # self.avg_fps_3s: float = 0.0
        # self.avg_fps_10s: float = 0.0
        # self.fps_data_3s = deque([], 3 * FPS_CAP)
        # self.fps_data_10s = deque([], 10 * FPS_CAP)
        try:
            while self.is_running:
                await self.run()
        finally:
            self.save_recording()
            pygame.quit()
