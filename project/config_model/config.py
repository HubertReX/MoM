"""Model konfiguracji gry (web) - WYGENEROWANY, NIE EDYTUJ RECZNIE.

Ten plik tworzy `scripts/gen_web_config.py` z modelu desktopowego w tym samym
katalogu (`config_model/`). Zeby zmienic pole - zmien je tam i uruchom
`just gen-web-config`, zeby przeniesc zmiane tutaj. Reczna edycja tego pliku
zniknie przy nastepnym uruchomieniu generatora i zostanie wykryta przez test
swiezosci (`tests/test_config_web_codegen.py`).

Web (pygbag/WASM) nie waliduje configu przy starcie - walidacja spojnosci
(czy przedmioty/postacie/skrzynie z odwolan istnieja) dzieje sie wylacznie na
desktopie, przy imporcie tresci.
"""


import json
from dataclasses import dataclass, field
from os import PathLike
from typing import Any

from enums import AttitudeEnum, ItemTypeEnum, RaceEnum
from settings import DEFAULT_DISPOSITION_WEIGHTS


def disposition(raw: object) -> dict[str, int]:
    # Mirrors the desktop model's disposition validator: int -> default
    # weights, dict -> copied + cast to int, anything else -> defaults.
    if isinstance(raw, int):
        return dict(DEFAULT_DISPOSITION_WEIGHTS)
    if isinstance(raw, dict):
        return {str(k): int(v) for k, v in raw.items()}
    return dict(DEFAULT_DISPOSITION_WEIGHTS)


@dataclass(slots=True)
class MazeLevelProperties():
    monsters_list: list[str] = field(repr=False)
    boss_monster: str
    monsters_count: int = field(repr=False)
    small_chest_count: int = field(repr=False)
    small_chest_template: str = field(repr=False)
    big_chest_template: str = field(repr=False)
    maze_cols: int = field(repr=False)
    maze_rows: int = field(repr=False)

    @classmethod
    def from_dict(cls: type["MazeLevelProperties"], data: dict[str, Any]) -> "MazeLevelProperties":
        return cls(
            monsters_list=[str(x) for x in data.get("monsters_list", [])],
            boss_monster=str(data.get("boss_monster", "")),
            monsters_count=int(data.get("monsters_count", 1)),
            small_chest_count=int(data.get("small_chest_count", 1)),
            small_chest_template=str(data.get("small_chest_template", "")),
            big_chest_template=str(data.get("big_chest_template", "")),
            maze_cols=int(data.get("maze_cols", 5)),
            maze_rows=int(data.get("maze_rows", 5)),
        )


@dataclass(slots=True)
class Character():
    name_EN: str
    name_PL: str
    sprite: str = field(repr=False)
    race: RaceEnum
    attitude: AttitudeEnum = field(repr=False)
    is_merchant: bool = field(repr=False)
    tradeable_items_types: list[ItemTypeEnum] = field(repr=False)
    allowed_zones: list[str] = field(repr=False)
    health: int = field(repr=False)
    max_health: int = field(repr=False)
    items: list[str]
    max_carry_weight: float = field(repr=False)
    money: int = field(repr=False)
    money_cap: int = field(repr=False)
    money_regen_pct: float = field(repr=False)
    damage: int = field(repr=False)
    speed_walk: int = field(repr=False)
    speed_run: int = field(repr=False)
    has_dialog: bool = field(repr=False)
    friendly: float = field(repr=False)
    disposition: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_DISPOSITION_WEIGHTS), repr=False)
    home: str = field(repr=False, default='')
    work: str = field(repr=False, default='')
    social: str = field(repr=False, default='')
    hobby: str = field(repr=False, default='')
    routine: str = field(repr=False, default='')
    barks: str = field(repr=False, default='')

    @classmethod
    def from_dict(cls: type["Character"], data: dict[str, Any]) -> "Character":
        return cls(
            name_EN=str(data.get("name_EN", "")),
            name_PL=str(data.get("name_PL", "")),
            sprite=str(data.get("sprite", "")),
            race=RaceEnum(data.get("race", "")),
            attitude=AttitudeEnum(data.get("attitude", "")),
            is_merchant=bool(data.get("is_merchant", False)),
            tradeable_items_types=[ItemTypeEnum(x) for x in data.get("tradeable_items_types", [])],
            allowed_zones=[str(x) for x in data.get("allowed_zones", [])],
            health=int(data.get("health", 30)),
            max_health=int(data.get("max_health", 30)),
            items=[str(x) for x in data.get("items", [])],
            max_carry_weight=float(data.get("max_carry_weight", 15.0)),
            money=int(data.get("money", 0)),
            money_cap=int(data.get("money_cap", 0)),
            money_regen_pct=float(data.get("money_regen_pct", 0.25)),
            damage=int(data.get("damage", 10)),
            speed_walk=int(data.get("speed_walk", 30)),
            speed_run=int(data.get("speed_run", 40)),
            has_dialog=bool(data.get("has_dialog", False)),
            friendly=float(data.get("friendly", 0.5)),
            disposition=disposition(data.get("disposition")),
            home=str(data.get("home", '')),
            work=str(data.get("work", '')),
            social=str(data.get("social", '')),
            hobby=str(data.get("hobby", '')),
            routine=str(data.get("routine", '')),
            barks=str(data.get("barks", '')),
        )


