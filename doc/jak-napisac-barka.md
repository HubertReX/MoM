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
- [time_of_day("morning")] O tej porze to tylko ja i myszy.
- [time_of_day("evening")] Ostatnia kolejka! Żartowałem.
- [sentiment > 60] O, mój ulubiony klient!
- [quest_done("Q01_S01_LEARN_ABOUT_CURSE")] Siadaj tam. Dalej. Jeszcze dalej.
```

W `Barki.md` nagłówek sekcji **jest kluczem puli**, w `SCREAMING_SNAKE`, bez spacji
i bez polskich znaków - jak każdy klucz encji. Proza pod nagłówkiem jest dla autora
i nie trafia do gry; liczą się tylko wypunktowania.

```markdown
## VILLAGERS

Pula dla mieszkańców bez własnego pliku postaci.

- [time_of_day("morning")] Dzień dobry.
- [activity("stand")] Robota sama się nie zrobi.

## FARM_ANIMALS

- Muuu.
- Mu?
```

## Warunki

Zakres `bark` zna to, co dialog, plus trzy rzeczy o świecie:

| Warunek                                              | Znaczenie                         |
| ---------------------------------------------------- | --------------------------------- |
| `time_of_day("morning"/"day"/"evening"/"night")`     | pora dnia na zegarze świata       |
| `activity("sleep"/"stand"/"wander"/"patrol"/"idle")` | co mówiący akurat robi wg rutyny  |
| `on_map("KLUCZ_MAPY")`                               | na której mapie stoi mówiący      |
| `sentiment > 60`                                     | sentyment **mówiącego** do gracza |
| `visited("WĘZEŁ")`, `visited("POSTAĆ", "WĘZEŁ")`     | czy węzeł dialogu był odwiedzony  |
| `has_item("KLUCZ")`, `item_count("KLUCZ") >= 2`      | ekwipunek gracza                  |
| `quest_done("KLUCZ")`                                | czy quest ukończony               |

Łączy się je przez `and`, `or`, `not` i nawiasy. Bez warunku bark leci zawsze.

**Nie myl `time_of_day` z `activity`.** Zegar mówi, która jest godzina na świecie;
`activity()` mówi, co robi **ta** postać. Barman ma lunch o innej porze niż Bart,
więc bark „głodny" to `activity("wander")` na slocie `type:social`, a nie
`time_of_day("day")`.

**`selected()` nie działa w barku** - bark nie jest częścią rozmowy, więc „którą
opcję wybrałeś" nie ma tu znaczenia. Import odrzuci taki warunek.

### „Wieś wie o klątwie"

To nie jest osobny przełącznik świata, tylko quest: `quest_done("Q01_S01_LEARN_ABOUT_CURSE")`.
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
