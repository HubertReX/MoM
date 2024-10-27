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

from settings import IS_WEB, USE_WEB_SIMULATOR, CONF_ENTITIES_TO_STORE  # noqa: E402

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
ENTITIES = ["all"] + list(CONF_ENTITIES_TO_STORE.keys())

#############################################################################################################


def main(task: str, entities: list[str]) -> None:
    print(rule.Rule(title="[bright_yellow]START[/]", characters="#"))

    game = Game(task, entities)
    asyncio.run(game.loop())
    print(rule.Rule(title="[bright_yellow]END[/]", characters="#"))


#############################################################################################################

if not IS_WEB:
    @click.group(context_settings=CONTEXT_SETTINGS,
                 invoke_without_command=True,
                 help="There are several task that can be performed automatically.")
    @click.option("-e", "--entity", "entities", default=["all"], type=click.Choice(ENTITIES), multiple=True,
                  show_default=True,
                  help="For load and store COMMAND, which entity to be processed")
    @click.pass_context
    def cli(ctx: click.core.Context, entities: list[str]) -> None:
        ctx.ensure_object(dict)
        ctx.obj["entities"] = entities
        if ctx.invoked_subcommand is None:
            main(task="run", entities=[])

    #############################################################################################################
    @cli.command()
    @click.pass_context
    def store(ctx: click.core.Context) -> None:
        "read 'config.json' and store to '<entities>.csv'"

        main(task=TaskEnum.store, entities=ctx.obj["entities"])

    #############################################################################################################
    @cli.command()
    @click.pass_context
    def load(ctx: click.core.Context) -> None:
        "load '<entities>.csv' and write to 'config.json'"

        main(task=TaskEnum.load, entities=ctx.obj["entities"])

    #############################################################################################################
    @cli.command()
    def run() -> None:
        "run the game  [default]"

        main(task=TaskEnum.run, entities=[])

    #############################################################################################################
    @cli.command()
    def update() -> None:
        "update config schema 'config_schema.json'"

        main(task=TaskEnum.update, entities=[])

#############################################################################################################

if __name__ == "__main__":
    if IS_WEB:
        main(task="run", entities=[])
    else:
        cli(max_content_width=120)
