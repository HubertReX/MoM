#!/bin/bash


# Fail-safe directives

set -o errexit    # Exit immediately if any command fails
set -o nounset    # Treat unset variables as an error
set -o pipefail   # Fail pipeline if any command in it fails

# ss-reviewer run
opencode run --agent ss-reviewer "Analyze this MoM game screenshot: /Users/hubertnafalski/Projects/MoM/screenshots/agent/agent_20260705_170854_textinput_demo_hotkey_01_at_main_menu.png. What game state is shown? Report in the format described in your instructions. Expected state: MENU_MAIN (main menu)."

# opencode run --agent ss-reviewer --model google/gemini-3.1-flash-lite -f "$1" "Analyze this MoM game screenshot. What game state is shown? Report the format described in your instructions. Expected state: MENU_MAIN (main menu)." 
