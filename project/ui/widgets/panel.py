"""Nine-patch box, którego rozmiar **wynika z zawartości**.

Najczęstsza klasa błędów UI w tym projekcie brzmi zawsze tak samo: „panel ma zaszytą
wysokość, tekst urósł, litery wchodzą na ramkę". Zdarzyło się to nazwie lokalizacji
(„Tawerna Brakująca klepka" zawijała się do dwóch linii w pudełku wysokim na jedną),
panelowi pomocy i kolumnom questów. Za każdym razem powód był ten sam: **rozmiar
pudełka był stałą, a zawartość zmienną**.

Ten widget odwraca zależność. Podajesz gotową powierzchnię z treścią, a on liczy
rozmiar ramki: ``box = content + 2 * pad``. Nie da się „zapomnieć" zwiększyć
wysokości, bo wysokości nigdzie się nie wpisuje.

Trzy rzeczy, które robi za wołającego:

1. **Liczy pudełko z treści**, razem z grubością ramki nine-patcha (``border * scale``
   pikseli z każdej strony) - to ona zjadała miejsce, którego „przecież było dość".
2. **Centruje treść w pudełku** względem *faktycznego* rozmiaru tła. ``NinePatch``
   podnosi żądany rozmiar do rozmiaru źródłowego obrazka, więc małe pudełko wychodzi
   większe, niż się prosiło - centrowanie po żądanym rozmiarze mijało się o kilka px.
3. **Sprawdza samo siebie** (A03): treść musi mieścić się w obszarze wewnętrznym,
   a pudełko w viewporcie. Naruszenie ląduje w rejestrze `layout` i wywala test,
   zamiast czekać na zrzut ekranu. Nigdy nie przycina i nie clampuje - to byłoby
   zamiatanie błędu pod dywan (patrz `ui/AGENTS.md`).

Tryb immediate, jak reszta HUD-a: trzymasz instancję na panelu (konfiguracja wyglądu),
a treść podajesz przy każdym rysowaniu.

Przykład - nazwa lokalizacji wyśrodkowana u góry ekranu::

    self._location_panel = Panel("nine_patch_04.png", pad=(40, 20), name="HUD(location)")
    ...
    self._location_panel.draw(surface, text_surf, anchor="midtop", offset=(0, HUD_EDGE))
"""

from __future__ import annotations

import pygame

import settings
from settings import TILE_SIZE

from .. import layout, theme

#: Domyślny odstęp treści od **wewnętrznej** krawędzi ramki (ponad samą ramkę).
#: 8 px to jeden „klik" siatki 4 px razy dwa - dość, żeby litery z wydłużeniami
#: dolnymi nie dotykały malowanej ramki.
DEFAULT_INNER_PAD = 8

#: Minimalny oddech między pudełkiem a krawędzią ekranu, gdy panel liczy swój limit.
DEFAULT_SCREEN_MARGIN = TILE_SIZE


