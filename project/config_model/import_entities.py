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
from settings import CONF_ENTITIES_TO_STORE  # noqa: E402


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


def parse_value(raw: str, current: object) -> object:
    """Parse a CSV cell value to match the type of the current value."""
    if raw == "":
        return current
    if isinstance(current, bool):
        return raw.lower() in ("true", "1", "yes")
    if isinstance(current, int):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    if isinstance(current, list):
        parsed = _cell_to_json(raw)
        if isinstance(parsed, list):
            return parsed
        return current  # failed to parse as list, leave unchanged
    if isinstance(current, dict):
        parsed = _cell_to_json(raw)
        if isinstance(parsed, dict):
            return parsed
        return current
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

    for line in lines[1:]:
        parts = line.split(";")
        key = parts[0]
        values = parts[1:]

        if key not in section:
            print(f"  [WARN] '{key}' not in config.json, skipping")
            continue

        obj = section[key]
        for i, field in enumerate(fields):
            if i < len(values):
                raw = values[i]
                if raw == "":
                    continue  # pusta komórka = nie nadpisuj → model użyje wartości domyślnej
                current = obj.get(field)
                obj[field] = parse_value(raw, current)
        updated += 1

    data[entity_name] = section
    print(f"  {entity_name}: {updated} rows imported")
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

    csv_path = HERE / f"{entity_name}.csv"
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(fields)
    for key in sorted(section.keys()):
        obj = section[key]
        row = [key]
        for f in fields[1:]:
            v = obj.get(f)
            if v is None:
                row.append("")
            elif isinstance(v, bool):
                row.append("true" if v else "false")
            elif isinstance(v, (list, dict)):
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
