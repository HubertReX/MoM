#!/usr/bin/env python3
"""Agent-driven UI/smoke test runner.

Two backends share one scenarios schema:

- **Desktop** (default): subprocess `MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy ... project/main.py`;
  komendy zapisywane do ``agent_input.txt``; screenshoty przez ``pygame.image.save``.
- **Web** (``--web``): subprocess `python -m pygbag ... project` + Playwright Chromium;
  komendy wstrzykiwane do ``window.localStorage['MoM.agent_input']``;
  screenshoty przez ``page.screenshot()``; save assertions czytane z localStorage.

Usage:
    # desktop (default) - jak dotychczas
    .venv/bin/python3 tests/automate_display_test.py "Save and Load Basic"
    .venv/bin/python3 tests/automate_display_test.py            # wszystkie desktop-owe
    # lub przez Just:  just test-agent "Save and Load Basic"  |  just test-agent

    # web (wymaga Playwright + chromium: patrz requirements-dev)
    .venv/bin/python3 tests/automate_display_test.py --web "Save and Load Basic"
    .venv/bin/python3 tests/automate_display_test.py --web      # wszystkie web-owe
    # lub przez Just:  just test-web "Save and Load Basic"  |  just test-web

Opcje CLI (patrz też ``--help``):
    scenario            nazwa scenariusza; pomiń, by uruchomić wszystkie dla backendu
    --web               użyj backendu web (pygbag + Playwright) zamiast desktop
    --url URL           web: nadpisz URL pygbag (domyślnie http://127.0.0.1:8001/)
    --timeout S         web: ile sekund czekać na boot gry po pojawieniu się canvasu
                        (domyślnie INIT_WAIT_WEB=12s); podbij na wolnym CI/sprzęcie
    --pygbag-timeout S  web: ile sekund czekać na build + serve pygbag (domyślnie 90s)
    --web-restart-per-scenario
                        web: restartuj pygbag + przeglądarkę dla KAŻDEGO scenariusza
                        (zachowanie sprzed A08). Domyślnie serwer i przeglądarka żyją
                        przez cały przebieg, a scenariusz startuje przez reload strony
                        - build WASM jest w przebiegu identyczny, więc to czysty zysk
                        czasu (~25 -> ~10 min). Użyj tej flagi, gdy podejrzewasz, że
                        stan przecieka między scenariuszami.
    --smoke             uruchom tylko zestaw smoke (TEST_CONFIG["SMOKE_SCENARIOS"]) -
                        kilka scenariuszy z rozłącznych obszarów jako szybka bramka
                        (`just test-smoke`); wyklucza się z podaniem nazwy scenariusza

Scenarios selection:
    Scenariusze z polem ``platform`` w ``scenarios.json`` są filtrowane per backend:
    ``"desktop"``, ``"web"`` lub lista ``["desktop", "web"]``. Brak pola = dotyczy obu.

Assertions (per scenario, opcjonalne):
    file_exists          desktop: plik ``<save_dir>/save_N.mom`` istnieje (min_size opcjonalny);
                         web: tłumaczone na obecność klucza ``MoM.save_N`` w localStorage.
    localstorage_exists  web: klucz ``key`` (np. ``MoM.save_0``) obecny w localStorage.
    ui_state             porównuje zrzut stanu gry z komendy ``debug_ui_state`` (którą
                         scenariusz MUSI wysłać jako akcję wcześniej). Desktop czyta
                         ``agent_ui_state.json``, web - localStorage ``MoM.agent_ui_state``.
                         W ``expect`` trzy rodzaje kluczy:
                         ``open_panels_contains`` (lista nazw klas paneli, każda musi być
                         otwarta), ``<ścieżka>_min``/``<ścieżka>_max`` (porównanie liczbowe,
                         np. ``"player.hp_min": 1``) oraz dowolny inny klucz = równość
                         (``"map": "BLUNDERHAVEN"``, ``"dialog.npc": "BARMAN_ABSINTHRAYNER"``).
    no_layout_violations FAIL, gdy UI zgłosiło naruszenie layoutu (tekst poza panelem,
                         overflow bez scrolla - patrz ``project/ui/layout.py``). Czyta
                         ``layout_violations`` z tego samego zrzutu, więc scenariusz
                         też musi wcześniej wysłać ``debug_ui_state``.
    screenshot_review    ss-reviewer (model z vision) ocenia screenshot. Pola:
                         ``target`` (slug akcji; brak = ostatni screenshot),
                         ``expect`` (opis oczekiwania), ``expected_state`` (np. ``GAMEPLAY``),
                         oraz OPCJONALNE checklisty trafiające wprost do prompta:
                         ``expected_elements`` - lista elementów, które MUSZĄ być widoczne,
                         ``ui_quality_checks`` - lista kontroli jakości UI (np. brak overflow).
                         Bez tych pól zachowanie jest jak dotychczas.
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, List

# save fixtures live in the repo's central `scripts/` dir (they are a hand-usable
# CLI, not a test); this runner is executed as a path, so only `tests/` lands on
# sys.path automatically.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

# --- Configuration & Constants ---
TEST_CONFIG = {
    "INIT_WAIT": 5.0,
    "INIT_WAIT_WEB": 12.0,  # pygbag boot + WASM load są wolniejsze
    "PYGBAG_BOOT_TIMEOUT": 90.0,  # ile czekać na wystartowanie serwera pygbag (build + serve)
    "TRANSITION_WAIT": 0.2,
    "SCREENSHOT_BUFFER": 0.1,
    "GAME_CMD": "MOM_AGENT_CONTROL=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy .venv/bin/python3 project/main.py",
    "PYGBAG_CMD": [
        sys.executable, "-m", "pygbag",
        "--ume_block", "0",
        "--template", "scripts/pygbag/black.tmpl",
        "--icon", "project/assets/icon.png",
        "--no_opt",
        "--bind", "127.0.0.1",
        "--port", "8001",
        "project",
    ],
    "WEB_URL": "http://127.0.0.1:8001/",
    "INPUT_FILE": os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent_input.txt"),
    "STATUS_FILE": os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent_status.txt"),
    "SCENARIOS_FILE": os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios.json"),
    "UI_STATE_FILE": os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent_ui_state.json"),
    "WALK_TIMEOUT": 30.0,   # max seconds to wait for a walk_to_* to reach its target
    # `--smoke`: szybka bramka (~4-5 min desktop) zamiast pełnego przebiegu (~18 min).
    # Dobór: rozłączne obszary, wszystkie dostępne na desktop i web.
    "SMOKE_SCENARIOS": [
        "Save and Load Basic",          # menu zapisu/wczytania, format save
        "Hammer Dialog Flow",           # dialog + wybór opcji + skutek w świecie
        "Auto Save on Maze Entry",      # labirynt, autosave, przejście mapy
        "UI Flow - Menu Save then Load",  # pełny obieg paneli UI
        "Display Settings Flow",        # ustawienia, zmiana rozdzielczości/layout
        "TextInput Basic",              # wejście tekstowe (klawiatura, kursor)
    ],
}

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_SCREENSHOT_DIR = REPO_ROOT / "screenshots" / "agent"

# localStorage klucze zapisów w trybie web (muszą zgadzać się z `LocalStorageSaveBackend._STORAGE_PREFIX`)
WEB_SAVE_KEY_PREFIX = "MoM.save_"
WEB_INPUT_KEY = "MoM.agent_input"
WEB_AGENT_FLAG = "MoM.agent_control"
# jeden kanał na WSZYSTKIE zmienne testowe web (A07): JSON {"MOM_...": "..."} czytany
# przez settings._test_env przy imporcie settings (dlatego pisany PRZED reload())
WEB_ENV_KEY = "MoM.env"
# zrzut stanu gry z komendy `debug_ui_state` (musi zgadzać się z agent_ctrl.WEB_UI_STATE_KEY)
WEB_UI_STATE_KEY = "MoM.agent_ui_state"

# Nazewnictwo screenshotów: agent_{run_ts}_{scenario_slug}_{NN}_{action_slug}.png
#   - run_ts        : jeden znacznik czasu na cały przebieg jednego scenariusza (grupuje pliki)
#   - scenario_slug : krótki slug scenariusza z pola "slug" w scenarios.json
#   - NN            : licznik screenshotów w obrębie scenariusza (2 cyfry)
#   - action_slug   : slug etykiety akcji, która zleciła screenshot
# Desktop generuje tę nazwę w grze (project/agent_ctrl.py); web — w runnerze. Oba MUSZĄ
# produkować identyczny format, żeby runner mógł przewidzieć ścieżkę na potrzeby asercji.
SS_PREFIX_ENV = "MOM_AGENT_SS_PREFIX"  # desktop: prefix "{run_ts}_{scenario_slug}" przekazany do gry

# --- ss-reviewer (analiza screenshotów przez subagenta z vision) ---
# Kolejność prób: najpierw Gemini (stabilny, odpowiada w kilka sekund), potem mimo-v2.5
# jako fallback. Odwrotna kolejność (mimo jako primary) powodowała regularne timeouty
# rc=124 - runner czekał 60 s na martwy model przed każdym fallbackiem.
# KAŻDY model na tej liście MUSI mieć vision (`attachment: true`,
# `modalities.input: ["text","image"]`), bo screenshot idzie jako załącznik `-f`;
# `-f` z modelem bez vision kończy się BŁĘDEM, nie degradacją.
# Gdy żaden model nie zwróci werdyktu -> asercja twardo pada (decyzja usera: hard-fail).
SS_REVIEW_AGENT = "ss-reviewer"
SS_REVIEW_MODELS: list[str | None] = ["google/gemini-3.1-flash-lite", "opencode-go/mimo-v2.5"]
SS_REVIEW_TIMEOUT = 60.0
SS_REVIEW_SKIP_ENV = "MOM_SKIP_SS_REVIEW"  # ustaw =1, by pominąć (szybka iteracja)


def get_timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")


def slugify(text: str, max_len: int = 48) -> str:
    """Zamień etykietę na bezpieczny slug do nazwy pliku (snake_case, [a-z0-9_])."""
    text = (text or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:max_len] or "shot"


def parse_review_json(text: str) -> tuple[str | None, list[str]]:
    """Znajdź ostatni blok JSON z polem ``verdict``; zwróć ``(verdict, failed_checks)``.

    Preferowana ścieżka parsowania werdyktu: ss-reviewer kończy odpowiedź fenced blokiem
    ``{"verdict": ..., "state": ..., "failed_checks": [...]}``. Regex łapie goły obiekt,
    więc otoczenie ```json ...``` nie przeszkadza, a blok nie musi być ostatnią linią.
    Gdy model nie umie w JSON (np. fallback), woła się :func:`parse_review_verdict`.
    """
    candidates = re.findall(r"\{[^{}]*\"verdict\"[^{}]*\}", text, re.DOTALL)
    for raw in reversed(candidates):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        verdict = str(data.get("verdict", "")).upper()
        if verdict in ("PASS", "FAIL"):
            return verdict, [str(c) for c in data.get("failed_checks", [])]
    return None, []


def parse_review_verdict(text: str) -> str | None:
    """Wyciągnij PASS/FAIL z odpowiedzi ss-reviewera (kilka wariantów formatu).

    Fallback dla modeli, które nie wyprodukowały bloku JSON (patrz :func:`parse_review_json`).
    """
    for pattern in (
        r"RESULT:\s*(PASS|FAIL)",
        r"\*\*Result\*\*:\s*(PASS|FAIL)",
        r"\bResult\b[:\s]+(PASS|FAIL)",
    ):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return None


def _timeout_cmd(cmd: list[str], timeout: int = 60) -> list[str]:
    """Wrap cmd with gtimeout (GNU coreutils, macOS) or timeout (Linux), if available."""
    exe = shutil.which("gtimeout") or shutil.which("timeout")
    if exe:
        return [exe, str(timeout), *cmd]
    return cmd


def build_review_prompt(
    expect: str,
    expected_state: str | None,
    expected_elements: list[str] | None = None,
    ui_quality_checks: list[str] | None = None,
) -> str:
    """Złóż prompt dla ss-reviewera z checklist scenariusza.

    ``expected_elements`` i ``ui_quality_checks`` są opcjonalne - scenariusze bez nich
    dostają prompt jak dotąd. Bez jawnego pytania o jakość UI model jej NIE ocenia
    (zweryfikowane 2026-07-25: ten sam model z pytaniem o overflow wykrywa wadę 2/2,
    bez pytania - przepuszcza).
    """
    return (
        "You are validating an automated test screenshot (attached) from the game "
        '"Misadventures of Malachi" (MoM). '
        f"Expected game state: {expected_state or 'described below'}. "
        f"Expectation to verify: {expect} "
        + (f"Expected visible elements: {'; '.join(expected_elements)}. " if expected_elements else "")
        + (f"UI quality checks (each must hold): {'; '.join(ui_quality_checks)}. " if ui_quality_checks else "")
        + "Analyze the attached screenshot and produce your structured report. "
        "Then output, as the FINAL fenced code block, a JSON object exactly of the form: "
        '{"verdict": "PASS"|"FAIL", "state": "<detected state>", "failed_checks": ["..."]}'
    )


def review_screenshot(
    path: Path,
    expect: str,
    expected_state: str | None,
    expected_elements: list[str] | None = None,
    ui_quality_checks: list[str] | None = None,
) -> tuple[str | None, str]:
    """Poproś subagenta ss-reviewer o werdykt PASS/FAIL dla screenshotu.

    Zwraca ``(verdict, detail)`` gdzie verdict to 'PASS'/'FAIL'/None (żaden model nie dał werdyktu).
    Próbuje kolejno modeli z ``SS_REVIEW_MODELS``; pierwszy zwracający czytelny werdykt wygrywa.

    Screenshot jest przekazywany jako ZAŁĄCZNIK przez ``-f`` (ścieżka inline w prompcie
    już nie działa - zmiana zachowania OpenCode zweryfikowana 2026-07-25). Kolejność
    argumentów ma znaczenie: message PIERWSZY, ``-f`` PO nim, bo ``-f`` jest greedy
    (``[array]``) i połknąłby trailing positional message jako nazwę pliku.
    Konsekwencja: każdy model w ``SS_REVIEW_MODELS`` musi mieć vision - patrz komentarz
    przy tej stałej.

    Werdykt parsowany jest najpierw z bloku JSON (:func:`parse_review_json`), a dopiero
    gdy go brak - starym regexem po markdownie (:func:`parse_review_verdict`).
    """
    prompt = build_review_prompt(expect, expected_state, expected_elements, ui_quality_checks)
    # MOM_SS_REVIEW_MODEL wymusza jeden konkretny model (pomija dead primary).
    forced = os.environ.get("MOM_SS_REVIEW_MODEL")
    models: list[str | None] = [forced] if forced else SS_REVIEW_MODELS
    last_detail = "no model attempted"
    for model in models:
        label = model or "agent-default"
        # message PIERWSZY, -f PO nim (patrz docstring) - inaczej `-f` połyka prompt.
        cmd = ["opencode", "run", "--pure", prompt, "--agent", SS_REVIEW_AGENT, "-f", str(path)]
        if model:
            cmd += ["--model", model]
        cmd = _timeout_cmd(cmd, int(SS_REVIEW_TIMEOUT))
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=SS_REVIEW_TIMEOUT + 10.0, cwd=str(REPO_ROOT),
            )
        except subprocess.TimeoutExpired:
            last_detail = f"{label}: timed out after {SS_REVIEW_TIMEOUT:.0f}s"
            print(f"[ss-review] {last_detail}")
            continue
        except FileNotFoundError:
            return None, "opencode CLI not found on PATH"
        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        verdict, failed_checks = parse_review_json(out)
        if verdict:
            print(f"[ss-review] {label} -> {verdict}"
                  + (f" failed_checks={failed_checks}" if failed_checks else ""))
            detail = f"[{label}]"
            if failed_checks:
                detail += " failed_checks: " + "; ".join(failed_checks)
            return verdict, detail
        verdict = parse_review_verdict(out)
        if verdict:
            # dołącz krótki kontekst z raportu (ostatnie niepuste linie) do detalu
            tail = " ".join(
                ln.strip() for ln in out.strip().splitlines()[-4:] if ln.strip()
            )
            print(f"[ss-review] {label} -> {verdict} (no JSON block, regex fallback)")
            return verdict, f"[{label}] {tail}"
        last_detail = f"{label}: no verdict (rc={proc.returncode})"
        print(f"[ss-review] {last_detail}")
    return None, last_detail


# --- tryb deterministyczny świata (A04) ---
LIVE_WORLD_ENV = "MOM_TEST_LIVE_WORLD"      # =1 przywraca w pełni losowy świat (opt-out)
DETERMINISTIC_ENV = "MOM_TEST_DETERMINISTIC"
START_HOUR_ENV = "MOM_TEST_START_HOUR"


def apply_determinism_env(env: dict[str, str], start_hour: int | None) -> None:
    """Ustaw w ``env`` procesu gry tryb deterministyczny i (opcjonalnie) godzinę startu.

    Domyślnie testy chodzą deterministycznie: ten sam seed świata i ta sama sekwencja
    decyzji pogodowych, więc screenshoty są porównywalne między uruchomieniami. Cząstki
    NIE są wyłączane - testowalibyśmy inną grę niż realna. ``MOM_TEST_LIVE_WORLD=1``
    wraca do w pełni losowego świata.

    ``start_hour`` pochodzi z pola scenariusza i działa niezależnie od trybu: gra
    normalnie zaczyna o 9:00 i scenariusze mają widzieć rutyny NPC takie jak gracz;
    wymuszamy porę tylko tam, gdzie test tego wprost potrzebuje (noc, zamknięty sklep).
    Env jest per scenariusz, bo runner odpala osobną instancję gry dla każdego.
    """
    if os.environ.get(LIVE_WORLD_ENV):
        env.pop(DETERMINISTIC_ENV, None)
        print(f"[world] live (random) - {LIVE_WORLD_ENV} is set")
    else:
        env[DETERMINISTIC_ENV] = "1"
        print("[world] deterministic (seeded world + weather)")
    if start_hour is not None:
        env[START_HOUR_ENV] = str(start_hour)
        print(f"[world] start hour forced to {start_hour}:00")
    else:
        env.pop(START_HOUR_ENV, None)


REAL_SAVES_ENV = "MOM_TEST_USE_REAL_SAVES"   # opt out of the sandbox (see isolate_game_data)
SANDBOX_DIR = Path(__file__).resolve().parent.parent / ".test-data"


# ============================================================================
# Singleton guard - jeden przebieg naraz
# ============================================================================
# Runner jest singletonem: jeden serwer pygbag na porcie 8001, wspólny
# `agent_input.txt`/`agent_status.txt` i wspólny `screenshots/agent/`. Dwa
# równoległe przebiegi NIE wywalają się głośno - mieszają sobie wejście
# i zrzuty, a wyniki są nieważne (zdarzyło się: trzy równoległe `just test-web`).
# Blokada + kontrola portu zatrzymują to na starcie, zanim cokolwiek zbuduje.
LOCK_FILE = Path(tempfile.gettempdir()) / "mom-automate-display-test.pid"


def _is_other_runner(pid: int) -> bool:
    """Czy *pid* żyje i jest innym przebiegiem tego runnera (nie recyklingiem PID)."""
    try:
        out = subprocess.run(
            ["ps", "-o", "command=", "-p", str(pid)],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception:
        return False
    return "automate_display_test" in out


def _pygbag_port() -> int | None:
    """Port lokalnego pygbaga z ``WEB_URL`` (jedno źródło prawdy z ``PYGBAG_CMD``)."""
    parsed = urllib.parse.urlparse(str(TEST_CONFIG["WEB_URL"]))
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        return None
    return parsed.port or (443 if parsed.scheme == "https" else 80)


def _port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def release_singleton_lock() -> None:
    try:
        if LOCK_FILE.exists() and LOCK_FILE.read_text().strip() == str(os.getpid()):
            LOCK_FILE.unlink()
    except Exception:
        pass


def acquire_singleton_lock(port: int | None) -> None:
    """Przerwij od razu, gdy inny przebieg (albo jego pygbag) jeszcze żyje."""
    if LOCK_FILE.exists():
        try:
            other = int(LOCK_FILE.read_text().strip())
        except (ValueError, OSError):
            other = -1
        if other > 0 and other != os.getpid() and _is_other_runner(other):
            raise SystemExit(
                f"Error: inny przebieg automate_display_test.py już działa (PID {other}).\n"
                f"  Runner jest singletonem - zaczekaj albo ubij: kill {other}\n"
                f"  (blokada: {LOCK_FILE})"
            )
        print(f"[lock] nieaktualna blokada po PID {other} - przejmuję")
    if port is not None and _port_in_use(port):
        raise SystemExit(
            f"Error: port {port} jest zajęty - leci inny przebieg albo został pygbag "
            "po przerwanym.\n"
            "  Sprzątanie: pkill -f 'tests/automate_display_test.py'; pkill -f 'm pygbag'; "
            "pkill -f chromium_headless_shell"
        )
    LOCK_FILE.write_text(str(os.getpid()))
    atexit.register(release_singleton_lock)


def _descendants(pid: int) -> list[int]:
    """PID-y wszystkich potomków *pid* (wszerz). Bez grup procesów - `killpg`
    na grupie dziecka potrafi trafić w naszą własną grupę (powłokę `just`)."""
    found: list[int] = []
    frontier = [pid]
    while frontier:
        current = frontier.pop()
        try:
            out = subprocess.run(
                ["pgrep", "-P", str(current)],
                capture_output=True, text=True, timeout=5,
            ).stdout
        except Exception:
            continue
        kids = [int(x) for x in out.split() if x.isdigit()]
        found.extend(kids)
        frontier.extend(kids)
    return found


def kill_descendants() -> None:
    """Ubij pygbaga, driver Playwrighta i chromium wprost, po drzewie procesów."""
    kids = _descendants(os.getpid())
    if not kids:
        return
    for pid in kids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    time.sleep(1.5)
    for pid in kids:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def install_cleanup_handlers(runner: "RunnerBase") -> None:
    """Zwiń pygbag i przeglądarkę także przy `kill`/`pkill`, nie tylko przy Ctrl-C.

    Domyślna obsługa SIGTERM ubija proces natychmiast - `atexit` ani `finally`
    się nie wykonują i po runnerze zostaje żywy pygbag na 8001 plus osierocone
    `chrome-headless-shell`.

    Handler NIE podnosi wyjątku i NIE woła `runner.cleanup()`: przez większość
    przebiegu główny wątek siedzi w synchronicznym API Playwrighta, które kręci
    się w greenlecie i wyjątek z handlera po prostu ginie (sprawdzone: proces
    stawał się odporny na `pkill` i trzeba go było ubijać `-9`). Zamiast tego
    handler robi to, co w sygnale jest bezpieczne - ubija potomków po PID-ach
    i wychodzi przez ``os._exit``. Normalne wyjście dalej idzie przez
    ``atexit``/``finally``, czyli czysty teardown Playwrighta.
    """
    atexit.register(runner.cleanup)

    def _handler(signum: int, _frame: Any) -> None:
        print(f"\n[{get_timestamp()}] Sygnał {signum} - sprzątam (pygbag, przeglądarka)...",
              flush=True)
        try:
            kill_descendants()
            release_singleton_lock()
        finally:
            os._exit(128 + signum)

    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _handler)


def isolate_game_data() -> None:
    """Point the game's data dir at a throw-away sandbox for the whole run.

    Scenarios call ``clear_all_saves()`` before each run and freely overwrite
    slots, and "Display Settings Flow" rewrites ``settings.json``. Both resolve
    through ``XDG_DATA_HOME``, so without this the suite eats the *developer's*
    real saves and display settings - which is exactly what it used to do.

    Set here rather than only on the subprocess env, because this process reads
    the same paths for its ``file_exists`` / ``save_absent`` assertions, and the
    game inherits ``os.environ`` when it is spawned. Must run before anything
    calls :func:`get_save_dir`.

    ``MOM_TEST_USE_REAL_SAVES=1`` opts out, for the rare case of inspecting a
    scenario against a real save - it will destroy those saves.
    """
    if os.environ.get(REAL_SAVES_ENV):
        print(f"[warn] {REAL_SAVES_ENV} is set - running against the REAL save dir "
              f"({get_save_dir()}); scenarios will delete those saves")
        return
    (SANDBOX_DIR / "mom" / "saves").mkdir(parents=True, exist_ok=True)
    os.environ["XDG_DATA_HOME"] = str(SANDBOX_DIR)
    print(f"Game data sandbox: {SANDBOX_DIR} (real saves untouched)")


def get_save_dir() -> Path:
    """Return the same save directory used by FileSaveBackend."""
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / "mom" / "saves"
    system = platform.system()
    home = Path.home()
    if system == "Darwin":
        return home / "Library" / "Application Support" / "mom" / "saves"
    elif system == "Linux":
        return home / ".local" / "share" / "mom" / "saves"
    return home / "AppData" / "Local" / "mom" / "saves"


def resolve_assertion_path(path: str) -> Path:
    """Resolve assertion paths, expanding <save_dir> and user home."""
    path = path.replace("<save_dir>", str(get_save_dir()))
    return Path(path).expanduser()


def delete_save_slot(slot_idx: int) -> None:
    path = get_save_dir() / f"save_{slot_idx}.mom"
    try:
        if path.exists():
            path.unlink()
    except OSError as e:
        print(f"[warn] could not delete {path}: {e}")


def clear_all_saves() -> None:
    save_dir = get_save_dir()
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[warn] could not create save dir {save_dir}: {e}")
        return
    for path in save_dir.glob("save_*.mom"):
        try:
            path.unlink()
            print(f"[cleanup] deleted {path}")
        except OSError as e:
            print(f"[warn] could not delete {path}: {e}")


# ============================================================================
# Scenarios
# ============================================================================
class TestAction:
    def __init__(self, slug: str, commands: List[str], wait: float = TEST_CONFIG["TRANSITION_WAIT"]):
        # slug: krótka nazwa snake_case akcji - używana w logach, w nazwie pliku
        # screenshotu (action_slug) oraz jako `target` asercji screenshot_review.
        self.slug = slugify(slug)
        self.commands = commands
        self.wait = wait

    def split_screenshot(self) -> tuple[List[str], bool]:
        """Oddziel screenshot od komend sterujących. Zwraca (control_commands, wants_screenshot)."""
        ctrl = [c for c in self.commands if c not in ("screenshot", "shot")]
        wants_shot = len(ctrl) != len(self.commands)
        return ctrl, wants_shot


class TestScenario:
    def __init__(
        self,
        name: str,
        actions: List[TestAction],
        assertions: List[dict[str, Any]] | None = None,
        cleanup_saves: List[int] | None = None,
        platform_spec: str | List[str] | None = None,
        setup_saves: List[dict[str, Any]] | None = None,
        slug: str | None = None,
        start_hour: int | None = None,
    ):
        self.name = name
        # opcjonalne wymuszenie pory dnia dla tego scenariusza (patrz apply_determinism_env)
        self.start_hour = start_hour
        self.actions = actions
        self.assertions = assertions or []
        self.cleanup_saves = cleanup_saves or []
        self.platform_spec = platform_spec
        self.setup_saves = setup_saves or []
        # slug do nazw plików screenshotów; fallback = slug z nazwy scenariusza
        self.slug = slug or slugify(name)

    def supports(self, backend: str) -> bool:
        if not self.platform_spec:
            return True
        if isinstance(self.platform_spec, list):
            return backend in self.platform_spec
        return self.platform_spec == backend

    def run(self, runner: "RunnerBase") -> None:
        print(f"\n>>> Starting Scenario: {self.name}")
        for action in self.actions:
            runner.execute_action(action)
        print(f">>> Scenario {self.name} Complete.")
        self._run_assertions(runner)

    def _run_assertions(self, runner: "RunnerBase") -> None:
        if not self.assertions:
            return
        failures: List[str] = []
        for assertion in self.assertions:
            failures.extend(runner.check_assertion(assertion))
        if failures:
            raise AssertionError("; ".join(failures))
        print(f">>> Assertions passed for {self.name}")


# ============================================================================
# Runner base + Desktop runner
# ============================================================================
class RunnerFatal(RuntimeError):
    """Awaria infrastruktury runnera - przerywa cały przebieg, nie pojedynczy scenariusz."""


class RunnerBase:
    backend = "desktop"

    def __init__(self) -> None:
        self.counter = 0
        self.run_ts = ""            # jeden znacznik czasu na przebieg jednego scenariusza
        self.scenario_slug = ""
        self.start_hour: int | None = None  # z pola `start_hour` bieżącego scenariusza
        self.screenshots: List[dict[str, Any]] = []  # {slug, label, path} w kolejności zrobienia

    # Cykl życia (A08): sesja obejmuje CAŁY przebieg, `start_game`/`stop_game`
    # jeden scenariusz. Desktop startuje grę per scenariusz (czyta env przy
    # imporcie `settings`), web trzyma jeden serwer pygbag + przeglądarkę na
    # całą sesję i per scenariusz tylko przeładowuje stronę.
    def start_session(self) -> None: ...
    def end_session(self) -> None: ...
    def start_game(self) -> None: ...
    def stop_game(self) -> None: ...
    def execute_action(self, action: TestAction) -> None: ...
    def check_assertion(self, assertion: dict[str, Any]) -> List[str]: ...
    def cleanup_saves_before(self, scenario: TestScenario) -> None: ...
    def setup_saves(self, saves: List[dict[str, Any]]) -> None: ...

    def cleanup(self) -> None:
        """Zamknij wszystko (scenariusz + sesja) - awaryjne wyjście."""
        self.stop_game()
        self.end_session()

    # ---------------------------------------------------------------- scenariusz
    def begin_scenario(self, scenario: TestScenario) -> None:
        """Zamroź jeden znacznik czasu + slug scenariusza; wyzeruj licznik i historię."""
        self.counter = 0
        self.run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.scenario_slug = scenario.slug
        self.start_hour = scenario.start_hour
        self.screenshots = []
        # zrzut stanu z poprzedniego scenariusza nie może wyciec do tego
        self.clear_ui_state()

    def screenshot_prefix(self) -> str:
        return f"{self.run_ts}_{self.scenario_slug}"

    def record_screenshot(self, action_slug: str) -> Path:
        """Policz przewidywaną ścieżkę screenshotu i zapamiętaj ją (dla asercji).

        Nazwa MUSI być identyczna z tą, którą generuje gra na desktopie
        (project/agent_ctrl.py) — patrz komentarz przy SS_PREFIX_ENV.
        """
        self.counter += 1
        slug = slugify(action_slug)
        name = f"agent_{self.run_ts}_{self.scenario_slug}_{self.counter:02d}_{slug}.png"
        path = AGENT_SCREENSHOT_DIR / name
        AGENT_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self.screenshots.append({"slug": slug, "path": path})
        return path

    def take_screenshot(self, action_slug: str) -> None:
        """Web: policz ścieżkę i zapisz zrzut (desktop zapisuje gra, nie runner)."""
        path = self.record_screenshot(action_slug)
        self._save_screenshot(path)
        print(f"[{get_timestamp()}] screenshot -> {path}")

    def _save_screenshot(self, path: Path) -> None:
        raise NotImplementedError

    # ---------------------------------------------------------------- asercje wspólne
    def find_screenshot(self, target: str | None) -> dict[str, Any] | None:
        """Znajdź zapamiętany screenshot po slugu akcji; brak target => ostatni."""
        if not self.screenshots:
            return None
        if not target:
            return self.screenshots[-1]
        wanted = slugify(target)
        for shot in reversed(self.screenshots):
            if shot["slug"] == wanted:
                return shot
        return None

    def check_common_assertion(self, assertion: dict[str, Any]) -> List[str] | None:
        """Asercje wspólne dla obu backendów. Zwraca None gdy typ nieobsługiwany tutaj."""
        a_type = assertion.get("type")
        if a_type == "screenshot_review":
            return self._assert_screenshot_review(assertion)
        if a_type == "screenshot_min_size":
            return self._assert_screenshot_min_size(assertion)
        if a_type == "process_alive":
            return self._assert_process_alive(assertion)
        if a_type == "ui_state":
            return self._assert_ui_state(assertion)
        if a_type == "no_layout_violations":
            return self._assert_no_layout_violations(assertion)
        return None

    def _assert_no_layout_violations(self, assertion: dict[str, Any]) -> List[str]:
        """Twardy błąd, gdy UI zgłosiło jakiekolwiek naruszenie layoutu.

        Źródłem jest ``layout_violations`` w zrzucie ``debug_ui_state`` - scenariusz
        musi więc wysłać tę komendę PO otwarciu paneli, które chce sprawdzić
        (naruszenie jest raportowane dopiero, gdy widżet faktycznie się rysuje).
        """
        state = self.read_ui_state()
        if state is None:
            return ["no_layout_violations: no state dump - the scenario must send the "
                    "`debug_ui_state` command as an action before this assertion"]
        found = state.get("layout_violations") or []
        if found:
            return [f"layout violations ({len(found)}): " + " | ".join(str(v) for v in found)]
        return []

    # ---------------------------------------------------------------- ui_state
    def read_ui_state(self) -> dict[str, Any] | None:
        """Zwróć ostatni zrzut `debug_ui_state` albo None, gdy go nie ma."""
        raise NotImplementedError

    def clear_ui_state(self) -> None:
        """Skasuj zrzut z poprzedniego przebiegu (żeby nie asertować cudzego stanu)."""

    @staticmethod
    def _dotted(state: dict[str, Any], path: str) -> Any:
        """Wyłuskaj wartość po ścieżce z kropkami (``player.hp``); brak -> None."""
        node: Any = state
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node

    def _assert_ui_state(self, assertion: dict[str, Any]) -> List[str]:
        """Porównaj zrzut stanu gry z oczekiwaniami scenariusza.

        Obsługiwane są dokładnie trzy rodzaje kluczy w ``expect``:

        - ``open_panels_contains`` - każdy element listy musi być w ``open_panels``
        - ``<ścieżka>_min`` / ``<ścieżka>_max`` - porównanie liczbowe pola po ścieżce
          z kropkami (``player.hp_min: 1`` => ``player.hp >= 1``)
        - dowolny inny klucz - równość z wartością spod tej ścieżki (``map``,
          ``top_state``, ``is_maze``, ``dialog.npc``, ...)
        """
        state = self.read_ui_state()
        if state is None:
            return ["ui_state: no state dump - the scenario must send the "
                    "`debug_ui_state` command as an action before this assertion"]
        expect = assertion.get("expect") or {}
        if not isinstance(expect, dict):
            return [f"ui_state: 'expect' must be an object, got {type(expect).__name__}"]

        failures: List[str] = []
        for key, wanted in expect.items():
            if key == "open_panels_contains":
                open_panels = state.get("open_panels") or []
                missing = [p for p in wanted if p not in open_panels]
                if missing:
                    failures.append(
                        f"ui_state.open_panels: missing {missing} (open: {open_panels})")
                continue
            if key.endswith("_min") or key.endswith("_max"):
                path, _, bound = key.rpartition("_")
                actual = self._dotted(state, path)
                if not isinstance(actual, (int, float)) or isinstance(actual, bool):
                    failures.append(f"ui_state.{path}: not a number ({actual!r})")
                elif bound == "min" and actual < wanted:
                    failures.append(f"ui_state.{path}: {actual} < min {wanted}")
                elif bound == "max" and actual > wanted:
                    failures.append(f"ui_state.{path}: {actual} > max {wanted}")
                continue
            actual = self._dotted(state, key)
            if actual != wanted:
                failures.append(f"ui_state.{key}: expected {wanted!r}, got {actual!r}")
        return failures

    def _assert_screenshot_review(self, assertion: dict[str, Any]) -> List[str]:
        if os.environ.get(SS_REVIEW_SKIP_ENV):
            print(f"[ss-review] skipped ({SS_REVIEW_SKIP_ENV} set)")
            return []
        target = assertion.get("target")
        shot = self.find_screenshot(target)
        if shot is None:
            avail = [s["slug"] for s in self.screenshots]
            return [f"screenshot_review: no screenshot for target={target!r} (have: {avail})"]
        path = Path(shot["path"])
        if not path.exists():
            return [f"screenshot_review: screenshot file missing: {path}"]
        expect = assertion.get("expect", "")
        expected_state = assertion.get("expected_state")
        # opcjonalne checklisty per-scenariusz (brak = prompt jak dotąd)
        expected_elements = assertion.get("expected_elements")
        ui_quality_checks = assertion.get("ui_quality_checks")
        verdict, detail = review_screenshot(
            path, expect, expected_state,
            expected_elements=expected_elements,
            ui_quality_checks=ui_quality_checks,
        )
        if verdict == "PASS":
            return []
        if verdict == "FAIL":
            return [f"screenshot_review[{shot['slug']}] FAIL: {detail}"]
        # hard-fail (decyzja usera): żaden model nie dał werdyktu
        return [f"screenshot_review[{shot['slug']}] no verdict from any model: {detail}"]

    def _assert_screenshot_min_size(self, assertion: dict[str, Any]) -> List[str]:
        target = assertion.get("target")
        shot = self.find_screenshot(target)
        if shot is None:
            return [f"screenshot_min_size: no screenshot for target={target!r}"]
        path = Path(shot["path"])
        if not path.exists():
            return [f"screenshot_min_size: file missing: {path}"]
        min_size = int(assertion.get("min_size", 1000))
        size = path.stat().st_size
        if size < min_size:
            return [f"screenshot_min_size[{shot['slug']}]: {size} bytes < {min_size} (blank frame?)"]
        return []

    def _assert_process_alive(self, assertion: dict[str, Any]) -> List[str]:
        """Domyślnie no-op; DesktopRunner nadpisuje realną kontrolą procesu."""
        return []


class DesktopRunner(RunnerBase):
    backend = "desktop"

    def __init__(self) -> None:
        super().__init__()
        self.game_proc: subprocess.Popen | None = None

    def _clear_input_file(self) -> None:
        try:
            with open(TEST_CONFIG["INPUT_FILE"], "w") as f:
                f.write("")
        except FileNotFoundError:
            pass

    def start_game(self) -> None:
        print(f"[{get_timestamp()}] Starting game (desktop)...")
        start_time = time.perf_counter()
        self._clear_input_file()
        # Prefix nazw screenshotów przekazany do gry — patrz SS_PREFIX_ENV.
        env = dict(os.environ)
        env[SS_PREFIX_ENV] = self.screenshot_prefix()
        apply_determinism_env(env, self.start_hour)
        self.game_proc = subprocess.Popen(
            TEST_CONFIG["GAME_CMD"], shell=True, preexec_fn=os.setsid, env=env
        )
        time.sleep(TEST_CONFIG["INIT_WAIT"])
        print(f"[{get_timestamp()}] Game Init Delta: {time.perf_counter() - start_time:.4f}s")

    def execute_action(self, action: TestAction) -> None:
        print(f"[{get_timestamp()}] {action.slug}")
        start = time.perf_counter()
        ctrl, wants_shot = action.split_screenshot()
        tokens = list(ctrl)
        if wants_shot:
            # Osadź slug akcji w komendzie: gra użyje go w nazwie pliku.
            tokens.append(f"screenshot:{action.slug}")
        walk_cmd = next((t for t in tokens if t.startswith("walk_to")), None)
        if walk_cmd is not None:
            self._reset_walk_status()
        cmd = f'echo "{" ".join(tokens)}" > {TEST_CONFIG["INPUT_FILE"]}'
        print(f"[RUNNER SEND] {cmd}")
        subprocess.run(cmd, shell=True)
        if walk_cmd is not None:
            # Deterministic: block until the game reports the walk finished (or failed),
            # instead of guessing a fixed sleep. Poll the status file the game writes.
            outcome = self._wait_for_walk()
            print(f"[{get_timestamp()}] walk '{walk_cmd}' -> {outcome}")
        if wants_shot:
            # Przewidź ścieżkę, którą zapisze gra (ten sam format nazwy), na potrzeby asercji.
            self.record_screenshot(action.slug)
        end = time.perf_counter()
        print(f"[{get_timestamp()}] Done. Delta: {end - start:.4f}s")
        if action.wait > 0:
            time.sleep(action.wait)

    def _reset_walk_status(self) -> None:
        try:
            with open(TEST_CONFIG["STATUS_FILE"], "w") as f:
                f.write("walking")
        except OSError:
            pass

    def _wait_for_walk(self) -> str:
        """Poll the game's status file until the walk is no longer in progress.

        Returns the terminal status: ``arrived`` / ``no_path`` / ``not_found`` /
        ``timeout``. Deterministic replacement for a fixed sleep after walk_to_*.
        """
        deadline = time.perf_counter() + TEST_CONFIG["WALK_TIMEOUT"]
        while time.perf_counter() < deadline:
            try:
                with open(TEST_CONFIG["STATUS_FILE"]) as f:
                    status = f.read().strip()
            except OSError:
                status = ""
            if status and status != "walking":
                return status
            time.sleep(0.1)
        return "timeout"

    def check_assertion(self, assertion: dict[str, Any]) -> List[str]:
        common = self.check_common_assertion(assertion)
        if common is not None:
            return common
        a_type = assertion.get("type")
        if a_type == "file_exists":
            path = resolve_assertion_path(assertion["path"])
            if not path.exists():
                return [f"{path} does not exist"]
            min_size = assertion.get("min_size")
            if min_size is not None and path.stat().st_size < min_size:
                return [f"{path} size {path.stat().st_size} < {min_size}"]
            return []
        if a_type == "save_absent":
            path = resolve_assertion_path(assertion["path"])
            if path.exists():
                return [f"{path} exists but should be absent"]
            return []
        return [f"unknown assertion type: {a_type}"]

    def _assert_process_alive(self, assertion: dict[str, Any]) -> List[str]:
        if self.game_proc is None or self.game_proc.poll() is not None:
            return ["process_alive: game process exited unexpectedly (crash or unwanted quit)"]
        return []

    def read_ui_state(self) -> dict[str, Any] | None:
        path = Path(TEST_CONFIG["UI_STATE_FILE"])
        try:
            with open(path, encoding="utf-8") as f:
                return dict(json.load(f))
        except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError, ValueError):
            return None

    def clear_ui_state(self) -> None:
        try:
            Path(TEST_CONFIG["UI_STATE_FILE"]).unlink()
        except (FileNotFoundError, OSError):
            pass

    def cleanup_saves_before(self, scenario: TestScenario) -> None:
        clear_all_saves()
        for slot_idx in scenario.cleanup_saves:
            delete_save_slot(slot_idx)

    def setup_saves(self, saves: List[dict[str, Any]]) -> None:
        from save_fixtures import (
            corrupt_save, corrupt_save_version, create_minimal_save, old_save_version,
        )
        for spec in saves:
            slot = int(spec["slot"])
            kind = spec.get("type", "minimal")
            if kind == "corrupt":
                corrupt_save(slot)
            elif kind == "corrupt_version":
                corrupt_save_version(slot)
            elif kind == "old_version":
                old_save_version(slot)
            else:
                create_minimal_save(slot)

    def stop_game(self) -> None:
        if self.game_proc:
            print(f"[{get_timestamp()}] Cleaning up...")
            try:
                os.killpg(os.getpgid(self.game_proc.pid), 15)
                try:
                    self.game_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(self.game_proc.pid), 9)
                    self.game_proc.wait(timeout=5)
            except Exception:
                pass
            print(f"[{get_timestamp()}] Game stopped.")
            self.game_proc = None

    def _save_screenshot(self, path: Path) -> None:
        # screenshot zapisuje gra przez agent_ctrl.capture(); ten runner nic nie robi
        pass


# ============================================================================
# Web runner (Playwright + pygbag)
# ============================================================================
class WebRunner(RunnerBase):
    backend = "web"

    def __init__(
        self,
        url: str | None = None,
        init_wait: float | None = None,
        pygbag_timeout: float | None = None,
        restart_per_scenario: bool = False,
    ) -> None:
        super().__init__()
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Playwright nie zainstalowany. Uruchom:\n"
                "  rtk uv pip install playwright && rtk .venv/bin/playwright install chromium"
            ) from e
        self._sync_playwright = sync_playwright
        self.pygbag_proc: subprocess.Popen | None = None
        self.url = url or TEST_CONFIG["WEB_URL"]
        # boot wait po pojawieniu się canvasu (asset load + MainMenuScreen); konfigurowalne przez --timeout
        self.init_wait = init_wait if init_wait is not None else TEST_CONFIG["INIT_WAIT_WEB"]
        self.pygbag_timeout = pygbag_timeout if pygbag_timeout is not None else TEST_CONFIG["PYGBAG_BOOT_TIMEOUT"]
        self.pw = None
        self.browser = None
        self.page = None
        # saves do wstrzyknięcia po pierwszym goto(), przed reloadem ze stroną z grą
        self._pending_setup_saves: List[dict[str, Any]] = []
        # A08: domyślnie jeden serwer pygbag + jedna przeglądarka na CAŁY przebieg
        # (build WASM jest w przebiegu identyczny). `--web-restart-per-scenario`
        # przywraca stare zachowanie na wypadek podejrzenia, że stan przecieka
        # między scenariuszami.
        self.restart_per_scenario = restart_per_scenario
        self._page_rebuilds = 0

    def _wait_for_pygbag_url(self, proc: subprocess.Popen, timeout: float | None = None) -> str:
        if timeout is None:
            timeout = self.pygbag_timeout
        """Sprawdź gotowość pygbag: (a) szukaj URL w stdout, (b) HTTP poll na self.url."""
        url_re = re.compile(r"http://[\w\.-]+:\d+/?")
        deadline = time.perf_counter() + timeout
        assert proc.stdout is not None
        poll_interval = 0.5
        while time.perf_counter() < deadline:
            line = proc.stdout.readline()
            if line:
                text = line.rstrip() if isinstance(line, str) else line.decode("utf-8", errors="replace").rstrip()
                if text:
                    print(f"[pygbag] {text}")
                m = url_re.search(text)
                if m:
                    return m.group(0)
            if proc.poll() is not None:
                raise RuntimeError("pygbag exited unexpectedly")
            # równolegle HTTP poll na znanym URL
            if self._http_up(self.url):
                return self.url
            time.sleep(poll_interval)
        raise RuntimeError(f"pygbag nie wystartował w {timeout}s (URL={self.url})")

    @staticmethod
    def _http_up(url: str) -> bool:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    # ------------------------------------------------------------------ sesja
    def start_session(self) -> None:
        """Raz na przebieg: serwer pygbag + Chromium + pierwsze wejście na stronę."""
        if self.restart_per_scenario:
            return  # stary tryb: cała infrastruktura wstaje w start_game()
        self._start_pygbag()
        self._start_browser()
        self._open_page()

    def end_session(self) -> None:
        self._teardown()

    def _start_pygbag(self) -> None:
        print(f"[{get_timestamp()}] Starting pygbag (web)...")
        env = dict(os.environ)
        self.pygbag_proc = subprocess.Popen(
            TEST_CONFIG["PYGBAG_CMD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT),
            env=env,
            text=True,
            bufsize=1,
            # własna sesja/grupa procesów: cleanup() robi os.killpg na tej grupie,
            # bez tego SIGTERM trafiłby też w sam runner (współdzielona grupa) -> exit 143/144
            start_new_session=True,
        )
        try:
            url = self._wait_for_pygbag_url(self.pygbag_proc)
        except Exception:
            self.cleanup()
            raise
        self.url = url
        print(f"[{get_timestamp()}] pygbag ready: {url}")

    def _start_browser(self) -> None:
        self.pw = self._sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=True)

    def _open_page(self) -> None:
        """Otwórz stronę i wejdź na URL (bez per-scenariuszowego przygotowania).

        Listener konsoli rejestrujemy RAZ na stronę - przy jednej stronie na sesję
        wielokrotna rejestracja multiplikowałaby log.
        """
        assert self.browser is not None
        self.page = self.browser.new_page(viewport={"width": 1280, "height": 720})
        # log gry idzie do konsoli przeglądarki; przekaż diagnostykę testową do stdout
        # runnera (selektywnie - pełna konsola pygbag to spory szum)
        self.page.on(
            "console",
            lambda msg: print(f"[browser] {msg.text}")
            if ("[test]" in msg.text or "[agent" in msg.text or msg.text.startswith("profile:"))
            else None,
        )
        # Basic load; zmienne testowe i reload robi _prepare_scenario_page().
        self.page.goto(self.url, wait_until="domcontentloaded", timeout=30000)

    def _page_alive(self) -> bool:
        if self.page is None:
            return False
        try:
            self.page.evaluate("() => 1")
            return True
        except Exception:
            return False

    # -------------------------------------------------------------- scenariusz
    def start_game(self) -> None:
        if self.restart_per_scenario:
            # stary tryb (--web-restart-per-scenario): pełny build na scenariusz
            self._start_pygbag()
            self._start_browser()
            self._open_page()
        elif not self._page_alive():
            # crash WASM / zamknięta strona nie może kaskadować na kolejne scenariusze:
            # jednorazowa odbudowa strony na tym samym serwerze pygbag.
            self._page_rebuilds += 1
            if self._page_rebuilds > 1:
                raise RunnerFatal(
                    "web: strona padła po raz drugi w tej sesji - przerywam przebieg "
                    "(odpal z --web-restart-per-scenario, żeby izolować scenariusze)"
                )
            print(f"[{get_timestamp()}] [warn] strona nie odpowiada - odbudowuję (1/1)")
            try:
                if self.page is not None:
                    self.page.close()
            except Exception:
                pass
            self.page = None
            self._open_page()
        self._prepare_scenario_page()

    def stop_game(self) -> None:
        # Strona i serwer żyją dalej: `cleanup_saves_before()` i `clear_ui_state()`
        # następnego scenariusza działają na żywym localStorage, a start scenariusza
        # to tylko reload. W starym trybie zwijamy wszystko.
        if self.restart_per_scenario:
            self._teardown()

    def _prepare_scenario_page(self) -> None:
        """Per scenariusz: wyczyść klucze, wstrzyknij MoM.env + saves, przeładuj stronę."""
        assert self.page is not None
        # Jeden kanał MoM.env na wszystkie zmienne (A07): ta sama funkcja co desktop
        # decyduje o trybie deterministycznym i godzinie startu (pole `start_hour`).
        test_env: dict[str, str] = {"MOM_AGENT_CONTROL": "1"}
        apply_determinism_env(test_env, self.start_hour)
        # Profiler klatki (E02) przekazany z env runnera: `MOM_PROFILE=1 just test-web ...`
        # zbiera liczby z WASM tą samą drogą co desktop. E02 musiało do tego napisać
        # jednorazowy skrypt Playwrighta - stąd te dwie linie.
        if os.environ.get("MOM_PROFILE"):
            test_env["MOM_PROFILE"] = os.environ["MOM_PROFILE"]
        self.page.evaluate(
            "([k,v]) => localStorage.setItem(k, v)",
            [WEB_ENV_KEY, json.dumps(test_env)],
        )
        # stary klucz per-flaga: czyść, żeby fallback w game.py nie włączał agenta
        # w sesji, która używa już wyłącznie MoM.env
        self.page.evaluate(
            "() => localStorage.removeItem('" + WEB_AGENT_FLAG + "')"
        )
        self.page.evaluate(
            "() => localStorage.removeItem('" + WEB_INPUT_KEY + "')"
        )
        # zrzut z poprzedniego scenariusza: begin_scenario() czyści go tylko wtedy,
        # gdy strona już żyła - przy pierwszym scenariuszu jej jeszcze nie było
        self.clear_ui_state()
        # wstrzyknij ewentualne saves (corrupt/minimal) zadeklarowane przez scenario.
        # Robione TU (po czyszczeniu, przed reloadem), bo gra czyta localStorage w __init__.
        self._inject_setup_saves()
        print(f"[{get_timestamp()}] localStorage[{WEB_ENV_KEY}]={json.dumps(test_env)}; reloading...")
        self.page.reload(wait_until="domcontentloaded", timeout=30000)

        # czekaj aż gra zacznie rysować canvas (pygbag generuje <canvas>)
        try:
            self.page.wait_for_selector("canvas", timeout=30000)
        except Exception as e:
            print(f"[warn] canvas not found within 30s: {e}")
        # daj grze czas na pełny boot (asset load, MainMenuScreen)
        time.sleep(self.init_wait)
        print(f"[{get_timestamp()}] Web game ready")

    def _send_commands(self, commands: List[str]) -> None:
        if not commands:
            return
        text = " ".join(commands)
        # escape for JS string literal
        escaped = text.replace("\\", "\\\\").replace("'", "\\'")
        self.page.evaluate(
            "([k,v]) => localStorage.setItem(k, v)",
            [WEB_INPUT_KEY, text],
        )

    def execute_action(self, action: TestAction) -> None:
        print(f"[{get_timestamp()}] {action.slug}")
        start = time.perf_counter()
        ctrl, wants_shot = action.split_screenshot()
        self._send_commands(ctrl)
        end = time.perf_counter()
        print(f"[{get_timestamp()}] Sent {len(ctrl)} cmds. Delta: {end - start:.4f}s")
        if action.wait > 0:
            time.sleep(action.wait)
        if wants_shot:
            self.take_screenshot(action.slug)

    def check_assertion(self, assertion: dict[str, Any]) -> List[str]:
        common = self.check_common_assertion(assertion)
        if common is not None:
            return common
        a_type = assertion.get("type")
        if a_type == "file_exists":
            # Translator: assertion z desktopa -> sprawdź localStorage zamiast pliku.
            # Format ścieżki: <save_dir>/save_N.mom -> wyciągnij N.
            m = re.search(r"save_(\d+)\.mom$", assertion["path"])
            if not m:
                return [
                    f"web: nie wyciągnąłem slotu z paths '{assertion['path']}'"
                    f" (use type 'localstorage_exists' jawnie)"
                ]
            slot = int(m.group(1))
            return self._check_localstorage_slot(slot, assertion.get("min_size"))
        elif a_type == "localstorage_exists":
            m = re.search(r"save_(\d+)", assertion.get("key", ""))
            if m:
                slot = int(m.group(1))
                return self._check_localstorage_slot(slot, assertion.get("min_size"))
            return [f"localstorage_exists: brak slotu w 'key' ({assertion.get('key')})"]
        elif a_type == "save_absent":
            m = re.search(r"save_(\d+)", assertion.get("path", ""))
            if not m:
                return [f"save_absent: brak slotu w 'path' ({assertion.get('path')})"]
            slot = int(m.group(1))
            key = f"{WEB_SAVE_KEY_PREFIX}{slot}"
            raw = self.page.evaluate("([k]) => localStorage.getItem(k)", [key])
            if raw:
                return [f"{key} present in localStorage but should be absent"]
            return []
        return [f"unknown assertion type: {a_type}"]

    def _assert_process_alive(self, assertion: dict[str, Any]) -> List[str]:
        # web: gra żyje, jeśli strona nadal odpowiada na evaluate (nie ma crashu WASM)
        if self.page is None:
            return ["process_alive: no page (web game not running)"]
        try:
            self.page.evaluate("() => 1")
        except Exception as e:
            return [f"process_alive: web page unresponsive ({e})"]
        return []

    def read_ui_state(self) -> dict[str, Any] | None:
        # web: gra nie ma dostępu do dysku, więc zrzut ląduje w localStorage
        if self.page is None:
            return None
        try:
            raw = self.page.evaluate("([k]) => localStorage.getItem(k)", [WEB_UI_STATE_KEY])
        except Exception:
            return None
        if not raw:
            return None
        try:
            return dict(json.loads(raw))
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def clear_ui_state(self) -> None:
        if self.page is None:
            return
        try:
            self.page.evaluate("([k]) => localStorage.removeItem(k)", [WEB_UI_STATE_KEY])
        except Exception:
            pass

    def _check_localstorage_slot(self, slot: int, min_size: Any) -> List[str]:
        key = f"{WEB_SAVE_KEY_PREFIX}{slot}"
        raw = self.page.evaluate(
            "([k]) => localStorage.getItem(k)",
            [key],
        )
        if not raw:
            return [f"{key} not present in localStorage"]
        if min_size is not None:
            size = len(raw)
            if size < min_size:
                return [f"{key} size {size} < {min_size}"]
        return []

    def cleanup_saves_before(self, scenario: TestScenario) -> None:
        # w web mode saveBackend jest localStorage -> czyścimy jeśli runner jest już w górze,
        # w przeciwnym razie clear nastąpi po starcie gry (reload czyści w _runner harmonogram).
        # Tutaj wykonujemy pomiędzy scenariuszami, gdy pygbag jest jeszcze aktywny z poprzedniego.
        if self.page is not None:
            self.page.evaluate(
                "() => {"
                f" for (let i=0;i<10;i++) localStorage.removeItem('{WEB_SAVE_KEY_PREFIX}'+i);"
                " }"
            )
            self.page.evaluate(f"() => localStorage.removeItem('{WEB_INPUT_KEY}')")
            print(f"[cleanup] cleared localStorage save slots")

    def setup_saves(self, saves: List[dict[str, Any]]) -> None:
        # w web nie jesteśmy jeszcze po pierwszym goto - zapamiętaj na później.
        self._pending_setup_saves = list(saves)

    def _inject_setup_saves(self) -> None:
        if not self._pending_setup_saves or self.page is None:
            return
        from save_fixtures import (
            FUTURE_VERSION, OLD_VERSION, corrupt_save_text, minimal_save_dict,
        )
        for spec in self._pending_setup_saves:
            slot = int(spec["slot"])
            kind = spec.get("type", "minimal")
            key = f"{WEB_SAVE_KEY_PREFIX}{slot}"
            if kind == "corrupt":
                payload = corrupt_save_text()
            elif kind == "corrupt_version":
                payload = json.dumps(minimal_save_dict(slot, version=FUTURE_VERSION))
            elif kind == "old_version":
                payload = json.dumps(minimal_save_dict(slot, version=OLD_VERSION))
            else:
                payload = json.dumps(minimal_save_dict(slot))
            self.page.evaluate(
                "([k,v]) => localStorage.setItem(k, v)",
                [key, payload],
            )
            print(f"[setup] localStorage['{key}'] = {kind}")
        self._pending_setup_saves = []

    def _teardown(self) -> None:
        """Zwiń całą infrastrukturę web: strona, przeglądarka, Playwright, pygbag."""
        if self.page:
            try:
                self.page.close()
            except Exception:
                pass
            self.page = None
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
            self.browser = None
        if self.pw:
            try:
                self.pw.stop()
            except Exception:
                pass
            self.pw = None
        if self.pygbag_proc:
            print(f"[{get_timestamp()}] Stopping pygbag...")
            try:
                os.killpg(os.getpgid(self.pygbag_proc.pid), 15)
                try:
                    self.pygbag_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(os.getpgid(self.pygbag_proc.pid), 9)
                    self.pygbag_proc.wait(timeout=5)
            except Exception:
                try:
                    self.pygbag_proc.kill()
                except Exception:
                    pass
            print(f"[{get_timestamp()}] pygbag stopped.")
            self.pygbag_proc = None

    def _save_screenshot(self, path: Path) -> None:
        assert self.page is not None
        self.page.screenshot(path=str(path), full_page=False)
        # daj chwilę buffer po capture, żeby kolejna akcja nie złapała intermediate frame
        time.sleep(TEST_CONFIG["SCREENSHOT_BUFFER"])


# ============================================================================
# Orchestration
# ============================================================================
def load_scenarios(path: str) -> List[TestScenario]:
    with open(path, "r") as f:
        data = json.load(f)
    scenarios = []
    for s in data:
        actions = [
            TestAction(
                a.get("slug") or a.get("label", ""),
                a["commands"],
                a.get("wait", TEST_CONFIG["TRANSITION_WAIT"]),
            )
            for a in s["actions"]
        ]
        scenarios.append(TestScenario(
            s["name"],
            actions,
            assertions=s.get("assertions"),
            cleanup_saves=s.get("cleanup_saves"),
            platform_spec=s.get("platform"),
            setup_saves=s.get("setup_saves"),
            slug=s.get("slug"),
            start_hour=s.get("start_hour"),
        ))
    return scenarios


def run_scenarios(scenarios: List[TestScenario], runner: RunnerBase) -> int:
    failures = 0
    runner.start_session()
    try:
        for scenario in scenarios:
            runner.begin_scenario(scenario)
            runner.cleanup_saves_before(scenario)
            if scenario.setup_saves:
                runner.setup_saves(scenario.setup_saves)
            try:
                runner.start_game()
                scenario.run(runner)
            except RunnerFatal:
                # infrastruktura padła (np. strona web drugi raz) - dalsze scenariusze
                # i tak posypią się kaskadowo; przerwij przebieg
                raise
            except AssertionError as e:
                print(f"Test failed: {e}")
                failures += 1
            except Exception as e:
                print(f"Test failed: {e}")
                failures += 1
            finally:
                runner.stop_game()
    finally:
        # musi się wykonać także przy KeyboardInterrupt - inaczej zostaje żywy pygbag
        runner.end_session()
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent-driven UI test runner")
    parser.add_argument("--web", action="store_true", help="use pygbag + Playwright web backend")
    parser.add_argument("--url", default=None, help="override pygbag URL (web mode)")
    parser.add_argument(
        "--timeout", type=float, default=None,
        help="web mode: seconds to wait for the game to boot after the canvas appears "
             f"(default {TEST_CONFIG['INIT_WAIT_WEB']}); bump on slow CI/hardware",
    )
    parser.add_argument(
        "--pygbag-timeout", type=float, default=None,
        help="web mode: seconds to wait for the pygbag server to build + serve "
             f"(default {TEST_CONFIG['PYGBAG_BOOT_TIMEOUT']})",
    )
    parser.add_argument(
        "--web-restart-per-scenario", action="store_true",
        help="web mode: restart pygbag + browser for every scenario (pre-A08 behaviour; "
             "use when you suspect state leaking between scenarios)",
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help="run only the smoke set (TEST_CONFIG['SMOKE_SCENARIOS']) instead of everything",
    )
    parser.add_argument("scenario", nargs="?", default=None, help="scenario name; omit to run all")
    args = parser.parse_args()
    if args.smoke and args.scenario:
        print("Error: --smoke i nazwa scenariusza wykluczają się.")
        return 2

    # zanim cokolwiek zbuduje/wystartuje - patrz acquire_singleton_lock()
    acquire_singleton_lock(_pygbag_port() if args.web and not args.url else None)

    # before anything resolves a save path - see isolate_game_data()
    isolate_game_data()

    scenarios = load_scenarios(TEST_CONFIG["SCENARIOS_FILE"])
    backend = "web" if args.web else "desktop"
    selected = [s for s in scenarios if s.supports(backend)]
    if args.scenario:
        target_name = args.scenario
        selected = [s for s in selected if s.name == target_name]
        if not selected:
            avail = [s.name for s in scenarios if s.supports(backend)]
            print(f"Error: scenario '{target_name}' not available for backend '{backend}'.")
            print(f"Available: {avail}")
            return 2
    if args.smoke:
        smoke_names = list(TEST_CONFIG["SMOKE_SCENARIOS"])
        by_name = {s.name: s for s in selected}
        missing = [n for n in smoke_names if n not in by_name]
        if missing:
            # literówka w SMOKE_SCENARIOS nie może cicho zmniejszyć bramki
            print(f"Error: smoke scenarios not available for backend '{backend}': {missing}")
            return 2
        selected = [by_name[n] for n in smoke_names]

    runner: RunnerBase
    if args.web:
        runner = WebRunner(
            url=args.url,
            init_wait=args.timeout,
            pygbag_timeout=args.pygbag_timeout,
            restart_per_scenario=args.web_restart_per_scenario,
        )
    else:
        runner = DesktopRunner()
    install_cleanup_handlers(runner)

    print(f"Backend: {backend}; scenarios: {[s.name for s in selected]}")
    failures = run_scenarios(selected, runner)
    if failures:
        print(f"\n{failures} scenario(s) failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())