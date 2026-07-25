# B01 - wielki refactor rdzenia: `scene.py` + `characters.py` (epic)

Priorytet: **P0** (Faza 2). Rozmiar: XL. Model: **Fable lub Opus** (nie delegować słabszym).
Zależności: Faza 1 zakończona (A01-A03 + C01 + **F03**) - refactor bez stabilnych testów
wizualnych, walidatora danych i czystej bazy mypy to loteria.

## Kontekst i problem

- `project/scene.py` - 2635 linii, ~30 odpowiedzialności: ładowanie map TMX, generacja
  i integracja labiryntów, kolizje, zegar świata (dzień/godzina/minuta), pogoda,
  rutyny NPC cross-map (roster, materializacja, sloty), intro-cutscene, filtr nocy,
  debug overlay, API agenta (agent_walk_*), notyfikacje, przejścia między mapami.
  `Scene.update` ma ~400 linii (scene.py:1937-2334).
- `project/characters.py` - 1962 linie: `NPC` (animacje, A*, FSM, dialog, sentyment,
  handel, sen/rutyny) + `Player(NPC)` (input, walka, inventory, encounter).
- `project/game.py` - 1234 linie: pętla + input + render + narzędzia deweloperskie
  (CSV import/eksport, recording).

Decyzja autora: **jeden duży, zaplanowany refactor teraz** (nie stopniowa ekstrakcja).

## Przebieg: dwa etapy z bramką akceptacji

### Etap 0 - dokument architektury docelowej (deliverable do akceptacji autora)

Stwórz dokument decyzyjny (HTML w `doc/_attachements/` wg wzorca istniejących tam
dokumentów + krótki md w `doc/`) zawierający:

1. Docelowy podział modułów z odpowiedzialnościami i zależnościami. Punkt startowy
   do weryfikacji (zbadaj kod i popraw, jeśli znajdziesz lepszy podział):

   ```text
   project/scene/
     __init__.py        # eksport Scene
     scene.py           # orkiestrator: State, update/draw jako sekwencja wywołań systemów (~300-400 linii)
     map_loader.py      # load_map, load_walls/items/zones/interactions, tileset, entry points
     world_clock.py     # minute_f/hour/day, apply_days, day_rng
     collisions.py      # kolizje gracz/NPC/broń/destructibles (dzisiejszy środek Scene.update)
     routines_director.py # roster, update_routine_npcs, materializacja, sloty, exit_to
     map_state.py       # store_map/restore_map/loaded_maps (kontrakt z save_load!)
     night_filter.py    # apply_time_of_day_filter + get_lights (przyszłe E01)
     intro.py           # start_intro, cutscene framing
     debug_overlay.py   # show_debug, _TIMEIT_CACHE
     agent_api.py       # agent_find_entity, agent_walk_*, agent_open_dialog
   project/characters/
     __init__.py        # eksport NPC, Player
     npc.py             # stan, model, animacje delegowane
     player.py          # Player NIE dziedziczy po NPC albo dziedziczenie świadomie
                        # potwierdzone w dokumencie (dziś: Player(NPC) - ocenić koszt zmiany)
     movement.py        # A*, waypointy, slide, get_direction_360
     combat.py          # encounter, hit, damage, stun
     animation.py       # import_sheet, klatki, animate
   ```

2. Kontrakty, których NIE wolno złamać (wypisz w dokumencie jawnie):
   - format save/load (`save_load/models.py` czyta atrybuty Scene i NPC po nazwach;
     `store_map()` snapshotuje atrybuty z listy `self.properties` - każda zmiana nazw
     atrybutów = migracja save)
   - API używane przez `agent_ctrl`, `tests/automate_display_test.py` i scenariusze
   - dual-target: żadnych importów pydantic poza gałęzią desktop; web bez zmian zachowania
   - pułapki importu by-value (`from settings import WIDTH/LANG/INITIAL_HOUR`) - w nowych
     modułach wyłącznie `import settings` + odczyt dynamiczny
3. Plan wykonania w krokach commitowalnych (każdy krok osobno zielony), kolejność
   proponowana: map_loader → world_clock → collisions → routines_director →
   night_filter/intro/debug/agent_api → podział characters → sprzątanie game.py
   (CSV-tools do `scripts/` lub `config_model/`).
