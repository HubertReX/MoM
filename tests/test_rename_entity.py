#!/usr/bin/env python3
"""Unit tests for `scripts/rename_entity.py` (C02 etap 5: D10, D17).

Run from the project root:
    .venv/bin/python tests/test_rename_entity.py

Obawa z W12 jest trafna i to ona jest powodem tego pliku: `rename_entity.py` zna
listę źródeł, w których siedzą nazwy encji. Za pół roku dojdzie `quests.csv` albo
nowy katalog map i pierwszy rename po cichu zostawi jedno źródło nietknięte -
walidator tego nie złapie, bo świat *pozostanie* spójny, tylko wokół starej nazwy.

Dlatego dwie bramki, w dwie różne strony:

1. **Pokrycie manifestu.** Każdy plik danych w repo jest albo objęty globem
   z `SOURCES`, albo wpisany do `UNTOUCHED_SOURCES` z powodem. Nowy plik danych
   failuje ten test w dniu, w którym powstaje - a nie przy pierwszym rename'ie po nim.
2. **Rename naprawdę działa.** Na KOPII świata w katalogu tymczasowym skrypt zmienia
   znaną encję każdego rodzaju, a test sprawdza, że stara nazwa nie została nigdzie
   i że nowa stoi w każdym źródle, w którym stała stara.

Test jest bezpieczny: nigdy nie pisze do plików repo (rename operuje na kopii, do
której przepięty jest `REPO_ROOT` skryptu), nie uruchamia gry i nie potrzebuje ekranu.
Wzór z `tests/test_config_web_codegen.py`, który tak samo pilnuje, że `config.py`
nie rozjechał się z generatorem.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import rename_entity                                            # noqa: E402
from rename_entity import (                                     # noqa: E402
    CHARACTER, CHEST, ENTRY_POINT, INSTANCE, ITEM, KINDS, MAP,
    MAP_SCOPED_KINDS, MAZE_ORIGIN, PLACE, SOURCES, UNTOUCHED_SOURCES,
    xml_object_names,
)


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}\n  expected: {b!r}\n  actual:   {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


###############################################################################################################
# 1. Manifest pokrywa repo
###############################################################################################################

def test_every_data_file_is_either_covered_or_explicitly_excluded() -> None:
    """Bramka z D17: nowy plik danych musi być świadomie zaklasyfikowany."""
    covered = rename_entity.covered_files()
    excluded = rename_entity.untouched_paths()
    orphans = [str(path.relative_to(ROOT)) for path in rename_entity.data_files()
               if path not in covered and path not in excluded]
    assert_eq(orphans, [],
              "dopisz glob do SOURCES albo wpis z powodem do UNTOUCHED_SOURCES "
              "w scripts/rename_entity.py")


def test_the_exclusion_list_has_no_stale_entries() -> None:
    """Wpis o pliku, którego już nie ma, usypia czujność następnego czytelnika.

    Klucz bywa globem (`**/*_base.tmx`), więc pytamy o TRAFIENIA, a nie o `exists()`:
    wzorzec, który dziś nie łapie niczego, jest tak samo martwy jak nieistniejąca ścieżka.
    """
    missing = [path for path in UNTOUCHED_SOURCES if not list(ROOT.glob(path))]
    assert_eq(missing, [], "te wpisy nie łapią żadnego pliku - skasuj je")


def test_no_file_is_both_covered_and_excluded() -> None:
    """Sprzeczny manifest kłamie w obie strony naraz."""
    covered = rename_entity.covered_files()
    both = sorted(str(hit.relative_to(ROOT))
                  for path in UNTOUCHED_SOURCES for hit in ROOT.glob(path) if hit in covered)
    assert_eq(both, [], "plik jest jednocześnie w SOURCES i w UNTOUCHED_SOURCES")


def test_every_source_glob_matches_at_least_one_file() -> None:
    """Glob, który nic nie łapie, wygląda na pokrycie, a nim nie jest."""
    empty = [source.glob for source in SOURCES if not source.paths()]
    assert_eq(empty, [], "martwy glob w SOURCES - katalog się przeniósł?")


###############################################################################################################
# 2. Rename działa - na kopii świata, nigdy na repo
###############################################################################################################

def _sandbox() -> tempfile.TemporaryDirectory[str]:
    """Kopia plików danych repo z przepiętym `REPO_ROOT` skryptu."""
    box = tempfile.TemporaryDirectory()
    root = Path(box.name)
    for path in rename_entity.data_files():
        target = root / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    rename_entity.REPO_ROOT = root
    rename_entity.GAME_MAPS_DIR = root / "project/assets/NinjaAdventure/maps"
    return box


def _restore() -> None:
    rename_entity.REPO_ROOT = ROOT
    rename_entity.GAME_MAPS_DIR = ROOT / "project/assets/NinjaAdventure/maps"


def _occurrences(root: Path, needle: str) -> list[str]:
    """Pliki, w których *needle* stoi jako samodzielny token."""
    import re
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(needle)}(?![A-Za-z0-9_])")
    return [str(path.relative_to(root))
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.suffix in rename_entity.DATA_SUFFIXES
            and pattern.search(path.read_text(encoding="utf-8"))]


def _rename_in_sandbox(kind: str, old: str, new: str) -> tuple[Path, list[str], list[str]]:
    """Zwraca (korzeń kopii, pliki ze starą nazwą PRZED, pliki ze starą nazwą PO)."""
    box = _sandbox()
    try:
        root = Path(box.name)
        before = _occurrences(root, old)
        rename_entity.rename(old, new, kind)
        after = _occurrences(root, old)
        # kopia żyje tylko w tym bloku, więc listy plików wyciągamy od razu
        return root, before, after
    finally:
        _restore()
        box.cleanup()


def test_renaming_a_map_touches_every_source_and_the_file_itself() -> None:
    """Nazwa mapy siedzi w pliku, w `to_map`, w audio, w locale i w prefiksach miejsc."""
    box = _sandbox()
    try:
        root = Path(box.name)
        maps = root / "project/assets/NinjaAdventure/maps"
        changes = rename_entity.rename("LOST_CORK_TAVERN", "TEST_TAVERN", MAP)
        touched = {change.path.name for change in changes}

        assert_true((maps / "TEST_TAVERN.tmx").exists(), "plik mapy nie został przemianowany")
        assert_true(not (maps / "LOST_CORK_TAVERN.tmx").exists(), "stary plik mapy został")
        for expected in ("BLUNDERHAVEN.tmx", "audio.toml", "PL.toml", "EN.toml",
                         "characters.csv", "config.json"):
            assert_true(expected in touched, f"{expected} nie zostało ruszone: {sorted(touched)}")
        assert_eq(_occurrences(root, "LOST_CORK_TAVERN"), [], "stara nazwa mapy gdzieś została")
    finally:
        _restore()
        box.cleanup()


def test_renaming_a_character_leaves_display_names_alone() -> None:
    """Klucz `HORSE` i napis `Horse` brzmią tak samo - i są zupełnie różnymi bytami."""
    box = _sandbox()
    try:
        root = Path(box.name)
        csv_path = root / "project/config_model/characters.csv"
        rename_entity.rename("HORSE", "PONY", CHARACTER)
        row = next(line for line in csv_path.read_text(encoding="utf-8").splitlines()
                   if line.startswith("PONY;"))
        cells = row.split(";")
        assert_eq(cells[1], "Horse", "name_EN (napis dla gracza) został ruszony")
        assert_eq(cells[3], "Horse", "sprite (nazwa katalogu) został ruszony")
        # Spawn na mapie nazywa się dziś `HORSE` (instancja) - to inny rodzaj klucza
        # i rename modelu świadomie go nie rusza. Nie wymieniamy map z imienia: koni
        # na mapach przybywa (każda mapa z zagrodą ma swojego), a testem jest REGUŁA
        # "zostało wyłącznie w `spawn_points`", nie spis plików z konkretnego dnia.
        left = _occurrences(root, "HORSE")
        maps_dir = "project/assets/NinjaAdventure/maps/"
        assert_true("project/assets/NinjaAdventure/maps/BLUNDERHAVEN.tmx" in left,
                    f"instancja `HORSE` powinna przeżyć rename modelu: {left}")
        for path in left:
            assert_true(path.startswith(maps_dir) and path.endswith(".tmx"),
                        f"stary klucz modelu został poza mapami: {path}")
            names = xml_object_names((root / path).read_text(encoding="utf-8"), "spawn_points")
            assert_true("HORSE" in names,
                        f"`HORSE` w {path} nie jest nazwą instancji - rename go pominął")
        tileset = (root / "project/assets/NinjaAdventure/maps/tilesets/CharacterTileset.tsx"
                   ).read_text(encoding="utf-8")
        assert_true('value="PONY"' in tileset, "kafel tilesetu nie poszedł za kluczem")
    finally:
        _restore()
        box.cleanup()


def test_renaming_an_instance_follows_the_waypoint_curve_and_the_routine() -> None:
    """Nazwa instancji jest jednocześnie kluczem krzywej i celem `route:` w rutynie."""
    box = _sandbox()
    try:
        root = Path(box.name)
        rename_entity.rename("ROBIN", "TEST_ROBIN", INSTANCE)
        village = (root / "project/assets/NinjaAdventure/maps/BLUNDERHAVEN.tmx").read_text(
            encoding="utf-8")
        routines = (root / "project/config_model/routines.toml").read_text(encoding="utf-8")
        assert_eq(village.count('name="TEST_ROBIN"'), 2, "spawn i krzywa mają iść razem")
        assert_true("route:TEST_ROBIN" in routines, "rutyna nie poszła za nazwą")
        assert_true('name="ROBIN"' not in village, "stara nazwa instancji została na mapie")
        assert_true("route:ROBIN" not in routines, "stara nazwa instancji została w rutynie")
    finally:
        _restore()
        box.cleanup()


def test_renaming_an_instance_leaves_the_character_key_alone() -> None:
    """Po C02 instancja i model brzmią tak samo - i dalej są osobnymi bytami.

    `ROBIN` w `spawn_points` to nazwa obiektu Tiled (klucz stanu w zapisie), a `ROBIN`
    w `characters.csv` to klucz modelu. Zbieżność nazw jest wynikiem konwencji z D1,
    nie tożsamością: rename jednego nie może pociągnąć drugiego.
    """
    box = _sandbox()
    try:
        root = Path(box.name)
        rename_entity.rename("ROBIN", "TEST_ROBIN", INSTANCE)
        csv_text = (root / "project/config_model/characters.csv").read_text(encoding="utf-8")
        assert_true(any(line.startswith("ROBIN;") for line in csv_text.splitlines()),
                    "klucz modelu ROBIN zniknął przy rename'ie instancji")
        tileset = (root / "project/assets/NinjaAdventure/maps/tilesets/CharacterTileset.tsx"
                   ).read_text(encoding="utf-8")
        assert_true('value="ROBIN"' in tileset, "kafel tilesetu zmienił model_name")
    finally:
        _restore()
        box.cleanup()


def test_renaming_a_place_updates_only_the_suffix_of_prefixed_cells() -> None:
    """`LOST_CORK_TAVERN:bar` - rename miejsca rusza `bar`, nie prefiks mapy."""
    box = _sandbox()
    try:
        root = Path(box.name)
        rename_entity.rename("bar", "counter", PLACE)
        csv_text = (root / "project/config_model/characters.csv").read_text(encoding="utf-8")
        assert_true("LOST_CORK_TAVERN:counter" in csv_text, "miejsce nie poszło za rename'em")
        assert_true("LOST_CORK_TAVERN:bedroom" in csv_text, "prefiks mapy ucierpiał")
        tavern = (root / "project/assets/NinjaAdventure/maps/LOST_CORK_TAVERN.tmx").read_text(
            encoding="utf-8")
        assert_true('name="counter"' in tavern, "obiekt w warstwie `places` nie zmienił nazwy")
    finally:
        _restore()
        box.cleanup()


def test_renaming_a_chest_updates_csv_config_and_the_map_object() -> None:
    """Klucz skrzyni żyje w `chests.csv`, w `config.json` i jako nazwa obiektu na mapie."""
    _, before, after = _rename_in_sandbox(CHEST, "MAZE_01_BIG_CHEST", "TEST_CHEST")
    assert_true(len(before) >= 3, f"za mało źródeł do sprawdzenia: {before}")
    assert_eq(after, [], "stary klucz skrzyni gdzieś został")


def test_renaming_an_entry_point_follows_both_properties() -> None:
    """Punkt wejścia jest wskazywany z drugiej mapy (`destination_entry_point`)."""
    _, before, after = _rename_in_sandbox(ENTRY_POINT, "LOST_CORK_TAVERN_DOOR", "TEST_DOOR")
    assert_true(len(before) >= 2, f"punkt wejścia powinien stać w co najmniej 2 plikach: {before}")
    assert_eq(after, [], "stara nazwa punktu wejścia gdzieś została")


def test_the_sandbox_never_touched_the_repo() -> None:
    """Bezpiecznik: po wszystkich rename'ach świat w repo jest nietknięty."""
    assert_eq(rename_entity.REPO_ROOT, ROOT, "skrypt został przepięty na kopię")
    for name in ("LOST_CORK_TAVERN", "HORSE", "ROBIN", "MAZE_01_BIG_CHEST"):
        assert_true(bool(_occurrences(ROOT / "project", name)),
                    f"'{name}' zniknął z repo - test pisał po plikach projektu")


