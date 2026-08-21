#!/usr/bin/env python3
"""Render mapy .tmx do PNG - oczy skilla `tiled-map` (bez pygame i SDL).

Dwa poziomy podglądu, bo mapa 256x256 kafli to obraz 4096x4096 px, a model
dostaje go przeskalowanego do ~1568 px na dłuższym boku - kafel schodzi wtedy
do ~6 px i nie da się na nim ocenić ani wariantów trawy, ani czy drzwi mają
dojście. Stąd podział:

* ``--overview``  - cała mapa pomniejszona, z siatką i etykietami współrzędnych;
  do oceny KOMPOZYCJI (czy droga się wije, czy pola nie są w idealnej kratce).
* ``--crop X,Y,W,H`` - wycinek w skali 1:1, kafel ma pełne 16 px; do oceny DETALU.
  Wołany tam, gdzie `lint_map.py` coś zgłosił - linter zawęża, gdzie patrzeć.

Do tego nakładki diagnostyczne (``--overlay``), które odpowiadają na pytanie
"czy da się dojść do stodoły" pewniej i szybciej niż oglądanie kafelków.

Przykłady:

    just map-render BLUNDERHAVEN --overview
    just map-render BLUNDERHAVEN --crop 40,40,32,32
    just map-render BLUNDERHAVEN --overlay reach
"""
from __future__ import annotations

import argparse
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image, ImageDraw, ImageFont

from tileset import TilesetTable
from tmx import (
    OBJECT_LAYERS,
    TILE_LAYERS,
    MapObject,
    ObjectGroup,
    TiledMap,
    TileLayer,
    bare_gid,
    gid_flags,
    GID_FLIP_D,
    GID_FLIP_H,
    GID_FLIP_V,
    maps_dir,
)

FONT_PATH = Path(__file__).resolve().parent.parent.parent / "project" / "assets" / "fonts" / "munro.ttf"

# Kolory markerów obiektów - jeden na warstwę, żeby overview czytało się jak legenda.
OBJECT_COLORS: dict[str, tuple[int, int, int]] = {
    "interactions": (233, 49, 49),
    "entry_points": (28, 126, 214),
    "waypoints": (232, 146, 12),
    "places": (47, 158, 68),
    "spawn_points": (190, 75, 219),
    "zones": (26, 188, 188),
    "stamps": (255, 210, 0),
}

CHECKER_A = (54, 54, 60)
CHECKER_B = (44, 44, 50)


# --------------------------------------------------------------------------
# MARK: cache kafli


class TileCache:
    """gid -> obrazek 16x16. Rozwiązuje flagi obrotu i tilesety-kolekcje."""

    def __init__(self, table: TilesetTable, tilewidth: int, tileheight: int) -> None:
        self.table = table
        self.tw = tilewidth
        self.th = tileheight
        self._images: dict[int, Image.Image | None] = {}
        self._sheets: dict[Path, Image.Image] = {}

    def _sheet(self, path: Path) -> Image.Image | None:
        if path not in self._sheets:
            if not path.exists():
                return None
            self._sheets[path] = Image.open(path).convert("RGBA")
        return self._sheets[path]

    def get(self, gid: int) -> Image.Image | None:
        if not gid:
            return None
        if gid in self._images:
            return self._images[gid]

        plain = bare_gid(gid)
        hit = self.table.resolve(plain)
        image: Image.Image | None = None
        if hit is not None:
            sheet_path = hit.tileset.tile_image_path(hit.local_id)
            box = hit.tileset.tile_box(hit.local_id)
            sheet = self._sheet(sheet_path) if sheet_path else None
            if sheet is not None and box is not None:
                # kafel z kolekcji bywa większy niż siatka mapy (sprite 23x16)
                image = sheet.crop(box)

        if image is not None:
            flags = gid_flags(gid)
            if flags & GID_FLIP_D:
                image = image.transpose(Image.Transpose.TRANSPOSE)
            if flags & GID_FLIP_H:
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if flags & GID_FLIP_V:
                image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        self._images[gid] = image
        return image


# --------------------------------------------------------------------------
# MARK: render warstw


def _checkerboard(width: int, height: int, cell: int = 8) -> Image.Image:
    """Tło w szachownicę - przezroczysta dziura w terenie ma być widoczna, nie biała."""
    base = Image.new("RGBA", (width, height), CHECKER_A)
    draw = ImageDraw.Draw(base)
    for y in range(0, height, cell):
        for x in range(0, width, cell):
            if (x // cell + y // cell) % 2:
                draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=CHECKER_B)
    return base


