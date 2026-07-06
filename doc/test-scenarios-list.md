# 📋 Scenariusze testowe (stan drzewa roboczego: 20)

Filtrowanie per backend robi pole `platform` w `scenarios.json` - teraz **zawsze jawne** dla każdego scenariusza: `["desktop", "web"]` (oba) lub `["web"]` (tylko web). **Desktop: 19, Web: 20.**

Każdy scenariusz ma też pole `slug` (krótka nazwa snake_case) używane w nazwach screenshotów.

## Nazewnictwo screenshotów

Pliki trafiają do `screenshots/agent/` w formacie:

```
agent_{run_ts}_{scenario_slug}_{NN}_{action_slug}.png
```

- `run_ts` - jeden znacznik czasu (`YYYYMMDD_HHMMSS`) na cały przebieg jednego scenariusza; wszystkie screenshoty tego przebiegu mają ten sam `run_ts`, więc łatwo je zgrupować.
- `scenario_slug` - `slug` scenariusza z `scenarios.json`.
- `NN` - licznik screenshotów w obrębie scenariusza (2 cyfry).
- `action_slug` - pole `slug` akcji, która zleciła screenshot (akcje nie mają już `label` - tylko `slug`).

Desktop generuje tę nazwę w grze (`project/agent_ctrl.py`, prefix z env `MOM_AGENT_SS_PREFIX`), web - w runnerze; oba dają identyczny format, dzięki czemu runner potrafi przewidzieć ścieżkę pliku na potrzeby asercji.

## Asercje

| Typ                   | Backend        | Sprawdza                                                                 |
| --------------------- | -------------- | ----------------------------------------------------------------------- |
| `file_exists`         | desktop / web  | Plik `save_N.mom` istnieje (web: klucz `MoM.save_N` w localStorage)      |
| `localstorage_exists` | web            | Klucz (np. `MoM.save_0`) obecny w localStorage                          |
| `save_absent`         | desktop / web  | Slot zapisu NIE istnieje (np. zapis zablokowany w lochu)                |
| `process_alive`       | desktop / web  | Proces gry nadal żyje (nie wyszedł/nie zcrashował na końcu scenariusza)  |
| `screenshot_min_size` | desktop / web  | Screenshot waży > `min_size` bajtów (tani wykrywacz pustej/czarnej klatki) |
| `screenshot_review`   | desktop / web  | Subagent `ss-reviewer` (vision) potwierdza, że screenshot pokazuje to, co powinien |

### `screenshot_review`

Wysyła wskazany screenshot do subagenta `ss-reviewer` (OpenCode, model z vision) i wymaga werdyktu `RESULT: PASS`. Pola:

- `expect` - opis oczekiwanej zawartości ekranu (naturalny język).
- `expected_state` - opcjonalna klasa stanu gry (`MENU_MAIN`, `MENU_SETTINGS`, `GAMEPLAY`, `GAME_OVER`, ...).
- `target` - **wymagany** slug akcji, której screenshot ma być oceniony (musi wskazywać akcję ze `screenshot` w `commands`). Dzięki temu przy wielu zrzutach w scenariuszu jednoznacznie wiadomo, który jest oceniany. (Runner nadal obsługuje pominięcie = ostatni screenshot, ale w scenariuszach zawsze podajemy `target` jawnie.)

Model: primary `opencode-go/mimo-v2.5`, fallback `google/gemini-3.1-flash-lite` (gdy primary niedostępny / wyczerpany limit). Gdy żaden model nie zwróci werdyktu - asercja **twardo pada** (hard-fail).

Zmienne środowiskowe:

- `MOM_SKIP_SS_REVIEW=1` - pomiń wszystkie `screenshot_review` (szybka iteracja; asercje przechodzą).
- `MOM_SS_REVIEW_MODEL=<provider/model>` - wymuś jeden model (pomija martwy primary, np. `google/gemini-3.1-flash-lite`).

## Lista scenariuszy

