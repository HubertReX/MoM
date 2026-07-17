"""Dialog System — graph entities, builder and condition engine (epic DS).

Pure logic (no pygame): dialog graph entities plus :func:`init_dialog` that
turns config dicts into a resolved ``{key: DialogNode}`` graph (T-029), and the
mini-DSL condition engine (:func:`check_condition` / :func:`validate_condition`,
T-032) that decides whether an option is available.
"""

from dialog.conditions import (
    ConditionContext,
    ConditionError,
    ConditionScope,
    DialogConditionContext,
    check_condition,
    eval_number,
    validate_condition,
    validate_number,
    )
from dialog.entities import (
    DialogNode,
    DialogOption,
    NodeVisitResult,
    NodeVisitResultCategory
    )
from dialog.graph import get_start_node, init_dialog
from dialog.result_sink import ResultSink, apply_result, visit_node

__all__ = [
    "DialogNode",
    "DialogOption",
    "NodeVisitResult",
    "NodeVisitResultCategory",
    "init_dialog",
    "get_start_node",
    "ConditionContext",
    "ConditionError",
    "ConditionScope",
    "DialogConditionContext",
    "check_condition",
    "eval_number",
    "validate_condition",
    "validate_number",
    "ResultSink",
    "apply_result",
    "visit_node",
]
