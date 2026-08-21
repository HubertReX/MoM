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
| 6 | `interactions` | obiekty | `obj_type=exit` (+`to_map`, `destination_entry_point`, opcjonalnie `requires_item`, `consumes_key`, `return_entry_point`) oraz `obj_type=chest`. |
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

## Autotiling za darmo

`Floor.tsx` niesie wangset **"grass-dirt Set"** (typ `corner`): 7 wariantów czystej trawy
(gid 721, 722, 741-745), 3 czystej ziemi (654, 719, 720) i 16 kafli przejściowych na wszystkie
kombinacje rogów. To pełny autotiling styku trawa/ziemia bez ani jednej zaszytej reguły.

## Pułapki

1. **Strefy muszą być prostokątami.** `load_zones` buduje `pygame.Rect(obj.x, obj.y, obj.width,
   obj.height)`, a wielokąt ma `width=height=0` - taka strefa ma w grze **zerową powierzchnię**.
   Na `BLUNDERHAVEN.tmx` siedmiu stref dotyczy ten błąd do dziś.
2. **Kotwiczenie obiektów z gidem.** W pliku `.tmx` obiekt Z GIDEM ma `y` na **dolnej** krawędzi,
   a pytmx normalizuje to do górnej. Model `scripts/mapgen/tmx.py` liczy to za ciebie
   (`MapObject.top`, `.center`, `.midbottom`, `.anchor`) - nie licz `y + height` ręcznie.
3. **Obiekt bez `obj_type` jest po cichu pomijany.** `load_interactions` bierze pod uwagę
   wyłącznie `exit` i `chest`. Skrzynia bez tej własności nie powstaje w grze i nikt o tym
   nie mówi (tak przez długi czas nie działała `BLUNDERHAVEN_CATS_CHEST` z questa Q04_S01).
4. **Kafel `items` z pustym `item_name`** wywala `create_item` na KeyError.
5. **Kopiowanie mapy między katalogami psuje ścieżki tilesetów.** `TiledMap.save()` przelicza
   je automatycznie przy zapisie do innego katalogu - używaj jego, nie `cp`.
6. **Mgła wojny dotyczy tylko labiryntów** - mapy zewnętrzne jej nie budują.

## Co jeszcze powstaje poza plikiem .tmx

| Plik | Co dopisać | Skutek braku |
|---|---|---|
| `assets/locale/{PL,EN}.toml`, sekcja `[map]` | `KLUCZ = "Nazwa dla gracza"` | gracz widzi surowy klucz |
| `config_model/audio.toml`, `[music]` | `KLUCZ = "utwor.ogg"` | cisza (nie błąd) |
| `config_model/characters.csv` | `home/work/social/hobby` = `MAPA:place` | rutyna degraduje się do "stój" |
| `config_model/routines.toml` | kroki `type:` / `location:` / `route:` | `validate-world` ERROR |
| mapa sąsiednia | `exit` tam + `entry_point` tutaj, parami | gracz ląduje w środku mapy |
