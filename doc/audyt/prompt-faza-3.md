# Prompt startowy - Faza 3 (brakujące mechaniki)

Skopiuj poniższy prompt do nowej sesji Claude Code w katalogu repo MoM.
Warunek startu: Fazy 1 i 2 odhaczone w `doc/audyt/audyt.md` (są - stan na 2026-07-28).

---

Realizujesz Fazę 3 backlogu audytu: brakujące mechaniki. Kontekst i zasady:

1. Przeczytaj `doc/audyt/audyt.md` (indeks, legenda, decyzje kierunkowe - wiążące),
   a przed każdym zadaniem jego plik W CAŁOŚCI. Rdzeń jest po refactorze B01: systemy
   mieszkają w pakietach `project/scene/` i `project/characters/`, na klasach zostały
   cienkie delegaty - nie dopisuj nowej logiki do klas `Scene`/`NPC`.

2. Kolejność (zależności są realne, nie kosmetyczne):
   - **E01** filtr nocy na desktop+web (cache + zdjęcie gałęzi `IS_WEB`)
   - **E02** `FPS_CAP=60` + profiler i profil web - mierzy JUŻ docelowy pipeline z E01
   - **D01** AudioManager (największe; niezależne od E01/E02, można przeplatać)
   - **H02** dzienny autosave o 6:00 (małe; druga połowa zadania zrobiona przy B02)
   - **U01** `bar.py` z `scrollbar.png` (małe, izolowane)
   - **D02** dokument decyzyjny progresji statystyk - **kończy się dokumentem**,
     zero kodu gry, potem STOP i pytanie do mnie o akceptację

3. Dwa zadania mają wbudowaną bramkę „zapytaj autora":
   - **D01 krok 0**: sonda web (czy pygbag gra ogg, czy autoplay potrzebuje gestu) -
     wynik zapisz w pliku zadania ZANIM zbudujesz resztę systemu;
   - **D02**: dokument do akceptacji przed jakąkolwiek implementacją.

4. Bramki po każdym zadaniu: `just test-unit` w całości, `just mypy` = 0,
   `just validate-world`, `just validate-locale`, `MOM_SKIP_SS_REVIEW=1 just test-smoke`
   (6 scenariuszy, ~96 s). Pełne zestawy (`just test-agent`, `just test-web`) tylko
   tam, gdzie plik zadania tego wymaga - są drogie.

5. Twarde zasady repo: commit bezpośrednio na `main`, ŻADNYCH feature branchy;
   każda zmiana działa na desktop I web (złota zasada dual-target); ręcznie edytowana
   konfiguracja w TOML/CSV, nigdy w JSON.

6. Gdy bramka nie przechodzi, plan rozjeżdża się z kodem albo trzeba zmienić decyzję
   z pliku zadania - STOP, opisz problem i zapytaj mnie. Nie improwizuj obejścia
   i nie poszerzaj zakresu.

Zacznij od E01.

---

Uwagi dla mnie (nie kopiować): pełny raport audytu to
`doc/_attachements/audyt-architektury-2026-07-25.html`. E03 (mgła wojny w labiryncie)
jest świadomie poza Fazą 3 - to plan na Fazę 4, po E01. Assety audio biorę z
`~/Projects/RPG/sounds` (Pixabay, licencje w `sources.txt`/`sfx.txt`) - agent ma je
przekonwertować do ogg i zmieścić w budżecie 10 MB.
