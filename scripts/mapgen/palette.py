#!/usr/bin/env python3
"""Katalog klocków ("stampów") czytany z warstwy `stamps` mapy-prototypu.

Nazwany prostokąt w `_wip/BLUNDERHAVEN_base.tmx` = jeden klocek. Skrypt wycina
z niego WSZYSTKIE sześć warstw kafelkowych naraz, więc dom przenosi się razem
z dachem (`over`), progiem (`foliage`) i kolizją (`walls`) - a nie jako sam
obrazek. Źródłem prawdy jest plik Tiled, nie osobny plik danych: obrys klocka
to decyzja graficzna i autor podejmuje ją myszą, w edytorze.

Kanoniczna tablica `firstgid` map zewnętrznych (patrz `tmx.OUTDOOR_TILESETS`)
jest identyczna w prototypie i w mapach gry, więc gidy przenoszą się 1:1 i nic
nie wymaga przeliczania. `Palette.paste` mimo to sprawdza zgodność tablic i
odmawia stemplowania między mapami o różnych tilesetach - cicha podmiana kafli
byłaby najdroższym w debugowaniu rodzajem błędu.

Właściwości obiektu w warstwie `stamps`:

    kind    building | fence | wall | prop | nature | farmyard | terrain | edge
    door    "dx,dy" - kafel drzwi względem lewego górnego rogu (budynki)
    anchor  bottom (domyślnie; budynki sadzi się dolną krawędzią) | center
    tags    lista po przecinku, do wyszukiwania
    tile    true = klocek wolno powtarzać w obie strony (płot, pole)

Użycie:

    python3 scripts/mapgen/palette.py list
    python3 scripts/mapgen/palette.py show tavern_tall --out /tmp/tavern.png
    python3 scripts/mapgen/palette.py sheet --out /tmp/klocki.png
    python3 scripts/mapgen/palette.py doors        # podpowiedź, gdzie są drzwi
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tmx import EMPTY, TILE_LAYERS, MapObject, TiledMap, maps_dir

STAMPS_LAYER = "stamps"
PROTOTYPE = maps_dir() / "_wip" / "BLUNDERHAVEN_base.tmx"

KINDS = ("building", "fence", "wall", "prop", "nature", "farmyard", "terrain", "edge")


@dataclass
class Stamp:
    """Wycinek wszystkich warstw kafelkowych plus opis, jak go sadzić."""

    name: str
    kind: str = "prop"
    x: int = 0
    y: int = 0
    w: int = 1
    h: int = 1
    door: tuple[int, int] | None = None
    anchor: str = "bottom"
    tags: list[str] = field(default_factory=list)
    tileable: bool = False
    layers: dict[str, list[list[int]]] = field(default_factory=dict)

    # ---------------- pytania, które zadaje generator ----------------

    def gids(self, layer: str) -> list[list[int]]:
        return self.layers.get(layer, [[EMPTY] * self.w for _ in range(self.h)])

    def blocking(self) -> set[tuple[int, int]]:
        """Kafle nieprzechodnie - czyli niepuste na `walls` (reguła `load_walls`)."""
        walls = self.gids("walls")
        return {(dx, dy) for dy in range(self.h) for dx in range(self.w) if walls[dy][dx]}

    def footprint(self) -> set[tuple[int, int]]:
        """Kafle, które klocek w ogóle zajmuje na którejkolwiek warstwie."""
        used: set[tuple[int, int]] = set()
        for rows in self.layers.values():
            for dy in range(self.h):
                for dx in range(self.w):
                    if rows[dy][dx]:
                        used.add((dx, dy))
        return used

    def door_tile(self) -> tuple[int, int] | None:
        return self.door

    def approach_tile(self) -> tuple[int, int] | None:
        """Kafel PRZED drzwiami - tam ma dochodzić ścieżka i tam staje NPC."""
        if self.door is None:
            return None
        return (self.door[0], self.door[1] + 1)

    def is_empty(self) -> bool:
        return not self.footprint()


class Palette:
    """Katalog klocków jednej mapy-prototypu."""

    def __init__(self, source: Path, stamps: dict[str, Stamp],
                 tileset_keys: list[str]) -> None:
        self.source = source
        self.stamps = stamps
        self.tileset_keys = tileset_keys

    # ---------------- wczytanie ----------------

    @classmethod
    def load(cls, path: str | Path | None = None) -> Palette:
        path = Path(path) if path is not None else PROTOTYPE
        tmap = TiledMap.load(path)
        if not tmap.has_layer(STAMPS_LAYER):
            raise SystemExit(
                f"{path.name} nie ma warstwy '{STAMPS_LAYER}'. "
                f"Uruchom `just map-palette --bootstrap`, żeby ją założyć."
            )
        stamps: dict[str, Stamp] = {}
        for obj in tmap.object_group(STAMPS_LAYER).objects:
            stamp = cls._cut(tmap, obj)
            if stamp.name in stamps:
                raise SystemExit(f"{path.name}: duplikat nazwy klocka '{stamp.name}'")
            stamps[stamp.name] = stamp
        return cls(path, stamps, [ref.key for ref in tmap.tilesets])

    @staticmethod
    def _cut(tmap: TiledMap, obj: MapObject) -> Stamp:
        tx, ty = tmap.tile_of(obj.x, obj.y)
        tw = max(1, int(round(obj.width / tmap.tilewidth)))
        th = max(1, int(round(obj.height / tmap.tileheight)))
        door_raw = obj.props.get("door", "")
        door: tuple[int, int] | None = None
        if door_raw:
            parts = door_raw.replace(" ", "").split(",")
            if len(parts) == 2 and all(p.lstrip("-").isdigit() for p in parts):
                door = (int(parts[0]), int(parts[1]))

        stamp = Stamp(
            name=obj.name,
            kind=obj.props.get("kind", "prop"),
            x=tx, y=ty, w=tw, h=th,
            door=door,
            anchor=obj.props.get("anchor", "bottom"),
            tags=[t.strip() for t in obj.props.get("tags", "").split(",") if t.strip()],
            tileable=obj.props.as_bool("tile", False),
        )
        for name in TILE_LAYERS:
            if not tmap.has_layer(name):
                continue
            layer = tmap.tile_layer(name)
            stamp.layers[name] = [
                [layer.get(tx + dx, ty + dy) for dx in range(tw)] for dy in range(th)
            ]
        return stamp

    # ---------------- wyszukiwanie ----------------

    def get(self, name: str) -> Stamp:
        if name not in self.stamps:
            near = [n for n in self.stamps if name.lower() in n.lower()]
            hint = f" Może chodziło o: {', '.join(sorted(near)[:5])}." if near else ""
            raise SystemExit(f"katalog nie ma klocka '{name}'.{hint}")
        return self.stamps[name]

    def of_kind(self, kind: str) -> list[Stamp]:
        return [s for s in self.stamps.values() if s.kind == kind]

    def tagged(self, tag: str) -> list[Stamp]:
        return [s for s in self.stamps.values() if tag in s.tags]

    # ---------------- warianty terenu ----------------

    def terrain_variants(self, name: str, layer: str = "ground") -> dict[int, int]:
        """gid -> ile razy wystąpił w próbce terenu. Wagi biorą się z częstości,
        więc autor steruje nimi malując w Tiled, a nie edytując tabelę."""
        stamp = self.get(name)
        if stamp.kind != "terrain":
            raise SystemExit(f"'{name}' to klocek rodzaju '{stamp.kind}', a nie 'terrain'")
        counts: dict[int, int] = {}
        for row in stamp.gids(layer):
            for gid in row:
                if gid:
                    counts[gid] = counts.get(gid, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))

    # ---------------- stemplowanie ----------------

    def paste(self, tmap: TiledMap, name: str, at: tuple[int, int],
              layers: list[str] | None = None, clear: bool = True) -> Stamp:
        """Postaw klocek lewym górnym rogiem w (x, y). Zwraca użyty klocek."""
        self._assert_same_tilesets(tmap)
        stamp = self.get(name)
        ax, ay = at
        for layer_name in (layers or TILE_LAYERS):
            if not tmap.has_layer(layer_name):
                continue
            target = tmap.tile_layer(layer_name)
            rows = stamp.gids(layer_name)
            for dy in range(stamp.h):
                for dx in range(stamp.w):
                    gid = rows[dy][dx]
                    if gid or clear:
                        target.set(ax + dx, ay + dy, gid if gid else target.get(ax + dx, ay + dy))
                    if gid:
                        target.set(ax + dx, ay + dy, gid)
        return stamp

    def _assert_same_tilesets(self, tmap: TiledMap) -> None:
        keys = [ref.key for ref in tmap.tilesets]
        if keys != self.tileset_keys:
            raise SystemExit(
                "tablica tilesetów mapy docelowej różni się od prototypu, więc te same "
                "gidy znaczyłyby co innego.\n"
                f"  prototyp: {', '.join(self.tileset_keys)}\n"
                f"  mapa:     {', '.join(keys)}"
            )


# --------------------------------------------------------------------------
# MARK: podpowiadanie drzwi


def guess_doors(palette: Palette) -> list[tuple[str, tuple[int, int] | None, float]]:
    """Zgadnij kafel drzwi: najciemniejszy kafel w dolnym pasie budynku.

    Drzwi w tym tilesecie to ciemny otwór, więc jasność jest sygnałem mocnym i
    tanim. To tylko PODPOWIEDŹ do wpisania w Tiled - ostatnie słowo ma autor,
    który i tak ogląda arkusz kontaktowy.
    """
    from PIL import Image

    from render_map import TileCache
    from tileset import TilesetTable

    tmap = TiledMap.load(palette.source)
    cache = TileCache(TilesetTable(tmap.tilesets, palette.source), 16, 16)

    def luma(gid: int) -> float:
        tile = cache.get(gid)
        if tile is None:
            return 255.0
        grey = tile.convert("L")
        alpha = tile.getchannel("A")
        pixels = [g for g, a in zip(grey.getdata(), alpha.getdata()) if a > 40]
        return sum(pixels) / len(pixels) if pixels else 255.0

    out: list[tuple[str, tuple[int, int] | None, float]] = []
    for stamp in palette.of_kind("building"):
        walls = stamp.gids("walls")
        best: tuple[int, int] | None = None
        best_luma = 255.0
        # tylko dolny wiersz: drzwi są zawsze u dołu bryły
        dy = stamp.h - 1
        for dx in range(stamp.w):
            gid = walls[dy][dx]
            if not gid:
                continue
            value = luma(gid)
            if value < best_luma:
                best_luma, best = value, (dx, dy)
        out.append((stamp.name, best, best_luma))
    return out


# --------------------------------------------------------------------------
# MARK: render klocków


def render_stamp(palette: Palette, name: str, scale: int = 4,
                 mark_door: bool = True) -> "Image.Image":
    from PIL import Image, ImageDraw

    from render_map import TileCache, render_tiles
    from tileset import TilesetTable

    stamp = palette.get(name)
    tmap = TiledMap.load(palette.source)
    cache = TileCache(TilesetTable(tmap.tilesets, palette.source), 16, 16)
    image = render_tiles(tmap, cache, list(TILE_LAYERS), (stamp.x, stamp.y, stamp.w, stamp.h))
    image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    if mark_door and stamp.door:
        draw = ImageDraw.Draw(image, "RGBA")
        dx, dy = stamp.door
        draw.rectangle(
            [dx * 16 * scale, dy * 16 * scale, (dx + 1) * 16 * scale - 1, (dy + 1) * 16 * scale - 1],
            outline=(255, 60, 60, 255), width=max(2, scale // 2),
        )
    return image


def contact_sheet(palette: Palette, cell: int = 190, columns: int = 6) -> "Image.Image":
    """Arkusz kontaktowy wszystkich klocków - jeden obraz do akceptacji przez autora.

    Każdy klocek skalowany osobno do wspólnej komórki: bez tego jedna zagroda
    26x12 kafli narzucałaby rozmiar komórki wszystkim i arkusz miałby 9000 px.
    Skala jest całkowita, gdy się mieści (pixel art nie znosi interpolacji przy
    powiększaniu), a przy zmniejszaniu idzie przez BOX.
    """
    from PIL import Image, ImageDraw

    from render_map import _font, _label

    names = sorted(palette.stamps, key=lambda n: (palette.stamps[n].kind, n))
    pad, header = 8, 34
    inner = cell - pad * 2

    thumbs: list["Image.Image"] = []
    for name in names:
        raw = render_stamp(palette, name, scale=1)
        factor = min(inner / raw.width, inner / raw.height)
        if factor >= 1:
            factor = max(1, int(factor))          # powiększanie tylko całkowicie
            resample = Image.Resampling.NEAREST
        else:
            resample = Image.Resampling.BOX
        size = (max(1, int(raw.width * factor)), max(1, int(raw.height * factor)))
        thumb = raw.resize(size, resample)
        if palette.stamps[name].door:
            dx, dy = palette.stamps[name].door        # type: ignore[misc]
            draw = ImageDraw.Draw(thumb, "RGBA")
            draw.rectangle(
                [dx * 16 * factor, dy * 16 * factor,
                 (dx + 1) * 16 * factor - 1, (dy + 1) * 16 * factor - 1],
                outline=(255, 60, 60, 255), width=max(1, int(factor)),
            )
        thumbs.append(thumb)

    rows = (len(thumbs) + columns - 1) // columns
    sheet = Image.new("RGBA", (cell * columns, (cell + header) * rows), (30, 30, 34, 255))
    draw = ImageDraw.Draw(sheet, "RGBA")
    font = _font(13)
    small = _font(11)
    for idx, (name, thumb) in enumerate(zip(names, thumbs)):
        col, row = idx % columns, idx // columns
        ox, oy = col * cell, row * (cell + header)
        draw.rectangle([ox, oy, ox + cell - 1, oy + cell + header - 1], outline=(70, 70, 78, 255))
        stamp = palette.stamps[name]
        door = f"drzwi {stamp.door[0]},{stamp.door[1]}" if stamp.door else "bez drzwi"
        _label(draw, (ox + pad, oy + 3), name, font)
        _label(draw, (ox + pad, oy + 18),
               f"{stamp.kind}  {stamp.w}x{stamp.h}  {door}"
               f"{'  kafelkowalny' if stamp.tileable else ''}", small, (150, 150, 160))
        sheet.alpha_composite(
            thumb,
            (ox + (cell - thumb.width) // 2, oy + header + (cell - thumb.height) // 2),
        )
    return sheet


# --------------------------------------------------------------------------
# MARK: zasiew katalogu

# Pierwsze obrysy klocków, odczytane z prototypu analizą spójnych brył na
# `walls`+`over` (budynek = wiersz dachu na `over` + wiersze ścian na `walls`).
# To TYLKO ZASIEW: po jednorazowym `bootstrap` źródłem prawdy jest warstwa
# `stamps` w pliku Tiled, którą autor poprawia myszą. Dlatego `bootstrap`
# odmawia nadpisania istniejącej warstwy bez `--force`.
SEED: tuple[tuple[str, str, int, int, int, int, str], ...] = (
    # nazwa, rodzaj, x, y, w, h, dodatkowe właściwości "klucz=wartość;..."
    ("hut_awning",          "building",  0,  0,  3,  3, ""),
    ("hut_brown",           "building",  0,  3,  3,  3, ""),
    ("hut_round_straw",     "building",  4,  0,  3,  2, ""),
    ("hut_round_cream",     "building",  9,  0,  2,  2, ""),
    ("house_cottage",       "building",  4,  3,  4,  3, "tags=dom,wies"),
    ("house_cream",         "building",  9,  3,  4,  3, "tags=dom,sklep"),
    ("house_ornate",        "building", 14,  3,  3,  3, "tags=dom,bogaty"),
    ("house_red",           "building", 18,  3,  3,  3, "tags=dom,wies"),
    ("hut_kiln",            "building", 22,  2,  3,  4, "tags=piec,warsztat"),
    ("farmhouse_big_1",     "building", 26,  1,  4,  5, "tags=dom,duzy"),
    ("farmhouse_big_2",     "building", 31,  1,  4,  5, "tags=dom,duzy"),
    ("tavern_tall",         "building", 36,  1,  4,  5, "tags=tawerna,duzy,pietrowy"),
    ("barn_wood",           "building", 42,  3,  3,  3, "tags=stodola,stajnia"),
    ("house_farmstead",     "building", 33, 18,  4,  3, "door=1,2;tags=dom,wies"),
    ("hut_cream_small",     "building", 25, 16,  2,  2, "tags=spichlerz"),

    ("fence_blue_gate",     "fence",     8,  7,  5,  3, "tile=true;tags=brama"),
    ("fence_wood",          "fence",    14,  7,  7,  3, "tile=true"),
    ("wall_stone",          "wall",     22,  7,  7,  3, "tile=true"),
    ("fence_rail_dark",     "fence",    30,  7,  6,  3, "tile=true"),

    ("well",                "prop",     39,  7,  1,  2, "tags=studnia,spotkania"),
    ("sunflowers",          "prop",     29, 14,  3,  3, "tile=true;tags=uprawa"),

    ("farmyard_small",      "farmyard",  0, 12, 11, 11, "tags=zagroda,kurnik,obora"),
    ("farmyard_big",        "farmyard", 13, 12, 26, 12, "tags=zagroda,pelna"),

    ("tree_round",          "nature",   53,  1,  2,  2, "anchor=center;tags=drzewo,las"),
    ("tree_bushy",          "nature",   55,  1,  2,  2, "anchor=center;tags=drzewo,las"),
    ("tree_fir",            "nature",   57,  1,  2,  2, "anchor=center;tags=drzewo,las,iglaste"),
    ("tree_dead",           "nature",   59,  1,  2,  2, "anchor=center;tags=drzewo,suche"),
    ("tree_stump",          "nature",   61,  1,  2,  2, "anchor=center;tags=drzewo,powalone"),
    ("tree_fir_big",        "nature",   55,  3,  4,  3, "anchor=center;tags=drzewo,las,duze"),
    ("tree_oak_big",        "nature",   59,  3,  4,  3, "anchor=center;tags=drzewo,las,duze"),
    ("tree_blossom_pink",   "nature",   52,  6,  3,  3, "anchor=center;tags=drzewo,sad"),
    ("tree_orchard_green",  "nature",   55,  6,  3,  3, "anchor=center;tags=drzewo,sad"),
    ("tree_blossom_white",  "nature",   58,  6,  3,  3, "anchor=center;tags=drzewo,sad"),
    ("tree_blossom_orange", "nature",   61,  6,  3,  3, "anchor=center;tags=drzewo,sad"),

    # Próbki terenu: wagi wariantów biorą się z CZĘSTOŚCI gidów w prostokącie,
    # więc autor steruje nimi malując w Tiled, a nie edytując tabelę.
    ("grass",               "terrain",   0, 30, 32, 16, "tags=trawa,baza"),
    ("field_crop",          "terrain",  48, 12,  6,  8, "tags=pole,uprawa"),
)


def bootstrap(map_path: Path, force: bool = False) -> int:
    """Załóż w prototypie warstwę `stamps` z zasiewu SEED (jednorazowo)."""
    from tmx import ObjectGroup, MapObject as Obj

    tmap = TiledMap.load(map_path)
    if tmap.has_layer(STAMPS_LAYER):
        if not force:
            raise SystemExit(
                f"{map_path.name} ma już warstwę '{STAMPS_LAYER}' - to ona jest źródłem "
                f"prawdy. Użyj --force, żeby ją nadpisać zasiewem (stracisz poprawki z Tiled)."
            )
        tmap.layers = [lay for lay in tmap.layers if lay.name != STAMPS_LAYER]

    group = ObjectGroup(id=tmap.new_layer_id(), name=STAMPS_LAYER, visible=False)
    for name, kind, x, y, w, h, extra in SEED:
        obj = Obj(
            id=tmap.new_object_id(), name=name,
            x=float(x * tmap.tilewidth), y=float(y * tmap.tileheight),
            width=float(w * tmap.tilewidth), height=float(h * tmap.tileheight),
        )
        obj.props.set("kind", kind)
        for pair in (part for part in extra.split(";") if part):
            key, _, value = pair.partition("=")
            if key == "tile":
                obj.props.set_bool("tile", value.lower() == "true")
            else:
                obj.props.set(key, value)
        group.objects.append(obj)
    tmap.layers.append(group)
    tmap.save(map_path)
    print(f"{map_path}: warstwa '{STAMPS_LAYER}' z {len(group.objects)} klockami")
    return 0


# --------------------------------------------------------------------------
# MARK: CLI


def cmd_list(palette: Palette, args: argparse.Namespace) -> int:
    from report import Row, report

    rows = []
    for name in sorted(palette.stamps, key=lambda n: (palette.stamps[n].kind, n)):
        stamp = palette.stamps[name]
        door = f"{stamp.door[0]},{stamp.door[1]}" if stamp.door else "-"
        rows.append(Row(
            level="info",
            source=stamp.kind,
            key=name,
            message=f"{stamp.w}x{stamp.h} kafli, drzwi {door}"
                    f"{', kafelkowalny' if stamp.tileable else ''}"
                    f"{'  [' + ','.join(stamp.tags) + ']' if stamp.tags else ''}",
        ))
    report(rows, title=f"Katalog klocków - {palette.source.name}",
           summary=f"{len(palette.stamps)} klocków")
    return 0


def cmd_show(palette: Palette, args: argparse.Namespace) -> int:
    image = render_stamp(palette, args.name, scale=args.scale)
    out = Path(args.out or f"/tmp/stamp_{args.name}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(out)
    stamp = palette.get(args.name)
    print(f"{out}  {stamp.w}x{stamp.h} kafli  rodzaj={stamp.kind}  "
          f"drzwi={stamp.door}  blokuje {len(stamp.blocking())} kafli")
    return 0


def cmd_sheet(palette: Palette, args: argparse.Namespace) -> int:
    sheet = contact_sheet(palette, cell=args.cell, columns=args.columns)
    out = Path(args.out or "/tmp/mapgen/klocki.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(out)
    print(f"{out}  {sheet.width}x{sheet.height}px  {len(palette.stamps)} klocków")
    return 0


def cmd_doors(palette: Palette, args: argparse.Namespace) -> int:
    print(f"{'klocek':<24} {'w pliku':>9} {'podpowiedź':>11}  jasność")
    for name, guess, value in sorted(guess_doors(palette)):
        stamp = palette.get(name)
        have = f"{stamp.door[0]},{stamp.door[1]}" if stamp.door else "-"
        want = f"{guess[0]},{guess[1]}" if guess else "-"
        flag = "" if have == want else "   <- różnica"
        print(f"{name:<24} {have:>9} {want:>11}  {value:6.1f}{flag}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--map", default=str(PROTOTYPE), help="mapa z warstwą `stamps`")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="tabela wszystkich klocków")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="render jednego klocka")
    p_show.add_argument("name")
    p_show.add_argument("--out")
    p_show.add_argument("--scale", type=int, default=6)
    p_show.set_defaults(func=cmd_show)

    p_sheet = sub.add_parser("sheet", help="arkusz kontaktowy wszystkich klocków")
    p_sheet.add_argument("--out")
    p_sheet.add_argument("--cell", type=int, default=190, help="bok komórki w px")
    p_sheet.add_argument("--columns", type=int, default=6)
    p_sheet.set_defaults(func=cmd_sheet)

    p_doors = sub.add_parser("doors", help="podpowiedz kafel drzwi dla budynków")
    p_doors.set_defaults(func=cmd_doors)

    p_boot = sub.add_parser("bootstrap", help="załóż warstwę `stamps` z zasiewu (jednorazowo)")
    p_boot.add_argument("--force", action="store_true", help="nadpisz istniejącą warstwę")
    p_boot.set_defaults(func=None)

    args = parser.parse_args(argv)
    if args.cmd == "bootstrap":
        return bootstrap(Path(args.map), force=args.force)
    palette = Palette.load(args.map)
    return int(args.func(palette, args))


if __name__ == "__main__":
    sys.exit(main())
