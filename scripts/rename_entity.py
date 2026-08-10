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

    just rename-entity Village BLUNDERHAVEN                # rodzaj wykryty automatycznie
    just rename-entity Snake_01 SNAKE --kind instance
    just rename-entity LOST_CORK_TAVERN:tables dining_tables   # tylko na tej mapie
    just rename-entity Village BLUNDERHAVEN --dry-run
    python3 scripts/rename_entity.py --list                # co dziś istnieje, per rodzaj

Rodzaje kluczy (``--kind``):

``character``    klucz modelu z `config.json`/`characters.csv` (``BARMAN_ABSINTHRAYNER``)
``map``          klucz mapy = stem pliku `.tmx` (``LOST_CORK_TAVERN``, ``MAZE_01``)
``instance``     nazwa obiektu w warstwie `spawn_points` i krzywej `waypoints` (``FISH_RED_01``)
``chest``        klucz skrzyni z `chests.csv` (``MAZE_01_BIG_CHEST``)
``entry_point``  nazwa obiektu w warstwie `entry_points` (``LOST_CORK_TAVERN_DOOR``)
``place``        nazwa obiektu w warstwie `places`, zawsze małymi (``house_bart``)
``item``         klucz przedmiotu z `items.csv` (``life_pot``, ``PHOENIX_FEATHER``)

**Zasięg nazwy.** `character`, `map`, `chest` i `item` są kluczami globalnymi - jeden
w całej grze. `instance`, `entry_point` i `place` są unikalne **tylko w obrębie jednej
mapy**: ładowarka trzyma je w słownikach per scena, więc dwie tawerny mogą mieć swój
`bar` i swoje `Door`. Stąd obowiązkowy prefiks mapy w odwołaniach do miejsc (D3)
i stąd `--list` dopisuje przy nich mapę, która je definiuje.

Dla tych trzech rodzajów starą nazwę podaje się więc **z zakresem albo bez**::

    just rename-entity LOST_CORK_TAVERN:tables dining_tables   # jedna mapa
    just rename-entity tables dining_tables                    # wszystkie mapy naraz

Bez zakresu skrypt najpierw ostrzega, na ilu mapach ta nazwa stoi. Zakres pilnuje
trzech rzeczy naraz: nazwy obiektu w `.tmx` tylko tej mapy, prefiksu w komórkach
miejsc (`LOST_CORK_TAVERN:tables`, nie `BLUNDERHAVEN:tables`) oraz - dla punktów
wejścia - **`to_map` obiektu, który się do nich odwołuje**, bo `destination_entry_point`
nazywa punkt na mapie docelowej, a nie na tej, na której stoją drzwi.

Czego skrypt świadomie NIE rusza:

- **zapisów gry** - stan NPC-a i skrzyni jest kluczowany nazwą obiektu (O1), więc
  rename kasuje ten stan. To nie jest do naprawienia skryptem: polityka jest w D9
  (podbicie wersji zapisu = jawna odmowa wczytania starego pliku).
- **kodu** - mapa startowa jest w `settings.START_MAP`, a klucz gracza
  w `settings.PLAYER_CONFIG_KEY`, właśnie po to, żeby rename danych nie wymagał
  edycji Pythona. Nowa stała w kodzie = nowy wiersz w tej liście, nie nowy glob.
- **dokumentów w Obsidianie** - `doc/PL/`, `doc/EN/`. Klucz encji jest tam aliasem
  we frontmatterze, bywa też nazwą pliku, a treść jest autora - skrypt zamiast
  edytować **wypisuje na koniec listę plików z `doc/`, w których stara nazwa jeszcze
  stoi**. Bez ich poprawienia pierwszy `just import-*` po rename'ie cofnie zmianę
  w `config.json` (dotyczy zwłaszcza `item`: klucze przedmiotów siedzą w warunkach
  `has_item("…")` w dialogach i questach).

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

CHARACTER, MAP, INSTANCE, CHEST, ENTRY_POINT, PLACE, ITEM = (
    "character", "map", "instance", "chest", "entry_point", "place", "item",
)
KINDS = (CHARACTER, MAP, INSTANCE, CHEST, ENTRY_POINT, PLACE, ITEM)

#: Rodzaje kluczy unikalne **tylko w obrębie jednej mapy**, nie w całej grze: ładowarka
#: trzyma je w słownikach per scena (`scene.entry_points`, `scene.places`), więc dwie
#: tawerny mogą mieć swój `bar`. Dlatego odwołanie do miejsca musi nosić prefiks mapy
#: (D3) i dlatego `--list` pokazuje przy nich, z której mapy pochodzą.
MAP_SCOPED_KINDS = (INSTANCE, ENTRY_POINT, PLACE)

