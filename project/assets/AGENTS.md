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

- Teksty źródłowe dialogów mieszkają w vaultcie Obsidian **`doc/`** (poza `project/assets`,
  żeby nie trafiały do bundla web): `doc/PL/Postacie/` i `doc/EN/Characters/`.
  **Pliki Markdown (PL = źródło prawdy) są źródłem prawdy** dla `config_model/config.json`.
  Szczegóły formatu: [`../dialog/AGENTS.md`](../dialog/AGENTS.md).
- **Konwencja nazw:** nazwa pliku = zlokalizowana nazwa postaci (np. `Barman Absyntnent.md`);
  klucz słownikowy tylko w polu `aliases` frontmattera — importer znajduje pliki po aliasie.
- **Regeneracja configu:** `just import-dialogs` uruchamia `markdown_importer.py`
  (domyślnie wszystkie postacie wykryte w `PL/Postacie/` — pliki WIP/nieparsowalne
  pomijane z ostrzeżeniem; merge do `config.json`, usuwanie osieroconych kluczy
  `messages`, upsert kolumn sprite/friendly/sentymentów w `characters.csv` z
  auto-dopisaniem brakujących wierszy), a następnie kaskadowo `just import-entities`
  (jedyny writer sekcji `characters`).
- **Wybór języka** w runtime przez zmienną `LANG` w `settings.py:22`:
  ```python
  LANG = "PL"                                   # settings.py:22 — mutable, zmieniane z UI
  ```
  Zmiana `LANG` jest sterowana z panelu Settings w grze (przełącznik `Language: PL`/`Language: EN`)
  i persistowana w `save_load/display_settings.py` (`settings.json` / localStorage).
  Dodając nowy dialog, utwórz odpowiedniki w **obu** językach
  (`doc/PL/Postacie/` + `doc/EN/Characters/`; szablony w `doc/_templates/`).
- Format rich-text (tagi `[bold]`, `[link plik.md]…[/link]`, inline `:emoji:`) renderowany
  przez SFText / `rich_text.py`.

## UI strings (lokalizacja interfejsu)

Teksty interfejsu (menu, powiadomienia, akcje) znajdują się w `locale/{PL,EN}.toml`.
Pliki TOML używają zagnieżdżonych tabel — klucze z kropkami w JSON odpowiadają
sekcjom TOML (np. `"menu.continue"` → `[menu]` + `continue`).

Ładowanie: `settings.load_ui_strings()` → `tomllib.load()` → `_flatten_toml()`
zagnieżdżony dict → flat dict z kluczami `"section.key"`. Funkcja `_()` czyta
z cache `UI_STRINGS[LANG]`.

**Walidacja:** `just validate-locale` (sprawdza symetrię kluczów PL/EN + spójność
placeholderów). Uruchamiane też przez `just check`.

Dodając nowy klucz: wpisz w **oba** pliki TOML, uruchom `just validate-locale`.

## Sprite-sheety postaci

Konwencja klatek animacji (`SPRITE_SHEET_DEFINITION_*`, dobór po szerokości sprite'a) jest
zdefiniowana w `settings.py` — opis i przepis na dodanie postaci w
[`../AGENTS.md`](../AGENTS.md) (sekcja „Animacja sprite'ów").

## Build web

`pygbag.ini` (w root) **wyklucza** z paczki web część plików (m.in. shadery `OpenGL3.3`
i Tiled project files). Dodając duże assety desktop-only, sprawdź czy nie trzeba ich tam dopisać.
