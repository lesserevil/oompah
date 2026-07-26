---
id: OOMPAH-356
type: epic
status: Merged
priority: 1
title: Reduce unfinished epic branch synchronization churn
parent: null
children:
- OOMPAH-357
- OOMPAH-358
- OOMPAH-359
blocked_by: []
labels:
- reliability
- workflow
assignee: null
created_at: '2026-07-22T01:23:32.887223Z'
updated_at: '2026-07-26T00:27:41.503331Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
merged_at: null
---
## Summary

Change Oompah's branch-maintenance policy so incomplete epic branches do not receive routine merges or rebases from main, and never synchronize directly with other epic branches. Integration must occur through main. Rebase work is permitted only for an actionable condition: preparing or refreshing an epic PR, a merge-blocking conflict, an explicit user request, or a configured long-lived/stale branch threshold. Default behavior must detect and surface staleness without changing the branch.\n\nAcceptance criteria:\n- No automatic main-to-epic merge/rebase occurs merely because main advanced.\n- No epic-to-epic merge/rebase is scheduled.\n- The UI/API exposes detected branch staleness and the actionable reason for any scheduled rebase.\n- Existing projects migrate to the conservative default without configuration changes.\n- Child tasks implement policy, scheduling, and test coverage.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-07-22 01:30
---
Completed, tested, pushed, and restarted the conservative epic synchronization policy.
---
author: oompah
created: 2026-07-26 00:27
---
Delivery reconciled: the conservative unfinished-epic synchronization policy is present on origin/main in commit 2ba37886b. This task was Done rather than waiting for an agent; it is now being aligned with the delivered repository state.
---
<!-- COMMENTS:END -->
