from dataclasses import dataclass
import random
from typing import Callable
import pygame

from settings import (
    BARK_DURATION,
    BARK_FADE_DURATION,
    BARK_LINE_CHARS,
    BARK_MAX_LINES,
    BARK_SHADOW_COLOR,
    BLACK_COLOR,
    CHAR_NAME_COLOR,
    FONT_SIZE_EXTRA_TINY,
    HUD_DIR,
    IS_WEB,
    MAIN_FONT,
    PANEL_BG_COLOR,
    PLAYER_CONFIG_KEY,
    TILE_SIZE,
    TRANSPARENT_COLOR,
    entity_name,
    load_image,
    wrap_bark,
)
from enums import AttitudeEnum, ItemTypeEnum, NotificationTypeEnum
if IS_WEB:
    from config_model.config import Character, Item, Chest
else:
    from config_model.config_pydantic import Character, Item, Chest  # type: ignore[assignment]

#################################################################################################################


class Collider(pygame.sprite.Sprite):
    """Drzwi: prostokąt na mapie, który wie tylko, dokąd prowadzi.

    C02/D13: `is_maze`, `maze_cols` i `maze_rows` tu nie wracają. Czy za drzwiami
    jest labirynt, wie mapa docelowa (`scene.map_registry.is_maze_map`), a jego
    wymiary siedzą w `maze_configs.csv` per poziom - obiekt na mapie zna wejście,
    nie zawartość.
    """

    def __init__(
        self,
        groups: pygame.sprite.Group,
        pos: tuple[int, int],
        size: tuple[int, int],
        name: str,
        to_map: str,
        destination_entry_point: str,
        return_entry_point: str = "",
        requires_item: str = "",
        consumes_key: bool = False,
    ) -> None:

        super().__init__(groups)
        self.image: pygame.Surface = pygame.Surface((size))
        self.rect: pygame.FRect = self.image.get_frect(topleft = pos)
        self.name = name
        self.to_map = to_map
        #: punkt wejścia NA MAPIE DOCELOWEJ - nie mylić ze `Scene.entry_point`,
        #: który mówi, gdzie gracz stoi teraz (C02/D13)
        self.destination_entry_point = destination_entry_point
        self.return_entry_point = return_entry_point
        #: Zamek (H01/D8) - te same dwa pola, co na skrzyni, tylko wzięte
        #: z WŁASNOŚCI obiektu w Tiled. Puste = drzwi otwarte, czyli wszystkie
        #: dzisiejsze.
        self.requires_item = requires_item
        self.consumes_key = consumes_key

#################################################################################################################


class Shadow(pygame.sprite.Sprite):
    def __init__(self,
                 groups: pygame.sprite.Group,
                 pos: tuple[int, int],
                 size: tuple[int, int],
                 empty: bool = False
                 ) -> None:
        super().__init__(groups)
        self.image: pygame.Surface = pygame.Surface((size)).convert_alpha()
        self.rect: pygame.FRect = self.image.get_frect(topleft = pos)
        self.image.fill(TRANSPARENT_COLOR)
        # self.image.set_colorkey("black")
        if not empty:
            pygame.draw.ellipse(self.image, BLACK_COLOR, self.rect)


