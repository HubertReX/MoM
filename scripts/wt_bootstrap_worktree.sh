#!/usr/bin/env bash
# Bootstrap nowego worktree (hook pre-start dla worktrunk).
#
# Nowy worktree dostaje z gita tylko pliki śledzone, więc brakuje w nim
# środowiska: .venv (333 MB), venva MOAB-web, node_modules OpenCode i
# lokalnych ustawień Claude. Zamiast odtwarzać je od zera (uv venv + npm
# install przy każdym `wt switch --create`) podlinkowujemy je z głównego
# worktree - zależności są te same dla wszystkich gałęzi.
#
# Użycie: wt_bootstrap_worktree.sh <ścieżka-głównego-worktree>
#
# MOM_WT_OWN_VENV=1  -> nie linkuj .venv, zostaw direnv/`layout uv` żeby
#                       zbudował własne środowisko (gdy gałąź zmienia
#                       requirements.txt i nie chcesz ruszać główego venva).

set -euo pipefail

PRIMARY="${1:?podaj ścieżkę głównego worktree}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "$HERE" == "$PRIMARY" ]]; then
    echo "[wt-bootstrap] jestem w głównym worktree, nic do roboty"
    exit 0
fi

# Podlinkuj katalog z głównego worktree, o ile jeszcze go tu nie ma.
link_dir() {
    local rel="$1"
    local src="$PRIMARY/$rel"
    local dst="$HERE/$rel"

    if [[ ! -d "$src" ]]; then
        echo "[wt-bootstrap] pomijam $rel (brak w $PRIMARY)"
        return 0
    fi
    if [[ -e "$dst" || -L "$dst" ]]; then
        echo "[wt-bootstrap] pomijam $rel (już istnieje)"
        return 0
    fi
    mkdir -p "$(dirname "$dst")"
    ln -s "$src" "$dst"
    echo "[wt-bootstrap] symlink $rel -> $src"
}

# Skopiuj plik z głównego worktree (kopia, nie link - to stan lokalny,
# który każdy worktree może zmieniać niezależnie).
copy_file() {
    local rel="$1"
    local src="$PRIMARY/$rel"
    local dst="$HERE/$rel"

    if [[ ! -f "$src" ]]; then
        echo "[wt-bootstrap] pomijam $rel (brak w $PRIMARY)"
        return 0
    fi
    if [[ -e "$dst" ]]; then
        echo "[wt-bootstrap] pomijam $rel (już istnieje)"
        return 0
    fi
    mkdir -p "$(dirname "$dst")"
    \cp "$src" "$dst"
    echo "[wt-bootstrap] kopia $rel"
}

if [[ "${MOM_WT_OWN_VENV:-0}" == "1" ]]; then
    echo "[wt-bootstrap] MOM_WT_OWN_VENV=1 - własny .venv, nie linkuję"
else
    # Główny venv gry. Projekt nie jest instalowany editable (site-packages
    # ma tylko zależności), więc współdzielenie jest bezpieczne - importy
    # `project.*` i tak idą z katalogu roboczego.
    link_dir .venv
fi

# Venv serwera MOAB-web (Tasks/web/run.sh sam by go zbudował, ale to 17 MB
# i kilkanaście sekund przy każdym worktree).
link_dir Tasks/web/.venv

# Wtyczki OpenCode (npm). Cała zawartość .opencode/ poza konfiguracją
# agentów jest nieśledzona i ukryta lokalnym .opencode/.gitignore - jego
# też trzeba skopiować, inaczej node_modules wyskoczy w `git status`.
copy_file .opencode/.gitignore
link_dir .opencode/node_modules
copy_file .opencode/package.json
copy_file .opencode/package-lock.json

# Lokalne zgody/ustawienia Claude Code (nieśledzone, per-maszyna).
copy_file .claude/settings.local.json

# Świeży worktree nie ma plików sterowania agentem; agent_ctrl czyta
# agent_input.txt przy starcie, więc niech istnieje pusty.
: > "$HERE/agent_input.txt"

echo "[wt-bootstrap] gotowe"
