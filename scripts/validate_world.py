#!/usr/bin/env python3
"""Cross-source consistency check for the game world (C01).

Entity keys live in half a dozen namespaces that nothing ties together: config.json,
characters.csv, the Tiled maps (object names, `model_name`, `places`, `waypoints`),
routines.toml, item keys inside dialogue/quest conditions, and the sprite folders.
Dialogues, quests and locale have validators; the maps have none - so a typo in a
spawn point's `model_name`, in a `home` place or in a routine name is a silent
runtime `print` or a missing NPC, found by playing the game. This script finds them
in under a second instead.

It DIAGNOSES ONLY - it never edits a source file.

Run:
    just validate-world              # table + summary, exit 1 on errors
    just validate-world --strict     # warnings fail too
    python3 scripts/validate_world.py --json

Deliberately free of pygame/SDL: it parses raw JSON/CSV/TOML/XML, so it runs on a
bare interpreter, in CI, and inside a `just` recipe without a display.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_DIR = REPO_ROOT / "project"
CONFIG_DIR = PROJECT_DIR / "config_model"
ASSETS = PROJECT_DIR / "assets"
AUDIO_DIR = ASSETS / "audio"

# Klucze muzyki, które nie są nazwą mapy. Powtórzone za `project/audio.py`
# świadomie: ten skrypt jest wolny od pygame'a i importu gry (patrz docstring).
SPECIAL_MUSIC_KEYS = ("main_menu", "maze", "death")

# Hand-listed rather than globbed: `assets/MazeTileset/` holds the procedural dungeon
# templates, whose objects are generated at runtime and have no authored keys to check.
MAP_DIRS = (
    ASSETS / "NinjaAdventure" / "maps",
    ASSETS / "map",
)
SPRITE_DIR = ASSETS / "NinjaAdventure" / "characters"

# Mapy, które gra faktycznie ładuje. `ASSETS/"map"` powyżej to prototypy w starszym
# schemacie (warstwa `exits`, brak `obj_type`) - walidator je czyta, ale nie są
# lokacjami i nie mają dostać nazw wyświetlanych.
GAME_MAPS_DIR = ASSETS / "NinjaAdventure" / "maps"
LOCALE_DIR = ASSETS / "locale"
LOCALE_LANGS = ("PL", "EN")
# Powtórzone za `project/scene/map_registry.MAZE_MAP_PREFIX` świadomie: ten skrypt
# nie importuje gry (patrz docstring), a `map_registry` ciągnie `settings`, czyli pygame'a.
MAZE_MAP_PREFIX = "MAZE"

# Szablon labiryntu. Poziom labiryntu nie ma pliku `.tmx` - powstaje w locie z tego
# szablonu, więc jego warstwa `entry_points` jest jedynym źródłem prawdy o tym, dokąd
# wolno celować z `destination_entry_point` prowadzącego do labiryntu.
MAZE_TEMPLATE = ASSETS / "MazeTileset" / "MazeTileset_Ninja.tmx"

# Tileset przedmiotów: własność `item_name` na kaflu jest jedynym mostem między
# kluczem przedmiotu a warstwą `items` mapy.
ITEMS_TILESET = ASSETS / "NinjaAdventure" / "items" / "items.tsx"

# Tiled object layers this validator understands
SPAWN_LAYER = "spawn_points"
PLACES_LAYER = "places"
WAYPOINTS_LAYER = "waypoints"
ENTRY_LAYER = "entry_points"
INTERACTIONS_LAYER = "interactions"
CHECKED_LAYERS = (SPAWN_LAYER, PLACES_LAYER, WAYPOINTS_LAYER, ENTRY_LAYER, INTERACTIONS_LAYER)

# Kolumny `characters.csv`, których wartością jest miejsce z warstwy `places`.
PLACE_COLUMNS = ("home", "work", "social", "hobby")

# `<KLUCZ_MODELU>` albo `<KLUCZ_MODELU>_<NN>` - konwencja nazwy instancji z D1/D2.
_INSTANCE_SUFFIX = re.compile(r"_(\d+)$")

# gid flip flags occupy the top three bits; strip them to get the real tile id
_GID_MASK = 0x1FFFFFFF

ERROR, WARN = "ERROR", "WARN"


@dataclass
class Violation:
    severity: str
    source: str
    message: str


@dataclass
class GameMap:
    """One .tmx, reduced to the parts that carry authored entity keys."""

    name: str                                    # map name in game = file stem
    path: Path
    # layer -> list of object names, in file order (duplicates preserved on purpose)
    objects: dict[str, list[str]] = field(default_factory=dict)
    # layer -> własności obiektów, w tej samej kolejności co `objects[layer]`.
    # Nazwa obiektu nie mówi wszystkiego: wyjście zna cel w `to_map`, a nie w nazwie.
    props: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    # spawn object name -> the character key it resolves to (see _resolve_model_name)
    spawns: dict[str, str] = field(default_factory=dict)

    def names(self, layer: str) -> set[str]:
        return set(self.objects.get(layer, []))

    def entries(self, layer: str) -> list[tuple[str, dict[str, str]]]:
        """(nazwa obiektu, jego własności) dla warstwy - w kolejności z pliku."""
        return list(zip(self.objects.get(layer, []), self.props.get(layer, []), strict=False))


@dataclass
class World:
    config: dict
    characters_csv: list[dict[str, str]]
    routines: dict[str, dict]
    maps: list[GameMap]
    sprites: set[str]
    #: `config_model/audio.toml` w surowej postaci; ``None`` = brak/nie parsuje się
    audio: dict | None = None
    #: ścieżka tilesetu (względem repo) -> {lokalne id kafla: `model_name`}
    tilesets: dict[str, dict[int, str]] = field(default_factory=dict)
    #: nazwy obiektów z warstwy `entry_points` szablonu labiryntu (MAZE_TEMPLATE)
    maze_entry_points: set[str] = field(default_factory=set)
    #: `config_model/items.csv` - ręcznie edytowane źródło sekcji `items` w configu
    items_csv: list[dict[str, str]] = field(default_factory=list)
    #: `config_model/chests.csv` - to samo dla sekcji `chests`
    chests_csv: list[dict[str, str]] = field(default_factory=list)
    #: klucze przedmiotów zadeklarowane na kaflach `items/items.tsx` (własność `item_name`)
    item_tiles: set[str] = field(default_factory=set)
    #: nazwy sprite'ów z arkuszy przedmiotów w `settings.py` (ITEMS_ + GEMS_SHEET_DEFINITION)
    item_sprites: set[str] = field(default_factory=set)

    @property
    def places(self) -> dict[str, set[str]]:
        """map name -> place names on it."""
        return {m.name: m.names(PLACES_LAYER) for m in self.maps}

    @property
    def all_places(self) -> set[str]:
        return {p for m in self.maps for p in m.names(PLACES_LAYER)}

    @property
    def all_waypoints(self) -> set[str]:
        return {w for m in self.maps for w in m.names(WAYPOINTS_LAYER)}


#############################################################################################################
# MARK: loading
def _tileset_model_names(tsx_path: Path) -> dict[int, str]:
    """local tile id -> `model_name` declared on that tile in the tileset."""
    try:
        root = ET.parse(tsx_path).getroot()
    except (OSError, ET.ParseError):
        return {}
    result: dict[int, str] = {}
    for tile in root.iter("tile"):
        tile_id = tile.get("id")
        if tile_id is None:
            continue
        for prop in tile.iter("property"):
            if prop.get("name") == "model_name" and prop.get("value"):
                result[int(tile_id)] = prop.get("value", "")
    return result


def _resolve_model_name(obj: ET.Element, tile_models: list[tuple[int, dict[int, str]]]) -> str:
    """The character key a spawn object stands for.

    Three layers, most specific first - the same order the game resolves them in
    (``pytmx`` merges tile properties into the object, ``Character.__init__`` falls
    back to the object name):

    1. a ``model_name`` property on the object itself,
    2. a ``model_name`` on the TILE the object references through its ``gid`` -
       this is how most spawn points are authored (the key lives once in
       ``CharacterTileset.tsx``, not on every copy on the map),
    3. the object's own name.
    """
    for prop in obj.iter("property"):
        if prop.get("name") == "model_name" and prop.get("value"):
            return prop.get("value", "")

    raw_gid = obj.get("gid")
    if raw_gid is not None:
        gid = int(raw_gid) & _GID_MASK
        # highest firstgid not above this gid wins (tilesets are ordered by firstgid)
        for firstgid, models in sorted(tile_models, key=lambda t: t[0], reverse=True):
            if gid >= firstgid:
                name = models.get(gid - firstgid)
                if name:
                    return name
                break
    return obj.get("name") or ""


def load_map(path: Path) -> GameMap:
    root = ET.parse(path).getroot()

    # external tilesets, so a gid can be traced back to the tile that names the model
    tile_models: list[tuple[int, dict[int, str]]] = []
    for tileset in root.findall("tileset"):
        first = tileset.get("firstgid")
        source = tileset.get("source")
        if first is None:
            continue
        if source:
            models = _tileset_model_names((path.parent / source).resolve())
        else:  # tileset embedded straight in the map
            models = {}
            for tile in tileset.iter("tile"):
                tile_id = tile.get("id")
                if tile_id is None:
                    continue
                for prop in tile.iter("property"):
                    if prop.get("name") == "model_name" and prop.get("value"):
                        models[int(tile_id)] = prop.get("value", "")
        if models:
            tile_models.append((int(first), models))

    game_map = GameMap(name=path.stem, path=path)
    for group in root.iter("objectgroup"):
        layer = group.get("name") or ""
        if layer not in CHECKED_LAYERS:
            continue
        names: list[str] = []
        props: list[dict[str, str]] = []
        for obj in group.iter("object"):
            name = obj.get("name") or ""
            names.append(name)
            props.append({p.get("name", ""): p.get("value", "") for p in obj.iter("property")})
            if layer == SPAWN_LAYER:
                game_map.spawns[name] = _resolve_model_name(obj, tile_models)
        game_map.objects[layer] = names
        game_map.props[layer] = props
    return game_map


def load_world() -> World:
    with open(CONFIG_DIR / "config.json", encoding="utf-8") as f:
        config = json.load(f)
    with open(CONFIG_DIR / "characters.csv", newline="", encoding="utf-8") as f:
        characters_csv = list(csv.DictReader(f, delimiter=";"))
    with open(CONFIG_DIR / "routines.toml", "rb") as f:
        routines = tomllib.load(f).get("routine", {})

    try:
        with open(CONFIG_DIR / "audio.toml", "rb") as f:
            audio: dict | None = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        audio = None

    maps = [load_map(p) for d in MAP_DIRS for p in sorted(d.glob("*.tmx"))]
    sprites = {p.name for p in SPRITE_DIR.iterdir() if p.is_dir()} if SPRITE_DIR.is_dir() else set()

    # Rekursywnie, bo tilesety leżą w podkatalogu `maps/tilesets/` (C02, D15). Puste
    # słowniki odpadają: interesują nas wyłącznie tilesety niosące klucze postaci.
    tilesets: dict[str, dict[int, str]] = {}
    for directory in MAP_DIRS:
        for path in sorted(directory.rglob("*.tsx")):
            models = _tileset_model_names(path)
            if models:
                tilesets[str(path.relative_to(REPO_ROOT))] = models

    maze_entry_points: set[str] = set()
    if MAZE_TEMPLATE.is_file():
        maze_entry_points = load_map(MAZE_TEMPLATE).names(ENTRY_LAYER)

    items_csv = _read_csv(CONFIG_DIR / "items.csv")
    chests_csv = _read_csv(CONFIG_DIR / "chests.csv")

    return World(config=config, characters_csv=characters_csv, routines=routines,
                 maps=maps, sprites=sprites, audio=audio,
                 tilesets=tilesets, maze_entry_points=maze_entry_points,
                 items_csv=items_csv, chests_csv=chests_csv,
                 item_tiles=_item_tile_names(ITEMS_TILESET),
                 item_sprites=_settings_sheet_keys("ITEMS_SHEET_DEFINITION",
                                                   "GEMS_SHEET_DEFINITION"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def _item_tile_names(tsx_path: Path) -> set[str]:
    """Klucze przedmiotów z własności ``item_name`` kafli tilesetu przedmiotów.

    To one stawiają przedmiot na mapie: `load_items` czyta `item_name` z kafla warstwy
    `items` i woła `conf.items[name]`, więc kafel z nieznanym kluczem wywala grę
    `KeyError`-em przy wczytaniu mapy - ta sama mina, co zepsute `model_name` z O8.
    """
    try:
        root = ET.parse(tsx_path).getroot()
    except (OSError, ET.ParseError):
        return set()
    return {prop.get("value", "") for prop in root.iter("property")
            if prop.get("name") == "item_name" and prop.get("value")}


def _settings_sheet_keys(*names: str) -> set[str]:
    """Klucze słowników-arkuszy sprite'ów wyciągnięte z `settings.py` przez `ast`.

    Bez importu: `settings` ciągnie pygame'a, a ten skrypt ma działać na gołym
    interpreterze (patrz docstring modułu). `_played_sfx_keys` czyta kod tak samo.
    """
    try:
        tree = ast.parse((PROJECT_DIR / "settings.py").read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    wanted, out = set(names), set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
            continue
        targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if not targets & wanted:
            continue
        out |= {key.value for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)}
    return out


#############################################################################################################
# MARK: helpers
def _place_exists(world: World, value: str) -> bool:
    """`Map:place` must exist on that map; a bare `place` on any map.

    Split once from the left: place names may legitimately contain no colon, and a
    second colon would belong to the name, not to the map prefix.
    """
    if ":" in value:
        map_name, place = value.split(":", 1)
        return place in world.places.get(map_name, set())
    return value in world.all_places


def _waypoint_exists(world: World, value: str) -> bool:
    """Same `[<map>:]<name>` shape as places - ``resolve_at`` accepts it for routes too."""
    if ":" in value:
        map_name, route = value.split(":", 1)
        for game_map in world.maps:
            if game_map.name == map_name:
                return route in game_map.names(WAYPOINTS_LAYER)
        return False
    return value in world.all_waypoints


def _csv_list(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _maze_monsters(world: World) -> set[str]:
    """Characters that only ever appear in procedurally generated dungeons."""
    keys: set[str] = set()
    for cfg in world.config.get("maze_configs", {}).values():
        if not isinstance(cfg, dict):
            continue
        for entry in cfg.get("monsters_list", []) or []:
            keys.add(str(entry))
        boss = cfg.get("boss_monster")
        if boss:
            keys.add(str(boss))
    return keys


def _game_map_keys(world: World) -> list[str]:
    """Klucze map, które gra ładuje: statyczne `.tmx` plus poziomy labiryntu.

    Ten sam rejestr, co `project/scene/map_registry.all_map_keys` - poziom labiryntu
    nie ma pliku `.tmx`, więc sama obecność pliku nigdy nie wystarczyła za listę
    legalnych map (C02, D13).
    """
    static = {p.stem for p in GAME_MAPS_DIR.glob("*.tmx")}
    maze = {f"{MAZE_MAP_PREFIX}_{int(level):02d}"
            for level in (world.config.get("maze_configs") or {})}
    return sorted(static | maze)


def _is_maze_key(world: World, map_key: str) -> bool:
    """Czy klucz jest poziomem labiryntu - liczone z rejestru, nie z prefiksu.

    ``MAZE_09`` przy czterech wierszach `maze_configs.csv` jest mapą, której nie ma,
    a nie labiryntem (to samo rozróżnienie, co `map_registry.is_maze_map`).
    """
    levels = len(world.config.get("maze_configs") or {})
    match = re.match(rf"^{re.escape(MAZE_MAP_PREFIX)}_(\d{{2,}})$", map_key)
    return bool(match) and 1 <= int(match.group(1)) <= levels


def _entry_points_of(world: World, map_key: str) -> set[str] | None:
    """Nazwy obiektów z warstwy `entry_points` mapy - albo ``None``, gdy mapy nie ma.

    Poziom labiryntu nie ma pliku `.tmx`: jego punkty wejścia (`Entry`, `Re-Entry`)
    przychodzą z szablonu, który generator przerabia na konkretny poziom.
    """
    for game_map in world.maps:
        if game_map.name == map_key:
            return game_map.names(ENTRY_LAYER)
    if _is_maze_key(world, map_key):
        return world.maze_entry_points
    return None


def _map_references(world: World) -> list[tuple[str, str]]:
    """(gdzie napisane, klucz mapy) dla każdego odwołania do mapy poza samym `.tmx`.

    Jedno miejsce zamiast pięciu: reguła „mapa spoza rejestru" ma świecić tak samo
    dla drzwi, dla prefiksu miejsca i dla celu rutyny (D13).
    """
    found: list[tuple[str, str]] = []
    for game_map in world.maps:
        for name, props in game_map.entries(INTERACTIONS_LAYER):
            to_map = props.get("to_map", "").strip()
            if to_map:
                found.append((f"{game_map.path.name}:{INTERACTIONS_LAYER}:{name}", to_map))

    for row in world.characters_csv:
        for column in PLACE_COLUMNS:
            value = (row.get(column) or "").strip()
            if ":" in value:
                found.append((f"characters.csv:{row.get('key', '?')}:{column}",
                              value.split(":", 1)[0]))

    for name, routine in world.routines.items():
        for step in routine.get("slot", []) or []:
            kind, _, arg = str(step.get("at", "")).partition(":")
            if kind == "location" and ":" in arg:
                found.append((f"routines.toml:{name}", arg.split(":", 1)[0]))
    return found


def _played_sfx_keys() -> set[str]:
    """Klucze z każdego `play_sfx("...")` w `project/`.

    Grep po źródłach, nie import gry: ten skrypt musi działać bez pygame'a i bez
    SDL-a. Zbierane są WSZYSTKIE literały z nawiasu wywołania, bo warunkowy wybór
    dźwięku (``play_sfx("player_die" if ... else "monster_die")``) jest w tym
    kodzie normalny i oba klucze są realnie używane. Cena tej prostoty: napis w
    WARUNKU (``play_sfx("a" if x == "b" else "c")``) też zostanie wzięty za klucz,
    więc takie wywołania rozpisujemy na dwie gałęzie ``if``/``else``. Dynamiczny
    klucz (``play_sfx(name)``) byłby nie do sprawdzenia statycznie - i nie ma go
    w grze.
    """
    keys: set[str] = set()
    call = re.compile(r"play_sfx\(([^)]*)\)")
    literal = re.compile(r'"([^"]+)"')
    for path in PROJECT_DIR.rglob("*.py"):
        if path.name == "audio.py":
            continue          # docstringi i `__all__` samego modułu, nie wywołania
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for args in call.findall(text):
            keys.update(literal.findall(args))
    return keys


def _condition_items(world: World) -> list[tuple[str, str]]:
    """(item key, where it was written) for every `has_item("...")` in dialogs/quests."""
    found: list[tuple[str, str]] = []
    for section in ("dialogs", "quests"):
        blob = json.dumps(world.config.get(section, {}), ensure_ascii=False)
        for item in re.findall(r'has_item\(\\?"([^"\\]+)\\?"\)', blob):
            found.append((item, f"config.json:{section}"))
    return found


#############################################################################################################
# MARK: checks
def check_spawn_models(world: World) -> list[Violation]:
    """Rule 1: every spawn point resolves to a character that exists in the config."""
    known = set(world.config.get("characters", {}))
    out = []
    for game_map in world.maps:
        for obj_name, model in game_map.spawns.items():
            if model and model not in known:
                out.append(Violation(
                    ERROR, f"{game_map.path.name}:{SPAWN_LAYER}",
                    f"spawn '{obj_name}' resolves to character '{model}', "
                    f"which is not in config.characters",
                ))
    return out


def check_character_places(world: World) -> list[Violation]:
    """Rule 2: home/work/social/hobby point at a real object on the `places` layer."""
    out = []
    for row in world.characters_csv:
        for column in ("home", "work", "social", "hobby"):
            value = (row.get(column) or "").strip()
            if not value:  # empty cell = no requirement, not an error
                continue
            if not _place_exists(world, value):
                out.append(Violation(
                    ERROR, f"characters.csv:{row.get('key', '?')}",
                    f"{column}='{value}' is not a place on any map's '{PLACES_LAYER}' layer",
                ))
    return out


def check_character_routines(world: World) -> list[Violation]:
    """Rule 3: the `routine` column names a routine that routines.toml defines."""
    out = []
    for row in world.characters_csv:
        routine = (row.get("routine") or "").strip()
        if routine and routine not in world.routines:
            out.append(Violation(
                ERROR, f"characters.csv:{row.get('key', '?')}",
                f"routine='{routine}' is not defined in routines.toml "
                f"(known: {', '.join(sorted(world.routines)) or 'none'})",
            ))
    return out


def check_routine_targets(world: World) -> list[Violation]:
    """Rule 4: routine steps point at a real place / waypoint curve.

    `type:<column>` is checked differently: it defers to the character's own
    home/work/social/hobby cell, which rule 2 already validates - here we only make
    sure the column it names exists at all.
    """
    columns = {"home", "work", "social", "hobby"}
    out = []
    for name, routine in world.routines.items():
        for step in routine.get("slot", []) or []:
            at = str(step.get("at", ""))
            kind, _, arg = at.partition(":")
            if kind == "location" and not _place_exists(world, arg):
                out.append(Violation(
                    ERROR, f"routines.toml:{name}",
                    f"step at='{at}' points at a place that no map declares",
                ))
            elif kind == "route" and not _waypoint_exists(world, arg):
                out.append(Violation(
                    ERROR, f"routines.toml:{name}",
                    f"step at='{at}' points at a waypoint curve that no map declares",
                ))
            elif kind == "type" and arg not in columns:
                out.append(Violation(
                    ERROR, f"routines.toml:{name}",
                    f"step at='{at}' names a column that characters.csv does not have "
                    f"(expected one of: {', '.join(sorted(columns))})",
                ))
    return out


def check_sprites(world: World) -> list[Violation]:
    """Rule 5: every character's sprite has an asset folder."""
    if not world.sprites:
        return [Violation(WARN, str(SPRITE_DIR), "sprite folder not found - sprites unchecked")]
    out = []
    for row in world.characters_csv:
        sprite = (row.get("sprite") or "").strip()
        if sprite and sprite not in world.sprites:
            out.append(Violation(
                ERROR, f"characters.csv:{row.get('key', '?')}",
                f"sprite='{sprite}' has no folder in {SPRITE_DIR.relative_to(REPO_ROOT)}",
            ))
    return out


