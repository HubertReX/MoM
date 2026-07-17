"""Quest engine: what is unlocked, what is complete (Q-03).

Pure logic. The engine never touches pygame, never renders and never notifies —
it answers questions about a ``{key: QuestDef}`` map plus a :class:`QuestState`,
and marks quests done. Toasts (Q-09) and the panel (Q-08) read the result.

Two decisions shape everything here:

- **D6 — "unlocked" is derived, never stored.** :func:`is_unlocked` recomputes
  from ``requires`` on every call. SSiS kept an ``is_unlocked`` flag in the
  config and set it from exactly two places; the result was ``Q01_S05``, a quest
  nothing ever unlocked, which killed the whole curse chain silently. A derived
  value cannot drift out of sync with the thing it is derived from.
- **D5 — completion is explicit.** No inferring "is this finished?" from the
  shape of the data; :class:`CompletionMode` says it outright.

Not exported from ``quest/__init__.py`` on purpose: this module reaches into the
condition DSL (and through it, ``settings``), while ``quest.entities`` /
``quest.graph`` stay a pure, dependency-free core.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dialog.conditions import ConditionContext, ConditionScope, check_condition, eval_number
from quest.entities import CompletionMode, QuestDef, QuestState
from quest.graph import children_of


class QuestEngineError(RuntimeError):
    """The engine hit a state that should be impossible after validation."""


@dataclass(slots=True)
class QuestCheckResult:
    """What changed during one :func:`check_quests` sweep.

    Both lists are in definition order and are empty on a quiet sweep, which is
    the overwhelmingly common case (the engine runs on events and on a ~1s
    safety sweep — see Q-07).
    """

    newly_done: list[str] = field(default_factory=list)
    newly_unlocked: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        """True when the sweep changed anything worth reacting to."""
        return bool(self.newly_done or self.newly_unlocked)


def is_unlocked(defs: dict[str, QuestDef], state: QuestState, key: str) -> bool:
    """Can the player work on ``key`` right now?

    Two gates, both derived (D6):

    - every quest in ``requires`` is done;
    - the parent thread, if any, is itself unlocked.

    The parent gate is what makes a subquest part of a *thread* rather than a
    free-floating task. ``Q03_S01`` ("Kto ma wiedzę o magii?") lists no
    ``requires`` of its own — only ``parent: Q03_S00`` — so without this gate it
    would be live from the first frame and the umbrella's own
    ``requires: [Q01_S01]`` would mean nothing.

    Note it is the parent's *unlocked* state that matters, not its done state:
    an ``all_subquests`` umbrella is only done once its children are, so gating
    children on a done parent would deadlock the pair.

    Safe to recurse: ``init_quests`` rejects cycles in the requires/parent graph.
    """
    quest = defs[key]
    if not all(state.is_done(required) for required in quest.requires):
        return False
    if quest.parent is not None and not is_unlocked(defs, state, quest.parent):
        return False
    return True


def unlocked_keys(defs: dict[str, QuestDef], state: QuestState) -> set[str]:
    """Every quest currently unlocked, done or not."""
    return {key for key in defs if is_unlocked(defs, state, key)}


def is_complete(
    defs: dict[str, QuestDef],
    state: QuestState,
    ctx: ConditionContext,
    key: str,
) -> bool:
    """Does ``key`` satisfy its completion rule *right now* (D5)?

    Says nothing about whether the quest is unlocked or already marked done —
    :func:`check_quests` owns that. Raises rather than guesses when a quest's
    rule cannot be evaluated.
    """
    quest = defs[key]

    if quest.completion is CompletionMode.manual:
        return False

    if quest.completion is CompletionMode.test:
        if not quest.test:
            # init_quests rejects this; reaching it means defs were hand-built
            raise QuestEngineError(f"quest {key!r} has completion 'test' but no test")
        return check_condition(quest.test, ctx, ConditionScope.quest)

    children = children_of(defs, key)
    if not children:
        # The Q01_S07 shape: an umbrella nobody parents to. all([]) is True, so
        # without this guard it would complete instantly and silently — the
        # opposite of the SSiS bug but just as wrong. init_quests rejects it.
        raise QuestEngineError(
            f"quest {key!r} has completion 'all_subquests' but no subquests"
        )
    return all(state.is_done(child) for child in children)


def check_quests(
    defs: dict[str, QuestDef],
    state: QuestState,
    ctx: ConditionContext,
) -> QuestCheckResult:
    """Complete every quest that has become completable; mutate ``state``.

    Cascades: finishing A can unlock B, which may already satisfy its own test
    (its condition is a fact about the world, and the world does not care in
    which order the player learned things). So this repeats until a pass changes
    nothing, rather than settling for one pass and leaving B to be caught a
    second later by the sweep.

    Returns what changed, so the caller can raise toasts (Q-09) without
    diffing state itself.
    """
    unlocked_before = unlocked_keys(defs, state)
    newly_done: list[str] = []

    # Every pass either marks at least one quest done or breaks, and a done quest
    # is never revisited, so len(defs) passes is the hard ceiling; the +1 lets the
    # final no-progress pass run. Falling out of the loop means that invariant
    # broke — say so instead of spinning.
    for _ in range(len(defs) + 1):
        progressed = False
        for key in defs:
            if state.is_done(key):
                continue
            if not is_unlocked(defs, state, key):
                continue
            if is_complete(defs, state, ctx, key):
                state.mark_done(key)
                newly_done.append(key)
                progressed = True
        if not progressed:
            break
    else:
        raise QuestEngineError(
            f"quest cascade did not stabilise after {len(defs) + 1} passes"
        )

    unlocked_after = unlocked_keys(defs, state)
    # A quest that unlocked and completed in the same sweep is reported as done
    # only: telling the player they can now start something they just finished is
    # noise.
    newly_unlocked = [
        key
        for key in defs
        if key in unlocked_after and key not in unlocked_before and not state.is_done(key)
    ]

    return QuestCheckResult(newly_done, newly_unlocked)


def quest_progress(
    defs: dict[str, QuestDef],
    state: QuestState,
    ctx: ConditionContext,
    key: str,
) -> tuple[int, int] | None:
    """``(current, total)`` for a progress bar, or ``None`` when there is nothing to show.

    Two sources, in order:

    - an explicit ``progress`` expression with its ``progress_total`` (D9);
    - an ``all_subquests`` umbrella, counted from its children ("2/3") — no
      authoring needed, the thread already says it.

    A done quest reads as full even if its expression says otherwise, so a
    finished quest never shows "2/3" in the log.
    """
    quest = defs[key]

    if quest.progress:
        total = quest.progress_total
        if state.is_done(key):
            return total, total
        current = eval_number(quest.progress, ctx, ConditionScope.quest)
        return max(0, min(current, total)), total

    if quest.completion is CompletionMode.all_subquests:
        children = children_of(defs, key)
        if not children:
            return None
        return sum(state.is_done(child) for child in children), len(children)

    return None


__all__ = [
    "QuestCheckResult",
    "QuestEngineError",
    "check_quests",
    "is_complete",
    "is_unlocked",
    "quest_progress",
    "unlocked_keys",
]
