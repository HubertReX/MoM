# AGENTS.md — system dialogów (`project/dialog/`)

Przepływ danych, kluczowe koncepty i znane pułapki.
Silnik: czysta logika (testowalny bez pygame), web-safe.

## Warstwy systemu

```
assets/dialogs/{EN,PL}/*.md
  → [markdown_importer.py]  (build-time, desktop only)
    → config.json  (character_dialogs[<dialog_key>]: 5 sekcji)
      → [graph.py] init_dialog(dict) → {key: DialogNode}
        → NPC.dialog_nodes = result   (pełny graf, raz na start)
          NPC.dialog = get_start_node(...)  (kursor)
```

Runtime:
```
[ui/panels/dialog.py] DialogPanel
  → NPCConditionContext (adapter do danych gry)
    → conditions.check_condition(expr, ctx)  (mini-DSL)
  → result_sink_adapter.GameResultSink
    → dialog/result_sink.visit_node(node, sink)
```

## Główny przepływ (krok po kroku)

### 1. Otwarcie panelu — `set_dialog(npc, text)`
1. `_visit_current_node()` → `visit_node(npc.dialog, GameResultSink)`:
   - ustawia `npc.dialog.visited = True`
   - jeśli węzeł ma `result` → aplikuje efekt (pieniądze, items, HP, sentyment)
   - chroni przed dublem: `visited=True` → druga wizyta nic nie robi
2. `_refresh_options()` → `NPCConditionContext(npc, player)`:
   - iteruje `npc.dialog.options`, woła `check_condition(opt.condition, ctx)` na każdej
   - spełnione warunki → `_options` (widoczne opcje)
   - niespełnione → pominięte
3. Jeśli `_options` jest puste i węzeł nie jest `is_final`:
   - `_on_final_node = True` (**dead-end auto-end**)

### 2. Wybór opcji — `activate_selected()`
1. `opt.selected = True` + `npc.selected_options_dict[opt.key] = True`
2. `npc.apply_option_sentiment(opt.sentiment)` → zmiana sentymentu NPC
3. **`npc.dialog = opt.next_node`** — przesunięcie kursora w grafie
4. `_visit_current_node()` — efekt *nowego* węzła (jednorazowy)
5. Jeśli `npc.dialog.is_final`:
   - `_on_final_node = True`
   - czeka na Accept gracza
6. Jeśli nie `is_final` ale 0 widocznych opcji:
   - `_on_final_node = True` (**auto-end**)
7. W przeciwnym razie renderuje nowy węzeł + opcje

### 3. Zamknięcie panelu
1. `game_ui.py` wykrywa `on_final_node` + Accept
2. `npc.reset_dialog()` → `npc.dialog = dialog_start_node`
3. Następna rozmowa zaczyna się od START_NODE, a warunki decydują o ścieżce

## Kluczowe koncepty

### `npc.dialog` (kursor) vs `dialog_nodes` (stan grafu)

- **`npc.dialog: DialogNode`** — *gdzie gracz jest teraz.* Zmieniany przy każdym
  `activate_selected()`: `npc.dialog = opt.next_node`. To jest bieżący węzeł który
  gracz widzi na ekranie.
- **`npc.dialog_nodes: dict[str, DialogNode]`** — *cały graf* dla danego NPC.
  Zbudowany raz przez `init_dialog()`, nigdy nie zmieniany (struktura statyczna).
- **`dialog_nodes[key].visited: bool`** — czy węzeł kiedykolwiek odwiedzony
  (przez `visit_node()`). Nigdy nie resetowany. Podstawa predykatu `visited()`.
- **Reset kursora** (`reset_dialog()`) nie czyści `visited` — tylko ustawia
  `npc.dialog` z powrotem na START_NODE.

**Pułapka:** sprawdzanie `npc.dialog.key == node_key` zamiast
`dialog_nodes[node_key].visited` to był źródłowy bug `visited()` — oba wyrażenia
są poprawne składniowo, ale pierwsze mówi "czy tu jesteś", drugie "czy tu byłeś".

### ConditionContext — kontrakt

`dialog/conditions.py` definiuje `ConditionContext` (Protocol). `NPCConditionContext`
to adapter do żywych danych gry.

| Metoda / property | Źródło danych | Uwagi |
|---|---|---|
| `selected(opt_key)` | `npc.selected_options_dict` | per-NPC, zapisywane przy `activate_selected()` |
| `visited(node_key)` | `npc.dialog_nodes[node_key].visited` | własny NPC |
| `visited(dialog_key, node_key)` | `scene.loaded_NPCs[dialog_key].dialog_nodes[node_key].visited` | **cross-NPC lookup** |
| `has_item(key)` | `player.items` po `item.model.name` | |
| `sentiment` | `npc.sentiment` (int, 0–100) | może być clampowany |

