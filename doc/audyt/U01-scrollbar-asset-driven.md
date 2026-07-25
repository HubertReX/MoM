# U01 - bar.py: `scrollbar.png` jako realne źródło wyglądu suwaka

Priorytet: **P2** (Faza 3). Rozmiar: S. Zależności: sensownie po A03 (layout self-checks
złapią ewentualne regresje geometrii), ale technicznie niezależne.

## Kontekst i problem

`project/ui/widgets/bar.py` (wspólny komponent wszystkich suwaków i pasków postępu)
deklaruje w docstringu `assets/NinjaAdventure/HUD/scrollbar.png` (8×16) jako "reference
art", ale w rzeczywistości rysuje wszystko **proceduralnie** - model 8-kolumnowy jest
zahardcodowany w kodzie (`_NATIVE_CROSS = 8` itd.), a plik PNG nie jest w ogóle
wczytywany. To wynik nieporozumienia w jednej z wcześniejszych sesji.

Intencja autora: **edycja `scrollbar.png` w Aseprite ma być widoczna w grze**.
Autor robi assety sam i chce mieć kontrolę nad wyglądem komponentu przez plik graficzny,
nie przez kod.

## Cel

`bar.py` buduje suwak/pasek z pikseli wczytanego `scrollbar.png` (model natywny →
integer scale, jak nine-patch), zachowując obecne API (`draw_scrollbar`,
`draw_progress`) i obecną zasadę "gruby/kańciasty" z `ui/AGENTS.md`. Zmiana pikselą
w assecie = zmiana w grze po restarcie.

## Podejście do kolorów (rekomendacja - do potwierdzenia z autorem przy odbiorze)

Problem: komponent przyjmuje dynamiczne kolory (`fill=` np. dla paska sentymentu
liczonego z wartości 0-100), a asset ma konkretne kolory.

Rekomendacja: **podmiana palety (color-swap) na wczytanym assecie**:

1. Asset pozostaje w kolorach kanonicznych (dzisiejsze mapowanie z `ui/AGENTS.md`:
   `INK` = ramka, `RULE` = pusty track, `GOLD` = wypełnienie, `WARN` = ciemny bevel,
   `TITLE` = jasny bevel).
2. Przy wczytaniu `bar.py` klasyfikuje każdy piksel do jednej z 5 ról po dokładnej
   równości z tokenem `theme.py` (piksel nierozpoznany = błąd ładowania z czytelnym
   komunikatem - twardy sygnał, że asset i tokeny się rozjechały).
3. Rysowanie z `fill=<inny kolor>`: piksele roli "fill" dostają zadany kolor, bevele
   wyprowadzane jak dziś (ciemny = fill×0.6, jasny = blend do bieli) albo z ról
   bevel przy `fill` domyślnym.

Alternatywa (jeśli autor woli): warianty kolorystyczne rysowane ręcznie w Aseprite
(`scrollbar_gold.png`, `scrollbar_cyan.png`...) + fallback color-swap dla kolorów
dynamicznych. Zapytaj autora JEDNYM pytaniem przed implementacją, którą ścieżkę
wybiera; domyślnie realizuj rekomendację.

## Kroki

1. Wczytanie assetu raz (cache modułowy), rozbiór na role pikseli wg palety tokenów.
2. Zastąp proceduralne budowanie modelu natywnego (track, thumb, bevele, końcówki)
   modelem z pikseli assetu: końcówki/narożniki stałe, środkowe rzędy rozciągane
   (dokładnie zasada nine-patch z `ui/AGENTS.md`, sekcja "kształty proceduralne").
3. Integer scale (nearest) jak dotąd: `k = round(cross/8)`, min 2.
4. Zachowaj sygnatury `draw_scrollbar(...)` i `draw_progress(...)` bez zmian -
   żadnych modyfikacji w panelach używających komponentu.
5. Test wizualny: porównaj przed/po na panelach: pomoc (suwak pionowy), questy
   (postęp KROKI), dialog (suwak opcji + pasek sentymentu), RichText (suwak prozy).

## Kryteria akceptacji

1. Dowód sterowalności assetem: zmień lokalnie (bez commita) jeden piksel ramki
   w `scrollbar.png` na jaskrawy kolor spoza palety - gra przy starcie zgłasza czytelny
   błąd ładowania assetu (klasyfikacja pikseli); przywróć plik. Następnie zmień piksel
   ramki na inny token palety - zmiana jest widoczna w grze na suwaku pomocy.
2. Wszystkie miejsca użycia (pomoc, questy, dialog, RichText) wyglądają bez regresji -
   scenariusze agentowe z ss-review na panelu pomocy i questów: PASS.
3. Pasek sentymentu (kolor dynamiczny) nadal działa w pełnym zakresie 0-100.
4. `just test-unit` - pass; `just mypy` - bez nowych błędów.
5. Finalna weryfikacja autora na realnym ekranie (headless nie jest w pełni wierny -
   memory projektu).

## Pułapki

- Nie zmieniaj geometrii publicznej (szerokości suwaków w panelach to wielokrotności 8).
- `theme.draw_pixel_round_rect` to osobny prymityw - nie ruszaj.
- Asset 8×16 ma bevel kierunkowy (krawędź wiodąca vs przeciwna) - przy pionowym
  i poziomym wariancie zachowaj dzisiejsze zachowanie rotacji/transpozycji.
- Wczytywanie przez `pygame.image.load(...).convert_alpha()` dopiero PO init display
  (jak inne assety); cache per moduł, nie per instancja.

## Po zakończeniu

- zaktualizuj sekcję "Suwak i pasek postępu" w `project/ui/AGENTS.md` (asset jest teraz
  źródłem, nie referencją; opis ról pikseli i zasady color-swap)
- odhacz U01 w `doc/audyt/audyt.md`
- commit: `U01: bar.py czyta scrollbar.png - asset-driven suwaki z podmianą palety`
