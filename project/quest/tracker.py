"""Który quest gra podpowiada graczowi na HUD-zie (H01/D7).

Dziennik pokazuje wszystko; wskaźnik ma odpowiadać na jedno pytanie - **„co
teraz?"**. To dwie różne rzeczy i dlatego wskaźnik nie jest skrótem do dziennika,
tylko osobnym wyborem.

Trzy pytania, które łatwo pomylić, i ich odpowiedzi:

- **kto wybiera** - domyślnie automat; gracz może przypiąć swój quest klawiszem
  ``T`` w dzienniku (``pinned``). Przypięcia automat nie rusza, dopóki ten quest
  żyje.
- **co po ukończeniu** - kaskada niżej, i tak samo dla przypiętego, jak dla
  wybranego automatem. Po kaskadzie pin **znika**: nowy wybór jest wyborem
  automatu, a przyklejony pin do questa, którego gracz nigdy nie wskazał, nie
  dałby się cofnąć inaczej niż przez dziennik.
- **co gdy nie ma czego śledzić** - wskaźnik znika. Bez pustej ramki.

Moduł jest **czysty**: same funkcje na ``defs``/``state``, zero pygame, zero
sceny. Dzięki temu każdy z pięciu kroków kaskady da się przetestować osobno,
bez ekranu.

**Automat odrzuca parasole.** Parasol mówi „przełam klątwę" - to tytuł rozdziału,
nie instrukcja. Gracz potrzebuje „idź pogadać z Zielarką". Ręczne przypięcie
parasola zostaje możliwe, bo to świadoma decyzja, a nie domyślna.

**Kolejność w ``defs`` to kolejność sekcji w pliku questa w Obsidianie**, czyli
kolejność, w jakiej autor to napisał. Jest deterministyczna i sterowalna treścią -
i to jest najważniejszy skutek uboczny tego pliku: *kolejność sekcji w pliku
questa staje się kolejnością podpowiadaną graczowi*.
"""
from __future__ import annotations

from quest.engine import is_unlocked
from quest.entities import QuestDef, QuestState
from quest.graph import children_of


def is_umbrella(defs: dict[str, QuestDef], key: str) -> bool:
    """Czy ``key`` jest parasolem (ma podquesty), a więc tytułem, nie instrukcją."""
    return bool(children_of(defs, key))


def is_trackable(defs: dict[str, QuestDef], state: QuestState, key: str) -> bool:
    """Czy automat ma prawo wskazać ten quest: odblokowany, nieukończony, nie parasol."""
    quest = defs.get(key)
    if quest is None or state.is_done(key):
        return False
    return not is_umbrella(defs, key) and is_unlocked(defs, state, key)


def open_steps(defs: dict[str, QuestDef], state: QuestState) -> list[str]:
    """Wszystkie kroki, które automat może dziś wskazać - w kolejności definicji."""
    return [key for key in defs if is_trackable(defs, state, key)]


def auto_pick(defs: dict[str, QuestDef], state: QuestState) -> str | None:
    """Domyślny wybór automatu: pierwszy otwarty krok w kolejności definicji."""
    steps = open_steps(defs, state)
    return steps[0] if steps else None


def is_still_valid(defs: dict[str, QuestDef], state: QuestState, key: str | None) -> bool:
    """Czy śledzony quest nadal ma sens.

    Osobno od :func:`is_trackable`, bo **przypięty parasol jest legalny**: gracz,
    który świadomie wybrał nagłówek wątku, wie, czego chce - jawny wybór bije
    heurystykę. Nielegalny jest tylko quest nieznany (przemianowany albo
    skasowany między zapisem a wczytaniem), ukończony albo zablokowany.
    """
    if not key:
        return False
    quest = defs.get(key)
    if quest is None or state.is_done(key):
        return False
    return is_unlocked(defs, state, key)


