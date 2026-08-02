# E03 etap 0 - dokument decyzyjny mgły wojny (skrót)

Pełny dokument (tabele opcji per decyzja, pomiary, pseudokod):
[fog-of-war-2026-08-02.html](../_attachements/fog-of-war-2026-08-02.html)
(podgląd: `docserve start doc/_attachements/fog-of-war-2026-08-02.html`).

Status: **zaakceptowany i zrealizowany 2026-08-02**. Autor zmienił D7 (potwory świecą
także w nieodkrytym terenie, ale ulotnie); reszta decyzji weszła bez zmian.
Kod: `project/scene/fog_of_war.py`, opis mechaniki w `project/AGENTS.md`.

## Wymagania autora (wiążące, ustalone 2026-08-02)

- **W1** - dwa algorytmy z prototypu (bez trybu „radius").
- **W2** - raycast polygon: pamięć hard, upscale nearest, zasięg 5 kafli, steps 4.
- **W3** - shadowcast tiles: pamięć hard, upscale nearest, zasięg 4 kafle, steps 4, rdzeń 2 kafle.
- **W4** - aktywny algorytm wybierany w SettingsMenu; reszta parametrów to stałe do fine tuningu.
- **W5** - wokół potworów labirynt też rozświetlony, tym samym algorytmem.
- **W6** - aggro potworów bez zmian: dystans, nie LoS („nie widzi, ale słyszy").

## Decyzje z rekomendacją

| # | Decyzja | Rekomendacja |
| --- | --- | --- |
| D1 | Reprezentacja odkrycia | bitset po kaflach (585 B) + maska `Surface` 1 px = 1 kafel |
| D2 | Gdzie żyje stan | `scene.fog` + wpis w `MAP_PROPERTIES` (jak `path_finding_grid`) |
| D3 | Wiersz w ustawieniach | trzy pozycje: wyłączona / promienie / kafle |
| D4 | Trwałość wyboru | `settings.json` + localStorage, pole `fog_algorithm`, BEZ podbicia `CURRENT_VERSION` |
| D5 | Renderowanie trzech stanów | maska podmienia `fill()` w istniejącym filtrze - żadnego drugiego pełnoekranowego `scale` |
| D6 | Które potwory świecą | tylko w kadrze, limit 3 najbliższych graczowi |
| D7 | Czy światło potwora odkrywa mapę | **decyzja autora:** świeci ZAWSZE, też w nieodkrytym korytarzu, ale ulotnie - pamięć odkrycia rośnie wyłącznie od gracza |
| D8 | Parametry światła potworów | ten sam algorytm, tańsze stałe (60 promieni, 2 pierścienie, zasięg 3) |
| D9 | Kiedy przeliczać | shadowcast i potwory przy zmianie kafla, raycast gracza przy ruchu ≥ 2 px |
| D10 | Zapis a wersja | nowe pole z domyślną w `MapState`, `VERSION` zostaje „0.3" (podbicie ODRZUCIŁOBY stare zapisy) |
| D11 | Wpływ na rozgrywkę | prolog: mgła wyłącznie wizualna (bez minimapy i modyfikatorów z CSV) |

## Liczby, które rozstrzygają koszt

Pomiary desktop (mac-mini M4, poziom 4 = 78x60 kafli, headless):

| Operacja | avg |
| --- | ---: |
| shadowcast, zasięg 4 | 0,025 ms |
| raycast, zasięg 5, 180 promieni | 0,324 ms |
| raycast, 60 promieni (potwór) | 0,127 ms |
| `commit` do maski | 0,055-0,079 ms |
| 4 pierścienie-wielokąty (per obserwator) | 0,136 ms |

Cała nakładka w tym samym pomiarze: dziś (sama noc) **0,561 ms**, + mgła kafelkowa
**0,572 ms**, + mgła raycast **0,699 ms**. Mgła mieści się w powierzchni filtra, którą
gra i tak skaluje co klatkę - warunek twardy zadania spełniony konstrukcyjnie.

Budżet web (E02): w labiryncie ~6 ms z 16,7 ms, zapas ~10 ms. Szacunek kosztu mgły:
1-2 ms (raycast), poniżej 0,5 ms (kafle). Liczba wiążąca = pomiar `MOM_PROFILE=1`
po implementacji, w treści commita.

## Plan wykonania (6 kroków, commit po każdym)

1. `scene/fog_of_war.py` - stan + czyste funkcje widoczności + testy jednostkowe.
2. Podpięcie do sceny i filtra, tylko gracz, algorytm ze stałej.
3. Wiersz w SettingsMenu + trwałość + lokalizacja PL/EN.
4. Potwory jako źródła światła (cullowanie, limit, kolejność malowania pierścieni).
5. Zapis mgły (`MapState` + żywa scena + cache map nieodwiedzonych).
6. Scenariusz agentowy, profil web, AGENTS.md, odhaczenie E03.

## Trzy rzeczy, które najłatwiej zepsuć

- **Czarne kwadraty** wracają po każdej zmianie w `commit` - selftest z prototypu
  (losowy spacer + licznik ciemnych kafli w jasnym otoczeniu) przechodzi do testów.
- **Kolejność malowania wielokątów** przy wielu obserwatorach: `draw.polygon` nadpisuje,
  więc rysujemy poziomami (najciemniejszy pierścień wszystkich obserwatorów, potem kolejny),
  inaczej pierścień potwora wymaże rdzeń gracza.
- **Zapis map, na których gracz nie stoi** - ta sama pułapka, która zdarzyła się już przy
  `destroyed_walls` i `dead_monsters`; obie ścieżki (`_build_fog`, `_build_fog_from_cache`)
  pisane razem.
- **Ślad potwora jako fałszywa pamięć (D7)** - kafel zwalniany z widoczności wraca do
  `FOG_ALPHA_REMEMBERED` tylko wtedy, gdy jego bit w `discovered` jest ustawiony;
  w przeciwnym razie do `FOG_ALPHA_UNSEEN`. Jedna wartość dla obu przypadków zostawia
  na mapie korytarz, którego gracz nigdy nie widział.
