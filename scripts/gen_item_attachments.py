#!/usr/bin/env python3
"""Regeneracja ikon przedmiotów w vaultcie ``doc/_attachements/``.

Siostra ``gen_face_attachments.py``: dla każdego przedmiotu z
``project/config_model/items.csv`` wycina kafel 16x16 z arkusza, którego używa
sama gra, powiększa go całkowitą krotnością (nearest neighbour - złota zasada
pixel-perfect) i zapisuje jako ``doc/_attachements/item_<klucz>.png``.

Współrzędne kafla **nie są tu przepisane**: biorą się z ``ITEMS_SHEET_DEFINITION``
i ``GEMS_SHEET_DEFINITION`` w ``settings.py``, czyli z tego samego miejsca, z
którego bierze je scena. Ikona w notatce nie może więc pokazywać czegoś innego
niż ekwipunek w grze - a tak by było, gdyby ten skrypt miał własną tabelkę.

Obrazek wyświetla inline dataview w notatce przedmiotu::

    `= "![[item_" + this.key + ".png|64]]"`

Użycie::

    just gen-item-icons
    .venv/bin/python scripts/gen_item_attachments.py --scale 8
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "project"))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from settings import (  # noqa: E402
    GEMS_SHEET_DEFINITION,
    GEMS_SHEET_FILE,
    ITEMS_SHEET_DEFINITION,
    ITEMS_SHEET_FILE,
    TILE_SIZE,
)

ITEMS_CSV = ROOT / "project" / "config_model" / "items.csv"
OUT_DIR = ROOT / "doc" / "_attachements"
PREFIX = "item_"
DEFAULT_SCALE = 4


def _sheets() -> list[tuple[Path, dict[str, list[tuple[int, int]]]]]:
    """Arkusze w kolejności szukania: zwykłe przedmioty, potem klejnoty."""
    return [(ITEMS_SHEET_FILE, ITEMS_SHEET_DEFINITION), (GEMS_SHEET_FILE, GEMS_SHEET_DEFINITION)]


def _icon(key: str, loaded: dict[Path, pygame.Surface]) -> pygame.Surface | None:
    """Pierwsza klatka przedmiotu z arkusza, który go zna."""
    for path, definition in _sheets():
        frames = definition.get(key)
        if not frames:
            continue
        if path not in loaded:
            loaded[path] = pygame.image.load(str(path)).convert_alpha()
        sheet = loaded[path]
        x, y = frames[0]
        rect = pygame.Rect(x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        if not sheet.get_rect().contains(rect):
            return None
        return sheet.subsurface(rect).copy()
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scale", type=int, default=DEFAULT_SCALE,
        help=f"integer upscale, nearest neighbour (default {DEFAULT_SCALE} -> "
             f"{TILE_SIZE * DEFAULT_SCALE}px)",
    )
    args = parser.parse_args(argv)

    if not ITEMS_CSV.exists():
        print(f"items.csv not found: {ITEMS_CSV}", file=sys.stderr)
        return 1

    pygame.init()
    pygame.display.set_mode((1, 1))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    loaded: dict[Path, pygame.Surface] = {}
    written = 0
    missing: list[str] = []
    size = TILE_SIZE * args.scale

    with ITEMS_CSV.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            key = row.get("key", "").strip()
            if not key:
                continue
            icon = _icon(key, loaded)
            if icon is None:
                missing.append(key)
                continue
            target = OUT_DIR / f"{PREFIX}{key}.png"
            pygame.image.save(pygame.transform.scale(icon, (size, size)), str(target))
            written += 1

    print(f"Wrote {written} item icon(s) at {size}x{size}  ->  {OUT_DIR.relative_to(ROOT)}")
    for key in missing:
        print(
            f"  [SKIP] {key}: no entry in ITEMS_SHEET_DEFINITION / GEMS_SHEET_DEFINITION",
            file=sys.stderr,
        )
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