def render_tiles(tmap: TiledMap, cache: TileCache, layers: list[str],
                 region: tuple[int, int, int, int]) -> Image.Image:
    """Kafle wybranych warstw z prostokąta (x, y, w, h) podanego w KAFLACH."""
    rx, ry, rw, rh = region
    tw, th = tmap.tilewidth, tmap.tileheight
    canvas = _checkerboard(rw * tw, rh * th)

    for layer in tmap.layers:
        if not isinstance(layer, TileLayer) or layer.name not in layers:
            continue
        # `sprites` jest z definicji pusta (rysuje na niej gra), `items` gra gasi
        # po wczytaniu - ale w renderze chcemy je widzieć, więc nic nie pomijamy.
        buffer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        for y in range(ry, min(ry + rh, layer.height)):
            for x in range(rx, min(rx + rw, layer.width)):
                gid = layer.data[y][x]
                if not gid:
                    continue
                tile = cache.get(gid)
                if tile is None:
                    continue
                # kafel wyższy niż siatka (drzewo, sprite) wisi w GÓRĘ od swojej komórki
                px = (x - rx) * tw
                py = (y - ry) * th + th - tile.height
                buffer.alpha_composite(tile, (px, py))
        if layer.opacity is not None and layer.opacity < 1.0:
            alpha = buffer.getchannel("A").point(lambda v: int(v * (layer.opacity or 1.0)))
            buffer.putalpha(alpha)
        canvas.alpha_composite(buffer)
    return canvas


# --------------------------------------------------------------------------
# MARK: siatka, etykiety, obiekty


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except OSError:
        return ImageFont.load_default()


def draw_grid(image: Image.Image, step_px: float, origin: tuple[int, int],
              step_tiles: int, coords: bool, scale: float) -> None:
    draw = ImageDraw.Draw(image, "RGBA")
    ox, oy = origin
    font = _font(max(9, int(11 * min(scale * 2, 1.6))))

    cols = int(image.width / step_px) + 1
    rows = int(image.height / step_px) + 1
    for col in range(cols + 1):
        x = col * step_px
        major = ((ox + col * step_tiles) % (step_tiles * 4)) == 0
        draw.line([(x, 0), (x, image.height)],
                  fill=(255, 255, 255, 70 if major else 30), width=1)
    for row in range(rows + 1):
        y = row * step_px
        major = ((oy + row * step_tiles) % (step_tiles * 4)) == 0
        draw.line([(0, y), (image.width, y)],
                  fill=(255, 255, 255, 70 if major else 30), width=1)

    if not coords:
        return
    for col in range(cols + 1):
        tile_x = ox + col * step_tiles
        if (tile_x % (step_tiles * 2)) or col * step_px > image.width - 8:
            continue
        _label(draw, (col * step_px + 2, 1), str(tile_x), font)
    for row in range(rows + 1):
        tile_y = oy + row * step_tiles
        if (tile_y % (step_tiles * 2)) or row * step_px > image.height - 8:
            continue
        _label(draw, (2, row * step_px + 1), str(tile_y), font)


def _label(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str,
           font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
           color: tuple[int, int, int] = (255, 255, 255)) -> None:
    x, y = xy
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 200))
    draw.text((x, y), text, font=font, fill=(*color, 255))


def draw_objects(image: Image.Image, tmap: TiledMap, region: tuple[int, int, int, int],
                 scale: float, labels: bool) -> None:
    """Markery obiektów: prostokąt strefy, kropka punktu, łamana trasy."""
    rx, ry, _, _ = region
    tw, th = tmap.tilewidth, tmap.tileheight
    draw = ImageDraw.Draw(image, "RGBA")
    font = _font(max(9, int(12 * min(scale * 2, 1.4))))

    def to_px(wx: float, wy: float) -> tuple[float, float]:
        return ((wx - rx * tw) * scale, (wy - ry * th) * scale)

    for group in tmap.object_groups():
        color = OBJECT_COLORS.get(group.name, (200, 200, 200))
        for obj in group.objects:
            _draw_one_object(draw, obj, color, to_px, scale)
            if labels and obj.name:
                lx, ly = to_px(obj.x, obj.y)
                _label(draw, (lx + 3, ly - 13), obj.name, font, color)


def _draw_one_object(draw: ImageDraw.ImageDraw, obj: MapObject,
                     color: tuple[int, int, int], to_px, scale: float) -> None:
    fill = (*color, 45)
    line = (*color, 220)
    if obj.shape in ("polygon", "polyline"):
        pts = [to_px(px, py) for px, py in obj.world_points()]
        if len(pts) >= 2:
            closed = obj.shape == "polygon"
            draw.line(pts + ([pts[0]] if closed else []), fill=line, width=max(1, int(scale)))
        for px, py in pts:
            radius = max(1.5, 2 * scale)
            draw.ellipse([px - radius, py - radius, px + radius, py + radius], fill=line)
        return

    if obj.width and obj.height:
        x0, y0 = to_px(obj.x, obj.top)
        x1, y1 = to_px(obj.x + obj.width, obj.top + obj.height)
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=line, width=max(1, int(scale)))
        return

    px, py = to_px(obj.x, obj.y)
    radius = max(2.5, 3.5 * scale)
    draw.ellipse([px - radius, py - radius, px + radius, py + radius],
                 fill=(*color, 200), outline=(255, 255, 255, 220))


