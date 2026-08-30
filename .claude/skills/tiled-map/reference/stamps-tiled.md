# Jak dodać klocek do katalogu (praca w Tiled)

Katalog klocków żyje w warstwie obiektów **`stamps`** mapy
`project/assets/NinjaAdventure/maps/_wip/BLUNDERHAVEN_base.tmx`. Jeden nazwany
prostokąt = jeden klocek. Skrypt wycina z niego **wszystkie sześć warstw
kafelkowych naraz**, więc dom przenosi się razem z dachem (`over`), progiem
(`foliage`) i kolizją (`walls`) - a nie jako sam obrazek.

## Procedura w interfejsie

1. Otwórz `_wip/BLUNDERHAVEN_base.tmx` i **narysuj element** na normalnych
   warstwach (`ground`, `foliage`, `walls`, `over`, ...), tak jak rysujesz mapę.
2. Zaznacz warstwę **`stamps`** na liście warstw po prawej.
3. Weź narzędzie **Insert Rectangle** (klawisz `R`) i obrysuj element.
   Trzymaj wciśnięty **Ctrl**, żeby prostokąt trzymał się siatki kafli -
   skrypt zaokrągla wymiary do kafli, więc obrys „prawie równy" da przesunięcie.
4. Przełącz się na **Select Object** (`S`), kliknij prostokąt i w panelu
   **Properties** (lewy dolny róg) wpisz **Name** - to jest nazwa klocka.
5. W tym samym panelu, w sekcji **Custom Properties**, klikaj **+** i dodawaj
   właściwości z tabeli poniżej. Typ zostaw `string`, chyba że tabela mówi inaczej.
6. Zapisz i sprawdź: `just map-palette list`, a potem `just map-palette sheet`
   i obejrzyj arkusz kontaktowy.

Warstwę `stamps` możesz ukryć (ikona oka) - generator i tak ją czyta, a gra
w ogóle o niej nie wie, bo prototyp nigdy nie jest ładowany.

## Właściwości

