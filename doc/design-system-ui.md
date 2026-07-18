# Design System UI dla MoM - audyt + dokument zasad

> Pełny audyt z próbkami palety, zrzutami pięciu ekranów i interaktywną tabelą decyzji:
> [`_attachements/design-system-2026-07-18.html`](_attachements/design-system-2026-07-18.html)
> (podgląd: `docserve start doc/_attachements/design-system-2026-07-18.html`).
> Zwięzłe zasady dla agentów: [`../project/ui/AGENTS.md`](../project/ui/AGENTS.md).

## Context

Gra (top-down RPG, Pygame-CE, dual-target desktop + web) udaje "retro pixel-art w
niskiej rozdzielczości", ale realnie renderuje **cały canvas (świat + UI) w logicznej
rozdzielczości 1280x720**, po czym skaluje go jako jeden obraz do fizycznej
rozdzielczości ekranu (`project/settings.py:266-269`, `SCALE`). UI powstawało panel po
panelu, więc każdy ekran wprowadził własne kolory, własny sposób rysowania klawiszy i
własne zasady cienia. Efekt: chwilami widać, że "niska rozdzielczość" jest udawana
(cienkie linie 1px, ułamkowe skalowanie), a te same elementy wyglądają inaczej na
różnych ekranach.

**Zakres tego przejścia (decyzja użytkownika): TYLKO dokument + decyzje.** Żadnych zmian
w kodzie UI. Rezultatem są dokumenty design-systemu; refaktory kodu to osobne, późniejsze
zadania (spisane tu jako backlog decyzji).

**Dwie zasady nadrzędne:**

1. **Nie zdradzać, że pixel-art jest skalowany.** Skalowanie = potęga dwójki, minimum
   liczba parzysta. Wyjątek tylko czcionka. Linie 1px na panelach - do poprawy.
2. **Te same komponenty wszędzie.** Jeden sposób na "klawisz", jeden na cień, jedna
   paleta, jeden minimalny rozmiar czcionki.

## Zebrany materiał (świeże screenshoty)

Zrzuty z realnej gry (headless, kanał `agent_ctrl`) w `screenshots/agent/`:

- `agent_audit_01_main_menu.png` - menu główne
- `agent_audit_02_gameplay.png` - mapa + HUD + hotbar + przyciski akcji
- `agent_audit_03_quest_panel.png` - dziennik zadań (J)
- `agent_audit_04_help_panel.png` - panel pomocy (H)
- `agent_audit_dlg_02_dlg_b.png` - dialog z Barmanem (realny in-game)
- `screenshots/_dialog.png` - dialog demo (referencja: ciemny panel + portrety)

## Decyzje podjęte z użytkownikiem

- **Komponent klawisza = zawsze SPRITE** (pixel-art). Retro-native, spójny z HUD.
  Wektorowe chipy z panelu pomocy i tekstowe klawisze (nagłówek pomocy, stopka questów,
  prefiks "(F)" w dialogu) zostają **wycofane** na rzecz sprite'ów `hud.icons["key_*"]`.
  Użytkownik dorysuje brakujące sprite'y w Aseprite (lista niżej).
- **Cień = model questów** (tylko chrome). Użytkownik: "wolę jak w questach".
- **Dokumenty:** zwięzły `project/ui/AGENTS.md` (zasady) + szczegółowy HTML w
  `doc/_attachements/` (audyt, próbki palety, before/after, inwentarz klawiszy). Ten plan
  trafia do `doc/` z linkiem do HTML.

## Inwentarz komponentu "klawisz" - stan i brakujące sprite'y

System działa dwuwarstwowo:

- **Ręcznie rysowany arkusz** (`HUD_SHEET_DEFINITION`, `settings.py:870`, skala 2 → 32px):
  `key` (pusty), `key_Esc/Tab/Ctl/Alt/Enter/Shift/Space`, `mouse_LMB/RMB`.
