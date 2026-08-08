---
id: OOMPAH-914
type: task
status: In Progress
priority: null
title: Recover expired task-transition claims without operator deadlock
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-08T14:25:47.766180Z'
updated_at: '2026-08-08T15:38:43.664845Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

A live Backlog to Open request for OOMPAH-912 was interrupted while its durable transition was in applying. After the 300-second claim expired and the service restarted, every new operator request was rejected with transition.recovery_required because TransitionJournal.begin only permits the exact old idempotency key to reclaim an expired foreign transition, while the ordinary status API generates a new key and exposes no recovery path. The task is therefore permanently stuck without direct database surgery or replaying an inaccessible internal key.\n\nImplementation scope:\n- Add a durable restart/runtime recovery lane for expired task-transition claims that inspects the original immutable intent and current tracker state, resumes or safely finalizes that exact transition, and releases the claim.\n- Keep per-task fencing and fail closed for live leases, ambiguous tracker evidence, changed task authority, and conflicting newer intents.\n- Make API/operator requests report bounded recovery progress and retry successfully after recovery rather than deadlocking forever on transition.recovery_required.\n- Add health/diagnostic visibility for outstanding expired claims.\n- Relevant code: oompah/task_transition_service.py TransitionJournal.begin and TaskTransitionService.execute, orchestrator startup/recovery wiring, server status-transition error mapping.\n\nRequired tests:\n- Simulate process death after APPLYING, advance beyond lease TTL, restart, and prove the original intent is recovered or safely finalized and a later operator transition can proceed.\n- Cover effect-already-applied, effect-not-applied, stale status/version, live foreign lease, and concurrent recovery claimant cases.\n- Prove recovery never deletes append-only journal history and never permits a conflicting writer while a lease is live.\n\nAcceptance criteria:\n- No task can remain permanently blocked solely because an inaccessible prior status-transition idempotency key owns an expired claim.\n- OOMPAH-912 can be promoted through the normal API after recovery without manual SQLite edits.\n- Focused transition-service, orchestrator restart, and server API tests pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-08 14:37
---
Direct owner implementation is in progress on the systemic composition branch. Recovery is being made durable: an expired foreign claim will reclaim and execute the exact immutable prior intent under CAS before retrying the waiting operator request; live leases and concurrent recovery remain fenced. Status remains Backlog only because this bug currently prevents normal promotion.
---
<!-- COMMENTS:END -->
