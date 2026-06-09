---
id: TASK-472.3
title: Harden orchestrator restart relay under Granian
status: Done
assignee: []
created_date: '2026-06-09 04:19'
updated_date: '2026-06-09 21:02'
labels:
  - 'needs:backend'
  - 'needs:test'
dependencies: []
parent_task_id: TASK-472
priority: high
ordinal: 192000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Restart currently relays from the worker to the Granian supervisor via a sentinel file + SIGTERM to PPID, then main() re-execs. Verify this against Granian's respawn_failed_workers setting and harden it. Ensure /api/v1/orchestrator/restart and workflow-file-reload restart both work end-to-end under granian, and that operator Ctrl-C shuts down cleanly without a spurious restart.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 API restart and workflow-reload restart both re-exec correctly under granian
- [ ] #2 Ctrl-C shuts down with no restart and no orphaned processes
- [ ] #3 Behavior verified against respawn_failed_workers
<!-- AC:END -->
