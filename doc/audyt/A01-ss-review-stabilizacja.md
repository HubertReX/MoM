# A01 - ss-review: stabilny model, checklisty per-scenariusz, werdykt JSON

Priorytet: **P0** (Faza 1). Rozmiar: M. Zależności: brak (można robić od razu).

## Kontekst i problem

Runner testów wizualnych `tests/automate_display_test.py` deleguje ocenę screenshotów do
subagenta `ss-reviewer` (`.opencode/agents/ss-reviewer.md`) przez `opencode run`.
Obecne problemy (zdiagnozowane empirycznie 2026-07-25):

1. Primary model `opencode-go/mimo-v2.5` regularnie timeoutuje (rc=124). Runner czeka
   60 s na martwy model i dopiero potem próbuje fallbacku `google/gemini-3.1-flash-lite`.
   Efekt: wolne testy i "niespójne odpowiedzi" (raz odpowiada jeden model, raz drugi, raz nikt).
2. Prompt w `review_screenshot()` pyta tylko o stan gry ("Expected game state: GAMEPLAY").
   Model NIE ocenia jakości UI, bo nikt go o to nie prosi. Test wykazał, że ten sam model
   z pytaniem o overflow tekstu wykrywa wadę 2/2, a bez pytania - przepuszcza.
3. Werdykt jest wyciągany regexem z free-textu (`parse_review_verdict()`, 3 wzorce) - kruche.

## Cel

Po tym zadaniu: (a) pierwszy strzał zawsze idzie do sprawnego modelu, (b) każdy scenariusz
może zadeklarować, co MA być widoczne i jakie kontrole jakości UI wykonać, (c) werdykt
jest parsowany z bloku JSON, nie regexem po markdown.

## Pliki do zmiany

- `tests/automate_display_test.py` - kolejność modeli, budowa prompta, parser werdyktu
- `tests/scenarios.json` - nowe (opcjonalne) pola asercji `screenshot_review`
- `.opencode/agents/ss-reviewer.md` - stany MoM + format bloku JSON na końcu odpowiedzi
- `project/AGENTS.md` - sekcja "ss-review" (aktualizacja dokumentacji po zmianie)

## Krok 1: kolejność modeli

W `tests/automate_display_test.py` (ok. linii 107):

```python
SS_REVIEW_MODELS: list[str | None] = ["google/gemini-3.1-flash-lite", "opencode-go/mimo-v2.5"]
```

Czyli: gemini staje się primary, mimo zostaje fallbackiem. NIE usuwaj mechanizmu
`MOM_SS_REVIEW_MODEL` (wymuszenie jednego modelu) ani pętli po modelach - działają dobrze.
Zaktualizuj komentarz nad stałą (opisuje starą kolejność).

## Krok 2: checklisty per-scenariusz w scenarios.json

Asercja `screenshot_review` w `tests/scenarios.json` dostaje dwa NOWE, opcjonalne pola:

```json
{
  "type": "screenshot_review",
  "expect": "opis oczekiwania (pole istniejące)",
  "expected_state": "GAMEPLAY",
  "expected_elements": [
    "dialog panel at the bottom with NPC portrait",
    "player HUD with health bar in top-right corner"
  ],
  "ui_quality_checks": [
    "no text overflows or touches any panel frame",
    "all UI elements fully inside their panels"
  ]
}
```

Zasady:

- oba pola są opcjonalne - istniejące scenariusze bez nich muszą działać bez zmian
- gdy pole jest obecne, jego zawartość trafia do prompta (krok 3)
- dodaj `expected_elements`/`ui_quality_checks` do 2-3 istniejących scenariuszy
  dialogowych (np. "Hammer Dialog Flow", "Dialog Open Deterministic") jako wzorzec;
  do pozostałych będą dopisywane przy okazji pracy nad nimi

## Krok 3: budowa prompta i przekazanie obrazka przez `-f`

**Zmiana zachowania OpenCode (zweryfikowana przez autora 2026-07-25):** przekazanie
ścieżki screenshotu inline w prompcie już NIE działa (błąd); działa załącznik przez
`-f`. Wzorzec wywołania (kolejność ma znaczenie - message PIERWSZY, `-f` PO nim,
bo `-f` jest greedy i połyka trailing positional message jako nazwę pliku):

```bash
opencode run --agent ss-reviewer "<prompt>" -f "<ścieżka.png>" --model "google/gemini-3.1-flash-lite" --pure
```

W `review_screenshot()` (ok. linii 145):

1. Zmień budowę `cmd` na: `["opencode", "run", "--pure", prompt, "--agent",
   SS_REVIEW_AGENT, "-f", str(path)]` (+ `--model` jak dotąd). Prompt jako pierwszy
   argument pozycyjny, `-f` PO nim.
2. Usuń z prompta zdanie o ścieżce pliku; obrazek przychodzi jako załącznik.
3. Zaktualizuj docstring funkcji (obecny tłumaczy, czemu ścieżka szła inline - to już
   nieaktualne) oraz komentarz przy `SS_REVIEW_MODELS`: **każdy model na tej liście MUSI
   mieć vision** (`attachment: true`), bo `-f` z modelem bez vision = błąd. Oba obecne
   modele (gemini, mimo) mają vision.

Rozszerz sygnaturę o nowe pola (przekaż je z miejsca, gdzie asercja jest czytana)
i buduj prompt tak:

