# AGENTS.md — assety i lokalizacja (`project/assets/`)

Grafiki, mapy, fonty, dialogi. Kontekst nadrzędny: [`../AGENTS.md`](../AGENTS.md).
Autor edytuje/tworzy assety w **Aseprite** (baza = paczki licencjonowane + własne modyfikacje).

## Aktywne paczki (✅ używać)

| Folder            | Zawartość                                                                         |
|-------------------|-----------------------------------------------------------------------------------|
| `NinjaAdventure/` | **Główny pack:** `characters/`, `items/`, `Emote/`, `HUD/`, `particles/`, `maps/` |
| `MazeTileset/`.   | Kafelki do proceduralnych labiryntów (`MazeTileset_clean.tmx` jako szablon)       |

### ⛔ Legacy / eksperymenty — pomijać

`kenney_tinyDungeon/`, `monochrome_ninja/` — nieużywane w grze, nie modyfikować ani nie
ładować.

## Mapy Tiled

- Pliki map: `assets/map/*.tmx` (+ tilesety `*.tsx`, np. `water.tsx`) oraz `NinjaAdventure/maps/`.
- Ładowane przez pytmx, renderowane przez pyscroll (patrz `scene.py`).
- Warstwy mapy: `walls` (kolizje), markery spawnów / wejść-wyjść, waypointy NPC; przejścia
  między mapami przez custom properties w Tiled.

## Dialogi i lokalizacja

- Teksty w `dialogs/EN/` i `dialogs/PL/` (+ `game_economy.md`, `rich_text_sample.md`).
- **Wybór języka działa przez stałą `LANG`** w `settings.py:21`:
  ```python
  LANG = "EN"                                   # settings.py:21
  DIALOGS_DIR = ASSETS_DIR / "dialogs" / LANG   # settings.py:436
  ```
  Zmiana `LANG` przełącza katalog dialogów (`EN` ↔ `PL`). **Brak jeszcze przełącznika w UI** —
  zmiana następuje w kodzie. Dodając nowy dialog, utwórz odpowiedniki w **obu** językach.
- Format rich-text (tagi `[bold]`, `[link plik.md]…[/link]`, inline `:emoji:`) renderowany
  przez SFText / `rich_text.py`.

## Sprite-sheety postaci

Konwencja klatek animacji (`SPRITE_SHEET_DEFINITION_*`, dobór po szerokości sprite'a) jest
zdefiniowana w `settings.py` — opis i przepis na dodanie postaci w
[`../AGENTS.md`](../AGENTS.md) (sekcja „Animacja sprite'ów").

## Build web

`pygbag.ini` (w root) **wyklucza** z paczki web część plików (m.in. shadery `OpenGL3.3`
i Tiled project files). Dodając duże assety desktop-only, sprawdź czy nie trzeba ich tam dopisać.
