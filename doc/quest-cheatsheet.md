---
tags: [sciagawka, questy]
---

# Questy - ściągawka

> [!warning] Wygenerowane przez `scripts/gen_quest_cheatsheet.py` (`just quest-cheatsheet`).
> Nie edytuj ręcznie - wszystko poniżej jest wyprowadzone z kodu (enumy, whitelista
> warunków, walidatory), więc nie może rozjechać się z tym, co robi import i silnik.

## Szablon questa

Jeden plik = jeden główny quest. Nagłówek sekcji jest **kluczem** questa, dosłownie, i musi
być globalnie unikalny. Alias to **własny klucz parasola** - sekcji, której podlegają
wszystkie pozostałe w pliku.

**PL** (`doc/PL/Misje/<Tytuł questa>.md`) jest źródłem prawdy;
**EN** (`doc/EN/Quests/<Quest title>.md`) daje samą prozę.

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

## Lista pól

| Pole         | Można też napisać                        | Obowiązkowe            | Skąd czytane |
| ------------ | ---------------------------------------- | ---------------------- | ------------ |
| `title`      | `title`, `tytul`, `tytuł`                | **tak**                | PL i EN      |
| `success`    | `success`, `sukces`                      | **tak**                | PL i EN      |
| `completion` | `completion`, `ukonczenie`, `ukończenie` | **tak**                | **tylko PL** |
| `test`       | `test`                                   | gdy `completion: test` | **tylko PL** |
| `requires`   | `requires`, `wymaga`                     | nie                    | **tylko PL** |
| `progress`   | `postep`, `postęp`, `progress`           | nie                    | **tylko PL** |
| `reward`     | `nagroda`, `reward`                      | nie                    | **tylko PL** |

Poza tymi polami obowiązkowa jest też **proza opisu** - akapit, który nie jest linią
`Pole:`. To on trafia do dziennika jako opis questa.

**Tylko PL** (decyzja D2): logika questa mieszka w **PL**. To samo pole napisane w **EN**
jest ignorowane z ostrzeżeniem - dzięki temu plik **EN** można bezpiecznie wygenerować
LLM-em: najgorsze, co zrobi, to źle napisana proza, nigdy zepsuty quest.

## Requires - zależności między questami

Link do questa, który musi być ukończony, aby **odblokować** ten krok. Klucz to tekst po
ostatnim `#`, więc każdy poniższy zapis znaczy to samo:

| Zapis | Kiedy |
| --- | --- |
| `[[#Q01_S05_MEET_MADAME_SARCASMIA]]` | cel w **tym samym pliku** - jedyna forma, którą Obsidian rozwiązuje wewnątrz notatki |
| `[[Q01_S00_BREAK_THE_CURSE#Q01_S01_LEARN_ABOUT_CURSE]]` | **krok innego łańcucha** - alias rozwiązuje plik, więc link przeżyje zmianę nazwy pliku |
| `[[Q00_S00_WHAT_IS_GOING_ON]]` | **parasol innego łańcucha** - alias JEST jego kluczem, więc powtarzanie go po `#` mówiłoby to samo dwa razy |
| `Q01_S01_LEARN_ABOUT_CURSE` | goły klucz, dalej działa |

Można wymienić kilka naraz, **po przecinku**.

## Completion - kiedy quest się zamyka

| Wartość         | Znaczenie                                                          |
| --------------- | ------------------------------------------------------------------ |
| `all_subquests` | parasol - zamyka się, gdy zamkną się wszystkie jej podrzędne kroki |
| `test`          | zamyka się sama, gdy `Test:` staje się prawdą                      |
| `manual`        | zamyka ją **wyłącznie kod gry** (`mark_done`)                      |

Odrzucane przy imporcie (`just import-quests`):

- `all_subquests` bez kroków - nic by jej nigdy nie zamknęło (to był bug `Q01_S07` w SSiS).
- `test` bez `Test:` - nie ma czego sprawdzać.
- `manual` **z** `Test:` - test nigdy by nie wystartował.

> [!tip] `manual` to obietnica do dotrzymania w kodzie
> Nic w configu nie zamknie questa `manual`. Jeśli nikt nie woła `mark_done`, wątek zostaje
> otwarty na zawsze. `just quest-graph` wypisuje takie questy wprost.

## Test - kiedy quest jest ukończony

Mini-DSL, nie `eval()`: whitelista dopuszczalnych komend, wszystko inne to błąd importu
(`just import-quests`) z numerem linii.

| Wywołanie | Znaczenie |
| --- | --- |
| `has_item("MERMAIDS_TEAR")` | gracz ma przedmiot `ITEM` w ekwipunku |
| `item_count("MERMAIDS_TEAR") >= 3` | ile sztuk `ITEM` gracz ma (liczba, nie prawda/fałsz) |
| `quest_done("Q01_S01_LEARN_ABOUT_CURSE")` | quest `KEY` jest ukończony |
| `visited("BARMAN_ABSINTHRAYNER", "012")` | gracz odwiedził węzeł dialogu `NODE` u postaci `NPC` |