#: Etykieta pochodzenia dla szablonu labiryntu. Poziomy `MAZE_01`…`MAZE_0N` powstają
#: w locie z jednego pliku, więc wypisywanie ich po kolei byłoby powtórzeniem.
MAZE_ORIGIN = "MAZE_*"

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


def _rename_place_value(value: str, kind: str, old: str, new: str, scope: str = "") -> str:
    """Podmiana w komórce ``MAPA:miejsce`` - osobno prefiks mapy, osobno miejsce.

    ``scope`` ogranicza zmianę miejsca do jednej mapy: `LOST_CORK_TAVERN:tables`
    zostawia `BLUNDERHAVEN:tables` w spokoju. Komórka bez prefiksu jest wtedy
    świadomie pomijana - skoro nie wiadomo, o którą mapę chodzi, zgadywanie byłoby
    dokładnie tym, przed czym broni reguła 15.
    """
    map_key, place = _split_place(value.strip())
    if kind == MAP and map_key == old:
        map_key = new
    elif kind == PLACE and place == old and (not scope or map_key == scope):
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


def xml_object_property(text: str, prop: str, old: str, new: str,
                        where: "Callable[[dict[str, str]], bool]") -> Edit:
    """Jak :func:`xml_property`, ale decyzję podejmuje się **per obiekt**.

    Potrzebne, gdy o zakresie zmiany mówi *inna własność tego samego obiektu*:
    `destination_entry_point` wskazuje punkt na mapie z `to_map`, więc przy rename'ie
    ograniczonym do jednej mapy trzeba przeczytać oba pola naraz. Zwykła podmiana po
    całym pliku zmieniłaby też drzwi prowadzące gdzie indziej, a mające punkt wejścia
    o tej samej nazwie (`Door` istnieje na trzech mapach).
    """
    hits = 0
    out: list[str] = []
    cursor = 0
    # Dwa warianty, bo `.*?` zatrzymałoby się na pierwszym `/>` - a to jest `/>`
    # pierwszej WŁASNOŚCI, nie koniec obiektu. Blok urwany w tym miejscu nie zawiera
    # `to_map`, więc predykat dostawał pusty słownik i przepuszczał wszystko.
    for match in re.finditer(r"<object\b[^>]*/>|<object\b[^>]*>.*?</object>", text, re.S):
        block = match.group(0)
        props = dict(re.findall(r'<property\b[^>]*?\bname="([^"]*)"[^>]*?\bvalue="([^"]*)"', block))
        out.append(text[cursor:match.start()])
        if where(props):
            block, count = xml_property(block, prop, old, new)
            hits += count
        out.append(block)
        cursor = match.end()
    out.append(text[cursor:])
    return "".join(out), hits


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
               listed: bool = False, place: str = "", scope: str = "") -> Edit:
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
            updated = _rename_place_value(cell, place, old, new, scope)
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


def toml_at_value(text: str, ren: "Rename") -> Edit:
    """Cel kroku rutyny: ``at = "route:NAZWA"`` albo ``at = "location:MAPA:miejsce"``.

    ``resolve_at`` przyjmuje obie formy z prefiksem mapy i bez niego, więc przy rename'ie
    ograniczonym do jednej mapy goła nazwa (`route:ROB`) jest niejednoznaczna. Zamiast
    zgadywać, zostawiamy ją nietkniętą - wołający wypisze ją jako rzecz do sprawdzenia.
    """
    hits = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal hits
        prefix, value = match.group(2), match.group(3)
        if prefix == "route" and ren.kind == INSTANCE:
            map_key, route = _split_place(value)
            if route != ren.old or not ren.place_scope_ok(map_key):
                return match.group(0)
            updated = f"{map_key}:{ren.new}" if map_key else ren.new
        elif prefix == "location" and ren.kind in (MAP, PLACE):
            updated = _rename_place_value(value, ren.kind, ren.old, ren.new, ren.scope)
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
class Rename:
    """Jedno zadanie: co, na co i w jakim zakresie.

    ``scope`` to klucz mapy albo pusty string. Rodzaje zależne od mapy
    (:data:`MAP_SCOPED_KINDS`) mogą powtarzać nazwę na wielu mapach - `tables` stoi
    i w tawernie, i w domu w wiosce - więc rename bez zakresu ruszyłby oba naraz.
    Zakres podaje się tak samo, jak zapisuje się odwołanie w danych: ``MAPA:nazwa``.
    """

    kind: str
    old: str
    new: str
    scope: str = ""

    def covers(self, file_map: str) -> bool:
        """Czy plik należący do mapy *file_map* jest w zakresie tego rename'u.

        Plik spoza map (``file_map == ""``: CSV, TOML, config) jest zawsze w zakresie -
        o jego wierszach rozstrzyga prefiks w samej wartości, nie przynależność pliku.
        """
        return not self.scope or not file_map or file_map == self.scope

    def targets(self, map_key: str) -> bool:
        """Czy odwołanie celujące w mapę *map_key* jest w zakresie.

        Inaczej niż :meth:`covers`: tu pusta wartość znaczy „nie wiadomo, dokąd",
        więc przy zawężonym rename'ie taki obiekt zostaje nietknięty zamiast przejść.
        """
        return not self.scope or map_key == self.scope

    def place_scope_ok(self, map_prefix: str) -> bool:
        """Czy komórka ``MAPA:miejsce`` z takim prefiksem jest w zakresie."""
        return not self.scope or map_prefix == self.scope


