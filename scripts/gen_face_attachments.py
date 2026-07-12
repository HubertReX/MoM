#!/usr/bin/env python3
"""Regeneracja twarzy postaci w vaultcie doc/_attachements/.

Dla każdej postaci z ``project/config_model/characters.csv`` z ``has_dialog=true``
kopiuje ``project/assets/NinjaAdventure/characters/<sprite>/Faceset.png`` do
``doc/_attachements/<KEY>.png``. Pliki w vaultcie to maszynowo regenerowalne
duplikaty - źródłem prawdy pozostają assety (kolumna ``sprite`` w CSV pochodzi
z frontmattera pliku postaci przez ``just import-dialogs``).

Obrazki wyświetla inline dataview w plikach postaci:
``= "![[" + this.aliases[0] + ".png|300]]"``.

Użycie:
    just gen-faces
    # lub bezpośrednio:
    .venv/bin/python scripts/gen_face_attachments.py
"""
from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHARACTERS_CSV = ROOT / "project" / "config_model" / "characters.csv"
SPRITES_DIR = ROOT / "project" / "assets" / "NinjaAdventure" / "characters"
OUT_DIR = ROOT / "doc" / "_attachements"


def main() -> int:
    if not CHARACTERS_CSV.exists():
        print(f"characters.csv not found: {CHARACTERS_CSV}", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    missing: list[str] = []
    with CHARACTERS_CSV.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            if row.get("has_dialog", "").lower() != "true":
                continue
            key = row.get("key", "").strip()
            sprite = row.get("sprite", "").strip()
            if not key or not sprite:
                missing.append(f"{key or '?'} (brak sprite w CSV)")
                continue
            faceset = SPRITES_DIR / sprite / "Faceset.png"
            if not faceset.exists():
                missing.append(f"{key} ({faceset} nie istnieje)")
                continue
            target = OUT_DIR / f"{key}.png"
            shutil.copyfile(faceset, target)
            print(f"  {key}: {sprite}/Faceset.png -> {target.relative_to(ROOT)}")
            copied += 1

    print(f"Copied {copied} faceset(s) to {OUT_DIR.relative_to(ROOT)}")
    for m in missing:
        print(f"  [SKIP] {m}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