def cascade(
    defs: dict[str, QuestDef],
    state: QuestState,
    closed_key: str,
    newly_unlocked: list[str],
) -> str | None:
    """Na co przeskakuje wskaźnik po zamknięciu śledzonego questa.

    Pięć kroków, pierwszy trafiony wygrywa - uporządkowane od „najbliżej tego, co
    gracz właśnie robił" do „cokolwiek sensownego":

    1. kroki z ``newly_unlocked`` tego samego zdarzenia (bez parasoli),
    2. nieukończone rodzeństwo, czyli pozostałe kroki tego samego parasola,
    3. gdy parasol też się właśnie domknął: nieukończone kroki parasola wyżej,
    4. globalnie: ostatni w kolejności definicji otwarty krok,
    5. brak kandydata -> ``None``, czyli wskaźnik znika.

    Krok 1 to wprost życzenie autora: quest, który coś odblokował, prowadzi
    gracza do tego, co odblokował.
    """
    # 1. co ten krok właśnie otworzył
    for key in newly_unlocked:
        if is_trackable(defs, state, key):
            return key

    closed = defs.get(closed_key)
    parent = closed.parent if closed is not None else None

    # 2. rodzeństwo - reszta tego samego wątku
    if parent is not None:
        for key in children_of(defs, parent):
            if is_trackable(defs, state, key):
                return key

        # 3. parasol też się domknął -> wątek piętro wyżej
        if state.is_done(parent):
            grandparent = defs[parent].parent if parent in defs else None
            if grandparent is not None:
                for key in children_of(defs, grandparent):
                    if is_trackable(defs, state, key):
                        return key

    # 4. cokolwiek sensownego. Dokument mówi „najpóźniej odblokowany", ale stan
    #    questów NIE NIESIE czasu odblokowania (`QuestState` to `{done: bool}`,
    #    decyzja D13) i dokładanie znacznika czasu tylko dla tego fallbacku byłoby
    #    nowym polem w zapisie. Ostatni w kolejności definicji to najbliższy
    #    deterministyczny odpowiednik: dalej w pliku = dalej w opowieści.
    steps = open_steps(defs, state)
    return steps[-1] if steps else None


def next_tracked(
    defs: dict[str, QuestDef],
    state: QuestState,
    current: str | None,
    pinned: bool,
    newly_done: list[str],
    newly_unlocked: list[str],
) -> tuple[str | None, bool]:
    """Nowe ``(tracked_quest_key, tracked_quest_pinned)`` po zdarzeniu questowym.

    Jedno miejsce, w którym spotykają się wszystkie trzy reguły z D7, więc nie da
    się ich przypadkiem rozjechać:

    - śledzony quest właśnie się zamknął -> kaskada, i pin **zawsze** znika,
    - śledzony quest przestał być ważny inaczej (przemianowany, zablokowany) ->
      automat od zera, bez pinu,
    - pin żyje -> nie ruszamy niczego; to jest właśnie po to, żeby automat
      nie nadpisywał świadomego wyboru gracza,
    - brak śledzonego -> automat wybiera.
    """
    if current and current in newly_done:
        return cascade(defs, state, current, newly_unlocked), False
    if not is_still_valid(defs, state, current):
        return auto_pick(defs, state), False
    if pinned:
        return current, True
    # automat może przemyśleć swój własny wybór, ale tylko jeśli ten przestał być
    # sensowny - a `is_still_valid` właśnie powiedziało, że jest
    return current, False


def toggle_pin(
    defs: dict[str, QuestDef],
    state: QuestState,
    current: str | None,
    key: str | None,
    pinned: bool = False,
) -> tuple[str | None, bool, str]:
    """Obsługa klawisza ``T`` na zaznaczonym queście.

    Zwraca ``(nowy klucz, przypięty, klucz komunikatu)``; pusty komunikat = bez
    toastu. Jeden klawisz robi obie rzeczy (przypnij/odepnij), bo drugi skrót na
    odpięcie byłby skrótem, którego nikt nigdy nie użyje.

    **Odpina tylko to, co gracz przypiął.** Dokument opisywał ten wiersz jako
    „aktualnie śledzony -> odpięcie", zakładając milcząco, że śledzony znaczy
    przypięty. Ale wskaźnik jest ustawiony także wtedy, gdy wybrał go automat -
    i wtedy „odpięcie" byłoby operacją, która nic nie zmienia (`auto_pick` odda
    ten sam quest), a gracz dostałby komunikat „wracam do automatu", choć nigdy
    z niego nie wyszedł. Co gorsza, questa wybranego przez automat nie dałoby się
    przypiąć NIGDY. Stąd rozróżnienie na stan: przypięty -> odpinamy,
    śledzony automatycznie -> przypinamy.

    Odmowa **nie jest ciszą**: quest ukończony albo zablokowany dostaje krótki
    komunikat, bo bez niego gracz naciska klawisz i nie wie, czy gra go nie
    usłyszała, czy nie chce.
    """
    if not key or key not in defs:
        return current, False, "quest.track_refused"
    if state.is_done(key):
        return current, False, "quest.track_refused_done"
    if not is_unlocked(defs, state, key):
        return current, False, "quest.track_refused_locked"
    if key == current and pinned:
        # odpięcie: wskaźnik wraca do trybu automatycznego
        return auto_pick(defs, state), False, "quest.track_off"
    return key, True, "quest.track_on"


__all__ = [
    "auto_pick",
    "cascade",
    "is_still_valid",
    "is_trackable",
    "is_umbrella",
    "next_tracked",
    "open_steps",
    "toggle_pin",
]
