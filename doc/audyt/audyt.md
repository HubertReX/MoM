# Audyt projektu MoM - 2026-07-25

Zbiorczy audyt architektury, długów technicznych i projektu gry, wykonany w sesji
Claude Code (Opus) jako podstawa długofalowego planu rozwoju.

- **Pełny raport (HTML, motyw jasny/ciemny, sekcje zwijane):**
  [audyt-architektury-2026-07-25.html](../_attachements/audyt-architektury-2026-07-25.html)
  (podgląd: `docserve start doc/_attachements/audyt-architektury-2026-07-25.html`)

## Legenda oznaczeń

Dwa poziomy identyfikatorów - myślnik odróżnia znalezisko od zadania:

- **Znaleziska audytu** (litera-myślnik-numer, opisują problem; szczegóły w raporcie HTML):
  - `D-1…D-13` - Dług techniczny / błąd projektowy (rozdz. 4 raportu)
  - `G-1…G-5` - Gameplay: obserwacja o projekcie gry (rozdz. 9 raportu)
- **Zadania backlogu** (litera obszaru + numer, bez myślnika; pliki w tym katalogu):
  - `Axx` - testy Automatyczne i ss-review (autonomia agentów)
  - `Bxx` - rdzeń silnika: wielki refactor, save/load (Big refactor)
  - `Cxx` - spójność encji i kluczy (Consistency)
  - `Dxx` - nowe mechaniki gry: audio, progresja (Dodatkowe mechaniki)
  - `Exx` - wydajność i Efekty (noc/FoW, FPS, web)
  - `Fxx` - Fixy porządkowe (utils, dokumentacja, mypy)
  - `Gxx` - Generowanie configu (codegen pydantic → web)
  - `Hxx` - świat gry i treść (barks, śmierć gracza, Humor)
  - `Uxx` - UI / design system

Przykład kolizji liter: `D-2` (dług: podwójny model configu) to nie `D02` (zadanie:
design progresji); `G-1` (znalezisko: kara śmierci) to nie `G01` (zadanie: codegen).

## Decyzje kierunkowe (ustalone w sesji)

- ss-review: gemini jako primary + checklisty per-scenariusz + asercje stanu z runtime + layout self-checks; bez golden images
- noc/FoW na web: najpierw tani fallback bez shaderów (jedna ścieżka kodu desktop+web)
- config: wersja web (dataclassy) generowana z modeli pydantic
- rdzeń: jeden duży, zaplanowany refactor `scene.py`/`characters.py`
- encje: walidator `just validate-world` + mapa przepływu + stopniowe ujednolicenie kluczy
- audio: pełny szkielet od razu (muzyka per mapa, SFX eventy, głośność, web-safe)
- progresja statystyk: najpierw dokument decyzyjny, kod po akceptacji
- priorytety: (1) naprawa ss-review i testów, (2) wielki refactor rdzenia

## Prompty startowe sesji

- [Faza 1 - Opus](prompt-faza-1.md) - zadania A01-A04, C01, F01-F03; wznawialny
  (agent pomija odhaczone zadania)
