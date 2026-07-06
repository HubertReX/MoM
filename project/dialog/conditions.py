"""Mini-DSL for dialog option conditions (decision **D1**).

Parse a condition with ``ast.parse(mode="eval")`` and interpret it with our own
walker over a strict *whitelist* of AST nodes. **Never** ``eval``/``exec`` — so
it is:

- **web-safe:** ``ast`` is pure Python and runs under pygbag/WASM (no C extension,
  no code object execution),
- **sandboxed:** no attribute access, no subscripts, no builtins, no name lookups
  except the handful below — a malformed or hostile condition cannot reach the
  game objects, only the predicate bridge can.

Ported from the RPG prototype, where ``dialog_loc.py:check_condition`` used raw
``eval(condition, cfg)`` against live game objects
(``character.selected_options_dict``, ``hero.inventory.items``,
``character.sentiment``). Here those raw attribute paths are replaced by a small
set of **predicates** — the only bridge between the DSL and game data:

===========================  ================================================
DSL                          meaning
===========================  ================================================
``selected(opt)``            option ``opt`` was chosen by the current character
``visited(node)``            node ``node`` was visited by the current character
``visited(npc, node)``       node ``node`` was visited by another NPC ``npc``
``has_item(key)``            the hero holds item ``key``
``sentiment``                current character's sentiment (bare name -> int)
===========================  ================================================

Predicates compose with boolean / unary / comparison operators::

    sentiment >= 42 and selected("BOB_DO_HOBBY_BIKE")
    not visited("003") or has_item("MERMAIDS_TEAR")
    visited("HAMMER_HOAXHEART_001", "004")

Data reaches the engine through a :class:`ConditionContext` (a ``Protocol`` — the
game adapter and tests both satisfy it). :func:`validate_condition` checks a
condition against the whitelist *without* a context, for loud import-time
failures (decision D6); :func:`check_condition` validates then evaluates.

Allowed AST nodes: ``Expression`` (root), ``BoolOp`` (and/or), ``UnaryOp``
(``not`` / unary ``-`` / ``+``), ``Compare``, ``Call`` (predicate whitelist
only), ``Name`` (``sentiment`` only), ``Constant``. Anything else — attribute
access, subscripts, lambdas, comprehensions, unknown names/functions, wrong
arity — raises :class:`ConditionError`.
"""

from __future__ import annotations

import ast
import operator
from functools import lru_cache
from typing import Any, Callable, Protocol, runtime_checkable


class ConditionError(ValueError):
    """A dialog condition is malformed or reaches outside the whitelist.

    Subclasses ``ValueError`` so existing ``except ValueError`` around graph
    loading (see ``dialog/graph.py``) also catches condition problems. The
    message quotes the offending condition so a broken dialog fails *loudly* at
    import time instead of silently evaluating to ``False`` mid-conversation.
    """


@runtime_checkable
class ConditionContext(Protocol):
    """The bridge between the DSL and game data (the only way in).

    The game supplies an adapter backed by the live character / hero / config
    (see decision D8, task T-023); tests supply a tiny in-memory stub. Every
    predicate in a condition maps to exactly one method / property here.
    """

    def selected(self, option_key: str) -> bool:
        """Did the current character choose option ``option_key``?"""
        ...

    def visited(self, node_key: str, npc: str | None = None) -> bool:
        """Was node ``node_key`` visited — by ``npc`` if given, else the current character?"""
        ...

    def has_item(self, item_key: str) -> bool:
        """Does the hero hold item ``item_key``?"""
        ...

    @property
    def sentiment(self) -> int:
        """The current character's sentiment toward the hero."""
        ...


# ---------------------------------------------------------------------------
# Whitelist tables
# ---------------------------------------------------------------------------

# predicate name -> (min args, max args). ``visited`` takes 1 (self) or 2 (npc, node).
_PREDICATES: dict[str, tuple[int, int]] = {
    "selected": (1, 1),
    "visited": (1, 2),
    "has_item": (1, 1),
}

# bare names that resolve to a value (not a call)
_VALUE_NAMES: frozenset[str] = frozenset({"sentiment"})

# comparison operator node -> concrete function
_COMPARE_OPS: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


# ---------------------------------------------------------------------------
# Parse + validate (context-free, cached)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=512)
def _compile(condition: str) -> ast.Expression:
    """Parse and whitelist-validate ``condition``; cache the resulting AST.

    Conditions are re-checked every frame while a dialog is on screen, so the
    parse + validation is memoised on the condition string. Raises
    :class:`ConditionError` on syntax or whitelist violations.
    """
    try:
        tree = ast.parse(condition, mode="eval")
    except SyntaxError as error:
        raise ConditionError(
            f"syntax error in condition {condition!r}: {error.msg}"
        ) from error
    _validate(tree.body, condition)
    return tree


