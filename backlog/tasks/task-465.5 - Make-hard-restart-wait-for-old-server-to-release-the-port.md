---
id: TASK-465.5
title: Make hard restart wait for old server to release the port
status: Done
assignee: []
created_date: '2026-06-08 19:51'
updated_date: '2026-06-09 03:13'
labels:
  - bug
dependencies: []
parent_task_id: TASK-465
priority: high
ordinal: 166000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
During live recovery on 2026-06-08, make restart ran stop + start immediately. The old oompah process still held port 8090, so the new process failed with errno 98 address already in use, then overwrote .oompah.pid with the failed process PID.

Fix the Makefile/service control path so restart waits for the old PID to exit and for the configured port to be released before starting a replacement. If the old process does not exit within a bounded timeout, report a clear failure or escalate intentionally instead of writing a dead PID file.

Acceptance criteria:
- make restart does not start a second process while the old one still owns the configured port.
- Failed starts do not leave .oompah.pid pointing at a dead process.
- Tests or scripted coverage exercise the restart wait/race behavior without relying on sleeps alone.
<!-- SECTION:DESCRIPTION:END -->

## Comments

<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-06-08 20:45
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 20:46
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 20:46
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 10s (attempt #1)
---

author: oompah
created: 2026-06-08 20:46
---
Run #1 [attempt=1, profile=default, role=fast -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 40s
- Log: TASK-465.5__20260608T204616Z.jsonl
---

author: oompah
created: 2026-06-08 20:48
---
Agent dispatched (profile: deep)
---

author: oompah
created: 2026-06-08 20:49
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 20:49
---
Agent failed: RuntimeError: Codex exec exited with code 1: . Retrying in 20s (attempt #2)
---

author: oompah
created: 2026-06-08 20:50
---
Run #2 [attempt=2, profile=deep, role=deep -> Codex/default]
- Turns: 1, Tool calls: 0
- Tokens: 0 in / 0 out [0 total]
- Cost: $0.0000
- Exit: error, Duration: 1m 16s
- Log: TASK-465.5__20260608T204939Z.jsonl
---

author: oompah
created: 2026-06-08 20:52
---
Retrying (attempt #2, agent: deep)
---

author: oompah
created: 2026-06-08 20:52
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 22:24
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-08 22:24
---
Focus: Duplicate Investigator
---

author: oompah
created: 2026-06-08 23:09
---
Agent completed successfully in 2741s (78682 tokens)
---

author: oompah
created: 2026-06-08 23:09
---
Run #1 [attempt=1, profile=default, role=fast -> Claude/default]
- Turns: 245, Tool calls: 152
- Tokens: 132 in / 78.5K out [78.7K total]
- Cost: $0.0000
- Exit: normal, Duration: 45m 41s
- Log: TASK-465.5__20260608T222507Z.jsonl
---

author: oompah
created: 2026-06-09 03:07
---
Agent dispatched (profile: default)
---

author: oompah
created: 2026-06-09 03:12
---
Duplicate investigation: No duplicate found. TASK-465.4 covers graceful restart drain wakeup (different problem). TASK-465.5 is unique — hard restart port/PID race. Previous agent (2026-06-08 23:09) implemented the fix in commit 89ffd7e but did not update task status to Done. Proceeding to verify implementation and close properly.
---

author: oompah
created: 2026-06-09 03:13
---
Verification: All 20 tests in tests/test_makefile_restart_wait.py pass (13 static-analysis, 4 functional port_in_use, 3 end-to-end wait_for_stop). Implementation from previous agent run is intact in commit 89ffd7e. Not a duplicate — closing task.
---
<!-- COMMENTS:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed make restart port/PID race: added wait_for_stop Makefile define (polls kill -0 then port_in_use before returning), port_in_use define (ss with lsof fallback), STOP_TIMEOUT variable (default 30s). stop: now waits before returning; start: refuses launch if port busy and removes .oompah.pid on failed startup. 20 tests added covering structure, port detection, and end-to-end wait behavior. Not a duplicate of TASK-465.4 (which handles graceful restart drain wakeup).
<!-- SECTION:FINAL_SUMMARY:END -->
