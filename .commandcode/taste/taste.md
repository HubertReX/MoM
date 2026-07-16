# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# communication
- Communicate in Polish for analysis, explanations, and discussions. Confidence: 0.90
- Use single commits for grouped/related changes rather than per-file commits. Confidence: 0.80

# architecture
- Prefer YAML or TOML over JSON for hand-editable configuration files. Never propose writing config directly in JSON for manual editing. Confidence: 0.85
- Use dataclasses with `slots=True` for data model classes. Confidence: 0.75
- Use a whitelist-based mini-DSL (parsed via `ast.parse`) instead of `eval()` for evaluating conditions in dialogue systems. Confidence: 0.75

# workflow
- Use the moab CLI (`python3 bin/moab`) for task management: claim, assign, review, done, new, status. Confidence: 0.80
- Use `/html-craft` to generate rich visual analysis pages when exploring complex migration or design questions. Confidence: 0.85
- For agent-based visual testing, set `MOM_SS_REVIEW_MODEL=google/gemini-3.1-flash-lite` before running the ss-reviewer agent. Confidence: 0.80
- Skip web/Playwright tests when wrapping up a task; focus on desktop-mode verification. Confidence: 0.70

# testing
- Use `python3 tests/test_X.py` (standalone scripts) rather than pytest for running tests. Confidence: 0.75
- For visual/agent-based UI tests, write structured JSON scenario files with `slug`, `actions`, and `screenshot_review` assertions. Confidence: 0.80
