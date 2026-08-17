# Justfile - Misadventures of Malachi task runner
# Compatible with both Unix (macOS, Linux) and Windows

# Set help to show all recipes when running `just` without arguments
default:
    @just --list

# Initialize virtual environment and install dependencies (uses `uv` if available). Rerun tu update modules.
[unix]
setup:
    # `--python 3.12` is also in `.python-version`;
    @if [ ! -d ".venv" ]; then \
        echo "Creating virtual environment using uv..."; \
        uv venv --python 3.12; \
    fi
    @if command -v uv >/dev/null 2>&1; then \
        uv pip install --python .venv/bin/python -r requirements.txt -r requirements-dev.txt; \
    else \
        .venv/bin/pip install -r requirements.txt -r requirements-dev.txt; \
    fi

# Initialize virtual environment and install dependencies (uses `uv` if available). Rerun to udpate modules.
[windows]
setup:
    #!powershell
    if (!(Test-Path .venv)) {
        Write-Host "Creating virtual environment..."
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            uv venv --python 3.12
        } else {
            python -m venv .venv
        }
    }
    # uv lives on PATH, not inside the venv - `uv venv` does not install it there
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        uv pip install --python .venv\Scripts\python.exe -r requirements.txt -r requirements-dev.txt
    } else {
        .venv\Scripts\pip.exe install -r requirements.txt -r requirements-dev.txt
    }

# Run the desktop game. Accepts CLI commands: `load` (csv->json), `store` (json->csv), `update` (config schema), or options like `-h`
[unix]
run *args:
    export PYGAME_HIDE_SUPPORT_PROMPT=1
    cd project && ../.venv/bin/python ./main.py {{args}}

# Run the desktop game. Accepts CLI commands: `load` (csv->json), `store` (json->csv), `update` (config schema), or options like `-h`
[windows]
run *args:
    #!powershell
    $env:PYGAME_HIDE_SUPPORT_PROMPT="1"
    cd project
    ..\.venv\Scripts\python.exe main.py {{args}}

# Start pygbag local web server. e.g: `--bind mac-mini.kamori-vector.ts.net --port 8989`. Append `#debug` to the URL to show debug console.
[unix]
serve-web *args:
    .venv/bin/python -m pygbag --ume_block 0 --template scripts/pygbag/black.tmpl --icon project/assets/icon.png --no_opt {{args}} project

# Start pygbag local web server. e.g: `--bind mac-mini.kamori-vector.ts.net --port 8989`. Append `#debug` to the URL to show debug console.
[windows]
serve-web *args:
    #!powershell
    .venv\Scripts\python.exe -m pygbag --ume_block 0 --template scripts/pygbag/black.tmpl --icon project/assets/icon.png --no_opt {{args}} project

# Fog of War prototype (E03): real maze + tileset, four visibility modes compared live. e.g: `--level 3 --seed 42`, `--shots <dir>` for headless screenshots
[unix]
fow-prototype *args:
    export PYGAME_HIDE_SUPPORT_PROMPT=1
    .venv/bin/python3 scripts/FoW-prototype.py {{args}}

# Fog of War prototype (E03): real maze + tileset, four visibility modes compared live. e.g: `--level 3 --seed 42`, `--shots <dir>` for headless screenshots
[windows]
fow-prototype *args:
    #!powershell
    $env:PYGAME_HIDE_SUPPORT_PROMPT="1"
    .venv\Scripts\python.exe scripts\FoW-prototype.py {{args}}

# Run the plain-Python unit tests (no pytest - each `tests/test_*.py` is its own runner). Optional filter: `just test-unit save_load`
[unix]
test-unit pattern="" *flags:
    .venv/bin/python3 scripts/run_unit_tests.py {{flags}} {{pattern}}

# Run the plain-Python unit tests (no pytest - each `tests/test_*.py` is its own runner). Optional filter: `just test-unit save_load`
[windows]
test-unit pattern="" *flags:
    #!powershell
    .venv\Scripts\python.exe scripts/run_unit_tests.py {{flags}} {{pattern}}

# Run agent-driven UI tests (DESKTOP). Example: `just test-agent "Save and Load Basic"`; Run `python tests/automate_display_test.py -h` for more.
[unix]
test-agent scenario="":
    #!/usr/bin/env bash
    if [ -z "{{scenario}}" ]; then
        .venv/bin/python3 tests/automate_display_test.py
    else
        .venv/bin/python3 tests/automate_display_test.py "{{scenario}}"
    fi

