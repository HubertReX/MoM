"""Pakiet scene - rdzeń rozgrywki na mapie (w trakcie refactoru B01, etap 1).

Kontrakt K4: ``from scene import Scene`` działa jak przed podziałem na pakiet.
Kontrakt K9: żywe globale modułu (np. ``USE_ALPHA_FILTER``) są dostępne przez
PEP 562 ``__getattr__`` niżej - zwykły re-eksport byłby snapshotem z chwili
importu i toggle przestałby działać. Flaga nakładki debug (backtick/Z) mieszka
od kroku 9 w ``scene/debug_overlay.py``; ``scene.SHOW_DEBUG_INFO`` nadal działa,
bo ``__getattr__`` dogląda też tego modułu.
Szczegóły: doc/refactor-rdzenia-B01.md.
"""
from typing import Any

from scene.scene import Scene

__all__ = ["Scene"]


def __getattr__(name: str) -> Any:
    # PEP 562: deleguj odczyt pozostałych atrybutów pakietu do modułu
    # implementacji, ŻYWO przy każdym odczycie (globale mutowane w runtime).
    from scene import scene as _impl
    try:
        return getattr(_impl, name)
    except AttributeError:
        # flagi, które wyprowadziły się do modułów systemów (np. SHOW_DEBUG_INFO
        # do debug_overlay) - stare `scene.<flaga>` ma nadal działać
        from scene import debug_overlay as _debug
        return getattr(_debug, name)
