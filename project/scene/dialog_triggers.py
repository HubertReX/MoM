"""Wyzwalacze dialogu z mapy: obszarowe i blokujące wyjście.

Moduł systemu wg B01 (D1): bezstanowe funkcje operujące na przekazanej scenie.

Obiekt na warstwie ``interactions`` w Tiled wskazuje **węzeł dialogowy** zapisem
``KLUCZ_POSTACI:WĘZEŁ`` (np. ``HAMMER_HOAXHEART:002``). Węzeł musi być oznaczony
w notatce sufiksem ``-entry`` i to **on** niesie warunek wejścia. Podział ról jest
celowy: obiekt na mapie mówi GDZIE scena się dzieje, notatka postaci mówi KIEDY -
dzięki temu warunek jest wikilinkiem w grafie Obsidiana i pilnuje go ta sama
gramatyka, co warunków opcji.

Dwa zastosowania, jeden mechanizm:

- ``obj_type="dialog"`` - obszar odgrywający scenę. Nic nie blokuje; odpala się
  przy WEJŚCIU w obszar i uzbraja ponownie po zejściu z niego. „Raz na zawsze"
  pisze autor warunkiem ``not visited(...)``, więc żaden nowy stan nie wchodzi
  do save'a.
- własność ``dialog`` na obiekcie ``exit`` - bramka fabularna. Dopóki warunek
  wejścia jest prawdziwy, dialog odgrywa się ZAMIAST przejścia na inną mapę
  (patrz ``Player.check_scene_exit``).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from dialog.conditions import check_condition
from dialog.context_adapter import NPCConditionContext, find_npc
from settings import MOM_DEBUG_TALK, get_msg, vec

if TYPE_CHECKING:
    from characters import NPC
    from dialog.entities import DialogNode
    from scene.scene import Scene


def parse_spec(spec: str) -> tuple[str, str] | None:
    """``"HAMMER_HOAXHEART:002"`` -> ``("HAMMER_HOAXHEART", "002")``.

    ``None`` dla zapisu, który nie ma dokładnie jednego dwukropka albo ma pustą
    połówkę. Walidator odrzuca takie mapy przy buildzie, więc w grze to już tylko
    siatka bezpieczeństwa.
    """
    key, sep, node = spec.partition(":")
    if not sep:
        return None
    key, node = key.strip(), node.strip()
    if not key or not node:
        return None
    return key, node


def resolve(scene: "Scene", spec: str) -> "tuple[NPC, DialogNode] | None":
    """Postać i jej węzeł ``-entry`` spod ``spec``, albo ``None``.

    Postać NIE musi stać na tej mapie - wyzwalacz wolno wycelować w kogoś, kto
    odzywa się zza kadru. Szukamy więc tak samo szeroko, jak ``visited()`` przy
    pytaniu o cudzą rozmowę (``dialog.context_adapter.find_npc``).

    Postać, której mapa nie była jeszcze ani razu wczytana, nie ma obiektu, więc
    nie ma też grafu dialogu - wyzwalacz cicho nie odpala. ``just validate-world``
    zgłasza ten przypadek jako ostrzeżenie przy buildzie.
    """
    parsed = parse_spec(spec)
    if parsed is None:
        return None
    npc_key, node_key = parsed

    npc = find_npc(scene, npc_key)
    if npc is None or getattr(npc, "dialog_nodes", None) is None:
        if MOM_DEBUG_TALK:
            scene.game.log(f"[DEBUG trigger] {spec!r}: nie ma postaci {npc_key!r}")
        return None

    node = npc.dialog_nodes.get(node_key) if npc.dialog_nodes else None
    if node is None or not node.is_entry:
        if MOM_DEBUG_TALK:
            scene.game.log(
                f"[DEBUG trigger] {spec!r}: węzeł {node_key!r} nie istnieje "
                f"albo nie jest oznaczony '-entry'")
        return None
    return npc, node


def should_fire(scene: "Scene", spec: str) -> bool:
    """Czy warunek wejścia węzła spod ``spec`` jest teraz prawdziwy?

    Ta sama funkcja, która filtruje opcje w panelu dialogu, i ten sam kontekst -
    warunek wejścia zna więc dokładnie te nazwy, co warunek opcji, łącznie
    z ``sentiment`` i ``selected()`` tej postaci.
    """
    resolved = resolve(scene, spec)
    if resolved is None:
        return False
    npc, node = resolved
    ctx = NPCConditionContext(npc, scene.player)
    try:
        return check_condition(node.entry_condition, ctx)
    except Exception:
        # warunek jest walidowany przy imporcie ORAZ przy budowie grafu, więc tu
        # może zostać już tylko awaria kontekstu; wtedy wyzwalacz milczy zamiast
        # wywalić klatkę
        return False


def fire(scene: "Scene", npc: "NPC", node: "DialogNode | None" = None) -> bool:
    """Otwórz panel dialogu z ``npc``, opcjonalnie ustawiając kursor na ``node``.

    Jeden kształt otwierania rozmowy spoza ścieżki SPACE - używa go i wyzwalacz
    z mapy, i deterministyczne ``talk_to_char`` agenta testowego.

    ``scene.player.npc_met`` MUSI zostać ustawione: ``GameUI`` czyta je przy
    zamykaniu panelu, żeby zdjąć ``is_talking`` z obu stron. Bez tego rozmówca
    zostaje „zajęty" na zawsze.
    """
    from ui.panels.dialog import DialogPanel

    if not getattr(npc, "has_dialog", False):
        return False
    if node is not None:
        npc.dialog = node
    if npc.dialog is None:
        return False

    # zamroź rozmówcę tam, gdzie stoi, żeby nie odszedł w trakcie; gracza NIE
    # ruszamy (wskoczenie na stertę przedmiotów wywołuje lawinę podnoszeń)
    npc.target = vec(0, 0)
    npc.waypoints = ()
    npc.waypoints_cnt = 0
    scene.player.npc_met = npc
    npc.npc_met = scene.player
    text = get_msg(scene.game.conf.messages, npc.dialog.text)
    scene.ui.open(DialogPanel, npc=npc, text=text)
    scene.player.is_talking = True
    npc.is_talking = True
    return True


def fire_spec(scene: "Scene", spec: str) -> bool:
    """``resolve`` + ``fire`` - wygodny skrót dla wołających z mapy."""
    resolved = resolve(scene, spec)
    if resolved is None:
        return False
    npc, node = resolved
    return fire(scene, npc, node)


def update(scene: "Scene") -> None:
    """Obszarowe wyzwalacze tej klatki (``obj_type="dialog"``).

    Wołane jako OSTATNIA linia ``Scene.update``: panel otwarty na końcu klatki
    zamraża świat dopiero w następnej, gdzie ``Scene.update`` i tak wychodzi
    wcześniej i czyści ``INPUTS`` - dzięki temu żaden klawisz nie wycieka do
    świeżo otwartej rozmowy.
    """
    if not scene.dialog_triggers:
        scene.dialog_triggers_inside.clear()
        return
    if scene.ui.is_modal_open():
        return

    feet = scene.player.feet
    inside = {t.name for t in scene.dialog_triggers if feet.colliderect(t.rect)}
    entered = inside - scene.dialog_triggers_inside
    # zbiór aktualizujemy ZAWSZE, także gdy warunek odrzucił scenę: inaczej
    # wyzwalacz próbowałby się odpalić co klatkę, dopóki gracz z niego nie zejdzie
    scene.dialog_triggers_inside = inside

    if not entered:
        return
    for trigger in scene.dialog_triggers:
        if trigger.name not in entered or not trigger.dialog:
            continue
        if should_fire(scene, trigger.dialog) and fire_spec(scene, trigger.dialog):
            # jeden panel na klatkę - nakładające się obszary czekają na swoją kolej
            return