###############################################################################################################
# 4. Klucze przedmiotów i pochodzenie kluczy zależnych od mapy
###############################################################################################################

def test_renaming_an_item_reaches_every_source_including_the_tileset() -> None:
    """Klucz przedmiotu siedzi w sześciu miejscach - kafel `items.tsx` jest tym,
    o którym najłatwiej zapomnieć, a to on wywala grę `KeyError`-em."""
    box = _sandbox()
    try:
        root = Path(box.name)
        changes = rename_entity.rename("life_pot", "TEST_POTION", ITEM)
        touched = {change.path.name for change in changes}
        for expected in ("items.csv", "items.tsx", "config.json",
                         "characters.csv", "chests.csv"):
            assert_true(expected in touched, f"{expected} nie ruszone: {sorted(touched)}")
        left = [f for f in _occurrences(root, "life_pot")
                if "autogenerated_config" not in f]      # martwy artefakt, patrz UNTOUCHED_SOURCES
        assert_eq(left, [], "stary klucz przedmiotu gdzieś został")
    finally:
        _restore()
        box.cleanup()


def test_renaming_an_item_follows_it_into_dialogue_conditions() -> None:
    """`has_item("klucz")` to fragment mini-DSL wewnątrz stringa, nie pole danych."""
    box = _sandbox()
    try:
        root = Path(box.name)
        rename_entity.rename("PHOENIX_FEATHER", "PHOENIX_QUILL", ITEM)
        config = (root / "project/config_model/config.json").read_text(encoding="utf-8")
        assert_true('has_item(\\"PHOENIX_QUILL\\")' in config
                    or "has_item(\"PHOENIX_QUILL\")" in config
                    or "PHOENIX_QUILL" in config, "warunek nie poszedł za nazwą")
        assert_true("PHOENIX_FEATHER" not in config, "stary klucz został w warunku")
    finally:
        _restore()
        box.cleanup()


