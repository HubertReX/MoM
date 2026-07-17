---
tags: [sciagawka, questy]
---

# Questy - ściągawka

> [!warning] Wygenerowane przez `scripts/gen_quest_cheatsheet.py` (`just quest-cheatsheet`).
> Nie edytuj ręcznie - wszystko poniżej jest wyprowadzone z kodu (enumy, whitelista
> warunków, walidatory), więc nie może rozjechać się z tym, co robi import i silnik.

## Szablon łańcucha

Jeden plik = jeden łańcuch. Nagłówek sekcji **jest** kluczem questa, dosłownie, i musi być
globalnie unikalny. Alias to **własny klucz parasola** - sekcji, której podlegają wszystkie
pozostałe w pliku.

PL (`doc/PL/Misje/<Tytuł łańcucha>.md`) jest źródłem prawdy; EN (`doc/EN/Quests/`) daje samą prozę.

```markdown
---
aliases:
  - Q01_S00_BREAK_THE_CURSE
---

# Przełamać klątwę

Proza wprowadzająca do łańcucha (opcjonalna, nie trafia do gry).

## Q01_S00_BREAK_THE_CURSE

**Tytuł**: Przełamać klątwę

Opis, który gracz zobaczy w dzienniku. Obsługuje znaczniki: [char]Kowal[/].

**Completion**: manual
**Requires**: [[Q00_S00_WHAT_IS_GOING_ON]]
**Sukces**: Klątwa zdjęta. Miecz milczy pierwszy raz od tygodni.
**Nagroda**: max_health=20
**Nagroda**: damage=5

## Q01_S01_LEARN_ABOUT_CURSE

**Tytuł**: Dowiedz się więcej o klątwie

Każda sekcja poza tą z aliasu jest krokiem parasola - `parent` bierze się z pliku.

**Completion**: test
**Test**: visited("BARMAN_ABSINTHRAYNER", "012")
**Sukces**: Barman gada. Barman zawsze gada.
```

## Pola sekcji

| Pole | Można też napisać | Skąd czytane |
| --- | --- | --- |
| `title` | `title`, `tytul`, `tytuł` | PL i EN |
| `success` | `success`, `sukces` | PL i EN |
| `completion` | `completion`, `ukonczenie`, `ukończenie` | **tylko PL** |
| `test` | `test` | **tylko PL** |
| `requires` | `requires`, `wymaga` | **tylko PL** |
| `progress` | `postep`, `postęp`, `progress` | **tylko PL** |
| `reward` | `nagroda`, `reward` | **tylko PL** |

**Tylko PL** (decyzja D2): logika questa mieszka w PL. To samo pole napisane w EN jest
ignorowane z ostrzeżeniem - dzięki temu plik EN można bezpiecznie wygenerować LLM-em:
najgorsze, co zrobi, to zła proza, nigdy zepsuty quest.

## Requires - linkowanie questów

Klucz to tekst po ostatnim `#`, więc każdy zapis znaczy to samo. Wybór jest kwestią
Obsidiana, nie importu:

| Zapis | Kiedy |
| --- | --- |
| `[[#Q01_S05_MEET_MADAME_SARCASMIA]]` | cel w **tym samym pliku** - jedyna forma, którą Obsidian rozwiązuje wewnątrz notatki |
| `[[Q01_S00_BREAK_THE_CURSE#Q01_S01_LEARN_ABOUT_CURSE]]` | **krok innego łańcucha** - alias rozwiązuje plik, więc link przeżyje zmianę nazwy pliku |
| `[[Q00_S00_WHAT_IS_GOING_ON]]` | **parasol innego łańcucha** - alias JEST jego kluczem, więc powtarzanie go po `#` mówiłoby to samo dwa razy |
| `Q01_S01_LEARN_ABOUT_CURSE` | goły klucz, dalej działa |

Kilka naraz: po przecinku.

## Completion

| Wartość | Znaczenie |
| --- | --- |
| `all_subquests` | parasol - zamyka się, gdy zamkną się wszystkie jej kroki |
| `test` | zamyka się sama, gdy `**Test**:` staje się prawdą |
| `manual` | zamyka ją **wyłącznie kod gry** (`mark_done`) |

Odrzucane przy imporcie:

- `all_subquests` bez kroków - nic by jej nigdy nie zamknęło (to był bug `Q01_S07` w SSiS).
- `test` bez `**Test**:` - nie ma czego sprawdzać.
- `manual` **z** `**Test**:` - test nigdy by nie wystartował.

> [!tip] `manual` to obietnica do dotrzymania w kodzie
> Nic w configu nie zamknie questa `manual`. Jeśli nikt nie woła `mark_done`, wątek zostaje
> otwarty na zawsze. `just quest-graph` wypisuje takie questy wprost.

