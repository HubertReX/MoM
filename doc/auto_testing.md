# Przykłady samodzielnego użycia

## Szybki test bez vision

```bash
MOM_SKIP_SS_REVIEW=1 MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  .venv/bin/python3 tests/automate_display_test.py "TextInput Demo Hotkey"
  
# Test z vision (domyślny model mimo-v2.5)
MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  .venv/bin/python3 tests/automate_display_test.py "TextInput Demo Hotkey"

#Test z konkretnym modelem vision
MOM_SS_REVIEW_MODEL='google/gemini-3.1-flash-lite' MOM_AGENT_CONTROL=1 \
  SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  .venv/bin/python3 tests/automate_display_test.py "Display Settings Flow"

#Ręczna analiza screenshotu przez ss-reviewer
# przez skrypt (ustaw execute: chmod +x ss-rev.sh)
./ss-rev.sh screenshots/agent/agent_20260708_151153_textinput_demo_hotkey_01_at_main_menu.png MENU_MAIN

# albo bezpośrednio przez opencode
opencode run --pure --agent ss-reviewer \
  "Analyze this MoM game screenshot: screenshots/agent/agent_20260708_151153_textinput_demo_hotkey_01_at_main_menu.png. Expected state: MENU_MAIN."

#Wszystkie scenariusze na raz (uwaga: długo!)
MOM_SKIP_SS_REVIEW=1 MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  .venv/bin/python3 tests/automate_display_test.py
  
