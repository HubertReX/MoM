# D02 - dokument decyzyjny: mini-progresja statystyk gracza

Priorytet: **P2** (Faza 3). Rozmiar: M. Zależności: brak.
**Zakres zadania kończy się na dokumencie** - decyzja kierunkowa z audytu brzmi
„najpierw dokument decyzyjny, kod po akceptacji". Ani jednej linii kodu gry.

## Kontekst i problem

Znalezisko G-2: walka w labiryntach nie buduje postaci. Progresja przez **przedmioty**
istnieje (broń ma `damage`, jedzenie leczy), questy potrafią podnieść statystyki, ale
**nie ma systemu, który to spina** - gracz nie wie, że rośnie, a autor nie ma jednego
miejsca, w którym stroi tempo.

Kierunek autora (audyt, rozdz. 9): mini-progresja **czterech** wielkości -
szybkość, `max_health`, `damage` oraz **bazowy sentyment** („jak bardzo bohater jest
lubiany na starcie rozmowy"), przy czym bazowy sentyment ma móc też **spadać** przez
niektóre decyzje.

## Co JUŻ istnieje (dokument musi startować z tej inwentaryzacji, nie od zera)

| Element | Stan w kodzie |
| --- | --- |
| `max_health`, `damage`, `max_items` gracza | mutowalne w runtime: `result_sink_adapter.py` (`raise_max_health`, `raise_damage`, `raise_max_items`) |
| nagrody questów | `QuestRewardCategory`: `money`, `items`, `health`, `max_health`, `damage`, `max_items`, `sentiment` (`quest/entities.py:51`) - kategorie już są, brakuje ich świadomego dawkowania |
| persystencja | `PlayerState` w `save_load/models.py:295` zapisuje `max_health`, `damage`, `max_items`. **`speed_walk`/`speed_run` NIE są zapisywane** |
| szybkość | `speed_walk` / `speed_run` w `characters.csv` i `config_pydantic.py:80` - dziś stała cechą modelu, nikt jej nie podnosi |
| bazowy sentyment | `NPC.__init__`: `self.sentiment = round(self.model.friendly * 100)` (`characters/npc.py:110`) - kolumna `friendly` w `characters.csv`, per NPC, bez wpływu bohatera |
| przesunięcia sentymentu | opcje dialogowe (`apply_option_sentiment`, wagi `kind`/`weak`/`angry`/`smart`/`funny` w CSV) + nagroda questa `sentiment @NPC_KEY` |
| liczby balansowe | `config_model/*.csv` - domena autora, dokument ich NIE ustala |

## Cel zadania

Dokument decyzyjny, po którego akceptacji da się napisać zadanie implementacyjne bez
kolejnej rundy pytań. Ma odpowiadać na: **skąd bierze się wzrost, gdzie mieszkają
liczby, gdzie gracz to widzi, co ląduje w zapisie**.

## Format dostarczenia (jak przy B01)

- **HTML** w `doc/_attachements/progresja-statystyk-<data>.html` - główny nośnik:
  motyw jasny/ciemny, sekcje zwijane, **tabela opcji per decyzja** (Opcja / Jak działa /
  Koszt / Ryzyko / Rekomendacja) - taki układ autor czyta najszybciej.
- **md** `doc/progresja-statystyk.md` - skrót do linkowania z AGENTS.md (decyzje
  w punktach, bez rozwlekłości).
- podgląd: `docserve start doc/_attachements/progresja-statystyk-<data>.html`
  (autor czyta na laptopie przez tailnet).

## Zawartość dokumentu - wymagane rozdziały

1. **Inwentaryzacja** - tabela wyżej, zweryfikowana w kodzie (numery linii aktualne).
2. **Decyzja 1: źródła wzrostu.** Minimum trzy warianty w tabeli opcji, np.:
   (a) tylko nagrody questów (zero nowej mechaniki, pełna kontrola autora nad tempem),
   (b) questy + kamienie milowe fabularne (poziom labiryntu, koniec aktu),
   (c) klasyczne PD za walkę i poziomy postaci.
   Wskaż rekomendację i uzasadnij tonem gry („nie roguelike, nie hack&slash").
3. **Decyzja 2: szybkość jako statystyka.** Dziś jest cechą modelu z CSV i **nie
   przeżywa zapisu**. Opcje: pole w `PlayerState` (podbicie wersji zapisu - patrz
   [B02](B02-polityka-wersji-save.md)) vs bonus wyliczany z przedmiotów/questów przy
   wczytaniu (nic w zapisie). Konsekwencje obu wypisz wprost.
4. **Decyzja 3: bazowy sentyment bohatera.** Dziś startowy sentyment to cecha NPC
   (`friendly`). Wprowadzenie „reputacji bohatera" znaczy: `sentiment_startowy =
   f(friendly NPC, reputacja gracza)`. Zaprojektuj `f`, zakres, oraz **co obniża**
   reputację (decyzje dialogowe, złamane obietnice questowe, kradzież?). Rozstrzygnij,
   czy reputacja jest jedna globalna, czy per frakcja/miejsce - i **odpowiedz, dlaczego
   prostszy wariant wystarczy na prolog**.
5. **Separacja Tiled / config / kod** - twarda tabela: co jest w mapie, co w CSV, co
   w `config.json`, co w kodzie. Zasada projektu: liczby balansowe w CSV (domena
   autora), mechanika w kodzie, świat w Tiled. Wskaż nazwy kolumn/plików, które
   zadanie implementacyjne ma założyć.
6. **Widoczność dla gracza** - gdzie wzrost jest komunikowany: toast, panel questów,
   HUD, panel postaci (którego dziś nie ma - czy ma powstać?). Bez tego cała progresja
   jest niewidzialna, a to był oryginalny zarzut z G-2.
7. **Wpływ na zapis** - lista pól, które dochodzą do `PlayerState`, i **czy to zmiana
   formatu zapisu** wg polityki z B02 (jeden numer wersji gry, `save_compatibility`
   jako jedyna bramka, migracje kluczowane wersją zmiany formatu).
8. **Plan wdrożenia** - kroki dla przyszłego zadania implementacyjnego (D03?),
   każdy z bramkami, w tym co trzeba dopisać do `just validate-world`.
9. **Pytania otwarte do autora** - maksymalnie 5, każde z rekomendacją domyślną,
   tak żeby brak odpowiedzi nie blokował.

## Kryteria akceptacji

1. Dokument HTML + md istnieją, HTML ma działający przełącznik motywu i zwijane
   sekcje (wzoruj się na `doc/_attachements/refactor-rdzenia-b01-2026-07-25.html`).
2. Każda decyzja ma tabelę opcji z jawną rekomendacją - nie sama proza.
3. Inwentaryzacja zweryfikowana w kodzie (plik:linia zgadzają się ze stanem repo).
4. Dokument nie ustala liczb balansowych; wskazuje, gdzie autor je wpisze.
5. **Żadnej zmiany w kodzie gry** w tym zadaniu (dopuszczalne: linki w AGENTS.md).
6. Zadanie kończy się **przedstawieniem dokumentu autorowi do akceptacji** i pytaniem
   wprost o pytania otwarte z rozdz. 9. Implementacja rusza dopiero po „akceptuję".

## Pułapki

- Nie projektuj poziomów i tabel PD, jeśli rekomendujesz wariant „bez PD" - dokument
  ma być wykonalny, nie encyklopedyczny.
- Nie mieszaj progresji przedmiotowej (już działa) z progresją statystyk - opisz
  granicę, żeby przyszły agent nie przebudował ekwipunku „przy okazji".
- `NPC.sentiment` jest zapisywany per NPC w stanie zapisu; reputacja globalna to
  **osobne** pole - nie próbuj jej wyprowadzać z sentymentów NPC przy wczytaniu.
- Memory `design-work-not-balance-tuning`: przy projektowaniu chodzi o architekturę
  i zestaw parametrów, nie o dobieranie liczb.

## Po zakończeniu

- link do dokumentu z `doc/audyt/audyt.md` i z `project/AGENTS.md`
- odhacz D02 w `doc/audyt/audyt.md` (zadanie = dokument; implementacja to osobna pozycja)
- commit: `D02: dokument decyzyjny mini-progresji statystyk (do akceptacji)`
