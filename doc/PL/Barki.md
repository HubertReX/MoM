# Barki - wspólne pule

Bark to jednolinijkowa zaczepka, którą postać rzuca, gdy **Malachi** przechodzi obok.
Nie jest dialogiem: gracz nie odpowiada, nie ma opcji, nie ma panelu.

Ten plik trzyma pule **wspólne** - dla statystów i zwierząt, które nie mają
własnego pliku w `Postacie/`. Postać z własnym plikiem pisze swoje barki w sekcji
`## Barki` u siebie, a pula i tak jej przysługuje: sekcja własna i pula **sumują
się**. Kto bierze z której puli, mówi kolumna `barks` w `characters.csv`, a jej
wartością jest nagłówek sekcji z tego pliku, dosłownie.

Uwaga na kształt pliku: **każdy nagłówek `##` jest kluczem puli** i musi być
w `SCREAMING_SNAKE`. Proza pod nagłówkiem jest dla autora i nie trafia do gry -
liczą się tylko wypunktowania. Pełna instrukcja (warunki, limit długości, przykłady)
jest w [jak napisać barka](../jak-napisac-barka.md); 

Uzupełnij tłumaczenia w [[bar]]
po każdej zmianie tutaj uruchom `just import-dialogs`.

Na razie nie ma tu żadnej puli - to poprawny stan, wieś po prostu milczy.
Zacznij od dopisania sekcji `## NAZWA_PULI` i wypunktowań pod nią.

## VILLAGERS

Pula dla mieszkańców wsi.

- [time_of_day("morning") or time_of_day("day")] Dzień dobry
- [time_of_day("evening") or time_of_day("night")] Dobry wieczór
- [sentiment > 70] Uszanowanko
- [sentiment > 80] Siemka
- [on_map("LOST_CORK_TAVERN")] Ależ tu śmierdzi
- [on_map("BLUNDERHAVEN") and time_of_day("day")] Ładny mamy dzień
- [on_map("BLUNDERHAVEN") and time_of_day("night")] Noce znów są chłodne
- [activity("stand")] Robota sama się nie zrobi
- [activity("idle")] Nudno tu
- [activity("wander")] Zjadłbym coś
- [activity("wander")] W końcu chwila przerwy
- [quest_done("Q01_S01_LEARN_ABOUT_CURSE")] O, idzie nasz pechowiec
- [not quest_done("Q01_S01_LEARN_ABOUT_CURSE")] Hmm, kim jest ten nowy

## FARM_ANIMALS

Wszystkie zwierzaki

- Muuu
- Mu?
- Hauuuuu
- hał, hał
- miau
- mIAu