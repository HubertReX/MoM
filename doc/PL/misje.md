# Quests

[translation](../EN/quests.md)

## PL

```dataview
TABLE WITHOUT ID
  file.link as "Misja",
  filter(file.outlinks, (x) => startswith(meta(x).path, "PL/Misje/"))  as "Misja zależy od",
  filter(file.outlinks, (x) => startswith(meta(x).path, "PL/Postacie/"))  as "Odnosi się do"
FROM ""
WHERE file.folder = "PL/Misje"
SORT file.aliases ASC, file ASC
```

`  filter(file.inlinks, (x) => startswith(meta(x).path, "PL/"))  as "Zależą",`

## lista

Jeden plik = jeden quest, więc poniżej są same parasole wątków (krok `S00`). Pełną listę z krokami daje tabela wyżej.

- [[Q00_S00 O co tu chodzi]]
- [[Q01_S00 Przełamać klątwę]]
- [[Q03_S00 Znajdź kogoś kto wie o klątwach]]

### **PL Finding the Amulet of Un-Cursing**

### **PL Break the curse**

### **PL Trinkets for Madams Sarcasmia's a little... project**
