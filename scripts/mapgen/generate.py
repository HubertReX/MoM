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

from fence import FenceKit, draw_fence, kits_from_palette, rect_cells
from palette import Palette, Stamp
from terrain import TerrainLib, blob_mask
from tileset import Tileset
from tmx import (
    EMPTY,
    TileLayer,
    OUTDOOR_TILESETS,
    MapObject,
    ObjectGroup,
    TiledMap,
    TileLayer,
    maps_dir,
    new_outdoor_map,
)

WIP_DIR = maps_dir() / "_wip"
# nazwa tilesetu -> jego firstgid, z kanonicznej tablicy map zewnętrznych
OUTDOOR_TILESETS_BY_KEY = tuple((key, firstgid) for firstgid, key in OUTDOOR_TILESETS)


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
    fences: list[str] = field(default_factory=list)   # zestawy płotów do losowania
    exit_to: str = ""                  # mapa wnętrza, pod którą podpiąć drzwi
    yard: tuple[int, int] = (0, 0)     # margines zagrody wokół budynku, w kaflach


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
    buildings: list[dict[str, object]] = field(default_factory=list)
    fields: list[dict[str, object]] = field(default_factory=list)
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
                fences=[str(f) for f in item.get("fences", [])],
                exit_to=str(item.get("exit_to", "")),
                yard=tuple(item.get("yard", (0, 0))),          # type: ignore[arg-type]
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
        for key in ("building", "fields", "prop", "entry", "place", "spawn", "zone", "exit"):
            target = {"building": brief.buildings, "fields": brief.fields,
                      "prop": brief.props, "entry": brief.entries, "place": brief.places,
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
        self.fence_kits: dict[str, FenceKit] = kits_from_palette(palette)
        self._char_gids: dict[str, int] | None = None
        self._undergrowth: list[int] | None = None
        self.yards: list[tuple[int, int, int, int]] = []
        self._door_seq = 0
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
        self.pass_seal_stamps()
        self.pass_nature()
        self.pass_seal_gaps()
        self.pass_fields()
        self.pass_landmarks()
        self.pass_districts()
        self.pass_props()
        self.pass_open_doors()
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

    def pass_seal_stamps(self) -> None:
        """Domknij skraj mapy - CAŁYMI klockami, nigdy ich fragmentami.

        Pierwsza wersja dosypywała w luki pojedyncze kafle wzięte z warstwy
        `walls` klocków natury. Kafel drzewa wyrwany z kontekstu to kawałek pnia
        albo pół korony, więc pas trzech kafli przy krawędzi zamieniał się
        w sieczkę - i było to widać tylko tam, bo tylko tam dosypywaliśmy.

        Teraz idą dwa etapy: najpierw wciskamy w pas całe klocki natury (od
        największych, żeby zamknąć jak najwięcej), a dopiero luki 1x1, których
        żaden klocek nie zapełni, dostają kompletny kafel podszytu z Nature.tsx
        (krzak, kępa trawy, kamień) - te są samodzielnymi obrazkami, więc
        wyglądają jak zarośla, a nie jak błąd.
        """
        margin = self._seal_margin()
        if margin <= 0:
            return
        stamps = sorted(self.palette.of_kind("nature"), key=lambda st: -(st.w * st.h))
        if not stamps:
            return
        stamped = 0
        for y in range(self.tmap.height):
            for x in range(self.tmap.width):
                if not self._in_band(x, y, margin) or self.road_mask[y][x]:
                    continue
                for stamp in stamps:
                    # klocek wolno wpuścić w głąb mapy, byle zaczynał się w pasie
                    if self._place(stamp, x, y, avoid_roads=True):
                        stamped += 1
                        break
        self.notes.append(f"brzeg: {stamped} całych klocków natury (pas {margin} kafli)")

    def pass_seal_gaps(self) -> None:
        """Domknij to, czego całe klocki nie zapełniły - kompletnymi kaflami podszytu."""
        margin = self._seal_margin()
        if margin <= 0:
            return
        undergrowth = self._undergrowth_gids()
        if not undergrowth:
            self.notes.append("brzeg: brak kafli podszytu, skraj mapy może być dziurawy")
            return
        walls = self.tmap.tile_layer("walls")
        sealed = 0
        for y in range(self.tmap.height):
            for x in range(self.tmap.width):
                if not self._in_band(x, y, margin) or walls.get(x, y):
                    continue
                if self.road_mask[y][x]:
                    continue          # trakt wychodzący poza mapę to zamierzone wyjście
                walls.set(x, y, self.rng.choice(undergrowth))
                self.taken[y][x] = True
                sealed += 1
        if sealed:
            self.notes.append(f"brzeg: {sealed} luk zasypanych podszytem")

    def _seal_margin(self) -> int:
        return max((b.margin for b in self.brief.biomes), default=0)

    def _in_band(self, x: int, y: int, margin: int) -> bool:
        return min(x, y, self.tmap.width - 1 - x, self.tmap.height - 1 - y) < margin

    # Awaryjny podszyt, gdy katalog nie ma klocków `kind=undergrowth`: ciągły blok
    # zwykłych krzaków i kęp traw z Nature.tsx. Celowo NIE bierzemy wszystkiego, co
    # zniszczalne - dalej w tym tilesecie siedzą słoneczniki, stokrotki i maki, a
    # kwiatki rozsypane po skraju lasu wyglądają jak pomyłka, nie jak zarośla.
    UNDERGROWTH_FALLBACK = range(240, 251)

    def _undergrowth_gids(self) -> list[int]:
        """Kompletne kafle 1x1 do zasypywania luk w ścianie lasu.

        Pierwszeństwo mają klocki `kind=undergrowth` z katalogu - to autor
        decyduje, jak wygląda podszyt. Dopiero gdy ich nie ma, sięgamy po
        awaryjny zestaw i mówimy o tym, bo to sytuacja do naprawienia w Tiled,
        a nie stan docelowy.
        """
        if self._undergrowth is not None:
            return self._undergrowth
        from_palette = [
            stamp.gids("walls")[0][0]
            for stamp in self.palette.of_kind("undergrowth")
            if stamp.w == 1 and stamp.h == 1 and stamp.gids("walls")[0][0]
        ]
        if from_palette:
            self._undergrowth = sorted(set(from_palette))
            return self._undergrowth
        tileset = Tileset.load(maps_dir() / "tilesets" / "Nature.tsx")
        firstgid = dict(OUTDOOR_TILESETS_BY_KEY)["Nature"]
        self._undergrowth = [firstgid + local_id
                             for local_id in self.UNDERGROWTH_FALLBACK
                             if local_id in tileset.tiles]
        self.notes.append(
            "katalog nie ma klocków `kind=undergrowth` (1x1) - luki w ścianie lasu "
            "zasypuję awaryjnym zestawem krzaków. Dodaj własne w warstwie `stamps`.")
        return self._undergrowth

    def pass_fields(self) -> None:
        """Symetryczne zagony przecinane drogami - kratka JEST tu zamierzona.

        Pole uprawne to jedyne miejsce na mapie, gdzie regularność czyta się jako
        praca ludzi, a nie jako lenistwo generatora, więc metryka szablonowości
        celowo nie obejmuje wnętrza pól (bryły na `walls` tam nie powstają).
        """
        for spec in self.brief.fields:
            rect = spec["rect"]
            stamp = self.palette.get(str(spec.get("stamp", "field_crop")))
            gap = int(spec.get("gap", 2))                      # type: ignore[arg-type]
            # Zagon składa się z `plot` klocków w poziomie i pionie. Bez tego
            # "duże połacie pól" wychodzą jako krata miedz z drobnymi łatkami:
            # przy klocku 6x8 i miedzy 4 kafle prawie połowa obszaru to ścieżka.
            tiles_x, tiles_y = (int(v) for v in spec.get("plot", (1, 1)))  # type: ignore[misc]
            rx, ry, rw, rh = (int(v) for v in rect)            # type: ignore[misc]
            plot_w, plot_h = stamp.w * tiles_x, stamp.h * tiles_y
            step_x, step_y = plot_w + gap, plot_h + gap
            plots = 0
            for oy in range(ry, ry + rh - plot_h + 1, step_y):
                for ox in range(rx, rx + rw - plot_w + 1, step_x):
                    if any(self.road_mask[y][x]
                           for y in range(oy, oy + plot_h) for x in range(ox, ox + plot_w)
                           if 0 <= y < self.tmap.height and 0 <= x < self.tmap.width):
                        continue
                    laid = 0
                    for ty in range(tiles_y):
                        for tx in range(tiles_x):
                            if self._place(stamp, ox + tx * stamp.w, oy + ty * stamp.h,
                                           avoid_roads=True):
                                laid += 1
                    plots += bool(laid)
            # miedze między zagonami idą na maskę traktu, więc dostaną autotiling
            for oy in range(ry, ry + rh):
                for ox in range(rx, rx + rw):
                    if not (0 <= ox < self.tmap.width and 0 <= oy < self.tmap.height):
                        continue
                    in_plot_x = (ox - rx) % step_x < plot_w
                    in_plot_y = (oy - ry) % step_y < plot_h
                    if not (in_plot_x and in_plot_y) and not self.taken[oy][ox]:
                        self.road_mask[oy][ox] = True
            # Pole domyślnie dostaje strefę - to po niej rutyna farmera wie, gdzie
            # go zagonić. Krzywa `waypoints` powstaje tylko na wyraźne życzenie
            # w briefie, bo trasa to decyzja o konkretnej postaci, a nie o terenie.
            zone = str(spec.get("zone", "field"))
            if zone:
                self.tmap.add_object("zones", MapObject(
                    name=zone,
                    x=float(rx) * self.tmap.tilewidth, y=float(ry) * self.tmap.tileheight,
                    width=float(rw) * self.tmap.tilewidth,
                    height=float(rh) * self.tmap.tileheight))
            self.notes.append(f"pola: {plots} zagonów w prostokącie {rx},{ry} {rw}x{rh}"
                              f"{f', strefa `{zone}`' if zone else ''}")

    def pass_landmarks(self) -> None:
        """Budynki stawiane WPROST - tam, gdzie prompt mówi "tu i tu"."""
        for spec in self.brief.buildings:
            stamp = self.palette.get(str(spec["stamp"]))
            at = spec["at"]
            x, y = int(at[0]), int(at[1])                      # type: ignore[index]
            if not self._place(stamp, x, y, avoid_roads=False):
                self.notes.append(f"budynek '{stamp.name}' w ({x},{y}): miejsce zajęte")
                continue
            owner = str(spec.get("owner", ""))
            yard = spec.get("yard")
            if yard:
                district = District(
                    fences=[str(f) for f in spec.get("fences", [])],   # type: ignore[union-attr]
                    yard=(int(yard[0]), int(yard[1])),                 # type: ignore[index]
                )
                toward = spec.get("gate_toward", (x + stamp.w // 2, y + stamp.h + 3))
                self._fence_yard(district, stamp, (x, y),
                                 (float(toward[0]), float(toward[1])),  # type: ignore[index]
                                 label=owner)
            self._connect_to_road(stamp, (x, y))
            self._wire_door(stamp, (x, y), str(spec.get("exit_to", "")), owner)

    def _wire_door(self, stamp: Stamp, at: tuple[int, int], to_map: str,
                   owner: str) -> None:
        """Podepnij drzwi budynku pod mapę wnętrza: wyjście + punkt powrotu.

        Dom z obiektem na `places`, ale bez `exit`-u, wygląda w grze jak dom bez
        drzwi: rutyna prowadzi tam NPC-a, gracz podchodzi i nic. Dlatego brak
        `exit_to` jest zgłaszany, a nie przemilczany - a na czas testów wolno
        podpiąć wszystko pod jedną istniejącą mapę wnętrza.
        """
        if stamp.door is None:
            return
        label = owner or stamp.name.upper()
        if not to_map:
            self.notes.append(f"budynek '{label}': drzwi bez `exit_to` - nikt tam "
                              f"nie wejdzie. Podaj mapę wnętrza w briefie")
            return
        tile = self.tmap.tilewidth
        dx, dy = stamp.door
        door_x, door_y = at[0] + dx, at[1] + dy

        exit_obj = MapObject(name=f"{label}_DOOR",
                             x=float(door_x) * tile, y=float(door_y) * tile,
                             width=float(tile), height=float(tile))
        exit_obj.props.set("obj_type", "exit")
        exit_obj.props.set("to_map", to_map)
        exit_obj.props.set("destination_entry_point", "Door")
        self.tmap.add_object("interactions", exit_obj)

        # Wnętrze wraca do punktu o nazwie, którą zna JEGO wyjście. Dopóki
        # wszystkie domy dzielą jedną mapę wnętrza, taki punkt może być tylko
        # jeden - reszta dostaje własną nazwę i czeka na swoje wnętrze.
        entries = self.tmap.object_group("entry_points")
        canonical = f"{to_map}_DOOR"
        name = canonical if not entries.first(canonical) else f"{label}_FRONT"
        self.tmap.add_object("entry_points", MapObject(
            name=name, shape="point",
            x=(float(door_x) + 0.5) * tile, y=(float(door_y) + 1.5) * tile))

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
        if had_roads or self.brief.fields:
            terrain = self.brief.roads[0].terrain if self.brief.roads else "dirt"
            self._paint_mask(self.road_mask, terrain)

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
                    # Zagroda PRZED odnogą: płot jest ścianą, więc A* i tak
                    # przeciśnie ścieżkę przez bramę - a brama celuje w drogę.
                    self._fence_yard(district, stamp, spot, path[cursor])
                    self._connect_to_road(stamp, spot)
                    self._wire_door(stamp, spot, district.exit_to,
                                    f"{district.name or 'HOUSE'}_{self._yard_seq():02}")
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

    def _fence_yard(self, district: District, stamp: Stamp, at: tuple[int, int],
                    toward: tuple[float, float], label: str = "") -> None:
        """Ogrodź budynek zagrodą o marginesie z briefu, z bramą od strony drogi."""
        pad_lo, pad_hi = district.yard
        if pad_hi <= 0:
            return
        kits = [self.fence_kits[name] for name in district.fences
                if name in self.fence_kits] or list(self.fence_kits.values())
        if not kits:
            return
        pad = self.rng.randint(int(pad_lo), int(pad_hi))
        # zagroda jest asymetryczna: podwórze przed drzwiami większe niż za domem
        x0, y0 = at[0] - pad, at[1] - max(1, pad - 1)
        w = stamp.w + pad * 2
        h = stamp.h + max(1, pad - 1) + pad + 1
        # Dwie zagrody NIGDY nie mogą na siebie wejść: nakładające się obwody
        # dają poszarpane płoty z uskokami, bo drugi rysuje się po pierwszym
        # i maska sąsiedztwa liczy się już na pomieszanych kaflach. Taniej
        # odpuścić zagrodę niż potem prostować takie przypadki brzegowe.
        if any(x0 < yx + yw and x0 + w > yx and y0 < yy + yh and y0 + h > yy
               for yx, yy, yw, yh in self.yards):
            return
        if x0 < 1 or y0 < 1 or x0 + w >= self.tmap.width or y0 + h >= self.tmap.height:
            return
        # Zagroda PRZYCINA się do traktu zamiast być odrzucana: przy cofnięciu
        # o 2-5 kafli prawie każda dotyka drogi, więc odrzucanie znaczyłoby "nigdy".
        # Po odjęciu kafli drogi zostaje kształt wklęsły - i dokładnie po to płot
        # składa się z segmentów po masce sąsiedztwa, a nie z gotowej ramki.
        cells = {
            (x, y) for x, y in rect_cells(x0, y0, w, h)
            if 0 <= x < self.tmap.width and 0 <= y < self.tmap.height
            and not self.road_mask[y][x]
        }
        if len(cells) < stamp.w * stamp.h + 6:
            return                       # z zagrody zostały strzępy

        walls = self.tmap.tile_layer("walls")
        occupied = {(x, y) for x, y in cells if walls.get(x, y)}
        # Próg drzwi NIGDY nie dostaje płotu. Przycięcie zagrody traktem potrafi
        # przesunąć obwód pod sam próg i wtedy dom staje się własną klatką - a
        # przebijanie bramy po fakcie to leczenie objawu.
        approach = stamp.approach_tile()
        if approach is not None:
            ax, ay = at[0] + approach[0], at[1] + approach[1]
            occupied |= {(ax, ay), (ax, ay + 1), (ax - 1, ay), (ax + 1, ay)}
        placed = draw_fence(walls, cells, self.rng.choice(kits), gates=1, rng=self.rng,
                            skip=occupied,
                            gate_toward=(int(toward[0]), int(toward[1])), gate_width=2)
        for x, y in cells:
            if 0 <= y < self.tmap.height and 0 <= x < self.tmap.width:
                self.taken[y][x] = True
        if not placed:
            self.notes.append(f"zagroda przy '{stamp.name}' w {at}: płot nie wszedł")
            return
        self.yards.append((x0, y0, w, h))
        self._open_yard(walls, cells, placed, stamp.name)
        # Każde podwórze dostaje WŁASNĄ strefę z sufiksem właściciela. Jedna
        # wspólna `backyard` sklejałaby podwórka kilku domów w jeden obszar,
        # po którym pies Bartusia biegałby do sąsiada.
        owner = label or f"{self._yard_seq():02}"
        self.tmap.add_object("zones", MapObject(
            name=f"backyard_{owner}",
            x=float(x0 + 1) * self.tmap.tilewidth,
            y=float(y0 + 1) * self.tmap.tileheight,
            width=float(w - 2) * self.tmap.tilewidth,
            height=float(h - 2) * self.tmap.tileheight))

    def _open_yard(self, walls: "TileLayer", cells: set[tuple[int, int]],
                   fence: set[tuple[int, int]], label: str) -> None:
        """Dopilnuj, żeby KAŻDY zakątek zagrody dało się obejść od zewnątrz.

        Sam płot z bramą nie wystarcza: budynek postawiony w poprzek podwórza
        dzieli je na dwie kieszenie, a brama otwiera tylko jedną. Druga zostaje
        klatką - linter zgłosi ją jako obszar nieosiągalny, ale dopiero po
        fakcie. Taniej sprawdzić to tutaj i wyciąć brakujące przejście.
        """
        interior = {(x, y) for x, y in cells if not walls.get(x, y)}
        if not interior:
            return
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        box = (min(xs) - 2, min(ys) - 2, max(xs) + 2, max(ys) + 2)

        for _attempt in range(4):
            outside = self._reach_in_box(walls, box, cells)
            stranded = interior - outside
            if not stranded:
                return
            # kafel płotu stykający się z uwięzioną częścią I z osiągalnym terenem
            opening = next(
                ((fx, fy) for fx, fy in sorted(fence)
                 if any((fx + dx, fy + dy) in stranded
                        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                 and any((fx + dx, fy + dy) in outside
                         for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))),
                None,
            )
            if opening is None:
                self.notes.append(f"zagroda przy '{label}': {len(stranded)} kafli bez "
                                  f"dojścia i nie ma gdzie przebić bramy")
                return
            walls.set(opening[0], opening[1], EMPTY)
            fence.discard(opening)
            self.notes.append(f"zagroda przy '{label}': dodatkowa brama w {opening}")

    def _reach_in_box(self, walls: "TileLayer", box: tuple[int, int, int, int],
                      cells: set[tuple[int, int]]) -> set[tuple[int, int]]:
        """Kafle w pudełku osiągalne od jego brzegu (czyli od zewnątrz zagrody)."""
        x0, y0, x1, y1 = box
        seen: set[tuple[int, int]] = set()
        queue: list[tuple[int, int]] = [
            (x, y)
            for x in range(x0, x1 + 1) for y in (y0, y1)
            if self.tmap.in_bounds(x, y) and not walls.get(x, y) and (x, y) not in cells
        ] + [
            (x, y)
            for y in range(y0, y1 + 1) for x in (x0, x1)
            if self.tmap.in_bounds(x, y) and not walls.get(x, y) and (x, y) not in cells
        ]
        seen.update(queue)
        while queue:
            x, y = queue.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (x0 <= nx <= x1 and y0 <= ny <= y1):
                    continue
                if (nx, ny) in seen or not self.tmap.in_bounds(nx, ny):
                    continue
                if walls.get(nx, ny):
                    continue
                seen.add((nx, ny))
                queue.append((nx, ny))
        return seen

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
            # Płot zagrody potrafi zamknąć drzwi w pułapce. Zamiast zostawić dom
            # bez dojścia (czego linter nie złapie, bo dom bez `exit` nikogo nie
            # obchodzi), przebijamy w płocie dziurę od strony traktu i próbujemy
            # jeszcze raz - zagroda ma mieć bramę, a nie być klatką.
            if self._punch_gate(walls, walk, (sx, sy)):
                path = astar(walk, cost, (sx, sy), goals)
        if not path:
            self.notes.append(f"klocek '{stamp.name}' w {at}: A* nie znalazł drogi "
                              f"od drzwi do traktu - sprawdź ten budynek")
            return
        for x, y in path:
            self.road_mask[y][x] = True

    def _punch_gate(self, walls: "TileLayer", walk: list[list[bool]],
                    door: tuple[int, int]) -> bool:
        """Usuń kafel płotu leżący między drzwiami a najbliższym traktem."""
        roads = self._road_tiles()
        if not roads:
            return False
        dx, dy = door
        target = min(roads, key=lambda r: (r[0] - dx) ** 2 + (r[1] - dy) ** 2)
        # kandydaci: kafle ściany w promieniu 6 od drzwi, posortowane po tym,
        # jak bardzo skracają dystans do traktu
        best: tuple[float, tuple[int, int]] | None = None
        for y in range(max(0, dy - 6), min(self.tmap.height, dy + 7)):
            for x in range(max(0, dx - 6), min(self.tmap.width, dx + 7)):
                if not walls.get(x, y):
                    continue
                score = ((x - target[0]) ** 2 + (y - target[1]) ** 2) ** 0.5
                if best is None or score < best[0]:
                    best = (score, (x, y))
        if best is None:
            return False
        gx, gy = best[1]
        walls.set(gx, gy, EMPTY)
        walk[gy][gx] = True
        self.notes.append(f"przebita brama w płocie przy {gx},{gy}")
        return True

    def _yard_seq(self) -> int:
        self._door_seq += 1
        return self._door_seq

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

    def pass_open_doors(self) -> None:
        """Przebieg końcowy: każde drzwi na mapie muszą mieć dojście.

        Zagrody powstają po kolei, więc płot postawiony PÓŹNIEJ potrafi zamurować
        próg budynku postawionego wcześniej - a wtedy ani `_open_yard`, ani
        przebicie przy odnodze nic nie wiedzą, bo w swoim momencie wszystko było
        w porządku. Dlatego sprawdzenie idzie na koniec, na gotowej mapie, i
        wycina najtańsze przejście od progu do terenu osiągalnego z traktu.
        """
        door_gids = {
            stamp.gids("walls")[stamp.door[1]][stamp.door[0]]
            for stamp in self.palette.of_kind("building") if stamp.door
        } - {0}
        if not door_gids:
            return
        walls = self.tmap.tile_layer("walls")
        opened = 0
        for _round in range(6):
            reachable = self._reachable_from_entries(walls)
            stuck = [
                (x, y + 1)
                for y in range(self.tmap.height - 1) for x in range(self.tmap.width)
                if walls.get(x, y) in door_gids and (x, y + 1) not in reachable
            ]
            if not stuck:
                break
            for tx, ty in stuck:
                opened += self._carve_to(walls, (tx, ty), reachable)
        if opened:
            self.notes.append(f"przebieg końcowy: {opened} kafli wyciętych, żeby "
                              f"progi budynków miały dojście")

    def _reachable_from_entries(self, walls: "TileLayer") -> set[tuple[int, int]]:
        """Teren osiągalny z PUNKTÓW WEJŚCIA - dokładnie tak, jak liczy to gra.

        Kuszące jest zalanie mapy od wszystkich kafli traktu, ale to daje fałszywy
        wynik: klocek postawiony na drodze (zagroda, która przyszła z własnym
        płotem) zamyka w sobie kawałek traktu, a wtedy "od traktu" wychodzi, że
        jego wnętrze jest osiągalne - mimo że z zewnątrz nie ma tam wejścia.
        """
        seeds = [(int(spec["at"][0]), int(spec["at"][1]))     # type: ignore[index]
                 for spec in self.brief.entries]
        if not seeds:
            # brak wejść w briefie: bierzemy trakt dotykający krawędzi mapy
            seeds = [(x, y) for y in range(self.tmap.height) for x in range(self.tmap.width)
                     if self.road_mask[y][x]
                     and (x in (0, self.tmap.width - 1) or y in (0, self.tmap.height - 1))]
        seen: set[tuple[int, int]] = set()
        queue = [(x, y) for x, y in seeds
                 if self.tmap.in_bounds(x, y) and not walls.get(x, y)]
        seen.update(queue)
        while queue:
            x, y = queue.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if (self.tmap.in_bounds(nx, ny) and (nx, ny) not in seen
                        and not walls.get(nx, ny)):
                    seen.add((nx, ny))
                    queue.append((nx, ny))
        return seen

    def _carve_to(self, walls: "TileLayer", start: tuple[int, int],
                  goals: set[tuple[int, int]]) -> int:
        """Wytnij najtańsze przejście od progu do osiągalnego terenu.

        Kafel pusty kosztuje 1, ściana 60 - więc trasa woli obejść budynek dookoła
        niż przebić się przez niego, a płot przecina tylko wtedy, gdy naprawdę
        nie ma innej drogi.
        """
        if not goals:
            return 0
        cost = [[1 if not walls.get(x, y) else 60 for x in range(self.tmap.width)]
                for y in range(self.tmap.height)]
        walk = [[True] * self.tmap.width for _ in range(self.tmap.height)]
        path = astar(walk, cost, start, goals)
        cleared = 0
        for x, y in path:
            if walls.get(x, y):
                walls.set(x, y, EMPTY)
                cleared += 1
        return cleared

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
        for spec in self.brief.spawns:
            at = spec["at"]
            model = str(spec["model"])
            gid = self._character_gid(model)
            if not gid:
                self.notes.append(f"spawn '{model}': brak takiego kafla w "
                                  f"CharacterTileset.tsx - pomijam")
                continue
            # Brief podaje miejsce z grubsza, a kod widzi teren - więc dosuwamy
            # spawn do wolnego kafla i MÓWIMY o tym. Gra nie ma dla NPC-ów siatki
            # bezpieczeństwa (`walkable_pos_near` używa tylko gracz), więc postać
            # postawiona w ścianie zostaje w niej na zawsze.
            spot = self._free_tile_near(int(at[0]), int(at[1]))
            if spot is None:
                self.notes.append(f"spawn '{model}': brak wolnego kafla w okolicy "
                                  f"({at[0]},{at[1]}) - pomijam")
                continue
            if spot != (int(at[0]), int(at[1])):
                self.notes.append(f"spawn '{model}': {at[0]},{at[1]} zajęte, "
                                  f"dosunięty na {spot[0]},{spot[1]}")
            # obiekt z gidem kotwiczy się DOLNĄ krawędzią (patrz tmx.MapObject.top)
            self.tmap.add_object("spawn_points", MapObject(
                name=str(spec.get("name", model)), gid=gid,
                x=float(spot[0]) * tile, y=float(spot[1]) * tile,
                width=float(tile), height=float(tile)))

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

    def _free_tile_near(self, x: int, y: int, reach: int = 6) -> tuple[int, int] | None:
        """Najbliższy kafel bez ściany, szukany pierścieniami."""
        walls = self.tmap.tile_layer("walls")
        for radius in range(reach + 1):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if radius and max(abs(dx), abs(dy)) != radius:
                        continue
                    nx, ny = x + dx, y + dy
                    if self.tmap.in_bounds(nx, ny) and not walls.get(nx, ny):
                        return (nx, ny)
        return None

    def _character_gid(self, model: str) -> int:
        """gid kafla postaci z CharacterTileset.tsx - to on niesie `model_name`,
        po którym `load_NPCs` rozpoznaje, kogo postawić."""
        if self._char_gids is None:
            self._char_gids = {}
            tileset = Tileset.load(maps_dir() / "tilesets" / "CharacterTileset.tsx")
            firstgid = dict(OUTDOOR_TILESETS_BY_KEY)["CharacterTileset"]
            for local_id, tile in tileset.tiles.items():
                name = tile.props.get("model_name", "") or tile.type
                if name:
                    self._char_gids[name] = firstgid + local_id
        return self._char_gids.get(model, 0)

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
