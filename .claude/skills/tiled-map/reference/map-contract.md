# Kontrakt mapy zewnętrznej

Wszystko poniżej to **fakty z kodu gry**, nie propozycje. Źródła: `project/scene/map_loader.py`,
`project/scene/fog_of_war.py`, `scripts/validate_world.py`.

## Warstwy i ich kolejność

`load_step_cost` czyta warstwy **po INDEKSIE 0 i 1**, a nie po nazwie, a
`scene.sprites_layer = scene.layers.index("sprites")` decyduje, gdzie pyscroll wstawia postacie.
Kolejność nie jest kosmetyką - zmienia zachowanie gry.

| # | Warstwa | Typ | Zawartość |
|---|---|---|---|
| 0 | `ground` | kafle | trawa, ziemia, woda (Floor.tsx, Water.tsx). Czytana po `step_cost`. |
| 1 | `foliage` | kafle | niska roślinność i ścieżki (FloorDetail.tsx, Nature.tsx, Field.tsx). Czytana po `step_cost`, **nadpisuje** `ground`. |
| 2 | `items` | kafle | przedmioty do podniesienia (items.tsx). Każdy kafel MUSI mieć `item_name` obecny w `config.items`. Warstwa gaszona po wczytaniu. |
| 3 | `walls` | kafle | **każdy niepusty kafel = kolizja**, koszt 100. `destructible=true` robi z niego niszczalny sprite. |
| 4 | `sprites` | kafle | pusta - tu gra rysuje postacie. |
| 5 | `over` | kafle | `opacity="0.99"` - dachy, korony drzew: chodzi się pod spodem. |
| 6 | `interactions` | obiekty | `obj_type=exit` (+`to_map`, `destination_entry_point`, opcjonalnie `requires_item`, `consumes_key`, `return_entry_point`, `dialog`), `obj_type=dialog` (+`dialog`) oraz `obj_type=chest`. |
| 7 | `entry_points` | obiekty | punkty pojawienia się; `start` to awaryjna pozycja gracza dla całej mapy. |
| 8 | `waypoints` | obiekty | polilinie/wielokąty. Nazwa **musi** zgadzać się z nazwą spawnu, inaczej nikt po niej nie chodzi. `enabled=false` wyłącza bez kasowania. |
| 9 | `places` | obiekty | nazwane cele rutyn; gra czyta `rect.midbottom`. |
| 10 | `spawn_points` | obiekty | gid z CharacterTileset.tsx niesie `model_name`; nazwa obiektu = **unikalna** nazwa instancji NPC (klucz zapisu gry). |
| 11 | `zones` | obiekty | **wyłącznie prostokąty** - patrz pułapki. |

## Koszt kroku (A*)

| `step_cost` | Znaczenie |
|---|---|
| 100 | droga, bruk - tanio |
| 150 | trawa, ziemia - normalnie |
| 200 | wysoka trawa, zboże - drogo |
| 300 / 500 | woda - bardzo drogo |
| brak własności | domyślne `STEP_COST_GROUND` (100) |

Wygrywa **górna z dwóch dolnych warstw**: kafel `foliage` ze swoim `step_cost` nadpisuje to,
co mówi `ground`. Ścieżka na `foliage` przyspiesza chodzenie tylko wtedy, gdy sama ma `step_cost=100`.

## Tilesety - tablica zamrożona

`BLUNDERHAVEN.tmx` i prototyp mają **identyczną** listę, więc gid skopiowany z jednej mapy na
drugą znaczy dokładnie to samo i nie wymaga przeliczania:

```
1  Water | 477 Floor | 1049 Field | 1124 Nature | 1628 House
2387 Element | 2627 FloorDetail | 2707 items | 2817 CharacterTileset
```

Generator zawsze wypisuje ten blok w tej kolejności; linter zgłasza ERROR przy odstępstwie.
Mapy WNĘTRZ mają inną tablicę - skill ich nie dotyka.

## Autotiling za darmo - DWA wangsety, dwa różne zadania

`Floor.tsx` niesie dwa zestawy terenu i mylenie ich jest realnym błędem, na który skill już raz wszedł.

| Wangset | Typ | Do czego |
|---|---|---|
| `grass-dirt Set` | `corner` | OBSZARY: trakt, plac, pole. 7 wariantów czystej trawy (gid 721, 722, 741-745), 3 czystej ziemi (654, 719, 720) i 16 kafli przejściowych na wszystkie kombinacje rogów. |
| `path Set` | `edge` | ŚCIEŻKA SZEROKA NA JEDEN KAFEL. Kolory `path` i `grass` na czterech BOKACH kafla; kolor `path` znaczy "tędy ścieżka biegnie dalej". |

