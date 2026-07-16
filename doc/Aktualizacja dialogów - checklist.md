---
tags: [dialogi, workflow]
---

# Aktualizacja dialogów - checklist

Kroki do wykonania **po każdej edycji dialogów** w plikach postaci. Źródłem prawdy
są pliki PL: `doc/PL/Postacie/*.md`. Wszystkie komendy odpalaj z katalogu głównego repo.

## 1. Edytuj dialog

Zmień treść w `doc/PL/Postacie/<Nazwa>.md` (węzły `## <numer>`, opcje `* [[#00x]] ...`,
warunki, `-end`, resume). Format i pułapki: `project/dialog/AGENTS.md`.

## 2. (Opcjonalnie) zsynchronizuj EN

Jeśli edytowałeś metadane/frontmatter, dociągnij kopię EN skillem `dialog-en-sync`.

## 3. Zaimportuj do gry

```bash
just import-dialogs
```

Kaskada `MD → characters.csv → config.json`. Bez argumentu importuje wszystkie postacie;
z nazwą - jedną (`just import-dialogs "Barman Absyntnent"`).

## 4. Przegeneruj grafy

```bash
just dialog-graph
```

Bez argumentu - wszystkie postacie; z `dialog_key` - jedna
(`just dialog-graph BARMAN_ABSINTHRAYNER`). Zapisuje notatki do `doc/_graphs/`.

## 5. Sprawdź graf w Obsidianie

Otwórz `doc/_graphs/<Nazwa postaci> - graf.md`. Nad grafem panel **PROBLEMY** wypisuje
orphany, ślepe zaułki i węzły z samymi warunkowymi opcjami - kliknięcie wpisu centruje
kamerę na węźle. Popraw źródło i wróć do kroku 1.

- Klik w węzeł - podświetla sąsiadów.
- Podwójny klik - otwiera węzeł w źródłowym `.md`.
- Hover - treść kwestii, warunek opcji, efekt węzła.

## Wymóg jednorazowy

W Obsidianie: **Ustawienia → Dataview → Enable JavaScript Queries = on**. Bez tego
blok grafu się nie wykona (zobaczysz surowy kod zamiast rysunku).

## Co trafia do repo

- `doc/_graphs/<Nazwa> - graf.md` oraz `doc/_graphs/data/<KEY>.json` - commituj.
- `doc/_graphs/lib/vis-network.min.js` - biblioteka offline, commitowana raz.
