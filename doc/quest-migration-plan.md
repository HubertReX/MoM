# Quest System - plan migracji SSiS -> MoM

Handoff do implementacji. Dokument samowystarczalny: nie trzeba czytać źródeł SSiS ani HTML-a.

- Analiza + 15 decyzji + projekt panelu: [[_attachements/quest-system-ssis-2026-07-16.html]] (commit `4de1448`)
- Wzorzec migracji dialogów: [[dialog-migration-plan.md]]
- Źródło SSiS: `~/Projects/RPG` (`quests.py`, `config.json`, `utils.py`, `ui.py`)

## Stan

Wszystkie **15 decyzji zamkniętych** (2026-07-16). Kod: **Q-01, Q-02, Q-03, Q-04, Q-06 zrobione**,
Q-10 naszkicowane (2026-07-16). Zostały: **Q-05** (czeka na 3 decyzje), **Q-07** (zależy od Q-05),
**Q-08** (panel, projekt gotowy w HTML-u), **Q-09** (zależy od Q-07), **Q-11** (graf, #S).

Q-05 wymaga rozstrzygnięcia: `max_items` (przerobić `MAX_HOTBAR_ITEMS` na pole gracza?),
`sentiment` (globalny czy konkretny NPC?), podwójna nagroda parasola (Pułapka 7 - szkic Q-10
odpowiada na nią przez treść: kroki nie płacą, ale regułę trzeba zamknąć jawnie).

Bramka po `parent` w `is_unlocked` (Q-03): **zaakceptowana** 2026-07-16.

**Treść (Q-10) jest naszkicowana** - 3 łańcuchy, 8 questów, przechodzi importem i silnikiem
od zera do domknięcia Q03. Proza i nagrody **do przepisania** przez autora; `Q01_S05` używa
węzła `001`, bo klucz z planu nie istniał w MoM (szczegóły w Q-10).

Po drodze przy Q-02 wyszły **dwa bugi w save/load niezwiązane z questami** - patrz "Bugi save/load
(znalezione przy Q-02)" niżej. Oba naprawione: pierwszy jako warunek wstępny (bez niego
cross-mapowe `visited()` nie mogło działać), drugi to duplikowanie przedmiotów questowych,
narastające z każdym cyklem save/load.

Doprecyzowania podjęte przy Q-01 (plan zostawiał je otwarte):

- `QuestReward` = `category` (enum `QuestRewardCategory`: `money`, `items`, `health`, `max_health`,
  `damage`, `max_items`, `sentiment`) + `value: int` + `items: list[str]`. `agility` nie istnieje
  (D11), więc nagroda w tej kategorii wywala się na enumie. Q-05 mapuje kategorie 1:1 na `ResultSink`.
- `init_quests` wylądowało w `project/quest/graph.py` (nie w `entities.py`) - wierny odpowiednik
  `dialog/graph.py`. `entities.py` zostaje czystym modelem danych.
- Walidacja warunków mini-DSL **nie jest** w `init_quests` - `quest_done()` nie istnieje jeszcze
  w whiteliście (Q-02), a Q-01 nie może zależeć od Q-02. Idzie do importu (Q-04), zgodnie z planem.
- ~~Acykliczność `requires` zostaje w Q-03~~ - przy Q-03 wylądowała jednak w `init_quests`
  (`quest/graph.py`), patrz Q-03.
- `Config.check_quests` (Pydantic) **woła `init_quests`** zamiast duplikować walidację grafu.
  Efekt: `config.json`, który przejdzie walidację na desktopie, nie wywali runtime'u na webie -
  to ten sam kod. Pydantic dokłada tylko to, czego builder nie widzi: typy pól i istnienie
  kluczy przedmiotów w `config["items"]`.
- Nagroda o zerowej wartości (lub `items` bez itemów) = błąd importu. To kształt, na którym
  SSiS-owy `break` cicho przechodził dalej (Pułapka 1); nigdy nie jest zamierzony.
- `completion: manual` + `test` = błąd (test nigdy by nie wystartował). `progress` i `progress_total`
  muszą być ustawione razem; postęp parasola liczy silnik z podquestów, więc nie potrzebuje żadnego z nich.

## Decyzje (D1-D15)

| #   | Temat             | Wybór   | Znaczenie                                                                       |
| --- | ----------------- | ------- | ------------------------------------------------------------------------------- |
| D1  | Granulacja MD     | A       | 1 plik = 1 łańcuch, podquesty jako `## S01`                                      |
| D2  | FM czy treść      | B       | wszystko w treści (podquesty nie zmieszczą się w YAML)                          |
| D3  | Teksty            | A       | `messages` w `config.json` jak dialogi; `success` bez dziur + auto-etykieta      |
| D4  | Typy              | A       | Pydantic przy imporcie (desktop), goły dict w runtime (web)                      |
| D5  | Agregacja         | A       | enum `completion: all_subquests \| test \| manual`                               |
| D6  | DAG               | B       | `requires: [klucze]` + osobny `parent`; `is_unlocked` znika ze stanu             |
| D7  | Predykaty DSL     | A       | wąskie, na żądanie; start: `quest_done()`                                        |
| D8  | `dialog.key`      | A       | `visited(npc, node)` zamiast wyścigu z kursorem                                  |
| D9  | Postęp            | A       | `eval_number(expr, ctx) -> int`                                                  |
| D10 | Nagrody           | B       | lista efektów przez `ResultSink`                                                 |
| D11 | Staty             | C + D   | `hp→damage`, `eloquence→sentyment`, `max_items→` pole gracza, `agility` porzucone |
| D12 | Kiedy sprawdzać   | C       | event-driven + sweep jako siatka                                                 |
| D13 | Persystencja      | A       | osobny `QuestState` w save; `config.json` niemutowalny                           |
| D14 | UI                | A       | `QuestPanel` pod `J` (alias `F10`) + toasty                                      |
| D15 | Dług treści       | C       | 1. iteracja = 8 questów z treścią                                                |

## Fakty zweryfikowane w kodzie

Nie zgaduj - to jest sprawdzone:

- **Tłumaczenia dialogów NIE są w TOML.** Siedzą w `config.json["messages"][lang][key]` (294 klucze/język),
  czytane przez `get_msg()` (`project/settings.py:87`). TOML (`project/assets/locale/{LANG}.toml`) to
  wyłącznie stringi UI, czytane przez `_()`. Questy idą mechanizmem `messages`.