def test_renaming_an_item_leaves_its_display_name_alone() -> None:
    """`name_EN`/`name_PL` przedmiotu to napis dla gracza, nie klucz."""
    box = _sandbox()
    try:
        root = Path(box.name)
        rename_entity.rename("life_pot", "TEST_POTION", ITEM)
        row = next(line for line in (root / "project/config_model/items.csv").read_text(
            encoding="utf-8").splitlines() if line.startswith("TEST_POTION;"))
        assert_true("Life potion" in row, f"napis dla gracza ucierpiał: {row}")
    finally:
        _restore()
        box.cleanup()


def test_map_scoped_keys_report_the_map_that_defines_them() -> None:
    """`Door` istnieje na kilku mapach - bez etykiety `--list` udawał jeden klucz."""
    known = rename_entity.existing_keys_with_origin()
    assert_true("LOST_CORK_TAVERN" in known[ENTRY_POINT]["Door"],
                f"{known[ENTRY_POINT]['Door']}")
    # Studnia stoi w niejednej wsi, więc pytamy o ZASIĘG, a nie o liczbę map: klucz
    # miejsca ma nieść etykietę mapy (odróżnia `well` z dwóch wiosek), a nie być
    # globalny. Przypięcie do jednej mapy failowało w dniu, w którym powstała druga.
    assert_true("BLUNDERHAVEN" in known[PLACE]["well"],
                f"miejsce ma nieść mapę, z której pochodzi: {known[PLACE]['well']}")
    assert_true(all(origin for origin in known[PLACE]["well"]),
                "pusta etykieta znaczy 'klucz globalny' - miejsce nim nie jest")


