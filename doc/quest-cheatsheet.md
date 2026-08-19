---
tags: [sciagawka, questy]
---

# Questy - ściągawka

> [!warning] Wygenerowane przez `scripts/gen_quest_cheatsheet.py` (`just gen-quest-cheatsheet`).
> Nie edytuj ręcznie - wszystko poniżej jest wyprowadzone z kodu (enumy, whitelista warunków, walidatory), więc nie może rozjechać się z tym, co robi import i silnik.

> [!important] Kolejność kluczy jest kolejnością podpowiadaną graczowi
> HUD pokazuje **jeden** quest naraz - wskaźnik „co teraz?" (H01/D7). Gdy śledzony krok się zamknie, gra przechodzi do następnego: najpierw do tego, co ten krok właśnie odblokował, potem do nieukończonego rodzeństwa - a w obu przypadkach bierze **pierwszy w kolejności definicji**, czyli pierwszy po kluczu (`Q01_S01` przed `Q01_S02`). Numer w kluczu jest więc kolejnością, w jakiej gracz to zobaczy. Parasole wskaźnik pomija (to tytuł rozdziału, nie instrukcja), choć gracz może przypiąć dowolny quest ręcznie klawiszem `T` w dzienniku.

## Szablon questa

**Jeden plik = jeden quest.** Alias we frontmatterze jest **kluczem** questa, dosłownie, i musi być globalnie unikalny; nagłówek `# H1` jest jego tytułem.

**PL** (`doc/PL/Misje/Qxx_Syy <Tytuł questa>.md`) jest źródłem prawdy;
**EN** (`doc/EN/Quests/Qxx_Syy <Quest title>.md`) daje samą prozę.

```markdown
---
aliases:
  - Q01_S01_LEARN_ABOUT_CURSE
---
# Dowiedz się więcej o klątwie

Opis, który gracz zobaczy w dzienniku. Obsługuje znaczniki: [char]Kowal[/].

**Requires**: [[Q01_S00 Przełamać klątwę]]
**Completion**: `test`
**Test**: `visited(`[[Barman Absyntnent#012|Barman#012]]`)`
**Sukces**: Barman gada. Barman zawsze gada.
**Nagroda**: `restore_health(20)`

## Notatki

Cokolwiek dla autora - importer przestaje czytać na pierwszym `##`.
```

### Klucz mówi, do jakiego wątku należy quest

Klucz czyta się `Qxx_Syy_NAZWA`: `Qxx` to **wątek**, `Syy` to **krok w nim**. Krok `S00` jest parasolem wątku, a każdy inny krok tego samego `Qxx` jest jego podquestem - `parent` **nie jest nigdzie zapisywany**, tylko wyliczany z klucza. Dlatego:

- wątek bez `S00` to błąd importu (kroki nie miałyby rodzica),
- dwa `S00` w jednym wątku to też błąd,
- nazwa pliku powtarza prefiks `Qxx_Syy` po to, żeby katalog sortował się w kolejności gry.

Kolejność **między krokami** to osobna rzecz: mówi o niej `Requires`, nie numeracja.

### Notatki - to, czego gracz nie zobaczy

Wszystko od **pierwszego nagłówka `##`** w dół importer pomija. Tam trafiają uwagi autorskie, długi treści, „dlaczego tak" - proza **nad** nim należy do gracza i ląduje w dzienniku. Pole `**Coś**:` zapisane poniżej `##` nie działa; import wypisze o tym ostrzeżenie zamiast po cichu je zjeść.

## Lista pól

| Pole         | Można też napisać                        | Obowiązkowe            | Skąd czytane |
| ------------ | ---------------------------------------- | ---------------------- | ------------ |
| `success`    | `success`, `sukces`                      | tak                    | PL i EN      |
| `completion` | `completion`, `ukonczenie`, `ukończenie` | tak                    | **tylko PL** |
| `test`       | `test`                                   | gdy `completion: test` | **tylko PL** |
| `requires`   | `requires`, `wymaga`                     | nie                    | **tylko PL** |
| `progress`   | `postep`, `postęp`, `progress`           | nie                    | **tylko PL** |
| `reward`     | `nagroda`, `reward`                      | nie                    | **tylko PL** |

**Tytuł** nie jest polem - to nagłówek `# H1` pliku.

Poza tymi polami obowiązkowa jest też **proza opisu** - akapit, który nie jest linią `Pole:`. To on trafia do dziennika jako opis questa. **Pusta linia rozdziela akapity** i przeżywa import (w dzienniku widać pustą linię); łamanie linii wewnątrz akapitu nie - zawijanie należy do panelu.