def check_items(world: World) -> list[Violation]:
    """Rule 6: item keys in inventories, chests, quest rewards and conditions exist."""
    known = set(world.config.get("items", {}))
    out = []

    for row in world.characters_csv:
        for item in _csv_list(row.get("items", "")):
            if item not in known:
                out.append(Violation(
                    ERROR, f"characters.csv:{row.get('key', '?')}",
                    f"carries item '{item}', which is not in config.items",
                ))

    for chest_key, chest in (world.config.get("chests") or {}).items():
        for item in (chest.get("items") or []) if isinstance(chest, dict) else []:
            if str(item) not in known:
                out.append(Violation(
                    ERROR, f"config.json:chests:{chest_key}",
                    f"contains item '{item}', which is not in config.items",
                ))

    for quest_key, quest in (world.config.get("quests") or {}).items():
        if not isinstance(quest, dict):
            continue
        for reward in (quest.get("rewards") or []):
            item = reward.get("item") if isinstance(reward, dict) else None
            if item and str(item) not in known:
                out.append(Violation(
                    ERROR, f"config.json:quests:{quest_key}",
                    f"rewards item '{item}', which is not in config.items",
                ))

    for item, where in _condition_items(world):
        if item not in known:
            out.append(Violation(
                ERROR, where, f"condition has_item(\"{item}\") names an item not in config.items"))
    return out


