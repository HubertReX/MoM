---
id: T-044
title: DS: umieszczenie pozostalych postaci z dialogami na mapie (Barman, Potioneer, Clapback, Sarcasmia)
status: needs-you
owner: human
priority: p2
type: feature
agent: opencode
created: 2026-07-06
updated: 2026-07-06
tags:
  - task
state: review
---
# T-044 - DS: umieszczenie pozostałych postaci z dialogami na mapie

## 🎯 Goal / Outcome

- [ ] Wszystkie 4 pozostałe postacie dialogowe są widoczne i zagadywalne na mapie: Barman Absinthrayner, Potioneer Puzzlemint, Clapback Sword, Madame Sarcasmia (Hammer już jest)
- [ ] Każda ma przypisany sprite/model i otwiera swój graf dialogu (`dialog_key` z `config.json`)
- [ ] Rozmieszczenie sensowne fabularnie (np. Barman w karczmie), bez kolizji ze ścianami/obiektami

## 🧭 Context

- **Kontekst wspólny:** [[DS-epic-brief]].
- Zgłoszone przez użytkownika: "nie widzę pozostałych postaci, które mają dialogi na mapie, choć Hammer został dodany".
- **Stan:** wszystkie 5 postaci mają definicje w `project/config_model/config.json` w sekcji `characters` (Hammer ~l.282, Barman Absinthrayner ~l.299 `dialog_key: BARMAN_ABSINTHRAYNER`, Clapback Sword ~l.316 `CLAPBACK_SWORD`, Potioneer Puzzlemint ~l.333, Madame Sarcasmia) oraz gotowe grafy dialogów. Brakuje ich **na mapie**.
- **Mechanizm placementu (potwierdzony):** `project/scene.py::load_NPCs()` (linie ~738-761) spawnuje NPC z warstwy obiektów Tiled `spawn_points`; każdy obiekt ma `name` (= klucz NPC, np. "Hammer") i property `model_name` (sprite).
- **Właściwa mapa (potwierdzone 2026-07-07):** `project/assets/NinjaAdventure/maps/Village.tmx` (NIE `project/assets/map/*.tmx` - tamte nie mają warstwy `spawn_points`). Hammer stoi tam na (880, 680), `model_name=Hammer`. Ludzcy NPC (Marry, Rob, Bart, Johny, Fred, Hammer) wszyscy na zewnątrz w wiosce. Interiory `VillageHouse.tmx` i `JacobsChamber.tmx` istnieją (portale w warstwie `interactions`), ale mają puste `spawn_points`. Strefy w Village (warstwa `zones`): `backyard` (624,688), `plains` (752,752), `wilderness` (800,640), `water`/`shore` (wschód+południe). Brak nazwanego budynku "karczma/sklep".
- Postacie nie są w `project/config_model/characters.csv` (tam m.in. Player/Marry/Rob/zwierzęta) - sprawdzić, czy NPC dialogowi wymagają wpisu w characters.csv (statystyki/model) oprócz sekcji `characters` w config.json.

## ⛓️ Constraints

- Dual-target desktop + web.
- Edycja map `.tmx` w Tiled - trzymać się istniejącej warstwy `spawn_points` i konwencji nazw (obiekt `name` = klucz NPC).
- Nazwy NPC muszą zgadzać się z kluczami w `config.json` `characters` (inaczej brak dialogu/modelu).
- Type hints wymagane (jeśli dotyka kodu).

## 🪜 Plan / Subtasks

- [x] Ustalić na której mapie i gdzie osadzić każdą postać (fabularnie). **Zdecydowane - opcja A:** wszyscy na zewnątrz w `Village.tmx`, tematycznie rozproszeni (patrz obsada niżej).
- [ ] Dodać 4 obiekty w warstwie `spawn_points` mapy `Village.tmx` (name = klucz NPC z config, property `model_name` = sprite). Proponowane pozycje (dostroić w Tiled, unikać kolizji ze ścianami):
  - **Barman Absinthrayner** → przy wejściu do VillageHouse ~(700, 720)
  - **Potioneer Puzzlemint** → strefa `backyard` ~(624, 660)
  - **Clapback Sword** → przy wyjściu do Maze ~(950, 700)
  - **Madame Sarcasmia** → skraj `wilderness` ~(800, 620)
- [ ] Zapewnić sprite/model dla każdej postaci (dobór z dostępnych arkuszy postaci) oraz ew. wpis w `characters.csv`.
- [ ] Zweryfikować w grze: podejście do każdej postaci otwiera właściwy dialog (Barman->BARMAN_ABSINTHRAYNER itd.).
- [ ] Test wizualny per postać (screenshot rozmowy).

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

- 2026-07-06 cc (review): utworzony na życzenie użytkownika. Postacie są w config.json, ale bez obiektów w warstwie Tiled `spawn_points` (spawn wg `scene.py::load_NPCs`).
- 2026-07-07 decyzja (autor): **opcja A** - wszyscy na zewnątrz w `Village.tmx`, tematycznie rozproszeni. Poprawiono ścieżkę mapy w Context (`NinjaAdventure/maps/Village.tmx`, nie `assets/map/`). Konkretna obsada + współrzędne w Plan.
- 2026-07-07 14:41 opencode: claimed, starting

## 🙋 Needs-You / Questions

- (brak - wszystko rozstrzygnięte)