@dataclass(frozen=True)
class Source:
    """Jedno źródło z manifestu: gdzie szukać plików i co w nich siedzi."""

    glob: str                                        # względem `REPO_ROOT`
    what: str                                        # opis dla człowieka i dla `--list`
    #: (tekst pliku, zadanie, klucz mapy do której plik należy) -> (nowy tekst, trafienia)
    edit: Callable[[str, Rename, str], Edit]
    scan: Callable[[str], dict[str, set[str]]]       # tekst -> rodzaj -> istniejące klucze
    #: Tylko klucze **zdefiniowane** w tym pliku, w odróżnieniu od tych, do których
    #: plik się jedynie odwołuje. `BLUNDERHAVEN.tmx` odwołuje się do punktu `Entry`,
    #: ale definiuje go szablon labiryntu - i to on jest odpowiedzią na pytanie
    #: „z jakiej mapy pochodzi ten klucz". Brak = wszystko z `scan` to definicje.
    defines: Callable[[str], dict[str, set[str]]] | None = None

    def paths(self) -> list[Path]:
        return sorted(REPO_ROOT.glob(self.glob))

    def definitions(self, text: str) -> dict[str, set[str]]:
        return self.defines(text) if self.defines else self.scan(text)


def _edit_tmx(text: str, ren: Rename, file_map: str) -> Edit:
    hits = 0
    layers = {INSTANCE: ("spawn_points", "waypoints"), ENTRY_POINT: ("entry_points",),
              PLACE: ("places",), MAP: ("interactions",), CHEST: ("interactions",)}
    # Nazwa obiektu to DEFINICJA klucza, więc zakres rozstrzyga sama przynależność
    # pliku: `LOST_CORK_TAVERN:tables` nie ma prawa ruszyć `tables` w innym `.tmx`.
    if ren.covers(file_map):
        for layer in layers.get(ren.kind, ()):
            text, count = xml_object_name(text, layer, ren.old, ren.new)
            hits += count

    if ren.kind == MAP:
        text, count = xml_property(text, "to_map", ren.old, ren.new)
        hits += count
    elif ren.kind == CHARACTER:
        text, count = xml_property(text, "model_name", ren.old, ren.new)
        hits += count
    elif ren.kind == ENTRY_POINT:
        # `destination_entry_point` nazywa punkt na mapie DOCELOWEJ, więc o zakresie
        # decyduje `to_map` tego samego obiektu, a nie plik, w którym stoi.
        text, count = xml_object_property(
            text, "destination_entry_point", ren.old, ren.new,
            where=lambda props: ren.targets(props.get("to_map", "")))
        hits += count
        # `return_entry_point` nazywa punkt na mapie, na której stoją te drzwi
        if ren.covers(file_map):
            text, count = xml_property(text, "return_entry_point", ren.old, ren.new)
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


def _defines_tmx(text: str) -> dict[str, set[str]]:
    """Klucze, które ta mapa *definiuje* - obiekty w swoich warstwach.

    `to_map`, `destination_entry_point` i spółka to odwołania do cudzych kluczy;
    gdyby liczyły się jako pochodzenie, `--list` twierdziłby, że punkt `Entry`
    „pochodzi" z wioski tylko dlatego, że prowadzą do niego jej drzwi.
    """
    return {
        INSTANCE: xml_object_names(text, "spawn_points"),
        ENTRY_POINT: xml_object_names(text, "entry_points"),
        PLACE: xml_object_names(text, "places"),
    }


def _edit_tsx(text: str, ren: Rename, file_map: str) -> Edit:
    if ren.kind != CHARACTER:
        return text, 0
    text, hits = xml_property(text, "model_name", ren.old, ren.new)
    text, more = tsx_tile_type(text, ren.old, ren.new)
    return text, hits + more


def _scan_tsx(text: str) -> dict[str, set[str]]:
    return {CHARACTER: xml_property_values(text, "model_name") | tsx_tile_types(text)}