- **Mini-DSL już istnieje i wystarcza:** `project/dialog/conditions.py` - interpreter AST na whiteliście,
  bez `eval()`, web-safe. Predykaty: `selected()`, `visited(node)`, `visited(npc, node)`, `has_item()`,
  nazwa `sentiment`. AST cache'owany (`@lru_cache` linia 124). Dane wchodzą przez `ConditionContext` (Protocol).
- **Adapter:** `project/dialog/context_adapter.py` - `NPCConditionContext`.
- **ResultSink:** `project/dialog/result_sink.py` - `add_money`, `remove_money`, `add_items`, `remove_items`,
  `restore_health`, `lose_health`, `shift_sentiment`. `visit_node()` ma semantykę "zastosuj dokładnie raz".
- **Toasty istnieją:** `scene.add_notification(tekst, NotificationTypeEnum)` - używane w
  `ui/panels/save_load.py:275` i `ui/panels/dialog.py:330`. `NotificationTypeEnum` (`project/enums.py:45`):
  `debug`, `info`, `warning`, `error`, `success`, `failure`.
- **Model postaci** (`project/config_model/config_pydantic.py:65-75`): `health`, `max_health`, `money`,
  `damage`, `speed_walk`, `speed_run`, `friendly`. **Brak** `agility`, `eloquence`, `hp`.
- **`MAX_HOTBAR_ITEMS = 6`** (`project/settings.py:317`) to **stała modułowa**, nie stan gracza.
- **Klawisz `J` wolny:** `K_j` ma zero trafień w `project/`. Zajęte litery: `a b d e f h i n q r s w x z`.
  Z funkcyjnych wolne tylko F10 i F11, ale F11 to fullscreen w przeglądarce (MoM chodzi na pygbag).
- **Panel wzorcowy:** `project/ui/panels/inventory.py` (mały), toggle w `project/ui/game_ui.py:136`
  (`self.toggle(InventoryPanel)` na `INPUTS["inventory"]`). Tło: `theme.nine_patch()`.
- **Kanwa:** 1280x720 (`X_TILES 80 × Y_TILES 45 × TILE_SIZE 16`).
- **Paleta:** `PANEL_BG_COLOR (30,30,30,200)`, `UI_BORDER_COLOR (17,17,17)`, `UI_BORDER_COLOR_ACTIVE "gold"`,
  `CHAR_NAME_COLOR (255,252,103)`, `FONT_COLOR (255,255,255)`, teal `(0,197,199)` (`ui/theme.py`).
- **Postacie i przedmioty questowe JUŻ SĄ w MoM:** `config.json["items"]` ma `POTION_CURSE_NO_MORE`,
  `MERMAIDS_TEAR`, `GNOMES_WHISKER`, `PHOENIX_FEATHER`; `config.json["dialogs"]` ma wszystkie postacie `Q*`.
- **Pipeline dialogów:** `project/dialog/markdown_importer.py` (`_LANG_SUBDIRS` linia 299:
  `PL/Postacie`, `EN/Characters`; `_validate_language_consistency` linia 475), odpalany przez
  `just import-dialogs` → `just import-entities`.

## Zakres 1. iteracji: 8 questów

Wszystkie warunki to `visited()` - **zero nowych predykatów w warstwie testów**.

| Klucz | Tytuł (PL) | completion | Warunek |
| --- | --- | --- | --- |
| `Q00_S00_WHAT_IS_GOING_ON` | O co tu chodzi? | test | `visited("CLAPBACK_SWORD", "015")` |
| `Q01_S00_BREAK_THE_CURSE` | Przełamać klątwę | **manual** | parasol - czeka na S06/S07 |
| `Q01_S01_LEARN_ABOUT_CURSE` | Dowiedz się więcej o klątwie | test | `visited("BARMAN_ABSINTHRAYNER", "012")` |
| `Q01_S05_MEET_MADAME_SARCASMIA` | Spotkaj się z Sarkażmijką | test | `visited("MADAME_SARCASMIA", "001")` ⚠ patrz niżej |
| `Q03_S00_LEARN_ABOUT_CURSE` | Znajdź kogoś kto wie o klątwach | all_subquests | 3 podquesty |
| `Q03_S01_WHO_HAS_MORE_KNOWLEDGE` | Kto ma wiedzę o magii? | test | `visited("POTIONEER_PUZZLEMINT","014") or visited("POTIONEER_PUZZLEMINT","017")` |
| `Q03_S02_WHERE_TO_FIND_THIS_PERSON` | Gdzie znaleźć tę osobę? | test | `visited("HAMMER_HOAXHEART", "009")` |
| `Q03_SO3_HOW_TO_GET_THERE` | Jak tam dotrzeć? | test | `visited("BARMAN_ABSINTHRAYNER", "017")`; poprawić literówkę `SO3`→`S03` |

Krawędzie `requires` (DAG, krzyżują łańcuchy):
`Q01_S00 ← Q00_S00`, `Q03_S00 ← Q01_S01`, `Q01_S05 ← Q01_S01`(*), `parent`: S01/S05 → Q01_S00; S01/S02/SO3 → Q03_S00.

(*) **Do zaprojektowania - w SSiS `Q01_S05` jest nieosiągalny.** Ma `is_unlocked: false`, a w całym
`config.json` **żaden quest nie ma go w `unlocks`**. Czyli poza `Q01_S07` (pułapka niżej) to drugi martwy
quest, a przez niego martwy jest cały łańcuch: `Q01_S05` → `Q02_S00` → `Q01_S06` → `Q01_S07`.
Wniosek: fabuła klątwy w SSiS **nigdy nie działała poza pierwszym krokiem**. Przy pisaniu treści (Q-10)
trzeba nadać `Q01_S05` sensowny `requires` - naturalny kandydat to `Q01_S01` (dowiedz się o klątwie →
możesz szukać Sarkażmijki).

**Zweryfikowane, nie domysł:** żaden z 31 questów nie ma `Q01_S05` w `unlocks`, a `is_unlocked = True`
jest w całym SSiS ustawiane **wyłącznie** w `quests.py:138` i `quests.py:178` - obie linie to mechanizm
`unlocks`. `ui.py` tylko czyta. Nie ma innej drogi odblokowania (dialogi też nie ruszają tego pola).

