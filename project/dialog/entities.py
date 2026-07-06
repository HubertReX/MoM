"""Dialog graph entities — pure dataclasses (no pygame, no Pydantic).

Ported from RPG ``dialog_node.py`` (canonical: 7 result categories,
``slots=True``). Works on both desktop and pygbag/WASM. Decision **D2** of the
Dialog System epic: entities are ``slots=True`` dataclasses, the graph is built
from plain dicts validated at import time.

Nodes hold only i18n *keys* (``text`` is a ``messages`` key, resolved via
``get_msg()`` at render time — decision D7), never rendered strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NodeVisitResultCategory(Enum):
    """The 7 kinds of side effect a dialog node can carry (decision D8)."""

    MONEY_RECEIVED = "money_received"
    MONEY_RETURNED = "money_returned"
    ITEMS_RECEIVED = "items_received"
    ITEMS_RETURNED = "items_returned"
    HEALTH_RESTORED = "health_restored"
    HEALTH_LOST = "health_lost"
    SENTIMENT_SHIFT = "sentiment_shift"


@dataclass(slots=True)
class NodeVisitResult:
    """Side effect applied when a node is visited (gold / items / HP / sentiment)."""

    key: str
    category: NodeVisitResultCategory
    money: int = field(default=0, repr=False)
    health: int = field(default=0, repr=False)
    value: int = field(default=0, repr=False)
    items: list[str] = field(default_factory=list, repr=False)


@dataclass(slots=True)
class DialogNode:
    """A single node in a character's dialog graph."""

    key: str
    text: str = field(repr=False)
    options: list["DialogOption"] = field(default_factory=list, repr=False)
    available_options: list["DialogOption"] = field(default_factory=list, repr=False)
    is_final: bool = field(default=False, repr=False)
    visited: bool = field(default=False, repr=False)
    result: NodeVisitResult | None = field(default=None, repr=False)


@dataclass(slots=True)
class DialogOption:
    """A selectable option on a node, pointing at the next node."""

    key: str
    next_node: "DialogNode"
    text: str = field(repr=False)
    order: int = field(default=0, repr=False)
    condition: str = field(default="True", repr=False)
    sentiment: str = field(default="😐", repr=False)
    selected: bool = field(default=False, repr=False)