- **Generowane w runtime** (`scene.py:277 generate_icons`) - glif nabity na pusty `key`:
  A-Z, cyfry 0-8, F1-F12, znaki `< > \` [ ] + -`.

Panel pomocy używa dziś **rysowanych chipów** i **trójkątów** zamiast tych sprite'ów -
to jest właśnie rozjazd do usunięcia. Po zestawieniu wszystkich klawiszy UI z pokryciem:

### Brakujące sprite'y (do dorysowania w Aseprite)

**MUSZĄ być rysowane ręcznie** (pixel font nie ma glifu - dlatego pomoc udaje je
trójkątami):

- `key_up` (↑), `key_down` (↓), `key_left` (←), `key_right` (→) - 4 klawisze strzałek.

**Można dogenerować kodem** (dopisać do `generate_icons`) - opcjonalnie ładniejsze jako
ręczny art, ale nie trzeba:

- `key_,` (przecinek), `key_.` (kropka) - używane w wierszu "przełącz przedmiot".
  Wystarczy rozszerzyć string znaków `"<>\`[]+-"` o `,.`.
- `key_9` (cyfra 9) - `generate_icons` ma `range(0, 9)` (0-8), brak 9 (latentny brak,
  nieużywany w pomocy). Fix: `range(0, 10)`.

Separatory `/` i `-` między klawiszami zostają zwykłym tekstem (to interpunkcja, nie
klawisz). Mysz `LMB/RMB` ma sprite'y. Reszta klawiszy pomocy w pełni pokryta.

## Audyt odstępstw - tabela decyzji (do backlogu)

Legenda: **FIX** = zmiana w kodzie (osobne zadanie), **DOC** = zasada do zapisania.

### A. Komponent "klawisz" - 3 warianty → 1 (sprite)

Sprite (HUD hotbar/broń/przyciski akcji) vs chip rysowany (ciało pomocy) vs tekst
(nagłówek pomocy, stopka questów, "(F)" w dialogu). **FIX:** wszędzie sprite
`hud.icons["key_*"]`; usunąć `help._draw_cap` i `_draw_arrow`, zamienić tekstowe klawisze
w stopce questów i dialogu na sprite'y. Wymaga 4 sprite'ów strzałek (wyżej).

### B. Cień tekstu - niespójny → model questów

- Questy: cień tylko na chromie (tytuł/etykiety/stopka), proza bez (`quest._text`).
- Pomoc: cień na **wszystkim** (`help._text` zawsze `border=PANEL_BG_COLOR`).
- Dialog: własny cień rich-text `(130,32,32)`.

**FIX:** `help._text` dostaje parametr `shadow` jak `quest._text`; cień włączony tylko na
nagłówku i tytułach sekcji.

### C. Paleta - zduplikowana literalnie

- `(255,252,103)` żółty tytułowy = `CHAR_NAME_COLOR` = `quest._TITLE` = `help._TITLE_COL`
  (3 definicje tego samego).
- `_GOLD (255,215,0)`, `_GREY (170,170,164)`, `_RULE (68,68,68)`,
  `_MANUAL`/`_ORANGE (232,146,12)`, `_WHITE` - osobno w `quest.py` i `help.py` (identyczne).
- `_DIVIDER (70,64,46)` - osobno w `inventory.py` i `trade.py`.
- `dialog.py` ma własny zestaw (`_OPTION_HIGHLIGHT`, `_SEPARATOR`, `_VISITED_BG`).

**FIX:** jedna paleta w `theme.py` (nazwane tokeny), panele importują z jednego miejsca;
`settings.CHAR_NAME_COLOR` re-eksport z tokenu.

### D. Skalowanie / "zdradzanie pixel-artu"

