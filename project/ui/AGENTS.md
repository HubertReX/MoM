# AGENTS.md — UI / Design System

Zasady tworzenia i utrzymania UI gry. Pełny audyt z próbkami palety, zrzutami pięciu
ekranów i tabelą decyzji: [`doc/_attachements/design-system-2026-07-18.html`](../../doc/_attachements/design-system-2026-07-18.html)
(podgląd: `docserve start doc/_attachements/design-system-2026-07-18.html`).

## Dwie zasady nadrzędne

1. **Nie zdradzać pixel-artu.** Canvas nie jest skalowany: `settings.SCALE == 1.0` zawsze,
   a finalny blit to 1:1 - wyższa rozdzielczość daje **większy viewport**, nie powiększony
   obraz (patrz "Złota zasada: pixel-perfect rendering" w [root `AGENTS.md`](../../AGENTS.md)).
   Skalowanie dotyczy więc pojedynczych elementów, nie całości: sprite'y i ikony UI
   powiększaj **wyłącznie o całkowity mnożnik** (najlepiej potęgę dwójki) - mnożnik ułamkowy
   duplikuje część rzędów pikseli i element wygląda na zniekształcony. Jedyny sankcjonowany
   wyjątek to czcionka.
2. **Te same komponenty wszędzie.** Jeden sposób na „klawisz", jeden na cień, jedna paleta,
   jeden minimalny rozmiar czcionki.

## Paleta

- **Jedno źródło prawdy** — kolory z nazwanych tokenów w `theme.py`, nigdy literały RGB w
  panelu. Jeśli tokenu brakuje, dodaj go do `theme.py`, nie kopiuj wartości.
- Kluczowe tokeny (hex): `TITLE #FFFC67`, `WHITE #FBF7EC` (ivory), `GREY #ADA898`,
  `GOLD #FFD700`, `ACCENT_CYAN #00C5C7`, `DONE #5FFA68` (= RichText `loc`), `WARN #E8920C`,
  `RULE`/`DIVIDER #4A4636` (jeden ciepły token), `PANEL_BG #1E1E1E`, `INK #111111`
  (ramka HUD + `BAR_BG`). Neutrale ocieplone do tonu oliwkowej palety (2026-07-19).
- `settings.CHAR_NAME_COLOR` to ten sam żółty co `TITLE`; `DONE` = RichText `loc`;
  `char` = `TITLE`, `text` = `ACCENT_CYAN` — trzymać jako aliasy, nie drugie definicje.
- Kolory RichText (tagi tekstu) w `STYLE_TAGS_DICT` (`settings.py`): `act #FF6E68`,
  `char #FFFC67`, `item #6871FF`, `loc #5FFA68`, `num #FF77FF`, `quest #60FDFF`,
  `text #00C5C7`, `error #DF394C` (error = debug, celowo krzykliwy).
- `CAP_BG`/`CAP_EDGE` **wycofane** (martwe po przejściu na sprite-keycapy).

## Skalowanie i geometria

- **Bazowa jednostka UI = 2px logiczne.** Grubości linii, odstępy i rozmiary elementów =
  wielokrotność 2px (lepiej 4px). Żadnych linii 1px na panelach.
- Zaokrąglenia (`border_radius`) łamią pixel-grid — 0 albo wielokrotność jednostki.
- Panel standardowy = nine-patch (`theme.nine_patch`, `nine_patch_04.png`, scale 4,
  border 6). Sprite'y i nine-patch skaluj parzyście (×2, ×4).
- Rozdzielczość ekranu nie skaluje obrazu — zmienia rozmiar viewportu (więcej kafelków).
  Nie ma więc „skali ułamkowej całego canvasa", której trzeba unikać; reguła integer
  scale dotyczy pojedynczych sprite'ów i kształtów (punkty niżej).
