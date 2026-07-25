# Prompt startowy - Faza 1 (model: Opus)

Skopiuj poniższy prompt do nowej sesji Claude Code (Opus) w katalogu repo MoM.

---

Realizujesz Fazę 1 backlogu audytu (fundament autonomii agentów AI). Kontekst i zasady:

1. Przeczytaj `doc/audyt/audyt.md` (indeks, legenda oznaczeń, decyzje kierunkowe,
   zasady realizacji zadań) - decyzje kierunkowe są wiążące, nie otwieraj ich na nowo.
2. Zadania Fazy 1 wykonuj po kolei, każde wg jego pliku w `doc/audyt/`:
   - A01 - ss-review: stabilny model, checklisty, werdykt JSON
   - A02 - agent_ctrl: `debug_ui_state` + asercje stanu w runnerze
   - A03 - layout self-checks w UI (overflow = twardy błąd)
   - A04 - tryb deterministyczny testów (seed świata i cząstek, parametr godziny)
   - C01 - `just validate-world`: walidator encji cross-source
   - F01 - cleanup `utils/`: pliki produkcyjne do `scripts/`, CI, codegraph ignore
   - F03 - mypy do zera (23 błędy; warunek startu Fazy 2)
   - F02 - aktualizacja AGENTS.md i docs design systemu (celowo ostatnie - A01
     i inne zadania też modyfikują dokumentację)
   Kolejność możesz lokalnie zmienić, jeśli coś Cię blokuje - odnotuj dlaczego.
3. Rytm pracy na JEDNO zadanie: przeczytaj plik zadania w całości → wykonaj kroki →
   spełnij WSZYSTKIE kryteria akceptacji → wykonaj sekcję "Po zakończeniu" (aktualizacja
   AGENTS.md, odhaczenie w audyt.md, commit na main z podanym opisem). Dopiero potem
   następne zadanie. Jeden commit = jedno zadanie.
4. Twarde zasady repo: commit bezpośrednio na `main`, ŻADNYCH feature branchy;
   każda zmiana działa na desktop i web (`IS_WEB`); type hints wymagane;
   stałe do `settings.py`; po zmianach `just test-unit` musi przechodzić w całości.
5. Gdy kryterium akceptacji nie daje się spełnić albo plik zadania rozjeżdża się
   z rzeczywistością kodu - STOP, opisz problem i zapytaj mnie (AskUserQuestion),
   nie improwizuj obejścia.
6. Na koniec sesji: raport co zrobione / co zostało, stan checkboxów w
   `doc/audyt/audyt.md` zgodny z rzeczywistością.

Zacznij od A01.

---

Uwagi dla mnie (nie kopiować): pełny raport audytu to
`doc/_attachements/audyt-architektury-2026-07-25.html`; sesja może nie zmieścić
wszystkich 8 zadań - kolejną sesję zaczynam tym samym promptem, agent sam pominie
odhaczone zadania.
