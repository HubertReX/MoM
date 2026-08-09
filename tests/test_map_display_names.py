#!/usr/bin/env python3
"""Unit tests for the map display-name layer (C02 etap 3: D12, W2, O6).

Run from the project root:
    .venv/bin/python tests/test_map_display_names.py

Trzy rzeczy są tu przypięte, bo każda psuje się cicho:

1. **Każda mapa ma nazwę w PL i EN.** Bez tego gracz czyta na HUD-zie surowy klucz
   (`LOST_CORK_TAVERN`) - znalezisko O5 audytu. Reguła 12 walidatora ma się zapalić
   w dniu, w którym ktoś doda mapę, a nie na zrzucie ekranu.
2. **Napis czytany jest na żywo dla bieżącego języka.** Zmiana języka w ustawieniach
   musi zmienić napis bez restartu, więc nazwa nie może być domknięta w `from settings
   import LANG` ani w cache'u kluczowanym mapą.
3. **Klucz `Player` nie jest napisem.** Kod odróżniał bohatera od NPC-ów przez
   `model.name_EN == "Player"` - czyli przez warstwę, którą punkt 1 każe tłumaczyć
   (O6). Test pilnuje, że żaden plik w `project/` do tego nie wraca.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "project"))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import settings                                                 # noqa: E402
from validate_world import (                                    # noqa: E402
    ERROR,
    LOCALE_LANGS,
    WARN,
    _game_map_keys,
    check_map_display_names,
    load_world,
)


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


WORLD = load_world()


###############################################################################################################
def test_every_game_map_has_a_display_name_in_both_languages() -> None:
    """Reguła 12 świeci na zielono na prawdziwym świecie."""
    violations = check_map_display_names(WORLD)
    errors = [v for v in violations if v.severity == ERROR]
    assert_eq([v.message for v in errors], [], "no missing map names")


def test_the_registry_covers_maze_levels_without_a_tmx_file() -> None:
    """Poziom labiryntu nie ma pliku `.tmx`, a i tak jest mapą (D13)."""
    keys = _game_map_keys(WORLD)
    levels = len(WORLD.config.get("maze_configs") or {})
    assert_true(levels > 0, "maze_configs is not empty")
    for level in range(1, levels + 1):
        assert_true(f"Maze_{level:02d}" in keys, f"Maze_{level:02d} is a map key")
    assert_true("LOST_CORK_TAVERN" in keys, "static maps are in the registry too")


def test_a_map_without_a_display_name_is_an_error() -> None:
    """Reguła musi umieć zapalić się na czerwono - inaczej jest dekoracją.

    Piąty poziom labiryntu to najtańsza „nowa mapa", jaką da się udać bez dotykania
    plików repo: rejestr wylicza go z liczby wierszy `maze_configs`, więc pojawia się
    tak samo, jak pojawi się prawdziwa mapa dodana przez autora.
    """
    levels = len(WORLD.config.get("maze_configs") or {})
    extra = f"Maze_{levels + 1:02d}"
    violations = check_map_display_names(_WorldWithMazeLevels(WORLD, levels + 1))
    errors = [v for v in violations if v.severity == ERROR]
    assert_eq(len(errors), len(LOCALE_LANGS), "one error per language")
    for v in errors:
        assert_true(extra in v.message, f"names the offending map: {v.message}")


def test_a_locale_entry_for_no_map_is_a_warning() -> None:
    """Wpis po przemianowanej mapie zostaje w locale i nikt go nie zauważa."""
    world = _WorldWithMazeLevels(WORLD, 0)
    warns = [v for v in check_map_display_names(world) if v.severity == WARN]
    assert_true(len(warns) >= 2, f"stale Maze_* entries are reported: {len(warns)}")
    assert_true(all("Maze_" in v.message for v in warns), "and they name the stale keys")


###############################################################################################################
def test_display_names_follow_the_current_language() -> None:
    """`_()` czyta `settings.LANG` na żywo - zmiana języka działa bez restartu."""
    original = settings.LANG
    try:
        settings.LANG = "PL"
        settings.reload_ui_strings()
        pl = settings._("map.LOST_CORK_TAVERN")
        settings.LANG = "EN"
        settings.reload_ui_strings()
        en = settings._("map.LOST_CORK_TAVERN")
    finally:
        settings.LANG = original
        settings.reload_ui_strings()

    assert_eq(pl, "Tawerna Brakująca klepka", "Polish name")
    assert_eq(en, "the Lost Cork Tavern", "English name")


def test_a_missing_entry_falls_back_to_the_key_not_to_a_dotted_key() -> None:
    """Fallback ma być czytelny: `_()` zwraca `map.X`, HUD skraca to do `X`."""
    raw = settings._("map.NIE_MA_TAKIEJ_MAPY")
    assert_eq(raw, "map.NIE_MA_TAKIEJ_MAPY", "settings falls back to the whole key")


###############################################################################################################
_PLAYER_BY_NAME = re.compile(r"name_(EN|PL)\s*[!=]=\s*[\"']Player[\"']")


def test_no_code_recognises_the_player_by_its_display_name() -> None:
    """O6: napis dla gracza jest tłumaczony, więc nie może być testem tożsamości."""
    offenders: list[str] = []
    for path in sorted((ROOT / "project").rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _PLAYER_BY_NAME.search(line) and not line.lstrip().startswith("#"):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}")
    assert_eq(offenders, [], "compare npc.config_key == PLAYER_CONFIG_KEY instead")


def test_the_player_key_is_a_real_character_key() -> None:
    """Stała musi wskazywać wiersz w `characters.csv`, nie nazwę sprite'a."""
    characters = WORLD.config.get("characters") or {}
    assert_true(settings.PLAYER_CONFIG_KEY in characters,
                f"'{settings.PLAYER_CONFIG_KEY}' is a character key")


###############################################################################################################
class _WorldWithMazeLevels:
    """`World` z podmienioną liczbą poziomów labiryntu (rejestr map jest wyliczany)."""

    def __init__(self, world: object, levels: int) -> None:
        self._world = world
        self.config = dict(world.config)          # type: ignore[attr-defined]
        self.config["maze_configs"] = {str(n): {} for n in range(1, levels + 1)}

    def __getattr__(self, item: str) -> object:
        return getattr(self._world, item)


def main() -> None:
    tests = [
        test_every_game_map_has_a_display_name_in_both_languages,
        test_the_registry_covers_maze_levels_without_a_tmx_file,
        test_a_map_without_a_display_name_is_an_error,
        test_a_locale_entry_for_no_map_is_a_warning,
        test_display_names_follow_the_current_language,
        test_a_missing_entry_falls_back_to_the_key_not_to_a_dotted_key,
        test_no_code_recognises_the_player_by_its_display_name,
        test_the_player_key_is_a_real_character_key,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} map display-name tests passed.")


if __name__ == "__main__":
    main()