def test_an_origin_is_where_a_key_is_defined_not_where_it_is_referenced() -> None:
    """`BLUNDERHAVEN` celuje w punkt `Entry`, ale definiuje go szablon labiryntu."""
    known = rename_entity.existing_keys_with_origin()
    assert_eq(known[ENTRY_POINT]["Entry"], {MAZE_ORIGIN},
              "punkt wejścia labiryntu pochodzi z szablonu, nie z wioski")


def test_global_keys_carry_no_origin() -> None:
    """Klucz postaci, mapy, skrzyni i przedmiotu jest jeden w całej grze."""
    known = rename_entity.existing_keys_with_origin()
    for kind in KINDS:
        if kind in MAP_SCOPED_KINDS:
            continue
        with_origin = {key for key, origins in known[kind].items() if origins}
        assert_eq(with_origin, set(), f"{kind} nie jest zależny od mapy")


def test_the_maze_template_placeholders_are_not_listed_as_keys() -> None:
    """`to_map="Return"` i `return_entry_point="0"` to wartości nadpisywane w locie."""
    known = rename_entity.existing_keys()
    assert_true("Return" not in known[MAP], "atrapa `Return` udaje mapę")
    assert_true("0" not in known[ENTRY_POINT], "atrapa `0` udaje punkt wejścia")
    assert_true("Stairs" not in known[ENTRY_POINT], "atrapa `Stairs` udaje punkt wejścia")
    assert_true("Entry" in known[ENTRY_POINT], "prawdziwy punkt wejścia zniknął razem z nimi")
    assert_true("Re-Entry" in known[ENTRY_POINT], "prawdziwy punkt wejścia zniknął razem z nimi")


