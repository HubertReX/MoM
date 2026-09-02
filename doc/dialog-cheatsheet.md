---
tags: [sciagawka, dialogi]
---

# Dialogi - ściągawka

> [!warning] Wygenerowane przez `scripts/gen_dialog_cheatsheet.py` (`just gen-dialog-cheatsheet`).
> Nie edytuj ręcznie - emoji sentymentów, predykaty warunków, czasowniki efektów i znaczniki tekstu są wyprowadzone z kodu, więc nie mogą rozjechać się z tym, co robi import i silnik.

> [!important] Jeden plik = jedna postać, a rozmowa to graf
> Węzeł (`## 000`) to **kwestia postaci**, opcja pod nim to **odpowiedź gracza** i zarazem krawędź do następnego węzła. Panel pokazuje jeden węzeł naraz; rozmowa kończy się na węźle z sufiksem `-end` albo tam, gdzie żadna opcja nie przeszła warunku.

## Szablon postaci

**PL** (`doc/PL/Postacie/<Nazwa postaci>.md`) jest źródłem prawdy dla logiki i metadanych;
**EN** (`doc/EN/Characters/<Character name>.md`) trzyma ten sam graf z samą prozą po angielsku.

```markdown
---
aliases:
  - ZIELARKA_ZMORA
  - Zielarka
EN: "[[Potioneer Puzzlemint]]"
location: "[[Gafowo Kolonia]]"
sprite: Hunter
friendly: 0.5
kind: 1
weak: -1
angry: -2
smart: 2
funny: 1
---
# Info

## Tło historyczne

Notatki autorskie. Importer zaczyna czytać dopiero od pierwszego numerycznego
nagłówka, więc proza i podsekcje `# Info` nigdy nie kolidują z węzłami.

## Barki

- Zioła same się nie posieją.

## 000

* Witaj w [[Tawerna Brakująca klepka|Tawernie]]. Czego szukasz:question:

