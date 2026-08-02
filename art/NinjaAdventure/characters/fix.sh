#!/bin/bash


# Fail-safe directives

set -o errexit    # Exit immediately if any command fails
set -o nounset    # Treat unset variables as an error
set -o pipefail   # Fail pipeline if any command in it fails
# filename="${1:t:r}" && extension="${1:e}"
fn="$1"
ext="${fn##*.}"
# echo pixelfixer process "${fn}" "${fn%.*}-fixed.${ext}" 
pixelfixer process "${fn}" "${fn%.*}-fixed.${ext}" | jq

# pixelfixer recon input.png 6.125 6.125 64 112 out.png [dark] [palette]
