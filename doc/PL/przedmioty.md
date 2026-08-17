# Przedmioty

[**translation**](../EN/items.md)

Jedna notatka = jeden przedmiot, w katalogu `PL/Przedmioty/` (i lustro w `EN/Items/`). Wszystkie kolumny `items.csv` siedzą tam jako **properties**, więc `items.csv` jest artefaktem, a nie miejscem do ręcznej edycji.

Powód, dla którego przedmioty w ogóle mają notatki: **dają się linkować**. Warunek w dialogu albo misji pisze się wtedy tak, że jest naraz warunkiem dla silnika i krawędzią w grafie **Obsidiana**:

```markdown
**Test**: `has_item(`[[Łza Syrenki]]`)`
* [[#012]] 1[`has_item(`[[Pióro Feniksa]]`)`]😐: Mam wszystko, o co prosiłaś.
```

Pełna ściągawka warunków: [[jak-napisac-barka]].

## Lista

### Base
```base
filters:
  and:
    - file.inFolder("PL/Przedmioty")
formulas:
  ikona: link("item_" + note.key + ".png", 100)
  safe_value: if(value == null, 50, value)
  safe_weight: if(weight == null, 1.0, weight)
  safe_damage: if(damage == null, 10, damage)
  safe_cooldown: if(cooldown_time == null, 1.0, cooldown_time)
  safe_health: if(health_impact == null, 0, health_impact)
  Roślinność: if(damage >=10, true, false)
  Untitled: if(damage >= 25, true, false)
  color: aliases[0].split("_")[1]
  Kolor: aliases[0].split("_")[2]
properties:
  formula.ikona:
    displayName: Ikona
  type:
    displayName: Typ
  formula.safe_value:
    displayName: Wartość
  formula.safe_weight:
    displayName: Waga
  formula.safe_damage:
    displayName: Obrażenia
  formula.safe_cooldown:
    displayName: Odnowienie
  formula.safe_health:
    displayName: Zdrowie
  file.name:
    displayName: nazwa
  formula.Untitled:
    displayName: Skały
  formula.color:
    displayName: Rozmiar
views:
  - type: cards
    name: Galeria Przedmiotów
    filters:
      and:
        - "!type.isEmpty()"
    groupBy:
      property: type
      direction: ASC
    order:
      - formula.ikona
      - file.name
      - formula.safe_value
      - formula.safe_weight
    sort:
      - property: file.name
        direction: ASC
    image: formula.ikona
    cardSize: 150
  - type: table
    name: Tabela
    order:
      - file.name
      - type
      - formula.safe_value
      - formula.safe_weight
      - formula.safe_damage
      - formula.safe_cooldown
      - formula.safe_health
    sort:
      - property: type
        direction: ASC
      - property: file.name
        direction: ASC
      - property: formula.ikona
        direction: ASC
      - property: formula.safe_health
        direction: DESC
    columnSize:
      file.name: 245
      formula.safe_value: 102
      formula.safe_weight: 87
      formula.safe_damage: 111
      formula.safe_cooldown: 123
      formula.safe_health: 140
  - type: table
    name: Jadalne
    filters:
      and:
        - type == "consumable"
    order:
      - file.name
      - formula.safe_value
      - formula.safe_weight
      - formula.safe_health
    sort:
      - property: formula.safe_health
        direction: ASC
      - property: formula.safe_weight
        direction: ASC
      - property: formula.safe_value
        direction: ASC
      - property: type
        direction: ASC
      - property: file.name
        direction: ASC
      - property: formula.ikona
        direction: ASC
    columnSize:
      file.name: 245
      formula.safe_value: 110
      formula.safe_weight: 95
      formula.safe_health: 110
  - type: table
    name: Broń
    filters:
      and:
        - type == "weapon"
    order:
      - file.name
      - formula.safe_value
      - formula.safe_weight
      - formula.safe_damage
      - formula.safe_cooldown
      - formula.Roślinność
      - formula.Untitled
    sort:
      - property: formula.safe_value
        direction: ASC
      - property: type
        direction: ASC
      - property: file.name
        direction: ASC
      - property: formula.ikona
        direction: ASC
      - property: formula.safe_health
        direction: DESC
    columnSize:
      file.name: 245
      formula.safe_value: 109
      formula.safe_weight: 95
      formula.safe_damage: 111
      formula.safe_cooldown: 133
  - type: table
    name: Klucz
    filters:
      and:
        - type == "key"
    order:
      - file.name
      - formula.safe_value
      - formula.safe_weight
    sort:
      - property: formula.safe_value
        direction: ASC
      - property: file.name
        direction: ASC
      - property: formula.ikona
        direction: ASC
    columnSize:
      file.name: 245
      formula.safe_value: 118
      formula.safe_weight: 95
  - type: table
    name: Klejnot
    filters:
      and:
        - type == "gem"
    order:
      - file.name
      - formula.safe_value
      - formula.safe_weight
      - formula.color
      - formula.Kolor
    sort:
      - property: formula.Kolor
        direction: DESC
      - property: formula.color
        direction: DESC
      - property: formula.safe_value
        direction: ASC
      - property: file.name
        direction: ASC
      - property: formula.ikona
        direction: ASC
    columnSize:
      file.name: 245
      formula.safe_value: 114
      formula.safe_weight: 95
      formula.Kolor: 92
  - type: table
    name: Pieniądz
    filters:
      and:
        - type == "money"
    order:
      - file.name
      - formula.safe_value
      - formula.safe_weight
    sort:
      - property: formula.safe_value
        direction: ASC
      - property: file.name
        direction: ASC
      - property: formula.ikona
        direction: ASC
    columnSize:
      file.name: 245
      formula.safe_value: 111
      formula.safe_weight: 95
      formula.safe_damage: 111
      formula.safe_cooldown: 133
      formula.safe_health: 110

```

