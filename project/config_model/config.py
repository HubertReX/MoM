import json
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Annotated, Any, Dict, List, Literal, Tuple

from enums import AttitudeEnum, ItemTypeEnum, RaceEnum
from settings import DEFAULT_DISPOSITION_WEIGHTS


# https://docs.python.org/3/library/enum.html#enum.Enum
# class ToolEnum(IntEnum):
#     spanner = 1
#     wrench = 2

###################################################################################################################
# MARK: Character

# class Character(BaseModel):
#     name: str   = Field(min_length=3, rozen=True, description="Unique character name")
#     sprite: str = Field(min_length=3,
#                       description=f"Must be valid asset folder name (assets/[ASSET_PACK]/characters/[sprite])" ,
#                       repr=False)
#     race:         Annotated[RaceEnum,     Field(description="Base character race (e.g. humanoid, animal)")]
#     attitude:     Annotated[AttitudeEnum, Field(description="Attitude towards the player", repr=False)]
#     health:       Annotated[int,          Field(30, ge=0, description="initial health value", repr=False)]
#     max_health:   Annotated[int,          Field(30, ge=0, description="maximal health value", repr=False)]
#     money:        Annotated[int,          Field(0,  ge=0, description="initial amount of possessed money",
#                                               repr=False)]
#     damage:       Annotated[int,          Field(10, ge=0, description="amount of damage delt to others", repr=False)]

# dataclass version


@dataclass(slots=True)
class MazeLevelProperties():
    monsters_list:        Annotated[list[str], field(repr=False)]
    boss_monster:         str =                field(repr=False)
    monsters_count:       Annotated[int,       field(repr=False)]
    small_chest_count:    Annotated[int,       field(repr=False)]
    small_chest_template: Annotated[str,       field(repr=False)]
    big_chest_template:   Annotated[str,       field(repr=False)]
    maze_cols:            Annotated[int,       field(repr=False)]
    maze_rows:            Annotated[int,       field(repr=False)]

    @classmethod
    def from_dict(cls: type["MazeLevelProperties"], data: dict[str, Any]) -> "MazeLevelProperties":
        return cls(
            monsters_list        = data.get("monsters_list",        []),
            boss_monster         = data.get("boss_monster",         ""),
            monsters_count       = data.get("monsters_count",       1),
            small_chest_count    = data.get("chest_count",          1),
            small_chest_template = data.get("small_chest_template", ""),
            big_chest_template   = data.get("big_chest_template",   ""),
            maze_cols            = data.get("maze_cols",            5),
            maze_rows            = data.get("maze_rows",            5)
        )


@dataclass(slots=True)
class Character():
    name_EN:               str
    name_PL:               str
    sprite:                Annotated[str,                field(repr=False)]
    race:                  Annotated[RaceEnum,           field(repr=False)]
    attitude:              Annotated[AttitudeEnum,       field(repr=False)]
    is_merchant:           Annotated[bool,               field(repr=False)]
    tradeable_items_types: Annotated[list[ItemTypeEnum], field(repr=False)]
    allowed_zones:         Annotated[list[str],          field(repr=False)]
    health:                Annotated[int,                field(repr=False)]
    max_health:            Annotated[int,                field(repr=False)]
    items:                 Annotated[list[str],          field(repr=False)]
    max_carry_weight:      Annotated[float,              field(repr=False)]
    money:                 Annotated[int,                field(repr=False)]
    money_cap:             Annotated[int,                field(repr=False)]
    money_regen_pct:       Annotated[float,              field(repr=False)]
    damage:                Annotated[int,                field(repr=False)]
    speed_walk:            Annotated[int,                field(repr=False)]
    speed_run:             Annotated[int,                field(repr=False)]
    has_dialog:            Annotated[bool,               field(repr=False)] = False
    friendly:              Annotated[float,              field(repr=False)] = 0.5
    disposition:           Annotated[dict[str, int],     field(repr=False)] = field(default_factory=lambda: dict(DEFAULT_DISPOSITION_WEIGHTS))
    # Daily-routine destinations - see the same block in config_pydantic.py.
    home:                  Annotated[str,                field(repr=False)] = ""
    work:                  Annotated[str,                field(repr=False)] = ""
    social:                Annotated[str,                field(repr=False)] = ""
    hobby:                 Annotated[str,                field(repr=False)] = ""

    @classmethod
    def from_dict(cls: type["Character"], data: dict[str, Any]) -> "Character":
        raw_disposition = data.get("disposition")
        disposition: dict[str, int] = dict(DEFAULT_DISPOSITION_WEIGHTS)
        if isinstance(raw_disposition, dict):
            disposition.update({str(k): int(v) for k, v in raw_disposition.items()})
        return cls(
            name_EN = data.get("name_EN", ""),
            name_PL = data.get("name_PL", ""),
            sprite = data.get("sprite", ""),
            race = RaceEnum(data.get("race", "")),
            attitude = AttitudeEnum(data.get("attitude", "")),
            is_merchant = data.get("is_merchant", False),
            tradeable_items_types = [ItemTypeEnum(t) for t in data.get("tradeable_items_types", [])],
            allowed_zones = data.get("allowed_zones", []),
            health = data.get("health", 30),
            max_health = data.get("max_health", 30),
            items = data.get("items", []),
            max_carry_weight = data.get("max_carry_weight", 15.0),
            money = data.get("money", 0),
            money_cap = data.get("money_cap", 0),
            money_regen_pct = float(data.get("money_regen_pct", 0.25)),
            damage = data.get("damage", 10),
            speed_walk = data.get("speed_walk", 30),
            speed_run = data.get("speed_run", 40),
            has_dialog = data.get("has_dialog", False),
            friendly = float(data.get("friendly", 0.5)),
            disposition = disposition,
            home = data.get("home", ""),
            work = data.get("work", ""),
            social = data.get("social", ""),
            hobby = data.get("hobby", ""),
        )


