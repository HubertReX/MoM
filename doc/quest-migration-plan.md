# Quest System - plan migracji SSiS -> MoM

Handoff do implementacji. Dokument samowystarczalny: nie trzeba czytać źródeł SSiS ani HTML-a.

- Analiza + 15 decyzji + projekt panelu: [[_attachements/quest-system-ssis-2026-07-16.html]] (commit `4de1448`)
- Wzorzec migracji dialogów: [[dialog-migration-plan.md]]
- Źródło SSiS: `~/Projects/RPG` (`quests.py`, `config.json`, `utils.py`, `ui.py`)

## Stan

Wszystkie **15 decyzji zamkniętych** (2026-07-16). Kod: **nic nie zaczęte**. Następny krok: taski Q-01..Q-11.

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
| `Q01_S05_..._MEET_MADAME_SARCASMIA` | Spotkaj się z Sarkażmijką | test | `visited("MADAME_SARCASMIA", "SARCASMIA_AA_BACK_SO_SOON")` |
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

### Q-01 · Encje questów + model danych `#M`

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

### Q-02 · DSL: `quest_done()` + `eval_number()` `#M`

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

### Q-03 · Silnik questów: DAG, requires, completion `#L`

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

### Q-04 · Pipeline importu MD → config `#L`

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

### Q-06 · Persystencja QuestState `#M`

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

### Q-10 · Treść 8 questów + smoke test `#M`

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
5. **`visited(npc, node)` iteruje po `scene.loaded_NPCs`** (`context_adapter.py:44`) - quest może
   pytać o NPC **spoza załadowanej sceny**. Dialogi tego problemu nie miały (zawsze był bieżący NPC).
   **Do rozwiązania w Q-02** - inaczej quest cicho nie zapali się na innej mapie.
6. **Config = savegame w SSiS.** W MoM `config.json` jest generowany i nadpisywany przez import.
   Stan idzie do save (D13).
7. **Podwójna nagroda:** parasol dostaje swój bonus ponad podquestami. Rozstrzygnąć świadomie (Q-05).
8. **Niespójne typy w SSiS:** `unlocks` bywa `null`/`false`/`str`, `test` bywa `bool`/`str`.
   U nas: `requires: list[str]` (domyślnie `[]`), `test: str | None` (D4).

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
