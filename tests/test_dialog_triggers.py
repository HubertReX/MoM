#!/usr/bin/env python3
"""Wyzwalacze dialogu z mapy - obszarowe i blokujące wyjście.

Obiekt na warstwie `interactions` wskazuje węzeł `-entry`, a warunek wejścia tego
węzła decyduje, czy scena się odegra. Dwa zastosowania jednego mechanizmu:
`obj_type="dialog"` odgrywa scenę i puszcza gracza dalej, własność `dialog` na
obiekcie `exit` blokuje przejście na inną mapę.

Co tu jest pilnowane:

- **wskaźnik `KLUCZ:WĘZEŁ` albo nic** - połowiczny zapis ma być odrzucony, a nie
  zinterpretowany po swojemu,
- **tylko węzeł `-entry`** - zwykły węzeł wolno odwiedzić wyłącznie krawędzią
  grafu, więc wyzwalacz w niego celujący jest błędem autora, nie wejściem
  tylnymi drzwiami,
- **scena raz na wejście w obszar** - kolizja trzyma się wiele klatek, a zejście
  z obszaru uzbraja go ponownie,
- **blokada wyjścia liczy warunek co klatkę, a dialog odgrywa raz** - rozmowa,
  która właśnie domknęła quest, przepuszcza gracza bez schodzenia z progu. To
  jest cała różnica między „bramką" a „murem".

Bez ekranu: systemy dostają atrapy, prawdziwej `Scene` nikt nie buduje.

Uruchamianie z katalogu projektu:
    .venv/bin/python tests/test_dialog_triggers.py
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame  # noqa: E402

from dialog.entities import DialogNode  # noqa: E402
from scene import dialog_triggers  # noqa: E402


def assert_eq(a: object, b: object, msg: str = "") -> None:
    assert a == b, f"{msg}\n  expected: {b!r}\n  actual:   {a!r}"


def assert_true(cond: bool, msg: str = "") -> None:
    assert cond, msg


# ---------------------------------------------------------------------------
# atrapy
# ---------------------------------------------------------------------------

class FakeNPC:
    """Tyle z `NPC`, ile czyta `resolve` + `NPCConditionContext`."""

    def __init__(self, config_key: str, nodes: dict[str, DialogNode]) -> None:
        self.config_key = config_key
        self.dialog_nodes = nodes
        self.dialog: DialogNode | None = None
        self.has_dialog = True
        self.selected_options_dict: dict[str, bool] = {}
        self.sentiment = 50


class FakePlayer:
    def __init__(self, scene: object) -> None:
        self.scene = scene
        self.items: list[object] = []
        self.feet = pygame.Rect(0, 0, 8, 8)


class FakeScene:
    def __init__(self, *npcs: FakeNPC) -> None:
        self.loaded_NPCs = {npc.config_key: npc for npc in npcs}
        self.loaded_maps: dict[str, dict] = {}
        self.pending_map_states: dict[str, object] = {}
        self.quest_state = None
        self.player = FakePlayer(self)
        self.dialog_triggers: list[object] = []
        self.dialog_triggers_inside: set[str] = set()
        self.ui = SimpleNamespace(is_modal_open=lambda: False)
        self.game = SimpleNamespace(log=lambda *a, **k: None)


def _node(key: str, *, is_entry: bool = True, condition: str = "True") -> DialogNode:
    return DialogNode(key, f"M_X_DN_{key}", is_entry=is_entry, entry_condition=condition)


def _scene_with(condition: str = "True", *, is_entry: bool = True) -> FakeScene:
    npc = FakeNPC("KOWAL", {"002": _node("002", is_entry=is_entry, condition=condition)})
    return FakeScene(npc)


class FakeTrigger:
    def __init__(self, name: str, dialog: str, rect: pygame.Rect) -> None:
        self.name = name
        self.dialog = dialog
        self.rect = rect


# ---------------------------------------------------------------------------
# wskaźnik KLUCZ:WĘZEŁ
# ---------------------------------------------------------------------------

def test_a_full_spec_splits_into_character_and_node() -> None:
    assert_eq(dialog_triggers.parse_spec("KOWAL:002"), ("KOWAL", "002"))
    assert_eq(dialog_triggers.parse_spec(" KOWAL : 002 "), ("KOWAL", "002"),
              "spacje wokół dwukropka to kwestia wpisywania w Tiled, nie znaczenia")


def test_a_half_written_spec_is_refused_rather_than_guessed() -> None:
    """Domyślanie się węzła zamieniłoby literówkę w cichą, inną scenę."""
    for spec in ("KOWAL", "KOWAL:", ":002", "", "   "):
        assert_eq(dialog_triggers.parse_spec(spec), None, f"{spec!r} nie jest wskaźnikiem")


# ---------------------------------------------------------------------------
# resolve / should_fire
# ---------------------------------------------------------------------------

def test_a_trigger_resolves_to_the_character_and_its_entry_node() -> None:
    scene = _scene_with()
    resolved = dialog_triggers.resolve(scene, "KOWAL:002")

    assert_true(resolved is not None, "postać i węzeł istnieją, więc muszą się znaleźć")
    npc, node = resolved                                  # type: ignore[misc]
    assert_eq(npc.config_key, "KOWAL")
    assert_eq(node.key, "002")


def test_a_node_without_the_entry_marker_is_not_a_trigger_target() -> None:
    """Do zwykłego węzła wchodzi się krawędzią grafu - wyzwalacz to nie furtka."""
    scene = _scene_with(is_entry=False)

    assert_eq(dialog_triggers.resolve(scene, "KOWAL:002"), None)
    assert_eq(dialog_triggers.should_fire(scene, "KOWAL:002"), False)


def test_an_unknown_character_fires_nothing() -> None:
    """Postać z nieodwiedzonej mapy nie ma obiektu - wyzwalacz milczy zamiast paść."""
    scene = _scene_with()

    assert_eq(dialog_triggers.resolve(scene, "ZIELARKA:002"), None)
    assert_eq(dialog_triggers.should_fire(scene, "ZIELARKA:002"), False)


def test_the_entry_condition_decides_whether_the_scene_plays() -> None:
    assert_eq(dialog_triggers.should_fire(_scene_with("True"), "KOWAL:002"), True)
    assert_eq(dialog_triggers.should_fire(_scene_with("sentiment > 90"), "KOWAL:002"), False)
    assert_eq(dialog_triggers.should_fire(_scene_with("sentiment >= 50"), "KOWAL:002"), True)


def test_the_entry_condition_sees_the_same_names_as_an_option_condition() -> None:
    """Jedna gramatyka, nie dwie - `visited()` u tej samej postaci musi działać."""
    scene = _scene_with('not visited("002")')
    assert_eq(dialog_triggers.should_fire(scene, "KOWAL:002"), True)

    scene.loaded_NPCs["KOWAL"].dialog_nodes["002"].visited = True
    assert_eq(dialog_triggers.should_fire(scene, "KOWAL:002"), False,
              "`not visited(...)` to sposób na scenę raz na zawsze, bez nowego stanu w save")


# ---------------------------------------------------------------------------
# wyzwalacz obszarowy
# ---------------------------------------------------------------------------

def _area_scene(condition: str = "True") -> tuple[FakeScene, list[str]]:
    scene = _scene_with(condition)
    scene.dialog_triggers = [FakeTrigger("SHRINE", "KOWAL:002", pygame.Rect(0, 0, 16, 16))]
    fired: list[str] = []
    dialog_triggers.fire_spec = lambda sc, spec: (fired.append(spec), True)[1]  # type: ignore[assignment]
    return scene, fired


def test_walking_into_an_area_plays_the_scene_once() -> None:
    """Kolizja trzyma się wiele klatek; scena ma się odegrać na wejściu, nie co klatkę."""
    scene, fired = _area_scene()
    scene.player.feet.topleft = (4, 4)

    dialog_triggers.update(scene)
    dialog_triggers.update(scene)
    dialog_triggers.update(scene)

    assert_eq(fired, ["KOWAL:002"], "trzy klatki na obszarze, jedna scena")


def test_leaving_the_area_re_arms_it() -> None:
    scene, fired = _area_scene()

    scene.player.feet.topleft = (4, 4)
    dialog_triggers.update(scene)
    scene.player.feet.topleft = (400, 400)
    dialog_triggers.update(scene)
    scene.player.feet.topleft = (4, 4)
    dialog_triggers.update(scene)

    assert_eq(fired, ["KOWAL:002", "KOWAL:002"], "zejście z obszaru uzbraja go ponownie")


def test_a_refused_condition_does_not_retry_every_frame() -> None:
    """Odrzucona scena nie ma się dopytywać - obszar jest „zaliczony" tak samo."""
    scene, fired = _area_scene("sentiment > 90")
    scene.player.feet.topleft = (4, 4)

    dialog_triggers.update(scene)
    dialog_triggers.update(scene)

    assert_eq(fired, [], "warunek fałszywy, więc nic się nie odegrało")
    assert_eq(scene.dialog_triggers_inside, {"SHRINE"},
              "obszar jest odnotowany jako zajęty, żeby nie próbować co klatkę")