def test_obsidian_mentions_point_at_the_vault_files_to_fix_by_hand() -> None:
    """Skrypt nie edytuje `doc/`, więc musi powiedzieć, gdzie autor ma zajrzeć."""
    mentions = rename_entity.obsidian_mentions("PHOENIX_FEATHER")
    assert_true(bool(mentions), "klucz questowego przedmiotu musi być widoczny w vault'cie")
    assert_true(all(path.startswith("doc/") for path in mentions), f"{mentions}")
    assert_eq(rename_entity.obsidian_mentions("NIE_MA_TAKIEJ_NAZWY_W_VAULCIE"), [])


###############################################################################################################
# 5. Zakres `MAPA:nazwa` - zmiana tylko na jednej mapie
###############################################################################################################

def test_a_scoped_place_rename_leaves_the_other_map_alone() -> None:
    """`tables` stoi w tawernie i w domu w wiosce - prawie zawsze chodzi o jedno z nich."""
    box = _sandbox()
    try:
        root = Path(box.name)
        rename_entity.rename("tables", "dining_tables", PLACE, scope="LOST_CORK_TAVERN")
        tavern = (root / "project/assets/NinjaAdventure/maps/LOST_CORK_TAVERN.tmx").read_text(
            encoding="utf-8")
        other = (root / "project/assets/NinjaAdventure/maps/_wip/VillageHouse.tmx").read_text(
            encoding="utf-8")
        assert_true('name="dining_tables"' in tavern, "mapa w zakresie nie została zmieniona")
        assert_true('name="tables"' in other, "mapa spoza zakresu została ruszona")
    finally:
        _restore()
        box.cleanup()


