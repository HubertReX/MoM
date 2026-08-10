#!/usr/bin/env python3
"""Unit tests for the C02 validator rules (13-19).

Run from the project root:
    .venv/bin/python tests/test_validate_world_rules.py

Etap 4 dokłada siatkę bezpieczeństwa PRZED rename'ami z etapu 5, więc na prawdziwym
świecie część reguł świeci teraz na czerwono - to zamierzone i te testy tego nie
udają. Pinujemy dwie rzeczy naraz:

1. **Reguła umie zapalić się na czerwono** - na spreparowanym świecie, bo reguła,
   która nigdy nie zgłasza błędu, jest dekoracją, a nie bramką.
2. **Reguła nie zapala się tam, gdzie świat już jest w porządku** - `check_tileset_model_names`
   (naprawione kafle z etapu 1), `check_interaction_targets` i `check_map_references`
   mają na prawdziwym świecie zero błędów i mają je mieć nadal po etapie 5.

Wszystko czyta surowe CSV/TOML/XML - zero pygame'a, zero ekranu (jak `validate_world.py`).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_world import (                                     # noqa: E402
    ERROR,
    WARN,
    GameMap,
    World,
    check_bark_pools,
    check_condition_entities,
    check_interaction_targets,
    check_map_coverage,
    check_map_references,
    check_item_keys,
    check_place_prefixes,
    check_spawn_naming,
    check_tileset_model_names,
    load_world,
)


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


WORLD = load_world()


###############################################################################################################
# MARK: helpers
def _map(name: str, **layers: list[tuple[str, dict[str, str]]]) -> GameMap:
    """Mapa z warstw podanych jako `nazwa_warstwy=[(nazwa obiektu, własności), …]`."""
    game_map = GameMap(name=name, path=Path(f"{name}.tmx"))
    for layer, objects in layers.items():
        game_map.objects[layer] = [obj for obj, _ in objects]
        game_map.props[layer] = [props for _, props in objects]
    return game_map


def _world(**overrides: object) -> World:
    """Świat z prawdziwym configiem i podmienionymi fragmentami."""
    fields: dict[str, object] = {
        "config": WORLD.config,
        "characters_csv": [],
        "routines": {},
        "maps": [],
        "sprites": WORLD.sprites,
        "audio": WORLD.audio,
        "tilesets": {},
        "maze_entry_points": WORLD.maze_entry_points,
        "items_csv": WORLD.items_csv,
        "chests_csv": WORLD.chests_csv,
        "item_tiles": WORLD.item_tiles,
        "item_sprites": WORLD.item_sprites,
    }
    fields.update(overrides)
    return World(**fields)                                       # type: ignore[arg-type]


def _errors(violations: list) -> list[str]:
    return [v.message for v in violations if v.severity == ERROR]


###############################################################################################################
# MARK: rule 13 - nazwa instancji (D1/D2)
def test_an_instance_named_after_its_model_passes() -> None:
    game_map = _map("Village")
    game_map.spawns = {"FISH_RED_01": "FISH_RED", "FISH_RED_02": "FISH_RED", "COW": "COW"}
    assert_eq(check_spawn_naming(_world(maps=[game_map])), [], "docelowa konwencja jest czysta")


def test_an_instance_named_anything_else_is_an_error() -> None:
    """Dokładnie ten stan, w którym `Village.tmx` stało PRZED etapem 5 (`FishRed01`, `Dog_orange`)."""
    game_map = _map("Village")
    game_map.spawns = {"FishRed01": "FISH_RED", "Dog_orange": "DOG_ORANGE"}
    messages = _errors(check_spawn_naming(_world(maps=[game_map])))
    assert_eq(len(messages), 2, "obie nazwy zgłoszone")
    assert_true(all("FISH_RED" in m or "DOG_ORANGE" in m for m in messages),
                f"komunikat podaje klucz docelowy: {messages}")


def test_a_number_on_the_only_copy_is_a_warning_not_an_error() -> None:
    """D2: numer należy się instancji dopiero wtedy, gdy kopii jest więcej niż jedna."""
    game_map = _map("Village")
    game_map.spawns = {"SNAKE_01": "SNAKE"}
    violations = check_spawn_naming(_world(maps=[game_map]))
    assert_eq(_errors(violations), [], "sam sufiks nie jest błędem")
    assert_eq([v.severity for v in violations], [WARN], "ale jest ostrzeżeniem")


###############################################################################################################
# MARK: rule 14 - drzwi donikąd (D6)
def _village_and_tavern(exit_props: dict[str, str]) -> World:
    village = _map(
        "Village",
        interactions=[("LOST_CORK_TAVERN", exit_props)],
        entry_points=[("VillageHouseDoor", {}), ("NextToMaze", {})],
    )
    tavern = _map("LOST_CORK_TAVERN", entry_points=[("Door", {}), ("start", {})])
    return _world(maps=[village, tavern])


def test_a_door_pointing_at_a_real_entry_point_passes() -> None:
    world = _village_and_tavern({"obj_type": "exit", "to_map": "LOST_CORK_TAVERN",
                                 "destination_entry_point": "Door"})
    assert_eq(check_interaction_targets(world), [], "poprawne drzwi nie zgłaszają nic")


def test_a_door_pointing_at_a_missing_entry_point_is_an_error() -> None:
    """Nietrafiony punkt wejścia stawia gracza w (0, 0) - widać to dopiero po przejściu."""
    world = _village_and_tavern({"obj_type": "exit", "to_map": "LOST_CORK_TAVERN",
                                 "destination_entry_point": "Drzwi"})
    messages = _errors(check_interaction_targets(world))
    assert_eq(len(messages), 1, "jeden błąd")
    assert_true("Drzwi" in messages[0] and "Door" in messages[0],
                f"komunikat mówi, czego nie ma i co jest: {messages[0]}")


def test_a_door_with_no_destination_entry_point_is_an_error() -> None:
    world = _village_and_tavern({"obj_type": "exit", "to_map": "LOST_CORK_TAVERN"})
    assert_eq(len(_errors(check_interaction_targets(world))), 1, "brak własności = błąd")


def test_a_return_point_must_exist_on_the_map_the_door_stands_on() -> None:
    world = _village_and_tavern({"obj_type": "exit", "to_map": "LOST_CORK_TAVERN",
                                 "destination_entry_point": "Door",
                                 "return_entry_point": "NieMaTakiego"})
    messages = _errors(check_interaction_targets(world))
    assert_eq(len(messages), 1, "powrót też jest sprawdzany")
    assert_true("NieMaTakiego" in messages[0], messages[0])


def test_a_door_into_the_maze_uses_the_template_entry_points() -> None:
    """Poziom labiryntu nie ma `.tmx` - `Entry` i `Re-Entry` przychodzą z szablonu."""
    assert_true("Entry" in WORLD.maze_entry_points,
                f"szablon labiryntu wczytany: {sorted(WORLD.maze_entry_points)}")
    village = _map("Village", interactions=[
        ("MAZE_01", {"obj_type": "exit", "to_map": "MAZE_01",
                     "destination_entry_point": "Entry"}),
    ])
    assert_eq(check_interaction_targets(_world(maps=[village])), [], "wejście do lochu przechodzi")

    village = _map("Village", interactions=[
        ("MAZE_01", {"obj_type": "exit", "to_map": "MAZE_01",
                     "destination_entry_point": "Wejscie"}),
    ])
    assert_eq(len(_errors(check_interaction_targets(_world(maps=[village])))), 1,
              "literówka w punkcie wejścia labiryntu też jest łapana")


def test_a_chest_object_must_name_a_chest_in_the_config() -> None:
    village = _map("Village", interactions=[("SmallChest_VillageHouse", {"obj_type": "chest"})])
    messages = _errors(check_interaction_targets(_world(maps=[village])))
    assert_eq(len(messages), 1, "stary klucz skrzyni = błąd")
    assert_true("config.chests" in messages[0], messages[0])


def test_an_unknown_obj_type_is_an_error() -> None:
    """Ładowarka zna `exit` i `chest`; wszystko inne jest w grze niewidoczne."""
    village = _map("Village", interactions=[("Cos", {"obj_type": "portal"})])
    assert_eq(len(_errors(check_interaction_targets(_world(maps=[village])))), 1,
              "obcy obj_type zgłoszony")


def test_a_door_named_differently_than_its_destination_is_a_warning() -> None:
    village = _map("Village",
                   interactions=[("Maze", {"obj_type": "exit", "to_map": "MAZE_01",
                                           "destination_entry_point": "Entry"})])
    violations = check_interaction_targets(_world(maps=[village]))
    assert_eq(_errors(violations), [], "gra działa - klucz siedzi w to_map")
    assert_eq([v.severity for v in violations], [WARN], "ale rozjazd jest widoczny")


def test_the_real_world_has_no_broken_doors() -> None:
    """Bramka regresji: po etapie 5 (rename map) ta reguła ma dalej być na zero."""
    assert_eq(_errors(check_interaction_targets(WORLD)), [], "żadne drzwi nie prowadzą donikąd")


###############################################################################################################
# MARK: rule 15 - prefiks mapy w miejscach (D3)
def test_a_place_without_a_map_prefix_is_an_error() -> None:
    """`bar` i `tables` istniały równocześnie na dwóch mapach - goła nazwa jest loterią."""
    world = _world(characters_csv=[{"key": "BART", "home": "house_bart",
                                   "work": "BLUNDERHAVEN:market_stall_2"}])
    messages = _errors(check_place_prefixes(world))
    assert_eq(len(messages), 1, "tylko goła nazwa jest zgłaszana")
    assert_true("house_bart" in messages[0], messages[0])


def test_a_routine_location_without_a_map_prefix_is_an_error() -> None:
    world = _world(routines={"farmer": {"slot": [{"at": "location:well"},
                                                 {"at": "location:BLUNDERHAVEN:pier"},
                                                 {"at": "type:home"},
                                                 {"at": "route:ROB"}]}})
    messages = _errors(check_place_prefixes(world))
    assert_eq(len(messages), 1, "tylko `location:` bez prefiksu")
    assert_true("location:MAPA:well" in messages[0], messages[0])


###############################################################################################################
# MARK: rule 16 - model_name na kaflu tilesetu (D14, O8)
def test_a_tile_naming_a_character_that_does_not_exist_is_an_error() -> None:
    """Kafel bez spawnu przechodził regule 1 pod nosem i czekał uśpiony na `KeyError`."""
    world = _world(tilesets={"CharacterTileset.tsx": {6: "Snake", 21: "SPIRIT"}})
    messages = _errors(check_tileset_model_names(world))
    assert_eq(len(messages), 1, "tylko zepsuty kafel")
    assert_true("Snake" in messages[0] and "6" in messages[0], messages[0])


def test_the_real_tilesets_are_clean() -> None:
    """Bramka regresji dla naprawy 7 kafli z etapu 1 (O8) i nowego kafla `ROBIN` (O9)."""
    assert_true(bool(WORLD.tilesets), "tilesety w ogóle wczytane")
    assert_eq(_errors(check_tileset_model_names(WORLD)), [], "każdy model_name jest kluczem postaci")


###############################################################################################################
# MARK: rule 17 - mapa spoza rejestru (D13)
def test_a_reference_to_a_map_outside_the_registry_is_an_error() -> None:
    """Mapa „istniała", bo istniał plik `.tmx` - a poziom labiryntu pliku nie ma."""
    village = _map("Village", interactions=[
        ("VillageHouse", {"obj_type": "exit", "to_map": "VillageHouse",
                          "destination_entry_point": "Door"}),
    ])
    world = _world(maps=[village],
                   characters_csv=[{"key": "BART", "home": "Wiocha:house_bart"}])
    messages = _errors(check_map_references(world))
    assert_eq(len(messages), 2, "drzwi i prefiks miejsca")
    assert_true(any("VillageHouse" in m for m in messages), f"{messages}")
    assert_true(any("Wiocha" in m for m in messages), f"{messages}")


