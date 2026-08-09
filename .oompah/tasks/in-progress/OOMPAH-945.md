---
id: OOMPAH-945
type: bug
status: In Progress
priority: 1
title: Unify terminal transition guards with exact-current work decisions
parent: OOMPAH-940
children: []
blocked_by: []
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:46.122749Z'
updated_at: '2026-08-09T09:27:06.177511Z'
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
author: oompah
created: 2026-08-09 09:25
---
Implemented the two reproduced authority splits in the isolated OOMPAH-945 worktree. Terminal API ownership refresh now restores the canonical native-tracker project scope and rejects explicit cross-project refreshes before staging. Done-epic decisions and lifecycle guards now share one containment-derived immediate-target landing selector, so child landings cannot falsely authorize epic auto-close when task branch metadata is absent. Focused decision/API/runtime/epic/integration/transition/audit coverage is green: 826 passed. Terminal mutation scan and secret scan pass; preparing the exact commit for publication.
---
author: oompah
created: 2026-08-09 09:27
---
Exact implementation commit 395ce9938 is pushed on origin/OOMPAH-945 and the worktree is clean/up to date. Normal  was attempted and correctly failed closed because the declared immediate target origin/epic-OOMPAH-940 is not yet published. No main-target PR or topology bypass was created. Resubmit after the parent epic target is published/composed.
---
<!-- COMMENTS:END -->
