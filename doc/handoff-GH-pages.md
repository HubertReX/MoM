## Kontekst

Repozytorium MoM (Misadventures of Malachi) na GitHubie (`HubertReX/MoM`) ma GitHub Actions do deploy na GitHub Pages. Użytkownik poprosił o uruchomienie workflowu i naprawienie problemów z deployem. Sesja dotyczyła diagnozy i naprawy pipeline'u GitHub Actions oraz problemów z uruchomieniem gry (Python/pygame-ce) w przeglądarce przez pygbag.

## Co zostało zrobione

1. **GitHub Pages włączone** - portal nie miał włączonego Pages (API zwracało 404). Włączono ręcznie przez API GitHub, Pages serwuje z brancha `gh-pages`.

2. **Naprawiony martwy URL browserfs** - szablon `utils/black.tmpl` (wersja 0.9.0) ładował `browserfs.min.js` z `cdn/0.9.3/` co dawało 404. Zmieniono URL na `archives/0.9/browserfs.min.js` (który jest żywy).

3. **Przeportowano szablon na wersję 0.9.4** - nowy loader pygbag 0.9.4 nie używa BrowserFS/MM.prepare tylko ekstrahuje przez `tarfile` i `shell.source`. Zaadoptowano customizacje "black" (czarne tło, pixelated canvas, custom_postrun). Commit: zmiana w `utils/black.tmpl`.

4. **Naprawiono `settings.py`** - usunięto `from pygame.colordict import THECOLORS as COLORS`, zwendorowano słownik kolorów (gra używa tylko `COLORS["black"]` i `COLORS["blue"]`), bo pygbag hook importów blokował import submodułów pygame.

## Co próbowano i z jakim skutkiem

- **Lokalny serwer HTTP do testów** - serwer bindował się tylko na IPv6 (`::1`), Chrome próbował IPv4 `127.0.0.1` → `ERR_CONNECTION_REFUSED`. Problem nierozwiązany (nieistotny - testowałem na innej maszynie).
- **importlib.import_module jako obejście hooka pygbag** - pygbag przechwytuje importy na poziomie systemu importów (owija `__import__`), więc importlib też przez niego przechodzi. **Nie działa**.
- **Cache bust przeglądarki** - tar.gz i IndexedDB cache'owane przez pygbag. Wyczyszczono IDB + cache przez `fetch(..., {cache:'reload'})`.
- **Wersja pygbag 0.9.3 vs 0.9.2** - kluczowe odkrycie: CI robił `pip install pygbag` (najnowsza 0.9.3), a repo pinuje `pygbag==0.9.2` w `requirements.txt`. Wersja 0.9.3 ma agresywny hook importów i inny runtime (cdn/0.9.3), podczas gdy 0.9.2 używa `archives/0.9/` (żywy, z BrowserFS, kompatybilny z oryginalnym `black.tmpl`).

## Aktualny stan i blocker

**Deploy jest skonfigurowany** (Pages włączone, workflow buduje, `gh-pages` istnieje).

**Gra nie uruchamia się w przeglądarce** bo sesja skończyła się przed wykonaniem ostatecznego fixu:

- workflow wciąż instaluje `pygbag==0.9.3` (najnowsza) zamiast przypiętego `0.9.2`
- `black.tmpl` został przeportowany na 0.9.4 (cofnąć!)
- `settings.py` został zmodyfikowany (cofnąć!)

**Kluczowe odkrycie**: pygbag 0.9.2 używa CDN `archives/0.9/` (który jest żywy), NIE `cdn/0.9.2/`. Więc przypięcie 0.9.2 + cofnięcie zmian w szablonie powinno naprawić wszystko.

## Następne kroki

1. **Przypiąć `pygbag==0.9.2` w workflowach GitHub Actions** - zmienić `pip install pygbag` na `pip install pygbag==0.9.2` w `.github/workflows/pygbag_build.yml` (zmiana została przygotowana w turze 122 ale nie zdążono zrobić commita przez limit sesji)
2. **Cofnąć przeportowanie `black.tmpl` na 0.9.4** - przywrócić oryginalny szablon 0.9.0 (z `MM.prepare` + BrowserFS) - `git checkout` lub revert commita z tur 65-70
3. **Cofnąć zmiany w `settings.py`** - przywrócić oryginalny import `from pygame.colordict import THECOLORS as COLORS`
4. **Zrobić rebuild i weryfikację** - workflow → Pages → przeglądarka → gra powinna wystartować

## Kluczowe pliki, komendy i adresy

- **Repo**: `/Users/hnafalsk/Projects/MoM`, remote `HubertReX/MoM`
- **Workflow**: `.github/workflows/pygbag_build.yml` - tu zmienić pin na `pygbag==0.9.2`
- **Template**: `utils/black.tmpl` - przywrócić oryginalną wersję 0.9.0 (commit cofający)
- **Settings gry**: `tarcheck/assets/settings.py` (linia 15 - import colordict)
- **Requirements**: `requirements.txt` + `requirements-dev.txt` (już pinują `pygbag==0.9.2`)
- **GitHub Pages URL**: `https://hubertrex.github.io/MoM/main/`
- **CDN runtime (żywy)**: `https://pygame-web.github.io/archives/0.9/`
- **CDN runtime (martwy)**: `https://pygame-web.github.io/cdn/0.9.2/` (usunięty)
- **CDN runtime 0.9.3**: `https://pygame-web.github.io/cdn/0.9.3/` (żywy, ale niekompatybilny)
- **Build komenda lokalna**: `just build-itchio` lub `just serve-web` (justfile linia 52, 213)

## Wskaźnik do źródła

- **sessionId**: `8095b91c-f90b-4a79-9247-d846414b1e65`
- **Ścieżka transkryptu**: `/Users/hnafalsk/.claude/projects/-Users-hnafalsk-Projects-MoM/8095b91c-f90b-4a79-9247-d846414b1e65.jsonl`
- **Liczba tur**: 123 (4 user / 119 assistant)
- **Czas trwania**: 2026-07-12 19:01 - 20:57 UTC
