"""Efekty pisane wywołaniem: ``add_n_items(1,`` ``[[Łza syrenki]]`` ``)`` -> co gra ma zrobić.

Węzeł dialogu i nagroda questa robią tę samą rzecz - zmieniają stan gracza -
więc pisze się je tak samo, jak warunki: wywołaniem z liczbą i encjami
w argumentach, gdzie encja jest **wikilinkiem**. Dzięki temu jedno wyrażenie jest
naraz instrukcją dla silnika i krawędzią w grafie Obsidiana (widać, kto komu co
daje), a nazwy funkcji są nazwami metod :class:`dialog.result_sink.ResultSink`,
więc od notatki do kodu prowadzi jedno słowo::

    * [`add_n_items(1,`[[Eliksir anty-zaklęcia]]`)`] Weź tę miksturę…
    * [`remove_n_items(1,`[[Wąs gnoma]]`,`[[Łza syrenki]]`)`] Dawaj je tutaj.
    * [`shift_sentiment(-10)`]Jak śmiesz!

    **Nagroda**: `add_money(50)`

Backquote'y są formatowaniem Obsidiana i schodzą razem z wikilinkami w
:func:`dialog.vault_links.expand_links` - tutaj przychodzi już samo wywołanie
z kluczami w cudzysłowach (``add_n_items(1,"POTION_CURSE_NO_MORE")``).

Parsowanie jak w :mod:`dialog.conditions`: ``ast.parse(mode="eval")`` i własny
spacer po whiteliście, **nigdy** ``eval``. Moduł jest czystą logiką (stdlib), więc
działa i w imporcie, i pod pygbag.

**Zasięgi.** Ta sama gramatyka, dwa różne zestawy czasowników, bo silniki mają
różne możliwości:

- ``dialog`` - 7 kategorii :class:`dialog.entities.NodeVisitResultCategory`.
  Rozmowa ma bieżącą postać, więc ``shift_sentiment(n)`` wie, komu zmienia
  sympatię.
- ``quest`` - 7 kategorii :class:`quest.entities.QuestRewardCategory`. Nagroda
  daje, a nie zabiera (nie ma czegoś takiego jak ``remove_money`` w nagrodzie),
  za to umie podnieść statystyki na stałe. Quest nie ma bieżącej postaci, więc
  sympatię zmienia się adresowanym ``shift_sentiment_of(`` ``[[Barman]]`` ``,10)``.

Mapowania nazwa -> kategoria mieszkają w importerach, nie tutaj: kategorie
dialogu i questa to dwa różne enumy, a ``quest`` importuje ``dialog``, nigdy
odwrotnie.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from enum import StrEnum, auto


class EffectError(ValueError):
    """Efekt, którego nie da się odczytać. Woła o ``file:line`` u wołającego."""


class EffectScope(StrEnum):
    """Gdzie efekt stoi - to decyduje, które czasowniki są legalne."""

    dialog = auto()
    quest = auto()


# Kształt argumentów każdego czasownika:
#   amount        - jedna dodatnia liczba: add_money(50)
#   signed_amount - jedna liczba ze znakiem: shift_sentiment(-10)
#   count_items   - krotność i lista przedmiotów: add_n_items(2,"A","B")
#   npc_amount    - adresat i liczba ze znakiem: shift_sentiment_of("BARMAN",10)
_SIGNATURES: dict[str, str] = {
    "add_money": "amount",
    "remove_money": "amount",
    "add_n_items": "count_items",
    "remove_n_items": "count_items",
    "restore_health": "amount",
    "lose_health": "amount",
    "shift_sentiment": "signed_amount",
    "raise_max_health": "amount",
    "raise_damage": "amount",
    "raise_max_items": "amount",
    "shift_sentiment_of": "npc_amount",
}

# Czasowniki dozwolone w danym zasięgu. Nazwa spoza zasięgu daje inny błąd niż
# nazwa nieznana w ogóle - autor ma się dowiedzieć, że pomylił miejsce, a nie
# szukać literówki.
EFFECTS_BY_SCOPE: dict[EffectScope, tuple[str, ...]] = {
    EffectScope.dialog: (
        "add_money", "remove_money",
        "add_n_items", "remove_n_items",
        "restore_health", "lose_health",
        "shift_sentiment",
    ),
    EffectScope.quest: (
        "add_money",
        "add_n_items",
        "restore_health",
        "raise_max_health",
        "raise_damage",
        "raise_max_items",
        "shift_sentiment_of",
    ),
}


@dataclass(slots=True)
class Effect:
    """Odczytane wywołanie: co robić, ile i z czym.

    ``items`` jest już **rozwinięte o krotność**: ``add_n_items(3,"fish")`` to
    trzy razy ``"fish"``. Krotność nie jedzie dalej jako osobne pole, bo i sink
    (``add_items``/``remove_items``), i zapis w ``config.json`` operują listą
    kluczy - lista jest listą.
    """

    name: str
    value: int = 0
    items: list[str] = field(default_factory=list, repr=False)
    target: str | None = field(default=None, repr=False)


def parse_effect(expression: str, scope: EffectScope) -> Effect:
    """``'add_n_items(2,"fish")'`` -> :class:`Effect`, albo :class:`EffectError`.

    Wejście jest już po :func:`dialog.vault_links.expand_links`: bez backquote'ów,
    z kluczami encji w cudzysłowach.
    """
    expression = expression.strip()
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as error:
        raise EffectError(f"effect {expression!r} is not a call: {error.msg}") from error

    call = tree.body
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
        raise EffectError(
            f"effect {expression!r} must be a call like "
            f"`add_n_items(1,`[[ITEM]]`)` or `add_money(50)`"
        )
    if call.keywords:
        raise EffectError(f"effect {expression!r} takes positional arguments only")

    name = call.func.id
    signature = _SIGNATURES.get(name)
    if signature is None:
        raise EffectError(
            f"unknown effect {name!r}; expected one of "
            f"{', '.join(sorted(_SIGNATURES))}"
        )
    if name not in EFFECTS_BY_SCOPE[scope]:
        raise EffectError(
            f"effect {name!r} cannot be used in a {scope.value}; here the "
            f"choices are {', '.join(EFFECTS_BY_SCOPE[scope])}"
        )

    if signature in ("amount", "signed_amount"):
        return _parse_amount(name, call, expression, signed=signature == "signed_amount")
    if signature == "count_items":
        return _parse_count_items(name, call, expression)
    return _parse_npc_amount(name, call, expression)


def _parse_amount(
    name: str, call: ast.Call, expression: str, *, signed: bool
) -> Effect:
    if len(call.args) != 1:
        raise EffectError(
            f"effect {name!r} takes exactly one number, got {len(call.args)} arguments"
        )
    value = _number(call.args[0], name, expression)
    if signed:
        if value == 0:
            raise EffectError(f"effect {name!r} with 0 changes nothing")
    elif value <= 0:
        raise EffectError(
            f"effect {name!r} needs a positive number, got {value}; the verb "
            f"already says which way it goes"
        )
    return Effect(name=name, value=value)


def _parse_count_items(name: str, call: ast.Call, expression: str) -> Effect:
    if len(call.args) < 2:
        raise EffectError(
            f"effect {name!r} reads as {name}(<count>, <item>, …), e.g. "
            f"`{name}(1,`[[ITEM]]`)`"
        )
    count = _number(call.args[0], name, expression)
    if count <= 0:
        raise EffectError(f"effect {name!r} needs a positive count, got {count}")

    keys = [_entity_key(arg, name, expression) for arg in call.args[1:]]
    # Krotność dotyczy każdego przedmiotu z listy: `remove_n_items(1,A,B,C)` to
    # po jednej sztuce z każdego, a `remove_n_items(5,A)` to pięć sztuk A.
    items = [key for key in keys for _ in range(count)]
    return Effect(name=name, value=count, items=items)


def _parse_npc_amount(name: str, call: ast.Call, expression: str) -> Effect:
    if len(call.args) != 2:
        raise EffectError(
            f"effect {name!r} reads as {name}(<npc>, <amount>), e.g. "
            f"`{name}(`[[Barman Absyntnent]]`,10)`"
        )
    target = _entity_key(call.args[0], name, expression)
    value = _number(call.args[1], name, expression)
    if value == 0:
        raise EffectError(f"effect {name!r} with 0 changes nothing")
    return Effect(name=name, value=value, target=target)


def _number(node: ast.expr, name: str, expression: str) -> int:
    """Stała całkowita, ewentualnie z jednoznakowym minusem (``-10``)."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _number(node.operand, name, expression)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(
        node.value, bool
    ):
        return node.value
    raise EffectError(
        f"effect {name!r} expects a whole number, got {ast.unparse(node)} "
        f"in {expression!r}"
    )


def _entity_key(node: ast.expr, name: str, expression: str) -> str:
    """Klucz encji - to, w co :func:`expand_links` zamienia wikilink."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.strip():
        return node.value.strip()
    raise EffectError(
        f"effect {name!r} expects an entity wikilink (or a quoted key), got "
        f"{ast.unparse(node)} in {expression!r}"
    )


__all__ = [
    "EFFECTS_BY_SCOPE",
    "Effect",
    "EffectError",
    "EffectScope",
    "parse_effect",
]