@dataclass(slots=True)
class Item():
    # id:            Annotated[str,          field(repr=False)]
    name_EN:       str
    name_PL:       str
    type:          ItemTypeEnum
    value:         Annotated[int,   field(repr=False)]
    in_use:        Annotated[bool,  field(repr=False)]
    count:         Annotated[int,   field(repr=False)]
    weight:        Annotated[float, field(repr=False)]
    health_impact: Annotated[int,   field(repr=False)]
    damage:        Annotated[int,   field(repr=False)]
    cooldown_time: Annotated[float, field(repr=False)]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Item":
        return cls(
            # id            = data.get("id", ""),
            name_EN       = data.get("name_EN", ""),
            name_PL       = data.get("name_PL", ""),
            type          = ItemTypeEnum(data.get("type", "")),
            value         = data.get("value", 50),
            in_use        = data.get("in_use", False),
            count         = data.get("count", 1),
            weight        = data.get("weight", 1.0),
            health_impact = data.get("health_impact", 0),
            damage        = data.get("damage", 10),
            cooldown_time = data.get("cooldown_time", 1.0),
        )


@dataclass(slots=True)
class Chest():
    name:               str
    is_small:           Annotated[bool,      field(repr=False)]
    is_closed:          Annotated[bool,      field(repr=False)]
    items:              Annotated[list[str], field(repr=False)]
    total_items_count:  Annotated[int,       field(repr=False)]
    random_items:       Annotated[list[str], field(repr=False)]

    @classmethod
    def from_dict(cls: type["Chest"], data: dict[str, Any]) -> "Chest":
        return cls(
            name      =          data.get("name", ""),
            is_small  =          data.get("is_small", True),
            is_closed =          data.get("is_closed", True),
            items     =          data.get("items", []),
            total_items_count =  data.get("random_items_count", 0),
            random_items      =  data.get("random_items", []),
        )


###################################################################################################################
# MARK: Config

# class Config(BaseModel):
#     characters: Dict[str, Character]

# dataclass version


@dataclass
class Config():
    characters:   dict[str, Character]
    chests:       dict[str, Chest]
    items:        dict[str, Item]
    maze_configs: dict[int, MazeLevelProperties]
    dialogs:      dict[str, Any] = field(default_factory=dict)
    # Quest definitions stay a plain dict here: the web build has no Pydantic
    # (decision D4), and `quest.graph.init_quests` reads exactly this shape.
    quests:       dict[str, Any] = field(default_factory=dict)
    messages:     dict[str, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def build(cls, data: dict[str, Any]) -> "Config":
        chars = {}
        for name, character_dict in data["characters"].items():
            character = Character.from_dict(character_dict)
            chars[name] = character

        chests = {}
        for name, chest_dict in data["chests"].items():
            chest = Chest.from_dict(chest_dict)
            chests[name] = chest
        items = {}

        for name, item_dict in data["items"].items():
            item = Item.from_dict(item_dict)
            items[name] = item

        maze_configs = {}
        for name, maze_config_dict in data["maze_configs"].items():
            maze_config = MazeLevelProperties.from_dict(maze_config_dict)
            maze_configs[int(name)] = maze_config

        dialogs = data.get("dialogs", {})
        quests = data.get("quests", {})
        messages = data.get("messages", {})

        # keyword args on purpose: this used to be positional, and inserting a
        # field in the middle would have silently shifted messages into quests
        return cls(
            characters=chars,
            chests=chests,
            items=items,
            maze_configs=maze_configs,
            dialogs=dialogs,
            quests=quests,
            messages=messages,
        )
###################################################################################################################


def test() -> None:
    # try:
    #     main_conf = Config(**conf)
    # except ValidationError as e:
    #     print(e.errors())

    # save_config_schema(Config, Path("config_schema.json"))

    c = load_config(Path("config.json"))

    print(len(c.characters.keys()))

###################################################################################################################
# MARK: Helper functions
# def generate_config_schema(model: BaseModel) -> dict[str, Any]:
#     return model.model_json_schema()


# def save_config_schema(model: BaseModel, file_name: PathLike) -> None:
#     schema = generate_config_schema(model)
#     with open(file_name, "w", encoding="utf-8") as f:
#         json.dump(schema, f, ensure_ascii=False, indent=4)

###################################################################################################################
# def save_config(model: BaseModel, file_name: PathLike) -> None:
#     with open(file_name, "w", encoding="utf-8") as f:
#         json.dump(model.model_dump_json(), f, ensure_ascii=False, indent=4)


def load_config(file_name: PathLike) -> "Config":
    with open(file_name, "r") as f:
        config_json = json.load(f)

    del config_json["$schema"]
    config = Config.build(config_json)
    # try:
    #     config = Config(**config_json)
    # # except ValidationError as e:
    # except Exception as e:
    #     print(e.errors())
    # finally:
    # print(config.characters)
    return config


###################################################################################################################
if __name__ == "__main__":
    test()