### Dataview

```dataview
TABLE WITHOUT ID
  embed(link("item_" + key + ".png", "100")) as "Ikona",
  file.link as "Przedmiot",
  type as "Typ",
  default(value, 50) as "Wartość", 
  default(weight, 1.0) as "Waga", 
  default(damage, 10) as "Obrażenia", 
  default(cooldown_time, 1.0) as "Odnowienie", 
  default(health_impact, 0) as "Zdrowie"
FROM ""
WHERE file.folder = "PL/Przedmioty"
SORT type ASC, file.name ASC
```

## Properties

| Property        | Znaczenie                                                      | Domyślnie, gdy puste |
| --------------- | -------------------------------------------------------------- | -------------------- |
| `key`           | klucz z `items.csv` - to on jedzie do gry, map Tiled i configu | **obowiązkowe**      |
| `name_PL`       | nazwa dla gracza po polsku (zwykle = nazwa pliku)              | **obowiązkowe**      |
| `name_EN`       | nazwa dla gracza po angielsku                                  | **obowiązkowe**      |
| `type`          | `weapon`, `key`, `consumable`, `money`, `gem`                  | **obowiązkowe**      |
| `value`         | ile przedmiot jest wart w złocie                               | `50`                 |
| `weight`        | waga jednej sztuki w kg                                        | `1.0`                |
| `damage`        | obrażenia zadawane bronią                                      | `10`                 |
| `cooldown_time` | ile sekund do kolejnego użycia broni                           | `1.0`                |
| `health_impact` | ile zdrowia wraca po zjedzeniu / wypiciu                       | `0`                  |

Puste property znaczy **„weź domyślne z modelu"**, nie „zapomniałem": pusta komórka nie trafia do `config.json` i przedmiot dostaje wartość z klasy `Item` w `config_pydantic.py`. Prawa kolumna jest pilnowana testem (`tests/test_items_markdown.py`), więc nie może rozjechać się z modelem.

`damage` i `cooldown_time` mają sens tylko dla `type: weapon`, `health_impact` tylko dla `consumable` - reszta po prostu ich nie używa.

## Receptury

```bash
just import-items          # notatki -> items.csv -> config.json -> validate-world
just import-items --export # items.csv -> notatki (zasianie nowych, regeneracja frontmatteru)
just gen-item-icons        # ikony -> doc/_attachements/item_<klucz>.png (--scale N dla większych)
```

Eksport przepisuje **sam frontmatter**, więc opis przedmiotu i wszystko pod nagłówkiem przeżywa regenerację. Ikonę wstawia inline dataview - `` `= "![[item_" + this.key + ".png|64]]"` `` - nazwa pliku składa się z klucza, więc nie trzeba jej wpisywać ręcznie. Ikony wycinane są z tych samych arkuszy, z których korzysta gra (`ITEMS_SHEET_DEFINITION` i `GEMS_SHEET_DEFINITION` w `settings.py`) i skalowane całkowitą krotnością, więc nie mogą pokazywać czegoś innego niż ekwipunek.

## Trzy rzeczy, które zaskakują

1. **Nazwa pliku nie jest daną.** Do CSV jadą properties `name_PL` / `name_EN`; nazwa pliku jest po to, żeby `[[Łza Syrenki]]` czytało się jak zdanie. Jeśli je rozjedziesz, wygrywa property, a import to wypisze. Dwa przedmioty o tej samej nazwie wyświetlanej dostają notatkę z sufiksem `(klucz)` - i to jest sygnał, że nazwę w grze trzeba poprawić, bo gracz też ich nie odróżni w ekwipunku.
2. **Klucz jest w `key:`, nie w aliasie.** Klucze przedmiotów bywają pisane małymi literami (`golden_key`, `life_pot`), więc po aliasie w UPPER_SNAKE - jak u postaci - nie dałoby się ich odróżnić od nazwy. Alias jest dodatkowo, żeby dało się linkować także po kluczu.
3. **Skasowanie notatki kasuje przedmiot.** Import wypisze o tym ostrzeżenie, a jeśli przedmiot leżał na mapie albo w skrzyni, złapie to `just validate-world` na końcu kaskady.

## Bez własnego przedmiotu

**Amulet Odrzucania Klątwy** - „Tak, słyszałem pogłoski o takiej relikwii, o której mówi się, że posiada moc cofania nawet najbardziej uporczywych klątw." Póki nie ma wpisu w `items.csv`, jest wyłącznie plotką w dialogu.
