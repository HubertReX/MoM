# H03 - sidequesty Aktu 1 i samospełniająca się przepowiednia

Priorytet: **P3** (Faza 4). Rozmiar: **L**. Zależność: **twarda** -
[H01](H01-barki-emoji-wskaznik-questa.md) musi być zrobione (barki, zamki, klucze,
model `RAT`).

Status: **rev. 1 - szkic scenariusza do akceptacji autora**. To jest **połowa
treściowa**: siedem sidequestów, rozbudowa wątku klątwy i teksty barków. Wszystko
poniżej to **propozycja do przepisania ręką autora w Obsidian** - dialogi, żarty
i imiona są jego domeną, a ten plik ma dać strukturę, haczyki i punkty zaczepienia
w istniejących mechanikach, nie gotowy tekst do wklejenia.

Zadanie realizuje **G-3** (świat reaguje na sentyment), **G-4** (noc i rutyny dają coś
gameplayowi) oraz „_regrywalność w tonie gry_" z [audytu](audyt.md).

## Decyzje autora (wiążące, ustalone 2026-08-10)

- **W1** - klątwa **nie karze mechanicznie**. Sentyment i ceny się nie zmieniają, bo
  wieść się rozeszła. Zmienia się **wyłącznie to, co postacie mówią**.
- **W2** - plotka rozchodzi się przez **dialogi, nie przez symulację**. Po przejściu
  którejkolwiek linii, w której ==Malachi== przyznaje się do klątwy, u innych postaci
  pojawiają się nowe opcje, część domyślnych znika, a powitanie dostaje nutkę -
  uszczypliwości, pogardy albo współczucia, zależnie od charakteru postaci.
- **W3** - raz subtelnie, raz wprost. Monotonia jest gorsza niż brak reakcji.
- **W4** - ==Malachi== **stopniowo sam zaczyna wierzyć**. Bez wyboru dla gracza: proza
  dryfuje sama, od śmiechu przez tłumaczenie się do tego, że przestaje dotykać klamek.
- **W5** - sidequesty mają być **różnorodne**: każdy inny w charakterze. Rutynowe questy
  klepane na jedno kopyto, bez haczyka i bez osadzenia w świecie, są najgorszą rzeczą,
  jaka może się tu wydarzyć.
- **W6** - wszystkie siedem pomysłów wchodzi: **3 od Barmana, 2 od Kowala, 2 od Zielarki**.
  Niski koszt, a zawsze można wyciąć.
- **W7** - piwnica to **nowa mała mapa** (nie `VillageHouse.tmx`), z gryzoniami jako
  pierwszym, łatwym przeciwnikiem niewymagającym mocnej broni.
- **W8** - zwierzęta dostają onomatopeje, a [[Miecz Ciętej-riposty]] je komentuje.

### Uwagi autora do unikania na przyszłość

- **Quest bez twistu, smaczku i żartu jest słaby** - nawet jeśli mechanicznie działa.
  Odrzucony wariant „_zioła z krzaków_" upadł właśnie na tym.
- **Nie planuj mechanik, których nie ma.** Nie istnieje zbieranie przedmiotów zależne od
  pory dnia; nie ma łowienia ryb. Quest oparty na takiej mechanice to nie quest, tylko
  ukryte zadanie silnikowe.

## Zasada przewodnia: wieś produkuje klątwę

To jest **oś tonalna całego zadania** i sprawdzian dla każdej dopisanej linijki.

==Malachi== wraca z [[Tawerna Brakująca klepka|tawerny]] przeklęty przez czarodziejów - to fakt. Ale wszystko, co się
dzieje potem, wieś **produkuje sama**: [[Barman Absyntnent]] opowiada, [[Zielarka Zmora]] potwierdza, [[Kowal Kłamca]] nie
zaprzecza, a ==Malachi== po pewnym czasie sam zaczyna się z tego tłumaczyć. Beczka, obok
której stał, była beczką, dopóki nikt nie wiedział o klątwie. Teraz jest dowodem.