- **Ikony pixel-art (emoji/emote/przedmioty) skaluj tylko całkowitą krotnością.** Źródła są
  małe (emote 14×13, przedmioty 16×16); rozciąganie ułamkowe (np. `target_h / src_h`)
  dubluje część rzędów/kolumn i ikona wygląda na zniekształconą. Wzór: `k = max(1,
  round(target_h / src_h))`, potem `pygame.transform.scale_by(src, k)` (helper
  `_icon_factor` w `rich_text.py`). Jeśli natywny rozmiar jest za mały — przerysuj asset w
  wyższej rozdzielczości, nie skaluj ułamkowo.
- **Kształty proceduralne (paski, ramki, zaokrąglenia) rysuj metodą nine-patch: model w
  natywnej siatce → integer scale (nearest).** Zamiast rysować cienkie 1–2px detale wprost
  w rozdzielczości ekranu (przy natywnym 1:1 wychodzą wątłe, „za cienkie", nie widać
  grubych pikseli), zbuduj kształt w małej **natywnej** siatce (jak asset źródłowy) i
  powiększ **całkowitą krotnością** `pygame.transform.scale` (nearest-neighbour). Wtedy każdy
  natywny piksel = blok `k×k`, a kańciaste zaokrąglone końce zachowują proporcje. Tylko
  środkowe, jednolite sekcje wolno rozciągać (długość paska) — narożniki/końcówki są stałe
  (`k × liczba_natywnych_rzędów`). Wzorzec referencyjny: `ui/widgets/bar.py` (siatka natywna
  **wczytana ze `scrollbar.png`**, `k = round(cross/8)`, min 2 — sekcja „Suwak i pasek postępu"
  niżej). Ta sama zasada co przy nine-patch panelu. **Lepiej niż rysować kształt w kodzie:
  narysuj go w Aseprite i sparsuj** — wtedy wygląd jest w assecie, a nie w stałych.

## Panel musi się zmieścić w viewporcie (i w każdym języku)