| Odstępstwo | Gdzie | Decyzja |
|---|---|---|
| Linie 1px | `help._draw_cap` `width=1`, `quest._draw_marker` `width=1` | **FIX** min. 2px; jednostka bazowa UI = 2px logiczne |
| `border_radius=4` na chipach/paskach | help, quest | **DOC/FIX** zaokrąglenie łamie pixel-grid; 0 lub wielokrotność jednostki |
| `UI_BORDER_WIDTH = 9` (nieparzyste) | `settings.py:398` | **FIX** 8 lub 10 |
| Ułamkowe skalowanie canvasu (SCALE 1.5 @1080p, 0.8 w test-env → letterbox, miękkie krawędzie) | `DISPLAY_RES_OPTIONS` | **DOC** udokumentować ryzyko; preferować całkowite krotności (1280x720 → 2560x1440 = 2x) |
| `nine_patch` scale=4, border=6 | `theme.py:73` | **DOC** wzorzec (parzyste, OK) |

### E. Minimalny rozmiar czcionki

Pixel font `[8, 10, 14, 16, 24, 155]`. Licznik questów w TINY=10. **DOC:** chrome min
**10px**, treść czytelna min **14px**, `FONT_SIZE_EXTRA_TINY=8` **wycofać z UI**
(nieczytelny po ułamkowym downscale).

### F. Panele - dobre praktyki do utrwalenia

- Questy i pomoc: ten sam nine-patch olive (`nine_patch_04.png`) - **DOC** wzorzec.
- Dialog: inny ciemny nine-patch - **DOC** świadomy wyjątek (inna warstwa + portrety).
- Reguły (`_RULE`, 2px) spójne quest↔pomoc - **DOC** (kolor do palety).
- Tag nazwy mówcy w dialogu (nine-patch zakładka, żółty tekst) - **DOC** komponent
  `name_tag`. (Uwaga: na `dlg_b` widać dwa nachodzące tagi - drobny bug, osobne zgłoszenie.)

## Deliverables (utworzone w tym przejściu)

1. **`project/ui/AGENTS.md`** - zwięzłe zasady tworzenia nowego UI (paleta, jednostka 2px,
   skalowanie parzyste, komponent klawisza = sprite, cień chrome-only, min. font).
   Podlinkowany z `project/AGENTS.md` (sekcja „Toolkit UI").
2. **`doc/_attachements/design-system-2026-07-18.html`** - pełny audyt (styl html-craft):
   próbki palety klikalne (hex), tabela decyzji A-F, inwentarz klawiszy + lista braków,
   zrzuty pięciu ekranów osadzone w pliku (self-contained).
3. **`doc/design-system-ui.md`** - ten dokument (plan + decyzje) z linkiem do HTML.

## Backlog implementacji (przyszłe zadania FIX)

Kolejność wg ryzyka - najpierw bezpieczne, mechaniczne:

1. **Paleta → `theme.py`** (C) - tokeny + podmiana literałów; 0 zmian wizualnych.
2. **Cień pomocy → model questów** (B).
3. **Linie 1px → 2px, `UI_BORDER_WIDTH` 9→8** (D).
4. **Komponent klawisza = sprite wszędzie** (A) - główna zmiana wizualna; wymaga 4
   sprite'ów strzałek od użytkownika + drobny fix `generate_icons` (`,` `.` `9`).
5. **Role fontów + wycofanie EXTRA_TINY z UI** (E).

Pliki kodu do dotknięcia w przyszłych zadaniach: `theme.py`, `help.py`, `quest.py`,
`settings.py`, `scene.py`, `dialog.py`, `inventory.py`, `trade.py` - **nietykane w tym
przejściu**.

## Weryfikacja

- HTML otworzyć podglądem (`docserve start doc/_attachements/design-system-2026-07-18.html`)
  i sprawdzić czytelność swatchy palety oraz tabel na laptopie przez tailnet.
- Sanity: hex-e w palecie zgadzają się z realnymi wartościami w kodzie (np.
  `CHAR_NAME_COLOR (255,252,103)` = `#FFFC67`).