def test_a_reference_to_a_maze_level_that_the_registry_knows_passes() -> None:
    village = _map("Village", interactions=[
        ("MAZE_01", {"obj_type": "exit", "to_map": "MAZE_01",
                     "destination_entry_point": "Entry"}),
    ])
    assert_eq(check_map_references(_world(maps=[village])), [], "labirynt jest mapą bez pliku")


def test_the_real_world_references_only_known_maps() -> None:
    assert_eq(_errors(check_map_references(WORLD)), [], "rejestr pokrywa wszystkie odwołania")


###############################################################################################################
# MARK: rule 18 - pokrycie map i muzyki (D7, O4)
def test_map_coverage_never_reports_an_error() -> None:
    """Cisza bywa zamierzona, a utwór odłożony na Akt 1 ma prawo leżeć w repo (W5)."""
    assert_eq(_errors(check_map_coverage(WORLD)), [], "sama diagnoza, nie bramka")


def test_a_music_file_with_no_manifest_entry_is_reported() -> None:
    """`check_audio_manifest` sprawdzał SFX-y w obie strony, a muzykę tylko w jedną (O4)."""
    messages = [v.message for v in check_map_coverage(WORLD)
                if v.source == "assets/audio/music"]
    assert_true(bool(messages), "nieużywane utwory są widoczne")
    assert_true(all(".ogg" in m and "kB" in m for m in messages),
                f"komunikat podaje plik i jego wagę: {messages}")