def check_dialog_keys(world: World) -> list[Violation]:
    """Rule 7: a character flagged as having a dialog actually has one."""
    dialogs = set(world.config.get("dialogs", {}))
    out = []
    for key, character in (world.config.get("characters") or {}).items():
        if not isinstance(character, dict):
            continue
        dialog_key = character.get("dialog_key") or ""
        if dialog_key and dialog_key not in dialogs:
            out.append(Violation(
                ERROR, f"config.json:characters:{key}",
                f"dialog_key='{dialog_key}' has no section in config.dialogs",
            ))
        elif not dialog_key and character.get("has_dialog") and key not in dialogs:
            out.append(Violation(
                ERROR, f"config.json:characters:{key}",
                "has_dialog is set but config.dialogs has no section under this key",
            ))
    return out


def check_unspawned_characters(world: World) -> list[Violation]:
    """Rule 8 (WARN): a character nobody places on a map and no dungeon rolls."""
    spawned = {model for m in world.maps for model in m.spawns.values()}
    maze_only = _maze_monsters(world)
    out = []
    for key in sorted(world.config.get("characters", {})):
        if key == "Player" or key in spawned or key in maze_only:
            continue
        out.append(Violation(
            WARN, f"config.json:characters:{key}",
            "character has no spawn point on any map and is not a dungeon monster",
        ))
    return out


