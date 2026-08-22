---
name: tiled-map
description: Tworzenie i poprawianie map terenów zewnętrznych (.tmx) w MoM - wioski, miasta, lasy, bagna. Generuje mapę z opisu słownego, przenosi i przestawia fragmenty istniejącej mapy z zachowaniem wszystkich warstw, sprawdza mapę linterem i ogląda render, żeby naprawić błędy wyglądu. Używaj, gdy pada prośba o "nową mapę", "wygeneruj wioskę", "przesuń dom", "popraw mapę", "narysuj las", albo gdy pojawia się plik .tmx z katalogu maps/.
---

# Mapy Tiled - generowanie i poprawianie

Mapa terenu zewnętrznego w MoM to **dwanaście warstw w wiążącej kolejności**, a nie obrazek.
Zanim cokolwiek zrobisz, przeczytaj [`reference/map-contract.md`](reference/map-contract.md) -
tam jest kontrakt wyczytany z kodu gry i lista pułapek, na które łatwo wejść dwa razy.

## Zasada podziału pracy

**Ty piszesz BRIEF, kod robi GEOMETRIĘ.** Brief wyraża zamiar ("droga wije się ze wschodu na
zachód, po obu stronach zagrody, dookoła las"). Nie wypisujesz w nim współrzędnych każdego
domu - od tego jest generator, który widzi teren, drogę i to, co już stoi.

Odwrotnie jest z obrysami klocków: to decyzja graficzna i podejmuje ją **autor**, myszą, w Tiled.
Twoją rolą jest zgłosić brak ("katalog nie ma klocków `kind=undergrowth`"), a nie dorysowywać.
Instrukcja dla autora: [`reference/stamps-tiled.md`](reference/stamps-tiled.md).

## Kiedy kafle nie chcą się złożyć - szukaj wangsetu, nie heurystyki

Jeśli coś ułożonego z kafli wygląda na porwane (ścieżka w koralikach, płot z uskokami),
**nie dokładaj reguły do kodu** - najpierw sprawdź, czy tileset ma na to wangset i czy jest
właściwego TYPU. `corner` opisuje obszary, `edge` opisuje pasma szerokie na jeden kafel;
użycie narożnikowego do pasma nie da się poprawić żadnym doborem wariantów, bo brakującej
informacji po prostu w nim nie ma. Tabela obu zestawów z `Floor.tsx` jest w
[`reference/map-contract.md`](reference/map-contract.md).

Uczenie się z próbki narysowanej w warstwie `stamps` jest tylko poszlaką: na zakręcie Tiled
dokłada do próbki kafle OBSZAROWE i dekoder nie ma jak odróżnić ich od kafli pasma. Wangset
jest umową autora i wygrywa z próbką.

Gdy brakuje kafla na jakiś układ - **zapytaj autora, nie zgaduj**. Autor odczyta id z Tiled
w kilkanaście sekund, a najtańszy sposób zapytania to zrzut: wyrenderuj wszystkie układy,
które są, i zaznacz puste miejsca (tak powstała tabela `path Set`).

## Nazwy nadawaj od razu w wymaganym formacie

Nazwa obiektu to **klucz encji**, nie etykieta - pełna tabela formatów jest w
[`reference/map-contract.md`](reference/map-contract.md). Nazwa "jakaś sensowna" kosztuje
tyle, że `just validate-world` sypie kilkunastoma błędami naraz, i to dopiero po tym, jak
autor nada mapie docelową nazwę: `COW_FARMSTEAD_BIG_01` ma brzmieć `COW_01` (D1/D2), a
`SMITHY_DOOR` - `JACOBS_CHAMBER`, czyli tak jak mapa, do której prowadzi (D6).

Generator robi to sam (`pass_names`), a `just map-lint` sprawdza to tymi samymi regułami,
co `validate-world`. **Jeśli sam dopisujesz obiekt do briefu albo do `.tmx`, trzymaj się
tej samej konwencji** - inaczej wracasz do niej po dwóch krokach.

## Strefy po zmianie rozmiaru mapy albo przesunięciu

`rect` strefy jest w **bezwzględnych kaflach**, więc jako jedyny element briefu nie
przelicza się razem z mapą, a `map-edit move` zabiera strefę tylko wtedy, gdy jej lewy
górny róg wpadł do przenoszonego prostokąta. Po każdej zmianie `size` w briefie i po
każdym `move` **sprawdź strefy**: `just map-lint MAPA --only zone`.

Objaw z pierwszej mapy: po zejściu z 256x256 na 256x128 strefa `plains` została na
tych samych kaflach, a tymi kaflami był już pas lasu obrzeżnego - 49% kafli chodliwych
zamiast 91%. Gra wczytuje taką strefę bez słowa, a NPC z `allowed_zones` po prostu nie
ma się w niej gdzie ruszyć. Linter i generator mierzą to teraz same, ale **nowe położenie
`rect` wybierasz ty** - z rendera, a nie z głowy.

## Narzędzia

```bash
just map-palette list                       # co jest w katalogu klocków
just map-palette sheet --out /tmp/k.png     # arkusz kontaktowy do obejrzenia
just map-new brief.toml                     # generowanie z briefu -> maps/_wip/
just map-lint MAPA                          # kontrakt + logika + metryki wyglądu
just map-render MAPA --overview             # cała mapa, do oceny kompozycji
just map-render MAPA --crop X,Y,W,H         # wycinek 1:1, do oceny detalu
just map-render MAPA --overlay reach        # co jest nieosiągalne
just map-edit MAPA move --rect X,Y,W,H --by DX,DY
```

## Workflow A: nowa mapa z opisu

1. **Przeczytaj katalog klocków** (`just map-palette list`). Nie planuj budynku, którego
   nie ma - zgłoś autorowi, że trzeba go dorysować, i wskaż mu
   [`reference/stamps-tiled.md`](reference/stamps-tiled.md): tam jest procedura
   dodawania klocka w Tiled i pełna tabela właściwości.
2. **Sprawdź, czego wymaga fabuła** - [`reference/lore.md`](reference/lore.md). Dla wioski
   Gafowo Kolonia to twarde wymagania (gracz budzi się w stajni, chałupa Zielarki na skraju
   przy lesie, skrzynia kota za zniszczalnymi krzakami), a nie klimat.
3. **Napisz brief TOML** - wzór w [`reference/brief-example.toml`](reference/brief-example.toml).
   Ustal ziarno jawnie, żeby dało się wrócić do tej samej mapy.
4. **`just map-new brief.toml`** - mapa ląduje w `maps/_wip/`, NIGDY w `maps/`.
   Przeniesienie do gry to osobna decyzja autora.
5. **Pętla weryfikacji** (patrz niżej).
6. **Raport braków** - wypisz, co trzeba dopisać w `characters.csv`, `routines.toml`,
   `locale/{PL,EN}.toml` i `audio.toml`. Tych plików NIE edytujesz sam.

## Workflow B: poprawka istniejącej mapy

1. **Zobacz, co przenosisz**, zanim to przeniesiesz:
   `just map-render MAPA --crop X,Y,W,H --scale 3`.
2. **Dobierz prostokąt tak, żeby obejmował całość rzeczy** - dom RAZEM z płotem, progiem
   i kaflem przed drzwiami. Prostokąt przecinający płot zostawia pół płotu w starym miejscu;
   linter tego nie złapie (przerwany płot jest chodliwy), a render pokazuje od razu.
3. **`just map-edit MAPA move --rect ... --by ...`** - narzędzie samo przenosi kafle na
   sześciu warstwach i obiekty na sześciu, zasypuje dziurę próbką z otoczenia, przestawia
   interaktywne obiekty stojące w miejscu docelowym i wypisuje, co przestawiło.
4. **Przeczytaj raport.** Ostrzeżenie o osieroconym `entry_point` znaczy, że rozerwałeś parę
   drzwi-punkt powrotu - rozszerz prostokąt i powtórz, zamiast zostawić to graczowi.
   Ostrzeżenie o strefie znaczy, że pod nią zmienił się teren, a ona została - przesuń ją
   osobno (`map-edit` nie zgaduje, gdzie ma być).
5. **Pętla weryfikacji.**

## Pętla weryfikacji (rdzeń skilla)

Powtarzaj **najwyżej trzy razy** na daną kategorię problemu:

1. **`just map-lint MAPA`** - to on mówi, GDZIE patrzeć. Bez tego oglądanie mapy 256x256
   jest nieopłacalne: to obraz 4096x4096 px, który przy odczycie schodzi do ~6 px na kafel.
   Linter zna reguły nazw (D1/D2/D6) i mierzy strefy, więc **`map-lint` bez błędów znaczy,
   że `validate-world` też przejdzie** - nie zostawiaj tego na koniec.
2. **`--overview`** - oceń KOMPOZYCJĘ: czy droga się wije, czy plac jest owalny, czy pola
   nie stoją w idealnej kratce, czy las domyka mapę.
3. **`--crop` w skali 1:1** - tylko tam, gdzie linter coś zgłosił albo overview budzi
   wątpliwość. Kafel ma wtedy pełne 16 px i widać wszystko.
4. **Nakładki**, gdy coś nie gra z dostępnością: `--overlay reach` (czerwone = chodliwe,
   ale odcięte), `--overlay cost`, `--overlay detail`.
5. **Popraw operacjami z `map-edit`**, nie przez generowanie na nowo z innym ziarnem.
   Nowe ziarno przemebluje całą wieś, żeby naprawić jeden kafel.

Jeśli po trzeciej iteracji ten sam problem wraca - **przestań zgadywać**, pokaż autorowi
render i zapytaj. Zapętlenie na jednym kafelku to najdroższy sposób spędzenia sesji.

### Co znaczą poziomy w raporcie

| Waga | Znaczenie | Co robisz |
|---|---|---|
| `ERROR` | gra tego nie wczyta albo NPC nie powstanie | naprawiasz, zanim oddasz mapę |
| `WARN` | działa, ale gorzej (monotonia, cisza zamiast muzyki) | naprawiasz albo świadomie zostawiasz i mówisz o tym |
| `INFO` | potwierdzenie, że coś jest obsłużone | nic |

Skrzynia osiągalna dopiero po zniszczeniu krzaków to `INFO`, a nie błąd - tak wygląda
zamierzony projekt questa Q04_S01.

## Budżet, o którym trzeba pamiętać

Rozmiar mapy prawie nic nie kosztuje na klatkę (zmierzone: 128x128 daje 0,65 ms, 256x256
daje 0,69 ms; dominuje liczba NPC-ów). **Kosztuje długość trasy A\***: na tej samej siatce
30 kafli to 0,7 ms, 90 kafli - 7,9 ms, a 134 kafle - 20 ms, czyli więcej niż cała klatka
przy 60 FPS. Dlatego dwa miejsca z warstwy `places`, które łączy jedna rutyna, mają leżeć
bliżej niż **110 kafli** od siebie. Linter to sprawdza (`check_routine_routes`), ale lepiej
zaplanować to w briefie: rozrzuć miejsca wokół centrum, a nie po przeciwnych rogach.

## Czego skill NIE robi

- nie edytuje `characters.csv`, `routines.toml`, `locale/*.toml` ani `audio.toml` -
  wypisuje, co dopisać, i zostawia to autorowi,
- nie stawia spawnu postaci, której nie ma w `characters.csv`,
- nie przenosi mapy z `_wip/` do `maps/` - to decyzja autora,
- nie dorysowuje klocków do katalogu - zgłasza brak.
