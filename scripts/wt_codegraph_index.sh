#!/usr/bin/env bash
# Zbuduj indeks CodeGraph w bieżącym worktree (hook post-start dla worktrunk).
#
# Indeksu nie da się podlinkować z głównego worktree: baza trzyma bezwzględne
# ścieżki plików, więc `codegraph explore` w gałęzi zwracałby kod z maina.
# Trzeba zbudować od nowa (ok. 45 MB, kilkadziesiąt sekund) - stąd post-start,
# w tle, po tym jak worktree jest już gotowy do pracy.
#
# Osobny skrypt zamiast jednej linijki w wt.toml, bo są tu dwie rzeczy, których
# nie da się czytelnie zapisać w TOML-u:
#   1. świeży worktree nie ma .codegraph/, a `codegraph index` wtedy odmawia
#      ("CodeGraph not initialized") - potrzebny jest `codegraph init`,
#   2. `init` nie ma `--quiet` i wypluwa ~38 KB animowanego paska postępu,
#      który zaśmieciłby log hooka (`wt config state logs`).

set -uo pipefail

if [[ -d .codegraph ]]; then
    codegraph index --quiet .
    status=$?
else
    # Pasek postępu jedzie po \r w jednej linii - rozbij go na linie i zostaw
    # tylko ogon (podsumowanie albo komunikat błędu).
    codegraph init . 2>&1 | tr '\r' '\n' | grep -v '░' | tail -5
    status=${PIPESTATUS[0]}
fi

exit "$status"