def test_a_scoped_place_rename_only_touches_cells_with_that_map_prefix() -> None:
    """Prefiks w komórce jest jedynym, co odróżnia dwa miejsca o tej samej nazwie."""
    box = _sandbox()
    try:
        root = Path(box.name)
        csv_path = root / "project/config_model/characters.csv"
        before = csv_path.read_text(encoding="utf-8")
        assert_true("LOST_CORK_TAVERN:tables" in before, "fixture stracił sens")
        rename_entity.rename("tables", "dining_tables", PLACE, scope="BLUNDERHAVEN")
        after = csv_path.read_text(encoding="utf-8")
        assert_true("LOST_CORK_TAVERN:tables" in after,
                    "komórka z innym prefiksem została zmieniona")
        assert_true("dining_tables" not in after, "coś się zmieniło mimo pustego zakresu")
    finally:
        _restore()
        box.cleanup()


def test_a_scoped_entry_point_follows_only_doors_leading_to_that_map() -> None:
    """`destination_entry_point` nazywa punkt na mapie z `to_map` tego samego obiektu.

    Wioska ma dwa wyjścia celujące w punkt `Door` - jedno do tawerny, drugie do komnaty.
    Zakres musi rozdzielić je po `to_map`, a nie po pliku, w którym stoją.
    """
    box = _sandbox()
    try:
        root = Path(box.name)
        rename_entity.rename("Door", "TAVERN_DOOR", ENTRY_POINT, scope="LOST_CORK_TAVERN")
        village = (root / "project/assets/NinjaAdventure/maps/BLUNDERHAVEN.tmx").read_text(
            encoding="utf-8")
        chamber = (root / "project/assets/NinjaAdventure/maps/JACOBS_CHAMBER.tmx").read_text(
            encoding="utf-8")
        assert_eq(village.count('value="TAVERN_DOOR"'), 1, "zmieniono więcej niż jedne drzwi")
        assert_true('value="Door"' in village, "wyjście do komnaty straciło swój punkt")
        assert_true('name="Door"' in chamber, "punkt wejścia komnaty został przemianowany")
    finally:
        _restore()
        box.cleanup()


def test_a_scoped_instance_rename_skips_the_bare_route_reference() -> None:
    """`route:ROB` bez prefiksu mapy jest niejednoznaczny - lepiej zostawić i powiedzieć."""
    box = _sandbox()
    try:
        root = Path(box.name)
        rename_entity.rename("ROB", "GUARD_ROB", INSTANCE, scope="BLUNDERHAVEN")
        routines = (root / "project/config_model/routines.toml").read_text(encoding="utf-8")
        assert_true("route:ROB" in routines, "goła nazwa została zmieniona mimo zakresu")
        village = (root / "project/assets/NinjaAdventure/maps/BLUNDERHAVEN.tmx").read_text(
            encoding="utf-8")
        assert_eq(village.count('name="GUARD_ROB"'), 2, "spawn i krzywa mają iść razem")
    finally:
        _restore()
        box.cleanup()
    assert_true(bool(rename_entity.bare_route_references("ROB")),
                "skrypt musi umieć wskazać taki krok do sprawdzenia")


