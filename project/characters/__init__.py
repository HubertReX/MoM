"""Pakiet characters - postacie (w trakcie refactoru B01, etap 1).

Kontrakt K4: ``from characters import NPC, Player`` działa jak przed podziałem
na pakiet. Kontrakt K9: pozostałe atrybuty modułu (stałe zaimportowane
z ``settings``, np. ``INPUTS``) są dostępne przez PEP 562 ``__getattr__``
niżej - odczyt jest ŻYWY, więc podmiana atrybutu w teście albo toggle
w runtime nadal działa. Szczegóły: doc/refactor-rdzenia-B01.md.
"""
import importlib
from typing import Any

from characters.npc import NPC
from characters.player import Player

__all__ = ["NPC", "Player"]

# kolejność ma znaczenie: pierwszy moduł, który ma atrybut, wygrywa
_IMPL_MODULES = ("npc", "player", "movement", "combat", "animation", "inventory")


def __getattr__(name: str) -> Any:
    # PEP 562: deleguj odczyt pozostałych atrybutów pakietu do modułów
    # implementacji, ŻYWO przy każdym odczycie (globale mutowane w runtime).
    for module_name in _IMPL_MODULES:
        module = importlib.import_module(f"characters.{module_name}")
        try:
            return getattr(module, name)
        except AttributeError:
            continue
    raise AttributeError(f"module 'characters' has no attribute '{name}'")
