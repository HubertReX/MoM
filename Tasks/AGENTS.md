# AGENTS.md — Tablica zadań

Lekki, plikowy system zadań dla **człowieka i agentów AI** (CC, OpenCode, Pi, Hermes).
Czysty Markdown, kompatybilny z pluginem **Obsidian Kanban**. Działa też jako zwykły
tekst — agent edytuje pliki, nawet bez Obsidiana.

## Co gdzie jest

| Plik / katalog | Rola |
|---|---|
| `board.md` | Tablica Kanban: 5 kolumn roboczych + `Archive`. **Cienkie** karty = wikilinki + flagi. |
| `Backlog/` | Po jednej notatce na zadanie (`T-00X <tytuł>.md`) — pełny kontrakt. |
| `_templates/_Template.md` | Szablon nowego zadania (folder szablonów Obsidiana). |
| `_attachments/` | Folder na obrazki i inne załączniki do zadań (domyślny w Obsidian). |
| `bin/moab` | **CLI, którym sterujesz tablicą**: `new`/`claim`/`review`/`block`/`done`/`move`/`retag`/`rm`/`log`/`status`/`sync`/`assign`/`web`. |

**Źródło prawdy = `board.md`.** Kolumna karty = `status`, tagi karty = `agent`/`priority`/
`type`, `@{data}` = `due`. **Nie edytuj boardu ani frontmatteru ręcznie** — mały model
zapętla się na exact-match edycjach markdown. Zamiast tego **wołaj `python3 bin/moab …`**,
które mutują board i synchronizują frontmatter notatek deterministycznie. Jedyne ręczne
pisanie to **treść notatki** (Goal/Context/Plan w świeżo utworzonym pliku).

## Kolumny i własność piłki

| Lane | Kto trzyma piłkę | AI może brać? | Znaczenie |
|---|---|---|---|
| 🧊 **Backlog** | człowiek | ❌ nie | Pomysły, jeszcze nie do wzięcia. Niedoprecyzowane mają `#raw`. **Nigdy** stąd nie startuj. |
| 🟢 **Ready for AI** | AI (kolejka) | ✅ **auto** | W pełni opisane, kryteria akceptacji jasne. Bierz **górną** kartę. |
| 🤖 **In Progress** | AI | w toku | Pracujesz; oznaczone `#<agent>`. **WIP = 1 karta na agenta**. |
| 🙋 **Needs You** | człowiek | ❌ nie | Oddałeś piłkę. `#blocked` = utknąłeś (potrzebna decyzja); `#review` = skończone, czeka na akcept. |
| 🏁 **Done** | — | — | Zatwierdzone i ukończone. |

## Flagi na karcie (`#tagi` → kolorowe chipy w Kanbanie)

- **Priorytet:** `#p1` `#p2` `#p3`
- **Typ:** `#feature` `#bug` `#chore` `#spike` `#docs`
- **Stan w obrębie lane:** `#raw` (niedoprecyzowane) · `#blocked` · `#review`
- **Agent (claim):** `#cc` `#opencode` `#pi` `#hermes` (tag, nie `@` — `@` jest zarezerwowane na **daty/terminy**, np. `@{2026-06-24}`)

Przykład karty: `- [ ] [[T-003 Add FPS counter toggle]] #feature #p2 #cc`

## Protokół agenta

> Złota zasada: **steruj tablicą wyłącznie komendami `python3 bin/moab …`.** Nie edytuj
> `board.md` ani frontmatteru ręcznie. Wszystkie komendy uruchamiaj z katalogu vaulta
> (tam gdzie jest `board.md`), albo dodaj `--dir <vault>`.

1. **Wybierz zadanie.** `python3 bin/moab status` → weź **górną** kartę z 🟢 **Ready for AI**.
   Nigdy nie tykaj 🧊 Backlog ani kart z `#raw`.
   Jeśli `status` pokazuje pustą kolejkę — **zatrzymaj się i czekaj** na człowieka.
2. **Claim.** `python3 bin/moab claim <id> --agent <twój_tag>` (np. `--agent cc`). Wykonaj commit.
   Przenosi kartę do In Progress, taguje, dopisuje Agent Log, synchronizuje. **WIP = 1**.
