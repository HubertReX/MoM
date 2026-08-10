"""Zegar świata: upływ czasu w grze, przełom doby i losowość per dzień.

Moduł systemu wg B01 (D1): bezstanowe funkcje operujące na przekazanej scenie -
zegar (``day``/``hour``/``minute``/``minute_f``) zostaje atrybutem ``Scene``
(kontrakt K1 save/load), a ``Scene`` ma tylko cienkie delegaty.

Kontrakt K6: ``settings.INITIAL_HOUR`` i ``settings.INITIAL_DAY`` czytamy
DYNAMICZNIE (``import settings``), bo scenariusze testowe i tryb deterministyczny
podmieniają je po imporcie modułu.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

import settings
from npc_schedule import MINUTES_PER_DAY
from world_rng import day_rng as _world_day_rng

if TYPE_CHECKING:
    from scene.scene import Scene


def reset(scene: "Scene") -> None:
    """Ustaw zegar na wartości startowe (nowa gra / przeładowanie mapy)."""
    scene.day = settings.INITIAL_DAY
    scene.hour = settings.INITIAL_HOUR
    scene.minute = 0
    scene.minute_f = 0.0


def day_phase(hour: float) -> str:
    """Nazwa fazy doby dla godziny zmiennoprzecinkowej (H01/D1).

    Granice czyta z ``settings.DAY_PHASES`` - jedynego źródła prawdy, z którego
    korzysta też filtr pory dnia. Faza trwa od swojej godziny do początku
    następnej, a ostatnia **zawija się przez północ**: naiwne ``start <= h < end``
    zwróciłoby dla 02:00 pustkę i nocny bark nigdy by nie zapalił.
    """
    h = hour % 24.0
    # domyślnie ostatnia faza: jeśli o tej godzinie nic się dziś jeszcze nie
    # zaczęło, w mocy jest ta, która zaczęła się wczoraj
    current = settings.DAY_PHASES[-1][0]
    for name, start in settings.DAY_PHASES:
        if h >= start:
            current = name
        else:
            break
    return current


def phase_bounds(phase: str) -> tuple[float, float]:
    """``(początek, koniec)`` fazy w godzinach; koniec ostatniej zawija przez północ.

    Filtr pory dnia interpoluje kolor wewnątrz fazy, więc potrzebuje obu granic -
    i musi je brać stąd, żeby nie zrobić drugiego kompletu liczb 6/9/17/20.
    """
    phases = settings.DAY_PHASES
    for index, (name, start) in enumerate(phases):
        if name == phase:
            return start, phases[(index + 1) % len(phases)][1]
    raise KeyError(f"unknown day phase {phase!r} (have: {', '.join(n for n, _ in phases)})")


def phase_names() -> tuple[str, ...]:
    """Nazwy faz w kolejności doby - dla walidatora warunków i komunikatów błędów."""
    return tuple(name for name, _ in settings.DAY_PHASES)


def abs_minutes(scene: "Scene") -> int:
    """Absolute game-minute (day + clock), monotonic across midnight and day turns.

    Cross-map transit arrival is stored in this unit so a boundary at 23:50 and
    an arrival at 00:10 next day compare correctly, and a multi-day `apply_days`
    jump simply lands past any in-flight transit's arrival, which then completes.
    """
    return scene.day * MINUTES_PER_DAY + scene.hour * 60 + scene.minute


def day_rng(scene: "Scene", name: str = "", day_offset: int = 0) -> random.Random:
    """Generator for `name`'s rolls on the current day (or a later one).

    `day_offset=1` asks for tomorrow, which is what makes a day-ahead preview
    - "the merchant will want amber tomorrow" - cost nothing to store: it is
    recomputed, not remembered. See world_rng.py.
    """
    return _world_day_rng(scene.world_seed, scene.day + day_offset, name)


def apply_days(scene: "Scene", days: int = 1) -> None:
    """Run the day-turn upkeep for `days` elapsed days in one go.

    Every step here has to be a function of the current state and the number
    of days, never a loop over days - coming back from a three-day trip is a
    single call, and `apply_days(3)` must land on the same state as three
    `apply_days(1)`.
    """
    if days <= 0:
        return

    for npc in scene.loaded_NPCs.values():
        if npc.model.is_merchant:
            npc.regenerate_money(days)
            npc.restock_items()


def next_day(scene: "Scene") -> None:
    """Przeskocz o pełną dobę (klawisz debugowy) - licznik dni + upkeep."""
    scene.day += 1
    apply_days(scene, 1)


def tick(scene: "Scene", dt: float) -> None:
    """Przesuń zegar o `dt` sekund realnego czasu; na przełomie doby odpal upkeep."""
    # absolute time calculation
    # scene.hour   = int((scene.game.time_elapsed + settings.INITIAL_HOUR) % 24)
    # scene.minute = int((scene.game.time_elapsed + settings.INITIAL_HOUR) % 1 * 60)

    # relative time calculation
    scene.minute_f += dt * 60 * settings.GAME_TIME_SPEED
    scene.minute = int(scene.minute_f)
    if scene.minute >= 60:
        scene.hour   += 1
        scene.minute  = 0
        scene.minute_f  -= 60.0
        if scene.hour >= 24:
            scene.day += 1
            scene.hour = 0
            apply_days(scene, 1)
