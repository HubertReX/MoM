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
- Kluczowe tokeny (hex): `TITLE #FFFC67`, `WHITE #FFFFFF`, `GREY #AAAAA4`, `GOLD #FFD700`,
  `ACCENT_CYAN #00C5C7`, `DONE #6ECF68`, `WARN #E8920C`, `RULE #444444`, `PANEL_BG #1E1E1E`.
- `settings.CHAR_NAME_COLOR` to ten sam żółty co `TITLE` — trzymać jako re-eksport, nie
  drugą definicję.

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

- Klawisze rysuj **sprite'em** `hud.icons["key_*"]` (te same, których używa HUD hotbar i
  przyciski akcji). **Nie** rysuj wektorowych chipów ani nie wypisuj klawisza tekstem.
- Sprite'y powstają dwuwarstwowo:
  - ręczny arkusz `HUD_SHEET_DEFINITION` (`settings.py:870`): `key` (pusty), `Esc`, `Tab`,
    `Ctl`, `Alt`, `Enter`, `Shift`, `Space`, `mouse_LMB`, `mouse_RMB`;
  - generowane w `generate_icons()` (`scene.py:277`): A–Z, cyfry 0–8, F1–F12, znaki
    `< > \` [ ] + -`.
- **Nowy klawisz z literą/cyfrą/F-em/znakiem** — dodaj do `generate_icons` (glif na pustym
  `key`). **Nowy klawisz bez glifu w foncie** (np. strzałki) — wymaga arta w arkuszu.
- Separatory `/` i `-` między klawiszami zostają tekstem (interpunkcja, nie klawisz).

## Cień tekstu — tylko chrome

- Model questów: cień **tylko** na chromie (nagłówki, etykiety sekcji, stopki). Proza i
  glify klawiszy **bez** cienia — pod prozą cień tylko pogrubia litery i psuje czytelność.
- Wzorzec API: `_text(..., shadow=False)` domyślnie, `shadow=True` na furniturze
  (patrz `quest.py` `_text`/`_label`).

## Rozmiary czcionki

- Font pixel: `[8, 10, 14, 16, 24, 155]` (EXTRA_TINY…HUGE).
- **Minimum:** chrome (etykiety, licznik) ≥ **10px** (`TINY`); treść czytana ≥ **14px**
  (`SMALL`). `FONT_SIZE_EXTRA_TINY` (8) **nie używać w UI** — nieczytelne po downscale.

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