class Panel:
    """Ramka nine-patch dopasowana do treści.

    Args:
        file: plik nine-patcha z `assets/.../HUD/Theme`.
        scale: skala źródłowego obrazka (jak w `theme.nine_patch`).
        border: szerokość rogu nine-patcha w pikselach **źródła** (mnożona przez `scale`).
        pad: całkowity odstęp treści od krawędzi pudełka, `(x, y)`. `None` = ramka
            plus :data:`DEFAULT_INNER_PAD`. Podana wartość mniejsza od ramki jest
            podnoszona do ramki - inaczej treść wjeżdżałaby na malowany brzeg.
        min_size: dolna granica rozmiaru pudełka (np. żeby jednolinijkowe toasty
            nie „skakały" wysokością). Nigdy nie jest granicą górną.
        margin: odstęp od krawędzi ekranu przy liczeniu :meth:`max_content_size`.
        name: nazwa w komunikatach rejestru layoutu - ma wskazywać panel, nie widget.
    """

    def __init__(
        self,
        file: str = "nine_patch_04.png",
        *,
        scale: int = 4,
        border: int = 6,
        pad: tuple[int, int] | None = None,
        min_size: tuple[int, int] = (0, 0),
        margin: int = DEFAULT_SCREEN_MARGIN,
        name: str = "Panel",
    ) -> None:
        self.file = file
        self.scale = scale
        self.border = border
        self.min_size = min_size
        self.margin = margin
        self.name = name
        frame = border * scale
        if pad is None:
            pad = (frame + DEFAULT_INNER_PAD, frame + DEFAULT_INNER_PAD)
        # Ramka jest nieprzekraczalna: pod nią nie ma miejsca na treść, jest na niej obrazek.
        self.pad = (max(pad[0], frame), max(pad[1], frame))

    #############################################################################################################
    @property
    def frame(self) -> int:
        """Grubość malowanej ramki w pikselach ekranu."""
        return self.border * self.scale

    def box_size(self, content_size: tuple[int, int]) -> tuple[int, int]:
        """Rozmiar pudełka dla treści o rozmiarze ``content_size``."""
        return (
            max(self.min_size[0], content_size[0] + 2 * self.pad[0]),
            max(self.min_size[1], content_size[1] + 2 * self.pad[1]),
        )

    def max_content_size(self, max_box: tuple[int, int] | None = None) -> tuple[int, int]:
        """Ile treści zmieści się w pudełku - **limit do zawijania, nie do przycinania**.

        Tym karmi się `RichText` zamiast magicznej stałej: przy każdej rozdzielczości
        tekst zawija się dokładnie tam, gdzie pudełko przestałoby się mieścić.

        ``max_box`` to budżet dla **pudełka**, gdy ekran nie jest jedynym ograniczeniem -
        HUD podaje tu szerokość, przy której wyśrodkowana nazwa lokacji jeszcze nie
        wchodzi na panel statystyk. Bez niego limitem jest sam viewport minus `margin`.
        """
        box = max_box or (settings.WIDTH - 2 * self.margin, settings.HEIGHT - 2 * self.margin)
        return (max(1, box[0] - 2 * self.pad[0]), max(1, box[1] - 2 * self.pad[1]))

    #############################################################################################################
    def background(self, content_size: tuple[int, int]) -> pygame.Surface:
        """Tło w rozmiarze policzonym z treści (cache'owane per rozmiar w `theme`)."""
        width, height = self.box_size(content_size)
        return theme.nine_patch(self.file, width, height, scale=self.scale, border=self.border)

    def draw(
        self,
        surface: pygame.Surface,
        content: pygame.Surface,
        *,
        anchor: str = "topleft",
        ref: pygame.Rect | None = None,
        offset: tuple[int, int] = (0, 0),
        pos: tuple[int, int] | None = None,
    ) -> pygame.Rect:
        """Narysuj pudełko z treścią i zwróć jego rect na ekranie.

        Pozycję podaje się albo kotwicą (``anchor``/``ref``/``offset``, przez
        `layout.anchor_rect`), albo wprost przez ``pos`` (lewy górny róg pudełka) -
        to drugie dla stosów, które same liczą sobie y, jak toasty.
        """
        bg = self.background(content.get_size())
        # rozmiar FAKTYCZNY, nie żądany: NinePatch podnosi pudełko do rozmiaru źródła
        size = bg.get_size()
        if pos is not None:
            rect = pygame.Rect(pos, size)
        else:
            rect = layout.anchor_rect(size, anchor, ref, offset)

        surface.blit(bg, rect.topleft)
        content_rect = content.get_rect(center=rect.center)
        surface.blit(content, content_rect.topleft)

        self._check(rect, content_rect)
        return rect

    #############################################################################################################
    def _check(self, rect: pygame.Rect, content_rect: pygame.Rect) -> None:
        """Samokontrola layoutu (A03) - mierzy i zgłasza, nigdy nie naprawia."""
        inner = rect.inflate(-2 * self.pad[0], -2 * self.pad[1])
        layout.check_inside(self.name, content_rect, inner)
        screen = layout.screen_rect()
        if rect.width > screen.width:
            layout.report_violation(
                self.name, "h-overflow",
                f"pudełko {rect.width}px szersze niż ekran {screen.width}px - "
                f"zawijaj treść do max_content_size()",
            )
        if rect.height > screen.height:
            layout.report_violation(
                self.name, "v-overflow",
                f"pudełko {rect.height}px wyższe niż ekran {screen.height}px",
            )
