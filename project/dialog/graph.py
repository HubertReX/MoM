"""Build a character dialog graph from config dicts.

Port of RPG ``main.py:init_dialog`` (``main.py:1108-1224``) as a *pure*
function — no pygame, no game object, so it can be unit-tested in isolation.

The input ``dialog`` dict has five sections (see RPG ``config.json``
``character_dialogs``):

- ``NODE_RESULTS``  – ``{key: {category, money?, health?, value?, items?}}``
- ``DIALOG_NODES``  – ``{key: {text, is_final?, result?}}``
- ``DIALOG_OPTIONS``– ``{key: {next_node, text, order?, condition?, sentiment?}}``
- ``NODES_OPTIONS`` – ``{node_key: [option_key, ...]}``
- ``START_NODE``    – key of the entry node

``init_dialog`` resolves every ``next_node`` / ``result`` / option reference and
returns ``{node_key: DialogNode}``. The caller picks the entry node with
``dialog["START_NODE"]`` (helper ``get_start_node`` below).

Dangling references raise ``ValueError`` with the offending key, so a broken
graph fails loudly at load time rather than mid-conversation.
"""

from __future__ import annotations

from typing import Any

from dialog.conditions import ConditionError, validate_condition
from dialog.entities import (
    DialogNode,
    DialogOption,
    NodeVisitResult,
    NodeVisitResultCategory,
)
from settings import normalise_sentiment


def init_dialog(dialog: dict[str, Any], *, debug: bool = False) -> dict[str, DialogNode]:
    """Build the ``{key: DialogNode}`` graph for one character.

    Args:
        dialog: one character's dialog config (the five sections above).
        debug: when ``True``, append RPG-style DEBUG options (jump to
            ``START_NODE`` and to every ``is_final`` node) for fast tree walking
            — gated by ``IS_DEBUG_MODE`` at the call site (decision D9).
    """
    results = _build_results(dialog.get("NODE_RESULTS", {}))
    nodes = _build_nodes(dialog.get("DIALOG_NODES", {}), results)
    options = _build_options(dialog.get("DIALOG_OPTIONS", {}), nodes)

    debug_options: list[DialogOption] = []
    if debug:
        debug_options = _build_debug_options(dialog, nodes)

    _attach_options(dialog.get("NODES_OPTIONS", {}), nodes, options, debug_options)

    if "START_NODE" not in dialog:
        raise ValueError("dialog config is missing 'START_NODE'")
    if dialog["START_NODE"] not in nodes:
        raise ValueError(
            f"START_NODE {dialog['START_NODE']!r} is not a known DIALOG_NODES key"
        )

    return nodes


def get_start_node(dialog: dict[str, Any], nodes: dict[str, DialogNode]) -> DialogNode:
    """Return the entry ``DialogNode`` for a graph built by :func:`init_dialog`."""
    return nodes[dialog["START_NODE"]]


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _build_results(section: dict[str, Any]) -> dict[str, NodeVisitResult]:
    results: dict[str, NodeVisitResult] = {}
    for key, data in section.items():
        result = NodeVisitResult(key, **data)
        # config stores the category as a string; resolve to the enum member
        result.category = NodeVisitResultCategory(result.category)
        results[key] = result
    return results


def _build_nodes(
    section: dict[str, Any], results: dict[str, NodeVisitResult]
) -> dict[str, DialogNode]:
    nodes: dict[str, DialogNode] = {}
    for key, data in section.items():
        result_key = data.get("result", "")
        if result_key and result_key not in results:
            raise ValueError(
                f"node {key!r} references unknown NODE_RESULTS key {result_key!r}"
            )
        nodes[key] = DialogNode(
            key,
            data["text"],
            is_final=data.get("is_final", False),
            result=results.get(result_key),
            resume_node=data.get("resume_node"),
        )
    return nodes


def _build_options(
    section: dict[str, Any], nodes: dict[str, DialogNode]
) -> dict[str, DialogOption]:
    options: dict[str, DialogOption] = {}
    for key, data in section.items():
        next_key = data["next_node"]
        if next_key not in nodes:
            raise ValueError(
                f"option {key!r} points at unknown next_node {next_key!r}"
            )
        condition = data.get("condition", "True")
        # validate the mini-DSL condition now (decision D1/D6): an unknown
        # predicate or name fails loudly here, not silently mid-conversation.
        try:
            validate_condition(condition)
        except ConditionError as error:
            raise ValueError(f"option {key!r} has an invalid condition: {error}") from error
        sentiment = normalise_sentiment(data.get("sentiment", "neutral"))
        options[key] = DialogOption(
            key,
            nodes[next_key],
            data["text"],
            data.get("order", 0),
            condition,
            sentiment,
        )
    return options


def _attach_options(
    section: dict[str, Any],
    nodes: dict[str, DialogNode],
    options: dict[str, DialogOption],
    debug_options: list[DialogOption],
) -> None:
    for node_key, option_keys in section.items():
        if node_key not in nodes:
            raise ValueError(
                f"NODES_OPTIONS references unknown node {node_key!r}"
            )
        node = nodes[node_key]
        for option_key in option_keys:
            if option_key not in options:
                raise ValueError(
                    f"node {node_key!r} references unknown option {option_key!r}"
                )
            node.options.append(options[option_key])
        if debug_options:
            node.options.extend(debug_options)


def _build_debug_options(
    dialog: dict[str, Any], nodes: dict[str, DialogNode]
) -> list[DialogOption]:
    """DEBUG jump options: to START_NODE and to every ``is_final`` node (D9)."""
    debug_options: list[DialogOption] = [
        DialogOption(
            key="DEBUG_START_NODE",
            next_node=nodes[dialog["START_NODE"]],
            # not an f-string on purpose — RPG evaluates the markup later.
            # MoM RichText tags (D3): [red]->[error], [blue]->[item], [yellow]->[char];
            # named closing tags (MoM parser has no generic [/]).
            text="[error]DEBUG[/error] START ([item]current dialog node[/item]=[char]{character.dialog.key}[/char])",
            order=100,
            condition="True",
            sentiment="human",
        )
    ]
    i = 0
    for node in nodes.values():
        if node.is_final:
            i += 1
            debug_options.append(
                DialogOption(
                    key=f"DEBUG_END_NODE_{node.key}",
                    next_node=node,
                    text=f"[error]DEBUG[/error] END   ([item]end     dialog node[/item]=[char]{node.key}[/char])",
                    order=100 + i,
                    condition="True",
                    sentiment="human",
                )
            )
    return debug_options
