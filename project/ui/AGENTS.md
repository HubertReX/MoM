# AGENTS.md — UI / Design System

Zasady tworzenia i utrzymania UI gry. Pełny audyt z próbkami palety, zrzutami pięciu
ekranów i tabelą decyzji: [`doc/_attachements/design-system-2026-07-18.html`](../../doc/_attachements/design-system-2026-07-18.html)
(podgląd: `docserve start doc/_attachements/design-system-2026-07-18.html`).

## Dwie zasady nadrzędne

1. **Nie zdradzać, że pixel-art jest skalowany.** Gra renderuje cały canvas (świat + UI) w
   logicznej rozdzielczości 1280×720, po czym skaluje go jako jeden obraz
   (`settings.py:266-269`, `SCALE`). Elementy UI skaluj **parzyście** (najlepiej potęgą
   dwójki). Jedyny sankcjonowany wyjątek to czcionka.
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
- Rozdzielczość ekranu — preferuj całkowite krotności bazy (1280×720 → 2560×1440 = ×2).
  Skala ułamkowa (1920×1080 → ×1.5) daje miękkie krawędzie; unikać dla nowych opcji.
- **Ikony pixel-art (emoji/emote/przedmioty) skaluj tylko całkowitą krotnością.** Źródła są
  małe (emote 14×13, przedmioty 16×16); rozciąganie ułamkowe (np. `target_h / src_h`)
  dubluje część rzędów/kolumn i ikona wygląda na zniekształconą. Wzór: `k = max(1,
  round(target_h / src_h))`, potem `pygame.transform.scale_by(src, k)` (helper
  `_icon_factor` w `rich_text.py`). Jeśli natywny rozmiar jest za mały — przerysuj asset w
  wyższej rozdzielczości, nie skaluj ułamkowo.

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
- Scrollbar paneli: **gruby** pionowy pasek (`help.py` `_draw_scrollbar`) — szary track +
  złoty thumb — z zaokrąglonymi końcami, ale **schodkowo/kańciasto** (nie gładkie AA):
  helper `theme.draw_pixel_round_rect` rysuje rogi z pełnych pikseli, tak jak wyglądałby
  nisko-rozdzielczy kształt powiększony nearest-neighbour. **Nie** używać
  `pygame.draw.rect(border_radius=)` (antyaliasuje → gładka krzywa, zdradza pixel-art).
  Dodatkowo scroll kółkiem myszy (obsługa w `game_ui.py`, celowo poza listą skrótów).

## Cień tekstu — tylko chrome

- Model questów: cień **tylko** na chromie (nagłówki, etykiety sekcji, stopki). Proza i
  glify klawiszy **bez** cienia — pod prozą cień tylko pogrubia litery i psuje czytelność.
- Wzorzec API: `_text(..., shadow=False)` domyślnie, `shadow=True` na furniturze
  (patrz `quest.py` `_text`/`_label`).

## Rozmiary czcionki

- Font pixel: `[8, 10, 14, 16, 24, 155]` (EXTRA_TINY…HUGE).
- **Minimum:** chrome (etykiety, licznik) ≥ **10px** (`TINY`); treść czytana ≥ **14px**
  (`SMALL`). `FONT_SIZE_EXTRA_TINY` (8) **nie używać w UI** — nieczytelne po downscale.
- **Tekst w przestrzeni świata vs UI — inne skalowanie.** Powyższe minimum dotyczy
  tekstu **UI** (rysowanego w logicznej rozdzielczości 1280×720 canvasu, potem
  downscale przez `SCALE`). Tekst **wtopiony w sprite świata** (np. imię postaci nad
  głową w `objects.py`) NIE jest downscalowany — jest skalowany kamerą (zoom ~3.8×), więc
  ten sam rozmiar czcionki wychodzi znacznie większy. Dla takich etykiet używaj
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

## Dual-target desktop + web

Każdy komponent UI musi działać w obu trybach (patrz [`../AGENTS.md`](../AGENTS.md) i
[`../../AGENTS.md`](../../AGENTS.md)). Web nie ma Pydantic i ma inny model konfiguracji —
zmiany w `config_model` łatwo rozjeżdżają się między web a desktopem.