def check_legacy_waypoints(world: World) -> list[Violation]:
    """Rule 9 (WARN): a routine-less NPC with no waypoint curve just stands still."""
    routine_by_key = {row.get("key"): (row.get("routine") or "").strip()
                      for row in world.characters_csv}
    out = []
    for game_map in world.maps:
        curves = game_map.names(WAYPOINTS_LAYER)
        for obj_name, model in game_map.spawns.items():
            if routine_by_key.get(model):       # has a routine: waypoints are legacy
                continue
            character = (world.config.get("characters") or {}).get(model)
            if not isinstance(character, dict) or character.get("race") != "humanoid":
                continue                        # animals/monsters roam without curves
            if obj_name not in curves:
                out.append(Violation(
                    WARN, f"{game_map.path.name}:{SPAWN_LAYER}",
                    f"'{obj_name}' has neither a routine nor a '{WAYPOINTS_LAYER}' curve "
                    f"- it will not move",
                ))
    return out


def check_duplicate_object_names(world: World) -> list[Violation]:
    """Rule 10 (WARN): two objects sharing a name in one layer of one map.

    Both the waypoint lookup and the loaded-NPC registry are keyed by object name, so
    the second one silently loses.
    """
    out = []
    for game_map in world.maps:
        for layer, names in game_map.objects.items():
            for name, count in Counter(n for n in names if n).items():
                if count > 1:
                    out.append(Violation(
                        WARN, f"{game_map.path.name}:{layer}",
                        f"'{name}' appears {count}x in this layer - lookups keyed by name "
                        f"will only see one of them",
                    ))
    return out


