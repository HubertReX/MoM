#!/bin/bash


# Fail-safe directives

set -o errexit    # Exit immediately if any command fails
set -o nounset    # Treat unset variables as an error
set -o pipefail   # Fail pipeline if any command in it fails

# start OpenCode to automatically take tasks from board
Tasks/bin/moab watch --agent opencode --model "opencode/big-pickle" --interval 5