def test_an_open_modal_never_stacks_a_second_dialog() -> None:
    scene, fired = _area_scene()
    scene.ui = SimpleNamespace(is_modal_open=lambda: True)
    scene.player.feet.topleft = (4, 4)

    dialog_triggers.update(scene)

    assert_eq(fired, [], "rozmowa w toku - drugi panel nie ma się na nią nałożyć")


# ---------------------------------------------------------------------------
# bramka na wyjściu
# ---------------------------------------------------------------------------

class FakeExit:
    def __init__(self, name: str, dialog: str = "", requires_item: str = "") -> None:
        self.name = name
        self.rect = pygame.Rect(0, 0, 16, 16)
        self.to_map = "ROADSIDE"
        self.dialog = dialog
        self.requires_item = requires_item
        self.consumes_key = False


def _exit_scene(condition: str, exit_obj: FakeExit) -> tuple[object, list[str]]:
    from characters import Player

    scene = _scene_with(condition)
    scene.exit_sprites = [exit_obj]                       # type: ignore[attr-defined]
    scene.transition = SimpleNamespace(exiting=False)     # type: ignore[attr-defined]
    scene.new_scene = None                                # type: ignore[attr-defined]

    player = Player.__new__(Player)
    player.scene = scene                                  # type: ignore[assignment]
    player.feet = pygame.Rect(0, 0, 8, 8)
    player._locked_door_told = ""
    player._exit_dialog_told = ""
    scene.player = player                                 # type: ignore[assignment]

    fired: list[str] = []
    dialog_triggers.fire_spec = lambda sc, spec: (fired.append(spec), True)[1]  # type: ignore[assignment]
    return player, fired