# Not supported on Windows - see the [unix] recipe above.
[windows]
test-agent scenario="":
    #!powershell
    Write-Host "test-agent is POSIX-only: tests/automate_display_test.py uses os.setsid/os.killpg,"
    Write-Host "a shell env-prefix GAME_CMD with a .venv/bin/python3 path, and gtimeout."
    Write-Host "Run it under WSL or on macOS/Linux."
    exit 1

# Quick gate: smoke set of agent-driven scenarios (DESKTOP, ~4-5 min instead of ~18). List: TEST_CONFIG["SMOKE_SCENARIOS"].
[unix]
test-smoke *flags:
    .venv/bin/python3 tests/automate_display_test.py --smoke {{flags}}

# Not supported on Windows - see the [unix] recipe above.
[windows]
test-smoke *flags:
    #!powershell
    Write-Host "test-smoke is POSIX-only: tests/automate_display_test.py uses os.setsid/os.killpg,"
    Write-Host "a shell env-prefix GAME_CMD with a .venv/bin/python3 path, and gtimeout."
    Write-Host "Run it under WSL or on macOS/Linux."
    exit 1

# Run agent-driven UI tests (WEB). One pygbag server for the whole run; `--web-restart-per-scenario` restores the old per-scenario restart. Example: `just test-web "Save and Load Basic" --timeout 25`. Run `playwright install chromium` (requirements-dev.txt).
[unix]
test-web scenario="" *flags:
    #!/usr/bin/env bash
    if [ -z "{{scenario}}" ]; then
        .venv/bin/python3 tests/automate_display_test.py --web {{flags}}
    else
        .venv/bin/python3 tests/automate_display_test.py --web {{flags}} "{{scenario}}"
    fi

# Not supported on Windows - see the [unix] recipe above.
[windows]
test-web scenario="" *flags:
    #!powershell
    Write-Host "test-web is POSIX-only: tests/automate_display_test.py kills the pygbag process"
    Write-Host "group with os.killpg and relies on POSIX process sessions."
    Write-Host "Run it under WSL or on macOS/Linux."
    exit 1

# Regenerate `config_schema.json` from the Pydantic models (desktop only)
[unix]
update-config-schema:
    cd project/config_model && ../../.venv/bin/python config_pydantic.py

# Regenerate `config_schema.json` from the Pydantic models (desktop only)
[windows]
update-config-schema:
    #!powershell
    cd project/config_model
    ..\..\.venv\Scripts\python.exe config_pydantic.py

# Import entity data from CSV files into `config.json` (overwrites character, item, chest, and maze sections)
[unix]
import-entities *ARGS:
    # Pass `--export` to go the other way: `config.json` -> CSV files (regenerates all columns).
    .venv/bin/python project/config_model/import_entities.py {{ARGS}}
    # A consistency error should surface while the author is editing content, not in
    # runtime as a silent print or a missing NPC. `import-dialogs` inherits this
    # through its cascade into this recipe, so it is not repeated there.
    just validate-world

# Import dialog Markdown sources from the `doc/` vault into `config.json`.
[unix]
import-dialogs *name:
    #!/usr/bin/env bash
    # Pipeline: MD frontmatter -> characters.csv -> config.json (import-entities
    # is the sole writer of the `characters` section, hence the cascade).
    # By default imports all compatible characters; pass a character name to import one.
    set -e
    if [ -z "{{name}}" ]; then
        .venv/bin/python project/dialog/markdown_importer.py
    else
        .venv/bin/python project/dialog/markdown_importer.py "{{name}}"
    fi
    just import-entities

# Import quest Markdown sources from the `doc/` vault into `config.json`.
[unix]
import-quests *chain:
    #!/usr/bin/env bash
    # PL (doc/PL/Misje/) is the source of truth: machine fields (Test, Requires,
    # Nagroda) are read from PL only, EN (doc/EN/Quests/) supplies prose. An invalid
    # condition or a broken graph fails the import and leaves config.json untouched.
    # By default imports every chain found; pass a chain key to import one (e.g. Q03).
    set -e
    if [ -z "{{chain}}" ]; then
        .venv/bin/python project/quest/markdown_importer.py
    else
        .venv/bin/python project/quest/markdown_importer.py "{{chain}}"
    fi
    # see the note in `import-entities`: content edits get validated on the spot
    just validate-world

# Import item notes from the `doc/` vault into `items.csv` (and on into `config.json`).
[unix]
import-items *ARGS:
    #!/usr/bin/env bash
    # Pipeline: doc/PL/Przedmioty/*.md -> items.csv -> config.json (import-entities
    # is the sole writer of the `items` section, hence the cascade).
    # Pass `--export` to go the other way: items.csv -> notes (first seeding,
    # regeneration). The export rewrites the frontmatter only, so prose survives.
    set -e
    .venv/bin/python project/config_model/items_markdown.py {{ARGS}}
    if [ -z "{{ARGS}}" ]; then
        just import-entities
    fi

