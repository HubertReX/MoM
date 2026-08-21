#!/usr/bin/env python3
"""Teren: warianty kafli, autotiling z wangsetu i nieregularne kształty biomów.

Trzy rzeczy, których potrzebuje generator, żeby mapa nie wyglądała na dywan:

1. **Warianty** - `Floor.tsx` ma 7 kafli czystej trawy i 3 czystej ziemi. Wybór
   losowy z wagami sprawia, że ta sama łąka nie powtarza się co kafel.
2. **Autotiling** - ten sam tileset niesie wangset "grass-dirt Set" (typ corner,
   16 kafli przejściowych). Malujemy siatkę ROGÓW, a kafel wybieramy po tym,
   jakie tereny spotykają się w jego czterech rogach. Dzięki temu brzeg ścieżki
   jest miękki bez jednej zaszytej reguły.
3. **Kształt** - szum wartościowy z progiem daje plamę o postrzępionym brzegu.
   Prostokątny las to pierwsza rzecz, po której widać, że mapę zrobiła maszyna.

Cały moduł jest deterministyczny względem podanego `random.Random`, więc mapa
odtwarza się z ziarna zapisanego we właściwościach `.tmx`.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Iterable
from pathlib import Path

from tileset import Tileset, WangSet
from tmx import TileLayer

# Wangset, którym maluje się styk trawy z ziemią. Nazwa pochodzi z Floor.tsx.
GRASS_DIRT = "grass-dirt Set"


@dataclass
class Terrain:
    """Jeden teren: lista wariantów wypełnienia z wagami."""

    name: str
    variants: list[int] = field(default_factory=list)
    weights: list[int] = field(default_factory=list)

    def pick(self, rng: random.Random) -> int:
        if not self.variants:
            return 0
        return rng.choices(self.variants, weights=self.weights or None, k=1)[0]


class TerrainLib:
    """Tereny wyprowadzone z wangsetu tilesetu i z próbek `kind=terrain` katalogu."""

    def __init__(self, floor: Tileset, firstgid: int) -> None:
        self.floor = floor
        self.firstgid = firstgid
        self.wang: WangSet | None = floor.wangset(GRASS_DIRT)
        self.terrains: dict[str, Terrain] = {}
        if self.wang:
            self._from_wangset()

    def _from_wangset(self) -> None:
        """Kafel, którego wszystkie cztery rogi to ten sam kolor, jest wypełnieniem."""
        assert self.wang is not None
        for index, color in enumerate(self.wang.colors, start=1):
            gids = [
                self.firstgid + tid
                for tid, wid in self.wang.tiles.items()
                if len(wid) >= 8 and all(wid[i] == index for i in (1, 3, 5, 7))
            ]
            if gids:
                self.terrains[color] = Terrain(color, sorted(gids), [1] * len(gids))

    def add_from_sample(self, name: str, counts: dict[int, int]) -> Terrain:
        """Teren z próbki w warstwie `stamps`: wagi biorą się z częstości gidów."""
        terrain = Terrain(name, list(counts), list(counts.values()))
        self.terrains[name] = terrain
        return terrain

    def get(self, name: str) -> Terrain:
        if name not in self.terrains:
            raise SystemExit(
                f"nie znam terenu '{name}'. Mam: {', '.join(sorted(self.terrains)) or 'żadnego'}. "
                f"Dodaj próbkę `kind=terrain` o tej nazwie do warstwy `stamps` prototypu."
            )
        return self.terrains[name]

    # ------------------------------------------------------------------
    # MARK: autotiling po rogach

    def paint(self, layer: TileLayer, corners: list[list[str]], rng: random.Random,
              region: tuple[int, int, int, int] | None = None) -> int:
        """Pomaluj warstwę wg siatki ROGÓW (o jeden większej w obu wymiarach).

        `corners[y][x]` to nazwa terenu w rogu (x, y). Kafel (x, y) czyta cztery
        rogi i szuka w wangsecie kafla o takim układzie; kiedy wszystkie cztery
        są tym samym terenem, bierze losowy wariant wypełnienia (bo tych jest
        7, a wangset trzyma tylko jeden reprezentatywny).
        """
        if self.wang is None:
            return 0
        rx, ry, rw, rh = region or (0, 0, layer.width, layer.height)
        index = {name: self.wang.color_index(name) for name in set(
            c for row in corners for c in row)}
        painted = 0
        for y in range(ry, min(ry + rh, layer.height)):
            for x in range(rx, min(rx + rw, layer.width)):
                nw, ne = corners[y][x], corners[y][x + 1]
                se, sw = corners[y + 1][x + 1], corners[y + 1][x]
                if nw == ne == se == sw:
                    gid = self.get(nw).pick(rng)
                else:
                    wangid = (0, index.get(ne, 0), 0, index.get(se, 0),
                              0, index.get(sw, 0), 0, index.get(nw, 0))
                    matches = self.wang.tiles_for(wangid)
                    if not matches:
                        continue
                    gid = self.firstgid + rng.choice(sorted(matches))
                if gid:
                    layer.set(x, y, gid)
                    painted += 1
        return painted

    def corners_from_mask(self, mask: list[list[bool]], inner: str, outer: str,
                          width: int, height: int, threshold: int = 2) -> list[list[str]]:
        """Siatka rogów z maski kafli.

        Róg należy do `inner`, gdy dotyka go co najmniej `threshold` z czterech
        sąsiadujących kafli maski. Próg 1 (czyli "którykolwiek") wydaje się
        naturalny, ale ROZDYMA obszar o kafel z każdej strony - droga szeroka na
        cztery kafle wychodziła wtedy na sześć-siedem i zlewała się w kleks.
        Próg 2 zostawia proste krawędzie tam, gdzie były, i tylko zaokrągla rogi.
        """
        corners = [[outer] * (width + 1) for _ in range(height + 1)]
        for cy in range(height + 1):
            for cx in range(width + 1):
                touching = sum(
                    1
                    for ty, tx in ((cy - 1, cx - 1), (cy - 1, cx), (cy, cx - 1), (cy, cx))
                    if 0 <= ty < height and 0 <= tx < width and mask[ty][tx]
                )
                if touching >= threshold:
                    corners[cy][cx] = inner
        return corners


# --------------------------------------------------------------------------
# MARK: szum i kształty


def value_noise(width: int, height: int, rng: random.Random,
                scale: float = 12.0, octaves: int = 3) -> list[list[float]]:
    """Szum wartościowy w [0, 1] - własna implementacja, bez zależności.

    Kilka oktaw siatki losowych wartości z interpolacją kosinusową. Duża `scale`
    = duże plamy. Wynik jest funkcją WYŁĄCZNIE `rng`, więc mapa odtwarza się
    z ziarna.
    """
    field_out = [[0.0] * width for _ in range(height)]
    amplitude, total = 1.0, 0.0
    for octave in range(octaves):
        step = max(2.0, scale / (2 ** octave))
        gw, gh = int(width / step) + 2, int(height / step) + 2
        grid = [[rng.random() for _ in range(gw)] for _ in range(gh)]
        for y in range(height):
            gy = y / step
            y0 = int(gy)
            fy = (1 - math.cos((gy - y0) * math.pi)) / 2
            for x in range(width):
                gx = x / step
                x0 = int(gx)
                fx = (1 - math.cos((gx - x0) * math.pi)) / 2
                top = grid[y0][x0] * (1 - fx) + grid[y0][x0 + 1] * fx
                bottom = grid[y0 + 1][x0] * (1 - fx) + grid[y0 + 1][x0 + 1] * fx
                field_out[y][x] += (top * (1 - fy) + bottom * fy) * amplitude
        total += amplitude
        amplitude *= 0.5
    return [[value / total for value in row] for row in field_out]


def blob_mask(width: int, height: int, rng: random.Random, coverage: float = 0.35,
              scale: float = 12.0, smooth: int = 1) -> list[list[bool]]:
    """Plama o zadanym pokryciu i postrzępionym brzegu.

    Próg dobierany jest z HISTOGRAMU szumu, a nie z góry - dzięki temu
    `coverage=0.35` naprawdę daje ~35% mapy, niezależnie od tego, jak akurat
    wypadł szum. Potem otwarcie/domknięcie morfologiczne zjada pojedyncze
    piksele, zostawiając brzeg nierówny, ale spójny.
    """
    noise = value_noise(width, height, rng, scale=scale)
    flat = sorted(value for row in noise for value in row)
    cut = flat[min(len(flat) - 1, int(len(flat) * (1 - coverage)))]
    mask = [[noise[y][x] >= cut for x in range(width)] for y in range(height)]
    for _ in range(smooth):
        mask = _morph(mask, width, height, keep=5)   # otwarcie: zjada wypustki
        mask = _morph(mask, width, height, keep=3)   # domknięcie: zasypuje dziury
    return mask


def _morph(mask: list[list[bool]], width: int, height: int, keep: int) -> list[list[bool]]:
    out = [[False] * width for _ in range(height)]
    for y in range(height):
        for x in range(width):
            live = sum(
                mask[y + dy][x + dx]
                for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if 0 <= y + dy < height and 0 <= x + dx < width
            )
            out[y][x] = live >= keep
    return out


def ring_sample(layer: TileLayer, rect: tuple[int, int, int, int],
                rng: random.Random, thickness: int = 2) -> list[int]:
    """Kafle z pierścienia wokół prostokąta - materiał do zasypania dziury po
    przeniesionym budynku. Zasypanie próbką z otoczenia zamiast jednym kaflem
    to jedyny sposób, żeby po przeprowadzce nie została prostokątna łata."""
    rx, ry, rw, rh = rect
    found: list[int] = []
    for y in range(ry - thickness, ry + rh + thickness):
        for x in range(rx - thickness, rx + rw + thickness):
            inside = rx <= x < rx + rw and ry <= y < ry + rh
            if inside or not (0 <= x < layer.width and 0 <= y < layer.height):
                continue
            gid = layer.get(x, y)
            if gid:
                found.append(gid)
    rng.shuffle(found)
    return found


# --------------------------------------------------------------------------
# MARK: wąskie ścieżki


N, E, S, W = 1, 2, 4, 8


@dataclass
class PathKit:
    """Kafle ścieżki szerokiej na jeden kafel, wyuczone z próbki narysowanej w Tiled.

    W odróżnieniu od płotu nie ma tu żadnego ustalonego układu: autor rysuje
    dowolny spójny kształt ścieżki, a my dla KAŻDEGO kafla próbki liczymy maskę
    sąsiedztwa (które z czterech sąsiadów też należą do ścieżki) i zapamiętujemy
    "przy takim układzie wygląda tak". Kilka kafli o tej samej masce zostaje
    wariantami - i dobrze, bo dzięki temu trakt nie powtarza się co kafel.
    """

    name: str = ""
    pieces: dict[int, list[int]] = field(default_factory=dict)

    @classmethod
    def from_grid(cls, name: str, rows: list[list[int]],
                  background: set[int] | None = None) -> "PathKit | None":
        """`background` to kafle terenu, na którym narysowano próbkę.

        Bez tego dekoder bierze trawę tła za ścieżkę: w prostokącie próbki
        wszystkie kafle są niepuste, więc "należy do ścieżki" nie może znaczyć
        po prostu "niezerowy gid".
        """
        skip = background or set()
        height = len(rows)
        width = len(rows[0]) if height else 0
        if not width:
            return None

        def is_path(px: int, py: int) -> bool:
            return (0 <= px < width and 0 <= py < height
                    and bool(rows[py][px]) and rows[py][px] not in skip)

        kit = cls(name=name)
        for y in range(height):
            for x in range(width):
                gid = rows[y][x]
                if not is_path(x, y):
                    continue
                mask = 0
                if is_path(x, y - 1):
                    mask |= N
                if is_path(x + 1, y):
                    mask |= E
                if is_path(x, y + 1):
                    mask |= S
                if is_path(x - 1, y):
                    mask |= W
                kit.pieces.setdefault(mask, [])
                if gid not in kit.pieces[mask]:
                    kit.pieces[mask].append(gid)
        return kit if kit.pieces else None

    def piece(self, mask: int, rng: random.Random) -> int:
        """Kafel dla danego układu sąsiadów, z wariantami.

        Gdy próbka nie zna dokładnie tego układu (np. skrzyżowanie, którego autor
        nie narysował), schodzimy do najbliższego podzbioru - lepiej położyć
        prostą ścieżkę niż zostawić dziurę w trakcie.
        """
        for candidate in (mask, mask & (N | S), mask & (E | W), N | S, E | W):
            options = self.pieces.get(candidate)
            if options:
                return rng.choice(options)
        any_piece = next(iter(self.pieces.values()), [0])
        return rng.choice(any_piece) if any_piece else 0


def draw_path(layer: TileLayer, cells: Iterable[tuple[int, int]], kit: PathKit,
              rng: random.Random) -> int:
    """Połóż ścieżkę na podanych kaflach, dobierając kafle po sąsiedztwie."""
    path = set(cells)
    laid = 0
    for x, y in sorted(path):
        mask = 0
        if (x, y - 1) in path:
            mask |= N
        if (x + 1, y) in path:
            mask |= E
        if (x, y + 1) in path:
            mask |= S
        if (x - 1, y) in path:
            mask |= W
        gid = kit.piece(mask, rng)
        if gid:
            layer.set(x, y, gid)
            laid += 1
    return laid


def pathkits_from_palette(palette: "object",
                          background: set[int] | None = None) -> dict[str, PathKit]:
    """Wszystkie zestawy ścieżek z katalogu (`kind=pathkit`)."""
    found: dict[str, PathKit] = {}
    for stamp in palette.of_kind("pathkit"):          # type: ignore[attr-defined]
        kit = PathKit.from_grid(stamp.name, stamp.gids("ground"), background)
        if kit is not None:
            found[stamp.name] = kit
    return found