def test_a_true_gate_blocks_the_transition_and_plays_the_dialog() -> None:
    door = FakeExit("GATE_WEST", dialog="KOWAL:002")
    player, fired = _exit_scene("True", door)

    player.check_scene_exit()

    assert_eq(fired, ["KOWAL:002"])
    assert_eq(player.scene.transition.exiting, False, "przejście ma się nie zacząć")
    assert_eq(player.scene.new_scene, None)


def test_the_gate_speaks_once_per_approach() -> None:
    door = FakeExit("GATE_WEST", dialog="KOWAL:002")
    player, fired = _exit_scene("True", door)

    player.check_scene_exit()
    player.check_scene_exit()
    player.check_scene_exit()

    assert_eq(fired, ["KOWAL:002"], "stanie na progu nie powtarza rozmowy")


def test_a_gate_that_stopped_being_true_lets_the_player_through_on_the_spot() -> None:
    """Sedno różnicy między bramką a murem: warunek liczy się DALEJ co klatkę.

    Rozmowa, która właśnie domknęła quest, ma przepuścić gracza bez schodzenia
    z progu i wracania - inaczej gracz stoi w drzwiach i nie rozumie, dlaczego
    nadal nie może wyjść.
    """
    door = FakeExit("GATE_WEST", dialog="KOWAL:002")
    player, fired = _exit_scene("sentiment < 90", door)

    player.check_scene_exit()
    assert_eq(player.scene.transition.exiting, False, "najpierw bramka trzyma")

    # to, co zrobiłby efekt węzła: świat się zmienił, warunek przestał być prawdziwy
    player.scene.loaded_NPCs["KOWAL"].sentiment = 95
    player.check_scene_exit()

    assert_eq(len(fired), 1, "druga rozmowa się nie odgrywa")
    assert_eq(player.scene.transition.exiting, True, "wyjście puszcza od razu")
    assert_eq(player.scene.new_scene, door)


def test_a_false_gate_is_the_old_behaviour() -> None:
    door = FakeExit("GATE_WEST", dialog="KOWAL:002")
    player, fired = _exit_scene("sentiment > 90", door)

    player.check_scene_exit()

    assert_eq(fired, [], "warunek fałszywy - żadnej rozmowy")
    assert_eq(player.scene.transition.exiting, True, "i zwykłe przejście")


