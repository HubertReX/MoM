#!/usr/bin/env python3
"""Unit tests for the two authoring surfaces a new map entity has to cross.

Run from the project root:
    .venv/bin/python tests/test_entity_authoring.py

Both cases here were reported as "either I am doing it wrong, or these are bugs".
They were bugs, and they share a shape: a tool asked the author to repeat
something the toolchain already knew.

1. `validate_world.load_map` read only an object's own <properties>, so a chest
   placed from a tile that already declares `obj_type=chest` in items.tsx was
   reported as having none - while the game, which reads the map through pytmx,
   inherited it fine.
2. `import_entities.import_csv` could create a brand-new entity only for
   `characters`. A new chests.csv row was skipped with a warning that listed
   character columns a chest has never had, so the only way in was editing
   config.json by hand.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project", "config_model"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from import_entities import REQUIRED_FIELDS_BY_ENTITY, import_csv  # noqa: E402
from validate_world import load_map  # noqa: E402


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


# ---------------------------------------------------------------------------
# 1. a property declared on the TILE reaches the object
# ---------------------------------------------------------------------------

_TSX = """<?xml version="1.0" encoding="UTF-8"?>
<tileset version="1.10" name="items" tilewidth="16" tileheight="16" tilecount="4" columns="2">
 <tile id="2">
  <properties>
   <property name="obj_type" value="chest"/>
  </properties>
 </tile>
</tileset>
"""

_TMX = """<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" orientation="orthogonal" width="4" height="4" tilewidth="16" tileheight="16">
 <tileset firstgid="1" source="items.tsx"/>
 <objectgroup id="1" name="interactions">
  <object id="1" name="INHERITED_CHEST" gid="3" x="16" y="16" width="16" height="16"/>
  <object id="2" name="SPELLED_OUT_CHEST" gid="3" x="32" y="16" width="16" height="16">
   <properties>
    <property name="obj_type" value="chest"/>
   </properties>
  </object>
  <object id="3" name="OVERRIDDEN" gid="3" x="48" y="16" width="16" height="16">
   <properties>
    <property name="obj_type" value="exit"/>
   </properties>
  </object>
  <object id="4" name="PLAIN_RECT" x="64" y="16" width="16" height="16"/>
 </objectgroup>