**Łączenie**: `and`, `or`, `not`, nawiasy.
**Porównania**: ` == ` `!=` `<` `<=` `>` `>=` `in` `not in`.

Gołych nazw-wartości nie ma - `sentiment` działa tylko w dialogu, bo quest nie ma kontekstu bieżącej postaci.

`visited()` w queście wymaga **2 argumentów** (`NPC`, `NODE`), inaczej niż w dialogu, gdzie postać wynika z kontekstu rozmowy.

## Pasek postępu - n / m

`Postęp:` rysuje **pasek postępu w dzienniku** i nic poza tym - questa nie zamyka.
Ukośnik nie jest dzieleniem, tylko separatorem dla wartości *"z ilu"*:

```markdown
**Postęp**: item_count("MERMAIDS_TEAR") / 3
```

czyta się "ile **Łez syrenki** gracz ma, z **3** potrzebnych" i rysuje np.: `2 / 3`.

- **Po lewej**: coś, co zwraca **liczbę** - w praktyce `item_count()`, jedyny
  predykat, który zwraca liczbę. Wyrażenie prawda/fałsz (`has_item`, `visited`,
  porównanie `>=`) jest **odrzucane przy imporcie** z numerem linii, a nie dopiero przy
  otwarciu dziennika. Arytmetyki (`+`, `*`) whitelista nie przepuszcza.
- **Po prawej**: liczba całkowita - oczekiwana wartość do spełnienia. Trzeba podać oba albo
  żadne; `Postęp:` bez licznika to błąd importu.
- Wartość bieżąca (po lewej) jest przycinana do zakresu, a ukończony quest zawsze pokazuje
  pełny pasek.

> [!warning] Pasek postępu to nie warunek ukończenia
> Quest z paskiem `3 / 3` **nadal się nie zamknie**, dopóki nie napiszesz `Test:`.
> Pasek mówi ile brakuje; `Test:` decyduje kiedy jest gotowe. Zwykle chcesz obu:
>
> ```markdown
> **Completion**: test
> **Test**: item_count("MERMAIDS_TEAR") >= 3
> **Postęp**: item_count("MERMAIDS_TEAR") / 3
> ```

Parasole (`all_subquests`) dostają pasek **za darmo**, liczony z kroków - nie dodawaj dla
nich `Postęp:`.

## Nagroda - co dostanie gracz

Jedna linia `Nagroda:` per bonus dla gracza - **wszystkie są aplikowane**, nie tylko
pierwsza.

| Kategoria                | Znaczenie                                        | Przykład                               |
| ------------------------ | ------------------------------------------------ | -------------------------------------- |
| `money=nn`               | złoto                                            | `money=50`                             |
| `items=KEY_1,KEY_2`      | przedmioty (po przecinku)                        | `items=MERMAIDS_TEAR, PHOENIX_FEATHER` |
| `health=nn`              | leczy bieżące HP                                 | `health=20`                            |
| `max_health=nn`          | podnosi max HP **i bieżące o tyle samo**         | `max_health=20`                        |
| `damage=nn`              | zwiększa obrażenia zadawane przez gracza         | `damage=5`                             |
| `max_items=nn`           | sloty w pasku (limit `MAX_HOTBAR_ITEMS_LIMIT=8`) | `max_items=7`                          |
| `sentiment=nn @CHAR_KEY` | sympatia NPC - **wymaga `@NPC_KEY`**             | `sentiment=10 @BARMAN_ABSINTHRAYNER`   |

Odrzucane przy imporcie:

- nagroda o wartości `0` (albo `items=` bez przedmiotów) - to kształt, który nigdy nie jest
  zamierzony,
- `sentiment` bez `@NPC_KEY` - quest nie ma bieżącej postaci, więc nie byłoby komu polubić
  gracza,
- `@NPC_KEY` przy czymkolwiek poza `sentiment`.

Etykiety nagród składa silnik gry - nie pisz wartości liczbowej nagrody w `Sukces:`. Dzięki
temu przeważenie nagrody nie dotyka tłumaczeń.

## Znaczniki tekstu - MoM RichText

Działają w `Tytuł`, w prozie opisu i w `Sukces`. W grze renderują się odpowiednim stylem,
a w tooltipie grafu spłaszczają się do **pogrubienia**.

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

## Co zrobić po edycji

```bash
just import-quests  # importuje wszystkie łańcuchy do config.json; Qxx albo pełny klucz = tylko ten jeden
just quest-graph    # generuje graf w doc/_graphs/
```

Import działa na zasadzie **wszystko albo nic**: quest, który się nie zaimportuje, to quest,
którego nie ma w grze - więc `config.json` zostaje nietknięty, a błąd wskazuje plik i linię.
