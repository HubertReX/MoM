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
``item_count(key)``          how many of item ``key`` the hero holds (-> int)
``quest_done(key)``          quest ``key`` is complete
``sentiment``                current character's sentiment (bare name -> int)
===========================  ================================================

Predicates compose with boolean / unary / comparison operators::

    sentiment >= 42 and selected("BOB_DO_HOBBY_BIKE")
    not visited("003") or has_item("MERMAIDS_TEAR")
    visited("HAMMER_HOAXHEART_001", "004")

**Scopes** (decision D7 — the whitelist stays narrow, and narrows further per
caller). A dialog condition is evaluated *during a conversation*, so it has a
"current character"; a quest ``test`` is evaluated from the quest engine and has
none. :class:`ConditionScope` picks which names are legal:

- ``dialog`` — everything in the table above.
- ``quest`` — no ``selected()``, no ``sentiment`` (there is no current NPC to
  ask), and ``visited()`` **requires** its ``npc`` argument, so a quest cannot
  accidentally ask "did *nobody in particular* visit this node?" and silently
  get ``False`` forever.

Data reaches the engine through a :class:`ConditionContext` (a ``Protocol`` — the
game adapter and tests both satisfy it); :class:`DialogConditionContext` adds the
two conversation-only members. :func:`validate_condition` checks a condition
against the whitelist *without* a context, for loud import-time failures
(decision D6); :func:`check_condition` validates then evaluates;
:func:`eval_number` does the same but yields an ``int`` (decision D9).

Allowed AST nodes: ``Expression`` (root), ``BoolOp`` (and/or), ``UnaryOp``
(``not`` / unary ``-`` / ``+``), ``Compare``, ``Call`` (predicate whitelist
only), ``Name`` (``sentiment`` only), ``Constant``. Anything else — attribute
access, subscripts, lambdas, comprehensions, unknown names/functions, wrong
arity — raises :class:`ConditionError`.
"""

from __future__ import annotations

import ast
import operator
from enum import StrEnum, auto
from functools import lru_cache
from typing import Any, Callable, Protocol, runtime_checkable


class ConditionError(ValueError):
    """A dialog condition is malformed or reaches outside the whitelist.

    Subclasses ``ValueError`` so existing ``except ValueError`` around graph
    loading (see ``dialog/graph.py``) also catches condition problems. The
    message quotes the offending condition so a broken dialog fails *loudly* at
    import time instead of silently evaluating to ``False`` mid-conversation.
    """


class ConditionScope(StrEnum):
    """Which names a condition may use — see the module docstring."""

    dialog = auto()
    quest = auto()


@runtime_checkable
class ConditionContext(Protocol):
    """The bridge between the DSL and game data (the only way in).

    This is the part that makes sense *without* a conversation on screen: facts
    about the world and the hero. Quests use exactly this; dialogs use
    :class:`DialogConditionContext`, which adds the conversation-only members.

    The game supplies an adapter backed by the live character / hero / config
    (see decision D8, task T-023); tests supply a tiny in-memory stub. Every
    predicate in a condition maps to exactly one method / property here.
    """

    def visited(self, node_key: str, npc: str | None = None) -> bool:
        """Was node ``node_key`` visited — by ``npc`` if given, else the current character?"""
        ...

    def has_item(self, item_key: str) -> bool:
        """Does the hero hold item ``item_key``?"""
        ...

    def item_count(self, item_key: str) -> int:
        """How many of item ``item_key`` does the hero hold?"""
        ...

    def quest_done(self, quest_key: str) -> bool:
        """Is quest ``quest_key`` complete?"""
        ...


@runtime_checkable
class DialogConditionContext(ConditionContext, Protocol):
    """A :class:`ConditionContext` evaluated *during a conversation*.

    Only these two need a "current character", which is exactly why quests
    cannot use them (scope ``quest`` rejects both at validation time).
    """

    def selected(self, option_key: str) -> bool:
        """Did the current character choose option ``option_key``?"""
        ...

    @property
    def sentiment(self) -> int:
        """The current character's sentiment toward the hero."""
        ...


# ---------------------------------------------------------------------------
# Whitelist tables
# ---------------------------------------------------------------------------

# predicate name -> (min args, max args), per scope.
#
# Names that make sense with or without a conversation on screen. ``visited``
# takes 1 (current character) or 2 (npc, node) args here.
_COMMON_PREDICATES: dict[str, tuple[int, int]] = {
    "visited": (1, 2),
    "has_item": (1, 1),
    "item_count": (1, 1),
    "quest_done": (1, 1),
}

_DIALOG_PREDICATES: dict[str, tuple[int, int]] = {
    **_COMMON_PREDICATES,
    "selected": (1, 1),
}

