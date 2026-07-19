import game
import pygame
import settings
from settings import (
    COLORS, FONT_SIZE_DEFAULT, FONT_SIZE_HUGE, INPUTS, TEXT_ROW_SPACING, _
)
from state import State


class SplashScreen(State):
    def __init__(self, game: game.Game, name: str = "") -> None:
        super().__init__(game)
        self.name = name

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.name}"

    def update(self, dt: float, events: list[pygame.event.EventType]) -> None:
        if INPUTS["left_click"]:
            self.game.reset_inputs()
            self.exit_state()

        if INPUTS["right_click"]:
            self.game.reset_inputs()
            self.exit_state()

        if INPUTS["quit"]:
            self.game.reset_inputs()
            self.exit_state()

        if INPUTS["accept"]:
            self.game.reset_inputs()
            self.exit_state()

        if INPUTS["select"]:
            # Scene(self.game, "grasslands", "start").enter_state()
            self.game.reset_inputs()
            self.exit_state()

    def draw(self, screen: pygame.Surface, dt: float) -> None:
        screen.fill(COLORS["blue"])
        self.game.render_text(f"{self.name}", (settings.WIDTH_SCALED // 2, settings.HEIGHT_SCALED // 2),
                              font_size=FONT_SIZE_HUGE, centred=True)
        self.game.render_text(
            _("splash.continue"),
            (settings.WIDTH_SCALED // 2, int(settings.HEIGHT_SCALED - (FONT_SIZE_DEFAULT * TEXT_ROW_SPACING))),
            centred=True
        )