def test_a_map_with_no_music_is_reported() -> None:
    world = _world(audio={"music": {"main_menu": "this-is-epic.ogg"}})
    messages = [v.message for v in check_map_coverage(world) if v.source == "audio.toml:[music]"]
    assert_true(any("BLUNDERHAVEN" in m for m in messages), f"{messages}")
    assert_true(any("MAZE_01" in m for m in messages),
                f"bez klucza `maze` poziomy labiryntu też są nieme: {messages}")


def test_maze_levels_inherit_the_special_music_key() -> None:
    world = _world(audio={"music": {"maze": "caves-of-dawn.ogg"}})
    messages = [v.message for v in check_map_coverage(world) if v.source == "audio.toml:[music]"]
    assert_true(not any("MAZE_" in m for m in messages),
                f"`maze` ma pierwszeństwo przed nazwą mapy: {messages}")


def test_an_unreachable_map_is_reported() -> None:
    """Mapa, do której nie prowadzi żadne wyjście - dokładnie stan `VillageHouse` z O2."""
    village = _map("Village", interactions=[
        ("LOST_CORK_TAVERN", {"obj_type": "exit", "to_map": "LOST_CORK_TAVERN",
                              "destination_entry_point": "Door"}),
    ])
    messages = [v.message for v in check_map_coverage(_world(maps=[village]))
                if v.source == "maps"]
    assert_true(any("JACOBS_CHAMBER" in m for m in messages), f"{messages}")
    assert_true(not any("MAZE_02" in m for m in messages),
                f"poziomy 2+ labiryntu chodzą po schodach z generatora: {messages}")


