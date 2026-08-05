# CodeGraph - wpływ na pracę Claude Code (2026-07-21 .. 2026-08-05)

Pomiar kontrolny do [[codegraph-benchmark-baseline-2026-07-20]]. CodeGraph zainstalowany **2026-07-21** (brew, `/opt/homebrew/bin/codegraph`; katalog `.codegraph/` utworzony 07-21 06:53). Okres obserwacji: 16 dni, do 2026-08-05.

Materiał: wszystkie transkrypty `.jsonl` sesji CC dla tego repo - **28 sesji przed** (07-06 .. 07-20, 74 MB) i **28 sesji po** (07-21 .. 08-05, 55 MB).

## Uwaga metodologiczna - liczby "przed" różnią się od dokumentu bazowego

Baseline liczył 12 największych sesji i klasyfikował komendę po jej pierwszym słowie (stąd 16% w koszu "pozostałe"). Tu użyłem jednego klasyfikatora dla obu okresów: komenda jest rozbijana na segmenty operatorami powłoki **z poszanowaniem cudzysłowów** (`shlex` z `punctuation_chars`), zdejmowane są prefiksy env/`rtk`/`gtimeout`, a kategoria przydzielana priorytetowo. Efekt: `grep` w potoku łapie się jako wyszukiwanie, więc udział wyszukiwań "przed" wychodzi 58,0% zamiast opublikowanych 37%.

**Nie jest to korekta baseline'u, tylko inna reguła.** Obie kolumny poniżej są liczone tą samą regułą, więc porównanie przed/po jest uczciwe; porównanie z tabelą w dokumencie bazowym - nie.

Pomiar jest odtwarzalny: `just codegraph-impact` (skrypt `scripts/codegraph_impact.py`). Liczby w tym dokumencie to zrzut z 2026-08-05.

## Wniosek w jednym zdaniu

CodeGraph działa technicznie i tam, gdzie jest faktycznie użyty, wyraźnie skraca nawigację - ale jest wołany w mniej niż połowie sesji, a użycie wygasa, więc zagregowany efekt na całym okresie jest niewielki.

## 1. Adopcja - to jest główne ustalenie

| Miara | Wartość |
|---|---:|
| Wywołania `codegraph_explore` (MCP) | 27 |
| Wywołania `codegraph explore` (shell) | 6 |
| **Razem realnych zapytań** | **33** |
| Sesje z co najmniej jednym zapytaniem | 12 / 28 (43%) |
| Wywołania shell zużyte na `--help` / `status` / `files` | 11 |

Rozkład w czasie:

| Okno | Sesji | Zapytań CG | Zapytań / sesję |
|---|---:|---:|---:|
| 07-21 .. 07-25 (pierwszy tydzień) | 15 | 25 | 1,7 |
| 07-26 .. 08-05 (kolejne 11 dni) | 13 | 8 | 0,6 |

Te późniejsze 8 zapytań pochodzi z trzech sesji: 07-28 (1), 08-01 13:06 (2) i 08-01 14:50 (5). Poza 07-28 i 08-01 CodeGraph nie pojawia się ani razu - w tym w żadnej sesji od 08-02 do dziś. Reguła "MANDATORY: przed grepem użyj codegraph" w globalnym `CLAUDE.md` nie jest w praktyce egzekwowana.

Do tego 11 wywołań shellowych z 07-24 i 07-25 to nie praca, tylko dłubanie w narzędziu (szukanie sposobu na wykluczenie `utils/zengl_examples` z indeksu). To koszt wdrożenia, nie zysk.

## 2. Profil nawigacji - cały okres przed vs po

Kategorie komend `Bash`:

| Kategoria | Przed | Udział | Po | Udział |
|---|---:|---:|---:|---:|
| wyszukiwanie (`rg`/`grep`) | 1057 | 58,0% | 1152 | 44,8% |
| uruchamianie (`python`/`pytest`/`just`) | 194 | 10,6% | 569 | 22,1% |
| `cd` | 288 | 15,8% | 86 | 3,3% |
| czytanie (`cat`/`sed`/`head`/`jq`) | 68 | 3,7% | 367 | 14,3% |
| `git` | 75 | 4,1% | 155 | 6,0% |
| `ls`/`tree`/`wc` | 34 | 1,9% | 78 | 3,0% |
| `find`/`fd` | 13 | 0,7% | 21 | 0,8% |
| `codegraph` | 0 | 0% | 18 | 0,7% |
| pozostałe | 94 | 5,2% | 123 | 4,8% |
| **Razem** | **1823** | | **2569** | |

Spadek udziału wyszukiwań z 58,0% do 44,8% wygląda dobrze, ale **mianownik się zmienił**: udział uruchomień skoczył z 10,6% do 22,1%, bo praca po 07-21 to w dużej mierze profiler E02, audio, prototyp mgły wojny i testy web - roboty runtime'owej, nie nawigacyjnej. Sam udział procentowy jest tu więc słabym dowodem.

Metryki znormalizowane liczbą edycji (`Edit` + `Write`), odporne na zmianę wielkości i typu sesji:

| Metryka | Przed | Po | Zmiana |
|---|---:|---:|---:|
| wyszukiwań na edycję | 0,94 | 0,93 | -1% |
| `Read` na edycję | 0,80 | 0,48 | **-40%** |
| akcje nawigacyjne na edycję | 1,81 | 1,72 | -5% |
| wywołań narzędzi na turę asystenta | 0,50 | 0,62 | +24% |

Czyli: **liczba grepów nie spadła praktycznie wcale**, spadło za to czytanie plików. Deklarowane przez autorów narzędzia "~58% mniej wywołań na zapytanie" nie zmaterializowało się - wywołań na turę jest więcej, nie mniej.

## 3. Sesje z CodeGraphem vs bez, w tym samym okresie

To jest najmocniejszy dowód, bo kontroluje wersję modelu, harness i epokę projektu.

| Grupa | n | wysz./edycję | `Read`/edycję | nawig./edycję |
|---|---:|---:|---:|---:|
| Po - sesje **używające** CG | 12 | 0,78 | 0,43 | 1,48 |
| Po - sesje **bez** CG | 16 | 1,18 | 0,58 | 2,14 |

Różnica jest duża (-33% nawigacji na edycję), ale częściowo pozorna: sesje z CG są średnio większe (2,7 MB vs 1,4 MB), a większe sesje z natury mają lepszy stosunek nawigacji do edycji. Widać to w okresie **przed** instalacją, gdzie CG nie mógł mieć wpływu:

| Grupa (okres przed) | n | nawig./edycję |
|---|---:|---:|
| sesje >= 1,7 MB | 15 | 1,73 |
| sesje < 1,7 MB | 13 | 2,38 |

Po kontroli rozmiaru (tylko sesje >= 1,7 MB) różnica maleje, ale nie znika:

| Grupa (>= 1,7 MB) | n | wysz./edycję | `Read`/edycję | nawig./edycję |
|---|---:|---:|---:|---:|
| Po, z CG | 9 | 0,73 | 0,37 | **1,35** |
| Po, bez CG | 6 | 1,04 | 0,48 | 1,89 |
| Przed (odniesienie) | 15 | 0,88 | 0,77 | 1,73 |

Odczyt: duże sesje **bez** CodeGrapha (1,89) wyglądają jak epoka sprzed instalacji (1,73). Duże sesje **z** CodeGraphem schodzą do 1,35, czyli o ~22% niżej niż baseline. Przy n=9 vs n=6 to sygnał, nie dowód, ale spójny kierunkowo we wszystkich trzech kolumnach.

## 4. Gubienie wątku - jedyna metryka z jednoznaczną poprawą

Baseline wskazywał jako główny sygnał marnowania tokenów wielokrotne szukanie tego samego symbolu. Policzone tylko z **wzorca wyszukiwania** (nie ze ścieżek ani flag), na sesjach z co najmniej 10 wyszukiwaniami:

| Metryka | Przed | Po | Zmiana |
|---|---:|---:|---:|
| sesje szukające >= 3x tego samego symbolu | 21/22 (95%) | 26/27 (96%) | +1 p.p. |
| **średnia maksymalna krotność powtórzenia** | **19,3x** | **8,0x** | **-59%** |
| nadmiarowe powtórzenia na wzorzec | 1,89 | 0,57 | **-70%** |
| sesje czytające >= 3x ten sam plik | 19/22 (86%) | 22/27 (81%) | -5 p.p. |

Sam fakt powtórki występuje niemal zawsze (to naturalne w długiej sesji), ale **skala patologii spadła trzykrotnie**. Przedtem zdarzało się szukać jednego symbolu ~19 razy w sesji; teraz najgorszy przypadek to średnio ~8, a nadmiarowych powtórzeń na wzorzec jest 3,3x mniej. To najbardziej wiarygodny efekt w całym pomiarze, chociaż część zasługi może przypadać zmianie modelu i harnessa, nie samemu CodeGraphowi.

Najczęściej re-czytane pliki po instalacji (>= 3x `Read` tego samego pliku): `project/scene.py` (59x łącznie), `project/scene/scene.py` (29x), `project/characters.py` (25x), `tests/automate_display_test.py` (24x), `project/game.py` (24x). To dokładnie te pliki, których `codegraph_explore` powinno oszczędzić czytanie.

## 5. Koszt kontekstu

| Metryka | Przed | Po |
|---|---:|---:|
| tokeny wejściowe z cache, na turę asystenta | 210k | 194k |
| tokeny wyjściowe na turę | 1057 | 879 |

Różnica ~6% - w granicach szumu, bez wpływu na budżet. CodeGraph nie zwrócił się na poziomie tokenów.

## 6. Stan techniczny indeksu

| Parametr | Wartość |
|---|---|
| Plików w indeksie | 197 |
| Węzłów / krawędzi | 9 015 / 36 253 |
| Rozmiar bazy | 39,45 MB (+ 6,1 MB WAL) |
| Backend | `node:sqlite`, journal WAL |
| Auto-sync | 45-150 ms na 2 pliki, stabilnie |

Indeks pokrywa 197 z 355 plików `.py` w repo, ale różnica to głównie **celowo wykluczone** `utils/zengl_examples` (103 pliki obcego kodu przykładowego). Rdzeń (`project/`, `tests/`, `scripts/`, `main.py`) jest zaindeksowany. Demon `codegraph serve --mcp` startuje razem z sesją CC i działa poprawnie; auto-sync nadąża za zapisami.

Technicznie **nie ma się do czego przyczepić** - narzędzie nie jest wąskim gardłem. Wąskim gardłem jest to, że nikt go nie woła.

## 7. Podsumowanie tabeli z baseline'u

| Metryka | Baseline (reguła własna) | Po CodeGraph | Werdykt |
|---|---:|---:|---|
| Udział wyszukiwań w komendach Bash | 58,0% | 44,8% | pozorny - zmienił się typ pracy |
| Wyszukiwań na edycję | 0,94 | 0,93 | **bez zmiany** |
| `Read` na edycję | 0,80 | 0,48 | **poprawa -40%** |
| Nawigacja na edycję | 1,81 | 1,72 | marginalna |
| Nawigacja na edycję (duże sesje z CG) | 1,73 | 1,35 | **poprawa -22%** |
| Maks. krotność powtórki symbolu | 19,3x | 8,0x | **poprawa -59%** |
| Wywołań narzędzi na turę | 0,50 | 0,62 | pogorszenie |

## 8. Co z tym zrobić

Trzy opcje, w kolejności rekomendacji:

1. **Wymusić użycie zamiast zalecać - ZROBIONE 2026-08-05.** Reguła w `CLAUDE.md` była ignorowana w 57% sesji. Zamiast niej działa teraz hook `PreToolUse` na `Bash` (`scripts/hook_codegraph_reminder.py`, podpięty w `.claude/settings.json`). Przy pierwszym w sesji grepie po symbolu Pythona wstrzykuje jedno zdanie kontekstu z podpowiedzią o `codegraph_explore`. Świadomie **nie blokuje** - grep jest właściwym narzędziem do stringów, CSV i logów, więc blokada kosztowałaby więcej, niż daje. Hook milczy, gdy wzorzec to zwykłe słowo, gdy szukanie jest zawężone do `.md`/`.json`/`.csv`, albo gdy w repo nie ma indeksu `.codegraph/`. Kolejny pomiar (za ~miesiąc, `just codegraph-impact`) powie, czy przypomnienie wystarczy, czy trzeba wariantu blokującego.
2. **Zawęzić obietnicę.** Zapytania, które faktycznie padły, były trafne (`Scene.__init__ / go_to_map / loaded_maps`, `save_load / MapState / maze_seed`, `apply_time_of_day_filter`) - to pytania architektoniczne przez wiele plików. Do nich CodeGraph się nadaje. Do "gdzie jest ten string" nie i nie ma sensu udawać, że tak. Można to spisać w `AGENTS.md` jako regułę "kiedy CG, kiedy rg".
3. **Zaakceptować status quo.** Koszt utrzymania jest niski (demon, 40 MB w `.codegraph/`, gitignorowane), a w dużych sesjach refactorowych narzędzie realnie pomaga. Nic nie trzeba zmieniać, ale wtedy nie należy oczekiwać efektu w zagregowanych statystykach.

Czego pomiar **nie** rozstrzyga: czy poprawa jakości odpowiedzi (trafność, mniej ślepych uliczek) wystąpiła. Transkrypty nie mają metryki poprawności, a liczba edycji rosła również z powodu większej ilości pracy implementacyjnej w tym okresie.

## Zastrzeżenia

- Okres "po" pokrywa się ze zmianą modelu i harnessa (m.in. `cd` spadło z 13,3% do 2,7% - to zmiana harnessa, nie CodeGrapha). Rozdzielenie tych efektów od wpływu CodeGrapha jest niemożliwe z samych transkryptów; stąd nacisk na porównanie wewnątrz okresu "po".
- Typ pracy przesunął się z nawigacji po kodzie w stronę runtime'u (profiler, audio, prototypy wizualne), co samo z siebie obniża udział grepów.
- Grupy w porównaniu wewnątrzokresowym są małe (9 vs 6 sesji po kontroli rozmiaru).
- **Korpus transkryptów nie jest stabilny.** W trakcie samej analizy liczba plików `.jsonl` spadła z 63 do 61 - Claude Code rotuje i usuwa stare sesje. Powtórzenie pomiaru za miesiąc da lekko inne liczby bezwzględne dla okresu "przed", bo część materiału źródłowego zniknie. Wskaźniki znormalizowane (`nav/edycję`) są na to odporne, liczby bezwzględne nie.
- Okres "po" zawiera **tę sesję analityczną**, która sama jest pełna grepów i uruchomień Pythona po transkryptach. To ~0,2 MB z 55 MB, więc wpływ jest pomijalny, ale przy kolejnych pomiarach warto o tym pamiętać.
- Skrypt pomiarowy: `scripts/codegraph_impact.py` (`just codegraph-impact`). Flagi: `--cutoff` (data cezury), `--min-size` (kontrola rozmiaru sesji), `--per-session`, `--queries`. Zmiana kolejności priorytetów w `classify()` unieważnia wszystkie procenty w tym dokumencie.
- **Pierwsza wersja pomiaru miała błąd parsera**, znaleziony przy budowie hooka: komenda była dzielona po `|` przed parsowaniem cudzysłowów, więc wzorce z alternatywą (`rg "def load_map|def load_NPCs"`) były rozcinane w środku i traciły część symboli. Liczby w tym dokumencie pochodzą z wersji poprawionej (`scripts/shell_parse.py`, `shlex` z `punctuation_chars`). Błąd dotyczył obu okresów jednakowo, więc kierunek wniosków się nie zmienił, ale metryka powtórek była zaniżona - po poprawce spadek nadmiarowych powtórzeń wychodzi -70%, nie -29%.