## Test i Postęp - składnia

Mini-DSL, nie `eval()`: whitelista, wszystko poza nią to błąd importu z numerem linii.

| Wywołanie | Znaczenie |
| --- | --- |
| `has_item("MERMAIDS_TEAR")` | gracz ma przedmiot `ITEM` w ekwipunku |
| `item_count("MERMAIDS_TEAR") >= 3` | ile sztuk `ITEM` gracz ma (liczba, nie prawda/fałsz) |
| `quest_done("Q01_S01_LEARN_ABOUT_CURSE")` | quest `KEY` jest ukończony |
| `visited("BARMAN_ABSINTHRAYNER", "012")` | gracz odwiedził węzeł dialogu `NODE` u postaci `NPC` |

Łączenie: `and`, `or`, `not`, nawiasy. Porównania: `==` `!=` `<` `<=` `>` `>=` `in` `not in`.

Gołych nazw-wartości nie ma - `sentiment` działa tylko w dialogu, bo quest nie ma bieżącej postaci.

`visited()` w queście wymaga **2 argumentów** (`NPC`, `NODE`), inaczej niż w dialogu, gdzie postać wynika z rozmowy. Quest nie ma "bieżącego NPC", więc `visited("012")` parsowałoby się, wiecznie zwracało fałsz i cicho blokowało łańcuch.

`**Postęp**:` to wyrażenie **liczbowe** i licznik, po ukośniku - oba albo żadne:

```markdown
**Postęp**: item_count("MERMAIDS_TEAR") / 3
```

## Nagroda

Jedna linia `**Nagroda**:` na nagrodę - **wszystkie są aplikowane**, nie tylko pierwsza.

| Kategoria | Znaczenie | Przykład |
| --- | --- | --- |
| `money` | złoto | `money=50` |
| `items` | przedmioty (po przecinku) | `items=MERMAIDS_TEAR, PHOENIX_FEATHER` |
| `health` | leczy bieżące HP | `health=20` |
| `max_health` | podnosi max HP **i bieżące o tyle samo** | `max_health=20` |
| `damage` | obrażenia gracza | `damage=5` |
| `max_items` | sloty w pasku (limit `MAX_HOTBAR_ITEMS_LIMIT`) | `max_items=1` |
| `sentiment` | sympatia NPC - **wymaga `@NPC_KEY`** | `sentiment=10 @BARMAN_ABSINTHRAYNER` |

Odrzucane przy imporcie:

- nagroda o wartości `0` (albo `items=` bez przedmiotów) - to kształt, na którym SSiS cicho
  przechodził dalej; nigdy nie jest zamierzony,
- `sentiment` bez `@NPC_KEY` - quest nie ma bieżącej postaci, więc nie byłoby komu polubić gracza,
- `@NPC_KEY` przy czymkolwiek poza `sentiment`.

Etykiety nagród składa silnik z liczb - nie pisz ich w `**Sukces**:`. Dzięki temu przeważenie
nagrody nie dotyka tłumaczeń.

## Znaczniki tekstu

Działają w `**Tytuł**`, w prozie opisu i w `**Sukces**`. W grze renderują się stylem,
w tooltipie grafu spłaszczają się do pogrubienia.

| Rodzaj | Znaczniki |
| --- | --- |
| kolor | `[act]`, `[char]`, `[error]`, `[item]`, `[loc]`, `[num]`, `[quest]`, `[text]` |
| rozmiar / nagłówek | `[big]`, `[h1]`, `[h2]`, `[h3]`, `[small]` |
| wyróżnienie | `[b]`, `[bold]`, `[i]`, `[italic]`, `[u]`, `[underline]` |
| cień | `[dark]`, `[light]`, `[shadow]` |
| wyrównanie | `[center]`, `[left]`, `[right]` |
| link | `[link https://...]tekst[/link]` |

`[/]` zamyka **ostatni otwarty** znacznik, więc `[char]Kowal[/]` == `[char]Kowal[/char]`,
a `[h3][char]X[/][/]` domyka najpierw `char`, potem `h3`.

Emotki wstawia się jako `:nazwa:` - pełen arkusz z kluczami:
![[_attachements/mom-emote-sheet.png]]

## Po edycji

```bash
just import-quests          # wszystkie łańcuchy; Qxx albo pełny klucz = jeden
just quest-graph            # graf DAG do doc/_graphs/
```

Import jest **wszystko albo nic**: quest, który się nie zaimportuje, to quest, którego po cichu
nie ma w grze - więc `config.json` zostaje nietknięty, a błąd wskazuje plik i linię.
