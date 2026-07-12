# AGENTS.md — system dialogów (`project/dialog/`)

Przepływ danych, kluczowe koncepty i znane pułapki.
Silnik: czysta logika (testowalny bez pygame), web-safe.

## Warstwy systemu

```
doc/PL/Postacie/*.md + doc/EN/Characters/*.md   (vault Obsidian; PL = źródło prawdy)
  → [markdown_importer.py]  (build-time, desktop only)
    → characters.csv  (kolumny sprite/friendly/kind/weak/angry/smart/funny)
      → [import_entities.py]  (jedyny writer sekcji `characters`)
    → config.json  (character_dialogs[<dialog_key>]: 5 sekcji)
      → [graph.py] init_dialog(dict) → {key: DialogNode}
        → NPC.dialog_nodes = result   (pełny graf, raz na start)
          NPC.dialog = get_start_node(...)  (kursor)
```

Kaskadę odpala ``just import-dialogs`` (markdown_importer → import-entities).

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
3. Następna rozmowa zaczyna się od `dialog_start_node` (może być zmieniony przez `resume_node`), a warunki decydują o ścieżce

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
| `has_item(key)` | `player.items` po `item.name` (config key) | **nie** `item.model.name` (to display name) |
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

Nagłówek węzła dialogowego to `## <numer>` (np. `## 000`, `## 015-end`);
legacy `### <numer>` jest nadal akceptowane. Wszystko przed pierwszym
numerycznym nagłówkiem (frontmatter, sekcja `# Info` z podsekcjami) jest
ignorowane przez importer — klucze węzłów są wyłącznie cyfrowe, więc
nagłówki prozy (`## Cechy charakteru`) nie kolidują.

Tekst węzła dialogowego w plikach `.md` zaczyna się od `* ` (gwiazdka + spacja)
ale może się ciągnąć przez wiele linii — również takich, które **nie** zaczynają
się od `* `. Koniec tekstu wyznacza pierwsza linia opcji (`* [00x](#00x) ...`).