# A quest has no current NPC, so `visited` MUST name one: arity is exactly 2.
# Without this, `visited("012")` in a quest would parse, evaluate against
# nothing, and sit at False forever — the silent-corpse failure mode the whole
# quest epic exists to prevent (see doc/quest-migration-plan.md, Pułapka 5).
_QUEST_PREDICATES: dict[str, tuple[int, int]] = {
    **_COMMON_PREDICATES,
    "visited": (2, 2),
}

_PREDICATES_BY_SCOPE: dict[ConditionScope, dict[str, tuple[int, int]]] = {
    ConditionScope.dialog: _DIALOG_PREDICATES,
    ConditionScope.quest: _QUEST_PREDICATES,
}

# bare names that resolve to a value (not a call), per scope
_VALUE_NAMES_BY_SCOPE: dict[ConditionScope, frozenset[str]] = {
    ConditionScope.dialog: frozenset({"sentiment"}),
    ConditionScope.quest: frozenset(),
}

# Predicates that return a *number* rather than a yes/no. Only these (or a
# numeric literal) make a valid `progress` expression — see `validate_number`.
# Kept in sync by hand with `_Interpreter._eval_call`: item_count reads a count,
# every other predicate answers a question. A numeric predicate added there
# without being added here would still work at runtime but be rejected as
# progress, which fails loud rather than silent — the safe direction.
_NUMERIC_PREDICATES: frozenset[str] = frozenset({"item_count"})

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
def _compile(condition: str, scope: ConditionScope) -> ast.Expression:
    """Parse and whitelist-validate ``condition``; cache the resulting AST.

    Conditions are re-checked every frame while a dialog is on screen, so the
    parse + validation is memoised on the (condition, scope) pair. Raises
    :class:`ConditionError` on syntax or whitelist violations.
    """
    try:
        tree = ast.parse(condition, mode="eval")
    except SyntaxError as error:
        raise ConditionError(
            f"syntax error in condition {condition!r}: {error.msg}"
        ) from error
    _validate(tree.body, condition, scope)
    return tree