**Poza 1. iteracją (dług treści, D15=C):** `Q01_S06`, `Q01_S07`, `Q02_S00`, `Q02_S01-S03` -
mają `<<PLACEHOLDER>>` zamiast tekstów. `Q01_S07` wymaga **decyzji projektowej**, nie tylko tekstu
(w SSiS jest martwy: `test:"False"` bez podquestów). Kandydaci na warunek: domknięcie dialogiem
(`visited()`, zero nowych predykatów) albo lokacja (`at_location()`, nowy predykat + pojęcie
"bezpiecznego miejsca").

## Taski

Format jak w [[dialog-migration-plan.md]]. Trudność: `#S` mały / `#M` średni / `#L` duży.

| ID | Task | Trud. | Zależy od |
| --- | --- | --- | --- |
| Q-01 | Encje questów + model danych | #M | (fundament) |
| Q-02 | DSL: `quest_done()` + `eval_number()` | #M | Q-01 |
| Q-03 | Silnik questów: DAG, requires, completion | #L | Q-01, Q-02 |
| Q-04 | Pipeline importu MD → config | #L | Q-01 |
| Q-05 | Nagrody: rozszerzenie ResultSink + auto-etykieta | #M | Q-01 |
| Q-06 | Persystencja QuestState | #M | Q-01, Q-03 |
| Q-07 | Integracja runtime: event-driven + sweep | #M | Q-03, Q-05 |
| Q-08 | QuestPanel UI (klawisz J) | #L | Q-01, Q-03, Q-04 |
| Q-09 | Toasty questowe | #S | Q-07 |
| Q-10 | Treść 8 questów + smoke test | #M | wszystko |
| Q-11 | Graf questów w Obsidianie | #S | Q-04 |

### Q-01 · Encje questów + model danych `#M` ✅

**Zrobione 2026-07-16.** Pliki: `project/quest/{__init__,entities,graph}.py`, modele `Quest`/`QuestReward`
+ walidator `check_quests` w `config_model/config_pydantic.py`, testy `tests/test_quest_entities.py`
(11, zielone). Zweryfikowane: `import quest` nie ciągnie pygame/Pydantic/rich; `just update-config-schema`
przechodzi; istniejący `config.json` ładuje się z pustą sekcją `quests`; mypy czysty.

**Goal:** kształt danych questa, web-safe, bez pygame.

**Plan:**

- `project/quest/__init__.py`, `project/quest/entities.py` (nowy pakiet obok `project/dialog/`).
- `CompletionMode(StrEnum)`: `all_subquests`, `test`, `manual` (D5).
- `QuestDef` (dataclass, web-safe): `key`, `name`/`description`/`success` (klucze i18n),
  `completion`, `test: str | None`, `progress: str | None`, `progress_total: int`,
  `requires: list[str]`, `parent: str | None`, `rewards: list[QuestReward]`.
- `QuestReward`: kategoria + wartość (kształt uzgodnić z Q-05).
- `QuestState` (D13): `{key: {"done": bool}}` - **stan osobno od definicji**.
- Model Pydantic w `config_model/config_pydantic.py` **tylko do walidacji przy imporcie** (D4);
  runtime czyta goły dict (web nie ma Pydantic).
- `init_quests(dict) -> {key: QuestDef}` (analogicznie do `dialog/graph.py:init_dialog`).

**DoD:** testy w pamięci; `import quest.entities` działa bez pygame; walidacja odrzuca
`completion: all_subquests` bez podquestów (to jest bug `Q01_S07` - patrz Pułapki).

### Q-02 · DSL: `quest_done()` + `eval_number()` `#M` ✅

**Zrobione 2026-07-16.** Pliki: `dialog/conditions.py` (scope + `quest_done` + `item_count` +
`eval_number`), `dialog/context_adapter.py` (`find_visited_node` - wspólny lookup),
`quest/context_adapter.py` (`QuestConditionContext`), testy `tests/test_quest_conditions.py` (10)
i `tests/test_quest_context_adapter.py` (7). Wszystkie stare testy dialogów (19) przechodzą bez
zmian - `scope` ma default `dialog`, więc `validate_condition(cond)` działa jak wcześniej.

Rozstrzygnięcia:

- **`ConditionScope`** (`dialog` / `quest`) zamiast jednej whitelisty. W scope `quest` nie ma
  `selected()` ani `sentiment` (brak bieżącego NPC), a `visited()` ma arność **dokładnie 2** -
  `visited("012")` w queście to błąd importu, nie ciche `False` na zawsze. Cache `_compile`
  kluczowany po `(condition, scope)`.
- **Protokół rozbity:** `ConditionContext` (świat: `visited`, `has_item`, `item_count`,
  `quest_done`) + `DialogConditionContext` (dokłada `selected`, `sentiment`). Quest implementuje
  tylko ten pierwszy.
- **`quest_done()` działa też w dialogach** ("opcja dostępna dopiero po queście X") - za darmo,
  bo to ta sama whitelista wspólna.
- **`eval_number()` odrzuca `bool`.** `progress: 'visited(...)'` to błąd autorski, a pasek
  postępu pokazujący 1/3 bo predykat wyszedł prawdziwy to dokładnie ten cichy bezsens, który
  ten epik ma eliminować.
- **Whitelist urosła tylko o `quest_done` i `item_count`** (zgodnie z DoD) - jest test, który
  tego pilnuje (`test_whitelist_did_not_grow_beyond_the_plan`).
- **`QuestConditionContext.quest_done` czyta `scene.quest_state`**, którego jeszcze nie ma -
  do podpięcia w Q-07. Do tego czasu zwraca `False` (czyli "quest nieukończony").

**Goal:** minimalne rozszerzenie `project/dialog/conditions.py` (D7, D9).

**Plan:**

- `quest_done(key)` do `_PREDICATES` + metoda w `ConditionContext`.
- `QuestConditionContext` - quest nie ma "bieżącego NPC", więc `selected()` i `sentiment`
  nie mają dla niego sensu. Rozważyć rozbicie Protocolu na część wspólną i dialogową.
  `visited(npc, node)` **musi** działać cross-NPC (dziś iteruje po `scene.loaded_NPCs` -
  **uwaga: quest może pytać o NPC spoza załadowanej sceny**, patrz Pułapki).
- `eval_number(expr, ctx) -> int` - to samo `_compile()` i whitelist, ale zwraca liczbę
  zamiast `bool`. Dodać `item_count()` gdy potrzebne.

**DoD:** testy jednostkowe; `validate_condition()` nadal wywala nieznane nazwy przy imporcie;
whitelist nie urosła o nic poza `quest_done` (+ `item_count` jeśli użyte).

### Q-03 · Silnik questów: DAG, requires, completion `#L` ✅

