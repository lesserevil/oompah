---
id: OOMPAH-959
type: task
status: In Progress
priority: null
title: Continue durable effects when concurrency fills before batch size
parent: null
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-09T14:08:58.066871Z'
updated_at: '2026-08-09T14:23:41.898294Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live rollout regression on build ba0859da9 after OOMPAH-939/OOMPAH-955: generations 497 and 500 each took 215-223 seconds, admitted exactly four effects (max_concurrent=4), left more than 140 queued plus 24 due retry jobs, but reported worker.batch_saturated=false and did not post the coalesced workflow continuation. Root cause is WorkflowRuntime._run_due defining saturation only as scheduled >= batch_size; when max_concurrent is lower than batch_size, admission fills every lane before reaching batch_size and the continuation signal is impossible. This strands ready durable effects until the next expensive full-sync tick and prevents OOMPAH-940 rollout convergence. Scope: make the runtime truthfully report remaining eligible work when admission stopped because all concurrency lanes filled, including reserved control/shared lanes, without false continuations when no eligible row remains; preserve per-task serialization, fair project claims, pause/drain fencing, coalescing, and non-recursive scheduling. Relevant files: oompah/workflow_runtime.py _run_due/_effect_finished, oompah/orchestrator.py _request_workflow_batch_continuation, workflow job eligibility queries, and tests/test_workflow_runtime.py plus tests/test_orchestrator_full_sync.py. Required tests: max_concurrent < batch_size with more eligible rows reports saturation and requests immediate continuation; exactly capacity rows does not spin; lane-specific exhaustion does not hide eligible work in the other lane; paused/ineligible/future rows do not trigger; completion replenishes capacity and converges through coalesced continuations; restart and concurrent _run_due callers remain fenced. Acceptance: production with max_concurrent=4 drains ready rows through prompt continuations rather than one four-row slice per 3.7-minute full sync, the saturation metric is truthful, no busy loop occurs, focused/full hosted gates pass, and the OOMPAH-940 rollout canary advances.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 14:23
---
Implemented exact non-mutating claimability probing shared with claim_next, concurrency-cap saturation signaling with a no-spin admission edge, and focused store/runtime regressions. Full workflow job/runtime modules pass: 155 tests. Ruff passes for changed surfaces aside from one pre-existing unused import excluded from the focused lint run.
---
<!-- COMMENTS:END -->
