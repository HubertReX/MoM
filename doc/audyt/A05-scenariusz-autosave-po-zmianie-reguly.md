# A05 - scenariusz "Auto Save on Map Change" po zmianie reguły autosave

Priorytet: **P2** (Faza 1, dług po zmianie mechaniki). Rozmiar: S. Zależności: brak.

## Kontekst i problem

Scenariusz `Auto Save on Map Change` (`tests/scenarios.json`) pada:

```
Test failed: /Users/.../.test-data/mom/saves/save_0.mom does not exist
```

Scenariusz powstał, gdy **każda** zmiana mapy robiła autosave slotu 0. Commit `b524e45`
("autosave tylko przy wchodzeniu do labiryntu, nie przy zwykłych przejściach między
pomieszczeniami") zawęził regułę - `scene.py` (`go_to_map`, koniec metody) zapisuje teraz
tylko gdy `self.is_maze`:

```python
if (self.is_maze
        and hasattr(self.game, "save_manager")
        and self.game.save_manager.save(QUICK_SAVE_SLOT)):
    self.add_notification(_("notify.autosaved_quick"), NotificationTypeEnum.info)
```

Scenariusz używa komendy `debug_map_change`, która **celowo wybiera wyjście NIE-labiryntowe**
(`agent_ctrl.py`: `next((e for e in state.exits if not getattr(e, "is_maze", False)), ...)`),
więc autosave nie ma prawa się wykonać - a asercja `file_exists` na `save_0.mom` została.

**Uwaga - to NIE jest kwestia numeru slotu.** Scenariusz już asertuje `save_0.mom`,
a `settings.QUICK_SAVE_SLOT == 0`. Numer się zgadza; nie zgadza się **zdarzenie**,
które ma zapis wywołać.

## Cel

Scenariusz znów sprawdza realną, obowiązującą regułę: autosave slotu 0 przy wejściu
do labiryntu, brak autosave przy zwykłym przejściu między mapami.

## Pliki do zmiany

- `tests/scenarios.json` - scenariusz `Auto Save on Map Change`
- `project/save_load/manager.py` - martwy `should_autosave_on_map_change` (krok 3)

## Krok 1: przestaw scenariusz na wejście do labiryntu

Zamień akcję `change_map` z `debug_map_change` na `debug_enter_maze` (ta sama komenda,
której używa działający scenariusz `Maze Persists Across Save Load`). Zaktualizuj też
nazwę i slug scenariusza, żeby mówiły prawdę o tym, co testują - np.
`Auto Save on Maze Entry` / `auto_save_on_maze_entry`; nazwa jest kluczem w
`just test-agent "<nazwa>"`, więc poszukaj jej w repo przed zmianą
(`rg "Auto Save on Map Change"`).

Reszta scenariusza (otwarcie menu, wejście w Load, screenshot panelu, zamknięcie) zostaje.

## Krok 2: dopisz drugi scenariusz - regułę negatywną

Nowy scenariusz `No Auto Save on Room Change`: `debug_map_change` (wyjście nie-labiryntowe),
a potem asercja `save_absent` na `<save_dir>/save_0.mom`. To on pilnuje właściwej treści
commita `b524e45` - bez niego nic nie wykryje powrotu do starego zachowania.

Dorzuć asercję `ui_state` z `debug_ui_state` (patrz `project/AGENTS.md`, sekcja
"Asercje stanu"), sprawdzającą, że gracz faktycznie zmienił mapę:
`{"type": "ui_state", "expect": {"top_state": "Scene", "is_maze": false}}` plus równość
`map` na nazwę mapy docelowej, jeśli jest deterministyczna.

## Krok 3: usuń martwy kod

`SaveManager.should_autosave_on_map_change` (`save_load/manager.py:131`) **nie ma
ani jednego wywołania** - decyzja przeniosła się wprost do `scene.py`. Usuń metodę
(jej docstring opisuje regułę, która i tak jest już opisana w komentarzu w `scene.py`).

## Kryteria akceptacji

1. `MOM_SKIP_SS_REVIEW=1 just test-agent "<nowa nazwa>"` przechodzi.
2. `MOM_SKIP_SS_REVIEW=1 just test-agent "No Auto Save on Room Change"` przechodzi.
3. `MOM_SKIP_SS_REVIEW=1 just test-agent` (cały zestaw desktop) - zero padających
   scenariuszy.
4. Wariant web obu scenariuszy przechodzi (`just test-web "<nazwa>"`) albo scenariusz
   dostaje `"platform": ["desktop"]` z komentarzem dlaczego.
5. `rg "should_autosave_on_map_change" project/` - zero trafień.
6. `just test-unit` przechodzi.

## Pułapki

- `debug_enter_maze` generuje poziom labiryntu - jest wolniejsze niż zwykła zmiana mapy;
  daj akcji `wait` co najmniej takie jak w `Maze Persists Across Save Load`.
- Scenariusz ma `cleanup_saves: [0]` - zostaw, bez tego asercja `save_absent` w kroku 2
  może zobaczyć zapis z poprzedniego scenariusza.
- Nie „naprawiaj" reguły autosave w kodzie - obowiązująca decyzja autora to autosave
  wyłącznie przy wejściu do labiryntu.

## Po zakończeniu

- odhacz A05 w `doc/audyt/audyt.md`
- commit: `A05: scenariusz autosave dostosowany do reguły "tylko wejście do labiryntu"`