def _scan_maze_template(text: str) -> dict[str, set[str]]:
    """Szablon labiryntu ma REALNE punkty wejścia i ATRAPY reszty.

    `build_tileset_map_from_maze` nadpisuje w locie `to_map`, `destination_entry_point`
    i `return_entry_point` na obiektach `Return`/`Stairs` - w pliku stoją tam wartości
    zastępcze (`to_map="Return"`, `return_entry_point="0"`), które nigdy nie trafiają
    do gry. Wciąganie ich do listy kluczy podpowiadało encje, których nie ma: „Return"
    jako mapa, „0" i „Stairs" jako punkty wejścia.

    Warstwa `entry_points` jest przeciwieństwem: `Entry` i `Re-Entry` to jedyne prawdziwe
    punkty wejścia poziomu labiryntu i to na nie celują drzwi z map statycznych.
    """
    return {ENTRY_POINT: xml_object_names(text, "entry_points")}


def _edit_characters_csv(text: str, ren: Rename, file_map: str) -> Edit:
    hits = 0
    if ren.kind == CHARACTER:
        text, hits = csv_column(text, "key", ren.old, ren.new)
    elif ren.kind == ITEM:
        text, hits = csv_column(text, "items", ren.old, ren.new, listed=True)
    elif ren.kind in (MAP, PLACE):
        for column in PLACE_COLUMNS:
            text, count = csv_column(text, column, ren.old, ren.new,
                                     place=ren.kind, scope=ren.scope)
            hits += count
    return text, hits


