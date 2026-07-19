# Brief: headless agent-screenshot nie łapie otwartego panelu modalnego

Zwięzły brief do świeżej sesji Claude Code. Nie potrzebujesz kontekstu poprzedniej
sesji (dotyczyła głównie pasków UI) - wszystko istotne jest tutaj + w pamięci projektu
`deterministic-dialog-testing.md`.

## Cel

Sprawić, by zrzut ekranu robiony przez `agent_ctrl` w trybie headless
(`MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy`) **zawierał otwarty panel modalny**
(`DialogPanel`, ewentualnie `TradePanel`). Dziś PNG pokazuje świat + HUD, mimo że dialog
jest udowodnienie otwarty. To blokuje deterministyczne testy dialogów (i zawsze blokowało -
żaden dialog-screenshot w repo nigdy nie pokazał panelu).

## Repro (deterministyczne, już działa)

```bash
cd /Users/hubertnafalski/Projects/MoM
rm -f agent_input.txt; printf "" > agent_input.txt
PYTHONUNBUFFERED=1 MOM_AGENT_SS_CANVAS=1 MOM_AGENT_CONTROL=1 \
  SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./.venv/bin/python3 project/main.py > /tmp/game.log 2>&1 &
GP=$!
sleep 6; printf "accept" > agent_input.txt
sleep 2; printf "talk_to_char:barman" > agent_input.txt
sleep 1; printf "screenshot:probe" > agent_input.txt
sleep 1.5
kill $GP
ls -t screenshots/agent/*probe*.png | head -1   # obejrzyj: pokazuje gameplay, nie dialog
```

`talk_to_char:barman` deterministycznie otwiera dialog (nowy prymityw, patrz
`scene.agent_open_dialog`). Log potwierdza `talk_to_char 'barman' -> dialog opened`.

## Co już wykluczono (nie trać na to czasu)

- **Dialog się NIE zamyka.** Probe przez 200+ klatek: `dialog_open=True modal=True
  disp_ui=True`, ta sama scena (`id` stałe). Panel zostaje w `ui._open`.
- **Świat jest zamrożony** gdy dialog otwarty (`is_modal_open()` -> `scene.update`
  wychodzi wcześnie na `return`, licznik dnia stoi).
- **To nie SOD** - `SOD` to `SecondOrderDynamics` (wygładzanie ruchu kamery), nie stan
  na stosie `game.states`.
- **Nie reload sceny** - `game.states[-1]` to ta sama instancja Scene przez cały czas.

## Pierwsza hipoteza do sprawdzenia (najbardziej prawdopodobna)

**Rozjazd powierzchni: cel rysowania panelu != powierzchnia przechwytywana.**

- `scene.draw(screen, dt)` (`project/scene.py` ~1729) woła `self.ui.draw(...)`.
- `GameUI.draw` (`project/ui/game_ui.py` ~325) rysuje na `surface = self.surface` -
  sprawdź czym jest `GameUI.surface` (skąd ustawiane) i czy to TEN SAM obiekt co
  powierzchnia, na której rysowany jest świat/HUD i którą przechwytuje kod zrzutu.
- Zrzut (`project/game.py` ~1092-1096): `ss_source = self.canvas if
  MOM_AGENT_SS_CANVAS==1 else self.screen`, potem `agent_ctrl.capture(ss_source)`.
- HUD (health bar, hotbar) POKAZUJE się na zrzucie, a rysowany jest w tym samym
  `ui.draw` co pętla `for panel in self._open: panel.draw(surface)`. Więc jeśli HUD
  ląduje na przechwytywanej powierzchni, panel też powinien - chyba że panel rysuje się
  inną ścieżką/na inny surface, albo jest zasłaniany. Zweryfikuj to najpierw.

Kluczowe linie: `game.py` ~1046-1096 (update/draw/flip/capture), `scene.py` ~1729
(`draw`), `game_ui.py` `draw` + skąd `self.surface`, `agent_ctrl.py` `capture`.

## Jak zweryfikować naprawę

Po poprawce uruchom repro powyżej i obejrzyj PNG - ma pokazać panel dialogu Barmana
(żółta plakietka imienia + gruby pasek sentymentu nad nią, lista opcji). Następnie
przywróć asercję `screenshot_review` w scenariuszu `Dialog Open Deterministic`
(`tests/scenarios.json`) i sprawdź, że przechodzi:

```bash
./.venv/bin/python3 tests/automate_display_test.py "Dialog Open Deterministic"
```

## Kontekst prymitywów (już w repo, commit 790a98b)

- `talk_to_char:<key>` - deterministycznie otwiera dialog (zamraża NPC, `npc_met`,
  `ui.open`). NPC-e wędrują, więc `walk_to + talk` jest niedeterministyczne.
- `walk_to_char` / `walk_to_point` - nawigacja A* + status w `agent_status.txt`.
- Metody na `Scene`: `agent_find_entity`, `agent_walk_target`, `agent_point_near`,
  `agent_walk_player_to`, `agent_player_arrived`, `agent_open_dialog`.
