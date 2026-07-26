# B01 - stan realizacji (handoff do wznowienia)

Ostatnia aktualizacja: 2026-07-25, sesja Fable (kroki 3-9). Architektura
**zaakceptowana przez autora** - obowiązuje
[doc/refactor-rdzenia-B01.md](../refactor-rdzenia-B01.md) + pełny dokument
HTML (decyzje D1-D6, kontrakty K1-K9, plan 16 kroków, ryzyka R1-R7).

## Zrobione (commity na main)

- `9f452c1` **krok 0**: `scripts/bench_scene.py` (benchmark headless; baseline
  mac-mini: update 0.775 ms / draw 1.284 ms, budżet +20%) + `scripts/b01_fixture.py`
  (referencyjny save sprzed refactoru w `.test-data/b01-fixture/save_0.mom`,
  podpolecenie `check` = bramka K1 po każdym kroku).
- `934b732` naprawa 5 scenariuszy dialogowych: ślepe `left:30 up:20` →
  `walk_to_point:960,720` (spawn gracza jest 8 px od drzwi VillageHouse;
  wahnięcie fps na web wpychało gracza do domu - padał `ui_state.map`).
- `a818b31` **krok 1**: `scene.py` → pakiet `project/scene/` (rename bajt-w-bajt)
  + `__init__.py` z eksportem `Scene` i PEP 562 `__getattr__` (żywe globale,
  K9). Pełny desktop 30/30, web po naprawie scenariuszy zielony.
- `d5728c5` **krok 2**: `scene/map_loader.py` - ładowanie mapy jako funkcje
  modułowe; na Scene delegaty tylko `create_item` i `load_map`; jedyny lokalny
  import NPC w pakiecie scene mieszka w map_loader. `scene.py` 2652 → 2072 linii.
- `100ce4c` **krok 3**: `scene/world_clock.py` - tick zegara, `apply_days`,
  `day_rng`, `abs_minutes`, `reset`, `next_day`; `settings.INITIAL_HOUR/INITIAL_DAY/
  GAME_TIME_SPEED` czytane dynamicznie (K6), koniec importu by-value.
- `f0923b0` **krok 4**: `scene/collisions.py` - jedna funkcja `resolve(scene)`
  (hot path, bez podfunkcji per pętla).
- `b49036b` **krok 5**: `scene/player_actions.py` (D4) - cały blok `INPUTS`.
  `Scene.update` jest spisem treści: freeze → grupy/rutyny → zegar → kolizje → akcje.
- `b776626` **krok 6**: `scene/routines_director.py` - harmonogram NPC-ów
  (tranzyty, reconcile/settle, materializacja, sen, roster, sloty) + stałe
  `_NOWHERE` / `_DEPARTURE_FALLBACK_MIN`.
- `2ef41ac` **krok 7**: `scene/map_state.py` - store/restore/go_to/reload/
  reset_sprite_groups + `MAP_PROPERTIES` (K1). Test
  `test_dead_monsters_is_a_cached_map_property` importuje teraz listę zamiast
  parsować AST scene.py.
- **krok 8**: `scene/night_filter.py` (filtry dnia/nocy, światła, framing)
  + `scene/intro.py` (cutscena); `intro_cutscene` przestał być atrybutem Scene.
- **krok 9**: `scene/agent_api.py` (delegaty `agent_*`, K3) + `scene/debug_overlay.py`
  z flagą `SHOW_DEBUG_INFO`; konsumenci (`characters.py`, `ui/panels/help.py`,
  `player_actions`) czytają ją z `debug_overlay`, a `scene/__init__.__getattr__`
  ma fallback na ten moduł, więc `scene.SHOW_DEBUG_INFO` nadal działa (K9).
  `scene/scene.py` 2072 → 669 linii.
- **krok 10**: `characters.py` → pakiet `project/characters/` - `npc.py` (klasa
  `NPC`, 1667 linii) + `player.py` (klasa `Player`, 334 linie) + `__init__.py`
  z eksportem `NPC`/`Player` i PEP 562 `__getattr__` (K4 + K9). Metody bez
  zmian; z `npc.py` wypadły importy, których używał tylko `Player`
  (`INVENTORY_ITEM_SCALE`, `INPUTS`, `get_msg`, `JOY_MOVE_MULTIPLIER`,
  `HealthBarUI`, `DialogPanel`, `TradePanel`) - `characters.INPUTS` nadal
  działa, bo `__getattr__` dogląda też `player`. Pełny web 25/25.

