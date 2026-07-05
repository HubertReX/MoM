# Dialog System

Brief dla agentów: [[Tasks/DS-epic-brief.md]]

## Podsumowanie

**D3 rozstrzygnięte** - mapowanie naniesione do obu tabel + finalna tabela konwersji w Ustaleniach. Wszystkie **11 decyzji (D1-D11) zamknięte**.

**10 tasków MOAB w Backlog** (epic „DS: Dialog System"), każdy z Goal / Context (zależności jako wiki-linki + odwołania do decyzji D#) / Plan / DoD:

| ID    | Task                               | Trud. | Zależy od                  |
| ----- | ---------------------------------- | ----- | -------------------------- |
| T-029 | Encje dialogu + init_dialog        | #M    | (fundament)                |
| T-032 | Silnik warunków - mini-DSL         | #L    | T-029                      |
| T-023 | Model NPC + pola sentymentu        | #M    | T-029                      |
| T-024 | Pipeline importu MD→config         | #L    | T-029, T-023               |
| T-033 | UI DialogPanel - opcje i wybór     | #L    | T-029, T-024               |
| T-034 | Efekty - adapter ResultSink        | #M    | T-029, T-023, T-033        |
| T-030 | Persystencja stanu rozmowy         | #M    | T-023, T-033, T-034        |
| T-035 | Sentyment w rozgrywce              | #L    | T-032, T-023, T-033, T-034 |
| T-028 | Migracja postaci + web smoke-test  | #M    | T-024, T-033, T-034, T-030 |
| T-036 | Feedback zmiany sentymentu (later) | #S    | T-035                      |

Rozkład trudności:

- **4×#L** (silnik, pipeline, UI, sentyment - dla mocniejszych modeli),
- **5×#M**,
- **1×#S** (feedback - dla małego modelu).


## Plan: przeniesienie dialogów RPG -> MoM

0. Rozpoznanie decyzji (spike): eval vs mini-DSL, i18n w MoM, format save stanu rozmowy -> ADR w doc/
1. Encje (core): przenieść dialog_node.py (7 kategorii, slots) do project/, dodać init_dialog(); test w pamieci
2. Silnik warunkow (ryzyko #1): check_condition() wg etapu 0, whitelist kontekstu; test realnych warunkow
3. Model NPC + sentyment: dialog_key, dialog, selected_options_dict, sentiment, disposition, known_disposition (bez pydantic na web)
4. Pipeline danych (ryzyko #6): 1 postac (Hammer) MD->config lub wprost JSON; mapowanie tagow rich->MoM
5. UI lista opcji i wybor (ryzyko #4): DialogPanel render + klawisze 1-9/pad/mysz, przejscie next_node, stan Talk
6. Efekty wezlow (ryzyko #8): process_result -> Inventory/HP/zloto, flaga visited
7. Persystencja (ryzyko #5): stan rozmowy do save/load (oba backendy), testy korupcji
8. Reszta postaci + web smoke-test: 4 postaci, just serve-web, testy wizualne

## Ryzyka

1. eval() w warunkach (krytyczne)
2. Brak Pydantic na web + save/load (krytyczne)
3. Dialekt znacznikow rich -> MoM RichText (wazne)
4. Turowe UI -> real-time pygame (wazne)
5. Persystencja + flaga visited (wazne)
6. Kruchy pozycyjny parser Markdown (wazne)
7. i18n PL/EN - do ustalenia
8. Mapowanie efektow na systemy MoM - do ustalenia