def _validate(node: ast.AST, condition: str) -> None:
    """Recursively assert ``node`` uses only whitelisted constructs."""
    if isinstance(node, ast.BoolOp):
        for value in node.values:
            _validate(value, condition)

    elif isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.Not, ast.USub, ast.UAdd)):
            raise ConditionError(
                f"unsupported unary operator {type(node.op).__name__} in "
                f"condition {condition!r}"
            )
        _validate(node.operand, condition)

    elif isinstance(node, ast.Compare):
        for op in node.ops:
            if type(op) not in _COMPARE_OPS:
                raise ConditionError(
                    f"unsupported comparison {type(op).__name__} in "
                    f"condition {condition!r}"
                )
        _validate(node.left, condition)
        for comparator in node.comparators:
            _validate(comparator, condition)

    elif isinstance(node, ast.Call):
        _validate_call(node, condition)

    elif isinstance(node, ast.Name):
        if node.id not in _VALUE_NAMES and node.id not in _PREDICATES:
            raise ConditionError(
                f"unknown name {node.id!r} in condition {condition!r} "
                f"(allowed: {', '.join(sorted(_VALUE_NAMES))})"
            )

    elif isinstance(node, ast.Constant):
        if not isinstance(node.value, (str, int, float, bool)) and node.value is not None:
            raise ConditionError(
                f"unsupported constant {node.value!r} in condition {condition!r}"
            )

    else:
        raise ConditionError(
            f"unsupported expression {type(node).__name__} in condition "
            f"{condition!r} (no attribute access, subscripts or lambdas allowed)"
        )


def _validate_call(node: ast.Call, condition: str) -> None:
    if not isinstance(node.func, ast.Name):
        raise ConditionError(
            f"only bare predicate calls are allowed in condition {condition!r}"
        )
    name = node.func.id
    if name not in _PREDICATES:
        raise ConditionError(
            f"unknown predicate {name!r} in condition {condition!r} "
            f"(allowed: {', '.join(sorted(_PREDICATES))})"
        )
    if node.keywords:
        raise ConditionError(
            f"predicate {name!r} takes no keyword arguments in condition "
            f"{condition!r}"
        )
    lo, hi = _PREDICATES[name]
    if not lo <= len(node.args) <= hi:
        arity = str(lo) if lo == hi else f"{lo}-{hi}"
        raise ConditionError(
            f"predicate {name}() takes {arity} argument(s), got "
            f"{len(node.args)} in condition {condition!r}"
        )
    for arg in node.args:
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            raise ConditionError(
                f"predicate {name}() arguments must be string literals in "
                f"condition {condition!r}"
            )


def validate_condition(condition: str) -> None:
    """Validate ``condition`` against the whitelist without evaluating it.

    Call this at dialog import time (decision D6) so an unknown name/predicate
    or a disallowed construct fails loudly with the offending source, rather
    than silently evaluating to ``False`` during play. Raises
    :class:`ConditionError` on any problem; returns ``None`` when valid.
    """
    _compile(condition)


# ---------------------------------------------------------------------------
# Evaluate against a context
# ---------------------------------------------------------------------------


def check_condition(condition: str, ctx: ConditionContext) -> bool:
    """Return the truth value of ``condition`` for ``ctx``.

    Validates first (so a broken condition raises :class:`ConditionError` rather
    than misbehaving), then interprets the whitelisted AST against the predicate
    bridge. The result is coerced to ``bool``.
    """
    tree = _compile(condition)
    return bool(_Interpreter(ctx).eval(tree.body))


class _Interpreter:
    """Walk a pre-validated condition AST, pulling data through the predicates."""

    __slots__ = ("ctx",)

    def __init__(self, ctx: ConditionContext) -> None:
        self.ctx = ctx

    def eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.BoolOp):
            return self._eval_boolop(node)
        if isinstance(node, ast.UnaryOp):
            return self._eval_unaryop(node)
        if isinstance(node, ast.Compare):
            return self._eval_compare(node)
        if isinstance(node, ast.Call):
            return self._eval_call(node)
        if isinstance(node, ast.Name):
            return self._eval_name(node)
        if isinstance(node, ast.Constant):
            return node.value
        # unreachable: _validate rejects everything else before we get here
        raise ConditionError(f"cannot evaluate {type(node).__name__}")

    def _eval_boolop(self, node: ast.BoolOp) -> bool:
        if isinstance(node.op, ast.And):
            return all(self.eval(value) for value in node.values)
        # ast.Or
        return any(self.eval(value) for value in node.values)

    def _eval_unaryop(self, node: ast.UnaryOp) -> Any:
        operand = self.eval(node.operand)
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.USub):
            return -operand
        # ast.UAdd
        return +operand

    def _eval_compare(self, node: ast.Compare) -> bool:
        left = self.eval(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = self.eval(comparator)
            if not _COMPARE_OPS[type(op)](left, right):
                return False
            left = right  # chained comparison: a < b < c
        return True

    def _eval_name(self, node: ast.Name) -> Any:
        if node.id == "sentiment":
            return self.ctx.sentiment
        # unreachable after validation
        raise ConditionError(f"unknown name {node.id!r}")

    def _eval_call(self, node: ast.Call) -> bool:
        name = node.func.id  # type: ignore[attr-defined]  # validated to be a Name
        args = [self.eval(arg) for arg in node.args]
        if name == "selected":
            return self.ctx.selected(args[0])
        if name == "has_item":
            return self.ctx.has_item(args[0])
        if name == "visited":
            if len(args) == 1:
                return self.ctx.visited(args[0])
            # visited(npc, node) — npc first, node second
            return self.ctx.visited(args[1], npc=args[0])
        # unreachable after validation
        raise ConditionError(f"unknown predicate {name!r}")


__all__ = [
    "ConditionContext",
    "ConditionError",
    "check_condition",
    "validate_condition",
]