Węzły z rozbitą kwestią na kilka akapitów (np. lista wymaganych przedmiotów
w #003 Madame Sarcasmii) używają linii bez `* ` dla drugiego i dalszych
akapitów. Importer grupuje kolejne linie bez pustej linii między nimi w jeden
akapit (połączone pojedynczym `\n`). Pusta linia w źródle = nowy akapit
(separator `\n\n` w renderowanym tekście).

### Frontmatter i wikilinki

Nazwa pliku = zlokalizowana nazwa postaci (np. `Barman Absyntnent.md`);
klucz słownikowy żyje wyłącznie w polu `aliases` frontmattera — importer
znajduje pliki po aliasie, nie po nazwie. **Frontmatter PL jest źródłem
prawdy** dla metadanych postaci (EN trzyma kopię, synchronizowaną skillem
`.opencode/skills/dialog-en-sync`):

```md
---
aliases:
  - BARMAN_ABSINTHRAYNER
EN: "[[Barman Absinthrayner]]"
sprite: Hunter
friendly: 0.6
kind: 1
weak: 1
angry: 1
smart: 1
funny: 1
---
```

- `sprite` — katalog assetów z `NinjaAdventure/characters/`.
- `friendly` — bazowy sentyment 0..1 (startowy `NPC.sentiment = friendly*100`).
- Wagi sentymentów (`kind/weak/angry/smart/funny`, zakres -2..2) — kanoniczne
  autorskie nazwy; `neutral` i `technical` mają zawsze 0 i nie występują we
  frontmatter. Mapowanie na ikony emote (`SENTIMENT_NAME_TO_EMOTE` w
  `settings.py`) następuje dopiero przy renderowaniu UI.

Postacie w tekstach dialogów są odwoływane przez wikilinki:

- **Po nazwie pliku:** `[[Barman Absyntnent]]`.
- **Z odmianą przez pipe:** `[[Barman Absyntnent|Barmana Absyntnenta]]` —
  lewa strona identyfikuje postać (nazwa pliku lub klucz), prawa to forma
  wyświetlana (poprawna gramatycznie).
- **Po kluczu:** `[[BARMAN_ABSINTHRAYNER]]` (Obsidian rozwiązuje przez alias).

Importer rozwiązuje wikilinki przez `characters` config (klucz oraz
`name_PL`/`name_EN`) i otacza wynik tagami `[char]...[/char]` w wyjściu;
nierozpoznane linki zostają bez zmian.

### Węzły końcowe (`-end`) i resume

Węzły końcowe (po których rozmowa się kończy) mają sufiks `-end` w nagłówku.
Link resume jest na **osobnej linii** pod nagłówkiem:

```md
## 005-end
[[#011]]

* A teraz idź już...
```

- Sufiks `-end` → `is_final=True` — po dotarciu do tego węzła panel pokazuje tekst i czeka na Accept, nie wyświetla opcji.
- Link `[[#011]]` na osobnej linii → `resume_node="011"` — **następna rozmowa** z tym NPC zacznie się od węzła #011 zamiast od START_NODE.
- Link jest klikalny w Obsidian, co ułatwia nawigację między węzłami.

**Backward compat:** stary format z linkiem w nagłówku (`### 990-end [011](#011)`) jest nadal wspierany przez importer. Preferowany jest nowy format (link na osobnej linii).

**Opcje wskazujące na węzeł końcowy** używają `-end` w anchorze linku:

```md
* [[#005-end]] 1😐: Zrozumiano.
```

Importer automatycznie stripuje `-end` z targetu (`#005-end` → node key `005`), ale anchor z `-end` działa w VS Code preview.

**Mechanizm resume w runtime:**
1. Gdy gracz wybiera opcję prowadzącą do węzła z `is_final=True`, `DialogPanel.activate_selected()` woła `npc.apply_resume_node()`.
2. `apply_resume_node()` podmienia `npc.dialog_start_node` na węzeł wskazany przez `resume_node`.
3. Po zamknięciu panelu, `npc.reset_dialog()` ustawia kursor na `dialog_start_node` — czyli na docelowy węzeł wznowienia.
4. `resume_node` jest przechowywane w `config.json` (`DIALOG_NODES[nkey].resume_node`) i deserializowane jako `DialogNode.resume_node`.

**Backward compat:** stary format z opcją `* [001](#001) 1😐: technical loop back` jest nadal wspierany — importer rozpoznaje tekst "technical loop back" i traktuje go jako dyrektywę resume (nie dodaje jako realnej opcji). Nowy format (link w nagłówku) ma pierwszeństwo.

### `has_item()` — porównanie po config key

`has_item()` w `context_adapter.py` porównuje `item.name` (`ItemSprite.name` = config key, np. `"MERMAIDS_TEAR"`) z kluczem z warunku. **Nie** porównuje `item.model.name` (display name jak `"Mermaid's tear"`) — to był bug (fix 2026-07-08).

Node #012 Madame Sarcasmii używa `[ITEMS-GNOMES_WHISKER,MERMAIDS_TEAR,PHOENIX_FEATHER]` → `_remove_one_item()` też używa `item.name`, więc poprawnie usuwa przedmioty z inventory po spełnieniu questu.

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

6. **`has_item()` porównuje display name z config key** (fix 2026-07-08):
   `context_adapter.py:53` — `item.model.name` (display name "Mermaid's tear")
   vs `item_key` (config key "MERMAIDS_TEAR") — zawsze `False`.
   Dotknięty: Madame Sarcasmia (węzeł #011 sprawdzający posiadanie przedmiotów).
   Fix: `item.name` (config key, tak jak reszta kodu).

7. **Brak `resume_node` — „technical loop back" był ignorowany** (fix 2026-07-08):
   Opcje z tekstem "technical loop back" były dodawane do grafu jako realne opcje
   (niewidoczne na finalnych węzłach, ale zaśmiecały dane). `resume_node` w ogóle
   nie istniał — `reset_dialog()` zawsze wracał do START_NODE, podczas gdy niektóre
   końcowe węzły powinny kierować następną rozmowę do innego węzła (np. #011 zamiast
   #000). Fix: dodano `DialogNode.resume_node`, parse linku `[011](#011)` w nagłówku
   węzła, i `NPC.apply_resume_node()` aktualizujące `dialog_start_node`.

8. **Walidator grafu nie znał `resume_node`** (fix 2026-07-08):
   Po przeniesieniu dyrektywy resume z opcji do nagłówka, węzły osiągalne tylko
   przez `resume_node` (np. Clapback Sword node #100) były zgłaszane jako orphan.
   Fix: `_validate_graph()` dodaje `resume_node` targety do zbioru znanych krawędzi.
