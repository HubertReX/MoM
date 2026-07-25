# F03 - mypy do zera: usunięcie stałego szumu 23 błędów

Priorytet: **P1** (Faza 1). Rozmiar: S. Zależności: brak.
**Musi być zrobione PRZED B01** (bramka "mypy bez nowych błędów" w refactorze wymaga
czystej bazy - inaczej "nowe vs stare" jest nierozstrzygalne).

## Kontekst i problem

`just mypy` zgłasza obecnie **23 błędy w 7 plikach** (stan 2026-07-25). Efekt uboczny
zaobserwowany przez autora: kolejne sesje agentów AI przekopują się przez tę listę
i kończą stwierdzeniem "ale to już było wcześniej" - marnowany czas i zamulony sygnał.
Nowy, realny błąd typów ginie w starym szumie.

Przykłady z bieżącego przebiegu (pełną listę daje `just mypy`):

- `project/agent_ctrl.py:525` - assignment `str` do zmiennej typu `Path`
- `project/ui/game_ui.py:80` - brak anotacji argumentów (`no-untyped-def`)
- `project/scene.py:1079` - `"object" has no attribute "__iter__"`
- `project/ui/panels/main_menu.py:75` - `object` zamiast `Callable[[], object] | None`

## Cel

`just mypy` = **0 błędów**. Od tej pory każdy nowy błąd to sygnał, nie szum.

## Zasady naprawy (w tej kolejności preferencji)

1. **Popraw typ naprawdę** - właściwa anotacja, poprawka logiki typu (np. `Path(...)`
   zamiast str), zawężenie `object` do faktycznego typu. To domyślna ścieżka.
2. **`cast()`** - gdy typ jest znany, ale mypy nie umie go wywieść (wzorzec już używany
   w kodzie, np. `cast(TiledTileLayer, ...)` w scene.py).
3. **`# type: ignore[<kod-błędu>]` z komentarzem dlaczego** - tylko gdy 1-2 wymagałyby
   refactoru poza zakresem zadania (np. dynamiczne atrybuty pytmx). ZAWSZE z konkretnym
   kodem błędu w nawiasie, nigdy gołe `# type: ignore`.
4. **Nie zmieniaj konfiguracji mypy** w `pyproject.toml` (żadnego wyłączania reguł ani
   dodawania plików do exclude) - to ukrywanie, nie naprawa. Wyjątek: jeśli znajdziesz
   błąd w bibliotece zewnętrznej bez stubs, dozwolone jest dodanie
   `[[tool.mypy.overrides]]` z `ignore_missing_imports` dla TEGO modułu.

## Kroki

1. `just mypy` - zbierz pełną listę do pliku roboczego.
2. Napraw plik po pliku (najpierw małe: agent_ctrl, game_ui, main_menu; scene.py
   na końcu - największe ryzyko).
3. Po każdym pliku: `just mypy` (licznik spada, nic nowego nie przybyło) +
   `just test-unit`.
4. Na końcu pełna weryfikacja (kryteria niżej).

## Kryteria akceptacji

1. `just mypy` - `Success: no issues found` (0 błędów).
2. `just test-unit` - 100% pass.
3. `MOM_SKIP_SS_REVIEW=1 just test-agent "Save and Load Basic"` - pass (dotykasz
   scene.py i agent_ctrl.py, więc smoke na żywej grze obowiązkowy).
4. Liczba nowych `# type: ignore` w diffie ≤ 5 (jeśli potrzebujesz więcej - stop,
   opisz problem w raporcie i zapytaj autora).
5. Zero zmian zachowania w runtime - diff zawiera wyłącznie anotacje, casty,
   konwersje typów i ewentualne oczywiste poprawki (jak `Path(...)` wokół str).

## Pułapki

- Dual-target: nie dodawaj importów pydantic ani typów z `config_pydantic` do modułów
  ładowanych na web - do anotacji użyj `TYPE_CHECKING` + string literal.
- `scene.py:1079` (`object` nie iterowalne) - to realne miejsce, gdzie typ jest zbyt
  szeroki; sprawdź co faktycznie tam płynie (prawdopodobnie property z pytmx),
  zawęź świadomie, nie `cast`-em w ciemno.
- Nie "naprawiaj" przy okazji stylu, nazw ani logiki - to zadanie ma diff czytelny
  jako czysto typowy.

## Po zakończeniu

- odhacz F03 w `doc/audyt/audyt.md`
- commit: `F03: mypy do zera - czysta bramka typów przed refactorem B01`