**Zrobione 2026-07-16.** Pliki: `project/quest/engine.py`, walidacja cykli w `quest/graph.py`,
testy `tests/test_quest_engine.py` (12) na realnym grafie 8 questów.

Rozstrzygnięcia:

- **`is_unlocked` bramkuje też po `parent`** - to jedyne odejście od litery planu, patrz
  "Bramka po parent" niżej.
- **`check_quests` kaskaduje aż do stabilizacji** i zwraca `QuestCheckResult(newly_done,
  newly_unlocked)` - gotowe pod toasty (Q-09), bez diffowania stanu po stronie wołającego.
  Kaskada schodzi realnie 3 poziomy: Q00 → odblokowuje wątek klątwy → Q01_S01 → odblokowuje
  wątek Q03 → Q03_S03 (jego `test` to inny węzeł tej samej rozmowy z barmanem). Wszystko
  w jednym przebiegu, bez czekania aż sweep to wydłubie po jednym.
- **Quest zablokowany nie jest w ogóle ewaluowany** - jest test, który to pilnuje (szpieg na
  kontekście liczy wywołania `visited`). Bez tego gracz dostawałby toast o ukończeniu kroku
  z wątku, którego jeszcze nie zaczął.
- **`newly_unlocked` nie zawiera questów ukończonych w tym samym przebiegu** - "możesz teraz
  zacząć coś, co właśnie skończyłeś" to szum.
- **Walidacja cykli wylądowała w `init_quests`** (`quest/graph.py`), nie w silniku. Powód:
  `init_quests` to jedyna brama, przez którą przechodzi każdy konsument, a `is_unlocked`
  rekurencyjnie schodzi po `parent` - cykl bez walidacji to `RecursionError`, nie deadlock.
  Sprawdzany jest graf **odblokowań** (`requires` + `parent`). `all_subquests` celuje w drugą
  stronę (parasol czeka na dzieci, dzieci czekają na *odblokowanie* parasola, nie na jego
  ukończenie), więc normalny wątek nie jest cyklem - jest na to osobny test.
- **`quest_progress`** liczy postęp z `progress`/`progress_total` (D9) albo z dzieci parasola
  ("2/3", bez pisania czegokolwiek). Quest ukończony pokazuje pełny pasek niezależnie od
  wyrażenia - inaczej po wydaniu przedmiotów skończony quest świeciłby "0/3".
- **`engine.py` nie jest eksportowany z `quest/__init__.py`** - ciągnie DSL, a przez niego
  `settings` i pygame. `quest.entities` / `quest.graph` zostają czystym rdzeniem (DoD Q-01).

#### Bramka po parent (do akceptacji)

Plan mówi: `is_unlocked(key)` = wszystkie `requires` mają `done`. Wzięte dosłownie, podquest
bez własnego `requires` jest odblokowany od pierwszej klatki - a `Q03_S01/S02/S03` mają tylko
`parent: Q03_S00`. Wtedy `requires: [Q01_S01]` na parasolu nic nie znaczy: gracz robi wszystkie
trzy kroki, a parasol zapala się w chwili ukończenia Q01_S01.

Więc `is_unlocked` sprawdza dodatkowo, czy **rodzic jest odblokowany** (nie: ukończony - parasol
`all_subquests` czeka na dzieci, więc bramka po ukończeniu rodzica to zakleszczenie).

Uwaga: to zmienia tylko **moment** zapalenia, nie wynik. `visited()` to trwały fakt o świecie,
więc krok zrobiony "za wcześnie" i tak zaliczy się od razu po otwarciu wątku - kaskada to łapie.
Różnica jest fabularna: gracz dostaje "Kto ma wiedzę o magii? ✓" wtedy, gdy już wie, że istnieje
klątwa, a nie zanim.

**Goal:** czysta logika: co jest odblokowane, co ukończone.

**Plan:**

- `project/quest/engine.py`.
- `is_unlocked(key)` = wszystkie `requires` mają `done` (D6 - liczone na żądanie, **nie stan**).
- `check_quests(defs, state, ctx) -> (done_keys, unlocked_keys)`:
  - `completion: test` → `check_condition(test, ctx)`
  - `completion: all_subquests` → wszystkie dzieci (`parent == key`) mają `done`
  - `completion: manual` → nigdy automatycznie
- **Kaskada:** ukończenie A może odblokować B, które od razu spełnia warunek → pętla do stabilizacji
  z limitem iteracji (ochrona przed cyklem).
- Walidacja acykliczności grafu `requires` przy starcie/imporcie.

**DoD:** testy na realnym grafie 8 questów; test kaskady; test cyklu (ma failować głośno).

### Q-04 · Pipeline importu MD → config `#L` ✅

**Zrobione 2026-07-16.** Pliki: `project/quest/markdown_importer.py`, `just import-quests`,
guard w `dialog/markdown_importer.py`, testy `tests/test_quest_import.py` (15).

**Sam pipeline jest gotowy, treści jeszcze nie ma** - `doc/PL/Misje/` nie istnieje, więc
`just import-quests` mówi "nothing to import" i kończy się zerem. Napisanie 8 questów to Q-10.

#### Format pliku (do zatwierdzenia przy pisaniu treści)

Nazwa pliku = tytuł łańcucha po polsku, klucz łańcucha we frontmatterze `aliases` (jak postacie).
Sekcja `## S01_SLUG` = jeden quest, klucz = `<łańcuch>_<sekcja>`, czyli `## S01_WHO_HAS_MORE_KNOWLEDGE`
w łańcuchu `Q03` daje `Q03_S01_WHO_HAS_MORE_KNOWLEDGE`.

```markdown
---
aliases:
  - Q03
---

## S01_WHO_HAS_MORE_KNOWLEDGE

**Tytuł**: Kto ma wiedzę o magii?

Barman wspomniał, że ktoś w miasteczku zna się na klątwach.

**Completion**: test
**Test**: visited("POTIONEER_PUZZLEMINT", "014")
**Sukces**: Puzzlemint wie więcej, niż chciałby przyznać.
**Nagroda**: money=50
```

Wszystko, co nie jest linią `**Pole**:`, to proza i trafia do `description`. Nazwy pól działają
po polsku i po angielsku (`Tytuł`/`Title`, `Sukces`/`Success`, `Nagroda`/`Reward`), żeby plik EN
czytał się naturalnie. Każda `**Nagroda**:` to jedna nagroda (`money=100`, `items=A, B`) - lista,
nie pierwsza-wygrywa. `**Postęp**: item_count("X") / 3`.

