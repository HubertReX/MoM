#!../.venv/bin/python
# /// script
# [project]
# name = "The Game"
# version = "0.1"
# description = "Boilerplate pygame-ce project for a top-down tiles sheet based RPG game that can run in the browser."
# readme = {file = "../README.md", content-type = "text/markdown"}
# requires-python = ">=3.12"
#
# dependencies = [
#  "numpy",
#  "pillow",
#  "pytmx",
#  "pyscroll",
#  "functools",
#  "rich",
#  "Pygments",
#  "pathlib",
#  "pillow",
#  "thorpy",
# ]
# ///
from enums import TaskEnum
from os import environ

environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
# https://www.reddit.com/r/pygame/comments/12twl0e/cannot_rumble_dualshock_4_via_bluetooth_in_pygame/
environ["SDL_JOYSTICK_HIDAPI_PS4_RUMBLE"] = "1"

from settings import IS_WEB, USE_WEB_SIMULATOR  # noqa: E402

if not IS_WEB:
    import click

if USE_WEB_SIMULATOR:
    import pygbag.aio as asyncio
else:
    import asyncio

import random  # noqa: E402
from rich import print, rule  # noqa: E402
from game import Game  # noqa: E402

seed = 107
random.seed(seed)
# np.random.seed(seed)

CONTEXT_SETTINGS = dict(help_option_names=["-h", "/h", "-?", "/?", "--help"])

#############################################################################################################


def main(task: str) -> None:
    print(rule.Rule(title="[bright_yellow]START[/]", characters="#"))

    game = Game(task)
    asyncio.run(game.loop())
    print(rule.Rule(title="[bright_yellow]END[/]", characters="#"))

#############################################################################################################


def init() -> None:
    if IS_WEB:
        main(task=TaskEnum.run)
    else:
        cli(max_content_width=120)


#############################################################################################################

if not IS_WEB:
    @click.group(context_settings=CONTEXT_SETTINGS,
                 invoke_without_command=True,
                 help="There are several task that can be performed automatically.")
    @click.pass_context
    def cli(ctx: click.core.Context) -> None:
        # CSV <-> config.json obsługuje `just import-entities`
        # (config_model/import_entities.py) - jedyna ścieżka do plików CSV.
        if ctx.invoked_subcommand is None:
            main(task="run")

    #############################################################################################################
    @cli.command()
    def run() -> None:
        "run the game  [default]"

        main(task=TaskEnum.run)

    #############################################################################################################
    @cli.command()
    def update() -> None:
        "update config schema 'config_schema.json'"

        main(task=TaskEnum.update)

#############################################################################################################

if __name__ == "__main__":
    init()
