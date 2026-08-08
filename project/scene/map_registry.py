"""Które klucze map istnieją i który z nich jest labiryntem (C02, D13).

Rejestr jest **wyliczany**, nie trzymany w osobnym pliku. Zbiór map to suma
dwóch źródeł, które i tak już istnieją:

- mapy statyczne - stemy plików ``assets/NinjaAdventure/maps/*.tmx``
  (podkatalogi, np. ``_wip/``, świadomie pominięte - patrz W3),
- poziomy labiryntu - ``MAZE_01``…``MAZE_0N`` dla N wierszy ``maze_configs.csv``.
  Głębokość labiryntu jest ograniczona liczbą tych wierszy: ``load_tileset_map``
  liczy ``max_level = len(maze_configs)``, a ``maze_utils`` stawia schody w dół
  tylko ``if current_map_level < max_level``.

Poziom labiryntu nie ma pliku ``.tmx`` (mapa powstaje z szablonu w locie), więc
sama obecność pliku nigdy nie wystarczyła za listę legalnych map.

``is_maze`` jest tu funkcją klucza mapy, a nie własnością obiektu drzwi w Tiled -
o to chodziło w W8. Drzwi wiedzą tylko, dokąd prowadzą; czy tam jest labirynt,
wie mapa docelowa.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import settings

if TYPE_CHECKING:
    from collections.abc import Iterable

#: Prefiks klucza mapy poziomu labiryntu. Etap 5 zmienia go na ``MAZE`` razem
#: z resztą nazw map (D5); do tego czasu w `.tmx` stoi ``Maze_01``.
MAZE_MAP_PREFIX = "Maze"

#: ``<PREFIKS>_<NN>`` - dokładnie ten kształt buduje generator
#: (``maze_utils.build_tileset_map_from_maze``) dla sąsiednich poziomów.
_MAZE_KEY_RE = re.compile(rf"^{re.escape(MAZE_MAP_PREFIX)}_(\d{{2,}})$")


def maze_map_keys(conf: Any) -> set[str]:
    """Klucze wszystkich poziomów labiryntu, np. ``{"Maze_01", …, "Maze_04"}``."""
    return {f"{MAZE_MAP_PREFIX}_{level:02d}" for level in conf.maze_configs}


def is_maze_map(conf: Any, map_key: str) -> bool:
    """Czy *map_key* jest poziomem labiryntu.

    Sprawdzamy przynależność do wyliczonego zbioru, a nie sam prefiks: dzięki
    temu ``Maze_09`` przy czterech poziomach w ``maze_configs.csv`` jest tym, czym
    jest - mapą, której nie ma - zamiast udawać labirynt i wywalić generator.
    """
    return map_key in maze_map_keys(conf)


def maze_level(map_key: str) -> int | None:
    """Numer poziomu z klucza mapy (``"Maze_03"`` -> ``3``), albo ``None``."""
    match = _MAZE_KEY_RE.match(map_key)
    return int(match.group(1)) if match else None


def static_map_keys() -> set[str]:
    """Stemy plików ``.tmx`` w katalogu map (bez podkatalogów, patrz W3)."""
    return {path.stem for path in settings.MAPS_DIR.glob("*.tmx")}


def all_map_keys(conf: Any) -> set[str]:
    """Komplet legalnych kluczy map - statyczne plus poziomy labiryntu."""
    return static_map_keys() | maze_map_keys(conf)


def unknown_map_keys(conf: Any, keys: "Iterable[str]") -> set[str]:
    """Te z *keys*, które nie są żadną znaną mapą - materiał na błąd walidatora."""
    known = all_map_keys(conf)
    return {key for key in keys if key not in known}