def test_an_exit_without_a_gate_is_untouched() -> None:
    """57 dzisiejszych wyjść nie ma własności `dialog` i ma działać jak dotąd."""
    door = FakeExit("GATE_WEST")
    player, fired = _exit_scene("True", door)

    player.check_scene_exit()

    assert_eq(fired, [])
    assert_eq(player.scene.transition.exiting, True)


def test_the_frame_the_gate_fires_keeps_the_speaker() -> None:
    """`collisions.resolve` nie może wyzerować `npc_met` w klatce startu rozmowy.

    Bramka odpala się w `group.update`, czyli PRZED `collisions.resolve` tej samej
    klatki, a rozmówcą bywa postać spoza zasięgu (bramka przy wyjściu, głos zza
    kadru). Wyzerowanie `npc_met` zabiera `GameUI` jedyny uchwyt do zdjęcia
    `is_talking` przy zamknięciu panelu - i rozmówca zostaje „zajęty" na zawsze.
    Tak właśnie objawił się ten błąd: panel się otwierał, a `dialog.npc` w zrzucie
    stanu było `None`.
    """
    from scene import collisions

    npc = FakeNPC("KOWAL", {"002": _node("002")})
    scene = SimpleNamespace(
        walls=[], chests=[], destructibles=[], NPCs=[],
        awake_NPCs=lambda: [],
    )
    player = SimpleNamespace(
        feet=pygame.Rect(0, 0, 8, 8), pos=pygame.Vector2(0, 0),
        chest_in_range=None, npc_met=npc, is_talking=True,
        is_flying=False, is_stunned=False,
        selected_weapon=None, is_attacking=False,
    )
    scene.player = player                                  # type: ignore[attr-defined]

    collisions.resolve(scene)                              # type: ignore[arg-type]

    assert_true(player.npc_met is npc,
                "rozmówca przeżywa klatkę, w której rozmowa właśnie ruszyła")


def test_a_door_collider_defaults_to_no_gate() -> None:
    from objects import Collider

    pygame.display.set_mode((64, 64))
    door = Collider(pygame.sprite.Group(), (0, 0), (16, 16), "Door", "MAP", "entry")

    assert_eq(door.dialog, "", "brak własności `dialog` = drzwi bez bramki")


if __name__ == "__main__":
    pygame.init()
    pygame.display.set_mode((64, 64))
    tests = [
        ("pełny wskaźnik się rozbija", test_a_full_spec_splits_into_character_and_node),
        ("połowiczny wskaźnik odrzucony", test_a_half_written_spec_is_refused_rather_than_guessed),
        ("wyzwalacz trafia w postać i węzeł", test_a_trigger_resolves_to_the_character_and_its_entry_node),
        ("węzeł bez -entry to nie cel", test_a_node_without_the_entry_marker_is_not_a_trigger_target),
        ("nieznana postać milczy", test_an_unknown_character_fires_nothing),
        ("warunek decyduje o scenie", test_the_entry_condition_decides_whether_the_scene_plays),
        ("warunek zna te same nazwy", test_the_entry_condition_sees_the_same_names_as_an_option_condition),
        ("scena raz na wejście", test_walking_into_an_area_plays_the_scene_once),
        ("zejście uzbraja obszar", test_leaving_the_area_re_arms_it),
        ("odrzucony warunek nie pyta co klatkę", test_a_refused_condition_does_not_retry_every_frame),
        ("otwarty modal nie dokłada panelu", test_an_open_modal_never_stacks_a_second_dialog),
        ("bramka blokuje i gada", test_a_true_gate_blocks_the_transition_and_plays_the_dialog),
        ("bramka gada raz na podejście", test_the_gate_speaks_once_per_approach),
        ("spełniony warunek puszcza od razu", test_a_gate_that_stopped_being_true_lets_the_player_through_on_the_spot),
        ("fałszywa bramka = stara logika", test_a_false_gate_is_the_old_behaviour),
        ("wyjście bez bramki bez zmian", test_an_exit_without_a_gate_is_untouched),
        ("rozmówca przeżywa klatkę startu", test_the_frame_the_gate_fires_keeps_the_speaker),
        ("Collider domyślnie bez bramki", test_a_door_collider_defaults_to_no_gate),
    ]
    failures = 0
    for name, func in tests:
        try:
            func()
            print(f"  ✓ {name}")
        except AssertionError as error:
            failures += 1
            print(f"  ✗ {name}\n{error}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
