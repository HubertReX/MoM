# Security audit and repository hardening - 2026-07-05

This document records the GitHub security review of the `HubertReX/MoM` repository, the hardening changes applied, the analysis of open Dependabot high-severity alerts, and the `requirements.txt` cleanup.

## Goal

Make sure that only the owner ([@HubertReX](https://github.com/HubertReX)) can commit and merge to `main`, apply open-source best practices, and reduce the risk of a malicious actor sabotaging, destroying, or disrupting work in the repository.

## Findings (initial state)

Good:

- Public repository under the MIT license.
- Owner is the only collaborator (admin) - external users already cannot push or merge to `main`; they must fork and open a Pull Request.
- Secret scanning and push protection: enabled.
- Actions default workflow permissions: `read`; workflows cannot approve Pull Requests.
- All workflows are `workflow_dispatch` (manual) only, so a Pull Request from a fork cannot trigger the deploy workflow and exfiltrate `ITCH_IO_API_KEY`. This closes the most common supply-chain attack vector on public repos.

Gaps:

- `main` was **not** protected (no branch protection, no rulesets) - force-push, branch deletion, and unreviewed direct commits were possible.
- Dependabot vulnerability alerts were disabled.
- No `SECURITY.md` (no private channel to report vulnerabilities).
- The contribution file is named `CONTRIBUTION.md`; GitHub only auto-links `CONTRIBUTING.md` in its UI (left as-is for now).

## Changes applied

On GitHub:

- Created ruleset **`protect-main`** (id `18525284`) on the default branch:
  - blocks force-push (`non_fast_forward`),
  - blocks branch deletion (`deletion`),
  - requires a Pull Request before merge (`pull_request`),
  - **bypass for the repository admin role** - the owner can still push directly to `main` when needed (solo-maintainer friendly). Verified working: a direct push reported `Bypassed rule violations for refs/heads/main`.
- Enabled Dependabot vulnerability alerts and automated security fixes.

In the repository (committed in `dd90320`):

- `CONTRIBUTION.md` - added a **Contributing** section documenting the fork-and-PR workflow, the protected-`main` rules, and the fact that only the maintainer merges.
- `SECURITY.md` - added, with a private vulnerability reporting channel (GitHub private advisories).

## Dependabot high-severity alerts

Enabling Dependabot surfaced 36 vulnerabilities (17 high, 16 moderate, 3 low). The 17 high alerts collapse to **4 unique packages** (the same advisories are counted across three manifest files: `requirements.txt`, `requirements-dev.txt`, `requirements_tree.txt`).

Rule applied: only auto-upgrade when a **minor-level** bump (no breaking changes) is enough. Under that rule, **no automatic upgrade was performed** - reasoning per package:

- **pillow** - installed `10.3.0`; fix requires `12.2.0` (OOB write PSD, FITS decompression bomb, integer overflow). `10 -> 12` / `11 -> 12` is a **major** bump (Pillow 12 dropped Python 3.9 and removed deprecated APIs). Needs review + testing.
- **setuptools** - `70.0.0` (dev-only); fix requires `78.1.1` (path traversal / arbitrary file write). `70 -> 78` crosses several majors with breaking changes. Needs review.
- **lxml** - `5.2.2`; fix requires `6.1.0` (XXE via `iterparse`). `5 -> 6` is a **major** bump. Also present only in `requirements_tree.txt` (a `pipdeptree` snapshot, not a real install manifest).
- **urllib3** - `2.2.1`; fix `2.7.0` is the only **minor** (safe) bump, but urllib3 is a **transitive** dependency (via `requests` <- `zengl-extras`) present only in the snapshot file. It is not directly pinned in the real manifests, so there is nothing to bump there.

### Recommendations (pending decision)

- Bump `pillow 10.3.0 -> 12.2.0` on a branch + PR, run the game and tests to confirm no regression (highest-value fix, especially if the web version will ever accept user-uploaded images/saves).
- Bump `setuptools` and `lxml` similarly (lower urgency: dev/build-only and snapshot-only respectively).

## requirements.txt cleanup

`requirements.txt` contained duplicate, conflicting pins. Notably, with two `pillow` pins (`10.3.0` then `11.2.1`), the **actually installed** version is `10.3.0` - so pip did not simply take the last line. The file was cleaned to a single pin per package, matching the versions currently installed and working in `.venv`:

- `rich`: `>=13.7.1` + `==14.0.0` -> `==15.0.0`
- `numpy`: `>=1.26.4` + `==2.2.5` -> `==2.5.0`
- `pydantic`: `>=2.7.1` + `==2.11.4` -> `==2.9.2`
- `pillow`: `==10.3.0` + `==11.2.1` -> `==10.3.0`
- `click`: `# ==8.1.7` + `==8.2.0` -> `==8.4.2`

Note: `pillow==10.3.0` is still within the vulnerable range - it stays pinned to the working version pending the major-bump decision above.

Dead entry removed: `ffmpeg==1.4` was listed but **not installed** in the venv, and it collided with `ffmpeg-python` (both expose the `ffmpeg` import). The game runs on `ffmpeg-python==0.2.0` alone, so `ffmpeg==1.4` was removed.

## Optional follow-ups

- Rename `CONTRIBUTION.md` -> `CONTRIBUTING.md` so GitHub auto-links it in the New PR / Issues UI.
- Add `CODE_OF_CONDUCT.md`, issue/PR templates, and a `CODEOWNERS` file.
- Enable 2FA on the `HubertReX` account (single highest-impact account-security step).
- Prefer a fine-grained PAT over the classic token with full `repo` + `workflow` scope.
- Clean up the same duplicate-pin pattern in `requirements-dev.txt` and regenerate `requirements_tree.txt`.