@dataclass(slots=True)
class Item():
    name_EN: str
    name_PL: str
    type: ItemTypeEnum
    value: int = field(repr=False)
    in_use: bool = field(repr=False)
    count: int = field(repr=False)
    weight: float = field(repr=False)
    health_impact: int = field(repr=False)
    damage: int = field(repr=False)
    cooldown_time: float = field(repr=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Item":
        return cls(
            name_EN=str(data.get("name_EN", "")),
            name_PL=str(data.get("name_PL", "")),
            type=ItemTypeEnum(data.get("type", "")),
            value=int(data.get("value", 50)),
            in_use=bool(data.get("in_use", False)),
            count=int(data.get("count", 1)),
            weight=float(data.get("weight", 1.0)),
            health_impact=int(data.get("health_impact", 0)),
            damage=int(data.get("damage", 10)),
            cooldown_time=float(data.get("cooldown_time", 1.0)),
        )


@dataclass(slots=True)
class Chest():
    name: str
    is_small: bool = field(repr=False)
    is_closed: bool = field(repr=False)
    items: list[str]
    total_items_count: int = field(repr=False)
    random_items: list[str]
    requires_item: str = field(repr=False)
    consumes_key: bool = field(repr=False)

    @classmethod
    def from_dict(cls: type["Chest"], data: dict[str, Any]) -> "Chest":
        return cls(
            name=str(data.get("name", "")),
            is_small=bool(data.get("is_small", True)),
            is_closed=bool(data.get("is_closed", True)),
            items=[str(x) for x in data.get("items", [])],
            total_items_count=int(data.get("total_items_count", 0)),
            random_items=[str(x) for x in data.get("random_items", [])],
            requires_item=str(data.get("requires_item", '')),
            consumes_key=bool(data.get("consumes_key", False)),
        )


@dataclass
class Config():
    characters: dict[str, Character]
    chests: dict[str, Chest]
    items: dict[str, Item]
    maze_configs: dict[int, MazeLevelProperties]
    dialogs: dict[str, Any]
    quests: dict[str, Any] = field(repr=False)
    messages: dict[str, dict[str, str]]
    barks: dict[str, list[dict[str, str]]]

    @classmethod
    def build(cls, data: dict[str, Any]) -> "Config":
        characters: dict[str, Character] = {}
        for key, entry in data["characters"].items():
            characters[key] = Character.from_dict(entry)

        chests: dict[str, Chest] = {}
        for key, entry in data["chests"].items():
            chests[key] = Chest.from_dict(entry)

        items: dict[str, Item] = {}
        for key, entry in data["items"].items():
            items[key] = Item.from_dict(entry)

        maze_configs: dict[int, MazeLevelProperties] = {}
        for key, entry in data["maze_configs"].items():
            maze_configs[int(key)] = MazeLevelProperties.from_dict(entry)

        dialogs = data.get("dialogs", {})

        quests = data.get("quests", {})

        messages = data.get("messages", {})

        barks = data.get("barks", {})

        # keyword args on purpose: this used to be positional, and inserting a
        # field in the middle would have silently shifted a value into the wrong slot
        return cls(
            characters=characters,
            chests=chests,
            items=items,
            maze_configs=maze_configs,
            dialogs=dialogs,
            quests=quests,
            messages=messages,
            barks=barks,
        )


def load_config(file_name: PathLike) -> "Config":
    with open(file_name, "r") as f:
        config_json = json.load(f)

    config_json.pop("$schema", None)
    return Config.build(config_json)
