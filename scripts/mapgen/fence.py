#!/usr/bin/env python3
"""Ogrodzenia o dowolnym kształcie z segmentów wyciętych z katalogu klocków.

Płoty w prototypie są narysowane jako gotowe demo-zagrody, ale wszystkie trzy
(`fence_wood`, `wall_stone`, `fence_rail_dark`) mają IDENTYCZNY układ, więc da
się z nich odczytać komplet segmentów po pozycjach - bez proszenia autora
o przerysowywanie czegokolwiek:

    NW  H   T↓  H   H   H   NE          rząd 0:  narożniki i krawędź pozioma
    V   .   V   .   .   .   V           rząd 1:  krawędź pionowa
    SW  H   T↑  ]   .   [   SE          rząd 2:  dolne narożniki, zaślepki

Mając te dziesięć kafli, ogrodzenie dowolnego kształtu składa się **maską
sąsiedztwa**: dla każdego kafla obwodu patrzymy, którzy z czterech sąsiadów też
należą do obwodu, i to wybiera segment. Ta sama zasada obsługuje prostokąt,
literę L i zagrodę z wewnętrzną przegrodą - bez osobnych przypadków.

Brakujące w zestawie segmenty (trójnik w bok, skrzyżowanie, zaślepka pionowa)
degradują się do najbliższej krawędzi zamiast zostawiać dziurę: lepiej mieć
ciągły płot z jednym uproszczonym kafelkiem niż otwór, którym ucieka krowa.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable

from palette import Palette, Stamp
from tmx import TileLayer

# Kierunki jako bity maski sąsiedztwa: N=1, E=2, S=4, W=8.
N, E, S, W = 1, 2, 4, 8


@dataclass
class FenceKit:
    """Dziesięć kafli, z których składa się dowolne ogrodzenie."""

    name: str = ""
    nw: int = 0
    ne: int = 0
    sw: int = 0
    se: int = 0
    horizontal: int = 0
    vertical: int = 0
    tee_down: int = 0      # krawędź pozioma z odgałęzieniem w dół
    tee_up: int = 0        # krawędź pozioma z odgałęzieniem w górę
    cap_east: int = 0      # koniec biegu poziomego od wschodu
    cap_west: int = 0      # koniec biegu poziomego od zachodu

    @classmethod
    def from_stamp(cls, stamp: Stamp) -> "FenceKit | None":
        """Odczytaj zestaw z demo-zagrody po pozycjach (patrz docstring modułu)."""
        if stamp.w < 6 or stamp.h < 3:
            return None
        walls = stamp.gids("walls")
        last_x, last_y = stamp.w - 1, stamp.h - 1
        kit = cls(
            name=stamp.name,
            nw=walls[0][0], ne=walls[0][last_x],
            sw=walls[last_y][0], se=walls[last_y][last_x],
            horizontal=walls[0][1], vertical=walls[1][0],
            tee_down=walls[0][2], tee_up=walls[last_y][2],
            cap_east=walls[last_y][3], cap_west=walls[last_y][last_x - 1],
        )
        # zestaw bez narożników albo bez krawędzi jest bezużyteczny
        if not (kit.nw and kit.ne and kit.sw and kit.se and kit.horizontal and kit.vertical):
            return None
        return kit

    def piece(self, mask: int) -> int:
        """Segment dla danej maski sąsiedztwa (N|E|S|W)."""
        table = {
            E | S: self.nw,
            S | W: self.ne,
            N | E: self.sw,
            N | W: self.se,
            E | W: self.horizontal,
            N | S: self.vertical,
            E | S | W: self.tee_down or self.horizontal,
            N | E | W: self.tee_up or self.horizontal,
            E: self.cap_west or self.horizontal,
            W: self.cap_east or self.horizontal,
            N: self.vertical,
            S: self.vertical,
            # brakujące w zestawie: trójniki w bok i skrzyżowanie
            N | E | S: self.vertical,
            N | S | W: self.vertical,
            N | E | S | W: self.vertical,
            0: self.horizontal,
        }
        return table.get(mask, self.horizontal)


def kits_from_palette(palette: Palette) -> dict[str, FenceKit]:
    """Wszystkie zestawy, jakie da się odczytać z klocków rodzaju `fence`/`wall`."""
    found: dict[str, FenceKit] = {}
    for stamp in palette.of_kind("fence") + palette.of_kind("wall"):
        kit = FenceKit.from_stamp(stamp)
        if kit is not None:
            found[stamp.name] = kit
    return found


# --------------------------------------------------------------------------
# MARK: rysowanie


def _components(ring: set[tuple[int, int]]) -> int:
    """Ile rozłącznych kawałków tworzy obwód."""
    remaining = set(ring)
    count = 0
    while remaining:
        count += 1
        queue = [remaining.pop()]
        while queue:
            x, y = queue.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (x + dx, y + dy)
                if nxt in remaining:
                    remaining.discard(nxt)
                    queue.append(nxt)
    return count


def _drop_short_runs(ring: set[tuple[int, int]], min_run: int) -> set[tuple[int, int]]:
    """Zostaw tylko spójne odcinki płotu o długości co najmniej `min_run`."""
    if min_run <= 1:
        return ring
    remaining = set(ring)
    kept: set[tuple[int, int]] = set()
    while remaining:
        seed = remaining.pop()
        run = {seed}
        queue = [seed]
        while queue:
            x, y = queue.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (x + dx, y + dy)
                if nxt in remaining:
                    remaining.discard(nxt)
                    run.add(nxt)
                    queue.append(nxt)
        if len(run) >= min_run:
            kept |= run
    return kept


def outline(cells: Iterable[tuple[int, int]]) -> set[tuple[int, int]]:
    """Kafle obwodu obszaru: te, którym brakuje choć jednego sąsiada z czwórki."""
    inside = set(cells)
    return {
        (x, y) for x, y in inside
        if not all((x + dx, y + dy) in inside
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    }


def rect_cells(x: int, y: int, w: int, h: int) -> set[tuple[int, int]]:
    return {(x + dx, y + dy) for dy in range(h) for dx in range(w)}


def draw_fence(layer: TileLayer, cells: Iterable[tuple[int, int]], kit: FenceKit,
               gates: int = 1, rng: random.Random | None = None,
               skip: Iterable[tuple[int, int]] = (),
               gate_toward: tuple[int, int] | None = None,
               gate_width: int = 2, min_run: int = 4,
               openings: Iterable[tuple[int, int]] = ()) -> set[tuple[int, int]]:
    """Postaw ogrodzenie na obwodzie obszaru. Zwraca kafle, na których stanął płot.

    `gates` to liczba przerw na wejście - bez nich zagroda jest pułapką, do której
    nie ma jak wejść (i którą linter słusznie zgłosi jako obszar nieosiągalny).
    `gate_toward` przesuwa bramę na tę stronę zagrody, która jest najbliżej
    podanego punktu (zwykle drogi) - brama od tyłu, przez las, wygląda jak błąd,
    nawet gdy A* sobie z nią radzi.
    `skip` wyłącza kafle, na których już coś stoi (np. ściana domu).
    `openings` to furtki wymuszone z zewnątrz - kafle, przez które biegnie już
    wydeptana ścieżka. Wycinamy je PO sprawdzeniu spójności obwodu, bo inaczej
    ścieżka przecinająca zagrodę rozbijałaby obwód na kawałki i ogrodzenie nie
    powstawałoby wcale, zamiast dostać w tym miejscu furtkę.
    `min_run` wyrzuca odcinki krótsze niż tyle kafli: gdy zagroda zostanie
    przycięta drogą, w obwodzie zostają pojedyncze ogryzki płotu, które czytają
    się jak śmieć, a nie jak ogrodzenie.
    """
    rng = rng or random.Random(0)
    ring = outline(cells) - set(skip)
    ring = _drop_short_runs(ring, min_run)
    if not ring:
        return set()
    # Ogrodzenie ma być JEDNYM zamkniętym obrysem albo nie powstać wcale.
    # Człowiek nie stawia wokół domu trzech niezależnych kawałków płotu - a
    # dokładnie to wychodziło, gdy droga rozcięła zagrodę na kilka części
    # i każda z osobna przechodziła próg `min_run`.
    if _components(ring) > 1:
        return set()
    ring -= set(openings)

    # Bramy wycinamy PRZED policzeniem masek, żeby po obu stronach przerwy
    # wyszły zaślepki, a nie urwana krawędź.
    openings: set[tuple[int, int]] = set()
    for _ in range(max(0, gates)):
        free = sorted(ring - openings)
        if len(free) < 6:
            break
        if gate_toward is not None:
            gx, gy = gate_toward
            spot = min(free, key=lambda c: (c[0] - gx) ** 2 + (c[1] - gy) ** 2)
        else:
            spot = rng.choice(free)
        openings.add(spot)
        # brama szersza niż kafel: dokładamy sąsiadów wzdłuż tej samej krawędzi
        for _extra in range(max(0, gate_width - 1)):
            neighbours = [c for c in ((spot[0] + 1, spot[1]), (spot[0] - 1, spot[1]),
                                      (spot[0], spot[1] + 1), (spot[0], spot[1] - 1))
                          if c in ring and c not in openings]
            if not neighbours:
                break
            spot = neighbours[0]
            openings.add(spot)
    ring -= openings

    placed: set[tuple[int, int]] = set()
    for x, y in ring:
        mask = 0
        if (x, y - 1) in ring:
            mask |= N
        if (x + 1, y) in ring:
            mask |= E
        if (x, y + 1) in ring:
            mask |= S
        if (x - 1, y) in ring:
            mask |= W
        gid = kit.piece(mask)
        if gid:
            layer.set(x, y, gid)
            placed.add((x, y))
    return placed
