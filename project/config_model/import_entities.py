#!/usr/bin/env python3
"""Import CSV files into config.json, overwriting entity data sections.

Reads characters.csv, items.csv, chests.csv and maze_configs.csv,
merges values into config.json, preserving dialogs and messages.
"""

import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "config.json"

sys.path.insert(0, str(HERE.parent))
from settings import CONF_ENTITIES_TO_STORE, DEFAULT_DISPOSITION_WEIGHTS  # noqa: E402

# characters.csv keeps per-sentiment weight columns (author-facing names,
# filled from Markdown frontmatter by `just import-dialogs`); they are
# aggregated into the `disposition` dict of the characters section here.
# `neutral` and `technical` always weigh 0 and have no CSV columns.
SENTIMENT_COLUMNS = ("kind", "weak", "angry", "smart", "funny")

# Minimal columns that must be present (non-empty) in a characters.csv row
# before a brand-new character entity may be created from it. These are the
# only fields of the character model without a default (see config_pydantic);
# every other field falls back to its model default.
REQUIRED_CHARACTER_FIELDS = ("name_EN", "name_PL", "sprite", "race", "attitude")


def _strip_nulls(obj: object) -> object:
    """Recursively remove dict entries with ``None`` values."""
    if isinstance(obj, dict):
        return {k: _strip_nulls(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_strip_nulls(v) for v in obj]
    return obj


def _cell_to_json(raw: str) -> object:
    """Try parsing a CSV cell as JSON (for lists/dicts), fallback to raw string."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return raw


def _parse_list(raw: str) -> list:
    """Parse a CSV cell holding a list.

    Lists are authored comma-separated (``water,shore``) because a cell of JSON
    is miserable to hand-edit and the column separator is ``;``, so the comma is
    free. The JSON form is still accepted so cells written by older exports (and
    anything pasted from `config.json`) keep working.
    """
    parsed = _cell_to_json(raw)
    if isinstance(parsed, list):
        return parsed
    return [part.strip() for part in raw.split(",") if part.strip()]


def parse_value(raw: str, current: object, is_list: bool = False) -> object:
    """Parse a CSV cell value to match the type of the current value.

    ``is_list`` marks a column that holds a list in *some* entity of the section,
    which is the only clue available when this particular entity has no value yet
    (a freshly created row) - without it a one-element list would land as a bare
    string.
    """
    if raw == "":
        return current
    if isinstance(current, bool):
        return raw.lower() in ("true", "1", "yes")
    if isinstance(current, int):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    if isinstance(current, list):
        return _parse_list(raw)
    if isinstance(current, dict):
        parsed = _cell_to_json(raw)
        if isinstance(parsed, dict):
            return parsed
        return current
    if current is None:
        if is_list:
            return _parse_list(raw)
        # New field with no existing value to match (e.g. a freshly created
        # character row) - infer the JSON type so booleans/ints/lists don't
        # land as strings (e.g. has_dialog "true" -> True).
        return _cell_to_json(raw)
    return raw


def import_csv(entity_name: str, data: dict) -> dict:
    """Read <entity_name>.csv and merge fields into data's entity section."""
    csv_file = HERE / f"{entity_name}.csv"
    if not csv_file.exists():
        print(f"  [SKIP] {csv_file} not found")
        return data

    lines = csv_file.read_text().strip().splitlines()
    if len(lines) < 2:
        print(f"  [SKIP] {csv_file} empty")
        return data

    header = lines[0].split(";")
    fields = header[1:]

    section = data.get(entity_name, {})
    updated = 0
    created = 0

    # Columns that hold a list somewhere in this section. Needed for rows that do
    # not carry the field yet, where the value's own type cannot be consulted.
    list_fields = {
        field
        for entity in section.values()
        for field, value in entity.items()
        if isinstance(value, list)
    }

    for line in lines[1:]:
        parts = line.split(";")
        key = parts[0]
        values = parts[1:]

        if key not in section:
            # A new character discovered by `just import-dialogs` (its row was
            # auto-appended to characters.csv) is created here from the row, so
            # long as it carries the model's required fields. For any other
            # entity type - or a row missing required fields (likely a typo in
            # an existing key) - keep the safe warn-and-skip.
            row = dict(zip(fields, values))
            can_create = entity_name == "characters" and all(
                row.get(f, "").strip() for f in REQUIRED_CHARACTER_FIELDS
            )
            if not can_create:
                missing = [f for f in REQUIRED_CHARACTER_FIELDS if not row.get(f, "").strip()]
                print(f"  [WARN] '{key}' not in config.json, skipping (missing required: {', '.join(missing)})")
                continue
            section[key] = {}
            created += 1

        obj = section[key]
        sentiment_updates: dict[str, int] = {}
        for i, field in enumerate(fields):
            if i < len(values):
                raw = values[i]
                if raw == "":
                    continue  # pusta komórka = nie nadpisuj → model użyje wartości domyślnej
                if entity_name == "characters" and field in SENTIMENT_COLUMNS:
                    sentiment_updates[field] = int(raw)
                    continue
                if entity_name == "characters" and field == "friendly":
                    obj[field] = float(raw)
                    continue
                current = obj.get(field)
                obj[field] = parse_value(raw, current, is_list=field in list_fields)
        if sentiment_updates:
            # fresh dict from defaults: stale keys (e.g. pre-rename emote
            # names) are dropped, neutral/technical come from the defaults
            disposition = dict(DEFAULT_DISPOSITION_WEIGHTS)
            disposition.update(sentiment_updates)
            obj["disposition"] = disposition
        updated += 1

    data[entity_name] = section
    created_note = f" ({created} created)" if created else ""
    print(f"  {entity_name}: {updated} rows imported{created_note}")
    return data


def _export_csv(entity_name: str, data: dict) -> None:
    """Export *entity_name* section from *data* back to ``<name>.csv``."""
    import csv, io

    section = data.get(entity_name, {})
    if not section:
        return

    # Collect all fields in insertion order from the first entity
    fields = ["key"]
    for v in section.values():
        for k in v:
            if k not in fields:
                fields.append(k)

    # characters: disposition dict is exported as per-sentiment columns
    # (round-trip with import_csv's aggregation)
    if entity_name == "characters" and "disposition" in fields:
        fields.remove("disposition")
        fields.extend(c for c in SENTIMENT_COLUMNS if c not in fields)

    csv_path = HERE / f"{entity_name}.csv"
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(fields)
    for key in sorted(section.keys()):
        obj = section[key]
        row = [key]
        for f in fields[1:]:
            if entity_name == "characters" and f in SENTIMENT_COLUMNS:
                weight = (obj.get("disposition") or {}).get(f)
                row.append("" if weight is None else str(weight))
                continue
            v = obj.get(f)
            if v is None:
                row.append("")
            elif isinstance(v, bool):
                row.append("true" if v else "false")
            elif isinstance(v, list):
                # comma-separated, not JSON - see _parse_list
                row.append(",".join(str(item) for item in v))
            elif isinstance(v, dict):
                row.append(json.dumps(v, ensure_ascii=False))
            else:
                row.append(str(v))
        w.writerow(row)
    csv_path.write_text(buf.getvalue())
    print(f"  {entity_name}: {len(section)} rows exported")


def export_csvs() -> None:
    """Export all config sections to CSV files."""
    if not CONFIG_FILE.exists():
        print(f"[ERROR] {CONFIG_FILE} not found")
        sys.exit(1)
    data = json.loads(CONFIG_FILE.read_text())
    for entity_name in CONF_ENTITIES_TO_STORE:
        _export_csv(entity_name, data)
    print(f"\n[OK] CSV files saved to {HERE}")


def main() -> None:
    if not CONFIG_FILE.exists():
        print(f"[ERROR] {CONFIG_FILE} not found")
        sys.exit(1)

    if "--export" in sys.argv:
        export_csvs()
        return

    data = json.loads(CONFIG_FILE.read_text())

    for entity_name in CONF_ENTITIES_TO_STORE:
        data = import_csv(entity_name, data)

    for entity_name in CONF_ENTITIES_TO_STORE:
        if entity_name in data:
            data[entity_name] = _strip_nulls(data[entity_name])

    CONFIG_FILE.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n")
    print(f"\n[OK] Config saved to {CONFIG_FILE}")


if __name__ == "__main__":
    main()