def check_audio_manifest(world: World) -> list[Violation]:
    """Rule 11: `config_model/audio.toml` opisuje pliki i eventy, które istnieją.

    Cztery pomyłki, które inaczej wychodzą dopiero przy graniu (i to jako cisza,
    czyli najgorszy możliwy objaw): brakujący plik ogg, klucz muzyki, który nie
    jest ani mapą, ani kontekstem specjalnym, wpis SFX, którego nikt nie woła,
    oraz `play_sfx("literówka")` bez wpisu w manifeście.
    """
    out: list[Violation] = []
    if world.audio is None:
        out.append(Violation(ERROR, "audio.toml", "manifest nie istnieje albo się nie parsuje"))
        return out

    music = world.audio.get("music", {}) or {}
    settings = music.get("settings", {}) or {}
    music_files = {k: v for k, v in music.items() if isinstance(v, str)}
    sfx_files = {k: v for k, v in (world.audio.get("sfx", {}) or {}).items() if isinstance(v, str)}

    if not isinstance(settings, dict):
        out.append(Violation(ERROR, "audio.toml:[music.settings]", "musi być tabelą"))

    # rejestr, nie lista plików `.tmx`: poziom labiryntu jest mapą bez pliku (D13),
    # a prototypy z `assets/map/` mapami nie są
    map_names = set(_game_map_keys(world))
    for key, file_name in music_files.items():
        if not (AUDIO_DIR / "music" / file_name).is_file():
            out.append(Violation(ERROR, "audio.toml:[music]",
                                 f"'{key}' wskazuje na nieistniejący plik 'music/{file_name}'"))
        if key not in SPECIAL_MUSIC_KEYS and key not in map_names:
            out.append(Violation(
                ERROR, "audio.toml:[music]",
                f"'{key}' to ani mapa, ani jeden z kontekstów {'/'.join(SPECIAL_MUSIC_KEYS)}"))

    for key, file_name in sfx_files.items():
        if not (AUDIO_DIR / "sfx" / file_name).is_file():
            out.append(Violation(ERROR, "audio.toml:[sfx]",
                                 f"'{key}' wskazuje na nieistniejący plik 'sfx/{file_name}'"))

    called = _played_sfx_keys()
    for key in sorted(set(sfx_files) - called):
        out.append(Violation(ERROR, "audio.toml:[sfx]",
                             f"event '{key}' nie jest wołany nigdzie w project/ - martwy wpis"))
    for key in sorted(called - set(sfx_files)):
        out.append(Violation(ERROR, "project/*.py",
                             f"play_sfx(\"{key}\") nie ma wpisu w audio.toml"))
    return out


