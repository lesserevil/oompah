---
id: OOMPAH-929
type: task
status: Backlog
priority: null
title: Rearm superseded durable events on newer source generations
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T02:47:20.781959Z'
updated_at: '2026-08-09T02:47:20.781959Z'
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

