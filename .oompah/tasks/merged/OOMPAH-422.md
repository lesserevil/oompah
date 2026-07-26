---
id: OOMPAH-422
type: bug
status: Merged
priority: 1
title: Require actionable handoffs for Needs Human transitions
parent: null
children: []
blocked_by: []
labels: []
assignee: null
created_at: '2026-07-23T20:10:29.633604Z'
updated_at: '2026-07-26T00:28:42.434203Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Enforce the tracker invariant that every transition to Needs Human is followed by a final oompah comment containing actionable human instructions or one or more explicit questions. Route all orchestrator transition paths through the shared helper and reject empty/non-actionable handoffs at the tracker boundary. Add native-tracker, GitHub-tracker, and orchestration regression tests that verify the final comment is the required human handoff. Run make test.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-23 20:13
---
Implemented tracker-boundary validation for Needs Human handoffs, routed all orchestrator transition paths through the shared handoff helper, and added native/GitHub regression coverage. Full make test passed. Live audit found zero tasks currently in Needs Human.
---
author: oompah
created: 2026-07-23 20:13
---
Enforced actionable final handoffs for Needs Human and verified the suite.
---
author: oompah
created: 2026-07-26 00:28
---
Delivery reconciled: actionable Needs Human handoff enforcement is present on origin/main in commit 296895829. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
<!-- COMMENTS:END -->
