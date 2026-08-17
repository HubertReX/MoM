# H03 - sidequesty Aktu 1 i samospełniająca się przepowiednia

Priorytet: **P3** (Faza 4)
Rozmiar: **L**
Zależność: **twarda** - [H01](H01-barki-emoji-wskaznik-questa.md) musi być zrobione (barki, zamki, klucze, model `RAT`)

**Status**: rev. 1 - szkic scenariusza do akceptacji autora. To była pierwsze **połowa - treściowa**: siedem sidequestów, rozbudowa wątku klątwy i teksty barków. Wszystko poniżej to **propozycja do przepisania ręką autora w Obsidian** - dialogi, żarty i imiona są jego domeną, a ten plik ma dać strukturę, haczyki i punkty zaczepienia w istniejących mechanikach, nie gotowy tekst do wklejenia.

Zadanie realizuje **G-3** (świat reaguje na sentyment), **G-4** (noc i rutyny dają coś gameplayowi) oraz „_regrywalność w tonie gry_" z [audytu](audyt.md).

## Decyzje autora (wiążące, ustalone 2026-08-10)

- **W1** - klątwa **nie karze mechanicznie**. Sentyment i ceny się nie zmieniają, bowieść się rozeszła. Zmienia się **wyłącznie to, co postacie mówią**.
- **W2** - plotka rozchodzi się przez **dialogi, nie przez symulację**. Po przejściu którejkolwiek linii, w której [[Malachiasz|Malachi]] przyznaje się do klątwy, u innych postaci pojawiają się nowe opcje, część domyślnych znika, a powitanie dostaje nutkę - uszczypliwości, pogardy albo współczucia, zależnie od charakteru postaci.
- **W3** - raz subtelnie, raz wprost. Monotonia jest gorsza niż brak reakcji.
- **W4** - [[Malachiasz|Malachi]] **stopniowo sam zaczyna wierzyć**. Bez wyboru dla gracza: proza dryfuje sama, od śmiechu przez tłumaczenie się do tego, że przestaje dotykać klamek.
- **W5** - sidequesty mają być **różnorodne**: każdy inny w charakterze. Rutynowe questy klepane na jedno kopyto, bez haczyka i bez osadzenia w świecie, są najgorszą rzeczą, jaka może się tu wydarzyć.
- **W6** - wszystkie siedem pomysłów wchodzi: **3 od Barmana, 2 od Kowala, 2 od Zielarki**. Niski koszt, a zawsze można wyciąć.
- **W7** - piwnica to **nowa mała mapa** (nie `VillageHouse.tmx`), z gryzoniami jako pierwszym, łatwym przeciwnikiem niewymagającym mocnej broni.
- **W8** - zwierzęta dostają onomatopeje, a [[Miecz Ciętej-riposty]] je komentuje.

### Uwagi autora do unikania na przyszłość

- **Quest bez twistu, smaczku i żartu jest słaby** - nawet jeśli mechanicznie działa. Odrzucony wariant „_zioła z krzaków_" upadł właśnie na tym.
- **Nie planuj mechanik, których nie ma.** Nie istnieje zbieranie przedmiotów zależne od pory dnia; nie ma łowienia ryb. Quest oparty na takiej mechanice to nie quest, tylko ukryte zadanie silnikowe.

## Zasada przewodnia: wieś uwiarygadnia klątwę

To jest **oś tonalna całego zadania** i sprawdzian dla każdej dopisanej linijki.

[[Malachiasz|Malachi]] wraca z [[Tawerna Brakująca klepka|tawerny]] przeklęty przez czarodziejów - to fakt. Ale wszystko, co się dzieje potem, wieś **sama uwiarygadnia klątwę**: [[Barman Absyntnent]] opowiada, [[Zielarka Zmora]] potwierdza, [[Kowal Kłamca]] nie zaprzecza, a [[Malachiasz|Malachi]] po pewnym czasie sam zaczyna się z tego tłumaczyć. _Beczka, obok której stał bohater, była tylko beczką, dopóki nikt nie wiedział o klątwie_. Teraz jest dowodem. To jest **samospełniająca się prorocznia**.