###############################################################################################################
# MARK: rule 19 - klucze przedmiotów (C02, uwaga autora 2026-08-09)
def _items_world(**overrides: object) -> World:
    """Świat z minimalnym, spójnym zestawem przedmiotów - do psucia po jednym miejscu."""
    config = dict(WORLD.config)
    config["items"] = {"life_pot": {}, "fish": {}}
    fields: dict[str, object] = {
        "config": config,
        "items_csv": [{"key": "life_pot"}, {"key": "fish"}],
        "chests_csv": [],
        "item_tiles": {"life_pot", "fish"},
        "item_sprites": {"life_pot", "fish"},
    }
    fields.update(overrides)
    return _world(**fields)


def test_a_consistent_item_set_reports_nothing() -> None:
    assert_eq(check_item_keys(_items_world()), [], "spójne przedmioty nie zgłaszają nic")


def test_an_item_in_the_csv_but_not_in_the_config_is_an_error() -> None:
    """Objaw zapomnianego `just import-entities` - CSV jest źródłem, config wynikiem."""
    messages = _errors(check_item_keys(_items_world(
        items_csv=[{"key": "life_pot"}, {"key": "fish"}, {"key": "elixir"}])))
    assert_eq(len(messages), 1, f"{messages}")
    assert_true("elixir" in messages[0] and "import-entities" in messages[0], messages[0])