### Cross-NPC lookup — ZAWSZE po `dialog_key`

`visited("BARMAN_ABSINTHRAYNER", "012")` szuka NPC po `other.dialog_key == "BARMAN_ABSINTHRAYNER"`.
**Nie** po `other.name` (to display name, np. "Barman Absinthrayner") i **nie** po
`other.model.name` (to samo). `dialog_key` jest kluczem konfiguracyjnym — ten sam
który występuje w `config.json` jako klucz sekcji `character_dialogs`.

## Mapa plików

| Plik | Zależności | Web-safe? | Rola |
|---|---|---|---|
| `entities.py` | — | ✅ | Dataclassy `slots=True`: `DialogNode`, `DialogOption`, `NodeVisitResult` |
| `conditions.py` | `entities` | ✅ | Mini-DSL: `check_condition()`, `validate_condition()`, `ConditionContext` Protocol |
| `graph.py` | `entities`, `conditions` | ✅ | `init_dialog(dict) → {key: DialogNode}`, resolve referencji |
| `result_sink.py` | `entities` | ✅ | `visit_node()`, `apply_result()`, `ResultSink` Protocol |
| `context_adapter.py` | `conditions`, **`characters`** (TYPE_CHECKING) | ✅ | `NPCConditionContext(ConditionContext)` — adapter do gry |
| `markdown_importer.py` | `conditions` (walidacja) | ❌ (tylko desktop) | Build-time: `.md → config.json` |
| `result_sink_adapter.py` | `result_sink`, **`characters`** (TYPE_CHECKING) | ✅ | `GameResultSink(ResultSink)` |

### Uwaga dotycząca formatu MD

Tekst węzła dialogowego w plikach `.md` zaczyna się od `* ` (gwiazdka + spacja)
ale może się ciągnąć przez wiele linii — również takich, które **nie** zaczynają
się od `* `. Koniec tekstu wyznacza pierwsza linia opcji (`* [00x](#00x) ...`).

Węzły z rozbitą kwestią na kilka akapitów (np. lista wymaganych przedmiotów
w #003 Madame Sarcasmii) używają linii bez `* ` dla drugiego i dalszych
akapitów. Importer grupuje kolejne linie bez pustej linii między nimi w jeden
akapit (połączone pojedynczym `\n`). Pusta linia w źródle = nowy akapit
(separator `\n\n` w renderowanym tekście).

## Znane pułapki (bug history)

1. **Bug visited() — bieżący węzeł zamiast historii** (fix 2026-07-08):
   `if npc.dialog.key == node_key` zamiast `dialog_nodes[node_key].visited`.
   Skutek: warunek `visited("003")` zwracał `True` tylko gdy gracz stał na węźle #003
   — nigdy po przejściu dalej. `not visited(...)` zawsze `True`.
   Dotknięci: Clapback Sword (wszystkie ekspozycje), Potioneer_Puzzlemint (gate node).

2. **Bug cross-NPC — porównanie `name` zamiast `dialog_key`** (fix 2026-07-08):
   `if other.name == npc` — `other.name` to display name ("Barman Absinthrayner"),
   `npc` to dialog_key ("BARMAN_ABSINTHRAYNER"). Nigdy nie matchowało.
   Dotknięty: Potioneer_Puzzlemint (warunek `visited("BARMAN_ABSINTHRAYNER", "012")`).

3. **Brak auto-end dla dead-endów** (fix 2026-07-08):
   Gdy wszystkie opcje były odfiltrowane przez warunki (pusta `_options`), panel
   zostawał otwarty bez żadnej akcji — gracz wisiał. Dodano sprawdzenie w
   `set_dialog()` i `activate_selected()`.

4. **Kursor nie resetowany po rozmowie** (fix 2026-07-08):
   Po zamknięciu panelu `npc.dialog` wskazywał ostatni węzeł (często finalny).
   Następna rozmowa zaczynała się od tego węzła, a nie od START_NODE.
   Dodano `NPC.reset_dialog()` wołane przez `game_ui.py`.

5. **Importer gubi kontynuację tekstu** (fix 2026-07-08):
   `_parse_file()` w `markdown_importer.py` zbierał tylko linie zaczynające się od
   `* ` (wzorzec `_NODE_TEXT_RE`). Linie kontynuacji bez gwiazdki — np. listing
   `[act]*[/act] ...` albo czysta proza w nowym akapicie — były milcząco pomijane.
   Dotknięci: Madame Sarcasmia (węzły #003, #004 i inne z rozbitą kwestią na
   wiele linii). Fix: każda nieopcyjna, niepusta linia między nagłówkiem węzła
   a pierwszą opcją traktowane jako kontynuacja. Kolejne linie bez pustej linii
   między nimi grupuje w jeden akapit (połączone `\n`). Pusta linia = separator
   akapitów (`\n\n`).