def check_map_display_names(world: World) -> list[Violation]:
    """Rule 12: każda mapa ma nazwę wyświetlaną w PL i EN (C02, D12/W2).

    Klucz encji (`LOST_CORK_TAVERN`) służy do projektowania świata, a gracz ma widzieć
    napis w swoim języku. HUD bierze go z sekcji `[map]` w locale; brak wpisu oznacza,
    że na ekranie wyląduje surowy klucz - dokładnie to, co C02 likwiduje (O5).
    Dodana mapa bez wpisu ma się zapalić tutaj, a nie dopiero na zrzucie ekranu.
    """
    out: list[Violation] = []
    tables: dict[str, dict[str, str]] = {}
    for lang in LOCALE_LANGS:
        path = LOCALE_DIR / f"{lang}.toml"
        try:
            with open(path, "rb") as f:
                data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            out.append(Violation(ERROR, f"locale/{lang}.toml", f"nie da się wczytać: {exc}"))
            continue
        section = data.get("map", {})
        if not isinstance(section, dict):
            out.append(Violation(ERROR, f"locale/{lang}.toml:[map]", "musi być tabelą"))
            continue
        tables[lang] = {key: str(value) for key, value in section.items()}

    if len(tables) < len(LOCALE_LANGS):
        return out

    map_keys = _game_map_keys(world)
    for key in map_keys:
        for lang in LOCALE_LANGS:
            if not tables[lang].get(key, "").strip():
                out.append(Violation(
                    ERROR, f"locale/{lang}.toml:[map]",
                    f"mapa '{key}' nie ma nazwy wyświetlanej - HUD pokaże graczowi surowy klucz",
                ))
    for lang in LOCALE_LANGS:
        for key in sorted(set(tables[lang]) - set(map_keys)):
            out.append(Violation(
                WARN, f"locale/{lang}.toml:[map]",
                f"'{key}' nie jest kluczem żadnej mapy - martwy wpis po rename'ie?",
            ))
    return out


def check_spawn_naming(world: World) -> list[Violation]:
    """Rule 13: nazwa obiektu w `spawn_points` = klucz modelu [+ `_NN`] (C02, D1/D2).

    Przed C02 stały obok siebie `BARMAN_ABSINTHRAYNER`, `Johny`, `FishRed01` i `Dog_orange`,
    więc autor przy każdej nowej postaci zgaduje, która forma jest ta właściwa. Po D1
    nazwa instancji to klucz modelu, a numer dochodzi dopiero wtedy, gdy kopii na mapie
    jest więcej niż jedna (D2) - stąd drugi, łagodniejszy poziom tej reguły.

    Nazwa obiektu nie jest ozdobą: zapis kluczuje po niej stan NPC-a (`npc_states[npc.name]`),
    a warstwa `waypoints` szuka krzywej pod tą samą nazwą.
    """
    out: list[Violation] = []
    for game_map in world.maps:
        copies = Counter(game_map.spawns.values())
        for obj_name, model in sorted(game_map.spawns.items()):
            if not model or obj_name == model:
                continue
            suffix = _INSTANCE_SUFFIX.search(obj_name)
            base = obj_name[:suffix.start()] if suffix else obj_name
            if base != model:
                out.append(Violation(
                    ERROR, f"{game_map.path.name}:{SPAWN_LAYER}",
                    f"'{obj_name}' stawia model '{model}' - nazwa instancji ma brzmieć "
                    f"'{model}' albo '{model}_NN' (D1)",
                ))
            elif copies[model] == 1:
                out.append(Violation(
                    WARN, f"{game_map.path.name}:{SPAWN_LAYER}",
                    f"'{obj_name}' to jedyna kopia '{model}' na tej mapie - numer "
                    f"instancji jest zbędny (D2)",
                ))
    return out


def check_interaction_targets(world: World) -> list[Violation]:
    """Rule 14: żadne drzwi nie prowadzą donikąd (C02, D6).

    Wyjście niesie trzy dane, z których każda może kłamać osobno: nazwę (klucz mapy
    docelowej), `to_map` i `destination_entry_point`. Nietrafiony punkt wejścia stawia
    gracza w (0, 0), a nietrafiona mapa wywala ładowarkę - jedno i drugie widać dopiero
    po przejściu przez te konkretne drzwi.

    Ta reguła jako jedyna czyta WŁASNOŚCI obiektów, nie same nazwy.
    """
    out: list[Violation] = []
    chests = set(world.config.get("chests") or {})
    known_maps = set(_game_map_keys(world))

    for game_map in world.maps:
        own_entries = game_map.names(ENTRY_LAYER)
        for name, props in game_map.entries(INTERACTIONS_LAYER):
            source = f"{game_map.path.name}:{INTERACTIONS_LAYER}"
            obj_type = props.get("obj_type", "").strip()

            if obj_type == "chest":
                if name not in chests:
                    out.append(Violation(
                        ERROR, source,
                        f"skrzynia '{name}' nie ma wpisu w config.chests",
                    ))
                continue

            if obj_type != "exit":
                out.append(Violation(
                    ERROR, source,
                    f"'{name}' ma obj_type='{obj_type}' - ładowarka zna tylko "
                    f"'exit' i 'chest', więc ten obiekt jest niewidoczny w grze",
                ))
                continue

            to_map = props.get("to_map", "").strip()
            if not to_map:
                out.append(Violation(ERROR, source, f"wyjście '{name}' nie ma własności 'to_map'"))
            elif name != to_map:
                # nie ERROR: klucz mapy docelowej jest w `to_map`, więc gra działa.
                # Rozjazd i tak jest miną - obiekt nazwany starą nazwą mapy przeżyje
                # rename i nikt tego nie zauważy.
                out.append(Violation(
                    WARN, source,
                    f"wyjście '{name}' prowadzi do '{to_map}' - nazwa obiektu ma być "
                    f"kluczem mapy docelowej (D6)",
                ))

            destination = props.get("destination_entry_point", "").strip()
            targets = _entry_points_of(world, to_map) if to_map else None
            if not destination:
                out.append(Violation(
                    ERROR, source,
                    f"wyjście '{name}' nie ma własności 'destination_entry_point'",
                ))
            elif to_map in known_maps and targets is not None and destination not in targets:
                out.append(Violation(
                    ERROR, source,
                    f"wyjście '{name}' celuje w punkt '{destination}', którego mapa "
                    f"'{to_map}' nie ma na warstwie '{ENTRY_LAYER}' "
                    f"(zna: {', '.join(sorted(targets)) or 'nic'})",
                ))

            back = props.get("return_entry_point", "").strip()
            if back and back not in own_entries:
                out.append(Violation(
                    ERROR, source,
                    f"wyjście '{name}' wraca w punkt '{back}', którego ta mapa nie ma "
                    f"na warstwie '{ENTRY_LAYER}'",
                ))
    return out