def _scan_characters_csv(text: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {
        CHARACTER: csv_column_values(text, "key").get("", set()),
        ITEM: csv_column_values(text, "items", listed=True).get("", set()),
    }
    for column in PLACE_COLUMNS:
        for kind, values in csv_column_values(text, column, place=MAP).items():
            out.setdefault(kind, set()).update(values)
    return out


def _edit_chests_csv(text: str, ren: Rename, file_map: str) -> Edit:
    hits = 0
    if ren.kind == CHEST:
        text, hits = csv_column(text, "key", ren.old, ren.new)
        text, more = csv_column(text, "name", ren.old, ren.new)
        hits += more
    elif ren.kind == ITEM:
        for column in ("items", "random_items"):
            text, count = csv_column(text, column, ren.old, ren.new, listed=True)
            hits += count
    return text, hits


def _scan_chests_csv(text: str) -> dict[str, set[str]]:
    items = (csv_column_values(text, "items", listed=True).get("", set())
             | csv_column_values(text, "random_items", listed=True).get("", set()))
    return {CHEST: csv_column_values(text, "key").get("", set()), ITEM: items}


def _edit_items_csv(text: str, ren: Rename, file_map: str) -> Edit:
    return csv_column(text, "key", ren.old, ren.new) if ren.kind == ITEM else (text, 0)


def _scan_items_csv(text: str) -> dict[str, set[str]]:
    return {ITEM: csv_column_values(text, "key").get("", set())}


def _edit_items_tsx(text: str, ren: Rename, file_map: str) -> Edit:
    """Kafle w `items/items.tsx` niosą klucz przedmiotu we własności `item_name`.

    To one stawiają przedmioty na mapie: `load_items` czyta `item_name` z kafla
    i woła `conf.items[name]`, więc kafel z nieistniejącym kluczem wywala grę
    `KeyError`-em przy wczytaniu mapy - dokładnie ta sama mina, co zepsute
    `model_name` w `CharacterTileset.tsx` (O8).
    """
    return xml_property(text, "item_name", ren.old, ren.new) if ren.kind == ITEM else (text, 0)


def _scan_items_tsx(text: str) -> dict[str, set[str]]:
    return {ITEM: xml_property_values(text, "item_name")}


def _edit_maze_csv(text: str, ren: Rename, file_map: str) -> Edit:
    columns = {CHARACTER: (("monsters_list", True), ("boss_monster", False)),
               CHEST: (("small_chest_template", False), ("big_chest_template", False))}
    hits = 0
    for column, listed in columns.get(ren.kind, ()):
        text, count = csv_column(text, column, ren.old, ren.new, listed=listed)
        hits += count
    return text, hits


def _scan_maze_csv(text: str) -> dict[str, set[str]]:
    characters = (csv_column_values(text, "monsters_list", listed=True).get("", set())
                  | csv_column_values(text, "boss_monster").get("", set()))
    chests = (csv_column_values(text, "small_chest_template").get("", set())
              | csv_column_values(text, "big_chest_template").get("", set()))
    return {CHARACTER: characters, CHEST: chests}


def _edit_audio_toml(text: str, ren: Rename, file_map: str) -> Edit:
    return toml_section_key(text, "music", ren.old, ren.new) if ren.kind == MAP else (text, 0)


def _scan_audio_toml(text: str) -> dict[str, set[str]]:
    return {MAP: toml_section_keys(text, "music") - set(SPECIAL_MUSIC_KEYS)}


def _edit_routines_toml(text: str, ren: Rename, file_map: str) -> Edit:
    return toml_at_value(text, ren) if ren.kind in (INSTANCE, MAP, PLACE) else (text, 0)


def _edit_locale_toml(text: str, ren: Rename, file_map: str) -> Edit:
    return toml_section_key(text, "map", ren.old, ren.new) if ren.kind == MAP else (text, 0)


def _scan_locale_toml(text: str) -> dict[str, set[str]]:
    return {MAP: toml_section_keys(text, "map")}


#: ``has_item("klucz")`` w warunkach dialogów i questów - wzorzec powtórzony
#: za `validate_world._condition_items`, żeby jedno i drugie widziało to samo.
_HAS_ITEM_RE = re.compile(r'(has_item\(\s*")([^"]+)("\s*\))')

#: Pola treści, których **wartością** jest klucz przedmiotu. Węzeł dialogu potrafi
#: dać graczowi przedmioty (`"items": [...]` w efekcie ResultSink), a nagroda questa
#: nazywa jeden (`"item": "..."`). Bez tej listy rename przedmiotu przechodził przez
#: warunki `has_item(...)`, a mijał to, co ten warunek sprawdza.
_ITEM_LIST_FIELDS = ("items", "random_items")
_ITEM_VALUE_FIELDS = ("item",)


def _rename_item_in_content(node: object, old: str, new: str,
                            field_name: str = "") -> tuple[object, int]:
    """Podmiana klucza przedmiotu w treści dialogów i questów.

    Dwa kształty, bo klucz występuje tam na dwa sposoby: jako fragment mini-DSL
    wewnątrz stringa (``has_item("KLUCZ")``) oraz jako wartość pola z listy powyżej.
    Zwykły string spoza tych pól zostaje nietknięty - to proza dla gracza.
    """
    hits = 0
    if isinstance(node, str):
        if field_name in _ITEM_LIST_FIELDS + _ITEM_VALUE_FIELDS and node == old:
            return new, 1

        def swap(match: re.Match[str]) -> str:
            nonlocal hits
            if match.group(2) != old:
                return match.group(0)
            hits += 1
            return f"{match.group(1)}{new}{match.group(3)}"
        return _HAS_ITEM_RE.sub(swap, node), hits
    if isinstance(node, dict):
        out_dict: dict[str, object] = {}
        for key, value in node.items():
            out_dict[key], count = _rename_item_in_content(value, old, new, key)
            hits += count
        return out_dict, hits
    if isinstance(node, list):
        out_list: list[object] = []
        for value in node:
            # lista dziedziczy nazwę pola, w którym stoi - inaczej element `"items"`
            # byłby nieodróżnialny od dowolnego innego stringa
            updated, count = _rename_item_in_content(value, old, new, field_name)
            out_list.append(updated)
            hits += count
        return out_list, hits
    return node, 0


#: Klucz encji **wewnątrz warunku barka** (H01/D1) - argument predykatu, per rodzaj.
#: Barki to trzecia treść z warunkami, obok dialogów i questów, ale jedyna, która
#: pyta o mapę (`on_map`), więc rename mapy mijał ją, dopóki tej tabeli nie było.
#: Rodzaj, którego tu nie ma, po prostu nie występuje w warunkach barków.
_BARK_CONDITION_RE: dict[str, re.Pattern[str]] = {
    MAP: re.compile(r'(on_map\(\s*")([^"]+)("\s*\))'),
    CHARACTER: re.compile(r'(visited\(\s*")([^"]+)("\s*,)'),
    ITEM: re.compile(r'((?:has_item|item_count)\(\s*")([^"]+)("\s*\))'),
}


def _rename_in_barks(data: dict, kind: str, old: str, new: str) -> int:
    """Klucz encji w sekcji `barks`: właściciel puli i argumenty w warunkach.

    Właścicielem wpisu jest klucz postaci **albo** nazwa wspólnej puli (D2) - dla
    runtime'u to ta sama rzecz, więc rename postaci musi ruszyć też ten klucz.
    """
    barks = data.get("barks")
    if not isinstance(barks, dict):
        return 0
    hits = 0
    if kind == CHARACTER and old in barks:
        data["barks"] = {(new if key == old else key): value for key, value in barks.items()}
        barks = data["barks"]
        hits += 1

    pattern = _BARK_CONDITION_RE.get(kind)
    if pattern is None:
        return hits

    def swap(match: re.Match[str]) -> str:
        nonlocal hits
        if match.group(2) != old:
            return match.group(0)
        hits += 1
        return f"{match.group(1)}{new}{match.group(3)}"

    for entries in barks.values():
        for entry in entries or ():
            condition = entry.get("condition")
            if isinstance(condition, str) and condition:
                entry["condition"] = pattern.sub(swap, condition)
    return hits


def _edit_config_json(text: str, ren: Rename, file_map: str) -> Edit:
    data = json.loads(text)
    kind, old, new = ren.kind, ren.old, ren.new
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
                updated = _rename_place_value(value, kind, old, new, ren.scope)
                if updated != value:
                    character[column] = updated
                    hits += 1
    elif kind == ITEM:
        rename_section("items")
        for owner in list((data.get("characters") or {}).values()) \
                + list((data.get("chests") or {}).values()):
            for column in ("items", "random_items"):
                values = owner.get(column)
                if isinstance(values, list) and old in values:
                    owner[column] = [new if v == old else v for v in values]
                    hits += 1
        # Treść (dialogi i questy) trzyma klucz przedmiotu w warunkach `has_item(...)`,
        # w nagrodach questów i w efektach węzłów dialogu - patrz `_rename_item_in_content`.
        for section in ("dialogs", "quests"):
            if section in data:
                data[section], count = _rename_item_in_content(data[section], old, new)
                hits += count

    hits += _rename_in_barks(data, kind, old, new)

    if not hits:
        return text, 0
    # dokładnie ten kształt zapisuje `import_entities.py` - inaczej pierwszy import
    # po rename'ie wyprodukowałby diff całego pliku
    return json.dumps(data, indent=4, ensure_ascii=False) + "\n", hits


def _scan_config_json(text: str) -> dict[str, set[str]]:
    data = json.loads(text)
    characters = set(data.get("characters") or {})
    chests = set(data.get("chests") or {})
    out: dict[str, set[str]] = {CHARACTER: characters, CHEST: chests,
                                ITEM: set(data.get("items") or {})}
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
           _edit_tmx, _scan_tmx, defines=_defines_tmx),
    Source("project/assets/MazeTileset/*.tmx",
           "szablony labiryntu: punkty wejścia poziomu; reszta własności to atrapy",
           _edit_tmx, _scan_maze_template, defines=_scan_maze_template),
    Source("project/assets/NinjaAdventure/maps/tilesets/*.tsx",
           "tilesety map: `model_name` i `type` na kaflu",
           _edit_tsx, _scan_tsx),
    Source("project/assets/MazeTileset/*.tsx",
           "tilesety labiryntu: `model_name` i `type` na kaflu",
           _edit_tsx, _scan_tsx),
    Source("project/config_model/characters.csv",
           "postacie: kolumna `key`, ekwipunek w `items`, miejsca (`MAPA:miejsce`)",
           _edit_characters_csv, _scan_characters_csv),
    Source("project/config_model/chests.csv",
           "skrzynie: kolumny `key` i `name`; zawartość w `items`/`random_items`",
           _edit_chests_csv, _scan_chests_csv),
    Source("project/config_model/items.csv",
           "przedmioty: kolumna `key`",
           _edit_items_csv, _scan_items_csv),
    Source("project/assets/NinjaAdventure/items/items.tsx",
           "tileset przedmiotów: `item_name` na kaflu stawia przedmiot na mapie",
           _edit_items_tsx, _scan_items_tsx),
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
           "config gry: klucze `characters`/`chests`/`items`, obsada labiryntu, miejsca, "
           "warunki `has_item(...)` i nagrody w dialogach oraz questach",
           _edit_config_json, _scan_config_json),
    Source("project/assets/locale/*.toml",
           "napisy: klucze sekcji [map] to nazwy map (D12)",
           _edit_locale_toml, _scan_locale_toml),
)

