---
id: T-041
title: DS: semantyczne kolorowanie slow kluczowych char, loc, item plus inline emotki w tresci wezla
status: needs-you
owner: human
priority: p2
type: feature
agent: opencode
created: 2026-07-06
updated: 2026-07-06
tags:
  - task
state: review
---
# T-041 - DS: semantyczne kolorowanie słów kluczowych (char/loc/item) + inline emotki

## 🎯 Goal / Outcome

- [ ] Słowa kluczowe w treści węzła mają rozróżnialne wizualnie style wg typu: postać (`[char]`, żółty), lokacja (`[loc]`, zielony), przedmiot (`[item]`, niebieski), błąd/negatyw (`[error]`, czerwony) - zgodnie z `STYLE_TAGS_DICT`
- [ ] Inline emotki w treści węzła (`:blessed:` i pochodne) renderują się jako sprite, nie znikają
- [ ] Ustalona i udokumentowana ścieżka autorska: skąd biorą się tagi typu w MD (autor taguje ręcznie vs. auto-mapowanie ze słownika encji)

## 🧭 Context

- **Kontekst wspólny:** [[DS-epic-brief]] (D3 - konwersja znaczników; `STYLE_TAGS_DICT` `project/settings.py:303` ma `char/item/loc/num/quest/error`; `_TAG_CONVERSIONS` w `markdown_importer.py` mapuje RPG `[red]->error`, `[blue]->item`, `[yellow]->char`).
- Zgłoszone przez użytkownika: "w treści postaci wszystkie słowa kluczowe są formatowane tak samo, a mamy tabelę mapowania char/location/item; treści zawierały też emotki, których teraz nie widzę".
- **Analiza:** źródłowe MD z RPG (`/Users/hubertnafalski/Projects/RPG/dialogs/*/char-Hammer_Hoaxheart.md`) w praktyce oznaczają słowa kluczowe tylko przez `**bold**` (np. `**Królestwo Pomylenia**` = lokacja), a nie przez tagi typu `[red]/[blue]/[yellow]`. Importer konwertuje `**...**` -> `[shadow]` (jednolity styl) - stąd "wszystko tak samo". Mapa `_TAG_CONVERSIONS` istnieje, ale w źródle brak tagów kolorów, więc nic jej nie uruchamia.
- Zależność renderu: jeśli treść węzła (RichText) nie pokazuje inline emotek, sprawdzić emote-sheet i parser; jeśli opcje - to [[T-038 DS bug: opcje dialogu renderowane plain fontem - znaczniki italic i kolory literalnie]].
- Powiązane: [[T-043 DS: zrodlowe MD dialogow w project assets dialogs plus task just konwersji MD do config.json]] (jeśli dojdzie tagowanie typów, robi się to w MD w projekcie).

## ⛓️ Constraints

- Dual-target desktop + web.
- **Złota reguła:** źródłem prawdy jest Markdown (D11); wszelkie tagi typu dopisujemy w MD, `config.json` regenerowany.
- Type hints wymagane.

## 🪜 Plan / Subtasks

- [ ] **Model tagowania (zdecydowane - opcja A):** autor **ręcznie** taguje słowa kluczowe w MD jawnymi tagami MoM RichText (patrz "Jawne mapowanie" niżej). Bez auto-mapowania po słowniku (polska fleksja + false-positive rozwalają wynik). Ewentualny jednorazowy skrypt bootstrap tylko jako pomoc - źródłem prawdy zostają ręczne tagi w MD (D11).
- [ ] Zweryfikować, że treść węzła (RichText) renderuje inline `:emote:` poprawnie; jeśli nie - naprawić.
- [ ] Udokumentować konwencję tagowania (tabela niżej) i otagować MD Hammera jako wzorzec/referencję.
- [ ] Test wizualny: węzeł z nazwą postaci, lokacji i przedmiotu w różnych kolorach + emotka.

## 🎨 Jawne mapowanie tagów (ustalone 2026-07-05, epic §6a; źródło `settings.py:STYLE_TAGS_DICT`)

Autor pisze bezpośrednio tagi MoM RichText w MD (MD leży już w projekcie MoM, D11):

| Typ słowa kluczowego | Tag MoM | Kolor | Uwaga |
| --- | --- | --- | --- |
| Postać (char) | `[char]...[/char]` | żółty (255,252,103) | nazwy NPC / bohatera |
| Lokacja (loc) | `[loc]...[/loc]` | zielony | miejsca, krainy |
| Przedmiot (item) | `[item]...[/item]` | niebieski (104,113,255) | itemy (nazwy zgodne z `items.csv`) |
| Błąd/negatyw (error) | `[error]...[/error]` | czerwony (223,57,76) | ostrzeżenia / negatyw |
| Akcja/klawisz | `[act]...[/act]` | - | akcje |
| Liczba | `[num]...[/num]` | - | liczby |
| Wyróżnienie (z `**bold**`) | `[shadow]...[/shadow]` | - | dawny RPG `[reverse]` |
| Emote inline | `:nazwa:` | - | np. `:blessed:`, `:angry:` (arkusz `EMOTE_SHEET_DEFINITION`) |

Konwersja z tagów RPG (dla importu istniejących MD): `[reverse]->[shadow]`, `[red]->[error]`, `[blue]->[item]`, `[yellow]->[char]`, `[key]->:key_X:`, `[symbol]/[e]->:name:`; tagi zgodne 1:1 (`italic`, `bold`, `char`, `action->act`, `item`, `location->loc`, `number->num`) bez zmian.

## ✅ Definition of Done

- [ ] Kryteria z Goal spełnione
- [ ] zmiany udokumentowa w tasku (`moab log`)
- [ ] na końcu tej sekcji "✅ Definition of Done" dodane jest zdjęcia potwierdzające prawidłowe działania
- [ ] Testy / lint przechodzą (jeśli dotyczy)
- [ ] W razie potrzeby odpowiednie pliki AGENTS.md są zaktualizowane
- [ ] commit zmian wykonany

## 📓 Agent Log

- 2026-07-06 cc (review): utworzony podczas weryfikacji epica DS. Analiza: źródło MD używa tylko `**bold**` dla słów kluczowych; brak tagów typu do kolorowania. Wymaga decyzji autorskiej (ręczne tagi vs auto-mapowanie).
- 2026-07-07 decyzja (autor): **opcja A** - ręczne, jawne tagi w MD (brak auto-mapowania po słowniku; polska fleksja + false-positive). Jawne mapowanie tagów wpisane w sekcji "🎨 Jawne mapowanie tagów".
- 2026-07-07 14:19 opencode: claimed, starting

## 🙋 Needs-You / Questions

- (brak - wszystko rozstrzygnięte)