Ten sam mechanizm dostaje **jawną, komediową klamrę** w queście o trofeum ([[#Q04_S02 - Trofeum z dalekiego świata]]): gracz na własne oczy widzi, jak [[Barman Absyntnent|Barman]] wymyśla legendę o sobie i jak wieś w nią wchodzi w kilka dni. [[Miecz Ciętej-riposty|Miecz]] ma to nazwać wprost - raz, ale tylko raz, bo dwa razy to już morał.

## Dryf Malachiego (W4) - trzy fazy, zero nowej maszynerii

Fazę wyznacza stan questów głównego wątku - dokładnie tak, jak ustala [H01/D3](H01-barki-emoji-wskaznik-questa.md). Nic nowego w zapisie, nic nowego w configu.

| Faza             | Warunek                                                       | Jak brzmi Malachi                  | Przykład                                                     |
| ---------------- | ------------------------------------------------------------- | ---------------------------------- | ------------------------------------------------------------ |
| 0 - lekceważy    | `not quest_done("Q01_S01_LEARN_ABOUT_CURSE")`                 | żartuje, bagatelizuje              | „_Klątwa? Dajcie spokój, po prostu mam słabszy dzień._"      |
| 1 - tłumaczy się | `quest_done("Q01_S01_...")` i `not quest_done("Q03_S00_...")` | przyznaje, ale z zastrzeżeniem     | „_Tak, klątwa. Ale to byli wyjątkowo złośliwi czarodzieje._" |
| 2 - uwierzył     | `quest_done("Q03_S00_LEARN_ABOUT_CURSE")`                     | uprzedza innych, zanim go poproszą | „_Może lepiej żebym tego nie dotykał. Sam to weź._"          |

Reguły pisania faz:

- **Faza 2 nie jest smutna, tylko praktyczna.** [[Malachiasz|Malachi]] nie użala się - on organizuje życie wokół klątwy, jak człowiek, który przestał kłócić się z pogodą.
- **Faza 2** zostaje w mocy **także w sidequestach**: w tej fazie [[Malachiasz|Malachi]] sam z siebie ostrzega [[Kowal Kłamca|Kowala]] przed dotknięciem zbroi. [[Kowal Kłamca|Kowal]] i tak nalega.
- [[Miecz Ciętej-riposty|Miecz]] **ma to zauważyć raz**, mniej więcej w połowie **fazy 2**, i nie wracać do tematu.

## Powitania (W2, W3) - kto jak reaguje

Każda postać reaguje **zgodnie ze swoim charakterem z `doc/PL/Postacie/`**, nie według jednego szablonu. Powitanie to pierwszy węzeł dialogu, więc technicznie jest to warunek na węźle startowym - dokładnie ten wzór, który działa dziś u [[Zielarka Zmora|Zielarka]] (węzeł [[Zielarka Zmora#016|016]] jako bramka).

| Postać                              | Charakter                       | Ton po plotce                                          | Szkic pierwszej linii                                                                                                   |
| ----------------------------------- | ------------------------------- | ------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| [[Barman Absyntnent]]               | żartobliwy, rozmowny, zabobonny | teatralna troska, ale interes ważniejszy               | „_O, jest i on! Siadaj. Ale nie tam. Tam, dalej. Przy ścianie nośnej._"                                                 |
| [[Kowal Kłamca]]                    | mruk, opryskliwy, gardzi wsią   | udaje, że go to nie obchodzi, czyli obchodzi go bardzo | „_Wiem. Wszyscy wiedzą. Nie dotykaj niczego na tej półce._"                                                             |
| [[Zielarka Zmora]]                  | zabobonna, nieufna, cwana       | zawodowe zainteresowanie okazem                        | „_Wejdź. Powoli... Chcę zobaczyć, jak się porusza się 7 nieszczęść._"                                                   |
| [[Bart]] / [[Johny]] (straganiarze) | statyści                        | plotka z drugiej ręki, przekręcona                     | „_Podobno ten nowy zamienia złoto w gówno._", "_Spotkać Cię to gorzej niż zbić lustro_", "_Można się **tym** zarazić?_" |
| [[Marysia]]                         | statystka                       | szczere współczucie, niezręczne                        | „_Modliłam się za pana. Trochę. Miałam pranie do zrobienia._", "_Oby to nie było dziedziczne_"                          |
| [[Miecz Ciętej-riposty]]            | złośliwy komentator             | jedyny, kto nie wierzy - i to on ma rację              | „_Zauważyłeś, że przestałeś dotykać klamek? Ja zauważyłem._"                                                            |

Zasada z **W3** w praktyce: **na trzy reakcje jedna ma być bezpośrednia, dwie subtelne.** Subtelna reakcja to taka, w której o klątwie nie pada ani słowo, a i tak wiadomo - [[Kowal]] odsuwający kubek, [[Barman]] zmieniający ==Malachiemu== stolik.

## Siedem sidequestów

Trzy łańcuchy, po jednym na postać, każdy jako parasol `all_subquests` z krokami. Parasol domyka się sam, gdy zamkną się wszystkie kroki, i daje nagrodę „_za relację_" (sentyment).

Kroki są **kolejnością zaufania**: pierwszy dostajesz od ręki, ostatni dopiero, gdy postać cię zna. Bramka to `Requires:` na poprzednim kroku, a nie sentyment - sentyment ma wpływać na **ton**, nie na dostępność, żeby żaden gracz nie utknął.

| Klucz                                             | Postać       | Haczyk (hook)                               | Mechanika                      |
| ------------------------------------------------- | ------------ | ------------------------------------------- | ------------------------------ |
| [[#Q04_S01 - Ryby, które zjadł kot]]              | [[Barman]]   | kot zjadł zapas ryb                         | krzak + skrzynia + przekazanie |
| [[#Q04_S02 - Trofeum z dalekiego świata]]         | [[Barman]]   | chce uchodzić za bywałego                   | klejnot + przekazanie          |
| [[#Q04_S03 - Piwnica, do której się nie schodzi]] | [[Barman]]   | rodzinna tajemnica, taboo                   | klucz + drzwi + walka          |
| [[#Q05_S01 - Ruda spod głazu]]                    | [[Kowal]]    | posłaniec z rudą przepadł                   | pożyczony topór + głaz         |
| [[#Q05_S02 - Dotknij tej zbroi]]                  | [[Kowal]]    | ostateczny test pechowca                    | dialog + plotka                |
| [[#Q06_S01 - Rupiecie Mariolki]]                  | [[Zielarka]] | zamknięta skrzynka po tajemniczej uczennicy | klucz + skrzynia               |
| [[#Q06_S02 - Pierwsze testy na ludziach]]         | [[Zielarka]] | kury zdechły od mikstury, pora na pechowca  | dialog + zdrowie               |

---

### Q04 - „Sprawy najwyższej wagi" 

**Postać:** [[Barman Absyntnent]]

Tytuł parasola jest ironiczny bo ta cała wioska to jeden wielki żart: dla [[Barman Absyntnent|Barmana]] sprawy wsi mają rangę
polityki międzynarodowej. 

**Nagroda parasola:** `max_items=+1` ([[Barman]] załatwia bohaterowi lepszy plecak „_od znajomego, nie pytaj_").

#### Q04_S01 - Ryby, które zjadł kot

**KEY:**  `Q04_S01_CATS_FISH`

**Haczyk:** Kot zjadł zapas ryb. Dla [[Barman Absyntnent|Barmana]] to nie jest problem gastronomiczny, tylko początek wojny domowej!

**Mechanika:** kot ma skrytkę za krzakiem; krzak trzeba rozwalić (`DESTRUCTIBLE_MIN_DAMAGE>10`), skrytka to mała skrzynia z kilkoma rybami (item `fish`), oddanie przez `items_returned` w dialogu.

**Twist:** Ryby są nadgryzione, a kot patrzy na [[Malachiasz|Malachiego]] przez cały czas z jednego miejsca. [[Barman]] ogłasza, że kot jest opętany. Kot nie zaprzecza, czyli taka musi być prawda.

```yaml
Barman: "Sprawa jest poważna. Kot zjadł zapas ryb. Bez ryb nie ma zakąski. Bez zakąski chłopi piją na czczo. A chłopi pijący na czczo, młodzieńcze, to początek każdej wojny domowej w tej okolicy!"
Miecz: "Ile tych wojen tu było?"
Barman: "Za mojej kandencji ani jednej! I wiesz dlaczego? Bo zawsze były ryby."
```

**Nagroda:** `money=40`, `sentiment=+10 @BARMAN_ABSINTHRAYNER`
**Test:** `item_count("fish") >= 5` po oddaniu, albo `visited("BARMAN_ABSINTHRAYNER", "<węzeł oddania>")`

**Do rozstrzygnięcia:** czy ryby dają się też kupić (wtedy quest ma drugą drogę i handel ma dodatkowy sens), czy tylko skrytka kota.

#### Q04_S02 - Trofeum z dalekiego świata

**KEY:** `Q04_S02_TAVERN_TROPHY`

**Haczyk:** [[Barman]] chce uchodzić za bywałego w świecie - to jego konflikt wewnętrzny wprost z `doc/PL/Postacie/Barman Absyntnent.md`. Prosi o „_coś egzotycznego_" do powieszenia nad barem.

**Mechanika:** dowolny klejnot z labiryntu albo z piwnicy, oddany w dialogu.

**Twist i klamra całego zadania:** [[Barman Absyntnent|Barman]] na oczach gracza wymyśla legendę o tym przedmiocie, a przez kolejne dni **inne postaci powtarzają ją (barki) coraz bardziej przekręconą**. To ten sam mechanizm, który produkuje klątwę [[Malachiasz|Malachiego]], tylko widziany z zewnątrz i śmieszny.

```yaml
Barman: (do chłopów) "...i wtedy ten smok strzegący klejnotu mówi do mnie: TY? Znowu TY?"
Miecz: "On nie był nawet w sąsiedniej wiosce."
Malachi: "Wiem."
Miecz: "A oni uwierzą we wszystko co mówi."
Malachi: "Wiem."
Miecz: "..."
Miecz: "Jakbym już gdzieś widział ten schemat..."
```

Barki po tym queście (przykłady do dopisania w `doc/PL/Barki.md`):

- dzień 1, [[Bart]]: „_Podobno w karczmie jest smoczy kamień._"
- dzień 2, [[Marysia]]: „_Ten kamień jest od smoka, który bał się Barmana._"
- dzień 3, [[Johny]]: „_Gdyby nie nasz Barman spłonęły by trzy wsie. I nasza Tawerna._"

**Nagroda:** `money=80`, `sentiment=+15 @BARMAN_ABSINTHRAYNER`
**Requires:** `Q04_S01_CATS_FISH` ([[#Q04_S01 - Ryby, które zjadł kot]])

#### Q04_S03 - Piwnica, do której się nie schodzi

**KEY:** `Q04_S03_TAVERN_CELLAR`

**Haczyk:** Pod [[Tawerna Brakująca klepka|Tawerną]] jest piwnica. [[Barman]] tam nie schodzi, ojciec nie schodził, dziadek zszedł raz i przez dwa lata nie pił. Klucz jest gdzieś, ale nikt nie wie gdzie.

**Mechanika:** srebrny klucz (`silver_key`) → zamknięte drzwi (`requires_item`) → **nowa mała mapa piwnicy** → `RAT` (sprite `HamsterGray`, ~15 HP) do ubicia kijem (item `stick`). To pierwszy kontakt gracza z walką, celowo na przeciwniku, który nie wymaga dobrej broni.

**Twist:** To są szczury. [[Miecz]] mówi, że to szczury. [[Barman]] ogłasza, że to znak. Wieś przyjmuje wersję [[Barmana]], bo jest ciekawsza - i to jest dokładnie ta sama operacja, którą wieś wykonała na [[Malachiasz|Malachim]].

```yaml
Miecz: "To były zwykłe szczury."
Barman: "To jest ZNAK."
Miecz: "To są TULKO szczury, które weszły dziurą w fundamencie."
Barman: "ZNAK, młodzieńcze. Dziura też jest częścią znaku."
```

**Nagroda:** dostęp do piwnicy na stałe, skrzynia z `golden_key` (patrz [[#Q06_S01 - Skrzynka Mariolki]]),
`max_health=+10` („_piwo z beczki, której nikt nie ruszał od 20 lat_")
**Requires:** `Q04_S02_TAVERN_TROPHY` ([[#Q04_S02 - Trofeum z dalekiego świata]])

**Do rozstrzygnięcia:** gdzie leży srebrny klucz (`silver_key`). Propozycja: w skrzyni `BLUNDERHAVEN_BIG_CHEST` (istnieje), żeby quest uczył też, że warto zaglądać do skrzyń.

---

### Q05 - „Nikomu ani słowa"

**Postać:** [[Kowal Kłamca]]

Tytuł to zdanie, które [[Kowal Kłamca|Kowal]] wypowiada w drugim kroku - i jedyne, jakie kiedykolwiek powiedział do [[Malachiasz|Malachiego]] dwa razy. 

**Nagroda parasola:** `damage=+5` ([[Kowal]] ostrzy stary sztylet i daje bohaterowi niechcąc za to pieniędzy, co u niego znaczy przyjaźń).

#### Q05_S01 - Ruda spod głazu

**KEY:** `Q05_S01_ORE_UNDER_BOULDER`

**Haczyk:** Zamówienie z [[Porażkowo|Porażkowa]] czeka, posłaniec z rudą nie przyszedł trzeci dzień z rzędu. [[Kowal]] wie, gdzie leży złoże - za lasem, pod głazem, którego kijem nie ruszysz.

**Mechanika:** [[Kowal]] **pożycza** topór wojenny (`axe` 35 dmg) przez `items_received`, gracz rozbija głazy (`DESTRUCTIBLE_MIN_DAMAGE>20`), wraca z rudą, **oddaje topór** przez `items_returned`. To jest naturalna lekcja mechaniki niszczenia - gracz uczy się jej z narzędziem w ręku, a nie z komunikatu „_broń za słaba_".

**Twist:** [[Kowal]] odbiera topór i waży go w dłoni dłużej, niż to konieczne. Nic nie mówi tylko wzdycha pod nosem.
To wystarczy - [[Malachiasz|Malachi]] (faza 1 lub 2) sam zaczyna się tłumaczyć, choć nikt go o nic nie oskarżył.

```yaml
Kowal: "Posłaniec nie przyszedł. Trzeci dzień z rzędu. Za lasem jest złoże, ale przykryte głazem. Twoim kijem tego nie ruszysz. Masz tu topór wojenny. ODDASZ. Policzyłem sobie w pamięci, ile waży.
Malachi: "A tak czysto teoretycznie, co by było gdybym go ... uszkodził? Przypadkiem oczywiście."
Malachi: "No a co jeśli, wypadnie mi z plecaka. Zdarza się to wszystkim. Chyba?"
Kowal: "Lepiej dla Ciebie aby tak się nie stało."
```

**Nagroda:** `money=60`, `sentiment=+10 @HAMMER_HOAXHEART`
**Nowy przedmiot:** `iron_ore` w `items.csv` (typ `other`, ciężki - `weight` ma boleć
przy udźwigu, to jedyna sensowna rola tej mechaniki w prologu).

#### Q05_S02 - Dotknij tej zbroi

**KEY:** `Q05_S02_TOUCH_THE_ARMOUR`

**Haczyk:** [[Kowal]] słyszał, że [[Malachiasz|Malachi]] psuje wszystko, czego dotknie. Chce to sprawdzić na swoim najlepszym wyrobie - bo od 30 lat nikt nie powiedział mu prawdy o jego pracy. (==ALT==: od 30 lat nikt niezdołał zniszczyć jego najtwadszego kowadła.)

**Mechanika:** czysty dialog, bez przedmiotów. Dostępny **tylko** gdy `quest_done("Q01_S01_LEARN_ABOUT_CURSE")` - to jest quest, którego nie ma, dopóki plotka nie ruszy. (==ALT==: przedmiot leży gdzieś obok i trzeba go przynieść. To wymusza zakończenie dialogu i powrót, co lepiej zadziała z powiadomieniami o rozpoczęciu questu i zakończeniu - nie wszystko w trakcie jednej rozmowy.)

**Twist:** Zbroja rozsypuje się. [[Kowal Kłamca|Kowal]] milczy i płaci za milczenie bohatera - a sentyment **rośnie**, bo [[Malachiasz|Malachi]] jest pierwszym człowiekiem od 30 lat, który dał mu szczerą informację zwrotną (==ALT==: nie może zniszczyć jego reputacji). [[Kowal Kłamca|Kowal]] nie umie inaczej sobie z tym poradzić, więc płaci.

Klątwa nie karze mechanicznie (W1) - ale **plotka i tak idzie dalej**: wieczorem [[Barman Absyntnent|Barman]] już i tak wie, mimo że [[Kowal Kłamca|Kowal]] z nikim nie rozmawia. Tego nie tłumaczymy. Tak działają plotki w małej wiosce, gdzie wszyscy wiedzą o sobie wszystko.

```yaml
Kowal: "Podobno psujesz wszystko, czego dotkniesz. Dotknij tej zbroi. Chcę wiedzieć, czy jest tak dobra, jak mówię klientom."
Malachi: "Nie sądzę, żeby to był dobry..."
Kowal: "DOTKNIJ" 
[zbroja rozsypuje się]
Kowal: "..."
Kowal: "Nikomu ani słowa. Bierz pieniądze i wyjdź. W tej chwili"
Miecz: "Zapłacił Ci za milczenie. Zapamiętaj to - to jest pierwszy raz, kiedy Twoja klątwa była coś warta."
```

**Nagroda:** `money=120`, `sentiment=+10 @HAMMER_HOAXHEART`
**Requires:** `Q05_S01_ORE_UNDER_BOULDER` ([[#Q05_S01 - Ruda spod głazu]]) **i** `Q01_S01_LEARN_ABOUT_CURSE` ([[Q01_S01 Dowiedz się więcej o klątwie]])

---

### Q06 - „Dla dobra nauki"

**Postać:** [[Zielarka Zmora]]

[[Zielarka Zmora|Zielarka]] nazywa nauką wszystko, co robi, łącznie z rzeczami, za które w mieście byłaby sądzona. 

**Nagroda parasola:** `life_pot` x2 i wiedza, która ustawia Akt 2.

#### Q06_S01 - Rupiecie Mariolki

**KEY:** `Q06_S01_MARIOLKAS_BOX`

**Haczyk:** Po tajemniczej uczennicy ([[Bibliofilistka des Informacja]]) została jej zamknięta skrzynka z zapiskami. [[Zielarka Zmora|Zielarka]] nigdy jej nie otworzyła. Klucza nie potrafi znaleźć.

**Mechanika:** zamknięta skrzynia z `requires_item="golden_key"`. Klucz leży w piwnicy tawerny ([[#Q04_S03 - Piwnica, do której się nie schodzi]]) - **łańcuchy się przecinają**, i to jest zaplanowane: gracz, który zrobił tylko jeden wątek, dostaje powód, żeby wrócić do drugiej.

**Twist:** W skrzynce są receptury spisane przez dziewczynę, która nie potrafiła nic ugotować - czyli bezużyteczne. Poza jedną kartką, która nie jest recepturą.

==TODO== do poprawy:
==ALT==: klątwy nie da się zdjąć miksturami, bo "_siedzi w głowie_"
```yaml
[kartka, pismo pospieszne]
"Klątwy nie da się zdjąć. Klątwę można tylko komuś oddać."
"Pytałam o to trzy razy. Za trzecim kazali mi wyjechać."
Miecz: "To jest zła wiadomość."
Malachi: "Dlaczego?"
Miecz: "Bo przeczytałeś ją głośno, a ja mam bardzo dobrą pamięć."
```

To zdanie **zapala Akt 2** i jest najważniejszą linijką w całym Prologu: od tej chwili klątwa nie jest chorobą do wyleczenia, tylko rzeczą do przekazania - a [[Malachiasz|Malachi]] zna już całkiem sporo osób.

**Nagroda:** `max_health=+10`, `sentiment=+15 @POTIONEER_PUZZLEMINT`
**Requires:** `Q03_S01_WHO_HAS_MORE_KNOWLEDGE` ([[Q03_S01 Kto ma wiedzę o magii]]) bo musi wiedzieć, kim była [[Bibliofilistka des Informacja|Mariolka]].

**Do rozstrzygnięcia u autora:** czy ta kartka ma być tu, czy dopiero u [[Bibliofilistka des Informacja|Bibliofilistki]] w Akcie 2. Tu jest wcześniej i mocniej, ale zjada część niespodzianki Aktu 2.

#### Q06_S02 - Pierwsze testy na ludziach

**KEY:** `Q06_S02_FIRST_HUMAN_TESTED`

**Haczyk:** [[Zielarka Zmora|Zielarka]] testowała miksturę na kurach. Kury zdechły. [[Malachiasz|Malachi]] i tak ma pecha, więc gorzej być może - a [[Zielarka Zmora|Zielarka]] sporo zapłaci za "_eksperyment_", więc propozycja jest kusząca.

**Mechanika:** dialog + efekty węzła (`health_lost` / `health_restored`), zero nowego kodu.

**Twist - i drugi silnik przepowiedni:** Mikstura działa **bez zarzutu**. [[Zielarka Zmora|Zielarka]] nie przyjmuje faktu, że receptura była dobra, tylko ogłasza, że **klątwa zjadła truciznę** - a wieś to podchwytuje. Od tej pory ludzie zaczynają prosić [[Malachiasz|Malachiego]], żeby próbował rzeczy przed nimi dla bezpieczeństwa, i to zostaje w barkach na stałe.

```yaml
Zielarka: "Testowałam moją nową miksturę na kurach. Kury jednak zdechły. Ale kura to nie człowiek. Kura ci nie powie, CO dokładnie czuje przed końcem."
Malachi: "A ja powiem?"
Zielarka: "Ty jesteś przeklęty, chłopcze. Tobie i tak nic gorszego już się nie stanie. Płacę z góry. Pij."
[nic złego się nie dzieje]
Zielarka: "Fascynujące. Klątwa zjadła truciznę."
Miecz: "Albo mikstura była dobra."
Zielarka: "Nie bądź śmieszny."
```

Barki odblokowane tym questem (do `doc/PL/Barki.md`):

- [[Bart]]: „_Panie, spróbuje pan tego sera? Tak na wszelki wypadek._"
- [[Marysia]]: „_Mąż mówi, że jak pan przejdzie koło studni, to woda się dłużej trzyma._"

**Nagroda:** `money=100`, `life_pot`, `sentiment=+10 @POTIONEER_PUZZLEMINT`.
**Requires:** `Q01_S01_LEARN_ABOUT_CURSE` [[Q01_S01 Dowiedz się więcej o klątwie]] bez plotki ten quest nie ma prawa istnieć.

---

## Barki - co napisać i gdzie

Format i mechanizm: [H01](H01-barki-emoji-wskaznik-questa.md), etap 1. Tutaj lista tego, co ma powstać treściowo.

| Plik                           | Kto                                                          | Ile linii (cel) |
| ------------------------------ | ------------------------------------------------------------ | --------------- |
| [[Barman Absyntnent#Barki]]    | [[Barman Absyntnent\|Barman]]                                | 10-14           |
| [[Kowal Kłamca#Barki]]         | [[Kowal Kłamca\|Kowal]]                                      | 6-8             |
| [[Zielarka Zmora#Barki]]       | [[Zielarka Zmora\|Zielarka]]                                 | 8-10            |
| [[Miecz Ciętej-riposty#Barki]] | [[Miecz Ciętej-riposty\|Miecz]]                              | 15-20           |
| [[Barki#VILLAGERS]]            | [[Bart]], [[Johny]], [[Marry]], [[Fred]], [[Rob]], [[Robin]] | 15-20           |


Nazwa puli to **nagłówek sekcji**, dosłownie, w `SCREAMING_SNAKE` - tak jak klucz questa jest nagłówkiem sekcji w pliku questa. Kto z której puli bierze, mówi kolumna `barks` w `characters.csv` ([H01/D2](H01-barki-emoji-wskaznik-questa.md)). Postać z własną sekcją `## Barki` **i** z pulą dostaje jedno i drugie.

Wytyczne, żeby barki nie zamieniły się w szum:

- **Bark ma być krótszy niż myśl.** Dwie linie po ~28 znaków to twardy limit importu - i dobrze, bo dłuższy bark nikt nie zdąży przeczytać, przechodząc obok.
- **Nie powtarzaj tego, co jest w dialogu.** Bark to nie skrót rozmowy, tylko to, co postać mówi, gdy nikt jej nie słucha.
- **Trzy warstwy na każdą postać:** neutralne (zawsze), zależne od pory dnia lub czynności, zależne od stanu świata (klątwa, ukończone questy).
- **Zwierzęta mówią mało i zawsze to samo** - w tym tkwi żart. Krowa ma trzy linijki i wszystkie brzmią „_Muuu_". Miecz komentuje **rzadko**, bo to on jest tu puentą.

## Co musi powstać poza tekstem

Rzeczy, których agent nie zrobi za autora:

| Rzecz                 | Gdzie                                                         | Status |
| --------------------- | ------------------------------------------------------------- | ------ |
| mapa piwnicy tawerny  | `maps/LOST_CORK_TAVERN_CELLAR.tmx` (Tiled)                    | ⏳      |
| sprite `HamsterGray`  | `assets/NinjaAdventure/characters/HamsterGray/` z asset packa | ✅      |
| emoji `food`, `sweat` | `assets/NinjaAdventure/Emote/emote_all_anim.png`              | ⏳      |
| ikona `iron_ore`      | arkusz przedmiotów                                            | ⏳      |
| skrytka kota + krzak  | mapa `BLUNDERHAVEN` (Tiled)                                   | ⏳      |
| głazy nad złożem      | mapa `BLUNDERHAVEN` albo nowa mapka „za lasem"                | ⏳      |
| liczby nagród i cen   | `items.csv`, `chests.csv`, nagrody questów                    | ⏳      |

Nowa mapa oznacza komplet: klucz `SCREAMING_SNAKE`, para plików `.md` PL i EN w `doc/PL/Lokalizacje/` i `doc/EN/Locations/`, wpis w sekcji `[map]` obu plików locale, wpis w `audio.toml`, punkty wejścia i drzwi zgodne z regułą 14 walidatora. Ściąga „_gdzie używam jakiego klucza_" jest w `project/AGENTS.md`.

## Kolejność pisania (propozycja)

1. **Powitania i dryf Malachiego** - najmniejsza zmiana, największy efekt, dotyka
   postaci, które już istnieją i już mają dialogi.
2. **`Q06_S02` (mikstura)** - jeden quest, zero nowych assetów, zero nowych mechanik.
   Dobry test, czy ton działa, zanim powstanie cokolwiek droższego.
3. **`Q05_S01` (ruda)** - uczy mechaniki niszczenia, potrzebuje tylko głazów na mapie.
4. **`Q04_S01` (ryby)** i **`Q05_S02` (zbroja)**.
5. **`Q04_S02` (trofeum)** - wymaga barków, więc dopiero po H01/etap 2.
6. **`Q04_S03` (piwnica)** i **`Q06_S01` (skrzynka)** - najdroższe: nowa mapa, nowy
   przeciwnik, klucze. Idą razem, bo dzielą `golden_key`.

## Kryteria akceptacji

- `just import-dialogs`, `just import-quests`, `just import-entities` przechodzą bez błędów; `just validate-world` - 0 błędów
- `just quest-graph` nie pokazuje questa `manual` bez kodu, który go domyka, ani parasola bez kroków (obie klasy błędów walidator odrzuca przy imporcie)
- `just dialog-graph` po imporcie - graf bez wiszących referencji i bez sierot
- każdy z siedmiu questów **da się ukończyć headless** przez `agent_ctrl` (skrypt przechodzący dialogi i sprawdzający `quest_state`) - bez tego łańcuch może być nieprzechodni i nikt się nie dowie
- wskaźnik questa na HUD (H01) pokazuje sensowny krok na każdym etapie każdego łańcucha
- **weryfikacja u autora**: czy to jest śmieszne. Tego nie da się zautomatyzować i nie ma sensu udawać, że się da

## Pułapki

- **Nie pisz questa, dla którego nie ma mechaniki.** Sprawdź listę: zbieranie, niszczenie krzaków i głazów odpowiednio silną bronią, skrzynie (od H01 także zamykane), handel, oddawanie i otrzymywanie przedmiotów w dialogu, cykl dobowy, rutyny, sentyment, walka. **Nie ma:** łowienia, przedmiotów zależnych od pory dnia,
  szybkiej podróży, rzemiosła.
- **`Test:` questa to nie to samo co `Postęp:`.** Pasek `3 / 3` nie zamyka questa. Zwykle chcesz obu (`doc/quest-cheatsheet.md`).
- **`visited()` w queście wymaga dwóch argumentów** (`NPC`, `NODE`); w dialogu jednego. To nie jest niekonsekwencja, tylko brak bieżącej postaci po stronie questa.
- **Nagroda o wartości `0` jest odrzucana przy imporcie**, a `sentiment` bez `@NPC_KEY` też. **Do sprawdzenia przed pisaniem:** czy importer przyjmuje **ujemny** sentyment - jeśli nie, żaden quest nie może obniżyć sympatii i trzeba to obejść treścią.
- **Klucz questa musi być globalnie unikalny** i jest dosłownie nagłówkiem sekcji.
- **Nazwa obiektu Tiled ≠ klucz configu.** Dialogi i questy używają `config_key`, zapis używa `name` (C02). Zmiana nazwy skrzyni **kasuje jej stan ze starych zapisów**.
- **Nie licz na to, że gracz przejdzie łańcuchy w kolejności.** `Q06_S01` potrzebuje klucza z `Q04_S03` - jeśli gracz zrobi tylko wątek [[Zielarki]], ma dostać czytelną wskazówkę, gdzie szukać, a nie ślepy zaułek.
- **Tłumaczenie EN jest ostatnim krokiem**, po wypolerowaniu polskiej wersji. PL jest jedynym źródłem prawdy dla struktury; EN daje samą prozę.

## Pytania otwarte do autora

1. **Ryby** - tylko ze skrytki kota, czy też do kupienia (drugi sposób, sens handlu)?
2. **`silver_key`** - w `BLUNDERHAVEN_BIG_CHEST`, czy gdzie indziej?
3. **Kartka Mariolki** („klątwę można tylko komuś oddać") - tu w Akcie 1, czy dopiero u [[Bibliofilistka des Informacja|Bibliofilistki]] w Akcie 2?
4. **Piwnica** - ile poziomów, ilu szczurów, czy jest tam coś poza `golden_key`?
5. **Nazwy parasoli** („_Sprawy najwyższej wagi_", „_Nikomu ani słowa_", „_Dla dobra nauki_") -  zostają, czy masz lepsze?
6. **Kot** - czy zostaje podejrzany do końca Aktu 1 (osobny bieg żartu w barkach), czy sprawa się zamyka wraz z questem?