#: Pliki danych, których rename świadomie nie dotyka. Powód jest częścią kontraktu:
#: test z D17 czyta tę listę, więc „nie wiem, co to" nie przejdzie przez CI.
UNTOUCHED_SOURCES: dict[str, str] = {
    "project/config_model/config_schema.json":
        "schemat wygenerowany z `config_pydantic.py` - nazwy pól, nie klucze encji",
    "project/config_model/autogenerated_config.json":
        "martwy artefakt po usuniętym w B01 `main.py store` - nikt go nie czyta",
    "project/assets/NinjaAdventure/items/Items.tmx":
        "mapa-katalog kafli przedmiotów - odwołuje się do nich przez `gid`, "
        "nie po nazwie; klucze siedzą w `items.tsx`",
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


def origin_of(path: Path) -> str:
    """Z której mapy pochodzi klucz znaleziony w tym pliku (pusto = klucz globalny).

    Punkty wejścia, miejsca i nazwy instancji są unikalne **tylko w obrębie mapy** -
    ładowarka trzyma je w słownikach per scena. Bez tej etykiety `--list` pokazywał
    `Door` dwa razy jako jeden wpis i nie było widać, że to dwa różne progi.
    """
    if path.suffix != ".tmx":
        return ""
    if path.parent.name == "MazeTileset":
        return MAZE_ORIGIN
    return f"{path.stem} (_wip)" if path.parent.name == "_wip" else path.stem


def existing_keys_with_origin() -> dict[str, dict[str, set[str]]]:
    """``rodzaj -> klucz -> {mapy, z których pochodzi}`` (pusty zbiór = klucz globalny)."""
    out: dict[str, dict[str, set[str]]] = {kind: {} for kind in KINDS}
    for source in SOURCES:
        for path in source.paths():
            origin = origin_of(path)
            text = path.read_text(encoding="utf-8")
            defined = source.definitions(text)
            for kind, values in source.scan(text).items():
                bucket = out.setdefault(kind, {})
                for value in values:
                    if not value:
                        continue
                    origins = bucket.setdefault(value, set())
                    if origin and value in defined.get(kind, ()):
                        origins.add(origin)
    # mapa istnieje także wtedy, gdy nikt do niej nie prowadzi - plikiem `.tmx`
    for path in GAME_MAPS_DIR.glob("*.tmx"):
        out[MAP].setdefault(path.stem, set())
    return out


def existing_keys() -> dict[str, set[str]]:
    """Co dziś istnieje, per rodzaj - podstawa autodetekcji i flagi ``--list``."""
    return {kind: set(keys) for kind, keys in existing_keys_with_origin().items()}


def detect_kind(old: str, allowed: "tuple[str, ...] | None" = None) -> str:
    """Rodzaj klucza wywnioskowany z tego, gdzie ta nazwa dziś stoi.

    ``allowed`` zawęża kandydatów. Używa tego zakres ``MAPA:nazwa``: skoro globalnego
    klucza nie da się przemianować na jednej mapie, sam prefiks rozstrzyga
    dwuznaczność, którą po C02 mamy z definicji - nazwa instancji JEST kluczem modelu
    (`ROB` w `spawn_points` i `ROB` w `characters.csv` to dwa różne byty o tej samej nazwie).
    """
    kinds = allowed or KINDS
    matches = [kind for kind, values in existing_keys().items()
               if kind in kinds and old in values]
    if not matches:
        raise SystemExit(f"nie znalazłem '{old}' w żadnym źródle - literówka? "
                         f"(`--list` pokaże, co istnieje)")
    if len(matches) > 1:
        raise SystemExit(f"'{old}' istnieje jako {', '.join(sorted(matches))} - "
                         f"wskaż rodzaj przez --kind")
    return matches[0]


def rename(old: str, new: str, kind: str, dry_run: bool = False,
           scope: str = "") -> list[Change]:
    """Przemianowanie w każdym źródle z manifestu. Zwraca listę zmienionych plików."""
    ren = Rename(kind=kind, old=old, new=new, scope=scope)
    changes: list[Change] = []
    for source in SOURCES:
        for path in source.paths():
            text = path.read_text(encoding="utf-8")
            updated, hits = source.edit(text, ren, origin_of(path))
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


def bare_route_references(old: str) -> list[str]:
    """Gołe ``route:<nazwa>`` w `routines.toml` - niejednoznaczne przy rename'ie z zakresem.

    `resolve_at` przyjmuje `route:MAPA:nazwa` i `route:nazwa`; ta druga forma rozwiązuje
    się na mapie macierzystej NPC-a, więc skrypt nie wie, czy trafia w zakres. Zamiast
    zgadywać, wypisuje takie kroki jako rzecz do sprawdzenia ręcznie.
    """
    path = CONFIG_DIR / "routines.toml"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    return [f'route:{value}' for prefix, value
            in re.findall(r'\bat\s*=\s*"(route|location):([^"]*)"', text)
            if prefix == "route" and ":" not in value and value == old]


def obsidian_mentions(old: str) -> list[str]:
    """Pliki w `doc/`, które nadal wymieniają starą nazwę - do poprawy w Obsidianie.

    Vault jest źródłem treści, a nie danych: `just import-*` wciąga z niego dialogi,
    questy i postacie z powrotem do `config.json`. Gdyby skrypt zmienił tam nazwę sam,
    zmieniłby autorowi tekst pod ręką (klucz bywa też nazwą pliku i aliasem we
    frontmatterze). Zamiast tego mówimy, gdzie zajrzeć - inaczej pierwszy `import`
    po rename'ie po cichu przywróciłby stary klucz.
    """
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])")
    doc = REPO_ROOT / "doc"
    if not doc.is_dir():
        return []
    return sorted(str(path.relative_to(REPO_ROOT)) for path in doc.rglob("*.md")
                  if pattern.search(path.read_text(encoding="utf-8", errors="ignore")))


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
    known = existing_keys_with_origin()
    for kind in KINDS:
        entries = known[kind]
        scoped = kind in MAP_SCOPED_KINDS
        header = " - unikalne w obrębie mapy" if scoped else ""
        print(f"\n{kind} ({len(entries)}){header}:")
        width = max((len(key) for key in entries), default=0)
        for key in sorted(entries):
            origins = ", ".join(sorted(entries[key]))
            suffix = f"  ({origins})" if scoped and origins else ""
            print(f"  {key.ljust(width) if suffix else key}{suffix}")


