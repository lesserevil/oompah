---
id: OOMPAH-945
type: bug
status: Open
priority: 1
title: Unify terminal transition guards with exact-current work decisions
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:46.122749Z'
updated_at: '2026-08-09T09:11:17.354717Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Complete liveness generation 260 projects OOMPAH-476 and OOMPAH-763 as disposition=terminal with reason terminal.immediate_target_landing_proven and zero divergence, yet set-status Merged rejects the child because its parent cannot be verified and rejects the epic because immediate-target evidence no longer authorizes auto-close. Scope: remove the semantic drift between decision projection and mutation guard by carrying/verifying an exact current decision/evidence generation through TaskTransitionService/owner override and automatic rollup. A terminal decision must either be executable under the same authority or must not be published as terminal. Preserve topology ordering, stale-generation fencing, owner authentication, and fail-closed unknown evidence. Tests: child/epic cases above, decision changes between evaluation and commit, parent-not-yet-landed sequencing, malicious/stale decision injection, and restart. Acceptance: exact-current terminal decisions apply once or return an explicit stale retry—not a contradictory policy rejection—and non-terminal decisions cannot bypass guards.

## Acceptance Criteria

- [ ] Define acceptance criteria.

## Notes

## Comments
<!-- COMMENTS:BEGIN -->
author: oompah
created: 2026-08-09 09:10
---
Accepted for direct-owner completion as part of the live legacy Done-backlog convergence program.
---
author: oompah
created: 2026-08-09 09:11
---
Accepted for direct-owner completion as part of the live legacy Done-backlog convergence program.
---
<!-- COMMENTS:END -->
