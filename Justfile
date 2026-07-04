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

# Fix libpng sRGB profile warnings in PNG files using mogrify
[unix]
fix-bad-png:
    mogrify *.png

# Fix libpng sRGB profile warnings in PNG files using Python
[windows]
fix-bad-png:
    #!powershell
    .venv\Scripts\python.exe utils\fix_bad_png.py

# Find PNG files with incorrect libpng sRGB profiles using pngcrush
[unix]
find-bad-png:
    pngcrush -n -q **/*.png 2> >(grep -v "Total")

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
