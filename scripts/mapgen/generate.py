#!/usr/bin/env python3
"""Generator map zewnętrznych: brief (TOML) -> gotowy plik .tmx.

Podział pracy jest tu celowy i wart zapamiętania: **model pisze BRIEF, kod robi
GEOMETRIĘ**. Brief wyraża zamiar ("droga wije się ze wschodu na zachód, po obu
stronach zagrody, na północy pola, dookoła las"), a nie współrzędne każdego
domu - bo modelowi trudno rozstawić dwadzieścia budynków, nie widząc terenu,
a kodowi trudno wymyślić, że wieś ma mieć owalny plac ze studnią.

Osiem przebiegów (2-7 są czystymi funkcjami ziarna i briefu, więc to samo
ziarno daje ten sam plik):

    1. brief     wczytanie i walidacja zamiaru
    2. teren     wypełnienie bazowe z wariantami + plamy biomów
    3. drogi     krzywe Catmull-Roma -> maska -> autotiling wangsetem
    4. natura    las obrzeżny z szumu, gęstość malejąca ku środkowi
    5. zabudowa  stemplowanie wzdłuż dróg z jitterem + odnoga A* do drzwi
    6. detale    rekwizyty i roślinność, gęściej przy drodze
    7. obiekty   wszystkie sześć warstw obiektowych
    8. zapis     .tmx z ziarnem i briefem we właściwościach

Użycie:

    just map-new brief.toml
    just map-new brief.toml --seed 123 --out-dir project/assets/.../maps/_wip
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import random
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from palette import Palette, Stamp
from terrain import TerrainLib, blob_mask
from tileset import Tileset
from tmx import (
    EMPTY,
    MapObject,
    ObjectGroup,
    TiledMap,
    TileLayer,
    maps_dir,
    new_outdoor_map,
)

WIP_DIR = maps_dir() / "_wip"


# --------------------------------------------------------------------------
# MARK: brief


@dataclass
class Road:
    name: str = "main"
    width: int = 3
    points: list[tuple[float, float]] = field(default_factory=list)
    terrain: str = "dirt"


@dataclass
class District:
    """Pas zabudowy wzdłuż drogi. Generator sam rozstawia budynki, z jitterem."""

    name: str = ""
    along: str = "main"
    side: str = "north"                # north | south | east | west | both
    stamps: list[str] = field(default_factory=list)
    spacing: tuple[int, int] = (7, 13)
    setback: tuple[int, int] = (2, 5)
    count: int = 0                     # 0 = ile się zmieści


@dataclass
class Biome:
    kind: str = "forest"               # forest | grove | patch
    stamps: list[str] = field(default_factory=list)
    coverage: float = 0.25
    scale: float = 16.0
    shape: str = "border"              # border | patch
    density: float = 0.35
    margin: int = 0


@dataclass
class Brief:
    name: str = "NEW_MAP"
    width: int = 128
    height: int = 128
    seed: int = 0
    base: str = "grass"
    particles: str = "leafs,rain"
    roads: list[Road] = field(default_factory=list)
    districts: list[District] = field(default_factory=list)
    biomes: list[Biome] = field(default_factory=list)
    plaza: dict[str, object] = field(default_factory=dict)
    props: list[dict[str, object]] = field(default_factory=list)
    entries: list[dict[str, object]] = field(default_factory=list)
    places: list[dict[str, object]] = field(default_factory=list)
    spawns: list[dict[str, object]] = field(default_factory=list)
    zones: list[dict[str, object]] = field(default_factory=list)
    exits: list[dict[str, object]] = field(default_factory=list)
    source: str = ""

    @classmethod
    def load(cls, path: str | Path) -> Brief:
        path = Path(path)
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        brief = cls(source=path.read_text(encoding="utf-8"))
        brief.name = str(raw.get("name", brief.name))
        size = raw.get("size", [brief.width, brief.height])
        brief.width, brief.height = int(size[0]), int(size[1])
        brief.seed = int(raw.get("seed", 0)) or random.randint(0, 2**31 - 1)
        brief.base = str(raw.get("base", brief.base))
        brief.particles = str(raw.get("particles", brief.particles))

        for item in raw.get("road", []):
            brief.roads.append(Road(
                name=str(item.get("name", "main")),
                width=int(item.get("width", 3)),
                points=[(float(p[0]), float(p[1])) for p in item.get("points", [])],
                terrain=str(item.get("terrain", "dirt")),
            ))
        for item in raw.get("district", []):
            brief.districts.append(District(
                name=str(item.get("name", "")),
                along=str(item.get("along", "main")),
                side=str(item.get("side", "north")),
                stamps=[str(s) for s in item.get("stamps", [])],
                spacing=tuple(item.get("spacing", (7, 13))),      # type: ignore[arg-type]
                setback=tuple(item.get("setback", (2, 5))),       # type: ignore[arg-type]
                count=int(item.get("count", 0)),
            ))
        for item in raw.get("biome", []):
            brief.biomes.append(Biome(
                kind=str(item.get("kind", "forest")),
                stamps=[str(s) for s in item.get("stamps", [])],
                coverage=float(item.get("coverage", 0.25)),
                scale=float(item.get("scale", 16.0)),
                shape=str(item.get("shape", "border")),
                density=float(item.get("density", 0.35)),
                margin=int(item.get("margin", 0)),
            ))
        brief.plaza = dict(raw.get("plaza", {}))
        for key in ("prop", "entry", "place", "spawn", "zone", "exit"):
            target = {"prop": brief.props, "entry": brief.entries, "place": brief.places,
                      "spawn": brief.spawns, "zone": brief.zones, "exit": brief.exits}[key]
            target.extend(dict(item) for item in raw.get(key, []))
        return brief


# --------------------------------------------------------------------------
# MARK: geometria


def catmull_rom(points: list[tuple[float, float]], samples: int = 24
                ) -> list[tuple[float, float]]:
    """Gładka krzywa przez podane punkty - stąd biorą się "szerokie łuki" drogi."""
    if len(points) < 2:
        return list(points)
    pts = [points[0]] + list(points) + [points[-1]]
    out: list[tuple[float, float]] = []
    for i in range(len(pts) - 3):
        p0, p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        for step in range(samples):
            t = step / samples
            t2, t3 = t * t, t * t * t
            out.append((
                0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
                0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3),
            ))
    out.append(points[-1])
    return out


def stroke(mask: list[list[bool]], path: list[tuple[float, float]], width: int,
           rng: random.Random, jitter: float = 0.6) -> None:
    """Odbij krzywą w masce pędzlem o zadanej szerokości, z drżącym brzegiem.

    Bez `jitter` droga ma idealnie równe krawędzie i czyta się jak asfalt,
    a nie jak wydeptany trakt.
    """
    height, width_map = len(mask), len(mask[0])
    for cx, cy in path:
        radius = width / 2 + rng.uniform(-jitter, jitter)
        r_int = int(radius) + 1
        for dy in range(-r_int, r_int + 1):
            for dx in range(-r_int, r_int + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue
                x, y = int(cx) + dx, int(cy) + dy
                if 0 <= x < width_map and 0 <= y < height:
                    mask[y][x] = True


def ellipse(mask: list[list[bool]], center: tuple[int, int], radii: tuple[int, int],
            rng: random.Random, wobble: float = 0.12) -> None:
    """Owalny plac - z lekkim falowaniem promienia, żeby nie był z cyrkla."""
    cx, cy = center
    rx, ry = radii
    height, width = len(mask), len(mask[0])
    phase = rng.uniform(0, 6.28)
    for y in range(max(0, cy - ry - 2), min(height, cy + ry + 3)):
        for x in range(max(0, cx - rx - 2), min(width, cx + rx + 3)):
            dx, dy = (x - cx) / max(1, rx), (y - cy) / max(1, ry)
            import math
            angle = math.atan2(dy, dx)
            limit = 1.0 + wobble * math.sin(angle * 3 + phase)
            if dx * dx + dy * dy <= limit * limit:
                mask[y][x] = True


def astar(walk: list[list[bool]], cost: list[list[int]], start: tuple[int, int],
          goals: set[tuple[int, int]]) -> list[tuple[int, int]]:
    """Najtańsza droga do najbliższego z celów. Ten sam algorytm, którym chodzą NPC,
    więc "nie ma dojścia do stodoły" wychodzi już przy stawianiu, a nie po zrzucie."""
    if not goals:
        return []
    height, width = len(walk), len(walk[0])
    queue: list[tuple[int, int, tuple[int, int]]] = [(0, 0, start)]
    came: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    best: dict[tuple[int, int], int] = {start: 0}
    while queue:
        _, spent, node = heapq.heappop(queue)
        if node in goals:
            path = []
            step: tuple[int, int] | None = node
            while step is not None:
                path.append(step)
                step = came[step]
            return list(reversed(path))
        x, y = node
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if not (0 <= nx < width and 0 <= ny < height) or not walk[ny][nx]:
                continue
            nxt = spent + cost[ny][nx]
            if nxt < best.get((nx, ny), 1 << 30):
                best[(nx, ny)] = nxt
                came[(nx, ny)] = node
                heapq.heappush(queue, (nxt, nxt, (nx, ny)))
    return []


# --------------------------------------------------------------------------
# MARK: generator


class Generator:
    def __init__(self, brief: Brief, palette: Palette) -> None:
        self.brief = brief
        self.palette = palette
        self.rng = random.Random(brief.seed)
        self.tmap = new_outdoor_map(
            WIP_DIR / f"{brief.name}.tmx", brief.width, brief.height, brief.particles)
        floor = Tileset.load(maps_dir() / "tilesets" / "Floor.tsx")
        self.terrain = TerrainLib(floor, 477)
        self._load_terrain_samples()
        self.road_mask = [[False] * brief.width for _ in range(brief.height)]
        self.taken = [[False] * brief.width for _ in range(brief.height)]
        self.road_paths: dict[str, list[tuple[float, float]]] = {}
        self.notes: list[str] = []

    def _load_terrain_samples(self) -> None:
        """Próbki `kind=terrain` z katalogu dopisują się do terenów z wangsetu."""
        for stamp in self.palette.of_kind("terrain"):
            counts = self.palette.terrain_variants(stamp.name, "ground")
            if counts and stamp.name not in self.terrain.terrains:
                self.terrain.add_from_sample(stamp.name, counts)

    # ---------------- przebiegi ----------------

    def run(self) -> TiledMap:
        self.pass_terrain()
        self.pass_roads()
        self.pass_nature()
        self.pass_seal_border()
        self.pass_districts()
        self.pass_props()
        self.pass_objects()
        self.pass_stamp_meta()
        return self.tmap

    # 2. teren
    def pass_terrain(self) -> None:
        ground = self.tmap.tile_layer("ground")
        base = self.terrain.get(self.brief.base)
        for y in range(self.tmap.height):
            for x in range(self.tmap.width):
                ground.set(x, y, base.pick(self.rng))

    # 3. drogi
    def pass_roads(self) -> None:
        if not self.brief.roads:
            return
        for road in self.brief.roads:
            path = catmull_rom(road.points)
            self.road_paths[road.name] = path
            stroke(self.road_mask, path, road.width, self.rng)
        if self.brief.plaza:
            at = self.brief.plaza.get("at", [self.tmap.width // 2, self.tmap.height // 2])
            radii = self.brief.plaza.get("radius", [10, 7])
            ellipse(self.road_mask, (int(at[0]), int(at[1])),      # type: ignore[index]
                    (int(radii[0]), int(radii[1])), self.rng)      # type: ignore[index]
        self._paint_mask(self.road_mask, self.brief.roads[0].terrain)

    def _paint_mask(self, mask: list[list[bool]], inner: str) -> None:
        ground = self.tmap.tile_layer("ground")
        corners = self.terrain.corners_from_mask(
            mask, inner, self.brief.base, self.tmap.width, self.tmap.height)
        self.terrain.paint(ground, corners, self.rng)

    # 4. natura
    def pass_nature(self) -> None:
        for biome in self.brief.biomes:
            mask = self._biome_mask(biome)
            stamps = [self.palette.get(name) for name in biome.stamps] or \
                     self.palette.of_kind("nature")
            self._scatter(mask, stamps, biome.density, avoid_roads=True)

    def _biome_mask(self, biome: Biome) -> list[list[bool]]:
        width, height = self.tmap.width, self.tmap.height
        if biome.shape == "border":
            # Las obrzeżny: plama tym gęstsza, im dalej od środka mapy. Prostokątna
            # ramka lasu jest pierwszą rzeczą, po której widać maszynę, więc próg
            # zależy od odległości, a nie od granicy.
            noise = blob_mask(width, height, self.rng, coverage=0.75, scale=biome.scale)
            mask = [[False] * width for _ in range(height)]
            reach = min(width, height) / 2
            band = max(3.0, reach * biome.coverage)   # głębokość pasa lasu, w kaflach
            for y in range(height):
                for x in range(width):
                    edge = min(x, y, width - 1 - x, height - 1 - y)
                    if edge < biome.margin:
                        mask[y][x] = True             # szczelny skraj mapy
                        continue
                    if edge > band:
                        continue
                    # gęsto przy krawędzi, coraz rzadziej ku środkowi - żeby las
                    # przechodził w łąkę, a nie kończył się linijką
                    fade = 1.0 - (edge - biome.margin) / max(1.0, band - biome.margin)
                    mask[y][x] = noise[y][x] and self.rng.random() < fade ** 0.6
            return mask
        return blob_mask(width, height, self.rng,
                         coverage=biome.coverage, scale=biome.scale)

    def _scatter(self, mask: list[list[bool]], stamps: list[Stamp], density: float,
                 avoid_roads: bool = True) -> int:
        placed = 0
        for y in range(self.tmap.height):
            for x in range(self.tmap.width):
                if not mask[y][x] or self.rng.random() > density:
                    continue
                stamp = self.rng.choice(stamps)
                if self._place(stamp, x - stamp.w // 2, y - stamp.h // 2,
                               avoid_roads=avoid_roads):
                    placed += 1
        return placed

    def pass_seal_border(self) -> None:
        """Domknij skraj mapy kaflami nieprzechodnimi.

        Samo rozsypanie drzew w pasie brzegowym NIE wystarcza: klocek 2x2 albo
        3x3 nie wchodzi w każdą lukę, więc po przebiegu natury zostają dziury,
        którymi gracz wychodzi na granicę świata (linter mówi wtedy "N osiągalnych
        kafli na krawędzi"). Tu dokładamy pojedyncze kafle blokujące, losowane
        z tych, które wnoszą klocki natury - żeby ściana lasu nie była jednolita.
        """
        margin = max((b.margin for b in self.brief.biomes), default=0)
        if margin <= 0:
            return
        walls = self.tmap.tile_layer("walls")
        fill = sorted({
            walls_gid
            for stamp in self.palette.of_kind("nature")
            for row in stamp.gids("walls") for walls_gid in row if walls_gid
        })
        if not fill:
            return
        sealed = 0
        for y in range(self.tmap.height):
            for x in range(self.tmap.width):
                edge = min(x, y, self.tmap.width - 1 - x, self.tmap.height - 1 - y)
                if edge >= margin or walls.get(x, y):
                    continue
                if self.road_mask[y][x]:
                    continue          # trakt wychodzący poza mapę to zamierzone wyjście
                walls.set(x, y, self.rng.choice(fill))
                self.taken[y][x] = True
                sealed += 1
        if sealed:
            self.notes.append(f"brzeg domknięty {sealed} kaflami (pas {margin} kafli)")

    # 5. zabudowa
    def pass_districts(self) -> None:
        had_roads = bool(self.brief.roads)
        for district in self.brief.districts:
            path = self.road_paths.get(district.along)
            if not path:
                self.notes.append(f"dzielnica '{district.name}': nie ma drogi "
                                  f"'{district.along}', pomijam")
                continue
            self._build_along(district, path)
        # jedno przemalowanie po wszystkich odnogach zamiast jednego na budynek:
        # przemalowanie to koszt całej mapy, a odnóg bywa kilkadziesiąt
        if had_roads:
            self._paint_mask(self.road_mask, self.brief.roads[0].terrain)

    @staticmethod
    def _arc_index(path: list[tuple[float, float]]) -> list[float]:
        """Długość krzywej narastająco - żeby `spacing` z briefu znaczyło KAFLE,
        a nie próbki. Bez tego gęstość zabudowy zależy od tego, jak gęsto akurat
        próbkowaliśmy splajn, czyli od szczegółu implementacji."""
        out = [0.0]
        for i in range(1, len(path)):
            dx = path[i][0] - path[i - 1][0]
            dy = path[i][1] - path[i - 1][1]
            out.append(out[-1] + (dx * dx + dy * dy) ** 0.5)
        return out

    def _build_along(self, district: District, path: list[tuple[float, float]]) -> None:
        stamps = [self.palette.get(name) for name in district.stamps]
        if not stamps:
            return
        sides = ["north", "south"] if district.side == "both" else [district.side]
        arc = self._arc_index(path)
        sides_cursor = {side: float(self.rng.randint(*district.spacing)) for side in sides}
        built = 0
        cursor = 0
        while cursor < len(path) - 2:
            for side in sides:
                if district.count and built >= district.count:
                    return
                if arc[cursor] < sides_cursor[side]:
                    continue
                stamp = self.rng.choice(stamps)
                spot = self._spot_beside(path, cursor, side, district, stamp)
                if spot and self._place(stamp, *spot, avoid_roads=True):
                    built += 1
                    self._connect_to_road(stamp, spot)
                    # jitter odstępu: równe odstępy czytają się jak kratka, nie jak wieś
                    sides_cursor[side] = arc[cursor] + self.rng.randint(*district.spacing)
                else:
                    sides_cursor[side] = arc[cursor] + 2
            cursor += 1

    def _spot_beside(self, path: list[tuple[float, float]], index: int, side: str,
                     district: District, stamp: Stamp) -> tuple[int, int] | None:
        cx, cy = path[index]
        px, py = path[max(0, index - 1)]
        dx, dy = cx - px, cy - py
        length = max(1e-6, (dx * dx + dy * dy) ** 0.5)
        # normalna do kierunku drogi - budynek odsuwa się prostopadle
        nx, ny = -dy / length, dx / length
        if side in ("south", "east"):
            nx, ny = -nx, -ny
        # `setback` to odstęp od KRAWĘDZI traktu do bliższej ściany budynku;
        # połowa szerokości drogi i połowa bryły dochodzą osobno, żeby liczba
        # z briefu znaczyła to, co czyta się w promptcie ("cztery kafle od drogi")
        road_half = self.brief.roads[0].width / 2 if self.brief.roads else 2
        back = road_half + self.rng.randint(*district.setback) + stamp.h / 2
        ox = int(cx + nx * back - stamp.w / 2)
        oy = int(cy + ny * back - stamp.h / 2)
        # jitter pozycji: bez tego budynki układają się w idealną linię
        ox += self.rng.randint(-1, 1)
        oy += self.rng.randint(-1, 1)
        if not (0 <= ox and ox + stamp.w < self.tmap.width
                and 0 <= oy and oy + stamp.h < self.tmap.height):
            return None
        return ox, oy

    def _connect_to_road(self, stamp: Stamp, at: tuple[int, int]) -> None:
        """Odnoga od progu drzwi do drogi, wyznaczona A* po koszcie kroku."""
        approach = stamp.approach_tile()
        if approach is None:
            return
        sx, sy = at[0] + approach[0], at[1] + approach[1]
        if not (0 <= sx < self.tmap.width and 0 <= sy < self.tmap.height):
            return
        walls = self.tmap.tile_layer("walls")
        walk = [[walls.get(x, y) == EMPTY for x in range(self.tmap.width)]
                for y in range(self.tmap.height)]
        walk[sy][sx] = True
        cost = [[1 if self.road_mask[y][x] else 4 for x in range(self.tmap.width)]
                for y in range(self.tmap.height)]
        goals = self._road_tiles()
        path = astar(walk, cost, (sx, sy), goals)
        if not path:
            self.notes.append(f"klocek '{stamp.name}' w {at}: A* nie znalazł drogi "
                              f"od drzwi do traktu - sprawdź ten budynek")
            return
        for x, y in path:
            self.road_mask[y][x] = True

    def _road_tiles(self) -> set[tuple[int, int]]:
        return {(x, y)
                for y in range(self.tmap.height) for x in range(self.tmap.width)
                if self.road_mask[y][x]}

    def _place(self, stamp: Stamp, x: int, y: int, avoid_roads: bool = True) -> bool:
        """Postaw klocek, jeśli miejsce jest wolne. Zwraca, czy się udało."""
        if x < 0 or y < 0 or x + stamp.w > self.tmap.width or y + stamp.h > self.tmap.height:
            return False
        for dy in range(stamp.h):
            for dx in range(stamp.w):
                if self.taken[y + dy][x + dx]:
                    return False
                if avoid_roads and self.road_mask[y + dy][x + dx]:
                    return False
        self.palette.paste(self.tmap, stamp.name, (x, y),
                           layers=["foliage", "items", "walls", "over"], clear=False)
        for dy in range(stamp.h):
            for dx in range(stamp.w):
                self.taken[y + dy][x + dx] = True
        return True

    # 6. detale
    def pass_props(self) -> None:
        """Rekwizyty na trzy sposoby: `at` (dokładnie tu), `count` (tyle sztuk
        gdziekolwiek) i `density` w prostokącie (dywan detali). Ten trzeci jest
        lekiem na "połać bez jednego detalu", którą zgłasza linter."""
        for spec in self.brief.props:
            names = spec.get("stamps") or [spec["stamp"]]
            stamps = [self.palette.get(str(name)) for name in names]  # type: ignore[union-attr]
            at = spec.get("at")
            if at:
                self._place(stamps[0], int(at[0]), int(at[1]),        # type: ignore[index]
                            avoid_roads=False)
                continue

            rect = spec.get("rect")
            area = (int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])) if rect \
                else (0, 0, self.tmap.width, self.tmap.height)        # type: ignore[index]
            density = float(spec.get("density", 0))                   # type: ignore[arg-type]
            if density > 0:
                # gęstość maleje przy drodze - pobocze traktu jest wydeptane
                for y in range(area[1], min(area[1] + area[3], self.tmap.height)):
                    for x in range(area[0], min(area[0] + area[2], self.tmap.width)):
                        near_road = any(
                            self.road_mask[y + dy][x + dx]
                            for dy in (-2, 0, 2) for dx in (-2, 0, 2)
                            if 0 <= y + dy < self.tmap.height and 0 <= x + dx < self.tmap.width
                        )
                        chance = density * (0.25 if near_road else 1.0)
                        if self.rng.random() < chance:
                            self._place(self.rng.choice(stamps), x, y)
                continue

            for _ in range(int(spec.get("count", 1))):                # type: ignore[arg-type]
                for _try in range(60):
                    stamp = self.rng.choice(stamps)
                    x = self.rng.randrange(max(1, area[2] - stamp.w)) + area[0]
                    y = self.rng.randrange(max(1, area[3] - stamp.h)) + area[1]
                    if self._place(stamp, x, y):
                        break

    # 7. obiekty
    def pass_objects(self) -> None:
        tile = self.tmap.tilewidth
        for spec in self.brief.entries:
            at = spec["at"]
            self.tmap.add_object("entry_points", MapObject(
                name=str(spec["name"]), shape="point",
                x=float(at[0]) * tile + tile / 2, y=float(at[1]) * tile + tile / 2))
        for spec in self.brief.places:
            at = spec["at"]
            self.tmap.add_object("places", MapObject(
                name=str(spec["name"]),
                x=float(at[0]) * tile + tile / 2, y=float(at[1]) * tile + tile))
        for spec in self.brief.zones:
            rect = spec["rect"]
            self.tmap.add_object("zones", MapObject(
                name=str(spec["name"]),
                x=float(rect[0]) * tile, y=float(rect[1]) * tile,
                width=float(rect[2]) * tile, height=float(rect[3]) * tile))
        for spec in self.brief.exits:
            at = spec["at"]
            obj = MapObject(name=str(spec["name"]),
                            x=float(at[0]) * tile, y=float(at[1]) * tile,
                            width=float(tile), height=float(tile))
            obj.props.set("obj_type", "exit")
            for key in ("to_map", "destination_entry_point", "return_entry_point",
                        "requires_item"):
                if spec.get(key):
                    obj.props.set(key, str(spec[key]))
            self.tmap.add_object("interactions", obj)

    # 8. metadane
    def pass_stamp_meta(self) -> None:
        self.tmap.props.set_int("gen_seed", self.brief.seed)
        digest = hashlib.sha256(self.brief.source.encode("utf-8")).hexdigest()[:12]
        self.tmap.props.set("gen_brief", digest)


# --------------------------------------------------------------------------
# MARK: CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("brief", help="plik TOML z briefem mapy")
    parser.add_argument("--seed", type=int, help="nadpisz ziarno z briefu")
    parser.add_argument("--out-dir", default=str(WIP_DIR))
    parser.add_argument("--palette", help="mapa z katalogiem klocków")
    args = parser.parse_args(argv)

    brief = Brief.load(args.brief)
    if args.seed is not None:
        brief.seed = args.seed
    palette = Palette.load(Path(args.palette) if args.palette else None)

    generator = Generator(brief, palette)
    tmap = generator.run()
    out = Path(args.out_dir) / f"{brief.name}.tmx"
    tmap.save(out)

    print(f"{out}  {brief.width}x{brief.height} kafli  ziarno {brief.seed}")
    for note in generator.notes:
        print(f"  uwaga: {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
