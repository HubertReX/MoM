# A03 - layout self-checks w UI (overflow = twardy błąd)

Priorytet: **P0** (Faza 1). Rozmiar: M. Zależności: brak; synergia z A02 (raport w ui_state).

## Kontekst i problem

Najczęstsza klasa błędów słabszych agentów AI przy pracy nad UI: "panel za mały na tekst",
"tekst najeżdża na ramkę panelu". Design system (`project/ui/AGENTS.md`) opisuje zasady
prozą, ale nikt ich nie egzekwuje maszynowo - błąd widać dopiero na screenshocie, a
ss-review (LLM-vision) bywa niedeterministyczny.

Widżety UI ZNAJĄ swoje wymiary: `RichText` wie, ile linii wyrenderował i w jakim rect,
panel zna swój rect i rect treści. Overflow da się wykryć w kodzie w 100% przypadków.

## Cel

Mechanizm raportowania naruszeń layoutu: widżet wykrywający treść poza swoim obszarem
loguje naruszenie; w trybie testowym naruszenia trafiają do pliku, a runner je asertuje.

## Pliki do zmiany

- `project/ui/layout.py` (istnieje, 1.5K) - dopisz tu moduł raportowania naruszeń
- `project/ui/widgets/rich_text.py` - detekcja overflow tekstu
- `project/ui/widgets/label.py` - detekcja obcięcia tekstu
- `project/ui/panels/dialog.py`, `quest.py`, `help.py`, `trade.py` - wywołania kontroli
  granic treści względem panelu (tam gdzie panel rysuje własne elementy poza widżetami)
- `tests/automate_display_test.py` - asercja `no_layout_violations`
- `project/ui/AGENTS.md` - opis mechanizmu

## Krok 1: rejestr naruszeń (`ui/layout.py`)

```python
# --- layout violation reporting -------------------------------------------
_violations: list[str] = []
_seen: set[str] = set()

def report_violation(widget: str, kind: str, detail: str) -> None:
    """Zgłoś naruszenie layoutu. Deduplikacja po (widget, kind) - jedno
    naruszenie na widżet na sesję, nie na klatkę (inaczej zaleje log)."""
    key = f"{widget}:{kind}"
    if key in _seen:
        return
    _seen.add(key)
    msg = f"[layout] {kind} in {widget}: {detail}"
    _violations.append(msg)
    print(msg)

def violations() -> list[str]:
    return list(_violations)

def reset_violations() -> None:
    _violations.clear()
    _seen.clear()
```

## Krok 2: detekcja w widżetach

`RichText` (rendering z zawijaniem i scrollem): po ułożeniu linii sprawdź dwa warunki -

- szerokość którejkolwiek wyrenderowanej linii > szerokość dostępnego obszaru
  (`kind="h-overflow"`)
- łączna wysokość treści > wysokość rect **przy wyłączonym scrollu** / braku ScrollView
  (`kind="v-overflow"`); widżet z aktywnym scrollem NIE zgłasza v-overflow (scroll to
  legalna odpowiedź na nadmiar treści)

`Label`: jeśli wyrenderowany tekst jest szerszy niż rect widżetu (`kind="clipped"`).

Jako `widget` przekazuj czytelny identyfikator: `f"{type(self).__name__}({self.name})"`
albo nazwę panelu-właściciela, jeśli jest dostępna. Detekcję rób w miejscu, gdzie znasz
finalne wymiary (po layoutcie, przed/w trakcie pierwszego blitu), nie co klatkę -
naturalne miejsce to ścieżka "dirty" (przebudowa cache powierzchni).

## Krok 3: kontrola granic paneli

W panelach, które rysują elementy bezpośrednio (poza RichText/Label), dodaj tanią kontrolę:
po złożeniu layoutu porównaj rect każdej sekcji treści z rectem wewnętrznym panelu
(rect pomniejszony o border nine-patch). Zgłoś `kind="outside-panel"`. Zacznij od
`dialog.py` (opcje + tekst NPC) i `quest.py` (kolumna szczegółów) - to tam historycznie
były błędy. Nie przebudowuj layoutu paneli - tylko zgłaszaj.

## Krok 4: integracja z testami

- W `agent_ctrl` (jeśli A02 zrobione): dołącz `"layout_violations": layout.violations()`
  do zrzutu `debug_ui_state`.
- W runnerze: nowy typ asercji `{"type": "no_layout_violations"}` - FAIL, gdy lista
  niepusta; komunikat wypisuje wszystkie naruszenia.
- Dodaj asercję do scenariuszy otwierających panele (dialog, questy, pomoc).

## Kryteria akceptacji

1. Test syntetyczny: w `tests/test_layout_checks.py` (nowy, wzorzec: inne pliki testów -
   samodzielny skrypt z listą `tests = [...]`) zbuduj `RichText` z za długim tekstem w za
   małym rect bez scrolla - `violations()` zawiera `h-overflow` lub `v-overflow`; po
   `reset_violations()` lista jest pusta; ten sam tekst w rect z ScrollView = zero naruszeń.
2. Scenariusz "Hammer Dialog Flow" z asercją `no_layout_violations` przechodzi
   (na obecnym, poprawnym UI).
3. Ręczna prowokacja: tymczasowo zmniejsz szerokość panelu dialogu o połowę
   (lokalnie, bez commita) - scenariusz z asercją pada i wypisuje naruszenie.
4. `just test-unit` przechodzi w całości; gra uruchamia się i wygląda bez zmian
   (mechanizm tylko raportuje, niczego nie rysuje inaczej).
5. Brak spamu: jedno naruszenie = jedna linia logu na sesję (deduplikacja działa).

## Pułapki

- NIE zmieniaj zachowania renderowania - żadnych clampów, przycinania ani "naprawiania"
  layoutu. Ten mechanizm tylko mierzy i raportuje. Naprawy = osobne zadania.
- Emoji/ikony inline w RichText mają własną szerokość po skalowaniu integer - szerokość
  linii licz z faktycznie zblitowanych elementów, nie z samego tekstu.
- Tekst w przestrzeni świata (imię NPC nad głową, `objects.py`) NIE podlega tym regułom
  (inna ścieżka renderu, skalowana kamerą) - nie dotykaj.
- Deduplikacja po `(widget, kind)` jest kluczowa: bez niej log rośnie co klatkę.
- Uważaj na fałszywe alarmy przy zmianie rozdzielczości: po `on_resize` panele przeliczają
  geometrię - wołaj `reset_violations()` przy zmianie rozdzielczości i przy `ui.reset()`.

## Po zakończeniu

- opisz mechanizm w `project/ui/AGENTS.md` (sekcja "Layout self-checks": jak zgłaszać,
  jak czytać, zasada "scroll = legalny nadmiar")
- odhacz A03 w `doc/audyt/audyt.md`
- commit: `A03: layout self-checks - deterministyczna detekcja overflow w UI`
