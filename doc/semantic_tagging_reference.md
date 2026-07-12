
# Konwencja tagowania semantycznego dialogów

W treści węzłów dialogowych (RichText) używamy następujących tagów do
semantycznego kolorowania słów kluczowych:

## Tabela tagów

| Typ słowa kluczowego | Tag MoM | Kolor | Przykład |
|---|---|---|---|
| Postać (NPC / bohater) | `[char]...[/char]` | żółty (255,252,103) | `[char]Barman Bart[/char]` |
| Lokacja (miejsca, krainy) | `[loc]...[/loc]` | zielony (95,250,104) | `[loc]Karczmie[/loc]` |
| Przedmiot (itemy) | `[item]...[/item]` | niebieski (104,113,255) | `[item]Miecz[/item]` |
| Błąd / negatyw | `[error]...[/error]` | czerwony (223,57,76) | `[error]DEBUG[/error]` |
| Akcja / klawisz | `[act]...[/act]` | pomarańcz (255,110,104) | `[act]załatwić[/act]` |
| Liczba | `[num]...[/num]` | różowy (255,119,255) | `[num]100[/num]` |
| Wyróżnienie (dawne bold) | `[shadow]...[/shadow]` | cień tekstu | `[shadow]ważne[/shadow]` |
| Pogrubienie | `[bold]...[/bold]` / `[b]...[/b]` | standard | `[bold]Uwaga![/bold]` |
| Kursywa | `[italic]...[/italic]` / `[i]...[/i]` | standard | `[italic]myśl[/italic]` |

## Inline emotki

Emotki wstawiamy przez `:nazwa:`. Lista dostępnych emotek pochodzi z
`EMOTE_SHEET_DEFINITION` w `settings.py`. Przykłady:

- `:smile:` :smile: · `:blessed:` :blessed: · `:angry:` :angry: · `:blink:` :blink:
- `:neutral:` :neutral: · `:dots:` :dots: · `:wondering:` :wondering:
- `:offended:` :offended: · `:indifferent:` :indifferent: · `:happy:` :happy:

## Zasady (D11)

1. **Źródłem prawdy jest Markdown** — tagi dopisujemy w MD, a config.json jest
   regenerowany z niego.
2. **Ręczne tagowanie** — autor sam oznacza słowa kluczowe w MD jawnymi tagami
   MoM RichText. Bez auto-mapowania po słowniku (polska fleksja + fałszywe
   trafienia).
3. **Typ encji** decyduje o tagu: postać → `[char]`, miejsce → `[loc]`,
   przedmiot → `[item]`.
4. **Konwersja z RPG** (przy imporcie istniejących MD): `[reverse]` → `[shadow]`,
   `[red]` → `[error]`, `[blue]` → `[item]`, `[yellow]` → `[char]`.
5. **Zawsze używaj nazwanych tagów zamykających** — `[/char]` a nie `[/]`.
   Parser MoM RichText nie wspiera generycznego `[/]`.

## Przykład

```markdown
[char]Barman[/char] z [loc]Karczmy Pod Wesołym Karłem[/loc] sprzedaje
[item]Wywar zdrowia[/item] za [num]50[/num] sztuk złota. :smile:
Pamiętaj — [error]nie negocjuj[/error] z nim!
Przygotuj się do [act]walki[/act].
```
