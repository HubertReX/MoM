# Jak napisać barka

Bark to jednolinijkowa zaczepka, którą postać rzuca, gdy Malachi przechodzi obok.
**Nie jest dialogiem**: gracz nie odpowiada, nie ma opcji, nie ma panelu. To tekst
z obrysem rysowany nad głową, w przestrzeni świata - jak imię pod postacią,
tylko wyżej.

Bark jest **tłem, nie wiadomością**. Z tego jednego zdania wynika reszta: kwestia,
która nie zmieściła się w limicie dwóch naraz, po prostu przepada, a milczenie
jest stanem domyślnym.

## Gdzie się pisze

Dwa miejsca, i one się **sumują**, a nie wykluczają:

| Kto                                           | Gdzie                               |
| --------------------------------------------- | ----------------------------------- |
| postać z własnym plikiem (`doc/PL/Postacie/`) | sekcja `## Barki` w tym pliku       |
| statyści i zwierzęta                          | wspólna pula w [Barki](PL/Barki.md) |

Postać może mieć jedno i drugie. Barman ma swoje żarty **i** mówi „dzień dobry"
jak każdy inny mieszkaniec - gdyby pula wykluczała własne linie, każda postać
z choćby jednym własnym barkiem musiałaby mieć przepisany cały komplet.

Kto bierze z której puli, mówi kolumna `barks` w `project/config_model/characters.csv`;
jej wartością jest nagłówek sekcji z `Barki.md`, dosłownie. Pusta komórka nie jest
błędem - taka postać po prostu milczy.

Po każdej zmianie: `just import-dialogs`.

## Format wiersza

Każdy bark to jedno wypunktowanie (`-` albo `*`). Opcjonalny nawias kwadratowy
**na początku** to warunek.

```markdown
## Barki

- Kufle same się nie umyją.
- [`time_of_day("morning")`] O tej porze to tylko ja i myszy.
- [`time_of_day("evening")`] Ostatnia kolejka! Żartowałem.
- [`sentiment > 60`] O, mój ulubiony klient!
- [`quest_done(`[[Q01_S01 Dowiedz się więcej o klątwie]]`)`] Siadaj tam. Dalej. Jeszcze dalej.
```

W `Barki.md` nagłówek sekcji **jest kluczem puli**, w `SCREAMING_SNAKE`, bez spacji
i bez polskich znaków - jak każdy klucz encji. Proza pod nagłówkiem jest dla autora
i nie trafia do gry; liczą się tylko wypunktowania.

```markdown
## VILLAGERS

Pula dla mieszkańców bez własnego pliku postaci.

- [`time_of_day("morning")`] Dzień dobry.
- [`activity("stand")`] Robota sama się nie zrobi.

## FARM_ANIMALS

- Muuu.
- Mu?
```

**Własna sekcja waży więcej niż pula.** Gdy w danej chwili pasuje coś z obu stron,
gra najpierw rzuca kością o ŹRÓDŁO (`BARK_OWN_SECTION_CHANCE` w `settings.py`,
domyślnie 0,7 na rzecz własnej sekcji), a dopiero potem losuje linię w wybranym
źródle. Bez tego o wadze decydowałaby długość puli: 5 własnych linii Barmana
wobec 13 linii `VILLAGERS` znaczyło, że własnym głosem mówi raz na pięć odezwań.
Wniosek dla piszącego: **nie trzeba dopisywać postaci dziesięciu linii, żeby ją
usłyszeć** - wystarczy, że ma choćby jedną pasującą.

## Warunki

To **cały** słownik warunków w grze - te same nazwy działają w opcjach dialogowych
i w questach, więc nie ma po co skakać między plikami. Kolumna „gdzie" mówi, w czym
wolno użyć danej nazwy: `bark` = ten plik, `dialog` = opcja dialogowa w pliku
postaci, `quest` = `Test:` i `Postęp:` w pliku misji.