def test_an_item_in_the_config_but_not_in_the_csv_is_an_error() -> None:
    """Zostaje po rename'ie zrobionym tylko w jednym pliku."""
    messages = _errors(check_item_keys(_items_world(items_csv=[{"key": "life_pot"}])))
    assert_true(any("fish" in m for m in messages), f"{messages}")


def test_a_tile_naming_an_item_that_does_not_exist_is_an_error() -> None:
    """`load_items` woła `conf.items[name]` - taki kafel wywala grę przy wczytaniu mapy."""
    messages = _errors(check_item_keys(_items_world(item_tiles={"life_pot", "sushi"})))
    assert_eq(len(messages), 1, f"{messages}")
    assert_true("sushi" in messages[0] and "KeyError" in messages[0], messages[0])


def test_an_item_with_no_sprite_is_an_error() -> None:
    """Bez wpisu w arkuszu `create_item` nie ma czym narysować przedmiotu."""
    messages = _errors(check_item_keys(_items_world(item_sprites={"life_pot"})))
    assert_true(any("fish" in m and "SHEET_DEFINITION" in m for m in messages), f"{messages}")


def test_a_chest_csv_row_with_an_unknown_item_is_an_error() -> None:
    """Reguła 6 patrzyła na `config.chests`, czyli na wynik importu, nie na źródło."""
    messages = _errors(check_item_keys(_items_world(
        chests_csv=[{"key": "BOX", "items": "life_pot,gold_bar", "random_items": ""}])))
    assert_eq(len(messages), 1, f"{messages}")
    assert_true("gold_bar" in messages[0], messages[0])


def test_the_real_world_item_keys_are_consistent() -> None:
    """Bramka regresji: sześć źródeł kluczy przedmiotów mówi dziś to samo."""
    assert_eq(_errors(check_item_keys(WORLD)), [], "klucze przedmiotów są spójne")


###############################################################################################################
# MARK: rule 20 - encje w warunkach (H01, D3)
def _conditions_world(**overrides: object) -> World:
    """Świat z jednym dialogiem, jednym questem i jedną pulą barków - do psucia."""
    config = dict(WORLD.config)
    config["characters"] = {"BARMAN": {}, "COW": {}}
    config["items"] = {"golden_key": {}}
    config["quests"] = {"Q01_LEARN": {}}
    config["dialogs"] = {"BARMAN": {
        "DIALOG_NODES": {"000": {}, "012": {}},
        "DIALOG_OPTIONS": {},
    }}
    config["barks"] = {}
    fields: dict[str, object] = {"config": config, "items_csv": [{"key": "golden_key"}]}
    fields.update(overrides)
    return _world(**fields)


def _with_condition(condition: str, **overrides: object) -> World:
    """Świat, w którym jedna opcja dialogowa Barmana niesie podany warunek."""
    world = _conditions_world(**overrides)
    world.config["dialogs"]["BARMAN"]["DIALOG_OPTIONS"] = {
        "000to012_1": {"condition": condition},
    }
    return world


def test_a_condition_naming_only_real_entities_reports_nothing() -> None:
    world = _with_condition(
        'visited("BARMAN", "012") and has_item("golden_key") and quest_done("Q01_LEARN")'
    )
    assert_eq(_errors(check_condition_entities(world)), [], "poprawny warunek nie zgłasza nic")