Rozstrzygnięcia:

- **`parent` jest domyślny z pliku** (D1: plik = łańcuch). Sekcja `S00` to parasol, reszta sekcji
  w pliku bierze go za rodzica. Nie trzeba powtarzać `requires` na każdym kroku - jedna rzecz
  mniej do zapomnienia. Krawędzie **między** łańcuchami są jawne (`**Requires**:` z pełnymi kluczami).
- **Pola maszynowe czytane tylko z PL** (D2). W EN są ignorowane z ostrzeżeniem - jest na to test,
  który sabotuje plik EN i sprawdza, że wygrywa PL. To jest właśnie to, co czyni EN bezpiecznym
  do regenerowania LLM-em: najwyżej zepsuje prozę, nigdy logikę.
- **`validate_condition(..., ConditionScope.quest)` przy imporcie** - `selected()` czy gołe
  `visited("015")` w queście wywalają import z nazwą pliku, zamiast cicho siedzieć na `False`.
- **`init_quests()` na scalonym zbiorze** - `requires` krzyżuje łańcuchy, więc żadnego pliku nie
  da się zwalidować osobno. Wisi cykle, martwe parasole i wiszące `requires`.
- **Błąd importu = `config.json` nietknięty** (jest test na bajtową identyczność). Importer
  dialogów pomija niedokończone pliki z ostrzeżeniem; tutaj celowo nie - quest, który się nie
  zaimportował, to quest, którego cicho nie ma w grze, czyli dokładnie ta klasa bugów, którą
  ten epik usuwa.
- **Guard w importerze dialogów.** `config.json["messages"]` jest wspólny, a importer dialogów
  kasuje każdy klucz, którego nie referuje żaden dialog. Bez guardu pierwsze `just import-dialogs`
  po `just import-quests` skasowałoby **wszystkie** tytuły i opisy questów, a dziennik pokazywałby
  puste wiersze bez śladu błędu. Zweryfikowane: bez guardu test gubi 12 kluczy.

**Goal:** `doc/PL/Misje/*.md` → `config.json` (D1, D2, D3).

**Plan:**

- `project/quest/markdown_importer.py` (wzorzec: `project/dialog/markdown_importer.py`).
- Katalogi: `doc/PL/Misje/` (źródło prawdy), `doc/EN/Quests/` (generowane LLM-em).
  Rozszerzyć `_LANG_SUBDIRS`.
- 1 plik = 1 łańcuch (D1). Sekcje `## S01` = podquesty. Pola maszynowe **w treści** (D2),
  np. `**Test**:`, `**Requires**:`, `**Nagroda**:`.
- **Pola maszynowe czytane TYLKO z PL** - plik EN ma wyłącznie prozę. To neutralizuje główny
  minus D2/B: LLM generujący EN nie może zepsuć logiki, najwyżej tekst.
- Klucze i18n: `M_QUEST_<KEY>_{NAME,DESCRIPTION,SUCCESS}` → `config.json["messages"][lang]`.
- Walidacja spójności PL/EN (te same klucze sekcji) - reuse pomysłu z
  `_validate_language_consistency`.
- `validate_condition()` na każdym `test`/`requires` **przy imporcie** - głośny błąd, nie cichy `False`.
- `just import-quests` w `Justfile` (wzorzec: `import-dialogs`, linie 97-110).

**DoD:** 8 questów przechodzi z MD do `config.json`; błędny `test` wywala import z podaniem pliku;
`config.json` pozostaje jedynym artefaktem generowanym (nie ruszamy go ręcznie).

### Q-05 · Nagrody: ResultSink + auto-etykieta `#M`

**Goal:** wszystkie nagrody z listy (nie pierwsza!), przez istniejący mechanizm (D10, D11, D3).

**Plan:**

- Rozszerzyć `ResultSink` (`project/dialog/result_sink.py`) o brakujące: `raise_max_health`,
  `raise_damage`, `raise_max_items`. `add_money`/`restore_health`/`shift_sentiment` **już są**.
- `apply_quest_rewards(quest, sink)` - **pętla po wszystkich**, bez `break` (to był bug SSiS).
- Zastosuj dokładnie raz (wzorzec `visit_node()`).
- **D11:** `max_items` wymaga zamiany `MAX_HOTBAR_ITEMS` (stała w `settings.py:317`) na pole gracza.
  `agility` **porzucone**. `eloquence` → sentyment (globalny modyfikator lub konkretny NPC - doprecyzować).
- **Auto-etykieta (D3=A):** `format_reward_label(rewards) -> str`, np. `+50 💰 · +10 sentymentu`.
  `success` to czysty tekst fabularny **bez `{value}`** - silnik dokleja etykietę.
  Uwaga: SSiS ma `get_quest_bonus_label()` z tym samym bugiem `break` - nie kopiować.
- Rozstrzygnąć: clamp `health` do `[0, max_health]` zawsze czy tylko przy nagrodzie zdrowotnej.
- Rozstrzygnąć: parasol daje własną nagrodę **ponad** podquestami (w SSiS tak, wartości sugerują zamiar).

**DoD:** test - quest z 3 nagrodami aplikuje 3; etykieta poprawna; `max_items` realnie zwiększa hotbar.

### Q-06 · Persystencja QuestState `#M` ✅

**Zrobione 2026-07-16.** Pliki: `SaveGame.quests` w `save_load/models.py`,
`_build_quest_state`/`_apply_quest_state` w `save_load/manager.py`, `Scene.quest_state`,
**`quests` w webowym `config_model/config.py`**, testy `tests/test_save_load_quest_state.py` (7).

#### ⚠ Luka z Q-01: webowy `Config` nie miał sekcji `quests`

`config_model/config.py` to bezpydanticowy mirror configu, ładowany **tylko na webie**
(`game.py:92`: `if IS_WEB: from config_model.config import load_config`). Q-01 dodało `quests`
do wersji Pydantic, ale nie do tego mirrora - czyli `conf.quests` wywaliłoby się na pygbag,
a na desktopie nigdy. Znalezione przy Q-06, naprawione. Przy okazji `Config.build()` przeszło
z argumentów pozycyjnych na nazwane: wstawienie pola w środku po cichu przesunęłoby
`messages` na `quests`.

Rozstrzygnięcia:

- **W save leży płaski `{klucz: {"done": bool}}`**, nie zserializowany obiekt `QuestState`.
  `asdict` zagnieździłby to w `quests.entries.<klucz>`; płasko save czyta się ludzko.
