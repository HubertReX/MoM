"""Dialog System — graph entities and builder (epic DS, task T-029).

Pure logic (no pygame): dialog graph entities plus :func:`init_dialog` that
turns config dicts into a resolved ``{key: DialogNode}`` graph.
"""

from dialog.entities import (
    DialogNode,
    DialogOption,
    NodeVisitResult,
    NodeVisitResultCategory,
)
from dialog.graph import get_start_node, init_dialog

__all__ = [
    "DialogNode",
    "DialogOption",
    "NodeVisitResult",
    "NodeVisitResultCategory",
    "init_dialog",
    "get_start_node",
]
