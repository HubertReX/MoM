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
                current = obj.get(field)
                obj[field] = parse_value(values[i], current)
        updated += 1

    data[entity_name] = section
    print(f"  {entity_name}: {updated} rows imported")
    return data


def main() -> None:
    if not CONFIG_FILE.exists():
        print(f"[ERROR] {CONFIG_FILE} not found")
        sys.exit(1)

    data = json.loads(CONFIG_FILE.read_text())

    for entity_name in CONF_ENTITIES_TO_STORE:
        data = import_csv(entity_name, data)

    CONFIG_FILE.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n")
    print(f"\n[OK] Config saved to {CONFIG_FILE}")


if __name__ == "__main__":
    main()
