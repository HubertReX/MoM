# H01 - ambient barki, emoji z rutyn, wskaźnik questa na HUD

Priorytet: **P3** (Faza 4). Rozmiar: **L**. Zależności: **miękka** - korzysta z rutyn
(`npc_schedule.py`), z silnika warunków dialogów (`dialog/conditions.py`), z trybu
deterministycznego ([A04](A04-tryb-deterministyczny-testow.md)) i z layout self-checks
([A03](A03-layout-selfchecks.md)).

Status: **zrealizowane 2026-08-10** (wszystkie pięć etapów). To jest **połowa silnikowa**.
Treść (sidequesty, dialogi klątwy, teksty barków) mieszka w
[H03](H03-sidequesty-i-klatwa.md) i powstaje w Obsidian ręką autora - tutaj zbudowaliśmy
wyłącznie to, co ma tę treść unieść. Silnik stoi dziś pusty, więc gra wygląda dokładnie
jak przed zadaniem.

## Co się zmieniło wobec planu (realizacja)

Trzy miejsca, w których kod świadomie odszedł od dokumentu - i dlaczego:

- **`T` na queście wybranym przez automat PRZYPINA, nie odpina.** Tabela w D7 mówiła
  „aktualnie śledzony -> odpięcie", zakładając milcząco, że *śledzony* znaczy *przypięty*.
  Wskaźnik jest jednak ustawiony także wtedy, gdy wybrał go automat - i wtedy „odpięcie"
  nic by nie zmieniło (`auto_pick` odda ten sam quest), a gracz dostałby komunikat
  o powrocie do trybu, z którego nigdy nie wyszedł. Co gorsza, questa wybranego automatem
  nie dałoby się przypiąć **nigdy**. Rozróżnienie idzie więc po stanie: przypięty ->
  odpinamy, śledzony automatycznie -> przypinamy.
- **Krok 4 kaskady to „ostatni w kolejności definicji", nie „najpóźniej odblokowany".**
  `QuestState` niesie wyłącznie `{done: bool}` (D13), więc czasu odblokowania po prostu
  nie ma, a dokładanie znacznika czasu wyłącznie dla tego fallbacku byłoby nowym polem
  w zapisie - dokładnie tym, czego D7 chciało uniknąć.
- **Sukces przypięcia nie dostaje toasta**, tylko znacznik na liście (dokument to
  przewidywał, ale pierwsza wersja implementacji dała jedno i drugie - zrzut ekranu
  pokazał toasta zasłaniającego listę, czyli dokładnie to, przed czym D7 ostrzegało).
  Odmowa toasta dostaje, bo nie zmienia niczego na ekranie.

Dwa błędy, które wyszły dopiero z licznika `routine_emotes_shown` w `debug_ui_state`
(bez niego asercja „coś wisi nad głową" nie ma zębów, bo `dots_anim` wisi nad każdym
rozmownym NPC-em, a `$_anim` nad każdym kupcem):

- **zerowanie odliczania emoji na granicy kroku** - przy `GAME_TIME_SPEED 0.25` krok
  rutyny trwa ~12-48 sekund realnych, a odstęp między emoji to 40-90 s, więc przeliczany
  od nowa termin prawie nigdy nie wypadał wewnątrz kroku;
