#!/usr/bin/env python3
"""Operacje na gotowej mapie .tmx - drugi tryb pracy skilla `tiled-map`.

Po co osobne narzędzie zamiast ręcznej edycji XML-a: "przesuń dom Jakuba
z zagrodą o 4 kafle na wschód" dotyka SZEŚCIU warstw kafelkowych i SZEŚCIU
obiektowych naraz (razem z wierzchołkami wielokątów). Ręcznie to gwarantowany
błąd, a znajdzie się go dopiero w grze.

Reguła przy przenoszeniu, zgodna z tym, co autor ustalił:

* elementy NIEINTERAKTYWNE w miejscu docelowym (trawa, drzewa, płot) są
  nadpisywane bez pytania,
* elementy INTERAKTYWNE (wyjście, skrzynia, miejsce, spawn, punkt wejścia)
  są PRZESTAWIANE w najbliższe sensowne miejsce i WYPISYWANE w raporcie -
  nigdy nie kasowane po cichu, bo od nich zależy logika gry,
* dziura po źródle jest zasypywana kaflami próbkowanymi z pierścienia wokół,
  a nie jednym kaflem - inaczej zostaje prostokątna łata.

Ten sam zestaw operacji nakłada poprawki po lincie, więc naprawienie jednego
niedopasowanego kafla nigdy nie przemebluje całej mapy (w odróżnieniu od
generowania na nowo z innym ziarnem).

Użycie:

    just map-edit MAPA move --rect 20,30,12,10 --by 4,0
    just map-edit MAPA stamp --name barn_wood --at 40,52
    just map-edit MAPA erase --rect 60,20,8,8
    just map-edit MAPA revar --rect 0,0,64,64 --terrain grass
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from palette import Palette
from report import ERROR, INFO, OK, WARN, Row, report
from terrain import TerrainLib, ring_sample
from tileset import Tileset
from tmx import EMPTY, TILE_LAYERS, MapObject, TiledMap, maps_dir

# Warstwy, których obiekty niosą logikę gry - tych nie wolno po cichu nadpisać.
INTERACTIVE_LAYERS = ("interactions", "entry_points", "places", "spawn_points")
GEOMETRY_LAYERS = ("waypoints", "zones")
# Ten sam próg, co w `lint_map.ZONE_WALKABLE_MIN` - strefa złożona głównie ze ścian
# jest w grze bezużyteczna, a `load_zones` nie ma jak o tym powiedzieć.
ZONE_WALKABLE_MIN = 0.60


def resolve_map(name: str) -> Path:
    candidate = Path(name)
    if candidate.suffix == ".tmx" and candidate.exists():
        return candidate
    for folder in (maps_dir() / "_wip", maps_dir()):
        hit = folder / f"{Path(name).stem}.tmx"
        if hit.exists():
            return hit
    raise SystemExit(f"nie znalazłem mapy '{name}'")


class Editor:
    def __init__(self, path: Path, seed: int = 0) -> None:
        self.path = path
        self.tmap = TiledMap.load(path)
        self.rng = random.Random(seed or 1)
        self.rows: list[Row] = []
        self._terrain: TerrainLib | None = None

    @property
    def terrain(self) -> TerrainLib:
        if self._terrain is None:
            floor = Tileset.load(maps_dir() / "tilesets" / "Floor.tsx")
            self._terrain = TerrainLib(floor, 477)
        return self._terrain

    def save(self) -> None:
        self.tmap.save(self.path)

    # ------------------------------------------------------------------
    # MARK: przenoszenie

    def move(self, rect: tuple[int, int, int, int], by: tuple[int, int]) -> None:
        rx, ry, rw, rh = rect
        dx, dy = by
        dest = (rx + dx, ry + dy, rw, rh)
        self._relocate_blocking_objects(dest, rect)
        self._move_tiles(rect, by)
        self._move_objects(rect, by)
        self._backfill(rect, dest)
        self._warn_orphaned_entries(rect, by)
        self._warn_stale_zones()
        self.rows.append(Row(OK, "move", "",
                             f"przeniesiono {rw}x{rh} kafli z ({rx},{ry}) o ({dx},{dy}) "
                             f"na wszystkich 12 warstwach"))

    def _warn_stale_zones(self) -> None:
        """Strefy zostają na swoich kaflach, nawet gdy teren spod nich odjechał.

        Prostokąt strefy jedzie razem z resztą tylko wtedy, gdy jego LEWY GÓRNY RÓG
        wpadł do przenoszonego prostokąta - strefa większa od niego zostaje w miejscu,
        a to, co ją wypełniało, już nie. Ta sama klasa błędu wychodzi po zmianie
        `size` w briefie: `plains` z mapy 256x256 wylądował na 256x128 w pasie lasu.
        Gra nie mrugnie okiem, bo `load_zones` bierze cztery liczby i tyle.

        Mierzymy więc to, co z tego wynika: udział kafli, po których w ogóle da się
        chodzić. Ten sam próg co w `lint_map.check_zone_placement`.
        """
        try:
            zones = self.tmap.object_group("zones").objects
        except KeyError:
            return
        walls = self.tmap.tile_layer("walls")
        tw, th = self.tmap.tilewidth, self.tmap.tileheight
        for obj in zones:
            if not (obj.width and obj.height):
                continue                 # wielokąt - to już błąd sam w sobie, mówi o nim linter
            x0, y0 = self.tmap.tile_of(obj.x, obj.y)
            x1, y1 = x0 + max(1, int(obj.width) // tw), y0 + max(1, int(obj.height) // th)
            inside = [(x, y) for y in range(y0, y1) for x in range(x0, x1)
                      if self.tmap.in_bounds(x, y)]
            if not inside:
                self.rows.append(Row(WARN, "zones", obj.name,
                                     "strefa leży poza mapą - w grze ma zerową powierzchnię",
                                     (x0, y0)))
                continue
            share = sum(1 for x, y in inside if not walls.get(x, y)) / len(inside)
            if share < ZONE_WALKABLE_MIN:
                self.rows.append(Row(
                    WARN, "zones", obj.name,
                    f"po tej operacji tylko {share:.0%} kafli strefy jest chodliwych - "
                    f"strefy nie jadą razem z terenem, przesuń ją osobno", (x0, y0)))

    def _warn_orphaned_entries(self, rect: tuple[int, int, int, int],
                               by: tuple[int, int]) -> None:
        """Wyjście i stojący przed nim punkt wejścia to para.

        Przeniesienie prostokąta, który obejmuje drzwi, ale nie kafel przed nimi,
        rozrywa tę parę po cichu: gracz wraca z wnętrza i ląduje tam, gdzie domu
        już nie ma. Prostokąta nie poprawiamy za autora - to jego decyzja - ale
        milczeć o tym nie wolno.
        """
        tile = self.tmap.tilewidth
        try:
            exits = [o for o in self.tmap.object_group("interactions").objects
                     if o.props.get("obj_type", "") == "exit"]
            entries = self.tmap.object_group("entry_points").objects
        except KeyError:
            return
        for obj in exits:
            if not self._in_rect((obj.anchor[0] - by[0] * tile,
                                  obj.anchor[1] - by[1] * tile), rect):
                continue          # to wyjście nie brało udziału w przeprowadzce
            here = self.tmap.tile_of(*obj.center)
            for entry in entries:
                ex, ey = self.tmap.tile_of(*entry.midbottom) if (entry.width or entry.height) \
                    else self.tmap.tile_of(entry.x, entry.y)
                old_x = here[0] - by[0]
                old_y = here[1] - by[1]
                near_old = max(abs(ex - old_x), abs(ey - old_y)) <= 2
                near_new = max(abs(ex - here[0]), abs(ey - here[1])) <= 2
                if near_old and not near_new:
                    self.rows.append(Row(
                        WARN, "entry_points", entry.name,
                        f"stał przy wyjściu `{obj.name}`, które właśnie odjechało - "
                        f"gracz wracający z `{obj.props.get('to_map', '?')}` wyląduje "
                        f"tam, gdzie domu już nie ma. Rozszerz prostokąt albo przesuń "
                        f"ten punkt osobno", (ex, ey)))

    def _move_tiles(self, rect: tuple[int, int, int, int], by: tuple[int, int]) -> None:
        rx, ry, rw, rh = rect
        dx, dy = by
        for name in TILE_LAYERS:
            layer = self.tmap.tile_layer(name)
            cut = [[layer.get(rx + x, ry + y) for x in range(rw)] for y in range(rh)]
            for y in range(rh):
                for x in range(rw):
                    layer.set(rx + x, ry + y, EMPTY)
            for y in range(rh):
                for x in range(rw):
                    if cut[y][x]:
                        layer.set(rx + dx + x, ry + dy + y, cut[y][x])

    def _in_rect(self, point: tuple[float, float], rect: tuple[int, int, int, int]) -> bool:
        rx, ry, rw, rh = rect
        tile = self.tmap.tilewidth
        return (rx * tile <= point[0] < (rx + rw) * tile
                and ry * tile <= point[1] < (ry + rh) * tile)

    def _move_objects(self, rect: tuple[int, int, int, int], by: tuple[int, int]) -> None:
        tile = self.tmap.tilewidth
        px, py = by[0] * tile, by[1] * tile
        for group in self.tmap.object_groups():
            for obj in group.objects:
                # kotwica, nie x/y: obiekt z gidem trzyma `y` na dolnej krawędzi
                if self._in_rect(obj.anchor, rect):
                    obj.translate(px, py)
                    self.rows.append(Row(INFO, group.name, obj.name or f"id={obj.id}",
                                         f"przesunięty razem z kaflami o ({by[0]},{by[1]})"))

    def _relocate_blocking_objects(self, dest: tuple[int, int, int, int],
                                   source: tuple[int, int, int, int]) -> None:
        """Interaktywne obiekty stojące w miejscu docelowym idą w bok, nie do kosza."""
        for name in INTERACTIVE_LAYERS:
            try:
                group = self.tmap.object_group(name)
            except KeyError:
                continue
            for obj in group.objects:
                if not self._in_rect(obj.anchor, dest) or self._in_rect(obj.anchor, source):
                    continue
                spot = self._free_spot_near(obj, dest)
                if spot is None:
                    self.rows.append(Row(
                        ERROR, name, obj.name or f"id={obj.id}",
                        "stoi w miejscu docelowym, a nie znalazłem dla niego wolnego "
                        "kafla obok - przestaw go ręcznie"))
                    continue
                tile = self.tmap.tilewidth
                obj.translate(spot[0] * tile - obj.anchor[0], spot[1] * tile - obj.anchor[1])
                self.rows.append(Row(
                    WARN, name, obj.name or f"id={obj.id}",
                    f"stał w miejscu docelowym - przestawiony na kafel {spot}",
                    spot))

    def _free_spot_near(self, obj: MapObject, dest: tuple[int, int, int, int]
                        ) -> tuple[int, int] | None:
        """Najbliższy chodliwy kafel poza prostokątem docelowym, szukany pierścieniami."""
        walls = self.tmap.tile_layer("walls")
        ox, oy = self.tmap.tile_of(*obj.anchor)
        for radius in range(1, 24):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    x, y = ox + dx, oy + dy
                    if not self.tmap.in_bounds(x, y) or walls.get(x, y):
                        continue
                    if (dest[0] <= x < dest[0] + dest[2]
                            and dest[1] <= y < dest[1] + dest[3]):
                        continue
                    return (x, y)
        return None

    def _backfill(self, source: tuple[int, int, int, int],
                  dest: tuple[int, int, int, int]) -> None:
        """Zasyp dziurę po źródle kaflami z pierścienia wokół niej."""
        ground = self.tmap.tile_layer("ground")
        sample = ring_sample(ground, source, self.rng)
        if not sample:
            return
        rx, ry, rw, rh = source
        filled = 0
        for y in range(ry, ry + rh):
            for x in range(rx, rx + rw):
                if not self.tmap.in_bounds(x, y):
                    continue
                if (dest[0] <= x < dest[0] + dest[2] and dest[1] <= y < dest[1] + dest[3]):
                    continue          # ten kafel zajął przeniesiony klocek
                ground.set(x, y, self.rng.choice(sample))
                filled += 1
        if filled:
            self.rows.append(Row(INFO, "backfill", "",
                                 f"{filled} kafli zasypanych próbką z otoczenia"))

    # ------------------------------------------------------------------
    # MARK: pozostałe operacje

    def stamp(self, palette: Palette, name: str, at: tuple[int, int]) -> None:
        stamp = palette.get(name)
        palette.paste(self.tmap, name, at)
        self._warn_stale_zones()
        self.rows.append(Row(OK, "stamp", name,
                             f"{stamp.w}x{stamp.h} postawiony w {at}"
                             f"{f', drzwi na {stamp.door}' if stamp.door else ''}", at))

    def erase(self, rect: tuple[int, int, int, int]) -> None:
        rx, ry, rw, rh = rect
        for name in TILE_LAYERS:
            layer = self.tmap.tile_layer(name)
            for y in range(ry, ry + rh):
                for x in range(rx, rx + rw):
                    layer.set(x, y, EMPTY)
        self._backfill(rect, (0, 0, 0, 0))
        self._warn_stale_zones()
        self.rows.append(Row(OK, "erase", "", f"wyczyszczono {rw}x{rh} kafli w ({rx},{ry})"))

    def revar(self, rect: tuple[int, int, int, int], terrain_name: str) -> None:
        """Przelosuj warianty terenu w obszarze - lek na monotonię bez ruszania kompozycji."""
        rx, ry, rw, rh = rect
        terrain = self.terrain.get(terrain_name)
        known = set(terrain.variants)
        ground = self.tmap.tile_layer("ground")
        changed = 0
        for y in range(ry, ry + rh):
            for x in range(rx, rx + rw):
                if not self.tmap.in_bounds(x, y) or ground.get(x, y) not in known:
                    continue     # nie ruszamy kafli spoza tego terenu (ścieżki, przejścia)
                ground.set(x, y, terrain.pick(self.rng))
                changed += 1
        self.rows.append(Row(OK, "revar", terrain_name,
                             f"{changed} kafli przelosowanych spośród "
                             f"{len(terrain.variants)} wariantów"))


# --------------------------------------------------------------------------
# MARK: CLI


def _rect(value: str) -> tuple[int, int, int, int]:
    parts = [int(p) for p in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("oczekuję X,Y,W,H w kaflach")
    return (parts[0], parts[1], parts[2], parts[3])


def _pair(value: str) -> tuple[int, int]:
    parts = [int(p) for p in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("oczekuję dwóch liczb: X,Y")
    return (parts[0], parts[1])


def main(argv: list[str] | None = None) -> int:
    # Wspólne flagi w parserze nadrzędnym, żeby działały PO podkomendzie
    # (`map-edit MAPA move --rect ... --dry-run`), bo tak się je pisze odruchowo.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--seed", type=int, default=0)
    common.add_argument("--dry-run", action="store_true", help="pokaż, nie zapisuj")
    common.add_argument("--no-lint", action="store_true", help="pomiń lint po zmianie")

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], parents=[common])
    parser.add_argument("map", help="nazwa mapy albo ścieżka do .tmx")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_move = sub.add_parser("move", parents=[common],
                            help="przenieś obszar ze wszystkimi warstwami")
    p_move.add_argument("--rect", type=_rect, required=True)
    p_move.add_argument("--by", type=_pair, required=True)

    p_stamp = sub.add_parser("stamp", parents=[common], help="postaw klocek z katalogu")
    p_stamp.add_argument("--name", required=True)
    p_stamp.add_argument("--at", type=_pair, required=True)

    p_erase = sub.add_parser("erase", parents=[common],
                             help="wyczyść obszar i zasyp terenem z otoczenia")
    p_erase.add_argument("--rect", type=_rect, required=True)

    p_revar = sub.add_parser("revar", parents=[common],
                             help="przelosuj warianty terenu w obszarze")
    p_revar.add_argument("--rect", type=_rect, required=True)
    p_revar.add_argument("--terrain", default="grass")

    args = parser.parse_args(argv)
    path = resolve_map(args.map)
    editor = Editor(path, args.seed)

    if args.cmd == "move":
        editor.move(args.rect, args.by)
    elif args.cmd == "stamp":
        editor.stamp(Palette.load(), args.name, args.at)
    elif args.cmd == "erase":
        editor.erase(args.rect)
    elif args.cmd == "revar":
        editor.revar(args.rect, args.terrain)

    if not args.dry_run:
        editor.save()
    report(editor.rows, title=f"{args.cmd} - {path.name}"
                              f"{'  (na sucho, nic nie zapisano)' if args.dry_run else ''}")

    if args.dry_run or args.no_lint:
        return 0
    # Każda operacja kończy się lintem: przesunięcie, które odcięło dojście do
    # stodoły, ma wyjść teraz, a nie przy najbliższym uruchomieniu gry.
    from lint_map import main as lint_main

    print()
    return lint_main([str(path)])


if __name__ == "__main__":
    sys.exit(main())
