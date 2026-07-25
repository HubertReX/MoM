# B01 - stan realizacji (handoff do wznowienia)

Ostatnia aktualizacja: 2026-07-25, sesja Fable (Faza 2). Architektura
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

## Następny krok: **krok 3 - world_clock.py**

Wg planu (sekcja 5 dokumentu): tick zegara z `Scene.update` (minute_f/hour/day,
~linie 1430-1445 w scene/scene.py), `apply_days`, `day_rng`, `abs_minutes`;
`settings.INITIAL_HOUR` czytać DYNAMICZNIE (K6 - dziś scene.py robi
`from settings import INITIAL_HOUR` by-value; usunąć ten import przy okazji);
sprawdzić `tests/test_deterministic_mode.py` i scenariusz ze `start_hour`.
Potem kroki 4-16 wg tabeli w dokumencie.

## Bramki po każdym kroku (przypomnienie)

1. `just test-unit` (427) 2. `just mypy` = 0 3. `MOM_SKIP_SS_REVIEW=1 just
test-agent "Save and Load Basic"` i `"Hammer Dialog Flow"` 4. `just
validate-world` 5. `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
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
- Kandydat na zadanie A08 (rozpisać w sesji audytowej): web-runner reużywa
  jednego serwera pygbag zamiast restartu per scenariusz (~25 → ~10 min);
  plus `just test-smoke` (5-6 kluczowych scenariuszy desktop).

## Pułapki świeżo potwierdzone w praktyce

- Backticki w `git commit -m` zjada zsh - commituj przez `git commit -F <plik>`.
- Rename + nowe pliki commituj z pathspecami obejmującymi TAKŻE stary plik,
  inaczej `D project/scene.py` zostaje poza commitem (naprawione amendem w kroku 1).
- pygbag nie startuje w świeżym worktree poza repo (nawet z kopią
  `project/build/`) - bisect web rób w głównym repo albo wcale.
- Pełne zestawy: desktop ~18 min, web ~25 min; web-flaki najpierw powtórz 2x,
  potem oglądaj screenshoty z `screenshots/agent/` (Read czyta PNG).
- `_roster_loaded` i podobne dynamiczne atrybuty: przy wynoszeniu kodu z klasy
  mypy wymaga jawnej deklaracji w `__init__`.

## Prompt wznowienia (do nowej sesji, np. Opus)

Kontynuujesz B01 etap 1 (refactor rdzenia MoM). Przeczytaj W CAŁOŚCI:
`doc/audyt/B01-refactor-rdzenia.md`, `doc/refactor-rdzenia-B01.md`,
`doc/audyt/B01-stan-realizacji.md` (ten plik). Architektura jest zaakceptowana;
NIE zmieniaj decyzji D1-D6. Realizuj kroki od **kroku 3** wg planu, z bramkami
po każdym kroku i commitem `B01 krok N: <co>` na main (bez feature branchy).
Gdy bramka nie przechodzi albo plan rozjeżdża się z kodem - STOP i zapytaj.
Po ukończeniu wszystkich kroków: AGENTS.md, memory, odhaczenie B01 w
`doc/audyt/audyt.md`, weryfikacja wizualna autora.
