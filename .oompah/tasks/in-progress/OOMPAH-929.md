---
id: OOMPAH-929
type: task
status: In Progress
priority: null
title: Rearm superseded durable events on newer source generations
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-09T02:47:20.781959Z'
updated_at: '2026-08-09T02:55:22.447102Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live all-enforce rollout of candidate 33f85955b exposed an indefinite liveness divergence for OOMPAH-869 and OOMPAH-899. Their validation_submission fact-lane jobs were superseded by newer imperative direct-owner events; later workflow snapshots reuse the unchanged event cursor/idempotency key, replay the terminal superseded rows, and correctly reject them as materialized. Implementation scope: update WorkflowJobStore.materialize_event and its runtime integration so a newer source generation allocates a fresh event generation/idempotency key when the exact semantic event has no live job or only a terminal superseded/cancelled/completed/exhausted job, while preserving same-source idempotency and replay of queued/running/retry_wait authority. Relevant files: oompah/workflow_jobs.py or the actual durable store module, workflow runtime materialization paths, and focused workflow job/runtime tests. Required tests: all terminal job states rearm only on a newer source generation; exact same-source replay stays idempotent; active equivalent jobs replay without duplication; runtime regression where a fact validation_submission is superseded by an imperative owner event and is regenerated on the next accepted snapshot. Acceptance: staged all-enforce live rollout reaches a complete liveness scan with required_recovery_count equal to materialized_recovery_count, current divergence zero, healthy service, zero actionable alerts, no expired jobs, and the five-minute rollout canary passes.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 02:47
---
Live reproduction confirmed at workflow generations 39 and 40: required_recovery_count=132, materialized_recovery_count=130, with OOMPAH-869 and OOMPAH-899 repeatedly replaying terminal superseded validation_submission jobs. Release advance is paused until the store/runtime fix, focused tests, exact gate, and all-enforce live convergence complete.
---
<!-- COMMENTS:END -->
