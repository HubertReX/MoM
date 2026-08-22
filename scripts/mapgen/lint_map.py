#!/usr/bin/env python3
"""Linter map .tmx - łapie to, co da się policzyć, żeby oczy oglądały resztę.

Wzorowany na `scripts/validate_world.py`: TYLKO DIAGNOZUJE, nigdy nie edytuje
źródła, nie importuje pygame'a (surowy XML/JSON/CSV) i chodzi na gołym
interpreterze. Dzieli się na trzy rodziny sprawdzeń:

* **kontrakt** - komplet i kolejność warstw, kanoniczna tablica tilesetów,
  przedmioty z `config.items`. Złamanie = mapa nie zadziała w grze.
* **logika** - dostępność liczona tym samym flood fillem, co widzi gracz;
  wyjścia na kaflach drzwi; strefy, spawny, waypointy. Tu mieszka pytanie
  "czy da się dojść do stodoły".
* **wygląd** - monotonia i szablonowość jako LICZBY: udział dominującego
  wariantu w oknie, najdłuższy ciąg jednego kafla, wyrównanie budynków,
  połacie bez detalu. Metryka nie zastępuje oka, ale mówi mu, gdzie patrzeć,
  a to jedyne, co czyni oglądanie mapy 256x256 opłacalnym.

Kafle zniszczalne (`destructible=true`) są liczone osobno: skrzynia zamknięta
krzakami jest projektem, a nie błędem (Q04_S01 "Ryby, które zjadł kot"), więc
dostajemy o niej INFO, a nie ERROR - ale skrzynia zamknięta ŚCIANĄ to już błąd.

Użycie:

    just map-lint BLUNDERHAVEN
    just map-lint BLUNDERHAVEN --json
    just map-lint BLUNDERHAVEN --strict     # ostrzeżenia też failują
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from report import ERROR, INFO, OK, WARN, Row, counts, report, sort_rows
from tileset import TilesetTable
from tmx import (
    OBJECT_LAYERS,
    OUTDOOR_TILESETS,
    OVER_LAYER_OPACITY,
    TILE_LAYERS,
    MapObject,
    TiledMap,
    maps_dir,
)

REPO = Path(__file__).resolve().parent.parent.parent
CONFIG_JSON = REPO / "project" / "config_model" / "config.json"
AUDIO_TOML = REPO / "project" / "config_model" / "audio.toml"
LOCALE_DIR = REPO / "project" / "assets" / "locale"
CHARACTERS_CSV = REPO / "project" / "config_model" / "characters.csv"

# ---- progi metryk wyglądu (do strojenia w jednym miejscu) ----
WINDOW = 16                 # bok okna, w kaflach
MONOTONY_SHARE = 0.92       # udział dominującego wariantu, powyżej którego okno jest monotonne
MONOTONY_DISTINCT = 3       # ...o ile wariantów w oknie jest mniej niż tyle
MAX_RUN = 24                # najdłuższy ciąg jednego gidu w wierszu/kolumnie
ALIGNED_BUILDINGS = 4       # tyle budynków w jednej linii to już szablon
ALIGN_WINDOW = 40           # ...o ile stoją w tym oknie kafli (wyrównanie jest lokalne)
EMPTY_PATCH = 16            # bok kwadratu bez detalu, od którego zgłaszamy pustkę
# Udział kafli chodliwych w strefie: poniżej `MIN` strefa nie nadaje się do niczego,
# poniżej `WARN` jest ciasna. Zmierzone na pierwszej mapie z generatora: podwórka
# mieszczą się w 71-100%, a `plains`, który po zmniejszeniu mapy trafił w las - 49%.
ZONE_WALKABLE_MIN = 0.60
ZONE_WALKABLE_WARN = 0.70

# `<KLUCZ_MODELU>` albo `<KLUCZ_MODELU>_<NN>` - konwencja nazwy instancji z D1/D2
_INSTANCE_SUFFIX = re.compile(r"_\d+")


# --------------------------------------------------------------------------
# MARK: dane świata


@dataclass
class World:
    items: set[str] = field(default_factory=set)
    chests: set[str] = field(default_factory=set)
    characters: set[str] = field(default_factory=set)
    zones_used: set[str] = field(default_factory=set)
    places_used: dict[str, set[str]] = field(default_factory=dict)  # mapa -> miejsca


def load_world() -> World:
    world = World()
    if CONFIG_JSON.exists():
        conf = json.loads(CONFIG_JSON.read_text(encoding="utf-8"))
        world.items = set(conf.get("items", {}))
        world.chests = set(conf.get("chests", {}))
    if CHARACTERS_CSV.exists():
        with CHARACTERS_CSV.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter=";"):
                key = (row.get("key") or "").strip()
                if key:
                    world.characters.add(key)
                for zone in (row.get("allowed_zones") or "").split(","):
                    if zone.strip():
                        world.zones_used.add(zone.strip())
                for column in ("home", "work", "social", "hobby"):
                    value = (row.get(column) or "").strip()
                    if ":" in value:
                        map_key, _, place = value.partition(":")
                        world.places_used.setdefault(map_key, set()).add(place)
    return world


# --------------------------------------------------------------------------
# MARK: kontekst mapy


@dataclass
class Ctx:
    path: Path
    tmap: TiledMap
    table: TilesetTable
    world: World
    door_gids: set[int] = field(default_factory=set)
    # chodliwość: `hard` = tak jak dziś, `soft` = po zniszczeniu krzaków
    hard: list[list[bool]] = field(default_factory=list)
    soft: list[list[bool]] = field(default_factory=list)
    reach_hard: list[list[bool]] = field(default_factory=list)
    reach_soft: list[list[bool]] = field(default_factory=list)

    @property
    def w(self) -> int:
        return self.tmap.width

    @property
    def h(self) -> int:
        return self.tmap.height

    def objects(self, layer: str) -> list[MapObject]:
        try:
            return self.tmap.object_group(layer).objects
        except KeyError:
            return []

    def tile_of(self, obj: MapObject) -> tuple[int, int]:
        """Kafel, na którym stoi obiekt (jego środek)."""
        px, py = obj.center if (obj.width or obj.height) else (obj.x, obj.y)
        return self.tmap.tile_of(px, py)

    def anchor_tile(self, obj: MapObject) -> tuple[int, int]:
        """Kafel `rect.midbottom` - dokładnie tak gra czyta `places`, `entry_points`
        i spawny (`MapObject.midbottom` uwzględnia kotwiczenie obiektów z gidem)."""
        px, py = obj.midbottom if (obj.width or obj.height) else (obj.x, obj.y)
        return self.tmap.tile_of(px, py)

    def stand_tile(self, obj: MapObject) -> tuple[int, int]:
        """Kafel, na którym stoją STOPY postaci - a to o kafel wyżej niż `anchor_tile`.

        `npc.feet` ma wysokość pół kafla i `midbottom` w pozycji spawnu, więc przy
        `midbottom` dokładnie na granicy kafli stopy leżą w kaflu NAD nią. Różnica
        jednego kafla brzmi jak pedanteria, dopóki tym kaflem nie jest sztacheta
        płotu: NPC nie ma siatki bezpieczeństwa i zostaje w niej na zawsze.
        """
        px, py = obj.midbottom if (obj.width or obj.height) else (obj.x, obj.y)
        return self.tmap.tile_of(px, py - 1)


def build_ctx(path: Path, world: World, palette_path: Path | None = None) -> Ctx:
    tmap = TiledMap.load(path)
    ctx = Ctx(path=path, tmap=tmap, table=TilesetTable(tmap.tilesets, path), world=world)
    ctx.door_gids = _door_gids(palette_path)
    _build_walkability(ctx)
    return ctx


def _door_gids(palette_path: Path | None) -> set[int]:
    """Kafle drzwi wyprowadzone z KATALOGU KLOCKÓW, nie z listy w kodzie.

    Dzięki temu dopisanie budynku do prototypu automatycznie uczy linter jego
    drzwi, a nierozpoznany kafel jest sygnałem "dodaj ten budynek do katalogu",
    a nie fałszywką do wyciszenia.
    """
    try:
        from palette import Palette

        palette = Palette.load(palette_path)
    except SystemExit:
        return set()
    gids: set[int] = set()
    for stamp in palette.stamps.values():
        if stamp.door:
            dx, dy = stamp.door
            gid = stamp.gids("walls")[dy][dx]
            if gid:
                gids.add(gid)
    return gids


def _build_walkability(ctx: Ctx) -> None:
    walls = ctx.tmap.tile_layer("walls")
    ctx.hard = [[walls.data[y][x] == 0 for x in range(ctx.w)] for y in range(ctx.h)]
    ctx.soft = [
        [
            walls.data[y][x] == 0
            or ctx.table.props_for(walls.data[y][x]).as_bool("destructible", False)
            for x in range(ctx.w)
        ]
        for y in range(ctx.h)
    ]
    starts = _entry_tiles(ctx)
    ctx.reach_hard = _flood(ctx, ctx.hard, starts)
    ctx.reach_soft = _flood(ctx, ctx.soft, starts)


def _entry_tiles(ctx: Ctx) -> list[tuple[int, int]]:
    return [ctx.anchor_tile(obj) for obj in ctx.objects("entry_points")]


def _flood(ctx: Ctx, walk: list[list[bool]],
           starts: list[tuple[int, int]]) -> list[list[bool]]:
    seen = [[False] * ctx.w for _ in range(ctx.h)]
    queue: deque[tuple[int, int]] = deque()
    for sx, sy in starts:
        if 0 <= sx < ctx.w and 0 <= sy < ctx.h and walk[sy][sx] and not seen[sy][sx]:
            seen[sy][sx] = True
            queue.append((sx, sy))
    while queue:
        x, y = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < ctx.w and 0 <= ny < ctx.h and walk[ny][nx] and not seen[ny][nx]:
                seen[ny][nx] = True
                queue.append((nx, ny))
    return seen


# --------------------------------------------------------------------------
# MARK: sprawdzenia kontraktu


def check_layers(ctx: Ctx) -> list[Row]:
    names = ctx.tmap.layer_names()
    expected = list(TILE_LAYERS) + list(OBJECT_LAYERS)
    # warstwy pomocnicze (np. `stamps` w prototypie) wolno mieć NA KOŃCU
    core = [n for n in names if n in expected]
    if core == expected:
        extra = [n for n in names if n not in expected]
        if extra and names[:len(expected)] != expected:
            return [Row(WARN, "warstwy", "", f"warstwy spoza kontraktu nie stoją na końcu: "
                                             f"{', '.join(extra)}")]
        return [Row(OK, "warstwy", "", f"komplet {len(expected)} warstw w wiążącej kolejności")]

    rows = []
    missing = [n for n in expected if n not in names]
    if missing:
        rows.append(Row(ERROR, "warstwy", "", f"brak warstw: {', '.join(missing)}"))
    if core and core != expected and not missing:
        rows.append(Row(
            ERROR, "warstwy", "",
            f"zła kolejność - jest [{', '.join(core)}], ma być [{', '.join(expected)}]. "
            f"`load_step_cost` czyta warstwy po indeksie 0 i 1, a `sprites_layer` to "
            f"`layers.index('sprites')`, więc kolejność zmienia zachowanie gry",
        ))
    return rows


def check_tilesets(ctx: Ctx) -> list[Row]:
    if not ctx.tmap.props.as_bool("outdoor", False):
        return []
    have = [(ref.firstgid, ref.key) for ref in ctx.tmap.tilesets]
    want = list(OUTDOOR_TILESETS)
    if have == want:
        return [Row(OK, "tilesety", "", "kanoniczna tablica map zewnętrznych")]
    return [Row(
        ERROR, "tilesety", "",
        f"tablica różni się od kanonicznej, więc te same gidy znaczą co innego niż "
        f"w katalogu klocków.\n  jest: {have}\n  ma być: {want}",
    )]


def check_sprites_layer(ctx: Ctx) -> list[Row]:
    layer = ctx.tmap.tile_layer("sprites")
    if layer.is_empty():
        return []
    return [Row(WARN, "sprites", "", f"warstwa ma {layer.count_non_empty()} kafli, "
                                     f"a jest przeznaczona wyłącznie na sprite'y rysowane w grze")]


def check_over_opacity(ctx: Ctx) -> list[Row]:
    layer = ctx.tmap.tile_layer("over")
    if layer.opacity is None or abs(layer.opacity - OVER_LAYER_OPACITY) > 0.001:
        return [Row(WARN, "over", "", f"opacity={layer.opacity}, w pozostałych mapach "
                                      f"{OVER_LAYER_OPACITY}")]
    return []


def check_items_layer(ctx: Ctx) -> list[Row]:
    layer = ctx.tmap.tile_layer("items")
    rows: list[Row] = []
    for y in range(ctx.h):
        for x in range(ctx.w):
            gid = layer.data[y][x]
            if not gid:
                continue
            props = ctx.table.props_for(gid)
            name = props.get("item_name", "")
            if "item_name" not in props:
                rows.append(Row(ERROR, "items", f"gid {gid}",
                                "kafel bez własności `item_name` - `load_items` czyta ją "
                                "bezwarunkowo (`tile_properties[gid]['item_name']`)", (x, y)))
            elif not name:
                rows.append(Row(ERROR, "items", f"gid {gid}",
                                "puste `item_name` - `create_item` poszuka wtedy przedmiotu "
                                "o pustej nazwie w `items_sheet` i `config.items`, i wywali "
                                "się na KeyError", (x, y)))
            elif ctx.world.items and name not in ctx.world.items:
                rows.append(Row(ERROR, "items", name,
                                "przedmiot nie istnieje w `config.items`", (x, y)))
    return rows


# --------------------------------------------------------------------------
# MARK: sprawdzenia logiki


def check_start(ctx: Ctx) -> list[Row]:
    entries = {obj.name: obj for obj in ctx.objects("entry_points")}
    if "start" not in entries:
        return [Row(ERROR, "entry_points", "start",
                    "brak punktu `start` - `set_entry_point` użyje środka mapy, "
                    "co na dużej mapie oznacza start w środku lasu")]
    x, y = ctx.anchor_tile(entries["start"])
    if not (0 <= x < ctx.w and 0 <= y < ctx.h):
        return [Row(ERROR, "entry_points", "start", "punkt poza mapą", (x, y))]
    if not ctx.hard[y][x]:
        return [Row(ERROR, "entry_points", "start", "gracz startuje w ścianie", (x, y))]
    return []


def _has_reachable_neighbour(ctx: Ctx, x: int, y: int) -> bool:
    return any(
        0 <= x + dx < ctx.w and 0 <= y + dy < ctx.h and ctx.reach_hard[y + dy][x + dx]
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0))
    )


def _reach_row(ctx: Ctx, layer: str, name: str, x: int, y: int,
               wall_is_fatal: bool = True) -> Row | None:
    if not (0 <= x < ctx.w and 0 <= y < ctx.h):
        return Row(ERROR, layer, name, "poza granicami mapy", (x, y))
    if not ctx.soft[y][x]:
        # Miejsce postawione na kaflu drzwi to sensowny zapis "idź pod ten dom",
        # więc dopóki da się do niego podejść, jest to uwaga, a nie błąd. NPC
        # spawnujący się w ścianie to co innego: nikt go stamtąd nie wyciągnie
        # (siatki bezpieczeństwa `walkable_pos_near` używa tylko gracz).
        if not wall_is_fatal and _has_reachable_neighbour(ctx, x, y):
            return Row(WARN, layer, name,
                       "stoi na kaflu nieprzechodnim (drzwi?) - NPC dojdzie najwyżej "
                       "do sąsiedniego kafla", (x, y))
        return Row(ERROR, layer, name,
                   "stoi na kaflu nieprzechodnim (płot, mur, drzewo) - gra nie dosuwa "
                   "NPC-ów do wolnego kafla, więc zostanie tam na zawsze", (x, y))
    if ctx.reach_hard[y][x]:
        return None
    if ctx.reach_soft[y][x]:
        return Row(INFO, layer, name,
                   "osiągalne dopiero po zniszczeniu krzaków - jeśli to zamierzone "
                   "(jak skrzynia kota w Q04_S01), nic nie rób", (x, y))
    return Row(ERROR, layer, name,
               "NIEOSIĄGALNE z żadnego punktu wejścia - gracz tu nie dojdzie", (x, y))


def check_reachability(ctx: Ctx) -> list[Row]:
    rows: list[Row] = []
    for layer in ("places", "entry_points", "spawn_points"):
        for obj in ctx.objects(layer):
            # Spawn liczymy po STOPACH, reszta po kotwicy: `places` i `entry_points`
            # gra czyta jako punkt (`rect.midbottom`), ale postać ma pod tym punktem
            # prostokąt `feet` i to ON zderza się ze ścianą - a leży kafel wyżej.
            # Ta jedna linijka różnicy przepuszczała krowy stojące w płocie.
            x, y = ctx.stand_tile(obj) if layer == "spawn_points" else ctx.anchor_tile(obj)
            row = _reach_row(ctx, layer, obj.name or f"<bez nazwy id={obj.id}>", x, y,
                             wall_is_fatal=layer == "spawn_points")
            if row:
                rows.append(row)
    for obj in ctx.objects("interactions"):
        x, y = ctx.tile_of(obj)
        kind = obj.props.get("obj_type", "")
        if kind == "chest":
            row = _reach_row(ctx, "interactions", obj.name, x, y)
        else:
            # drzwi SAME stoją w ścianie - liczy się kafel, z którego się wchodzi
            row = _approach_row(ctx, obj, x, y)
        if row:
            rows.append(row)
    return rows


def _approach_row(ctx: Ctx, obj: MapObject, x: int, y: int) -> Row | None:
    """Do wyjścia musi dać się podejść: któryś z czterech sąsiadów jest osiągalny."""
    for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < ctx.w and 0 <= ny < ctx.h and ctx.reach_hard[ny][nx]:
            return None
    return Row(ERROR, "interactions", obj.name,
               "do wyjścia nie da się podejść - żaden sąsiedni kafel nie jest "
               "osiągalny z punktu wejścia", (x, y))


def check_exit_on_door(ctx: Ctx) -> list[Row]:
    walls = ctx.tmap.tile_layer("walls")
    rows: list[Row] = []
    for obj in ctx.objects("interactions"):
        if obj.props.get("obj_type", "") != "exit":
            continue
        x, y = ctx.tile_of(obj)
        gid = walls.get(x, y)
        near_wall = any(
            walls.get(x + dx, y + dy)
            for dx in (-1, 0, 1) for dy in (-1, 0, 1)
        )
        if not gid and not near_wall:
            rows.append(Row(ERROR, "interactions", obj.name,
                            "wyjście stoi w otwartym terenie - żadnego budynku ani wejścia "
                            "w promieniu kafla", (x, y)))
        elif gid and ctx.door_gids and gid not in ctx.door_gids:
            rows.append(Row(WARN, "interactions", obj.name,
                            f"kafel {gid} nie jest znanym kaflem drzwi. Jeśli to drzwi, "
                            f"dodaj ten budynek do katalogu klocków (warstwa `stamps`)", (x, y)))
    return rows


def check_doors_reachable(ctx: Ctx) -> list[Row]:
    """Do każdych drzwi na mapie musi dać się podejść.

    Sprawdzenie `check_reachability` patrzy tylko na obiekty, więc dom, który nie
    ma jeszcze `exit`-u do wnętrza, mógłby zostać otoczony płotem bez bramy i nikt
    by tego nie zauważył. Drzwi rozpoznajemy po kaflach z katalogu klocków, a
    "podejść" znaczy: kafel pod progiem jest osiągalny z punktu wejścia.
    """
    if not ctx.door_gids:
        return []
    walls = ctx.tmap.tile_layer("walls")
    rows: list[Row] = []
    for y in range(ctx.h):
        for x in range(ctx.w):
            if walls.data[y][x] not in ctx.door_gids:
                continue
            below = y + 1
            if below >= ctx.h:
                continue
            if ctx.reach_hard[below][x]:
                continue
            level = WARN if ctx.reach_soft[below][x] else ERROR
            rows.append(Row(level, "drzwi", f"kafel {walls.data[y][x]}",
                            "próg nieosiągalny z żadnego punktu wejścia - gracz i NPC-e "
                            "nie wejdą do tego budynku", (x, below)))
    return rows


def check_doors_wired(ctx: Ctx) -> list[Row]:
    """Drzwi bez `exit`-u to dom, do którego nie da się wejść.

    Rutyna doprowadzi tam NPC-a, `places` będzie wskazywać ten dom, a gracz
    podejdzie i nic się nie stanie - bez żadnego komunikatu, bo z punktu widzenia
    gry po prostu nie ma tam wyjścia. Dopóki każde wnętrze nie ma swojej mapy,
    da się je tymczasowo podpiąć pod istniejącą (np. JACOBS_CHAMBER), żeby dało
    się to przetestować.
    """
    if not ctx.door_gids:
        return []
    walls = ctx.tmap.tile_layer("walls")
    wired = {ctx.tile_of(obj) for obj in ctx.objects("interactions")
             if obj.props.get("obj_type", "") == "exit"}
    rows: list[Row] = []
    for y in range(ctx.h):
        for x in range(ctx.w):
            if walls.data[y][x] not in ctx.door_gids or (x, y) in wired:
                continue
            rows.append(Row(WARN, "drzwi", f"kafel {walls.data[y][x]}",
                            "drzwi bez `exit`-u - nie prowadzą do żadnej mapy wnętrza. "
                            "Na czas testów podepnij je pod istniejące wnętrze",
                            (x, y)))
    return rows


def check_exit_targets(ctx: Ctx) -> list[Row]:
    """Do każdego `exit` musi istnieć `entry_point` po drugiej stronie."""
    rows: list[Row] = []
    for obj in ctx.objects("interactions"):
        if obj.props.get("obj_type", "") != "exit":
            continue
        to_map = obj.props.get("to_map", "")
        target = obj.props.get("destination_entry_point", "")
        if not to_map:
            rows.append(Row(ERROR, "interactions", obj.name, "wyjście bez `to_map`"))
            continue
        other = maps_dir() / f"{to_map}.tmx"
        if not other.exists():
            rows.append(Row(INFO, "interactions", obj.name,
                            f"mapy `{to_map}` nie ma jeszcze w `maps/` - sprawdzę, gdy powstanie"))
            continue
        names = {o.name for o in TiledMap.load(other).object_group("entry_points").objects}
        if target and target not in names:
            rows.append(Row(ERROR, "interactions", obj.name,
                            f"`{to_map}` nie ma punktu wejścia `{target}` "
                            f"(ma: {', '.join(sorted(names)) or 'żadnego'})"))
    return rows


def check_chests(ctx: Ctx) -> list[Row]:
    rows: list[Row] = []
    for obj in ctx.objects("interactions"):
        kind = obj.props.get("obj_type", "")
        if kind:
            if kind == "chest" and ctx.world.chests and obj.name not in ctx.world.chests:
                rows.append(Row(ERROR, "interactions", obj.name,
                                "skrzynia bez wzorca w `config.chests`"))
            continue
        # obiekt z gidem, ale bez `obj_type` - `load_interactions` pomija go po cichu
        rows.append(Row(
            ERROR, "interactions", obj.name or f"<bez nazwy id={obj.id}>",
            "obiekt bez własności `obj_type` - `load_interactions` bierze pod uwagę "
            "wyłącznie `exit` i `chest`, więc ten jest po cichu pomijany",
        ))
    return rows


def check_spawn_points(ctx: Ctx) -> list[Row]:
    rows: list[Row] = []
    seen: Counter[str] = Counter()
    for obj in ctx.objects("spawn_points"):
        name = obj.name
        if not name:
            rows.append(Row(ERROR, "spawn_points", f"<bez nazwy id={obj.id}>",
                            "spawn bez nazwy - nazwa jest kluczem instancji w zapisie gry "
                            "i wiąże trasę z warstwy `waypoints`",
                            ctx.anchor_tile(obj)))
            continue
        seen[name] += 1
        model = ctx.table.props_for(obj.gid).get("model_name", "") if obj.gid else ""
        if not model:
            rows.append(Row(ERROR, "spawn_points", name,
                            "gid nie niesie `model_name` - użyj kafla z CharacterTileset.tsx"))
        elif ctx.world.characters and model not in ctx.world.characters:
            rows.append(Row(ERROR, "spawn_points", name,
                            f"model `{model}` nie istnieje w characters.csv"))
    for name, times in seen.items():
        if times > 1:
            rows.append(Row(ERROR, "spawn_points", name,
                            f"nazwa użyta {times} razy - instancje NPC muszą być unikalne "
                            f"(konwencja `KLUCZ_NN`)"))
    return rows


def check_spawn_naming(ctx: Ctx) -> list[Row]:
    """D1/D2 tak samo, jak liczy je `validate-world` - tylko o krok wcześniej.

    Ta sama reguła stoi w `scripts/validate_world.py` (`check_spawn_naming`), ale
    tam widać ją dopiero po przeniesieniu mapy do gry i nazwaniu jej na stałe.
    Piętnaście błędów naraz po zmianie nazwy mapy to nie przypadek: nazwy nadał
    generator i nikt ich po drodze nie sprawdził.
    """
    rows: list[Row] = []
    models = Counter(
        ctx.table.props_for(obj.gid).get("model_name", "")
        for obj in ctx.objects("spawn_points") if obj.gid
    )
    for obj in ctx.objects("spawn_points"):
        model = ctx.table.props_for(obj.gid).get("model_name", "") if obj.gid else ""
        if not model or not obj.name or obj.name == model:
            continue
        suffix = obj.name[len(model):]
        if not (obj.name.startswith(model) and _INSTANCE_SUFFIX.fullmatch(suffix)):
            rows.append(Row(ERROR, "spawn_points", obj.name,
                            f"stawia model `{model}` - nazwa instancji ma brzmieć "
                            f"`{model}` albo `{model}_NN` (D1)",
                            ctx.stand_tile(obj)))
        elif models[model] == 1:
            rows.append(Row(WARN, "spawn_points", obj.name,
                            f"jedyna kopia `{model}` na mapie - numer instancji "
                            f"jest zbędny (D2)", ctx.stand_tile(obj)))
    return rows


def check_exit_naming(ctx: Ctx) -> list[Row]:
    """D6: nazwą obiektu `exit` jest KLUCZ MAPY DOCELOWEJ, nie nazwa budynku.

    Gra działa i bez tego (cel siedzi w `to_map`), więc to WARN - ale nazwa typu
    `SMITHY_DOOR` przeżywa rename mapy docelowej i od tego momentu kłamie, a
    znajduje się to dopiero przy ręcznym czytaniu warstwy `interactions`.
    """
    rows: list[Row] = []
    for obj in ctx.objects("interactions"):
        if obj.props.get("obj_type", "") != "exit":
            continue
        to_map = obj.props.get("to_map", "")
        if to_map and obj.name != to_map:
            rows.append(Row(WARN, "interactions", obj.name,
                            f"wyjście prowadzi do `{to_map}` - nazwa obiektu ma być "
                            f"kluczem mapy docelowej (D6)", ctx.tile_of(obj)))
    return rows


def check_zones(ctx: Ctx) -> list[Row]:
    rows: list[Row] = []
    present: set[str] = set()
    for obj in ctx.objects("zones"):
        present.add(obj.name)
        if obj.shape in ("polygon", "polyline") or not (obj.width and obj.height):
            rows.append(Row(
                ERROR, "zones", obj.name,
                "strefa nie jest prostokątem. `load_zones` buduje "
                "`pygame.Rect(x, y, width, height)`, a wielokąt ma width=height=0, "
                "więc w grze ta strefa ma zerową powierzchnię",
                ctx.tmap.tile_of(obj.x, obj.y),
            ))
    missing = ctx.world.zones_used - present
    if missing and present:
        rows.append(Row(WARN, "zones", ", ".join(sorted(missing)),
                        "strefa wymieniana w `allowed_zones` w characters.csv, "
                        "ale nieobecna na tej mapie"))
    return rows


def check_zone_placement(ctx: Ctx) -> list[Row]:
    """Czy strefa nadal leży TAM, GDZIE MIAŁA - po zmianie rozmiaru mapy albo `map-edit move`.

    Strefy są jedynymi prostokątami podawanymi w bezwzględnych kaflach, więc jako
    jedyne nie jadą razem z resztą: zmniejszenie mapy z 256x256 na 256x128 zostawiło
    `plains` w tym samym miejscu, tyle że tym miejscem był już pas lasu obrzeżnego.
    Gra nie mówi o tym ani słowa - `load_zones` buduje `pygame.Rect` z dowolnych
    liczb, a NPC z `allowed_zones` po prostu nie ma się gdzie ruszyć.

    Nie ma jak sprawdzić, czy strefa nazwana `plains` leży NA ŁĄCE (linter nie zna
    briefu), ale da się sprawdzić to, co z tego wynika: ile w niej kafli, po których
    da się chodzić. Las to głównie ściany i ten jeden pomiar łapie każdy taki
    przypadek, niezależnie od nazwy.
    """
    rows: list[Row] = []
    tw, th = ctx.tmap.tilewidth, ctx.tmap.tileheight
    for obj in ctx.objects("zones"):
        if not (obj.width and obj.height):
            continue                      # brak prostokąta zgłasza już `check_zones`
        x0, y0 = ctx.tmap.tile_of(obj.x, obj.y)
        x1 = x0 + max(1, int(obj.width) // tw)
        y1 = y0 + max(1, int(obj.height) // th)

        outside = sum(1 for y in range(y0, y1) for x in range(x0, x1)
                      if not (0 <= x < ctx.w and 0 <= y < ctx.h))
        total = (x1 - x0) * (y1 - y0)
        if outside == total:
            rows.append(Row(ERROR, "zones", obj.name,
                            f"strefa leży w całości poza mapą {ctx.w}x{ctx.h} - "
                            f"w grze ma zerową powierzchnię", (x0, y0)))
            continue
        if outside:
            rows.append(Row(ERROR, "zones", obj.name,
                            f"{outside * 100 // total}% strefy wystaje poza mapę "
                            f"{ctx.w}x{ctx.h} - przytnij prostokąt", (x0, y0)))

        inside = [(x, y) for y in range(y0, y1) for x in range(x0, x1)
                  if 0 <= x < ctx.w and 0 <= y < ctx.h]
        walkable = sum(1 for x, y in inside if ctx.hard[y][x])
        share = walkable / len(inside)
        if share < ZONE_WALKABLE_MIN:
            rows.append(Row(ERROR, "zones", obj.name,
                            f"tylko {share:.0%} kafli strefy jest chodliwych - stoi "
                            f"w lesie albo w zabudowie. Po zmianie rozmiaru mapy albo "
                            f"`map-edit move` strefy zostają na starych kaflach",
                            (x0, y0)))
        elif share < ZONE_WALKABLE_WARN:
            rows.append(Row(WARN, "zones", obj.name,
                            f"{share:.0%} kafli strefy jest chodliwych - ciasno jak "
                            f"na obszar wędrowania NPC-a", (x0, y0)))
        elif not any(ctx.reach_hard[y][x] for x, y in inside):
            rows.append(Row(ERROR, "zones", obj.name,
                            "cała strefa jest odcięta od reszty mapy - NPC nie ma "
                            "jak do niej dojść", (x0, y0)))
    return rows


def check_places(ctx: Ctx) -> list[Row]:
    rows: list[Row] = []
    map_key = ctx.path.stem
    wanted = ctx.world.places_used.get(map_key, set())
    present = {obj.name for obj in ctx.objects("places")}
    for name in sorted(wanted - present):
        rows.append(Row(ERROR, "places", name,
                        f"characters.csv kieruje tu rutynę (`{map_key}:{name}`), "
                        f"ale mapa nie ma takiego miejsca"))
    for name in sorted(present - wanted):
        rows.append(Row(WARN, "places", name,
                        "miejsce bez właściciela - żaden wiersz characters.csv do niego "
                        "nie celuje w kolumnach home/work/social/hobby"))
    return rows


def check_waypoints(ctx: Ctx) -> list[Row]:
    """Trasy patrolowania NPC. Kluczowe: `load_NPCs` wiąże krzywą ze spawnem PO NAZWIE
    (`scene.waypoints.get(obj.name, ())`), więc krzywa, której nazwy nie nosi żaden
    spawn, nie jest trasą chodzenia - to np. `intro`, czyli przelot kamery. Kamera
    nie koliduje ze ścianą, więc sprawdzanie jej wierzchołków byłoby fałszywką."""
    rows: list[Row] = []
    walkers = {obj.name for obj in ctx.objects("spawn_points") if obj.name}
    for obj in ctx.objects("waypoints"):
        if obj.props.as_bool("enabled", True) is False:
            continue
        if obj.name not in walkers:
            rows.append(Row(INFO, "waypoints", obj.name,
                            "krzywa bez spawnu o tej nazwie - nikt po niej nie chodzi "
                            "(przelot kamery albo trasa do podpięcia)"))
            continue
        for px, py in obj.world_points():
            x, y = ctx.tmap.tile_of(px, py)
            if not (0 <= x < ctx.w and 0 <= y < ctx.h):
                rows.append(Row(ERROR, "waypoints", obj.name, "wierzchołek poza mapą", (x, y)))
            elif not ctx.soft[y][x]:
                rows.append(Row(ERROR, "waypoints", obj.name,
                                "wierzchołek trasy leży w ścianie", (x, y)))
            elif not ctx.hard[y][x]:
                rows.append(Row(WARN, "waypoints", obj.name,
                                "wierzchołek trasy leży w zniszczalnym krzaku - NPC ruszy "
                                "dopiero, gdy ktoś go rozbije", (x, y)))
    return rows


def check_object_names(ctx: Ctx) -> list[Row]:
    rows: list[Row] = []
    for group in ctx.tmap.object_groups():
        for obj in group.objects:
            if obj.name != obj.name.strip():
                rows.append(Row(ERROR, group.name, repr(obj.name),
                                "nazwa ma białe znaki na brzegu - klucz encji nigdy się nie zgodzi"))
            elif "  " in obj.name:
                rows.append(Row(WARN, group.name, repr(obj.name),
                                "nazwa ma zwielokrotnione spacje w środku"))
    return rows


def check_border(ctx: Ctx) -> list[Row]:
    """Brzeg mapy ma być szczelny - inaczej kamera staje, a gracz idzie w czerń."""
    holes = 0
    for x in range(ctx.w):
        holes += ctx.reach_hard[0][x] + ctx.reach_hard[ctx.h - 1][x]
    for y in range(ctx.h):
        holes += ctx.reach_hard[y][0] + ctx.reach_hard[y][ctx.w - 1]
    if holes:
        return [Row(WARN, "brzeg", "", f"{holes} osiągalnych kafli na samej krawędzi mapy - "
                                       f"gracz dojdzie do granicy świata")]
    return []


def check_step_cost(ctx: Ctx) -> list[Row]:
    """Kafle bez `step_cost` chodzą po domyślnym koszcie - A* traktuje je jak drogę."""
    ground = ctx.tmap.tile_layer("ground")
    foliage = ctx.tmap.tile_layer("foliage")
    bare = 0
    for y in range(ctx.h):
        for x in range(ctx.w):
            if not ctx.hard[y][x]:
                continue
            top = foliage.data[y][x] or ground.data[y][x]
            if top and "step_cost" not in ctx.table.props_for(top):
                bare += 1
    if bare:
        share = bare / max(1, sum(row.count(True) for row in ctx.hard))
        level = WARN if share > 0.02 else INFO
        return [Row(level, "step_cost", "", f"{bare} chodliwych kafli ({share:.0%}) bez "
                                            f"`step_cost` - A* liczy im koszt domyślny")]
    return []


# --------------------------------------------------------------------------
# MARK: sprawdzenia wyglądu


def check_world_wiring(ctx: Ctx) -> list[Row]:
    """Czego brakuje POZA plikiem .tmx, żeby mapa była pełnoprawną lokacją.

    Skill nie dopisuje tych wpisów sam (decyzja D12: `characters.csv`, `locale`
    i `audio.toml` są domeną autora), więc jedyne, co może zrobić, to wypisać
    listę - i zrobić to tak, żeby dało się ją przepisać bez zgadywania.
    """
    import tomllib

    key = ctx.path.stem
    rows: list[Row] = []
    for lang in ("PL", "EN"):
        path = LOCALE_DIR / f"{lang}.toml"
        if not path.exists():
            continue
        names = tomllib.loads(path.read_text(encoding="utf-8")).get("map", {})
        if key not in names:
            rows.append(Row(WARN, f"locale/{lang}.toml [map]", key,
                            "brak nazwy dla gracza - w HUD i dzienniku widać surowy klucz"))
    if AUDIO_TOML.exists():
        music = tomllib.loads(AUDIO_TOML.read_text(encoding="utf-8")).get("music", {})
        if key not in music:
            rows.append(Row(INFO, "audio.toml [music]", key,
                            "brak wpisu - na tej mapie będzie cisza (to nie jest błąd)"))
    return rows


def check_monotony(ctx: Ctx) -> list[Row]:
    ground = ctx.tmap.tile_layer("ground")
    rows: list[Row] = []
    for y0 in range(0, ctx.h - WINDOW + 1, WINDOW):
        for x0 in range(0, ctx.w - WINDOW + 1, WINDOW):
            gids = [ground.data[y][x]
                    for y in range(y0, y0 + WINDOW) for x in range(x0, x0 + WINDOW)
                    if ground.data[y][x]]
            if len(gids) < WINDOW * WINDOW * 0.6:
                continue                      # okno w większości pod zabudową - nie oceniamy
            tally = Counter(gids)
            share = tally.most_common(1)[0][1] / len(gids)
            if share >= MONOTONY_SHARE and len(tally) < MONOTONY_DISTINCT:
                rows.append(Row(WARN, "monotonia", f"okno {WINDOW}x{WINDOW}",
                                f"jeden wariant zajmuje {share:.0%} kafli "
                                f"({len(tally)} wariantów) - dosyp odmian terenu",
                                (x0, y0)))
    return rows


WATER_STEP_COST = 300        # od tego kosztu w górę kafel jest wodą (Water.tsx)


def check_runs(ctx: Ctx) -> list[Row]:
    """Woda jest z natury jednolita, więc pas morza nie jest monotonią do naprawy -
    metryka pyta o to, czy generator rozłożył nudny dywan na terenie, po którym się chodzi."""
    ground = ctx.tmap.tile_layer("ground")
    worst = 0
    where = (0, 0)
    for y in range(ctx.h):
        run, prev = 0, -1
        for x in range(ctx.w):
            gid = ground.data[y][x]
            if gid and ctx.table.step_cost(gid, 100) >= WATER_STEP_COST:
                run, prev = 0, -1
                continue
            run = run + 1 if gid and gid == prev else 1
            prev = gid
            if run > worst:
                worst, where = run, (x - run + 1, y)
    if worst > MAX_RUN:
        return [Row(WARN, "monotonia", "ciąg w wierszu",
                    f"{worst} identycznych kafli z rzędu (próg {MAX_RUN})", where)]
    return []


def _blobs(ctx: Ctx) -> list[tuple[int, int, int, int]]:
    """Spójne bryły na `walls`+`over` - z grubsza budynki i kępy drzew."""
    walls = ctx.tmap.tile_layer("walls")
    over = ctx.tmap.tile_layer("over")
    occ = [[bool(walls.data[y][x] or over.data[y][x]) for x in range(ctx.w)]
           for y in range(ctx.h)]
    seen = [[False] * ctx.w for _ in range(ctx.h)]
    out: list[tuple[int, int, int, int]] = []
    for y in range(ctx.h):
        for x in range(ctx.w):
            if not occ[y][x] or seen[y][x]:
                continue
            queue = deque([(x, y)])
            seen[y][x] = True
            cells = []
            while queue:
                cx, cy = queue.popleft()
                cells.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nx, ny = cx + dx, cy + dy
                        if (0 <= nx < ctx.w and 0 <= ny < ctx.h
                                and occ[ny][nx] and not seen[ny][nx]):
                            seen[ny][nx] = True
                            queue.append((nx, ny))
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            out.append((min(xs), min(ys), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1))
    return out


def check_alignment(ctx: Ctx) -> list[Row]:
    """Budynki ustawione w idealnej linii czytają się jako krata, nie jako wieś."""
    # Bryły dotykające krawędzi mapy to ściana lasu domykająca świat - jej prostota
    # jest z definicji, a nie z lenistwa generatora, więc nie liczymy jej do szablonu.
    blobs = [
        b for b in _blobs(ctx)
        if 2 <= b[2] <= 8 and 2 <= b[3] <= 8
        and b[0] > 0 and b[1] > 0
        and b[0] + b[2] < ctx.w and b[1] + b[3] < ctx.h
    ]
    rows: list[Row] = []
    # Wyrównanie liczy się LOKALNIE. Na mapie 256x256 cztery bryły dzielące
    # współrzędną x trafiają się przypadkiem kilkanaście razy (drzewa w pasie
    # lasu), a to nie jest szablon - szablonem jest rząd domów stojących obok
    # siebie. Stąd grupowanie po oknie: liczą się tylko bryły blisko siebie.
    for axis, index, other in (("kolumnie x", 0, 1), ("wierszu y", 1, 0)):
        tally: Counter[tuple[int, int]] = Counter(
            (b[index], b[other] // ALIGN_WINDOW) for b in blobs)
        for (value, bucket), times in tally.items():
            if times >= ALIGNED_BUILDINGS:
                rows.append(Row(WARN, "szablonowość", f"{axis}={value}",
                                f"{times} bryły wyrównane do jednej linii w oknie "
                                f"{ALIGN_WINDOW} kafli - rozrzuć je o kafel-dwa",
                                (value, bucket * ALIGN_WINDOW) if index == 0
                                else (bucket * ALIGN_WINDOW, value)))
    return rows


def check_empty_patches(ctx: Ctx) -> list[Row]:
    layers = [ctx.tmap.tile_layer(n) for n in ("foliage", "items", "walls", "over")]
    step = EMPTY_PATCH
    rows: list[Row] = []
    for y0 in range(0, ctx.h - step + 1, step):
        for x0 in range(0, ctx.w - step + 1, step):
            if any(layer.data[y][x]
                   for layer in layers
                   for y in range(y0, y0 + step) for x in range(x0, x0 + step)):
                continue
            if not any(ctx.reach_hard[y][x]
                       for y in range(y0, y0 + step) for x in range(x0, x0 + step)):
                continue                       # pustka poza zasięgiem gracza nie razi
            rows.append(Row(WARN, "pustka", f"{step}x{step}",
                            "połać bez jednego detalu, a gracz tędy chodzi", (x0, y0)))
    return rows


# Zmierzony próg (krok 6 planu): na siatce 256x256 A* kosztuje 0,7 ms przy trasie
# 30 kafli, 7,9 ms przy 90 i 20 ms przy 134 - czyli budżet klatki (16,7 ms przy
# 60 FPS) pęka w okolicach 110 kafli TRASY, niezależnie od rozmiaru mapy. Rutyna
# łącząca dwa miejsca dalej od siebie zawiesza grę na kilka klatek za każdym
# przekroczeniem slotu, a te lecą co kilka sekund realnego czasu.
ROUTE_BUDGET_TILES = 110


def check_routine_routes(ctx: Ctx) -> list[Row]:
    """Czy rutyny nie każą NPC-om chodzić dalej, niż A* zdąży policzyć w klatce."""
    map_key = ctx.path.stem
    wanted = ctx.world.places_used.get(map_key, set())
    places = {obj.name: ctx.anchor_tile(obj)
              for obj in ctx.objects("places") if obj.name in wanted}
    if len(places) < 2:
        return []
    rows: list[Row] = []
    names = sorted(places)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            (ax, ay), (bx, by) = places[first], places[second]
            manhattan = abs(ax - bx) + abs(ay - by)
            if manhattan <= ROUTE_BUDGET_TILES:
                continue          # trasa nie ma prawa być dłuższa niż odległość w linii
            rows.append(Row(
                WARN, "rutyny", f"{first} - {second}",
                f"miejsca dzieli {manhattan} kafli, a A* liczy trasę dłuższą niż "
                f"{ROUTE_BUDGET_TILES} kafli ponad budżet klatki (zmierzone: 134 kafle "
                f"= 20 ms przy 16,7 ms na klatkę). Postaw po drodze miejsce pośrednie "
                f"albo zbliż te dwa"))
    return rows


CHECKS = (
    check_layers, check_tilesets, check_sprites_layer, check_over_opacity, check_items_layer,
    check_start, check_reachability, check_doors_reachable, check_doors_wired,
    check_exit_on_door,
    check_exit_targets, check_chests,
    check_spawn_points, check_spawn_naming, check_exit_naming,
    check_zones, check_zone_placement, check_places, check_waypoints, check_object_names,
    check_border, check_step_cost, check_routine_routes, check_world_wiring,
    check_monotony, check_runs, check_alignment, check_empty_patches,
)


# --------------------------------------------------------------------------
# MARK: CLI


def resolve_map(name: str) -> Path:
    candidate = Path(name)
    if candidate.suffix == ".tmx" and candidate.exists():
        return candidate
    for folder in (maps_dir(), maps_dir() / "_wip"):
        hit = folder / f"{Path(name).stem}.tmx"
        if hit.exists():
            return hit
    raise SystemExit(f"nie znalazłem mapy '{name}' ani jako ścieżki, ani w maps/ i maps/_wip/")


def lint(path: Path, palette_path: Path | None = None) -> list[Row]:
    ctx = build_ctx(path, load_world(), palette_path)
    rows: list[Row] = []
    for check in CHECKS:
        rows.extend(check(ctx))
    return sort_rows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("map", help="nazwa mapy (BLUNDERHAVEN) albo ścieżka do .tmx")
    parser.add_argument("--json", action="store_true", help="wynik maszynowo")
    parser.add_argument("--strict", action="store_true", help="ostrzeżenia też failują")
    parser.add_argument("--palette", help="mapa z katalogiem klocków (domyślnie prototyp)")
    parser.add_argument("--only", help="tylko sprawdzenia, których nazwa zawiera ten tekst")
    args = parser.parse_args(argv)

    path = resolve_map(args.map)
    ctx = build_ctx(path, load_world(), Path(args.palette) if args.palette else None)
    rows: list[Row] = []
    for check in CHECKS:
        if args.only and args.only not in check.__name__:
            continue
        rows.extend(check(ctx))
    rows = sort_rows(rows)
    tally = counts(rows)

    if args.json:
        print(json.dumps({
            "map": path.stem,
            "size": [ctx.w, ctx.h],
            **{k: v for k, v in tally.items()},
            "rows": [row.as_dict() for row in rows],
        }, ensure_ascii=False, indent=2))
    else:
        report(rows, title=f"Lint mapy - {path.stem} ({ctx.w}x{ctx.h} kafli)")

    if tally[ERROR]:
        return 1
    return 1 if (args.strict and tally[WARN]) else 0


if __name__ == "__main__":
    sys.exit(main())