- [Faza 2 - Fable](prompt-faza-2.md) - B01 z bramką akceptacji architektury po etapie 0
- [Faza 3](prompt-faza-3.md) - mechaniki: E01/E02, D01, H02, U01, D02 (dwie bramki
  „zapytaj autora": sonda web w D01 i akceptacja dokumentu w D02)

## Zadania

Każde zadanie = osobny plik md w tym katalogu, pisany dla agentów AI słabszych niż
Fable/Opus: pełny kontekst, pliki do zmiany, kryteria akceptacji, komendy weryfikacji,
pułapki. Status: `[ ]` do napisania, `[x]` gotowy do realizacji, a sufiks
`✅ <data>` = **zrealizowane** (kod scommitowany, kryteria akceptacji spełnione).

### Faza 1 - fundament autonomii agentów

- [x] [A01 - ss-review: stabilny model, checklisty, werdykt JSON](A01-ss-review-stabilizacja.md) - P0 ✅ 2026-07-25
- [x] [A02 - agent_ctrl: `debug_ui_state` + asercje stanu w runnerze](A02-agent-ctrl-asercje-stanu.md) - P0 ✅ 2026-07-25
- [x] [A03 - layout self-checks w UI (overflow = twardy błąd)](A03-layout-selfchecks.md) - P0 ✅ 2026-07-25
- [x] [A04 - tryb deterministyczny testów (seed, cząstki, godzina)](A04-tryb-deterministyczny-testow.md) - P1 ✅ 2026-07-25
- [x] [C01 - `just validate-world`: walidator encji cross-source](C01-validate-world.md) - P0 ✅ 2026-07-25
- [x] [F01 - cleanup `utils/`: black.tmpl i find_bad_png do `scripts/`, CI, codegraph ignore](F01-utils-cleanup.md) - P1 ✅ 2026-07-25
- [x] [F02 - aktualizacja AGENTS.md i docs design systemu do stanu kodu](F02-aktualizacja-dokumentacji.md) - P1 ✅ 2026-07-25
- [x] [F03 - mypy do zera: usunięcie stałego szumu 23 błędów (przed B01!)](F03-mypy-do-zera.md) - P1 ✅ 2026-07-25

Dopisane po realizacji Fazy 1 (znaleziska z sesji 2026-07-25, oba zastane - nie regresje):

- [x] [A05 - scenariusz autosave po zmianie reguły (tylko wejście do labiryntu)](A05-scenariusz-autosave-po-zmianie-reguly.md) - P2 ✅ 2026-07-25
- [x] [A06 - CLI `agent_ctrl.py` nic nie wysyła (martwy blok po `sys.exit`)](A06-agent-ctrl-cli-nieosiagalne.md) - P2 ✅ 2026-07-25
- [x] [A07 - zmienne środowiskowe testów na web (domknięcie A04 - jeden kanał `MoM.env`)](A07-zmienne-srodowiskowe-na-web.md) - P1 ✅ 2026-07-25

### Faza 2 - wielki refactor rdzenia

- [x] [B01 - refactor `scene.py`/`characters.py`: dokument architektury docelowej + wykonanie (epic, model Fable/Opus)](B01-refactor-rdzenia.md) - P0 ✅ 2026-07-26 (kroki 0-16: pakiety `project/scene/` i `project/characters/`, `config_model/csv_tools.py`; stan: [B01-stan-realizacji.md](B01-stan-realizacji.md))
- [x] [A08 - web-runner: jeden serwer pygbag na przebieg + `just test-smoke`](A08-web-runner-jeden-pygbag-i-smoke.md) - P1 ✅ 2026-07-25 (pełny web 25 → 11,5 min; `just test-smoke` 96 s)
- [x] [G01 - codegen `config.py` (web) z `config_pydantic.py`](G01-codegen-config-web.md) - P1
- [x] [B02 - polityka wersji save + mechanizm migracji](B02-polityka-wersji-save.md) - P2 ✅ 2026-07-28 (jeden numer wersji gry = zapisu jako string + `version_code`, `save_compatibility` jako jedyna bramka, migracje kluczowane wersją zmiany formatu i puste do 1.0, widoczna odmowa + koniec zwijania stosu na ekranie śmierci)

### Faza 3 - brakujące mechaniki

Kolejność wykonania: E01 → E02 (mierzy pipeline po E01) → D01 → H02 → U01 → D02.
Decyzje autora z 2026-07-28 są wpisane w pliki zadań (assety audio z `~/Projects/RPG`,
mapowanie w `audio.toml`, autosave o 6:00 do slotu 0, rozdzielenie nocy i mgły wojny).

- [x] [E01 - filtr nocy: jedna ścieżka kodu desktop+web (cache, koniec gałęzi `IS_WEB`)](E01-filtr-nocy-desktop-i-web.md) - P1 ✅ 2026-07-29 (cache kół świateł + bufory alokowane raz + wczesne wyjście w dzień; desktop `draw` w dzień 1,27 → 0,78 ms; trzy tryby kompozycji pod `settings.NIGHT_FILTER_MODE` zamiast nieskutecznego `FILTER_SCALE=16` - decyzja autora)
- [x] [E02 - FPS_CAP=60 + profiler sekcji klatki i profil web z liczbami](E02-fps-cap-i-profil-web.md) - P2 ✅ 2026-07-30 (`FPS_CAP=60`, profiler `MOM_PROFILE` w `Game.run` - update/draw/flip, agregacja 1s, zero kosztu wyłączony; profil web w [E02-profil-web-wyniki.md](E02-profil-web-wyniki.md): budżet 16,7 ms z dużym zapasem, `test-smoke` 96 → 105 s; stabilność `dt` i decyzja `tick` vs `tick_busy_loop` w [E02-dt-jitter-desktop.md](E02-dt-jitter-desktop.md))
- [x] [D01 - AudioManager: muzyka per mapa, SFX eventów, głośność, web-safe](D01-audio-manager.md) - P1 ✅ 2026-07-29 (manifest `config_model/audio.toml` + `project/audio.py`, 20 eventów SFX, 3 suwaki głośności, bramka gestu na web z `navigator.userActivation`; assety 5,9 MB, `web.zip` 1,3 → 7,1 MB)
- [x] [H02 - dzienny autosave o 6:00 do slotu 0 (ekran wczytania po śmierci już jest - B02)](H02-autosave-dzienny.md) - P2
- [x] [U01 - bar.py: scrollbar.png jako realne źródło wyglądu suwaka (asset-driven)](U01-scrollbar-asset-driven.md) - P2 ✅ 2026-08-01 (sprite parsowany na starcie przez `bar.load_model()`, kolory = role + color-swap, struktura z pikseli; sprite odtwarza sam siebie 1:1 w `tests/test_bar_asset.py`; nowy scenariusz agentowy „Panel Bars Asset Driven"; decyzja autora: zostawiamy asset jak jest, więc suwaki są węższe o 4 px - ramka 2 px zamiast 4 px)
- [x] [D02 - dokument decyzyjny mini-progresji statystyk (szybkość, max_health, damage, bazowy sentyment ±); kończy się dokumentem do akceptacji](D02-design-progresji-statystyk.md) - P2

### Faza 4 - treść prologu i późniejsze

- [x] [E03 - prawdziwa mgła wojny w labiryncie (dokument decyzyjny + implementacja); po E01](E03-fog-of-war-labirynt.md) - P3
- [ ] C02 - stopniowe ujednolicenie kluczy Tiled ↔ config - P3
- [ ] H01 - ambient barks + wskaźnik aktywnego questa na HUD - P3

## Zasady realizacji zadań (dla agentów)

- przed startem przeczytaj plik zadania w całości oraz linkowane sekcje `AGENTS.md`
- po zmianach: `just test-unit` musi przechodzić w całości; scenariusze agentowe wskazane
  w zadaniu muszą przechodzić z `MOM_SKIP_SS_REVIEW=1` oraz (gdy zadanie tego wymaga) z ss-review
- każda zmiana musi działać na desktop i web (złota zasada dual-target)
- commit bezpośrednio na `main` z opisem: co + dlaczego + objaw naprawianego problemu
- po zakończeniu zaktualizuj odpowiedni `AGENTS.md` oraz odhacz zadanie w tym pliku
