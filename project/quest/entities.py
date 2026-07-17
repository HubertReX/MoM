"""Quest entities — pure dataclasses (no pygame, no Pydantic).

Ported from SSiS ``quests.py``, but with its two structural bugs designed out
(see ``doc/quest-migration-plan.md``, Pułapki 1-2 and 8):

- SSiS inferred "how does this quest finish?" from the shape of the data, which
  let ``Q01_S07`` ship as a silent corpse (``test: "False"``, no subquests, so
  it could never complete and blocked the whole curse chain). Here
  :class:`CompletionMode` is **explicit** (decision D5) and
  :func:`quest.graph.init_quests` refuses that combination outright.
- SSiS applied only the *first* non-zero reward (a stray ``break``). Rewards are
  a plain ``list`` here (decision D10) and Q-05 loops over all of them.

Quests hold only i18n *keys* (``name`` / ``description`` / ``success`` are
``messages`` keys, resolved via ``get_msg()`` at render time — decision D3),
never rendered strings.

Definition and progress are separate on purpose (decision D13): :class:`QuestDef`
comes from ``config.json`` (generated, immutable at runtime), :class:`QuestState`
lives in the savegame. ``is_unlocked`` is deliberately **absent** from the state
— it is derived from ``requires`` on demand (decision D6), which is what makes
an unreachable quest impossible to persist.

Works on both desktop and pygbag/WASM: stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any


class CompletionMode(StrEnum):
    """How a quest decides it is finished (decision D5).

    Explicit rather than inferred — this enum is the whole reason the
    ``Q01_S07`` class of bug cannot be expressed any more.
    """

    all_subquests = auto()
    """Done when every quest whose ``parent`` is this one is done (umbrella)."""

    test = auto()
    """Done when the ``test`` mini-DSL condition evaluates to True."""

    manual = auto()
    """Never completes on its own — only the story/engine closes it."""


class QuestRewardCategory(StrEnum):
    """What a reward gives. Maps 1:1 onto a ``ResultSink`` call in Q-05.

    Per decision D11 the SSiS stats were remapped onto stats MoM actually has:
    ``hp`` -> :attr:`damage`, ``eloquence`` -> :attr:`sentiment`; ``agility``
    was dropped (MoM has no such stat) and ``max_items`` needs
    ``MAX_HOTBAR_ITEMS`` promoted from a module constant to a player field.
    """

    money = auto()
    items = auto()
    health = auto()
    max_health = auto()
    damage = auto()
    max_items = auto()
    sentiment = auto()


@dataclass(slots=True)
class QuestReward:
    """One effect granted when a quest completes.

    ``value`` carries the amount for every category except :attr:`items`, which
    uses ``items`` (a list of ``config.json["items"]`` keys).

    ``target`` names the NPC a :attr:`sentiment` reward applies to. A quest is
    evaluated by the engine, not during a conversation, so unlike a dialog it has
    no "current NPC" to shift — the reward has to say who it means
    (``sentiment=10 @BARMAN_ABSINTHRAYNER``). Unused by every other category.
    """

    category: QuestRewardCategory
    value: int = 0
    items: list[str] = field(default_factory=list, repr=False)
    target: str | None = field(default=None, repr=False)


@dataclass(slots=True)
class QuestDef:
    """A single quest (or subquest) — immutable definition, no progress.

    ``name`` / ``description`` / ``success`` are ``messages`` keys, not text.
    ``success`` is plain prose with no ``{value}`` placeholder: the reward label
    is appended by the engine (decision D3, Q-05).
    """

    key: str
    name: str = field(repr=False)
    description: str = field(repr=False)
    success: str = field(repr=False)
    completion: CompletionMode
    test: str | None = field(default=None, repr=False)
    progress: str | None = field(default=None, repr=False)
    progress_total: int = field(default=0, repr=False)
    requires: list[str] = field(default_factory=list, repr=False)
    parent: str | None = field(default=None, repr=False)
    rewards: list[QuestReward] = field(default_factory=list, repr=False)


@dataclass(slots=True)
class QuestState:
    """Per-quest progress, the part that belongs in the savegame (decision D13).

    Serialised shape is ``{quest_key: {"done": bool}}`` — a dict per quest rather
    than a bare set of done keys, so Q-06 can add fields (timestamps, progress
    snapshots) without breaking old saves.

    A quest that is defined but missing from the state counts as not done, so a
    save written before new content was added still loads.
    """

    entries: dict[str, dict[str, Any]] = field(default_factory=dict)

    def is_done(self, key: str) -> bool:
        """Is quest ``key`` complete? Unknown keys are simply not done."""
        return bool(self.entries.get(key, {}).get("done", False))

    def mark_done(self, key: str, done: bool = True) -> None:
        """Set the done flag for ``key``, preserving any other fields."""
        self.entries.setdefault(key, {})["done"] = done

    def done_keys(self) -> set[str]:
        """Keys of every quest currently marked done."""
        return {key for key in self.entries if self.is_done(key)}

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Serialise for the save file (copies, so the save can't alias state)."""
        return {key: dict(entry) for key, entry in self.entries.items()}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "QuestState":
        """Rebuild from a save.

        Defensive by design: a non-dict entry (hand-edited or corrupted save)
        degrades to "not done" instead of crashing the load. Filtering keys that
        no longer exist in the definitions, and warning about them, is Q-06's
        job — it needs the defs, which this module deliberately does not.
        """
        if not isinstance(data, dict):
            return cls()
        entries: dict[str, dict[str, Any]] = {}
        for key, entry in data.items():
            if isinstance(entry, dict):
                entries[str(key)] = {**entry, "done": bool(entry.get("done", False))}
            else:
                entries[str(key)] = {"done": False}
        return cls(entries)


__all__ = [
    "CompletionMode",
    "QuestRewardCategory",
    "QuestReward",
    "QuestDef",
    "QuestState",
]