- **krok 11**: `characters/movement.py` (D6) - ruch, A*, waypointy, fizyka,
  kierunki animacji i `slide`/`move_back` jako funkcje przyjmujące `npc` jawnie;
  na `NPC` zostały cienkie delegaty o niezmienionych nazwach (K3 - `find_path`,
  `get_random_safe_pos` itd. podmieniają testy i woła `agent_ctrl`). Wywołania
  wewnątrz modułu idą przez `npc.<metoda>()`, więc monkeypatch na instancji nadal
  działa. `__getattr__` pakietu ma teraz trzeci fallback na `movement` (K9).
  `npc.py` 1662 → 1224 linii, `movement.py` 560 linii.

- **krok 12**: `characters/combat.py` (D6) - `die`, `encounter`, `hit`,
  `check_cooldown`, `process_custom_event`, `set_event_timer` jako funkcje na
  `npc` + delegaty na klasie. `__getattr__` pakietu przeszedł na pętlę po
  `("npc", "player", "movement", "combat")` (K9). `npc.py` 1224 → 1058 linii,
  `combat.py` 216.

- **krok 13**: `characters/animation.py` (D6) - `set_sprite_sheet_type`,
  `generate_masks`, `animate`, `adjust_rect` + `load_sprites` (blok wczytywania
  sprite sheetu wyjęty z `NPC.__init__`; w `__init__` zostały same deklaracje
  atrybutów dla mypy, w tym nowe `image`/`mask`/`avatar`). `npc.py` 1058 → 967
  linii, `animation.py` 142.

- **krok 14**: `characters/inventory.py` (D6) - `pick_up`, `drop_item`,
  `can_buy`/`can_sell`, `get_tradable_items`, `select_next/prev_item`,
  `load_items`, `restock_items`, `regenerate_money`, `money_cap` (na klasie
  zostaje `@property`). `npc.py` 967 → 745 linii, `inventory.py` 297. Podział
  pakietu `characters/` wg D6 jest kompletny.

- **krok 15**: `config_model/csv_tools.py` (D5) - `store_config_to_csv` /
  `load_config_from_csv` jako funkcje na `conf`; `Game.__init__` woła je LENIWYM
  importem w gałęzi zadania CLI, bo moduł ciągnie pydantic (K5). CLI `--task`
  bez zmian, round-trip `main.py store` + `main.py load` przechodzi.
  **Uwaga (zastane, nie z refactoru):** `main.py load` na CSV-kach z repo pada
  `ValueError: invalid literal for int()` - pliki są starsze niż obecna lista
  `CONF_ENTITIES_TO_STORE` (mają kolumnę `monsters_list`, której już nie ma).
  Po `store` (regeneracja) `load` działa; regeneracja to zmiana danych, więc
  decyzja autora, czy CSV-ki przepisać.

## Następny krok: **krok 16 - finalizacja**

AGENTS.md, memory, odhaczenie B01 w `doc/audyt/audyt.md`, pełny `just test`
(desktop, ~18 min) + pełny `just test-web` (~11,5 min), ss-review i weryfikacja
wizualna autora.

## Bramki po każdym kroku (przypomnienie)

1. `just test-unit` (427) 2. `just mypy` = 0 3. `MOM_SKIP_SS_REVIEW=1 just
test-smoke` (6 scenariuszy, ~1,5 min - od A08 zamiast dwóch scenariuszy z nazwy)
4. `just validate-world` 5. `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
.venv/bin/python3 scripts/bench_scene.py` (< +20% od baseline) 6.
`... scripts/b01_fixture.py check` (kontrakt K1). **Pełne zestawy OSZCZĘDNIE
(decyzja autora 2026-07-25, koszty):** pełny desktop tylko po krokach 9 i 16,
pełny web tylko po 10 i 16; poza tym wystarczą bramki wyżej. Commit
`B01 krok N: <co>` po każdym kroku; STOP i pytanie do autora, gdy bramka
nie przechodzi albo krok nie mieści się w ~600 liniach diffu.

## Higiena kosztów sesji (obowiązuje agenta)

