# Justfile - Misadventures of Malachi task runner
# Compatible with both Unix (macOS, Linux) and Windows

# Set help to show all recipes when running `just` without arguments
default:
    @just --list

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
