import json
from os import PathLike
from pathlib import Path
from typing import Annotated, Any, Self
from rich import print
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, ValidationError, field_validator, model_validator

try:
    from settings import DEFAULT_DISPOSITION_WEIGHTS, SCHEMA_FILE
    from enums import AttitudeEnum, ItemTypeEnum, RaceEnum
    from quest.entities import CompletionMode, QuestRewardCategory
    from quest.graph import init_quests
except Exception:
    # when script run as stand alone to update config schema
    import sys
    sys.path.append("..")
    from settings import DEFAULT_DISPOSITION_WEIGHTS, SCHEMA_FILE
    from enums import AttitudeEnum, ItemTypeEnum, RaceEnum
    from quest.entities import CompletionMode, QuestRewardCategory
    from quest.graph import init_quests


# https://docs.python.org/3/library/enum.html#enum.Enum
# class ToolEnum(IntEnum):
#     spanner = 1
#     wrench = 2

IS_FROZEN = True
##################################################################################################################
# MARK: MazeLevelProperties


class MazeLevelProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monsters_list:        Annotated[list[str], Field(repr=False, default_factory=list,
                                                     description = "List of regular monster NPC models names")]
    boss_monster:         Annotated[str,       Field(min_length=3, description="Boss monster NPC model name")]
    monsters_count:       Annotated[int,       Field(1, ge=0, repr=False,
                                                     description="Number of regular monster per level (without boss)",)]
    small_chest_count:    Annotated[int,       Field(1, ge=0, repr=False,
                                                     description="Number of small chests on the map",)]
    small_chest_template: Annotated[str,       Field(min_length=3, repr=False,
                                                     description="Small chest name from config")]
    big_chest_template:   Annotated[str,       Field(min_length=3, repr=False,
                                                     description="Big chest name from config",)]
    maze_cols:            Annotated[int,       Field(5, ge=0, repr=False,
                                                     description="Number of columns in map grid",)]
    maze_rows:            Annotated[int,       Field(5, ge=0, repr=False,
                                                     description="Number of rows in map grid",)]