Ten sam mechanizm dostaje **jawną, komediową klamrę** w queście o trofeum
([[#Q04_S02 - Trofeum z dalekiego świata]]): gracz na własne oczy widzi, jak [[Barman Absyntnent]] wymyśla legendę o sobie i jak wieś
w nią wchodzi w trzy dni. [[Miecz Ciętej-riposty|Miecz]] ma to nazwać wprost - raz, i nigdy więcej, bo dwa razy
to już morał.

## Dryf Malachiego (W4) - trzy fazy, zero nowej maszynerii

Fazę wyznacza stan questów głównego wątku - dokładnie tak, jak ustala
[H01/D3](H01-barki-emoji-wskaznik-questa.md). Nic nowego w zapisie, nic nowego w configu.

| Faza             | Warunek                                                       | Jak brzmi Malachi                  | Przykład                                                           |
| ---------------- | ------------------------------------------------------------- | ---------------------------------- | ------------------------------------------------------------------ |
| 0 - lekceważy    | `not quest_done("Q01_S01_LEARN_ABOUT_CURSE")`                 | żartuje, bagatelizuje              | „_Klątwa? Dajcie spokój, po prostu mam słaby tydzień._"            |
| 1 - tłumaczy się | `quest_done("Q01_S01_...")` i `not quest_done("Q03_S00_...")` | przyznaje, ale z zastrzeżeniem     | „_Tak, klątwa. Ale to była wyjątkowo pechowa noc, nie osobowość._" |
| 2 - uwierzył     | `quest_done("Q03_S00_LEARN_ABOUT_CURSE")`                     | uprzedza innych, zanim go poproszą | „_Nie, nie podam ci tego. Sam weź._"                               |

Reguły pisania faz:

- **Faza 2 nie jest smutna, tylko praktyczna.** ==Malachi== nie użala się - on organizuje
  życie wokół klątwy, jak człowiek, który przestał kłócić się z pogodą.
- Faza 2 zostaje w mocy **także w sidequestach**: w tej fazie ==Malachi== sam z siebie
  ostrzega [[Kowal Kłamca|Kowala]] przed dotknięciem zbroi. [[Kowal Kłamca|Kowal]] i tak nalega.
- **Miecz ma to zauważyć raz**, mniej więcej w połowie fazy 2, i nie wracać do tematu.

## Powitania (W2, W3) - kto jak reaguje

Każda postać reaguje **zgodnie ze swoim charakterem z `doc/PL/Postacie/`**, nie według
jednego szablonu. Powitanie to pierwszy węzeł dialogu, więc technicznie jest to warunek
na węźle startowym - dokładnie ten wzór, który działa dziś u [[Zielarka Zmora|Zielarka]] (węzeł [[Zielarka Zmora#016|016]] jako
bramka).

| Postać                              | Charakter                       | Ton po plotce                                          | Szkic pierwszej linii                                                  |
| ----------------------------------- | ------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------- |
| [[Barman Absyntnent]]               | żartobliwy, rozmowny, zabobonny | teatralna troska, ale interes ważniejszy               | „_O, jest i on! Siadaj. Nie tam. Tam. Przy ścianie nośnej._"           |
| [[Kowal Kłamca]]                    | mruk, opryskliwy, gardzi wsią   | udaje, że go to nie obchodzi, czyli obchodzi go bardzo | „_Wiem. Wszyscy wiedzą. Nie dotykaj niczego po lewej._"                |
| [[Zielarka Zmora]]                  | zabobonna, nieufna, cwana       | zawodowe zainteresowanie okazem                        | „_Wejdź. Powoli. Chcę zobaczyć, jak się poruszasz._"                   |
| [[Bart]] / [[Johny]] (straganiarze) | statyści                        | plotka z drugiej ręki, przekręcona                     | „_Podobno pan zabił trzech czarodziejów. Rabat dla bohaterów: żaden._" |
| [[Marysia]]                         | statystka                       | szczere współczucie, niezręczne                        | „_Modliłam się za pana. Trochę. Miałam dużo prania._"                  |
| [[Miecz Ciętej-riposty]]            | złośliwy komentator             | jedyny, kto nie wierzy - i to on ma rację              | „_Zauważyłeś, że przestałeś dotykać klamek? Ja zauważyłem._"           |

Zasada z **W3** w praktyce: **na trzy reakcje jedna ma być bezpośrednia, dwie subtelne.**
Subtelna reakcja to taka, w której o klątwie nie pada ani słowo, a i tak wiadomo -
[[Kowal]] odsuwający kubek, [[Barman]] zmieniający ==Malachiemu== stolik.

## Siedem sidequestów

Trzy łańcuchy, po jednym na postać, każdy jako parasol `all_subquests` z krokami.
Parasol domyka się sam, gdy zamkną się wszystkie kroki, i daje nagrodę „_za relację_".

Kroki są **kolejnością zaufania**: pierwszy dostajesz od ręki, ostatni dopiero,
gdy postać cię zna. Bramka to `Requires:` na poprzednim kroku, a nie sentyment -
sentyment ma wpływać na **ton**, nie na dostępność, żeby żaden gracz nie utknął.

| Klucz                        | Postać       | Haczyk                              | Mechanika                  |
| ---------------------------- | ------------ | ----------------------------------- | -------------------------- |
| `Q04_S01_CATS_FISH`          | [[Barman]]   | kot zjadł zapas ryb                 | krzak + skrzynia + oddanie |
| `Q04_S02_TAVERN_TROPHY`      | [[Barman]]   | chce uchodzić za bywałego           | klejnot + oddanie          |
| `Q04_S03_TAVERN_CELLAR`      | [[Barman]]   | piwnica, do której nikt nie schodzi | klucz + drzwi + walka      |
| `Q05_S01_ORE_UNDER_BOULDER`  | [[Kowal]]    | posłaniec z rudą nie przyszedł      | pożyczony topór + głaz     |
| `Q05_S02_TOUCH_THE_ARMOUR`   | [[Kowal]]    | test pechowca na jego dziele        | dialog + plotka            |
| `Q06_S01_MARIOLKAS_BOX`      | [[Zielarka]] | zamknięta skrzynka po uczennicy     | klucz + skrzynia           |
| `Q06_S02_FIRST_HUMAN_TESTED` | [[Zielarka]] | testowała na kurach, kury zdechły   | dialog + zdrowie           |

---

### Q04 - „Sprawy najwyższej wagi" (Barman Absyntnent)

Tytuł parasola jest ironiczny i to jest cały żart: dla [[Barman Absyntnent|Barmana]] sprawy wsi mają rangę
polityki międzynarodowej. **Nagroda parasola:** `max_items=+1` ([[Barman]] załatwia mu
lepszy plecak „_od znajomego, nie pytaj_").

#### Q04_S01 - Ryby, które zjadł kot

**Haczyk.** Kot zjadł zapas ryb. Dla [[Barman Absyntnent|Barmana]] to nie jest problem gastronomiczny, tylko
początek wojny domowej.

**Mechanika (wszystko istnieje):** kot ma skrytkę za krzakiem; krzak trzeba rozwalić
(`DESTRUCTIBLE_MIN_DAMAGE`), skrytka to mała skrzynia z `fish`, oddanie przez
`items_returned` w dialogu.

**Twist.** Ryby są nadgryzione, a kot patrzy na ==Malachiego== przez cały czas z jednego
miejsca. [[Barman]] ogłasza, że kot jest opętany. Kot nie zaprzecza.

```
Barman: Sprawa jest poważna. Kot zjadł zapas ryb.
  Bez ryb nie ma zakąski. Bez zakąski chłopi piją na czczo.
  A chłopi pijący na czczo, młodzieńcze, to początek każdej
  wojny domowej w tej okolicy.
Miecz: Ile tych wojen tu było?
Barman: Ani jednej. I wiesz dlaczego? Bo zawsze były ryby.
```

**Nagroda:** `money=40`, `sentiment=+10 @BARMAN_ABSINTHRAYNER`.
**Test:** `item_count("fish") >= 5` po oddaniu, albo `visited("BARMAN_ABSINTHRAYNER", "<węzeł oddania>")`.

**Do rozstrzygnięcia:** czy ryby dają się też kupić (wtedy quest ma drugą drogę
i handel dostaje sens), czy tylko skrytka kota.

#### Q04_S02 - Trofeum z dalekiego świata

**Haczyk.** [[Barman]] chce uchodzić za bywałego - to jego konflikt wewnętrzny wprost
z `doc/PL/Postacie/Barman Absyntnent.md`. Prosi o „_coś egzotycznego_" nad bar.

**Mechanika:** dowolny klejnot z labiryntu albo z piwnicy, oddany w dialogu.

**Twist i klamra całego zadania.** Barman na oczach gracza wymyśla legendę, a przez
kolejne dni **barki innych postaci powtarzają ją coraz bardziej przekręconą**. To ten
sam mechanizm, który produkuje klątwę ==Malachiego==, tylko widziany z zewnątrz i śmieszny.

```
Barman (do chłopów): ...i wtedy ten smok mówi do mnie: TY? Znowu TY?
Miecz: On nie był nawet w sąsiedniej wiosce.
Malachi: Wiem.
Miecz: A oni mu wierzą.
Malachi: Wiem.
Miecz: ...
Miecz: Zastanów się nad tym przez chwilę.
```

Barki po tym queście (przykłady do dopisania w `doc/PL/Barki.md`):

- dzień 1, [[Bart]]: „_Podobno w karczmie jest smoczy kamień._"
- dzień 2, [[Marysia]]: „_Ten kamień jest ze smoka, co pożarł całą wieś._"
- dzień 3, [[Johny]]: „_Trzy wsie. I biskupa._"

**Nagroda:** `money=80`, `sentiment=+15 @BARMAN_ABSINTHRAYNER`.
**Requires:** `Q04_S01_CATS_FISH`.

#### Q04_S03 - Piwnica, do której się nie schodzi

**Haczyk.** Pod [[Tawerna Brakująca klepka|Tawerną]] jest piwnica. [[Barman]] tam nie schodzi, ojciec nie schodził,
dziadek zszedł raz i przez dwa lata nie pił. Klucz gdzieś jest.

**Mechanika (nowa z H01):** klucz `silver_key` → zamknięte drzwi (`requires_item`) →
**nowa mała mapa piwnicy** → `RAT` (sprite `HamsterGray`, ~15 HP, do ubicia `stick`iem).
To pierwszy kontakt gracza z walką, celowo na przeciwniku, który nie wymaga dobrej broni.

**Twist.** To są szczury. [[Miecz]] mówi, że to szczury. [[Barman]] ogłasza, że to znak.
Wieś przyjmuje wersję [[Barmana]], bo jest ciekawsza - i to jest dokładnie ta sama
operacja, którą wieś wykonała na ==Malachim==.

```
Miecz: To są szczury.
Barman: To jest ZNAK.
Miecz: To są szczury, które weszły dziurą w fundamencie.
Barman: ZNAK, młodzieńcze. Dziura też jest częścią znaku.
```

**Nagroda:** dostęp do piwnicy na stałe, skrzynia z `golden_key` (patrz `Q06_S01`),
`max_health=+10` („_piwo z beczki, której nikt nie ruszał od 20 lat_").
**Requires:** `Q04_S02_TAVERN_TROPHY`.

**Do rozstrzygnięcia:** gdzie leży `silver_key`. Propozycja: w `BLUNDERHAVEN_BIG_CHEST`
(istnieje), żeby quest uczył też, że warto zaglądać do skrzyń.

---

### Q05 - „Nikomu ani słowa" (Kowal Kłamca)

Tytuł to zdanie, które Kowal wypowiada w drugim kroku - i jedyne, jakie kiedykolwiek
powiedział do Malachiego dwa razy. **Nagroda parasola:** `damage=+5` (Kowal ostrzy mu
broń i nie chce za to pieniędzy, co u niego znaczy przyjaźń).

#### Q05_S01 - Ruda spod głazu

**Haczyk.** Zamówienie z [[Porażkowo|Porażkowa]] czeka, posłaniec z rudą nie przyszedł trzeci raz.
[[Kowal]] wie, gdzie leży złoże - pod głazem, którego kijem nie ruszysz.

**Mechanika:** Kowal **pożycza** `axe` (35 dmg) przez `items_received`, gracz rozbija
głazy (`DESTRUCTIBLE_MIN_DAMAGE`), wraca z rudą, **oddaje topór** przez `items_returned`.
To jest naturalna lekcja mechaniki niszczenia - gracz uczy się jej z narzędziem
w ręku, a nie z komunikatu „_broń za słaba_".

**Twist.** [[Kowal]] odbiera topór i waży go w dłoni dłużej, niż to konieczne. Nic nie mówi.
To wystarczy - ==Malachi== (faza 1 lub 2) sam zaczyna się tłumaczyć, choć nikt go nie oskarżył.

```
Kowal: Posłaniec nie przyszedł. Trzeci raz.
  Za lasem jest złoże, ale przykryte głazem.
  Twoim kijem tego nie ruszysz. Masz topór.
  ODDASZ. Policzyłem sobie w pamięci, ile waży.
```

**Nagroda:** `money=60`, `sentiment=+10 @HAMMER_HOAXHEART`.
**Nowy przedmiot:** `iron_ore` w `items.csv` (typ `key`, ciężki - `weight` ma boleć
przy udźwigu, to jedyna sensowna rola tej mechaniki w prologu).

#### Q05_S02 - Dotknij tej zbroi

**Haczyk.** [[Kowal]] słyszał, że ==Malachi== psuje wszystko, czego dotknie. Chce to sprawdzić
na swoim najlepszym wyrobie - bo od 30 lat nikt nie powiedział mu prawdy o jego pracy.

**Mechanika:** czysty dialog, bez przedmiotów. Dostępny **tylko** gdy
`quest_done("Q01_S01_LEARN_ABOUT_CURSE")` - to jest quest, którego nie ma, dopóki
plotka nie ruszy.

**Twist.** Zbroja rozsypuje się. [[Kowal Kłamca|Kowal]] milczy, płaci za milczenie - i sentyment **rośnie**,
bo ==Malachi== jest pierwszym człowiekiem od 30 lat, który dał mu szczerą informację
zwrotną. [[Kowal Kłamca|Kowal]] nie umie tego nazwać, więc płaci.

Klątwa nie karze mechanicznie (W1) - ale **plotka i tak idzie dalej**: wieczorem
[[Barman Absyntnent|Barman]] już wie, mimo że [[Kowal Kłamca|Kowal]] z nikim nie rozmawia. Tego nie tłumaczymy. To jest żart.

```
Kowal: Podobno psujesz wszystko, czego dotkniesz.
  Dotknij tej zbroi. Chcę wiedzieć, czy jest tak dobra,
  jak mówię klientom.
Malachi: Nie sądzę, żeby to był dobry...
Kowal: DOTKNIJ.
[zbroja rozsypuje się]
Kowal: ...
Kowal: Nikomu ani słowa. Płacę. Wyjdź.
Miecz: Zapłacił ci za milczenie. Zapamiętaj to - to jest
  pierwszy raz, kiedy twoja klątwa była coś warta.
```

**Nagroda:** `money=120`, `sentiment=+10 @HAMMER_HOAXHEART`.
**Requires:** `Q05_S01_ORE_UNDER_BOULDER` **i** `Q01_S01_LEARN_ABOUT_CURSE`.

---

### Q06 - „Dla dobra nauki" (Zielarka Zmora)

[[Zielarka Zmora|Zielarka]] nazywa nauką wszystko, co robi, łącznie z rzeczami, za które w mieście byłaby
sądzona. **Nagroda parasola:** `life_pot` x2 i wiedza, która ustawia Akt 2.

#### Q06_S01 - Skrzynka Mariolki

**Haczyk.** Po uczennicy ([[Bibliofilistka des Informacja]]) została jej
zamknięta skrzynka z zapiskami. [[Zielarka Zmora|Zielarka]] nigdy jej nie otworzyła. Klucza nie pamięta.

**Mechanika (nowa z H01):** zamknięta skrzynia z `requires_item="golden_key"`.
Klucz leży w piwnicy tawerny (`Q04_S03`) - **łańcuchy się przecinają**, i to jest
zaplanowane: gracz, który zrobił tylko jedną nitkę, dostaje powód, żeby wrócić do drugiej.

**Twist.** W skrzynce są receptury spisane przez dziewczynę, która nie potrafiła nic
ugotować - czyli bezużyteczne. Poza jedną kartką, która nie jest recepturą.

```
[kartka, pismo pospieszne]
"Klątwy nie da się zdjąć. Klątwę można tylko komuś oddać.
 Pytałam o to trzy razy. Za trzecim kazali mi wyjechać."
Miecz: To jest zła wiadomość.
Malachi: Dlaczego?
Miecz: Bo przeczytałeś ją głośno, a ja mam bardzo dobrą pamięć.
```

To zdanie **zapala Akt 2** i jest najważniejszą linijką w całym H03: od tej chwili
klątwa nie jest chorobą do wyleczenia, tylko rzeczą do przekazania - a ==Malachi== zna
już całkiem sporo osób.

**Nagroda:** `max_health=+10`, `sentiment=+15 @POTIONEER_PUZZLEMINT`.
**Requires:** `Q03_S01_WHO_HAS_MORE_KNOWLEDGE` (musi wiedzieć, kim była [[Bibliofilistka des Informacja|Mariolka]]).

**Do rozstrzygnięcia u autora:** czy ta kartka ma być tu, czy dopiero u [[Bibliofilistka des Informacja|Bibliofilistka]]
w Akcie 2. Tu jest wcześniej i mocniej, ale zjada część niespodzianki Aktu 2.

#### Q06_S02 - Pierwszy testowany człowiek

**Haczyk.** [[Zielarka Zmora|Zielarka]] testowała miksturę na kurach. Kury zdechły. ==Malachi== i tak ma pecha,
więc gorzej nie będzie - i płaci z góry.

**Mechanika:** dialog + efekty węzła (`health_lost` / `health_restored`), zero nowego kodu.

**Twist - i drugi silnik przepowiedni.** Mikstura działa **bez zarzutu**. [[Zielarka Zmora|Zielarka]] nie
przyjmuje wniosku, że receptura była dobra, tylko ogłasza, że **klątwa zjadła truciznę** -
a wieś to podchwytuje. Od tej pory ludzie zaczynają prosić ==Malachiego==, żeby próbował
rzeczy przed nimi, i to zostaje w barkach na stałe.

```
Zielarka: Testowałam na kurach. Kury zdechły.
  Ale kura to nie człowiek. Kura ci nie powie, CO dokładnie
  czuje przed końcem.
Malachi: A ja powiem?
Zielarka: Ty jesteś przeklęty, chłopcze. Tobie i tak nic
  gorszego już się nie stanie. Płacę z góry. Pij.
[nic złego się nie dzieje]
Zielarka: Fascynujące. Klątwa zjadła truciznę.
Miecz: Albo mikstura była dobra.
Zielarka: Nie bądź śmieszny.
```

Barki odblokowane tym questem (do `doc/PL/Barki.md`):

- [[Bart]]: „_Panie, spróbuje pan tego sera? Tak na wszelki wypadek._"
- [[Marysia]]: „_Mąż mówi, że jak pan przejdzie koło studni, to woda się dłużej trzyma._"

**Nagroda:** `money=100`, `life_pot`, `sentiment=+10 @POTIONEER_PUZZLEMINT`.
**Requires:** `Q01_S01_LEARN_ABOUT_CURSE` (bez plotki ten quest nie ma prawa istnieć).

---

## Barki - co napisać i gdzie

Format i mechanizm: [H01](H01-barki-emoji-wskaznik-questa.md), etap 1. Tutaj lista tego, co ma powstać treściowo.

| Plik                                      | Kto                                                          | Ile linii (cel)            |
| ----------------------------------------- | ------------------------------------------------------------ | -------------------------- |
| `doc/PL/Postacie/Barman Absyntnent.md`    | [[Barman Absyntnent\|Barman]]                                | 10-14                      |
| `doc/PL/Postacie/Kowal Kłamca.md`         | [[Kowal Kłamca\|Kowal]]                                      | 6-8, w tym dwie samo „..." |
| `doc/PL/Postacie/Zielarka Zmora.md`       | [[Zielarka Zmora\|Zielarka]]                                 | 8-10                       |
| `doc/PL/Postacie/Miecz Ciętej-riposty.md` | [[Miecz Ciętej-riposty\|Miecz]]                              | 15-20 (komentuje wszystko) |
| `doc/PL/Barki.md`, pula `VILLAGERS`       | [[Bart]], [[Johny]], [[Marry]], [[Fred]], [[Rob]], [[Robin]] | 15-20                      |
| `doc/PL/Barki.md`, pula `FARM_ANIMALS`    | krowa, świnia, koń, kury                                     | 6-8                        |
| `doc/PL/Barki.md`, pula `PETS`            | psy, kot                                                     | 4-6                        |

Nazwa puli to **nagłówek sekcji**, dosłownie, w `SCREAMING_SNAKE` - tak jak klucz questa
jest nagłówkiem sekcji w pliku questa. Kto z której puli bierze, mówi kolumna `barks`
w `characters.csv` ([H01/D2](H01-barki-emoji-wskaznik-questa.md)). Postać z własną sekcją
`## Barki` **i** z pulą dostaje jedno i drugie.

Wytyczne, żeby barki nie zamieniły się w szum:

- **Bark ma być krótszy niż myśl.** Dwie linie po ~28 znaków to twardy limit importu -
  i dobrze, bo dłuższy bark nikt nie zdąży przeczytać, przechodząc obok.
- **Nie powtarzaj tego, co jest w dialogu.** Bark to nie skrót rozmowy, tylko to, co
  postać mówi, gdy nikt jej nie słucha.
- **Trzy warstwy na każdą postać:** neutralne (zawsze), zależne od pory dnia lub
  czynności, zależne od stanu świata (klątwa, ukończone questy).
- **Zwierzęta mówią mało i zawsze to samo** - w tym tkwi żart. Krowa ma trzy linijki
  i wszystkie brzmią „_Muuu_". Miecz komentuje **rzadko**, bo to on jest tu puentą.

## Co musi powstać poza tekstem

Rzeczy, których agent nie zrobi za autora:

| Rzecz | Gdzie | Kto |
| --- | --- | --- |
| mapa piwnicy tawerny | `maps/LOST_CORK_TAVERN_CELLAR.tmx` (Tiled) | autor |
| sprite `HamsterGray` | `assets/NinjaAdventure/characters/HamsterGray/` z asset packa | autor |
| emoji `food`, `sweat` | `assets/NinjaAdventure/Emote/emote_all_anim.png` | autor |
| ikona `iron_ore` | arkusz przedmiotów | autor |
| skrytka kota + krzak | mapa `BLUNDERHAVEN` (Tiled) | autor |
| głazy nad złożem | mapa `BLUNDERHAVEN` albo nowa mapka „za lasem" | autor |
| liczby nagród i cen | `items.csv`, `chests.csv`, nagrody questów | autor |

Nowa mapa oznacza komplet z C02: klucz `SCREAMING_SNAKE`, para plików `.md` PL i EN
w `doc/PL/Lokalizacje/` i `doc/EN/Locations/`, wpis w sekcji `[map]` obu plików locale,
wpis w `audio.toml`, punkty wejścia i drzwi zgodne z regułą 14 walidatora.
Ściąga „_gdzie używam jakiego klucza_" jest w `project/AGENTS.md`.

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

- `just import-dialogs`, `just import-quests`, `just import-entities` przechodzą
  bez błędów; `just validate-world` - 0 błędów
- `just quest-graph` nie pokazuje questa `manual` bez kodu, który go domyka, ani
  parasola bez kroków (obie klasy błędów walidator odrzuca przy imporcie)
- `just dialog-graph` po imporcie - graf bez wiszących referencji i bez sierot
- każdy z siedmiu questów **da się ukończyć headless** przez `agent_ctrl` (skrypt
  przechodzący dialogi i sprawdzający `quest_state`) - bez tego łańcuch może być
  nieprzechodni i nikt się nie dowie
- wskaźnik questa na HUD (H01) pokazuje sensowny krok na każdym etapie każdego łańcucha
- **weryfikacja u autora**: czy to jest śmieszne. Tego nie da się zautomatyzować
  i nie ma sensu udawać, że się da

## Pułapki

- **Nie pisz questa, dla którego nie ma mechaniki.** Sprawdź listę: zbieranie,
  niszczenie krzaków i głazów odpowiednio silną bronią, skrzynie (od H01 także
  zamykane), handel, oddawanie i otrzymywanie przedmiotów w dialogu, cykl dobowy,
  rutyny, sentyment, walka. **Nie ma:** łowienia, przedmiotów zależnych od pory dnia,
  szybkiej podróży, rzemiosła.
- **`Test:` questa to nie to samo co `Postęp:`.** Pasek `3 / 3` nie zamyka questa.
  Zwykle chcesz obu (`doc/quest-cheatsheet.md`).
- **`visited()` w queście wymaga dwóch argumentów** (`NPC`, `NODE`); w dialogu jednego.
  To nie jest niekonsekwencja, tylko brak bieżącej postaci po stronie questa.
- **Nagroda o wartości `0` jest odrzucana przy imporcie**, a `sentiment` bez `@NPC_KEY`
  też. **Do sprawdzenia przed pisaniem:** czy importer przyjmuje **ujemny** sentyment -
  jeśli nie, żaden quest nie może obniżyć sympatii i trzeba to obejść treścią.
- **Klucz questa musi być globalnie unikalny** i jest dosłownie nagłówkiem sekcji.
- **Nazwa obiektu Tiled ≠ klucz configu.** Dialogi i questy używają `config_key`,
  zapis używa `name` (C02). Zmiana nazwy skrzyni **kasuje jej stan ze starych zapisów**.
- **Nie licz na to, że gracz przejdzie łańcuchy w kolejności.** `Q06_S01` potrzebuje
  klucza z `Q04_S03` - jeśli gracz zrobi tylko nitkę Zielarki, ma dostać czytelną
  wskazówkę, gdzie szukać, a nie ślepy zaułek.
- **Tłumaczenie EN jest ostatnim krokiem**, po wypolerowaniu polskiej wersji. PL jest
  jedynym źródłem prawdy dla struktury; EN daje samą prozę.

## Pytania otwarte do autora

1. **Ryby** - tylko ze skrytki kota, czy też do kupienia (drugi sposób, sens handlu)?
2. **`silver_key`** - w `BLUNDERHAVEN_BIG_CHEST`, czy gdzie indziej?
3. **Kartka Mariolki** („klątwę można tylko komuś oddać") - tu w Akcie 1, czy dopiero
   u Bibliofilistki w Akcie 2?
4. **Piwnica** - ile poziomów, ilu szczurów, czy jest tam coś poza `golden_key`?
5. **Nazwy parasoli** („_Sprawy najwyższej wagi_", „_Nikomu ani słowa_", „_Dla dobra nauki_") -
   zostają, czy masz lepsze?
6. **Kot** - czy zostaje podejrzany do końca Aktu 1 (osobny bieg żartu w barkach),
   czy sprawa się zamyka wraz z questem?