**Zestawem narożnikowym nie da się narysować ścieżki 1-kaflowej.** Wangset `corner` opisuje,
co spotyka się w ROGACH kafla, więc pas ziemi szeroki na jeden kafel wychodzi z niego jako
dwa kafle przejściowe, których ziemia styka się rogiem - i ścieżka rozsypuje się na koraliki.
To była przyczyna, a nie objaw: generator uczył się ścieżki z próbki `kind=pathkit`, a Tiled
dorysowywał do tej próbki kafle obszarowe z `grass-dirt Set` i dekoder nie miał ich jak
odróżnić od kafli ścieżki.

Zawartość `path Set` (tileid w `Floor.tsx`, nazwa = kierunki, w które ścieżka biegnie DALEJ):

| Kształt | tileid | Kształt | tileid |
|---|---|---|---|
| `-` samotny | 223 | `NE` | 224 |
| `N` | 201 | `NW` | 227 |
| `E` | 220 | `SE` | 158 |
| `S` | 157 | `SW` | 161 |
| `W` | 222 | `NES` | 246 |
| `NS` | 179 | `NSW` | 249 |
| `EW` | 221 | `ESW` | 162, 159 |
| `NESW` | 250 | `NEW` | 228 |

Zestaw jest **kompletny: 16 układów na 16 możliwych**, więc `PathKit.piece` zawsze trafia
co do bitu i nigdy nie zgaduje. Nowy wariant kształtu dokłada się w Tiled (kilka kafli może
mieć ten sam `wangid` - patrz `ESW`), a kod nie wymaga zmiany.

## Nazwy obiektów - format wymagany przez `validate-world`

Nazwa obiektu nie jest etykietą: to **klucz encji**. Zapis gry kluczuje stan NPC-a po nazwie
spawnu (`npc_states[npc.name]`), warstwa `waypoints` wiąże trasę po tej samej nazwie, a
`validate-world` sprawdza format każdej z nich. Wygenerowanie nazwy w dowolnym formacie
znaczy tyle, że autor dostanie kilkanaście błędów naraz - i to dopiero wtedy, gdy zdąży
nadać mapie docelową nazwę.

| Warstwa | Format nazwy | Reguła |
|---|---|---|
| `spawn_points` | `MODEL`, a `MODEL_NN` dopiero od DRUGIEJ kopii na mapie | D1/D2 |
| `interactions` (`exit`) | klucz **mapy docelowej**, ten sam co w `to_map` | D6 |
| `interactions` (`chest`) | klucz wzorca z `config.chests` | - |
| `places` | mała litera, klucz miejsca z `characters.csv` (`MAPA:miejsce`) | - |
| `zones` | mała litera, klucz z `allowed_zones` w `characters.csv` | - |
| mapa, encje | SCREAMING_SNAKE, klucz z Obsidiana | C02 |

Numer instancji jest **zbędny przy jednej kopii** (`CAT`, nie `CAT_01`) i **obowiązkowy przy
kilku** (`COW_01`, `COW_02`). Generator liczy kopie na całej mapie w osobnym przebiegu
(`pass_names`), bo stawiając krowę w pierwszej zagrodzie nie wie jeszcze, ile ich będzie.

## Pułapki

1. **Strefy muszą być prostokątami.** `load_zones` buduje `pygame.Rect(obj.x, obj.y, obj.width,
   obj.height)`, a wielokąt ma `width=height=0` - taka strefa ma w grze **zerową powierzchnię**.
   Na `BLUNDERHAVEN.tmx` siedmiu stref dotyczy ten błąd do dziś.
2. **Kotwiczenie obiektów z gidem.** W pliku `.tmx` obiekt Z GIDEM ma `y` na **dolnej** krawędzi,
   a pytmx normalizuje to do górnej. Model `scripts/mapgen/tmx.py` liczy to za ciebie
   (`MapObject.top`, `.center`, `.midbottom`, `.anchor`) - nie licz `y + height` ręcznie.
3. **Spawn stoi o kafel WYŻEJ, niż mówi `midbottom`.** Gra sadza postać w `rect.midbottom`,
   ale zderza ze ścianą prostokąt `npc.feet` o wysokości pół kafla, którego dolna krawędź
   leży w tym punkcie - czyli ciało jest w kaflu NAD nim. Żeby postać stanęła na kaflu
   `(tx, ty)`, obiekt musi mieć w pliku `y = (ty + 1) * 16`. Użycie `ty * 16` przesuwa ją
   o kafel w górę: tak cztery zwierzęta z pierwszej mapy stanęły w sztachetach płotu, bo
   wolny kafel był tuż pod nim. **NPC nie ma siatki bezpieczeństwa** (`walkable_pos_near`
   używa tylko gracz), więc postać w ścianie zostaje tam na zawsze.