- **tykanie emoji w `_continue_slot`**, które celowo wychodzi wcześniej, gdy postać
  jeszcze idzie - a idzie prawie cały czas. Sztandarowy przypadek z tego dokumentu
  („głodny, gdy idzie na lunch") dzieje się właśnie w drodze.

Dwie rzeczy z planu **nie weszły**, obie z podanym powodem:

- **wiersz `RAT` w `characters.csv` (D9)** - sprite `HamsterGray` nie istnieje w repo (wg
  W9 wgrywa go autor), a reguła 5 walidatora słusznie odrzuca postać ze sprite'em bez
  folderu. Dopisanie wiersza przed assetem postawiłoby `just validate-world` na czerwono.
- **rodzaj `bark_pool` w `scripts/rename_entity.py`** - dokument stawiał to jako pytanie
  („do sprawdzenia przy realizacji") i odpowiedź brzmi „jeszcze nie":
  `test_every_kind_has_at_least_one_source` odrzuca rodzaj klucza, który nie ma w repo ani
  jednego wystąpienia, a pul nie ma do czasu treści z H03. Wtedy dopisać.

Do weryfikacji u autora (headless tego nie rozstrzyga): czytelność barka na trawie i na
podłodze tawerny, czy 3,5 s to dobry czas życia, czy cooldown 60 s nie jest za długi, czy
emoji nie robią się szumem przy 30 NPC. Osobne pytanie projektowe: krok `sleep` ustawia
`zzz` na stałe, ale `update_sleepers` zdejmuje śpiącą postać z grupy rysowania, więc dziś
widać to tylko przez klatkę przed zniknięciem.

Zadanie zamyka znaleziska **G-3** (sentyment ma głębsze skutki niż widać) i **G-4**
(noc/rutyny to koszt bez nagrody gameplayowej) z [audytu](audyt.md) oraz dwie pozycje
z rozdziału „gdzie gracz może się nudzić": *martwe odpowiedzi* i *brak celu
krótkoterminowego na HUD*.

## Poprawki po pierwszym teście u autora (2026-08-10)

Autor wgrał `HamsterGray`, dopisał wiersz `RAT`, napisał pierwsze barki - i zobaczył
trzy rzeczy, których headless nie pokazał:

- **Czarne prostokąty wokół barków.** `BarkSprite` dostaje
  `blendmode = pygame.BLEND_ALPHA_SDL2`, który `PyscrollGroup` podaje dalej jako flagę
  blitu. Bez niej SDL blituje sprite'a ścieżką „copy" i wpisuje alfę źródła do
  `game.canvas`: przezroczyste tło barka wychodzi na ekranie czarnym prostokątem
  wielkości całego sprite'a - także wokół **milczącego** barka, bo ten jest
  przezroczysty w całości, więc raz odezwana postać zostawiała czarną plamę na stałe.
  To ta sama pułapka i to samo lekarstwo, co przy cząstkach rozpadu (`particles.emit`)
  i kursorze myszy (`game.custom_cursor`) - obie opisane w `project/AGENTS.md`.
  **Dlaczego bramka tego nie złapała:** format okna na macOS ma maskę alfy, a SDL
  dummy nie ma jej wcale, więc ta sama scena headless wygląda czysto. Zrzut agenta
  na prawdziwym ekranie wymaga `MOM_AGENT_SS_CANVAS=1` (`self.screen` po `flip()`
  to pusty back-buffer), a `agent_ctrl.capture` zapisuje teraz `convert(24)` - bez
  tego PNG z prawdziwego ekranu jest w całości przezroczysty i nie da się go obejrzeć.
- **Warunek po kroku rutyny, nie tylko po `activity`** (życzenie autora): nowy predykat
  **`at("type:work")`** w `ConditionScope.bark`. Cytuje pole `at` kroku **dosłownie tak,
  jak stoi w `routines.toml`**, z rodzajem (`type:` / `location:` / `route:`), więc
  obsługuje wszystkie trzy warianty destynacji jednym predykatem i nie wprowadza
  drugiego słownika nazw. Rozróżnienie względem `activity()`: `activity("stand")` to
  „stoi" i obejmuje barmana, kowala i Barta naraz, a `at()` mówi, **który to krok dnia**.
  Słownik dozwolonych wartości bierze się wprost z `routines.toml`, a pilnuje go
  **reguła 20** walidatora - `at("type:wrok")` i skrót `at("work")` bez rodzaju są
  błędem przy `just validate-world`, a nie cichym `False`.
- **Znacznik śledzonego questa nachodził na tytuł.** W kolumnie wątków nie ma miejsca
  na słowo, więc na liście został **sam symbol** (pierścień z oczkiem, kształtami -
  font pikselowy nie ma ◉), a napis „śledzony" przeniósł się na prawą stronę, do linii
  nagłówka **SZCZEGÓŁY**, i pokazuje się tam dla questa, którego szczegóły akurat widać.
  Licznik/`manual` zostaje widoczny obok symbolu - wcześniej znacznik go kasował.

Przy okazji, bo od treści barków zrobiło się czerwono: `scripts/rename_entity.py`
nie ruszał sekcji `barks` w `config.json`, więc rename mapy zostawiał w warunku
`on_map("STARA_NAZWA")` (i `test_rename_entity` to złapał). Rename obsługuje teraz
właściciela puli oraz argumenty `on_map` / `visited` / `has_item` / `item_count`
w warunkach barków. Osobnego **rodzaju** klucza `bark_pool` dalej nie ma - to wciąż
czeka na treść z H03.

## Decyzje autora (wiążące, ustalone 2026-08-10)

- **W1** - bark to **sam tekst z obrysem**, rysowany w przestrzeni świata (jak imię pod
  postacią), **nie** panel i **nie** toast. Panel zasłoniłby za dużo mapy.
- **W2** - emoji nad głową i barki tekstowe to **dwa niezależne kanały**. Oba wchodzą,
  autor ocenia po fakcie, który się lepiej sprawdza. Żaden nie zastępuje drugiego.
- **W3** - emoji wynika z **kroku rutyny** (sen → `zzz`, lunch → głód, praca → wysiłek),
  ale moment i wariant (`_anim` czy statyczny) **losowo**, żeby wieś nie tykała jak zegarek.
- **W4** - bark odpala się na **zbliżenie gracza + długi cooldown**, plus dodatkowo
  wynika z rutyny (głodny, gdy idzie na lunch), również z elementem losowym.
- **W5** - teksty barków: sekcja `## Barki` w pliku postaci (`doc/PL/Postacie/`) dla
  nazwanych NPC + **wspólna pula** w `doc/PL/Barki.md` dla statystów i zwierząt.
- **W6** *(zmienione 2026-08-10, po pierwszej wersji planu)* - wskaźnik questa **da się
  przestawić ręcznie**: jeden skrót klawiszowy, duża wygoda. Po ukończeniu śledzonego
  questa wskaźnik **sam przechodzi dalej**; jeśli ten quest coś odblokował, śledzimy
  pierwszy z nowo odblokowanych, a na wypadek, gdy nie odblokował nic - musi istnieć
  fallback. *(Poprzednia wersja: „tylko automatyczny, bez przypinania" - nieaktualna.)*
- **W7** - zwierzęta dostają **emoji + onomatopeje** („Muuu", „Ko-ko"), a Miecz
  Ciętej-riposty czasem to komentuje. Mechanizm reakcji zwierząt na gracza **już jest**
  (`npc_state.py:17` - `shocked_anim` przy kolizji) i ma zostać rozszerzony, nie napisany
  od zera.
- **W8** - rozszerzenia mechanik pod sidequesty **przyjęte wszystkie cztery**: zamknięta
  skrzynia + klucz, zamknięte drzwi + klucz, oddawanie przedmiotu w dialogu (już działa),
  krzak/kamień jako blokada questowa (już działa).
- **W9** - sprite przeciwnika do piwnicy: **`HamsterGray`** z oryginalnego asset packa
  NinjaAdventure (wygląda jak mysz). Nazw assetów nie zmieniamy - referencja do oryginału
  jest ważniejsza niż spójność z kluczem encji.

## Kontekst

Silnik ma dziś wszystko, czego potrzeba, żeby wieś żyła - i nie robi z tego użytku:

- **`EmoteSprite` już istnieje** (`objects.py:316`) z `set_emote()` (stałe) i
  `set_temporary_emote(emote, duration)` (chwilowe). Ma 60 emoji w
  `EMOTE_SHEET_DEFINITION` (`settings.py:1131`), w tym 12 wariantów `_anim`. Używany jest
  **w czterech miejscach**: walka (`combat.py:150,174`), krok `idle` rutyny
  (`npc.py:561`), kolizja z graczem (`npc_state.py:17`), zderzenie w ruchu
  (`movement.py:276`). Cała reszta puli leży odłogiem.
- **Rutyny wiedzą, co postać robi** (`npc_schedule.py`, `scene/routines_director.py`):
  `slot.activity` to jedno z `sleep`, `wander`, `idle`, `stand`, `patrol`, a
  `characters.csv` mówi dokąd (`home`/`work`/`social`/`hobby`). Ta wiedza nie wychodzi
  dziś poza sterowanie nogami.
- **Silnik warunków jest gotowy i bezpieczny** (`dialog/conditions.py`): whitelista
  węzłów AST, `ConditionScope` per kontekst, walidacja przy imporcie z `file:line`,
  cache przez `lru_cache`. Predykaty `visited`, `has_item`, `item_count`, `quest_done`
  plus `sentiment` w zakresie dialogu. Bark to kolejny konsument tego samego silnika,
  a nie powód, żeby pisać drugi.
- **Panel questów jest, wskaźnika nie ma.** `QuestPanel` (`ui/panels/quest.py`) pokazuje
  pełny dziennik pod klawiszem, ale nic nie prowadzi wzroku „co teraz?". `QuestRuntime`
  (`quest/runtime.py`) już liczy `newly_done` i `newly_unlocked` przy każdym zdarzeniu -
  wskaźnik może się z tego karmić bez ani jednego nowego przebiegu po questach.
- **Napis w przestrzeni świata ma już wzorzec**: `HealthBar.set_bar()` (`objects.py:228`)
  rysuje imię postaci fontem `FONT_SIZE_EXTRA_TINY` (8 px) z cieniem `(84, 135, 137)`,
  z zawijaniem na spacji. Komentarz w tym miejscu tłumaczy dlaczego 8, a nie 10:
  napis jest wtapiany w sprite świata i skalowany zoomem kamery (~3,8x), więc nie
  podlega regułom tekstu UI.

Czego brakuje: pętli, która to spina, i formatu, w którym autor pisze teksty.

## Decyzje projektowe

| # | Decyzja | Rozstrzygnięcie |
| --- | --- | --- |
| D1 | Warunki barków | **rozszerzenie istniejącego mini-DSL** (`ConditionScope.bark`), nie drugi silnik |
| D2 | Gdzie żyje tekst barka | `messages` w `config.json` (jak dialogi) + nowa sekcja `barks` z warunkami |
| D3 | „Wieś wie o klątwie" | **`quest_done("Q01_S01_LEARN_ABOUT_CURSE")`** + **reguła 20 walidatora** jako bramka |
| D4 | Rysowanie barka | nowy `BarkSprite` w `scene.label_sprites`, wzorowany na `HealthBar` |
| D5 | Wybór barka spośród pasujących | losowanie z **zasianego** RNG (A04), waga = kolejność w pliku |
| D6 | Emoji z rutyny | **opcjonalne pole `emotes` w slocie** `routines.toml`, bez osobnej tabeli |
| D7 | Który quest na HUD | automat + **ręczna zmiana klawiszem `T`** w dzienniku; po zamknięciu - kaskada |
| D8 | Zamek na skrzyni i drzwiach | jedno pole `requires_item` + `consumes_key` w obu miejscach |
| D9 | Klucz encji nowego wroga | **`RAT`** (jeden wariant), sprite `HamsterGray` |

### D1 - dlaczego bark dostaje własny `ConditionScope`, a nie `dialog`

`ConditionScope` istnieje dokładnie po to: dialog ma bieżącego NPC (więc `sentiment`
i jednoargumentowe `visited()` mają sens), a quest go nie ma (więc `visited()` wymaga
dwóch argumentów). Bark jest trzecim przypadkiem: **ma** bieżącego NPC - to ten, który
mówi - ale **ma też** rzeczy, których żaden z dwóch pozostałych nie zna: porę dnia,
aktualny krok rutyny i mapę.

Nowy `ConditionScope.bark`:

| Predykat / nazwa | Skąd | Uwagi |
| --- | --- | --- |
| `visited(node)` / `visited(npc, node)` | jak w dialogu | mówiący jest kontekstem |
| `has_item(key)`, `item_count(key)` | wspólne | ekwipunek gracza |
| `quest_done(key)` | wspólne | nośnik „wieś wie o klątwie" (D3) |
| `sentiment` | jak w dialogu | sentyment **mówiącego** do gracza |
| `time_of_day(faza)` | **nowe** | `"morning"`, `"day"`, `"evening"`, `"night"` - patrz niżej |
| `activity(nazwa)` | **nowe** | bieżący `slot.activity` z rutyny (`sleep`, `idle`, …) |
| `on_map(klucz)` | **nowe** | klucz mapy z rejestru (C02, `scene/map_registry.py`) |

Trzy nowe predykaty, zero nowych mechanizmów - `_validate_call` sprawdzi arność, a błędny
warunek w pliku Obsidiana wywali `just import-dialogs` z numerem linii, tak jak dziś
wywala błędny warunek opcji dialogowej.

#### Fazy doby: nazwy po angielsku, granice już istnieją w kodzie

Nazwy faz są **po angielsku**, jak cała reszta mini-DSL. Warunek to kod, nie zdanie -
`time_of_day("morning")` stoi obok `has_item("silver_key")` i `quest_done(...)`, więc
`"rano"` byłoby jedynym polskim napisem w wyrażeniu. Napisy dla gracza i tak żyją osobno,
w locale (C02/W2).

**Granic nie wymyślamy - one już są w grze**, tylko nie mają nazw. `scene/night_filter.py`
dzieli dobę na cztery odcinki godzinami **6, 9, 17, 20**, i robi to **w trzech miejscach**
(`filter_color` w liniach 111-120, warunek w 159-160, `night_weight` w 230-236) -
za każdym razem literałami. Fazy barków biorą dokładnie te same liczby, bo inaczej
gracz zobaczy zachód słońca w jednym momencie, a usłyszy „dobry wieczór" w innym:

| Faza | Godziny | Co się dzieje na ekranie |
| --- | --- | --- |
| `morning` | 06:00-09:00 | rozjaśnianie: interpolacja z `NIGHT_FILTER` do `DAY_FILTER` |
| `day` | 09:00-17:00 | pełne światło, filtr = `DAY_FILTER` |
| `evening` | 17:00-20:00 | ściemnianie: interpolacja z `DAY_FILTER` do `NIGHT_FILTER` |
| `night` | 20:00-06:00 | pełny `NIGHT_FILTER` |

Dlaczego `morning`/`evening`, a nie `dawn`/`dusk`: to są bloki po trzy godziny, a nie
chwile. `dusk` sugeruje moment zachodu, a tu chodzi o całe popołudnie od 17:00. Autor
piszący „Ostatnia kolejka!" myśli „wieczorem", nie „o zmierzchu".

**Gdzie mieszka mapowanie.** Nowa stała w `settings.py` plus jedna funkcja - i to ona
staje się **jedynym** źródłem prawdy:

```python
# Faza zaczyna się o podanej godzinie i trwa do początku następnej;
# ostatnia zawija się przez północ do pierwszej (20:00 -> 06:00).
DAY_PHASES: tuple[tuple[str, float], ...] = (
    ("morning",  6.0),
    ("day",      9.0),
    ("evening", 17.0),
    ("night",   20.0),
)
```

`day_phase(hour: float) -> str` w `scene/world_clock.py` - tam, gdzie już jest zegar.
Musi obsłużyć **zawinięcie przez północ**: `night` to jedyna faza, dla której początek
jest większy od końca, i naiwne `start <= h < end` zwróci dla 02:00 pustkę.

**`night_filter.py` przechodzi na `DAY_PHASES` - to część zadania, nie opcja.**
Trzy komplety literałów 6/9/17/20 (`filter_color:111-120`, warunek `:159-160`,
`night_weight:230-236`) czytają granice ze stałej. Bez tego `DAY_PHASES` byłoby
czwartym kompletem tych samych liczb, czyli pogorszeniem stanu, a nie naprawą.

Zakres jest wąski i taki ma zostać: **wymieniamy skąd biorą się liczby, nie jak liczy
się kolor**. Wzory interpolacji, `NIGHT_FILTER`, `DAY_FILTER`, wyjście wcześniejsze
w dzień i cała optymalizacja z [E01](E01-filtr-nocy-desktop-i-web.md) zostają nietknięte.
Przy tych samych granicach wynik jest identyczny co do piksela.

**Bramka: `just test-unit` w całości plus `mypy`** - to one łapią to, czym ten refactor
realnie grozi, czyli wyjątkiem w runtime (literówka w nazwie fazy, złe rozpakowanie
krotki, `None` z lookupu). Testy wizualne i ocena wyglądu **zostają po stronie autora** -
nie ma tu bramki ss-review ani zrzutów do porównania.

Jedno nowe *unit*-owe: `tests/test_day_phases.py` dla samej funkcji `day_phase()` -
zawinięcie przez północ i podział doby bez dziur. To test nowej funkcji, wymagany tak
samo jak każdy inny w tym zadaniu, a nie dodatkowa bramka na refactor. Test wiążący
`DAY_PHASES` z `night_weight()` **odpada** - po refactorze źródło jest jedno, więc nie
ma czego z czym wiązać.

**Fazy muszą być podziałem doby bez dziur i bez zakładek** - test ma to sprawdzać dla
każdej pełnej i połówkowej godziny. Dołożenie piątej fazy (np. `noon`) to jeden wpis
w krotce, ale zmienia znaczenie już napisanych barków `day`, więc nie robimy tego „na
wszelki wypadek".

**Nie myl `time_of_day` z `activity`.** Zegar mówi, która jest godzina na świecie;
`activity()` mówi, co robi **ta** postać. Barman ma lunch o innej porze niż Bart
(`routines.toml`: `[[routine.barman.slot]]` nie przerywa pracy w porze lunchu), więc
bark „głodny" to `activity("wander")` na slocie `type:social`, a nie `time_of_day("day")`.

### D2/D5 - format autorski i co z niego wychodzi

**Nazwany NPC** - sekcja w jego własnym pliku, tuż pod „Tło historyczne", żeby ton
barków pisało się patrząc na charakter postaci:

```markdown
## Barki

- Kufle same się nie umyją.
- [time_of_day("morning")] O tej porze to tylko ja i myszy.
- [time_of_day("evening")] Ostatnia kolejka! Żartowałem.
- [sentiment > 60] O, mój ulubiony klient!
- [quest_done("Q01_S01_LEARN_ABOUT_CURSE")] Siadaj tam. Dalej. Jeszcze dalej.
```

**Statyści i zwierzęta** - wspólne pule w `doc/PL/Barki.md`. **Nagłówek sekcji jest
kluczem puli, dosłownie** - dokładnie ta sama konwencja co w plikach questów
(„nagłówek sekcji jest kluczem questa, dosłownie, i musi być globalnie unikalny",
`doc/quest-cheatsheet.md`). Klucz jest w `SCREAMING_SNAKE`, jak każdy klucz encji po C02,
więc nie ma w nim polskich znaków ani spacji, a zmiana nazwy pliku niczego nie psuje:

```markdown
## VILLAGERS

Proza dla autora: pula dla mieszkańców bez własnego pliku postaci.
Nie trafia do gry - liczą się tylko wypunktowania niżej.

- [time_of_day("morning")] Dzień dobry.
- [activity("stand")] Robota sama się nie zrobi.

## FARM_ANIMALS

Pula dla krowy, świni i konia.

- Muuu.
- Mu?
```

Kto bierze z której puli: **nowa kolumna `barks` w `characters.csv`**, a jej wartością
jest **klucz puli**, czyli dosłownie ten nagłówek:

| `key` | `barks` | co dostaje |
| --- | --- | --- |
| `BARMAN_ABSINTHRAYNER` | `VILLAGERS` | własna sekcja `## Barki` **+** pula `VILLAGERS` |
| `BART` | `VILLAGERS` | tylko pula (nie ma własnego pliku) |
| `COW` | `FARM_ANIMALS` | tylko pula |
| `HAMMER_HOAXHEART` | *(puste)* | tylko własna sekcja `## Barki` |
| `SNAKE` | *(puste)* | nic - milczy |

**Sekcja własna i pula sumują się**, nie wykluczają. Barman ma swoje żarty i mówi też
„dzień dobry" jak każdy inny mieszkaniec - gdyby pula wykluczała własne linie, każda
postać z choćby jednym własnym barkiem musiałaby mieć przepisany cały komplet.

Pusta komórka `barks` **nie jest błędem** - to samo rozumowanie, co przy pustej komórce
`routine` dzisiaj (`routines.toml` mówi to wprost: „Pusta komórka destynacji nie jest
błędem"). Postać bez puli i bez własnej sekcji po prostu milczy.

Dwie reguły walidatora, które to domykają (razem z regułą z D3 niżej):

- `barks` nazywa pulę, której nie ma w `doc/PL/Barki.md` → **ERROR**,
- pula, do której nie odwołuje się żadna postać → **WARN** (martwy tekst, nie awaria).

**Do sprawdzenia przy realizacji:** czy `scripts/rename_entity.py` (C02/D10) ma dostać
siódmy rodzaj klucza - `bark_pool`. Jeśli tak, `tests/test_rename_entity.py` (D17)
i tak zapali się przy nowym pliku danych, którego nie obejmuje żaden glob manifestu -
to jest dokładnie sytuacja, na którą ten test powstał.

Import (`dialog/markdown_importer.py`) emituje:

- do `messages`: `bark.<WŁAŚCICIEL>.<nnn>` = tekst (PL i EN, jak dialogi),
- do nowej sekcji `barks` w `config.json`:
  `{właściciel: [{"msg": "bark.X.003", "condition": "sentiment > 60"}, …]}`.

Właściciel to klucz postaci **albo** nazwa puli - jedna sekcja obsługuje oba, bo dla
runtime'u to ta sama rzecz: lista kandydatów z warunkami.

**Wybór spośród pasujących (D5):** losowanie z RNG zasianego jak cząstki
(`scene._particle_rng()` - wzór z A04), **nigdy** z gołego `random`. Bark, który raz
wypadnie tak, a raz inaczej przy tym samym seedzie, zabija scenariusze agentowe.
Kandydat wybrany ostatnio jest wykluczony z następnego losowania u tej samej postaci -
inaczej Barman powtórzy ten sam żart dwa razy pod rząd i wyjdzie z tego usterka, a nie żart.

### D3 - „wieś wie o klątwie" bez nowego rejestru stanu

Autor chce, żeby po ujawnieniu klątwy zmieniły się powitania, doszły nowe opcje
dialogowe, a część domyślnych zniknęła. Kuszące jest dopisać do configu tabelę
„światowych faktów". Nie trzeba - **ten fakt już jest zapisany i już się serializuje**:

`Q01_S01_LEARN_ABOUT_CURSE` (`doc/PL/Misje/Przełamać klątwę.md`) ma dziś test
`visited("BARMAN_ABSINTHRAYNER", "012") or visited("BARMAN_ABSINTHRAYNER", "009")`.
Wystarczy **rozszerzyć ten test** o pozostałe linie, w których Malachi się przyznaje
(u Zielarki `#009`, u Miecza, u kolejnych postaci z H03), i każdy bark oraz każda opcja
dialogowa pyta o jedną rzecz:

```
quest_done("Q01_S01_LEARN_ABOUT_CURSE")
```

Zysk: zero nowego pliku danych, zero nowego pola w zapisie (`QuestState` już jest
serializowany, decyzja D13 systemu questów), zero drugiego miejsca, które może się
rozjechać z pierwszym. Koszt: fakt świata jest wyrażony questem, więc **skasowanie albo
przemianowanie tego questa wyłączy reakcje wsi na klątwę**.

#### Bramką jest walidator, nie wpis w `AGENTS.md`

Sam dopisek w dokumentacji tego nie utrzyma - to jest dokładnie rozumowanie z C02/D17
(„wpis w `AGENTS.md` nie daje gwarancji… bramką jest CI"), tam zastosowane do skryptu
rename'ującego, tu do treści.

**Nowa reguła 20 w `scripts/validate_world.py`:** każde `quest_done("KLUCZ")` występujące
w **dowolnym** warunku - barka, opcji dialogowej, `Test:` i `Postęp:` questa - musi
nazywać istniejącego questa. Poziom: **ERROR**.

Dlaczego to musi być właśnie walidator świata, a nie importer:

- `validate_condition()` sprawdza składnię, arność i whitelistę - nie ma i nie powinien
  mieć pojęcia, jakie questy istnieją (silnik warunków celowo nie importuje niczego z gry),
- import dialogów i import questów to **dwa osobne przebiegi** (`just import-dialogs`,
  `just import-quests`), więc żaden z nich nie widzi obu stron naraz,
- `validate_world` czyta **wszystkie** źródła i po to powstał (C01). To ta sama klasa
  co reguła 16 z C02 („`model_name` w tilesecie musi być kluczem istniejącej postaci").

Przy okazji, tym samym kosztem, reguła 20 obejmuje **wszystkie** predykaty odwołujące się
do encji, nie tylko questy:

| Predykat w warunku | Musi nazywać | Poziom |
| --- | --- | --- |
| `quest_done("K")` | istniejącego questa | ERROR |
| `has_item("K")`, `item_count("K")` | klucz z `items.csv` | ERROR |
| `visited("NPC", "WĘZEŁ")` | postać **i** jej węzeł dialogu | ERROR |
| `on_map("K")` | klucz z `map_registry.all_map_keys` | ERROR |
| `activity("nazwa")` | jedno z `sleep`/`wander`/`idle`/`stand`/`patrol` | ERROR |

To jest realna wartość dodana wobec dzisiejszego stanu: dziś literówka w
`visited("BARMAN_ABSINTHRAYNER", "0012")` daje **cichy `False`** na zawsze - warunek,
który nigdy nie zapali, i opcję dialogową, której gracz nigdy nie zobaczy. Dokładnie ta
klasa błędu wyłączyła kiedyś cały dialog Miecza (patrz „Znane bugi (fix 2026-07-08)"
w `project/AGENTS.md`). Wpis w `AGENTS.md` zostaje jako wyjaśnienie dla człowieka -
ale gwarancją jest CI.

Gdyby `quest_done` okazało się za sztywne (np. autor będzie chciał „wie tylko połowa
wsi"), alternatywą jest nazwany alias warunku w osobnym pliku - ale to decyzja na wtedy,
nie na teraz. Nie budujemy jej na zapas.

### D4 - jak narysować napis, którego nie da się nie przeczytać

`BarkSprite` idzie do `scene.label_sprites` (ta sama grupa co `EmoteSprite`
i `HealthBar`), warstwa `scene.sprites_layer + 1`, kotwica `midbottom` **nad** głową
postaci - imię jest pod nią, więc nie kolidują.

Twarde reguły, wprost z tego, co już wiadomo o tekście w świecie:

- font `FONT_SIZE_EXTRA_TINY` (8 px) - ten sam co imię. **Nie zwiększać**: napis jest
  skalowany zoomem kamery, więc 10 px czyta się w świecie jak nagłówek.
- **obrys, nie panel** (W1). Ta sama technika co imię: `render_text(..., shadow=...)`.
  Kolor obrysu ma dawać kontrast na trawie **i** na drewnie tawerny - do sprawdzenia
  na zrzutach, nie na oko w kodzie.
- **maksymalnie 2 linie po ~28 znaków**, zawijanie na spacji jak w `HealthBar`. Dłuższy
  tekst to **twardy błąd importu** z `file:line`, a nie ucięcie w runtime - autor ma się
  dowiedzieć przy `just import-dialogs`, nie zobaczyć obcięty żart w grze.
- czas życia ~3,5 s + zanik alfą; przy wielu postaciach obok siebie **maksymalnie 2
  barki naraz na ekranie** - trzeci czeka albo przepada (przepada; bark nie jest
  wiadomością, tylko tłem).
- **cykl życia sprite'a musi iść za `EmoteSprite`.** `routines_director.py:356-378`
  dodaje i usuwa `npc.emote` z `label_sprites` przy zasypianiu i budzeniu. Bark, który
  tego nie robi, zostanie wisieć nad pustym miejscem po NPC, który poszedł spać.

### D6 - emoji jako opcjonalne pole slotu, bez osobnej tabeli

Emoji opisuje **konkretny krok dnia**, więc mieszka w tym kroku - jako opcjonalne pole
`emotes` w slocie `routines.toml`, obok `from`, `at` i `activity`:

```toml
[[routine.townsfolk.slot]]
from     = "08:00"
at       = "type:work"
activity = "stand"
emotes   = ["sweat", "star"]

# Lunch w tawernie

[[routine.townsfolk.slot]]
from     = "13:00"
at       = "type:social"
activity = "wander"
emotes   = ["food", "food_anim", "happy"]

[[routine.townsfolk.slot]]
from     = "20:00"
at       = "type:home"
activity = "sleep"
emotes   = ["zzz", "zzz_anim"]
```

Osobna sekcja `[emotes]` mapująca `activity → emoji` (wariant z rev. 1) była gorsza
z trzech powodów:

- **łatwo o niej zapomnieć** - dopisujesz slot na dole pliku, a tabela jest na górze,
- **`activity` to za gruba miara**. `stand` znaczy „stoi" i tyle: barman za barem, kowal
  przy kowadle i Bart przy straganie mają ten sam `activity`, a to trzy różne obrazki.
  W slocie każdy z nich może dostać swoje,
- **byłaby trzecim rejestrem** obok slotów i `EMOTE_SHEET_DEFINITION`, opisującym coś,
  co i tak jest własnością kroku.

**Brak pola `emotes` = brak emoji**, i to nie jest błąd. Dokładnie ta sama filozofia,
którą `routines.toml` deklaruje dziś w nagłówku o pustej komórce destynacji („taki krok
degraduje się do »zostań gdzie jesteś«, a nie do wyjątku"). Wieś nie musi być cała
oplakatowana emoji, żeby ożyć.

Losowość (W3): co `40-90 s` (jitter z zasianego RNG) postać stojąca na slocie z polem
`emotes` dostaje `set_temporary_emote` z wylosowanym elementem listy. Wariant `_anim`
wpisuje się do listy **wprost**, jako osobny element - dzięki temu autor steruje jego
częstością samą listą (`["food", "food", "food_anim"]` to jeden na trzy), zamiast stałym
progiem 30% zaszytym w kodzie.

Krok `sleep` jest wyjątkiem: `zzz` wisi **stale** przez `set_emote`, bo spanie nie jest
chwilą. Rozpoznanie po `activity == "sleep"`, nie po nazwie emoji.

**Brakujące emoji:** `EMOTE_SHEET_DEFINITION` (`settings.py:1131`) nie ma dziś `food`
ani `sweat`. Autor zapowiedział dorysowanie. Do czasu assetu sloty używają istniejących
(`happy`, `dots`, `star`), a **walidacja przy starcie musi odrzucić nieznaną nazwę**:
`EMOTE_SHEET_DEFINITION` to zwykły słownik, więc literówka `zzz_animm` da albo `KeyError`
w losowym momencie rozgrywki, albo - jeśli ktoś „naprawi" to `get()`-em - postać, która
po prostu nigdy nic nie pokaże. Drugie jest gorsze, bo nie do zauważenia.

### D7 - który quest trafia na HUD

Trzy osobne pytania, które łatwo pomylić: **kto wybiera**, **co się dzieje po
ukończeniu** i **co gdy nie ma czego śledzić**.

Stan to dwa pola na scenie: `tracked_quest_key` oraz `tracked_quest_pinned` (bool).
`pinned=False` znaczy „to jest wynik automatu" - automat może to nadpisać przy każdym
zdarzeniu questowym. `pinned=True` znaczy „gracz tak chce" - i wtedy automat **nie rusza**
wskaźnika, dopóki ten quest żyje.

#### Ręczna zmiana: jeden klawisz w dzienniku (W6)

Klawisz **`T`** (jak *track* / *śledź*) w `QuestPanel`, na zaznaczonym queście.
`pygame.K_t` jest wolny - zero trafień w całym `project/`. Nowy wpis w `ACTIONS`
(`settings.py:660`) obok `quest_log`, z `show: ["key_T"]` i `msg: "action.track_quest"`.

To jest naprawdę **jeden** klawisz, a nie nowy tryb: dziennik ma już zaznaczenie
(`select_prev`/`select_next` przez W/S) i już obsługuje `_edge()`, więc `T` tylko
odczytuje to, co gracz i tak widzi podświetlone.

Zachowanie na zaznaczonym queście:

| Stan questa | Co robi `T` |
| --- | --- |
| odblokowany, nieukończony, nieśledzony | zaczyna być śledzony (`pinned=True`) |
| **aktualnie śledzony** | odpięcie - wskaźnik wraca do trybu automatycznego |
| ukończony albo zablokowany | nic + krótki komunikat, **nie cisza** |

Jeden klawisz robi obie rzeczy (przypnij / odepnij), bo drugi skrót na odpięcie byłby
skrótem, którego nikt nigdy nie użyje.

**Parasol wolno przypiąć ręcznie**, choć automat parasole odrzuca (niżej). Gracz, który
świadomie wybiera nagłówek wątku, wie, czego chce - jawny wybór bije heurystykę.

**Widoczność w dzienniku.** Śledzony quest dostaje znacznik na liście. Bez tego
przypięcie jest niewidoczne w momencie, w którym gracz je wykonuje: dziennik zasłania
statystyki i wskaźnik (`draw_overlay(stats=…)`), więc gracz zobaczyłby efekt dopiero po
zamknięciu panelu. Znacznik na liście zamiast toastu - toast tuż po fanfarze ukończenia
questa to trzeci komunikat w tej samej sekundzie.

#### Kaskada po zamknięciu śledzonego questa (W6)

Uruchamiana **tylko wtedy**, gdy śledzony quest właśnie się zamknął - i tak samo dla
przypiętego, jak dla wybranego automatem. Kolejne kroki, pierwszy trafiony wygrywa:

```
1. kroki z `newly_unlocked` tego samego zdarzenia (z pominięciem parasoli)
   -> pierwszy w kolejności definicji
2. nieukończone rodzeństwo, czyli pozostałe kroki tego samego parasola
   -> pierwszy w kolejności definicji
3. gdy parasol też się właśnie domknął: nieukończone kroki parasola wyżej
4. globalnie: najpóźniej odblokowany nieukończony krok (nie parasol)
5. brak kandydata -> wskaźnik znika, bez pustej ramki
```

Krok 1 to wprost życzenie autora: quest, który coś odblokował, prowadzi gracza do tego,
co odblokował. Kroki 2-4 to szukany fallback, uporządkowany od „najbliżej tego, co gracz
właśnie robił" do „cokolwiek sensownego".

Po kaskadzie `tracked_quest_pinned` wraca do `False`. Nowy wybór jest wyborem automatu,
nie gracza - gdyby pin się przeniósł, gracz miałby przyklejony wskaźnik do questa,
którego nigdy nie wskazał.

**Dlaczego „pierwszy w kolejności definicji", a nie ostatni.** Kolejność w `config.json`
pochodzi z kolejności sekcji w pliku questa w Obsidian, czyli z kolejności, w jakiej autor
to napisał i przeczytał. Jest deterministyczna i **sterowalna treścią** - i to jest
najważniejszy skutek uboczny tej decyzji, do wpisania w ściągę questów:
**kolejność sekcji w pliku questa staje się kolejnością podpowiadaną graczowi.**

**Dlaczego automat odrzuca parasole.** Parasol mówi „przełam klątwę" - to nie jest
instrukcja, tylko tytuł rozdziału. Gracz potrzebuje „idź pogadać z Zielarką". Manualne
przypięcie parasola zostaje możliwe, bo to świadoma decyzja, a nie domyślna.

#### Kiedy to się liczy

**Tylko przy zdarzeniu questowym** (`QuestRuntime.on_event` już zwraca `newly_done`
i `newly_unlocked`) oraz przy wciśnięciu `T` - nigdy co klatkę. Wynik cache'owany.
Reguła liczona co klatkę zacznie migotać między dwoma questami przy pierwszym remisie.

#### Rysowanie i zapis

Jedna linia pod panelem lokacji w `ui/panels/hud.py`, przez `_()`, z tytułem questa
z `messages` (`QuestRuntime._quest_name` już to umie). Wskaźnik **znika razem ze
statystykami**, gdy otwarty jest dziennik albo panel pomocy.

`tracked_quest_key` i `tracked_quest_pinned` idą **do zapisu jako pola opcjonalne
z wartością domyślną** - dokładnie tak, jak E03 wstawiło stan mgły wojny bez podbijania
wersji zapisu. Brak pola w starym zapisie = tryb automatyczny, czyli stan, w którym gra
i tak startuje. `save_compatibility` bez zmian.

**Przy wczytaniu klucz trzeba zweryfikować przeciw `self.defs`**: autor przemianuje albo
skasuje questa i zapis zostanie z kluczem, którego już nie ma. Nieznany klucz = cichy
powrót do automatu, a nie `KeyError` w połowie wczytywania.

Do `debug_ui_state` (A02) dochodzą **dwa** pola: `tracked_quest` i `tracked_quest_pinned`,
żeby scenariusz agentowy odróżnił „automat trafił w to samo" od „pin działa".

### D8 - jeden kształt zamka dla skrzyni i dla drzwi

Nie dwa mechanizmy, tylko jeden w dwóch miejscach:

- `chests.csv` - nowe kolumny `requires_item` (klucz przedmiotu albo puste)
  i `consumes_key` (`true`/`false`),
- obiekt w warstwie `interactions` - te same dwie **własności** w Tiled,
  przekazywane do `Collider` (`objects.py`).

Zachowanie przy braku klucza: **komunikat z nazwą potrzebnego przedmiotu**, dokładnie
jak `notify.weapon_too_weak` przy za słabej broni (`scene/collisions.py`). To już
sprawdzony wzorzec - gracz ma wiedzieć, czego mu brakuje, a nie że „nic się nie stało".

Konsekwencje do domknięcia w tym samym etapie:

- `config_pydantic.py` + **regeneracja `config.py` przez `just gen-web-config`** (G01) -
  bez tego web dostanie skrzynię bez pola i wywali się dopiero w przeglądarce,
- reguła **19** walidatora: `requires_item` musi nazywać klucz z `items.csv`
  (ta sama klasa co reguła 16 z C02),
- nowe klucze locale w `PL.toml` i `EN.toml` + `just validate-locale`,
- `golden_key` i `silver_key` **już istnieją** w `items.csv` (typ `key`, wartość 500)
  i dziś nie robią zupełnie nic - to one dostają pierwszą rolę.

### D9 - `RAT`, nie `HAMSTER`

Sprite nazywa się `HamsterGray`, bo tak nazywa się w oryginalnym asset packu i tego nie
ruszamy (W9). **Klucz encji to osobna przestrzeń nazw** - dokładnie o to chodziło w C02 -
więc postać w `characters.csv` to `RAT` („Szczur"), a `sprite` to `HamsterGray`.
Precedens jest w repo: `POTIONEER_PUZZLEMINT` ma sprite `EggGirl`.

Jeden wariant, więc bez sufiksu koloru (D18/D19 z C02: numer i kolor należą się dopiero
drugiemu wariantowi). Statystyki: **~15 HP**, żeby dało się go ubić `stick`iem (5 dmg) -
piwnica ma być pierwszym kontaktem z walką, zanim gracz ma czym walczyć.

## Etapy

Kolejność jest wymuszona: barki i emoji potrzebują zasianego RNG, wskaźnik questa jest
niezależny, a zamki muszą być **przed** treścią z H03.

### Etap 1 - `ConditionScope.bark` + import sekcji `barks`

Czysta logika, zero pygame, testowalne bez ekranu.

- `settings.py`: stała `DAY_PHASES` (D1); `scene/world_clock.py`: `day_phase(hour)`
  z obsługą zawinięcia przez północ
- `scene/night_filter.py`: trzy komplety literałów 6/9/17/20 czytają `DAY_PHASES` (D1);
  wzory interpolacji bez zmian. Bramka: `just test-unit` + `mypy`; **wygląd sprawdza autor**
- `tests/test_day_phases.py`: `day_phase()` - zawinięcie przez północ, podział doby
  bez dziur i zakładek
- `dialog/conditions.py`: nowy scope, trzy nowe predykaty, uzupełnienie
  `_PREDICATES_BY_SCOPE` i `_VALUE_NAMES_BY_SCOPE`
- `dialog/bark_context.py`: `BarkConditionContext` (wzór: `dialog/context_adapter.py`) -
  most do `world_clock`, do slotu rutyny i do rejestru map
- `dialog/markdown_importer.py`: parsowanie sekcji `## Barki` w plikach postaci
  i **sekcji-pul** w `doc/PL/Barki.md` (nagłówek = klucz puli, D2); walidacja długości (D4)
  i warunków
- `characters.csv`: nowa kolumna `barks` (klucz puli albo puste);
  `config_pydantic.py` + `just gen-web-config`
- `scripts/validate_world.py`: **reguła 20** (D3) - odwołania do encji we wszystkich
  warunkach; **reguła 21** - `barks` nazywa istniejącą pulę (ERROR) i pula bez odbiorcy
  (WARN)
- testy: `tests/test_bark_conditions.py`, `tests/test_bark_import.py`,
  rozszerzenie `tests/test_validate_world_rules.py`

**Bramka:** `just import-dialogs` przechodzi na pustych sekcjach `## Barki`
(zero barków = zero zmian w grze), `just validate-world` na zero błędów.
Reguła 20 puszczona na **dzisiejszej** treści musi wyjść na zero - jeśli coś zapali,
to znalazła zastany cichy `False`, i to jest dobra wiadomość, nie regres.

### Etap 2 - `BarkDirector` + `BarkSprite` (silnik i rysowanie)

- `characters/barks.py`: `BarkDirector` na scenie - promień ~3,5 kafla, cooldown
  per NPC ~60 s + globalny ~8 s, limit 2 naraz, wykluczenie ostatnio użytego
- `objects.py`: `BarkSprite` wzorowany na `HealthBar` (8 px, obrys, 2 linie, zanik)
- `scene/routines_director.py`: bark dołącza do tego samego cyklu życia co `emote`
- wyzwalacz „na zbliżenie" **oraz** wyzwalacz z rutyny (W4)
- layout self-check (A03): przekroczenie 2 linii lub szerokości = twardy błąd

**Bramka:** nowy scenariusz agentowy „Ambient Barks" z asercją stanu przez
`debug_ui_state` (ile barków aktywnych, czyje) - **nie** przez zrzut ekranu; przypominam
notatkę o tym, że headless nie jest wierny dla kompozycji klatki.

### Etap 3 - emoji z rutyn + rozszerzenie reakcji zwierząt

- `config_model/routines.toml`: opcjonalne pole `emotes` w slotach (D6) + walidacja nazw
  przeciw `EMOTE_SHEET_DEFINITION` przy wczytaniu rutyn
- `npc_schedule.py` (model slotu) - nowe pole; `characters/npc.py`: wyzwalanie
  `set_temporary_emote` na zasianym jitterze; `sleep` (po `activity`) jako stan stały
- rozszerzenie istniejącej reakcji zwierząt (`npc_state.py:17`) o więcej sytuacji
  niż sama kolizja
- **fallback** dla `food`/`sweat`, dopóki autor ich nie dorysuje

**Bramka:** `just test-unit` + scenariusz „NPC Routine Emotes" z przewinięciem doby;
ten sam seed musi dawać ten sam ciąg emoji (A04).

### Etap 4 - wskaźnik aktywnego questa na HUD

- `quest/runtime.py`: wyliczenie i cache śledzonego questa, kaskada po zamknięciu (D7)
- `ui/panels/hud.py`: jedna linia pod panelem lokacji, `_()`, znika ze statystykami
- `settings.py`: nowa akcja `track_quest` w `ACTIONS` (`K_t`, `show: ["key_T"]`)
- `ui/game_ui.py`: obsługa `T` w bloku `is_open(QuestPanel)` przez istniejące `_edge()`
- `ui/panels/quest.py`: znacznik śledzonego questa na liście + skrót w stopce panelu
- `ui/panels/help.py`: `T` w referencji skrótów (design system: skróty w stopce)
- `save_load/`: `tracked_quest_key` + `tracked_quest_pinned` jako pola opcjonalne,
  **bez podbicia wersji zapisu**; walidacja klucza przeciw `defs` przy wczytaniu
- `agent_ctrl.py`: `tracked_quest` i `tracked_quest_pinned` w `debug_ui_state`
- locale: nowe klucze w `PL.toml` i `EN.toml` (`action.track_quest`, komunikat odmowy
  dla questa ukończonego lub zablokowanego)
- testy: `tests/test_quest_tracking.py` - czysta logika, bez ekranu: wybór automatu,
  **każdy z pięciu kroków kaskady osobno**, toggle pinu, kasowanie pinu po kaskadzie,
  nieznany klucz z zapisu

**Bramka:** scenariusz agentowy przechodzący `Q00 → Q01_S01` i asertujący, że wskaźnik
przeskoczył **na quest odblokowany przez ten krok** (kaskada 1), drugi scenariusz na
przypięcie klawiszem `T` i przetrwanie pinu przez zapis i wczytanie; ss-review na
zrzucie HUD-u i na dzienniku ze znacznikiem.

### Etap 5 - zamki, klucze i `RAT`

- `chests.csv` + `config_pydantic.py` + `just gen-web-config` (D8)
- `objects.py` (`Collider`) - `requires_item` / `consumes_key` na drzwiach
- `scene/player_actions.py` + `scene/collisions.py` - odmowa z komunikatem
- `scripts/validate_world.py` - **reguła 19**
- `characters.csv` - wiersz `RAT` (D9); sprite `HamsterGray` **wgrywa autor**
- locale + `just validate-locale`

**Bramka:** `just test-smoke` 6/6, `just validate-world` 0 błędów, headless otwarcie
skrzyni z kluczem i bez klucza.

## Kryteria akceptacji

- `just test-unit` w całości zielone; nowe testy dopisane do `tests = [...]` w `main()`
  swoich plików (inaczej `just test-unit` sam to wykryje i zwróci błąd)
- `just validate-world` - 0 błędów, ostrzeżenia tylko znane (9 po C02)
- `just validate-locale` OK, `mypy` czysty
- `just test-smoke` 6/6 + nowe scenariusze („Ambient Barks", „NPC Routine Emotes",
  „Quest Tracker on HUD") przechodzą z `MOM_SKIP_SS_REVIEW=1` **oraz** z ss-review
- **złota zasada dual-target**: `just run` i `just serve-web`; nowe pole configu
  przeszło przez `just gen-web-config`
- ten sam seed = ten sam ciąg barków i emoji (A04); scenariusz uruchomiony dwa razy
  daje identyczne asercje stanu
- pusta sekcja `## Barki` u wszystkich postaci = gra wygląda **dokładnie** jak dziś
  (silnik bez treści niczego nie psuje)
- **wskaźnik questa**: `T` przypina i odpina, przypięcie przeżywa zapis i wczytanie,
  a zapis sprzed H01 (bez tych pól) wczytuje się w tryb automatyczny; po ukończeniu
  śledzonego questa wskaźnik ląduje na queście odblokowanym przez ten krok, a gdy nic
  się nie odblokowało - na rodzeństwie; gdy nie ma czego śledzić, znika bez pustej ramki
- `T` widoczne w stopce dziennika **i** w panelu pomocy (design system)
- **weryfikacja u autora** (headless nie jest wierny): czytelność barka na trawie
  i na podłodze tawerny, czy 3,5 s to dobry czas, czy cooldown 60 s nie jest za długi,
  czy emoji nie robią się szumem przy 30 NPC

## Pułapki

- **Nie rysuj barka w warstwie UI.** Imię postaci jest w świecie (`label_sprites`,
  8 px, skalowane zoomem) i bark ma być obok niego, w tej samej przestrzeni. Bark w UI
  odjedzie od postaci przy pierwszym ruchu kamery.
- **Nie zwiększaj fontu barka do minimum UI (10 px).** Komentarz w `objects.py:228-231`
  wprost tłumaczy, dlaczego imię ma 8 px - to ta sama reguła i ten sam powód.
- **`_particle_rng()`, nie `random`.** A04 istnieje po to, żeby scenariusze były
  powtarzalne; goły `random` w barkach unieważni każdą asercję agentową.
- **Sprite barka musi wypisać się z grupy razem z NPC.** `routines_director.py:376-378`
  usuwa `emote` i `health_bar` przy zaśnięciu - bark bez tej samej obsługi zostanie
  wisieć nad pustym polem.
- **Nie zostawiaj drugiego kompletu godzin 6/9/17/20.** `night_filter.py` ma je dziś
  w trzech miejscach literałami i wszystkie trzy mają czytać `DAY_PHASES` (D1) -
  dodanie stałej **bez** tego refactoru pogarsza stan, bo robi czwarty komplet.
- **W `night_filter.py` ruszamy tylko źródło liczb.** Wzory interpolacji i optymalizacje
  z E01 zostają; przy tych samych granicach obraz ma być identyczny co do piksela.
- **`night` zawija się przez północ.** Naiwne `start <= h < end` da dla 02:00 pustkę,
  a bark nocny nigdy nie zapali - i nikt tego nie zauważy, bo o 02:00 rzadko kto gra.
- **Nowe pole configu = `just gen-web-config`.** `config.py` jest generowany
  z `config_pydantic.py` (G01) - ręczna edycja albo pominięcie regeneracji da błąd
  wyłącznie na web, czyli najpóźniej jak się da.
- **Nazwa emoji z literówką nie może być cicha.** `EMOTE_SHEET_DEFINITION` to słownik;
  `zzz_animm` da `KeyError` w losowym momencie rozgrywki albo, gorzej, zostanie obsłużone
  `get()`-em i postać po prostu nigdy nic nie pokaże. Walidacja przy imporcie.
- **`quest_done` jako nośnik faktu świata to sprzężenie** (D3). Skasowanie albo
  przemianowanie `Q01_S01_LEARN_ABOUT_CURSE` wyłączy reakcje wsi na klątwę - dlatego
  bramką jest **reguła 20 walidatora**, a nie akapit w `AGENTS.md`.
- **Cichy `False` to najgorszy tryb awarii treści.** Literówka w kluczu wewnątrz
  `visited()` / `quest_done()` / `has_item()` nie wywala niczego - po prostu warunek
  nigdy nie zapala, a opcja dialogowa nigdy się nie pokazuje. Tak zniknął kiedyś cały
  dialog Miecza. Reguła 20 istnieje dokładnie po to.
- **Klucz encji ≠ nazwa sprite'a** (C02). `RAT` ma sprite `HamsterGray` i to jest
  poprawne, a nie niekonsekwencja do posprzątania.
- **Skrzynia jest kluczowana nazwą obiektu Tiled w zapisie** (C02/O1). Dodanie zamka
  nie zmienia nazwy, więc stare zapisy przeżyją - ale zmiana nazwy skrzyni przy okazji
  **skasuje jej stan**.
- **Klucz questa w zapisie może już nie istnieć.** Autor przemianuje sekcję w Obsidian
  i `tracked_quest_key` ze starego zapisu wskazuje na nic. Walidacja przy wczytaniu,
  cichy powrót do automatu - nie `KeyError` w połowie ładowania.
- **Pin nie może przeżyć kaskady.** Po zamknięciu przypiętego questa nowy wybór jest
  wyborem automatu (`pinned=False`); przeniesienie pinu przykleiłoby wskaźnik do questa,
  którego gracz nigdy nie wskazał, i gracz nie miałby jak tego cofnąć poza dziennikiem.
- **Wskaźnik liczony co klatkę będzie migotać.** Liczy się wyłącznie przy zdarzeniu
  questowym i przy `T`; reszta czasu to odczyt cache'u.
- **Przypięcie w dzienniku jest niewidoczne bez znacznika na liście.** Dziennik zasłania
  statystyki i wskaźnik, więc bez znacznika gracz naciska `T` i nie widzi żadnej reakcji.

## Po zakończeniu

- wpis w `project/AGENTS.md`: sekcja „Barki" (format autorski, klucz puli, scope
  warunków, cykl życia sprite'a) + dopisek o sprzężeniu z D3 **z zaznaczeniem, że
  pilnuje go reguła 20 walidatora, a nie ten akapit**
- aktualizacja `doc/quest-cheatsheet.md` o wskaźnik na HUD (generowana:
  `just quest-cheatsheet`), z **jawnym ostrzeżeniem dla autora**: kolejność sekcji
  w pliku questa jest kolejnością, w której gra podpowie graczowi kolejny krok (D7)
- nowa ściąga dla autora w `doc/` albo rozszerzenie istniejącej: „jak napisać barka"
  (`just gen-dialog-docs` jeśli generowane)
- odhaczenie H01 w [audyt.md](audyt.md) i odblokowanie [H03](H03-sidequesty-i-klatwa.md)
