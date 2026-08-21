#!/usr/bin/env python3
"""Model plików .tsx i rozwiązywanie gid -> (tileset, kafel).

Obsługuje oba rodzaje tilesetów, których używa gra:

* **atlas** - jeden obrazek pocięty siatką (`Floor.tsx`, `Nature.tsx`, `items.tsx`),
* **kolekcja** - każdy kafel ma własny `<image>` (`CharacterTileset.tsx`, gdzie
  jeden "kafel" to wycinek arkusza animacji postaci, opisany atrybutami
  `x/y/width/height` samego kafla).

Rozróżnienie ma znaczenie dla renderu: w kolekcji `columns="0"` i liczenie
pozycji z siatki dałoby dzielenie przez zero.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from tmx import Props, TilesetRef, _parse_props, bare_gid


@dataclass
class WangSet:
    """Zestaw terenu z Tiled. `Floor.tsx` ma jeden: "grass-dirt Set" (typ corner)."""

    name: str = ""
    type: str = "corner"
    colors: list[str] = field(default_factory=list)      # indeks 1-based w wangid
    tiles: dict[int, tuple[int, ...]] = field(default_factory=dict)  # tileid -> 8 wartości

    def color_index(self, name: str) -> int:
        """Numer koloru (1-based) albo 0, gdy tego terenu tu nie ma."""
        for idx, color in enumerate(self.colors, start=1):
            if color == name:
                return idx
        return 0

    def tiles_for(self, wangid: tuple[int, ...]) -> list[int]:
        return [tid for tid, wid in self.tiles.items() if wid == wangid]


@dataclass
class TilesetTile:
    id: int = 0
    props: Props = field(default_factory=Props)
    type: str = ""
    image: str = ""                 # tylko w kolekcji
    image_width: int = 0
    image_height: int = 0
    # wycinek w obrazku kafla (kolekcja); dla atlasu liczony z siatki
    box: tuple[int, int, int, int] | None = None


@dataclass
class Tileset:
    path: Path
    name: str = ""
    tilewidth: int = 16
    tileheight: int = 16
    tilecount: int = 0
    columns: int = 0
    spacing: int = 0
    margin: int = 0
    image: str = ""
    image_width: int = 0
    image_height: int = 0
    tiles: dict[int, TilesetTile] = field(default_factory=dict)
    wangsets: list[WangSet] = field(default_factory=list)

    @property
    def is_collection(self) -> bool:
        return not self.image

    @property
    def image_path(self) -> Path:
        return (self.path.parent / self.image).resolve()

    def tile_props(self, local_id: int) -> Props:
        tile = self.tiles.get(local_id)
        return tile.props if tile else Props()

    def tile_box(self, local_id: int) -> tuple[int, int, int, int] | None:
        """Prostokąt (left, top, right, bottom) w obrazku źródłowym kafla."""
        if self.is_collection:
            tile = self.tiles.get(local_id)
            return tile.box if tile else None
        if self.columns <= 0 or not 0 <= local_id < self.tilecount:
            return None
        col = local_id % self.columns
        row = local_id // self.columns
        left = self.margin + col * (self.tilewidth + self.spacing)
        top = self.margin + row * (self.tileheight + self.spacing)
        return (left, top, left + self.tilewidth, top + self.tileheight)

    def tile_image_path(self, local_id: int) -> Path | None:
        """Obrazek, z którego wycinamy kafel - w kolekcji własny, w atlasie wspólny."""
        if not self.is_collection:
            return self.image_path
        tile = self.tiles.get(local_id)
        if tile is None or not tile.image:
            return None
        return (self.path.parent / tile.image).resolve()

    def wangset(self, name: str) -> WangSet | None:
        for wang in self.wangsets:
            if wang.name == name:
                return wang
        return None

    @classmethod
    def load(cls, path: str | Path) -> Tileset:
        path = Path(path).resolve()
        root = ET.parse(path).getroot()
        tileset = cls(
            path=path,
            name=root.get("name", path.stem),
            tilewidth=int(root.get("tilewidth", 16)),
            tileheight=int(root.get("tileheight", 16)),
            tilecount=int(root.get("tilecount", 0)),
            columns=int(root.get("columns", 0)),
            spacing=int(root.get("spacing", 0)),
            margin=int(root.get("margin", 0)),
        )
        image = root.find("image")
        if image is not None:
            tileset.image = image.get("source", "")
            tileset.image_width = int(image.get("width", 0))
            tileset.image_height = int(image.get("height", 0))

        for node in root.findall("tile"):
            local_id = int(node.get("id", 0))
            tile = TilesetTile(
                id=local_id,
                props=_parse_props(node),
                type=node.get("type", "") or node.get("class", ""),
            )
            tile_image = node.find("image")
            if tile_image is not None:
                tile.image = tile_image.get("source", "")
                tile.image_width = int(tile_image.get("width", 0))
                tile.image_height = int(tile_image.get("height", 0))
                left = int(float(node.get("x", 0)))
                top = int(float(node.get("y", 0)))
                width = int(float(node.get("width", 0) or tile.image_width))
                height = int(float(node.get("height", 0) or tile.image_height))
                tile.box = (left, top, left + width, top + height)
            tileset.tiles[local_id] = tile

        for wangsets in root.findall("wangsets"):
            for node in wangsets.findall("wangset"):
                wang = WangSet(name=node.get("name", ""), type=node.get("type", "corner"))
                wang.colors = [c.get("name", "") for c in node.findall("wangcolor")]
                for wtile in node.findall("wangtile"):
                    raw = wtile.get("wangid", "")
                    wang.tiles[int(wtile.get("tileid", 0))] = tuple(
                        int(part) for part in raw.split(",") if part != ""
                    )
                tileset.wangsets.append(wang)
        return tileset


@dataclass
class ResolvedTile:
    tileset: Tileset
    local_id: int


class TilesetTable:
    """Tablica tilesetów jednej mapy: zamienia gid na (tileset, numer kafla w nim)."""

    def __init__(self, refs: list[TilesetRef], map_path: Path) -> None:
        self.map_dir = map_path.parent
        self.entries: list[tuple[int, Tileset]] = []
        self._cache: dict[int, ResolvedTile | None] = {}
        for ref in refs:
            tsx = (self.map_dir / ref.source).resolve()
            self.entries.append((ref.firstgid, Tileset.load(tsx)))
        # malejąco, żeby pierwszy pasujący `firstgid` był tym właściwym
        self.entries.sort(key=lambda item: item[0], reverse=True)

    def resolve(self, gid: int) -> ResolvedTile | None:
        plain = bare_gid(gid)
        if not plain:
            return None
        if plain in self._cache:
            return self._cache[plain]
        found: ResolvedTile | None = None
        for firstgid, tileset in self.entries:
            if plain >= firstgid:
                local = plain - firstgid
                found = ResolvedTile(tileset, local) if local < tileset.tilecount else None
                break
        self._cache[plain] = found
        return found

    def props_for(self, gid: int) -> Props:
        hit = self.resolve(gid)
        return hit.tileset.tile_props(hit.local_id) if hit else Props()

    def tileset_of(self, gid: int) -> str:
        hit = self.resolve(gid)
        return hit.tileset.name if hit else ""

    def step_cost(self, gid: int, default: int) -> int:
        """`step_cost` kafla albo wartość domyślna - tak, jak czyta to `load_step_cost`."""
        props = self.props_for(gid)
        return props.as_int("step_cost", default) if "step_cost" in props else default

    def gid_of(self, tileset_name: str, local_id: int) -> int:
        for firstgid, tileset in self.entries:
            if tileset.name == tileset_name or tileset.path.stem == tileset_name:
                return firstgid + local_id
        raise KeyError(f"mapa nie ma tilesetu '{tileset_name}'")
