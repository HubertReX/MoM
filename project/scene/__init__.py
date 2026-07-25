"""Pakiet scene - rdzeń rozgrywki na mapie (w trakcie refactoru B01, etap 1).

Kontrakt K4: ``from scene import Scene`` działa jak przed podziałem na pakiet.
Kontrakt K9: żywe globale modułu (np. ``scene.SHOW_DEBUG_INFO``, przełączane
klawiszem backtick/Z w trakcie gry i czytane przez ``ui/panels/help.py``
i ``characters.py``) są dostępne przez PEP 562 ``__getattr__`` niżej - zwykły
re-eksport byłby snapshotem z chwili importu i toggle przestałby działać.
Szczegóły: doc/refactor-rdzenia-B01.md.
"""
from typing import Any

from scene.scene import Scene

__all__ = ["Scene"]


def __getattr__(name: str) -> Any:
    # PEP 562: deleguj odczyt pozostałych atrybutów pakietu do modułu
    # implementacji, ŻYWO przy każdym odczycie (globale mutowane w runtime).
    from scene import scene as _impl
    return getattr(_impl, name)