#################################################################################################################
class InventorySlot(pygame.sprite.Sprite):
    def __init__(self, item_model: Item | None, pos: tuple[int, int], scale: int) -> None:
        super().__init__()
        # self.image: pygame.Surface = pygame.Surface((70 * scale * TILE_SIZE, 16 * scale * TILE_SIZE)).convert_alpha()
        self.item_model = item_model

        self.image_full: pygame.Surface = load_image(HUD_DIR / "inventorySlot.png").convert_alpha()
        self.image_selector: pygame.Surface = load_image(HUD_DIR / "hotbar_selector.png").convert_alpha()

        if scale != 1:
            self.image_full = pygame.transform.scale(
                self.image_full, (scale * self.image_full.get_width(),
                                  scale * self.image_full.get_height()))

            self.image_selector = pygame.transform.scale(
                self.image_selector, (scale * self.image_selector.get_width(),
                                      scale * self.image_selector.get_height()))

        self.rect_full: pygame.Rect = self.image_full.get_rect(topleft = pos)

        self.image: pygame.Surface = self.image_full.subsurface(0, 0, self.rect_full.width, self.rect_full.width)
        self.image_selected: pygame.Surface = self.image_full.subsurface(
            0, self.rect_full.width, self.rect_full.width, self.rect_full.width)
        # self.image: pygame.Surface = pygame.Surface(self.image.get_size()).convert_alpha()
        # self.image.fill(TRANSPARENT_COLOR)

        self.rect: pygame.Rect = self.image.get_rect(topleft = pos)
        self.rect_selected: pygame.Rect = self.image_selected.get_rect(topleft = pos)
        self.rect_selector: pygame.Rect = self.image_selector.get_rect(topleft = pos)
        # self.rect_full: pygame.FRect = self.image.get_frect(topleft = pos)

#################################################################################################################


class HealthBarUI(pygame.sprite.Sprite):
    def __init__(self, model: Character, groups: pygame.sprite.Group, pos: tuple[int, int], scale: int) -> None:
        super().__init__()
        # self.image: pygame.Surface = pygame.Surface((70 * scale * TILE_SIZE, 16 * scale * TILE_SIZE)).convert_alpha()
        self.model = model

        self.image_full: pygame.Surface = load_image(HUD_DIR / "LifeBarMiniProgress.png").convert_alpha()
        self.image_empty: pygame.Surface = load_image(HUD_DIR / "LifeBarMiniUnder.png").convert_alpha()
        # self.image = pygame.transform.scale(self.image, (scale * TILE_SIZE, scale * TILE_SIZE))
        self.image_full = pygame.transform.scale(
            self.image_full, (scale * self.image_full.get_width(), scale * self.image_full.get_height()))
        self.image_empty = pygame.transform.scale(
            self.image_empty, (scale * self.image_empty.get_width(), scale * self.image_empty.get_height()))
        self.image: pygame.Surface = pygame.Surface(self.image_full.get_size()).convert_alpha()
        # self.image: pygame.Surface = pygame.Surface((700, 200)).convert_alpha()
        self.image.fill(TRANSPARENT_COLOR)

        self.rect: pygame.FRect = self.image.get_frect(topleft = pos)
        self.rect_full: pygame.FRect = self.image_full.get_frect(topleft = pos)
        # self.rect_full.x = self.rect.left
        # self.rect_full.y += 1
        self.color: pygame._common.ColorValue = "white"
        if self.model.attitude == AttitudeEnum.enemy.value:
            self.color = "red"
        elif self.model.attitude == AttitudeEnum.friendly.value:
            self.color = CHAR_NAME_COLOR
        elif self.model.attitude == AttitudeEnum.afraid.value:
            self.color = "green"
        else:
            self.color = "pink"

    #############################################################################################################
    def set_bar(self, percentage: float, pos: tuple[int, int]) -> None:
        self.rect.topleft = pos
        self.rect_full.topleft = pos
        # self.rect_full.left += 50
        # draw empty bar
        self.image.fill(TRANSPARENT_COLOR)  # TRANSPARENT_COLOR) PANEL_BG_COLOR

        # # leave image fully transparent (hide labels)
        # if percentage < 0.0:
        #     return

        # self.image.blit(self.image_full, self.rect_full.topleft)
        self.image.blit(self.image_full, (0, 0))

        percentage = min(1.0, percentage)
        percentage = max(0.0, percentage)
        width = int(self.rect_full.width * percentage)
        rect = pygame.Rect(width, 0, self.rect_full.width - width, self.image_full.get_height())
        tmp_img = self.image_empty.subsurface(rect)

        self.image.blit(tmp_img, (width, 0))

#################################################################################################################


