# Barki - wspólne pule

Bark to jednolinijkowa zaczepka, którą postać rzuca, gdy Malachi przechodzi obok.
Nie jest dialogiem: gracz nie odpowiada, nie ma opcji, nie ma panelu.

Ten plik trzyma pule **wspólne** - dla statystów i zwierząt, które nie mają
własnego pliku w `Postacie/`. Postać z własnym plikiem pisze swoje barki w sekcji
`## Barki` u siebie, a pula i tak jej przysługuje: sekcja własna i pula **sumują
się**. Kto bierze z której puli, mówi kolumna `barks` w `characters.csv`, a jej
wartością jest nagłówek sekcji z tego pliku, dosłownie.

Uwaga na kształt pliku: **każdy nagłówek `##` jest kluczem puli** i musi być
w `SCREAMING_SNAKE`. Proza pod nagłówkiem jest dla autora i nie trafia do gry -
liczą się tylko wypunktowania. Pełna instrukcja (warunki, limit długości, przykłady)
jest w [jak napisać barka](../jak-napisac-barka.md); po każdej zmianie tutaj
uruchom `just import-dialogs`.

Na razie nie ma tu żadnej puli - to poprawny stan, wieś po prostu milczy.
Zacznij od dopisania sekcji `## NAZWA_PULI` i wypunktowań pod nią.
