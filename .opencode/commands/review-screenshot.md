---
description: >-
  Analyzes a game screenshot via the ss-reviewer subagent. Defaults to the
  most recent screenshot in screenshots/agent/, or accepts a path/filename
  as an argument to review a specific one.
agent: ss-reviewer
subtask: true
---

Argument provided by the user (may be empty): `$ARGUMENTS`

Most recent screenshot detected automatically:
!`ls -t screenshots/agent/*.png 2>/dev/null | head -n1`

Resolve which screenshot to analyze:
- If the argument above is non-empty, use it as the target screenshot.
  If it's a bare filename with no directory (e.g. `agent_20260630_214903_0005.png`),
  assume it lives in `screenshots/agent/`.
- If the argument is empty, use the "most recent screenshot detected
  automatically" path shown above.

Read that screenshot file and analyze it following your standard
screenshot-review process (scene summary, player/NPCs/UI, anomalies,
cross-reference against tests/scenarios.json where relevant).