def split_scope(value: str, kind: str | None = None) -> tuple[str, str]:
    """``"LOST_CORK_TAVERN:tables"`` -> ``("LOST_CORK_TAVERN", "tables")``.

    Zakres zapisuje się dokładnie tak, jak zapisuje się odwołanie w danych (D3), więc
    autor nie musi pamiętać osobnej składni. Prefiks ma sens tylko dla rodzajów
    zależnych od mapy - dla klucza globalnego byłby fałszywą obietnicą, że da się
    ograniczyć zmianę, której ograniczyć się nie da.
    """
    scope, name = _split_place(value)
    if not scope:
        return "", value
    known_maps = existing_keys()[MAP]
    if scope not in known_maps:
        raise SystemExit(f"'{scope}' nie jest mapą (zna: {', '.join(sorted(known_maps))})")
    if kind and kind not in MAP_SCOPED_KINDS:
        raise SystemExit(
            f"'{kind}' to klucz globalny - jeden w całej grze, więc nie da się go "
            f"przemianować tylko na jednej mapie. Zakres ma sens dla: "
            f"{', '.join(MAP_SCOPED_KINDS)}")
    return scope, name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Przemianuj klucz encji we wszystkich źródłach naraz (C02, D10).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Rodzaje: " + ", ".join(KINDS) + "\n"
               "Zakres: MAPA:nazwa ogranicza zmianę do jednej mapy "
               f"({', '.join(MAP_SCOPED_KINDS)})")
    parser.add_argument("old", nargs="?", help="obecny klucz, opcjonalnie jako MAPA:nazwa")
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

    scope, old = split_scope(args.old)
    new_scope, new = split_scope(args.new)
    if new_scope and new_scope != scope:
        parser.error(f"nowa nazwa wskazuje inną mapę ('{new_scope}') niż stara ('{scope}') - "
                     f"przeniesienie encji na inną mapę to nie rename")
    if old == new:
        parser.error("stara i nowa nazwa są takie same")

    # zakres przesądza, że chodzi o klucz zależny od mapy - to rozwiązuje
    # dwuznaczność `ROB` (instancja) vs `ROB` (model) bez pytania o --kind
    kind = args.kind or detect_kind(old, MAP_SCOPED_KINDS if scope else None)
    split_scope(args.old, kind)                  # dopiero teraz znamy rodzaj: sprawdź zakres
    if kind in MAP_SCOPED_KINDS and not scope:
        maps = existing_keys_with_origin()[kind].get(old, set())
        if len(maps) > 1:
            print(f"UWAGA: '{old}' istnieje na {len(maps)} mapach "
                  f"({', '.join(sorted(maps))}) - zmieniam na wszystkich.\n"
                  f"       Jedną mapę wskażesz przez '{sorted(maps)[0]}:{old}'.\n")

    changes = rename(old, new, kind, dry_run=args.dry_run, scope=scope)

    head = "DRY RUN: " if args.dry_run else ""
    where = f" (tylko {scope})" if scope else ""
    print(f"{head}{kind}: {old} -> {new}{where}")
    if not changes:
        print("  nic nie znalazłem - zły rodzaj klucza albo zła mapa w zakresie?")
        return 1
    for change in changes:
        print(f"  {change.path.relative_to(REPO_ROOT)}  ({change.hits}) {change.note}".rstrip())
    print(f"  razem: {sum(c.hits for c in changes)} trafień w {len(changes)} plikach")

    if kind in (INSTANCE, CHEST):
        print("  UWAGA: stan tej encji w istniejących zapisach jest kluczowany starą "
              "nazwą (O1) - zapisy sprzed rename'u dostaną wartości domyślne")

    if scope and kind == INSTANCE:
        for step in bare_route_references(old):
            print(f"  DO SPRAWDZENIA: `{step}` w routines.toml nie ma prefiksu mapy, "
                  f"więc nie wiem, czy dotyczy '{scope}' - zostawiam bez zmian")

    mentions = obsidian_mentions(old)
    if mentions:
        print(f"\n  '{old}' występuje jeszcze w {len(mentions)} plikach w `doc/` "
              f"(vault Obsidiana - skrypt go nie rusza):")
        for path in mentions:
            print(f"    {path}")
        print("  popraw je w Obsidianie, inaczej `just import-*` przywróci starą nazwę")

    if args.dry_run or args.no_validate:
        return 0
    print()
    return subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "validate_world.py")],
                          cwd=REPO_ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
