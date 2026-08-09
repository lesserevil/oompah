---
id: OOMPAH-960
type: bug
status: Backlog
priority: 1
title: Consume parent-scoped canonical child landing facts
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T14:20:14.654158Z'
updated_at: '2026-08-09T14:20:14.654158Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Fix integration/Done decision evidence composition so a child task can consume its parent epic scoped canonical landing fact when that fact names the child as its source. Current production evidence shows at least 23 Done tasks have exact durable LANDED facts under the parent task_id but IntegrationLandingRequestResolver and IntegrationWorkflowController only read facts under the child task_id, causing false retry.exhausted decisions. Scope the change to the landing fact resolver/controller and durable fact queries; import only route-bound, source-matching, revision-current facts and preserve fail-closed behavior for ambiguous, stale, foreign-project, or non-contained evidence. Add regression tests for accepted parent-scoped child proof, stale/wrong-source/wrong-route rejection, current target containment, restart persistence, and no regression to epic cleanup composition. Acceptance: the 23 known affected tasks converge without operator reconstruction after deployment, no ambiguous evidence is promoted, focused tests and the configured branch gate pass.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