- **Rozmiar panelu to MAKSIMUM, nie stała.** Rozdzielczość zmienia rozmiar viewportu
  (patrz „Skalowanie i geometria"), więc panel o zaszytej szerokości prędzej czy później
  wystaje poza ekran - `help.py` przy 1120 px zwisał po ~48 px z **obu** krawędzi przy
  1024×720. Wzorzec: `PANEL_W = min(_DESIGN_W, settings.WIDTH - 2 * _MIN_MARGIN)`
  (analogicznie wysokość), a **cała reszta geometrii liczona z tego** w
  `_recompute_geometry()` wołanym w `__init__` i w `open()`. Jeśli rozmiar panelu może się
  zmienić, w `open()` przebuduj też nine-patch tła - samo przesunięcie `rect` zostawia
  tło w starym rozmiarze (`theme.nine_patch` jest cache'owany per rozmiar, więc to darmowe).
- **Szerokości kolumn mierz z fontu, nie zgaduj.** Najdłuższy opis zależy od **języka**:
  polskie „Rozmawiaj / otwórz / atakuj" ma 378 px i po cichu wychodziło poza swój slot
  341 px. Licz zapotrzebowanie kolumny z `theme.measure(...)` po realnych stringach
  (`help.py` `_measure_columns`), a szerokość ikon klawiszy - funkcją bliźniaczą do tej,
  która je rysuje (`_keys_width` vs `_draw_keys`), żeby nie mogły się rozjechać.
- **Za wąsko = mniej kolumn, nie ciaśniejsze kolumny.** Gdy dwie kolumny się nie mieszczą,
  ułóż je jedna pod drugą w jednej kolumnie i pozwól `ScrollView` przewijać - przewijanie
  to legalny nadmiar, przycinanie tekstu nie jest. Gdy nie mieści się nawet jedna, zgłoś
  `layout.report_violation(..., "h-overflow", ...)`; **nigdy nie clampuj, żeby ukryć problem**.

## Komponent „klawisz" (hotkey) — zawsze sprite

- Klawisze rysuj przez współdzielony moduł **`ui/keycap.py`** (nie duplikuj logiki):
  - `keycap.build_cap(icons, token, glyph_font, glyph_color)` → keycap 32px (natywny sprite);
  - `keycap.render_hint(surface, icons, glyph_font, text_font, text, pos, color, ...)` →
    inline wiersz mieszający keycapy i tekst ze składni `{TOKEN}` (hinty nawigacji: nagłówek
    pomocy `close_hint`, stopka questów `hints`).
  **Nie** rysuj wektorowych chipów ani nie wypisuj klawisza tekstem. Panel pomocy i hinty
  nawigacji pomocy/questów są już na sprite'ach (dawne `_draw_cap`/`_draw_arrow` usunięte).
- Sprite'y powstają dwuwarstwowo:
  - ręczny arkusz `HUD_SHEET_DEFINITION` (`settings.py:870`): `key` (pusty), `Esc`, `Tab`,
    `Ctl`, `Alt`, `Enter`, `Shift`, `Space`, `mouse_LMB`, `mouse_RMB`;
  - generowane w `generate_icons()` (`scene.py:277`): A–Z, cyfry 0–9, F1–F12, znaki
    `< > \` [ ] + - , .` (glif na pustym `key`).
    Strzałki `up/down/left/right` mają **ręczny art w arkuszu** (rząd 2
    `HUD_SHEET_DEFINITION`), nie są już generowane w kodzie.
- **Nowy klawisz z literą/cyfrą/F-em/znakiem** — dodaj do `generate_icons` (glif na pustym
  `key`). **Nowy klawisz bez glifu w foncie** (np. strzałki) — ręczny art w arkuszu `HUD.png`.
- **Kontrast:** lico wszystkich kafli (`key` i kafle nazwane) jest **przyciemnione wprost
  w arkuszu `HUD.png`**, żeby **biały** glif był czytelny — bez mnożenia w kodzie.
- **Rozmiar:** keycapy renderuj w natywnym **32px** (`scale=1.0`, domyślnie) — wszędzie,
  także w gęstych panelach. Skalowanie w dół do 16px było nieczytelne i jest zabronione.
  Capy jednoznakowe renderuj świeżym glifem na `key` (ostrość); wieloznakowe / mysz /
  strzałki reużywają arta sprite'a 1:1.
- Separatory między klawiszami zostają tekstem/kształtem, nie keycapem: `/` („lub") to
  szary glif w **większym foncie** (`FONT_SIZE_LARGE`), proporcjonalny do keycapów 32px
  (parametr `sep_font` w `keycap.render_hint`); zakres (`1–6`) to krótka szara kreska
  (en-dash `–` w danych, rysowany jako prostokąt). Uwaga: ASCII `-` to realny klawisz
  (zoom out), więc **nie** jest separatorem.

## Skróty w stopce panelu

- **Skróty klawiszowe panelu idą do stopki** (nad dolną krawędzią, pod linią działową),
  nie do nagłówka. Wzorzec: linia `RULE` + wiersz `keycap.render_hint` (patrz
  `help.py` `_draw_footer`, `quest.py` stopka). Lewa strona = zamknięcie/akcje, prawa =
  hinty kontekstowe (np. `↑ / ↓ przewiń`, pokazywane tylko gdy jest co scrollować).
- Dodatkowo scroll kółkiem myszy (obsługa w `game_ui.py`, celowo poza listą skrótów).

## Suwak i pasek postępu — jeden komponent `ui/widgets/bar.py`

- **Wszystkie suwaki i paski postępu** rysuje współdzielony moduł **`ui/widgets/bar.py`**
  (styl jak `keycap.py` — funkcje, nie klasa). Nie duplikuj rysowania paska, nie używaj
  `pygame.draw.rect(border_radius=)` (antyaliasuje → gładka krzywa, **zdradza pixel-art**).
- **Asset jest źródłem wyglądu, nie referencją (U01).** `assets/NinjaAdventure/HUD/scrollbar.png`
  (8×16) jest **wczytywany i parsowany na starcie** (`bar.load_model()` w `game.py`, tuż po
  `set_display()`), a każdy piksel narysowanego paska pochodzi z niego. Przemalowanie sprite'a
  w Aseprite + restart gry = inny wygląd wszystkich suwaków. W kodzie **nie ma** zaszytego
  modelu kształtu (ani grubości ramki, ani profilu końcówek).
- **Kolor = rola.** Każdy piksel musi być **dokładnie** tokenem `theme.py`; piksel spoza palety
  (albo półprzezroczysty) to **twardy błąd ładowania** z podaniem współrzędnych i koloru —
  sygnał, że asset i paleta się rozjechały. Mapowanie ról:

  | kolor w sprite | token | rola |
  |---|---|---|
  | `#111111` | `INK` | ramka |
  | `#4A4636` | `RULE` | pusty track (rowek) |
  | `#FFD700` | `GOLD` | ciało wypełnienia |
  | `#E8920C` | `WARN` | ciemny bevel (krawędź wiodąca) |
  | `#FFFC67` | `TITLE` | jasny bevel (krawędź przeciwna) |
  | alfa 0 | — | poza kształtem |

- **Podmiana palety (color-swap), nie rodzina sprite'ów.** Przy rysowaniu role `fill`/`dark`/
  `light` dostają kolory z argumentów (`fill=`, `bevel=`), role `frame`/`track` zostają
  tokenami. Dlatego jeden sprite obsługuje pasek sentymentu (czerwony→zielony) — patrz punkt
  o kolorze zmiennym niżej.
- **Struktura jest parsowana, nie zakładana.** Skrajne, w pełni przezroczyste rzędy są
  obcinane (oś główna jest tą rozciąganą), potem rzędy dzielą się na: stałą czapkę wiodącą,
  **rozciągany rząd korpusu** (ten z najszerszym rowkiem) i stałą czapkę końcową — zasada
  nine-patch z „kształtów proceduralnych" wyżej, zastosowana wzdłuż jednej osi. Sprite
  **pokazuje też własne stany** (kciuk u góry), więc wzorce wnętrza czyta się z niego:
  rząd w pełni wypełniony (`dark, fill, fill, light`) i rząd zaokrąglonego końca wypełnienia
  (`track, fill, fill, track`). Wszystkie rzędy korpusu muszą mieć ten sam profil ramki/rowka.
- **Skala: `k = round(cross / szerokość_sprite'a)`, min 4** → integer scale (nearest).
  Czwórka nie jest przypadkowa: pasek życia w HUD (`LifeBarMini*.png`) jest skalowany
  `INVENTORY_ITEM_SCALE = 4`, więc dopiero przy `k=4` blok piksela suwaka jest ten sam co
  paska życia i oba czyta się jako jeden design (przy `k=2` suwak wyglądał na drobniejszy).
  Skaluje się do dowolnej długości, działa **pionowo i poziomo** (wariant poziomy to
  transpozycja: `flip` + `rotate(90)`).
- **Test kontraktu:** `tests/test_bar_asset.py` — wysłany sprite **odtwarza sam siebie
  piksel w piksel** (render jego własnego stanu == plik), piksel spoza palety = czytelny
  `ValueError`, a przemalowanie ramki zmienia narysowany pasek. Jeśli zmieniasz asset i ten
  test pada na „reprodukcji", to zwykle znak, że sprite przestał pokazywać pełne wypełnienie
  (bevele nie mają skąd być odczytane) — nie „napraw" testu, domaluj stan w sprite.
- **API:** `bar.draw_scrollbar(surface, rect, *, frac_visible, frac_pos, vertical=True,
  fill=GOLD, bevel=(WARN,TITLE))` — track + beveled thumb; `bar.draw_progress(surface,
  rect, fraction, *, vertical=False, fill=ACCENT_CYAN, bevel=None)` — track + wypełnienie
  od początku do `fraction`. Progressbar to **szczególny przypadek** suwaka (ta sama
  kapsuła i bevel). Domyślne `bevel=(WARN,TITLE)` na `fill=GOLD` odtwarza asset 1:1.
- **Kolor zmienny (np. sentyment) → filtr, nie sprite'y.** Podaj `fill=<liczony kolor>` z
  `bevel=None` — komponent **wyprowadza** bevel z koloru (ciemna = fill×0.6, jasna = blend
  do bieli). Jeden komponent pokrywa każdy odcień, bez rodziny sprite'ów.
- **Miejsca użycia:** panel pomocy (`help.py`), suwak przewijalnego `RichText`
  (`rich_text.py` — m.in. kwestia NPC), suwak opcji dialogu i pasek sentymentu
  (`dialog.py`), postęp `all_subquests` w questach (`quest.py` KROKI). Suwaki i paski
  rysuj **wymiarem poprzecznym 32 px** (wielokrotność 8 px sprite'a → `k=4`). 16 px prosi
  o `k=2`, ale zostanie narysowane w 4× i **wyjdzie poza swój slot** — a wizualnie
  rozjedzie się z paskiem życia w HUD.
- `theme.draw_pixel_round_rect` zostaje osobnym prymitywem dla innych kańciastych
  zaokrągleń (nie jest już używany przez `bar.py`, który idzie ścieżką natywna+integer-scale).

## Przewijalny obszar — jeden komponent `ui/widgets/scroll_view.py`

- **Każdy obszar, który może być wyższy niż jego ramka** (details questa, długa kolumna
  pomocy, ściana prozy dialogu), rysuj przez współdzielony **`ScrollView`** — nie
  przepisuj w panelu clip-rect + offsetu + clampu + scrollbara od nowa (tak było w
  `help.py` ręcznie, a `quest.py` w ogóle nie miał i nagrody wychodziły za ramkę).
- **Tryb immediate, jak reszta paneli.** Trzymasz instancję na panelu (jedna na obszar) i
  co klatkę wołasz `scroll.draw(surface, viewport, render)`, gdzie
  `render(top_y, width) -> bottom_y` rysuje treść od `top_y` (lewy brzeg = `viewport.left`),
  zawija do `width` i **zwraca** y końca. Z różnicy komponent liczy wysokość treści.
  `ScrollView` robi: **clip** do viewportu, **offset** scrolla + clamp do `[0, max_scroll]`,
  oraz rysuje współdzielony **scrollbar (`bar.py`) tylko gdy treść się nie mieści**.
- **Bez oscylacji reflow.** Kolumna scrollbara jest **rezerwowana z `width` zawsze** (stała
  rynna), nie tylko gdy pasek widoczny — inaczej pojawienie się paska zwężałoby treść,
  zmieniało zawijanie i mogłoby przełączyć overflow z powrotem (migotanie na granicy).
  Kilka pikseli szerokości za stabilność.
- **Wejście:** `scroll_up/down`, `scroll_by(dy)`, `page_or_top()` (SPACJA — stronicowanie
  z zawinięciem do góry na końcu, jak przewijanie kwestii NPC), `handle_wheel(events)`
  (kółko myszy, celowo poza listą skrótów), `reset()` (na `open()` panelu i przy zmianie
  zaznaczenia — każdy element otwiera się od góry). Hint scrolla do stopki **tylko gdy
  `scroll.overflows`** (wzorzec „skróty w stopce”).
- **Miejsca użycia:** panel questów (details, `quest.py`), panel pomocy (dwie kolumny,
  `help.py`). Wzorzec dla kolejnych paneli z przewijaną treścią.

## Cień tekstu — tylko chrome

- Model questów: cień **tylko** na chromie (nagłówki, etykiety sekcji, stopki). Proza i
  glify klawiszy **bez** cienia — pod prozą cień tylko pogrubia litery i psuje czytelność.
- Wzorzec API: `_text(..., shadow=False)` domyślnie, `shadow=True` na furniturze
  (patrz `quest.py` `_text`/`_label`).

## Rozmiary czcionki

- Font pixel: `[8, 10, 14, 16, 24, 155]` (EXTRA_TINY…HUGE).
- **Minimum:** chrome (etykiety, licznik) ≥ **10px** (`TINY`); treść czytana ≥ **14px**
  (`SMALL`). `FONT_SIZE_EXTRA_TINY` (8) **nie używać w UI** — nieczytelne w tym rozmiarze.
- **Tekst w przestrzeni świata vs UI — inne skalowanie.** Powyższe minimum dotyczy
  tekstu **UI**, rysowanego 1:1 na canvasie — tyle pikseli, ile podasz. Tekst
  **wtopiony w sprite świata** (np. imię postaci nad głową w `objects.py`) idzie inną
  ścieżką: jest skalowany kamerą (zoom ~3.8×), więc ten sam rozmiar czcionki wychodzi
  znacznie większy. Dla takich etykiet używaj
  `FONT_SIZE_EXTRA_TINY` (8) — reguła „min 10px" ich nie dotyczy (inna ścieżka renderu).

## Rytm pionowy — komponent „etykieta sekcji"

- **Jeden odstęp etykieta→treść wszędzie.** Etykieta sekcji (WĄTKI / SZCZEGÓŁY / KROKI /
  NAGRODA / grupy pomocy) to `FONT_SIZE_SMALL` (14px), `GREY`, cień chrome. Treść pod nią
  zaczyna się zawsze `theme.SECTION_LABEL_GAP` (18px) **poniżej dolnej krawędzi etykiety**.
- **Wyliczaj z metryki fontu, nie z magicznego offsetu:**
  `content_top = label_top + label_font.get_height() + theme.SECTION_LABEL_GAP`
  (helper `quest.py:_content_y`). Dzięki temu zmiana rozmiaru czcionki etykiety **nie może**
  ścisnąć treści — to był bug, który rozjechał panel questów (prawa kolumna vs lewa).
- **Meta-zasada (dlaczego to się powtarzało):** gdy zmieniasz współdzielony token (rozmiar
  czcionki, kolor, szerokość), **wszystko co wyliczyło z jego starej wartości magiczną liczbę
  po cichu się psuje.** Wartości zależne wyliczaj z tokenu/metryki albo z nazwanej stałej —
  inaczej design system nie ochroni przed rozjazdem. Nie wpisuj „na oko" liczby, która
  zależy od innej stałej.

## Pozostałe wzorce

- Znaczniki stanu (✔ / ● / ○, karety, strzałki) rysuj jako **kształty**, nie glify — pixel
  font ich nie ma i renderuje „tofu".
- Panel dialogu ma świadomie inny, ciemny nine-patch (osobna warstwa: portrety + tag nazwy
  mówcy `name_tag`). To dozwolony wyjątek od panelu standardowego.
- Linie działowe: kolor `RULE`, grubość 2px.

## Layout self-checks — overflow to twardy błąd

Zasady z tego dokumentu były dotąd egzekwowane wyłącznie okiem: „panel za mały na tekst"
i „tekst najeżdża na ramkę" widać było dopiero na screenshocie, a ocena wizualna przez
LLM bywa niedeterministyczna. Widżety **znają** swoją geometrię, więc detekcja jest w 100%
pewna — rejestr naruszeń mieszka w `ui/layout.py`.

**Ten mechanizm tylko mierzy i raportuje.** Nigdy nie przycina, nie clampuje i nie
„naprawia" layoutu. Naruszenie to błąd do naprawienia u źródła, nie coś do zaklejenia tutaj.

### Jak zgłaszać

```python
from .. import layout

layout.report_violation("DialogPanel(option 3)", "outside-panel", "opis co i o ile wystaje")
layout.check_inside("QuestPanel(details)", viewport, panel_inner)  # gotowy helper
```

Rodzaje (`kind`) w użyciu:

| kind | znaczenie |
|---|---|
| `h-overflow` | najdłuższa linia szersza niż obszar — nierozrywalne słowo lub ikona inline, których zawijanie nie uratuje |
| `v-overflow` | treść wyższa niż obszar **i brak paska przewijania** |
| `clipped` | `Label` z rectem mniejszym niż jego tekst (ktoś nadpisał `rect.size` po `_relayout`) |
| `outside-panel` | sekcja treści wystaje poza wewnętrzny obszar panelu (rect panelu minus ramka) |

### Scroll = legalny nadmiar

Treść wyższa niż okno **nie jest** naruszeniem, jeśli da się ją przewinąć — to zaprojektowane
zachowanie `ScrollView` i `RichText(show_scrollbar=True)`. Dlatego `v-overflow` zgłasza się
tylko przy `show_scrollbar=False`.

### Mierz przy layoucie, raportuj przy rysowaniu

`RichText` liczy naruszenia w `_bake()`, ale zgłasza je dopiero w `draw()`. Powód: część
instancji `RichText` powstaje **wyłącznie do pomiaru** (`render_static()` w toastach HUD,
binarne szukanie długości linii w `quest.py`) i nigdy nie trafia na ekran — bez tego
rozdziału pośrednie kandydatury sypałyby fałszywymi alarmami.

### Deduplikacja i reset

`report_violation` zapamiętuje `(widget, kind)` i loguje raz na sesję — checki siedzą na
ścieżce rysowania, więc bez tego log rósłby o linię na klatkę. `reset_violations()` wołane
jest tam, gdzie geometria legalnie się zmienia: przy zmianie rozdzielczości (`game.py`,
`set_display`) i w `GameUI.reset()`.

### Jak czytać wyniki

- w logu gry: linie `[layout] <kind> in <widget>: <detail>`
- w testach agentowych: komenda `debug_ui_state` wkłada listę do pola `layout_violations`,
  a asercja `{"type": "no_layout_violations"}` twardo pada, gdy lista jest niepusta
- testy jednostkowe mechanizmu: `tests/test_layout_checks.py`

Nowy panel? Jeśli rysujesz sekcje sam (bez `RichText`/`Label`), dopisz `layout.check_inside`
po złożeniu layoutu — wzorzec w `panels/dialog.py` (`_check_layout`) i `panels/quest.py`.

## Zmiana języka w locie (i18n)

- **Nigdy nie importuj `LANG` przez wartość** (`from settings import LANG`). To wiązanie
  utrwala wartość z chwili importu i nie widzi późniejszych `settings.LANG = ...`. Każdy
  moduł reagujący na zmianę języka w locie musi czytać `settings.LANG` na żywo (przez
  `import settings`). Ta sama pułapka co przy `WIDTH/HEIGHT` — czytaj atrybut modułu, nie
  jego kopię.
- Panele budują etykiety przez `_()` w konstruktorze, więc **nie odświeżają się same** po
  zmianie języka. `MenuScreen.update` wykrywa zmianę (`settings.LANG != self._last_lang`)
  i woła `panel.rebuild_i18n()`. Każdy panel osadzony w `MenuScreen` musi mieć
  `rebuild_i18n()`, inaczej ten kod rzuci `AttributeError`.
- `rebuild_i18n()` musi odświeżyć **wszystko** zbudowane z `_()`: etykiety przycisków,
  linie tekstu **oraz tytuł** (`_title_surf` renderowany raz w `__init__` to najczęstsza
  luka — patrz bug „nagłówek Settings nie zmienia języka").
- Menu buforowane na stosie stanów (np. `MainMenuScreen` pod `SettingsMenu`) nie odświeży
  się dopóki nie wróci na wierzch stosu — `update` biegnie tylko dla `states[-1]`. Odświeża
  je pierwsza klatka `update` po powrocie (dlatego działa też świeżo zbudowane menu).

## Dual-target desktop + web

Każdy komponent UI musi działać w obu trybach (patrz [`../AGENTS.md`](../AGENTS.md) i
[`../../AGENTS.md`](../../AGENTS.md)). Web nie ma Pydantic i ma inny model konfiguracji —
zmiany w `config_model` łatwo rozjeżdżają się między web a desktopem.