| #   | Scenariusz                        | slug                          | Desktop | Web | Asercje                                             |
| --- | --------------------------------- | ----------------------------- | :-----: | :-: | -------------------------------------------------- |
| 1   | Display Settings Flow             | `display_settings_flow`       |    ✓    |  ✓  | review ×2 (MENU_MAIN, MENU_SETTINGS)               |
| 2   | Save and Load Basic               | `save_load_basic`             |    ✓    |  ✓  | review (GAMEPLAY po load)                          |
| 3   | Quick Save and Load               | `quick_save_and_load`         |    ✓    |  ✓  | review (GAMEPLAY - powrót na start)               |
| 4   | Death then Load                   | `death_then_load`             |    ✓    |  ✓  | review ×2 (GAME_OVER, GAMEPLAY)                    |
| 5   | Multiple Quick Saves              | `multiple_quick_saves`        |    ✓    |  ✓  | file_exists save_0/1 + review                     |
| 6   | Auto Save on Map Change           | `auto_save_on_map_change`     |    ✓    |  ✓  | file_exists save_0 + review (slot auto-save)      |
| 7   | Corrupt Save Handling             | `corrupt_save_handling`       |    ✓    |  ✓  | review + process_alive (setup: corrupt save_0)    |
| 8   | Web Save in localStorage          | `web_save_localstorage`       |    —    |  ✓  | localstorage_exists save_0                        |
| 9   | Empty Slot Load                   | `empty_slot_load`             |    ✓    |  ✓  | review (pusty LoadPanel)                          |
| 10  | Load from Main Menu               | `load_from_main_menu`         |    ✓    |  ✓  | file_exists save_0 + review (GAMEPLAY)            |
| 11  | UI Flow - Full Save Load          | `ui_flow_full_save_load`      |    ✓    |  ✓  | review (GAMEPLAY po load)                          |
| 12  | TextInput Basic                   | `textinput_basic`             |    ✓    |  ✓  | review (ekran demo TextInput)                     |
| 13  | Manage Saves                      | `manage_saves`                |    ✓    |  ✓  | review ×2 (modal delete, pusta lista)             |
| 14  | In-Game LoadPanel Paused          | `ingame_loadpanel_paused`     |    ✓    |  ✓  | review (GAMEPLAY) + process_alive                 |
| 15  | Maze Save Blocked                 | `maze_save_blocked`           |    ✓    |  ✓  | save_absent save_0 + review (blokada zapisu)      |
| 16  | In-Game Reload Confirm            | `ingame_reload_confirm`       |    ✓    |  ✓  | review (dialog reload) + process_alive            |
| 17  | In-Game Esc Shows Continue        | `ingame_esc_shows_continue`   |    ✓    |  ✓  | review ×2 (MENU_MAIN, GAMEPLAY) + process_alive   |
| 18  | Load from Menu then Esc           | `load_from_menu_then_esc`     |    ✓    |  ✓  | review (MENU_MAIN) + process_alive                |
| 19  | Menu Load Cancel Returns to Menu  | `menu_load_cancel_returns`    |    ✓    |  ✓  | review (MENU_MAIN) + process_alive                |
| 20  | TextInput Demo Hotkey             | `textinput_demo_hotkey`       |    ✓    |  ✓  | review ×2 (MENU_MAIN, ekran demo)                 |

## Postacie zmigrowane z RPG (dialogi i sentyment)

Wszystkie postacie z prototypu RPG zostały zmigrowane do `config.json` w projekcie MoM:
- **Hammer** (Hammer Hoaxheart) - Kowal w wiosce. Pełny graf dialogowy, sprawdzany w scenariuszach `"Hammer Dialog Flow"` oraz `"Dialog Save and Load"`.
- **Barman Absinthrayner** - Barman Absyntnent. Graf zmigrowany przez pipeline z markdown, obsługuje warunki i zmianę sentymentu.
- **Clapback Sword** - Gadający miecz. Graf zmigrowany i zweryfikowany pod kątem spójności językowej PL/EN.
- **Potioneer Puzzlemint** - Alchemik w wiosce. Graf zmigrowany przez pipeline, zawiera efekty zmiany sentymentu i warunki.
- **Madame Sarcasmia** - Dowcipna czarodziejka. Graf i tłumaczenia zmigrowane z RPG config.json, a warunki (szukanie przedmiotów i odpytywanie o opcje) w pełni przetłumaczone na mini-DSL MoM.

Do debugowania i szybkiego testowania drzew dialogowych na żywo służą opcje `DEBUG` dodawane do grafu, gdy włączony jest tryb `IS_DEBUG_MODE` w `project/settings.py` (decyzja **D9**). Pozwalają one na natychmiastowe skoki do START_NODE lub węzłów końcowych (`is_final`).