# --------------------------------------------------------------------------
# MARK: nakładki diagnostyczne


def walkable_grid(tmap: TiledMap) -> list[list[bool]]:
    """Chodliwość wg reguły gry: każdy niepusty kafel na `walls` blokuje."""
    walls = tmap.tile_layer("walls")
    return [[walls.data[y][x] == 0 for x in range(tmap.width)] for y in range(tmap.height)]


def reachable_from(tmap: TiledMap, starts: list[tuple[int, int]]) -> list[list[bool]]:
    walk = walkable_grid(tmap)
    seen = [[False] * tmap.width for _ in range(tmap.height)]
    queue: deque[tuple[int, int]] = deque()
    for sx, sy in starts:
        if tmap.in_bounds(sx, sy) and walk[sy][sx] and not seen[sy][sx]:
            seen[sy][sx] = True
            queue.append((sx, sy))
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if tmap.in_bounds(nx, ny) and walk[ny][nx] and not seen[ny][nx]:
                seen[ny][nx] = True
                queue.append((nx, ny))
    return seen


def start_tiles(tmap: TiledMap) -> list[tuple[int, int]]:
    """Punkty, od których liczymy dostępność: `start` i wszystkie wejścia."""
    points: list[tuple[int, int]] = []
    try:
        group = tmap.object_group("entry_points")
    except KeyError:
        return points
    for obj in group.objects:
        mx, my = obj.midbottom if (obj.width or obj.height) else (obj.x, obj.y)
        points.append(tmap.tile_of(mx, my))
    return points


def overlay_reach(tmap: TiledMap, base: Image.Image, scale: float) -> Image.Image:
    seen = reachable_from(tmap, start_tiles(tmap))
    walk = walkable_grid(tmap)
    tint = Image.new("RGBA", (tmap.width, tmap.height), (0, 0, 0, 0))
    pixels = tint.load()
    for y in range(tmap.height):
        for x in range(tmap.width):
            if not walk[y][x]:
                pixels[x, y] = (0, 0, 0, 150)              # ściana
            elif not seen[y][x]:
                pixels[x, y] = (224, 49, 49, 190)          # chodliwe, ale odcięte
            else:
                pixels[x, y] = (47, 158, 68, 60)           # osiągalne
    return _blend_grid(base, tint, tmap, scale)


def overlay_cost(tmap: TiledMap, base: Image.Image, scale: float) -> Image.Image:
    table = TilesetTable(tmap.tilesets, tmap.path or Path("."))
    ground = tmap.tile_layer("ground")
    foliage = tmap.tile_layer("foliage")
    walls = tmap.tile_layer("walls")
    tint = Image.new("RGBA", (tmap.width, tmap.height), (0, 0, 0, 0))
    pixels = tint.load()
    for y in range(tmap.height):
        for x in range(tmap.width):
            if walls.data[y][x]:
                pixels[x, y] = (0, 0, 0, 200)
                continue
            # ta sama reguła co `load_step_cost`: wygrywa górna z dwóch dolnych warstw
            cost = table.step_cost(ground.data[y][x], 100)
            cost = table.step_cost(foliage.data[y][x], cost) if foliage.data[y][x] else cost
            level = max(0, min(255, int(255 - (cost - 100) * 255 / 400)))
            pixels[x, y] = (level, level, 255 - level, 150)
    return _blend_grid(base, tint, tmap, scale)


def overlay_detail(tmap: TiledMap, base: Image.Image, scale: float,
                   window: int = 8) -> Image.Image:
    """Gęstość detali w oknie NxN - czerwone są martwe, puste połacie."""
    layers = [tmap.tile_layer(name) for name in ("foliage", "items", "walls", "over")]
    tint = Image.new("RGBA", (tmap.width, tmap.height), (0, 0, 0, 0))
    pixels = tint.load()
    for y0 in range(0, tmap.height, window):
        for x0 in range(0, tmap.width, window):
            filled = sum(
                1
                for layer in layers
                for y in range(y0, min(y0 + window, tmap.height))
                for x in range(x0, min(x0 + window, tmap.width))
                if layer.data[y][x]
            )
            ratio = min(1.0, filled / (window * window))
            color = (224, 49, 49, 170) if ratio < 0.03 else (
                (232, 146, 12, 120) if ratio < 0.10 else (47, 158, 68, 60))
            for y in range(y0, min(y0 + window, tmap.height)):
                for x in range(x0, min(x0 + window, tmap.width)):
                    pixels[x, y] = color
    return _blend_grid(base, tint, tmap, scale)


