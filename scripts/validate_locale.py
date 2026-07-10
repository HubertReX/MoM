"""Validate locale TOML files for key symmetry and placeholder consistency.

Usage:
    python scripts/validate_locale.py

Reads project/assets/locale/{PL,EN}.toml, flattens nested tables, and checks:
  1. Every key in PL exists in EN and vice versa.
  2. Placeholder names ({name}, {n}, ...) match between PL and EN for each key.

Exit code 0 = OK, 1 = errors found.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

LOCALE_DIR = Path(__file__).resolve().parent.parent / "project" / "assets" / "locale"
LANGUAGES = ["PL", "EN"]

PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")


def flatten_toml(nested: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested TOML dict into dotted-key pairs."""
    flat: dict[str, str] = {}
    for key, value in nested.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten_toml(value, full_key))
        else:
            flat[full_key] = str(value)
    return flat


def extract_placeholders(text: str) -> set[str]:
    """Return set of placeholder tokens from a string value."""
    return set(PLACEHOLDER_RE.findall(text))


def load_locale(lang: str) -> dict[str, str]:
    """Load and flatten a locale TOML file."""
    path = LOCALE_DIR / f"{lang}.toml"
    with open(path, "rb") as f:
        return flatten_toml(tomllib.load(f))


def main() -> int:
    errors: list[str] = []

    locales: dict[str, dict[str, str]] = {}
    for lang in LANGUAGES:
        path = LOCALE_DIR / f"{lang}.toml"
        if not path.exists():
            errors.append(f"File not found: {path}")
            continue
        locales[lang] = load_locale(lang)

    if len(locales) < 2:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    pl_keys = set(locales["PL"])
    en_keys = set(locales["EN"])

    # Key symmetry
    missing_in_en = pl_keys - en_keys
    missing_in_pl = en_keys - pl_keys

    for key in sorted(missing_in_en):
        errors.append(f"Key in PL but missing in EN: {key}")
    for key in sorted(missing_in_pl):
        errors.append(f"Key in EN but missing in PL: {key}")

    # Placeholder consistency
    common_keys = pl_keys & en_keys
    for key in sorted(common_keys):
        pl_ph = extract_placeholders(locales["PL"][key])
        en_ph = extract_placeholders(locales["EN"][key])
        if pl_ph != en_ph:
            errors.append(
                f"Placeholder mismatch in '{key}': "
                f"PL={sorted(pl_ph)} EN={sorted(en_ph)}"
            )

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    with_ph = sum(1 for k in sorted(common_keys) if extract_placeholders(locales["PL"][k]))
    print(f"OK: {len(common_keys)} keys, {with_ph} with placeholders")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