3. **Pracuj.** Realizuj wg sekcji *Goal / Plan / Definition of Done* w notatce; trzymaj się *Constraints*.
   Odhaczaj zrobione kroki (`[ ]` → `[x]`). Po zmianach na boardzie — commit.
   Postęp loguj: `python3 bin/moab log <id> --agent <tag> --note "<postęp>"`. Commit.
4. **Zablokowany?** `python3 bin/moab block <id> --agent <tag> --note "<pytanie/decyzja>"` →
   karta do 🙋 **Needs You** z `#blocked`. Commit. **Zatrzymaj się** — czekaj na człowieka.
5. **Skończone?** Sprawdź sekcję '✅ Definition of Done' (lub '🎯 Goal / Outcome' jeśli pusta)
   i upewnij się, że każdy punkt jest odhaczony. Następnie:
   `python3 bin/moab review <id> --agent <tag> --note "<co zrobiono, jak testować>"`
   → karta do 🙋 **Needs You** z `#review`. Commit. **Czekaj na akceptację człowieka.**
   Gdy człowiek powie "OK" albo "zrobione" — `python3 bin/moab done <id>`. **Wróć do kroku 1.**

## Zakładanie nowego zadania

1. `python3 bin/moab new "<tytuł>" --type <feature|bug|chore|spike|docs> --prio <p1|p2|p3>`
   `[--lane ready] [--raw] [--due RRRR-MM-DD]` → tworzy notatkę (nadaje `T-00X`),
   dodaje kartę na board, synchronizuje frontmatter, drukuje id.
2. Uzupełnij w notatce sekcje **Goal / Context / Plan / Definition of Done** (jedyne ręczne pisanie).

## Pozostałe komendy

| Komenda | Do czego |
|---|---|
| `python3 bin/moab move <id> --to <lane>` | Przenosi kartę do dowolnej kolumny (opcjonalnie `--review`/`--blocked`/`--raw`). |
| `python3 bin/moab retag <id> [--prio pX] [--type T] [--add tag] [--remove tag]` | Edytuje tagi karty i synchronizuje. |
| `python3 bin/moab rm <id>` | Usuwa kartę z boardu i notatkę z Backlog/. |
| `python3 bin/moab assign <id> --agent <name> [--model <m>] [--long] [--run]` | Generuje (lub wykonuje) komendę `opencode run`. Bez `--long`: tylko claim. Z `--long`: pełne instrukcje implementacji + review + block. `--model` ustawia model opencode. |
| `python3 bin/moab install <dir> [--project-name <name>]` | Instaluje MOAB z opcjonalną nazwą projektu (auto: git remote > folder). |
| `python3 bin/moab web [--port PORT]` | Uruchamia webowy edytor FastAPI (domyślny port: 8770). |
| `python3 bin/moab watch --agent <name> [--model <m>] [--interval 10] [--limit 1]` | Monitoruje board i automatycznie przypisuje zadania Ready for AI do agenta. |

## Sync i status

- `python3 bin/moab sync` — jedyny sposób, w jaki frontmatter się zmienia.
  Wykonuj zawsze po ręcznej zmianie boardu. `python3 bin/moab sync --check` (exit 1
  przy rozjeździe) nadaje się do hooka pre-commit.
- `python3 bin/moab status` — szybki podgląd w terminalu (kolejka per kolumna).
- Daty/terminy używają `@`, zapis `@{RRRR-MM-DD}`.

## Formatowanie notatek (Obsidian Markdown)

Notatki w `Backlog/` muszą przestrzegać poniższych reguł. `moab sync`
automatycznie naprawia naruszenia; `moab sync --check` (uruchamiany przez
pre-commit hook) blokuje commit gdy są do naprawy.

- **Pusta linia po nagłówku** — po `##` / `###` itd. musi być pusta linia.
- **Brak końcowych spacji** — żadna linia nie może kończyć się spacją/tabem.
- **Maks. 2 puste linie z rzędu** — 3+ puste linie są zwijane do 2.
- **Frontmatter tylko przez `moab sync`** — nie edytuj pól `status/owner/agent/priority/type/state/due/updated` ręcznie.

## Zasady

- Po skończonym zadaniu zrób commit i zaproponuj "czy chcesz przejrzeć zmiany?".
- Dłuższe zadania dziel na podzadania (np. T-003 → T-003-a, T-003-b; dodaj link do rodzica w sekcji '🧭 Context').
- Przestrzegaj też zasad z osobnego pliku AGENTS.md projektu (jeśli istnieje).
