"""Quest runtime: when to check, and what to do about it (Q-07).

Decision **D12=C**: event-driven, with a periodic sweep as a safety net. The two
halves have different jobs, and the difference matters:

- **Events** are the real mechanism. A quest should light up the moment the
  conversation that satisfies it ends, not a second later.
- **The sweep** exists to catch the event we forgot to wire. When it finds
  something, it **says so** — a net that quietly does the job of the mechanism it
  is backing up will hide every missing hook forever, and the log line is the only
  thing that turns "it works" into "it works for the right reason".

This is the piece that connects the pure engine to the live game: it owns the
definitions and the condition context, applies rewards for whatever completed,
and hands the result to the caller (Q-09 turns it into toasts).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from enums import NotificationTypeEnum
from dialog.result_sink import ResultSink
from quest.context_adapter import QuestConditionContext
from quest.engine import QuestCheckResult, check_quests
from quest.entities import QuestDef
from quest.graph import children_of, init_quests
from quest.rewards import apply_quest_rewards, success_text
from settings import _, entity_name, get_msg

if TYPE_CHECKING:
    from scene import Scene

# How often the safety sweep runs. Long enough to be cheap (8 quests, a handful
# of dict lookups), short enough that a missing event costs the player a beat
# rather than a session.
SWEEP_INTERVAL: float = 1.0


def quest_config(conf: object) -> dict[str, dict]:
    """The ``quests`` section as plain dicts, whichever loader built ``conf``.

    Decision D4 in the flesh: the desktop reads config.json through Pydantic, so
    ``conf.quests`` holds ``Quest`` *models*; the web build has no Pydantic and
    holds plain dicts. ``init_quests`` reads the plain shape — validate on the
    desktop, run on dicts everywhere — so the difference has to be flattened
    exactly once, here, rather than assumed by every caller.
    """
    raw = getattr(conf, "quests", None) or {}
    return {
        key: (value.model_dump(mode="json") if hasattr(value, "model_dump") else value)
        for key, value in raw.items()
    }


class QuestRuntime:
    """Owns quest definitions and drives :func:`check_quests` for one Scene.

    Progress itself lives on the Scene (``scene.quest_state``) because that is
    what the save serialises (decision D13); this object is rebuilt whenever a
    Scene is.
    """

    __slots__ = ("scene", "defs", "ctx", "_sweep_timer", "_sink_factory")

    def __init__(self, scene: "Scene", sink_factory: Callable[[], ResultSink] | None = None) -> None:
        self.scene = scene
        # init_quests re-validates on every Scene, which is cheap and means a
        # hand-edited config.json fails at load rather than mid-quest.
        self.defs: dict[str, QuestDef] = init_quests(quest_config(scene.game.conf))
        self.ctx = QuestConditionContext(scene)
        self._sweep_timer: float = 0.0
        # Injectable so tests can watch what the rewards do without building the
        # whole character/UI stack; the game leaves it at the default.
        self._sink_factory: Callable[[], ResultSink] = sink_factory or self._game_sink

    def on_event(self, source: str) -> QuestCheckResult:
        """Check quests because something happened that could have changed them."""
        return self._check(source)

    def update(self, dt: float) -> None:
        """Run the safety sweep every :data:`SWEEP_INTERVAL` seconds."""
        self._sweep_timer += dt
        if self._sweep_timer < SWEEP_INTERVAL:
            return
        self._sweep_timer = 0.0

        result = self._check("sweep")
        if result:
            # Not a crash, but not fine either: the quest is correct and the
            # wiring is not. Name what fired so the missing event is findable.
            print(
                f"[quest] sweep completed what an event should have: "
                f"done={result.newly_done} unlocked={result.newly_unlocked} "
                f"— an event hook is missing"
            )

    def _check(self, source: str) -> QuestCheckResult:
        if not self.defs:
            return QuestCheckResult()

        result = check_quests(self.defs, self.scene.quest_state, self.ctx)

        if result.newly_done:
            sink = self._sink_factory()
            for key in result.newly_done:
                apply_quest_rewards(self.defs[key], sink)

        self._announce(result)
        return result

    # --- toasts (Q-09) -------------------------------------------------------

    def _announce(self, result: QuestCheckResult) -> None:
        """Tell the player what just changed. No new machinery — Scene already toasts."""
        notify = getattr(self.scene, "add_notification", None)
        if notify is None:
            return

        for key in result.newly_done:
            quest = self.defs[key]
            name = f"[quest]{self._quest_name(quest)}[/quest]"
            # The author's prose is the payoff for finishing, and until now it was
            # imported, stored and localized without ever reaching the player.
            # success_text already knows how to join it to the reward label (D3=A).
            body = success_text(self._success_prose(quest), quest.rewards, self._item_name)

            if children_of(self.defs, key):
                # Closing a thread is a chapter ending, not another tick on a
                # list, so its headline is set apart — but by weight, not size:
                # [h3] was size 28, which wrapped the headline and left the toast's
                # lines uneven. [b] keeps every line the same size and still reads
                # as the louder of the two.
                headline = _("quest.toast_thread_done", name=name)
                notify(f"[b]{headline}[/b]\n{body}", NotificationTypeEnum.success)
            else:
                headline = _("quest.toast_done", name=name)
                notify(f"{headline}\n{body}", NotificationTypeEnum.success)

        for key in result.newly_unlocked:
            name = f"[quest]{self._quest_name(self.defs[key])}[/quest]"
            # A thread opening and a step inside it becoming available are
            # different news; calling a step "a new thread" would be a plain lie
            # to the player, and they can see both in the log anyway.
            message_key = (
                "quest.toast_unlocked_thread"
                if children_of(self.defs, key)
                else "quest.toast_unlocked_step"
            )
            notify(_(message_key, name=name), NotificationTypeEnum.info)

    def _quest_name(self, quest: QuestDef) -> str:
        """The quest's title in the current language (D3: quests hold keys, not text)."""
        messages = getattr(self.scene.game.conf, "messages", None) or {}
        return get_msg(messages, quest.name)

    def _success_prose(self, quest: QuestDef) -> str:
        """What the author wrote for how this quest ends."""
        messages = getattr(self.scene.game.conf, "messages", None) or {}
        return get_msg(messages, quest.success)

    def _item_name(self, item_key: str) -> str:
        items = getattr(self.scene.game.conf, "items", None) or {}
        model = items.get(item_key)
        return entity_name(model) if model is not None else item_key

    def _game_sink(self) -> ResultSink:
        # Imported here: result_sink_adapter pulls in the whole character/UI
        # stack, and quest.runtime is imported from Scene during its own
        # construction.
        from result_sink_adapter import GameResultSink

        # No NPC: a quest is not a conversation. Rewards that need to name one
        # carry their own target (`sentiment=10 @NPC`, Q-05).
        return GameResultSink(self.scene.player, None)


__all__ = ["QuestRuntime", "SWEEP_INTERVAL", "quest_config"]
