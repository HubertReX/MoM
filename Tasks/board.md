---

kanban-plugin: board
tags:
  - task
  - board

---

## 🧊 Backlog

- [ ] [[T-038 DS bug: opcje dialogu renderowane plain fontem - znaczniki italic i kolory literalnie]] #bug #p2
- [ ] [[T-039 DS bug: wskaznik opcji pokazuje generyczna ikone zamiast emotki sentymentu z pliku MD]] #bug #p2
- [ ] [[T-041 DS: semantyczne kolorowanie slow kluczowych char, loc, item plus inline emotki w tresci wezla]] #feature #p2
- [ ] [[T-042 DS: oznaczanie odwiedzonych linii dialogowych (nowe bold, odwiedzone bez bold)]] #feature #p3
- [ ] [[T-043 DS: zrodlowe MD dialogow w project assets dialogs plus task just konwersji MD do config.json]] #chore #p2
- [ ] [[T-044 DS: umieszczenie pozostalych postaci z dialogami na mapie (Barman, Potioneer, Clapback, Sarcasmia)]] #feature #p2

## 🟢 Ready for AI

## 🤖 In Progress

- [ ] [[T-040 DS bug: strzalki przesuwaja wybor opcji o 2 pozycje (podwojna obsluga KEYDOWN)]] #bug #p1 #opencode

## 🙋 Needs You

- [ ] [[T-023 DS: Model NPC i pola sentymentu (dialog_key, sentiment, disposition)]] #feature #p2 #M #opencode #review
- [ ] [[T-024 DS: Pipeline importu Markdown do config (parser + walidacja + konwersja znacznikow)]] #feature #p2 #L #opencode #review
- [ ] [[T-033 DS: UI DialogPanel - lista opcji i wybor (hybryda kursor + 1-9 + mysz)]] #feature #p2 #L #opencode #review
- [ ] [[T-034 DS: Efekty wezlow - adapter ResultSink (zloto, itemy, HP, sentyment)]] #feature #p2 #M #opencode #review
- [ ] [[T-030 DS: Persystencja stanu rozmowy w save-load (oba backendy + testy korupcji)]] #feature #p2 #M #opencode #review
- [ ] [[T-035 DS: Sentyment w rozgrywce - odkrywanie, bramkowanie opcji, mnoznik cen]] #feature #p2 #L #opencode #review
- [ ] [[T-028 DS: Migracja pozostalych postaci + web smoke-test + testy wizualne]] #feature #p2 #M #opencode #review
- [ ] [[T-036 DS: Feedback zmiany sentymentu - floating plus-minus N (later)]] #feature #p3 #S #opencode #review
- [ ] [[T-037 DialogPanel nie zamyka rozmowy przy opcji finalnej poza widocznym zwojem listy]] #bug #p2 #cc #review

## 🏁 Done

**Complete**
- [ ] [[T-018 Load z menu głównego nie działa]] #bug #p1 #opencode
- [ ] [[T-020 Widget pola tekstowego (TextInput) w module UI]] #feature #p2 #cc
- [ ] [[T-019 ręczny zapis screenshot (F6) nie działa]] #bug #p2 #opencode
- [ ] [[T-021 Panel zarządzania slotami zapisu w menu głównym (edycja nazwy, usuwanie)]] #feature #p2 #cc
- [ ] [[T-029 DS: Encje dialogu i budowa grafu (DialogNode, Option, Result + init_dialog)]] #feature #p2 #M #cc
- [ ] [[T-032 DS: Silnik warunkow - mini-DSL (AST-whitelist + predykaty)]] #feature #p2 #L #cc

## Archive