```python
prompt = (
    "You are validating an automated test screenshot (attached) from the game "
    '"Misadventures of Malachi" (MoM). '
    f"Expected game state: {expected_state or 'described below'}. "
    f"Expectation to verify: {expect} "
    + (f"Expected visible elements: {'; '.join(expected_elements)}. " if expected_elements else "")
    + (f"UI quality checks (each must hold): {'; '.join(ui_quality_checks)}. " if ui_quality_checks else "")
    + "Analyze the attached screenshot and produce your structured report. "
    "Then output, as the FINAL fenced code block, a JSON object exactly of the form: "
    '{"verdict": "PASS"|"FAIL", "state": "<detected state>", "failed_checks": ["..."]}'
)
```

## Krok 4: parser werdyktu

Dodaj nową funkcję i użyj jej PRZED starym regexem (stary zostaje jako fallback,
bo fallback-model może nie umieć w JSON):

```python
def parse_review_json(text: str) -> tuple[str | None, list[str]]:
    """Znajdź ostatni blok JSON z polem verdict; zwróć (verdict, failed_checks)."""
    candidates = re.findall(r"\{[^{}]*\"verdict\"[^{}]*\}", text, re.DOTALL)
    for raw in reversed(candidates):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        verdict = str(data.get("verdict", "")).upper()
        if verdict in ("PASS", "FAIL"):
            return verdict, [str(c) for c in data.get("failed_checks", [])]
    return None, []
```

W `review_screenshot()`: najpierw `parse_review_json(out)`; gdy zwróci werdykt, dołącz
`failed_checks` do `detail` (to trafia do logu runnera). Gdy nie - dotychczasowy
`parse_review_verdict(out)`.

## Krok 5: prompt agenta ss-reviewer

W `.opencode/agents/ss-reviewer.md`:

1. Rozszerz listę stanów w sekcji "State Classification" o realne stany MoM:
   `DIALOG` (panel dialogu z NPC), `TRADE` (panel handlu), `QUEST_LOG` (dziennik zadań, J),
   `HELP` (panel pomocy, H), `INVENTORY`, `SAVE_LOAD` (panel slotów zapisu),
   `DEATH_SCREEN` ("GAME OVER"). Zostaw dotychczasowe stany.
2. W sekcji "Output Format" dodaj na końcu wymóg: po raporcie markdown ZAWSZE jeden
   fenced block `json` w formacie `{"verdict": ..., "state": ..., "failed_checks": [...]}`.
3. NIE zmieniaj pól frontmatter `permission` ani `mode: all` (patrz komentarz w pliku -
   `mode: subagent` jest po cichu ignorowane przez `opencode run --agent`).
4. Zmień `model:` na `google/gemini-3.1-flash-lite` (spójnie z krokiem 1).

## Kryteria akceptacji

1. `MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python3
   tests/automate_display_test.py "Save and Load Basic"` (bez `MOM_SKIP_SS_REVIEW`)
   kończy się sukcesem, a log zawiera `[ss-review] google/gemini-3.1-flash-lite -> PASS`.
2. Ten sam scenariusz z `MOM_SKIP_SS_REVIEW=1` działa bez zmian (skip nadal respektowany).
3. Ręczny test negatywny: uruchom review na screenshocie z wadą
   `screenshots/barman_dialog_overflow.png` z checkiem "no text overflows any panel frame" -
   werdykt FAIL, a `failed_checks` wymienia overflow. Można wywołać funkcję wprost:

   ```bash
   .venv/bin/python3 -c "
   import sys; sys.path.insert(0, 'tests')
   from automate_display_test import review_screenshot
   from pathlib import Path
   v, d = review_screenshot(Path('screenshots/barman_dialog_overflow.png'),
       'dialog panel renders correctly', 'DIALOG',
       expected_elements=['dialog panel with NPC text'],
       ui_quality_checks=['no text overflows or touches any panel frame'])
   print(v, d)"
   ```

4. Scenariusze bez nowych pól (`expected_elements`/`ui_quality_checks`) przechodzą jak dotąd.
5. `just test-unit` przechodzi w całości (nie powinno być dotknięte, ale sprawdź).

## Pułapki

- Kolejność argumentów opencode: message PIERWSZY, `-f` PO nim - `-f` jest greedy
  (`[array]`) i połyka trailing positional message jako nazwę pliku
  (`Error: File not found: <twój prompt>`).
- Do `SS_REVIEW_MODELS` wolno dodawać wyłącznie modele z vision - `-f` z modelem
  bez vision kończy się błędem, nie degradacją.
- `--pure` w komendzie opencode jest konieczne (wyłącza plugin discover-models robiący
  HTTP na starcie). Nie usuwaj.
- Timeout: zostaw owijkę `_timeout_cmd` (gtimeout/timeout) - chroni przed wiszącym CLI.
- Nie loguj pełnej odpowiedzi modelu do stdout runnera (za dużo szumu) - tylko werdykt,
  model i `failed_checks`.
- JSON w odpowiedzi modelu może być otoczony ```json ...``` - regex w kroku 4 znajduje
  goły obiekt, więc działa w obu wypadkach; nie zakładaj, że blok jest ostatnią linią.

## Po zakończeniu

- zaktualizuj sekcję "ss-review" w `project/AGENTS.md` (nowa kolejność modeli, pola
  checklisty, format werdyktu)
- odhacz A01 w `doc/audyt/audyt.md`
- commit na `main`: `A01: ss-review - gemini primary, checklisty scenariuszy, werdykt JSON`
