---
id: OOMPAH-931
type: bug
status: In Progress
priority: 1
title: Retire repaired exhausted workflow generations
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T04:24:02.309459Z'
updated_at: '2026-08-09T04:32:29.676891Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Rollout of exact head d8610fbdc reproduced a durable-health deadlock: materialize_event correctly created a newer active generation for an equal semantic event after a newer source cut, but the replaced historical job remained in exhausted state. WorkflowJobStore.health_snapshot therefore continued reporting exhausted=1 and workflow_rollout_check could never turn green despite a queued replacement owning recovery. Update oompah/workflow_jobs.py so activation of an exact replacement generation atomically retires older exhausted rows in the selected event lanes without mutating the current exhausted row when no replacement exists. Preserve append-only job-event history and idempotent replay semantics. Add regression tests in tests/test_workflow_jobs.py for exhausted replacement, completed/cancelled/superseded terminal variants, same-source replay, restart/idempotence, and health_snapshot exhausted count. Acceptance: the prior exhausted row becomes superseded only when a distinct current generation owns recovery; the replacement remains queued/active; repeated materialization is stable; genuine current exhaustion stays visible; focused tests and the complete make test gate pass; staged all-enforce rollout reaches fresh complete healthy liveness with zero exhausted/expired jobs and no actionable alerts.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 04:32
---
Focused regression and affected-module verification passed (20 serial tests; 243 parallel tests). Design correction: preserve exhausted rows as immutable ledger history and add an authoritative current_states.exhausted health projection; rollout canary uses current_states with fail-closed fallback to raw states for older servers. This clears only history proven replaced by durable schedule/event authority and leaves genuine current or unknown exhaustion actionable.
---
<!-- COMMENTS:END -->
