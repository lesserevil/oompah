---
id: OOMPAH-960
type: bug
status: Open
priority: 1
title: Consume parent-scoped canonical child landing facts
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels:
- human-only
assignee: null
created_at: '2026-08-09T14:20:14.654158Z'
updated_at: '2026-08-09T14:35:27.783690Z'
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

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 14:22
---
Direct-owner implementation started in isolated worktree /home/shedwards/src/oompah-960 on branch OOMPAH-960. I am adding fail-closed parent-scoped child landing evidence composition and focused route/source/revision/current-containment/restart regressions; no service mutation or deployment. The Open to In Progress CLI transition was correctly rejected because the workflow generation is required, so implementation proceeds under the explicit owner assignment while preserving tracker fencing.
---
author: oompah
created: 2026-08-09 14:35
---
Implemented fail-closed parent-scoped canonical child landing consumption in the isolated OOMPAH-960 worktree. A Done child now imports only one durable LANDED fact owned by its current parent epic when current direct containment, project, exact route, source, and any named revision agree; the Git collector still revalidates current target history, and the parent fact remains parent-owned across restart. Validation so far: 113 integration workflow tests passed; 91 epic workflow/adapter tests passed; terminal mutation scan and paranoid secret scan passed. Preparing the review-ready commit and push; no service mutation or deployment.
---
<!-- COMMENTS:END -->
