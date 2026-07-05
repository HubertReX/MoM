# Security Policy

## Reporting a vulnerability

If you discover a security vulnerability in this project, please report it **privately** - do not open a public issue, discussion, or pull request that discloses the details.

Preferred channel:

- Use GitHub's [private vulnerability reporting](https://github.com/HubertReX/MoM/security/advisories/new) ("Report a vulnerability" under the repository **Security** tab).

Please include:

- a description of the issue and its potential impact,
- steps to reproduce (proof of concept if possible),
- affected version, branch, or commit.

You can expect an initial response within a reasonable time. Once the issue is confirmed and fixed, the report may be disclosed publicly, crediting the reporter unless anonymity is requested.

## Scope

This is a hobby game project. There is no production service or user data at stake, but the following are still in scope:

- exposure of build/deploy secrets (e.g. `itch.io` API key) via workflows,
- malicious code paths or supply-chain issues in dependencies,
- anything that could compromise a contributor's or player's machine when building or running the game.

## Supported versions

Only the `main` branch is actively maintained. Fixes are applied to `main`; older tags and branches are not patched.