def check_place_prefixes(world: World) -> list[Violation]:
    """Rule 15: miejsce zawsze z prefiksem mapy - `MAPA:miejsce` (C02, D3).

    `bar`, `tables` i `badroom` istniały równocześnie na dwóch mapach, a goła nazwa
    trafiała na pierwszą z brzegu. Prefiks jest obowiązkowy także wewnątrz jednej mapy:
    inaczej dzień, w którym druga mapa dostaje `well`, zmienia znaczenie wpisów, których
    nikt nie ruszał.
    """
    out: list[Violation] = []
    for row in world.characters_csv:
        for column in PLACE_COLUMNS:
            value = (row.get(column) or "").strip()
            if value and ":" not in value:
                out.append(Violation(
                    ERROR, f"characters.csv:{row.get('key', '?')}",
                    f"{column}='{value}' nie ma prefiksu mapy - ma być 'MAPA:{value}' (D3)",
                ))

    for name, routine in world.routines.items():
        for step in routine.get("slot", []) or []:
            at = str(step.get("at", ""))
            kind, _, arg = at.partition(":")
            if kind == "location" and ":" not in arg:
                out.append(Violation(
                    ERROR, f"routines.toml:{name}",
                    f"krok at='{at}' nie ma prefiksu mapy - ma być 'location:MAPA:{arg}' (D3)",
                ))
    return out


def check_tileset_model_names(world: World) -> list[Violation]:
    """Rule 16: `model_name` na kaflu tilesetu jest kluczem istniejącej postaci (D14, O8).

    Reguła 1 sprawdza wartość ROZWIĄZANĄ dla obiektu stojącego na mapie, więc kafel,
    z którego nikt jeszcze nie postawił spawnu, przechodzi jej pod nosem - i czeka
    uśpiony, aż pierwszy spawn z niego postawiony wywali grę na `KeyError`.
    """
    known = set(world.config.get("characters") or {})
    out: list[Violation] = []
    for tileset, models in sorted(world.tilesets.items()):
        for tile_id, model in sorted(models.items()):
            if model not in known:
                out.append(Violation(
                    ERROR, tileset,
                    f"kafel {tile_id} ma model_name='{model}', którego nie ma "
                    f"w config.characters",
                ))
    return out


def check_map_references(world: World) -> list[Violation]:
    """Rule 17: każde odwołanie do mapy wskazuje mapę z rejestru (C02, D13).

    Mapa „istniała", bo istniał plik `.tmx` - a poziom labiryntu pliku nie ma i nigdy
    nie miał. Rejestr (`map_registry.all_map_keys`) jest jedyną listą legalnych kluczy;
    tutaj konfrontujemy z nią drzwi, prefiksy miejsc i cele rutyn naraz.
    """
    known = set(_game_map_keys(world))
    out: list[Violation] = []
    for source, map_key in _map_references(world):
        if map_key not in known:
            out.append(Violation(
                ERROR, source,
                f"odwołuje się do mapy '{map_key}', której nie ma w rejestrze map "
                f"(zna: {', '.join(sorted(known))})",
            ))
    return out


def check_map_coverage(world: World) -> list[Violation]:
    """Rule 18 (WARN): mapa bez muzyki, mapa nieosiągalna, utwór bez wpisu (D7, O4).

    Trzy objawy jednego kształtu - dane i świat rozjechały się po cichu. Żaden nie jest
    błędem: cisza na mapie bywa zamierzona, mapa może czekać na podpięcie, a utwór
    odłożony na Akt 1 ma prawo leżeć w repo (W5). Ale każdy chce być widziany.
    """
    out: list[Violation] = []
    map_keys = _game_map_keys(world)

    music: dict[str, str] = {}
    if world.audio is not None:
        music = {k: v for k, v in (world.audio.get("music") or {}).items() if isinstance(v, str)}

    for key in map_keys:
        # w labiryncie klucz `maze` ma pierwszeństwo przed nazwą mapy (patrz audio.toml)
        if key in music or (_is_maze_key(world, key) and "maze" in music):
            continue
        out.append(Violation(WARN, "audio.toml:[music]",
                             f"mapa '{key}' nie ma wpisu muzyki - będzie na niej cisza"))

    reachable = {map_key for _, map_key in _map_references(world)}
    # Poziomy 2+ labiryntu nie są wymienione w żadnym `.tmx`: schody w dół dostawia
    # generator (`maze_utils.build_tileset_map_from_maze`), gdy poprzedni poziom istnieje.
    reachable |= {key for key in map_keys
                  if _is_maze_key(world, key) and int(key.rsplit("_", 1)[1]) > 1}
    for key in map_keys:
        if key not in reachable:
            out.append(Violation(
                WARN, "maps",
                f"mapa '{key}' nie jest celem żadnego wyjścia z warstwy "
                f"'{INTERACTIONS_LAYER}' - gracz nie ma jak tam wejść "
                f"(mapa startowa jest tu wyjątkiem)",
            ))

    music_dir = AUDIO_DIR / "music"
    if music_dir.is_dir():
        used = set(music.values())
        for path in sorted(music_dir.glob("*.ogg")):
            if path.name not in used:
                out.append(Violation(
                    WARN, "assets/audio/music",
                    f"'{path.name}' nie ma wpisu w audio.toml - {path.stat().st_size // 1024} kB "
                    f"w repo i w paczce web, których gra nigdy nie odtworzy",
                ))
    return out