- **Nieznany klucz w save → ostrzeżenie i pominięcie**, nie wywalenie gry. Ale **jest**
  logowany, bo klucz, którego nikt nie definiuje, to zwykle przemianowany quest, czyli postęp,
  który gracz właśnie po cichu stracił.
- **Quest w definicjach, brak w save → nieukończony.** Nic do robienia: `is_done` czyta nieznany
  klucz jako `False`, co jest dokładnie tym, czego chcemy dla treści dodanej po zapisie.
- Zepsuty wpis (`{"Q00": "yes"}`) degraduje się do "nieukończony", cała zepsuta sekcja do `{}`.

**Weryfikacja:** test re-importu treści przepisuje `config.json` dokładnie tak jak importer
i sprawdza, że save jest **bajtowo identyczny**, a postęp przeżywa - to jest ta różnica wobec
SSiS, gdzie config **był** savegamem. Plus przejście na żywej grze: oznacz 2 questy → save →
load → oba wracają, `quest_done()` przez adapter je widzi. Webowy `load_config` (bez Pydantica)
ładuje 8 questów i `init_quests` je łyka. Smoke test "Save and Load Basic" - PASS.

**Goal:** postęp w save, nie w configu (D13).

**Plan:**

- `QuestState` do save/load, **oba backendy** (desktop + web).
- `config.json` **niemutowalny w runtime** - `just import-quests` nie może kasować postępu.
- Nieznany klucz w save (po zmianie treści) → ignoruj z ostrzeżeniem, nie wywalaj gry.
- Quest w definicjach, brak w save → traktuj jak `done: False`.

**DoD:** zapis/odczyt na obu backendach; test korupcji; re-import treści nie gubi postępu.

### Q-07 · Integracja runtime: event-driven + sweep `#M`

**Goal:** sprawdzanie questów wtedy, gdy ma sens (D12=C).

**Plan:**