##################################################################################################################
# MARK: Character
class Character(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name_EN:       Annotated[str,          Field(min_length=1, frozen=IS_FROZEN, description="English character name")]
    name_PL:       Annotated[str,          Field(min_length=1, frozen=IS_FROZEN, description="Polish character name")]
    sprite:        Annotated[str,          Field(min_length=3, repr=False,
                                                 description="Must be valid file name from assets folder")]
    race:          Annotated[RaceEnum,     Field(description="Base character race (e.g. humanoid, animal)")]
    attitude:      Annotated[AttitudeEnum, Field(description="Attitude towards the player", repr=False)]
    is_merchant:   Annotated[bool,         Field(False, description="Flag if NPC can trade items", repr=False)]
    tradeable_items_types: Annotated[list[ItemTypeEnum], Field(repr=False, default_factory=list,
                                                               description="Item's type that can be traded. Empty means all.",)]  # noqa E501
    allowed_zones: Annotated[list[str],    Field(repr=False, default_factory=list,
                                                 description="Zones where the character is allowed to move. Empty means everywhere.",)]  # noqa E501
    health:        Annotated[int,          Field(30, ge=0, description="initial health value", repr=False)]
    max_health:    Annotated[int,          Field(30, ge=0, description="maximal health value", repr=False)]
    # items:        Annotated[list["Item"], Field(description="list of character's items", default_factory = list)]
    items:         Annotated[list[str],    Field(description="list of character's items", default_factory=list)]
    max_carry_weight: Annotated[float,     Field(15.0, ge=0, description="maximal carrying weight in kg", repr=False)]
    money:         Annotated[int,          Field(0,  ge=0, description="initial amount of possessed money", repr=False)]
    money_cap:     Annotated[int,          Field(0,  ge=0, repr=False,
                                                 description="ceiling the purse regenerates up to; 0 means 'use `money`'")]
    money_regen_pct: Annotated[float,      Field(0.25, ge=0.0, le=1.0, repr=False,
                                                 description="fraction of `money_cap` restored per elapsed day")]
    damage:        Annotated[int,          Field(10, ge=0, description="amount of damage delt to others", repr=False)]
    speed_walk:    Annotated[int,          Field(30, gr=0, description="walking speed", repr=False)]
    speed_run:     Annotated[int,          Field(40, gr=0, description="walking speed", repr=False)]
    has_dialog:    Annotated[bool,         Field(False, description="Whether this character has a dialog graph", repr=False)]
    friendly:      Annotated[float,        Field(0.5, ge=0.0, le=1.0, description="Base sentiment towards the player (0..1, maps to initial NPC sentiment 0..100)", repr=False)]
    disposition:   Annotated[int | dict[str, int], Field(default_factory=lambda: dict(DEFAULT_DISPOSITION_WEIGHTS), description="Per-sentiment weights that shift NPC sentiment when a dialog option is chosen; legacy int is converted to default weights", repr=False)]
    # Daily-routine destinations. Each names an object on the map's `places` layer;
    # the routine only ever says "go to your `work`", which is what lets one routine
    # serve the whole village. The role of a place is a *relation* between character
    # and place, not a property of the place - the same tavern is the barman's `work`
    # and everybody else's `social` - so it is bound here and not in Tiled.
    # An empty cell degrades that routine step to "stay put", never to a crash.
    home:          Annotated[str,          Field("", description="place object the character sleeps at", repr=False)]
    work:          Annotated[str,          Field("", description="place object the character works at", repr=False)]
    social:        Annotated[str,          Field("", description="place object the character spends its break at", repr=False)]
    hobby:         Annotated[str,          Field("", description="place object characteristic for this character", repr=False)]

    @field_validator("disposition", mode="before")
    @classmethod
    def _convert_disposition(cls, v: object) -> dict[str, int]:
        if isinstance(v, int):
            return dict(DEFAULT_DISPOSITION_WEIGHTS)
        if isinstance(v, dict):
            return {str(k): int(val) for k, val in v.items()}
        return dict(DEFAULT_DISPOSITION_WEIGHTS)


##################################################################################################################
# MARK: Item


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # id: str   = Field(
    #     min_length=3, frozen=IS_FROZEN, description="Unique string identifier")
    name_EN:       Annotated[str,          Field(min_length=1, frozen=IS_FROZEN, description="English item name")]
    name_PL:       Annotated[str,          Field(min_length=1, frozen=IS_FROZEN, description="Polish item name")]
    type:          Annotated[ItemTypeEnum, Field(description="Item type (e.g. weapon, tool, consumable)")]
    value:         Annotated[int,          Field(50, ge=0, description="Monetary value", repr=False)]
    in_use:        Annotated[bool,         Field(False, description="Whether the item is currently in use", repr=False)]
    count:         Annotated[int,          Field(1, ge=1, description="Number of items in the stack", repr=False)]
    weight:        Annotated[float,        Field(1.0, ge=0, repr=False,
                                                 description="Weight of single item in the stack in kg")]
    health_impact: Annotated[int,          Field(0, ge=0, repr=False,
                                                 description="The impact on health when consumed")]
    damage:        Annotated[int,          Field(10, ge=0, repr=False,
                                                 description="The amount of damage delt (weapon only)")]
    cooldown_time: Annotated[float,        Field(1.0, ge=0.0, repr=False,
                                                 description="The amount of time in seconds it takes to use the weapon again")]  # noqa E501


###################################################################################################################
# MARK: Chest
class Chest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # id: str   = Field(
    #     min_length=3, frozen=IS_FROZEN, description="Unique string identifier")
    name:               Annotated[str,       Field(min_length=3, frozen=IS_FROZEN, description="Chest display name")]
    is_small:           Annotated[bool,      Field(True, description="Is it small or big", repr=False)]
    is_closed:          Annotated[bool,      Field(True, description="Is it closed or open", repr=False)]
    items:              Annotated[list[str], Field(default_factory=list,
                                                   description = "list of persistent items in the chest")]
    total_items_count:  Annotated[int,       Field(0, repr=False,
                                                   description="total numer of items to generate (persistent + random)")]  # noqa E501
    random_items:       Annotated[list[str], Field(default_factory=list,
                                                   description="list of items to generate randomly")]


###################################################################################################################
# MARK: Quest
# Decision D4: quests are validated with Pydantic at *import* time (desktop only).
# The runtime — including web, where Pydantic is absent — reads the plain dict via
# `quest.graph.init_quests`. These models mirror the `quest.entities` dataclasses;
# the dataclasses are the runtime shape, these are the gatekeeper at the door.


class QuestReward(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: Annotated[QuestRewardCategory, Field(description="Which stat/resource the reward grants")]
    value:    Annotated[int,       Field(0, ge=0, repr=False,
                                         description="Amount granted; unused by the 'items' category")]
    items:    Annotated[list[str], Field(default_factory=list, repr=False,
                                         description="Item keys granted; 'items' category only")]
    target:   Annotated[str | None, Field(None, repr=False,
                                          description="NPC config key a 'sentiment' reward applies to; a quest has no current character")]  # noqa E501


class Quest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name:        Annotated[str, Field(min_length=1, description="`messages` key of the quest title")]
    description: Annotated[str, Field(min_length=1, repr=False, description="`messages` key of the quest description")]
    success:     Annotated[str, Field(min_length=1, repr=False,
                                      description="`messages` key of the completion text; plain prose, the reward label is appended by the engine")]  # noqa E501
    completion:  Annotated[CompletionMode, Field(description="How the quest completes: all_subquests / test / manual")]
    test:        Annotated[str | None, Field(None, repr=False,
                                             description="Mini-DSL condition; required by (and only by) completion='test'")]  # noqa E501
    progress:    Annotated[str | None, Field(None, repr=False,
                                             description="Mini-DSL numeric expression for the progress bar; pairs with progress_total")]  # noqa E501
    progress_total: Annotated[int, Field(0, ge=0, repr=False,
                                         description="Denominator of the progress bar; 0 means no explicit progress")]
    requires:    Annotated[list[str], Field(default_factory=list, repr=False,
                                            description="Quest keys that must be done before this one unlocks (DAG edges)")]  # noqa E501
    parent:      Annotated[str | None, Field(None, repr=False,
                                             description="Umbrella quest this one is a subquest of")]
    rewards:     Annotated[list[QuestReward], Field(default_factory=list, repr=False,
                                                    description="Effects applied on completion; ALL of them, in order")]


###################################################################################################################
# MARK: Config
class Config(BaseModel):
    # this class is used only for crating instances of the config class
    characters:   dict[str, Character]
    chests:       dict[str, Chest]
    items:        dict[str, Item]
    maze_configs: dict[int, MazeLevelProperties]
    dialogs:      Annotated[dict[str, Any], Field(default_factory=dict, repr=False,
                                                   description="Character dialog graphs keyed by character config key")]
    quests:       Annotated[dict[str, Quest], Field(default_factory=dict, repr=False,
                                                    description="Quest definitions keyed by quest key")]
    messages:     Annotated[dict[str, dict[str, str]], Field(default_factory=dict, repr=False,
                                                             description="Localized UI strings keyed by language")]

    @model_validator(mode='after')
    def check_character_items(self) -> Self:
        for character in self.characters.values():
            for item in character.items:
                if item not in self.items:
                    raise ValueError(f"item '{item}' from '{character.name_EN}' character does not exist")

        for chest in self.chests.values():
            for item in chest.items:
                if item not in self.items:
                    raise ValueError(f"item '{item}' from '{chest.name}' chest does not exist")

            for item in chest.random_items:
                if item not in self.items:
                    raise ValueError(f"random item '{item}' from '{chest.name}' chest does not exist")

        for key, maze_config in self.maze_configs.items():
            for monster in maze_config.monsters_list:
                if monster not in self.characters:
                    raise ValueError(f"monster '{monster}' from monsters_list of '{key}' maze_config does not exist")

            if maze_config.boss_monster not in self.characters:
                raise ValueError(f"boss_monster '{maze_config.boss_monster}' from '{key}' maze_config does not exist")

            if maze_config.small_chest_template not in self.chests:
                raise ValueError(f"small_chest_template '{maze_config.small_chest_template}' from '{
                                 key}' maze_config does not exist")

            if maze_config.big_chest_template not in self.chests:
                raise ValueError(f"big_chest_template '{maze_config.big_chest_template}' from '{
                                 key}' maze_config does not exist")

        return self

    @model_validator(mode='after')
    def check_quests(self) -> Self:
        for key, quest in self.quests.items():
            for reward in quest.rewards:
                for item in reward.items:
                    if item not in self.items:
                        raise ValueError(f"item '{item}' from '{key}' quest reward does not exist")

        # Graph semantics (dangling requires/parent, completion modes that can never
        # be satisfied) are checked by the runtime builder rather than duplicated here.
        # Delegating keeps one source of truth AND guarantees the property we actually
        # want: a config.json that passes desktop validation cannot break the web
        # runtime, which runs the very same init_quests() without Pydantic.
        init_quests({key: quest.model_dump(mode="json") for key, quest in self.quests.items()})

        return self


class ConfigForSchemaGen(Config):
    # this class is used only for generating the config schema
    # we can't use the same class since $schema won't validate
    # json_schema_extra={'$schema': "./config_schema.json"}
    model_config = ConfigDict(extra="forbid")


###################################################################################################################


def test() -> None:
    # try:
    #     main_conf = Config(**conf)
    # except ValidationError as e:
    #     print(e.errors())
    save_config_schema(ConfigForSchemaGen, Path("config_schema.json"))

    # c = load_config(Path("config.json"))

    # print(len(c.characters.keys()))

###################################################################################################################
# MARK: Helper functions


def generate_config_schema(model: type[Config]) -> dict[str, Any]:
    return model.model_json_schema()


def save_config_schema(model: type[Config], file_name: Path) -> None:
    schema = generate_config_schema(model)
    # hack allows to add additional property that $schema name
    schema["properties"]["$schema"] = f"./{file_name.name}"
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=4)

    print(f"\n[light_green]INFO[/] Config schema regenerated and saved to '{file_name}'\n")

###################################################################################################################


def save_config(model: Config | ConfigForSchemaGen, file_name: PathLike) -> None:
    json_model = model.model_dump_json(indent=4, exclude_defaults=True)
    json_model = '{\n    "$schema": "./config_schema.json",' + json_model[1:]
    with open(file_name, "w", encoding="utf-8") as f:
        f.write(json_model)  # ensure_ascii=False, indent=4)

    print(f"\n[light_green]INFO[/] Config regenerated and saved to '{file_name}'\n")

###################################################################################################################


def load_config(file_name: PathLike) -> "Config":
    config: Config | None = None
    with open(file_name, "r") as f:
        config_json = json.load(f)

    # del config_json["$schema"]
    # config = Config.build(config_json)
    try:
        config = Config(**config_json)
    # except ValidationError as e:
    except Exception as e:
        print("[red]Error![/] Unable to create config - validation failed.")
        print(e)
        exit(1)
    # finally:
    #     print(config.characters)
    return config


def update_config_schema() -> None:
    # print(Item({"name": "Dummy", "type": ItemTypeEnum.gem}).model_dump())
    save_config_schema(ConfigForSchemaGen, SCHEMA_FILE)


###################################################################################################################
if __name__ == "__main__":
    update_config_schema()
