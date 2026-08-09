---
id: OOMPAH-927
type: bug
status: In Progress
priority: 1
title: Schedule universal workflow controller under durable runtime
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-08T23:01:44.924274Z'
updated_at: '2026-08-09T05:13:38.526701Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-763

All-enforce production rollout on ce8b839811c2f0ff297179278aa3aa6171c5705b exposed a liveness deadlock: Orchestrator._tick() returns after _run_durable_workflow_tick() whenever workflow_runtime is installed, while the only _run_workflow_controller_sweep() scheduling site is in the unreachable legacy/runtime-less path. The durable domain pass completes and jobs flow, but workflow_controller passes/evaluated/wakeups remain zero forever and restored liveness remains restart_overdue with scan_complete=false. Implement production scheduling/coalescing of the universal controller sweep from the durable runtime tick path in oompah/orchestrator.py without restoring legacy lifecycle writers or allowing concurrent sweeps. Add regression coverage proving an installed all-enforce durable runtime tick advances the universal controller, publishes a liveness snapshot, clears restart reconstruction, preserves fail-closed generation fencing, and does not duplicate scheduling across event-driven/full-sync ticks. Run focused orchestrator/workflow liveness tests plus the complete make test gate. Acceptance: staged all-enforce live rollout reaches healthy liveness with controller passes greater than zero, zero actionable alerts, no expired/exhausted jobs, and passes the five-minute workflow rollout canary.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 23:03
---
Architecture refinement from live forensics: do not revive the retired process-local _run_workflow_controller_sweep below the durable-runtime early return. The retirement architecture intentionally bans that second lifecycle owner. The fix must make UniversalTotalityLivenessController observation/publication a WorkflowRuntime-owned step at the accepted durable snapshot generation, then expose that runtime-owned controller/liveness projection through Orchestrator state. Preserve one WorkflowJobStore authority, stale-generation fencing, and idempotent job materialization. Live proof: durable gen18 completed at 22:57:33 and gen19 after restart, while controller passes/wakeups stayed zero and liveness snapshot_generation stayed null across both instances.
---
author: oompah
created: 2026-08-09 05:13
---
Direct project-owner completion verified on composed rollout head dec2c35bb9e61bd286e271bcd03fcb0700f69a6e: exact full gate passed (18,874 passed, 7 skipped, 2 xfailed), all four durable workflow domains are live in enforce mode, no actionable global alerts remain, and current durable exhaustion/expired leases are zero.
---
<!-- COMMENTS:END -->