def check_item_keys(world: World) -> list[Violation]:
    """Rule 19: klucz przedmiotu znaczy to samo we wszystkich sześciu źródłach.

    Reguła 6 sprawdzała tylko *odwołania* do `config.items` - a `config.items` jest
    generowane z `items.csv` przez `just import-entities`, więc sam rozjazd tych dwóch
    plików był niewidoczny. Do tego dochodzą dwa źródła, których nikt dotąd nie czytał:

    - ``items/items.tsx`` - własność `item_name` na kaflu. To ona stawia przedmiot na
      mapie: `load_items` woła `conf.items[name]`, więc kafel z nieznanym kluczem
      wywala grę `KeyError`-em przy wczytaniu mapy. Ta sama mina co O8, tylko
      w przestrzeni przedmiotów zamiast postaci.
    - ``ITEMS_SHEET_DEFINITION`` / ``GEMS_SHEET_DEFINITION`` w `settings.py` - bez
      wpisu tam `create_item` nie ma czym narysować przedmiotu i też leci `KeyError`.

    ``chests.csv`` dochodzi z tego samego powodu, co `items.csv`: reguła 6 patrzy na
    `config.chests`, czyli na wynik importu, a nie na to, co autor napisał ręcznie.
    """
    known = set(world.config.get("items") or {})
    csv_keys = {row["key"].strip() for row in world.items_csv if (row.get("key") or "").strip()}
    out: list[Violation] = []

    for key in sorted(csv_keys - known):
        out.append(Violation(
            ERROR, "items.csv",
            f"'{key}' nie ma w config.items - uruchom `just import-entities`",
        ))
    for key in sorted(known - csv_keys):
        out.append(Violation(
            ERROR, "config.json:items",
            f"'{key}' nie ma wiersza w items.csv - został po rename'ie albo po kasacie",
        ))

    for key in sorted(world.item_tiles - known):
        out.append(Violation(
            ERROR, "items/items.tsx",
            f"kafel ma item_name='{key}', którego nie ma w config.items - "
            f"mapa z tym kaflem wywali grę na KeyError",
        ))

    if world.item_sprites:
        for key in sorted(known - world.item_sprites):
            out.append(Violation(
                ERROR, "config.json:items",
                f"'{key}' nie ma sprite'a w ITEMS_SHEET_DEFINITION ani "
                f"GEMS_SHEET_DEFINITION (settings.py) - nie da się go narysować",
            ))

    for row in world.chests_csv:
        for column in ("items", "random_items"):
            for item in _csv_list(row.get(column, "")):
                if item not in known:
                    out.append(Violation(
                        ERROR, f"chests.csv:{row.get('key', '?')}",
                        f"{column} zawiera '{item}', którego nie ma w config.items",
                    ))
    return out


CHECKS = (
    check_spawn_models,
    check_character_places,
    check_character_routines,
    check_routine_targets,
    check_sprites,
    check_items,
    check_dialog_keys,
    check_unspawned_characters,
    check_legacy_waypoints,
    check_duplicate_object_names,
    check_audio_manifest,
    check_map_display_names,
    check_spawn_naming,
    check_interaction_targets,
    check_place_prefixes,
    check_tileset_model_names,
    check_map_references,
    check_map_coverage,
    check_item_keys,
)


#############################################################################################################
# MARK: report
def report_table(violations: list[Violation], world: World) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        for v in violations:
            print(f"{v.severity:5}  {v.source}  {v.message}")
        return

    console = Console()
    table = Table(title="World consistency", header_style="bold", show_lines=False)
    table.add_column("Severity", no_wrap=True)
    table.add_column("Source", no_wrap=True, style="cyan")
    table.add_column("Problem")
    for v in violations:
        colour = "red" if v.severity == ERROR else "yellow"
        table.add_row(f"[{colour}]{v.severity}[/{colour}]", v.source, v.message)
    if violations:
        console.print(table)
    console.print(
        f"checked {len(world.maps)} maps, {len(world.characters_csv)} characters, "
        f"{len(world.routines)} routines"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strict", action="store_true", help="warnings fail the run too")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = parser.parse_args(argv)

    world = load_world()
    violations: list[Violation] = []
    for check in CHECKS:
        violations.extend(check(world))
    # errors first, then grouped by source, so a fix list reads top to bottom
    violations.sort(key=lambda v: (v.severity != ERROR, v.source, v.message))

    errors = sum(1 for v in violations if v.severity == ERROR)
    warnings = len(violations) - errors

    if args.json:
        print(json.dumps({
            "errors": errors,
            "warnings": warnings,
            "violations": [vars(v) for v in violations],
        }, ensure_ascii=False, indent=2))
    else:
        report_table(violations, world)
        summary = f"{errors} errors, {warnings} warnings"
        print(summary if (errors or warnings) else "no problems found (0 errors, 0 warnings)")

    if errors:
        return 1
    return 1 if (args.strict and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
