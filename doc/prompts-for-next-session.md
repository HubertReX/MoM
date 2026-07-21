Konieczne do ukończenia prologu:

- [ ] nowa mapa na bazie Village z dodatkowymi budynkami i docelowym rozmieszczeniem postaci oraz przedmiotów
- [ ] system odnawiania stanu posiadania handlarzy kolejnego dnia
- [ ] prosty dobowy cykl życia NPC
- [ ] balancing atrybutów postaci, przedmiotów (bohatera, na mapie, w lochu, u handlarzy)

Inne:

- [ ] gra nie zapisuje lub źle odczytuje stań skrzyni (otwarta/zamknięta) oraz stan obiektów, które da się zniszczyć (krzaki, kamienie) - po wczytaniu gry, stan tych obiektów jest jak przy wczytaniu nowej mapy
- [ ] podczas odczytu gry (F9), zmiany nazwy zapisu gry, i handlu klawisze 'i', 'j' oraz 'h' otwierają panele (inventory, quest, help) - to powinno być zablokowane.
- [ ] system cząsteczkowy destrukcji źle wyświetla swoje sprite'y w nocy kiedy działa shader - tło sprite'a jest czarne a ma być przeźroczyste.
- [ ] w polach input, jak się wciśnie i przytrzyma przycisk to działa on tylko raz - kolejne litery powinny pojawiać się z małym opóźnieniem, a strzałki powinny przesuwać kursor, aż do zwolnienia klawisza 
- [ ] scrollbar.png nie jest używany - kod sam rysuje scrollbary zamiast użyć nine-patch.
- [ ] co się stanie jak zwiększę max_inventory?
- [ ] po zmianie rozdzielczości ekran wraca na monitor na którym był uruchomiony
- [ ] przydało by się włączyć FOW w labiryncie w trybie web
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