def _validate(node: ast.AST, condition: str, scope: ConditionScope) -> None:
    """Recursively assert ``node`` uses only constructs whitelisted for ``scope``."""
    if isinstance(node, ast.BoolOp):
        for value in node.values:
            _validate(value, condition, scope)

    elif isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.Not, ast.USub, ast.UAdd)):
            raise ConditionError(
                f"unsupported unary operator {type(node.op).__name__} in "
                f"condition {condition!r}"
            )
        _validate(node.operand, condition, scope)

    elif isinstance(node, ast.Compare):
        for op in node.ops:
            if type(op) not in _COMPARE_OPS:
                raise ConditionError(
                    f"unsupported comparison {type(op).__name__} in "
                    f"condition {condition!r}"
                )
        _validate(node.left, condition, scope)
        for comparator in node.comparators:
            _validate(comparator, condition, scope)

    elif isinstance(node, ast.Call):
        _validate_call(node, condition, scope)

    elif isinstance(node, ast.Name):
        value_names = _VALUE_NAMES_BY_SCOPE[scope]
        if node.id not in value_names and node.id not in _PREDICATES_BY_SCOPE[scope]:
            allowed = ", ".join(sorted(value_names)) or "none"
            raise ConditionError(
                f"unknown name {node.id!r} in {scope.value} condition {condition!r} "
                f"(allowed: {allowed})"
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


def _validate_call(node: ast.Call, condition: str, scope: ConditionScope) -> None:
    if not isinstance(node.func, ast.Name):
        raise ConditionError(
            f"only bare predicate calls are allowed in condition {condition!r}"
        )
    predicates = _PREDICATES_BY_SCOPE[scope]
    name = node.func.id
    if name not in predicates:
        # Name the scope: `selected()` in a quest is a plausible authoring
        # mistake, and "unknown predicate" alone would read as a typo.
        raise ConditionError(
            f"unknown predicate {name!r} in {scope.value} condition {condition!r} "
            f"(allowed: {', '.join(sorted(predicates))})"
        )
    if node.keywords:
        raise ConditionError(
            f"predicate {name!r} takes no keyword arguments in condition "
            f"{condition!r}"
        )
    lo, hi = predicates[name]
    if not lo <= len(node.args) <= hi:
        arity = str(lo) if lo == hi else f"{lo}-{hi}"
        raise ConditionError(
            f"predicate {name}() takes {arity} argument(s), got "
            f"{len(node.args)} in {scope.value} condition {condition!r}"
        )
    for arg in node.args:
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            raise ConditionError(
                f"predicate {name}() arguments must be string literals in "
                f"condition {condition!r}"
            )


def validate_condition(
    condition: str, scope: ConditionScope = ConditionScope.dialog
) -> None:
    """Validate ``condition`` against ``scope``'s whitelist without evaluating it.

    Call this at import time (decision D6) so an unknown name/predicate or a
    disallowed construct fails loudly with the offending source, rather than
    silently evaluating to ``False`` during play. Raises :class:`ConditionError`
    on any problem; returns ``None`` when valid.
    """
    _compile(condition, scope)


def _yields_number(node: ast.AST) -> bool:
    """Would this pre-validated node evaluate to a number rather than a bool?

    A static mirror of :func:`eval_number`'s runtime type check. The whitelist is
    small enough to decide from shape alone: a numeric literal, a call to a
    numeric predicate, their unary sign, or an ``and``/``or`` of numeric operands.
    A comparison, a ``not``, or a call to a yes/no predicate is boolean.
    """
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id in _NUMERIC_PREDICATES
    if isinstance(node, ast.UnaryOp):
        return isinstance(node.op, (ast.USub, ast.UAdd)) and _yields_number(node.operand)
    if isinstance(node, ast.BoolOp):
        return all(_yields_number(value) for value in node.values)
    return False


def validate_number(
    expression: str, scope: ConditionScope = ConditionScope.quest
) -> None:
    """Validate ``expression`` as a numeric one (decision D9 — quest progress).

    Whitelist first, then a static type check: a ``progress`` expression drives a
    bar, so it must yield a *number*. Without this, ``progress: 'has_item("X")'``
    passes the plain whitelist (it is a valid *condition*) and only blows up at
    runtime — the moment the journal opens and draws the bar — instead of naming
    the offending line at import. Raises :class:`ConditionError`; returns ``None``
    when valid.
    """
    tree = _compile(expression, scope)
    if not _yields_number(tree.body):
        raise ConditionError(
            f"expression {expression!r} must be a number, not a yes/no condition "
            f"(a progress bar counts something — use e.g. item_count(\"ITEM\"))"
        )


# ---------------------------------------------------------------------------
# Evaluate against a context
# ---------------------------------------------------------------------------


def check_condition(
    condition: str,
    ctx: ConditionContext,
    scope: ConditionScope = ConditionScope.dialog,
) -> bool:
    """Return the truth value of ``condition`` for ``ctx``.

    Validates first (so a broken condition raises :class:`ConditionError` rather
    than misbehaving), then interprets the whitelisted AST against the predicate
    bridge. The result is coerced to ``bool``.
    """
    tree = _compile(condition, scope)
    return bool(_Interpreter(ctx).eval(tree.body))


def eval_number(
    expression: str,
    ctx: ConditionContext,
    scope: ConditionScope = ConditionScope.quest,
) -> int:
    """Evaluate ``expression`` to an ``int`` (decision D9 — quest progress).

    Same parser, same whitelist, same predicate bridge as
    :func:`check_condition`; only the result type differs. Used for a quest's
    ``progress`` expression, e.g. ``item_count("MERMAIDS_TEAR")``.

    A ``bool`` result is rejected rather than silently counted as 0/1: writing
    ``progress: 'visited("X", "1")'`` is an authoring mistake (a yes/no fact is
    not a quantity), and a progress bar reading "1/3" because a predicate
    happened to be true is exactly the kind of quiet nonsense this epic is
    trying to design out.
    """
    tree = _compile(expression, scope)
    value = _Interpreter(ctx).eval(tree.body)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConditionError(
            f"expression {expression!r} must evaluate to a number, got "
            f"{type(value).__name__} ({value!r})"
        )
    return int(value)


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
            # dialog scope only; validation keeps quests from reaching this
            return self.ctx.sentiment  # type: ignore[attr-defined]
        # unreachable after validation
        raise ConditionError(f"unknown name {node.id!r}")

    def _eval_call(self, node: ast.Call) -> Any:
        name = node.func.id  # type: ignore[attr-defined]  # validated to be a Name
        args = [self.eval(arg) for arg in node.args]
        if name == "has_item":
            return self.ctx.has_item(args[0])
        if name == "item_count":
            return self.ctx.item_count(args[0])
        if name == "quest_done":
            return self.ctx.quest_done(args[0])
        if name == "visited":
            if len(args) == 1:
                return self.ctx.visited(args[0])
            # visited(npc, node) — npc first, node second
            return self.ctx.visited(args[1], npc=args[0])
        if name == "selected":
            # dialog scope only; validation keeps quests from reaching this
            return self.ctx.selected(args[0])  # type: ignore[attr-defined]
        # unreachable after validation
        raise ConditionError(f"unknown predicate {name!r}")


__all__ = [
    "ConditionContext",
    "ConditionError",
    "ConditionScope",
    "DialogConditionContext",
    "check_condition",
    "eval_number",
    "validate_condition",
    "validate_number",
]
