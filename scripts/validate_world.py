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
MAZE_MAP_PREFIX = "Maze"

# Tiled object layers this validator understands
SPAWN_LAYER = "spawn_points"
PLACES_LAYER = "places"
WAYPOINTS_LAYER = "waypoints"
CHECKED_LAYERS = (SPAWN_LAYER, PLACES_LAYER, WAYPOINTS_LAYER, "entry_points", "interactions")

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
    # spawn object name -> the character key it resolves to (see _resolve_model_name)
    spawns: dict[str, str] = field(default_factory=dict)

    def names(self, layer: str) -> set[str]:
        return set(self.objects.get(layer, []))


@dataclass
class World:
    config: dict
    characters_csv: list[dict[str, str]]
    routines: dict[str, dict]
    maps: list[GameMap]
    sprites: set[str]
    #: `config_model/audio.toml` w surowej postaci; ``None`` = brak/nie parsuje się
    audio: dict | None = None

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
        for obj in group.iter("object"):
            name = obj.get("name") or ""
            names.append(name)
            if layer == SPAWN_LAYER:
                game_map.spawns[name] = _resolve_model_name(obj, tile_models)
        game_map.objects[layer] = names
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
    return World(config=config, characters_csv=characters_csv, routines=routines,
                 maps=maps, sprites=sprites, audio=audio)


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

    map_names = {m.name for m in world.maps}
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