# Import item notes from the `doc/` vault into `items.csv` (and on into `config.json`).
[windows]
import-items *ARGS:
    #!powershell
    .venv\Scripts\python.exe project\config_model\items_markdown.py {{ARGS}}
    if ("{{ARGS}}" -eq "") { just import-entities }

# Regenerate dialog-system doc images (emote sheet + RichText tag palette) in `doc/_attachements/` from real MoM modules
[unix]
gen-dialog-docs:
    .venv/bin/python scripts/gen_dialog_doc_assets.py

# Regenerate dialog-system doc images (emote sheet + RichText tag palette) in `doc/_attachements/` from real MoM modules
[windows]
gen-dialog-docs:
    #!powershell
    .venv\Scripts\python.exe scripts\gen_dialog_doc_assets.py

# Regenerate `config_model/config.py` (web) from the Pydantic model in `config_pydantic.py`
[unix]
gen-web-config:
    .venv/bin/python scripts/gen_web_config.py

# Regenerate `config_model/config.py` (web) from the Pydantic model in `config_pydantic.py`
[windows]
gen-web-config:
    #!powershell
    .venv\Scripts\python.exe scripts\gen_web_config.py

# Regenerate character faceset copies in `doc/_attachements/ (<KEY>.png)` from the sprite column of `characters.csv`
[unix]
gen-faces:
    .venv/bin/python scripts/gen_face_attachments.py

# Regenerate character faceset copies in `doc/_attachements/ (<KEY>.png)` from the sprite column of `characters.csv`
[windows]
gen-faces:
    #!powershell
    .venv\Scripts\python.exe scripts\gen_face_attachments.py

# Regenerate item icons in `doc/_attachements/ (item_<key>.png)` from the sprite sheets the game itself uses
[unix]
gen-item-icons *ARGS:
    # Pass `--scale N` for a bigger PNG (default 4, i.e. 64x64 from a 16x16 tile).
    .venv/bin/python scripts/gen_item_attachments.py {{ARGS}}

# Regenerate item icons in `doc/_attachements/ (item_<key>.png)` from the sprite sheets the game itself uses
[windows]
gen-item-icons *ARGS:
    #!powershell
    .venv\Scripts\python.exe scripts\gen_item_attachments.py {{ARGS}}

# Regenerate interactive dialog graphs (DataviewJS + vis-network) in `doc/_graphs/`.
[unix]
dialog-graph *key:
    #!/usr/bin/env bash
    # Run AFTER `just import-dialogs`. No arg = all characters; pass a dialog_key for one
    # (e.g. `just dialog-graph BARMAN_ABSINTHRAYNER`). Needs Dataview "Enable JavaScript Queries" in Obsidian.
    set -e
    if [ -z "{{key}}" ]; then
        .venv/bin/python scripts/dialog_graph.py --all --format json
    else
        .venv/bin/python scripts/dialog_graph.py -c "{{key}}" --format json
    fi

# Regenerate interactive dialog graphs (DataviewJS + vis-network) in `doc/_graphs/`.
[windows]
dialog-graph *key:
    #!powershell
    # Run AFTER `just import-dialogs`. No arg = all characters; pass a dialog_key for one
    # (e.g. `just dialog-graph BARMAN_ABSINTHRAYNER`). Needs Dataview "Enable JavaScript Queries" in Obsidian.
    if ("{{key}}" -eq "") {
        .venv\Scripts\python.exe scripts\dialog_graph.py --all --format json
    } else {
        .venv\Scripts\python.exe scripts\dialog_graph.py -c "{{key}}" --format json
    }

# Regenerate the interactive quest DAG (DataviewJS + vis-network) in `doc/_graphs/`.
[unix]
quest-graph:
    # Run AFTER `just import-quests`: the graph is built from config.json, so it shows
    # what the game sees. One note for every chain - the edges that matter cross them.
    # Needs Dataview "Enable JavaScript Queries" in Obsidian.
    .venv/bin/python scripts/quest_graph.py

# Regenerate the interactive quest DAG (DataviewJS + vis-network) in `doc/_graphs/`.
[windows]
quest-graph:
    # Run AFTER `just import-quests`: the graph is built from config.json, so it shows
    # what the game sees. One note for every chain - the edges that matter cross them.
    # Needs Dataview "Enable JavaScript Queries" in Obsidian.
    #!powershell
    .venv\Scripts\python.exe scripts\quest_graph.py