- [ ] [[T-001 UI nie skaluje się przy zmianie rozdzielczości]] #bug #p2 #opencode
- [ ] [[T-002 ekran nie przesuwa się na środek po zmianie rozdzielczości]] #bug #p2 #opencode
- [ ] [[T-003 nie działa przycisk "full screen"]] #bug #p2 #opencode
- [ ] [[T-004 zmiana ustawień wyświetlania bez potwierdzania]] #feature #p1 #opencode
- [ ] [[T-005 Core save data model — SaveGame, SaveSlot, per-state dataclasses]] #feature #p1 #opencode
- [ ] [[T-006 Save-Load manager engine — SaveManager class, desktop file backend, web localStorage backend, slot CRUD]] #feature #p1 #opencode
- [ ] [[T-007 Save-Load UI panels and game integration — SavePanel, LoadPanel, hotkeys F5-F9, auto-save, death screen load]] #feature #p2 #opencode
- [ ] [[T-008 Save-load test scenarios — agent tests for save, load, corrupt data, edge cases]] #feature #p2 #opencode
- [ ] [[T-009 TestRunner nie restartuje gry między scenariuszami w automate_display_test.py]] #bug #p1 #opencode
- [ ] [[T-010 Save Overwrite wczytuje stary stan zamiast nadpisanego zapisu]] #bug #p1
- [ ] [[T-011 Auto Save on Map Change nie testuje faktycznie zmiany mapy]] #bug #p2
- [ ] [[T-012 quick_load nie zamyka otwartego LoadPanel w testach]] #bug #p2 #user #opencode
- [ ] [[T-013 Po wczytaniu gry nie wyświetlają się ikony w inventory]] #bug #p1
- [ ] [[T-014 F5 quick save zapisuje w nowym slocie]] #feature #p2 #opencode
- [ ] [[T-015 Continue w menu głównym tylko przy trwającej grze]] #feature #p2 #opencode
- [ ] [[T-016 Load w menu głównym pokazuje wybór slotu i wczytuje grę]] #feature #p2 #opencode
- [ ] [[T-017 DeathScreen i DeadState pokazują wybór slotu do wczytania]] #feature #p2


%% kanban:settings
```
{"kanban-plugin":"board","list-collapse":[false,false,false,false,false,true,true],"lane-width":280,"show-checkboxes":true,"new-line-trigger":"enter","new-note-folder":"Backlog","new-note-template":"_templates/_Template.md","tag-action":"kanban","tag-sort":[{"tag":"#p1"},{"tag":"#p2"},{"tag":"#p3"}],"date-trigger":"@","time-trigger":"@@","date-format":"YYYY-MM-DD","date-display-format":"YYYY-MM-DD","show-relative-date":true,"date-link-to-daily-note":false,"move-dates":true,"move-tags":true,"date-picker-week-start":1,"tag-colors":[{"tagKey":"#p1","color":"#04201c","backgroundColor":"rgba(255, 170, 12, 1)"},{"tagKey":"#p2","color":"#04201c","backgroundColor":"rgba(209, 172, 100, 1)"},{"tagKey":"#p3","color":"#2a2620","backgroundColor":"#b0a494"},{"tagKey":"#bug","color":"#ffffff","backgroundColor":"#f46262"},{"tagKey":"#feature","color":"#04261a","backgroundColor":"#56c480"},{"tagKey":"#chore","color":"#1a1d22","backgroundColor":"rgba(112, 138, 180, 1)"},{"tagKey":"#spike","color":"#04122a","backgroundColor":"#5ea2f7"},{"tagKey":"#docs","color":"#1a0f2e","backgroundColor":"#b086f0"},{"tagKey":"#raw","color":"#2a2620","backgroundColor":"rgba(102, 159, 143, 1)"},{"tagKey":"#blocked","color":"#2a1206","backgroundColor":"#ff8048"},{"tagKey":"#review","color":"#04241c","backgroundColor":"rgba(201, 64, 186, 1)"},{"tagKey":"#cc","color":"#04241c","backgroundColor":"rgba(250, 111, 45, 1)"},{"tagKey":"#opencode","color":"#04241c","backgroundColor":"rgba(131, 129, 129, 1)"},{"tagKey":"#pi","color":"#04241c","backgroundColor":"rgba(255, 255, 255, 1)"},{"tagKey":"#hermes","color":"#04241c","backgroundColor":"rgba(255, 244, 12, 1)"},{"tagKey":"#example","color":"#222222","backgroundColor":"rgba(108, 108, 114, 1)"}],"date-colors":[],"show-add-list":false,"show-view-as-markdown":false,"move-task-metadata":true}
```
%%
