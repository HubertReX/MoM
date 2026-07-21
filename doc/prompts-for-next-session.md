Konieczne do ukończenia prologu:

- [ ] nowa mapa na bazie Village z dodatkowymi budynkami i docelowym rozmieszczeniem postaci oraz przedmiotów
- [ ] system odnawiania stanu posiadania handlarzy kolejnego dnia
- [ ] prosty dobowy cykl życia NPC
- [ ] balancing atrybutów postaci, przedmiotów (bohatera, na mapie, w lochu, u handlarzy)

Inne:

- [x] gra nie zapisuje lub źle odczytuje stań skrzyni (otwarta/zamknięta) oraz stan obiektów, które da się zniszczyć (krzaki, kamienie) - po wczytaniu gry, stan tych obiektów jest jak przy wczytaniu nowej mapy
- [x] gra źle odtwarza stan labiryntu => gra zapisuje jedną liczbą `seed`, która odtwarza cały stan (korytarze, potwory, przedmioty, skrzynie)
- [x] przed wejściem do lochów, gra robi cichy `quick save` na slot 0 => gra pokazuje tost przy `auto save`
- [x] Wczytaj zapis z menu głównego to nie ten sam modal co quick load (F9) to samo z rename - usuń duplikaty, referencyjne obiekty to te z quick load, bo tam są już ładne keycap dla przycisków. 
- [x] F5 i F9 to mają działać jak autentyczne quick save/load (obecnie F5 jest ok, F9 otwiera panel) używające slot 0, który zawsze nazywa się 'quick save' w wersji EN a 'szybki zapis' w wersji PL. Slot 0 ma być specjalnie traktowany: nie da się zapisać manualnie gry na nim, nie można go skasować. Może być oddzielony kreską na liście. Pełne menu save i load ma pokazywać się dopiero z poziomu menu głównego - load już jest, save trzeba dodać. `SavePanel` jest już zdefiniowany, ale nigdzie nie otwierany - użyj go i dostosuj do design system (project/ui/AGENTS.md), pamiętaj o keycap dla skrótów klawiszowych. Menu Save ma być niedostępne w labiryncie.
- [x] podczas odczytu gry (F9), zmiany nazwy zapisu gry, i handlu klawisze 'i', 'j' oraz 'h' otwierają panele (inventory, quest, help) - to powinno być zablokowane.
- [ ] mypy 24 błędy
- [x] system cząsteczkowy destrukcji źle wyświetla swoje sprite'y (nie zawsze, chyba głównie w nocy kiedy działa shader) - tło sprite'a jest czarne a ma być przeźroczyste.
- [x] przy nieudanej próbie zniszczenia obiektu (kamienie, krzaki), bo broń jest za słaba powinien pojawić się toast z informacją, aby gracz wiedział, że "pomysł był dobry" (da się niszczyć niektóre obiekty), ale "wykonanie złe" (broń musi być dostatecznie mocna)
- [ ] w polach input, jak się wciśnie i przytrzyma przycisk to działa on tylko raz - kolejne litery powinny pojawiać się z małym opóźnieniem, a strzałki powinny przesuwać kursor, aż do zwolnienia klawisza 
- [ ] scrollbar.png nie jest używany - kod sam rysuje scrollbary zamiast użyć nine-patch.
- [ ] co się stanie jak zwiększę max_inventory?
- [ ] po zmianie rozdzielczości ekran wraca na monitor na którym był uruchomiony
- [ ] przydało by się włączyć fog-of-war (FoW) w labiryncie w trybie web, ale to się wiąże z shaderami
- [ ] zwierzęta mają być tylko w określonych strefach (np.: łąka), bo przeszkadzają
- [ ] zwierzęta czasami się klinują i dygocą w miejscu
- [ ] ryby i żaby jak są w wodzie to nie powinny rzucać cienia
- [ ] brakowało elementu w EN.toml, ale nic nie rzucało błędem - sprawdzić czy jest jakiś test podczas importu
- [x] system cząsteczek po pauzie lub wejściu w menu nagle spawnuje mnóstwo elementów
- [-] przeanalizuj ten artykuł i ostatnie nasze sesje, szczególnie te dłuższe, zobacz kiedy model męczył się z czymś wielokrotnie i tracił tokeny. Czy zainstalowanie jednego z narzędzi wymienionych w tym artykule może przynieść znaczącą poprawę skuteczności, przyśpieszyć pracę i zaoszczędzić tokeny? Jeśli tak, to które narzędzie będzie najlepsze dla projektu gry MoM?
- [x] ekran restartu (r) mapy wymaga trochę miłości
- [x] ekran wczytaj grę (F9) oraz zmień nazwę (r), oraz potwierdzenie wczytania (enter - richtext, brak panelu, który kolor wybiera?) wymagają dużo miłości
- [x] skróty F5, F6 i F9 powinny być wydoczne na panelu help w trybie web
- [x] jak sprzedam przedostatni przedmiot to potem nie wybiera się pierwszy i jest próba sprzedania przedmiotu niedozwolonego typu (Jaś)
- [x] nagrody czasami się nie mieszczą w panelu - dodaj scrollbar albo jeszce lepiej komponent panel, który ma wbudowany scrollbar, pokazujący się tylko wtedy kiedy trzeba
- [x] zjedzenie czegoś powinno uruchamiać toast
- [x] po zmianie języka interfejs w menu się nie aktualizuje, a w samej grze nie widać zupełnie HUD
- [x] czy cały ekran jest na koniec pipeline renderu skalowany 3.xx?

Problemy ze źle wyskalowanymi emoji:

- [x] panel quest w sekcji nagród - jest jakaś dziwna skala, poprawić do 16 lub 32
- [x] toast mają za małe emocji - nieczytelne
- [x] panel stats przesunąć w prawy górny róg i upewnić się, że toasty jadą teraz do samej góry ekranu
- [x] zachować spójne odległości od granicy ekranu stałych elementów HUD: stats, broń, sloty itemów, show help, toasty - preferowana odległość taka jak obecnie ma panel broni.
- [x] wyrównać keycap akcji w prawym dolnym rogu tak, aby prawa krawędź keycap pokrywała się z prawą krawędzią panelu z opisem akcji

