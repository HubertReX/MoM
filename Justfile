# Justfile - Misadventures of Malachi task runner
# Compatible with both Unix (macOS, Linux) and Windows

# Set help to show all recipes when running `just` without arguments
default:
    @just --list

[unix]
setup:
    @if [ ! -d ".venv" ]; then \
        echo "Creating virtual environment using uv..."; \
        uv venv; \
    fi
    .venv/bin/uv pip install -r requirements.txt -r requirements-dev.txt

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

[unix]
run *args:
    export PYGAME_HIDE_SUPPORT_PROMPT=1
    cd project && ../.venv/bin/python ./main.py {{args}}

[windows]
run *args:
    #!powershell
    $env:PYGAME_HIDE_SUPPORT_PROMPT="1"
    cd project
    ..\.venv\Scripts\python.exe main.py {{args}}

[unix]
serve-web:
    .venv/bin/python -m pygbag --ume_block 0 --template utils/black.tmpl --icon project/assets/icon.png --no_opt project

[windows]
serve-web:
    #!powershell
    .venv\Scripts\python.exe -m pygbag --ume_block 0 --template utils/black.tmpl --icon project/assets/icon.png --no_opt project

[unix]
update-config-schema:
    cd project/config_model && ../../.venv/bin/python config_pydantic.py

[windows]
update-config-schema:
    #!powershell
    cd project/config_model
    ..\..\.venv\Scripts\python.exe config_pydantic.py

[unix]
mypy:
    .venv/bin/mypy --config-file pyproject.toml project

[windows]
mypy:
    #!powershell
    .venv\Scripts\mypy.exe --config-file pyproject.toml project

[unix]
sourcery:
    @if [ -f .venv/bin/sourcery ]; then \
        .venv/bin/sourcery review project; \
    elif command -v sourcery >/dev/null 2>&1; then \
        sourcery review project; \
    else \
        echo "Sourcery is not installed. Uncomment it in requirements-dev.txt and run 'just setup'."; \
    fi

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

# Run all static analysis and code checks
check: sourcery mypy

[unix]
fix-bad-png:
    mogrify *.png

[windows]
fix-bad-png:
    #!powershell
    .venv\Scripts\python.exe utils\fix_bad_png.py

[unix]
find-bad-png:
    pngcrush -n -q **/*.png 2> >(grep -v "Total")

[unix]
mem-profiling:
    cd project && ../.venv/bin/memray run --live main.py

[windows]
cpu-profiling:
    #!powershell
    cd project
    austin -t 4s -x 5 -bo "..\profiling\austin_$((Get-Date).ToString('yyyyMMdd_HHmmss')).aprof" ..\.venv\Scripts\python.exe main.py

[unix]
build-itchio:
    .venv/bin/pygbag --ume_block 0 --template utils/black.tmpl --icon project/assets/icon.png --no_opt --archive project

[unix]
start-oc-agent:
    Tasks/bin/moab watch --agent opencode --model "opencode/big-pickle" --interval 5
