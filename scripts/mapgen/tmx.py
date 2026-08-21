#!/usr/bin/env python3
"""Model plików .tmx/.tsx dla generatora map (skill `tiled-map`).

Czysty stdlib: żadnego pygame, SDL ani pytmx - dokładnie z tego powodu, co
`scripts/validate_world.py`, czyli żeby narzędzia mapowe chodziły w CI, przez
ssh i w recepturach `just` bez ekranu i bez sterownika audio.

Model zachowuje KOLEJNOŚĆ warstw, bo kolejność jest kontraktem gry, a nie
kosmetyką: `map_loader.load_step_cost` czyta warstwy po INDEKSIE 0 i 1 (a nie
po nazwie), a `scene.sprites_layer` to `layers.index("sprites")`. Przestawienie
warstw zmienia więc koszty chodzenia i to, pod czym rysują się postacie.

Zapis celowo nie idzie przez `ElementTree.tostring`: Tiled ma własny format
(wcięcie jednospacjowe na poziom, dane CSV wierszami, `</data>` w kolumnie 0)
i pliki mają się dawać czytać w diffie obok tych zapisanych przez edytor.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# MARK: gid i flagi obrotu

# Trzy najstarsze bity gidu to flagi odbicia/obrotu, a nie numer kafla.
GID_FLIP_H = 0x80000000
GID_FLIP_V = 0x40000000
GID_FLIP_D = 0x20000000
GID_FLAGS = GID_FLIP_H | GID_FLIP_V | GID_FLIP_D
GID_MASK = 0x1FFFFFFF

EMPTY = 0


def bare_gid(gid: int) -> int:
    """Numer kafla bez flag obrotu."""
    return gid & GID_MASK


def gid_flags(gid: int) -> int:
    """Same flagi obrotu, do przeniesienia na inny kafel."""
    return gid & GID_FLAGS


# --------------------------------------------------------------------------
# MARK: kontrakt mapy zewnętrznej

# Kolejność jest wiążąca - patrz docstring modułu.
TILE_LAYERS: tuple[str, ...] = ("ground", "foliage", "items", "walls", "sprites", "over")
OBJECT_LAYERS: tuple[str, ...] = (
    "interactions", "entry_points", "waypoints", "places", "spawn_points", "zones",
)
LAYER_ORDER: tuple[str, ...] = TILE_LAYERS + OBJECT_LAYERS

# Dwie najniższe warstwy niosą `step_cost` (czytane przez `load_step_cost`).
STEP_COST_LAYERS: tuple[str, ...] = ("ground", "foliage")

# Warstwa `over` jest u autora półprzezroczysta, żeby w Tiled było widać, co pod nią.
OVER_LAYER_OPACITY = 0.99

# Kanoniczna tablica tilesetów map ZEWNĘTRZNYCH. `BLUNDERHAVEN.tmx` i prototyp
# `_wip/BLUNDERHAVEN_base.tmx` mają ją identyczną, więc gid skopiowany z jednej
# mapy na drugą znaczy dokładnie to samo i nie wymaga przeliczania. Generator
# zawsze wypisuje ten blok w tej kolejności, a linter pilnuje, żeby nikt go nie
# przestawił - inaczej cała biblioteka klocków wskazywałaby na inne kafle.
# Nazwa "@items" to jedyny tileset spoza katalogu `maps/tilesets/`.
OUTDOOR_TILESETS: tuple[tuple[int, str], ...] = (
    (1, "Water"),
    (477, "Floor"),
    (1049, "Field"),
    (1124, "Nature"),
    (1628, "House"),
    (2387, "Element"),
    (2627, "FloorDetail"),
    (2707, "@items"),
    (2817, "CharacterTileset"),
)

TILE_SIZE = 16
TMX_VERSION = "1.10"
TILED_VERSION = "1.12.2"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def assets_dir() -> Path:
    return _repo_root() / "project" / "assets" / "NinjaAdventure"


def maps_dir() -> Path:
    return assets_dir() / "maps"


def tileset_source(name: str, map_path: Path) -> str:
    """Ścieżka do .tsx względem pliku mapy (mapa może leżeć w `maps/` albo `maps/_wip/`)."""
    target = assets_dir() / "items" / "items.tsx" if name == "@items" \
        else maps_dir() / "tilesets" / f"{name}.tsx"
    return os.path.relpath(target, map_path.parent).replace(os.sep, "/")


# --------------------------------------------------------------------------
# MARK: własności obiektów i kafli


@dataclass
class Props:
    """Własności Tiled: nazwa -> (typ, wartość). Typ pusty = string (Tiled go nie zapisuje)."""

    items: dict[str, tuple[str, str]] = field(default_factory=dict)

    def __contains__(self, name: str) -> bool:
        return name in self.items

    def __len__(self) -> int:
        return len(self.items)

    def get(self, name: str, default: str = "") -> str:
        entry = self.items.get(name)
        return entry[1] if entry else default

    def set(self, name: str, value: str, type_: str = "") -> None:
        self.items[name] = (type_, value)

    def set_bool(self, name: str, value: bool) -> None:
        self.items[name] = ("bool", "true" if value else "false")

    def set_int(self, name: str, value: int) -> None:
        self.items[name] = ("int", str(value))

    def as_bool(self, name: str, default: bool = False) -> bool:
        raw = self.get(name, "").strip().lower()
        if not raw:
            return default
        return raw in ("true", "1", "yes")

    def as_int(self, name: str, default: int = 0) -> int:
        try:
            return int(float(self.get(name, "")))
        except ValueError:
            return default

    def copy(self) -> Props:
        return Props(dict(self.items))


def _parse_props(node: ET.Element | None) -> Props:
    props = Props()
    if node is None:
        return props
    block = node.find("properties")
    if block is None:
        return props
    for prop in block.findall("property"):
        name = prop.get("name", "")
        # Tiled trzyma wartość wieloliniową w treści elementu, nie w atrybucie.
        value = prop.get("value")
        if value is None:
            value = prop.text or ""
        props.items[name] = (prop.get("type", ""), value)
    return props


# --------------------------------------------------------------------------
# MARK: obiekty i warstwy


@dataclass
class MapObject:
    """Obiekt z warstwy obiektowej. `shape` odwzorowuje dziecko elementu <object>."""

    id: int = 0
    name: str = ""
    type: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    gid: int = 0
    rotation: float = 0.0
    visible: bool = True
    shape: str = "rect"          # rect | point | ellipse | polygon | polyline
    points: list[tuple[float, float]] = field(default_factory=list)
    props: Props = field(default_factory=Props)

    # Kotwiczenie obiektów - pułapka, na którą łatwo wejść dwa razy:
    # w PLIKU .tmx obiekt Z GIDEM ma `y` na DOLNEJ krawędzi, a bez gidu na górnej.
    # pytmx normalizuje to przy wczytaniu (odejmuje wysokość), więc gra liczy
    # `Rect(x, y, w, h).midbottom` i wraca dokładnie do wartości z pliku.
    # Model trzyma liczby TAK JAK W PLIKU, więc przelicza sam.

    @property
    def top(self) -> float:
        """Górna krawędź - to, co pytmx pokazuje grze jako `obj.y`."""
        return self.y - self.height if self.gid else self.y

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.top + self.height / 2)

    @property
    def midbottom(self) -> tuple[float, float]:
        """Punkt, którym gra czyta `places`, `entry_points` i spawny (`rect.midbottom`)."""
        return (self.x + self.width / 2, self.top + self.height)

    @property
    def anchor(self) -> tuple[float, float]:
        """Lewy górny róg - po nim decydujemy, czy obiekt należy do przesuwanego prostokąta."""
        return (self.x, self.top)

    def translate(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def world_points(self) -> list[tuple[float, float]]:
        """Wierzchołki wielokąta/polilinii w układzie mapy (w pliku są względem x/y)."""
        return [(self.x + px, self.y + py) for px, py in self.points]


@dataclass
class TileLayer:
    id: int = 0
    name: str = ""
    width: int = 0
    height: int = 0
    data: list[list[int]] = field(default_factory=list)
    opacity: float | None = None
    visible: bool = True
    props: Props = field(default_factory=Props)

    def get(self, x: int, y: int) -> int:
        if 0 <= y < self.height and 0 <= x < self.width:
            return self.data[y][x]
        return EMPTY

    def set(self, x: int, y: int, gid: int) -> None:
        if 0 <= y < self.height and 0 <= x < self.width:
            self.data[y][x] = gid

    def fill(self, gid: int) -> None:
        for row in self.data:
            for x in range(self.width):
                row[x] = gid

    def is_empty(self) -> bool:
        return all(gid == EMPTY for row in self.data for gid in row)

    def used_gids(self) -> set[int]:
        return {bare_gid(gid) for row in self.data for gid in row if gid}

    def count_non_empty(self) -> int:
        return sum(1 for row in self.data for gid in row if gid)


@dataclass
class ObjectGroup:
    id: int = 0
    name: str = ""
    visible: bool = True
    opacity: float | None = None
    objects: list[MapObject] = field(default_factory=list)
    props: Props = field(default_factory=Props)

    def by_name(self, name: str) -> list[MapObject]:
        return [obj for obj in self.objects if obj.name == name]

    def first(self, name: str) -> MapObject | None:
        found = self.by_name(name)
        return found[0] if found else None

    def names(self) -> list[str]:
        return [obj.name for obj in self.objects]


Layer = TileLayer | ObjectGroup


@dataclass
class TilesetRef:
    firstgid: int
    source: str

    @property
    def key(self) -> str:
        """Logiczna nazwa tilesetu (`Floor`, `@items`) niezależna od głębokości ścieżki."""
        stem = Path(self.source).stem
        return "@items" if stem == "items" else stem


# --------------------------------------------------------------------------
# MARK: mapa


@dataclass
class TiledMap:
    path: Path | None = None
    width: int = 0
    height: int = 0
    tilewidth: int = TILE_SIZE
    tileheight: int = TILE_SIZE
    version: str = TMX_VERSION
    tiledversion: str = TILED_VERSION
    orientation: str = "orthogonal"
    renderorder: str = "right-down"
    infinite: int = 0
    nextlayerid: int = 1
    nextobjectid: int = 1
    props: Props = field(default_factory=Props)
    tilesets: list[TilesetRef] = field(default_factory=list)
    layers: list[Layer] = field(default_factory=list)

    # ---------------- dostęp do warstw ----------------

    def layer_names(self) -> list[str]:
        return [layer.name for layer in self.layers]

    def tile_layer(self, name: str) -> TileLayer:
        for layer in self.layers:
            if isinstance(layer, TileLayer) and layer.name == name:
                return layer
        raise KeyError(f"mapa nie ma warstwy kafelkowej '{name}'")

    def has_layer(self, name: str) -> bool:
        return name in self.layer_names()

    def object_group(self, name: str) -> ObjectGroup:
        for layer in self.layers:
            if isinstance(layer, ObjectGroup) and layer.name == name:
                return layer
        raise KeyError(f"mapa nie ma warstwy obiektowej '{name}'")

    def tile_layers(self) -> list[TileLayer]:
        return [layer for layer in self.layers if isinstance(layer, TileLayer)]

    def object_groups(self) -> list[ObjectGroup]:
        return [layer for layer in self.layers if isinstance(layer, ObjectGroup)]

    def all_objects(self) -> list[tuple[ObjectGroup, MapObject]]:
        return [(group, obj) for group in self.object_groups() for obj in group.objects]

    # ---------------- alokacja identyfikatorów ----------------

    def new_object_id(self) -> int:
        oid = self.nextobjectid
        self.nextobjectid += 1
        return oid

    def new_layer_id(self) -> int:
        lid = self.nextlayerid
        self.nextlayerid += 1
        return lid

    def add_object(self, layer: str, obj: MapObject) -> MapObject:
        if not obj.id:
            obj.id = self.new_object_id()
        self.object_group(layer).objects.append(obj)
        return obj

    # ---------------- geometria ----------------

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def tile_of(self, px: float, py: float) -> tuple[int, int]:
        return (int(px // self.tilewidth), int(py // self.tileheight))

    def pixel_size(self) -> tuple[int, int]:
        return (self.width * self.tilewidth, self.height * self.tileheight)

    # ---------------- odczyt i zapis ----------------

    @classmethod
    def load(cls, path: str | Path) -> TiledMap:
        path = Path(path)
        root = ET.parse(path).getroot()
        tmap = cls(
            path=path,
            width=int(root.get("width", 0)),
            height=int(root.get("height", 0)),
            tilewidth=int(root.get("tilewidth", TILE_SIZE)),
            tileheight=int(root.get("tileheight", TILE_SIZE)),
            version=root.get("version", TMX_VERSION),
            tiledversion=root.get("tiledversion", TILED_VERSION),
            orientation=root.get("orientation", "orthogonal"),
            renderorder=root.get("renderorder", "right-down"),
            infinite=int(root.get("infinite", 0)),
            nextlayerid=int(root.get("nextlayerid", 1)),
            nextobjectid=int(root.get("nextobjectid", 1)),
            props=_parse_props(root),
        )
        for node in root:
            if node.tag == "tileset":
                tmap.tilesets.append(TilesetRef(
                    firstgid=int(node.get("firstgid", 1)),
                    source=node.get("source", ""),
                ))
            elif node.tag == "layer":
                tmap.layers.append(_parse_tile_layer(node))
            elif node.tag == "objectgroup":
                tmap.layers.append(_parse_object_group(node))
        return tmap

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path is not None else self.path
        if target is None:
            raise ValueError("brak ścieżki zapisu")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_xml(), encoding="utf-8")
        self.path = target
        return target

    def to_xml(self) -> str:
        out: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>']
        attrs = [
            ("version", self.version), ("tiledversion", self.tiledversion),
            ("orientation", self.orientation), ("renderorder", self.renderorder),
            ("width", str(self.width)), ("height", str(self.height)),
            ("tilewidth", str(self.tilewidth)), ("tileheight", str(self.tileheight)),
            ("infinite", str(self.infinite)),
            ("nextlayerid", str(self.nextlayerid)), ("nextobjectid", str(self.nextobjectid)),
        ]
        out.append(f"<map {_attrs(attrs)}>")
        out.extend(_props_xml(self.props, 1))
        for ref in self.tilesets:
            out.append(f' <tileset firstgid="{ref.firstgid}" source="{_esc(ref.source)}"/>')
        for layer in self.layers:
            if isinstance(layer, TileLayer):
                out.extend(_tile_layer_xml(layer))
            else:
                out.extend(_object_group_xml(layer))
        out.append("</map>")
        return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# MARK: parsowanie


def _parse_tile_layer(node: ET.Element) -> TileLayer:
    width = int(node.get("width", 0))
    height = int(node.get("height", 0))
    data_node = node.find("data")
    encoding = data_node.get("encoding", "") if data_node is not None else ""
    if data_node is None or encoding != "csv":
        raise ValueError(
            f"warstwa '{node.get('name')}': obsługiwane jest wyłącznie kodowanie CSV "
            f"(jest '{encoding or 'brak'}'). Zapisz mapę w Tiled jako CSV."
        )
    raw = (data_node.text or "").replace("\n", "").replace(" ", "")
    values = [int(chunk) for chunk in raw.split(",") if chunk]
    if len(values) != width * height:
        raise ValueError(
            f"warstwa '{node.get('name')}': {len(values)} kafli zamiast {width * height}"
        )
    data = [values[y * width:(y + 1) * width] for y in range(height)]
    opacity = node.get("opacity")
    return TileLayer(
        id=int(node.get("id", 0)),
        name=node.get("name", ""),
        width=width,
        height=height,
        data=data,
        opacity=float(opacity) if opacity is not None else None,
        visible=node.get("visible", "1") != "0",
        props=_parse_props(node),
    )


def _parse_object(node: ET.Element) -> MapObject:
    obj = MapObject(
        id=int(node.get("id", 0)),
        name=node.get("name", ""),
        type=node.get("type", "") or node.get("class", ""),
        x=float(node.get("x", 0)),
        y=float(node.get("y", 0)),
        width=float(node.get("width", 0)),
        height=float(node.get("height", 0)),
        gid=int(node.get("gid", 0)),
        rotation=float(node.get("rotation", 0)),
        visible=node.get("visible", "1") != "0",
        props=_parse_props(node),
    )
    for shape in ("point", "ellipse", "polygon", "polyline"):
        found = node.find(shape)
        if found is None:
            continue
        obj.shape = shape
        raw = found.get("points", "")
        if raw:
            obj.points = [
                (float(pair.split(",")[0]), float(pair.split(",")[1]))
                for pair in raw.split(" ") if pair
            ]
        break
    return obj


def _parse_object_group(node: ET.Element) -> ObjectGroup:
    opacity = node.get("opacity")
    return ObjectGroup(
        id=int(node.get("id", 0)),
        name=node.get("name", ""),
        visible=node.get("visible", "1") != "0",
        opacity=float(opacity) if opacity is not None else None,
        objects=[_parse_object(child) for child in node.findall("object")],
        props=_parse_props(node),
    )


# --------------------------------------------------------------------------
# MARK: serializacja w formacie Tiled


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _num(value: float) -> str:
    """Tiled zapisuje liczby całkowite bez części dziesiętnej."""
    return str(int(value)) if float(value).is_integer() else repr(round(float(value), 4))


def _attrs(pairs: list[tuple[str, str]]) -> str:
    return " ".join(f'{key}="{_esc(value)}"' for key, value in pairs)


def _props_xml(props: Props, depth: int) -> list[str]:
    if not props.items:
        return []
    pad = " " * depth
    out = [f"{pad}<properties>"]
    for name, (type_, value) in props.items.items():
        attrs = [("name", name)]
        if type_:
            attrs.append(("type", type_))
        attrs.append(("value", value))
        out.append(f"{pad} <property {_attrs(attrs)}/>")
    out.append(f"{pad}</properties>")
    return out


def _tile_layer_xml(layer: TileLayer) -> list[str]:
    attrs = [("id", str(layer.id)), ("name", layer.name),
             ("width", str(layer.width)), ("height", str(layer.height))]
    if layer.opacity is not None:
        attrs.append(("opacity", _num(layer.opacity)))
    if not layer.visible:
        attrs.append(("visible", "0"))
    out = [f" <layer {_attrs(attrs)}>"]
    out.extend(_props_xml(layer.props, 2))
    out.append('  <data encoding="csv">')
    # Format jak w Tiled: wiersz kafli na linię, przecinek na końcu każdej linii
    # poza ostatnią, `</data>` w kolumnie 0.
    rows = [",".join(str(gid) for gid in row) for row in layer.data]
    out.append(",\n".join(rows))
    out.append("</data>")
    out.append(" </layer>")
    return out


def _object_xml(obj: MapObject) -> list[str]:
    attrs: list[tuple[str, str]] = [("id", str(obj.id))]
    if obj.name:
        attrs.append(("name", obj.name))
    if obj.type:
        attrs.append(("type", obj.type))
    if obj.gid:
        attrs.append(("gid", str(obj.gid)))
    attrs.append(("x", _num(obj.x)))
    attrs.append(("y", _num(obj.y)))
    if obj.width or obj.height:
        attrs.append(("width", _num(obj.width)))
        attrs.append(("height", _num(obj.height)))
    if obj.rotation:
        attrs.append(("rotation", _num(obj.rotation)))
    if not obj.visible:
        attrs.append(("visible", "0"))

    body = _props_xml(obj.props, 3)
    if obj.shape == "point":
        body.append("   <point/>")
    elif obj.shape == "ellipse":
        body.append("   <ellipse/>")
    elif obj.shape in ("polygon", "polyline"):
        pts = " ".join(f"{_num(px)},{_num(py)}" for px, py in obj.points)
        body.append(f'   <{obj.shape} points="{pts}"/>')

    if not body:
        return [f"  <object {_attrs(attrs)}/>"]
    return [f"  <object {_attrs(attrs)}>", *body, "  </object>"]


def _object_group_xml(group: ObjectGroup) -> list[str]:
    attrs = [("id", str(group.id)), ("name", group.name)]
    if group.opacity is not None:
        attrs.append(("opacity", _num(group.opacity)))
    if not group.visible:
        attrs.append(("visible", "0"))
    body = _props_xml(group.props, 2)
    for obj in group.objects:
        body.extend(_object_xml(obj))
    if not body:
        # Tiled zapisuje pustą warstwę obiektową jako element samozamykający
        return [f" <objectgroup {_attrs(attrs)}/>"]
    return [f" <objectgroup {_attrs(attrs)}>", *body, " </objectgroup>"]


# --------------------------------------------------------------------------
# MARK: fabryka nowej mapy zewnętrznej


def new_outdoor_map(path: str | Path, width: int, height: int,
                    particles: str = "leafs,rain") -> TiledMap:
    """Pusta mapa zewnętrzna z pełnym, kanonicznym kompletem warstw i tilesetów.

    Wszystkie dwanaście warstw powstaje od razu i w wiążącej kolejności - mapa bez
    którejś z nich nie jest "prostsza", tylko niezgodna z kontraktem (patrz
    docstring modułu). Puste warstwy obiektowe nic nie kosztują.
    """
    path = Path(path)
    tmap = TiledMap(path=path, width=width, height=height)
    tmap.props.set_bool("outdoor", True)
    tmap.props.set("particles", particles)
    tmap.tilesets = [
        TilesetRef(firstgid, tileset_source(name, path))
        for firstgid, name in OUTDOOR_TILESETS
    ]
    for name in TILE_LAYERS:
        tmap.layers.append(TileLayer(
            id=tmap.new_layer_id(),
            name=name,
            width=width,
            height=height,
            data=[[EMPTY] * width for _ in range(height)],
            opacity=OVER_LAYER_OPACITY if name == "over" else None,
        ))
    for name in OBJECT_LAYERS:
        tmap.layers.append(ObjectGroup(id=tmap.new_layer_id(), name=name))
    return tmap