| Właściwość | Typ | Kto tego używa | Znaczenie |
|---|---|---|---|
| **(Name)** | pole nazwy | wszyscy | Nazwa klocka, po niej odwołujesz się w briefie. `snake_case`, bez spacji. Powtórzenie nazwy jest **dozwolone i znaczące** - patrz „Warianty" niżej. |
| `kind` | string | wszyscy | Rodzaj - decyduje, co generator z tym klockiem robi. Wartości w tabeli niżej. **Wymagane.** |
| `door` | string `"dx,dy"` | `building`, `farmyard` | Kafel drzwi (albo bramy zagrody), liczony **od lewego górnego rogu klocka**, od zera. Generator kieruje tu ścieżkę i sadzi na tym kaflu obiekt `exit`. W zagrodzie kafel bramy jest dodatkowo przenoszony z `walls` na `foliage`, żeby dało się przez nią przejść. Brak = element bez wejścia (stóg, stodoła bez drzwi). |
| `anchor` | string | `nature`, `prop` | `bottom` (domyślnie) sadzi klocek dolną krawędzią - tak stawia się budynki. `center` sadzi środkiem - tak rozsypuje się drzewa. |
| `tags` | string | wyszukiwanie | Lista po przecinku, **po angielsku**: `house,village`, `tree,forest`. Służy do grupowania („weź wszystkie `tree`"). |
| `tile` | **bool** | `fence`, `prop` | `true` = klocek wolno powtarzać obok siebie w obie strony (płot, grządka). Domyślnie `false`. |

## Warianty - kilka obrysów o tej samej nazwie

Ta sama nazwa na kilku obrysach to **jeden klocek o kilku wariantach**, a nie
pomyłka. Generator losuje wariant przy każdym postawieniu, więc jedna pozycja
w briefie:

```toml
[[prop]]
stamps = ["decorations", "baskets"]
rect = [70, 30, 46, 48]
density = 0.010
```

rozsypuje po podwórzach wszystkie trzydzieści skrzynek, beczek i koszy, które
narysujesz - bez wypisywania ich po kolei. Tak samo działa `field_crop`: dwa
prostokąty o tej nazwie to dwa gatunki zboża i zagony wypadają na przemian.

Zasady:

- warianty muszą mieć **ten sam `kind`** - grupa jest jednym klockiem,
- w `[[fields]]` liczy się tylko wariant PIERWSZY (z niego bierze się rozmiar
  zagonu); warianty innej wielkości są pomijane, żeby kratka pola się nie rozjechała,
- tam, gdzie brief wskazuje jedną konkretną rzecz (`[[building]] stamp = ...`),
  generator bierze wariant pierwszy - kolejność z pliku `.tmx`,
- `just map-palette list` pokazuje liczbę wariantów przy nazwie; arkusz kontaktowy
  rysuje wariant pierwszy.

## Wartości `kind`

| `kind` | Rozmiar | Co generator z tym robi |
|---|---|---|
| `building` | dowolny | Stawia wzdłuż dróg (`[[district]]`) albo wprost (`[[building]]`). Z `door` dostaje ścieżkę do traktu i wyjście do wnętrza. |
| `fence` | **min. 6x3** | Czyta z niego **zestaw segmentów** i buduje ogrodzenie dowolnego kształtu. Układ obowiązkowy - patrz niżej. |
| `wall` | **min. 6x3** | To samo co `fence`, tylko mur. |
| `nature` | 2x2 - 4x4 | Rozsypuje w biomach (`[[biome]]`) i wciska w pas lasu przy krawędzi mapy. |
| `undergrowth` | **dokładnie 1x1** | Zasypuje luki w ścianie lasu, których nie zapełni całe drzewo. Bez tego generator sięga po awaryjny zestaw krzaków i mówi o tym w raporcie. |
| `prop` | dowolny | Rekwizyty: studnia, stóg, grządka. Stawiane przez `[[prop]]` - w konkretnym miejscu, w zadanej liczbie albo dywanem o zadanej gęstości. |
| `farmyard` | duży | Gotowa zagroda z własnym płotem i inwentarzem. Stawiana wprost przez `[[building]]`, bez dokładania jej zagrody. |
| `pathkit` | dowolny | **Próbka ścieżki** szerokiej na jeden kafel. Narysuj dowolny spójny kształt (proste, zakręty, trójniki, skrzyżowanie) - generator sam policzy, który kafel pasuje do jakiego układu sąsiadów. Z tego robi dojścia do drzwi i bram. |
| `terrain` | duży | **Próbka terenu**, nie klocek. Generator liczy w niej częstość gidów i z tego robi wagi wariantów - malujesz gęściej, częściej wypada. |
| `edge` | mały | Próbka styku dwóch terenów. Dla trawy i ziemi niepotrzebna: `Floor.tsx` ma gotowy wangset. |

## Układ klocka `fence` / `wall`

Zestaw segmentów czyta się **po pozycjach**, więc płot musi być narysowany jako
demo-zagroda dokładnie w tym układzie (tak wyglądają wszystkie trzy istniejące):

```
kolumna:   0    1    2    3   ...  w-2  w-1
wiersz 0:  NW   H    T↓   H   ...  H    NE
wiersz 1:  V    .    V    .   ...  .    V
wiersz 2:  SW   H    T↑   ]   ...  [    SE
```

| Pozycja | Segment |
|---|---|
| `(0,0)` / `(w-1,0)` | narożnik górny lewy / prawy |
| `(0,h-1)` / `(w-1,h-1)` | narożnik dolny lewy / prawy |
| `(1,0)` | krawędź **pozioma** |
| `(0,1)` | krawędź **pionowa** |
| `(2,0)` | trójnik: krawędź górna z odgałęzieniem w dół |
| `(2,h-1)` | trójnik: krawędź dolna z odgałęzieniem w górę |
| `(3,h-1)` | zaślepka: koniec biegu poziomego od wschodu |
| `(w-2,h-1)` | zaślepka: koniec biegu poziomego od zachodu |

Segmentów, których brakuje (trójnik w bok, skrzyżowanie, zaślepka pionowa),
generator nie wymaga - degraduje je do zwykłej krawędzi.

## Sprawdzenie po dodaniu

```bash
just map-palette list                  # czy klocek się pojawił, z jakim rozmiarem i drzwiami
just map-palette doors                 # podpowiedź, gdzie są drzwi (najciemniejszy kafel dolnego pasa)
just map-palette show <nazwa>          # render jednego klocka, drzwi w czerwonej ramce
just map-palette sheet --out /tmp/k.png  # arkusz kontaktowy wszystkiego
```

Najczęstsze pomyłki, które widać na arkuszu:

- **obrys o kafel za mały** - ucięty dach albo brak dolnego rzędu ścian,
- **obrys o kafel za duży** - w kadrze siedzi kawałek sąsiada,
- **`door` wskazujący ciemny róg bryły zamiast wejścia** - `just map-palette doors`
  pokazuje różnicę między tym, co jest w pliku, a swoją podpowiedzią,
- **brak `kind`** - klocek wpada do worka `prop` i nigdy nie trafi tam, gdzie miał.

## Dlaczego niektóre reguły są takie, a nie inne

- **Ścieżka do każdego wejścia.** Klocek z `door` zawsze dostaje dojście - A* prowadzi
  je od progu do najbliższego traktu albo do już położonej ścieżki. Zagroda bez dojścia
  to makieta, więc `door` na zagrodzie jest równie ważny jak na domu.
- **Ogrodzenie to jeden zamknięty obrys albo nic.** Gdy droga rozetnie zagrodę na
  kilka kawałków, generator nie stawia płotu wcale - człowiek nie otacza domu trzema
  niezależnymi odcinkami sztachet.
- **Dwie zagrody nigdy na siebie nie wchodzą.** Nakładające się obwody dają uskoki,
  bo maska sąsiedztwa liczy się już na pomieszanych kaflach.
- **Duży klocek ustępuje drodze.** `farmyard_big` postawiona na trakcie przecina wieś
  na pół. Wyjątek trzeba wpisać jawnie (`on_road = true` w briefie).
- **Kolejność prób w lesie jest losowa**, a pas przy krawędzi mapy używa TYCH SAMYCH
  gatunków, co biom obrzeżny z briefu. Branie zawsze największego klocka dawało to samo
  drzewo wzdłuż całego boku, a branie wszystkiego, co `nature`, wstawiało na skraj drzewa
  z sadu, których w lesie obok nie było.
- **Drzewa wolno nachodzić na siebie o kafel**, o ile nie kolidują na tej samej warstwie.
  Pień siedzi na `walls`, korona na `over`, więc dwa drzewa jedno nad drugim dzielą kafel:
  korona górnego przykrywa pień dolnego i las robi się zwarty zamiast rosnąć w kratkę.
- **Wnętrze ścieżki bierze kafle o masce pełnej.** Kafle o masce częściowej są kaflami
  PRZEJŚCIA trawa/ziemia - mają ziemię przewężoną przy krawędzi, więc ułożone w rzędzie
  stykają się tylko wąskim przesmykiem i ścieżka rozpada się na koraliki.
- **Ścieżka przecinająca zagrodę robi w płocie furtkę**, a nie kasuje ogrodzenia.
  Sprawdzenie spójności obwodu leci PRZED wycięciem furtek, inaczej wydeptana droga
  dyskwalifikowałaby cały płot.
- **Zwierzę nigdy nie stanie na kaflu `walls`** (płot to też ściana) ani na trakcie.
  Gra nie ma dla NPC-ów siatki bezpieczeństwa, więc krowa postawiona w sztachetach
  zostaje w nich na zawsze.
- **Szerokość pomalowanej drogi = szerokość maski.** Próg rogów wangsetu to 3: przy 2
  dochodził kafel przejścia z każdej strony i `width = 2` z briefu dawało cztery kafle
  na mapie.
