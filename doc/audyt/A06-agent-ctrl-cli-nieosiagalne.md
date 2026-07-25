# A06 - CLI `agent_ctrl.py` nic nie wysyła (martwy blok po `sys.exit`)

Priorytet: **P2** (Faza 1, drobny fix). Rozmiar: XS. Zależności: brak.

## Kontekst i problem

`project/agent_ctrl.py` dokumentuje w swoim docstringu tryb CLI:

```bash
python project/agent_ctrl.py down accept
python project/agent_ctrl.py up:30 right:15 attack screenshot
```

Ten tryb **nie działa**. Blok `__main__` ma złe wcięcia: dwie ostatnie linie
(`print` z podpowiedzią i `sys.exit(1)`) wyszły poza `if len(sys.argv) < 2`, więc
proces kończy się **zawsze** kodem 1, zanim dojdzie do wysłania komend:

```python
    if len(sys.argv) < 2:
        print("Usage: python project/agent_ctrl.py <action[:frames]> [more...]")
        print("  e.g. python project/agent_ctrl.py down accept")
        print("       python project/agent_ctrl.py up:30 right:15 attack screenshot")
    print("  special: screenshot, exit, debug_map_change")   # <- poza if
    sys.exit(1)                                               # <- poza if

    AgentController.send(sys.argv[1:], input_file)             # <- nieosiągalne
    print(f"sent: {' '.join(sys.argv[1:])}  ->  {input_file}") # <- nieosiągalne
```

Skutek: agent, który zaufa docstringowi, dostaje exit 1 bez żadnego efektu i nie ma
jak się domyślić dlaczego (komunikat "Usage" wygląda jak zwykła pomoc). Obejściem,
którego wszyscy dziś używają, jest `echo "..." > agent_input.txt` - też opisane
w docstringu, więc problem był niewidoczny.

Znalezione przy okazji F03 (mypy do zera); nie naprawione tam, bo F03 miał mieć diff
czysto typowy, a to jest zmiana zachowania.

## Cel

`python project/agent_ctrl.py down accept` faktycznie zapisuje komendy do
`agent_input.txt` i kończy się kodem 0. Wywołanie bez argumentów pokazuje pomoc
i kończy się kodem 1.

## Pliki do zmiany

- `project/agent_ctrl.py` - wyłącznie blok `if __name__ == "__main__":`

## Kroki

1. Wciągnij `print("  special: ...")` i `sys.exit(1)` do wnętrza `if len(sys.argv) < 2:`.
2. Zostaw `AgentController.send(...)` i potwierdzenie na poziomie modułu - wykonają się
   tylko wtedy, gdy argumenty są.
3. Przy okazji uzupełnij listę komend specjalnych w tej pomocy - jest niepełna
   (brakuje m.in. `talk_to_char`, `walk_to_char`, `walk_to_point`, `debug_ui_state`,
   `debug_enter_maze`, `debug_set_maze`, `type:`, `backspace`). Pełna lista jest
   w docstringu modułu na górze pliku - nie dubluj jej w całości, wypisz nazwy.

## Kryteria akceptacji

1. `.venv/bin/python3 project/agent_ctrl.py down accept; echo $?` - kod **0**,
   a `agent_input.txt` zawiera `down accept`.
2. `.venv/bin/python3 project/agent_ctrl.py; echo $?` - kod **1** i wypisana pomoc.
3. Uruchomiona gra z `MOM_AGENT_CONTROL=1` reaguje na komendę wysłaną tym CLI
   (smoke ręczny: odpal grę, wyślij `screenshot`, sprawdź `screenshots/agent/`).
4. `just mypy` nadal `Success: no issues found`.
5. `just test-unit` przechodzi (runner testów nie używa tego CLI - pisze do pliku
   wprost - więc nic nie powinno się zmienić).

## Pułapki

- Nie przenoś logiki CLI do funkcji ani nie dodawaj `argparse` - to celowo
  kilkulinijkowy pomocnik, a docstring modułu jest jego dokumentacją.
- `input_file` ma dwie ścieżki (import z `settings` albo fallback dla uruchomienia
  spoza gry) - obie muszą dalej działać.

## Po zakończeniu

- odhacz A06 w `doc/audyt/audyt.md`
- commit: `A06: agent_ctrl CLI - naprawa wcięć, przez które nic nie było wysyłane`