* [[#001]] 1😇: Szukam lekarstwa na _klątwę_.
* [[#002]] 2[`visited(`[[Barman Absyntnent#012]]`)`]🧠: [[Barman Absyntnent|Barman]] mówił, że **Ty** wiesz więcej.
* [[#990-end]] 9😐: Nic, tak tylko zaglądam.

## 001

* [`add_n_items(1,`[[Łza Syrenki]]`)`] Weź to i nie pytaj, skąd mam.

* [[#990-end]] 1😐: Dzięki:blink:

## 002

* [`shift_sentiment(-10)`] Barman gada, a ja pracuję.

* [[#990-end]] 1😐: Rozumiem.

## 990-end
[[#001]]

* Wracaj, gdy będziesz gotów.
```

Oba pliki muszą mieć **te same numery węzłów i tyle samo opcji w każdym węźle** - inaczej import odmawia. Nazwa pliku to nazwa postaci w danym języku, a klucz żyje wyłącznie w `aliases`, więc zmiana nazwy pliku nie psuje żadnego warunku.

## Frontmatter

| Pole                                      | Znaczenie                                                                                                              | Obowiązkowe |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ----------- |
| `aliases`                                 | **klucz postaci** (`SCREAMING_SNAKE`) - pierwszy alias pisany wielkimi literami; dalsze aliasy to skróty do linkowania | tak         |
| `sprite`                                  | katalog assetów z `NinjaAdventure/characters/`                                                                         | tak         |
| `friendly`                                | startowa sympatia 0..1 (`NPC.sentiment = friendly * 100`)                                                              | nie         |
| `kind`, `weak`, `angry`, `smart`, `funny` | wagi sentymentów (-2..2) - o tyle zmienia się sympatia po wyborze opcji z tym emoji; brak pola = wartość domyślna      | nie         |

Pozostałe pola (`EN`, `location`, `inspirations`, `alternative`) importer ignoruje - są dla Obsidiana i dla autora. **Frontmatter PL jest źródłem prawdy**; kopię w EN synchronizuje skill `dialog-en-sync`.

## Sentymenty - emoji na końcu opcji

Emoji nie jest ozdobą: mówi, **jak** gracz to powiedział, i o tyle zmienia sympatię postaci. Wagę można nadpisać per postać we frontmatterze.

| Emoji | Nazwa       | Domyślna waga | Ikonka        | Ton odpowiedzi                                         |
| ----- | ----------- | ------------- | ------------- | ------------------------------------------------------ |
| 😇    | `kind`      | `+1`          | `:blessed:`   | życzliwie                                              |
| 😢    | `weak`      | `-1`          | `:offended:`  | żałośnie                                               |
| 😐    | `neutral`   | `0`           | `:neutral:`   | rzeczowo                                               |
| 😡    | `angry`     | `-2`          | `:angry:`     | gniewnie                                               |
| 🧠    | `smart`     | `+1`          | `:wondering:` | z głową                                                |
| 😉    | `funny`     | `+1`          | `:blink:`     | żartem                                                 |
| 🤖    | `technical` | `0`           | `:human:`     | techniczne (nie postawa gracza, tylko obsługa rozmowy) |

Sympatia (0..100) rządzi cenami w handlu i warunkami `sentiment > n`, więc opcja „grubiańska" ma realny koszt. `technical` i `neutral` mają wagę zero z założenia - to opcje, które tylko przewijają rozmowę.

## Węzeł - `## numer`

Klucze węzłów są **wyłącznie cyframi**, dlatego nagłówki prozy (`## Cechy charakteru`, `## Barki`) nigdy z nimi nie kolidują - importer po prostu ich nie widzi.

- **Pierwszy węzeł w pliku jest węzłem startowym.** Nie ma osobnego pola: to, co stoi najwyżej, otwiera rozmowę.
- **Tekst węzła** zaczyna się od `* ` i może się ciągnąć przez wiele linii. Pusta linia = nowy akapit; kolejne linie bez pustej linii sklejają się w jeden.
- **`-end` w nagłówku** (`## 990-end`) znaczy „tu rozmowa się kończy": panel pokazuje kwestię i czeka na Accept, opcji nie wyświetla. Opcja na węźle `-end` jest błędem importu.
- **Link pod nagłówkiem `-end`** (`[[#001]]` w osobnej linii) to **resume**: następna rozmowa z tą postacią zacznie się od tego węzła zamiast od startowego. Tak się pisze „przywitanie tylko raz".
- Opcja wskazująca węzeł końcowy pisze się z sufiksem (`[[#990-end]]`) - importer sam go zdejmuje, a link zostaje klikalny w Obsidianie.
- **`-entry` w nagłówku** (`## 002-entry`) znaczy „do tego węzła wchodzi się z mapy": wskazuje go wyzwalacz na warstwie `interactions` w Tiled. Sufiks, jak `-end`, mówi o obchodzeniu się z węzłem, a nie o jego kluczu - klucz to nadal `002`.

## Wejście z mapy - `## numer-entry`

Scena może zacząć się bez naciskania spacji: wejściem gracza na wskazany obszar mapy albo próbą wyjścia z okolicy. Obiekt w Tiled mówi **gdzie**, notatka postaci mówi **kiedy**.

```markdown
## 002-entry
[`not quest_done(`[[Q01_S01 Kto wie więcej o klątwie]]`)`]

* Nie ruszysz się stąd, póki nie pogadasz z [[Barman Absyntnent|Barmanem]].

* [[#990-end]] 1😐: No dobrze.
```

- **Linia pod nagłówkiem** to **warunek wejścia** - ta sama gramatyka, co w warunku opcji (backquote'y, wikilinki, `sentiment`, `visited()`). Brak linii znaczy „zawsze".
- Węzeł `-entry` jest **zwolniony z reguły węzła-sieroty**: krawędź do niego prowadzi z mapy, a importer widzi tylko graf. Że wyzwalacz naprawdę istnieje, sprawdza `just validate-world` - i on też zgłasza węzeł `-entry`, na który nic nie wskazuje.
- W Tiled na warstwie `interactions`: `obj_type="dialog"` + własność `dialog` = `KLUCZ_POSTACI:WĘZEŁ` (np. `HAMMER_HOAXHEART:002`) to obszar odgrywający scenę. Ta sama własność na obiekcie `obj_type="exit"` **blokuje przejście** na inną mapę, dopóki warunek wejścia jest prawdziwy.
- Scena odgrywa się **raz na wejście** w obszar; zejście z niego uzbraja wyzwalacz ponownie. „Raz na zawsze" pisze się warunkiem `not visited(`[[#002]]`)`, bo odwiedzone węzły i tak siedzą w save.
- Postać z wyzwalacza **nie musi** stać na tej mapie - odezwie się zza kadru. Walidator o tym ostrzega, bo bywa to niezamierzone: dopóki jej własna mapa nie była ani razu wczytana, wyzwalacz milczy.

## Opcje - linia po linii

```markdown
* [[#002]] 3[`sentiment > 60`]😉: A może opowiesz mi o tej [quest]klątwie[/]:question:
```

| Kawałek                | Co znaczy                                                   | Obowiązkowy |
| ---------------------- | ----------------------------------------------------------- | ----------- |
| `* `                   | wypunktowanie - tak zaczyna się **każda** opcja             | tak         |
| `[[#002]]`             | węzeł, do którego opcja prowadzi                            | tak         |
| `3`                    | kolejność na liście - opcje sortują się po tej liczbie      | tak         |
| `` [`visited(...)`] `` | warunek - bez niego opcji nie widać; brak = zawsze widoczna | nie         |
| `😐`                   | sentyment: jak gracz to mówi i o ile zmieni się sympatia    | tak         |
| `: tekst`              | kwestia gracza (dwukropek oddziela ją od reszty)            | tak         |

Klucz opcji składa się sam: `<węzeł>to<cel>_<kolejność>`, czyli powyżej `002to003_3`. Ten klucz widać w save'ach i w warunkach `selected(...)`, więc numer kolejności nie jest kosmetyką - zmieniony przenumerowuje opcję i unieważnia warunek, który się na nią powoływał.

## Warunek opcji

Mini-DSL, nie `eval()`: whitelista dopuszczalnych nazw, wszystko inne to błąd importu z numerem linii. Ta sama gramatyka, co w questach - różni się tylko zestaw nazw.

| Wywołanie                                            | Znaczenie                                                                                    |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| `has_item(`[[Łza Syrenki]]`)`                        | gracz ma przedmiot `ITEM` w ekwipunku                                                        |
| `item_count(`[[Łza Syrenki]]`) >= 3`                 | ile sztuk `ITEM` gracz ma (liczba, nie prawda/fałsz)                                         |
| `quest_done(`[[Q01_S01 Kto wie więcej o klątwie]]`)` | quest `KEY` jest ukończony                                                                   |
| `selected("001to002_3")`                             | gracz wybrał **kiedykolwiek** opcję o tym kluczu u tej postaci                               |
| `visited(`[[#004]]`)`                                | gracz był już w węźle `NODE` - u **tej** postaci (1 argument) albo u wskazanej (2 argumenty) |

**Łączenie**: `and`, `or`, `not`, nawiasy.
**Porównania**: ` ==` `!=` `<` `<=` `>` `>=` `in` `not in`.
Gołe nazwy-wartości: `sentiment` - sympatia **tej** postaci do gracza (0..100).

`visited()` w dialogu bierze **jeden** argument (węzeł u tej samej postaci) albo **dwa** (`NPC`, `NODE`) - inaczej niż w queście, gdzie postać trzeba nazwać zawsze, bo quest nie ma bieżącego rozmówcy.

Warunek zamyka się w **backquote'ach**, a odwołania do encji w środku pisze się **wikilinkami**, przeplatanymi z backquote'ami - jedno wyrażenie jest wtedy naraz warunkiem dla silnika i krawędzią w grafie Obsidiana:

```markdown
* [[#021]] 7[`visited(`[[Zielarka Zmora#009]]`)`]😐: A może ja mogę coś dla **Ciebie** zrobić:question:
```

`[[#005]]` bez nazwy notatki znaczy „węzeł u mówiącego". Link do notatki, której w vaulcie nie ma, to błąd importu z numerem linii - literówka w nazwie postaci nie ma szans dożyć do gry. Stare zapisy (`Potioneer_Puzzlemint.004.visited`, `character.sentiment`, gołe stringi) nadal się importują, ale nie rysują się w grafie.

> [!warning] Niewidoczna opcja nie zamyka rozmowy sama z siebie
> Gdy **wszystkie** opcje węzła odpadną na warunkach, panel kończy rozmowę (auto-end) - gracz nie wisi. Ale to znaczy, że węzeł z samymi warunkowymi opcjami może być ślepym zaułkiem, którego nie widać w tekście. Panel **PROBLEMY** nad grafem wypisuje takie węzły.

## Efekt węzła - co gra robi, gdy gracz tu dotrze

Efekt pisze się **na początku tekstu węzła**, w nawiasie kwadratowym, jako wywołanie w backquote'ach. Aplikuje się **raz**: powtórna wizyta w tym samym węźle nic nie robi.

| Zapis                         | Znaczenie                                                          | Przykład                                                      |
| ----------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------- |
| `add_money(nn)`               | daje graczowi złoto                                                | `` [`add_money(50)`] ``                                       |
| `remove_money(nn)`            | zabiera graczowi złoto                                             | `` [`remove_money(20)`] ``                                    |
| `add_n_items(nn, ITEM, …)`    | daje przedmioty - pierwszy argument to **krotność każdego** z nich | `` [`add_n_items(1,`[[Łza Syrenki]]`)`] ``                    |
| `remove_n_items(nn, ITEM, …)` | zabiera przedmioty (tak płaci się postaci za przysługę)            | `` [`remove_n_items(1,`[[Wąs Gnoma]]`,`[[Łza Syrenki]]`)`] `` |
| `restore_health(nn)`          | leczy bieżące HP                                                   | `` [`restore_health(20)`] ``                                  |
| `lose_health(nn)`             | odbiera HP                                                         | `` [`lose_health(10)`] ``                                     |
| `shift_sentiment(±nn)`        | zmienia sympatię **tej** postaci - jedyny czasownik ze znakiem     | `` [`shift_sentiment(-10)`] ``                                |

Ta sama gramatyka opisuje nagrody questów (`dialog/effects.py`), a nazwy czasowników są nazwami metod `ResultSink` w kodzie - od notatki do kodu prowadzi jedno słowo. Czasowniki `raise_max_health`, `raise_damage`, `raise_max_items`, `shift_sentiment_of` należą **wyłącznie** do nagród questa: rozmowa daje i zabiera, ale nie przebudowuje bohatera na stałe i nie sięga do sympatii kogoś, kto właśnie nie stoi naprzeciwko.

Odrzucane przy imporcie:

- wartość `0` (albo `add_n_items` bez przedmiotu) - to kształt, który nigdy nie jest zamierzony,
- liczba ujemna przy czasowniku, który już mówi, w którą stronę idzie (`add_money(-50)`),
- przedmiot bez wiersza w `items.csv` - notatka istnieje, ale gra nie umie go stworzyć,
- stary zapis kategorią (`[GOLD+50]`) - import mówi wprost, na co go zamienić.

## `[[#trade-end]]` - opcja, która oddaje gracza do sklepu

Postać może być naraz rozmówcą i handlarzem. Spacja zawsze otwiera dialog; do handlu wchodzi się **wybraną opcją**:

```markdown
* [[#trade-end]] 7😐: A co masz na sprzedaż:question:
```

`trade` to zarezerwowany cel - klucze węzłów są cyframi, więc żaden prawdziwy węzeł się z nim nie zderzy. Sufiks `-end` czyta się tak samo jak w nagłówku: „to kończy rozmowę" - tu przez oddanie gracza, nie przez pożegnanie. Zapis bez sufiksu jest twardym błędem importu (jedna gramatyka, nie dwie), a `just validate-world` (reguła 23) zgłasza taką opcję u postaci bez `is_merchant`.

Sentyment liczy się **zanim** panel się przełączy - to ma znaczenie, bo sympatia ustala ceny, które gracz zaraz zobaczy.

## Encje w prozie - pisze się je linkiem

Postać, lokalizację, przedmiot i quest pisze się w kwestii i w opcji **wikilinkiem**; import zamienia go na znacznik, którym gra koloruje encję:

| W notatce                              | W grze                                    |
| -------------------------------------- | ----------------------------------------- |
| `[[Zielarka Zmora]]`                   | `[char]Zielarka Zmora[/char]`             |
| `[[Tawerna Brakująca klepka]]`         | `[loc]Tawerna Brakująca klepka[/loc]`     |
| `[[Łza Syrenki]]`                      | `[item]Łza Syrenki[/item]`                |
| `[[Q01_S01 Kto wie więcej o klątwie]]` | `[quest]Kto wie więcej o klątwie[/quest]` |
| `[[Barman Absyntnent\|Barmana]]`       | `[char]Barmana[/char]` - odmiana z kreski |

Znacznik bierze się z **katalogu notatki**, więc nie trzeba go wybierać, a napis po pionowej kresce niesie odmianę. Link bez kreski pokazuje nazwę notatki w języku pliku, więc `[[Zielarka Zmora]]` w pliku EN wyświetli się jako „Potioneer Puzzlemint".

Znacznikiem wprost pisze się dalej to, co **nie ma notatki**: istoty ze wspomnień, rzeczowniki pospolite, zaimki (`[char]Ty[/char]`). Link do nieistniejącej notatki zostaje w tekście dosłownie i `just validate-world` (reguła 22) uzna to za błąd - gracz zobaczyłby surowe `[[nawiasy]]`.

## Znaczniki tekstu - MoM RichText

Markdownowe wyróżnienia pisze się **po markdownowemu**, a stare znaczniki z RPG-a importer tłumaczy sam:

| Zapis w notatce        | W grze               |
| ---------------------- | -------------------- |
| `[reverse]…[/reverse]` | `[shadow]…[/shadow]` |
| `[red]…[/red]`         | `[error]…[/error]`   |
| `[blue]…[/blue]`       | `[item]…[/item]`     |
| `[yellow]…[/yellow]`   | `[char]…[/char]`     |
| `**pogrubienie**`      | `[shadow]…[/shadow]` |
| `_kursywa_`            | `[italic]…[/italic]` |

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

Emotki wstawia się jako `:nazwa:`, a emoji wpisane wprost w tekst importer zamienia na nie sam - wszystkie 7: 😇 -> `:blessed:`, 😢 -> `:offended:`, 😐 -> `:neutral:` i tak dalej. Pełen arkusz z kluczami:
![[_attachements/mom-emote-sheet.png]]

Paleta znaczników w renderze silnika:
![[_attachements/mom-richtext-tags.png]]

## Barki - jedna linijka nad głową

Sekcja `## Barki` w pliku postaci to zaczepki rzucane, gdy gracz przechodzi obok - **nie** dialog: gracz nie odpowiada, nie ma panelu. Warunek pisze się w nawiasie **na początku** linii, tą samą gramatyką co warunek opcji:

```markdown
## Barki

- Kufle same się nie umyją.
- [`time_of_day("morning")`] O tej porze to tylko ja i myszy.
- [`sentiment > 60`] O, mój ulubiony klient!
```

Barek ma nazwy, których dialog nie ma: `activity()` - co mówiący właśnie robi (krok rutyny), `at()` - dokąd prowadzi bieżący krok rutyny (`type:`, `location:`, `route:`), `on_map()` - na której mapie stoi mówiący, `time_of_day()` - pora dnia w świecie gry. Pory dnia: `morning`, `day`, `evening`, `night`. Nie ma za to `selected()` - barek nie jest częścią rozmowy.

Limit jest twardy i sprawdzany przy imporcie: **2 linie po 28 znaków**. O za długim żarcie autor dowiaduje się z `file:line`, a nie widząc go uciętego w grze.

Pełna instrukcja (wspólna pula w `PL/Barki.md`, kolumna `barks` w `characters.csv`, rytm i limity): [[jak-napisac-barka|Jak napisać barka]].

## Czego import nie przepuści

Import działa na zasadzie **wszystko albo nic**: postać, która się nie zaimportuje, to postać, której nie ma w grze - `config.json` zostaje nietknięty, a błąd wskazuje plik i linię.

| Co                             | Dlaczego to błąd                                                                                                                       |
| ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| węzeł-sierota                  | żadna opcja ani resume na niego nie wskazuje - gracz nigdy go nie zobaczy (węzeł `-entry` jest zwolniony: wchodzi się do niego z mapy) |
| opcja w nieznany węzeł         | literówka w numerze; w grze byłby ślepy skok                                                                                           |
| kotwica ≠ cel                  | `[[#002]]` prowadzące do `003` - link w Obsidianie kłamałby                                                                            |
| duplikat numeru węzła          | dwa `## 007` w jednym pliku                                                                                                            |
| nieznane emoji sentymentu      | sentyment musi być jedną z nazw kanonicznych                                                                                           |
| opcja na węźle `-end`          | węzeł końcowy nigdy nie pokazuje opcji                                                                                                 |
| rozjazd PL/EN                  | inne numery węzłów, inna liczba opcji w węźle albo `-entry` tylko po jednej stronie                                                    |
| link do nieistniejącej notatki | w warunku i w efekcie - twardy błąd, nie ciche `False`                                                                                 |

## Co zrobić po edycji

```bash
just import-dialogs   # kaskada MD -> characters.csv -> config.json; bez argumentu wszystkie postacie
just gen-dialog-graph # graf do doc/_graphs/; bez argumentu wszystkie postacie
just validate-world   # reguły spójności świata (m.in. 22 i 23)
```

Szczegółowa lista kroków: [[Aktualizacja dialogów - checklist]].

## Jak czytać graf

Graf rysuje `scripts/dialog_graph.py` i to na nim widać rzeczy, których w tekście nie widać wcale - większość historycznych bugów dialogów była **własnością grafu**, nie treści.

- **Węzły**: zielony START, pomarańczowy `-entry` (wejście z mapy), czerwony `-end`, żółty z efektem, niebieski zwykły; różowa przerywana obwódka = problem.
- **Krawędzie**: etykieta w kolorze sentymentu (`3 smart`, `2 angry`), przerywana = warunkowa, kropkowana cyjanowa = `resume`.
- **Panel PROBLEMY** nad grafem wypisuje sieroty, ślepe zaułki i węzły z samymi warunkowymi opcjami; kliknięcie centruje kamerę na węźle.
- Klik = podświetl sąsiadów, podwójny klik = otwórz węzeł w źródłowym `.md`, hover = treść, warunek i efekt.

Wymóg jednorazowy: w Obsidianie **Dataview -> Enable JavaScript Queries = on**.