class HealthBar(pygame.sprite.Sprite):
    def __init__(self,
                 name: str,
                 config_key: str,
                 model: Character,
                 render_text: Callable,
                 groups: pygame.sprite.Group,
                 pos: tuple[int, int],
                 #  translate_pos: Callable
                 ) -> None:
        super().__init__(groups)
        self.image: pygame.Surface = pygame.Surface((125, 43)).convert_alpha()
        self.image.fill(TRANSPARENT_COLOR)
        self.visible: bool = True
        self.name = name
        # `name` to nazwa obiektu Tiled ("Malachi"), `config_key` to klucz z config.json
        # ("Player") - pasek życia potrzebuje tego drugiego, żeby wiedzieć, czy rysuje
        # bohatera (C02, O6). Nazwa wyświetlana jest tłumaczona i nie nadaje się na test.
        self.config_key = config_key
        self.model = model
        self.render_text = render_text
        self.translate_pos: Callable = lambda pos:  pos
        self.image_full: pygame.Surface = load_image(HUD_DIR / "LifeBarMiniProgress.png").convert_alpha()
        self.image_empty: pygame.Surface = load_image(HUD_DIR / "LifeBarMiniUnder.png").convert_alpha()
        self.rect: pygame.FRect = self.image.get_frect(midtop = pos)
        self.rect_full: pygame.FRect = self.image_full.get_frect()
        self.rect_full.x = self.rect.width // 2 - self.rect_full.width // 2
        self.rect_full.y += 1
        self.color: pygame._common.ColorValue = "white"
        if self.model.attitude == AttitudeEnum.enemy.value:
            self.color = "red"
        elif self.model.attitude == AttitudeEnum.friendly.value:
            self.color = CHAR_NAME_COLOR
        elif self.model.attitude == AttitudeEnum.afraid.value:
            self.color = "green"
        else:
            self.color = "pink"

    #############################################################################################################
    def set_bar(self, percentage: float) -> None:
        self.image.fill(TRANSPARENT_COLOR)

        # leave image fully transparent (hide labels)
        if percentage < 0.0:
            return
        y: int = 8
        # show health bar only for enemies
        if self.model.attitude == AttitudeEnum.enemy.value or self.config_key == PLAYER_CONFIG_KEY:
            self.image.blit(self.image_full, self.rect_full.topleft)

            percentage = min(1.0, percentage)
            percentage = max(0.0, percentage)
            width = int(self.rect_full.width * percentage)
            rect = pygame.Rect(width, 0, self.rect_full.width - width, self.image_full.get_height())
            tmp_img = self.image_empty.subsurface(rect)

            self.image.blit(tmp_img, (self.rect_full.left + width, 1))

            y += 5

        # render name of the character (wrap at space if too wide).
        # EXTRA_TINY (8px), NOT the UI minimum (10px): this label is baked into the
        # character's world sprite and drawn at camera zoom (~3.8x), so it is not
        # downscaled like UI text — 10px reads oversized in-world (design-system:
        # world-space vs UI-space text scaling).
        name = entity_name(self.model)
        fs = FONT_SIZE_EXTRA_TINY
        max_w = self.image.get_width() - 4
        _font = pygame.font.Font(MAIN_FONT, fs)
        line_h = fs + 4

        if _font.size(name)[0] <= max_w:
            self.render_text(
                name,
                (int(self.rect.width // 2), y),
                self.color,
                font_size=fs,
                shadow=(84, 135, 137),
                centred=True,
                surface=self.image
            )
        else:
            words = name.split()
            line1: list[str] = []
            for w in words:
                if _font.size(" ".join(line1 + [w]))[0] > max_w:
                    break
                line1.append(w)
            line2 = " ".join(words[len(line1):])
            s1 = " ".join(line1)
            cy = y if not line2 else y + line_h // 2
            self.render_text(
                s1,
                (int(self.rect.width // 2), cy - line_h // 2),
                self.color,
                font_size=fs,
                shadow=(84, 135, 137),
                centred=True,
                surface=self.image
            )
            if line2:
                self.render_text(
                    line2,
                    (int(self.rect.width // 2), cy + line_h // 2),
                    self.color,
                    font_size=fs,
                    shadow=(84, 135, 137),
                    centred=True,
                    surface=self.image
                )

#################################################################################################################
    def show(self) -> None:
        self.visible = True
        self.set_bar(self.model.health / self.model.max_health)

#################################################################################################################
    def hide(self) -> None:
        if not self.visible:
            return
        self.visible = False
        self.set_bar(-1)

#################################################################################################################


class BarkSprite(pygame.sprite.Sprite):
    """Ambientowa zaczepka nad głową postaci - sam tekst z obrysem (H01/W1, D4).

    **Nie panel i nie toast.** Panel zasłoniłby za dużo mapy, a toast oderwałby
    kwestię od mówiącego. To ta sama technika, co imię pod postacią
    (`HealthBar.set_bar`): napis wtapiany w świat, w tej samej grupie
    `label_sprites`, rysowany zoomem kamery.

    **Font `FONT_SIZE_EXTRA_TINY` (8 px), nie minimum UI (10 px)** - i nie wolno
    tego podnieść. Napis nie jest skalowany w dół jak tekst UI, tylko w GÓRĘ
    zoomem kamery (~3,8x), więc 10 px czyta się w świecie jak nagłówek. Powód
    jest ten sam co w `HealthBar` i stoi tam wypisany.

    Sprite istnieje przez całe życie postaci (jak `EmoteSprite`) i normalnie jest
    całkowicie przezroczysty. Dzięki temu jego cykl życia to dokładnie ten sam
    kod, co dla emote - a bark, który nie idzie za postacią, zostaje wisieć nad
    pustym polem po kimś, kto poszedł spać.
    """

    #: Cache metryk fontu: powierzchnia jest liczona z treści (28 znaków x 2 linie),
    #: a nie z zaszytego rozmiaru pudełka - `pygame.font.Font` per sprite byłby
    #: kosztem na każdą postać we wsi.
    _font: pygame.font.Font | None = None

    def __init__(
        self,
        group: pygame.sprite.Group,
        pos: tuple[int, int],
        render_text: Callable,
        # cudzysłów NIE jest ozdobą: `pygame._common` istnieje tylko dla mypy,
        # a adnotacja w sygnaturze jest ewaluowana przy definicji klasy
        # (ten moduł nie ma `from __future__ import annotations`)
        color: "pygame._common.ColorValue" = CHAR_NAME_COLOR,
    ) -> None:
        super().__init__(group)
        self.render_text = render_text
        self.color = color
        #: klucz wiadomości aktualnie mówionej - dla asercji agentowych (A02)
        self.message_key: str = ""
        self.text: str = ""
        self.time_left: float = 0.0

        font = self._shared_font()
        line_h = FONT_SIZE_EXTRA_TINY + 4
        # +4 na obrys po obu stronach; "W" jest najszerszym znakiem tego fontu,
        # więc mieści się KAŻDY dopuszczony przez importer bark
        width = font.size("W" * BARK_LINE_CHARS)[0] + 4
        self.image: pygame.Surface = pygame.Surface(
            (width, line_h * BARK_MAX_LINES + 4)).convert_alpha()
        self.image.fill(TRANSPARENT_COLOR)
        self.rect: pygame.FRect = self.image.get_frect(midbottom=pos)
        self._line_h = line_h
        #: `PyscrollGroup.draw` czyta ten atrybut sprite'a i podaje go dalej jako
        #: flagę blitu. BEZ niego SDL wybiera ścieżkę "copy" i wpisuje alfę ŹRÓDŁA
        #: do `game.canvas`, robiąc w nim całkowicie przezroczystą dziurę wielkości
        #: całego barka - na ekranie czarny prostokąt (także wokół milczącego
        #: sprite'a, bo on jest przezroczysty w całości). To ta sama pułapka i to
        #: samo lekarstwo, co przy cząstkach (`particles.emit`, patrz „Pułapka
        #: (przezroczystość)" w `project/AGENTS.md`) i przy kursorze myszy
        #: (`game.custom_cursor`). Widać ją WYŁĄCZNIE na prawdziwym ekranie:
        #: format okna na macOS ma maskę alfy, a headless SDL dummy nie ma jej
        #: wcale, więc scenariusze agentowe pokazywały czysty obraz.
        self.blendmode: int = pygame.BLEND_ALPHA_SDL2

    @classmethod
    def _shared_font(cls) -> pygame.font.Font:
        if cls._font is None:
            cls._font = pygame.font.Font(MAIN_FONT, FONT_SIZE_EXTRA_TINY)
        return cls._font

    @property
    def is_speaking(self) -> bool:
        return self.time_left > 0.0

    def say(self, text: str, message_key: str = "") -> None:
        """Pokaż kwestię przez `BARK_DURATION` sekund, z zanikiem na końcu."""
        self.text = text
        self.message_key = message_key
        self.time_left = BARK_DURATION
        self._render()

    def silence(self) -> None:
        """Zgaś natychmiast - postać zasnęła, zeszła z mapy albo umarła."""
        self.text = ""
        self.message_key = ""
        self.time_left = 0.0
        self.image.fill(TRANSPARENT_COLOR)
        # alfa powierzchni zostaje z ostatniego zaniku, a `say()` może przyjść
        # zanim ktokolwiek ją wyzeruje - bez tego następna kwestia zaczyna
        # rozmowę półprzezroczysta
        self.image.set_alpha(255)

    def update(self, dt: float) -> None:
        """Odliczanie i zanik. Wołane przez `scene.group.update(dt)`."""
        if self.time_left <= 0.0:
            return
        self.time_left -= dt
        if self.time_left <= 0.0:
            self.silence()
            return
        # alfa spada dopiero na ostatnim odcinku - kwestia ma być czytelna,
        # a nie migotać przez cały czas życia
        if self.time_left < BARK_FADE_DURATION:
            self.image.set_alpha(int(255 * (self.time_left / BARK_FADE_DURATION)))

    def _check_layout(self, lines: list[str]) -> None:
        """A03: kwestia, która się nie mieści, jest ZGŁASZANA, a nie po cichu ucinana.

        Importer odrzuca za długie barki już przy `just import-dialogs`, więc tu
        normalnie nic się nie zapala. To siatka na tekst, który dotarł do gry inną
        drogą: ręcznie zmieniony `config.json`, wywołanie `say()` z kodu.
        """
        from ui.layout import report_violation

        if len(lines) > BARK_MAX_LINES:
            report_violation(
                "BarkSprite", "v-overflow",
                f"bark {self.message_key or self.text!r} potrzebuje {len(lines)} linii, "
                f"mieszczą się {BARK_MAX_LINES}",
            )
        for line in lines:
            if len(line) > BARK_LINE_CHARS:
                report_violation(
                    "BarkSprite", "h-overflow",
                    f"linia dłuższa niż {BARK_LINE_CHARS} znaków: {line!r}",
                )
                break

    def _render(self) -> None:
        self.image.fill(TRANSPARENT_COLOR)
        self.image.set_alpha(255)
        # `wrap_bark` jest wspólne z importerem - a importer odrzucił już wszystko,
        # co nie mieści się w BARK_MAX_LINES, więc tutaj nie ma czego ucinać
        wrapped = wrap_bark(self.text)
        self._check_layout(wrapped)
        lines = wrapped[:BARK_MAX_LINES]
        top = self.image.get_height() - self._line_h * len(lines) - 2
        for index, line in enumerate(lines):
            self.render_text(
                line,
                (int(self.rect.width // 2), top + index * self._line_h),
                self.color,
                font_size=FONT_SIZE_EXTRA_TINY,
                shadow=BARK_SHADOW_COLOR,
                centred=True,
                surface=self.image,
            )

#################################################################################################################


class Object(pygame.sprite.Sprite):
    def __init__(
        self,
        group: pygame.sprite.Group | None,
        pos: tuple[int, int],
        image: pygame.Surface  = pygame.Surface((TILE_SIZE, TILE_SIZE)),
        # z: str = "blocks",
    ) -> None:
        if group is not None:
            super().__init__(group)
        else:
            super().__init__()

        self.image = image
        self.rect: pygame.FRect = image.get_frect(topleft = pos)
        # self.hitbox: pygame.FRect = self.rect.copy().inflate(0, 0)
        # self.z = z
#################################################################################################################


class EmoteSprite(Object):
    def __init__(
        self,
        group: pygame.sprite.Group,
        pos: tuple[int, int],
        emotes: dict[str, list[pygame.Surface]],
        # emote: pygame.Surface  = pygame.Surface((TILE_SIZE, TILE_SIZE)),
        # z: str = "blocks",
    ) -> None:

        self.emotes = emotes
        self.emote: str = ""
        self.temporary_emote: str = ""
        self.temporary_emote_counter: float = 0.0
        self.frame_index: float = 0.0
        self.image: pygame.Surface = self.emotes["clear"][0]
        self.set_emote("clear")
        super().__init__(group, pos, self.image)

        self.rect: pygame.FRect = self.image.get_frect(midbottom = pos)

    def set_emote(self, emote: str) -> None:
        # if self.temporary_emote_counter > 0.0:
        #     print("set_emote", emote)

        if self.emote != emote:
            # if emote == "clear" and self.emote == "red_exclamation_anim":
            #     return

            self.emote = emote
            if not self.temporary_emote:
                self.frame_index = 0.0
                # self.image = self.emotes[self.emote][int(self.frame_index)]
                # self.image = self.emotes[self.emote][0]
                self.animate(0.0, forced=True)

    def clear_temporary_emote(self) -> None:
        self.temporary_emote = ""
        self.temporary_emote_counter = 0.0
        self.frame_index = 0.0
        self.animate(0.0, forced=True)

    def set_temporary_emote(self, emote: str, duration: float) -> None:
        # print("set_temporary_emote", emote)

        # if not self.temporary_emote:
        self.temporary_emote = emote
        self.temporary_emote_counter = duration
        self.frame_index = 0.0
        self.animate(0.0, forced=True)

    def animate(self, dt: float, forced: bool = False) -> None:
        # if self.temporary_emote_counter > 0.0:
        #             print(f"""before e={self.emote}
        # te={self.temporary_emote}
        # tec={self.temporary_emote_counter}
        # dt={dt:5.2f}
        # delta={(self.temporary_emote_counter - dt):5.2f}
        # fi={self.frame_index}""".replace("\n", " "))
        # skip if not animated and not forced
        # if "_anim" not in self.emote and forced == False:
        #     return

        self.frame_index += dt

        #         if self.temporary_emote_counter > 0.0:
        #             print(f"""after  e={self.emote}
        # te={self.temporary_emote}
        # tec={self.temporary_emote_counter}
        # dt={dt:5.2f}
        # delta={(self.temporary_emote_counter - dt):5.2f}
        # fi={self.frame_index}""".replace("\n", " "))

        if self.temporary_emote:
            self.temporary_emote_counter -= dt
            if self.temporary_emote_counter < 0.0:
                self.temporary_emote = ""

        active_emote = self.emote if not self.temporary_emote else self.temporary_emote

        if self.frame_index >= len(self.emotes[active_emote]):
            self.frame_index = 0.0  # if loop else len(self.emotes[self.emote]) - 1.0

        self.image = self.emotes[active_emote][int(self.frame_index)]  # .copy()

#################################################################################################################


class ItemSprite(Object):
    def __init__(
        self,
        group: pygame.sprite.Group | None,
        # gid: int,
        pos: tuple[int, int],
        # z: str = "blocks",
        name: str,
        model: Item,
        image: list[pygame.Surface] = [pygame.Surface((TILE_SIZE, TILE_SIZE))],
    ) -> None:

        super().__init__(group, pos, image[0])
        # decrease the size of rectangle for collisions aka. hitbox
        # self.hitbox: pygame.FRect = self.rect.copy().inflate(0, -self.rect.height / 2)
        # self.gid = gid
        self.name = name
        self.model = model
        if model.type == ItemTypeEnum.weapon:
            self.image_directions: dict[str, pygame.Surface] = {
                "down": image[0],
                "up": pygame.transform.flip(image[0], False, True),
            }
            self.image_directions["left"] = pygame.transform.rotate(image[0], -90)
            self.image_directions["right"] = pygame.transform.rotate(image[0], 90)

            # self.weapon_mask = pygame.mask.from_surface(self.image)
            self.masks: dict[str, pygame.mask.Mask] = {}
            for direction in self.image_directions:
                self.masks[direction] = pygame.mask.from_surface(self.image_directions[direction])

            self.mask: pygame.mask.Mask = self.masks["up"]

#################################################################################################################


class ChestSprite(Object):
    def __init__(
        self,
        group: pygame.sprite.Group | None,
        pos: tuple[int, int],
        # name: str,
        model: Chest,
        chests_sprites: dict[str, list[pygame.Surface]],
        name: str | None = None,
        rng: random.Random | None = None,
        # image_open: pygame.Surface = pygame.Surface((TILE_SIZE, TILE_SIZE)),
        # image_closed: pygame.Surface = pygame.Surface((TILE_SIZE, TILE_SIZE)),
    ) -> None:

        self.image_closed = chests_sprites["small_chest"][0] if model.is_small else chests_sprites["big_chest"][0]
        self.image_open = chests_sprites["small_chest"][1] if model.is_small else chests_sprites["big_chest"][1]
        image = self.image_closed if model.is_closed else self.image_open
        super().__init__(group, pos, image)
        # self.rect.center = pos
        self.model = model
        # `name` is the chest's identity in the save file and must be unique within
        # a map; the scene builds it as `<template>#<n>`. Falling back to the model
        # name keeps direct construction (tests, tools) working.
        self.name = name if name is not None else model.name

        self.generate_random_items(rng)
        # self.is_closed = True
        # self.items: list[Item] = []

#################################################################################################################
    def generate_random_items(self, rng: random.Random | None = None) -> None:
        """Top the chest up to ``total_items_count`` with random loot.

        ``rng`` must be the maze generator for a maze chest: the drawn loot has to
        come back identical when the level is rebuilt from its seed. Outside a maze
        the global ``random`` is fine - those chests have fixed contents anyway.

        ``self.model`` must be a *deep* copy of the config entry. It used to be a
        shallow one, which shares the ``items`` list, so this loop appended straight
        into ``game.conf``: every chest built from the same template ended up with
        the same loot and the config stayed polluted for the rest of the process.
        """
        if len(self.model.random_items) == 0:
            return

        r = rng or random

        # self.model.items = []
        curr_count = len(self.model.items)

        if self.model.total_items_count - curr_count < 0:
            return

        # random.shuffle(self.model.random_items)
        for _ in range(self.model.total_items_count - curr_count):
            self.model.items.append(r.choice(self.model.random_items))

#################################################################################################################
    def open(self) -> None:
        self.image = self.image_open
        self.model.is_closed = False

#################################################################################################################
    def close(self) -> None:
        self.image = self.image_closed
        self.model.is_closed = True

#################################################################################################################


class DestructibleSprite(Object):
    def __init__(
        self,
        group: pygame.sprite.Group | None,
        pos: tuple[int, int],
        # name: str,
        # model: Chest,
        sprite: pygame.Surface,
        wall: pygame.Rect,
        prev_step_cost: int,
        type: str,
        # image_open: pygame.Surface = pygame.Surface((TILE_SIZE, TILE_SIZE)),
        # image_closed: pygame.Surface = pygame.Surface((TILE_SIZE, TILE_SIZE)),
    ) -> None:

        # self.image = sprite
        super().__init__(group, pos, sprite)
        self.mask = pygame.mask.from_surface(sprite)
        self.wall = wall
        self.step_cost = prev_step_cost
        self.type = type
        # self.rect.center = pos
        # self.model = model
        # self.name = model.name
        # self.is_closed = True


################################################################################################################


@dataclass(slots=True)
class Notification():
    type: NotificationTypeEnum
    message: str
    message_text: str
    width: int
    height: int
    create_time: float
    emote_key: str = ""
    # When this toast becomes visible. Its lifetime and its slide-in both run
    # from here, not from create_time, so a queued toast still gets the full
    # NOTIFICATION_DURATION and still animates in when its turn comes.
    show_time: float = 0.0