| Warunek                                              | Gdzie               | Znaczenie                                                       |
| ---------------------------------------------------- | ------------------- | --------------------------------------------------------------- |
| `time_of_day("morning"/"day"/"evening"/"night")`     | bark                | pora dnia na zegarze świata (granice 6/9/17/20)                 |
| `activity("sleep"/"stand"/"wander"/"patrol"/"idle")` | bark                | co mówiący akurat robi wg rutyny                                |
| `at("type:work")`, `at("location:Tavern")`           | bark                | **który krok rutyny** akurat trwa (pole `at` z `routines.toml`) |
| `on_map("KLUCZ_MAPY")`                               | bark                | na której mapie stoi mówiący                                    |
| `sentiment > 60`                                     | bark, dialog        | sentyment **mówiącego** do gracza (liczba 0-100)                |
| `visited("WĘZEŁ")`                                   | bark, dialog        | czy gracz był w tym węźle u **mówiącego**                       |
| `visited("POSTAĆ", "WĘZEŁ")`                         | bark, dialog, quest | …u wskazanej postaci (w queście **obowiązkowe** dwa argumenty)  |
| `has_item("KLUCZ")`                                  | bark, dialog, quest | czy gracz ma przedmiot                                          |
| `item_count("KLUCZ") >= 2`                           | bark, dialog, quest | ile sztuk ma gracz (liczba)                                     |
| `quest_done("KLUCZ")`                                | bark, dialog, quest | czy quest ukończony                                             |
| `selected("KLUCZ_OPCJI")`                            | dialog              | którą opcję gracz wybrał w tej rozmowie                         |

Łączy się je przez `and`, `or`, `not` i nawiasy. Liczby (`sentiment`, `item_count`) porównuje się przez ` ==`, `!=`, `<`, `<=`, `>`, `>=`. Bez warunku bark leci zawsze.

### Zapis warunku: backquote'y i wikilinki

Cały warunek zamyka się w **backquote'ach**, a odwołanie do encji pisze się w środku jako **prawdziwy wikilink**, przeplatany z backquote'ami - dokładnie tak samo jak w plikach misji:

```markdown
- [`on_map(`[[Tawerna Brakująca klepka|Tawerna]]`)`] Ależ tu śmierdzi
- [`quest_done(`[[Q01_S01 Dowiedz się więcej o klątwie]]`)`] O, idzie nasz pechowiec
```

Dzięki temu jeden zapis jest naraz warunkiem dla silnika i **krawędzią w grafie Obsidiana**: widać, że ten bark zależy od tego questa, bez czytania pliku. Import zdejmuje backquote'y i zamienia linki na klucze, więc `config.json` dostaje to, co zawsze.

Co da się zlinkować, a co nie:

| W warunku                          | Zapis w notatce                                                | Wychodzi z importu                        |
| ---------------------------------- | -------------------------------------------------------------- | ----------------------------------------- |
| węzeł **innej** postaci            | `` `visited(`[[Barman Absyntnent#012]]`)` ``                   | `visited("BARMAN_ABSINTHRAYNER", "012")`  |
| węzeł **mówiącego** (tylko dialog) | `` `visited(`[[#005]]`)` ``                                    | `visited("005")`                          |
| mapa                               | `` `on_map(`[[Gafowo Kolonia]]`)` ``                           | `on_map("BLUNDERHAVEN")`                  |
| quest                              | `` `quest_done(`[[Q01_S01 Dowiedz się więcej o klątwie]]`)` `` | `quest_done("Q01_S01_LEARN_ABOUT_CURSE")` |
| przedmiot                          | `` `has_item(`[[Łza Syrenki]]`)` ``                            | `has_item("MERMAIDS_TEAR")`               |
| opcja dialogowa, pora dnia         | `` `selected("007to008_1")` ``                                 | bez zmian                                 |

Klucze opcji dialogowych i pory dnia **nie mają własnych notatek**, więc zostają zwykłym napisem w cudzysłowie - pisze się je dokładnie tak, jak brzmią (`007to008_1`, `"morning"`). Wariant z aliasem (`[[Notatka#012|Barman#012]]`) w tabeli nie stoi z jednego powodu: pionowa kreska rozbiłaby komórkę - w treści notatek jest jak najbardziej w porządku.

Link do notatki, której w vaulcie nie ma, to **błąd importu z numerem linii**. To jest ta różnica, która się liczy: literówka w nazwie postaci przestaje być warunkiem, który nigdy nie zapala, i staje się czerwonym komunikatem przy `just import-dialogs`.

Stary zapis (`Potioneer_Puzzlemint.004.visited`, `character.sentiment`, gołe stringi) **nadal się importuje** - plik, którego nikt nie ruszał, ma działać. Tyle że nie rysuje się w grafie, więc przy okazji edycji warto go przepisać.

Wszystko poza tą tabelą jest odrzucane przy imporcie z numerem linii: nie ma
odwołań do pól gry (`scene.hour`), indeksów, wywołań w wywołaniu ani zmiennych.
Literówkę w **kluczu** łapie `just validate-world` (reguła 20) - i to jest ważne,
bo sam warunek z literówką jest składniowo poprawny, tylko nigdy nie zapala.

**Nie myl `time_of_day` z `activity`.** Zegar mówi, która jest godzina na świecie;
`activity()` mówi, co robi **ta** postać. Barman ma lunch o innej porze niż Bart,
więc bark „głodny" to `activity("wander")` na slocie `type:social`, a nie
`time_of_day("day")`.

**`at()` to krok dnia, `activity()` to czynność.** `activity("stand")` znaczy tylko
tyle, że postać stoi - tak samo barman za barem, kowal przy kowadle i Bart przy
straganie. Dopiero `at()` mówi, KTÓRY to krok rutyny: wartość jest **dosłownie
tym, co stoi w polu `at`** danego kroku w `config_model/routines.toml`, razem
z rodzajem:

```markdown
- [`at("type:work")`] Robota sama się nie zrobi.
- [`at("type:social")`] W końcu chwila przerwy.
- [`at("type:home") and time_of_day("evening")`] Nogi mnie bolą.
- [`at("location:Tavern")`] Tu zawsze pachnie tak samo.
```

Skrót bez rodzaju (`at("work")`) **nie zadziała** i `just validate-world` powie
to wprost - tak samo jak przy literówce (`at("type:wrok")`). Postać bez rutyny
nie pasuje do żadnego `at(...)` i to nie jest błąd; po prostu milczy na takich
liniach.

**`selected()` nie działa w barku** - bark nie jest częścią rozmowy, więc „którą
opcję wybrałeś" nie ma tu znaczenia. Import odrzuci taki warunek.

### „Wieś wie o klątwie"

To nie jest osobny przełącznik świata, tylko quest: `quest_done(`[[Q01_S01 Dowiedz się więcej o klątwie]]`)`.
Ten sam warunek działa w barku i w opcji dialogowej, więc cała wieś reaguje na
jedną rzecz. Skasowanie albo przemianowanie tego questa wyłączy te reakcje -
pilnuje tego reguła 20 walidatora (`just validate-world`), nie ten akapit.

## Limit długości

Bark musi się zmieścić w **dwóch liniach po 28 znaków**. Dłuższy to twardy błąd
przy `just import-dialogs`, z numerem linii. Tagi RichText i `:emote:` nie liczą
się do limitu - nie zajmują pikseli.

## Trzy rzeczy, które zaskakują

1. **Nawias na początku wiersza to ZAWSZE warunek.** Bark zaczynający się od tagu
   (`[shadow]Grubo[/shadow]…`) wywali import. Przestaw go tak, żeby zaczynał się
   od słowa. Zgadywanie („czy to wygląda na warunek?") robiłoby z literówki cichy
   tekst, czyli dokładnie ten cichy `False`, przed którym cały ten import broni.
2. **Plik EN musi mieć tyle samo wypunktowań, co PL.** PL jest źródłem prawdy dla
   warunków i kolejności; EN dostarcza wyłącznie tłumaczenie. Rozjazd liczby to
   błąd importu - inaczej dwa pliki po cichu opisywałyby różne zachowanie.
3. **Ta sama kwestia nie poleci dwa razy pod rząd** u jednej postaci. Nie musisz
   tego obchodzić powtórzeniami; potrzebujesz tylko co najmniej dwóch linii,
   żeby było z czego wybierać.

## Jak często to słychać

Postać milczy 60 sekund po swoim barku, a cała wieś 8 sekund po dowolnym; naraz
widać najwyżej dwa. Poza tym bark odpala się na dwa sposoby: gdy gracz wejdzie
blisko (z rzutem kością, żeby wieś nie tykała jak zegarek) i gdy postaci właśnie
zmienił się krok dnia - wtedy z dalszej odległości i bez rzutu, bo ma konkretny
powód, żeby się odezwać.

Nastawy siedzą w `settings.py` (`BARK_*`) i są do dokręcenia na żywym ekranie.

## Emoji nad głową to osobny kanał

Emoji i barki tekstowe nie zastępują się nawzajem - to dwa niezależne kanały.
Emoji opisuje **krok dnia**, więc pisze się je w slocie rutyny
(`project/config_model/routines.toml`, pole `emotes`), a nie tutaj. Szczegóły
w komentarzu na górze tamtego pliku.
