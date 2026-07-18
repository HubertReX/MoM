# Przeprojektowanie panelu pomocy (skróty klawiszowe)

## Context

Naciśnięcie `H` (lub `F1`) w grze wyświetla dziś panel pomocy renderowany przez
`HUD.show_help` (`project/ui/panels/hud.py:293`). Ma trzy wady:

1. **Nie pauzuje gry** - świat toczy się dalej za panelem (potwora atakuje gracza
   w trakcie czytania).
2. **Nie mieści się na ekranie** - to wąski, przewijalny pasek przyklejony do
   prawej krawędzi (`content_w = 400`, `panel_x = WIDTH - content_w - 16`), który
   przy większej liczbie akcji wymaga scrollowania.
3. **Brak logicznego grupowania i brak realnego chowania skrótów debugowych** -
   panel iteruje po wszystkich `ACTIONS`, które mają ustawione pole `show`, bez
   żadnej flagi debug (jedyne gatowanie to `[] if IS_WEB` dla `reload`/`quick_save`/
   `quick_load`). Dodatkowo część realnych kontrolek gracza (cyfry 1-6, `.`/`,`,
   skok) ma `show=None` i w ogóle nie pojawia się w pomocy.

Cel: nowy, wyśrodkowany, duży panel modalny, który **pauzuje świat** do zamknięcia,
grupuje skróty tematycznie, chowa skróty deweloperskie za flagą runtime
`SHOW_DEBUG_INFO`, dokumentuje brakujące kontrolki gracza oraz sterowanie
wewnątrz okien dialogu i dziennika questów, i nigdy nie pokazuje w web klawiszy
niedostępnych w tym trybie.

## Decyzje (potwierdzone z userem)

- **Pauza** przez wzorzec panelu modalnego (jak `QuestPanel`), nie przez
  `game.is_paused` (F8). Scena już zamraża świat, gdy otwarty jest panel z krotki
  `_MODAL` (`project/scene.py:1210-1226`): `scene.update` robi wczesny return po
  `reset_inputs`, ale `ui.update` (a więc toggle/zamknięcie panelu) wykonuje się
  wcześniej, więc panel da się zamknąć. `game.is_paused` pomija `scene.update`
  całkowicie, co uniemożliwiłoby zamknięcie.
