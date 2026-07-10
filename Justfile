# Justfile - Misadventures of Malachi task runner
# Compatible with both Unix (macOS, Linux) and Windows

# Set help to show all recipes when running `just` without arguments
default:
    @just --list

# Initialize virtual environment and install dependencies (uses 'uv' if available)
[unix]
setup:
    @if [ ! -d ".venv" ]; then \
        echo "Creating virtual environment using uv..."; \
        uv venv; \
    fi
    .venv/bin/uv pip install -r requirements.txt -r requirements-dev.txt

# Initialize virtual environment and install dependencies (uses 'uv' if available, falls back to standard pip)
[windows]
setup:
    #!powershell
    if (!(Test-Path .venv)) {
        Write-Host "Creating virtual environment..."
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            uv venv
        } else {
            python -m venv .venv
        }
    }
    if (Test-Path .venv\Scripts\uv.exe) {
        .venv\Scripts\uv.exe pip install -r requirements.txt -r requirements-dev.txt
    } else {
        .venv\Scripts\pip.exe install -r requirements.txt -r requirements-dev.txt
    }

# Run the desktop game. Accepts CLI commands: 'load' (csv->json), 'store' (json->csv), 'update' (config schema), or options like '-h'
[unix]
run *args:
    export PYGAME_HIDE_SUPPORT_PROMPT=1
    cd project && ../.venv/bin/python ./main.py {{args}}

# Run the desktop game. Accepts CLI commands: 'load' (csv->json), 'store' (json->csv), 'update' (config schema), or options like '-h'
[windows]
run *args:
    #!powershell
    $env:PYGAME_HIDE_SUPPORT_PROMPT="1"
    cd project
    ..\.venv\Scripts\python.exe main.py {{args}}

# Start pygbag local web server. Pass '--bind 0.0.0.0' to make it available on the local network (e.g. `just serve-web --bind 0.0.0.0`)
[unix]
serve-web *args:
    .venv/bin/python -m pygbag --ume_block 0 --template utils/black.tmpl --icon project/assets/icon.png --no_opt {{args}} project

# Start pygbag local web server. Pass '--bind 0.0.0.0' to make it available on the local network (e.g. `just serve-web --bind 0.0.0.0`)
[windows]
serve-web *args:
    #!powershell
    .venv\Scripts\python.exe -m pygbag --ume_block 0 --template utils/black.tmpl --icon project/assets/icon.png --no_opt {{args}} project

# Run agent-driven UI smoke tests on the DESKTOP build. Quote a scenario name to run one (`just test "Save and Load Basic"`); omit to run all desktop scenarios. Run `.venv/bin/python3 tests/automate_display_test.py -h` for full flags.
[unix]
test scenario="":
    #!/usr/bin/env bash
    if [ -z "{{scenario}}" ]; then
        .venv/bin/python3 tests/automate_display_test.py
    else
        .venv/bin/python3 tests/automate_display_test.py "{{scenario}}"
    fi

# Run the same agent-driven UI smoke tests on the WEB build (pygbag + Playwright Chromium). Scenario name FIRST (quoted), then optional flags: `just test-web "Corrupt Save Handling"`, `just test-web "Save and Load Basic" --timeout 25`, or `just test-web` for all web scenarios. Requires `playwright install chromium` (see requirements-dev.txt).
[unix]
test-web scenario="" *flags:
    #!/usr/bin/env bash
    if [ -z "{{scenario}}" ]; then
        .venv/bin/python3 tests/automate_display_test.py --web {{flags}}
    else
        .venv/bin/python3 tests/automate_display_test.py --web {{flags}} "{{scenario}}"
    fi

# Regenerate config JSON schema from the Pydantic models (desktop only)
[unix]
update-config-schema:
    cd project/config_model && ../../.venv/bin/python config_pydantic.py

# Regenerate config JSON schema from the Pydantic models (desktop only)
[windows]
update-config-schema:
    #!powershell
    cd project/config_model
    ..\..\.venv\Scripts\python.exe config_pydantic.py

# Import entity data from CSV files into config.json (overwrites character, item, chest, and maze sections)
[unix]
import-entities:
    .venv/bin/python project/config_model/import_entities.py

# Import dialog Markdown sources from project/assets/dialogs/ into config.json.
# By default imports all compatible characters; pass a character name to import one.
[unix]
import-dialogs *name:
    #!/usr/bin/env bash
    if [ -z "{{name}}" ]; then
        .venv/bin/python project/dialog/markdown_importer.py
    else
        .venv/bin/python project/dialog/markdown_importer.py "{{name}}"
    fi

# Regenerate dialog-system doc images (emote sheet + RichText tag palette) in doc/img/ from real MoM modules
[unix]
gen-dialog-docs:
    .venv/bin/python doc/gen_dialog_doc_assets.py

# Regenerate dialog-system doc images (emote sheet + RichText tag palette) in doc/img/ from real MoM modules
[windows]
gen-dialog-docs:
    #!powershell
    .venv\Scripts\python.exe doc\gen_dialog_doc_assets.py

# Run mypy static type checker on the project directory
[unix]
mypy:
    .venv/bin/mypy --config-file pyproject.toml project

# Run mypy static type checker on the project directory
[windows]
mypy:
    #!powershell
    .venv\Scripts\mypy.exe --config-file pyproject.toml project

# Check for code smells using Sourcery (if installed)
[unix]
sourcery:
    @if [ -f .venv/bin/sourcery ]; then \
        .venv/bin/sourcery review project; \
    elif command -v sourcery >/dev/null 2>&1; then \
        sourcery review project; \
    else \
        echo "Sourcery is not installed. Uncomment it in requirements-dev.txt and run 'just setup'."; \
    fi

# Check for code smells using Sourcery (if installed)
[windows]
sourcery:
    #!powershell
    if (Test-Path .venv\Scripts\sourcery.exe) {
        .venv\Scripts\sourcery.exe review project
    } elseif (Get-Command sourcery -ErrorAction SilentlyContinue) {
        sourcery review project
    } else {
        Write-Host "Sourcery is not installed. Uncomment it in requirements-dev.txt and run 'just setup'."
    }

# Run all static analysis and code checks (Sourcery + mypy)
check: sourcery mypy

# Fix all PNGs that have sRGB/gAMA/cHRM/iCCP chunks (strips profile chunks via mogrify)
[unix]
fix-bad-png:
    @python3 utils/find_bad_png.py | xargs -r mogrify -strip

# Fix libpng sRGB profile warnings in PNG files using Python
[windows]
fix-bad-png:
    #!powershell
    .venv\Scripts\python.exe utils\fix_bad_png.py

# Find PNGs with sRGB/gAMA/cHRM/iCCP chunks (potential libpng header warnings)
[unix]
find-bad-png:
    @python3 utils/find_bad_png.py

# Run memray live memory profiling (Unix only)
[unix]
mem-profiling:
    cd project && ../.venv/bin/memray run --live main.py

# Run austin CPU profiling on the running game (Windows only)
[windows]
cpu-profiling:
    #!powershell
    cd project
    austin -t 4s -x 5 -bo "..\profiling\austin_$((Get-Date).ToString('yyyyMMdd_HHmmss')).aprof" ..\.venv\Scripts\python.exe main.py

# Build the pygbag web.zip archive ready for itch.io deployment
[unix]
build-itchio:
    .venv/bin/pygbag --ume_block 0 --template utils/black.tmpl --icon project/assets/icon.png --no_opt --archive project

# Start the OpenCode watch agent to automatically process tasks from board
[unix]
start-oc-agent:
    Tasks/bin/moab watch --agent opencode --model "opencode/big-pickle" --interval 5