def test_an_unscoped_rename_still_changes_every_map() -> None:
    """Zakres jest opcją, nie nowym wymogiem - stare wywołanie ma działać jak dotąd."""
    box = _sandbox()
    try:
        root = Path(box.name)
        rename_entity.rename("tables", "dining_tables", PLACE)
        for path in ("LOST_CORK_TAVERN.tmx", "_wip/VillageHouse.tmx"):
            text = (root / "project/assets/NinjaAdventure/maps" / path).read_text(encoding="utf-8")
            assert_true('name="dining_tables"' in text, f"{path} nie zostało zmienione")
    finally:
        _restore()
        box.cleanup()


def test_the_scope_prefix_is_parsed_and_validated() -> None:
    assert_eq(rename_entity.split_scope("LOST_CORK_TAVERN:tables"),
              ("LOST_CORK_TAVERN", "tables"))
    assert_eq(rename_entity.split_scope("tables"), ("", "tables"))
    try:
        rename_entity.split_scope("NIE_MA_TAKIEJ_MAPY:tables")
    except SystemExit as exc:
        assert_true("nie jest mapą" in str(exc), str(exc))
    else:
        raise AssertionError("nieistniejąca mapa w zakresie przeszła bez błędu")


def test_a_global_key_cannot_be_scoped_to_one_map() -> None:
    """Klucz postaci jest jeden w całej grze - obietnica zawężenia byłaby fałszywa."""
    try:
        rename_entity.split_scope("BLUNDERHAVEN:HORSE", CHARACTER)
    except SystemExit as exc:
        assert_true("globalny" in str(exc), str(exc))
        return
    raise AssertionError("zakres dla klucza globalnego przeszedł bez błędu")


def test_the_scope_resolves_the_instance_vs_model_ambiguity() -> None:
    """Po C02 nazwa instancji JEST kluczem modelu, więc bez zakresu `ROB` jest dwuznaczny."""
    assert_eq(rename_entity.detect_kind("ROB", MAP_SCOPED_KINDS), INSTANCE)
    try:
        rename_entity.detect_kind("ROB")
    except SystemExit as exc:
        assert_true("--kind" in str(exc), str(exc))
        return
    raise AssertionError("dwuznaczna nazwa bez zakresu przeszła bez pytania o --kind")


###############################################################################################################
# 3. Kontrakt CLI
###############################################################################################################

def test_kind_is_detected_from_where_the_name_stands_today() -> None:
    """`just rename-entity <stara> <nowa>` ma dwa argumenty - rodzaj wynika z danych."""
    assert_eq(rename_entity.detect_kind("LOST_CORK_TAVERN"), MAP)
    assert_eq(rename_entity.detect_kind("FISH_RED_01"), INSTANCE)
    assert_eq(rename_entity.detect_kind("house_bart"), PLACE)
    assert_eq(rename_entity.detect_kind("MAZE_01_BIG_CHEST"), CHEST)


def test_an_unknown_name_stops_the_script_instead_of_editing_nothing() -> None:
    """Literówka w nazwie ma boleć od razu, a nie wyglądać jak udany przebieg."""
    try:
        rename_entity.detect_kind("NIE_MA_TAKIEJ_ENCJI")
    except SystemExit as exc:
        assert_true("NIE_MA_TAKIEJ_ENCJI" in str(exc), f"nieczytelny komunikat: {exc}")
        return
    raise AssertionError("nieznana nazwa przeszła bez błędu")


def test_every_kind_has_at_least_one_source() -> None:
    """Rodzaj klucza bez źródła to rename, który nic nie robi i nic nie mówi."""
    known = rename_entity.existing_keys()
    empty = [kind for kind in KINDS if not known[kind]]
    assert_eq(empty, [], "rodzaj bez ani jednego klucza w repo")


