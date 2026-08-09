#!/usr/bin/env python3
"""Przemianowanie klucza encji we WSZYSTKICH źródłach naraz (C02, D10).

Klucz encji nie mieszka w jednym pliku. Klucz postaci siedzi w `characters.csv`,
w `config.json`, na kaflu `CharacterTileset.tsx` i w `maze_configs.csv`; klucz mapy -
w nazwie pliku `.tmx`, we własności `to_map` sąsiedniej mapy, w `audio.toml`,
w sekcji `[map]` obu plików locale i w prefiksach miejsc. Ręczny rename zawsze
którąś z tych warstw pomija, a walidator zobaczy to dopiero po fakcie.

Ten skrypt EDYTUJE pliki - i jest w tym dosłowny: nie robi wyszukiwania po całym
tekście, tylko wie, *w którym polu* którego pliku żyje dany rodzaj klucza. To
dlatego nie da się nim przypadkiem zamienić kolumny `name_EN` ("Horse") przy
przemianowaniu modelu `HORSE`: te dwie wartości brzmią tak samo, ale są zupełnie
różnymi bytami i skrypt nigdy ich nie myli.

Uruchomienie::

    just rename-entity Village BLUNDERHAVEN          # rodzaj wykryty automatycznie
    just rename-entity Snake_01 SNAKE --kind instance
    just rename-entity Village BLUNDERHAVEN --dry-run
    python3 scripts/rename_entity.py --list           # co dziś istnieje, per rodzaj

Rodzaje kluczy (``--kind``):

``character``    klucz modelu z `config.json`/`characters.csv` (``BARMAN_ABSINTHRAYNER``)
``map``          klucz mapy = stem pliku `.tmx` (``LOST_CORK_TAVERN``, ``MAZE_01``)
``instance``     nazwa obiektu w warstwie `spawn_points` i krzywej `waypoints` (``FISH_RED_01``)
``chest``        klucz skrzyni z `chests.csv` (``MAZE_01_BIG_CHEST``)
``entry_point``  nazwa obiektu w warstwie `entry_points` (``LOST_CORK_TAVERN_DOOR``)
``place``        nazwa obiektu w warstwie `places`, zawsze małymi (``house_bart``)

Czego skrypt świadomie NIE rusza:

- **zapisów gry** - stan NPC-a i skrzyni jest kluczowany nazwą obiektu (O1), więc
  rename kasuje ten stan. To nie jest do naprawienia skryptem: polityka jest w D9
  (podbicie wersji zapisu = jawna odmowa wczytania starego pliku).
- **kodu** - mapa startowa jest w `settings.START_MAP`, a klucz gracza
  w `settings.PLAYER_CONFIG_KEY`, właśnie po to, żeby rename danych nie wymagał
  edycji Pythona. Nowa stała w kodzie = nowy wiersz w tej liście, nie nowy glob.
- **dokumentów w Obsidianie** - `doc/PL/`, `doc/EN/`. Klucz encji jest tam
  aliasem we frontmatterze i to autor decyduje o nazwie pliku; `just import-*`
  wciągnie zmianę z powrotem.
- **kluczy przedmiotów** - siedzą także w warunkach dialogów i questów, czyli
  w treści, a nie w polu danych. Poza zakresem C02.

Manifest źródeł (``SOURCES`` niżej) jest publiczny: pilnuje go
`tests/test_rename_entity.py`, który failuje w dniu, w którym ktoś doda plik
danych nieobjęty żadnym globem - a nie przy pierwszym rename'ie po nim (D17).

Wolny od pygame'a i od importu gry, jak `validate_world.py`: surowy XML/CSV/TOML/JSON.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_DIR = REPO_ROOT / "project"
CONFIG_DIR = PROJECT_DIR / "config_model"
ASSETS = PROJECT_DIR / "assets"
GAME_MAPS_DIR = ASSETS / "NinjaAdventure" / "maps"

CHARACTER, MAP, INSTANCE, CHEST, ENTRY_POINT, PLACE = (
    "character", "map", "instance", "chest", "entry_point", "place",
)
KINDS = (CHARACTER, MAP, INSTANCE, CHEST, ENTRY_POINT, PLACE)

#: Kolumny `characters.csv` (i pola `config.json`), których wartość ma kształt
#: ``MAPA:miejsce`` - dwa klucze różnych rodzajów w jednej komórce (D3).
PLACE_COLUMNS = ("home", "work", "social", "hobby")

#: Klucze sekcji `[music]`, które nie są nazwą mapy (za `project/audio.py`).
SPECIAL_MUSIC_KEYS = ("main_menu", "maze", "death")

# ---------------------------------------------------------------------------
# Prymitywy edycji - każdy zwraca (nowy tekst, liczba trafień)
# ---------------------------------------------------------------------------

Edit = tuple[str, int]


def _split_place(value: str) -> tuple[str, str]:
    """``"BLUNDERHAVEN:well"`` -> ``("BLUNDERHAVEN", "well")``; ``"well"`` -> ``("", "well")``."""
    map_key, sep, place = value.partition(":")
    return (map_key, place) if sep else ("", value)


def _rename_place_value(value: str, kind: str, old: str, new: str) -> str:
    """Podmiana w komórce ``MAPA:miejsce`` - osobno prefiks mapy, osobno miejsce."""
    map_key, place = _split_place(value.strip())
    if kind == MAP and map_key == old:
        map_key = new
    elif kind == PLACE and place == old:
        place = new
    else:
        return value
    return f"{map_key}:{place}" if map_key else place


def _place_values(value: str) -> dict[str, set[str]]:
    map_key, place = _split_place(value.strip())
    found: dict[str, set[str]] = {}
    if map_key:
        found[MAP] = {map_key}
    if place:
        found[PLACE] = {place}
    return found


# --- XML (.tmx / .tsx): edycja tekstowa, bo ElementTree przeformatowałby plik ---

def _object_layers(text: str) -> list[tuple[str, int, int]]:
    """``[(nazwa warstwy, początek, koniec), …]`` dla każdej ``<objectgroup>``."""
    out: list[tuple[str, int, int]] = []
    for match in re.finditer(r'<objectgroup\b[^>]*\bname="([^"]+)"[^>]*>', text):
        if match.group(0).rstrip().endswith("/>"):      # pusta warstwa, np. `<objectgroup … />`
            continue
        end = text.find("</objectgroup>", match.end())
        out.append((match.group(1), match.end(), len(text) if end < 0 else end))
    return out


def xml_object_name(text: str, layer: str, old: str, new: str) -> Edit:
    """Nazwa obiektu w konkretnej warstwie ``.tmx``."""
    pattern = re.compile(rf'(<object\b[^>]*?\bname=")({re.escape(old)})(")')
    hits = 0
    # od końca, żeby wcześniejsze podmiany nie przesuwały pozostałych zakresów
    for name, start, end in reversed(_object_layers(text)):
        if name != layer:
            continue
        chunk, count = pattern.subn(rf"\g<1>{new}\g<3>", text[start:end])
        hits += count
        text = text[:start] + chunk + text[end:]
    return text, hits


def xml_object_names(text: str, layer: str) -> set[str]:
    out: set[str] = set()
    for name, start, end in _object_layers(text):
        if name == layer:
            out |= set(re.findall(r'<object\b[^>]*?\bname="([^"]*)"', text[start:end]))
    return out - {""}


def xml_property(text: str, prop: str, old: str, new: str) -> Edit:
    """Wartość własności ``<property name="prop" value="…"/>`` - w całym pliku."""
    pattern = re.compile(
        rf'(<property\b[^>]*?\bname="{re.escape(prop)}"[^>]*?\bvalue=")({re.escape(old)})(")')
    return pattern.subn(rf"\g<1>{new}\g<3>", text)


def xml_property_values(text: str, prop: str) -> set[str]:
    found = re.findall(
        rf'<property\b[^>]*?\bname="{re.escape(prop)}"[^>]*?\bvalue="([^"]*)"', text)
    return set(found) - {""}


def tsx_tile_type(text: str, old: str, new: str) -> Edit:
    """Atrybut ``type`` kafla - Tiled trzyma tam kopię ``model_name``."""
    pattern = re.compile(rf'(<tile\b[^>]*?\btype=")({re.escape(old)})(")')
    return pattern.subn(rf"\g<1>{new}\g<3>", text)


def tsx_tile_types(text: str) -> set[str]:
    return set(re.findall(r'<tile\b[^>]*?\btype="([^"]*)"', text)) - {""}


# --- CSV (średnik, bez cudzysłowów - patrz `config_model/AGENTS.md`) ---

def _csv_rows(text: str) -> tuple[list[str], list[list[str]], str]:
    lines = text.splitlines()
    header = lines[0].split(";") if lines else []
    return header, [line.split(";") for line in lines[1:]], "\n" if text.endswith("\n") else ""


def _csv_join(header: list[str], rows: list[list[str]], tail: str) -> str:
    return "\n".join([";".join(header)] + [";".join(row) for row in rows]) + tail


def csv_column(text: str, column: str, old: str, new: str,
               listed: bool = False, place: str = "") -> Edit:
    """Podmiana wartości w jednej kolumnie. ``listed`` = komórka jest listą po przecinku."""
    header, rows, tail = _csv_rows(text)
    if column not in header:
        return text, 0
    index, hits = header.index(column), 0
    for row in rows:
        if index >= len(row):
            continue
        cell = row[index]
        if place:
            updated = _rename_place_value(cell, place, old, new)
        elif listed:
            parts = [new if part == old else part for part in cell.split(",")]
            updated = ",".join(parts)
        else:
            updated = new if cell == old else cell
        if updated != cell:
            row[index] = updated
            hits += 1
    return (_csv_join(header, rows, tail), hits) if hits else (text, 0)


def csv_column_values(text: str, column: str, listed: bool = False,
                      place: str = "") -> dict[str, set[str]]:
    header, rows, _ = _csv_rows(text)
    if column not in header:
        return {}
    index = header.index(column)
    out: dict[str, set[str]] = {}
    for row in rows:
        if index >= len(row) or not row[index]:
            continue
        cell = row[index]
        if place:
            for kind, values in _place_values(cell).items():
                out.setdefault(kind, set()).update(values)
        else:
            out.setdefault("", set()).update(cell.split(",") if listed else [cell])
    return out


# --- TOML: edycja tekstowa, żeby komentarze i wyrównanie przeżyły ---

def toml_section_key(text: str, section: str, old: str, new: str) -> Edit:
    """Klucz wewnątrz sekcji ``[section]``, z zachowaniem kolumny znaku ``=``."""
    lines, current, hits = text.splitlines(keepends=True), "", 0
    for i, line in enumerate(lines):
        header = re.match(r"\s*\[([^\]]+)\]", line)
        if header:
            current = header.group(1)
            continue
        if current != section:
            continue
        match = re.match(rf"^(\s*)({re.escape(old)})( *)=", line)
        if not match:
            continue
        indent, pad = match.group(1), match.group(3)
        keep = max(1, len(old) + len(pad) - len(new))
        lines[i] = f"{indent}{new}{' ' * keep}=" + line[match.end():]
        hits += 1
    return ("".join(lines), hits) if hits else (text, 0)


def toml_section_keys(text: str, section: str) -> set[str]:
    out, current = set(), ""
    for line in text.splitlines():
        header = re.match(r"\s*\[([^\]]+)\]", line)
        if header:
            current = header.group(1)
            continue
        match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*) *=", line)
        if match and current == section:
            out.add(match.group(1))
    return out


def toml_at_value(text: str, kind: str, old: str, new: str) -> Edit:
    """Cel kroku rutyny: ``at = "route:NAZWA"`` albo ``at = "location:MAPA:miejsce"``."""
    hits = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal hits
        prefix, value = match.group(2), match.group(3)
        if prefix == "route" and kind == INSTANCE and value == old:
            updated = new
        elif prefix == "location" and kind in (MAP, PLACE):
            updated = _rename_place_value(value, kind, old, new)
        else:
            return match.group(0)
        if updated == value:
            return match.group(0)
        hits += 1
        return f'{match.group(1)}"{prefix}:{updated}"'

    pattern = re.compile(r'(\bat\s*=\s*)"(route|location):([^"]*)"')
    return pattern.sub(replace, text), hits


def toml_at_values(text: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for prefix, value in re.findall(r'\bat\s*=\s*"(route|location):([^"]*)"', text):
        if prefix == "route":
            out.setdefault(INSTANCE, set()).add(value)
        else:
            for kind, values in _place_values(value).items():
                out.setdefault(kind, set()).update(values)
    return out


# ---------------------------------------------------------------------------
# Uchwyty plików - jeden na rolę pliku, nie na rozszerzenie
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Source:
    """Jedno źródło z manifestu: gdzie szukać plików i co w nich siedzi."""

    glob: str                                        # względem `REPO_ROOT`
    what: str                                        # opis dla człowieka i dla `--list`
    edit: Callable[[str, str, str, str], Edit]       # (tekst, rodzaj, stara, nowa)
    scan: Callable[[str], dict[str, set[str]]]       # tekst -> rodzaj -> istniejące klucze

    def paths(self) -> list[Path]:
        return sorted(REPO_ROOT.glob(self.glob))


def _edit_tmx(text: str, kind: str, old: str, new: str) -> Edit:
    hits = 0
    layers = {INSTANCE: ("spawn_points", "waypoints"), ENTRY_POINT: ("entry_points",),
              PLACE: ("places",), MAP: ("interactions",), CHEST: ("interactions",)}
    for layer in layers.get(kind, ()):
        text, count = xml_object_name(text, layer, old, new)
        hits += count
    props = {MAP: ("to_map",), CHARACTER: ("model_name",),
             ENTRY_POINT: ("destination_entry_point", "return_entry_point")}
    for prop in props.get(kind, ()):
        text, count = xml_property(text, prop, old, new)
        hits += count
    return text, hits


def _scan_tmx(text: str) -> dict[str, set[str]]:
    return {
        INSTANCE: xml_object_names(text, "spawn_points") | xml_object_names(text, "waypoints"),
        ENTRY_POINT: (xml_object_names(text, "entry_points")
                      | xml_property_values(text, "destination_entry_point")
                      | xml_property_values(text, "return_entry_point")),
        PLACE: xml_object_names(text, "places"),
        MAP: xml_property_values(text, "to_map"),
        CHARACTER: xml_property_values(text, "model_name"),
    }


def _edit_tsx(text: str, kind: str, old: str, new: str) -> Edit:
    if kind != CHARACTER:
        return text, 0
    text, hits = xml_property(text, "model_name", old, new)
    text, more = tsx_tile_type(text, old, new)
    return text, hits + more


def _scan_tsx(text: str) -> dict[str, set[str]]:
    return {CHARACTER: xml_property_values(text, "model_name") | tsx_tile_types(text)}


def _edit_characters_csv(text: str, kind: str, old: str, new: str) -> Edit:
    hits = 0
    if kind == CHARACTER:
        text, hits = csv_column(text, "key", old, new)
    elif kind in (MAP, PLACE):
        for column in PLACE_COLUMNS:
            text, count = csv_column(text, column, old, new, place=kind)
            hits += count
    return text, hits


def _scan_characters_csv(text: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {CHARACTER: csv_column_values(text, "key").get("", set())}
    for column in PLACE_COLUMNS:
        for kind, values in csv_column_values(text, column, place=MAP).items():
            out.setdefault(kind, set()).update(values)
    return out


def _edit_chests_csv(text: str, kind: str, old: str, new: str) -> Edit:
    if kind != CHEST:
        return text, 0
    text, hits = csv_column(text, "key", old, new)
    text, more = csv_column(text, "name", old, new)
    return text, hits + more


def _scan_chests_csv(text: str) -> dict[str, set[str]]:
    return {CHEST: csv_column_values(text, "key").get("", set())}


def _edit_maze_csv(text: str, kind: str, old: str, new: str) -> Edit:
    columns = {CHARACTER: (("monsters_list", True), ("boss_monster", False)),
               CHEST: (("small_chest_template", False), ("big_chest_template", False))}
    hits = 0
    for column, listed in columns.get(kind, ()):
        text, count = csv_column(text, column, old, new, listed=listed)
        hits += count
    return text, hits


def _scan_maze_csv(text: str) -> dict[str, set[str]]:
    characters = (csv_column_values(text, "monsters_list", listed=True).get("", set())
                  | csv_column_values(text, "boss_monster").get("", set()))
    chests = (csv_column_values(text, "small_chest_template").get("", set())
              | csv_column_values(text, "big_chest_template").get("", set()))
    return {CHARACTER: characters, CHEST: chests}


def _edit_audio_toml(text: str, kind: str, old: str, new: str) -> Edit:
    return toml_section_key(text, "music", old, new) if kind == MAP else (text, 0)


def _scan_audio_toml(text: str) -> dict[str, set[str]]:
    return {MAP: toml_section_keys(text, "music") - set(SPECIAL_MUSIC_KEYS)}


def _edit_routines_toml(text: str, kind: str, old: str, new: str) -> Edit:
    return toml_at_value(text, kind, old, new) if kind in (INSTANCE, MAP, PLACE) else (text, 0)


def _edit_locale_toml(text: str, kind: str, old: str, new: str) -> Edit:
    return toml_section_key(text, "map", old, new) if kind == MAP else (text, 0)


def _scan_locale_toml(text: str) -> dict[str, set[str]]:
    return {MAP: toml_section_keys(text, "map")}


def _edit_config_json(text: str, kind: str, old: str, new: str) -> Edit:
    data = json.loads(text)
    hits = 0

    def rename_section(section: str) -> None:
        nonlocal hits
        block = data.get(section)
        if isinstance(block, dict) and old in block:
            data[section] = {(new if key == old else key): value for key, value in block.items()}
            hits += 1

    if kind == CHARACTER:
        rename_section("characters")
        for row in (data.get("maze_configs") or {}).values():
            if row.get("boss_monster") == old:
                row["boss_monster"] = new
                hits += 1
            monsters = row.get("monsters_list")
            if isinstance(monsters, list) and old in monsters:
                row["monsters_list"] = [new if m == old else m for m in monsters]
                hits += 1
    elif kind == CHEST:
        rename_section("chests")
        for key, chest in (data.get("chests") or {}).items():
            if chest.get("name") == old:
                chest["name"] = new
                hits += 1
        for row in (data.get("maze_configs") or {}).values():
            for column in ("small_chest_template", "big_chest_template"):
                if row.get(column) == old:
                    row[column] = new
                    hits += 1
    elif kind in (MAP, PLACE):
        for character in (data.get("characters") or {}).values():
            for column in PLACE_COLUMNS:
                value = character.get(column)
                if not isinstance(value, str):
                    continue
                updated = _rename_place_value(value, kind, old, new)
                if updated != value:
                    character[column] = updated
                    hits += 1

    if not hits:
        return text, 0
    # dokładnie ten kształt zapisuje `import_entities.py` - inaczej pierwszy import
    # po rename'ie wyprodukowałby diff całego pliku
    return json.dumps(data, indent=4, ensure_ascii=False) + "\n", hits


def _scan_config_json(text: str) -> dict[str, set[str]]:
    data = json.loads(text)
    characters = set(data.get("characters") or {})
    chests = set(data.get("chests") or {})
    out: dict[str, set[str]] = {CHARACTER: characters, CHEST: chests}
    for character in (data.get("characters") or {}).values():
        for column in PLACE_COLUMNS:
            value = character.get(column)
            if isinstance(value, str) and value:
                for kind, values in _place_values(value).items():
                    out.setdefault(kind, set()).update(values)
    return out


#: **Manifest źródeł.** Pilnowany przez `tests/test_rename_entity.py` (D17):
#: plik danych, którego nie obejmuje żaden glob, musi być wpisany na listę
#: `UNTOUCHED_SOURCES` z powodem - inaczej test na CI świeci na czerwono.
SOURCES: tuple[Source, ...] = (
    Source("project/assets/NinjaAdventure/maps/**/*.tmx",
           "mapy gry: nazwy obiektów w warstwach + to_map/model_name/*entry_point",
           _edit_tmx, _scan_tmx),
    Source("project/assets/MazeTileset/*.tmx",
           "szablony labiryntu: te same własności, mapy powstają z nich w locie",
           _edit_tmx, _scan_tmx),
    Source("project/assets/NinjaAdventure/maps/tilesets/*.tsx",
           "tilesety map: `model_name` i `type` na kaflu",
           _edit_tsx, _scan_tsx),
    Source("project/assets/MazeTileset/*.tsx",
           "tilesety labiryntu: `model_name` i `type` na kaflu",
           _edit_tsx, _scan_tsx),
    Source("project/config_model/characters.csv",
           "postacie: kolumna `key` + kolumny miejsc (`MAPA:miejsce`)",
           _edit_characters_csv, _scan_characters_csv),
    Source("project/config_model/chests.csv",
           "skrzynie: kolumny `key` i `name`",
           _edit_chests_csv, _scan_chests_csv),
    Source("project/config_model/maze_configs.csv",
           "poziomy labiryntu: obsada potworów i szablony skrzyń",
           _edit_maze_csv, _scan_maze_csv),
    Source("project/config_model/audio.toml",
           "manifest audio: klucze sekcji [music] to nazwy map",
           _edit_audio_toml, _scan_audio_toml),
    Source("project/config_model/routines.toml",
           "rutyny: cele kroków `route:` i `location:`",
           _edit_routines_toml, toml_at_values),
    Source("project/config_model/config.json",
           "config gry: klucze `characters`/`chests`, obsada labiryntu, miejsca",
           _edit_config_json, _scan_config_json),
    Source("project/assets/locale/*.toml",
           "napisy: klucze sekcji [map] to nazwy map (D12)",
           _edit_locale_toml, _scan_locale_toml),
)

#: Pliki danych, których rename świadomie nie dotyka. Powód jest częścią kontraktu:
#: test z D17 czyta tę listę, więc „nie wiem, co to" nie przejdzie przez CI.
UNTOUCHED_SOURCES: dict[str, str] = {
    "project/config_model/items.csv":
        "klucze przedmiotów - żyją też w warunkach dialogów i questów, poza zakresem C02",
    "project/config_model/config_schema.json":
        "schemat wygenerowany z `config_pydantic.py` - nazwy pól, nie klucze encji",
    "project/config_model/autogenerated_config.json":
        "martwy artefakt po usuniętym w B01 `main.py store` - nikt go nie czyta",
    "project/assets/NinjaAdventure/items/Items.tmx":
        "tileset przedmiotów - klucze przedmiotów, patrz items.csv",
    "project/assets/NinjaAdventure/items/items.tsx":
        "tileset przedmiotów - klucze przedmiotów, patrz items.csv",
    "project/assets/map/grasslands.tmx":
        "prototyp w starszym schemacie (warstwa `exits`), gra go nie ładuje",
    "project/assets/map/map.tmx":
        "prototyp w starszym schemacie, gra go nie ładuje",
    "project/assets/map/small.tmx":
        "prototyp w starszym schemacie, gra go nie ładuje",
    "project/assets/map/water.tsx":
        "tileset graficzny prototypu, zero kluczy encji",
    "project/assets/map/water_bckp.tsx":
        "kopia zapasowa tilesetu graficznego prototypu",
}

#: Katalogi przeszukiwane przez test pokrycia (D17) - każdy plik danych stąd musi
#: być albo objęty globem z `SOURCES`, albo wpisany do `UNTOUCHED_SOURCES`.
DATA_ROOTS = ("project/config_model", "project/assets")
DATA_SUFFIXES = (".tmx", ".tsx", ".csv", ".toml", ".json")


def data_files() -> list[Path]:
    """Wszystkie pliki danych w repo - materiał dla testu pokrycia manifestu."""
    out: list[Path] = []
    for root in DATA_ROOTS:
        out += [path for path in (REPO_ROOT / root).rglob("*")
                if path.is_file() and path.suffix in DATA_SUFFIXES]
    return sorted(out)


def covered_files() -> set[Path]:
    return {path for source in SOURCES for path in source.paths()}


# ---------------------------------------------------------------------------
# Rename
# ---------------------------------------------------------------------------

@dataclass
class Change:
    path: Path
    hits: int
    note: str = ""


def existing_keys() -> dict[str, set[str]]:
    """Co dziś istnieje, per rodzaj - podstawa autodetekcji i flagi ``--list``."""
    out: dict[str, set[str]] = {kind: set() for kind in KINDS}
    for source in SOURCES:
        for path in source.paths():
            for kind, values in source.scan(path.read_text(encoding="utf-8")).items():
                out.setdefault(kind, set()).update(v for v in values if v)
    # mapa istnieje także wtedy, gdy nikt do niej nie prowadzi - plikiem `.tmx`
    out[MAP] |= {path.stem for path in GAME_MAPS_DIR.glob("*.tmx")}
    return out


def detect_kind(old: str) -> str:
    """Rodzaj klucza wywnioskowany z tego, gdzie ta nazwa dziś stoi."""
    matches = [kind for kind, values in existing_keys().items() if old in values]
    if not matches:
        raise SystemExit(f"nie znalazłem '{old}' w żadnym źródle - literówka? "
                         f"(`--list` pokaże, co istnieje)")
    if len(matches) > 1:
        raise SystemExit(f"'{old}' istnieje jako {', '.join(sorted(matches))} - "
                         f"wskaż rodzaj przez --kind")
    return matches[0]


def rename(old: str, new: str, kind: str, dry_run: bool = False) -> list[Change]:
    """Przemianowanie w każdym źródle z manifestu. Zwraca listę zmienionych plików."""
    changes: list[Change] = []
    for source in SOURCES:
        for path in source.paths():
            text = path.read_text(encoding="utf-8")
            updated, hits = source.edit(text, kind, old, new)
            if hits and updated != text:
                if not dry_run:
                    path.write_text(updated, encoding="utf-8")
                changes.append(Change(path, hits))

    if kind == MAP:
        tmx = GAME_MAPS_DIR / f"{old}.tmx"
        if tmx.exists():
            target = GAME_MAPS_DIR / f"{new}.tmx"
            if target.exists():
                raise SystemExit(f"{target.relative_to(REPO_ROOT)} już istnieje - przerywam")
            if not dry_run:
                _move(tmx, target)
            changes.append(Change(tmx, 1, f"-> {target.name}"))
    return changes


def _move(source: Path, target: Path) -> None:
    """`git mv`, żeby historia pliku przeżyła rename; poza repo zwykły `rename`."""
    try:
        subprocess.run(["git", "mv", str(source), str(target)],
                       cwd=REPO_ROOT, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        source.rename(target)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_list() -> None:
    known = existing_keys()
    for kind in KINDS:
        keys = sorted(known[kind])
        print(f"\n{kind} ({len(keys)}):")
        for key in keys:
            print(f"  {key}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Przemianuj klucz encji we wszystkich źródłach naraz (C02, D10).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Rodzaje: " + ", ".join(KINDS))
    parser.add_argument("old", nargs="?", help="obecny klucz")
    parser.add_argument("new", nargs="?", help="nowy klucz")
    parser.add_argument("--kind", choices=KINDS, help="rodzaj klucza (domyślnie wykrywany)")
    parser.add_argument("--dry-run", action="store_true", help="pokaż, nie zapisuj")
    parser.add_argument("--no-validate", action="store_true",
                        help="nie uruchamiaj `validate_world.py` na koniec")
    parser.add_argument("--list", action="store_true", help="wypisz istniejące klucze i wyjdź")
    parser.add_argument("--sources", action="store_true", help="wypisz manifest źródeł i wyjdź")
    args = parser.parse_args(argv)

    if args.list:
        _print_list()
        return 0
    if args.sources:
        for source in SOURCES:
            print(f"{source.glob}\n    {source.what}")
        print("\nświadomie nietykane:")
        for path, why in UNTOUCHED_SOURCES.items():
            print(f"{path}\n    {why}")
        return 0
    if not args.old or not args.new:
        parser.error("podaj starą i nową nazwę (albo --list / --sources)")
    if args.old == args.new:
        parser.error("stara i nowa nazwa są takie same")

    kind = args.kind or detect_kind(args.old)
    changes = rename(args.old, args.new, kind, dry_run=args.dry_run)

    head = "DRY RUN: " if args.dry_run else ""
    print(f"{head}{kind}: {args.old} -> {args.new}")
    if not changes:
        print("  nic nie znalazłem - zły rodzaj klucza?")
        return 1
    for change in changes:
        print(f"  {change.path.relative_to(REPO_ROOT)}  ({change.hits}) {change.note}".rstrip())
    print(f"  razem: {sum(c.hits for c in changes)} trafień w {len(changes)} plikach")

    if kind in (INSTANCE, CHEST):
        print("  UWAGA: stan tej encji w istniejących zapisach jest kluczowany starą "
              "nazwą (O1) - zapisy sprzed rename'u dostaną wartości domyślne")

    if args.dry_run or args.no_validate:
        return 0
    print()
    return subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "validate_world.py")],
                          cwd=REPO_ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