**Tylko PL** (decyzja D2): logika questa mieszka w **PL**. To samo pole napisane w **EN** jest ignorowane z ostrzeżeniem - dzięki temu plik **EN** można bezpiecznie wygenerować LLM-em: najgorsze, co zrobi, to źle napisana proza, nigdy zepsuty quest.

## Backquote i wikilinki - jak się pisze wartości

Wartość, którą czyta silnik (`Completion`, `Test`, `Postęp`, `Nagroda`), zamyka się w **backquote'ach**: w Obsidianie widać wtedy od razu, gdzie kończy się proza, a zaczyna kod. Importer je zdejmuje.

Odwołanie do postaci albo questa pisze się w środku jako **prawdziwy wikilink**, przeplatany z backquote'ami - dzięki temu jedno wyrażenie jest jednocześnie warunkiem dla silnika i krawędzią w grafie Obsidiana, po którym widać, kto od czego zależy:

```markdown
**Test**: `visited(`[[Barman Absyntnent#012|Barman#012]]`) or visited(`[[Barman Absyntnent#009|Barman#009]]`)`
```

Import rozwija linki po kluczach z frontmatteru notatki, na którą wskazują:

- `[[Notatka#kotwica]]` -> `"KLUCZ", "kotwica"` - kotwica to węzeł dialogu, więc jeden link daje **oba** argumenty `visited()`. Sufiks `-end` w nagłówku dialogu nie należy do klucza węzła i jest obcinany.
- `[[Notatka]]` -> `"KLUCZ"` - sama encja.

Link do notatki, której w vaulcie nie ma, to błąd importu z numerem linii - literówka w nazwie postaci nie ma szans dożyć do gry. Stary zapis z gołymi stringami (`visited("BARMAN_ABSINTHRAYNER", "012")`) nadal działa, ale nie rysuje się w grafie.

> [!warning] Nie zaczynaj backquote'a od znaku równości
> Zawartość backquote'a zaczynającą się od znaku równości Dataview bierze za **inline query** i zamiast operatora wypisuje w notatce błąd parsera (tak umiera zapis równości wpisany wprost). Wstaw spację po otwierającym backquote - ` ==` - wygląda tak samo, a Dataview przestaje się tym interesować.

## Requires - zależności między questami

Link do questa, który musi być ukończony, aby **odblokować** ten krok. Każdy poniższy zapis znaczy to samo:

| Zapis                                      | Kiedy                                                                                             |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| `[[Q01_S01 Dowiedz się więcej o klątwie]]` | **po nazwie notatki** - to podpowiada autouzupełnianie Obsidiana i to rysuje graf                 |
| `[[Q01_S01_LEARN_ABOUT_CURSE]]`            | **po aliasie**, czyli po kluczu - alias rozwiązuje notatkę, więc link przeżyje zmianę nazwy pliku |
| `Q01_S01_LEARN_ABOUT_CURSE`                | goły klucz, dalej działa                                                                          |

Można wymienić kilka naraz, **po przecinku**.

`Requires` to jedyne miejsce, w którym zapisuje się **kolejność kroków w wątku**: parasol bierze się z klucza, ale to, czy kroki idą po kolei, czy równolegle, wynika wyłącznie stąd.

### Odblokowanie węzłem dialogu

W tym samym polu można napisać **warunek** zamiast (albo obok) linku do questa. Rozpoznaje się go po tym, że jest **wywołaniem** - ma nawiasy:

| Zapis                                            | Znaczy                                                                     |
| ------------------------------------------------ | -------------------------------------------------------------------------- |
| `` `visited(`[[Barman Absyntnent#023]]`)` ``     | quest otwiera się, gdy gracz **odwiedził węzeł 023** w dialogu Barmana     |
| `` `has_item(`[[Łza Syrenki]]`)` ``              | gdy gracz ma przedmiot - dowolny warunek z whitelisty zasięgu `quest`      |
| `` `not visited(`[[Barman Absyntnent#023]]`)` `` | operatory (`not`, `and`, `or`, porównania) działają tak samo, jak w `Test` |

Tak zapisuje się „quest pojawia się, kiedy gracz o nim usłyszy": dopóki rozmowa się nie odbyła, questa nie ma nawet w dzienniku.

Warunek jest sprawdzany **na żywo**, przy każdym pytaniu „czy odblokowany?", i sprawdza go ta sama whitelista, co `Test` (zasięg `quest`, więc `visited` **musi** wskazywać postać - a wskazuje ją wikilink). Literówka w nazwie węzła to błąd importu, nie cichy `False` do końca gry.

Kilka pozycji nadal rozdziela się przecinkiem i można je mieszać - warunki łączą się przez `and`, a linki do questów zostają osobną listą:

```markdown
**Requires**: [[Q01_S01 Dowiedz się więcej o klątwie]], `visited(`[[Barman Absyntnent#023]]`)`
```

> [!warning] `quest_done()` w `Requires` jest odrzucane
> Zależność od innego questa **musi** być linkiem na liście. Schowana w warunku byłaby krawędzią odblokowania, której nie widzi kontrola cykli przy imporcie - i zakleszczenie dwóch questów weszłoby do gry po cichu. Ten sam sens, widoczny zapis.

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
> Nic w configu nie zamknie questa `manual`. Jeśli nikt nie woła `mark_done`, wątek zostaje otwarty na zawsze. `just gen-quest-graph` wypisuje takie questy wprost.

## Test - kiedy quest jest ukończony

Mini-DSL, nie `eval()`: whitelista dopuszczalnych komend, wszystko inne to błąd importu (`just import-quests`) z numerem linii.

| Wywołanie                                 | Znaczenie                                            |
| ----------------------------------------- | ---------------------------------------------------- |
| `has_item("MERMAIDS_TEAR")`               | gracz ma przedmiot `ITEM` w ekwipunku                |
| `item_count("MERMAIDS_TEAR") >= 3`        | ile sztuk `ITEM` gracz ma (liczba, nie prawda/fałsz) |
| `quest_done("Q01_S01_LEARN_ABOUT_CURSE")` | quest `KEY` jest ukończony                           |
| `visited("BARMAN_ABSINTHRAYNER", "012")`  | gracz odwiedził węzeł dialogu `NODE` u postaci `NPC` |

**Łączenie**: `and`, `or`, `not`, nawiasy.
**Porównania**: ` ==` `!=` `<` `<=` `>` `>=` `in` `not in`.

Gołych nazw-wartości nie ma - `sentiment` działa tylko w dialogu, bo quest nie ma kontekstu bieżącej postaci.

`visited()` w queście wymaga **2 argumentów** (`NPC`, `NODE`), inaczej niż w dialogu, gdzie postać wynika z kontekstu rozmowy.

## Pasek postępu - n / m

`Postęp:` rysuje **pasek postępu w dzienniku** i nic poza tym - questa nie zamyka. Ukośnik nie jest dzieleniem, tylko separatorem dla wartości *"z ilu"*:

```markdown
**Postęp**: item_count("MERMAIDS_TEAR") / 3
```

czyta się "ile **Łez syrenki** gracz ma, z **3** potrzebnych" i rysuje np.: `2 / 3`.

- **Po lewej**: coś, co zwraca **liczbę** - w praktyce `item_count()`, jedyny predykat, który zwraca liczbę. Wyrażenie prawda/fałsz (`has_item`, `visited`, porównanie `>=`) jest **odrzucane przy imporcie** z numerem linii, a nie dopiero przy otwarciu dziennika. Arytmetyki (`+`, `*`) whitelista nie przepuszcza.
- **Po prawej**: liczba całkowita - oczekiwana wartość do spełnienia. Trzeba podać oba albo żadne; `Postęp:` bez licznika to błąd importu.
- Wartość bieżąca (po lewej) jest przycinana do zakresu, a ukończony quest zawsze pokazuje pełny pasek.

> [!warning] Pasek postępu to nie warunek ukończenia
> Quest z paskiem `3 / 3` **nadal się nie zamknie**, dopóki nie napiszesz `Test:`. Pasek mówi ile brakuje; `Test:` decyduje kiedy jest gotowe. Zwykle chcesz obu:
>
> ```markdown
> **Completion**: test
> **Test**: item_count("MERMAIDS_TEAR") >= 3
> **Postęp**: item_count("MERMAIDS_TEAR") / 3
> ```

Parasole (`all_subquests`) dostają pasek **za darmo**, liczony z kroków - nie dodawaj dla nich `Postęp:`.

## Nagroda - co dostanie gracz

Jedna linia `Nagroda:` per bonus dla gracza - **wszystkie są aplikowane**, nie tylko pierwsza.

| Zapis                         | Znaczenie                                                            | Przykład                                               |
| ----------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------ |
| `add_money(nn)`               | złoto                                                                | `add_money(50)`                                        |
| `add_n_items(nn, ITEM, …)`    | przedmioty - pierwszy argument to **krotność każdego** z nich        | `add_n_items(2,`[[Łza Syrenki]]`,`[[Pióro Feniksa]]`)` |
| `restore_health(nn)`          | leczy bieżące HP                                                     | `restore_health(20)`                                   |
| `raise_max_health(nn)`        | podnosi max HP **i bieżące o tyle samo**                             | `raise_max_health(20)`                                 |
| `raise_damage(nn)`            | zwiększa obrażenia zadawane przez gracza                             | `raise_damage(5)`                                      |
| `raise_max_items(nn)`         | sloty w pasku (limit `MAX_HOTBAR_ITEMS_LIMIT=8`)                     | `raise_max_items(7)`                                   |
| `shift_sentiment_of(NPC, nn)` | sympatia NPC - **wymaga adresata**, bo quest nie ma bieżącej postaci | `shift_sentiment_of(`[[Barman Absyntnent]]`,10)`       |

Nagroda **daje**, a nie zabiera, więc czasowniki odbierające (`remove_money`, `lose_health`, `remove_n_items`) są tu błędem importu - te mieszkają w dialogu, gdzie NPC może coś graczowi wziąć. Ta sama gramatyka opisuje jedno i drugie: to ten sam mechanizm (`dialog/effects.py`), a nazwy czasowników są nazwami metod `ResultSink` w kodzie.

Odrzucane przy imporcie:

- nagroda o wartości `0` (albo `add_n_items` bez przedmiotu) - to kształt, który nigdy nie jest zamierzony,
- liczba ujemna przy czasowniku, który już mówi, w którą stronę idzie (`add_money(-50)`),
- `shift_sentiment(10)` bez adresata - quest nie ma bieżącej postaci, więc nie byłoby komu polubić gracza; adresata podaje `shift_sentiment_of`.

Etykiety nagród składa silnik gry - nie pisz wartości liczbowej nagrody w `Sukces:`. Dzięki temu przeważenie nagrody nie dotyka tłumaczeń.

## Encje w prozie - pisze się je linkiem

Postać, lokalizację i przedmiot pisze się w tytule, opisie i `Sukces` **wikilinkiem**; import zamienia go na znacznik, którym gra koloruje encję:

| W notatce                        | W grze                                    |
| -------------------------------- | ----------------------------------------- |
| `[[Zielarka Zmora]]`             | `[char]Zielarka Zmora[/char]`             |
| `[[Tawerna Brakująca klepka]]`   | `[loc]Tawerna Brakująca klepka[/loc]`     |
| `[[Łza Syrenki]]`                | `[item]Łza Syrenki[/item]`                |
| `[[Barman Absyntnent\|Barmana]]` | `[char]Barmana[/char]` - odmiana z kreski |

Znacznik bierze się z **katalogu notatki**, więc nie trzeba go wybierać, a napis po pionowej kresce niesie odmianę. Link bez kreski pokazuje nazwę notatki w języku pliku, więc `[[Zielarka Zmora]]` w pliku EN wyświetli się jako „Potioneer Puzzlemint".

Znacznikiem wprost pisze się dalej to, co **nie ma notatki**: istoty ze wspomnień, rzeczowniki pospolite, zaimki (`[char]Ty[/char]`). Link do nieistniejącej notatki zostaje w tekście dosłownie i `just validate-world` (reguła 22) uzna to za błąd - gracz zobaczyłby surowe `[[nawiasy]]`.

## Znaczniki tekstu - MoM RichText

Działają w `Tytuł`, w prozie opisu i w `Sukces`. W grze renderują się odpowiednim stylem, a w tooltipie grafu spłaszczają się do **pogrubienia**.

Markdownowe wyróżnienia pisze się **po markdownowemu**: `**pogrubienie**` i `_kursywa_` importer sam zamienia na `[shadow]` i `[italic]` - tak samo, jak w dialogach. Znaczników wyróżnienia nie trzeba pisać ręcznie.

`**` idzie na `[shadow]`, a nie na `[bold]`, bo font pikselowy nie ma prawdziwego pogrubienia: `[bold]` to jeden dodatkowy piksel grubości kreski i w akapicie go po prostu nie widać. Wyróżnia cień.

| Rodzaj             | Znaczniki                                                                     |
| ------------------ | ----------------------------------------------------------------------------- |
| kolor              | `[act]`, `[char]`, `[error]`, `[item]`, `[loc]`, `[num]`, `[quest]`, `[text]` |
| rozmiar / nagłówek | `[big]`, `[h1]`, `[h2]`, `[h3]`, `[small]`                                    |
| wyróżnienie        | `[b]`, `[bold]`, `[i]`, `[italic]`, `[u]`, `[underline]`                      |
| cień               | `[dark]`, `[light]`, `[shadow]`                                               |
| wyrównanie         | `[center]`, `[left]`, `[right]`                                               |
| link               | `[link https://...]tekst[/link]`                                              |

`[/]` zamyka **ostatni otwarty** znacznik, więc `[char]Kowal[/]` znaczy to samo co `[char]Kowal[/char]`, a `[h3][char]X[/][/]` domyka najpierw `char`, potem `h3`.

Emotki wstawia się jako `:nazwa:` - pełen arkusz z kluczami:
![[_attachements/mom-emote-sheet.png]]

## Co zrobić po edycji

```bash
just import-quests  # importuje wszystkie łańcuchy do config.json; Qxx albo pełny klucz = tylko ten jeden
just gen-quest-graph    # generuje graf w doc/_graphs/
```

Import działa na zasadzie **wszystko albo nic**: quest, który się nie zaimportuje, to quest, którego nie ma w grze - więc `config.json` zostaje nietknięty, a błąd wskazuje plik i linię.

### Czego szukać na grafie

Graf czyta się **od lewej do prawej**, kolumnami:

```text
[rozmowa otwierająca]  [WĄTEK]  [rozmowy z Test wątku]  [kroki wątku]  [rozmowy z Test kroków]
     sześciokąt        prostokąt      sześciokąty       owale, jeden      sześciokąty
                                                         pod drugim
```

Rytm kolumn jest stały: **quest odblokowany przez quest stoi zawsze o dwie kolumny dalej, rozmowa o jedną**. Kolumna na rozmowy jest rezerwowana nawet wtedy, gdy quest żadnej nie nazywa - pusta kolumna kosztuje cal ekranu, złamany rytm kosztuje czytelność całego obrazka. Pustej kolumny globalnie nie ma: wątek bez rozmowy otwierającej zaczyna od lewej krawędzi.

**Wszystkie kroki jednego wątku stoją w jednej kolumnie**, jeden pod drugim; ich kolejność niosą szare strzałki `requires` między nimi. To jest ta jedna rzecz, która pozwala prześledzić wątek wzrokiem.

### Jak czytać strzałki

Jedna reguła na wszystkie cztery rodzaje: **grot pokazuje skutek**.

| Zapis w notatce                    | Znaczy                                             |
| ---------------------------------- | -------------------------------------------------- |
| `**Requires**: [[quest]]`          | quest **ukończony** -> ten quest **odblokowany**   |
| klucz `Qxx_S00` (parasol)          | wątek **odblokowany** -> jego krok **odblokowany** |
| `` **Requires**: `visited(...)` `` | rozmowa **odbyta** -> quest **odblokowany**        |
| `` **Test**: `visited(...)` ``     | rozmowa **odbyta** -> quest **zamknięty**          |
| `` **Test**: `quest_done(...)` ``  | quest **ukończony** -> ten quest **zamknięty**     |

Dwie ostatnie to **krawędzie zamykające** i one jedyne wracają **łukiem w lewo**: quest otwiera się wcześniej, niż to, co go zamyka, więc jego koniec leży dalej w prawo niż on sam. Łuk odsuwa je od szkieletu odblokowań, żeby powrót było widać kształtem, zanim się przeczyta kolor.

Do tego dwa znaki na krawędzi:

- **poprzeczka** zamiast grotu: warunek zanegowany (`not`),
- podpis **`lub`**: wystarczy jeden z tych warunków, nie wszystkie.

W prawo znaczy później, więc cały obrazek skanuje się jak kolejność rozgrywki. Przycisk **Zamknięcia** w pasku chowa rozmowy razem z łukami - zostaje sam szkielet odblokowań, i to jest widok, w którym najłatwiej prześledzić kolejność. Podwójny klik w sześciokąt otwiera kwestię w notatce postaci - to najszybszy sposób sprawdzenia, czy quest wisi na węźle, który faktycznie da się osiągnąć.

Pełnego wyrażenia graf nie oddaje (i nie próbuje): zagnieżdżone `and`/`or` zostają w dymku questa, w oryginalnym zapisie.
