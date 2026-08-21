# Czego fabuła wymaga od mapy

Źródła: `doc/PL/fabuła.md`, `doc/PL/Lokalizacje/`, `doc/PL/Postacie/`, `doc/PL/Misje/`.

## Gafowo Kolonia (BLUNDERHAVEN)

"Mała, zacofana wieś na południu [[Królestwo Pomylenia]]". Notatka do questa Q04_S00 mówi
wprost: *"ta cała wioska to jeden wielki żart"* - dla Barmana brak ryb ma rangę polityki
międzynarodowej.

**Ton, nie ozdobnik:** wieś ma być **zaniedbana i przaśna**, nie malownicza. Krzywe płoty,
ścieżki rozjeżdżone w koleiny, kupki siana i beczek gdzie popadnie, jedna kapliczka
(`shrine`) traktowana przez mieszkańców całkiem serio.

## Twarde wymagania przestrzenne

| Źródło | Wymóg |
|---|---|
| Q00_S00 "Obudziłeś się w **stajni**" | `start` stoi w stajni, nie na łące |
| Q01_S01 "w Tawernie mówi się o wszystkich" | Tawerna blisko `start`, wejście widoczne z placu |
| Zielarka Zmora: "chałupa **na końcu wioski, koło lasu**" | jej dom na skraju zabudowy, stykający się z biomem lasu |
| Q04_S01 "skrzynia ukryta **za krzakami**, trzeba mocnej broni" | skrzynia `BLUNDERHAVEN_CATS_CHEST` otoczona kafelkami `destructible=true` (Nature.tsx, `destruct_type=foliage`) |
| Q04_S02 "kryształ z Labiryntu" | wejście `MAZE_01` z `return_entry_point=NextToMaze` |
| Q01_S03 "dwa dni drogi **na północ**, za Splątanym lasem na wschód" | wyjazd na Porażkowo prowadzi na północ, w las |
| `characters.csv`: Barman `social=BLUNDERHAVEN:well` | studnia jako miejsce spotkań, centralny plac |
| Kowal: `work=smithy`, `home=house_smith` | kuźnia osobno od domu; kowal gardzi wsią, więc jego chałupa na uboczu |

## Mieszkańcy (z `characters.csv` i kart postaci)

| Klucz | Kto to | Gdzie mieszka |
|---|---|---|
| `BARMAN_ABSINTHRAYNER` | Barman Absyntnent - gaduła, boi się świata, wierzy w zabobony, brzydzi się magią | LOST_CORK_TAVERN (urodzony tam) |
| `HAMMER_HOAXHEART` | Kowal Kłamca - gburowaty, bywał w świecie, czuje się niedoceniany | `house_smith`, pracuje w `smithy` |
| `POTIONEER_PUZZLEMINT` | Zielarka Zmora - staroświecka, zabobonna, wścibska | chałupa na końcu wsi, przy lesie |
| `MARRY` | Zielarka Marry - stara, nie rusza się poza wieś | dom we wsi |
| `BART`, `JOHNY`, `ROB`, `ROBIN` | mieszkańcy, rutyna `townsfolk` | `house_bart`, `house_johny` |
| `CLAPBACK_SWORD` | Miecz Ciętej-riposty - gadający kompan | przy graczu |
| `MADAME_SARCASMIA`, `MISS_INFORMATION` | mieszkają w **Porażkowo**, na BLUNDERHAVEN stoją testowo | - |

Zwierzęta z `allowed_zones`: kury (4 warianty), krowa, świnia, koń, psy i koty (`backyard`,
`plains`), żaby (`shore`), ryby (`water`), dzik i szop (dzicz).

## Istniejące klucze, których należy używać zamiast wymyślać nowe

**`places`:** `well`, `shrine`, `smithy`, `pier`, `market_stall_1`, `market_stall_2`,
`house_bart`, `house_johny`, `house_smith`, `house_barman`.

**`zones`:** `water`, `shore`, `plains`, `backyard`, `wilderness` - i tylko te, bo
`allowed_zones` w `characters.csv` nie zna innych.

**Rutyny:** `townsfolk`, `barman`.