# Regenerate the quest authoring cheat sheet at `doc/quest-cheatsheet.md`.
[unix]
quest-cheatsheet:
    # Everything in it is derived from the code (enums, condition whitelist, validators),
    # so run it after changing any of them - a hand-kept cheat sheet lies with authority.
    .venv/bin/python scripts/gen_quest_cheatsheet.py

# Regenerate the quest authoring cheat sheet at `doc/quest-cheatsheet.md`.
[windows]
quest-cheatsheet:
    #!powershell
    .venv\Scripts\python.exe scripts\gen_quest_cheatsheet.py

# Run mypy static type checker on the `project` directory
[unix]
mypy:
    .venv/bin/mypy --config-file pyproject.toml project

# Run mypy static type checker on the `project` directory
[windows]
mypy:
    #!powershell
    .venv\Scripts\mypy.exe --config-file pyproject.toml project

# Check for code smells using Sourcery
[unix]
sourcery:
    @if [ -f .venv/bin/sourcery ]; then \
        .venv/bin/sourcery review project; \
    elif command -v sourcery >/dev/null 2>&1; then \
        sourcery review project; \
    else \
        echo "Sourcery is not installed. Uncomment it in requirements-dev.txt and run 'just setup'."; \
    fi

# Check for code smells using Sourcery
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

# Validate locale TOML files `EN.toml`, `PL.toml` (key symmetry + placeholder consistency)
[unix]
validate-locale:
    .venv/bin/python scripts/validate_locale.py

# Validate locale TOML files `EN.toml`, `PL.toml `(key symmetry + placeholder consistency)
[windows]
validate-locale:
    #!powershell
    .venv\Scripts\python.exe scripts\validate_locale.py

# Validate world entity consistency across maps, CSVs, config and routines
[unix]
validate-world *ARGS:
    # `--strict` makes warnings fail too; `--json` emits machine-readable output.
    .venv/bin/python scripts/validate_world.py {{ARGS}}

# Validate world entity consistency across maps, CSVs, config and routines
[windows]
validate-world *ARGS:
    #!powershell
    .venv\Scripts\python.exe scripts\validate_world.py {{ARGS}}

# Rename an entity key in every source at once (maps, CSVs, config, locale, Tiled). e.g: `just rename-entity Village BLUNDERHAVEN`
[unix]
rename-entity *ARGS:
    # The kind of key is detected from where the name stands today; `--kind` overrides it.
    # `--list` shows what exists, `--dry-run` shows what would change, `--sources` prints
    # the manifest of files the script knows (guarded by tests/test_rename_entity.py).
    .venv/bin/python scripts/rename_entity.py {{ARGS}}

# Rename an entity key in every source at once (maps, CSVs, config, locale, Tiled). e.g: `just rename-entity Village BLUNDERHAVEN`
[windows]
rename-entity *ARGS:
    #!powershell
    .venv\Scripts\python.exe scripts\rename_entity.py {{ARGS}}

# Run all static analysis and code checks (Sourcery + mypy + locale + world)
check: sourcery mypy validate-locale validate-world

# Fix all PNGs that have sRGB/gAMA/cHRM/iCCP chunks (strips profile chunks via `mogrify`)
[unix]
fix-bad-png:
    @python3 scripts/find_bad_png.py | xargs -r mogrify -strip

# Fix libpng sRGB profile warnings in PNG files using Python
[windows]
fix-bad-png:
    #!powershell
    .venv\Scripts\python.exe scripts\fix_bad_png.py

# Find PNGs with sRGB/gAMA/cHRM/iCCP chunks (potential libpng header warnings)
[unix]
find-bad-png:
    @python3 scripts/find_bad_png.py

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

# Build the pygbag `web.zip` archive ready for `itch.io` deployment
[unix]
build-itchio:
    .venv/bin/pygbag --ume_block 0 --template scripts/pygbag/black.tmpl --icon project/assets/icon.png --no_opt --archive project

# Start the OpenCode watcher agent to automatically process tasks from board (run `Tasks/bin/moab` for more options)
[unix]
start-oc-agent:
    Tasks/bin/moab watch --agent opencode --model "opencode/big-pickle" --interval 5

# Measure how CodeGraph (or any tool adoption) changed CC's work profile, from session transcripts.
[unix]
codegraph-impact *ARGS:
    # Compares two eras split by --cutoff (default: CodeGraph install 2026-07-21). Pair with
    # --min-size 1.7 to control for the size confound - see doc/codegraph-wplyw-2026-08-05.md.
    .venv/bin/python scripts/codegraph_impact.py {{ARGS}}
