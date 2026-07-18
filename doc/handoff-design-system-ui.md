## Kontekst

Sesja dotyczy budowy "design systemu" dla UI gry MoM (Misadventures of Malachi) - Pygame-CE top-down RPG. Nadrzędne zasady: (a) skalowanie pixel-art potęgą dwójki / liczbą parzystą, by "udawana niska rozdzielczość" nie zdradzała się nierównymi pikselami, (b) te same komponenty wszędzie (keycapy, shadow model, palette). Rendering: canvas 1280×720 → skalowany jako jedna bitmapa do rozdzielczości fizycznej.

## Co zostało zrobione

- **Audyt 5 ekranów** (main menu, mapa, dialog, quest, help) - odstępstwa spisane do decyzji
- **`project/ui/theme.py`** - współdzielona paleta (zamiast inline kolorów w każdym panelu). Przemapowane: quest.py, help.py, inventory.py, trade.py, dialog.py
- **Shadow model ujednolicony**: w help.py tylko chrome (nagłówek, etykiety sekcji) ma cień, reszta bez - zgodnie ze stylem questów
- **1px linie → 2px**: `UI_BORDER_WIDTH` 9→8, chipy/ramki width=1→2, kółko markera questów width=2
- **Emoji scaling naprawiony** w 3 miejscach: rich_text.py (helper `_icon_factor`, 4 site'y), hud.py (toast), dialog.py (`_EMOTE_SCALE` 1.8→2)
- **Pasek sentymentu** (`dialog.py`): pełny bar, bez ramki, zaokrąglone boki (wg Twojej decyzji)
- **border_radius wyczyszczone**: dialog option highlights, save_load slot, progress bar, scrollbar thumb - kanciaste (pixel-grid); wyjątek: sentiment bar (celowo rounded, bo tak kazałeś)
- **Keycap sprite wszędzie**: pomocny moduł `project/ui/keycap.py` z `build_cap()` + `render_hint()`; stringi i18n na markery `{TOKEN}`; hinty nawigacji (header help + footer quest) teraz sprite'y; placeholdery strzałek (4 kierunki) jako fallback
- **Kontrast keycap**: ciemne tło (mult75) = `(75, 82, 105)` z białym glyphem
- **EXTRA_TINY** (8px) wycofane z UI: `objects.py:222` nazwy postaci → FONT_SIZE_TINY (10px)
- **Brakujące keycapy**: `,`, `.`, `9` dodane w `scene.py:generate_icons()`
- **Dokumenty**: `project/ui/AGENTS.md` (zasady), `doc/design-system-ui.md` (plan), `doc/_attachements/design-system-2026-07-18.html` (audyt HTML), `doc/_attachements/design-system-progress.html` (log postępów before/after)
- **Skrypt**: `scripts/gen_design_system_progress.py` - headless capture + builder HTML
- **GA branch docs/design-system-ui → main zmergowany** (commit `0895b38`..`e6e812d` → merged)

## Co próbowano i z jakim skutkiem

- **Dialog capture headless**: początkowo nie otwierał dialogu (player nie podchodził do NPC). Rozwiązane przez dedykowany driver `capture_dialog.py` chodzący do Barmana. Później wbudowane w `gen_design_system_progress.py` z sekwencją `move_down;move_right;move_up;move_left`
- **Fractional emoji scaling**: znalezione i naprawione we wszystkich 3 ścieżkach (rich_text, toast, dialog emotes). Integer scaling helper `_icon_factor()`
- **Misdiagnoza "podwójnego tagu Barman"**: początkowo zgłosiłem jako bug. Po sprawdzeniu kodu - drugi żółty "Barman Absyntnent" to wikilink `[[Barman Absyntnent]]` w powitaniu NPC (pliku `doc/PL/Postacie/Barman Absyntnent.md:39`). Sprostowane w docs.
- **Keycap kontrast**: za mały kontrast białych glyphów na jasnym tle keycap. Naprawione przez ciemne tło (`mult75`). Baked tiles (Shift/Space/Esc/Enter) wciąż jasne - do dorysowania w Aseprite.
- **Sentiment bar**: moja propozycja segmentowa odrzucona, zaakceptowana decyzja: "pełny, bez ramki, zaokrąglony po bokach". Zaimplementowane.
- **Session limit**: przerwane 2 razy przez limit planu ("resets 1pm / 11pm"). Kontynuowane po resecie.

## Aktualny stan i blocker

**Stan**: Wszystkie poprawki kodu zaimplementowane i zmergowane do `main`. Design system gotowy do użycia.

**Blocker**: **4 keycap sprite'y strzałek (up/down/left/right) + przyciemnienie baked kafli (Shift/Space/Esc/Enter/Alt) - musisz dorysować w Aseprite.** Placeholdery (białe trójkąty) działają jako fallback, ale wyglądają blado vs hand-drawn tiles.

## Następne kroki

1. **Dorysuj w Aseprite** 4 strzałki (strzałka w górę/dół/lewo/prawo) do `project/sprites/hud/HUD_sheet.png`. Pozycje i aktualny stan placeholderów: patrz `HUD_SHEET_DEFINITION` w `settings.py:870` - slots dla key_up, key_down, key_left, key_right istnieją.
2. **Przyciemnij baked kafle** (Shift/Space/Esc/Enter) w Aseprite - dark face z białym glyphem, jak reszta.
3. **Devlog na itch.io**: użyj `scripts/gen_design_system_progress.py` po każdej porcji zmian. Jeden plik: `python scripts/gen_design_system_progress.py` (headless capture + build). Wynik w `doc/_attachements/design-system-progress.html`.
4. Jeśli potrzebujesz dalszych poprawek kodu (nowe elementy UI, regresje), otwórz nową sesję OC z tym handoffem.

## Kluczowe pliki, komendy i adresy

- **`project/ui/theme.py`** - paleta (single source of truth)
- **`project/ui/keycap.py`** - współdzielony moduł keycap + `render_hint()`
- **`project/ui/panels/dialog.py:519`** - `_draw_sentiment_indicator` (ostatnia zmiana)
- **`project/ui/panels/help.py`** - sprite keycaps, chrome-only shadow
- **`project/ui/panels/quest.py`** - sprite keycaps w footerze
- **`project/ui/widgets/rich_text.py`** - integer emoji scaling
- **`project/scene.py:277`** - `generate_icons()` (tu dodawane nowe keycap sprite'y)
- **`project/settings.py:870`** - `HUD_SHEET_DEFINITION` (gdzie wkleić nowe strzałki)
- **`project/ui/AGENTS.md`** - zasady design systemu
- **`doc/design-system-ui.md`** - plan + tabela decyzji
- **`doc/_attachements/design-system-2026-07-18.html`** - audyt HTML (podgląd: `docserve`)
- **`doc/_attachements/design-system-progress.html`** - log postępów (podgląd: `docserve`)
- **`scripts/gen_design_system_progress.py`** - skrypt do regeneracji progress HTML
- **docserve**: `http://mac-mini.kamori-vector.ts.net:8899/`
- **GA branch (merged)**: `docs/design-system-ui` → `main`

## Wskaźnik do źródła

- **sessionId**: `252585c0-3499-4c6b-85fd-ceb7f72c7d8d`
- **transkrypt**: `/Users/hubertnafalski/.claude/projects/-Users-hubertnafalski-Projects-MoM/252585c0-3499-4c6b-85fd-ceb7f72c7d8d.jsonl`
- **repo**: `/Users/hubertnafalski/Projects/MoM` (gałąź `main`, po merge'u)
