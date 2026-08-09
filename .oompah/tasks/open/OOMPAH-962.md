---
id: OOMPAH-962
type: bug
status: Open
priority: 1
title: Recover quarantined control effects without task deadlock
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T14:35:21.482578Z'
updated_at: '2026-08-09T14:35:34.588829Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Fix durable workflow recovery when a synchronous control-effect adapter exceeds its operation timeout and the invocation cannot be terminated. Live reproduction on OOMPAH-959: authority_revocation exceeded 60 seconds, WorkflowJobStore.quarantine_owned left the job running with phase=quarantined and lease_expires_at=NULL, and the per-task serialization predicate then blocked a newer direct_owner_claim indefinitely while the service process remained alive. Preserve the core safety invariant that a possibly running external mutation must never overlap a replacement. Add an observable bounded recovery path: detect when the detached call actually returns and safely finalize/recover its exact fenced job, or request/coalesce a graceful service recycle when it cannot be proven complete; surface operator health until recovery and do not require manual SQLite edits. Relevant code: workflow_worker quarantine/detached-call lifecycle, workflow job recovery and per-task serialization, orchestrator restart/health signaling. Tests: late successful and failed return, permanently blocked call, concurrent replacement, shutdown/restart, PID-generation fencing, no duplicate external mutation, no busy loop, and exact control/data lane behavior. Acceptance: a quarantined control effect either reaches a safe terminal/retry state after its call returns or triggers bounded safe recovery, subsequent same-task work flows automatically, and complete gates pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