- **Flaga gatująca debug**: `settings.SHOW_DEBUG_INFO` (przełączana runtime przez
  `` ` ``/`Z`). Sekcja "Debug" panelu pojawia się tylko przy włączonym overlayu debug.
- **Skróty debug/dev-only** (chowane): `` ` ``/`Z` (debug overlay), `B` (filtr alpha),
  `N` (następny dzień), `F3` (toggle UI), `F4` (intro), `F7` (TextInput demo),
  `R` (reload mapy), `Alt` (fly/noclip).
- **Skróty pozostające dla gracza**: m.in. `F2` (menu) i `F6` (screenshot) NIE są
  debugowe - zostają widoczne.
- **Dodać brakujące kontrolki gracza**: cyfry `1-6` (wybór slotu hotbara),
  `.`/`,` (przełączanie przedmiotu), `Space` (skok), oraz **osobną sekcję
  sterowania wewnątrz okna dialogu i przeglądu questów**.

## Grupowanie skrótów (docelowa treść panelu)

Trójkolumnowy układ, każda grupa z tytułem. Rows = ikona(y) klawisza + opis
przeznaczenia (nie tylko techniczna nazwa akcji).

- **Ruch**: `WASD`/strzałki - poruszanie; `Shift` - bieg; `Space` - skok;
  `+`/`-` - przybliż/oddal kamerę.
- **Interakcja**: `Space` - rozmawiaj / otwórz / atakuj (kontekstowo); `E` -
  podnieś / przełącz; `X` - upuść; `F` - użyj przedmiotu / kup / sprzedaj.
- **Ekwipunek**: `I` - ekwipunek; `J`/`F10` - dziennik questów; `1-6` - wybór
  slotu paska; `.`/`,` - przełącz zaznaczony przedmiot.
- **Mysz**: `LMB` - idź do; `RMB` - zatrzymaj.
- **System**: `H`/`F1` - ta pomoc; `F2` - menu główne; `Esc`/`Q` - menu główne;
  `F5` - szybki zapis; `F9` - szybki odczyt; `F6` - zrzut ekranu.
- **W oknach (dialog / dziennik)**: `↑`/`↓` - wybór opcji / pozycji; `Space` -
  przewiń tekst NPC; `Enter` - zatwierdź / rozwiń; `←`/`→` - filtr wątków
  (dziennik); `Esc`/`Q` - zamknij okno.
- **Debug** (tylko przy `SHOW_DEBUG_INFO`): `` ` ``/`Z` - overlay debug; `B` - filtr
  światła; `N` - następny dzień; `F3` - ukryj UI; `F4` - odtwórz intro; `F7` -
  demo TextInput; `R` - przeładuj mapę; `Alt` - tryb latania.

Web: cała sekcja **Debug** ukryta (i tak `SHOW_DEBUG_INFO` w web nieużywane),
plus wiersze `F5`/`F9` (zapis/odczyt) ukryte tak jak dziś (`[] if IS_WEB`).

## Implementacja

### 1. Mock HTML (pierwszy krok, do zatwierdzenia layoutu)

Zgodnie z ustalonym w repo wzorcem (`QuestPanel` zbudowany do
`doc/_attachements/quest-system-ssis-2026-07-16.html`) - zbudować statyczny mock
`doc/_attachements/help-panel-<data>.html` z docelowym układem kolumn, paletą i
rozmiarami, który stanie się specyfikacją współrzędnych panelu. Użyć skilla
`html-craft`.

### 2. Nowy panel modalny `HelpPanel`

Nowy plik `project/ui/panels/help.py`, klasa `HelpPanel(Widget)` wzorowana na
`project/ui/panels/quest.py`:

- Wyśrodkowany nine-patch (`theme.nine_patch("nine_patch_04.png", W, H)`),
  geometria ~ `PANEL_X=90, PANEL_Y=60, PANEL_W=1100, PANEL_H=600` (logiczne
  `WIDTH=1280, HEIGHT=720`), dostrojona do mocka.
- Renderuje tytuł, następnie grupy rozłożone w 3 kolumnach; każdy wiersz to
  ikona(y) klawisza + opis. Rysowanie tekstu przez `self.hud.draw_text`
  (jak `QuestPanel._text`), ikony przez `self.hud.icons[...]`.
- `open()` resetuje ewentualny scroll (docelowo layout ma się mieścić bez
  scrolla; scroll zostaje jako fallback dla trybu debug, obsługa jak w
  `hud._on_event`).

**Źródło danych**: curated struktura grup w `help.py` (lista sekcji: tytuł i18n +
wiersze). Każdy wiersz referuje istniejący klucz `ACTIONS` po nazwie (żeby ikona
klawisza była jednym źródłem prawdy) lub podaje własną listę ikon dla kombinacji
nie mapujących się 1:1 na akcję (nawigacja w oknach). Opis = nowy klucz i18n.
Sekcja Debug filtrowana `if SHOW_DEBUG_INFO`; wiersze web-wrażliwe filtrowane
`if not IS_WEB`.

### 3. Rejestracja jako modal (`project/ui/game_ui.py`)

- Import `HelpPanel`, dopisać do krotek `_MODAL` i `_BLOCKING` (freeze świata +
  ukrycie hotbara/HUD gameplay pod panelem).
- W `GameUI.update` dodać (wzór jak `QuestPanel`, linie 154-174):
  ```
  if INPUTS["help"]:
      self.toggle(HelpPanel); INPUTS["help"] = False
  if self.is_open(HelpPanel):
      if self._edge("up"):   help.scroll_up()
      if self._edge("down"): help.scroll_down()
      if INPUTS["quit"]:     self.close(HelpPanel); INPUTS["quit"] = False
  ```
- Property `show_help_info` (getter/setter w `game_ui.py:131-136`) przemapować na
  `is_open(HelpPanel)` albo usunąć na rzecz bezpośredniego `is_open`.

### 4. Usunięcie starej ścieżki (`project/scene.py`, `project/ui/panels/hud.py`)

- `scene.py:1386-1388` - usunąć toggle `INPUTS["help"]` (przeniesiony do
  `GameUI.update`).
- `hud.py` - usunąć `show_help` (293-319) oraz `_on_event`/`handle_event`
  scrollowania starego panelu, jeśli nieużywane; w `draw_gameplay` (452-455)
  zawsze wołać `show_available_actions` (panel modalny rysuje `GameUI.draw`).
- `show_available_actions` (338-340) - guard "podpowiedź H" zmienić z
  `show_help_info` na `not self.scene.ui.is_open(HelpPanel)`.

### 5. Brakujące ikony klawiszy (`project/scene.py:generate_icons`)

`generate_icons` (277-315) generuje `key_A..Z`, `key_0..8`, `key_F1..F12`,
oraz znaki z `"<>``[]+-"`. Brakuje ikon dla `.` `,` (przełączanie przedmiotu) oraz
etykiet `Alt`/`Enter`/strzałek. Rozszerzyć pętlę znaków o `.` i `,`; dla
`Alt`/`Enter`/`↑`/`↓` dodać drobny helper piekący keycap z krótkim tekstem
(`Alt`, `Ent`, `Up`, `Dn`) - pixel font nie ma glifów strzałek (patrz komentarz
w `QuestPanel._draw_marker` o braku `✔`/`●`).

### 6. i18n (`project/assets/locale/PL.toml`, `EN.toml`)

Nowa sekcja `[help]`: tytuł panelu, tytuły grup (`ruch`, `interakcja`,
`ekwipunek`, `mysz`, `system`, `okna`, `debug`) i opisy wierszy. Styl PL/EN
spójny z istniejącą sekcją `[action]`. Zachować blank line po nagłówku sekcji
(reguły markdown/TOML usera).

## Pliki do zmiany

- `project/ui/panels/help.py` - **nowy** panel modalny.
- `project/ui/game_ui.py` - rejestracja modala + obsługa input/toggle.
- `project/scene.py` - usunięcie starego toggle; rozszerzenie `generate_icons`.
- `project/ui/panels/hud.py` - usunięcie starego renderera; poprawka guardu podpowiedzi.
- `project/assets/locale/PL.toml`, `EN.toml` - sekcja `[help]`.
- `doc/_attachements/help-panel-<data>.html` - **nowy** mock (spec layoutu).

## Weryfikacja

1. `just run` (desktop). Wcisnąć `H`:
   - Panel wyśrodkowany, duży, wszystkie grupy widoczne bez scrollowania.
   - Świat zamrożony: potwór obok nie rusza się i nie atakuje; licznik czasu gry
     stoi; wcisnąć kierunek - gracz się nie porusza.
   - `H`/`F1`/`Esc`/`Q` zamyka panel; świat wznawia bez "wycieku" klawisza
     (Esc nie otwiera menu przy zamknięciu).
2. Skróty debug: bez debug overlay sekcja "Debug" niewidoczna; po `` ` ``/`Z`
   (włącza `SHOW_DEBUG_INFO`) i ponownym `H` - sekcja "Debug" obecna.
3. Weryfikacja web: `USE_WEB_SIMULATOR = True` w `settings.py` (lub build pygbag),
   `H` - brak sekcji Debug, brak wierszy `F5`/`F9`/reload.
4. Wizualnie porównać z mockiem HTML (kolumny, paleta, wyrównanie ikon).
5. Skill `verify` do przejścia flow end-to-end (otwórz/zamknij, freeze, sekcja debug).
