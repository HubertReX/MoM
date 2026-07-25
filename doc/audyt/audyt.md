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

- [x] [A05 - scenariusz autosave po zmianie reguły (tylko wejście do labiryntu)](A05-scenariusz-autosave-po-zmianie-reguly.md) - P2
- [x] [A06 - CLI `agent_ctrl.py` nic nie wysyła (martwy blok po `sys.exit`)](A06-agent-ctrl-cli-nieosiagalne.md) - P2
- [x] [A07 - zmienne środowiskowe testów na web (domknięcie A04 - jeden kanał `MoM.env`)](A07-zmienne-srodowiskowe-na-web.md) - P1

### Faza 2 - wielki refactor rdzenia

- [x] [B01 - refactor `scene.py`/`characters.py`: dokument architektury docelowej + wykonanie (epic, model Fable/Opus)](B01-refactor-rdzenia.md) - P0
- [ ] G01 - codegen `config.py` (web) z `config_pydantic.py` - P1
- [ ] B02 - polityka wersji save + minimalna migracja - P2

### Faza 3 - brakujące mechaniki

- [ ] D01 - AudioManager: muzyka per mapa, SFX eventy, głośność, web-safe - P1
- [ ] D02 - design doc mini-progresji statystyk gracza: szybkość, max_health, damage, bazowy sentyment (rosnący i malejący przez decyzje); progresja przez przedmioty już istnieje - P2
- [ ] E01 - noc/FoW fallback bez shaderów (desktop+web) - P1
- [ ] E02 - FPS_CAP=60 + profil wydajności web - P2
- [ ] H02 - śmierć gracza: codzienny autosave (rano lub o północy) + po śmierci od razu ekran wczytania gry (decyzja autora 2026-07-25; obecny twardy reset zostaje jako tło, bo gracz i tak wczytuje) - P2
- [x] [U01 - bar.py: scrollbar.png jako realne źródło wyglądu suwaka (asset-driven)](U01-scrollbar-asset-driven.md) - P2

### Faza 4 - treść prologu i późniejsze

- [ ] C02 - stopniowe ujednolicenie kluczy Tiled ↔ config - P3
- [ ] H01 - ambient barks + wskaźnik aktywnego questa na HUD - P3

## Zasady realizacji zadań (dla agentów)

- przed startem przeczytaj plik zadania w całości oraz linkowane sekcje `AGENTS.md`
- po zmianach: `just test-unit` musi przechodzić w całości; scenariusze agentowe wskazane
  w zadaniu muszą przechodzić z `MOM_SKIP_SS_REVIEW=1` oraz (gdy zadanie tego wymaga) z ss-review
- każda zmiana musi działać na desktop i web (złota zasada dual-target)
- commit bezpośrednio na `main` z opisem: co + dlaczego + objaw naprawianego problemu
- po zakończeniu zaktualizuj odpowiedni `AGENTS.md` oraz odhacz zadanie w tym pliku