- Output pełnych zestawów ZAWSZE do pliku w scratchpadzie + grep licznika;
  nigdy do kontekstu. Jeden waiter w tle zamiast pollingu.
- Czytaj wąskie zakresy plików (offset/limit), nie całe moduły; codegraph
  tylko gdy grep-outline nie wystarcza.
- [A08](A08-web-runner-jeden-pygbag-i-smoke.md) **zrealizowane 2026-07-25**:
  web-runner reużywa jednego serwera pygbag (pełny web 25 → **11,5 min**, 25/25
  zielone), `just test-smoke` = 6 scenariuszy w **96 s**. Bramka 3 wyżej używa
  już smoke; przy podejrzeniu przeciekania stanu na web:
  `just test-web --web-restart-per-scenario`.

## Pułapki świeżo potwierdzone w praktyce

- **`just test-web` / `just test-smoke` to singleton** (jeden pygbag na porcie
  8001, wspólny `agent_input.txt` i `screenshots/agent/`). Przed startem:
  `pgrep -f automate_display_test | wc -l` i `lsof -ti :8001 | wc -l` = 0.
  Każdy run do WŁASNEGO pliku loga - `>` na plik, do którego pisze żywy run,
  obcina go i run wygląda na martwy (tak powstały trzy równoległe runy).
  Urwany log ≠ martwy proces: najpierw `pgrep`, potem diagnoza. Sprzątanie po
  przerwaniu: `pkill -f tests/automate_display_test.py`, `pkill -f "m pygbag"`,
  `pkill -f chromium_headless_shell-1228` (build 1228 = testy MoM; build 1208
  to długodziałający `~/Projects/playwright-service` - nie ubijać).
- Backticki w `git commit -m` zjada zsh - commituj przez `git commit -F <plik>`.
- Rename + nowe pliki commituj z pathspecami obejmującymi TAKŻE stary plik,
  inaczej `D project/scene.py` zostaje poza commitem (naprawione amendem w kroku 1).
- pygbag nie startuje w świeżym worktree poza repo (nawet z kopią
  `project/build/`) - bisect web rób w głównym repo albo wcale.
- Pełne zestawy: desktop ~18 min, web ~25 min; web-flaki najpierw powtórz 2x,
  potem oglądaj screenshoty z `screenshots/agent/` (Read czyta PNG).
- `_roster_loaded` i podobne dynamiczne atrybuty: przy wynoszeniu kodu z klasy
  mypy wymaga jawnej deklaracji w `__init__`.
- Duże bloki (kroki 6, 8, 9) najtaniej wynosić skryptem: wytnij zakres linii,
  `textwrap.dedent`, podmień sygnatury, `re.sub(r'\bself\b', 'scene')` - potem
  mypy i `just test-unit` wyłapią resztę. Ręczne przepisywanie 400 linii to
  czysta strata tokenów.
- Zmienna, która w metodzie trzymała raz `Player`, raz `NPC`, po wyniesieniu do
  funkcji traci szerszy kontekst wnioskowania - mypy wymaga jawnego `npc: Any`
  (import `characters` w pakiecie scene zrobiłby cykl).
- Testy potrafią czytać KSZTAŁT kodu, nie tylko zachowanie
  (`test_dead_monsters_is_a_cached_map_property` parsował AST `scene.py`).
  Przy przenoszeniu stałych szukaj `ast.parse` / `inspect.getsourcefile` w testach.

## Prompt wznowienia (do nowej sesji, np. Opus)

Kontynuujesz B01 etap 1 (refactor rdzenia MoM). Przeczytaj W CAŁOŚCI:
`doc/audyt/B01-refactor-rdzenia.md`, `doc/refactor-rdzenia-B01.md`,
`doc/audyt/B01-stan-realizacji.md` (ten plik). Architektura jest zaakceptowana;
NIE zmieniaj decyzji D1-D6. Realizuj kroki od **kroku 3** wg planu, z bramkami
po każdym kroku i commitem `B01 krok N: <co>` na main (bez feature branchy).
Gdy bramka nie przechodzi albo plan rozjeżdża się z kodem - STOP i zapytaj.
Po ukończeniu wszystkich kroków: AGENTS.md, memory, odhaczenie B01 w
`doc/audyt/audyt.md`, weryfikacja wizualna autora.
