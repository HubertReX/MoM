# Prompt startowy - Faza 2 (model: Fable)

Skopiuj poniższy prompt do nowej sesji Claude Code (Fable) w katalogu repo MoM.
Warunek startu: Faza 1 odhaczona w `doc/audyt/audyt.md` (w szczególności A01-A03,
C01 i F03 - bramki refactoru na nich polegają).

---

Realizujesz Fazę 2 backlogu audytu: wielki refactor rdzenia. Kontekst i zasady:

1. Przeczytaj `doc/audyt/audyt.md` (indeks, legenda, decyzje kierunkowe - wiążące)
   oraz W CAŁOŚCI `doc/audyt/B01-refactor-rdzenia.md`. Sprawdź, że zadania Fazy 1
   (A01-A03, C01, F03) są odhaczone - jeśli nie, STOP i zgłoś mi to.
2. B01 ma dwa etapy z bramką akceptacji:
   - **Etap 0:** dokument architektury docelowej (HTML w `doc/_attachements/` + md
     w `doc/`) wg wytycznych z pliku zadania. Po jego ukończeniu ZATRZYMAJ SIĘ
     i przedstaw mi dokument do akceptacji. Nie zaczynaj przenoszenia kodu bez
     mojego wyraźnego "akceptuję".
   - **Etap 1:** wykonanie wg zaakceptowanego planu, krok po kroku; po KAŻDYM kroku
     wszystkie bramki z pliku zadania (test-unit, mypy=0, scenariusze agentowe,
     validate-world, benchmark) i osobny commit "B01 krok N: <co>".
3. Po B01: `doc/audyt/` zawiera też G01 (codegen configu web z pydantic) i B02
   (polityka wersji save) - jeżeli pliki zadań istnieją, realizuj je tak samo;
   jeżeli nie, zapytaj mnie, czy mamy je najpierw rozpisać.
4. Twarde zasady repo: commit bezpośrednio na `main`, ŻADNYCH feature branchy;
   dual-target desktop+web; kroki refactoru małe (< ~600 linii diffu), każdy
   osobno odwracalny przez git revert.
5. Kontrakty nietykalne (szczegóły w pliku zadania): format save/load, API używane
   przez agent_ctrl i testy, pułapki importu by-value (`import settings` + odczyt
   dynamiczny w nowych modułach).
6. Gdy bramka nie przechodzi albo plan rozjeżdża się z kodem - STOP, opisz problem
   i zapytaj mnie. Nie improwizuj obejścia i nie poszerzaj zakresu kroku.

Zacznij od etapu 0.

---

Uwagi dla mnie (nie kopiować): pełny raport audytu to
`doc/_attachements/audyt-architektury-2026-07-25.html`. Etap 0 kończy się moją
akceptacją architektury - dopiero po niej (może być w tej samej lub nowej sesji)
rusza etap 1. Pliki zadań G01/B02 rozpisujemy w sesji audytowej razem z Fazą 3/4.
