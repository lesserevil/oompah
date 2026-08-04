---
id: OOMPAH-806
type: bug
status: Open
priority: 1
title: Fence stalled-task recovery behind internal gate authority
parent: OOMPAH-763
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-04T20:44:00.064452Z'
updated_at: '2026-08-04T20:44:10.764626Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Live reproduction on 2026-08-04: OOMPAH-793's exact-head combined-tree integration gate failed at ef5e8c30e (integration row blocked; task Needs CI Fix). Minutes later the stalled-task watchdog observed unrelated passing external commit CI, reopened the task to Open, and the integration reconciler cancelled the blocked row because tracker state was Open. This discarded the authoritative internal gate failure and could expose completed implementation to duplicate dispatch; only an existing direct-owner lease prevented churn. Implementation scope: make current internal integration/gate records and exact-head authority outrank generic forge CI when classifying Needs CI Fix/Ready to Integrate; never reopen or cancel a blocked integration generation based solely on external CI for the same or another check suite; require a newer pushed head, explicit same-generation integration retry, or authoritative repair evidence; serialize watchdog and integration transitions through TaskTransitionService with generation CAS; keep actionable blocked evidence visible to UI/liveness. Relevant code: oompah/stalled_task_watchdog.py, orchestrator watchdog evidence/action plumbing, integration queue reconciliation/executor, TaskTransitionService, and state/alert projections. Required deterministic tests: reproduce blocked combined-tree gate plus passing external CI; watchdog performs no Open transition and row remains blocked; newer repaired head may reopen/resubmit exactly once; race watchdog vs gate completion has one generation winner; restart preserves precedence; unrelated project/task CI cannot influence it; direct-owner absence still cannot cause duplicate implementation dispatch. Acceptance: an internal failed gate remains authoritative until repaired or explicitly retried, watchdog recovery cannot cancel or regress its integration generation, and OOMPAH-793-style churn cannot recur.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