def test_a_typo_inside_visited_is_an_error() -> None:
    """Sedno reguły: dziś taka literówka daje cichy `False` na zawsze.

    Tak zniknął kiedyś cały dialog Miecza - opcja, której gracz nigdy nie zobaczył,
    bez jednego komunikatu w konsoli.
    """
    messages = _errors(check_condition_entities(_with_condition('visited("BARMAN", "0012")')))
    assert_eq(len(messages), 1, f"{messages}")
    assert_true("0012" in messages[0] and "cichy False" in messages[0], messages[0])


def test_the_one_argument_visited_is_checked_against_the_owning_character() -> None:
    """W dialogu wiadomo, czyj to graf - więc `visited("013")` też da się sprawdzić."""
    assert_eq(_errors(check_condition_entities(_with_condition('visited("012")'))), [])
    assert_true(_errors(check_condition_entities(_with_condition('visited("013")'))))


def test_an_unknown_quest_is_an_error() -> None:
    """D3: `quest_done` niesie fakt świata, więc skasowanie questa musi być głośne."""
    messages = _errors(check_condition_entities(_with_condition('quest_done("Q99_GHOST")')))
    assert_true(any("Q99_GHOST" in m for m in messages), f"{messages}")


def test_an_unknown_item_in_a_condition_is_an_error() -> None:
    messages = _errors(check_condition_entities(_with_condition('item_count("silver_key") > 1')))
    assert_true(any("silver_key" in m for m in messages), f"{messages}")


def test_bark_only_predicates_are_checked_too() -> None:
    world = _conditions_world()
    world.config["barks"] = {"BARMAN": [
        {"msg": "bark.BARMAN.001", "condition": 'time_of_day("rano")'},
        {"msg": "bark.BARMAN.002", "condition": 'activity("dancing")'},
        {"msg": "bark.BARMAN.003", "condition": 'on_map("NARNIA")'},
    ]}
    messages = _errors(check_condition_entities(world))
    assert_eq(len(messages), 3, f"{messages}")
    assert_true(any("rano" in m for m in messages), f"{messages}")
    assert_true(any("dancing" in m for m in messages), f"{messages}")
    assert_true(any("NARNIA" in m for m in messages), f"{messages}")


def test_a_one_argument_visited_in_a_shared_pool_is_not_guessed_at() -> None:
    """Puli nie da się przypisać do jednego grafu - lepiej milczeć niż zmyślać błąd."""
    world = _conditions_world()
    world.config["barks"] = {"VILLAGERS": [
        {"msg": "bark.VILLAGERS.001", "condition": 'visited("013")'},
    ]}
    assert_eq(_errors(check_condition_entities(world)), [], "pula nie ma jednego właściciela")


def test_an_unparseable_condition_does_not_crash_the_validator() -> None:
    """Składni pilnują importery z `file:line` - walidator ma tylko nie wybuchnąć."""
    assert_eq(_errors(check_condition_entities(_with_condition("to nie jest ==== wyrażenie"))), [])


def test_the_real_world_conditions_name_only_real_entities() -> None:
    """Bramka H01: reguła 20 puszczona na dzisiejszej treści musi wyjść na zero."""
    assert_eq(_errors(check_condition_entities(WORLD)), [], "zastane warunki są spójne")


###############################################################################################################
# MARK: rule 21 - pule barków (H01, D2)
def test_an_empty_barks_cell_is_not_an_error() -> None:
    """Ta sama filozofia, co pusta komórka destynacji: postać po prostu milczy."""
    world = _conditions_world(characters_csv=[{"key": "COW", "barks": ""}])
    assert_eq(check_bark_pools(world), [], "pusta komórka nie jest błędem")


def test_a_barks_cell_naming_a_missing_pool_is_an_error() -> None:
    world = _conditions_world(characters_csv=[{"key": "COW", "barks": "FARM_ANIMALS"}])
    messages = _errors(check_bark_pools(world))
    assert_eq(len(messages), 1, f"{messages}")
    assert_true("FARM_ANIMALS" in messages[0], messages[0])


