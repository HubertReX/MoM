#!/bin/bash
# ss-rev.sh — ręczne uruchomienie ss-reviewer agenta dla screenshotu MoM.
#
# Użycie:
#   ./ss-rev.sh <ścieżka/do/screenshotu.png> [oczekiwany_stan]
#
# UWAGA: ścieżkę podajemy INLINE w treści prompta, a nie przez -f.
# -f wymaga modelu z vision (attachment + modalities.input: ["text","image"]),
# a domyślny model agenta (opencode-go/mimo-v2.5) vision nie ma.
#
# Force vision model: export MOM_SS_REVIEW_MODEL='google/gemini-3.1-flash-lite'
# lub: opencode run ... --model google/gemini-3.1-flash-lite

set -o errexit
set -o nounset
set -o pipefail

SCREENSHOT="${1:?Usage: $0 <screenshot.png> [expected_state]}"
EXPECTED="${2:-MENU_MAIN}"

# opencode run --agent ss-reviewer \
#   "Analyze this MoM game screenshot: ${SCREENSHOT}. What game state is shown? Report in the format described in your instructions. Expected state: ${EXPECTED}."
# opencode run --agent ss-reviewer "Analyze this MoM game screenshot png What game state is shown? Report in the format described in your instructions.." -f "/Users/hubertnafalski/Projects/MoM/screenshots/dialog_hammer_formatting.png" --model "google/gemini-3.1-flash-lite" --pure
opencode run --agent ss-reviewer "Analyze this MoM game screenshot png What game state is shown? Report in the format described in your instructions.." -f "${SCREENSHOT}" --model "google/gemini-3.1-flash-lite" --pure