def _blend_grid(base: Image.Image, tint: Image.Image, tmap: TiledMap,
                scale: float) -> Image.Image:
    size = (int(tmap.width * tmap.tilewidth * scale), int(tmap.height * tmap.tileheight * scale))
    grown = tint.resize(size, Image.Resampling.NEAREST)
    out = base.copy()
    out.alpha_composite(grown)
    return out


OVERLAYS = {"reach": overlay_reach, "cost": overlay_cost, "detail": overlay_detail}


# --------------------------------------------------------------------------
# MARK: CLI


def resolve_map(name: str) -> Path:
    """Nazwa mapy albo ścieżka. Bez rozszerzenia szukamy w `maps/` i `maps/_wip/`."""
    candidate = Path(name)
    if candidate.suffix == ".tmx" and candidate.exists():
        return candidate
    for folder in (maps_dir(), maps_dir() / "_wip"):
        hit = folder / f"{Path(name).stem}.tmx"
        if hit.exists():
            return hit
    raise SystemExit(f"nie znalazłem mapy '{name}' ani jako ścieżki, ani w maps/ i maps/_wip/")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("map", help="nazwa mapy (BLUNDERHAVEN) albo ścieżka do .tmx")
    parser.add_argument("--out", help="plik wynikowy PNG (domyślnie do katalogu tymczasowego)")
    parser.add_argument("--overview", action="store_true",
                        help="cała mapa, skala dobrana automatycznie, siatka + współrzędne")
    parser.add_argument("--crop", help="wycinek w KAFLACH: X,Y,W,H (domyślnie skala 1:1)")
    parser.add_argument("--scale", type=float, default=0.0, help="mnożnik skali (0 = auto)")
    parser.add_argument("--layers", default="", help="lista warstw po przecinku (domyślnie wszystkie)")
    parser.add_argument("--grid", type=int, default=0, help="siatka co N kafli (0 = bez siatki)")
    parser.add_argument("--coords", action="store_true", help="etykiety współrzędnych przy siatce")
    parser.add_argument("--objects", action="store_true", help="markery obiektów")
    parser.add_argument("--labels", action="store_true", help="nazwy obiektów (implikuje --objects)")
    parser.add_argument("--overlay", choices=sorted(OVERLAYS), help="nakładka diagnostyczna")
    parser.add_argument("--max-px", type=int, default=1536,
                        help="dłuższy bok obrazu przy --overview (domyślnie 1536)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = resolve_map(args.map)
    tmap = TiledMap.load(path)
    table = TilesetTable(tmap.tilesets, path)
    cache = TileCache(table, tmap.tilewidth, tmap.tileheight)

    if args.crop:
        parts = [int(part) for part in args.crop.split(",")]
        if len(parts) != 4:
            raise SystemExit("--crop oczekuje czterech liczb: X,Y,W,H (w kaflach)")
        region = (parts[0], parts[1], parts[2], parts[3])
    else:
        region = (0, 0, tmap.width, tmap.height)

    names = [n.strip() for n in args.layers.split(",") if n.strip()] or list(TILE_LAYERS)
    unknown = [n for n in names if n not in TILE_LAYERS]
    if unknown:
        raise SystemExit(f"nieznane warstwy kafelkowe: {', '.join(unknown)}; "
                         f"dostępne: {', '.join(TILE_LAYERS)}")

    image = render_tiles(tmap, cache, names, region)

    scale = args.scale
    if not scale:
        if args.overview or args.overlay:
            scale = min(1.0, args.max_px / max(image.width, image.height))
        else:
            scale = 1.0
    if scale != 1.0:
        size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
        # zmniejszanie: BOX (uśrednianie obszarem) czyta się lepiej dla kompozycji
        # niż NEAREST, który gubi cienkie linie; powiększanie: NEAREST, bo pixel art
        resample = Image.Resampling.BOX if scale < 1 else Image.Resampling.NEAREST
        image = image.resize(size, resample)

    if args.overlay:
        if region != (0, 0, tmap.width, tmap.height):
            raise SystemExit("--overlay działa na całej mapie, nie łącz go z --crop")
        image = OVERLAYS[args.overlay](tmap, image, scale)

    if args.objects or args.labels:
        draw_objects(image, tmap, region, scale, labels=args.labels)

    grid = args.grid or (16 if args.overview else 0)
    if grid:
        draw_grid(image, grid * tmap.tilewidth * scale, (region[0], region[1]),
                  grid, args.coords or args.overview, scale)

    out = Path(args.out) if args.out else Path("/tmp") / f"{path.stem}_render.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(out)
    print(f"{out}  {image.width}x{image.height}px  skala {scale:.3g}  "
          f"mapa {tmap.width}x{tmap.height} kafli  warstwy: {','.join(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
