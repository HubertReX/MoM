#!/usr/bin/env python3
"""Testy narzędzi mapowych (`scripts/mapgen/`) - skill `tiled-map`.

Trzy rzeczy, które muszą trzymać, bo ich złamanie jest ciche:

1. **Round-trip .tmx** - wczytanie i zapis nie mogą zgubić ani przestawić niczego,
   co niesie znaczenie. Kolejność warstw jest kontraktem gry (`load_step_cost`
   czyta warstwy po indeksie 0 i 1), więc jej utrata psuje koszty chodzenia.
2. **Kotwiczenie obiektów z gidem** - w pliku `y` jest na DOLNEJ krawędzi,
   a pytmx normalizuje to do górnej. Pomyłka o jeden kafel sprawia, że ryby
   i koty "stoją w ścianie", a linter zgłasza fałszywki.
3. **Kanoniczna tablica tilesetów** - to na niej stoi cała biblioteka klocków:
   ten sam gid ma znaczyć ten sam kafel w prototypie i w mapie gry.

Uruchamianie z katalogu repo:
    .venv/bin/python tests/test_mapgen.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts" / "mapgen"))

from tmx import (  # noqa: E402
    OBJECT_LAYERS,
    OUTDOOR_TILESETS,
    TILE_LAYERS,
    MapObject,
    ObjectGroup,
    TiledMap,
    TileLayer,
    bare_gid,
    gid_flags,
    new_outdoor_map,
)

MAPS = REPO / "project" / "assets" / "NinjaAdventure" / "maps"
GAME_MAPS = [MAPS / "BLUNDERHAVEN.tmx", MAPS / "LOST_CORK_TAVERN.tmx",
             MAPS / "JACOBS_CHAMBER.tmx", MAPS / "_wip" / "BLUNDERHAVEN_base.tmx"]


def assert_true(cond: object, msg: str) -> None:
    assert cond, msg


def assert_eq(got: object, want: object, msg: str) -> None:
    assert got == want, f"{msg}: jest {got!r}, ma być {want!r}"


def _snapshot(tmap: TiledMap) -> object:
    """Wszystko, co niesie znaczenie - formatowanie pomijamy świadomie."""
    layers: list[object] = []
    for layer in tmap.layers:
        if isinstance(layer, TileLayer):
            layers.append(("tile", layer.id, layer.name, layer.width, layer.height,
                           layer.opacity, layer.visible, dict(layer.props.items), layer.data))
        else:
            layers.append(("obj", layer.id, layer.name, layer.visible, layer.opacity,
                           dict(layer.props.items),
                           [(o.id, o.name, o.type, o.x, o.y, o.width, o.height, o.gid,
                             o.rotation, o.visible, o.shape, o.points, dict(o.props.items))
                            for o in layer.objects]))
    return (tmap.width, tmap.height, tmap.tilewidth, tmap.tileheight, tmap.orientation,
            tmap.renderorder, tmap.infinite, tmap.nextlayerid, tmap.nextobjectid,
            dict(tmap.props.items), [(t.firstgid, t.source) for t in tmap.tilesets], layers)


# --------------------------------------------------------------------------


def test_round_trip_keeps_everything() -> None:
    for path in GAME_MAPS:
        before = TiledMap.load(path)
        with tempfile.NamedTemporaryFile("w", suffix=".tmx", delete=False) as fh:
            tmp = Path(fh.name)
        try:
            # zapis do tego samego katalogu, żeby nie zadziałało przeliczanie tilesetów
            same_dir = path.parent / f"__rt_{path.name}"
            before.save(same_dir)
            after = TiledMap.load(same_dir)
            assert_eq(_snapshot(after), _snapshot(before), f"round-trip {path.name}")
        finally:
            (path.parent / f"__rt_{path.name}").unlink(missing_ok=True)
            tmp.unlink(missing_ok=True)


def test_layer_order_is_preserved() -> None:
    tmap = TiledMap.load(MAPS / "BLUNDERHAVEN.tmx")
    names = tmap.layer_names()
    assert_eq(names, list(TILE_LAYERS) + list(OBJECT_LAYERS),
              "BLUNDERHAVEN ma mieć kanoniczną kolejność warstw")
    assert_eq(names.index("sprites"), 4, "`sprites` musi być piątą warstwą (indeks 4)")
    assert_eq(names[:2], ["ground", "foliage"],
              "`load_step_cost` czyta warstwy 0 i 1, więc muszą to być ground i foliage")


def test_gid_object_anchors_like_pytmx() -> None:
    """Obiekt z gidem: `y` w pliku to dolna krawędź, pytmx podaje grze górną."""
    obj = MapObject(gid=2824, x=728.0, y=996.8, width=16.0, height=16.0)
    assert_eq(obj.top, 980.8, "górna krawędź = y - height")
    assert_eq(obj.midbottom, (736.0, 996.8), "midbottom wraca do wartości z pliku")
    assert_eq(obj.anchor, (728.0, 980.8), "kotwica to lewy górny róg")

    plain = MapObject(x=680.0, y=752.0, width=16.0, height=16.0)
    assert_eq(plain.top, 752.0, "bez gidu `y` jest już górną krawędzią")
    assert_eq(plain.midbottom, (688.0, 768.0), "midbottom bez gidu to y + height")


def test_gid_flags_are_split_off() -> None:
    flipped = 0x80000000 | 1234
    assert_eq(bare_gid(flipped), 1234, "numer kafla bez flag")
    assert_eq(gid_flags(flipped), 0x80000000, "same flagi obrotu")
    assert_eq(bare_gid(0), 0, "pusty kafel zostaje pusty")


def test_new_outdoor_map_matches_the_contract() -> None:
    tmap = new_outdoor_map(MAPS / "_wip" / "__probe.tmx", 24, 16)
    assert_eq(tmap.layer_names(), list(TILE_LAYERS) + list(OBJECT_LAYERS),
              "nowa mapa ma komplet warstw w wiążącej kolejności")
    assert_eq([(t.firstgid, t.key) for t in tmap.tilesets], list(OUTDOOR_TILESETS),
              "nowa mapa ma kanoniczną tablicę tilesetów")
    assert_true(tmap.props.as_bool("outdoor"), "mapa zewnętrzna ma własność outdoor")
    assert_eq(tmap.tile_layer("over").opacity, 0.99, "warstwa over jest półprzezroczysta")
    for name in TILE_LAYERS:
        layer = tmap.tile_layer(name)
        assert_eq((layer.width, layer.height), (24, 16), f"rozmiar warstwy {name}")
        assert_true(layer.is_empty(), f"świeża warstwa {name} ma być pusta")


def test_game_maps_share_the_canonical_tileset_table() -> None:
    """Na tym stoi stemplowanie: gid z prototypu ma znaczyć to samo w mapie gry."""
    for path in (MAPS / "BLUNDERHAVEN.tmx", MAPS / "_wip" / "BLUNDERHAVEN_base.tmx"):
        tmap = TiledMap.load(path)
        assert_eq([(t.firstgid, t.key) for t in tmap.tilesets], list(OUTDOOR_TILESETS),
                  f"{path.name} ma kanoniczną tablicę tilesetów")


def test_saving_elsewhere_rebases_tilesets() -> None:
    """Kopiowanie mapy do innego katalogu musi przeliczyć ścieżki .tsx."""
    tmap = TiledMap.load(MAPS / "BLUNDERHAVEN.tmx")
    target = MAPS / "_wip" / "__rebase.tmx"
    try:
        tmap.save(target)
        for ref in tmap.tilesets:
            resolved = (target.parent / ref.source).resolve()
            assert_true(resolved.exists(), f"tileset {ref.source} ma istnieć z {target.parent}")
        assert_true(any(r.source.startswith("../") for r in tmap.tilesets),
                    "z _wip/ ścieżki muszą wyjść katalog wyżej")
    finally:
        target.unlink(missing_ok=True)


def test_stamp_palette_cuts_all_tile_layers() -> None:
    from palette import Palette

    palette = Palette.load()
    assert_true(palette.stamps, "prototyp ma mieć niepusty katalog klocków")
    tavern = palette.get("tavern_tall")
    assert_eq((tavern.w, tavern.h), (4, 5), "rozmiar klocka tavern_tall")
    assert_true(tavern.blocking(), "budynek musi blokować chodzenie")
    assert_true(any(gid for row in tavern.gids("over") for gid in row),
                "budynek niesie dach na warstwie `over`")
    for stamp in palette.of_kind("building"):
        if stamp.door is None:
            continue
        dx, dy = stamp.door
        assert_true(0 <= dx < stamp.w and 0 <= dy < stamp.h,
                    f"drzwi klocka {stamp.name} leżą poza jego obrysem")
        assert_true(stamp.gids("walls")[dy][dx],
                    f"kafel drzwi klocka {stamp.name} musi być na warstwie `walls`")


def test_terrain_comes_from_the_wangset() -> None:
    from tileset import Tileset
    from terrain import TerrainLib

    lib = TerrainLib(Tileset.load(MAPS / "tilesets" / "Floor.tsx"), 477)
    assert_true("grass" in lib.terrains and "dirt" in lib.terrains,
                "wangset Floor.tsx ma dawać tereny grass i dirt")
    assert_eq(len(lib.get("grass").variants), 7, "wariantów czystej trawy")
    assert_eq(len(lib.get("dirt").variants), 3, "wariantów czystej ziemi")


def test_blob_mask_hits_requested_coverage() -> None:
    import random

    from terrain import blob_mask

    mask = blob_mask(64, 64, random.Random(1), coverage=0.35, scale=14)
    got = sum(sum(row) for row in mask) / (64 * 64)
    assert_true(0.25 <= got <= 0.50, f"pokrycie plamy {got:.0%} poza widełkami dla 35%")
    # kształt ma być nieregularny: żaden pełny wiersz ani żaden pusty na przemian
    rows_full = sum(1 for row in mask if all(row))
    assert_true(rows_full < 32, "plama nie może być prostokątem")


def test_linter_finds_polygon_zones() -> None:
    """Regresja na znanej usterce: strefy-wielokąty mają w grze zerową powierzchnię."""
    from lint_map import lint
    from report import ERROR

    rows = lint(MAPS / "BLUNDERHAVEN.tmx")
    zone_errors = [r for r in rows if r.source == "zones" and r.level == ERROR]
    assert_true(zone_errors, "linter ma zgłosić strefy-wielokąty na BLUNDERHAVEN")
    assert_true(all("prostokątem" in r.message for r in zone_errors),
                "komunikat ma mówić, o co chodzi")


def test_linter_is_quiet_about_layer_contract() -> None:
    from lint_map import lint
    from report import ERROR

    rows = lint(MAPS / "BLUNDERHAVEN.tmx")
    for source in ("warstwy", "tilesety"):
        bad = [r for r in rows if r.source == source and r.level == ERROR]
        assert_true(not bad, f"BLUNDERHAVEN nie łamie kontraktu '{source}': {bad}")


def main() -> None:
    tests = [
        ("round-trip .tmx nic nie gubi", test_round_trip_keeps_everything),
        ("kolejność warstw zachowana", test_layer_order_is_preserved),
        ("kotwiczenie obiektów z gidem", test_gid_object_anchors_like_pytmx),
        ("flagi obrotu w gidzie", test_gid_flags_are_split_off),
        ("nowa mapa spełnia kontrakt", test_new_outdoor_map_matches_the_contract),
        ("mapy dzielą tablicę tilesetów", test_game_maps_share_the_canonical_tileset_table),
        ("zapis gdzie indziej przelicza .tsx", test_saving_elsewhere_rebases_tilesets),
        ("katalog tnie wszystkie warstwy", test_stamp_palette_cuts_all_tile_layers),
        ("tereny z wangsetu", test_terrain_comes_from_the_wangset),
        ("plama trafia w zadane pokrycie", test_blob_mask_hits_requested_coverage),
        ("linter łapie strefy-wielokąty", test_linter_finds_polygon_zones),
        ("linter nie zmyśla o kontrakcie", test_linter_is_quiet_about_layer_contract),
    ]
    failures = 0
    for name, func in tests:
        try:
            func()
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            import traceback

            traceback.print_exc()
            failures += 1

    print(f"\n{'─' * 40}")
    total = len(tests)
    passed = total - failures
    if failures:
        print(f"  FAILED  {failures}/{total} tests")
        sys.exit(1)
    else:
        print(f"  PASSED  {passed}/{total} tests")


if __name__ == "__main__":
    main()