def test_a_pool_nobody_draws_from_is_a_warning() -> None:
    """Tekst napisany i nigdy nieusłyszany to strata, a nie awaria."""
    world = _conditions_world(characters_csv=[])
    world.config["barks"] = {"FARM_ANIMALS": []}
    violations = check_bark_pools(world)
    assert_eq(_errors(violations), [], "martwa pula nie jest błędem")
    assert_true(any(v.severity == WARN and "FARM_ANIMALS" in v.message for v in violations),
                f"{violations}")


def test_a_characters_own_section_is_not_a_dead_pool() -> None:
    """Klucz postaci w `barks` to jej własna sekcja - ma odbiorcę z definicji."""
    world = _conditions_world(characters_csv=[])
    world.config["barks"] = {"BARMAN": [{"msg": "bark.BARMAN.001", "condition": "True"}]}
    assert_eq(check_bark_pools(world), [], "własna sekcja nie jest martwą pulą")


###############################################################################################################
def main() -> None:
    tests = [
        test_an_instance_named_after_its_model_passes,
        test_an_instance_named_anything_else_is_an_error,
        test_a_number_on_the_only_copy_is_a_warning_not_an_error,
        test_a_door_pointing_at_a_real_entry_point_passes,
        test_a_door_pointing_at_a_missing_entry_point_is_an_error,
        test_a_door_with_no_destination_entry_point_is_an_error,
        test_a_return_point_must_exist_on_the_map_the_door_stands_on,
        test_a_door_into_the_maze_uses_the_template_entry_points,
        test_a_chest_object_must_name_a_chest_in_the_config,
        test_an_unknown_obj_type_is_an_error,
        test_a_door_named_differently_than_its_destination_is_a_warning,
        test_the_real_world_has_no_broken_doors,
        test_a_place_without_a_map_prefix_is_an_error,
        test_a_routine_location_without_a_map_prefix_is_an_error,
        test_a_tile_naming_a_character_that_does_not_exist_is_an_error,
        test_the_real_tilesets_are_clean,
        test_a_reference_to_a_map_outside_the_registry_is_an_error,
        test_a_reference_to_a_maze_level_that_the_registry_knows_passes,
        test_the_real_world_references_only_known_maps,
        test_map_coverage_never_reports_an_error,
        test_a_music_file_with_no_manifest_entry_is_reported,
        test_a_map_with_no_music_is_reported,
        test_maze_levels_inherit_the_special_music_key,
        test_an_unreachable_map_is_reported,
        test_a_consistent_item_set_reports_nothing,
        test_an_item_in_the_csv_but_not_in_the_config_is_an_error,
        test_an_item_in_the_config_but_not_in_the_csv_is_an_error,
        test_a_tile_naming_an_item_that_does_not_exist_is_an_error,
        test_an_item_with_no_sprite_is_an_error,
        test_a_chest_csv_row_with_an_unknown_item_is_an_error,
        test_the_real_world_item_keys_are_consistent,
        test_a_condition_naming_only_real_entities_reports_nothing,
        test_a_typo_inside_visited_is_an_error,
        test_the_one_argument_visited_is_checked_against_the_owning_character,
        test_an_unknown_quest_is_an_error,
        test_an_unknown_item_in_a_condition_is_an_error,
        test_bark_only_predicates_are_checked_too,
        test_a_one_argument_visited_in_a_shared_pool_is_not_guessed_at,
        test_an_unparseable_condition_does_not_crash_the_validator,
        test_the_real_world_conditions_name_only_real_entities,
        test_an_empty_barks_cell_is_not_an_error,
        test_a_barks_cell_naming_a_missing_pool_is_an_error,
        test_a_pool_nobody_draws_from_is_a_warning,
        test_a_characters_own_section_is_not_a_dead_pool,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} validator rule tests passed.")


if __name__ == "__main__":
    main()
