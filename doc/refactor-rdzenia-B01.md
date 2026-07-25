# B01 - architektura docelowa refactoru rdzenia (etap 0)

Skrót dokumentu decyzyjnego. Pełna wersja (tabele opcji per decyzja, plan 16 kroków,
kontrakty, ryzyka):
[refactor-rdzenia-b01-2026-07-25.html](_attachements/refactor-rdzenia-b01-2026-07-25.html)
(podgląd: `docserve start doc/_attachements/refactor-rdzenia-b01-2026-07-25.html`).

Status: **zaakceptowany 2026-07-25**, etap 1 w toku - postęp i instrukcja
wznowienia: [audyt/B01-stan-realizacji.md](audyt/B01-stan-realizacji.md)
(zrobione kroki 0-10, następny: krok 11 movement).

## Decyzje (rekomendacje)

- **D1 - mechanika podziału:** systemy jako moduły z funkcjami przyjmującymi `scene`/`npc`
  jawnie; klasy `Scene`/`NPC` trzymają CAŁY stan (atrybuty bez zmian - kontrakt save)
  i cienkie delegaty dla nazw publicznych. Bez mixinów, bez komponentów-obiektów.
- **D2 - `Player(NPC)`:** dziedziczenie zostaje; podział tylko na pliki.
- **D3 - żywe globale:** `scene.SHOW_DEBUG_INFO` czytane na żywo przez `help.py`
  i `characters.py`; pakiet `scene/` dostaje PEP 562 `__getattr__` w `__init__.py`,
  docelowo flaga mieszka w `scene/debug_overlay.py`.
- **D4 - obsługa INPUTS:** wychodzi z `Scene.update` do `scene/player_actions.py`
  (rozszerzenie szkicu z zadania - bez tego update nie będzie spisem treści).
- **D5 - narzędzia CSV z `game.py`:** do `config_model/csv_tools.py` (funkcje na `conf`);
  CLI `--task` bez zmian.
- **D6 - pakiet `characters/`:** 6 modułów - `npc`, `player`, `movement`, `combat`,
  `animation`, `inventory` (handel/ekwipunek; rozszerzenie szkicu, żeby `npc.py`
  nie przekroczył 800 linii).

## Docelowe pakiety

```text
project/scene/      __init__ (eksport + __getattr__), scene (orkiestrator), map_loader,
                    world_clock, collisions, player_actions, routines_director, map_state,
                    night_filter, intro, debug_overlay, agent_api
project/characters/ __init__, npc, player, movement, combat, animation, inventory
project/config_model/csv_tools.py
```

## Kontrakty nietykalne (skrót)

K1 format save (atrybuty po nazwach + lista `properties`), K2 sygnatura `Scene(...)`,
K3 API agenta/testów (delegaty), K4 `from scene import Scene` / `from characters import
NPC, Player`, K5 dual-target (pydantic tylko desktop, pygbag pakuje podpakiety),
K6 `import settings` + odczyt dynamiczny w nowych modułach, K7 jeden `clear_maze_cache()`,
K8 emote przy modal-open, K9 żywe globale przez `__getattr__`.

## Plan wykonania

16 kroków, każdy < ~600 linii diffu, osobny commit `B01 krok N: <co>`, odwracalny przez
`git revert`. Kolejność: 0 fixture+benchmark → 1 pakiet scene/ (czyste przeniesienie) →
2 map_loader → 3 world_clock → 4 collisions → 5 player_actions → 6 routines_director →
7 map_state → 8 night_filter+intro → 9 debug_overlay+agent_api → 10 pakiet characters/ →
11 movement → 12 combat → 13 animation → 14 inventory → 15 game.py/CSV → 16 finalizacja
(AGENTS.md, memory, ss-review, weryfikacja wizualna autora).

Bramki po każdym kroku: `just test-unit`, `just mypy` (0), scenariusze "Save and Load
Basic" + "Hammer Dialog Flow", `just validate-world`, benchmark klatki (baseline: update
0,41 ms / draw 1,31 ms, budżet +20%), kontrola wczytania fixture sprzed refactoru.
Po krokach 1 i 10 pełny `just test-web` (pygbag musi spakować nowe podpakiety).