def test_a_rename_reaches_inside_bark_conditions() -> None:
    """Barki to trzecia treść z warunkami - i jedyna, która pyta o mapę.

    Bez tego rename mapy zostawiał `on_map("STARA")` w sekcji `barks`, czyli warunek,
    który już nigdy nie zapali. Test jest na samej funkcji, a nie na treści repo:
    pokrycie nie może zależeć od tego, czy autor akurat trzyma taki bark w `Barki.md`.
    """
    data = {
        "barks": {
            "BARMAN": [{"msg": "bark.BARMAN.001", "condition": 'on_map("LOST_CORK_TAVERN")'}],
            "VILLAGERS": [
                {"msg": "bark.VILLAGERS.001", "condition": 'visited("BARMAN", "012")'},
                {"msg": "bark.VILLAGERS.002", "condition": 'has_item("golden_key")'},
                {"msg": "bark.VILLAGERS.003", "condition": "True"},
            ],
        }
    }

    assert_eq(rename_entity._rename_in_barks(data, MAP, "LOST_CORK_TAVERN", "TAVERN"), 1)
    assert_eq(data["barks"]["BARMAN"][0]["condition"], 'on_map("TAVERN")')

    # postać: klucz właściciela puli ORAZ argument `visited(...)` w warunku
    assert_eq(rename_entity._rename_in_barks(data, CHARACTER, "BARMAN", "BARKEEP"), 2)
    assert_true("BARKEEP" in data["barks"], f"{list(data['barks'])}")
    assert_eq(data["barks"]["VILLAGERS"][0]["condition"], 'visited("BARKEEP", "012")')

    assert_eq(rename_entity._rename_in_barks(data, ITEM, "golden_key", "brass_key"), 1)
    assert_eq(data["barks"]["VILLAGERS"][1]["condition"], 'has_item("brass_key")')

    # rodzaj, którego w warunkach barków nie ma, nie rusza niczego
    assert_eq(rename_entity._rename_in_barks(data, CHEST, "MAZE_01_BIG_CHEST", "X"), 0)


def main() -> None:
    tests = [
        test_every_data_file_is_either_covered_or_explicitly_excluded,
        test_the_exclusion_list_has_no_stale_entries,
        test_no_file_is_both_covered_and_excluded,
        test_every_source_glob_matches_at_least_one_file,
        test_renaming_a_map_touches_every_source_and_the_file_itself,
        test_renaming_a_character_leaves_display_names_alone,
        test_renaming_an_instance_follows_the_waypoint_curve_and_the_routine,
        test_renaming_an_instance_leaves_the_character_key_alone,
        test_renaming_a_place_updates_only_the_suffix_of_prefixed_cells,
        test_renaming_a_chest_updates_csv_config_and_the_map_object,
        test_renaming_an_entry_point_follows_both_properties,
        test_the_sandbox_never_touched_the_repo,
        test_kind_is_detected_from_where_the_name_stands_today,
        test_an_unknown_name_stops_the_script_instead_of_editing_nothing,
        test_every_kind_has_at_least_one_source,
        test_renaming_an_item_reaches_every_source_including_the_tileset,
        test_renaming_an_item_follows_it_into_dialogue_conditions,
        test_renaming_an_item_leaves_its_display_name_alone,
        test_map_scoped_keys_report_the_map_that_defines_them,
        test_an_origin_is_where_a_key_is_defined_not_where_it_is_referenced,
        test_global_keys_carry_no_origin,
        test_the_maze_template_placeholders_are_not_listed_as_keys,
        test_obsidian_mentions_point_at_the_vault_files_to_fix_by_hand,
        test_a_scoped_place_rename_leaves_the_other_map_alone,
        test_a_scoped_place_rename_only_touches_cells_with_that_map_prefix,
        test_a_scoped_entry_point_follows_only_doors_leading_to_that_map,
        test_a_scoped_instance_rename_skips_the_bare_route_reference,
        test_an_unscoped_rename_still_changes_every_map,
        test_the_scope_prefix_is_parsed_and_validated,
        test_a_global_key_cannot_be_scoped_to_one_map,
        test_the_scope_resolves_the_instance_vs_model_ambiguity,
        test_a_rename_reaches_inside_bark_conditions,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} rename-entity tests passed.")


if __name__ == "__main__":
    main()