- Eventy: koniec dialogu, zmiana ekwipunku (`ResultSink` to naturalny punkt), kaskada po ukończeniu questa.
- Sweep co ~1 s jako siatka bezpieczeństwa, **z ostrzeżeniem w logu** ("quest zapalił się ze sweepa,
  brakuje eventu") - siatka ma donosić, nie maskować.
- Docelowo dojdą warunki od lokacji - przewidzieć hook na zmianę mapy.

**DoD:** quest zapala się natychmiast po dialogu; sweep nie loguje ostrzeżeń przy poprawnym podpięciu.

### Q-08 · QuestPanel UI `#L`

**Goal:** dziennik pod `J`. **Projekt wizualny gotowy** - sekcja 6 HTML-a (makiety SVG, wymiary, paleta).

**Plan:**

- `project/ui/panels/quest.py` - `QuestPanel(Widget)`, tło `theme.nine_patch()`.
  Wzorzec: `panels/inventory.py`.
- `project/settings.py`: `"quest_log": {"show": ["key_J"], "msg": "action.quest_log",
  "keys": [pygame.K_j, pygame.K_F10]}`.
- `project/ui/game_ui.py`: `if INPUTS["quest_log"]: self.toggle(QuestPanel)` (wzorzec linia 136).
- `project/assets/locale/{PL,EN}.toml`: `action.quest_log` + sekcja `[quest]` (Wątki, Szczegóły,
  Kroki, Nagroda, filtry).
- Układ: 2 kolumny (wątki / szczegóły), pasek postępu, lista kroków, chipy nagród, stopka z podpowiedziami.
- Klawisze: `↑↓` wybór, `←→` filtr, `Enter` rozwiń, `Esc`/`J` zamknij. Rising edge przez `_fired()`.
- **Zablokowane kroki (`○`) są WIDOCZNE** - ustalone. Dawkowanie fabuły to zadanie autora, nie UI.

**DoD:** panel otwiera się `J`, pokazuje 8 questów, postęp 2/3 się zgadza; działa na web.

**Uwaga i18n:** etykiety panelu → TOML przez `_()`. Tytuły/opisy questów → `messages` przez `get_msg()`.
Te dwa mechanizmy się nie mieszają.

### Q-09 · Toasty questowe `#S`

**Goal:** powiadomienia. **Zero nowego mechanizmu** - `scene.add_notification()` już istnieje.

**Plan:**

- Ukończenie questa → `NotificationTypeEnum.success` + auto-etykieta nagród (Q-05).
- Odblokowanie → `NotificationTypeEnum.info`.
- Domknięcie wątku (parasol) odróżnić wizualnie od zwykłego kroku - inaczej gracz nie zauważy
  końca rozdziału. Makiety w sekcji 6 HTML-a.
- Dźwięk: później (SSiS wołał kanał `quest`).

**DoD:** 3 rodzaje toastów wyglądają jak makieta.

### Q-10 · Treść 8 questów + smoke test `#M` 🟡 szkic do przepisania

**Naszkicowane 2026-07-16 przez Claude, PL = źródło prawdy, EN przetłumaczone.**
Pliki: `doc/PL/Misje/{O co tu chodzi, Przełamać klątwę, Znajdź kogoś kto wie o klątwach}.md`
+ `doc/EN/Quests/*`. 3 łańcuchy, 8 questów, `just import-quests` przechodzi.

**To jest szkic, nie gotowa treść.** Proza jest do przepisania Twoim głosem - najsłabszym
punktem są nagrody (patrz niżej) i uzasadnienie fabularne `Q01_S05`.

#### ⚠ `SARCASMIA_AA_BACK_SO_SOON` nie istnieje w MoM

Klucz węzła z planu **nie istnieje** w `config.json`. Sarkażmijka ma węzły numeryczne
`000`-`021`, jak reszta postaci - klucz z planu pochodzi ze schematu nazw SSiS. Sprawdzone:
7 z 8 węzłów z planu istnieje, ten jeden nie. Gdyby wszedł do treści bez sprawdzenia,
`Q01_S05` byłby cichym trupem - dokładnie tym, co ten epik miał wyeliminować.

Semantycznie `SARCASMIA_AA_BACK_SO_SOON` ≈ węzeł `011` ("Ach, wracasz tak szybko... czy
udało Ci się zebrać moją małą listę zakupów?"), ale to jest **powrót** po drobiazgi, a nie
spotkanie. Dla questa "Spotkaj się z Sarkażmijką" wziąłem **`001`** - tam przyznaje, że to
klątwa, i deklaruje, że może pomóc. Czyli spotkanie z treścią, a nie samo otwarcie dialogu
(`000` zapala się od "dzień dobry").

**Do decyzji:** czy `001` to właściwy beat, czy raczej `003` (podaje listę trzech drobiazgów,
co naturalnie przekazuje pałeczkę do Q02).

#### Fabuła zweryfikowana w dialogach

Łańcuch faktycznie się spina (to nie były domysły, tylko odczyt z `config.json`):

- Miecz `015`: to klątwa, nie pech, rozpytaj ludzi, zacznij od karczmy.
- Barman `012`: pomóc może **Zielarka Zmora** (`POTIONEER_PUZZLEMINT`), chałupa koło lasu.
- Zielarka `014`/`017`: dawna **Mariolka**, dziś **Bibliofilistka des Informacja**
  (`MISS_INFORMATION`), pilnuje zakazanych ksiąg w tajnej bibliotece.
- Kowal `009`: do miasta nie jeżdżę, pytaj Barmana - on gada z przybyszami.
- Barman `017`: dwa dni na północ, za Splątanym lasem irytacji na wschód.

#### Nagrody (D11=D) - najsłabszy punkt szkicu

**Ustalone z kodu, nie zgadywane:** żaden dialog nie daje pieniędzy. Jedyne `NODE_RESULTS`
to kary sentymentu za chamstwo i wymiana u Sarkażmijki (oddajesz drobiazgi w `012`,
dostajesz `POTION_CURSE_NO_MORE` w `020`). Nie ma więc ryzyka podwójnej wypłaty.

Zasada, którą przyjąłem: **kroki informacyjne nie płacą, płacą parasole.** Nikt ci nie jest
winien pieniędzy za to, że *ty* się czegoś dowiedziałeś - a gracz dostaje rytm "3 × ✓ postęp,
potem wypłata za domknięcie wątku".

| Quest | Nagroda | Dlaczego |
| --- | --- | --- |
| `Q00_S00` | brak | prolog, miecz daje tylko sarkazm |
| `Q01_S00` | `max_health=20`, `damage=5` | wypłata za cały łuk; honoruje intencję SSiS (`hp→damage`, D11). `manual`, więc na razie nie odpali |
| `Q01_S01`, `Q01_S05` | brak | kroki informacyjne |
| `Q03_S00` | `max_health=10` | domknięcie wątku śledczego |
| `Q03_S01/S02/S03` | brak | kroki informacyjne |

**To odpowiada przy okazji na Pułapkę 7** (podwójna nagroda): skoro kroki nie płacą, nagroda
parasola nie jest "ponad" niczym. Ogólną regułę i tak trzeba świadomie zamknąć w Q-05.

Świadomie **nie użyłem** `sentiment` (D11 zostawia otwarte "globalny czy konkretny NPC")
ani `max_items` (wymaga przerobienia `MAX_HOTBAR_ITEMS` na pole gracza). Obie kategorie
przejdą walidację, ale nic jeszcze nie robią - do Q-05.

#### Weryfikacja (przejście silnikiem po prawdziwym configu)

Nowa gra → otwarte tylko `Q00_S00`. Miecz → domyka Q00, otwiera wątek klątwy. Barman `012`
→ domyka `Q01_S01`, otwiera `Q01_S05` **i cały wątek Q03**. Zielarka → 1/3, kowal → 2/3,
barman `017` → `Q03_S03` **i parasol `Q03_S00` w tym samym przebiegu** (kaskada) → 3/3.
Sarkażmijka → `Q01_S05`. Koniec: **7 z 8 ukończonych, `Q01_S00` otwarty** (`manual`).
To jest DoD Q-10.

`just import-dialogs` po `just import-quests`: 24 klucze `M_QUEST_` **przeżywają** (guard z
Q-04 działa na żywym materiale). `config.json` waliduje się Pydantikiem z 8 questami.

**Zostaje:** smoke test wizualny (`just run` + panel) - dopiero po Q-08, bo panelu jeszcze nie ma.

**Goal:** grywalny wątek.

**Plan:**

- Napisać `doc/PL/Misje/*.md` dla 4 łańcuchów (Q00, Q01, Q03 + parasole). PL = źródło prawdy.
- Wygenerować EN LLM-em, `just import-quests` waliduje.
- **Nagrody zaprojektować od nowa** (D11=D) - wartości SSiS to `agility`, którego nie ma.
- **Tytuły kroków muszą być zapowiedzią, nie spoilerem** - są widoczne przed odblokowaniem.
  "Jak tam dotrzeć?" dobre, "Wypij miksturę w kryjówce Sarkażmijki" złe.
- Poprawić literówkę `Q03_SO3` → `Q03_S03`.
- Smoke test: `just run`, przejść wątek, sprawdzić panel i toasty. Potem `just serve-web`.

**DoD:** wątek Q03 przechodzi od zera do domknięcia; `Q01_S00` zostaje otwarty (`manual`).

### Q-11 · Graf questów w Obsidianie `#S`

**Goal:** wizualizacja DAG w vaultcie - narzędzie autorskie i wykrywacz kolejnego `Q01_S07`.

**Plan:** reuse `scripts/dialog_graph.py` (DataviewJS + vis-network, `just dialog-graph`).
Quest-DAG to ten sam kształt: węzły + krawędzie. Węzły = questy, krawędzie = `requires` + `parent`.

**DoD:** `just quest-graph` generuje graf do `doc/_graphs/`.

## Pułapki (nie powtórz błędów SSiS)

1. **`break` w `apply_quest_bonus`** - aplikował TYLKO pierwszą niezerową nagrodę. Ofiary:
   `02_game_mechanics` `{max_health:20, agility:1}` i `Q01_S07` `{agility:100, hp:50}`.
   Zakomentowana pętla pod spodem pokazuje, że intencją było aplikować wszystkie. **Pętla, nie break.**
2. **`test: "False"` bez podquestów = cichy trup.** `Q01_S07` nigdy się nie kończy i blokuje
   cały wątek klątwy. Walidator (Q-01) **musi** to wyłapywać - to jedyny powód, dla którego
   wybraliśmy jawny enum `completion` (D5=A).
3. **`eval()` na całym `cfg`** - odpada. Mamy mini-DSL.
4. **`dialog.key ==` to wyścig** - sprawdza pozycję kursora, nie fakt. Po wczytaniu save'a fałszywy.
   Używamy `visited()` (D8).
5. ~~**`visited(npc, node)` iteruje po `scene.loaded_NPCs`**~~ - **rozwiązane w Q-02.**
   `find_visited_node()` (`dialog/context_adapter.py`) szuka w trzech miejscach, od
   najświeższego: `loaded_NPCs` (bieżąca mapa) → `loaded_maps[*]["NPCs"]` (mapy odwiedzone
   wcześniej w tej sesji, obiekty w cache) → `pending_map_states[*]` (mapy z save'a, na które
   gracz jeszcze nie wrócił - nie mają obiektów NPC, tylko stan). Przejście przez wszystkie trzy
   bez trafienia znaczy, że gracz nie miał jak spotkać tego NPC - wtedy `False` jest prawdą,
   nie cichą porażką. Trzeci poziom wymagał dodania `config_key` do `NPCState` w save
   (pole z defaultem `""`, stare save'y ładują się dalej, bez bumpa `SAVE_VERSION`).
6. **Config = savegame w SSiS.** W MoM `config.json` jest generowany i nadpisywany przez import.
   Stan idzie do save (D13).
7. **Podwójna nagroda:** parasol dostaje swój bonus ponad podquestami. Rozstrzygnąć świadomie (Q-05).
8. **Niespójne typy w SSiS:** `unlocks` bywa `null`/`false`/`str`, `test` bywa `bool`/`str`.
   U nas: `requires: list[str]` (domyślnie `[]`), `test: str | None` (D4).

## Bugi save/load (znalezione przy Q-02)

**Nie dotyczą tylko questów** - znalezione przy projektowaniu cross-mapowego `visited()`,
naprawione 2026-07-16 jako warunek wstępny Q-02. Oba są sprzed questów.

### Bug 1: stan innych map gubiony po wczytaniu

**Objaw:** stan **każdej mapy poza tą, na której zapisano grę**, był tracony po wczytaniu save'a.
Rozmowy (odwiedzone węzły, wybrane opcje, sentyment NPC), otwarte skrzynie, zabite potwory i
przedmioty na ziemi - wszystko wracało do stanu z TMX-a, gdy gracz tam wrócił.

**Przyczyna:** `SaveManager._apply_map_states` aplikował **tylko** `save.maps[current_map]`,
po czym robił `scene.loaded_maps.clear()`. Stan pozostałych map był poprawnie **zapisywany**
do pliku (`_build_map_states` iteruje po wszystkich `loaded_maps`), ale przy wczytaniu nikt go
już nie czytał - `save.maps` szło do śmieci razem z obiektem `SaveGame`.

**Naprawa:**

- `Scene.pending_map_states` - stan map z save'a, na które gracz jeszcze nie wszedł
  (świadomie **nie** w `self.properties`: to stan globalny, nie per-mapa).
- `SaveManager.apply_pending_map_state(scene)` - wołane z `Scene.load_map()` po zbudowaniu mapy
  z TMX-a, a przed `store_map()`. Zdejmuje wpis (dokładnie raz) i aplikuje.
- `_build_map_states` przepuszcza dalej mapy jeszcze nieodwiedzone. **To była pułapka w samej
  naprawie:** autosave leci przy *każdej* zmianie mapy, a `_build_map_states` czyta żywe obiekty,
  których pending mapa nie ma - bez tego przejście A → C kasowałoby postęp mapy B z nowego save'a.
- Przedmioty na ziemi: `apply_pending_map_state` **czyści** je przed aplikacją. TMX własnie je
  zrespawnował, a save wie, które gracz już podniósł - trzeba zastąpić, nie dokleić.

**Weryfikacja:** `tests/test_save_load_multi_map.py` (7 testów; sprawdzone, że **failują na starym
kodzie** - inaczej nic by nie testowały). Plus smoke testy `just test "Save and Load Basic"` i
`just test "Auto Save on Map Change"` - oba PASS.

### Bug 2: duplikowanie przedmiotów na ziemi (potwierdzony i naprawiony)

Podejrzenie z pierwszego podejścia, **potwierdzone empirycznie na żywej grze** (2026-07-16),
okazało się gorsze niż wyglądało.

**Objaw (zmierzony, nie domysł):** `Village` ma 4 przedmioty na ziemi z TMX-a
(`GNOMES_WHISKER`, `MERMAIDS_TEAR`, `PHOENIX_FEATHER`, `golden_coin` - czyli **przedmioty
questowe**). Save + load: **4 → 8**. I to **narasta z każdym cyklem**: 4 → 8 → 12 → 16, bez
ograniczenia. Gorzej: podniesiony przedmiot **wracał na ziemię**, zostając jednocześnie w
plecaku - czyli darmowe duplikowanie przedmiotów questowych w kółko.

**Przyczyna:** świeżo zbudowana mapa respawnuje wszystkie przedmioty z TMX-a (`Scene.load_items`),
a `_apply_ground_items` **dokleja** do nich te zapisane, zamiast zastąpić. Save wie, co gracz już
podniósł; TMX nie.

**Naprawa:** `_restore_ground_items` = wyczyść + zastosuj; save jest źródłem prawdy.
Obie ścieżki (bieżąca mapa i pending) idą teraz przez **jedno** `_apply_one_map_state` - bo to
właśnie rozjazd dwóch kopii tego samego kodu pozwolił temu bugowi przeżyć (kopia pendingowa
czyściła, kopia dla bieżącej mapy nie).

**Weryfikacja:** repro na żywej grze przed i po (4 → 8 → 12 → 16 vs stabilne 4; podniesiony
przedmiot zostaje podniesiony) + 2 testy regresyjne w `test_save_load_multi_map.py`, sprawdzone
że failują na starym kodzie z dokładnie tym objawem (`expected 1, got 2`).

## Weryfikacja

- Testy jednostkowe: `project/quest/` bez pygame (wzorzec: testy dialogów).
- `just import-quests` - błędny warunek wywala import z nazwą pliku.
- `just run` - przejść Q03 od zera, panel pod `J`, toasty, postęp 2/3.
- `just serve-web` - panel i persystencja działają na pygbag (brak Pydantic!).
- Save/load w połowie wątku - postęp przeżywa.
- `just import-quests` po zmianie treści **nie kasuje** postępu w save.

## Podgląd dokumentu HTML

Serwer z auto-reloadem na mac-mini: `docserve status` / `docserve start <ścieżka>` (`~/bin/docserve`,
tailnet-only). URL: `http://mac-mini.kamori-vector.ts.net:8899/quest-system-ssis-2026-07-16.html`.