4. **Obiekt bez `obj_type` jest po cichu pomijany.** `load_interactions` bierze pod uwagę
   wyłącznie `exit`, `dialog` i `chest`. Skrzynia bez tej własności nie powstaje w grze i nikt
   o tym nie mówi (tak przez długi czas nie działała `BLUNDERHAVEN_CATS_CHEST` z questa Q04_S01).
9. **Wyzwalacz dialogu wskazuje węzeł, ale warunku nie zna.** Własność `dialog` ma postać
   `KLUCZ_POSTACI:WĘZEŁ` (np. `HAMMER_HOAXHEART:002`) i wskazuje węzeł oznaczony w notatce
   postaci sufiksem `-entry`. Kiedy scena się odgrywa, decyduje **warunek wejścia zapisany
   w notatce**, nie mapa: obiekt mówi GDZIE, notatka mówi KIEDY. Ta sama własność na obiekcie
   `exit` blokuje przejście, dopóki warunek jest prawdziwy - `exit` bez warunku (`True`)
   zamurowuje wyjście na zawsze, dlatego `validate-world` o tym ostrzega. Obszar
   `obj_type=dialog` musi mieć niezerowe `width`/`height`: punkt nie ma pola i nikt w niego
   nie wejdzie.
5. **Kafel `items` z pustym `item_name`** wywala `create_item` na KeyError.
6. **Kopiowanie mapy między katalogami psuje ścieżki tilesetów.** `TiledMap.save()` przelicza
   je automatycznie przy zapisie do innego katalogu - używaj jego, nie `cp`.
7. **Mgła wojny dotyczy tylko labiryntów** - mapy zewnętrzne jej nie budują.
8. **Strefy nie jadą razem z mapą.** `rect` strefy jest w bezwzględnych kaflach, więc jako
   jedyny element briefu nie przelicza się po zmianie `size`, a `map-edit move` zabiera
   strefę tylko wtedy, gdy jej lewy górny róg wpadł do przenoszonego prostokąta. Zmniejszenie
   mapy z 256x256 na 256x128 zostawiło `plains` na tych samych kaflach - tyle że tymi kaflami
   był już pas lasu obrzeżnego (49% kafli chodliwych zamiast 91%). Gra o tym nie powie:
   `load_zones` bierze cztery liczby i nie sprawdza, co pod nimi leży. Sprawdza to
   `map-lint` (`check_zone_placement`), generator przy `map-new` i `map-edit` po każdej
   operacji zmieniającej `walls`.

9. **Klocek przenosi WSZYSTKIE warstwy kafelkowe, `ground` włącznie.** Generator długo
   wklejał tylko `foliage`, `items`, `walls` i `over`, bo podłoże i tak maluje wangset -
   i przez to gubił ubite ścieżki narysowane w prototypie WEWNĄTRZ klocka: zagroda
   przyjeżdżała bez podwórza, a pole bez miedzy między czterema zagonami. Drugą połową
   tej pułapki jest kolejność: `pass_districts` na koniec przemalowuje CAŁĄ warstwę
   `ground` po masce traktu, więc samo wklejenie nie wystarcza. Kafle, na których klocek
   niesie coś innego niż czyste tło mapy, trafiają do `ground_locked` i `TerrainLib.paint`
   je omija. Czystej trawy spod drzewa nie blokujemy - wangset odtworzyłby ją identycznie,
   a blokada wybijałaby dziurę w odnodze poprowadzonej później pod tym samym drzewem.

## Co jeszcze powstaje poza plikiem .tmx

| Plik | Co dopisać | Skutek braku |
|---|---|---|
| `assets/locale/{PL,EN}.toml`, sekcja `[map]` | `KLUCZ = "Nazwa dla gracza"` | gracz widzi surowy klucz |
| `config_model/audio.toml`, `[music]` | `KLUCZ = "utwor.ogg"` | cisza (nie błąd) |
| `config_model/characters.csv` | `home/work/social/hobby` = `MAPA:place` | rutyna degraduje się do "stój" |
| `config_model/routines.toml` | kroki `type:` / `location:` / `route:` | `validate-world` ERROR |
| mapa sąsiednia | `exit` tam + `entry_point` tutaj, parami | gracz ląduje w środku mapy |
