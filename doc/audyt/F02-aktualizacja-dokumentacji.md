# F02 - aktualizacja AGENTS.md i dokumentów design systemu do stanu kodu

Priorytet: **P1** (Faza 1). Rozmiar: S. Zależności: brak.

## Kontekst i problem

Dokumentacja dla agentów (AGENTS.md, design-system) zawiera stwierdzenia sprzeczne
z obecnym kodem. Agenci AI traktują te pliki jako prawdę nadrzędną, więc każde
nieaktualne zdanie produkuje błędne decyzje ("elementarne błędy słabszych modeli"
zgłaszane przez autora mają tu jedno ze źródeł). Audyt 2026-07-25 znalazł konkretne
rozjazdy - lista poniżej jest wyczerpująca dla tego zadania (nie szukaj dalej,
nie przepisuj całych plików).

## Rozjazdy do naprawy (kompletna lista)

### 1. root `AGENTS.md`

- "~11.9K LOC własnego kodu" - jest ~26,2K (policz aktualnie:
  `find project -name "*.py" -not -path "*/animation/*" | xargs wc -l | tail -1`)
- "na etapie tech-demo: (...) brak fabuły i pełnej mapy świata" - nieaktualne: fabuła
  jest (`doc/PL/fabuła.md`), prolog w budowie, 8 questów, 6 grafów dialogowych;
  przeformułuj na "prolog (Akt 1) w budowie"
- sekcja "Testy jednostkowe": "23 pliki, 285 testów" - jest 30 plików, 407 testów
  (zweryfikuj: `just test-unit` wypisuje podsumowanie); zamiast wpisywać kolejną
  liczbę na sztywno, napisz "30+ plików, 400+ testów (aktualną liczbę podaje
  `just test-unit`)"
- `settings.py:84` jako lokalizacja `IS_WEB` - dziś to `settings.py:303-304`; usuń
  numer linii, zostaw nazwę pliku (numery linii w docach gniją najszybciej)

### 2. `project/AGENTS.md`

- sekcja "Persystencja stanu" zaczyna się od "**Brak systemu save/load na dysk** -
  zamknięcie gry traci postęp (na liście TODO w README)" - FAŁSZ, pełny save/load
  istnieje (`save_load/`, sloty, quick save F5/F9, web localStorage) i jest opisany
  niżej w tym samym pliku. Usuń zdanie i przepisz akapit tak, by opisywał: caching map
  w RAM (`loaded_maps`) + save/load na dysk/localStorage + odesłanie do sekcji o F5/F9
- sekcja "ss-review": po wykonaniu zadania A01 zaktualizuje ją tamten agent; jeśli A01
  jeszcze nie zrobione - zostaw bez zmian (nie wyprzedzaj)

### 3. `project/ui/AGENTS.md`

- zasada nadrzędna nr 1: "Gra renderuje cały canvas (świat + UI) w logicznej
  rozdzielczości 1280×720, po czym skaluje go jako jeden obraz (`settings.py:266-269`,
  `SCALE`)" - NIEAKTUALNE. Od zmiany pixel-perfect: `SCALE = 1.0` zawsze, canvas =
  rozmiar okna, zero skalowania (root AGENTS.md sekcja "pixel-perfect" opisuje to
  poprawnie). Przepisz zasadę nr 1 w duchu: "nie zdradzać pixel-artu: elementy UI
  skaluj parzyście (integer scale), fonty to jedyny wyjątek" - bez odwołań do
  globalnego SCALE. Sekcja "Rozdzielczość ekranu - preferuj całkowite krotności bazy"
  też wymaga korekty (nie ma już skali ułamkowej całego canvasa; zostaje zasada
  integer scale dla sprite'ów)
- sekcja "Rozmiary czcionki", wzmianka o "downscale przez SCALE" - usuń odwołanie
  do downscale (tekst UI nie jest już skalowany)

### 4. `doc/design-system-ui.md`

- sekcja "Context": ten sam rozjazd co wyżej (1280×720 + SCALE). Dopisz na początku
  sekcji adnotację: "> [!note] Stan na 2026-07: opis skalowania poniżej jest
  historyczny - gra renderuje pixel-perfect 1:1 (SCALE=1.0), patrz root AGENTS.md."
  (dokument jest częściowo historycznym zapisem audytu - adnotacja zamiast
  przepisywania)

### 5. `README.md` / `CONTRIBUTION.md`

- W `CONTRIBUTION.md` sekcja "Known bugs": pozycja "game is not working in the
  **Firefox** browser" - zweryfikuj jednym zdaniem z autorem przy odbiorze zadania
  czy nadal aktualne; NIE zmieniaj bez potwierdzenia. Pozostałych sekcji nie ruszaj
  (autor traktuje je jako listę historyczno-pomysłową).

## Kryteria akceptacji

1. `rg -n "11.9K|285 testów|23 pliki" AGENTS.md project/AGENTS.md` - zero trafień.
2. `rg -n "Brak systemu save/load" project/AGENTS.md` - zero trafień.
3. `rg -n "1280×720|1280x720" project/ui/AGENTS.md` - zero trafień (w design-system-ui.md
   może zostać, bo tam jest adnotacja).
4. Zasady formatowania markdown autora zachowane (pusta linia po nagłówku, listy `-`,
   bez em-dash - separator to " - ").
5. Żadnych zmian w kodzie (`git diff --stat` pokazuje wyłącznie pliki md).

## Pułapki

- NIE przepisuj całych plików - punktowe korekty. AGENTS.md to żywe dokumenty
  z dużą wartością; zadanie usuwa fałsz, nie zmienia stylu.
- Root AGENTS.md sekcja pixel-perfect jest POPRAWNA - to wzorzec, do którego
  równasz ui/AGENTS.md, nie odwrotnie.
- Nie aktualizuj liczb, które będą gnić (liczba testów, LOC) na kolejne sztywne
  liczby - tam gdzie się da, wskaż komendę źródłową.

## Po zakończeniu

- odhacz F02 w `doc/audyt/audyt.md`
- commit: `F02: AGENTS.md/design-docs - usunięcie stwierdzeń sprzecznych z kodem`
