#!/bin/bash


# Fail-safe directives

set -o errexit    # Exit immediately if any command fails
set -o nounset    # Treat unset variables as an error
set -o pipefail   # Fail pipeline if any command in it fails

# MOM_SKIP_SS_REVIEW=1  just test-agent 'Display Settings Flow'
# Desktop
just test-agent 'Display Settings Flow'
# Web
just test-web   'Display Settings Flow'
