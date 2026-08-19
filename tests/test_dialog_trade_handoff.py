#!/usr/bin/env python3
"""Unit tests for the dialog -> shop handoff (`[[#trade-end]]`).

Run from the project root:
    .venv/bin/python tests/test_dialog_trade_handoff.py

The seam that makes this testable without a display is `GameUI._panel()`, which
returns `self._panels.get(panel_type)` before constructing anything: pre-seeding
that dict with fakes means no real panel (and no pygame surface) is ever built.
`GameUI.__init__` still wants a `HUD`, so the object is raised with
`object.__new__` and given only the attributes the handoff touches.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import inspect

from characters.player import Player
from ui.game_ui import GameUI
from ui.panels.dialog import DialogPanel
from ui.panels.trade import TradePanel


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}: expected {b!r}, got {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


class _FakePanel:
    def __init__(self) -> None:
        self.visible = False
        self.opened_with: list[dict] = []

    def open(self, **kwargs: object) -> None:
        self.opened_with.append(dict(kwargs))


class _FakeDialogPanel(_FakePanel):
    def __init__(self) -> None:
        super().__init__()
        self.trade_requested = False


class _FakeModel:
    def __init__(self, is_merchant: bool) -> None:
        self.is_merchant = is_merchant


class _FakeNPC:
    def __init__(self, is_merchant: bool = True) -> None:
        self.model = _FakeModel(is_merchant)
        self.dialog = "SOME_MID_NODE"
        self.dialog_start_node = "START"
        self.is_talking = True

    def reset_dialog(self) -> None:
        self.dialog = self.dialog_start_node


class _FakePlayer:
    def __init__(self, npc: "_FakeNPC | None") -> None:
        self.npc_met = npc
        self.is_talking = True
        self.normalised = 0

    def normalise_trade_selection(self) -> None:
        self.normalised += 1


class _FakeQuests:
    def __init__(self) -> None:
        self.events: list[str] = []

    def on_event(self, name: str) -> None:
        self.events.append(name)


class _FakeScene:
    def __init__(self, player: "_FakePlayer") -> None:
        self.player = player
        self.quests = _FakeQuests()


def _ui(npc: "_FakeNPC | None") -> tuple[GameUI, _FakeDialogPanel, _FakePanel, _FakePlayer]:
    player = _FakePlayer(npc)
    ui = object.__new__(GameUI)
    ui.scene = _FakeScene(player)  # type: ignore[assignment]
    dialog, trade = _FakeDialogPanel(), _FakePanel()
    ui._panels = {DialogPanel: dialog, TradePanel: trade}  # type: ignore[assignment]
    ui._open = [dialog]  # type: ignore[assignment]
    dialog.visible = True
    return ui, dialog, trade, player


def test_the_handoff_swaps_the_panels() -> None:
    """The dialog closes and the shop opens - in that order, in one frame."""
    ui, dialog, trade, player = _ui(_FakeNPC(is_merchant=True))
    dialog.trade_requested = True

    ui._drain_trade_request()

    assert_true(not ui.is_open(DialogPanel), "the conversation is over")
    assert_true(ui.is_open(TradePanel), "the shop is open")
    assert_eq(player.normalised, 1, "the hotbar cursor was re-seated for the merchant")
    assert_eq(dialog.trade_requested, False, "the flag is drained, not left to re-fire")


def test_is_talking_survives_the_handoff() -> None:
    """Clearing it here would let the next SPACE open a dialog on top of the shop.

    The trade-close path (`end_trade`) is what clears it, for both panels.
    """
    ui, dialog, _, player = _ui(_FakeNPC(is_merchant=True))
    dialog.trade_requested = True

    ui._drain_trade_request()

    assert_eq(player.is_talking, True, "the player is still busy")
    assert_eq(player.npc_met.is_talking, True, "so is the merchant")  # type: ignore[union-attr]


def test_the_next_conversation_starts_from_the_top() -> None:
    """Leaving for the shop ends the conversation, so its cursor goes back."""
    ui, dialog, _, player = _ui(_FakeNPC(is_merchant=True))
    dialog.trade_requested = True

    ui._drain_trade_request()

    npc = player.npc_met
    assert_eq(npc.dialog, npc.dialog_start_node, "the dialog rewound to its start node")  # type: ignore[union-attr]


def test_a_non_merchant_keeps_the_dialog(): # type: ignore[no-untyped-def]
    """`validate-world` calls this out, but the runtime must not open a blank shop.

    `TradePanel.draw` bails out for a non-merchant, so opening it would leave a
    window with nothing in it and no obvious way to reason about the state.
    """
    ui, dialog, trade, player = _ui(_FakeNPC(is_merchant=False))
    dialog.trade_requested = True

    ui._drain_trade_request()

    assert_true(ui.is_open(DialogPanel), "the conversation is left alone")
    assert_true(not ui.is_open(TradePanel), "no empty shop window")
    assert_eq(dialog.trade_requested, False, "the flag is still drained, not retried every frame")


def test_no_request_changes_nothing() -> None:
    """The drain runs every frame; it must be inert when nobody asked."""
    ui, dialog, _, player = _ui(_FakeNPC(is_merchant=True))

    ui._drain_trade_request()

    assert_true(ui.is_open(DialogPanel), "the dialog stays open")
    assert_true(not ui.is_open(TradePanel), "the shop stays shut")
    assert_eq(player.normalised, 0, "nothing was touched")


def test_the_handoff_reports_the_closed_dialog_to_the_quest_engine() -> None:
    """Quests key on `DialogPanel_closed`; leaving for the shop still closes it."""
    ui, dialog, _, player = _ui(_FakeNPC(is_merchant=True))
    dialog.trade_requested = True

    ui._drain_trade_request()

    assert_true(
        "DialogPanel_closed" in ui.scene.quests.events,  # type: ignore[attr-defined]
        f"got {ui.scene.quests.events}",  # type: ignore[attr-defined]
    )


def test_the_drain_is_wired_into_update() -> None:
    """The logic above is worthless if nothing calls it.

    It has to sit at the end of `update`: after both activation surfaces (the
    `accept` edge and the raw-event route that carries digits, Enter and mouse),
    and outside the loop over `_open`, which `close`/`open` mutate.
    """
    source = inspect.getsource(GameUI.update)
    assert_true("_drain_trade_request" in source, "GameUI.update drains the request")
    assert_true(
        source.index("for panel in self._open") < source.index("_drain_trade_request"),
        "the drain runs after the panel-update loop, not inside it",
    )


# ---------------------------------------------------------------------------
# SPACE arbitration: one key raises `talk`, `open` and `attack` together
# ---------------------------------------------------------------------------


class _FakeItem:
    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"<{self.name}>"


class _PlayerBits:
    """The two Player methods under test, borrowed onto a bare object.

    `Player.__init__` wants a live scene and a sprite group; these methods want
    four attributes between them, so lending the functions is both cheaper and
    more honest than half-building a Player.
    """

    can_interact_with_npc = Player.can_interact_with_npc
    normalise_trade_selection = Player.normalise_trade_selection

    def __init__(self, npc: object = None, items: "list[_FakeItem] | None" = None,
                 tradable: "list[_FakeItem] | None" = None, idx: int = 0) -> None:
        self.npc_met = npc
        self.items = items or []
        self._tradable = tradable if tradable is not None else (items or [])
        self.selected_item_idx = idx

    def get_tradable_items(self) -> "list[_FakeItem]":
        return self._tradable


class _TalkableNPC:
    def __init__(self, has_dialog: bool, is_merchant: bool) -> None:
        self.has_dialog = has_dialog
        self.model = _FakeModel(is_merchant)


def test_who_counts_as_interactable() -> None:
    assert_eq(_PlayerBits(None).can_interact_with_npc(), False, "nobody nearby")
    assert_eq(
        _PlayerBits(_TalkableNPC(has_dialog=True, is_merchant=False)).can_interact_with_npc(),
        True, "a plain talker counts",
    )
    assert_eq(
        _PlayerBits(_TalkableNPC(has_dialog=False, is_merchant=True)).can_interact_with_npc(),
        True, "a dialog-less merchant counts",
    )
    assert_eq(
        _PlayerBits(_TalkableNPC(has_dialog=True, is_merchant=True)).can_interact_with_npc(),
        True, "and so does one who is both",
    )
    assert_eq(
        _PlayerBits(_TalkableNPC(has_dialog=False, is_merchant=False)).can_interact_with_npc(),
        False, "a passer-by who neither talks nor trades does not",
    )


def test_a_drawn_weapon_does_not_swing_at_someone_you_can_talk_to() -> None:
    """SPACE is `talk` + `open` + `attack` at once (settings.ACTIONS).

    The talk branch clears only `INPUTS["talk"]`, so without this guard the hero
    opened the shop and swung at the shopkeeper in the same frame.
    """
    source = inspect.getsource(Player.movement)
    attack_block = source[source.index('if INPUTS["attack"]:'):]
    guard = attack_block.index("can_interact_with_npc")
    swing = attack_block.index("self.is_attacking = True")
    assert_true(guard < swing, "the peaceful action is checked before the swing")
    assert_true(
        attack_block[:swing].count("elif") == 1,
        "the swing hangs off the guard as an elif, so movement below still runs",
    )


def test_an_empty_pack_still_gets_you_into_the_shop() -> None:
    """Nothing to sell is no reason to refuse - the player may have come to buy."""
    player = _PlayerBits(items=[], tradable=[], idx=3)
    player.normalise_trade_selection()
    assert_eq(player.selected_item_idx, 0, "the cursor is parked, not left dangling")


def test_the_cursor_lands_on_something_the_merchant_takes() -> None:
    sword, fish = _FakeItem("sword"), _FakeItem("fish")
    # merchant deals in consumables only; the hero currently holds the sword
    player = _PlayerBits(items=[sword, fish], tradable=[fish], idx=0)
    player.normalise_trade_selection()
    assert_eq(player.selected_item_idx, 0, "an untradable selection falls back to the first slot")

    player = _PlayerBits(items=[sword, fish], tradable=[fish], idx=1)
    player.normalise_trade_selection()
    assert_eq(player.selected_item_idx, 0, "a tradable one is re-indexed into the filtered list")


def test_a_stale_cursor_does_not_crash() -> None:
    """`selected_item_idx` can outlive the item it pointed at."""
    fish = _FakeItem("fish")
    player = _PlayerBits(items=[fish], tradable=[fish], idx=7)
    player.normalise_trade_selection()
    assert_eq(player.selected_item_idx, 0, "an out-of-range cursor is reset, not indexed")


def main() -> None:
    tests = [
        test_the_handoff_swaps_the_panels,
        test_is_talking_survives_the_handoff,
        test_the_next_conversation_starts_from_the_top,
        test_a_non_merchant_keeps_the_dialog,
        test_no_request_changes_nothing,
        test_the_handoff_reports_the_closed_dialog_to_the_quest_engine,
        test_the_drain_is_wired_into_update,
        test_who_counts_as_interactable,
        test_a_drawn_weapon_does_not_swing_at_someone_you_can_talk_to,
        test_an_empty_pack_still_gets_you_into_the_shop,
        test_the_cursor_lands_on_something_the_merchant_takes,
        test_a_stale_cursor_does_not_crash,
    ]
    for t in tests:
        t()
        print(f"  PASS  {t.__name__}")
    print(f"\nAll {len(tests)} dialog/trade handoff tests passed.")


if __name__ == "__main__":
    main()