4. Strategia testowa: co po każdym kroku (patrz bramki niżej) + które testy jednostkowe
   trzeba zaktualizować (importy!) i jak zachować ich semantykę.
5. Ryzyka i plan odwrotu (git revert per krok; żadnych kroków > ~600 linii diffu).

**STOP: dokument przedstaw autorowi do akceptacji. Bez akceptacji nie zaczynaj etapu 1.**

### Etap 1 - wykonanie wg zaakceptowanego planu

Bramki po KAŻDYM kroku (wszystkie muszą być zielone przed następnym):

1. `just test-unit` - 100% pass
2. `just mypy` - 0 błędów (baza wyzerowana w F03; jakikolwiek błąd = regresja kroku)
3. `MOM_SKIP_SS_REVIEW=1 just test-agent "Save and Load Basic"` oraz
   `"Hammer Dialog Flow"` - pass
4. `just validate-world` - bez nowych naruszeń
5. Benchmark klatki bez regresji > 20%: użyj podejścia z
   `doc/audyt/audyt.md` / raportu audytu (konstrukcja Scene wprost + krokowanie
   update/draw headless; baza: update 0,41 ms + draw 1,31 ms na mac-mini)
6. Raz na 2-3 kroki: pełny przebieg wszystkich scenariuszy desktop
   (`MOM_SKIP_SS_REVIEW=1 just test-agent`) i raz web (`just test-web`)

Po zakończeniu każdego kroku - commit na `main` z opisem "B01 krok N: <co>".

## Kryteria akceptacji całego epica

1. `scene.py` (orkiestrator) < 500 linii; żaden nowy moduł > 800 linii.
2. `Scene.update` czyta się jak spis treści: sekwencja wywołań systemów, bez inline
   logiki kolizji/handlu/czasu.
3. Wszystkie bramki testowe zielone; save wykonany przed refactorem wczytuje się po nim
   (test ręczny: `scripts/save_fixtures.py create 0` przed, `quick_load` po).
4. `project/AGENTS.md` zaktualizowany: nowa mapa plików rdzenia + zaktualizowane
   odsyłacze; sekcje opisujące stare lokalizacje poprawione.
5. Gra działa wizualnie identycznie (scenariusze z ss-review na kluczowych ekranach
   + finalna weryfikacja autora na realnym ekranie - headless nie jest wierny dla
   pełnej kompozycji, patrz memory projektu).

## Pułapki (zebrane z audytu i historii projektu)

- `store_map()`/`restore_map()` działają przez `getattr/setattr` po liście
  `self.properties` - przenosząc atrybuty do podsystemów, zaktualizuj tę listę
  i `save_load/manager.py` (`_build_*_from_cache` czytają słownik cache po tych
  samych kluczach).
- `scene.py` robi `from settings import INITIAL_HOUR` (by-value) - testy i narzędzia
  patchują `scene.INITIAL_HOUR`; zmiana miejsca odczytu zepsuje istniejące gotchy
  z memory - w nowym world_clock czytaj `settings.INITIAL_HOUR` dynamicznie
  i zaktualizuj notatki.
- Cykliczne importy: NPC importowany w `load_NPCs` lokalnie ("moved here to avoid
  circular imports") - projektując pakiety, rozwiąż cykl jawnie (typ TYPE_CHECKING,
  wstrzykiwanie), nie przenoś problemu.
- `clear_maze_cache()` woływany z wielu miejsc (load_map, niszczenie ścian) - musi
  pozostać jednym, wspólnym punktem.
- Częściowe metody Scene są monkeypatchowane w testach/narzędziach
  (`Scene.update_routine_npcs` jako sonda - memory "headless-scene-stepping") -
  zachowaj nazwy publicznych metod tam, gdzie to możliwe.
- Emote'y animowane w update także przy zamrożonym świecie (modal open) - nie zgub
  tej gałęzi przy przenoszeniu (scene.py:1955-1964).

## Po zakończeniu

- odhacz B01 w `doc/audyt/audyt.md`
- zaktualizuj memory projektu, jeśli zmieniły się ścieżki z notatek
  (headless-scene-stepping, deterministic-dialog-testing)
