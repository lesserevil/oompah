---
id: OOMPAH-940
type: epic
status: In Progress
priority: 1
title: Converge the legacy Done backlog from authoritative delivery evidence
parent: null
children:
- OOMPAH-941
- OOMPAH-942
- OOMPAH-943
- OOMPAH-944
- OOMPAH-945
- OOMPAH-954
- OOMPAH-955
- OOMPAH-956
- OOMPAH-958
blocked_by:
- OOMPAH-939
start_blocked_by: []
labels: []
assignee: null
created_at: '2026-08-09T09:08:16.594615Z'
updated_at: '2026-08-09T13:40:17.483871Z'
work_branch: null
target_branch: null
review_url: null
review_number: null
review_head: null
merged_at: null
---
## Summary

Triggered by: OOMPAH-935 and OOMPAH-937\n\nThe live all-enforce rollout now has zero current liveness divergence, but 185 Oompah tasks remain in Done and generation 260 still reports 97 actionable exhausted jobs. Production evidence divides the residual backlog into independent authority gaps: authorized owner-delivery provenance is ignored, terminal parent branches were pruned without a trusted accepted-head fallback, successful landing refresh effects are not durably fed back, epic cleanup uses a separate child-proof path, and terminal transition guards can contradict an exact-current terminal work decision. Decompose and deliver the child bugs without direct database edits or broad status overrides.\n\nScope: make the workflow fact, action, transition, and cleanup paths share durable exact evidence and one current authority decision; preserve immutable history, bounded scheduling, pause semantics, and fail-closed behavior. Required rollout verification: complete scan, zero current divergence, zero current exhausted jobs or an explicitly non-task system owner, no repeated successful landing refreshes, no contradictory terminal guard decisions, and natural topology-safe movement of the legacy Done backlog. Required tests: focused unit/integration/restart regressions for each child plus complete protected branch gates and a live rollout canary. Acceptance: all children and OOMPAH-939 land; the Oompah project has no erroneously stuck non-terminal task and the workflow rollout check passes.

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
created: 2026-08-09 13:40
---
Refreshed the systemic workflow epic onto composition merge 91bf64c57 at exact branch head 2dd74be288b81265ea4a242d7467ecc1ed9f1435. Resolved the workflow-worker/runtime seams while preserving atomic landing completion, restart-safe transition finalization, exact containment authority, and canonical runtime fact composition. Validation: 159 workflow/runtime/finalization tests, 202 integration/epic/decision tests, 8 targeted composed-seam tests, and terminal mutation scan all passed. PR #757 hosted matrix is refreshing; a final small main refresh will follow OOMPAH-957.
---
<!-- COMMENTS:END -->
