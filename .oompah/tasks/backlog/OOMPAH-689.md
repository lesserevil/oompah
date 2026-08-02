---
id: OOMPAH-689
type: task
status: Backlog
priority: null
title: Do not poison successful handoff after expected non-running peer reads
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-02T00:13:22.222984Z'
updated_at: '2026-08-02T00:13:22.222984Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Live regression on EXOCOMP-155 on 2026-08-01/02 after merged OOMPAH-678. The worker successfully viewed, commented on, and submitted its assigned task, but also attempted read-only oompah task view calls for related non-running Exocomp tasks. Those calls correctly returned scoped HTTP 403. At worker exit, Oompah nevertheless consumed a recorded task-handoff failure, overwrote the successful Ready-to-Integrate submission with Needs Human, and claimed the task-scoped capability could not update the task.

Root cause: server._is_verified_peer_scope_denial verifies both the source worker and the target with _verified_running_entry. OOMPAH-678 therefore treats read-only exploration as informational only when the target task happens to be running; an Open, Ready-to-Integrate, Done, or otherwise non-running peer produces record_task_handoff_failure, even though the source assignment/token is verified and its own-task mutations succeed.

Implementation scope:
- Classify a read-only cross-task view denial from a verified live source worker as an intentional policy denial without requiring the target task to have a RunningEntry.
- Keep authorization fail-closed: the peer request remains HTTP 403 and returns no task data.
- Do not suppress wrong-token propagation, missing/expired/revoked capabilities, cross-project ambiguity, or forbidden cross-task mutations.
- Make worker-exit reconciliation distinguish informational denials from failures of the assigned task's own handoff operations. A successful own-task submit must not be overwritten by earlier expected peer-read denials.
- Preserve actionable auth-health counters for genuine mismatches and informational policy counters for expected exploration.

Relevant code: oompah/server.py (_is_verified_peer_scope_denial and task-handoff validation), oompah/task_handoff.py failure recording, and oompah/orchestrator.py worker-exit handoff reconciliation.

Required tests:
- A verified worker views a non-running sibling, receives 403, then comments on and submits its assigned task; exit leaves the task submitted and never Needs Human.
- The same sequence covers Open, Ready-to-Integrate, terminal, and unknown target identifiers without leaking existence.
- Wrong-token use against the assigned task and cross-task mutation attempts remain rejected and retain the intended actionable signal.
- OOMPAH-678 live-peer behavior and auth-health tests remain green.

Acceptance criteria:
- Replaying the EXOCOMP-155 request sequence cannot overwrite a successful submit with Needs Human.
- Expected peer reads stay fail-closed but do not degrade handoff health or poison exit reconciliation.
- Focused task-handoff/server/orchestrator tests and make test pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