</map>
"""


def _map_props() -> dict[str, dict[str, str]]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "items.tsx").write_text(_TSX, encoding="utf-8")
        (root / "TESTMAP.tmx").write_text(_TMX, encoding="utf-8")
        game_map = load_map(root / "TESTMAP.tmx")
        return dict(game_map.entries("interactions"))


def test_obj_type_is_inherited_from_the_tile() -> None:
    """The author declares it once in the tileset, not once per placed object."""
    props = _map_props()
    assert_eq(
        props["INHERITED_CHEST"].get("obj_type"), "chest",
        "a tile that says 'chest' makes every object placed from it a chest",
    )


def test_a_property_on_the_object_still_wins() -> None:
    """Same precedence as pytmx: object first, tile as the fallback."""
    props = _map_props()
    assert_eq(props["SPELLED_OUT_CHEST"].get("obj_type"), "chest", "agreeing is a no-op")
    assert_eq(
        props["OVERRIDDEN"].get("obj_type"), "exit",
        "the object overrides the tile rather than the other way round",
    )


def test_an_object_without_a_tile_has_no_inherited_properties() -> None:
    """A plain rectangle has no gid, so there is nothing to inherit from."""
    props = _map_props()
    assert_eq(props["PLAIN_RECT"].get("obj_type", ""), "", "no gid, no inheritance")


# ---------------------------------------------------------------------------
# 2. a new CSV row creates the entity, whatever kind it is
# ---------------------------------------------------------------------------


def _import_row(entity: str, header: str, row: str, section: dict) -> dict:
    """Run import_csv against a throwaway <entity>.csv, using the real code path."""
    import import_entities

    with tempfile.TemporaryDirectory() as tmp:
        csv_path = Path(tmp) / f"{entity}.csv"
        csv_path.write_text(f"{header}\n{row}\n", encoding="utf-8")
        original = import_entities.HERE
        import_entities.HERE = Path(tmp)
        try:
            return import_csv(entity, {entity: section})[entity]
        finally:
            import_entities.HERE = original


_CHEST_HEADER = "key;name;total_items_count;random_items;is_small;items;requires_item;consumes_key"


def test_a_new_chest_row_creates_the_chest() -> None:
    """chests.csv is an authoring surface - a new row must reach config.json."""
    out = _import_row(
        "chests",
        _CHEST_HEADER,
        "BLUNDERHAVEN_CATS_CHEST;BLUNDERHAVEN_CATS_CHEST;;;true;fish,fish;;",
        # a section that already holds chests, as config.json always does - see
        # `test_a_list_column_needs_a_sibling_that_already_holds_a_list`
        {"OLD_CHEST": {"name": "OLD_CHEST", "items": ["golden_coin"]}},
    )
    chest = out.get("BLUNDERHAVEN_CATS_CHEST")
    assert_true(chest is not None, f"the chest was created, got {sorted(out)}")
    assert_eq(chest["name"], "BLUNDERHAVEN_CATS_CHEST", "name carried over")
    assert_eq(chest["is_small"], True, "bools are coerced, not left as strings")
    assert_eq(chest["items"], ["fish", "fish"], "a list column becomes a list")


def test_a_list_column_needs_a_sibling_that_already_holds_a_list() -> None:
    """Documents a sharp edge that creation newly exposes - NOT a fixed behaviour.

    `import_csv` decides which columns are lists by looking at the values already
    in the section, so the very first entity of a type would keep `items` as the
    raw string. Every real section has siblings, so nothing hits it today; this
    test exists so the day someone bootstraps an empty section, the surprise is
    already written down.
    """
    out = _import_row(
        "chests",
        _CHEST_HEADER,
        "FIRST_EVER_CHEST;FIRST_EVER_CHEST;;;true;fish,fish;;",
        {},
    )
    assert_eq(
        out["FIRST_EVER_CHEST"]["items"], "fish,fish",
        "with no sibling to learn from, the list column stays a string",
    )


def test_a_row_that_cannot_stand_on_its_own_is_still_refused() -> None:
    """The guard against a typo'd key survives - it just knows the right columns now.

    `name` is the one Chest field with no model default, so a row without it
    cannot become an entity.
    """
    out = _import_row(
        "chests",
        "key;name;is_small",
        "TYPOED_KEY;;true",
        {"REAL_CHEST": {"name": "REAL_CHEST"}},
    )
    assert_eq(sorted(out), ["REAL_CHEST"], "the bad row was skipped, the good one kept")


def test_an_existing_row_is_updated_not_duplicated() -> None:
    out = _import_row(
        "chests",
        "key;name;is_small",
        "REAL_CHEST;REAL_CHEST;false",
        {"REAL_CHEST": {"name": "REAL_CHEST", "is_small": True}},
    )
    assert_eq(sorted(out), ["REAL_CHEST"], "no second entity appeared")
    assert_eq(out["REAL_CHEST"]["is_small"], False, "the row won over the old value")


def test_every_imported_entity_type_declares_its_required_fields() -> None:
    """A type missing from the map would silently accept any row as a new entity."""
    from settings import CONF_ENTITIES_TO_STORE

    missing = sorted(set(CONF_ENTITIES_TO_STORE) - set(REQUIRED_FIELDS_BY_ENTITY))
    assert_eq(missing, [], "every entity type import_entities writes has a required list")


def main() -> None:
    tests = [
        test_obj_type_is_inherited_from_the_tile,
        test_a_property_on_the_object_still_wins,
        test_an_object_without_a_tile_has_no_inherited_properties,
        test_a_new_chest_row_creates_the_chest,
        test_a_list_column_needs_a_sibling_that_already_holds_a_list,
        test_a_row_that_cannot_stand_on_its_own_is_still_refused,
        test_an_existing_row_is_updated_not_duplicated,
        test_every_imported_entity_type_declares_its_required_fields,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} entity authoring tests passed.")


if __name__ == "__main__":
    main()
