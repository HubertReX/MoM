"""Quest System — quest entities and builder (epic Q).

Pure logic (no pygame, no Pydantic): the quest data model plus
:func:`init_quests`, which turns the ``config.json["quests"]`` section into a
resolved ``{key: QuestDef}`` map and rejects quests that could never complete
(Q-01).

Definitions come from the config; progress lives in :class:`QuestState`, which
goes into the savegame (decision D13). "Unlocked" is not stored anywhere — it is
derived from ``requires`` by the engine (decision D6, Q-03).
"""

from quest.entities import (
    CompletionMode,
    QuestDef,
    QuestReward,
    QuestRewardCategory,
    QuestState,
    )
from quest.graph import children_of, init_quests

__all__ = [
    "CompletionMode",
    "QuestRewardCategory",
    "QuestReward",
    "QuestDef",
    "QuestState",
    "init_quests",
    "children_of",
]
