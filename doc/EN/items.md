# Items

[**translation**](../PL/przedmioty.md)

One note per item, in `EN/Items/` - a mirror of `PL/Przedmioty/`, which is the source of truth. The Polish note carries every `items.csv` column as a property; the English note carries the key, the alias and the name, so an item can be linked from English dialog and quest files:

```markdown
**Test**: `has_item(`[[Mermaid's tear]]`)`
* [[#012]] 1[`has_item(`[[Phoenix feather]]`)`]😐: I have everything you asked for.
```

Rules, property defaults and the `just` recipes live in the Polish note: [[przedmioty]].

## List

```dataview
TABLE WITHOUT ID
  ("![[item_" + key + ".png|32]]") as "Icon",
  file.link as "Item",
  key as "Key"
FROM ""
WHERE file.folder = "EN/Items"
SORT file.name ASC
```

## Not an item yet

**the Amulet of Un-Cursing** - "Aye, I've heard whispers of such a relic, said to possess the power to undo even the most stubborn curses." Until it has a row in `items.csv`, it is only a rumour in dialogue.
