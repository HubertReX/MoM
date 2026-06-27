#!/bin/bash


# Fail-safe directives

set -o errexit    # Exit immediately if any command fails
set -o nounset    # Treat unset variables as an error
set -o pipefail   # Fail pipeline if any command in it fails

# test install
./moab install ~/Projects/dummy --with-plugins --with-theme --hook --keep-demo  # setup gry
# ./moab new "Dodaj licznik FPS" --type feature --prio p2 --lane ready                     # zadanie
# ./moab assign T-001 --agent opencode
